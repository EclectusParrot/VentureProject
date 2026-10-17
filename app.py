import json
import re
import sqlite3
import sys
import threading
from datetime import datetime

from flask import Flask, jsonify, send_from_directory
from pydantic import ValidationError

from emailManagement import accessEmails, markProcessed
from triage import Ticket, triage  # loads the models once at startup

DB = "emailsUsers.db"
app = Flask(__name__, static_folder="static")

state = {"running": False, "error": None, "last_run": None, "last_count": 0}
state_lock = threading.Lock()

# makeDatabases.py stores subscriptionTier as a one-character code (e.g. '3').
# triage.py's rules use tier NAMES, so translate here.
# EDIT THIS to match what your codes actually mean.
TIER_NAMES = {"1": "free", "2": "pro", "3": "premium", "4": "business", "5": "enterprise"}

# Messages that mention self-harm must never be auto-routed or discarded,
# whatever the model thinks of the rest of the email.
CRISIS_PATTERN = re.compile(
    r"\b(kill(ing)? myself|end(ing)? my (own )?life|take my own life|commit(ting)? suicide|"
    r"suicid\w*|want(ed)? to die|don'?t want to (live|be alive)|"
    r"hurt(ing)? myself|harm(ing)? myself|self[- ]?harm|better off dead)\b",
    re.I,
)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def check_db():
    """Fail early with a clear message if makeDatabases.py hasn't been run."""
    con = db()
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    missing = {"email_tbl", "user_tbl"} - tables
    if missing:
        sys.exit(f"{DB} is missing {sorted(missing)}. Run 'python makeDatabases.py' first.")


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS triage_results (
            ticket_id TEXT PRIMARY KEY,
            sender TEXT, subject TEXT, body TEXT,
            tier TEXT, emails_sent INTEGER,
            category TEXT, category_pct INTEGER,
            risk TEXT, risk_pct INTEGER, risk_breakdown TEXT,
            sentiment TEXT, route TEXT, reasons TEXT,
            triaged_at TEXT
        )
    """)
    # makeDatabases.py drops and rebuilds email_tbl but knows nothing about this table,
    # so tidy up results whose email no longer exists.
    con.execute("DELETE FROM triage_results WHERE ticket_id NOT IN (SELECT ticketID FROM email_tbl)")
    con.commit()
    con.close()


def normalise(raw: dict) -> dict:
    """Map the makeDatabases.py column names onto what triage.py's Ticket expects."""
    item = dict(raw)
    item.setdefault("subject", item.get("emailTitle") or "")  # column is emailTitle
    code = str(item.get("subscriptionTier") or "").strip()
    item["subscriptionTier"] = TIER_NAMES.get(code, code or "free")
    item["emailsSent"] = item.get("emailsSent") or 0  # NULL-safe
    return item


def apply_safety_override(ticket, result):
    """Force self-harm language to a human, overriding the model and any discard rule."""
    text = f"{ticket.subject or ''} {ticket.body or ''}"
    if not CRISIS_PATTERN.search(text):
        return result
    return result.model_copy(update={
        "risk": "high",
        "risk_pct": 100,
        "risk_breakdown": {"low": 0, "medium": 0, "high": 100},
        "route": "human_queue",
        "reasons": ["SAFETY RULE: possible self-harm language, escalate to a human "
                    "immediately (overrides the model)"] + list(result.reasons),
    })


def save_result(ticket, result, sender_label):
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO triage_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            result.ticket_id, sender_label, ticket.subject or "", ticket.body or "",
            result.tier, ticket.emails_sent,
            result.category, result.category_pct,
            result.risk, result.risk_pct, json.dumps(result.risk_breakdown),
            result.sentiment, result.route, json.dumps(result.reasons),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    con.commit()
    con.close()


def run_job():
    try:
        emails = json.loads(accessEmails())
        done = 0
        for raw in emails:
            try:
                item = normalise(raw)
                ticket = Ticket.model_validate(item)
                result = apply_safety_override(ticket, triage(ticket))
                sender = item.get("senderEmail") or ticket.sender
                save_result(ticket, result, sender)
                markProcessed(ticket.id)  # only after triage and save succeeded
                done += 1
            except ValidationError as e:
                print("Skipped email, bad fields:", [err["loc"] for err in e.errors()])
            except Exception as e:
                print("Skipped email, error:", e)
        with state_lock:
            state["last_count"] = done
            state["error"] = None
    except Exception as e:
        with state_lock:
            state["error"] = str(e)
    finally:
        with state_lock:
            state["running"] = False
            state["last_run"] = datetime.now().strftime("%H:%M:%S")


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/tickets")
def tickets():
    # Only show results whose email is still marked processed, so re-running
    # makeDatabases.py (which resets email_tbl) never leaves stale rows on screen.
    con = db()
    rows = con.execute("""
        SELECT r.* FROM triage_results r
        JOIN email_tbl e ON e.ticketID = r.ticket_id
        WHERE e.processedBool = 1
        ORDER BY r.triaged_at DESC
    """).fetchall()
    con.close()
    out = []
    for r in rows:
        d = dict(r)
        d["risk_breakdown"] = json.loads(d["risk_breakdown"] or "{}")
        d["reasons"] = json.loads(d["reasons"] or "[]")
        out.append(d)
    return jsonify(out)


@app.get("/api/status")
def status():
    con = db()
    pending = con.execute("SELECT COUNT(*) FROM email_tbl WHERE processedBool = 0").fetchone()[0]
    con.close()
    with state_lock:
        return jsonify({**state, "pending": pending})


@app.post("/api/triage")
def start_triage():
    with state_lock:
        if state["running"]:
            return jsonify({"started": False, "reason": "already running"}), 409
        state["running"] = True
        state["error"] = None
    threading.Thread(target=run_job, daemon=True).start()
    return jsonify({"started": True})


@app.post("/api/reset")
def reset():
    """Demo helper: mark every email unprocessed again and clear saved results."""
    con = db()
    con.execute("UPDATE email_tbl SET processedBool = 0")
    con.execute("DELETE FROM triage_results")
    con.commit()
    con.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    check_db()
    init_db()
    app.run(debug=False, port=5000)
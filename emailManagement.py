import sqlite3 as sql
import json
import hashlib
from mailFetcher import getNewMail

def _short_id(text):
    return hashlib.sha1(text.encode()).hexdigest()[:8]

def accessEmails():
    try:
        addNewMailDB(getNewMail())
    except Exception as e:
        print("Mail fetch failed, using emails already in the database:", e)

    con = sql.connect("emailsUsers.db")
    con.row_factory = sql.Row
    rows = con.execute("""
        SELECT email_tbl.*, user_tbl.subscriptionTier, user_tbl.emailsSent
        FROM email_tbl
        INNER JOIN user_tbl ON user_tbl.senderID = email_tbl.senderID
        WHERE processedBool = 0""").fetchall()
    con.close()
    return json.dumps([dict(r) for r in rows])

def markProcessed(email_id):
    con = sql.connect("emailsUsers.db")
    con.execute("UPDATE email_tbl SET processedBool = 1 WHERE ticketID = ?", (email_id,))
    con.commit()
    con.close()

def addNewMailDB(listOfMail):
    con = sql.connect("emailsUsers.db")
    try:
        for m in listOfMail:
            row = con.execute("SELECT senderID FROM user_tbl WHERE senderEmail = ?",
                              (m["Sender"],)).fetchone()
            sender_id = row[0] if row else _short_id(m["Sender"])
            email_id = _short_id(m["Sender"] + m["Subject"] + m["Body"])

            cur = con.execute("INSERT OR IGNORE INTO email_tbl VALUES (?,?,?,0,?)",
                              (email_id, m["Subject"], m["Body"], sender_id))
            if cur.rowcount == 0:        # already seen this email
                continue
            if row:
                con.execute("UPDATE user_tbl SET emailsSent = emailsSent + 1 WHERE senderID = ?",
                            (sender_id,))
            else:
                con.execute("INSERT INTO user_tbl VALUES (?,?,?,?)",
                            (sender_id, m["Sender"], "2", 1))
        con.commit()
    finally:
        con.close()
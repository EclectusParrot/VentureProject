import json
import re
from dataclasses import dataclass, asdict
from transformers import pipeline
from STANDIN import accessEmails
from pydantic import BaseModel, Field, ConfigDict, ValidationError

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
sentiment_model = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)

CATEGORIES = ["billing", "technical issue", "account access", "sales inquiry", "spam"]
URGENT_WORDS = ["urgent", "asap", "outage", "down", "charged twice", "legal", "immediately"]

RISK_LABELS = {
    "a routine low risk email": "low",
    "a medium risk email that needs attention": "medium",
    "a high risk urgent email": "high",
}
URGENT_PATTERN = re.compile(
    r"\b(urgent|asap|outage|down|charged twice|legal|immediately)\b", re.I
)

class Ticket(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)

    id: str
    sender: str = Field(alias="from")
    subject: str
    body: str

class TriageResult(BaseModel):
    ticket_id: str
    category: str
    category_pct: int      # how sure it is about the category
    risk: str              # low / medium / high
    risk_pct: int          # how sure it is about the risk level
    risk_breakdown: dict   # e.g. {"low": 94, "medium": 5, "high": 1}
    sentiment: str
    route: str

def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)

def triage(ticket: Ticket) -> TriageResult:
    text = clean(f"{ticket.subject}. {ticket.body}")[:1500]

    # Category + confidence
    cat = classifier(text, CATEGORIES)
    category, cat_conf = cat["labels"][0], cat["scores"][0]

    # Risk level + confidence (scores sum to 1 across the three levels)
    out = classifier(text, list(RISK_LABELS), hypothesis_template="This email is {}.")
    scores = {RISK_LABELS[l]: s for l, s in zip(out["labels"], out["scores"])}

    # Keyword nudge: urgent wording pushes probability toward "high"
    if URGENT_PATTERN.search(text):
        scores["high"] += 0.3
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}

    risk = max(scores, key=scores.get)
    risk_conf = scores[risk]

    sent = sentiment_model(text, truncation=True)[0]
    sentiment = sent["label"].lower()

    # Routing: low confidence goes to a human, whatever the label
    if category == "spam" and cat_conf > 0.6:
        route = "discard"
    elif risk == "high" or risk_conf < 0.6 or cat_conf < 0.4:
        route = "human_queue"
    elif category == "billing":
        route = "billing_team"
    elif category == "technical issue":
        route = "tech_support"
    else:
        route = "general_queue"

    return TriageResult(
        ticket_id=ticket.id,
        category=category,
        category_pct=round(cat_conf * 100),
        risk=risk,
        risk_pct=round(risk_conf * 100),
        risk_breakdown={k: round(v * 100) for k, v in scores.items()},
        sentiment=sentiment,
        route=route,
    )

def run_triage():
    emails = accessEmails()
    print(f"Fetched {len(emails)} unprocessed emails")

    results = []
    for i, item in enumerate(emails):
        try:
            ticket = (Ticket.model_validate_json(item) if isinstance(item, str)
                      else Ticket.model_validate(item))
            result = triage(ticket)
            results.append(result)
            print(result.model_dump_json())
        except ValidationError as e:
            print(f"Email #{i}: invalid email ({e.error_count()} problems): {e.errors()[0]['loc']}")
        except Exception as e:
            print(f"Email #{i}: unexpected error ({e})")

    print(f"[{result.ticket_id}] {result.risk_pct}% sure: {result.risk} risk | "f"{result.category_pct}% sure: {result.category} -> {result.route}")
    return results

if __name__ == "__main__":
    run_triage()
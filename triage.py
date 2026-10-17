import json
from dataclasses import dataclass, asdict
from transformers import pipeline

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
sentiment_model = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)

CATEGORIES = ["billing", "technical issue", "account access", "sales inquiry", "spam"]
URGENT_WORDS = ["urgent", "asap", "outage", "down", "charged twice", "legal", "immediately"]

@dataclass
class Ticket:
    id: str
    sender: str
    subject: str
    body: str

    @classmethod
    def from_dict(cls, d: dict):
        # Manual validation instead of pydantic
        for key in ("id", "from", "subject", "body"):
            if key not in d or not isinstance(d[key], str):
                raise ValueError(f"missing or invalid field: {key}")
        return cls(id=d["id"], sender=d["from"], subject=d["subject"], body=d["body"])

@dataclass
class TriageResult:
    ticket_id: str
    category: str
    category_confidence: float
    sentiment: str
    priority: str
    route: str

def triage(ticket: Ticket) -> TriageResult:
    text = f"{ticket.subject}. {ticket.body}"[:1500]

    cat = classifier(text, CATEGORIES)
    category, conf = cat["labels"][0], cat["scores"][0]

    sent = sentiment_model(text, truncation=True)[0]
    sentiment = sent["label"].lower()  # "positive" / "negative"

    # Priority: keyword rules + sentiment
    lowered = text.lower()
    if any(w in lowered for w in URGENT_WORDS):
        priority = "urgent"
    elif sentiment == "negative" and sent["score"] > 0.9:
        priority = "high"
    else:
        priority = "normal"

    # Routing: plain Python rules
    if category == "spam" and conf > 0.6:
        route = "discard"
    elif priority == "urgent" or conf < 0.4:
        route = "human_queue"
    elif category == "billing":
        route = "billing_team"
    elif category == "technical issue":
        route = "tech_support"
    else:
        route = "general_queue"

    return TriageResult(ticket.id, category, round(conf, 2), sentiment, priority, route)

if __name__ == "__main__":
    with open("tickets.json") as f:
        raw = json.load(f)

    for item in raw:
        try:
            result = triage(Ticket.from_dict(item))
            print(json.dumps(asdict(result)))
        except ValueError as e:
            print(f"Skipping {item.get('id')}: {e}")
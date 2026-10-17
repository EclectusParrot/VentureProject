import json
import re
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, ValidationError
from transformers import pipeline
from emailManagement import accessEmails, markProcessed

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
sentiment_model = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)

CATEGORIES = ["billing", "technical issue", "account access", "sales inquiry", "spam"]
RISK_LABELS = {
    "a routine low risk email": "low",
    "a medium risk email that needs attention": "medium",
    "a high risk urgent email": "high",
}
URGENT_PATTERN = re.compile(
    r"\b(urgent|asap|outage|down|charged twice|legal|immediately)\b", re.I
)
PRIORITY_TIERS = {"pro", "premium", "business", "enterprise"}  # match your tier names


class Ticket(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)

    id: str = Field(validation_alias=AliasChoices("emailID", "email_id", "id"))
    sender: str = Field(validation_alias=AliasChoices("senderEmail", "from"))
    subject: str | None = ""
    body: str | None = Field(
        default="",
        validation_alias=AliasChoices("body", "emailBody", "content", "message", "text"),
    )
    tier: str = Field(default="free", validation_alias=AliasChoices("subscriptionTier"))
    emails_sent: int = Field(default=0, validation_alias=AliasChoices("emailsSent"))


class TriageResult(BaseModel):
    ticket_id: str
    sender: str
    tier: str
    category: str
    category_pct: int
    risk: str
    risk_pct: int
    risk_breakdown: dict
    sentiment: str
    route: str


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def triage(ticket: Ticket) -> TriageResult:
    text = clean(f"{ticket.subject or ''}. {ticket.body or ''}")[:1500]

    cat = classifier(text, CATEGORIES)
    category, cat_conf = cat["labels"][0], cat["scores"][0]

    out = classifier(text, list(RISK_LABELS), hypothesis_template="This email is {}.")
    scores = {RISK_LABELS[l]: s for l, s in zip(out["labels"], out["scores"])}

    if URGENT_PATTERN.search(text):
        scores["high"] += 0.3
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}

    risk = max(scores, key=scores.get)
    risk_conf = scores[risk]

    sentiment = sentiment_model(text, truncation=True)[0]["label"].lower()

    priority_customer = ticket.tier.lower() in PRIORITY_TIERS

    if category == "spam" and cat_conf > 0.6:
        route = "discard"
    elif risk == "high" or risk_conf < 0.6 or cat_conf < 0.4:
        route = "human_queue"
    elif priority_customer and risk != "low":
        route = "priority_queue"
    elif category == "billing":
        route = "billing_team"
    elif category == "technical issue":
        route = "tech_support"
    else:
        route = "general_queue"

    return TriageResult(
        ticket_id=ticket.id,
        sender=ticket.sender,
        tier=ticket.tier,
        category=category,
        category_pct=round(cat_conf * 100),
        risk=risk,
        risk_pct=round(risk_conf * 100),
        risk_breakdown={k: round(v * 100) for k, v in scores.items()},
        sentiment=sentiment,
        route=route,
    )


def run_triage():
    emails = json.loads(accessEmails())  # one JSON string -> list of dicts
    print(f"Fetched {len(emails)} unprocessed emails")

    results = []
    for i, item in enumerate(emails):
        try:
            ticket = Ticket.model_validate(item)
            result = triage(ticket)
            results.append(result)
            print(f"[{result.ticket_id}] {result.risk_pct}% sure: {result.risk} risk | "
                  f"{result.category_pct}% sure: {result.category} | "
                  f"{result.tier} -> {result.route}")
            markProcessed(ticket.id)  # only after triage succeeded
        except ValidationError as e:
            missing = [".".join(map(str, err["loc"])) for err in e.errors()]
            print(f"Email #{i}: bad fields {missing}")
        except Exception as e:
            print(f"Email #{i}: unexpected error ({e})")
    return results


if __name__ == "__main__":
    run_triage()
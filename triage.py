import json
import re
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, ValidationError
from transformers import pipeline
from emailManagement import accessEmails, markProcessed
from mailFetcher import getNewMail

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
PRIORITY_TIERS = {"pro", "premium", "business", "enterprise"}
TIER_RISK_BOOST = {"free": 0.0, "pro": 0.05, "premium": 0.1, "business": 0.1, "enterprise": 0.15}
SPAM_VOLUME = 200
HEAVY_USER = 50 


class Ticket(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)

    id: str = Field(validation_alias=AliasChoices("ticketID", "email_id", "id"))
    sender: str = Field(validation_alias=AliasChoices("senderID", "from"))
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
    reasons: list[str] = []


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def apply_context(scores: dict, ticket: Ticket, category: str) -> tuple[dict, list[str]]:
    """Shift risk probabilities using account context. Returns new scores plus the reasons."""
    reasons = []
    tier = ticket.tier.lower()

    # Paying customers: unhappy ones matter more, so push toward medium/high
    boost = TIER_RISK_BOOST.get(tier, 0.0)
    if boost and category != "spam":
        scores["low"] = max(scores["low"] - boost, 0.0)
        scores["medium"] += boost
        reasons.append(f"{tier} tier (+{int(boost*100)}% risk weight)")

    # Very high volume from a free account: likely spam/abuse, treat as higher risk
    if tier == "free" and ticket.emails_sent > SPAM_VOLUME:
        scores["high"] += 0.2
        reasons.append(f"free account with {ticket.emails_sent} emails sent")
    elif ticket.emails_sent > HEAVY_USER and category == "spam":
        scores["high"] += 0.1
        reasons.append("high volume + spam-like content")

    total = sum(scores.values())
    return {k: v / total for k, v in scores.items()}, reasons

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

    scores, reasons = apply_context(scores, ticket, category)
    risk = max(scores, key=scores.get)
    risk_conf = scores[risk]

    sentiment = sentiment_model(text, truncation=True)[0]["label"].lower()

    priority_customer = ticket.tier.lower() in PRIORITY_TIERS

    if category == "spam" and cat_conf > 0.6:
        route = "discard"
    elif risk == "high" or cat_conf < 0.4:
        route = "human_queue"
    elif risk_conf < (0.75 if priority_customer else 0.6):
        route = "human_queue"   # paying customers get human review sooner when the model is unsure
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
        reasons=reasons,
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
                    f"{result.category_pct}% sure: {result.category} | {result.tier} -> {result.route} "
                    f"{result.reasons}")
            markProcessed(ticket.id)  # only after triage succeeded
        except ValidationError as e:
            missing = [".".join(map(str, err["loc"])) for err in e.errors()]
            print(f"Email #{i}: bad fields {missing}")
        except Exception as e:
            print(f"Email #{i}: unexpected error ({e})")
    return results


if __name__ == "__main__":
    run_triage()
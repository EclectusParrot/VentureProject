import json

SAMPLE_EMAILS = [
    {"id": "1001", "from": "angry.customer@example.com",
     "subject": "Charged twice!!",
     "body": "I was charged twice for my subscription this month. Fix this immediately or I'm contacting my bank."},
    {"id": "1002", "from": "jane@startup.io",
     "subject": "Pricing for 50 seats",
     "body": "Hi, we're interested in your team plan. Could you send over pricing for 50 seats?"},
    {"id": "1003", "from": "promo@win-big-now.biz",
     "subject": "You've won a prize",
     "body": "Click here to claim your free gift card now."},
    {"id": "1004", "from": "sam@example.com",
     "subject": "Can't log in",
     "body": "I reset my password but I still can't get into my account. Any ideas?"},
    {"id": "1005", "from": "pat@example.com",
     "subject": "Thanks!",
     "body": "Just wanted to say the new dashboard is great. Keep it up."},
]

def accessEmails() -> list[str]:
    return [json.dumps(e) for e in SAMPLE_EMAILS]
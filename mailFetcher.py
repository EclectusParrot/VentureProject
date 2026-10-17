import poplib
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr

def getNewMail():
    with open("password.txt") as f:
        password = f.read().strip()

    box = poplib.POP3_SSL("pop.gmail.com", 995)
    box.user("teamtelevisionteam@gmail.com")
    box.pass_(password)
    mail = []
    try:
        for i in range(1, len(box.list()[1]) + 1):
            raw = b"\r\n".join(box.retr(i)[1])
            msg = BytesParser(policy=policy.default).parsebytes(raw)
            part = msg.get_body(preferencelist=("plain", "html"))
            body = part.get_content() if part else ""
            mail.append({
                "Subject": msg["Subject"] or "",
                "Sender": parseaddr(msg["From"] or "")[1],
                "Body": body.strip(),
            })
    finally:
        box.quit()
    return mail
import poplib as pl
#import rfc822
from email import policy
from email.parser import BytesParser

def getNewMail():
    newMail = []
    route = open("password.txt")
    password = route.read()
    route.close()
    ourmail = pl.POP3_SSL('pop.googlemail.com', '995')
    ourmail.user('teamtelevisionteam')
    ourmail.pass_(password)
    for i in range(len(ourmail.list()[1])):
        for thingy in ourmail.retr(i+1)[1]:
            part = BytesParser(policy=policy.default).parsebytes(thingy)
            if "Subject" in part:
                subject = part.as_string().strip().replace("Subject: ", "")
            if "From" in part:
                temp1 = part.as_string().find("<")
                temp2 = part.as_string().find(">")
                sender = part.as_string()[temp1+1:temp2]
            if "div dir" in part.as_string():
                body = part.as_string().strip().replace('<div dir="ltr">', '').replace('</div>', '').replace('<div>', '\n')
        newMail.append({"Subject": subject, "Sender": sender, "Body": body})
    ourmail.quit()
    return(newMail)
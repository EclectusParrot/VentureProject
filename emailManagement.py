import sqlite3 as sql
import json

def accessEmails():
    con = sql.connect("emailsUsers.db")
    con.row_factory = sql.Row
    cur = con.cursor()
    ## make json for thingy in select all from emails inner join
    newEmails = cur.execute("""SELECT email_tbl.*, user_tbl.subscriptionTier, user_tbl.emailsSent FROM email_tbl INNER JOIN user_tbl ON user_tbl.senderID = email_tbl.senderID WHERE (processedBool = 0)""")
    temp = json.dumps([dict(i) for i in newEmails.fetchall()])
    con.close()
    return temp

#print(accessEmails())

def markProcessed(email_id):
    con = sql.connect("emailsUsers.db")
    cur = con.cursor()
    cur.execute("UPDATE email_tbl SET processedBool = 1 WHERE senderID = ?", (email_id,))
    con.commit()
    con.close()

if __name__ == "__main__":
    print(accessEmails())
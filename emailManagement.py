import sqlite3 as sql
import json

def accessEmails():
    con = sql.connect("emailsUsers.db")
    con.row_factory = sql.Row
    cur = con.cursor()
    ## make json for thingy in select all from emails inner join
    newEmails = cur.execute("""SELECT email_tbl.*, user_tbl.subscriptionTier, user_tbl.emailsSent FROM email_tbl INNER JOIN user_tbl ON user_tbl.senderID = email_tbl.senderID WHERE (processedBool = 0)""")
    return json.dumps([dict(i) for i in newEmails.fetchall()])

#print(accessEmails())
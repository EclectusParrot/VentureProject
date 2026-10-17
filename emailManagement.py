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
    cur.execute("UPDATE email_tbl SET processedBool = 1 WHERE ticketID = ?", (email_id,))
    print([i for i in cur.execute("SELECT * FROM email_tbl")])
    con.commit()
    con.close()

def addNewMailDB(listOfMail):
    for i in listOfMail:
        con = sql.connect("emailsUsers.db")
        cur = con.cursor()
        #MAKE NEW USER IN TABLE IF NEEDED, ELSE INCREMEMNT EMAILSENT
        ### Check if email in userTable
        sendID = cur.execute("SELECT senderID FROM user_tbl WHERE senderEmail = ?", (i["Sender"],)).fetchall()
        if sendID == []:
            sendID = [(str(hash(i["Sender"]))[1:9],)]
            cur.execute("INSERT INTO user_tbl VALUES (?, ?, ?, ?)", (sendID[0][0], i["Sender"], "2", "1",))
        else:
            numEmails = cur.execute("SELECT emailsSent FROM user_tbl WHERE senderEmail = ?", (i["Sender"],)).fetchall()[0][0]
            cur.execute("UPDATE user_tbl SET emailsSent = ? WHERE senderEmail = ?", (str(int(numEmails)+1), i["Sender"],))
        emailID = str(hash(i["Body"]))[1:9]
        cur.execute("""INSERT INTO email_tbl VALUES (?,?,?,0,?)""", (emailID, i["Subject"], i["Body"], sendID[0][0],))
        print(cur.execute("SELECT * FROM user_tbl").fetchall())
        print(cur.execute("SELECT * FROM email_tbl").fetchall())
        con.commit()
        con.close()
        ### If yes, increment emailssent
        ### If no
        #MAKE NEW EMAIL IN TABLE, GENERATE ID, LINK
        

if __name__ == "__main__":
    print(accessEmails())
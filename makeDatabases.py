import sqlite3 as sql
#make connection
#make cursor

con = sql.connect("emailsUsers.db")
cur = con.cursor()

cur.execute("DROP TABLE IF EXISTS email_tbl;")
cur.execute("DROP TABLE IF EXISTS user_tbl;")

cur.execute("""CREATE TABLE user_tbl (
senderID CHARACTER(8) PRIMARY KEY NOT NULL,
senderEmail VARCHAR(254),
subscriptionTier CHARACTER(1),
emailsSent INT);
""")

cur.execute("""CREATE TABLE email_tbl (
ticketID CHARACTER(8) PRIMARY KEY NOT NULL,
emailTitle VARCHAR(254),
emailBody TEXT,
processedBool BOOLEAN,
senderID CHARACTER(8) NOT NULL,
FOREIGN KEY (senderID) REFERENCES user_tbl(senderID));
""")

cur.execute("""INSERT INTO user_tbl
VALUES ('90000000', 'talonlockett59@gmail.com', '3', 1)""")

cur.execute("""INSERT INTO email_tbl
VALUES ('00000000', 'My Email', 'Help me', True, '90000000')""")



print([i for i in cur.execute("SELECT * FROM email_tbl")])
print([i for i in cur.execute("SELECT * FROM user_tbl")])
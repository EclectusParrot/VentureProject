import sqlite3 as sql
#make connection
#make cursor
def resetDatabases():
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

    # Tier codes assumed by app.py's TIER_NAMES: 1 free, 2 pro, 3 premium, 4 business, 5 enterprise
    users = [
        # senderID,   senderEmail,                    tier, emailsSent
        ('90000000', 'talonlockett59@gmail.com',      '3',  1),    # original seed user
        ('90000001', 'dana.whitfield@example.com',    '5',  12),   # enterprise customer
        ('90000002', 'priya.nair@example.org',        '1',  3),    # free, new account
        ('90000003', 'promo.deals@example.net',       '1',  480),  # free + very high volume (abuse rule)
        ('90000004', 'sam.okafor@example.com',        '2',  27),   # pro
        ('90000005', 'devops@example.org',            '4',  64),   # business
        ('90000006', 'mei.tanaka@example.net',        '2',  9),    # pro, happy customer
    ]
    cur.executemany("INSERT INTO user_tbl VALUES (?, ?, ?, ?)", users)

    # processedBool is 0 so every email is waiting to be triaged.
    # The comment on each shows what a sensible triage should do (expectations, not guarantees).
    emails = [
        # ticketID,   title, body, processedBool, senderID

        # 0: original seed. Calm parcel request, but ends with self-harm language.
        # Expect: high risk, human_queue (safety rule overrides the model)
        ('00000000', 'My Email',
        'Help me. My address has changed and I need my parcel redirected. Pleaaseeeee please please please. Thank you Im gonna kill myself.',
        0, '90000000'),

        # 1: furious, billing, urgent, legal threat, enterprise customer.
        # Expect: billing, high risk, human_queue
        ('00000001', 'CHARGED TWICE - fix this NOW',
        "I have just checked my bank statement and you have charged me TWICE for this month's subscription. "
        "This is the second time this has happened and I am absolutely furious. I want an immediate refund "
        "or I will be contacting my bank and my lawyer. Completely unacceptable.",
        0, '90000001'),

        # 2: polite, sales inquiry, no urgency, free account.
        # Expect: sales inquiry, low risk, general_queue
        ('00000002', 'Pricing for a 50-seat team',
        "Hi there, hope you're having a good week. We're a small design agency looking at your team plan "
        "for around 50 seats. Could you send over pricing and let me know whether you offer an annual "
        "discount? No rush at all. Thanks so much, Priya",
        0, '90000002'),

        # 3: spam from a free account with very high volume.
        # Expect: spam, discard (and the high-volume free-account rule should show in the reasons)
        ('00000003', 'You have been selected!!! Free gift card',
        "CONGRATULATIONS!!! You are our lucky winner. Claim your FREE $500 gift card now before it expires: "
        "http://example.com/claim-prize . Limited time offer, act fast! Reply with your full name and "
        "date of birth to confirm.",
        0, '90000003'),

        # 4: mildly frustrated, account access, medium urgency, pro customer.
        # Expect: account access, medium risk, priority_queue or human_queue
        ('00000004', "Still can't log in",
        "Hi, I reset my password yesterday as suggested but I still can't get into my account. It keeps "
        "saying invalid credentials. This is a bit annoying as I need to get some work done this afternoon. "
        "Can you take a look when you get a chance? Thanks, Sam",
        0, '90000004'),

        # 5: calm but urgent, technical outage, business customer.
        # Expect: technical issue, high risk, human_queue
        ('00000005', 'URGENT: API returning 500 errors in production',
        "Since about 14:20 UTC our production integration has been failing with 500 errors on every request "
        "to the orders endpoint. Our checkout is effectively down and we are losing sales every minute. "
        "Please escalate immediately. I can send request IDs and logs on request.",
        0, '90000005'),

        # 6: happy, positive feedback, no action needed, pro customer.
        # Expect: low risk, general_queue
        ('00000006', 'Thank you!',
        "Just wanted to drop a quick note to say the new dashboard is fantastic. It has saved our team hours "
        "every week and your support staff were brilliant when we onboarded. Keep up the great work!",
        0, '90000006'),
    ]
    cur.executemany("INSERT INTO email_tbl VALUES (?, ?, ?, ?, ?)", emails)


    con.commit()
    con.close()
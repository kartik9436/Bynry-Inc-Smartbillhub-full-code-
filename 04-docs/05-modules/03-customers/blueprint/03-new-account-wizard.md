# 03 · New account wizard EXISTS BEHIND NO COMMITMENT

**Source:** `accounts-blueprint.pdf`, pages 60–65. Extracted text, verbatim — **derived, do not edit.**

**12,944 characters over 6 page(s).**

---

```
g
Everything around it is labelled properly: Category renders Commercial, status renders Active, the behaviour class renders Billable. Sub-type is the one field that was never given a
display map. It is drawn as it is, because a blueprint that quietly prettifies the product stops being evidence — and it is filed here rather than fixed in the picture.
03 New account wizard EXISTS BEHIND NO COMMITMENT
/:tenant/accounts/new  ·  ?step=1–6  ·  S18  ·  NewAccountWizard.tsx
Five steps, not six — the plan step is gone
The product draws a whole step for the plan, and its own copy explains why it should not: "the plan is read from the unit and is not stored on the account", "shown, not stored", and
then the warning "pick a unit first if this reads empty". A step of a six-step wizard carrying no input, whose only value is derived from the step before it.
PO ruling: "there should not be any step to select a plan as plan is already attached on the unit itself. So whenever the unit is selected, show all the details." So the unit step now carries
the unit’s whole record — its plan, version, lock and base charge among it — and the clerk sees what the account will inherit before committing to the unit rather than two clicks
later. Every drawing below is the wizard as it should be, not as it is.
The question: "They're standing at the counter and they want service. Get them on the
books."
All 6 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/accounts/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT
Create a first-time customer account.
Step 1 of 5 · Customer
Save & exit
1 Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Category *
Residential ▼
Full name *
Miller, Sarah
Email
s.miller@example.com
Phone
(512) 555-0142
Date of birth
04/11/1988 📅
Government id
last four only
Customer kind
A person ▼
No duplicate check runs here yet — the customer link arrives from the import
today.
Customer · /brazosbend/accounts/new?step=1
v2.234.15
SO
Sam Ortiz
Billing Clerk
A person · A company.
IDENTITY — STORED ENCRYPTED
SSN
•••-••-4417
Driving licence
TX ••••882
MAILING ADDRESS
Address line
1408 Elm Street
City
Austin
State
TX
Postal code
78704
Continue →
/brazosbend/accounts/new?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT
Which unit?
Step 2 of 5 · Unit
Save & exit
✓ Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Unit *
Pick a vacant or reserved unit ▼
Start date *
05/02/2026 📅
The picker offers vacant and reserved units only.
Services Electric · Water
Meters at unit M-4021 · M-4022
INITIAL READS
Not captured here — reads commit through metering's own batch path.
Unit A, 1408 Elm Street — everything this unit carries
Unit number U-000912
Label Unit A
Unit type Duplex — half
Floor Ground
Floor area 1,120 sq ft
Premises 1408 Elm Street · PR-0402
Service address 1408 Elm Street, Silver Creek, TX 78611
Map point Reads the building’s
the address is the building’s; this unit carries no point of its own, and the screen says which of the two it is showing
Parcel —
Plan SCW-RES · Sample — Residential · v1
Plan in force since 06/01/2026
Plan locked No
Base charge $20.00 a month
Bill the owner when vacant No
Meters M-4021 · M-4022
Services available ELECTRIC WATER
the plan comes from here, which is why there is no plan step — it is not locked on this unit, so a later
change-plan can override it on the account
Nothing on this panel is an input.
Unit · /brazosbend/accounts/new?step=2 · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
Account preferences · /brazosbend/accounts/new?step=3
v2.234.15
SO
Sam Ortiz
Billing Clerk
←  Back Continue →
/brazosbend/accounts/new?step=3
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT
Account preferences
Step 3 of 5 · Account preferences
Save & exit
✓ Customer ✓ Service address 3 Account preferences 4 Deposit 5 Review
How the bill is delivered
A bill is always printed. Paperless and text reminders are extra channels on top of the paper, not instead of it — neither of them switches the printed bill off.
✓ Paperless billing — email a copy of every bill
Goes to the email captured on step 1. With no email on file this is shown and cannot be ticked.
Text reminders — when a bill is issued, and before it falls due
Needs a mobile number.
Both start off.
Paying
Autopay
Capture-only in v1 — the enrolment is stored and shown, and nothing collects on it.
Tax
✓ Tax exempt
Tax-exempt reference
TX-EX-99213
The certificate number.
Expires
12/31/2027 📅
The account starts being taxed again the day after.
Language
Preferred language
English ▼
The accepted codes come from this utility’s regional settings.
←  Back Continue →
/brazosbend/accounts/new?step=4
SMARTBillHub ☰
BB Brazos Bend Utilities
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
← Accounts
Deposit · /brazosbend/accounts/new?step=4 · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
  Accounts
NEW ACCOUNT
Deposit
Step 4 of 5 · Deposit
Save & exit
✓ Customer ✓ Service address ✓ Account preferences 4 Deposit 5 Review
Does this account need a deposit?
Deposit *
Yes — take one ▼
Yes — take one · No · Waive it (needs a supervisor)
Amount *
150.00
Typed by hand today.
Why this amount
Standard for the category ▼
Standard for the category · No credit history · Previous arrears · Returning customer
Due
05/16/2026 📅
Falls on the first bill’s due date, unless it is taken today.
A CREDIT TIER WOULD SIZE THIS, AND NOTHING WORKS ONE OUT
The tier stays blank rather than showing a grade, so the amount above is a judgement with a reason beside it rather than a number the system stands behind.
Is the customer paying it now?
The account does not exist until the last step creates it, and a payment has to post against an account.
Take the deposit now *
Yes — the customer is paying today ▼
Yes — the customer is paying today · No · send it with the first bill
Method *
Card ▼
ACH · Card · Cash · Check · Lockbox · Money order · Wire
Reference or receipt number
AUTH 55192
Whatever the customer can quote back.
Amount taken
150.00
Defaults to the deposit.
Posting date *
05/02/2026 📅
The day this payment counts from.
Clearing date
05/02/2026 📅
The day the money actually arrived.
A deposit only reaches the deposit register when its payment clears. Leave the clearing date blank and the money is recorded and still on its way: the new account will read a deposit of $0.00 while the cash is
in the drawer.
What the customer pays today
Deposit $150.00
First bill Not raised yet — it follows the first cycle
Connection fee None on this category
Taken today $150.00
←  Back Continue →
/brazosbend/accounts/new?step=5
SMARTBillHub ☰ Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT
Review
Step 5 of 5 · Review
Save & exit
✓ Customer ✓ Service address ✓ Account preferences ✓ Deposit 5 Review
Check this over before it is created
Everything entered across the four steps, in the order it was asked for.
CUSTOMER · STEP 1 Edit →
Category Residential
Customer kind A person
Full name Miller, Sarah
Email s.miller@example.com
Phone +1 (512) 555-0132
Date of birth 04/18/1984
Government ID Driving licence · seen 05/02/2026
SSN Not captured
Address line 1408 Elm Street, Unit A
City Silver Creek
State TX
Postal code 78611
the mailing address matches the service address, so the bill goes to the property
SERVICE ADDRESS AND UNIT · STEP 2 Edit →
Unit Unit A · 1408 Elm Street
Unit number U-000912
Unit type Duplex — half · 1,120 sq ft
Premises 1408 Elm Street · PR-0402
Service address 1408 Elm Street, Silver Creek, TX 78611
Services ELECTRIC WATER
Meters M-4021 · M-4022
Plan, from the unit SCW-RES · Sample — Residential · v1
Base charge $20.00 a month
Start date 05/02/2026
the plan is inherited, not chosen — it is the unit’s
ACCOUNT PREFERENCES · STEP 3 Edit →
Paperless billing On · to s.miller@example.com
Text reminders Off
Printed bill Always — the elections above are on top of it
Autopay Off · captured, nothing collects on it
Tax exempt Yes · TX-EX-99213, expires 12/31/2027
Preferred language English
DEPOSIT · STEP 4 Edit →
Deposit Required
Amount $150.00
Why this amount Standard for the category
Due 05/16/2026
Credit tier Not worked out — nothing computes one
DEPOSIT PAYMENT · STEP 4 Edit →
Taken today Yes
Amount taken $150.00
Method Card
Reference AUTH 55192
Posting date 05/02/2026
Clearing date 05/02/2026
The clearing date is filled in, so the deposit reaches the deposit register and the
new account will read $150.00.
What will be on the account the moment it is created
Account number Allocated at save
Customer number None — this contact is not linked to a customer record
Balance $0.00 — nothing is billed until the first cycle
Deposit on file $150.00
Review · /brazosbend/accounts/new?step=5 · Commits POST /accounts, then POST /accounts/{id}/activate when Activate is chosen, then POST /accounts/{id}/payments for the deposit
Where a new account lands
This is the one flow whose landing was already drawn. What the wizard
creates is an account, which lands in the register’s own first tab and opens on
the account page — screens 01 and 02 at the top of this document, with all
twelve of its tabs. A draft lands there too, carrying its number and a Draft status.
There is no separate “new account request” object and inventing a queue for
v2.234.15
SO
Sam Ortiz
Billing Clerk
Taken from the customer today $150.00
What is still not written: the customer link and the plan snapshot.
What goes out to the customer
Three are ticked and two are not, and none of it is a default nobody chose. The portal invitation is off because this account has no portal sign-in yet, and the first-bill note has no template behind it.
SEND WHAT IT SAYS TO CHANNEL TEMPLATE WHEN
☑ The account is open, and its number Okonkwo, Adaeze Email · Print Welcome — new account v5 On create
☑ A receipt for the $150.00 deposit Okonkwo, Adaeze Email Deposit receipt v3 On create
☑ The service agreement Okonkwo, Adaeze Print Service agreement v2 On create
☐ How to sign in to the portal Okonkwo, Adaeze Email Portal invitation v4 On create
☐ When the first bill is coming Okonkwo, Adaeze Email — none chosen With the first cycle
Choosing a template
Search templates
⚲  welcome
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
Welcome — new account Email Email Residential · English v5 Published
Welcome — new account Printable Print Residential · English v5 Published
Welcome — new account Email Email Default · Spanish v2 Draft
Welcome — commercial Email Email Commercial · English v3 Published
Everything here is queued, and nothing is sent. This product writes a row per message and no sender picks it up — no email, no text, no print file.
Print is the floor. Paperless and text reminders are channels on top of the paper, not instead of it, so an account with paperless on gets the email AND the envelope.
A template resolves on three axes and falls back on two. The class of letter, the customer category and the language — and where no variant exists for a category or a language, the default one is used.
The draft version is listed and cannot be picked. Hiding it sends a clerk looking for something they can see exists; offering it would queue a letter nobody has approved.
And how should it be saved?
Save as *
Activate — it becomes the occupant ▼
Draft occupies nothing: the unit stays vacant, nothing bills, and the account can be activated later. Activate takes the unit now — the account becomes its occupant and starts billing on the start date.
This is the last thing asked because it is the thing that decides what the other four steps mean.
←  Back Create and activate ✓
```

# 04 · Move-in wizard EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 66–74. Extracted text, verbatim — **derived, do not edit.**

**22,075 characters over 9 page(s).**

---

```
There is no separate new account request  object, and inventing a queue for
one would be drawing a table the product does not have. Every other flow in
this document does produce its own record, and each is drawn beside the
wizard that makes it.
How you get here Three doors: the Accounts tab primary (AccountsListPage.tsx:999), the list's empty-state CTA (:1522), and the move-in wizard's step-1 refusal strip, which offers it
when the unit picker cannot help (moveShared.tsx:1653).
Primary action Create account ✓ on step 6, with a radio choosing Draft or Activate. A draft occupies nothing.
Tabs None — a six-step stepper with ?step= in the URL.
Write surfaces Add POST /accounts, then optionally POST /accounts/{id}/activate. Edit / Update n/a.
Walked Not walked.
States Loading unit picker skeleton · Empty "no vacant units" with a link out · Failed commit failure keeps every entered value · Draft the account exists and holds nothing.
Rules BR-CUS-018 · 019 (advisory) · 020 · 021 · 023 · 029 · 055 · 064 · UI-RULES 3 · 7 (violated) · 11
⚠  Step 8 constraint This file is NOT on route-b-migrated.txt. A Tailwind utility written here renders as nothing at all, and every check passes on it. Any remedy for this screen reuses a
class customers.css already declares.
04 Move-in wizard EXISTS BEHIND
/:tenant/accounts/:accountId/move-in  ·  S19  ·  six steps
The question: "The last tenant's gone. Put the new one on, from the right day, with the
right readings."
All 5 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/accounts/a-10432/move-in?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
←  Account A-10432
MOVE-IN
The unit
Step 1 of 6 · Find unit
Save & exit
1 Find unit 2 Customer 3 Start & read 4 Account
preferences 5 Deposit 6 Review
Which unit are they moving into?
Started from Move-in rather than from an account, so there is no outgoing account to inherit a unit from.
Unit · /brazosbend/accounts/a-10432/move-in?step=1
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
▤
▧
✦
▩
▦
▤
⚙
Search for a vacant unit *
1408 elm
An address, a unit label or a premises name.
UNIT ADDRESS TYPE SERVICES VACANT SINCE PREVIOUS ACCOUNT
Unit A 1408 Elm Street Duplex — half ELECTRIC WATER 01/29/2026 A-10432 · Okafor, D.
Unit B 1408 Elm Street Duplex — half ELECTRIC WATER Occupied · A-11455 —
Unit 2 1412 Elm Street Apartment ELECTRIC 11/03/2025 A-09871 · Nadeau, R.
Unit A, 1408 Elm Street — everything this unit carries
The unit
Unit number U-000912
Label Unit A
Unit type Duplex — half
Floor Ground
Floor area 1,120 sq ft
Premises 1408 Elm Street · PR-0402
Service address 1408 Elm Street, Silver Creek, TX 78611
Map point Reads the building’s
Parcel —
the address is the building’s and this unit carries no point of its own, so the screen says which of the two it is
showing
What it is billed on
Plan SCW-RES · Sample — Residential · v1
In force since 06/01/2026
Plan locked No
Base charge $20.00 a month
Bill the owner when vacant No
the plan belongs to the unit and the new account inherits it — it is not a choice on any later step
Services and meters
Services available ELECTRIC WATER
METER SERVICE TYPE LAST READ READ ON
M-4021 Electric Walk-by 41,607 01/28/2026
M-4022 Water Walk-by 8,902 01/28/2026
these are the outgoing account’s final reads, and they become the new occupant’s opening reads on step 3
Who was here before
Previous account A-10432 · Okafor, D.
Closed 01/28/2026
Vacant since 01/29/2026
Vacant for 94 days
a long vacancy is worth noticing: nothing has been read here since January, so the opening reads above are three
months old
Nothing on this panel is an input.
A UNIT WITH NO METER CAN STILL BE MOVED INTO
The wizard does not refuse it. Service starts, nothing can be measured, and no metered bill can be raised until one is fitted — which is the state A-11812 has been in since 2024.
Continue →
/brazosbend/accounts/a-10432/move-in?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
▦
←  Account A-10432
MOVE-IN
Who is moving in?
Save & exit
Customer · /brazosbend/accounts/a-10432/move-in?step=2
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
 g
Step 2 of 6 · Customer
✓ Find unit 2 Customer 3 Start & read 4 Account
preferences 5 Deposit 6 Review
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
A person · A company.
IDENTITY — STORED ENCRYPTED
SSN
•••-••-4417
Driving licence
TX ••••882
MAILING ADDRESS
Address line
1408 Elm Street
City / State / Postal
Austin · TX · 78704
←  Back Continue →
/brazosbend/accounts/a-10432/move-in?step=3
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
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Account A-10432
MOVE-IN
Start date & reads
Step 3 of 6 · Start & read
Save & exit
✓ Find unit ✓ Customer 3 Start & read 4 Account
preferences 5 Deposit 6 Review
Moved in on *
05/02/2026 📅
Opening reads
METER READING READ DATE COULD NOT BE READ
M-4021 · Electric · total 41,680 05/02/2026 📅 ☐
M-4022 · Water · total 8,902 04/29/2026 📅 ☐
M-4021 · Electric · demand — 05/02/2026 📅 ☑
Earliest start 01/29/2026
BILL FROM
Needs the cycle the billing module owns.
Prior final read is prefilled where one exists, with how old it is.
An estimate can refuse, in five named ways — no earlier reading, the
consecutive-estimate cap, a demand peak, no reading settings, and no period to work
over. A reading that merely looks odd still POSTS, flagged: vacant unit is the expected
one here.
Start date & reads · /brazosbend/accounts/a-10432/move-in?step=3 · the read date is new — the reading and the estimate are already built · 2 stated absences on this step, drawn dashed — each names the rule or table
it waits on
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▤
⚙
 📅
Both registers continue the reads step 1 showed — 41,607 and 8,902, taken on 01/28 as the outgoing account’s finals.
Ninety-four empty days added 73 units of standby electric and not a drop of water, which is what an empty flat looks like.
Every date opens on the move-in day, so a clerk who changes nothing gets what the screen does today. The water
meter was read three days before the tenant moved in, and now it can say so.
The demand register could not be read, and could not be estimated either. A demand peak is never estimated,
because the charge it drives would be disputed.
The outgoing account must have been billed through the move day — the server
refuses an earlier start.
NOTHING GUARDS THE READ DATE
The locked rules catch a duplicate reading and a negative period. Nothing checks
a read date against the previous occupant and no rule refuses one dated after
today — while the start date above has both.
←  Back Continue →
/brazosbend/accounts/a-10432/move-in?step=4
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
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Account A-10432
MOVE-IN
Account preferences
Step 4 of 6 · Account preferences
Save & exit
✓ Find unit ✓ Customer ✓ Start & read 4 Account
preferences 5 Deposit 6 Review
How the bill is delivered
A bill is always printed. Paperless and text reminders are extra channels on top of the paper, not instead of it — neither of them switches the printed bill off.
✓ Paperless billing — email a copy of every bill
Goes to the email captured on step 2. With no email on file this is shown and cannot be ticked.
Text reminders — when a bill is issued, and before it falls due
Needs a mobile number.
Both start off.
Paying
Autopay
Capture-only in v1 — the enrolment is stored and shown, and nothing collects on it.
Tax
Tax exempt
A reference and an expiry are asked for the moment it is ticked.
Language
Preferred language
English ▼
The accepted codes come from this utility’s regional settings.
The same elections the new-account wizard takes, and the same columns behind them. A move-in writes every field a create writes bar the unit, which it takes from the account being moved out of — so nothing
here is new ground, and a preference set on this step is stored exactly as it would be on a counter sign-up.
ACCOUNT PLAN
Not asked on this step, and not asked on any other: the plan lives on the unit and the account derives it. Step 1 shows the unit’s plan; there is nothing to choose here and nothing to store.
Account preferences · /brazosbend/accounts/a-10432/move-in?step=4 · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
SO
Sam Ortiz
Billing Clerk
←  Back Continue →
/brazosbend/accounts/a-10432/move-in?step=5
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
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Account A-10432
MOVE-IN
Deposit
Step 5 of 6 · Deposit
Save & exit
✓ Find unit ✓ Customer ✓ Start & read ✓ Account
preferences 5 Deposit 6 Review
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
Has this customer paid us a deposit before?
DEPOSIT CARRY-FORWARD
The one question this step has that the new-account wizard does not: a mover may have held an account with this utility before, and their own deposit could follow them. Carry-forward rides the customer linkage, so
there is nothing to read a prior position from - the server warns on every move-in that it could not be checked, and this step says the same before the commit rather than after.
It is the CUSTOMER’s own prior account, not the one being moved out of. A-10432 belongs to the outgoing tenant; their deposit settles on their own close-out and has nothing to do with the person moving in.
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
Deposit · /brazosbend/accounts/a-10432/move-in?step=5 · copied from the new-account wizard, with the one question a move-in adds · 2 stated absences on this step, drawn dashed — each names the rule or table it
waits on
v2.234.15
SO Sam Ortiz
Billing Clerk
What the customer pays today
Deposit $150.00
First bill Not raised yet — it follows the first cycle
Connection fee None on this category
Taken today $150.00
←  Back Continue →
/brazosbend/accounts/a-10432/move-in?step=6
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
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Account A-10432
MOVE-IN
Review
Step 6 of 6 · Review
Save & exit
✓ Find unit ✓ Customer ✓ Start & read ✓ Account
preferences ✓ Deposit 6 Review
The unit they are moving into ✎Step 1
Unit number U-000912
Label Unit A
Unit type Duplex — half
Floor Ground
Floor area 1,120 sq ft
Premises 1408 Elm Street · PR-0402
Service address 1408 Elm Street, Silver Creek, TX 78611
Map point Reads the building’s — this unit carries none of its own
Parcel —
Services available Electric · Water
What it is billed on
Plan SCW-RES · Sample — Residential · v1
In force since 06/01/2026
Plan locked No
Base charge $20.00 a month
Bill the owner when vacant No
The plan is the unit’s and the account inherits it.
Who was here before
Previous account A-10432 · Okafor, D.
Closed 01/28/2026
Start date and opening reads ✎Step 3
Moved in on 05/02/2026
Earliest start 01/29/2026 · the day after A ‑ 10188 closed
REGISTER READING READ DATE HOW
M-4021 · Electric · total 41,680 05/02/2026 Read
M-4022 · Water · total 8,902 04/29/2026 Read
M-4021 · Electric ·
demand
— 05/02/2026 Not
estimated
One register opens unread and unestimated. A demand peak is never
estimated, so this account starts with no demand figure and somebody has to
attend.
BILL FROM
Needs the cycle the billing module owns.
Account preferences ✎Step 4
Paperless billing On — and a printed bill is raised as well
Text reminders Off
Autopay Off
Tax exempt No
Preferred language English
Print is the floor.
D it
Vacant since 01/29/2026
Vacant for 94 days
The customer ✎Step 2
Category Residential
Full name Miller, Sarah
Email s.miller@example.com
Phone (512) 555 ‑ 0142
Date of birth 04/11/1988
Customer kind Person
Identity — stored encrypted
SSN •••-••-4417
Driving licence TX ••••882
Government id — not captured
Mailing address
Address line 1408 Elm Street
City Austin
State TX
Postal code 78704
The customer was resolved at save, and nobody was shown it. This move-in required an identifier and matched or created
a customer on it — the server knew which, recorded it, and dropped the answer before this screen.
Deposit ✎Step 5
Deposit Yes — take one
Amount $150.00
Why this amount Standard for the category
Due 05/16/2026
Paid today
Take the deposit now Yes — the customer is paying today
Method Card
Reference AUTH 55192
Amount taken $150.00
Posting date 05/02/2026
Clearing date 05/02/2026
Still to collect $0.00
DEPOSIT CARRY-FORWARD
Could not be checked. A prior deposit of this customer’s would ride the customer
linkage, and there is none - so this $150.00 is taken as if they were new to the
utility.
What the commit writes ✎Step 6
Account number allocated at save
Status Active from 05/02/2026
Order the account, then the reads, then the payment
One transaction.
What goes out to the customer
The last row is the one this move-in actually needs. One register opened unread and could not be estimated, so this account starts with no demand figure — and the customer has not been told.
SEND WHAT IT SAYS TO CHANNEL TEMPLATE WHEN
☑ The move-in is done, and the new account number Miller, Sarah Email · Print Welcome — move-in v5 On commit
☑ A receipt for the $150.00 deposit Miller, Sarah Email Deposit receipt v3 On commit
☑ The service agreement Miller, Sarah Print Service agreement v2 On commit
☐ The readings this account opened on Miller, Sarah Email Opening reads v2 On commit
☐ That a meter still has to be read Miller, Sarah Email — none chosen When a visit is raised
Choosing a template
Search templates
⚲  move-in
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
Welcome — move-in Email Email Residential · English v5 Published
Welcome — move-in Printable Print Residential · English v5 Published
Opening reads Email Email Default · English v2 Published
Welcome — move-in Email Email Default · Spanish v1 Draft
Everything here is queued, and nothing is sent. This product writes a row per message and no sender picks it up — no email, no text, no print file.
PrintisthefloorPaperlessandtextremindersarechannelsontopofthepaper notinsteadofit soanaccountwithpaperlessongetstheemailANDtheenvelope
Review · /brazosbend/accounts/a-10432/move-in?step=6 · Commits to POST /accounts/{fromId}/move-in · every field from all six steps, and 5 stated absences among them
Where a move-in lands, and what it becomes
The wizard ends at a commit, and this is the question it leaves: where did it
go? Into the accounts register, which has ten tabs and uses seven of them
as worklists — Requests, New connects, Move-ins, Move-outs, Transfers,
Disconnects and Imports. Not eight destinations to learn: one screen a clerk
already lives on, with a queue per flow. Every one has a real table behind it and
the columns drawn are the ones those screens already declare.
The Reads column is what a clerk works this list from. One move-in opened
with no reading at all and another with one estimated register — both bill, and
both need somebody to go back.
And the record is deliberately short, which the drawing says on its face. A
move-in is the record of an ACT; the thing it produced is an ACCOUNT, and
every later question — the balance, the bills, the meters — is answered there.
What this page is for is the day itself, and the fact that completed does not
mean finished: one register on MVI-26-0114 opened with no figure at all, so
the first bill on that account prices two of three.
Where a move-in lands · the Move-ins tab · /brazosbend/accounts?tab=move-ins · The six-step move-in’s own worklist · a move record, and the account it opened
v2.234.15
SO
Sam Ortiz
Billing Clerk
Print is the floor. Paperless and text reminders are channels on top of the paper, not instead of it, so an account with paperless on gets the email AND the envelope.
A template resolves on three axes and falls back on two. The class of letter, the customer category and the language — and where no variant exists for a category or a language, the default one is used.
The draft version is listed and cannot be picked. Hiding it sends a clerk looking for something they can see exists; offering it would queue a letter nobody has approved.
←  Back Complete move-in ✓
/brazosbend/accounts?tab=move-ins
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
Accounts / Move-ins ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNTS
The register
10 tabs · Move-ins · 1 still open
+ New move-in
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
OPEN
1
not yet completed
STARTING THIS WEEK
2
move-in date within 7 days
WAITING ON A READING
2
one unread, one estimated
Open Starting this week Completed All Filter ▾ ⚲  Search by reference, account, customer or unit Columns ▾ ⇩  Export
REFERENCE ACCOUNT CUSTOMER UNIT MOVE-IN DATE STEP READS DEPOSIT STATE
MVI-26-0114 A-12051 Miller, Sarah 1408 Elm · Unit A 05/02/2026 6 of 6 1 estimated $150.00 taken Completed ↗Open
The move-in, opened · MVI-26-0114 · /brazosbend/moves/mvi-26-0114 · Proposed · the record of the act, and a door to the account it opened
This record has no actions, and that is the answer rather than a gap. A
move-in and a sale are records of acts that have already happened — there is
nothing left to decide on them, so the only controls are doors to the account
and the customer. The two things this record says are still wrong are
deliberately not buttons here: the property’s owner record and the account’s
contact details are both fixed on their own screens, by somebody who can see
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
MVI-26-0113 A-12049 Reyes, M. 1408 Elm · Unit C 05/06/2026 3 of 6 Not taken — In progress ↗Open
MVI-26-0110 A-12044 Adeyemi, K. 77 Cedar Ct · Unit 4 04/28/2026 6 of 6 Read $150.00 taken Completed ↗Open
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
The Reads column is the one a clerk works from. MVI-26-0113 opened with no reading at all and MVI-26-0114 with one estimated register — both bill, and both need somebody to go back.
A move-in is a record OF an act, and the thing it produced is an account. The reference opens the move record; the account number beside it opens the account, which is where every later question about this
customer gets answered.
/brazosbend/moves/mvi-26-0114
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
Accounts / Move-ins / MVI-26-0114 ⚲  Search accounts, premises, meters… ⚑ ?
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
←  The register
MOVE-IN MVI-26-0114
Miller, Sarah
Completed 1 register estimated Moved in 05/02/2026
⌂ 1408 Elm Street · Unit A
Open the account
A move-in is the record of an act. The thing it produced is an account.
WHAT HAPPENED
Account opened A-12051
From account A-10432 · Okafor, D.
Unit 1408 Elm Street · Unit A
Moved in on 05/02/2026
Earliest legal start 01/29/2026
Committed by S. Ortiz · 05/02/2026 10:04
OPENING READS
REGISTER READING READ DATE HOW
M-4021 · Electric · total 41,680 05/02/2026 Read
M-4022 · Water · total 8,902 04/29/2026 Read
M-4021 · Electric · demand — 05/02/2026 Not estimated
MONEY TAKEN
Deposit
Required by the plan $150.00
Taken · cheque 4471 $150.00
Still to collect $0.00
WHAT IS STILL OWED TO THIS MOVE
Demand register unread and not estimated
Visit not raised
Carry-forward could not be checked
Completed does not mean finished. One register opened with no figure at all,
so the first bill on this account prices two of three registers.
```

# 18 · Complaints NEW BUILD NO COMMITMENT

**Source:** `accounts-blueprint.pdf`, pages 39–45. Extracted text, verbatim — **derived, do not edit.**

**16,955 characters over 7 page(s).**

---

```
ACC-S3
No screen tells a clerk the customer portal does not exist
STATUS Unverified
WAITS ON Nothing. The portal shipped (155 files under 07-frontend/src/portal/) and DEF-CUS-4625 already fixed this sentence on the Overview's Portal panel.
SCREENS 02 — Notes tab and Audit tab
WHAT DONE LOOKS LIKE ON SCREEN The Notes tab's Customer visible hint no longer contains the words "there is no customer portal in this version", and neither does the Audit tab's
portal-actor hover. Each says what is actually true of a note's visibility and of a portal-originated audit row.
18 Complaints NEW BUILD NO COMMITMENT
/:tenant/accounts?tab=complaints  ·  no screen id  ·  a four-step form on its own page
The question: "They rang about their bill on Friday. Where does that live, and when
did we promise to get back to them?"
⚠  This tab does not exist, and everything behind it does. There is no
complaints list, no complaint form and no complaint record anywhere in the
front end — but a complaint is already a work order: Consumer Complaint is
one of the nine job types the Product Owner listed themselves, it carries fifteen
kinds beneath it, and a job can already stand on an account. What is missing is
the screen, not the record. These three are drawn from that model and invent
nothing; where they show a gap, the gap is in the model and says so.
All 6 screens of this tab, drawn at 1280 and buildable as drawn. Real app
shell, real table, real field labels. A dashed block is a stated absence; a required
field carries its asterisk (UI-RULES 10).
/brazosbend/accounts?tab=complaints&f.state=open
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
Accounts / Complaints ⚲  Search accounts, premises, meters… ⚑ ?
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
10 tabs · Complaints · 4 open, 1 past due
+ Log a complaint
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
OPEN
4
not yet resolved
PAST DUE
1
the response time has gone
URGENT
1
4 hours to respond
LOGGED THIS MONTH
9
opened since 05/01
Open Past due Urgent Resolved All Filter ▾ ⚲  Search by reference, account, customer or address Columns ▾ ⇩  Export
REF ACCOUNT CUSTOMER ADDRESS WHAT ABOUT SERVICE PRIORITY LOGGED RESPOND BY STATE
Complaints · the table · /brazosbend/accounts?tab=complaints · Work orders of type Consumer Complaint, standing on an account
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
WO-26-
0412
A-11812 Bramble
Bakery
142 Bakers Row ·
Suite 1
Billing Issues — High · 8 h 05/09
09:14
05/09 17:14 Open ↗
Open
WO-26-
0409
A-11333 Halvorsen, P. 88 Quarry Lane Odour complaint Gas Urgent · 4
h
05/09
07:50
05/09 11:50 In
progress
↗
Open
WO-26-
0401
A-11602 Ncube, T. 1408 Elm · Unit E Low Pressure Water High · 8 h 05/08
14:02
05/08 22:02 Past due ↗
Open
WO-26-
0388
A-11455 Ferraro, L. 1408 Elm · Unit B Missed
collection
Trash High · 8 h 05/07
11:30
05/07 19:30 Resolved ↗
Open
1–4 of 4  ·  Rows per page 50 100 200    ‹ ›
A complaint is a work order, and this tab is a filter on one type. There is no complaints table in this product and there does not need to be: the job types the Product Owner listed include Consumer
Complaint with fifteen kinds beneath it, and a job can already stand on an account.
Respond by is not a promise this platform makes. It is the moment a job was logged plus the hours this utility set for that priority, and every one of those hours is editable on their own settings.
Priority came from the kind of complaint, not from the clerk. An odour complaint is urgent because gas is urgent; a billing query is high because a bill is not an emergency.
/brazosbend/complaints/new?step=1
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
Complaints / Log a complaint ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Complaints
COMPLAINT
Who is complaining
Step 1 of 4 · Who is complaining
Save & exit
1 Who is complaining 2 What happened 3 How fast we answer 4 Review & log
Search for the account *
⚲  bramble
Account number, customer name, service address or meter number.
ACCOUNT CUSTOMER SERVICE ADDRESS CATEGORY
A-11812 Bramble Bakery 142 Bakers Row · Suite 1 Commercial
A-11333 Halvorsen, P. 88 Quarry Lane Residential
The account
Account number A-11812
Customer Bramble Bakery
Customer number C-00271
Category Commercial · Small commercial
Status Active · billable
Service address 142 Bakers Row, Silver Creek, TX 78611
Unit U-000744 · Suite 1
It does not have to be an account
STAND IT ON WHEN CHOSEN
An account Somebody we bill ☑
A premises A complaint about a property with no
account
☐
An asset A bin, a meter, a hydrant ☐
A build A connection under construction ☐
A job stands on at least one of four things. A passer-by reporting a smell
outside an empty property has no account to hang it on, and the record still has to
exist — so the form offers all four and a constraint stops one floating free of every
record.
Who told us
Who reported it *
Priya Okafor
Phone
(512)555 ‑ 0188
Who is complaining · /brazosbend/complaints/new?step=1 · Four anchors — an account, a premises, an asset or a build
v2.234.15
SO
Sam Ortiz
Billing Clerk
Services Electric · Water
Balance $2,410.00
Preferred language English
What else is open on it
WHAT REFERENCE STATE
Disconnect case DSC-26-0003 Due to cut 05/14
Complaint — none open —
This account is four days from being cut off. A complaint does not pause a collection ladder and the case will not
learn this exists — so if it is upheld, somebody has to go and stop the ladder by hand on the disconnect case.
(512) 555 0188
Email
p.okafor@bramblebakery.example
How they told us
Telephone ▼
Telephone · At the counter · Email · The portal · A letter
The reporter is not always the customer. A tenant rings about a landlord-billed
property, a neighbour reports a smell.
Cancel Continue →
/brazosbend/complaints/new?step=2
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
Complaints / Log a complaint ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Complaints
COMPLAINT
What happened
Step 2 of 4 · What happened
Save & exit
✓ Who is complaining 2 What happened 3 How fast we answer 4 Review & log
What the complaint is about
Service
Electric ▼
Or none — a billing complaint is about no single service.
Kind *
Billing Issues ▼
What happened *
Two months of estimated reads and the March bill is four times December’s. Wants a real read and the bill re-
issued.
In the customer’s words where you can.
When it happened
05/08/2026 📅
Blank means they are telling us now.
Where
The service address ▼
Or a unit, or a specific asset.
Anything attached
FILE SIZE ADDED BY
photo-of-bill.jpg 240 KB S. Ortiz Remove
+ Attach a file
The kinds this utility offers
KIND SERVICE ARRIVES AT
Billing Issues — High · 8 h
Low Pressure Water High · 8 h
No Water Supply Water Urgent · 4 h
Gas leak call-out Gas Urgent · 4 h
Odour complaint Gas Urgent · 4 h
Outage report Electric Urgent · 4 h
Voltage complaint Electric High · 8 h
Missed collection Trash High · 8 h
Damaged cart Trash High · 8 h
Blocked inlet Storm water High · 8 h
Flooding Storm water High · 8 h
No service Broadband High · 8 h
What happened · /brazosbend/complaints/new?step=2 · The utility’s own fifteen kinds, maintained in Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
A photo of the bill, a letter, a picture of the meter. What a customer sends is part of what they said.
 g
Slow speed Broadband High · 8 h
Blockage Sewer High · 8 h
Backup Sewer High · 8 h
Fifteen kinds, and this list is not the platform’s. It is this utility’s own catalogue,
maintained on Settings →  Reference data →  Work order types — where a kind is
added, renamed, retired or moved under a different heading.
Four of them arrive Urgent in their own right, and that is deliberate. A
kind with no response time of its own inherits the heading’s.
A CAUSE OR AN OUTCOME TO PICK FROM
There is no vocabulary to offer. A complaint closes with a sentence somebody
typed, so this product cannot group complaints by what was wrong or by what
was done about it.
←  Back Continue →
/brazosbend/complaints/new?step=3
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
Complaints / Log a complaint ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Complaints
COMPLAINT
How fast we answer
Step 3 of 4 · How fast we answer
Save & exit
✓ Who is complaining ✓ What happened 3 How fast we answer 4 Review & log
The clock this starts
Priority
High ▼
Respond by
05/09/2026 17:14
The moment you log it plus this utility’s hours for that priority.
PRIORITY RESPOND WITHIN USED BY
Urgent 4 hours 4 kinds
High 8 hours 3 types · 11 kinds
Normal 72 hours 3 types
Low 168 hours 2 types
These four hours are this utility’s own numbers, not a promise this platform makes. They were seeded as a
starting point and are changed in one field on Settings →  Reference data →  Work priorities.
Raising or lowering it
Why you changed it
N t h g d
Does somebody have to attend?
How it gets done
Nobody — we answer it from here ▼
A billing query needs no van.
Where
The service address ▼
Customer has to be in
No ▼
Putting a billing query in the field-work queue was deliberate. A job may
carry no template, no duration and no expectation that anyone is home — so
everything a customer is waiting on sits in one place, whether or not it involves a van.
Who picks it up
Assign to
Meter Services ▼
How fast we answer · /brazosbend/complaints/new?step=3 · A response time stamped from the tenant’s own hours
v2.234.15
SO
Sam Ortiz
Billing Clerk
Not changed
A priority moved by hand is recorded against your name.
Nothing recalculates after this. The response time is stamped when the complaint is logged.
Person
Unassigned ▼
A team now, a person later. Leaving the person blank sends it to the team’s
queue; the scheduling board gives it a name.
HOW LONG THIS KIND USUALLY TAKES
No duration is held against any kind. The catalogue carries names, a heading
and a default response time, and nothing else — so the board cannot plan a
day from what is in here.
←  Back Continue →
/brazosbend/complaints/new?step=4
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
Complaints / Log a complaint ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Complaints
COMPLAINT
Review — and what it starts
Step 4 of 4 · Review & log
Save & exit
✓ Who is complaining ✓ What happened ✓ How fast we answer 4 Review & log
Who is complaining ✎  Step 1
Account A-11812 · Bramble Bakery
Customer number C-00271
Category Commercial · Small commercial
Service address 142 Bakers Row, Silver Creek, TX 78611
Unit U-000744 · Suite 1
Stood on The account
Reported by Priya Okafor
Phone (512) 555 ‑ 0188
Email p.okafor@bramblebakery.example
How they told us Telephone
What happened ✎  Step 2
Kind Consumer Complaint · Billing Issues
Service — not about one service
It happened on 05/08/2026
Where The service address
Attached photo-of-bill.jpg · 240 KB
How fast ✎  Step 3
Priority High · 8 hours at this utility
Changed by hand No — the kind chose it
Logged 05/09/2026 09:14
Respond by 05/09/2026 17:14
Attendance Nobody — answered from here
Assigned to Meter Services
Person — the team’s queue
What happens when you log it
WHEN WHAT
Now One job, referenced and on the clock from this minute
Now It appears on the Complaints tab and in the work queue
Now One audit row naming you
Now Nothing goes to the customer
Next The team picks it up, or the board gives it a name
Then Somebody types what they found and closes it
Review & log · /brazosbend/complaints/new?step=4 · Every field from three steps, and four letters that do not exist
v2.234.15
SO Sam Ortiz
Billing Clerk
In their words
Two months of estimated reads and the March bill is four times December’s.
Logging this does not touch the disconnect case. This customer is still
due to be cut on 05/14. If the complaint is upheld, stopping the ladder is a
separate act on a separate screen, and nothing will remind anybody.
What goes out to the customer
Every row here is unticked, and not one of them is a choice. No template exists for any of it.
SEND WHAT IT SAYS TO CHANNEL TEMPLATE WHEN
☐ That we have it, and its reference Bramble Bakery Email · Print — none exists On logging
☐ When we said we would answer Bramble Bakery Email — none exists On logging
☐ That somebody is coming Bramble Bakery SMS — none exists When a visit is booked
☐ What we found and what we did Bramble Bakery Email · Print — none exists On resolving
Choosing a template
Search templates
⚲  complaint
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
— nothing matches complaint — — — —
Everything here is queued, and nothing is sent. This product writes a row per message and no sender picks it up — no email, no text, no print file.
The search finds nothing, and that is the true answer. There is no complaint family in the template catalogue at all — not a draft, not an unpublished one.
←  Back Log the complaint · respond by 05/09 17:14
/brazosbend/work/wo-26-0412
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
Accounts / Complaints / WO-26-0412 ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Complaints
COMPLAINT WO-26-0412
Bramble Bakery — Billing
Issues
In progress High · respond by 05/09 17:14 Logged by telephone
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611
Reassign Change priority Put on hold Resolve
What was reported
Reference WO-26-0412
Kind Consumer Complaint · Billing Issues
Service — not about one service
Reported by Priya Okafor · (512) 555 ‑ 0188
How Telephone
Logged 05/09/2026 09:14 by S. Ortiz
Where it has got to
WHEN WHAT WHO
05/09 09:14 Logged · High · respond by 17:14 S. Ortiz
05/09 09:20 Assigned to Meter Services S. Ortiz
05/09 10:02 Accepted D. Rivera
05/09 11:40 Re-read ordered — WO-26-0415 D. Rivera
Wh h it
Complaints · the detail view · /brazosbend/work/wo-26-0412 · What was said, who has it, and the clock it is answered on
What it is A filter on one job type. Not a new table — work_orders already carries the type, the priority, the due time and the account it is for.
How you get here Nowhere. The tab is proposed, so no door exists. Drawn beside the register because that is where it belongs.
Write surfaces Add a four-step wizard on /complaints/new, not a dialog over the list. Update reassign, change priority, hold, resolve. No delete — a complaint is cancelled with a
reason.
Walked Not walked. There is nothing to walk.
No commitment Nobody has undertaken to build this. It is drawn because it was asked for and because the data supports it; that is not the same as a commitment, and this
document keeps the two apart on purpose.
Rules BR-WRK-006 · 016 · 018 · OQ-WRK-1765
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
⚙
It happened on 05/08/2026
In their words
Two months of estimated reads and the March bill is four times December’s.
The account it stands on
Account A-11812 · Bramble Bakery
Customer number C-00271
Category Commercial · Small commercial
Service address 142 Bakers Row, Silver Creek, TX 78611
Unit U-000744 · Suite 1
Balance $2,410.00
Open disconnect case DSC-26-0003 · due to cut 05/14
This customer is four days from a cut, and the complaint is about the bill being chased. Nothing links the two: a
complaint does not pause a ladder and nothing on the disconnect case knows this exists.
Attached
FILE ADDED BY
photo-of-bill.jpg 05/09/2026 S. Ortiz
Who has it
Assigned to D. Rivera · Meter Services
How it gets done Our own crew
Raised a follow-on job WO-26-0415 · Re-read
Blocked by — nothing
Customer has to be in No
Time on the clock
Logged 05/09/2026 09:14
Respond by 05/09/2026 17:14
Left 5 h 34 m
Priority High · 8 hours at this utility
The eight hours are this utility’s own number. They were seeded as a starting
point and are changed in one field on their settings — no screen, rule or letter here
treats them as a promise the platform made.
How it ends
What happened
Not recorded yet
Free text.
A CAUSE, A CATEGORY, AND THE REPORT A REGULATOR ASKS FOR
A complaint closes with a sentence somebody typed and nothing else. There
is no cause, no outcome class and no complaints register — so how many
pressure complaints did we get, and how many were upheld has no answer in
this product, for any period.
NOTHING TELLS THE CUSTOMER IT IS RESOLVED
Closing a job queues no letter, no email and no text. Whoever resolves it rings
them, or nobody does.
```

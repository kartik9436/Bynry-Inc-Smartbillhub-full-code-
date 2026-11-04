# 11 · Transfer wizard EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 112–119. Extracted text, verbatim — **derived, do not edit.**

**22,062 characters over 8 page(s).**

---

```
Primary action Record the close-out, on the danger tier — B14 rule 6 honoured, colour and not only shape.
Write surfaces Update POST /accounts/{id}/close-out, and it accepts three fields only — the date you did it, the reason, and the terminal status. The closing date, a final read, a
deposit disposition and a shortfall path are all refused by omission: the date is derived and the rest belong to acts that collect a consent this one does not.
What it does NOT write No move record — a close-out is not a move, and filing one would be the exact falsification the separate act exists to prevent. No final-read state — the meter was
read, or was not, at the cut months earlier, and writing a value would claim a reading this act never took.
⚠  One sentence
corrected
The drawing said "The final bill — Billing issues none yet". That was reversed on 2026-08-30: the cut raises the final bill — $23.23 of a $40.00 base on this account,
18 days of 31 — so by the time anyone reaches this screen the bill exists and the balance has been static ever since.
Walked Not walked.
No commitment No epic owns this screen. Its own trace block says so: the PO ruled the act on 2026-08-27 and no epic covers it, so a story is owed. That absence is the finding, and
this document does not invent a commitment to fill it.
Rules BR-CUS-082 · 430 · 431 · BR-CUS-110 · B14 rule 6
11 Transfer wizard EXISTS BEHIND
/:tenant/transfers/new  ·  S89  ·  five steps
The question: "I sold the house. Hand the whole account to whoever bought it — the
number, the meter and what it owes."
⛔  This flow was redrawn to the job the product actually does, and the old
drawing is not a variant of it. Until 2026-09-01 a transfer moved a customer to
another of our addresses: it closed one account, opened a second at a new unit,
took a final read and an opening read, and carried the deposit across. The
Product Owner ruled that a transfer is a SALE — "dont create new account -
we reassing that account - bascailly I have sold my property - so account get
transfer to new person or business; if I move to new location then it is new Service
request". The account, its number, its unit, its meters, its plan and its whole
ledger stay where they are; the customer changes. So there is no leaving step,
no arriving step and no final read, and a customer MOVING is a new service
request instead. The five steps below are the five the code names.
All 5 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/transfers/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Transfers / Transfer ⚲  Search accounts, premises, meters… ⚑ ?
←  Transfers
TRANSFER
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
TRANSFER
Find the account, and who is selling
Step 1 of 5 · Find the account
Save & exit
1 Find the account 2 The buyer 3 Date of sale 4 What they take on 5 Review & confirm
Search for the account *
⚲  marigold
Account number, customer name, service address or meter number.
ACCOUNT CUSTOMER SERVICE ADDRESS STATUS BALANCE
A-11674 Delgado, R. 310 Marigold Lane · Unit 1 Active $318.40
A-11602 Ncube, T. 1408 Elm Street · Unit E Already being sold $84.15
One sale at a time. An account already part-way through a sale cannot start another — the second row is listed rather than
hidden, so a clerk can see it exists and why it is not offered.
The account — and all of it changes hands
Account number A-11674
Customer number C-00461
Seller Delgado, R.
Customer kind Person
Category Residential · Standard
Status Active
Opened 03/08/2022
Current balance $318.40
Deposit on file $150.00
Deposit interest — not recorded
Autopay On · bank transfer
Paperless billing On
Bill email r.delgado@example.com
Phone (512) 555 ‑ 0311
Preferred language English
Mailing address Same as service
What is changing hands with it
Unit U-001355 · Unit 1
Unit type Duplex — half
Floor Ground
Floor area 1,040 sq ft
Premises 310 Marigold Lane · PR-0518
Service address 310 Marigold Lane, Silver Creek, TX 78611
Services Electric · Water
Meters M-5180 Electric · M-5181 Water
Plan SCW-RES·Residential·v1
Stays with you. The account number, the unit, the meters, the plan, the billing cycle
and the whole ledger stay exactly where they are.
Selling the property, or moving house? If this customer is moving to another
of our addresses, this is not a transfer.
Said here on purpose
The two used to be one door, and the door that existed did the second job.
The same customer elsewhere
Other accounts 1 · A-11721 · 88 Quarry Lane
Affected by this sale No — that one is theirs still
The seller keeps every other account they hold.
What this sale will not touch
Issued bills Stay in the seller’s name, for ever
Payments taken Stay as taken
Journal entries Stay as posted
The account number Unchanged
The unit and meters Unchanged
Service agreements Unchanged
A bill is a record of what was sent, not a claim about who owes it today. A bill
posted to this seller still says their name a year from now, and nothing here reissues or
re-addresses one.
THE PROPERTY OWNER RECORD
A sale does not rewrite the premises’ owner. That is a separate, typed record on
the property itself and it still wants matching by hand — the commit says so out
loud rather than leaving a clerk to assume it followed.
Find the account, and who is selling · /brazosbend/transfers/new?step=1
v2.234.15
SO
Sam Ortiz
Billing Clerk
Plan SCWRES  Residential  v1
Base charge $20.00 a month
Billing cycle Cycle 2 · the 9th
Ledger 51 months, unbroken
Continue →
/brazosbend/transfers/new?step=2
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
Transfers / Transfer ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Transfers
TRANSFER
Who is buying it
Step 2 of 5 · The buyer
Save & exit
✓ Find the account 2 The buyer 3 Date of sale 4 What they take on 5 Review & confirm
Who is buying it
Matched first, created only on no match. The buyer is looked up against the customers already on file before anybody new is
written.
Person or company
Customer kind
A person ▼
A person · A company.
Full name *
Vasquez, M.
As it should appear on the bill.
One identifier — and one is enough
Social Security number
Not given
Driving licence
Not given
Phone
(512) 555 ‑ 0197
A phone identifies a person here.
How to reach them
Email
m.vasquez@example.com
Mailing address
Same as the service address ▼
Matched an existing customer. C-00902 · Vasquez, M., on the phone number.
Needs one identifier to continue. This is what the step refuses with when a name is typed and nothing else is.
Field visit — the changeover read
This is where the reading is arranged, and it is not typed here. A sale closes no
account and opens none, so there is no final read and no opening read: the meter
keeps running on one unbroken account.
RAISE REFERENCE WHAT IT IS SERVICE HOW LONG
☑ WT-0114 Changeover
read
Electric 20 min
☑ WT-0115 Changeover
read
Water 20 min
☐ WT-0132 Meter
condition
check
— 30 min
No visit needed
A recorded answer, not an unticked box.
What happens when you save
WHEN WHAT
Now Two jobs are raised on this account and go to the work queue
Now The sale records which jobs it raised
Next Scheduling gives them a crew and a slot
Then The readings land through the ordinary reads door
The sale does not wait for the visit, and the visit does not close the account.
Either can finish first.
The list is the utility’s own. These are the published job templates this tenant wrote.
A FINAL READ, TYPED HERE
There is none, and it is not missing. Nothing on a sale records a meter reading:
the account is not closing, so there is no closing figure to capture.
Who is buying it · /brazosbend/transfers/new?step=2
The date of sale · /brazosbend/transfers/new?step=3
v2.234.15
SO Sam Ortiz
Billing Clerk
←  Back Continue →
/brazosbend/transfers/new?step=3
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
Transfers / Transfer ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Transfers
TRANSFER
The date of sale
Step 3 of 5 · Date of sale
Save & exit
✓ Find the account ✓ The buyer 3 Date of sale 4 What they take on 5 Review & confirm
The date of sale
Date of sale *
05/09/2026 📅
The day the account changes hands.
One date, not two. The old step asked for a leaving date and an arriving date because the job closed one account and opened
another.
Nothing is prorated at a sale. One unbroken account, one service agreement, one billing period.
What changes hands on that day
Unit U-001355 · Unit 1
Unit type Duplex — half · ground · 1,040 sq ft
Premises 310 Marigold Lane · PR-0518
Service address 310 Marigold Lane, Silver Creek, TX 78611
Services Electric · Water
Electric meter M-5180 · walk-by · read 04/09/2026
Water meter M-5181 · walk-by · read 04/09/2026
Plan SCW-RES · Residential · v1
Base charge $20.00 a month
Billing cycle Cycle 2 · the 9th
Current period 04/09/2026 – 05/08/2026
Next bill 05/09/2026
Read-only, and that is the point. None of this is chosen on a sale.
What the date does
Who owns the account from 05/09/2026
Who the next bill goes to The buyer
Recorded as One day, on the sale
What the date does not do
Split the bill No
Close a period No
Start a new ledger No
Trigger a final statement No
Move the deposit No — there is nowhere to move it to
The period covering this date is not divided. 04/09 to 05/08 is one bill and it is
issued on 05/09 to the buyer, who by then owns the account. Whatever the two parties
settle between themselves about the days before the sale is their arrangement, not
ours.
The buyer pays for days the seller used. That follows from the ruling that the
debt goes with the property, and it is the one thing on this wizard a clerk should
say out loud to a buyer on the phone.
A CLOSING STATEMENT FOR THE SELLER
Nothing produces one. A sale closes no account, so there is no final bill and no
settlement run.
←  Back Continue →

What the buyer takes on · /brazosbend/transfers/new?step=4 · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
/brazosbend/transfers/new?step=4
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
Transfers / Transfer ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Transfers
TRANSFER
What the buyer takes on
Step 4 of 5 · What they take on
Save & exit
✓ Find the account ✓ The buyer ✓ Date of sale 4 What they take on 5 Review & confirm
What the buyer takes on
As it stands on 05/09/2026
Account balance $318.40
Deposit on file $150.00
Deposit interest earned — not recorded
Taken on by the buyer $318.40
The debt goes with the property. The buyer takes the address and what it owes.
And it costs one line of code, because nothing moves. The account carries its own ledger and the account is not going
anywhere — so the balance never moves, because the thing it sits on never moves.
Fees to collect on this sale
THERE ARE NONE, AND THIS STEP TAKES NO PAYMENT
A reassignment quotes nothing and collects nothing. There is no change-of-ownership fee in this product: no rule sets one,
no table holds one, and no door would take the money.
What a fee would need, if one is wanted. A named charge with an amount and a tax treatment, a place on the bill or a receipt of
its own, and a decision about whether an unpaid one blocks the sale.
Before you continue
✓ I have shown this to the buyer
Recorded with the sale: a clerk confirms the figure was put in front of the buyer, not that they agree with it.
Why there is nothing to decide here
This step used to have two switches — should the deposit carry, should the
arrears follow — because four rules disagreed and nobody had ruled. Both were
answered the same day: the debt follows the property.
Two figures this screen cannot fully
stand behind
DEPOSIT INTEREST
Interest on a held deposit is agreed and is not built. This account shows $150.00
and the agreed arithmetic for a deposit held this long says $153.50. It renders as
not recorded rather than as $0.00, because zero would be a claim.
THE BALANCE IS A RUNNING TOTAL, NOT A RE-DERIVED ONE
$318.40 is the figure the account carries, not a sum recomputed from the bills and
payments underneath it. It is what every other screen shows and it is what the
buyer takes on — but it is a cache, and this screen says so instead of implying an
audit.
Who gets told this figure
The clerk Here, on this step
The record Written with the sale, at the moment of sale
The buyer Not decided
Whether the buyer must be shown what they are taking on, and where, has
never been ruled. It is not answered by inference here: the figure rides the record so it
exists, and no letter claims to have told them.
←  Back Continue →
/brazosbend/transfers/new?step=5
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Transfers / Transfer ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
←  Transfers
TRANSFER
Review — one account, one new owner
Step 5 of 5 · Review & confirm
Save & exit
✓ Find the account ✓ The buyer ✓ Date of sale ✓ What they take on 5 Review & confirm
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
The account being sold ✎  Step 1
Account number A-11674
Seller Delgado, R.
Customer number C-00461
Category Residential · Standard
Status Active — and it stays active
Opened 03/08/2022
Unit U-001355 · Unit 1
Premises 310 Marigold Lane · PR-0518
Service address 310 Marigold Lane, Silver Creek, TX 78611
Services Electric · Water
Meters M-5180 Electric · M-5181 Water
Plan SCW-RES · Residential · v1
Base charge $20.00 a month
Billing cycle Cycle 2 · the 9th
The buyer ✎  Step 2
Name Vasquez, M.
Customer kind Person
Identifier given Phone
Social Security number — not given
Driving licence — not given
Phone (512) 555 ‑ 0197
Email m.vasquez@example.com
Mailing address Same as the service address
Matched to C-00902 · already on file
New customer created No
The changeover read ✎  Step 2
Jobs raised 2
Electric WT-0114 · Changeover read · 20 min
Water WT-0115 · Changeover read · 20 min
Meter condition check — not raised
No visit needed Not chosen
A reading recorded by this sale None — there is no such thing
The date ✎  Step 3
Date of sale 05/09/2026
Recorded as One day
Current period 04/09/2026 – 05/08/2026
Next bill 05/09/2026 · to the buyer
Prorated No
The money ✎  Step 4
Account balance $318.40
Deposit on file $150.00
Deposit interest — not recorded
Taken on by the buyer $318.40
Refunded to the seller $0.00
Re-collected from the buyer $0.00
Fees collected — there are none
Shown to the buyer Yes
What will happen when you confirm
WHEN WHAT
Now The buyer becomes the customer on A-11674
Now The seller’s link to this account is removed
Now The balance and deposit are recorded as they stand today
Now Two changeover-read jobs go to the work queue
Now One audit row: from whom, to whom, and the figures
Next The bill on 05/09 is issued to the buyer
Then The property’s owner record still wants updating by hand
One transaction. All five writes land together or none of them does.
The account keeps the seller’s contact details and settings. Paperless is
still on, the bill email is still the seller’s, and autopay is still running on the seller’s
bank instruction.
What goes out to the buyer and the seller
The two unticked rows are the two this sale cannot send, and they are unticked for different reasons. Nobody has decided whether the buyer is told the balance they have just taken on, so no letter claims to have
told them.
SEND WHAT IT SAYS TO CHANNEL TEMPLATE WHEN
☑ That the account has changed hands Vasquez, M. · buyer Email · Print Change of ownership — buyer v2 On commit
Review — one account, one new owner · /brazosbend/transfers/new?step=5 · Commits to one door running all five staged writes in a single transaction
Where a transfer lands, and what it becomes
Onto the Transfers tab, with two dates rather than one. A transfer has an out
date and an in date and they are rarely the same day; a single date column
would have to pick one and would be wrong about the other.
The record is where the flow justifies existing at all. A transfer is the one case
where the deposit is supposed NOT to move: a move-out followed by a move-in
would refund $150.00 and take it again, and would start the customer’s history
over. The closing balance travels with it, because a transfer that left a $64.20
stub on a closed account is how somebody ends up in collections for a house
they no longer live in.
Where a transfer lands · the Transfers tab · /brazosbend/accounts?tab=transfers · One customer, two addresses — and the deposit that follows them
v2.234.15
SO Sam Ortiz
Billing Clerk
☑ That the account has changed hands Delgado, R. · seller Email · Print Change of ownership — seller v2 On commit
☑ That somebody is coming to read the meters Vasquez, M. · buyer SMS Field visit booked v1 When a crew is assigned
☐ What they have taken on — the $318.40 and the deposit Vasquez, M. · buyer Email — none chosen On commit
☐ Where things stood on the day they sold Delgado, R. · seller Print — none exists On commit
Choosing a template
Search templates
⚲  ownership
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
Change of ownership — buyer Email Email Residential · English v2 Published
Change of ownership — buyer Printable Print Residential · English v2 Published
Change of ownership — seller Email Email Default · English v2 Published
Field visit booked SMS SMS Default · English v1 Published
Change of ownership — buyer Email Email Default · Spanish v1 Draft
Everything here is queued, and nothing is sent. This product writes a row per message and no sender picks it up — no email, no text, no print file.
Print is the floor. Paperless and text reminders are channels on top of the paper, not instead of it, so this account gets the email AND the envelope.
A template resolves on three axes and falls back on two. The class of letter, the customer category and the language — and where no variant exists for a category or a language, the default one is used.
The draft version is listed and cannot be picked. Hiding it sends a clerk looking for something they can see exists; offering it would queue a letter nobody has approved.
And read the address these go to before you tick anything. The account keeps the seller’s email and the seller’s paperless election, because a sale changes who owns the account and nothing else.
←  Back Complete the sale ✓
/brazosbend/accounts?tab=transfers
SMARTBillHub ☰
BB BrazosBendUtilities
Accounts / Transfers ⚲  Search accounts, premises, meters… ⚑ ?
ACCOUNTS
The transfer, opened · TRF-26-0021 · /brazosbend/transfers/trf-26-0021 · Proposed · the deposit and the balance that followed the customer
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
ACCOUNTS
The register
10 tabs · Transfers · 1 still open
+ New transfer
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
OPEN
1
a sale part-way through
SELLING THIS WEEK
1
sale date within 7 days
OWED ON ACCOUNTS BEING SOLD
$318.40
goes with the property
Open Selling this week Completed All Filter ▾ ⚲  Search by reference, account, address or name Columns ▾ ⇩  Export
REFERENCE ACCOUNT ADDRESS SOLD BY SOLD TO SALE DATE STEP TAKEN ON STATE
TRF-26-0021 A-11455 1408 Elm · Unit B Tan, Wei Ferraro, L. 05/07/2026 5 of 5 $64.20 Completed ↗  Open
TRF-26-0020 A-11674 310 Marigold · Unit 1 Delgado, R. Vasquez, M. 05/09/2026 3 of 5 $318.40 In progress ↗  Open
1–2 of 2  ·  Rows per page 50 100 200    ‹ ›
One account, not two — and that is the whole point of this flow. A sale reassigns the account that is already at the address: the number, the unit, the meters and the ledger all stay, and the customer changes.
One date, because there is only one. This used to be a flow with an out date and an in date, because it closed one account and opened another.
Taken on is the balance at the moment of sale, and the buyer owes it. The debt goes with the property.
THE REFERENCE IN THE FIRST COLUMN
No transfer numbering series has been set up, so every sale is recorded without a reference today and this column would show the reason rather than a number. It is one catalogue row away and the column is drawn as
it will read once somebody adds it.
/brazosbend/transfers/trf-26-0021
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
S tti g
Accounts / Transfers / TRF-26-0021 ⚲  Search accounts, premises, meters… ⚑ ?
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
TRANSFER TRF-26-0021
Tan, Wei →  Ferraro, L.
Completed Account reassigned Sold 05/07/2026
Open the customer Open the account
There is one account here, and it never closed. A-11455 is the same account it was before the sale, at the same address, with the same meters and the same unbroken ledger.
WHAT HAPPENED
Account A-11455 · active, and it stayed active
Unit 1408 Elm Street · Unit B
Service address 1408 Elm Street, Silver Creek, TX 78611
Sold on 05/07/2026
Sold by Tan, Wei · C-00344
Sold to Ferraro, L. · C-00877
Buyer kind Person
THE MONEY, AS IT STOOD ON THE DAY
What the buyer took on
Account balance $64.20
Deposit on file $150.00
Deposit interest — not recorded
Refunded to the seller $0.00
Re-collected from the buyer $0.00
Fees charged — there are none
Taken on by the buyer $64.20
```

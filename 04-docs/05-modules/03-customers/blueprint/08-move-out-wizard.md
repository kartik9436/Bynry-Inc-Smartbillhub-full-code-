# 08 · Move-out wizard EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 98–106. Extracted text, verbatim — **derived, do not edit.**

**24,015 characters over 9 page(s).**

---

```
08 Move-out wizard EXISTS BEHIND
/:tenant/accounts/:accountId/move-out  ·  S20  ·  six steps
The question: "They're leaving on the 28th. Close it properly — and tell me what
happens to the deposit before I promise them anything."
All 6 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/accounts/a-10432/move-out?step=1
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
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT
The account
Step 1 of 6 · Find account
Save & exit
1 Find account 2 Date & final reads 3 Final bill & deposit 4 The shortfall 5 What happens next 6 Review & close
Search for the account *
⚲  okafor
Account number, customer number, name, service address or meter number.
ACCOUNT CUSTOMER SERVICE ADDRESS STATUS BALANCE
A-10432 Okafor, D. 1408 Elm Street · Unit A Active $247.30
A-10188 Okafor, D. 88 Quarry Lane Closed $0.00
Two accounts, one name. A customer who has lived at two of our addresses has two accounts, and the closed one cannot be
moved out again — it is listed so the clerk can see they picked the right one, not hidden so they wonder.
The account
Account number A-10432
Customer number C-00318
Name Okafor, D.
Category Residential · Standard
Status Active
Opened 02/14/2024
Balance $247.30
Deposit on file $150.00
Autopay Off
Paperless billing On
Preferred language English
Mailing address Same as service
Entered from the account’s own page, this step confirms rather than
searches — the account arrives in the address bar and a second picker could choose
one the page cannot act on. Entered from the Move-outs tab, there is nothing in the
URL and the search above is the only way in.
Meters on this unit
METER SERVICE TYPE LAST READ READ ON
M-4021 Electric Walk-by 51,776 12/28/2025
M-4022 Water Walk-by 1,388 12/28/2025
Both were last read a month ago, so neither figure is what the register stands at
today. Step 2 is where that gets fixed.
What is open on this account
Unpaid bills 2 · $247.30
Payment plan None
Disputes None
Open service requests None
Sub-accounts 0 — this is not a master account
Whether an issued bill blocks this move-out cannot be checked here.
Billing has no invoices table, so the screen genuinely does not know — the server
answers it at the commit, and every move-out warns that the check could not run.
THE MOVE-OUT REASON
Five options are named on screen and none of them is stored. There is no
column for it, so the wizard asks and forgets - which is worse than not asking, and
is drawn rather than quietly dropped.
The account · /brazosbend/accounts/a-10432/move-out?step=1
v2.234.15
SO
Sam Ortiz
Billing Clerk
The unit they are leaving
Unit U-000912 · Unit A
Unit type Duplex — half
Floor Ground
Floor area 1,120 sq ft
Premises 1408 Elm Street · PR-0402
Service address 1408 Elm Street, Silver Creek, TX 78611
Plan SCW-RES · Residential · v1
Base charge $20.00 a month
Bill the owner when vacant No
Continue →
/brazosbend/accounts/a-10432/move-out?step=2
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
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT
Date & final reads
Step 2 of 6 · Date & final reads
Save & exit
✓ Find account 2 Date & final reads 3 Final bill & deposit 4 The shortfall 5 What happens next 6 Review & close
Moved out on *
01/28/2026 📅
The last day this customer is responsible for the supply.
Final reads
Key the register as it stands, and the day it was read.
METER FINAL READ READ DATE COULD NOT BE READ
M-4021 · Electric · total
Last read 51,776 · read 31 days ago
52,410 01/28/2026 📅 ☐
M-4022 · Water · total
Last read 1,388 · read 31 days ago
— 01/28/2026 📅 ☑
Every date opens on the move-out day. A meter read on the Saturday before a Tuesday move-out can say so, and a clerk who
changes nothing gets the move-out date on both.
What the estimate answered
REGISTER OUTCOME WHAT WAS RECORDED
M-4022 ·
Water
Estimated 1,402 — worked from this register’s own history over 31 days, method
disclosed on the read.
An estimated final read is lawful and it is also the one a customer disputes. It prices the last month of a bill they are
The three answers a final read can
have
STATE WHAT IT MEANS
Taken Somebody read the register at or after the move-out date.
Estimated Worked out from that register’s own history, with the
method disclosed.
Due No reading at all, and the date has passed.
Two would not have been enough. A settlement reached on an estimate and one
reached on a real reading are not the same claim, and the state is stored on the
account so the difference survives the wizard closing.
An estimate can refuse, in five named ways — no earlier reading, the
consecutive-estimate cap, a demand peak, no reading settings, or no period to
work over. A refusal comes back as data beside the row: never a zero, never an
invented figure.
What this step does NOT do
NO USAGE IS WORKED OUT HERE
The difference between the last reading and this one is not computed on this
screen. Reads commit through metering's own door and the consumption follows
from them; a delta drawn here would be a second arithmetic to disagree with the
Date & final reads · /brazosbend/accounts/a-10432/move-out?step=2 · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
v2.234.15
SO Sam Ortiz
Billing Clerk
about to be asked to settle, so the account closes on a figure nobody stood in front of. first.
The reads are committed with the close, not before it. The whole move-out is
one transaction, so a refused reading rolls the close back with it and everything stays
on screen.
←  Back Continue →
/brazosbend/accounts/a-10432/move-out?step=3
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
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT
Final bill & deposit
Step 3 of 6 · Final bill & deposit
Save & exit
✓ Find account ✓ Date & final reads 3 Final bill & deposit 4 The shortfall 5 What happens next 6 Review & close
The final bill
LINE PERIOD AMOUNT
Electric · 634 kWh 12/28/2025 — 01/28/2026 $71.40
Water · 14 kgal · estimated 12/28/2025 — 01/28/2026 $17.70
Unbanked export credit — $0.00
Final bill, net $89.10
What to do with the deposit
Apply it to the final bill
The only one that reduces what this customer owes, and the only one available while the account lands short.
Amount to apply *
150.00
The whole deposit by default.
Applied on *
01/28/2026 📅
The move-out day.
Three are greyed and each says why. Which of the four is available is decided by the subtraction below, not by the clerk — and
hiding the other three would leave a clerk wondering whether this product can refund a deposit at all.
Everything outstanding
The subtraction
How the money lands is not a choice. It is one subtraction, and the answer
decides which case this account is in: above zero is short, zero is settled, and
below zero is a refund — unless a dispute holds it, or a sibling account owes us
money, in which case it goes there.
The five landings, one arithmetic
LANDING WHEN THIS ACCOUNT
Settled nothing left either way
Refund
due
below zero, nothing in the way
Short above zero this one
Held below zero, a dispute is open
To a sibling below zero, another account owes
us
What the other three would ask for
ACTION ITS FIELDS
Refund it Method — ACH, a mailed cheque, or carried to a new
account · the amount · where to send it
Hold it Which dispute · a review date · who authorised the hold
Transfer
it
The receiving account, resolved by the server · the amount ·
a reason
Named rather than hidden, so a reader can see what each one needs without
having to find an account in the right state to make it appear.
⚠  The signed arithmetic includes deposit interest and this product does
not track it. The frozen figure applies $153.50 — a $150.00 deposit held
fourteen months at the tenant’s 2% simple rate earns $3.50. Here applied counts
the deposit alone, and the consequence runs against the customer: a
smaller amount applied makes the shortfall bigger, so this account is asked for
Refund it Account is short
Needs the subtraction to land below zero, and this one lands $186.40 above it.
Hold it No dispute
Needs an open dispute.
Transfer it to another account Different flow
That is the transfer flow, not a move-out — there the deposit never leaves and the history is kept.
Final bill & deposit · /brazosbend/accounts/a-10432/move-out?step=3 · 3 stated absences on this step, drawn dashed — each names the rule or table it waits on
v2.234.15
SO
Sam Ortiz
Billing Clerk
Prior balance $247.30
Final bill, net $89.10
Outstanding $336.40
Deposit applied − $150.00
Deposit interest not recorded
Unapplied credit − $0.00
Short by $186.40
The next step is what happens to that $186.40. It is its own step because it is a decision about somebody else’s money, not
an arithmetic.
 gg
more than the signed rule says it owes.
NO BILL IS ISSUED BY THIS SCREEN
Billing raises the final bill; this wizard prices what it will contain and posts nothing.
The figures above are a settlement position, not an invoice, and the account
closes owing what the invoice will say.
←  Back Continue →
/brazosbend/accounts/a-10432/move-out?step=4
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
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT
The shortfall
Step 4 of 6 · The shortfall
Save & exit
✓ Find account ✓ Date & final reads ✓ Final bill & deposit 4 The shortfall 5 What happens next 6 Review & close
What happens to $186.40
Outstanding $336.40
Deposit applied − $150.00
Short by $186.40
Owed by Okafor, D. · A-10432, closing today
Collect it
It stays owed by Okafor, D. and collections chase them at their next address.
Forwarding address
88 Quarry Lane, Silver Creek, TX 78611
Where the reminders go.
A payment plan
Agreed before the account closes, and the plan survives the closure.
Transfer it to the master account
A-10001 · Elm Street Holdings LLC, the declared owner of 1408 Elm Street.
Write it off
The debt stops existing rather than moving.
What each one would ask for
PATH ITS FIELDS WHO CAN
Transferring points the reminder ladder at somebody who never agreed
to this debt. A departing tenant’s residue moving to their landlord is lawful and it
is also a letter arriving at a company that has never heard of Okafor.
What the chosen path will do
THEN WHAT
Now $186.40 stays on A-10432 as a closing balance
Now The account closes SHORT, which keeps its reminder ladder
running
Next Collections chase Okafor, D. at 88 Quarry Lane
Not
now
Nothing moves to the landlord and nothing is forgiven
Closing does not stop the reminders. Only a settled or refunded close does that.
If the transfer were chosen instead: the master account’s own ladder restarts, this
account closes settled, and the sub-account is closed by the transfer rather than by the
move-out. That is one ruling, not two screens agreeing by accident.
WHICH CASE THE ACCOUNT IS IN COMES FROM A READ THIS
DEPLOYMENT ANSWERS ONLY IN PART
The landing and the figures are served. The rest of the close picture - premises
occupancy afterwards, the vacant-charge position, payment-plan progress -
arrives empty, so no path is offered on a guess and nothing is assumed in its
place.
The shortfall · /brazosbend/accounts/a-10432/move-out?step=4 · 3 stated absences on this step, drawn dashed — each names the rule or table it waits on
v2.234.15
SO Sam Ortiz
Billing Clerk
Collect it A forwarding address Any clerk
A payment plan Instalments · first payment date · amount each · the customer’s agreement Any clerk
Transfer it The target — the master account or the premises owner — and a reason Any clerk
Write it off A reason · a supervisor’s approval A supervisor
←  Back Continue →
/brazosbend/accounts/a-10432/move-out?step=5
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
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT
What happens next
Step 5 of 6 · What happens next
Save & exit
✓ Find account ✓ Date & final reads ✓ Final bill & deposit ✓ The shortfall 5 What happens next 6 Review & close
The account
Status becomes Closed · 01/28/2026
Balance at close $186.40 still owed
Service agreements both ended 01/28/2026
Autopay stops
Paperless kept — the final bill still goes out
Closing does not stop the reminders. An account that closes SHORT keeps its ladder running against the person who
left.
The unit
Falls to Vacant · from 01/29/2026
Vacant standby Off — nobody is billed for it
Plan stays on the unit
Next occupant can start 01/29/2026 at the earliest
A vacant unit bills the owner only where its own standby flag is set. This one is off, so the unit costs nobody anything until
somebody moves in.
The meters
On the unit 2 · M-4021, M-4022
They stay fitted yes — a move-out removes nothing
Final reads one taken, one estimated
The money
Deposit $150.00 applied to the final bill
Deposit interest not recorded
Shortfall $186.40 · to be collected
Final bill raised by billing, not by this wizard
Refund none — the account is short
What we will send
MESSAGE WHEN STATE
Final bill when billing raises it Not queued here
Closing statement on close Queued
Deposit applied on close Queued
Amount still owed on close Queued
Queued is not sent. Rows are written and no sender picks them up.
What this close does NOT do
NOT THIS WHY
Issue the final
bill
Billing raises it on its own cycle.
Refund
anything
The account is short; there is nothing to return.
Remove the
meters
They belong to the unit, not the customer.
Freetheunitfor Theoutgoingaccountisbilledthroughitsmove-out
What happens next · /brazosbend/accounts/a-10432/move-out?step=5
v2.234.15
SO
Sam Ortiz
Billing Clerk
Free the unit for
today
The outgoing account is billed through its move-out
day, so the next tenant starts the day after.
Close a sub-
account
There are none — this is not a master account.
SIX CONSEQUENCES THE PRODUCT CANNOT YET STATE
Premises occupancy afterwards, the owner on record, the vacant-charge
position, payment-plan progress, what happens to the assets, and any master-
account effect all arrive empty from the close-impact read. Each is named rather
than defaulted, because a blank consequence and a harmless one look identical
once a screen guesses.
←  Back Continue →
/brazosbend/accounts/a-10432/move-out?step=6
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
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT
Review & close
Step 6 of 6 · Review & close
Save & exit
✓ Find account ✓ Date & final reads ✓ Final bill & deposit ✓ The shortfall ✓ What happens next 6 Review & close
The account and the unit ✎Step 1
Account A-10432 · Okafor, D.
Customer number C-00318
Category Residential · Standard
Opened 02/14/2024
Unit U-000912 · Unit A
Service address 1408 Elm Street, Silver Creek, TX 78611
Plan SCW-RES · Residential · v1
Prior balance $247.30
Deposit on file $150.00
Date and final reads ✎Step 2
Moved out on 01/28/2026
Reason — asked for, and not stored
REGISTER FINAL READ READ DATE HOW
M-4021 · Electric 52,410 01/28/2026 Read
M-4022 · Water 1,402 01/28/2026 Estimated
Final bill and deposit ✎Step 3
What happens next ✎Step 5
Account status Closed · 01/28/2026
Reminders keep running — the account closes short
Unit Vacant from 01/29/2026 · standby off
Meters stay fitted
Messages queued 3
On commit
THEN WHAT
Now The account closes and both service agreements end
Now The two final reads commit through metering
Now The deposit is applied and the shortfall recorded
Now Three messages are queued
Next Billing raises the final bill on its cycle
Next Collections chase $186.40 at the customer’s new address
Then The unit is free for a move-in from 01/29/2026
One transaction. A refused reading rolls the close back with it, so nothing half-
lands and everything stays on screen.
Review & close · /brazosbend/accounts/a-10432/move-out?step=6 · Commits to POST /accounts/{id}/move-out · reads GET /accounts/{id}/close-impact at step 5
Where a move-out lands, and what it becomes
Onto the register’s Move-outs tab, beside the six other worklists the register
carries.
Settlement is a direction, not a status. One of these owes the utility $186.40
and one is owed $42.15 back, and they are the same kind of row. A column
reading only settled would hide which way the money goes, which is the only
thing a clerk ringing about it needs. Final read has three answers and not two
— taken, estimated, or still due — and the middle one is why it is a column: a
move-out settled on an estimate is lawful, and it is also the one a customer
disputes.
A closed move-out can still be waiting on a decision
MVO-26-0088 is short by $186.40 owed by somebody who has left, and nothing has decided where it goes. It can follow the customer, or be tied back to the master account for
that address — and tying it back points the reminder ladder at a landlord, so it is a clerk’s deliberate act and never a consequence of closing.
Nothing is preselected on that record. A default there would be the product deciding whose debt this is.
Where a move-out lands · the Move-outs tab · /brazosbend/accounts?tab=move-outs · The six-step move-out’s worklist · final reads and where the money landed
v2.234.15
SO Sam Ortiz
Billing Clerk
AMOUNT
Prior balance $247.30
Final bill, net $89.10
Outstanding $336.40
Deposit applied − $150.00
Deposit interest not recorded
Short by $186.40
Landing Short
Deposit action Applied to the final bill
The shortfall ✎Step 4
Short by $186.40
Decision Collect it
Forwarding address 88 Quarry Lane, Silver Creek, TX 78611
Transferred to — nothing moved to the landlord
Written off — none
The already-issued-bill check could not run. Billing has no invoices table, so
this screen genuinely cannot know it — the server answers it at the commit, and
every move-out carries the warning rather than implying the check passed.
The answer carries both exits as links — the closed account and a move-in on the
freed unit — so the chain survives and the server’s warnings are not lost behind a
navigation.
←  Back Complete move-out ✓
/brazosbend/accounts?tab=move-outs
The move-out, opened · MVO-26-0088 · /brazosbend/moves/mvo-26-0088 · Proposed · and the one decision a closed move-out can still be waiting on
/brazosbend/accounts?tab move outs
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
SO Sam Ortiz
Billing Clerk
Accounts / Move-outs ⚲  Search accounts, premises, meters… ⚑ ?
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
10 tabs · Move-outs · 1 still open
+ New move-out
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
OPEN
1
not yet closed
LEAVING THIS WEEK
1
move-out date within 7 days
FINAL READS DUE
1
no reading and the date has passed
Open Leaving this week Closed All Filter ▾ ⚲  Search by reference, account, customer or unit Columns ▾ ⇩  Export
REFERENCE ACCOUNT CUSTOMER UNIT MOVE-OUT DATE STEP FINAL READ SETTLEMENT STATE
MVO-26-0088 A-10432 Okafor, D. 1408 Elm · Unit A 01/28/2026 6 of 6 Taken Short by $186.40 Completed ↗Open
MVO-26-0087 A-11602 Ncube, T. 1408 Elm · Unit E 05/09/2026 2 of 6 Due — In progress ↗Open
MVO-26-0084 A-11890 Fairbanks, J. 1408 Elm · Unit D 04/14/2026 6 of 6 Estimated Refund $42.15 Completed ↗Open
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
Settlement is a direction, not a status. One of these owes the utility $186.40 and one is owed $42.15 back, and they are the same kind of row.
Final read has three answers and not two. Taken, estimated, or still due — and the middle one is why it is a column: a move-out settled on an estimate is lawful, and it is also the one a customer disputes.
/brazosbend/moves/mvo-26-0088
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
Accounts / Move-outs / MVO-26-0088 ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT MVO-26-0088
Okafor, D.
Completed Short by $186.40 Moved out 01/28/2026
⌂ 1408 Elm Street · Unit A
Open the account Tie the shortfall back
WHAT HAPPENED
Account closed A-10432
Unit 1408 Elm Street · Unit A
Moved out on 01/28/2026
Final read Taken · 01/28/2026
Unit now Vacant · standby off
Committed by S. Ortiz · 01/28/2026 15:12
HOW THE MONEY LANDED
$186.40 is owed by somebody who has left, and nothing has decided
where it goes. It can follow the customer, or be tied back to the master account
for this address — and tying it back points the reminder ladder at the landlord, so
it is a clerk’s deliberate act and never a consequence of closing.
WHERE IT COULD GO
OPTION WHAT IT MEANS
Follow the
customer
The debt stays theirs and collections chase them at
their new address.
Tie back to the
master
A-10001 · Elm Street Holdings LLC. Their ladder
restarts, and this account closes.
Write it off Needs a supervisor and a reason.
One action, and it is a consent rather than a consequence. Written as an
automatic rule, tying a shortfall back would move a departing tenant’s debt onto
a landlord who never agreed to it, silently, on every move-out in the product.
Tie the shortfall back — and what it does to the landlord · /brazosbend/moves/mvo-26-0088 · The only action on a completed move-out · and it is a consent, not a consequence
v2.234.15
SO
Sam Ortiz
Billing Clerk
Settlement
Closing balance $336.40
Deposit applied $150.00
Short by $186.40
Nothing is preselected. A default here would be the product deciding whose debt
this is.
/brazosbend/moves/mvo-26-0088
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
SamOrtiz
Accounts / Okafor, D. ⚲  Search accounts, premises, meters… ⚑ ?
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
MOVE-OUT MVO-26-0088
Okafor, D.
Completed Short by $186.40
Open the account Tie the shortfall back
Tie $186.40 back
A-10432 closes; somebody else starts being chased
✕
WHERE IT WOULD GO
Amount $186.40
From A-10432 · Okafor, D. · closed 01/28/2026
To A-10001 · Elm Street Holdings LLC
Why that account the declared owner of 1408 Elm Street
The target is resolved by the server and cannot be typed. There is no account box on this form: a transfer built against an ambiguous target is refused, so rather than validate a
typed account number the screen never offers one.
WHAT THIS WILL DO — READ IT BEFORE YOU AGREE TO IT
THEN WHAT
Now $186.40 moves to A-10001 and A-10432 settles at zero
Now The reminder ladder starts pointing at the landlord, not the tenant who left
Now This move-out closes and stops waiting on a decision
Later Elm Street Holdings receives the notices for a debt their tenant ran up
This is a clerk’s consent, not a consequence of closing. Written as an automatic rule it would move a departing tenant’s debt onto a landlord who never agreed to it,
silently, on every move-out in the product.
Cancel Tie it back to A-10001
```

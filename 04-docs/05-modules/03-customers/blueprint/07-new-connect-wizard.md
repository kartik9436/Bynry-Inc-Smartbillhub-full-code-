# 07 · New connect wizard EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 86–97. Extracted text, verbatim — **derived, do not edit.**

**28,219 characters over 12 page(s).**

---

```
How you get here Five doors: the Requests tab primary (AccountsListPage.tsx:914), the standalone list's header (ServiceRequestsListPage.tsx:548, gated to the standalone route),
the list's empty CTA (:593), an inline link in the Transfers tab's wrong-door explainer (TransfersTab.tsx:603), and "Capture another" on the confirmation
(ServiceRequestCapturePage.tsx:1551).
Primary action Submit request ✓ — and submitting sends the customer an acknowledgement. A request is numbered the moment it is created; a draft carries its number and
abandoning one does not reuse it.
Write surfaces Add the request. Edit each review block links back to the step that captured it.
Walked Not walked.
Small finding ServiceRequestCapturePage.tsx:1551 navigates to a hardcoded "/requests/new" although the same file imports SERVICE_REQUEST_NEW_ROUTE. Same shape at
features/metering/OwnerAccount.tsx:434, which builds `/accounts/${id}` rather than calling accountDetailPath. Neither is broken today; both are a route that
will not move when the constant does.
Rules BR-CUS-079 · 089 · 092 · 093 · 095 · 1020 · 1021 · 1032 · 1044
07 New connect wizard EXISTS BEHIND
/:tenant/connections/new  ·  S87  ·  eight steps — the longest flow in the product
The question: "A developer's built six flats. Connect the building, meter every unit, and
bill the developer for the work."
All 8 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
v2.234.15
SO Sam Ortiz
Billing Clerk
Cancel Ask and queue the message
/brazosbend/connections/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
←  New connects
NEW CONNECT
Who is asking, and what for?
Step 1 of 8 · Owner & scope
Save & exit
1 Owner &
scope 2 Premise 3 Units 4 Map
services 5
Plans &
work
orders
6 Charges 7 Communic
ation 8 Review &
confirm
Who is asking
Owner type Owner or developer
Two steps, merged, because they are one question. Who is asking and what
they are building were never separable: the scope decides how many units the next
steps ask for, and the owner is who they are created against.
Owner & scope · /brazosbend/connections/new?step=1 · two steps merged — who is asking and what they are building are one question
g
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▧
✦
▩
▦
▤
⚙
Choose an owner type ▼ Balcones Development LLC
Prefix
BAL
External system reference
if known
What is being built
Scope
A single new dwelling
A multi-unit build
A common area only
How is the work being done?
Our crew did it
We schedule it
The owner becomes a customer.
Three cases, and the sub-lines are the definitions. A single dwelling makes one
unit; a multi-unit build asks how many; a common area only adds shared space to a
building that already exists.
This build has no home yet — the premise arrives on the next step.
Continue →
/brazosbend/connections/new?step=2
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
The premise
Step 2 of 8 · Premise
Save & exit
✓ Owner &
scope 2 Premise 3 Units 4 Map
services 5
Plans &
work
orders
6 Charges 7 Communic
ation 8 Review &
confirm
Premise type
Choose a premise type ▼
Service address
Street address or premise *
212 Balcones Drive
Unit, flat or suite
Named on the next step ▼
Greyed rather than removed, so the address set reads the same
everywhere it is asked for.
City *
Austin
State *
TX ▼
ZIP code *
78704
The record
Parcel or GIS reference
R-0044-1189
Read route
Route 4 · North ▼
This is where an address comes from. An address is kept on the premise and
nowhere else; every meter, account, route, cycle, bill and work order at this build
reaches it by walking back to this record.
The same five boxes the request wizard asks for, so a clerk who captures an
application and a clerk who builds a site are typing into the same shape. What differs is
what happens to it: a request keeps what the APPLICANT said, verbatim and never
overwritten, because it is not a premise yet.
It becomes the service address of every unit below it.
The parcel and the read route are the building’s own, not part of the address. A
unit may carry its own map point where its GIS differs; the address it never carries.
←  Back Continue →
Premise · /brazosbend/connections/new?step=2 · the service address is created here, in the same five boxes the request wizard asks for
Units · /brazosbend/connections/new?step=3
/brazosbend/connections/new?step=3
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
The units
Step 3 of 8 · Units
Save & exit
✓ Owner &
scope ✓ Premise 3 Units 4 Map
services 5
Plans &
work
orders
6 Charges 7 Communic
ation 8 Review &
confirm
How many units
6
✓ Include a common-area unit
UNIT KIND OCCUPANCY
1 Dwelling Vacant
2 Dwelling Vacant
CA Common area —
Showing 3 of 6 units · common area included.
←  Back Continue →
/brazosbend/connections/new?step=4
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
Which services per unit
Step 4 of 8 · Map services
Save & exit
✓ Owner &
scope ✓ Premise ✓ Units 4 Map
services 5
Plans &
work
orders
6 Charges 7 Communic
ation 8 Review &
confirm
How are services chosen?
Apply to all units
One tick per service, written to every unit.
Choose per unit
A row per unit.
Services at each unit
UNIT KIND ELECTRIC WATER SEWER
Per unit is not an alternative shape — it is the shape. One row per unit per service
is what the product stores, each with its own state and its own activation date, so a
build energises one service at one unit at a time.
What this grid adds up to
Service points 20
— dwellings 6 units × 3 services = 18
— common area electric and water = 2
Map services · /brazosbend/connections/new?step=4 · per unit, because the common area takes no sewer · 1 stated absence on this step
Plans & work orders · /brazosbend/connections/new?step=5
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▤
⚙
Unit 1 Dwelling ☑ ☑ ☑
Unit 2 Dwelling ☑ ☑ ☑
Unit 3 Dwelling ☑ ☑ ☑
Unit 4 Dwelling ☑ ☑ ☑
Unit 5 Dwelling ☑ ☑ ☑
Unit 6 Dwelling ☑ ☑ ☑
Common area Common area ☑ ☑ ☐
Tick a column Clear a column Copy unit 1 to all
The common area is why this grid exists. It takes electric and water and no sewer — there is nothing to drain from a
hallway and a car park.
Meters to fit 20 · one per service point
Work orders 9
Every figure on the review step is this grid counted. Change a tick here and the
meters, the plan assignments and the one-time charges all move, which is why it is
worth getting right before the money step rather than after it.
SUB-METER LINKS
Set after the meters exist. Nothing on this build declares a sub-meter, so the
review will show none rather than a zero that reads like an answer.
←  Back Continue →
/brazosbend/connections/new?step=5
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
Plans & work orders
Step 5 of 8 · Plans & work orders
Save & exit
✓ Owner &
scope ✓ Premise ✓ Units ✓ Map
services 5
Plans &
work
orders
6 Charges 7 Communic
ation 8 Review &
confirm
Plan
Choose a published plan ▼
✓ Apply to all units
Work order template
New service connection ▼
Target activation date
11/15/2026 📅
Plan assignments 7 units
Outstanding work 9 orders will be written
←  Back Continue →
/brazosbend/connections/new?step=6
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
Charges
Step 6 of 8 · Charges
Save & exit
✓ Owner &
scope ✓ Premise ✓ Units ✓ Map
services ✓
Plans &
work
orders
6 Charges 7 Communic
ation 8 Review &
confirm
What this build is quoted
CHARGE DESCRIPTION BASIS QTY UNIT AMOUNT
CC-CONN Connection fee per unit 6 $325.00 $1,950.00
CC-METERSET Meter set per meter 20 $45.00 $900.00
CC-CASVC Common-area service point per premise 1 $180.00 $180.00
Quoted $3,030.00
Add a charge Waive a line
Every quantity is counted from the services grid, not typed. Six units, twenty service points, one premise — change a tick
on step 4 and these move with it.
Who is billed
The owner’s account for this address
A-10088 · Balcones Development LLC.
Each unit’s first bill
Split across six accounts that do not exist yet, and the developer never sees an invoice.
The connection itself
Refused: a charge on a build is a debt owed by nobody, and nothing in the product can settle it.
There is ONE money path, and this is the choice that keeps it that way. Charges are tagged to an account number —
the ledger posts against accounts, the frozen money rules are account-shaped, and every rule that says the account would
have grown a silent exception for a payable that is not an invoice, settled by a payment referencing no account.
Taking the money now
Take payment *
Yes — a deposit against the quote ▼
Yes · No, invoice it on activation · No, the developer pays per unit
Method *
Cheque ▼
ACH · Card · Cash · Cheque · Wire
Reference *
CHQ 118420
The cheque or confirmation number.
Amount taken *
1,500.00
A part payment is accepted and the rest stays outstanding.
Posting date *
05/04/2026 📅
The day this payment counts from.
Clearing date
if known 📅
Leave blank on a cheque that has not cleared.
Payment summary
Quoted · three lines $3,030.00
Taken now · cheque CHQ 118420 $1,500.00
Outstanding at activation $1,530.00
Nothing is written until the last step. Every figure here is held on the draft,
the payment included — so a wizard abandoned at step 7 has taken no money
and raised no charge.
The owner’s account is the only one of the three that names a party who
exists at confirm. Splitting across each unit’s first bill names six accounts that will not
exist until people move in, and a charge on the build itself names nobody at all.
THE PRODUCT WILL NOT TAG THIS ACCOUNT YET
The create-a-payer path refuses, and the stated reason is that an account must
name a unit while the owner's account is for the whole build - there being no unit
that means all of them.
⚠  That reason expired on 2026-09-01 and the refusal did not. An account
no longer has to name a unit: a Master Account hangs off the ADDRESS with no
unit at all, which is exactly the owner’s account for the whole build.
A deposit against a quote is not a deposit against an account. This money
settles one-time charges on a build; it is not the security deposit a tenant pays when
they move in, and the two never meet.
Charges · /brazosbend/connections/new?step=6 · the quote, the payer and the money · 1 stated absence on this step
v2.234.15
SO
Sam Ortiz
Billing Clerk
←  Back Continue →
/brazosbend/connections/new?step=7
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
Telling the customer
Step 7 of 8 · Communication
Save & exit
✓ Owner &
scope ✓ Premise ✓ Units ✓ Map
services ✓
Plans &
work
orders
✓ Charges 7 Communic
ation 8 Review &
confirm
Who we are telling
Contact Balcones Development LLC · ops
Email ops@balconesdev.example
Phone (512) 555 ‑ 0199
Preferred language English
What goes out
COMMUNICATION TO CHANNEL TEMPLATE WHEN
Build confirmed Owner · Balcones
Development LLC
Email New connect —
confirmed
On commit ☑
Quote and what is
owed
Owner · Balcones
Development LLC
Email ·
Print
Connection
quote
On commit ☑
Schedule of works Owner · Balcones
Development LLC
Email Work schedule On commit ☑
Unit energised Owner, per unit Email Service live —
per unit
As each unit
activates
☑
Inspection booked Owner · Balcones
Development LLC
SMS — none chosen When the order
is scheduled
☐
Welcome pack Each occupant Print — none chosen When an
account opens
☐
Two are unticked and neither is an oversight. An SMS about a booking nobody has made yet has nothing to say, and the
welcome pack belongs to whoever moves in rather than to the developer.
Choosing a template
Search templates
⚲  connection
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
Connection quote Printable Print Commercial · English v4 Published
Connection quote Email Email Default · English v2 Published
Connection quote — Spanish Email Email Default · Spanish v1 Draft
New connect — confirmed Email Email Default · English v7 Published
Everything here is queued, and nothing is sent. This product writes a row
per message and no sender picks it up — no email, no text, no print file.
A template is chosen along three axes and falls back on two of them. The class
of letter, the customer category, and the language — and where no variant exists for a
category or a language, the default one is used.
The Spanish variant is a draft, and drafts are listed but cannot be picked.
Hiding it would send a clerk looking for something they can see exists; showing it as
choosable would queue a letter nobody has approved.
Print is the floor here too. The quote goes by email AND on paper: an owner who
never opens the address on file still gets the figure they owe.
A PREVIEW OF THE RENDERED LETTER
The template picker names the version that would be used and does not render it.
Nothing on this screen proves the merge fields resolve against a build that does
not exist yet.
Communication · /brazosbend/connections/new?step=7 · what goes out, and which template it uses · 1 stated absence on this step
v2.234.15
SO
Sam Ortiz
Billing Clerk
←  Back Continue →
/brazosbend/connections/new?step=8
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
New connects / New connect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  New connects
NEW CONNECT
What will be created
Step 8 of 8 · Review & confirm
Save & exit
✓ Owner &
scope ✓ Premise ✓ Units ✓ Map
services ✓
Plans &
work
orders
✓ Charges ✓ Communic
ation 8 Review &
confirm
What will be created
WHAT COUNT
Customer 1 · Balcones Development LLC
Premises 1 · 212 Balcones Drive
Units 7 · six dwellings and one common area
Meters 20
Sub-meter links 0 · none declared on this build
Plan assignments 7
One-time charges $3,030.00
These seven counts are a contract, not a summary. The commit must produce exactly them.
From each step
Owner and scope
Owner or developer Balcones Development LLC
Prefix BAL
Scope A multi-unit build
How the work is done We schedule it
The premise
Service address 212 Balcones Drive, Austin, TX 78704
Parcel R-0044-1189
Read route Route 4 · North
From request SR-26-0001 · approved 05/04/2026
Units and services
Dwellings 6 · electric, water, sewer
Common area 1 · electric and water, no sewer
What happens next
WHEN WHAT WHERE IT SHOWS
On
confirm
The build is created across five
modules — the customer, the
premises and units, the meters,
the plans and the charges
New connects tab
On
confirm
Three messages are queued to
the owner
Nothing sends them
yet
On
confirm
Nine work orders are raised, one
of them the gate
The build’s own
record
Next An inspection is booked and
passed
Waiting on clears
Then Units energise one at a time as
their meters are fitted
Partly activated
When a
tenant
arrives
An account opens on that unit Accounts tab
First bill The one-time charges appear on
the owner’s account, not the
tenant’s
A-10088
Nothing before this button has written anything. Every step has been held
on a draft, the payment included.
Activation is not part of this commit. The build is created waiting on an inspection;
no unit is live and no account exists yet.
THE OWNER’S ACCOUNT CANNOT BE TAGGED YET
The charges are quoted and the payer is chosen, and the path that attaches them
refuses on a reason that expired on 2026-09-01. Until that is corrected the quote
stands on the build and the money has nowhere to post.
What this build will NOT do: it opens no accounts, sends nothing, and energises
nothing. Those are three later acts by three different people, and the review says so
rather than letting Confirm imply otherwise.
Review & confirm · /brazosbend/connections/new?step=8 · every field from every step, the seven-count contract, and what happens next · Commits to creates premises, units, meters, plan assignments, work orders
and charges in one commit
Where an approved build lands, and what it becomes
Onto the New connects tab, either raised directly or created by approving a
request — and the list says which.
“Partly activated” is a state, not a warning. A nine-unit build has some units
live and some not; a list answering only activated: yes or no would call that whole
building finished or unfinished, and both would be wrong. A build completes
one unit at a time, and each unit’s account opens on the day its unit does.
The record carries the work orders and what the build is waiting on. On CX-
26-0007 that is one inspection — nothing else is blocked and three units cannot
activate until it passes, which is why it is on the header rather than buried in a
list of nine orders.
Where an approved connect lands · the New connects tab · /brazosbend/accounts?tab=new-connects · What the eight-step connect wizard creates, and what a request becomes
v2.234.15
SO
Sam Ortiz
Billing Clerk
Service points 20
Plans and work orders
Plan Commercial Standard — from the unit
Assignments 7
Work orders 9
Gate inspection — no unit energises until it passes
Charges and money
Quoted $3,030.00 · three lines
Billed to A-10088 · the owner’s account
Taken now $1,500.00 · cheque CHQ 118420
Clearing date not given — the cheque has not cleared
Outstanding at activation $1,530.00
Communication
Going out on commit 3 of 6
Channels Email · Print
Templates Connection quote v4 · New connect confirmed v7 · Work schedule
←  Back Create connection ✓
/brazosbend/accounts?tab=new-connects
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Accounts / New connects ⚲  Search accounts, premises, meters… ⚑ ?
▦
ACCOUNTS
The register
10 tabs · New connects · 2 open builds, 1 activated
+ New connect
The build, opened · CX-26-0007 · /brazosbend/connections/cx-26-0007 · Every field the eight steps collected, on one page · 1 stated absence
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
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
OPEN BUILDS
2
not fully activated
PARTLY ACTIVATED
1
some units live, some not
UNITS AWAITING
11
across the open builds
WAITING ON INSPECTION
1
CX-26-0007
OLDEST OPEN
22 d
CX-26-0006
Open Partly activated Activated All Filter ▾ ⚲  Search by connection #, premise, applicant or request # Columns ▾ ⇩  Export
CONNECTION # PREMISE UNITS SERVICES WORK ORDERS TARGET ACTIVATION WAITING ON STATE FROM REQUEST
CX-26-0007 212 Balcones
Drive
6 Electric · Water ·
Sewer
4 of 9 05/26/2026 An
inspection
In progress SR-26-0001 ↗Open
CX-26-0006 77 Cedar Court 9 Electric · Water 9 of 9 05/12/2026 — Partly
activated
SR-26-0031 ↗Open
CX-26-0004 310 Marigold
Way
2 Electric 2 of 2 04/30/2026 — Activated — ↗Open
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
A build is not activated all at once, which is why Partly activated is a state and not a warning. CX-26-0006 has nine units and some are live while others are not; a list that answered only activated: yes or no would
call that whole building unfinished or finished, and both would be wrong.
The From request column is the spine. CX-26-0007 exists because SR-26-0001 was approved, and CX-26-0004 has none because somebody raised it directly.
/brazosbend/connections/cx-26-0007
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
Accounts / New connects / CX-26-0007 ⚲  Search accounts, premises, meters… ⚑ ?
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
CONNECTION CX-26-0007  ·  FROM SR-26-0001
212 Balcones Drive
In progress Waiting on an inspection 7 units · 3 activated Target 05/26/2026
ELECTRIC WATER SEWER
Add a work order Activate units
Owner and scope · step 1
Owner type Developer
Owner or developer Balcones Development LLC
Prefix BAL
External system reference — not given
Scope A multi-unit build
How the work is done We schedule it
The premise · step 2
Premise type Apartment block
Street address or premise 212 Balcones Drive
Unit, flat or suite — units are named below
City Austin
Charges and money · step 6
CHARGE BASIS QTY UNIT AMOUNT
Connection fee per unit 6 $325.00 $1,950.00
Meter set per meter 20 $45.00 $900.00
Common-area
service point
per
premise
1 $180.00 $180.00
Quoted $3,030.00
Billed to A-10088 · the owner’s account
Taken $1,500.00 · cheque CHQ 118420 · 05/04/2026
Clearing date not given — the cheque has not cleared
Outstanding $1,530.00
THE PAYER IS CHOSEN AND NOT YET TAGGED
Two actions on a build. Activate units is the one that ends the build, and it is
terminal per service — there is no transition back out of activated. Add a work
order raises an ad-hoc job with no template behind it, which gates nothing
unless somebody says so.
Activate units — and the gate that stops it · /brazosbend/connections/cx-26-0007 · Action 1 of 2 on the build · activation is terminal
v2.234.15
SO
Sam Ortiz
Billing Clerk
 y
State TX
ZIP code 78704
Parcel or GIS reference R-0044-1189
Read route Route 4 · North
Premises number PR-0731
This is where the address came from. Every meter, account, route, bill and work order on this build reaches it by walking back
to this record.
Units and services · steps 3 and 4
How many units 6 dwellings
Common-area unit included
Services chosen Per unit — not apply to all
UNIT ELECTRIC WATER SEWER METER STATE
Unit 1 ☑ ☑ ☑ M-5101 Activated
Unit 2 ☑ ☑ ☑ M-5102 Activated
Unit 3 ☑ ☑ ☑ M-5103 Meter fitted
Unit 4 ☑ ☑ ☑ — Awaiting meter
Unit 5 ☑ ☑ ☑ — Awaiting meter
Unit 6 ☑ ☑ ☑ — Awaiting meter
Common area ☑ ☑ ☐ M-5120 Activated
The common area takes no sewer, and that is why the grid was filled in per unit.Apply to all units would have raised
a sewer service point, a meter and a work order for a drain a car park will never need.
Plans and work orders · step 5
Plan Commercial Standard · v3 — from the unit
Plan assignments 7 · one per unit
Target activation 05/26/2026
Work orders 9 · 4 done
Gate Inspection — no unit energises until it passes
The path that attaches an account refuses on a reason that expired on 2026-09-
01 - that an account must name a unit. Until it is corrected the quote stands on
the build and the money has nowhere to post.
Communication · step 7
WHAT WENT OUT CHANNEL TEMPLATE STATE
Build confirmed Email New connect
confirmed v7
Queued
Quote and what is
owed
Email ·
Print
Connection
quote v4
Queued
Schedule of works Email Work schedule
v2
Queued
Unit energised Email Service live ·
per unit
Per unit, as
it happens
Queued is not sent. A row exists for each and no sender picks it up.
Where it came from
Request SR-26-0001 · approved 05/04/2026
Approved by A. Whitfield
Created 05/04/2026 14:22
Fee outstanding on the request $105.00
Live state
State In progress
Waiting on an inspection
Units activated 3 of 7
Service points live 8 of 20
Activated at — not yet
The inspection is what the whole build is waiting on. Nothing else is
blocked and four units cannot energise until it passes.
/brazosbend/connections/cx-26-0007
SMARTBillHub ☰
BB Brazos Bend Utilities
Accounts / 212 Balcones Drive ⚲  Search accounts, premises, meters… ⚑ ?
←  The register
Add a work order — ad-hoc, and not a gate · /brazosbend/connections/cx-26-0007 · Action 2 of 2 on the build · an order with no template behind it
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
CONNECTION CX-26-0007
212 Balcones Drive
In progress Waiting on an inspection
Add a work order Activate units
Activate units on CX-26-0007
Service goes live and billing can start
✕
WHICH UNITS
UNIT SERVICES METER GATE ORDER CAN ACTIVATE?
Unit 3 E · W · S M-5103 WO-26-0338 · Waiting No — gate not passed
Unit 4 E · W · S — — No — no meter
Unit 5 E · W · S — — No — no meter
Unit 6 E · W · S — — No — no meter
Nothing here can be activated, and the screen says which of two reasons applies to each. Unit 3 has its meter and is waiting on the inspection; units 4 to 6 have no
meter at all.
WHAT THE GATE IS
A work order permits energisation, and it is not the same order for every service. Electric and water gate on the meter set; gas gates on the light-up, not the meter set
— gating gas on the meter set would energise an account for a service nobody has lit, and bill it.
Activation is terminal. A service that has been activated has nowhere left to go: there is no transition back to pending, in progress or on hold.
Cancel
Activate the selected units
/brazosbend/connections/cx-26-0007
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
Accounts / 212 Balcones Drive ⚲  Search accounts, premises, meters… ⚑ ?
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
←  The register
CONNECTION CX-26-0007
212 Balcones Drive
In progress Waiting on an inspection
Add a work order Activate units
Add a work order to CX-26-0007
Something the templates did not cover
✕
THE JOB
Type *
Trench and lay — second water main
Matched against the job catalogue where it can be.
How you get here Three doors: the New connects tab primary (AccountsListPage.tsx:923), the tab's empty CTA (NewConnectsTab.tsx:783), and Resume on a parked draft
(parkedDrafts.tsx:416).
Primary action Create connection ✓, whose answer offers Open the connection → — which lands on the account's Work tab, not a screen of its own.
Write surfaces Add premises, units, meters, plan assignments, work orders and charges, in one commit. Charges bill to a master account, per BR-CUS-083.
Walked Not walked.
Rules BR-CUS-083 · 1010 · 1011 · BR-MET-1161
04
Ending service
Four terminal paths, and the product is careful that they are visibly different: a
tenancy ends (move-out), a customer moves to another of your addresses
(transfer), service is cut for non-payment (disconnect), and a cut customer is
finally finished (close-out).
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
Scope *
Per premise ▼
Per premise · per unit · per asset
Due *
05/20/2026 📅
How is it done
We schedule it ▼
Our crew · we schedule it · done outside our system and recorded here.
This order gates energisation
Off by default.
WHAT ADDING IT WILL DO
THEN WHAT
Now A tenth order appears on this build, Planned
Now It carries no template, which its record says rather than leaving blank
Not now It changes no unit’s state and gates nothing
Why an order remembers which template raised it, and which version. A tenant editing a template must not silently change what a crew was told to do in January — so the
version is stamped at the raise and never rewritten.
Cancel Add the work order
```

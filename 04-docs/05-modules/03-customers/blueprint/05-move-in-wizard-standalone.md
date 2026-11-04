# 05 · Move-in wizard · standalone EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 75–85. Extracted text, verbatim — **derived, do not edit.**

**26,445 characters over 11 page(s).**

⚠ **The blueprint prints this entry on the same page as 06 · Service request capture EXISTS BEHIND**, so the text below covers all of them. Read the heading you want.


---

```
what else is on them.
How you get here Account-scoped: the S21 Move-in button (AccountDetailPage.tsx:728) and the move-out wizard's done screen, which chains straight into it
(MoveOutWizard.tsx:1441).
Primary action Complete move-in ✓
Write surfaces Add POST /accounts/{fromId}/move-in. Park ?park=1, resumable from the Move-ins tab.
Walked Not walked.
Rules BR-CUS-017 · 020 · 021 · 022 · 024 · 056 · BR-SHL-046
05 Move-in wizard · standalone EXISTS BEHIND
/:tenant/move-ins/new  — the same MoveInWizard as screen 04, entered with no account chosen
What it is A second address, not a second screen. Same component; step 1 asks for the unit and derives the outgoing account from it, so nothing is guessed.
How you get here Four doors: the S17 header Move-in (AccountsListPage.tsx:1217), the Move-ins tab primary (:984), the tab's empty-state CTA (MoveInsTab.tsx:1188), and
Resume on a parked draft (parkedDrafts.tsx:416).
Walked Not walked.
06 Service request capture EXISTS BEHIND
/:tenant/requests/new  ·  S85  ·  six steps
The question: "Somebody's asking us for something. Write it down and give them a
number they can quote."
All 6 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/requests/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
←  Requests
NEW REQUEST
Who is this request for?
Step 1 of 6 · Customer
Save & exit
Addresses&
Customer · /brazosbend/requests/new?step=1
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
1 Customer 2 Connection 3 Addresses &
property 4 Documents 5 Fees 6 Check & submit
Channel *
Counter ▼
Full name *
Miller, Sarah
Email
s.miller@example.com
Phone
(512) 555-0142
Date of birth
if known 📅
Driver's licence
TX ••••882
SSN
•••-••-4417
Add a co-applicant
Optional on a staff-raised request.
Stored encrypted at the application layer, shown as the last four.
Continue →
/brazosbend/requests/new?step=2
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
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Requests
NEW REQUEST
What are they asking for?
Step 2 of 6 · Connection
Save & exit
✓ Customer 2 Connection 3 Addresses &
property 4 Documents 5 Fees 6 Check & submit
Category *
New connection ▼
Sub-category
Residential dwelling ▼
Which services does this property need? *
3 of 11 selected ▼
Electric ✕ Water ✕ Sewer ✕
Pick from the eleven this utility runs.
When each one is wanted
SERVICE REQUESTED START
Electric 05/12/2026
Water 05/12/2026
Sewer 05/12/2026
Each service carries its own start. A block that needs electric on the 12th and sewer a fortnight later is one request and not
two, so the date sits per service rather than once on the form.
Connection date
if known 📅
Thewholejob wheretheapplicanthasadateinmind
Services are asked here because this is where the request stops being a
name and becomes a job. The address comes next; what they want comes first,
because it is what decides which questions the rest of the wizard has to ask.
A multiselect, not eleven rows. A clerk at a counter picks two or three of eleven, so
the list is somewhere to look rather than something to read: the picked ones sit under
the box and the other eight stay out of the way.
WHETHER A SERVICE CAN ACTUALLY REACH THIS ADDRESS
Each service on a request carries a flag for that, and it is NULL until somebody
surveys - a real third state that is neither yes nor no. Nothing on this wizard sets it,
so every service picked here is a request and never a promise.
Connection · /brazosbend/requests/new?step=2 · services picked from a multiselect, each with its own start · 1 stated absence on this step
Addresses · /brazosbend/requests/new?step=3 · the service address, the unit count and the billing address — the plot is gone · 3 stated absences on this step
v2.234.15
SO Sam Ortiz
Billing Clerk
The whole job, where the applicant has a date in mind.
←  Back Continue →
/brazosbend/requests/new?step=3
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
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Requests
NEW REQUEST
Addresses
Step 3 of 6 · Addresses
Save & exit
✓ Customer ✓ Connection 3 Addresses &
property 4 Documents 5 Fees 6 Check & submit
Service address
Street address or premise *
212 Balcones Drive
Unit, flat or suite
Unit 3
City *
Austin
State *
TX ▼
ZIP code *
78704
The property
How many units are on this property? *
6
What the applicant says is there.
Billing address
✓ Billing address same as service
Billing address
—
Filled in only when the box above is cleared.
What the register matched
LOOKED FOR MATCHED CONFIDENCE
212 Balcones Drive · Unit 3 PR-0731 · 212 Balcones Drive Exact
Unit 3 U-001884 · Unit 3 Exact
Units on the property · 6 6 units on PR-0731 Agrees
The address is the APPLICANT’S, not a record. It is matched against the
premises register below it and the match is shown beside it — never written over it.
THE ADDRESS IS ONE FIELD TODAY, NOT FIVE
The request keeps the address exactly as the applicant gave it, in a single line,
and never overwrites it with whatever the resolver matches. Five boxes is five
columns - and the reason there is one is that an applicant's address is not a
premises yet.
NOTHING HOLDS A UNIT COUNT
No column on the request records how many units a property has. Today the
number lives only in whatever the clerk typed into the notes, which no screen and
no rule can read.
The plot has gone from this step. It was the one field here asking a clerk for a land-
registry reference they would have to go and look up, on a form filled in while somebody
waits.
THE PLOT COLUMN STAYS, AND STOPS BEING WRITTEN
Removing a control is not dropping a column. The request still has somewhere to
keep a plot or parcel reference, and nothing on this wizard writes it any more - so
a request captured here carries none, and the surveyor's own record is where it
belongs.
The match is evidence, never a decision. What the resolver found sits beside what
the applicant said.
An address that matches nothing is not refused. It is flagged as having no
premises on record, and the request carries on - because a new connection at a
field with no address yet is exactly the job this wizard exists for.
←  Back Continue →

Documents · /brazosbend/requests/new?step=4 · the attach path is built and the file store is not · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
/brazosbend/requests/new?step=4
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
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Requests
NEW REQUEST
Documents
Step 4 of 6 · Documents
Save & exit
✓ Customer ✓ Connection ✓ Addresses &
property 4 Documents 5 Fees 6 Check & submit
DOCUMENT REQUIRED FILE UPLOADED BY STATE
Proof of identity Yes driving-licence.pdf · 1.2
MB
S. Ortiz ·
05/04/2026
Verified
Proof of address or
occupancy
Yes lease-212-balcones.pdf
· 840 KB
S. Ortiz ·
05/04/2026
Not checked
Tenancy agreement or
deed
No — — Nothing
attached
Site plan or unit
schedule
Yes block-plan.pdf · 3.1 MB S. Ortiz ·
05/04/2026
Rejected ·
unreadable
Anything else — — — Nothing
attached
All Required Missing Rejected Attach a file Add another document
Attaching one
Document type *
Proof of identity ▼
Eight designed types, plus Anything else for whatever the applicant
brought that helps.
File *
driving-licence.pdf · 1.2 MB
Name and size are recorded, with who attached it and when.
What it proves
Identity and current address
Required on this request
Attaching a file is not the same as verifying it. Every attachment lands Not checked and stays there until somebody looks at
it.
A missing document never blocks the request being created. It is chased
afterwards, and the request shows as waiting on documents until somebody clears it.
THERE IS NO FILE STORE
The path to attach one is built: the type, the name, the size, who uploaded it and
when are all recorded. What is recorded is a REFERENCE to a file this product
does not hold, so nothing here can open, re-read or re-send the document later.
Two different facts decide whether a document is required and both feed the
same approval gate: the utility's own checklist for this request type, and a clerk ticking
required on this request because of something about this applicant.
Approval is blocked until every required document is checked — not until one is
attached.
←  Back Continue →
/brazosbend/requests/new?step=5
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
←  Requests
NEW REQUEST
Fees
Step 5 of 6 · Fees
Save & exit
Add &
Fees · /brazosbend/requests/new?step=5 · the fee is taken here and posts nothing — finance reconciles
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
✓ Customer ✓ Connection ✓ Addresses &
property ✓ Documents 5 Fees 6 Check & submit
What this request is quoted
CHARGE DESCRIPTION BASIS QTY UNIT AMOUNT
CC-REQFEE Application fee per request 1 $25.00 $25.00
CC-EXPED Expedited processing per request 1 $60.00 $60.00
CC-METERT Meter test on connection per meter 3 $15.00 $45.00
Quoted $130.00
Add a fee Waive a line
Taking the money
Fee timing *
Collect now ▼
Collect now · Collect later
Method *
Cash ▼
Cash · Card · Cheque
Amount taken *
25.00
A part payment is accepted.
Receipt number *
RCP-26-4471
The number on the receipt the clerk has just written.
Payment summary
Quoted $130.00
Settled by an invoice $0.00
Collected at the counter · cash · RCP-26-4471 $25.00
Outstanding $105.00
This takes money and posts nothing. No journal line, no invoice, no account
— there is no account yet.
The quote is snapshotted the moment money is taken. Adding a line afterwards
must not retro-change what the clerk handed over a receipt for, so $130.00 is frozen
onto the request beside the $25.00.
Outstanding is signed and is never clamped at zero. If a counter took more than
the quote, the screen says so.
Collecting twice is refused by name. The same receipt number again answers with
what is already recorded; a DIFFERENT one on a request that has already been
collected is refused and names the receipt it already holds.
A waived line leaves the quote and stays on the request with its reason, so a fee
nobody paid and a fee somebody excused never look the same afterwards.
←  Back Continue →
/brazosbend/requests/new?step=6
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
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Requests
NEW REQUEST
Check and submit
Step 6 of 6 · Check
Save & exit
✓ Customer ✓ Connection ✓ Addresses &
property ✓ Documents ✓ Fees 6 Check & submit
The applicant ✎Step 1
Channel At the counter
Full name Miller, Sarah
Email s.miller@example.com
Phone (512) 555 ‑ 0142
Documents ✎Step 4
DOCUMENT FILE STATE
Proof of identity driving-licence.pdf Verified
Proof of address lease-212-balcones.pdf Not checked
Site plan block-plan.pdf Rejected
Runbooks
Reports
Settings
▦
▤
⚙
Date of birth 04/11/1988
Driver’s licence TX ••••882
SSN •••-••-4417
What they are asking for ✎Step 2
Category New connection
Sub-category Residential dwelling
Services Electric · Water · Sewer
Requested start 05/12/2026, all three
Connection date — not given
Addresses and property ✎Step 3
Service address
Street address or premise 212 Balcones Drive
Unit, flat or suite Unit 3
City Austin
State TX
ZIP code 78704
Units on the property 6
Billing address Same as service
Matched premises PR-0731 · exact
Matched unit U-001884 · exact
Plot or parcel — not asked on this wizard
Tenancy agreement — Nothing attached
Two required documents are not yet cleared.
Fees ✎Step 5
Quoted $130.00 · three lines
Fee timing Collect now
Taken $25.00 · cash · RCP ‑ 26 ‑ 4471
Settled by an invoice $0.00
Outstanding $105.00
$105.00 is still owed and this request can still be submitted. The money is
not what gates it; the unchecked documents are.
On submit ✎Step 6
Request number SR-26-0001 · already allocated
State Draft →  Submitted
Waiting on Documents
The number exists before the submit. A draft carries its own number, so a clerk can
quote it to somebody standing at the counter who has not finished answering.
What goes out to the applicant
The second row is what makes this submission useful. Two required documents are not cleared, and telling them so as they leave the counter is the difference between a request that moves next week and one that
sits.
SEND WHAT IT SAYS TO CHANNEL TEMPLATE WHEN
☑ The request is in, and its number Miller, Sarah Email Request acknowledged v6 On submit
☑ What we still need from them Miller, Sarah Email Documents outstanding v2 On submit
☑ A receipt for the $25.00 taken Miller, Sarah Print Counter receipt v1 Already handed over
☐ That $105.00 is still owed Miller, Sarah Email — none chosen On submit
☐ The decision, when it is made Miller, Sarah Email · SMS Request decided v4 On approve or refuse
Choosing a template
Search templates
⚲  request
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
Request acknowledged Email Email Default · English v6 Published
Documents outstanding Email Email Default · English v2 Published
Request decided Email Email Default · English v4 Published
Request acknowledged SMS SMS Default · English v2 Draft
Everything here is queued, and nothing is sent. This product writes a row per message and no sender picks it up — no email, no text, no print file.
Check · /brazosbend/requests/new?step=6 · Commits to creates a NUMBERED request — a draft carries its number · every field from all six steps, and 1 stated absence among them
Where a captured request lands, and what it becomes
Onto the register’s Requests tab, already numbered — a draft carries its
number from the moment it is started, so a clerk can quote it to somebody still
standing at the counter.
⚠  Requests is the front door, and the other five queues are what a request BECOMES
A service request carries an outcome, and the five job outcomes are exactly the other five flows in this document: new_connection, move_in, move_out, transfer, disconnect.
Approve SR-26-0001 and a build appears on the New connects tab; the build names the request it came from, and the $105.00 still outstanding on it travels along rather than
being lost at approval. A build raised directly has no request and its column says so — both are ordinary, and nobody goes looking for a request that never existed.
This is the spine of the whole document, and until now no drawing in it had shown the link.
“Waiting on” is not the state, and that is the column’s whole point. One
request is Approved and waiting on a scheduled date; another is Under review
and waiting on a supervisor. A list showing only the state puts those two in the
same bucket and tells a clerk nothing about which one they can move.
The record is the one detail view that exists in the product today — three
tabs, Applicant, Documents and History — and the drawing follows it rather than
proposing a new shape. On it, the money does not gate approval and the
documents do: $105.00 outstanding is finance’s to reconcile; an unchecked
identity document is this clerk’s.
Where a captured request lands · the register’s Requests tab · /brazosbend/accounts?tab=requests&f.state=open · The front door · and the tab the six-step capture commits into
v2.234.15
SO
Sam Ortiz
Billing Clerk
A text never replaces a posted notice. Where a decision has to be put in writing, the SMS on the last row is a courtesy alongside it and never instead of it.
The receipt is already in their hand. It was written at the counter when the $25.00 was taken, so this row records what was given rather than queueing a second copy.
A template resolves on three axes and falls back on two. The class of letter, the customer category and the language — and where no variant exists for a category or a language, the default one is used.
The draft version is listed and cannot be picked. Hiding it sends a clerk looking for something they can see exists; offering it would queue a letter nobody has approved.
←  Back Save as draft Submit request ✓
/brazosbend/accounts?tab=requests&f.state=open
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts / Requests ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
ACCOUNTS
The register
10 tabs · Requests is one of them · 4 open, 1 refused
+ New request
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
OPEN WAITING ON SOMEONE APPROVED, NOT STARTED REFUSED THIS MONTH OLDEST OPEN
The request, opened · SR-26-0001 · /brazosbend/requests/sr-26-0001 · The one detail view that exists in the product today · three tabs
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
◉
▩
▤
▧
✦
▩
▦
▤
⚙
4
not in a terminal state
3
a person, a date or a document
1
no job raised yet
1
with a reason on each
23 d
SR-26-0039
Open Waiting Approved Closed All Filter ▾ ⚲  Search by request #, applicant, address or meter Columns ▾ ⇩  Export
REQUEST # TYPE APPLICANT ADDRESS RECEIVED CHANNEL AGE WAITING ON STATE
SR-26-0001 New connection Miller, Sarah 212 Balcones Drive · Unit 3 05/04/2026 Counter 0 d Documents Submitted ↗Open
SR-26-0046 Move-in Ncube, T. 1408 Elm Street · Unit E 04/28/2026 Portal 6 d A scheduled date Approved ↗Open
SR-26-0042 Disconnect Okafor, D. 1408 Elm Street · Unit A 04/19/2026 Phone 15 d A supervisor Under review ↗Open
SR-26-0039 Transfer Tan, Wei 1408 Elm Street · Unit B 04/11/2026 Counter 23 d — In fulfilment ↗Open
SR-26-0031 New connection Cedar Court Properties LLC 77 Cedar Court 03/30/2026 Email 35 d — Refused ↗Open
1–5 of 5  ·  Rows per page 50 100 200    ‹ ›
SR-26-0001 is the request the six-step capture just committed — and it arrives already numbered, because a draft carries its number from the moment it is started. The clerk can quote it to somebody still standing at
the counter.
“Waiting on” is not the state, and that is the column’s whole point. SR-26-0046 is Approved AND waiting on a scheduled date; SR-26-0042 is Under review and waiting on a supervisor.
Type is the OUTCOME, and it is how this queue feeds the other six. A request resolves to one of five jobs — new connection, move-in, move-out, transfer, disconnect — or to a refusal.
/brazosbend/requests/sr-26-0001
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
Accounts / Requests / SR-26-0001 ⚲  Search accounts, premises, meters… ⚑ ?
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
REQUEST SR-26-0001  ·  NEW CONNECTION
Miller, Sarah
Submitted Waiting on documents Counter Received 05/04/2026
⌂ 212 Balcones Drive · Unit 3  ·  Austin, TX 78704
Refuse Ask for more Approve
Applicant Documents History
Approving this is what creates the job. A request resolves to one of five outcomes and this one is a new connection, so approval raises a build on the New connects tab and links it back here.
WHAT THEY ASKED FOR
Type New connection
Sub-category Residential dwelling
Services Electric · Water · Sewer
Requested start 05/12/2026, all three
Units on the property 6
WHO IS ASKING
Applying as A person
Full name Miller, Sarah
DOCUMENTS · 4
DOCUMENT FILE STATE
Proof of identity driving-licence.pdf Verified
Proof of address lease-212-balcones.pdf Not checked
Site plan block-plan.pdf Rejected
Tenancy agreement — Nothing attached
Two required documents are not cleared, and that is what waiting on
documents means. It did not stop the request being created and it does stop
approval — which is why the state and the waiting-on are two different fields.
FEES
Three actions, and what each one does. The decision panel is the point of this
record — everything above it is evidence for it. Approve resolves the request to
one of five outcomes and raises that job; Refuse is terminal and reopenable with
a reason; Ask for more keeps it open and moves waiting on to the applicant,
which is why that is a column and not a state.
Approve the request — and what it creates · /brazosbend/requests/sr-26-0001 · Action 1 of 3 on the request · the one that makes a job
v2.234.15
SO
Sam Ortiz
Billing Clerk
Email s.miller@example.com
Phone (512) 555 ‑ 0142
Channel At the counter
THE ADDRESS THEY GAVE
As given 212 Balcones Drive, Unit 3, Austin TX 78704
Matched premises PR-0731 · exact
Matched unit U-001884 · exact
What they typed is kept beside what we matched, never replaced by it. The resolver is evidence; if the two ever disagree,
the clerk can see both.
FEES
Quoted and taken
Quoted · three lines $130.00
Settled by an invoice $0.00
Collected · cash · RCP-26-4471 $25.00
Outstanding $105.00
The money does not gate approval and the documents do. $105.00 outstanding
is finance’s to reconcile; an unchecked identity document is this clerk’s.
HISTORY
WHEN WHAT WHO
05/04/2026 09:22 Created as a draft S. Ortiz
05/04/2026 09:31 Fee collected · $25.00 cash S. Ortiz
05/04/2026 09:33 Submitted S. Ortiz
05/04/2026 14:10 Site plan rejected · unreadable A. Whitfield
/brazosbend/requests/sr-26-0001
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
Accounts / Miller, Sarah ⚲  Search accounts, premises, meters… ⚑ ?
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
←  The register
REQUEST SR-26-0001  ·  NEW CONNECTION
Miller, Sarah
Submitted Waiting on documents
Refuse Ask for more Approve
Approve SR-26-0001
This creates real service and real charges
✕
WHAT IS THIS REQUEST?
A new connection
Raises a build on the New connects tab, linked back to this request.
A move-in
Opens an account on a unit that already has service.
Amoveout
Refuse the request — terminal, and reopenable · /brazosbend/requests/sr-26-0001 · Action 2 of 3 on the request · a reason is required
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
⚙
A move-out
Closes an account and frees its unit.
A transfer
One customer, a different address of ours.
A disconnect
Raises a case and starts the notice ladder.
Nothing is preselected, deliberately. The resolver matched this address to PR-0731 exactly, and that is EVIDENCE — not the decision.
WHAT APPROVING WILL DO
THEN WHAT
Now This request becomes Approved and the outcome is recorded against your name
Now A build is raised on the New connects tab, naming this request
Now The $105.00 still outstanding here travels with it
Next The build’s own wizard asks for units, services, plans and charges
Not now No account opens, no meter is fitted, nothing is energised
Two required documents are still unchecked — an identity proof and a rejected site plan. That is what makes this request waiting on documents, and approval is exactly the
thing it blocks.
Cancel
Approve and raise the build
/brazosbend/requests/sr-26-0001
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
Accounts / Miller, Sarah ⚲  Search accounts, premises, meters… ⚑ ?
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
REQUEST SR-26-0001  ·  NEW CONNECTION
Miller, Sarah
Submitted Waiting on documents
Refuse Ask for more Approve
Refuse SR-26-0001
The applicant is told; the request stays on record
✕
WHY
Reason *
Not our service area ▼
Not our service area · Documents not provided · Applicant withdrew · Duplicate of another request · Other
What to tell them
212 Balcones Drive falls outside the Brazos Bend boundary. The city utility covers this street.
Goes into the refusal letter.
WHAT REFUSING WILL DO
Ask for more — the state that is not a refusal · /brazosbend/requests/sr-26-0001 · Action 3 of 3 on the request · and the one clerks reach for most
v2.234.15
SO
Sam Ortiz
Billing Clerk
THEN WHAT
Now The request becomes Refused, which is terminal
Now A refusal letter is queued to the applicant
Now The $25.00 already collected stays collected — refunding it is finance’s act, not this one
Later It can be reopened, with a reason, from refused or withdrawn and from nowhere else
Refusing does not undo the money. $25.00 was taken at the counter against a $130.00 quote. The request closes owing $105.00 that will never be collected and holding
$25.00 that may have to be given back — both visible, because a refusal that silently wrote off a receipt is how a cash drawer stops reconciling.
Cancel Refuse the request
/brazosbend/requests/sr-26-0001
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
Accounts / Miller, Sarah ⚲  Search accounts, premises, meters… ⚑ ?
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
REQUEST SR-26-0001  ·  NEW CONNECTION
Miller, Sarah
Submitted Waiting on documents
Refuse Ask for more Approve
Ask SR-26-0001 for more
It stays open and stops waiting on you
✕
WHAT IS NEEDED
✓ A readable site plan — the one attached was rejected
✓ Proof of identity checked and verified
A connection date
Something else
Message to the applicant
The site plan you sent will not open. Please send it again as a PDF, and bring photo id to the counter.
Sent to them and kept on the request’s history.
WHAT THIS WILL DO
THEN WHAT
Now The request becomes More info — open, not refused
Now Waiting on changes from documents to the applicant
Now A message is queued to them
Then It leaves your queue and stays on theirs, which is the whole point of the state
This is why waiting on is a column and not a state. The request is open in both cases; what changes is whose move it is.
```

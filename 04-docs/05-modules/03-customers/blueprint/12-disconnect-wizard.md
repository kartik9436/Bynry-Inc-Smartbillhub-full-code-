# 12 · Disconnect wizard BLOCKED

**Source:** `accounts-blueprint.pdf`, pages 120–131. Extracted text, verbatim — **derived, do not edit.**

**30,763 characters over 12 page(s).**

---

```
This record has no actions, and that is the answer rather than a gap. A
move-in and a transfer are records of acts that have already happened — there
is nothing left to decide on them, so the only controls are doors to the accounts
they produced. Drawing a button here would invent a decision the product does
not offer.
How you get here Three doors: Transfers tab primary (AccountsListPage.tsx:930), empty CTA (TransfersTab.tsx:709), parked Resume.
Primary action Complete the sale ✓ — one door running all five staged writes inside one transaction: start, name the buyer, set the date, show the money, reassign. All of it lands
or none of it does.
⚠  Blocked in the
shipped screen
The buyer is never asked for. The five steps on the running product are still the old job — Leaving · Final reads · Arriving · Money · Review — so the wizard posts a
destination unit, two dates and two elections that the commit does not read, and never sends the buyer, which the commit requires. Every attempt refuses at the
second of five writes, naming a field that appears on none of the screens.
Walked Not walked.
Rules BR-CUS-086 · 590 · 1030 · 1031
12 Disconnect wizard BLOCKED
/:tenant/disconnects/new  ·  S90  ·  five steps
The question: "They haven't paid in three months. Cut them — lawfully, and tell me
what I'm not allowed to assume."
The five steps are the five the code names and every figure below is the
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
⚙
Identifier given Driving licence
Buyer matched or created Matched — already on file
Changeover read 2 jobs raised · both completed 05/07
Committed by S. Ortiz · 05/07/2026 14:06
WHAT DID NOT CHANGE
Account number A-11455
Unit and meters Unchanged
Plan Unchanged
Service agreements Unchanged
Status Active throughout
The ledger One continuous history, 38 months
Bills issued to Tan, Wei Still in their name, unaltered
A bill is a record of what was sent. Every invoice, payment and journal entry issued before the sale still names the seller and
always will.
 y y
Nothing moved, and that is why this is cheap. The account carries its own ledger
and the account did not go anywhere, so the balance never moved either.
WHAT THIS RECORD DOES NOT SAY
Whether the buyer was shown the figure Not decided anywhere
The property’s owner record Still names the seller
The account’s contact details Still the seller’s
THE REFERENCE ABOVE
No transfer numbering series exists, so this sale carries no reference in the
database today. The header is drawn as it will read once one is set up; until then
the record is found by its account and its date.
The contact details stayed with the account, and somebody has to fix
that. The bill email, the paperless election and the autopay instruction all belong
to the account, not to the customer — so after a sale they are still the seller’s until
a clerk changes them on the account screen.
The five steps are the five the code names, and every figure below is the
module’s own. Ten protection questions of which three can be answered; three
protections, each with a different life; the send and the proof kept as two
separate records; three fee codes of which one is ever charged; and a cut that
nothing performs on the day it is scheduled for. This wizard schedules — it
never cuts.
All 5 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/disconnects/new?step=1
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
Disconnects / Disconnect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Disconnects
DISCONNECT
Whose service, and why
Step 1 of 5 · Account & reason
Save & exit
1 Account & reason 2 Protections 3 Notice & date 4 Fees & consequences 5 Review
Search for the account *
⚲  bramble
Account number, customer name, service address or meter number.
ACCOUNT CUSTOMER SERVICE ADDRESS OWED TIER
A-11812 Bramble Bakery 142 Bakers Row · Suite 1 $2,410.00 Final notice
A-11602 Ncube, T. 1408 Elm Street · Unit E $512.80 Case already open
One open case at a time. The second row has a case running already and cannot start another.
The customer
Account number A-11812
Customer Bramble Bakery
Customer number C-00271
Customer kind Company
Category Commercial · Small commercial
Account status Active · billable
Opened 09/10/2024
Premises 142 Bakers Row · PR-0288
Unit U-000744 · Suite 1
Service address 142 Bakers Row, Silver Creek, TX 78611
Contact p.okafor@bramblebakery.example
Phone (512) 555 ‑ 0188
Preferred language English
Why is service being cut?
Reason
Non-payment ▼
Non-payment · Unsafe installation · Tampering or theft · Premises abandoned · Customer
asked
Only non-payment has a lawful path to a cut today. A cut is scheduled after
the final certified notice, and the ladder that produces one runs on debt.
And the reason drives nothing else. It is recorded on the case and no rule branches
on it — no fee, no notice period and no protection changes because of what is chosen
here.
Which services
CUT SERVICE METER WHAT HAPPENS TO IT
☑ Electric M-3391 Full disconnection
☑ Water M-3392 Full disconnection
☐ Trash — Left on
A cut need not take everything, and each service says what happens to it rather
than leaving the treatment implied.
A RESTRICTOR INSTEAD OF A CUT
A flow restrictor — leaving a trickle rather than nothing — is refused by name.
Nothing in this product can express a partial supply, and a screen that offered it
would be promising a state no meter, bill or read could represent.
Where the ladder has got to
Tier 3 of 3 · final notice
Friendlyreminder 04/14/2026
Whose service, and why · /brazosbend/disconnects/new?step=1
v2.234.15
SO
Sam Ortiz
Billing Clerk
 g g
Paperless billing Off
Autopay Off
The money — why the ladder is running
Where this account stands
Balance $2,410.00
Oldest item 62 days past due
Deposit on file $450.00
Last payment $180.00 · 03/02/2026
Payment plan None
Ladder floor $25.00 — this is well above it
The bills behind that figure
BILL ISSUED DUE AMOUNT STATE
INV-26-0411 03/08/2026 03/22/2026 $840.00 Overdue
INV-26-0538 04/08/2026 04/22/2026 $795.00 Overdue
INV-26-0662 05/08/2026 05/22/2026 $775.00 Issued
Three unpaid bills reconcile to the balance exactly. $840.00 plus $795.00 plus $775.00 is $2,410.00, and the newest is not
yet overdue — the ladder is running on the two above it.
Friendly reminder 04/14/2026
10-day notice 04/24/2026
Final notice 05/09/2026
Case raised by S. Ortiz · 04/14/2026
Case reference DSC-26-0003
Continue →
/brazosbend/disconnects/new?step=2
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
Disconnects / Disconnect ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Disconnects
DISCONNECT
Protections — anything that stops this
Step 2 of 5 · Protections
Save & exit
✓ Account & reason 2 Protections 3 Notice & date 4 Fees & consequences 5 Review
Ten questions, and only three have an answer
This step exists because cutting service to a protected household is the most serious thing this product does. It
never says all clear: it lists what was asked, what answered, and what nothing in this product can check.
QUESTION ANSWER ANSWERED ON WHO ANSWERS IT
Medical equipment on site? No 05/09/2026 The product
Weather moratorium in force? No 05/09/2026 The product
An active payment plan? No 05/09/2026 The product
An open dispute? — not
checked
— Nobody — no table holds one
Life-support registration? — not — Nobody — not modelled
What you can do here
Record a protection
Protection
Medical certificate ▼
Medical certificate · Payment plan · Weather moratorium.
PROTECTION HOW LONG IT LASTS ENDS WHEN
Medical certificate Until a date The certificate expires
Payment plan No date of its own The plan ends or is
missed
Weather A date window The regulator’s window
Protections — anything that stops this · /brazosbend/disconnects/new?step=2
v2.234.15
SO Sam Ortiz
Billing Clerk
 pp g
checked
 y
Age or disability protection? — not
checked
— Nobody — not modelled
An assistance application
pending?
— not
checked
— Nobody — not modelled
A recent partial payment? — not
checked
— Payments knows — not read
here
Has the notice period been
served?
— not
checked
— Step 3 knows — not read here
Is this a landlord-billed premises? — not
checked
— Nobody — not modelled
Seven of the ten cannot be answered by anything. They are drawn as questions rather than hidden, because a screen
that showed only the three it can answer would read as a clean check on a household nobody has actually checked.
An answer from three weeks ago is not the same claim as an answer from this morning, which is why the date sits beside
each one.
moratorium closes
Certificate expires
Not given 📅
A medical certificate is the only one that carries its own date.
Reference
Not given
Recording one stops this immediately. A protected account is refused a cut date
before any date is written, and the case moves to held rather than cancelled — the
money is still owed.
Or stop the ladder without a protection
Clerk error
It should never have been started.
Disputed
The customer is contesting the bill.
The regulator told us to
An instruction from outside.
What happened
Customer disputes INV-26-0411 on a meter reading
Recorded with the act and with who did it.
Three reasons, and the list is closed. A fourth reason is a fourth way to stop
chasing a real debt, and that needs a decision rather than a new word in a
dropdown.
NONE OF THIS IS OPERABLE ON THE SHIPPED SCREEN
The protections step as built takes no input at all — it receives nothing to write to
and offers no control. Everything on this side of the step is drawn from what the
module can already do: it records protections, lifts them, and stops a ladder for
one of three reasons.
←  Back Continue →
/brazosbend/disconnects/new?step=3
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Disconnects / Disconnect ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
←  Disconnects
DISCONNECT
The notice, and the date
Step 3 of 5 · Notice & date
Save & exit
✓ Account & reason ✓ Protections 3 Notice & date 4 Fees & consequences 5 Review
What has gone out already
NOTICE SENT CHANNEL DELIVERED?
Proof that it was served
Sending and proving are two different records, and only one of them is ours.
The send is what this product writes.
The notice, and the date · /brazosbend/disconnects/new?step=3
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
▧
✦
▩
▦
▤
⚙
Friendly reminder 04/14/2026 Email — not known
10-day notice 04/24/2026 Print · SMS — not known
Final notice 05/09/2026 Print · certified — not known
Nothing in this product delivers a notice, and this column will not pretend otherwise. A row is written and a sender
that does not exist yet would pick it up.
How the next one goes out
✓ Certified mail
Required on the final notice, and it cannot be unticked here.
✓ Posted
✓ Email
Text message
A text may go alongside, but it never stands alone at this tier.
Door hanger
✓ In the portal
The only channel that actually delivers anything today.
Six ways out, and they are not equivalent. The final notice is the one a cut is counted from, so the law cares how it went.
A MEDICAL-HOLD ACCOUNT NEVER REACHES THIS STEP
Accounts on a medical hold are excluded from the notice ladder entirely. This is drawn on an account with no hold; the
exclusion happens before a clerk ever gets here.
Served by
Certified mail ▼
Certified mail · Posted · Email · Text message · Door hanger
Reference
RA 4821 9930 US
The tracking or receipt number on the proof itself.
Signed for on
05/11/2026 📅
Recorded by
S. Ortiz
Somebody decided, and the record names them.
No proof, no cut. A cut at the final tier cannot be scheduled on a notice nobody
can show was served.
The date
Earliest lawful cut 05/14/2026
Counted from The final notice, 05/09/2026
Locked Yes — computed, not typed
Scheduled cut date *
05/14/2026 📅
On or after the earliest lawful date.
The earliest date is computed and cannot be moved. A clerk may schedule later
— a Friday cut before a bank holiday is a real reason to wait — but never earlier.
←  Back Continue →
/brazosbend/disconnects/new?step=4
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
Disconnects / Disconnect ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
←  Disconnects
DISCONNECT
Fees, and what a cut does
Step 4 of 5 · Fees & consequences
Save & exit
✓ Account & reason ✓ Protections ✓ Notice & date 4 Fees & consequences 5 Review
The fees on this cut
CHARGE CODE AMOUNT WHEN CHARGED?
Reconnection fee CC-RECON $75.00 At the cut Yes
Disconnection fee CC-DISC $45.00 At the cut No — nothing raises it
Fieldvisit CCFIELD $3500 Onlyifacrewattends N thi g i it
What the deposit does
Hold it
It stays as it is.
Apply it against the arrear
$450.00 comes off the $2,410.00, leaving $1,960.00 owed and nothing held if they
 b k
Fees, and what a cut does · /brazosbend/disconnects/new?step=4
Finance
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▩
▦
▤
⚙
Field visit CC-FIELD $35.00 Only if a crew attends No — nothing raises it
Three fees are designed and one is charged. The cut raises the reconnection fee and nothing else: the other two codes
exist as names with no path to a bill.
From the tenant’s own charge codes, never typed. The amounts above are this utility’s rows.
What must be cleared before service comes back
The reconnection figure
Arrears at the cut $2,410.00
Reconnection fee $75.00
To clear before reconnection $2,485.00
The fee lands at the cut, not at restoration — and that is the whole difference. Charged at restoration, a customer pays
the arrears, the balance reads zero, and the gate lets them back with the fee never collected.
Take a payment now
Amount
$2,485.00
Prefilled with the full figure.
Method
Card ▼
Reference
AUTH 60114
IF THEY PAY WHAT IT DOES TO THIS CASE
$2,485.00 or more Clears it. The cut has nothing left to chase
At or above the tenant’s threshold Pauses the ladder until the next instalment is missed
Below it Recorded, and the cut still stands
A payment is always accepted, and accepting it changes no status by itself. Taking money here records a payment;
it does not lift this case.
ever come back.
A deposit is money held on the customer’s behalf. Applying it reduces what they
owe and does not make it income — and it leaves nothing in hand if service is later
restored.
THE ELECTION IS RECORDED; THE MONEY DOES NOT MOVE HERE
Choosing to apply it writes down that somebody decided, and no journal line
follows. Moving money between a deposit and a debt is a balance-sheet posting
and only the ledger may write one.
What the cut will do
WHAT
1 Cut electric and water on 05/14/2026, leaving the account open
2 Stop the base and standing charges at the cut
3 Add the $75.00 reconnection fee to the balance
4 Leave the balance unchanged from that day on
5 Block new service elsewhere until it is settled
Two of those five reverse what this screen used to say. It said a disconnected
account keeps accruing base charges and that a cut does not stop the balance
growing.
What it will not do
Close the account Closing is a separate act
Forgive the debt It stays exactly where it is
Cut anything today Nothing happens until the date
Remove the deposit Unless it is applied above
AND THE CUT WILL REFUSE ON THIS TENANT TODAY
The three charge codes above are in no catalogue on this system, and the
reconnection one does not exist under any spelling. The cut looks its code up and
refuses when it finds nothing — so every cut refuses everywhere until somebody
adds the row.
←  Back Continue →
/brazosbend/disconnects/new?step=5
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Disconnects / Disconnect ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
←  Disconnects
DISCONNECT
Review — nothing is cut today
Step 5 of 5 · Review
Save & exit
✓ Account & reason ✓ Protections ✓ Notice & date ✓ Fees & consequences 5 Review
The account ✎  Step 1 The date ✎  Step 3
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
▤
▧
✦
▩
▦
▤
⚙
Account number A-11812
Customer Bramble Bakery
Customer number C-00271
Category Commercial · Small commercial
Service address 142 Bakers Row, Silver Creek, TX 78611
Unit U-000744 · Suite 1
Balance $2,410.00
Oldest item 62 days past due
Deposit on file $450.00
Last payment $180.00 · 03/02/2026
Reason Non-payment
Services cut Electric · Water
Trash Left on
Treatment Full disconnection on both
Protections ✎  Step 2
Medical certificate No · checked 05/09/2026
Weather moratorium No · checked 05/09/2026
Active payment plan No · checked 05/09/2026
Questions nothing can answer 7 of 10
Protection recorded here None
Ladder stopped by hand No
Seven of the ten protection questions were never answered. Nothing in this product can check a life-support
registration, an age or disability protection, an open dispute, an assistance application or a landlord-billed premises.
The notice ✎  Step 3
Tier 3 of 3 · final notice
Final notice written 05/09/2026
Going out by Certified mail · post · email · portal
Delivery confirmed — nothing here delivers
Served by Certified mail
Proof reference RA 4821 9930 US
Signed for on 05/11/2026
Proof recorded by S. Ortiz
Earliest lawful cut 05/14/2026 · locked
Scheduled for 05/14/2026
Counted from The final notice, 05/09/2026
The money ✎  Step 4
What this cut does to the balance
Arrears today $2,410.00
Reconnection fee at the cut $75.00
Disconnection fee — not charged
Field visit fee — not charged
Deposit $450.00 · held, not applied
Payment taken now $0.00
To clear before reconnection $2,485.00
What happens when you confirm
WHEN WHAT
Now The case records the date, the reason and the deposit choice
Now One audit row naming who scheduled it
Now Nothing is cut, and no fee is raised yet
05/14 The cut runs: services off, fee raised, base charges stop
05/14 The balance goes static at $2,485.00
After Reconnection needs the whole $2,485.00, not the arrears
Nothing performs that cut on the day. No runner, job, queue or timer in this
product reads a date and acts on it.
What goes out to the customer
The last row is the one this cut most needs and cannot send. A household or a business being cut off should be told who to ring if somebody there depends on the supply — and no template exists for it.
SEND WHAT IT SAYS TO CHANNEL TEMPLATE WHEN
☑ That the cut is scheduled, and for when Bramble Bakery Email · Print Cut scheduled — commercial v3 On scheduling
☑ What must be paid to stop it — $2,485.00 Bramble Bakery Email · Print Amount to clear v2 On scheduling
☑ That a payment now would still stop this Bramble Bakery SMS Pay to avoid disconnection v4 On scheduling
☐ That the supply has been cut Bramble Bakery Email · Print Service disconnected v2 On the cut date
Review — nothing is cut today · /brazosbend/disconnects/new?step=5 · Commits to the disconnect ladder — each of its eleven acts has its own route
Where a disconnect lands, and what it becomes
Onto the Disconnects tab as a numbered case, with the notices sent under it.
“On hold” is a protection, not a delay. A case held on a medical certificate still
owes the money and is still open, and nothing about that row may be read as a
job somebody forgot — so it sits in its own segment and is never worked by
accident. Tier and Last notice answer different questions: the tier is where the
ladder has got to, the last notice is what was actually sent and when.
Two things the record says that the list cannot. Queued is not sent — nothing
in this product delivers a notice, so a cut date counted from a notice nobody
posted is exactly what that column exists to make visible. And a disconnect is
not a close-out: the account stays open, the ladder stops, and the debt stays
where it is.
DSC-26-0003 is the case this document’s own account carries — $2,410.00
outstanding, 62 days past due, two notices sent and a cut date on the calendar.
Where a disconnect lands · the Disconnects tab · /brazosbend/accounts?tab=disconnects · The five-step notice flow’s worklist · a case, and the notices under it
v2.234.15
SO Sam Ortiz
Billing Clerk
☐ Who to ring about a medical or safety need Bramble Bakery Print — none exists On scheduling
Choosing a template
Search templates
⚲  disconnect
Searches the name a human gave it.
TEMPLATE GROUP CHANNEL VARIANT VERSION
Cut scheduled Email Email Commercial · English v3 Published
Cut scheduled Printable Print Commercial · English v3 Published
Amount to clear Email Email Default · English v2 Published
Pay to avoid disconnection SMS SMS Default · English v4 Published
Cut scheduled Printable Print Residential · Spanish v1 Draft
Everything here is queued, and nothing is sent. This product writes a row per message and no sender picks it up — no email, no text, no print file.
Print is the floor. Paperless and text reminders are channels on top of the paper, not instead of it.
A template resolves on three axes and falls back on two. The class of letter, the customer category and the language — and where no variant exists for a category or a language, the default one is used.
The draft version is listed and cannot be picked. Hiding it sends a clerk looking for something they can see exists; offering it would queue a letter nobody has approved.
And none of these is proof of anything. Queueing a letter is not serving a notice.
←  Back Schedule the disconnection ✓
/brazosbend/accounts?tab=disconnects
A t / Di t ⚲ S h t i t ⚑ ?
The disconnect case, opened · DSC-26-0003 · /brazosbend/disconnects/dsc-26-0003 · Proposed · the case, its notices, and the four protections that can stop it
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
Accounts / Disconnects ⚲  Search accounts, premises, meters… ⚑ ?
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
10 tabs · Disconnects · 3 open cases
+ New disconnect
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
AT NOTICE
1
the ladder is running
DUE TO CUT
1
the date has arrived
CUT, AWAITING
RECONNECT
0
nothing disconnected
ON HOLD
1
a protection is in force
RECONNECTIONS
0
none requested
Due to cut At notice On hold Reconnections All Filter ▾ ⚲  Search by case #, account, customer or address Columns ▾ ⇩  Export
CASE # ACCOUNT CUSTOMER ADDRESS OWED TIER CUT DATE LAST NOTICE STATE
DSC-26-0003 A-11812 Bramble Bakery 142 Bakers Row · Suite 1 $2,410.00 Final notice 05/14/2026 10-day · 04/24/2026 Due to cut ↗Open
DSC-26-0002 A-11602 Ncube, T. 1408 Elm · Unit E $512.80 10-day 05/21/2026 10-day · 05/01/2026 At notice ↗Open
DSC-26-0001 A-11333 Halvorsen, P. 88 Quarry Lane $318.20 — — Friendly · 04/02/2026 On hold · medical ↗Open
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
On hold is not a delay, it is a protection. DSC-26-0001 is held on a medical certificate: the money is still owed and the case is still open, and nothing about this row may be read as a job somebody forgot.
Tier and Last notice answer different questions. The tier is where the ladder has got to; the last notice is what was actually sent and when.
DSC-26-0003 is the case this document’s own account carries — $2,410.00 outstanding, 62 days past due, two notices sent and a cut date on the calendar.
/brazosbend/disconnects/dsc-26-0003
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
Accounts / Disconnects / DSC-26-0003 ⚲  Search accounts, premises, meters… ⚑ ?
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
CASE DSC-26-0003
Bramble Bakery
Due to cut Final notice sent Cut date 05/14/2026 Commercial
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611
Hold the case Open the account Mark as cut
THE CASE
Account A-11812
Owed $2,410.00
Oldest debt 62 days past due
Tier Final notice
Cut date 05/14/2026
Raised by S. Ortiz · 04/14/2026
NOTICES SENT
PROTECTIONS CHECKED
QUESTION ANSWER CHECKED
Medical certificate on file? No 05/09/2026
Weather hold in force? No 05/09/2026
A payment plan running? No 05/09/2026
Disputed bill open? No 05/09/2026
Four questions, each able to stop this on its own, and each answered on a date.
An answer from three weeks ago is not the same claim as an answer from this morning,
which is why the date is beside it.
Two figures on this record were wrong until this draft. The reconnection fee
read $85.00 against a signed $75.00, and the consequence panel said billing
"keeps running — a cut is not a close", which is the exact sentence the base-
charge ruling reversed. A cut is now the thing that stops the balance growing,
and the fee lands the day the supply goes off rather than the day it comes back
— so $2,485.00 is what reopens this supply, not $2,410.00.
Two actions on a case, and both are narrower than they sound. Hold stops
the ladder and forgives nothing. Mark as cut stops the supply and closes
nothing — the account stays open, the debt stays where it is, and billing keeps
running.
Hold the case — the ladder stops, the debt does not · /brazosbend/disconnects/dsc-26-0003 · Action 1 of 2 on the case · a protection, not a delay
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
⚙
NOTICE SENT CHANNEL STATE
Final · 5-day 05/09/2026 Print Queued
10-day 04/24/2026 Print · SMS Sent
Friendly reminder 04/14/2026 Email Sent
Queued is not sent. Nothing in this product delivers a notice: a row is written and a sender that does not exist yet would
pick it up.
WHAT A CUT WOULD DO
Services affected Electric · Water
Reconnection fee $75.00 · raised at the cut
Account status
becomes
Disconnecte
d To clear before
reconnection
$2,485.0
0
Base charges stop at the cut — the balance goes static
A disconnect is not a close-out. The account stays open, the ladder stops,
and the debt stays exactly where it is.
/brazosbend/disconnects/dsc-26-0003
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
Accounts / Bramble Bakery ⚲  Search accounts, premises, meters… ⚑ ?
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
CASE DSC-26-0003
Bramble Bakery
Due to cut Final notice sent
Hold the case Open the account Mark as cut
Hold DSC-26-0003
Nothing is cut while a hold is in force
✕
WHY
Medical certificate
On file and dated.
Weather
A published temperature rule, not a judgment call.
A payment plan has been agreed
The plan itself stops the ladder; this records that it did.
Mark as cut — and what it is not · /brazosbend/disconnects/dsc-26-0003 · Action 2 of 2 on the case · the account stays open
v2.234.15
SO Sam Ortiz
Billing Clerk
A bill is disputed
The disputed amount is not collectable while it is open.
Review on
06/14/2026 📅
A hold with no review date is a case nobody comes back to.
WHAT HOLDING WILL DO
THEN WHAT
Now The cut date of 05/14/2026 is cleared
Now The notice ladder stops where it is — it does not reverse
Now The case moves to the On hold segment, so it is never worked by accident
Not now The $2,410.00 is still owed and still ages
A hold is not forgiveness and the screen says so twice. The money stays owed, the debt keeps ageing, and the tier stays where the ladder had got to — so lifting the hold
resumes rather than restarts.
Cancel Hold the case
/brazosbend/disconnects/dsc-26-0003
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
Accounts / Bramble Bakery ⚲  Search accounts, premises, meters… ⚑ ?
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
CASE DSC-26-0003
Bramble Bakery
Due to cut Final notice sent
Hold the case Open the account Mark as cut
Mark DSC-26-0003 as cut
Service stops at an address where somebody works
✕
WHAT WAS CUT
Account A-11812 · Bramble Bakery
Address 142 Bakers Row · Suite 1
Services Electric · Water
Cut on *
05/14/2026 📅
Who did it
Field crew · WO-26-0402 ▼
Meter reading at the cut
18,204
How you get here Four doors: Disconnects tab primary (AccountsListPage.tsx:937), empty CTA (DisconnectsTab.tsx:915), parked Resume, and — newly — the S21 icon rail's ⚡
Disconnect notice, which navigates to /disconnects/new?account=<id> (accountRailReadiness.ts:291).
⚠  Four findings drawn Two of the three fee codes are read by nothing — only the reconnection charge is ever raised, so a designed $155.00 bills as $75.00. None of the three is in any
catalogue on this system, and the cut refuses when it cannot resolve one — so every cut refuses, everywhere, today. The protections step takes no input at all: it
is handed nothing to write to and offers no control. And nothing performs a scheduled cut — no runner, job, queue or timer in this product reads a date and acts
on it.
Primary action Schedule the disconnection ✓ on the danger tier. Nothing is cut by this screen; the cut happens on the date it schedules.
Walked Not walked.
Why Blocked This is the only screen in the surface carrying Blocked. It states more open questions than any other: seven of its refusals name a decision nobody has made — what
a restricted service is charged, who a block on new service applies to, what the earliest lawful cut date is, what happens when a crew attends and does not cut. Those
are rulings, not code.
Rules BR-CUS-039 · 091 · 591 · A19 §2
05
Money on an account
v2.234.15
SO
Sam Ortiz
Billing Clerk
What the register stood at when service stopped.
THE FOUR PROTECTIONS, RE-CHECKED AT THE CUT
QUESTION ANSWER CHECKED
Medical certificate on file? No 05/14/2026
Weather hold in force? No 05/14/2026
A payment plan running? No 05/14/2026
Disputed bill open? No 05/14/2026
They are asked again on the day. An answer from when the notice went out is five days old, and a medical certificate that arrived yesterday is exactly the thing that must stop this.
WHAT MARKING IT CUT WILL DO
THEN WHAT
Now The account’s status becomes Disconnected
Now The notice ladder stops
Now A reconnection fee of $75.00 is raised — payable now, not at restoration
Not now The account does not close and the $2,410.00 stays exactly where it is
Not now Billing keeps running — a standing charge on a cut supply is still a charge
A disconnect is not a close-out. Closing the account is a different act, on a different screen, by somebody deciding the customer has gone.
Cancel Mark as cut
```

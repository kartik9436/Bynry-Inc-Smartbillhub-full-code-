# 02 · Account detail EXISTS BEHIND ACC-03

**Source:** `accounts-blueprint.pdf`, pages 6–38. Extracted text, verbatim — **derived, do not edit.**

**78,249 characters over 33 page(s).**

---

```
② Name contacts.full_name via primary_contact_names_for() customers SERVED
③ Premise premises.address_line1 (+ unit label) via premise_cells_for() customers ⇄
metering
SERVED
④ Services service_agreements.service_code via service_codes_for_accounts() customers ⇄
rating
SERVED
④ Services badge
colour + letter
a literal badge map in features/rating/ratingShared.tsx — HARDCODED
⑤ Balance ledger journal lines via _ar_positions_for() — NOT accounts.balance customers ⇄
ledger
SERVED
⑥ Last bill billing invoices via seams.last_issued_invoice_dates() customers ⇄
billing
SERVED
⑦ Status account_statuses.code via accounts.status_id customers SERVED
⑦ Status filter options ACCOUNT_SEED_STATUSES — a literal 5-tuple in customersShared.tsx:166. The vocabulary is tenant-EXTENSIBLE and
the only route that enumerates it is System-Admin-only, so a clerk's filter cannot offer a tenant-added status
— HARDCODED
⑧ Ageing band account_opening_buckets via ageing_segments_for() customers SERVED
⑧ row.aging (the
neighbour)
billing's own three-state display vocabulary — served null, read by nothing on this screen billing ⇄
customers
DEAD
⑨ Category filter
options
GET /lookups platform catalogue, fetched (useAccountCategories) customers ⇄
tenancy
SERVED
⑩ KPI · Outstanding accounts_rollup() — the ledger's Σ with the CHAR(3) the ledger derived customers ⇄
ledger
SERVED
⑪ KPI · Past due 60+ served null ON PURPOSE — needs each open bill's due date, which no module publishes billing NOT SERVED
⑫ KPI · Closed this
year
accounts.closed_at exists; ACCOUNT_FILTERS carries no date dimension, so "closed since January" is unaskable customers NOT SERVED
⑬ KPI · Pending
activation
a SECOND GET /accounts with f.status=pending_activation; the rows come back and are thrown away for the
envelope count
customers DERIVED
Screen health: NOT SERVED  — the worst field on the screen, never an average. 9
SERVED · 1 DERIVED · 3 HARDCODED/DEAD · 2 NOT SERVED · 0 untraced.
02 Account detail EXISTS BEHIND ACC-03
/:tenant/accounts/:accountId  ·  ?tab= × 12  ·  ?order=  ·  S21  ·  AccountDetailPage.tsx
The question: "I have this customer on the phone. What do they owe, what have they
paid, what's on their meter — and what can I actually do for them before I have to say
paid, at s o  t ei  ete   a d at ca   actually do fo  t e  befo e  a e to say
I'll call back?"
/brazosbend/accounts/a-11812?tab=overview
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
AGEING
61–90 days past
61 days past due · from opening
buckets
LAST BILL
Never billed
no bill has been issued on this
account
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
DEPOSIT ON FILE
$0.00
none received
⇆ ⚡📅✎
MONEY
Balance $2,410.00
Basis Posting date
what the figure counts — not the clearing date
Source The ledger
every posted charge, less every posted payment
Ageing 61–90 days past
Days past due 61
Ageing source Opening buckets
derived from opening balances, not from each open bill's due date
Credit tier Not computed
Deposit on file $0.00
Deposit received —
Interest accrued Not accrued
Returned payments 0
SERVICE
Filter ▾ ⚲  Search services
Columns ▾ ⇩  Export
SERVICE STARTED ENDED
ELECTRIC 09/10/2024 —
WATER 09/10/2024 —
CUSTOMER
Full name Bramble Bakery
Email —
Phone —
Date of birth —
Government ID —
MAILING ADDRESS — WHERE THE BILL GOES
NO MAILING ADDRESS OF ITS OWN
The bill goes to the service address above. A mailing address is a SEPARATE
fact and is shown here only when it differs — two identical addresses on one
screen teach a clerk to skip the second.
CUSTOMER RECORD
Customer ID —
this account is not linked to a customer record, so its contact above is the only one it has
Linked accounts 0
no other account is grouped with this one
BILLING PREFERENCES
Autopay Off
enrolment is recorded here; nothing is collected automatically in this version
Paperless Off
Text reminders Off
Preferred language —
N tifi ti t l t Tenantdefault
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Every tab on this screen, drawn
Twelve tabs, twelve drawings, one account behind all of them — A-11812,
Bramble Bakery, 142 Bakers Row · Suite 1.
These twelve are drawn with sample data, and here is exactly what that means
A-11812 has almost nothing on it in the seeded database: no bill has ever been issued, no meter is fitted, nothing has been read. Drawn truthfully, eleven of the twelve tabs were an
empty state — and an empty state shows a reader nothing about the layout. So rows and figures are invented. Every drawing says sample data in its own corner, so no figure
below is ever quoted back as a finding.
The rule they are drawn to: mock the data, keep the behaviour. Rows, amounts, dates and references are invented. What the product can and cannot WORK OUT is not. So the
bills carry real tax arithmetic and reconcile to the balance — the three unpaid ones total exactly $2,410.00 — and every one of them still reads Issued rather than Overdue, because
past-due is not computed on this deployment and drawing it would promise a build that cannot be delivered. Every stated absence that no amount of data would fix stays where it
was: adjustments have no endpoint, documents have no upload, an audit row has no link back, usage behind a bill is not summed.
What is real on these drawings, and stays real. The account, its address, its category and the raw small_commercial. The balance of $2,410.00 and 62 days past due. A commercial
account sitting on a residential plan. PY-260911-0076 — $500.00, posted with no clearing date, met nothing, still Processing, balance unmoved. And the two dunning notices and
disconnect case DSC-26-0003, with the audit rows that name them in database words.
One difference to expect between these and the action drawings below. Here bills exist, so Print bill and Issue credit are live in the rail. On the real account they refuse,
because a bill is what they need — and the action drawings are deliberately left on the account as it really is, because refusal states are the whole point of that set.
v2.234.15
SO Sam Ortiz
Billing Clerk
METERS
NO METER IS ASSIGNED
This account holds two service agreements and no measuring asset. Consumption cannot be read and a metered bill cannot
be raised until one is assigned.
PLAN
Plan Sample — Residential
Code SCW-RES
Version 1
In force since 06/01/2026
HISTORY All bills →
NO BILL HAS BEEN ISSUED
No bill has been raised on this account yet. The balance above was carried in as an opening figure, which is why the ageing is
counted from that rather than from a bill’s due date.
Notification template Tenant default
ACCOUNT SETUP
Category Commercial
Sub-type small_commercial
Account kind Regular
Master account —
this account is not part of a master/sub group
Behaviour class Billable
this status raises bills
Tax exempt No
Exemption reference —
Exemption expires —
Bad address No
Opened 09/10/2024
Closed —
PORTAL ACCESS
Sign-in Nobody can sign in
Locked 0
Last sign-in Never signed in
ACC-02
All twelve render, all twelve reflect in the address bar, none is blank and none
raised an error. One address is worth noting: Payment plan is ?tab=plan, not ?
tab=paymentplan — a link built by guessing from the label lands on Overview.
Tab 1 of 12 · Overview · /brazosbend/accounts/a-11812?tab=overview · the tab a clerk lands on — every fact under a named group
/brazosbend/accounts/a-11812?tab=overview
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
MONEY
Balance $2,410.00
Basis Posting date
Source The ledger
every posted charge, less every posted payment — three issued bills stand behind it
Oldest unpaid 62 days
Returned payments 0
Bad address No
SERVICE
Filter ▾ ⚲  Search services
Columns ▾ ⇩  Export
SERVICE STARTED ENDED
ELECTRIC 09/10/2024 Still open
WATER 09/10/2024 Still open
METERS ON THIS UNIT
Filter ▾ ⚲  Search meters
ACCOUNT
Number A-11812
Status Active
Opened 09/10/2024
Category Commercial
Sub-type small_commercial
Cycle Silver Creek — monthly
Tax exempt No
Preferred language English
the sub-type is printed as the value the database stores — this is the one place on the account
where an internal string reaches a clerk
CUSTOMER
Full name Bramble Bakery
Kind An organisation
Email accounts@bramblebakery.example
Phone +1 (512) 555-0117
Trading name Bramble Bakery
Adjust
Activate account
Move-in
Close out
✉
Nothing on this tab can be corrected, and the next drawing fixes it
Every fact above is read-only, in every group, forever — a tax certificate that expires, a phone number that changes, a billing address that moves. The drawing below is the same
tab with an edit control on all eleven groups, and it is a proposal: the product has no edit control on any group of this screen today. The five forms behind it are R5 in §10. Go to
R5 →
Tab 1 of 12 · Overview PROPOSED with an edit control on every group · /brazosbend/accounts/a 11812?tab=overview · eleven groups eleven controls five live one that opens the Change plan wizard five
v2.234.15
SO Sam Ortiz
Billing Clerk
Columns ▾ ⇩  Export
METER SERVICE LAST READ READ ON
E-4417 Electric 61,480 kWh 08/18/2026
W-4417 Water 9,214 kgal 08/18/2026
PLAN — TAKEN FROM THE UNIT, NOT HELD ON THE ACCOUNT
Plan Sample — Residential
Code SCW-RES
Version 1
In force since 06/01/2026
a residential plan on a commercial account — the plan follows the unit, and nothing reconciles the two
RECENT BILLS All bills →
Filter ▾ ⚲  Search bills
Columns ▾ ⇩  Export
BILL # ISSUED DUE TOTAL STATUS
BL-2608-000229 08/22/2026 09/11/2026 $811.35 Issued
BL-2607-000204 07/22/2026 08/11/2026 $812.25 Issued
BL-2606-000181 06/22/2026 07/11/2026 $786.40 Issued
USAGE TREND Usage →
12 months 24 months
Filter ▾ ⚲  Search periods
Columns ▾ ⇩  Export
MONTH ELECTRIC WATER
Aug 2026 5,510 kWh 62 kgal
Jul 2026 5,083 kWh 58 kgal
Jun 2026 4,870 kWh 55 kgal
May 2026 4,410 kWh 49 kgal
Apr 2026 4,180 kWh 46 kgal
Mar 2026 4,020 kWh 44 kgal
the six most recent months, newest first — averaging 5,140 kWh and 56 kgal a month.
Business ID Seen 09/10/2024
MAILING ADDRESS — WHERE THE BILL GOES
Goes to Marchetti & Co, Suite 400
18 Cedar Ridge Way
Silver Creek, TX 78611
their accountant — different from the service address, which is why this is shown at all
CUSTOMER RECORD
NOT LINKED TO A CUSTOMER RECORD
This is one contact on one account. Until it is linked, the panel below can only list
the account you are on.
PAYMENT METHOD
On file ACH · Frost Bank ••••7712
Verified 09/24/2024
Autopay Off
autopay is recorded on the account and nothing collects on it in this version, so turning it on
changes a flag and not a payment
DEPOSIT & CREDIT
Deposit on file $450.00
Received 09/24/2024
Interest accrued Not accrued
Credit tier Not computed
interest and the credit tier are both served as absent — neither is worked out on this
deployment
PORTAL ACCESS
Sign-in Nobody has signed up
Last sign-in Never signed in
Paperless Off
Text reminders Off
there is no customer portal in this version, so none of these four can change
ALL ACCOUNTS FOR THIS CUSTOMER
ACCOUNT ADDRESS STATUS BALANCE
A-11812 142 Bakers Row · Suite 1 Active $2,410.00
one row, because no customer record is linked
ACC-T01 · sample data
Tab 1 of 12 · Overview — PROPOSED, with an edit control on every group · /brazosbend/accounts/a-11812?tab=overview · eleven groups, eleven controls — five live, one that opens the Change plan wizard, five
disabled with their reason. The forms behind them are R5 →
/brazosbend/accounts/a-11812?tab=overview
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$450.00
received 09/24/2024
MONEY ✎Edit
Balance $2,410.00
Basis Posting date
Source The ledger
Oldest unpaid 62 days
SERVICE ✎Edit
Filter ▾ ⚲  Search services
Columns ▾ ⇩  Export
SERVICE STARTED ENDED
ELECTRIC 09/10/2024 Still open
WATER 09/10/2024 Still open
PLAN — TAKEN FROM THE UNIT ✎Change plan
Plan Sample — Residential
Code SCW-RES
Version 1
In force since 06/01/2026
RECENT BILLS ✎Edit
Filter ▾ ⚲  Search bills
Columns ▾ ⇩  Export
ACCOUNT ✎Edit
Number A-11812
Status Active
Category Commercial
Sub-type small_commercial
Tax exempt No
Preferred language English
UNIT — WHAT THIS ACCOUNT IS ATTACHED TO ✎Change unit
Unit Suite 1
Premises 142 Bakers Row
Service address 142 Bakers Row, Silver Creek, TX 78611
Unit type Retail unit
Plan the unit carries SCW-RES v1
the address is the building’s and the plan is the unit’s — both follow this row, which is why it has
a control of its own
CUSTOMER ✎Edit
Full name Bramble Bakery
Email accounts@bramblebakery.example
Phone +1 (512) 555-0117
Business ID Seen 09/10/2024
MAILING ADDRESS — WHERE THE BILL GOES ✎Edit
Adjust
Activate account
Move-in
Close out
Tab 2 of 12 · Bills · /brazosbend/accounts/a-11812?tab=bills · nine columns, server-sorted on issue date, newest first
v2.234.15
SO
Sam Ortiz
Billing Clerk
BILL # ISSUED DUE TOTAL STATUS
BL-2608-000229 08/22/2026 09/11/2026 $811.35 Issued
BL-2607-000204 07/22/2026 08/11/2026 $812.25 Issued
BL-2606-000181 06/22/2026 07/11/2026 $786.40 Issued
USAGE TREND ✎Edit
Filter ▾ ⚲  Search periods
Columns ▾ ⇩  Export
MONTH ELECTRIC WATER
Aug 2026 5,510 kWh 62 kgal
Jul 2026 5,083 kWh 58 kgal
Jun 2026 4,870 kWh 55 kgal
May 2026 4,410 kWh 49 kgal
Goes to Marchetti & Co, Suite 400
18 Cedar Ridge Way
Silver Creek, TX 78611
PAYMENT METHOD ✎Edit
On file ACH · Frost Bank ••••7712
Autopay Off
DEPOSIT & CREDIT ✎Edit
Deposit on file $450.00
Received 09/24/2024
Credit tier Not computed
PORTAL ACCESS ✎Edit
Sign-in Nobody has signed up
Paperless Off
The rule. Every group heading carries the control.
ACC-T01E
/brazosbend/accounts/a-11812?tab=bills
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Outstanding Settled Filter ▾ ⚲  Search All bills → Columns ▾ ⇩  Export
BILL # CYCLE ISSUE DATE ▼ DUE DATE SUBTOTAL TAX TOTAL STATUS
BL-2608-000229 SilverCreek—monthly 08/22/2026 09/11/2026 $79544 $1591 $81135 Issued 🖨
Adjust
Activate account
Move-in
Close out
✉
Tab 3 of 12 · Payments · /brazosbend/accounts/a-11812?tab=payments · expandable rows — each opens onto what the money met
v2.234.15
SO Sam Ortiz
Billing Clerk
BL2608 000229 Silver Creek  monthly 08/22/2026 09/11/2026 $795.44 $15.91 $811.35 Issued 🖨 …
BL-2607-000204 Silver Creek — monthly 07/22/2026 08/11/2026 $796.32 $15.93 $812.25 Issued 🖨 …
BL-2606-000181 Silver Creek — monthly 06/22/2026 07/11/2026 $770.98 $15.42 $786.40 Issued 🖨 …
BL-2605-000163 Silver Creek — monthly 05/22/2026 06/11/2026 $753.97 $15.08 $769.05 Settled 🖨 …
BL-2604-000147 Silver Creek — monthly 04/22/2026 05/11/2026 $727.63 $14.55 $742.18 Settled 🖨 …
1–5 of 5  ·  Rows per page 50 100 200 500 1000    ‹ ›
Three of these are unpaid and not one says so. Past-due is not worked out on this deployment: whether a bill is met comes from payments and today’s date comes from the utility’s own clock, and until both are
wired every issued bill answers Issued.
Columns this tab cannot show
USAGE BEHIND EACH BILL
The design also shows the usage each bill was raised on. Usage is summed from meter reads and that summary is not built, so no number is drawn rather than a zero that would read as “they used nothing”.
ACC-T02 · sample data
/brazosbend/accounts/a-11812?tab=payments
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Cleared Processing Filter ▾ ⚲  Search Columns ▾ ⇩  Export
PAYMENT # POSTED ▼ TYPE METHOD REFERENCE APPLIED TO AMOUNT STATUS
▸ PY-260911-0076 09/11/2026 Payment No instrument — Met no bill $500.00 Processing …
▸ PY-260610-0052 06/10/2026 Payment ACH Frost ••••7712 BL-2605-000163 $682.65 Cleared …
▸ PY-260511-0041 05/11/2026 Payment ACH Frost ••••7712 BL-2604-000147 $742.18 Cleared …
▸ PY-240924-0003 09/24/2024 Deposit Check 1184 Deposit register $450.00 Cleared …
Adjust
Activate account
Move-in
Close out
✉
Tab 4 of 12 · Credits · /brazosbend/accounts/a-11812?tab=credits · two credit notes, each still sitting beside the bill it corrected
v2.234.15
SO Sam Ortiz
Billing Clerk
Row opened — PY-260911-0076
Amount $500.00
Posted 09/11/2026
Cleared Not cleared — no clearing date was given
Applied to Nothing
Recorded by Sam Ortiz
a payment with no clearing date is still on its way: it meets no bill, reaches no books and leaves the balance where it was
1–4 of 4  ·  Rows per page 50 100 200    ‹ ›
$500.00 was taken and the balance still reads $2,410.00. That is correct — the payment has not cleared — and Processing is the only word on the screen carrying it. This row is real: it was entered on this
account to see what a missing clearing date does.
THE DEPOSIT ROW IS DRAWN HERE AND THE PRODUCT WOULD NOT LIST IT
The design shows a held deposit among the payments. Nothing writes the deposit register yet, and whether a held deposit belongs in this list has not been settled.
ACC-T03 · sample data
/brazosbend/accounts/a-11812?tab=credits
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Applied Open Filter ▾ ⚲  Search Columns ▾ ⇩  Export
CREDIT NOTE # ISSUED ▼ REASON AGAINST BILL AMOUNT STATUS
CN-2606-000014 06/28/2026 Water charge billed in error BL-2605-000163 −$86.40 Applied
CN-2601-000004 01/19/2026 Goodwill — service interruption BL-2512-000098 −$40.00 Applied
R d CN2606000014
Adjust
Activate account
Move-in
Close out
✉
Tab 5 of 12 · Payment plan · /brazosbend/accounts/a-11812?tab=plan · note the address: this tab is ?tab=plan, not ?tab=paymentplan
v2.234.15
SO Sam Ortiz
Billing Clerk
Row opened — CN-2606-000014
Original bill BL-2605-000163 · $769.05
Credited −$86.40
Replacement bill Not raised — the correction was partial
Reason given to the customer A water charge was billed twice for the period 04/22 — 05/22.
Raised by Dana Whitfield · approved by Priya Raman
the original stays on the record beside the credit — a bill is never edited, it is credited and replaced
1–2 of 2  ·  Rows per page 50    ‹ ›
A credit is raised from the bill it corrects, never from this tab.
ACC-T04 · sample data
/brazosbend/accounts/a-11812?tab=plan
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
No plan is running None live
Arrears now $2,410.00
Oldest unpaid 62 days
Dunning so far Two notices issued, and a disconnect case opened
all three are on the account today — this is the account a plan is for
Propose a payment plan
Earlier plans on this account
Filter ▾ ⚲  Search plans Columns ▾ ⇩  Export
Adjust
Activate account
Move-in
Close out
✉
Tab 6 of 12 · Usage · /brazosbend/accounts/a-11812?tab=usage · a real chart, and the stats beside it are worked out from the same twelve numbers
v2.234.15
SO Sam Ortiz
Billing Clerk
PLAN # OPENED SPREAD INSTALMENTS OUTCOME
PP-2512-0004 12/08/2025 $1,284.00 4 × $321.00 Completed 03/08/2026
PP-2512-0004 — how it ran
Filter ▾ ⚲  Search instalments Columns ▾ ⇩  Export
# DUE INSTALMENT PAID ON STATUS
1 12/08/2025 $321.00 12/08/2025 Paid
2 01/08/2026 $321.00 01/09/2026 Paid
3 02/08/2026 $321.00 02/08/2026 Paid
4 03/08/2026 $321.00 03/08/2026 Paid
kept in full — which is worth a clerk knowing before refusing a second one
This account has kept a plan before and is in arrears again.
ACC-T05 · sample data
/brazosbend/accounts/a-11812?tab=usage
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
Electric Water All 12 months 24 months
Electric · Sep 2025 — Aug 2026
8,000
5,130 5,340
6,110
6,820
6,250
3960 4020 4,180 4,410
4,870 5,083
5,510
Adjust
Activate account
Move-in
Close out
✉6,000
Tab 7 of 12 · Meters · /brazosbend/accounts/a-11812?tab=meters · one table — the meters on this unit — searchable, filterable, with the read log as a row action
v2.234.15
SO Sam Ortiz
Billing Clerk
3,960 4,020 ,
Sep 25 Oct 25 Nov 25 Dec 25 Jan 26 Feb 26 Mar 26 Apr 26 May 26 Jun 26 Jul 26 Aug 26
kWh a month
Average
5,140 kWh
a month
Highest
6,820 kWh
Dec 25
Lowest
3,960 kWh
Feb 26
This month vs last
+8.4%
5,510 against 5,083
Month by month
Filter ▾ ⚲  Search periods Columns ▾ ⇩  Export
MONTH ELECTRIC WATER READ ON SOURCE
Aug 2026 5,510 kWh 62 kgal 08/18/2026 Walk-by
Jul 2026 5,083 kWh 58 kgal 07/17/2026 Walk-by
Jun 2026 4,870 kWh 55 kgal 06/18/2026 Walk-by
May 2026 4,410 kWh 49 kgal 05/19/2026 Estimated
Apr 2026 4,180 kWh 46 kgal 04/17/2026 Walk-by
Mar 2026 4,020 kWh 44 kgal 03/18/2026 Walk-by
A bakery’s winter peak is the ovens running longer, and it is the shape a clerk is asked to explain on the phone.
4,000
2,000
0
ACC-T06 · sample data
/brazosbend/accounts/a-11812?tab=meters
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Electric Water Installed Removed Filter ▾ ⚲  Search by meter number or serial Sort: Meter # ▼ Columns ▾ ⇩  Export
Adjust
Activate account
Move-in
Close out
✉
Tab 7 of 12 · Meters — the Read log action, opened · /brazosbend/accounts/a-11812?tab=meters&meter=e-4417&view=reads · one meter’s reads, over the tab it was opened from
v2.234.15
SO
Sam Ortiz
Billing Clerk
METER # SERVICE METER TYPE READ METHOD INSTALLED MULTIPLIER LAST READ READ ON STATUS ACTIONS
E-4417 ELECTRIC AMR Walk-by 09/10/2024 ×1 61,480 08/18/2026 Installed ☰Read log …
W-4417 WATER AMR Walk-by 11/06/2025 ×1 9,214 08/18/2026 Installed ☰Read log …
W-2288 WATER Walk-by Walk-by 09/10/2024 ×1 7,902 11/06/2025 Removed ☰Read log …
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
Read log opens that one meter’s reads over this unit — date, reading, usage, how it was collected and any note — without leaving the tab. It is a row action rather than a table per meter, because a unit with six meters would
otherwise push the list itself off the screen.
The meters belong to the unit, not to the account — they stay when the occupant leaves, which is why a meter removed in November 2025 is still listed here under a tenancy that began in 2024. The services this
account holds are a separate fact and live in the Service group on Overview.
What the filters are. Service, status, meter type, read method and test-due are the ones the register already filters on, in the product’s own f.‹name› grammar. Two of the columns look alike and are not: meter type is
what the meter IS, read method is how the reading is COLLECTED — W-2288 was a walk-by meter read by walking to it, while W-4417 is an AMR meter still being read on foot because the collector has not been fitted.
ACC-T07 · sample data
/brazosbend/accounts/a-11812?tab=meters
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
Read log — E-4417
Electric · AMR meter read walk-by · 142 Bakers Row · Suite 1
✕
THE METER
Meter E-4417
Service ELECTRIC
Meter type AMR
Readmethod Walk-by
Installed 09/10/2024
Multiplier ×1
Status Installed
Reads held 24, newest first
Tab 8 of 12 · Work · /brazosbend/accounts/a-11812?tab=work · one table — every job at this address, finished ones included
v2.234.15
SO
Sam Ortiz
Billing Clerk
Read method a by eads ed
the meter is the unit’s — this log is every read taken on it, whoever was occupying at the time
THE READS
12 months 24 months All Estimated only Filter ▾ ⚲  Search by date or reading
Columns ▾ ⇩  Export
DATE ▼ CHANNEL READING USAGE EXPORT HOW IT WAS COLLECTED STATUS
08/18/2026 Total 61,480 5,510 kWh — Walk-by Committed
07/17/2026 Total 55,970 5,083 kWh — Walk-by Committed
06/18/2026 Total 50,887 4,870 kWh — Walk-by Committed
05/19/2026 Total 46,017 4,410 kWh — Estimated Committed
04/17/2026 Total 41,607 4,180 kWh — Walk-by Committed
03/18/2026 Total 37,427 4,020 kWh — Walk-by Committed
02/17/2026 Total 33,407 3,960 kWh — Walk-by Committed
1–7 of 24  ·  Rows per page 50 100 200    ‹ ›
Each reading less the one before it is the usage beside it. That is why the register is shown next to the consumption rather than instead of it: a customer disputing a bill is
asking about the gap between two numbers, and both are on the row.
05/19/2026 was estimated. Nobody could reach the meter — the job raised for it is WO-26-3980 on the Work tab — so the reading was worked out rather than taken, and
every bill raised on it is marked too.
WHAT A READ DOES NOT CARRY
NO READER AND NO NOTE
The log records what was measured and how it was collected, and not who collected it or what they saw. Neither is served, so neither is drawn: a “side gate locked” belongs to
the work order, not to the read.
EXPORT IS EMPTY ON THIS METER
The column is the other half of a net-metering pair and fills where a meter exports — solar, chiefly. This one only imports, so every row is a dash rather than a zero, which would
read as “it exported nothing”.
Reads are taken and corrected in Reads, never here.
Read from the meter’s own record Export the log Close
ACC-T07R · sample data
/brazosbend/accounts/a-11812?tab=work
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
Move-out Record payment
Adjust
Activate account
Move-in
Close out
Tab 9 of 12 · Adjustments · /brazosbend/accounts/a-11812?tab=adjustments · the one tab whose own button is disabled — the rows show the shape it waits for
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
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Open Scheduled Closed Filter ▾ ⚲  Search by order number, type or technician Columns ▾ ⇩  Export
ORDER # TYPE PRIORITY TECHNICIAN DUE STATUS RAISED BY
WO-26-4417 Disconnect — site visit Urgent Not assigned 09/26/2026 Scheduled Dana Whitfield …
WO-25-2611 Water meter exchange Normal Field crew C 11/06/2025 Closed Dana Whitfield …
WO-26-3980 Read — no access Normal Field crew A 05/19/2026 Closed System …
WO-24-1902 Meter set — new service Not set Field crew B 09/10/2024 Closed Dana Whitfield …
1–4 of 4  ·  sorted by priority, then due time  ·  Rows per page 50 100 200    ‹ ›
This list is not in date order and the footer has to say so. It is sorted by priority rank, then by due time, and that sort is fixed — there is no column to click.
Six filters, and a seventh is refused. Search, type, status, priority, technician and area are the whole set.
The build history is not a second table. The jobs that built this service are work orders like any other and sit in this list — WO-24-1902 is the meter set.
✉
ACC-T08 · sample data
/brazosbend/accounts/a-11812?tab=adjustments
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
Adjust
Activate account
Move-in
Close out
Tab 10 of 12 · Documents · /brazosbend/accounts/a-11812?tab=documents · the correspondence a collections clerk is asked for, and cannot produce
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Filter ▾ ⚲  Search Columns ▾ ⇩  Export
DATE ADJUSTMENT # REASON APPLIED TO AMOUNT APPROVED BY
07/03/2026 ADJ-2607-000031 Leak allowance BL-2606-000181 −$118.25 Priya Raman
02/11/2026 ADJ-2602-000009 Rate applied wrongly BL-2601-000112 −$63.90 Priya Raman
10/22/2025 ADJ-2510-000004 Missed charge BL-2510-000073 +$45.00 Dana Whitfield
1–3 of 3  ·  Rows per page 50    ‹ ›
These rows are the shape, not the state. Adjustments are billing rows and billing is not built: no endpoint lists an adjustment and none posts one, so this table cannot be filled from anywhere today.
✉
New adjustment
ACC-T09 · sample data
/brazosbend/accounts/a-11812?tab=documents
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Correspondence Evidence Filter ▾ ⚲  Search Columns ▾ ⇩  Export
DOCUMENT TYPE DATE UPLOADED BY SIZE
Ten-day notice — DSC-26-0003 Correspondence 09/10/2026 System 48 KB
Payment reminder Correspondence 08/27/2026 System 41 KB
Plan agreement PP-2512-0004 Agreement 12/08/2025 Dana Whitfield 112 KB
Business registration Evidence 09/10/2024 Dana Whitfield 1.2 MB
Adjust
Activate account
Move-in
Close out
✉
Upload document
Tab 11 of 12 · Notes · /brazosbend/accounts/a-11812?tab=notes · one pinned note, then the rest newest first
Tab 12 of 12 · Audit · /brazosbend/accounts/a-11812?tab=audit · every money action writes here — hard rule 7
v2.234.15
SO Sam Ortiz
Billing Clerk
1–4 of 4  ·  Rows per page 50    ‹ ›
These rows are the shape, not the state. Account documents have no table and no upload endpoint: nothing here can be listed and nothing can be uploaded.
ACC-T10 · sample data
/brazosbend/accounts/a-11812?tab=notes
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Pinned Collections Customer-visible ⚲  Search Add note
📌  Pinned · Disputes the opening balance
Sam Ortiz · 09/11/2026 11:24 · Collections
Owner rang about the ten-day notice. Says they have never had a bill from us for the arrears and will not pay without seeing one. Holding the disconnection until this is sorted. Follow up 09/18.
WHEN ▼ WHO KIND NOTE
08/27/2026 Dana Whitfield Collections Reminder sent. No reply to the voicemail left on 08/22. 📌…
05/19/2026 Field crew A Field visit No access for the water read — side gate locked. Estimated. 📌…
12/08/2025 Dana Whitfield Agreement Payment plan PP-2512-0004 agreed on the phone, four instalments. 📌…
1–4 of 4  ·  Rows per page 50    ‹ ›
A NOTE CANNOT BE CORRECTED ONCE IT IS SAVED
Pinning is recorded in the audit log. Changing the words of a note is not offered, because there is no ruling yet on whether the original wording stays visible to the next person who reads it.
Adjust
Activate account
Move-in
Close out
✉
ACC-T11 · sample data
Every action on this screen, drawn
/brazosbend/accounts/a-11812?tab=audit
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out on this
deployment
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026  ·  Base charge
LAST ACTIVITY
09/11/2026
a payment was recorded
DEPOSIT ON FILE
$450.00
received 09/24/2024
🖨 $ ⇆ ⚡📅✎
Sample data. The rows and figures on this tab are invented to show the layout working.
All Money Status Collections Filter ▾ ⚲  Search Columns ▾ ⇩  Export
WHEN ▼ WHO WHAT HAPPENED
▸ 09/11/2026 11:18 Sam Ortiz Payment recorded · $500.00
▸ 09/10/2026 07:14 Dana Whitfield Activity recorded · this event type is not described yet
▸ 09/10/2026 07:14 Dana Whitfield Activity recorded · this event type is not described yet
▸ 09/10/2026 07:14 Dana Whitfield Activity recorded · this event type is not described yet
▸ 08/22/2026 02:05 System Bill issued · BL-2608-000229
▸ 03/08/2026 09:40 Dana Whitfield Payment plan completed · PP-2512-0004
Row opened — the third of the three from 09/10
What it shows Tier Not set · State notice_sent · Cut on Not set · Case no DSC-26-0003 · Currency USD · Delivery 3 recorded · Sequence service ·
Opened on 2026-09-10 · Scheduler 3 recorded · Stopped on Not set · Next step due Not set · Stopped reason Not set · Tier reached
on Not set · Cut scheduled for Not set · Amount owed at open 2 recorded · Case no unavailable Not set
sixteen fields, named as the database names them, nine of them empty
This is the most-read screen on a disputed account and it is the least readable. Three events were recorded within the same minute and all three say the same thing — this event type is not described yet — so
a clerk cannot tell them apart from the list.
LINKS BACK TO THE RECORD ARE NOT SHOWN
An audit row names what happened and not which row it happened to, so a clerk cannot open the disconnect case from the line that announces it, or the bill from the line that issued it.
Adjust
Activate account
Move-in
Close out
✉
ACC-T12 · sample data
Thirteen controls — six buttons in the header, seven icons in the rail — in
fifteen drawings, because Change plan has three steps and each one is its own
screen. Every refusal sentence is the product’s own wording, taken from the
control itself rather than from the code that writes it.
Seven of the thirteen refuse on this account, which is more than on any
account with bills: four of the six buttons, and three of the seven icons. The three
icons — Send statement, Print bill, Issue credit — all need an issued bill, and this
account has never had one. That is the rail working correctly, and it is also the
clearest picture in the document of how much of the screen goes dark when
billing has not run.
What the walk found. Adjust is refused on every account in every status —
and on this one that means a $2,410.00 opening balance with no bill behind it
cannot be corrected from anywhere in the product. Two actions do not open a
dialog at all: Activate account commits on the click with no confirmation, and
Issue credit, where it is live, leaves the account entirely and lands on Billing › Fix
a bill with an empty bill box. Close out is the sharpest of them: it is disabled on
every status this deployment seeds, and the one status it exists for —
disconnected — has no account at all.
Three of the fifteen are drawn on another account, and each says so on its face:
Activate account and Move-in cannot be reached from an active account, and
Print bill is shown as the refusal it is here.
The truth tables below were measured, not reasoned: each account was opened
and each control read for whether it was disabled and what sentence it carried.
Action 1 of 13 · Adjust · /brazosbend/accounts/a-11812 · disabled in every status on every account — there is no deployment where it opens
/brazosbend/accounts/a-11812
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust is disabled here.
Adjustments are billing rows, and billing is not built. There is no endpoint to post one to.
The control stays on the screen carrying its reason.
Adjust
Activate account
Move-in
Close out
Action 2 of 13 · Move-out, step 1 of 6 · /brazosbend/accounts/a-11812/move-out · the step has no search: the account is fixed by the address bar
Action 3 of 13 · Activate account · /brazosbend/accounts/a-12048 · one click, no confirmation, and a partial success it reports honestly
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
Where the same sentence appears again
SURFACE STATE
The Adjust button, here Disabled
The Adjustments tab Empty, with the reason
New adjustment, on that tab Disabled
one absence, three places — each says the same thing in the same words
It bites hardest on an account like this one.
ACC-A01
/brazosbend/accounts/a-11812/move-out
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
Accounts / A-11812 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Bramble Bakery
MOVE-OUT
Close an account and free the unit.
6 steps · final bill, deposit, and what happens to the unit.
1 Find account 2 Date & final read 3 Final bill & deposit 4 The shortfall 5 What happens next 6 Review & close
Which account is moving out?
The account is the one you came from — the server closes the account named in the address bar, so there is no search on this step.
Account A-11812
Name Bramble Bakery
Service address 142 Bakers Row · Suite 1
Services ELECTRIC WATER
Since 09/10/2024
Status Active
Balance $2,410.00
worked out from the ledger — every posted charge, less every posted payment
Save & exit Park Continue
Step 2 asks for a final read.
ACC-A02
/brazosbend/accounts/a-12048
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Accounts / A-12048 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
←  Accounts
ACCOUNT A-12048  ·  CUSTOMER — NOT LINKED
Kwan, Michael
Move-out Record payment
Adjust
Activate account
Move-in
Close out
Action 4 of 13 · Move-in, step 1 of 5 · /brazosbend/accounts/ac-2026-00042/move-in · opens only from a closed account — it hands that account’s unit on
Action 5 of 13 · Close out · /brazosbend/accounts/a-11812 · a control with no reachable state — and one it reaches by mistake
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
Active Billable Residential · Single family Regular account
Autopay off
⌂ 88 Pine Vista · Unit 2  ·  Silver Creek, TX 78611  ·  Since Sep 2026
ELECTRIC WATER
 + 9 more ▾
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
What the server could not do
No plan snapshot was recorded. The table that holds an account’s plan does not exist, so this account is not tied to a plan version.
No deposit was applied.
BALANCE
$0.00
nothing has been charged yet
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$150.00
08/22/2026
There is no wizard and no confirmation. Pressing Activate account commits immediately; the account is Active before the page has finished redrawing.
Drawn on A-12048 rather than on Bramble Bakery, because this is the one action of the thirteen that Bramble Bakery cannot reach: it was activated two years ago.
ACC-A03
/brazosbend/accounts/ac-2026-00042/move-in
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
Accounts / AC-2026-00042 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Rosa Pemberton
MOVE-IN
New occupant moving into a vacant unit.
Six steps. The unit comes from the account that has just left it, and the start date is fixed to the day after that account’s move-out.
1 Find unit 2 Customer 3 Start & read 4 Account
preferences 5 Deposit 6 Review
Which unit are they moving into?
The unit is the one the previous account has just left.
Unit 301 Mill Pond Ln · Apt 102
Services No services
the outgoing account’s ended agreements, shown under a unit label
Previous account AC-2026-00042
Moved out on 07/31/2026
Plan Kept from the last tenancy
THERE IS NO UNIT PICKER ON THIS STEP
The design searches a list of vacant units here. The server takes the unit from the account in the address bar, so a unit sent with this call would be a second answer to a question that already has one.
Save & exit Park Continue
Drawn on a closed account, because Move-in opens only from one.
ACC-A04
/brazosbend/accounts/a-11812
Action 6 of 13 · Record payment · /brazosbend/accounts/a-11812 · a modal, not a wizard — one step, eight fields, and it commits
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Close out is disabled here.
Only an account whose service has been cut is closed out. An occupant leaves by moving out, and a closed account is already finished.
The control stays on the screen carrying its reason.
Close out is disabled on every account this deployment has
ACCOUNT STATUS SEEDED? CLOSE OUT
Active 68 accounts, this one among them Disabled
Marked disconnect 1 account Disabled
Vacation hold 1 account Disabled
Closed 1 account Disabled
Pending activation 1 account Live — and should not be
Disconnected none the one status it is for, and it has no account
the only status that opens this button is the one it was not written for
Bramble Bakery is on its way there.
Adjust
Activate account
Move-in
Close out
ACC-A05
/brazosbend/accounts/a-11812
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
Action 7 of 13 · Send statement · /brazosbend/accounts/a-11812 · the first rail icon, disabled in every status on every account
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
✦
▩
▦
▤
⚙
✕Record a payment
BRAMBLE BAKERY · A-11812
BALANCE
2410.000000 USD
worked out from the ledger — every posted charge, less every posted payment
Amount *
2410.000000
Starts at the balance shown above and can be changed.
What this money is for *
Against bills ▼
Against bills · Deposit · Plan down payment · Prepayment
Posting date *
09/11/2026 📅
The day this payment counts from.
Clearing date
📅
The day the money actually arrived.
Method
Choose a method ▼
ACH · Card · Cash · Check · Lockbox · Money order · Wire.
Reference or cheque number
Whatever the customer can quote back.
Apply to
Oldest open bill first ▼
Oldest open bill first · A specific bill · Carry as account credit · Split across bills
Memo
Kept with the payment and read by anyone asking why later.
Cancel Record payment
Three faults on this form, all drawn as they are.
The balance reads 2410.000000 USD and the amount field is pre-filled with the same six decimals. Money displays to two.
ACC-A06
/brazosbend/accounts/a-11812
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
⇆ ⚡📅✎
Send statement is disabled here.
Statements are not built yet.
The control stays on the screen carrying its reason.
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Action 8 of 13 · Print bill · /brazosbend/accounts/a-11812 · live wherever a bill exists — refused here, because none does
Action 9 of 13 · Issue credit · /brazosbend/accounts/a-11812 · refused here for a good reason, and broken where it is live
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
⚙
Five words is the whole refusal.
ACC-A07
/brazosbend/accounts/a-11812
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
⇆ ⚡📅✎
Print bill is disabled here.
No bill has been issued yet.
The control stays on the screen carrying its reason.
What it opens where a bill does exist
Opens The bill as it was sent, on a page of its own
Source The stored file, not a rebuild
Shown File name, size and checksum, then the bill rebuilt below
Leaves the account Yes — the clerk loses their place
read off BL-2608-000057 on another account; there is nothing to open here
Adjust
Activate account
Move-in
Close out
✉
🖨
$
ACC-A08
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
Move-out Record payment
Adjust
Activate account
Move-in
Close out
Action 10 of 13 · Change plan, step 1 of 3 · /brazosbend/accounts/a-11812/change-plan · six plans, priced, with the service each one drops
Action 11 of 13 · Change plan, step 2 of 3 · /brazosbend/accounts/a-11812/change-plan · the quote is worked and priced, and names what it left out
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
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
⇆ ⚡📅✎
Issue credit is disabled here.
A credit needs an issued bill.
The control stays on the screen carrying its reason.
Where it is live, it drops the account on the way. On an account with bills this icon leaves for Billing › Fix a bill with an empty bill box, asking the clerk to paste an id they were one click away from — and it lists its
eleven reasons as stored values (charge_billed_in_error, wrong_rate_plan) rather than as sentences.
The refusal here is the correct behaviour: a credit corrects a bill, and this account has never had one.
✉
🖨
$
ACC-A09
/brazosbend/accounts/a-11812/change-plan
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
Accounts / A-11812 / Change plan ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Bramble Bakery
ACCOUNT A-11812
Change plan
Current plan Sample — Residential Services at this unit ELECTRIC WATER
1 · Pick the new plan
Filter ▾ ⚲  Search plans Columns ▾ ⇩  Export
PLAN BASE PER MONTH NOTE
Industrial $180.00 Drops water
Residential Standard $20.00 —
Sample — Commercial $63.00 —
Sample — Industrial $195.00 —
Sample — Residential $20.00 Current
Small Commercial $15.00 Drops electric
a plan that does not carry a service this unit takes says so on its own row
Continue
There is no step rail on this wizard.
Worth reading twice on this account: a commercial bakery is on the residential plan, because the plan follows the unit.
ACC-A10
Action 12 of 13 · Change plan, step 3 of 3 · /brazosbend/accounts/a-11812/change-plan · the last step recaps every answer — from, to, date, and the worked figures
/brazosbend/accounts/a-11812/change-plan
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
Accounts / A-11812 / Change plan ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Bramble Bakery
ACCOUNT A-11812
Change plan
Current plan Sample — Residential Services at this unit ELECTRIC WATER
2 · Effective date and what it costs
When it takes effect
On a date I choose ▼
Only a date can be used today.
New plan starts on *
10/01/2026 📅
A date inside a period already billed is refused: bills already sent are never repriced.
Show what it costs
What this changes
LINE AMOUNT
Current plan, base charges $20.00
New plan, base charges $63.00
Difference on the next bill $43.00
PART-PERIOD LINE DAYS SERVED AMOUNT
SCW-RES 17 $11.33
SCW-COM 13 $27.30
These part-period amounts were worked out by the rating engine.
NOT CALCULATED — THE CATEGORY DIFFERENTIAL
One rule says recompute the category differential on a plan change and another says the deposit is not recomputed in v1. Both are CONFIRMED. No differential is stated and none is registered. Two rules
meet here and neither covers the gap
NOT CALCULATED — USAGE
B4.3 prorates usage as well as base. Pricing usage for a period that has not happened needs a forecast, and no rule says what it should be. No rule says what the forecast should be
Net effect on the next bill $43.00
This total leaves out: deposit_differential, usage.
Back Continue
Six internal strings reach a clerk on this step. Four rule and question ids, a Python module path, and two database column names.
ACC-A11
/brazosbend/accounts/a-11812/change-plan
SMARTBillHub ☰
BB Brazos Bend Utilities
Accounts / A-11812 / Change plan ⚲  Search accounts, premises, meters… ⚑ ?
←  Bramble Bakery
ACCOUNTA-11812
Action 13 of 13 · Disconnect notice, step 1 of 5 · /brazosbend/disconnects/new · the only account action that starts with a search, because it is reached from Disconnects too
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
ACCOUNT A-11812
Change plan
Current plan Sample — Residential Services at this unit ELECTRIC WATER
3 · Confirm and notify
From Sample — Residential
To Sample — Commercial
New plan starts on 10/01/2026
Net effect on the next bill $43.00
Part period, old plan 17 days · $11.33
Part period, new plan 13 days · $27.30
What this changes
LINE AMOUNT
Current plan, base charges $20.00
New plan, base charges $63.00
Difference on the next bill $43.00
PART-PERIOD LINE DAYS SERVED AMOUNT
SCW-RES 17 $11.33
SCW-COM 13 $27.30
These part-period amounts were worked out by the rating engine.
NOT CALCULATED — THE CATEGORY DIFFERENTIAL
One rule says recompute the category differential on a plan change and another says the deposit is not recomputed in v1. Both are CONFIRMED. No differential is stated and none is registered. Two rules
meet here and neither covers the gap
NOT CALCULATED — USAGE
B4.3 prorates usage as well as base. Pricing usage for a period that has not happened needs a forecast, and no rule says what it should be. No rule says what the forecast should be
Net effect on the next bill $43.00
This total leaves out: deposit_differential, usage.
Reason
Kept with the change history, and read by anyone asking why later.
Email the customer about this change
Record that proof of eligibility was seen
written to the trail as evidence — not a gate: the change goes through whether it is ticked or not
Back Change plan
ACC-A12
/brazosbend/disconnects/new
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans&Rates
Disconnects / New ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
←  Disconnects
DISCONNECT
Cut service at an address
Action 14 · Payment plan (rail icon 6 of 7) · /brazosbend/accounts/a-11812/payment-plan · live here, and this is the account it was written for
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
Five steps · notices, protections and the date. Nothing is cut until the scheduled date.
1 Account & reason 2 Protections 3 Notice & date 4 Fees & consequences 5 Review
The account
Find the account whose service is being cut.
Account *
A-11812
Type the account number as your lists show it, the customer’s name or the service address.
Account A-11812
Customer Bramble Bakery
Service address 142 Bakers Row · Suite 1
Owed $2,410.00
Deposit held $0.00
Oldest item —
how old the oldest unpaid item is cannot be worked out — no module publishes open-bill due dates yet, though the
account itself is serving 62 days past due
Why is service being cut?
Only the first of these is a collections outcome.
Reason
Non-payment — the ladder has run and they have not paid ▼
Unsafe installation · Tampering or theft · Premises abandoned · The customer asked
What is done at the meter
Full disconnection ▼
Full disconnection · Restrictor / limiter · Leave connected
Save & exit Park Continue
A case is already open on this account. The audit tab records DSC-26-0003 opened on 09/10/2026 with a notice sent, after two dunning tiers.
And the meter question has no answer here: this unit has no meter to disconnect.
ACC-A13
/brazosbend/accounts/a-11812/payment-plan
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
Accounts / A-11812 / Payment plan ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Bramble Bakery
ACCOUNT A-11812
Payment plan
Propose a plan
BALANCE OWED
$2,410.00
all of it arrears
HOW OLD
62 days
past due, from opening buckets
PLANS ON THIS ACCOUNT
None
nothing has been proposed
THIS ACCOUNT HAS NO PAYMENT PLAN
A plan spreads arrears a customer cannot pay at once. There is $2,410.00 here and two dunning notices have already gone out, so this is the account a plan is for.
On an account that already has a live plan the same icon opens onto that plan and refuses a second one: a new plan cannot be proposed: this account already has a live payment plan.
ACC-A14
Action 15 · Add note (rail icon 7 of 7) · /brazosbend/accounts/a-11812 · two fields, two flags — and one of the flags does nothing yet
For A clerk holding one customer's whole position — money, meters, jobs and history — on one screen, and able to act on it without leaving.
How you get here 33 doors, the most-linked screen in the product. The list row (AccountsListPage.tsx:1018) · global search · the customers list · billing (bill rows, bill detail,
pending queue) · payments (four separate tabs) · metering (unit detail, common areas, owner account) · work (build views, awaiting approval, and a BuildRedirect
resolver) · and every wizard's back arrow and done screen.
Primary action Record payment — and it earned the slot. It carried "Activate account" until payments landed, on the argument that a permanently dead button in the primary slot
teaches the wrong thing about a page. The reason expired and the button followed it.
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
⚙
/brazosbend/accounts/a-11812
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
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
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
✕
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Add note
BRAMBLE BAKERY · A-11812
Title
Fill in a title, a note, or both.
Note
Pin to the top
Visible to the customer
This flag is recorded and does nothing yet: there is no customer portal in this version, so no customer can read the note either way.
Cancel Save note
Add note is its own modal and stands alone. It is not a step of Record payment: the two open independently, neither carries a stepper, and neither mentions the other.
Two fields and two flags is the whole of what can be written down about an account in collections.
Adjust
Activate account
Move-in
Close out
ACC-A15
Tabs Twelve, all in the URL. overview · bills (embeds billing's S30 scoped by account) · payments (embeds S33, local table state) · credits · plan · usage · meters · work (+ ?
order= drawer) · adjustments — a frame, no endpoint · documents — a frame, no endpoint · notes · audit.
Table controls Not a list screen. The embedded Bills and Payments tables carry their owning module's controls; the Payments tab's state is deliberately local, not URL-backed,
because the query string is already spent on ?tab= and an account deep link should not carry a payments page number.
Write surfaces Detail n/a — this is the detail.
Add Add note (live) · Record payment (live) · Documents upload disabled with its reason.
Edit NOTHING for account attributes. A note's pin can change; its text cannot, by rule.
Update NOTHING FROM ANY SCREEN — see below.
Walked Not walked — the app would not boot here.
Cognitive load Removes the clerk's need to hold four modules in their head: the bill, the payment, the meter and the job are one page, each read from its owning module rather
than copied.
States Loading panel skeletons; money cells hold their height.
Empty a new account renders every panel with its own stated absence, never a blank.
Failed FailedWithRetry with a cancel back to the list.
Draft (pending activation) Activate is the only live write; move-out, change-plan, payment-plan and close-out each render disabled with a sentence saying why.
Words Chosen: "Due date not known yet" over a blank, and the hover explains that it is the oldest open bill's date and that "which is still open" is the missing half.
Refused: showing the unit's plan as though it were the account's — the two are equal only until the first override.
Components PageHeader · AccountIconRail · accountDetailHeader · accountDetailTabs · AccountUsageTab · NotesTab · RecordPaymentModal · CustomFieldsView ·
WorkOrdersTab · BuildTabPanel
Rules BR-CUS-016 · 018 · 023 · 028 · 029 · 030 · 034 · 035 · 045 · 054 · 055 · 057 · 058 · 059 · 066 · BR-SHL-020 · 023 · 025 · 034 · 044 · 045
These same thirteen, redrawn as forms
Everything above is the product as it stands. R4 in §10 draws all thirteen again as dialogs opening over this screen, each carrying every one of its fields rather than a first step
— including the confirmation Activate account has never had, the unit search Move-in has never had, and the late fee, credits and outstanding remainder Record payment has
never shown. Go to R4 →
The six header buttons, measured on one account per status
Four statuses are seeded and were each opened. Disconnected has no account,
so the column that would prove Close out is the one column that cannot be
filled.
Action Active Marked disconnect Vacation hold Closed Disconnected
Adjust off off off off no account
Move-out live live live off no account
Activate account off off off off no account
Move-in off off off live no account
Close out off off off off no account
Record payment live live live live no account
Record payment is live in every status, deliberately — a payment is always
accepted, whatever state the account is in. Adjust and Close out are live in
none.
There is no way to write to the customer from here
Seven icons and six buttons, and not one of them sends the customer a word. On an account carrying two dunning notices and an open disconnect case, a clerk taking the
call cannot answer what have you already sent me without leaving for the Notifications queue. R6 in §10 adds an eighth icon and draws both halves of it. Go to R6 →
The seven rail icons, same four accounts
Icon Active Marked disconnect Vacation hold Closed
Send statement off off off off
Print bill live off off live
Issue credit live off off live
Change plan live live live off
Disconnect notice live live live off
Payment plan live live live off
Add note live live live live
Print bill and Issue credit turn on when a bill exists, not when the account is
open — which is why they are live on the closed account and dead on the two
open ones that have never been billed. Every icon stays on the screen in every
state; only the reason changes.
Finding · the account cannot be edited from anywhere in the product
The write path exists and works. PATCH /accounts/{id} is mounted (apps/customers/api.py:225-228) and handled by services.update_account (services.py:3204), which
validates the payload, applies a status change through the proper path, saves only the fields that actually changed, and writes an audit row. It is covered by tests —
tests/test_us_cus_003_account_write.py:569, :940 and tests/test_cr052_w4_delivery_election.py:157.
No screen calls it. There is no wrapper in api/endpoints.ts, so there is no button. The file says so itself, twice — endpoints.ts:8756: "PATCH /accounts/{id} still has no caller and is
still not wrapped", and in its exceptions block: "still served with no caller and is still deliberately unwrapped (LAW 0 — an unused wrapper is not coverage)."
What that costs a clerk. Every attribute this screen displays is read-only forever: category, sub-type, tax-exempt flag and its reference and expiry, preferred language, autopay,
paperless, SMS reminders, bad address. A tax certificate that gets renewed, a customer who asks for Spanish, a wrong sub-type caught at the counter — none of them has a door.
The only ways to change an account are the six wizards and the bulk import.
Why this is the mirror of the usual finding. The classic defect is a button with no form behind it. This is a form's worth of working, tested, audited server with no button in front of
it — and it is invisible to every check, because nothing fails.
Finding · a defect fixed on one panel survives on two others
DEF-CUS-4625 is recorded at AccountDetailPage.tsx:1301. The PO opened an account and read a panel saying the portal was out of scope — over an account that had a login. Their
words: "I have login portal for this account - portal access says…". The Overview's Portal panel was rebuilt to derive every line.
The same false sentence is still on two other tabs of the same screen.
· Notes tab, AccountActions.tsx:516 — "This flag is recorded and does nothing yet: there is no customer portal in this version, so no customer can read the note either way."
· Audit tab, accountDetailTabs.tsx:1180 — "…There is no customer portal in this version, so no entry can come from a customer."
There are 155 .tsx files under 07-frontend/src/portal/. The portal shipped, and the Overview panel two clicks away now reads its live sign-in data. These two sentences are the
same defect, unfixed, and a clerk reads them as current.
Where this screen's data comes from
accounts.* ───────────→ selectors.account_detail_dict()      (customers)
                      └→ GET /:tenant/accounts/{id}
                      └→ useQuery → <AccountDetailPage/>                    WHOLE
portal_credentials ──→ customers/portal_seam.portal_access_for_account()
   portal_sessions      returns a DICT of derived scalars, reads only
                      └→ <PortalAccessPanel/>      field ⑮   customers ⇄  portal   HEALTHY SEAM
assets.* ────────────→ GET /assets/{id} + /assets/{id}/reads, ONE PER METER
                      └→ <AccountMetersTab/>       fields ⑱-⑳  customers ⇄  assets  WHOLE
account_plan_assignments ─╳ NO DDL IN ANY SIGNED DOCUMENT
                      └→ plan: null + plan_snapshot_unavailable:"BR-CUS-029"
                      └→ header PLAN column shows the UNIT's plan instead      FORKED
# Field Comes from Owned by Health
⑭ Balance ledger via _ar_positions_for() — not accounts.balance customers ⇄
ledger
SERVED
⑭ Balance due date nothing — needs "which bills are still open", a payments position billing does not publish per account billing NOT SERVED
⑮ Plan (header) seams.unit_plan_in_force(account.unit_id) — the UNIT's plan, shown because the account's own snapshot has
no table
customers ⇄
rating
DERIVED
⑯ Last activity nothing — payments are readable, bills and audit are not joined to them, so showing part of the history
would be worse than none
— NOT SERVED
⑰ Portal sign-ins portal_credentials + portal_sessions via portal_seam.portal_access_for_account() customers ⇄
portal
SERVED
⑱ Deposit on file accounts.deposit on file customers SERVED
⑱ Deposit on file accou ts.depos t_o _ e customers SERVED
⑲ Deposit interest no column exists at all (BR-CUS-057) — NOT SERVED
⑳ Credit tier accounts.credit_tier — a computed cache with no computer (BR-CUS-058); always null customers
 STUBBED
㉑ Meter rows assets via GET /assets/{id}, one request per meter, cached by asset id customers ⇄
assets
SERVED
㉒ Recent bills GET /invoices?f.account_id= customers ⇄
billing
SERVED
㉓ Gov id contacts.gov_id_last4, masked — four digits is all the server holds customers SERVED
㉔ Tenant custom
fields
accounts.custom_data on the row, never a live join customers ⇄
tenancy
SERVED
㉕ Adjustments table nothing — no endpoint; the tab draws headings and states the absence billing NOT SERVED
㉖ Documents table nothing — no table and no upload endpoint customers NOT SERVED
Screen health: NOT SERVED  — the worst field on the screen, never an average. 8
SERVED · 1 DERIVED · 1 STUBBED · 5 NOT SERVED · 0 untraced.
Commitments in this section
ACC-S1
A clerk can correct an account's details without a wizard
STATUS Unverified
WAITS ON Nothing on the server. PATCH /accounts/{id} is mounted, handled, audited and tested. What is missing is a client wrapper and a form. The repo's own note is the blocker's
whole text: "still served with no caller and is still deliberately unwrapped (LAW 0 — an unused wrapper is not coverage)."
SCREENS 02
WHAT DONE LOOKS LIKE ON SCREEN On A-10432, an EDIT control on the Account panel opens a form carrying Category Residential, Preferred language English, Tax exempt Yes · TX-EX-
99213 · expires 12/31/2027. Changing the language to Spanish and saving returns to the panel reading Spanish, and the Audit tab gains one account.updated row naming the field, the
old value and the new one.
ACC-S2
The accounts list stays fast at forty thousand accounts
STATUS Unverified
WAITS ON A decision, not a table: the two derived filters and all five sorts run in Python because the figures they order by live in no column. Either those positions get materialised
somewhere sortable, or the list accepts SQL sorting on the four stored columns and states that ageing and balance order only within a page.
SCREENS 01
WHAT DONE LOOKS LIKE ON SCREEN On a tenant with 40,000 accounts, opening Accounts and sorting by Balance descending returns the first fifty rows in under a second, and the
footer reads Showing 1–50 of 40,000. Today the same request builds 40,000 row dicts and seven cross-module batch reads before it slices.
```

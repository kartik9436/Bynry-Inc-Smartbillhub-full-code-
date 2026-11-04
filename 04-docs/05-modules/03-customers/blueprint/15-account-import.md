# 15 · Account import EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 136–140. Extracted text, verbatim — **derived, do not edit.**

**9,455 characters over 5 page(s).**

---

```
Agreement · /brazosbend/accounts/a-11488/payment-plan?step=3 · Commits to POST /accounts/{id}/payment-plans · preview at /payment-plans/preview
How you get here One door: the S21 icon rail's 🗓  Payment plan (AccountDetailPage.tsx:591), occupying accounts only.
Primary action Send agreement ✓ — which queues only. Nothing leaves the building in this release and no e-signature provider is connected.
Walked Not walked.
⚠  Step 8 constraint Not on route-b-migrated.txt — legacy CSS.
Rules BR-CUS-043 · 044 · B4.4 (2dp half-up, remainder on the final)
06
Loading a utility, and the request queue
The three remaining routes: the bulk import that makes a brownfield utility exist
at all, and the two service-request screens the Accounts tab embeds.
15 Account import EXISTS BEHIND
/:tenant/accounts/import  ·  S68  ·  five stages  ·  returns to ?tab=imports
The question: "We're going live on Monday with two thousand accounts in a
spreadsheet. Get them in, and tell me exactly what didn't."
All 5 screens of this flow, drawn at 1280 and buildable as drawn. Real app
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
The agreement
Step 3 of 3 · Agreement
NO STEPPER IS RENDERED
The three steps exist in the code and no rail is drawn for them, so the running screen shows only the form — only the form and a disabled Continue. The three names below are the code’s model of this flow, kept here
because a build would start from them.
The steps as the code models them: Terms · Schedule · Agreement
Email SMS Print
Signed on
09/24/2026 📅
✓ Record signature
Pick at least one channel.
The signature date cannot fall after the first instalment is due.
Queued only — notifications has no send path, so the channel records intent.
←  Back Send agreement ✓
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
Extract · /brazosbend/accounts/import
/brazosbend/accounts/import
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
Accounts · Imports / Account import ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts · Imports
ACCOUNT IMPORT
Where is the file?
Step 1 of 5 · Extract
Save & exit
1 Extract 2 Transform 3 Validate 4 Load WRITES 5 Result
File SFTP API Manual Device
Drop a file
accounts-2026-09.csv
Batch label *
Cutover — wave 1
Encoding detected UTF-8
Migration order: premises →  units + plans →  assets →  ACCOUNTS →  opening reads.
Continue →
/brazosbend/accounts/import
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
Accounts · Imports / Account import ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts · Imports
ACCOUNT IMPORT
Map the columns
Step 2 of 5 · Transform
Save & exit
✓ Extract 2 Transform 3 Validate 4 Load WRITES 5 Result
Saved mapping
System default — accounts ▼
Filter ▾ ⚲  Search columns
Columns ▾ ⇩  Export
THEIR COLUMN OUR FIELD
Then the VALUE map: their codes to ours, per column.
Read as dates OPEN_DT, CLOSE_DT
COLUMNS THAT COULD NOT BE READ
Named individually, with the row count behind each.
Mapped, and empty on every row — also named, because a silently ignored column is
the one that loses data.
Transform · /brazosbend/accounts/import · 1 stated absence on this step, drawn dashed — each names the rule or table it waits on
Validate · /brazosbend/accounts/import
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▦
▤
⚙
CUST_NO customer_no
ACCT account_no
PREMISE unit
BAL_30 opening 31–60
←  Back Continue →
/brazosbend/accounts/import
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
Accounts · Imports / Account import ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts · Imports
ACCOUNT IMPORT
Dry run
Step 3 of 5 · Validate
Save & exit
✓ Extract ✓ Transform 3 Validate 4 Load WRITES 5 Result
Rows with errors
Skip them and load the rest
Stop the whole run
Write mode
Create only
Create and update
Will load 1,904 rows
Loads, with a warning 62 rows
Blocked — will not load 34 rows
A row naming a missing unit ERRORS — it does not create one.
The account number is the utility's own — taken from the file verbatim, required,
and never generated.
←  Back Continue →
/brazosbend/accounts/import
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts · Imports / Account import ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
←  Accounts · Imports
ACCOUNT IMPORT
Commit
Step 4 of 5 · Load
Save & exit
✓ Extract ✓ Transform ✓ Validate 4 Load WRITES 5 Result
Load · /brazosbend/accounts/import
Result · /brazosbend/accounts/import · Commits to the ONE shared ETL runner, accounts target
Where a load lands
Onto the register’s Imports tab, which keeps every run. A rejected run is kept
rather than deleted and it is the most useful row on the list: IMP-26-0011 loaded
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
I have checked the dry run Rows to load 1,966
Opening balances post as balanced opening journal entries, aged into buckets per
account.
An account created by the import inherits its unit's services whatever its status.
←  Back Load ✓
/brazosbend/accounts/import
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
Accounts · Imports / Account import ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Accounts · Imports
ACCOUNT IMPORT
The receipt
Step 5 of 5 · Result
Save & exit
✓ Extract ✓ Transform ✓ Validate ✓ Load WRITES 5 Result
Filter ▾ ⚲  Search rows
Columns ▾ ⇩  Export
ROW WHY IT WAS REJECTED
118 No unit at 44 Cedar
402 Account number blank
Download successes Download failures
Rows in 2,000
Loaded 1,966
Rejected 34
Duration 41s
A refusal skips its own record and nothing else, and every run hands back both files.
Rolling back reverses the opening journal entries with a MIRROR entry dated the
same day — it does not delete them.
Roll back Back to imports
rather than deleted, and it is the most useful row on the list: IMP 26 0011 loaded
nothing and is what the operator corrected to produce IMP-26-0012. The pair is
the record of what was wrong with the file.
Rows in, loaded and rejected are three figures and never two — 1,213 in,
1,201 loaded, 12 rejected. A run showing only a success count would let twelve
accounts go missing without anybody subtracting.
The run’s own record is not redrawn, because it already exists: opening one
of these is the Result screen above — the same five phases with their counts and
the rejected rows listed. Drawing it again would be the same screen twice.
Where a load lands · the Imports tab · /brazosbend/accounts?tab=imports · The five-phase import’s own history — every run, kept
How you get here Two doors: the Imports tab primary (AccountsListPage.tsx:990) and the run-history empty CTA (AccountImportsTab.tsx:426).
Primary action Load ✓, behind a "I have checked the dry run" gate.
Write surfaces Add in bulk, through the ONE shared ETL runner — this is its sixth target, not a pipeline of its own. Roll back reverses the opening journal entries with a mirror entry
dated the same day; it does not delete them.
Walked Not walked.
/brazosbend/accounts?tab=imports
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
Accounts / Imports ⚲  Search accounts, premises, meters… ⚑ ?
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
10 tabs · Imports · 3 runs
↑ New import
Accounts Requests New connects Move-ins Move-outs Transfers Disconnects Complaints Services Imports
RUNS
3
all time
ROWS LOADED
1,297
across every run
REJECTED
1,225
each with a named reason
LAST RUN
05/04/2026
IMP-26-0012
All Loaded Rejected In progress Filter ▾ ⚲  Search by run #, file name or who ran it Columns ▾ ⇩  Export
RUN # FILE STARTED RUN BY ROWS IN LOADED REJECTED STATUS
IMP-26-0012 bbu-accounts-cutover.csv 05/04/2026 09:14 S. Ortiz 1,213 1,201 12 Loaded ↗Open
IMP-26-0011 bbu-accounts-cutover.csv 05/03/2026 16:40 S. Ortiz 1,213 0 1,213 Rejected ↗Open
IMP-26-0009 cedar-court-units.csv 04/22/2026 11:02 A. Whitfield 96 96 0 Loaded ↗Open
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
A rejected run is kept, not deleted. IMP-26-0011 loaded nothing and it is the most useful row here: it is what the operator corrected to produce IMP-26-0012, and the pair is the record of what was wrong with the file.
Rows in, loaded and rejected are three figures and never two. 1,213 in, 1,201 loaded, 12 rejected — a run that showed only a success count would let twelve accounts go missing without anybody subtracting.
The run’s own detail is already drawn. Opening one of these is the import wizard’s Result screen in §08 — the same five phases with their counts and the rejected rows listed.
```

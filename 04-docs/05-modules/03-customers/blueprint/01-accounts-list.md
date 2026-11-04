# 01 · Accounts list EXISTS BEHIND ACC-01 · ACC-02

**Source:** `accounts-blueprint.pdf`, pages 3–5. Extracted text, verbatim — **derived, do not edit.**

**9,484 characters over 3 page(s).**

---

```
B14 rule 31 No database id is ever the visible value of a field.
B14 rule 32 A screen has a description budget, and no rule id or internal code appears in clerk-facing copy.
BR-SHL-025 A control this role or this deployment cannot honour renders disabled with its reason, never hidden.
BR-SHL-044 One page header, exactly one primary action.
NFR-3 / NFR-5 Universal server pagination; no hard caps anywhere. Load-bearing rather than tidy — they are what keeps T4/T3 reachable.
Hard rule 4 Financial immutability: no UPDATE or DELETE on issued invoices, invoice lines, payments or journal entries. So an edit control on any of those is a finding,
not a feature. One narrowing exists — three columns on payments through POST /payments/{id}/correct-reference alone.
02
The register — where a clerk lives
Two screens carry this whole surface: the list a clerk opens twenty times a day,
and the account behind one row of it. Everything else in this document is a
wizard launched from one of these two.
The headline, stated plainly: every route here has a door
The single highest-value thing this audit does is find screens that are built, routed, tested and unreachable. On the Accounts surface there are none. All 17 routes name at least
one inbound link read out of the source; /:tenant/accounts/:accountId alone has 33, reaching in from billing, payments, metering and work. The door problem this process exists
to catch is not this surface's problem.
The two real findings are the mirror image — a write path with no door (§02, PATCH), and a list that builds the whole tenant before it pages (§02, NFR-3).
01 Accounts list EXISTS BEHIND ACC-01 · ACC-02
/:tenant/accounts  ·  ?tab= × 8  ·  S17  ·  AccountsListPage.tsx
The question: "Someone is on the phone and all they've given me is a name, or a
number off a bill, or the street. Find them — and tell me what they owe before I have to
ask."
/brazosbend/accounts?tab=accounts&sort=name&dir=asc&page=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Accounts ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
Accounts
Move-out Move-in + New account
Accounts 72 Requests New connects Move-ins Move-outs Transfers Disconnects Imports
For A billing clerk at a utility of up to 40,000 accounts finding one customer from a fragment, and reading their money position without opening anything.
How you get here It is the door — the sidebar's own nav item (SHELL_NAV { module:"accounts", path:"/accounts" }, AppShell.tsx:216, rendered :752). Also from the Dashboard
to-do rows (DashboardPage.tsx:990), global search "View all in Accounts" (GlobalSearchResults.tsx:220), and as the back-arrow target of eight wizards.
Primary action One slot that relabels per tab — "+ New account" · "+ New request" · "+ New connect" · "Move-in" · "Move-out" · "+ New transfer" · "+ New disconnect" · "↑ New
import". Exactly one primary on the page whatever the tab, which is BR-SHL-044 honoured rather than fought.
Tabs Eight, all in the URL as ?tab= and all with a real body — none renders a note about itself. accounts → this table · requests → ServiceRequestsListPage urlState=
{false} · new-connects → ParkedDraftsPanel + NewConnectsTab · move-ins / move-outs / transfers / disconnects → the same pairing · imports →
AccountImportsTab. An unknown ?tab= falls back to accounts rather than erroring.
Table controls Search SERVER  one SQL statement, five OR-legs, gated at 2 characters (selectors.py:2706-2723). Two legs are lazy querysets rendered as nested subqueries, so
they cost no extra round trip.
Filter SERVER  for status · category · autopay · kind · unit_id · premises_id (:2726-2747). IN MEMORY  for ageing and balance>0 (:2795-2802) — deliberately,
because both figures are derived and stored in no column, so a WHERE clause would be a second implementation of the same maths free to disagree with the cell in
the same response.
Columns HEALTHY  show/hide, bidirectional reorder, Reset, and persisted per user server-side under table.<screen>.columns (DataTable.tsx:381). The identity
column can never be hidden.
Sort & pagination IN MEMORY  — see the finding below. All five sorts run as rows.sort() in Python; SQL does only .order_by("id").
Write surfaces Detail the account-number cell is a link to screen 02 (AccountsListPage.tsx:1018).
Add "+ New account" opens the six-step creator and it really posts (:999, :848) — not the usual Add-button-with-no-form.
Edit NOTHING.
Update NOTHING FROM ANY SCREEN — see the PATCH finding below.
Walked Not walked. The app could not be booted here (no docker daemon, no systemd, no PostgreSQL, no node_modules). Every statement in this entry is read from
source.
Cognitive load Removes "which number is this?" — one box takes the account number, the customer number, a name, a street or a meter number. And removes the arithmetic of
"do they owe us anything", by putting the ledger's own figure on the row rather than a cached column.
States Loading skeleton rows at table height; the KPI tiles render —, not 0.
E t th h d t t t ith "+ N t" it CTA ( 1522)
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
ACCOUNTS
72
live and closed
OUTSTANDING
POSTING DATE
$24,992.65
across all ageing
PAST-DUE 60+
Not counted yet
accounts owing money 60 days or more
overdue
CLOSED THIS YEAR
Not counted yet
PENDING ACTIVATION
1
no bill can be raised yet
⚲  Account #, customer #, name, address, or meter #… All + Filter ▾ ▦ Columns ▾ ⇩  Export
ACCOUNT ⇅ NAME ⇅ PREMISE SERVICES BALANCE ⇅ LAST BILL STATUS ⇅ AGEING
AC-2026-00001 Ana Alvarez 101 Silver Creek Rd · Unit 1 E W $158.10 08/02/2026 Active —
A-11812 Bramble Bakery 142 Bakers Row · Suite 1 E W $2,410.00 Awaits billing Active 61–90 days past
A-11721 Calloway, Brett 9 Tanner Street · Unit 1 E W $1,204.50 Awaits billing Active Over 90 days past
1–50 of 72  ·  Rows per page 50 ▾   ·  ‹ ›
Empty the shared empty state with "+ New account" as its CTA (:1522).
Failed a permission failure renders PermissionDenied with a way back to the dashboard; the surface is not drawn at all.
Nothing can be owed yet a pending-activation row reads Awaiting in Balance, never $0.00 — the domain state this screen exists to get right.
Words Chosen: Awaiting over a dash or a zero, everywhere a figure is absent rather than nil. Refused: Current as a fallback for a null ageing band — that would be a claim
about a customer's money. Refused: a Plan column, because the snapshot has no DDL and an always-empty column is a worse answer than none.
Components PageHeader · KPIStrip · DataTable · FilterBar · MoneyCell · DateCell · StatusPill · AwaitsCell · AccountServiceChips · AgeingCell
Rules BR-CUS-015 · 016 · 017 · 048 · 053 · 055 · 059 · 068 · 510 · BR-SHL-010 · 011 · 013 · 023 · 025 · 034 · 044 · NFR-3
Finding · GET /accounts builds the whole tenant before it pages
What the code does. selectors.py:2751 is accounts = list(qs.order_by("id")) — every matching account, materialised. Seven batch cross-module reads then run across all of
those ids (:2755-2770): AR positions, last issued invoice dates, ageing segments, customer numbers, contact names, service codes, premise cells. Rows are built for all of them, two
filters and all five sorts run in Python, and only then does api.py:143 slice fifty out.
The docstring says so itself, at :2752: "this function serializes EVERY matching account and the paginator slices afterwards."
What it costs. The work is O(tenant), not O(page). There is a measured datum in the file already — the DEF-2723 comment records 562 ms for seventy-three accounts on an idle
system. T5's ceiling is 40,000 accounts, which is roughly 550× the rows built to render the same fifty.
Not overclaimed. The client does receive fifty rows and the envelope count is correct, so this is not a correctness bug — it is a scale breach of NFR-3, and the Python sort is the
same disposition CLAUDE.md already flags on GET /outstandings. CLAUDE.md names four known NFR-3 breaches; this is a fifth, and it is on the busiest screen in the product.
Why it is defensible today and not tomorrow. Every Python-side step has a stated, good reason: the derived figures live in no column, and batching per page beat a query per
row. At T7 (≤3,000) it is fine. The rule it breaks is the one that exists so T4 and T3 stay reachable.
Where this screen's data comes from
accounts.account_no ──→ selectors.account_row()          (customers)
                    └→ GET /:tenant/accounts               50 of N, sliced in Python
                    └→ getAccounts() → <DataTable/>        field ①            WHOLE
ledger journal lines ─→ selectors._ar_positions_for()      (customers ⇄  ledger)
                    └→ row.balance + row.balance_currency
                    └→ <MoneyCell/>                        field ⑤            WHOLE
billing invoices ────→ seams.last_issued_invoice_dates()   (customers ⇄  billing)
                    └→ row.last_bill_at                    field ⑥   null today  BREAKS AT billing
                                                           renders "Awaiting", never a dash
account_opening_buckets → selectors.ageing_segments_for()  (customers)
                    └→ row.ageing_segment (4 bands)        field ⑧            WHOLE
                       row.aging  ← billing's OWN vocabulary, still null       FORKED
# Field Comes from Owned by Health
① Account # accounts.account_no via GET /accounts customers SERVED
```

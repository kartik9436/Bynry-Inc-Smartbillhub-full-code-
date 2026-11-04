# Billing blueprint — the pages nobody had opened

**`CR-101-BRC03` · measurement lane · 2026-09-14.** Step 1 rendered all 249 pages of
`05-prototype/04 Billing, As Built.pdf` and **opened 187 as images**. This file is the other
62 — read as IMAGES (B14 rule 42), never from the text layer, which on this document drops
every slash, colon and digit.

**Nothing here is built. This file is a record.**

| | |
|---|---|
| Pages this lane was sent at | **62**, in nine ranges |
| Pages the nine ranges actually contain | **59** — see *The page arithmetic* below |
| Pages opened as images by this lane | filled in per block, counted at the end |
| Renders | `/tmp/bil-gap-png/pNNN.png`, scale 2 (2448×1584); scale 4 where a table needed it |

---

## ⛔ CONTRADICTION 1 — §14's cards do NOT start where step 1 says they start

**Step 1's coverage table** (`03-rulings-and-registers.md` §10) splits §14 like this:

| Step 1 says | |
|---|---|
| p173–178 | *"§14's index table rows (the 100-row index above the cards)"* · *"Nothing material"* |
| p180–201 | *"§14's remaining commitment cards"* |
| p179 | opened |

**Measured from the images, that boundary is wrong by two pages, and the error hides five
full cards.**

* The 100-row **index table ENDS in the top two-thirds of p177**, with `BIL-S102`.
* **`The cards in full` is a heading on p177**, and **`BIL-S1`'s card opens beneath it on the
  same page.**
* **p178 is entirely cards** — `BIL-S2`, `S3`, `S4`, `S5` in full and `BIL-S6` opening.

So the true split is **index p172–p177 (upper), cards p177 (lower)–p201**, and step 1's
*"nothing material"* verdict on p173–178 is true of p173–p176 and **false of p177 and p178**,
which carry the bodies of `BIL-S1` … `BIL-S6`. **`BIL-S1` is one of §12's nine that cost the
most**, so the highest-priority card in the document sat inside the range marked *nothing
material*.

⚠ **Why this matters beyond the two pages:** step 1's own count says 94 card bodies were
unread. It is **100** — the six on p177–p178 were counted as index rows.

---

## ⛔ CONTRADICTION 2 — the two withdrawn commitments can now both be named

Step 1 recorded *"Withdrawn by a ruling — 2 — not independently counted (`BIL-S101` is one)"*.

**Read off the index table, the minted range is `BIL-S1` … `BIL-S102` with exactly two ids
absent: `BIL-S87` and `BIL-S101`.** `S86` is followed by `S88`; `S100` is followed by `S102`.

**102 minted − 2 withdrawn = 100 live**, which is what the figure band claims and what step 1
counted from the STATUS lines. ⚠ **This also explains step 1's flagged
*"`BIL-S1 … all 101`" vs "Of the 100 here"* discrepancy**: the register's own range sentence
counts minted ids and the figure band counts live cards, so **neither is wrong — they measure
different things**, and the safe statement is *100 live commitments across ids `S1`–`S102`*.

---

## §14 · The 100-row index, as read off p173–p177

**Columns, left to right: id · what it undertakes · WAITS ON (truncated in the index — the
card is authoritative) · SCREENS · STATUS chip.**

⚠ **The index's WAITS ON column is truncated with `…` on long rows and reads `—` on every id
from `S71` upward.** Step 1 quoted §15 saying the index repeats the cards verbatim (*"67 of
70 waits-on texts byte-identical"*); that is true of the EARLIER ids only. **For `S71`–`S102`
the index carries no waits-on text at all** and the card is the only source.

`BIL-S1`–`S6`'s index rows are on p172, which step 1 opened; their CARDS are below.

| id | Undertakes | Waits on (index) | Screens | Chip |
|---|---|---|---|---|
| S7 | An approver can read what a correction moves, line by line | Nothing. | 13 | Exists behind |
| S8 | A clerk can find a correction case, and a budget-billing row, past the first fifty | Nothing on the server — both endpoints paginate and order in SQL already. | 12, 13 | Exists behind |
| S9 | A clerk sees the product's own failure state instead of a JavaScript stack trace | Nothing. | 01–15 (all fifteen) | **New build** |
| S10 | A clerk can identify a bill and an account by their number, not their database id | Nothing. | 12, 13 | Exists behind |
| S11 | A clerk is told when a budget-billing action fails | Nothing. | 12, 13 | New build |
| S12 | A refusal stops being true and the suite goes red | Nothing but the decision to do it. | 02, 04, 05, 10, 11 | New build |
| S13 | A clerk can narrow the bills list to one cycle, one run or a date range | Nothing on the server. | 01 | Exists behind |
| S14 | The Billing header tells a clerk something true, and takes them somewhere | Nothing for two of the three. | 01 | Exists behind |
| S15 | A clerk can see whether a bill has actually been printed | The outbound queue has no table (BR-BIL-016 / r10 #8). | 01 | New build |
| S16 | A clerk can start a correction from the row the bill is on | An overflow-menu component, which does not exist anywhere in this product (DEF-2453) — which is… | 01, 13 | New build |
| S17 | A clerk can tell whose bill they are looking at, and how much, without scrolling | One read. | 02, 02.1, 02.2, 02.3, 02.4 | New read |
| S18 | The bill overview reads as seven questions, each with a one-word label | Nothing for five of the seven. | 02.1 | Exists behind |
| S19 | A clerk can see whether the bill reached the customer, without hunting for it | Nothing to move it. | 01, 02.1 | New read |
| S20 | Small things stop costing a clerk a click or a squint | Nothing, except the Audit tab — and that one is not billing's to fix: it is metering's S61 viewe… | 02, 02.1, 02.2, 02.3, 02.4 | Exists behind |
| S21 | A clerk can read what a correction did, in order, and what the customer owes because of it | Nothing for the sequence — GET /invoices/{id}/chain and the correction case are both served, and… | 02.3 | Exists behind |
| S22 | An audit row cannot be misread | Not billing's to fix. | 02, 02.1, 02.2, 02.3, 02.4, 02.5 | **Blocked** |
| S23 | The Charges tab says how much water, not just how much money | Nothing. | 02.2 | Exists behind |
| S24 | A clerk settles the routine decisions once, before the run starts | Nothing. | 01, 16 | Exists behind |
| S25 | A clerk can bill part of a cycle, sweep up who was missed, and take over an open run | Scope needs a filter on the run's account set. | 01, 16, 14 | Exists behind |
| S26 | Pricing runs in the background, with progress, and money is on screen before any decision | Nothing. | 16, 17 | Exists behind |
| S27 | One review screen shows every account, searchable, filterable and paged | Search and filters over the run's account set; | 02, 17 | New build |
| S28 | No account can fall out of a run silently | Nothing — it is one subtraction over counts already served. | 02, 17 | Exists behind |
| S29 | The sign-off says what signing does, in three groups | Nothing. | 18, 03 | Exists behind |
| S30 | The run can print the bills it just issued | Nothing. | 19, 04, 15 | Exists behind |
| S31 | Every input on a billing screen uses the right control | The multi-select half. | — | New build |
| S32 | Step 2's chips are generated from what the run raised, in three bands | Nothing. | 17, 17.1–17.15 | Exists behind |
| S33 | Every option states whether it bills or holds the account | Nothing, and it is the highest-value label in the section: two prorate choices are recorded and… | 17.1–17.9 | Exists behind |
| S34 | A master account's bill says how many units it covers | Nothing. | 16, 17.11, 17.14, 17.15 | Exists behind |
| S35 | A clerk can bill a held account from the queue | Nothing on the server — | 20, 20.1 | Exists behind |
| S36 | The held-accounts queue is dated, filtered and paged | Nothing. | 20 | Exists behind |
| S37 | An account can be held out of billing until a review date | A ruling. | 20.2, 20.3 | **Blocked** |
| S38 | A run's service scope is part of its idempotency key | Nothing but the change itself. | 16 | New build |
| S39 | A master bill prices each connection on its own plan and its own tier ladder | Nothing. | 17.11, 17.15, 20 | New build |
| S40 | A pre-bill check runs stages 1–5 and writes nothing; bills are created at sign-off | Nothing architectural. | 17.0, 17, 18 | Exists behind |
| S41 | The check runs in a worker and the screen fills in while it does | Nothing on the server — | 17.0 | Exists behind |
| S42 | A bulk action can apply to every row in a chip, not just the visible page | Nothing but the UI and one server call. | 17.16–17.20, 17.22 | New build |
| S43 | Sign-off states what is NOT being billed, and the money foots on screen | One new axis and one new aggregate. | 18 | New build |
| S44 | Arrears are visible while the clerk is still deciding | One thing, and it is the same thing three screens need: the business day has to reach the past-d… | 01, 17.21, 20 | New build |
| S45 | The served note claiming no run has ever been timed is corrected | Nothing. | 17.0 | Exists behind |
| S46 | Metering publishes one aggregate count of a cycle's metering inventory | One new published read, owned by metering. | 16 | New read |
| S47 | A clerk can select rows and act on the selection | Nothing on the server. | 17.1–17.22 (all 22) | Exists behind |
| S48 | A bulk action acts on the selection the clerk made, and reports what moved | Nothing new on the server — | 17.16–17.20, 17.22 | Exists behind |
| S49 | The estimate disposition can actually be submitted | A fix, not a feature. | 17.1, 17.16, 17.22 | Exists behind |
| S50 | A clerk can open a real bill before anything is sent, and a specimen before anything is created | Step 4's three bills are a link to a served endpoint. | 18, 19 | New build |
| S51 | A clerk can raise all six one-time kinds through one three-step wizard | Nothing on the server. | 21, 22.1–22.6, 23 | Exists behind |
| S52 | The back-bill's period list shows what the grouping costs the customer | Nothing but the panel. | 22.4, 22.5, 24 | Exists behind |
| S53 | Mid-period split billing gets a caller | A wiring fix, not a feature. | — | Exists behind |
| S54 | Step 2 shows what a one-time bill will price on, before it prices it | Nothing new on the server. | 21, 22.1–22.6 | Exists behind |
| S55 | A clerk can enter a missing reading on the bill screen, and it lands in Meter Reads | Nothing on either server. | 22.1–22.4, 24 | Exists behind |
| S56 | A final bill applies the deposit first, then offers exactly one settlement path | The arithmetic and the master path are both built. | 22.3, 23 | **Blocked** |
| S57 | Step 3 shows what the bill will do to the books — including when it cannot | Both deposit entries are written and signed; | 22.3, 23 | Exists behind |
| S58 | A utility can put one customer on a flat monthly amount | Nothing on the server. | 25, 25.1 | Exists behind |
| S59 | The three level figures are never collapsed into one | Nothing — | 25, 25.1 | Exists behind |
| S60 | The settle-up is already posted by the cycle run, and a clerk can see it coming | Nothing on the server, and nothing to build there either. | 25.2 | Exists behind |
| S61 | An operator picks a reason and the system says what it will do | The taxonomy is written; | 26, 26.1, 26.2, 26.3 | **Blocked** |
| S62 | A clerk can cancel and regenerate one account's bills over a window | Nothing new — | 26, 26.4 | Exists behind |
| S63 | A clerk can cancel and regenerate a batch, and cannot undo it | All six scope selectors and the aggregate are built, including the tie-out (Σ credit − … | 26.5 | Exists behind |
| S64 | A print set can be scoped to a period, not only to a run | A screen change, not a contract change. | 28 | Exists behind |
| S65 | Every bill that will not print says why, and whose job it is | Nothing on the server — | 28, 28.1 | Exists behind |
| S66 | A customer can ask for level pay from the portal, and the button works | One write, and it is a write the portal is already allowed to make. | 25.3, 25.4 | Exists behind |
| S67 | A clerk can see what a customer was promised beside what is correct now | Nothing new on the server — | 25, 25.1, 25.3 | Exists behind |
| S68 | A clerk can see what happens to money already paid against a corrected bill | Nothing on the server — | 26.6, 26.7 | Exists behind |
| S69 | A six-month correction is settled per month, and the two big numbers are separated | Nothing new — | 26.2, 26.7 | Exists behind |
| S70 | Print bills is a Billing tab with a searchable table of the period | A screen change, not a contract change, twice over. | 28, 28.1 | Exists behind |
| S71 | A clerk can send a bill-ready e-mail that has the customer's figures on it, not em-dashes | — | 02, 09 | New build |
| S72 | A queued delivery row names a template the dispatcher can actually render | — | 09 | New build |
| S73 | A clerk can see the base charge and the schedule name the run already gathered | — | 17, 05 | New read |
| S74 | The Enrol button can enable itself, because the plan's budget-billing flag is answered through the seam | — | 25, 25.1 | New read |
| S75 | A clerk can enrol every eligible account at once | OQ-237 — | 25, 25.1 | **Blocked** |
| S76 | A clerk can trust a run's status, because the column advances or it is gone | — | 27, 10 | New build |
| S77 | The late-fee floor is one number, read from one place | — | 17.20, 22.5 | New build |
| S78 | BR-BIL-030 means one thing, because it is defined once | — | — | New build |
| S79 | A Japanese or French bill line says billing cycle, not bicycle | — | 01, 03 | New build |
| S80 | A clerk reads money at two decimals on every billing screen | — | 25, 25.1, 25.2, 26, 26.1, 26.2, 12, 13 | New build |
| S81 | A clerk can page, sort and filter every billing list, at any size | — | 25, 26, 12, 13 | New build |
| S82 | A billing form reads label, then input, then help — and its chips render | — | 21, 22.1, 25, 25.1, 11, 12 | New build |
| S83 | A clerk never reads a rule id or an internal code on screen | — | 17, 26, 26.1, 13 | New build |
| S84 | Nobody can reach the old six-step run wizard, because it is gone | §03 landing first | 04, 05, 06, 07, 08, 09 | New build |
| S85 | A clerk can generate and send the corrected documents at the end of Fix a bill | — | 26.8 | New build |
| S86 | A clerk can cancel a bill, and is told what the cancellation moves before confirming | — | 02, 11 | New build |
| **S87** | — **WITHDRAWN, id absent from the register** | — | — | — |
| S88 | A clerk never meets copy describing a screen that cannot be reached | — | 04, 11 | New build |
| S89 | B14 rule 7 can be complied with, because it names the style world the product uses | a B14 amendment | 16, 04 | **Blocked** |
| S90 | A utility with more than 25,000 accounts can run a cycle at all | — | 16, 17 | New build |
| S91 | A clerk never decides on a row that shows no amount | — | 17, 17.1, 05 | New build |
| S92 | An account whose meter simply was not read still reaches the run | — | 17, 17.1 | New build |
| S93 | A customer receives a bill that looks like a bill | — | 28, 03 | New build |
| S94 | The bills list answers at 40,000 accounts, because the search stops building every matching row | — | 01 | New build |
| S95 | A lost race refuses cleanly instead of failing the whole transaction | — | 16 | New build |
| S96 | Five seams read the tables that now exist instead of substituting a fact | — | 17.0, 17 | New build |
| S97 | A clerk can find a bill by its cycle, which the search box already offers to do | — | 01 | New build |
| S98 | The four refusal states on the bill header can be seen before they ship | — | 02, 02.1 | New build |
| S99 | A clerk reads the tax and the service period on the bills list, without opening the bill | — | 01 | Exists behind |
| S100 | A clerk can see when a hold started and whether it was ever caught up | — | 20, 14 | Exists behind |
| **S101** | — **WITHDRAWN by ruling 25, id absent from the register** | — | — | — |
| S102 | A utility sets its own late-fee balance floor, instead of inheriting a number written into the code | — | 17.20, 22.5 | New build |

⚠ **`S94` is the `NFR-3` commitment and it names the ICP ceiling in its own title** —
*"answers at 40,000 accounts"*. Step 1 routed the `NFR-3` breach to `DEF-BIL-5234`; the
document had already undertaken it as a commitment.

---

## §14 · How the register is actually built — four groups, not one flat run

**Read off the images. Step 1 had no way to see this, and it is what makes the arithmetic
close.**

| Group | Heading, verbatim | ids | cards printed |
|---|---|---|---|
| 1 | (no heading — the register proper, opened by `The cards in full` on p177) | `S1`–`S70` | 70 |
| 2 | **`Minted in this pass — nineteen`** (p194) | `S71`–`S89` | 18 (`S87` withdrawn) |
| 3 | **`Minted after the ruling — one`** (p198) | `S102` | 1 |
| 4 | **`Minted in the commitment pass — twelve`** (p199) | `S90`–`S101` | 11 (`S101` withdrawn) |
| | | **102 ids** | **100 cards** |

**19 + 1 + 12 = 32**, which is the figure band's *"32 were minted across the three audit
passes"* — **so the group headings count MINTED ids, withdrawn ones included**, and the card
count is 100. Every figure in §14 now reconciles:

    70 originally minted + 32 minted across three audit passes − 2 withdrawn = 100 live
    50 Exists behind + 38 New build + 6 New read + 6 Blocked            = 100 ✔

⚠ **Groups 2–4 carry a FIFTH field the register proper does not: `MINTED FROM`** — the
defect, ruling or section the commitment was raised out of, usually with the measured line of
code. Step 1 recorded four fields (`STATUS` · `WAITS ON` · `SCREENS` · `DONE LOOKS LIKE`).
**For the 30 printed cards in groups 2–4 there are five**, and the fifth is the one that says
why the commitment exists.

### The figure band, read off p172 (step 1 opened this page; the band is quoted here because
every count above is checked against it)

> *"**A new ID series, on purpose.** These are `BIL-S1` … `BIL-S30`, minted for this
> document. … **Every row carries one of four state chips, and only four** — Exists behind ·
> New read · New build · Blocked — and the chip says **what the work waits on**, never how
> confident anyone is. Of the **100** here: **50 exist behind a screen that does not ask for
> them**, 6 need a read published, 38 are new build, and 6 are blocked. **32 were minted
> across the three audit passes and two were withdrawn** — each withdrawn by a ruling that
> made the absence deliberate rather than by anyone deciding it did not matter."*

⚠ **Step 1 was RIGHT that the id-range sentence is stale, and there are TWO MORE stale figures
in §14's own prose that step 1 did not see:**

| §14 says | Measured on the pages |
|---|---|
| *"These are `BIL-S1` … `BIL-S30`"* | the register runs to `S102` — step 1's finding, confirmed |
| *"a **seventy-row** index ran ten pages"* (p172) | the index printed today is **100 rows over p172–p177**, under six pages |
| *"Sixteen of **the thirty**"* (p184, closing the first group) | the first group is **seventy** cards, `S1`–`S70` |

**Three stale counts in one section.** Take every §14 count from the figure band, never from
the surrounding prose.

---

## §14 · THE NINE THAT COST THE MOST — cards in full

These are §12's nine. **This is the block a sibling needs first.**

### `BIL-S1` — *A clerk can see what was billed last month, and who signed it off* · p177–p178
* **STATUS** Exists behind
* **WAITS ON** *"Nothing. `GET /billing/runs` is served, `PastRunsPanel` is written, and
  `bill_runs.run_by` is populated and on the wire. The blocker named on screen — "nothing
  would list it" / "no actor column" — is false in both halves that matter."*
* **SCREENS** 27, 10, 04, 01 *(the index row on p172 lists the same four as 01, 27, 04, 10)*
* **DONE LOOKS LIKE** *"Opening `Billing → Past billing runs` shows a table whose first row
  reads `BR-2608-0042 · 08-A · 01 Aug – 31 Aug 2026 · 1,263 bills · $338,904.00 · Dana Reyes ·
  Issued`, and the panel that currently says it arrives later is gone."*
* ⚠ **This is `DEF-BIL-5230`'s refusal from the other side** — step 1 found *"It arrives with
  the billing run work"* standing over 3 served runs. The card says the same thing and says
  what replacing it looks like. **Every figure in that row is an illustration (B14 rule 37);
  do not seed a fixture from it.**

### `BIL-S9` — *A clerk sees the product's own failure state instead of a JavaScript stack trace* · p179
* **STATUS** New build
* **WAITS ON** *"Nothing. There is no error boundary and no `errorElement` anywhere in the
  route tree; the only one in the whole front end is inside `MoneyCell`."*
* **SCREENS** *"all 15, and every other screen in the product"*
* **DONE LOOKS LIKE** *"A screen whose read returns an unexpected shape shows A18 §4's framed
  message **with the left rail still there**, and "Unexpected Application Error!" never reaches
  a clerk."*

### `BIL-S56` — *A final bill applies the deposit first, then offers exactly one settlement path* · p190–p191
* **STATUS** Blocked
* **WAITS ON** *"**The arithmetic and the master path are both built.** A $150.00 deposit held
  14 months at 2% earns $3.50, so $153.50 applies before any path is chosen; the accrual engine
  landed 2026-09-03. The transfer target is **resolved from the data, never supplied** — your
  ruling of 2026-08-24, "master account gets debt - if sub accoun tis unable to pay it ; even
  aftr deposite settlement". **Two things are genuinely missing:** there is **no settlements
  table**, so the chosen path has nowhere to live and one-path-per-bill is enforced inside a
  call and not across calls; and the owner rung needs `premises.owner_customer_id`, measured
  absent."*
* **SCREENS** 22.3, 23
* **DONE LOOKS LIKE** *"A commercial move-out with $289.40 of charges and a $150.00 deposit
  shows **−$150.00 and −$3.50 as separate lines, $135.90 still due**, and three paths of which
  *Transfer to master* names **100299 Alder Holdings** — or is greyed with the reason no master
  resolved."*
* ⚠ **The chip reads Blocked and the card does not name a ruling it waits on.** By the
  document's own vocabulary Blocked means *waits on a ruling, or on something this module does
  not own* — here it is the second half: a missing table and a column on `premises`, which is
  metering's. **Nothing on this card is with the PO.**

### `BIL-S61` — *An operator picks a reason and the system says what it will do* · p192
* **STATUS** Blocked
* **WAITS ON** *"**The taxonomy is written; two things are not.** Thirteen reasons in three
  classes, the strongest-class rule, the refusal of a document-class case with a money delta,
  and the five routed-away reasons all exist in code. ⚠ **The reason→class map is PROPOSED, not
  ratified**, and the tenant-extensible reason table **has no class column and is not built** —
  so a tenant's own reason is refused rather than defaulted."*
* **SCREENS** 26, 26.1, 26.2, 26.3
* **DONE LOOKS LIKE** *"Ticking *Goodwill* renders "issues a goodwill credit on the account,
  excluding tax: the bill is not touched…" in the operator's words, and **no mechanism dropdown
  exists anywhere in the workflow**."*
* ⚠ **This is the other side of `DEF-BIL-5233`** — step 1 measured all thirteen correction
  reasons reaching a clerk as raw `snake_case` with zero `billing.fix.reason.*` keys in any
  catalogue. The card asks for the same words. **`BIL-S61` is the commitment `DEF-BIL-5233`
  had no owner for.**

### `BIL-S90` — *A utility with more than 25,000 accounts can run a cycle at all* · p199
* **STATUS** New build
* **WAITS ON** *"— nothing. `NFR-5` already forbids a per-tenant cap and `CLAUDE.md` names it
  load-bearing"*
* **SCREENS** 16, 17
* **DONE LOOKS LIKE** *"Scope accepts a 40,000-account cycle and the run completes; no constant
  caps it."*
* **MINTED FROM** *"§13 — `DEF-BIL-4224`. **Measured:** `run_jobs.py:227`
  `MAX_ACCOUNTS_PER_RUN_DEFAULT = 25_000` against a T5 ceiling of 40,000. **Blast radius: one
  constant, one module — and every tenant above 25,000.**"*

⚠ **DOES THE CARD AGREE WITH THE PO RULING? PARTLY, AND THE HALVES MATTER.**
The PO ruled 2026-09-14: *"generally utilities will devide them into nilling cycles and hence
25k limit is good"* — a run is scoped to a CYCLE, so the cap stays and `BIL-S90` is not built.

| | Card | Ruling | Verdict |
|---|---|---|---|
| What the constant is | names it `MAX_ACCOUNTS_PER_RUN_DEFAULT` — a **default**, i.e. a setting | *"it is a deployment setting where `0` switches it off"* | **AGREE.** The card's own naming supports *change one setting* |
| What it caps | **a RUN** | **a run, scoped to a cycle** | **AGREE** |
| The rule it rests on | `NFR-5`, *no hard caps anywhere* | — | ⚠ **THE STRAIN.** `NFR-5` and B6's design rule forbid a **per-TENANT** cap. This is a **per-RUN** cap, and once a run is a cycle it is not a per-tenant maximum at all. The card's citation overreaches |
| The consequence claimed | title: a utility above 25,000 *cannot run a cycle at all* | a 40,000-account utility billing four cycles of 10,000 never reaches it | **DISAGREE, and the ruling is right** |

⚠ **THE DRAMATIC SENTENCE IS NOT ON THE CARD.** *"A utility above 25,000 accounts cannot run
a cycle at all"* is §12's ranking prose, not `BIL-S90`'s text. The card's own claim is the
narrower *"no constant caps it"*. **The ruling stands and the card should not be built** — but
the card is a better-argued item than the summary that was routed, and the honest statement of
the residue is: *a per-run default of 25,000 is lawful under `NFR-5` only while a run is a
cycle; if a run is ever scoped wider, the cap becomes the thing `NFR-5` forbids.*

⚠ **Two other cards treat a 25,000-account run as ordinary and neither is flagged** —
`BIL-S41`'s *"A 25,000-account run opens Check within a second, shows `9,412 of 25,000`"* and
`BIL-S42`'s *"On a 25,000-account run, selecting the Missing read chip selects all 231 rows"*.
**The document's own illustrations assume the cap is a run-size, which is what the PO ruled.**

### `BIL-S91` — *A clerk never decides on a row that shows no amount* · p199
* **STATUS** New build · **WAITS ON** `—` · **SCREENS** 17, 17.1, 05
* **DONE LOOKS LIKE** *"Every reviewable row carries an amount and a currency, or says in
  words why it cannot."*
* **MINTED FROM** *"§13 — `DEF-2596`. **Measured:** `read_analysis.py:328-329` returns
  `amount: None, currency: None`."*

### `BIL-S92` — *An account whose meter simply was not read still reaches the run* · p199–p200
* **STATUS** New build · **WAITS ON** `—` · **SCREENS** 17, 17.1
* **DONE LOOKS LIKE** *"An unread meter appears as a decidable row, not a refusal, and a
  customer type with no base charge still bills."*
* **MINTED FROM** *"§13 — `DEF-3221`, high and open"*

### `BIL-S93` — *A customer receives a bill that looks like a bill* · p200
* **STATUS** New build · **WAITS ON** `—` · **SCREENS** 28, 03
* **DONE LOOKS LIKE** *"The printed page uses the product's own layout, not Courier with
  space-aligned columns."*
* **MINTED FROM** *"§08 — `DEF-BIL-4524`. **Measured:** `documents.py:2017` still reasons from
  "Courier's whole appeal here was that a column position is integer arithmetic". **Blast
  radius: every bill this product prints.**"*

### `BIL-S102` — *A utility sets its own late-fee balance floor, instead of inheriting a number written into the code* · p198–p199
* **STATUS** New build
* **WAITS ON** *"— **ruled 2026-09-13.**"*  ← **nothing is in the way**
* **SCREENS** 17.20, 22.5
* **DONE LOOKS LIKE** *"The floor is read from tenant settings beside the late percentage, the
  minimum and the grace window; no default argument decides it."*
* **MINTED FROM** *"A Product Owner ruling of 2026-09-13, verbatim: **"Yes, if it is limit set
  in setting then - it is not hard coded; it should be based on setting"**. **Measured:** the
  floor is `LATE_FEE_BALANCE_FLOOR`, a *default argument* of `assess_late_fee`
  (`late_fee.py:561`, `:748`), while `BR-BIL-021` already makes the late percentage, the
  minimum and the grace window tenant config. That file's own exception (7) says the question
  *"was never put"* and stamps itself `VERIFIED-UNRATIFIED`. **It has been put, and answered.**"*
* Its group heading (p198) says why it is a group of one: *"The audit found the **$25 late-fee
  floor was a hard-coded default that nobody had ratified**. It was put to the Product Owner in
  plain English with its worked figures; **the answer made it tenant configuration, which is
  work rather than a description.**"*

## ⛔ CONTRADICTION 3 — the late-fee floor. The brief and step 1 say the opposite of the card

| Source | Says |
|---|---|
| Step-2 shared brief | *"The `$25` floor is untouched and still a module constant (`BIL-S102`)."* |
| Step-1 record | *"`$25` floor untouched and still a module constant with no tenant setting (`BIL-S102`)"* |
| **`BIL-S102`'s card + its group heading** | **a PO ruling of 2026-09-13 makes the floor TENANT CONFIGURATION. New build. Waits on nothing.** |

**Both of ours are true as a description of the code and false as a description of the
commitment.** There are **two rulings about the same number, one day apart**, and they do
different jobs:

* **2026-09-13** — the floor comes OUT of the code and into tenant settings. → `BIL-S102`,
  ruled, unbuilt, nothing blocking.
* **2026-09-14** — the floor is tested against the **ageing portion**, not the whole bill. →
  ratifies working code at `late_fee.py:612`, costs nothing. Step 1 has this one right.

**A lane reading the brief concludes `BIL-S102` needs nothing.** It needs the whole move.
⚠ **And `BIL-S77` — *"The late-fee floor is one number, read from one place"*, New build,
waits on nothing, the SAME two screens (17.20, 22.5), minted from `DEF-205`, done = *"Both
screens quote the same floor, and a test fails if the two constants diverge"* — is the same
number a second time.** Anyone touching the floor must read `S77` and `S102` together or they
will de-duplicate two constants into one hard-coded constant and call it done.

## ⛔ CONTRADICTION 4 — both of step 1's NOT-BUILDABLE collisions live in ONE card whose chip says nothing is in the way

`BIL-S39` — *A master bill prices each connection on its own plan and its own tier ladder*
(p186) — **STATUS New build · WAITS ON "Nothing."**

* **WAITS ON** *"Nothing. **Both halves ruled 2026-09-11 — *per connection*.** An engine
  change: a line set, a tariff resolution and a plan snapshot **per connection**, and a tier
  ladder that resets per connection. Two gather refusals are then deleted rather than handled.
  **Reverses the bill-level tax ruling of 2026-08-11 for master accounts**; the supersession is
  written down first."*
* **SCREENS** 17.11, 17.15, 20
* **DONE LOOKS LIKE** *"Elm Court HOA, with a hallway meter and a stairwell meter both
  electric, bills `$64.00` on four lines — two base charges of $12.00 and two usage ladders of
  $20.00. Hillcrest Apartments, spanning *Common Electric* and *Common Water*, bills `$70.17`:
  $69.60 of charges plus a 2.00% city water fee of `$0.57` levied on the water connection
  alone, not $1.39 on the whole bill. Both leave the blocked band. Bayside Holdings, whose
  coverage cannot be read, is still refused."*

**Step 1 escalated these as two separate rulings — `"per conenction"` ($64.00 vs $52.00
pooled) and `"as per connection"` ($69.60 + $0.57 = $70.17). They are ONE commitment card,
and its chip says New build waiting on nothing.** A lane scoping work off the register's
chips — which is what a chip is for — walks straight into a reversal of a signed rule and a
❄️ frozen `GT-17`. **The card is not blind to it** (*"Reverses the bill-level tax ruling of
2026-08-11 … the supersession is written down first"*), but the CHIP is, and the chip is the
part that gets read. **Build neither half. Both are with the PO.**

---

# §17 · The rest of the screens, as built — p215–p247

**Thirteen screens, in four groups**, read as images. Group headings, from the pages:
**Group A** (unlabelled on p215 — 03 alone) · **Group B · Producing bills** (p217, screens
04–10) · **Group C · Billing outside the cycle** (p232, screens 11–12) · **Group D · Putting
a bill right** (p236, screens 13–15).

## What an §17 entry is actually made of — eight parts, not three

Step 1 described §17 entries as *"per-screen drawings, spec tables, data flows and field
tables"*. Measured, each entry has up to **eight** parts, in this order:

1. **Heading** — `nn  <name>` followed by **the commitment ids that touch it, grouped by
   chip** (e.g. screen 04: `Blocked S89 · New build S9 S12 S84 S88 · Exists behind S1 S30`).
   ⚠ **This is a commitment→screen index step 1 never recorded, and it is the fastest way to
   find every card that changes one screen.**
2. **The stamp**, red monospace — `REDRAWN AS …` or `No redraw.`
3. **The address line** — `/:tenant/billing/run · S31 · BIL-02 · step from BILL_RUN_STEPS[0]`
4. **One sentence in a clerk's voice** — *"It's the end of the month. Bill everybody."*
5. **A provenance band** — `AS-BUILT, FROM CODE … never rendered` or `AS-BUILT measured in
   Chromium 1194 at 1440×1100 on 2026-09-11, at commit a1d37a68`
6. **The drawing**
7. **The spec table** — 14 rows: For · How you get here · Primary action · Tabs · Table
   controls · Write surfaces · Walked · Cognitive load · States · Words · Components · Rules ·
   Audience · **Health**
8. **Data flow** (monospace trace) · **field table** (# · FIELD · COMES FROM · OWNED BY ·
   HEALTH) · often a red commentary block

Three entries (10, 13, 14) add a **remedy legend**, a **`Carry-over` table** (AS-BUILT FIELD ·
DISPOSITION · WHY) and **element arithmetic** that states whether it `RECONCILES`.

## ⛔ CONTRADICTION 5 — step 1's §17 warning is RIGHT, and both halves of its evidence are wrong

Step 1 and the shared brief both say: *"NOT ONE of §17's thirteen screens carries a drawing to
build. **Every entry stamps `REDRAWN AS … Build that one`.** Three sources say otherwise and
all three are stale — the contents rail's diamonds, **§17's own summary table on p215**, and
earlier lane briefs."*

**The conclusion is correct. Verified on the pages, one screen at a time.** Two things
supporting it are not.

**(a) NOT every entry stamps `REDRAWN AS`. Screen 03 stamps `No redraw.`**

> `03  Bill document` — `No redraw. This is the current state and there is nothing to build
> from it.` (p215)

Step 1's own coverage table says it located *"every `REDRAWN AS` / `No redraw` stamp"* — so
step 1 knew. **The consolidated record and the brief flattened two stamps into one**, and a
lane checking the claim finds a counter-example on the first entry it opens and then doubts
the whole warning. The accurate sentence is: **twelve of thirteen stamp `REDRAWN AS … Build
that one`; the thirteenth (03) stamps `No redraw`, which reaches the same place.**

**(b) p215's summary table is stale in a precise and DANGEROUS way — it is RIGHT that a
drawing exists and WRONG that it is to build.**

Read off p215, verbatim:

| Row | p215 says | Measured on the entry |
|---|---|---|
| `10 Past billing runs` ▎`CARRIES A DRAWING` | *"**Still has a drawing to build (`BIL-S1`)**: the panel saying the list arrives later is false in both halves that matter."* | **p229: `REDRAWN AS §07 screen 27 — Past billing runs. Build that one.`** and the drawing beneath is banded **`SUPERSEDED — This proposal is replaced by §07 screen 27. Kept as the earlier reading, not as work.`** |
| `13 Fix a bill` ▎`CARRIES A DRAWING` | *"Has its own remedy drawing. Reached from a bill, never from a run."* | **p236: `REDRAWN AS §06 screens 26–26.8 — the fix-a-bill wizard. Build that one.`** · p237 bands the remedy **`SUPERSEDED — This proposal is replaced by §06 screens 26–26.8.`** |
| `14 Pending queue` ▎`SUPERSEDED` | *"⚠ Its redraw is now §03's screen 20, Held queue … **Build 20, not this.**"* | **p241: `SUPERSEDED — This proposal is replaced by §03 screens 20–20.3.`** ✔ the table is right here |

⚠ **THE TRAP IS THAT `CARRIES A DRAWING` IS LITERALLY TRUE.** Screens 10 and 13 each carry a
full remedy drawing with a numbered legend, a carry-over table and reconciling element
arithmetic. A lane that reads p215, opens the entry and **finds exactly the drawing it was
promised** has its expectation confirmed and never reads the band four lines above it.
**"The table is stale" understates it: the table is true about the drawing and false about
the verb.**

**Their remedy titles and what each CLOSES, so nobody has to re-derive them:**

| Screen | Remedy title (superseded) | Closes |
|---|---|---|
| 10 | *Past billing runs — fill the tab with the panel that already exists* | `BIL-S1` · `DEF-2434` |
| 13 | *Fix a bill — make the approval path readable* | `BIL-S7` · `DEF-180` · `DEF-BIL-4633` |
| 14 | *Pending queue — page it in SQL before a T5 tenant opens it* | `BIL-S6` · `NFR-3` · `NFR-5` |

⚠ **Screen 10's remedy carries the shortest honest build in the module**, and it is worth
knowing before anybody scopes §07 screen 27: *"the component is already written and already
mounted. `PastRunsPanel` (`billRunResume.tsx:312-355`) renders on step 1 of the wizard. Three
of the nine new elements need no back-end work at all … **The smallest honest version of this
remedy is: mount the existing panel in the tab and rewrite the sentence.** Everything else
here is separable."* (p231)

## ⛔ CONTRADICTION 6 — the collapsed frames are NOT wholly absent; only the PICTURE is

Step 1: *"Five as-built frames are collapsed disclosures the PDF renders closed. **They are
not in the file.** No claim about how a §02 screen looks TODAY can be sourced from this
document."*

**Measured in §17, the disclosure line renders as `▶ As built today — kept because the
findings below point at it. Do not build this.` and EVERYTHING BELOW IT IS PRESENT** — the
full 14-row spec table, the field table and the red commentary. Seen on screen 10 (p231),
screen 13 (p238) and screen 14 (p242).

**So the missing thing is the DRAWING, not the description.** Screen 10's as-built is
described in detail with nothing drawn: *"For — Nothing, today. It is the one tab of six that
renders a refusal."* · *"Table controls — None; there is no table."* · *"Write surfaces —
NOTHING, all four."* · *"Walked — SEEN Rendered at 1440 …"* · *"Health — NOT SERVED, one
field, and the data for it exists."*

**Step 1's caution stands for anything visual and is too strong for everything else.** The
precise statement: **a claim about how a screen LOOKS today cannot be sourced from this
document; a claim about what it DOES, serves, refuses or breaches can be, from the spec and
field tables, which are in the file.**

## §17 · The thirteen screens, their stamps and their commitments

| # | Screen | Address · id | Stamp | Commitments on the heading |
|---|---|---|---|---|
| 03 | Bill document | `/:tenant/billing/bills/:invoiceId/document` · `BIL-05.document` · **no A1 id** | **`No redraw.`** | New build `S9 S79 S93` · Exists behind `S29` |
| 04 | Run bills · step 1 of 6 — pick the cycle | `/:tenant/billing/run` · `S31` · `BIL-02` | `REDRAWN AS §03 screen 16 Scope` | Blocked `S89` · New build `S9 S12 S84 S88` · Exists behind `S1 S30` |
| 05 | Run bills · step 2 of 6 — what was found | `/:tenant/billing/run` · `BILL_RUN_STEPS[1]`, phase `prepare` | `REDRAWN AS §03 screen 17 Check` | New build `S9 S12 S84 S91` · New read `S73` |
| 06 | Run bills · step 3 of 6 — the customers | `BILL_RUN_STEPS[2]` · sixteen case kinds | `REDRAWN AS §03 screen 17 Check` | New build `S9 S84` |
| 07 | Run bills · step 4 of 6 — the totals | `BILL_RUN_STEPS[3]`, phase `breaks` | `REDRAWN AS §03 screen 17 Check` | New build `S9 S84` · New read `S5` · Exists behind `S4` |
| 08 | Run bills · step 5 of 6 — sign off | `BILL_RUN_STEPS[4]`, phase `summary` | `REDRAWN AS §03 screen 18 Sign off` | New build `S9 S84` |
| 09 | Run bills · step 6 of 6 — send | `BILL_RUN_STEPS[5]`, phase `release` | `REDRAWN AS §03 screen 19 Send` | New build `S9 S71 S72 S84` |
| 10 | Past billing runs | `/:tenant/billing/history` · `BIL-01.history` · `S30` | `REDRAWN AS §07 screen 27` | New build `S9 S12 S76` · Exists behind `S1` |
| 11 | One-time bill | `/:tenant/billing/one-time` · `BIL-01.one-time` · `S30` | `REDRAWN AS §04 screens 21–24` | New build `S9 S12 S82 S86 S88` · Exists behind `S2` |
| 12 | Budget Bills | `/:tenant/billing/budget` · `BIL-01.budget` · `S30` | `REDRAWN AS §05 screens 25–25.4` | New build `S9 S11 S80 S81 S82` · Exists behind `S8 S10` |
| 13 | Fix a bill | `/:tenant/billing/fix` (also `/billing/fix?bill=<uuid>`) · `BIL-01.fix` · `S30` | `REDRAWN AS §06 screens 26–26.8` | New build `S9 S11 S16 S80 S81 S83` · Exists behind `S7 S8 S10` |
| 14 | Pending queue | `BIL-06` | `SUPERSEDED → §03 screens 20–20.3` | (remedy closes `BIL-S6` · `NFR-3` · `NFR-5`) |
| 15 | Print bills | `/:tenant/billing/print` · `BIL-07` · **no A1 id** | `REDRAWN AS §08 screens 28 and 28.1` | New build `S9` · Exists behind `S30` |

⚠ **Two of the thirteen have NO A1 screen id** — 03 (`no A1 id`) and 15 (`no A1 id`). That is
hard-won law 8's shape (*every screen needs a story*) in the A1 vocabulary, and step 1 did not
record it.

## §17 · Health, read off every spec table — the honest per-screen state

| Screen | Health row, verbatim |
|---|---|
| 03 | **SERVED**, with one caveat carried below |
| 04 | **NOT SERVED** — two of the Past-runs columns cannot be filled |
| 05 | **NOT SERVED** — the whole Plans & Rates tab denies a gather the run performs |
| 06 | **STUBBED** — no money on any row, by phase-1 design |
| 07 | **NOT SERVED** |
| 08 | **SERVED** |
| 09 | **SERVED** — and the absence on it is verified still true |
| 10 (as built) | **NOT SERVED** — one field, and the data for it exists |
| 11 | **SERVED** for every field drawn. This screen's problems are its copy and its form construction, not its data |
| 12 | **NOT SERVED** — eligibility is null by construction |
| 13 | **NOT SERVED** — the line-by-line list reads three keys the server does not send |
| 14 (as built) | **SERVED** for every field. This screen's problem is its shape at scale, not its data |
| 15 | **SERVED** |

## ⚠ §17 ADDS THREE UNPAGINATED BILLING ENDPOINTS TO `NFR-3`, AND ONE OF THEM IS STAMPED BY THE DOCUMENT ITSELF

Step 1 routed **one** billing `NFR-3` surface (`GET /billing/pending`, `DEF-BIL-5234`, *"a
fifth NFR-3 surface, and the first outside payments"*). §17's spec tables name **three more**,
each measured:

| Endpoint | What the page says | Where |
|---|---|---|
| `GET /billing/runs/{id}/findings` | *"unpaginated by declared design — `selectors.py:2978-2984`: 'NOT PAGINATED, deliberately, where every list endpoint in this API is… `PreparedRun` is not a queryset: it is one in-memory pass over the run's accounts.'"* ⚠ **and the cost is in the same comment: `At 1,000 accounts the pass is 66,053 SQL statements… a clerk pays for the whole pass on every refresh, and at that size waits about two minutes.`** `OQ-843` closed on *recompute*, so it is not cached. **Four unbounded arrays: `ready · blocked · decisions · silent`** | p221 |
| `GET /billing/runs/{id}/breaks` | *"**unbounded** — `selectors.py:2782-2785` `list(rows.order_by(...).values())`, no slice. Bounded only by accounts-per-run, itself capped at 25,000."* ▎**`NFR-3 BREACH`** — the document's own stamp | p225 |
| `GET /billing/pending` | *"takes **no `page`, no `per`, no `sort`** … materialises every unresolved exclusion for the tenant, then **sorts in Python at `:324`**, discarding its own SQL ordering. And `pending_count()` — the KPI number — **re-runs the same unbounded query, so the full set is built twice per request.**"* | p243–p244 |
| `GET /budget-billing` (client half) | *"**Sort and pagination — the server is compliant and the client cannot reach it**: `budget_api.py:286-292` orders in SQL and paginates, and the client sends no `page`, `per`, `sort` or `dir` and renders no pager. **Page 1 only, for ever.**"* | p235 |

⚠ **THE FOURTH IS A NEW SHAPE AND IT MATTERS**: the server is `NFR-3`-compliant and **the
CLIENT throws the compliance away**. Every `NFR-3` surface in `CLAUDE.md` is a server fault; a
grep of server code would report this one healthy. `BIL-S81` is the commitment
(*"A clerk can page, sort and filter every billing list, at any size"*, New build, minted from
*"§11 — B14 16, NFR-3"*).

⚠ **AND `/breaks` IS BOUNDED ONLY BY THE 25,000 CAP.** That is a direct argument the document
does not make and `BIL-S90` walks past: **removing the run cap without paginating `/breaks`
first removes the only bound on an unbounded response.** It is one more reason the PO's ruling
to keep the cap is the safe one, and it should be stated in that order if the cap is ever
revisited.

## ⛔ CONTRADICTION 7 — the flagship `BIL-S90` paragraph gets its own subtraction wrong

p244, verbatim, checked at scale 4 to be sure of the digits:

> *"At T5 — **40,000** accounts, the top of the current ICP — a run excluding 3% leaves about
> 1,200 unpaginated rows; and the run that produced them is itself capped at **25,000**
> accounts (`DEF-BIL-4224`, high, open), which is **13,000 short of the ICP**."*

**40,000 − 25,000 = 15,000.** The document is out by 2,000 in the one paragraph that argues
the cap is a problem, with both operands printed on the same line. Neither step 1 nor the
brief quotes this figure, so nothing is built on it — but **it is the third failure of this
document's own arithmetic** (after the two elevens and the `seventy-row index` / `thirty`
counts above), and it is in the flagship item. **Do not quote `13,000`.**

---

# §15 · p204–p205 — the chip audit, and the three same-day rulings

**These two pages are the most load-bearing thing in the 62, after the cards.** p203 (which
step 1 read) is the largest page of §15; p204 and p205 carry the rows that settle four figures
step 1 could not.

## ⛔ CONTRADICTION 8 — §15 says **24 rulings, 12 nowhere**; step 1 says **27 and 15**. BOTH ARE RIGHT, and here is why

p204, verbatim:

> *"**Twelve rulings existed nowhere but in this file.** The appendix had two ruling tables
> and neither asked the question. Grepped against the tree: **12 of the 24 rulings this
> document quotes exist in no file** — including the whole shape of §03, §06 and §08, the
> *per connection* rule that decides what a master account is charged, and the confirmation
> that approval moves the books. **The constraint that keeps the tree clean is the same one
> that puts them at risk.**"*

Three rows further down, the same page records **three more rulings arriving that day**. So:

    24 rulings · 12 ungreppable          ← §15, before the three same-day rulings
    + 3 rulings put and answered 2026-09-13
    = 27 rulings · 15 ungreppable        ← the appendix, which is what step 1 counted

**Step 1's 27/15 is the final figure and is the one to quote.** §15's 24/12 is a true earlier
reading of the same fact. **Neither is stale in the damaging sense** — but a lane grepping for
*"twelve rulings"* and a lane grepping for *"fifteen"* will each find a page and conclude the
other is wrong.

## ⚠ THE THREE RULINGS OF 2026-09-13, VERBATIM — and two of them WITHDREW a commitment

p204, under *"Three rulings arrived, and two commitments stopped being work — put to the
Product Owner, answered the same day, recorded here"*:

| # | PO, verbatim | Effect |
|---|---|---|
| 1 | *"We ahve to write everything in HTML artifact only Billing, as built - noting in repo"* | the twelve un-landed rulings become **an accepted risk with a ruling behind it**, and **`BIL-S101` is withdrawn** |
| 2 | *"you cannot change it here - it should be thorough process only"* | **a charge line is never editable on screen**, so **`BIL-S87` is withdrawn** and that absence is *"out of scope **with law behind it at last**"* |
| 3 | *"it is not hard coded; it should be based on setting"* | the late-fee floor becomes tenant configuration — ⚠ ***"the one ruling that CREATED work: `BIL-S102`"*** |

⚠ **THIS IS THE THIRD INDEPENDENT CONFIRMATION OF CONTRADICTION 3**, and the plainest: §15
calls the late-fee-floor ruling **the one ruling that created work**, while our brief and our
step-1 record call the floor *"untouched"*. **`BIL-S102` is ruled, unblocked and unbuilt.**

⚠ **AND IT NAMES BOTH WITHDRAWALS WITH THEIR REASONS**, which step 1 could not: `S101`
(rulings stay in the artifact) and `S87` (a charge line is never editable on screen). **`S87`
is the harder one to lose** — it is hard rule 4's territory, and the reason it is absent is a
PO ruling, not an oversight.

## ⛔ CONTRADICTION 9 — the commitment count is a TIME SERIES, and every figure in it is right

Step 1: *"⚠ **`BIL-S1 … all 101` against §14's 'Of the 100 here'.** One of the two is off by
one; both are the document's own figures, one page apart. **Neither is safe to quote.**"*

**Reconstructed from four pages, all of which now have a number on them:**

| Moment | Count | Where it is printed |
|---|---|---|
| the register proper, `S1`–`S70` | **70** | p172 — *"a seventy-row index"* · p194's group heading |
| + 19 minted in this pass (`S71`–`S89`) | **89** | **p205 — *"Eighty-nine specifications — nineteen of them minted in this pass"*** |
| + 12 minted in the commitment pass (`S90`–`S101`) | **101** | **p204 — *"101 commitments in register order"*** · §12's *"all 101"* |
| + 1 minted after the ruling (`S102`) | **102 ids** | p198's group heading |
| − 2 withdrawn (`S101`, `S87`) | **100 cards** | p172's figure band · counted here off the index |

**Every one of the four counts is correct at the moment it was written.** The safe statement is
not *"neither is safe to quote"* — it is **"quote 100, and know that 89 and 101 are earlier
readings of the same register."** ⚠ **The one genuinely stale figure is p172's ID-RANGE
sentence (`BIL-S1 … BIL-S30`)**, which was never a count at all.

## ⚠ Other rows on p204–p205 worth carrying, each measured by the document

| Finding | What it says |
|---|---|
| **A defect row was being read as a plan** | *"51 defect ids are cited here; **9 open ones had no commitment at all**. A defect records that somebody noticed — it undertakes nothing. `BIL-S90`–`BIL-S98` now name that work."* |
| **B14 rule 31's two breaches need NO NEW READ** | *"screen 10 serves twelve fields and shows none of them; screens 12 and 13 print a raw UUID **while the read beside them already serves `account_no` and `case_no`**. So B14 31's two breaches need **no new read**, which the violation table did not say."* — ⚠ this makes `BIL-S10` and `BIL-S80`'s UUID half a rendering fix, not a read |
| **Three numbers this document repeated were wrong** | *"89 open billing defects"* → the register holds **228 billing rows, 86 open** · *"39 rules"* for B14 → **30 rules**, 39 the highest number, *"three sources gave three numbers and none was the count"* · `assess_late_fee` *"has no production caller"* → **it has exactly one** |
| **Every route has a door — but two hang off one button** | *"the pending queue and Print bills each hang off exactly one button on one screen, and **neither is in `SIDEBAR_DESTINATIONS`**, so no reachability test covers the two screens that carry **the only working delivery channel and the only view of unbilled accounts**"* |
| **Four things it expected and did not find** | no unreachable screens · **no dead links** · **no cross-module write** · **no seam returns a raw queryset — ten seam files, 94 functions, zero** |
| **It counted B14's rot itself** | *"`CLAUDE.md` says B14 holds thirty-eight rules; it holds thirty-nine… **This is the sixth time that pointer has lagged its target**, and `CLAUDE.md`'s own text predicts it."* **Not repaired, because this pass writes nothing to the repo** |
| **It knows about the five-digit ceiling** | *"Screen numbering has no gap… If a later pass adds a screen, it appends — nothing is renumbered, **for the same reason `OQ-291` is not `OQ-00291`**"* |
| **The worked figure behind one of its own judgments** | *"the pre-bill check running in a worker (**137 ms × 25,000 = 57 minutes against a 60-second wall**, so the arithmetic decided it, not a preference)"* — ✔ the arithmetic checks: 137 ms × 25,000 = 3,425 s = **57.1 min** |
| **How three stale sources were made** | *"**My own generator overwrote a table and left a stale copy of another.** The §12 regenerator targeted *the first table in the section*. Two tables were added above the build index in the previous pass, so it overwrote the cost ranking and left a **stale duplicate build index still naming two withdrawn commitments.** Found by the dangling-link check, not by reading."* ⚠ **This is the origin of step 1's "three sources say otherwise and all three are stale"** — a generator that assumed its target was first |

## ⛔ CONTRADICTION 10 — the document's ONE remaining open question was answered on 2026-09-14, and nobody joined it up

p204, verbatim:

> *"**A question was answered in half, and only the answered half was recorded.** The floor
> ruling settles that it is a **setting**. It does not settle **what the setting is measured
> against** — the part of the bill that is actually ageing, or the whole bill. **On a $60 bill
> with $40 disputed those two readings differ by the entire fee.** Taking the ruling as
> covering both halves would have been the cheapest mistake available, so the second half is
> written up as still open rather than assumed."*

**That second half is the PO ruling of 2026-09-14 that step 1 recorded** — *the late-fee floor
tests the AGEING PORTION, not the whole bill.*

**So the two halves are now both answered and they belong together:**

* **2026-09-13** — the floor is a **tenant setting**, not a constant. → `BIL-S102`, unbuilt.
* **2026-09-14** — the setting is measured against the **ageing portion**. → already true in
  code at `late_fee.py:612`; ratifies working behaviour.

⚠ **Step 1 read the second ruling as standing alone and concluded the floor was untouched.
Read together they are one complete instruction: make it a setting, and test it against the
ageing portion.** Building only the second half leaves `BIL-S102` unbuilt; building only the
first half re-opens the $60/$40 question the PO has now closed. **Whoever picks this up must
build both.**

---

# ⛔ CONTRADICTION 11 — p004 is not a contents page

This lane's scope table lists **`p004` — "the last contents page"**. **It is not.** p004 is the
tail of **§01's picker/authority table** — *"What these drawings are drawn to"* — with rows for
`+ Filter`, `Rows per page`, the bulk-run decision table, `ONE-TIME BILLS, §04`, `BUDGET BILLS,
§05`, `FIX A BILL, §06` and `PRINT BILLS, §08`. Step 1's own map is right (*"the contents rail
on pages 1–3"*); the scope table is the thing that was wrong.

**Three rows on it are worth having anyway, because each is the source of a commitment:**

* *"**Reason** — ⚠ **Meant to be tenant-extensible reference data, and that table is not
  built.** The thirteen seeded reasons are a map in code, and a reason it cannot class is
  **refused rather than defaulted**"* → this is exactly `BIL-S61`'s *waits on*, from the other
  side, and it is the second surface of `DEF-BIL-5233`.
* *"**Manifest format** — ⚠ The format registry, which holds **exactly one entry** today. A
  second is a registration, not a change to the print set"* → `BIL-S64`'s *"Exactly one
  manifest format is registered."*
* *"**Bill layout** — ⚠ The bill-template chain. **The template table does not exist**, so
  *current* is the caller's fact until it does"* → the missing table behind `BIL-S93` and
  `BIL-S15`.
* And the rule the table exists to state: *"**A picker whose source is a constant says so**,
  because a constant is a code change and a lookup is a settings change."*

---

# 2 · DOES 91 RECONCILE? **NO — and here are both numbers**

## The taxonomy, which p204 supplies and which makes the question answerable at all

> p204: *"Every drawing now opens with **`AS-BUILT`** (with the date and commit it was measured
> at), **`AS-BUILT, FROM CODE`** (with the reason it was never rendered) or **`REDESIGN`**
> (with what the product ships instead, and `NEVER BUILT`). **70 of the 91 are redesigns that
> have never been built, which no single figure previously admitted.**"*

So the cover's **91 = 70 REDESIGN + 21 as-built**, and §12's component table splits the 21 as
**9 `AS-BUILT` measured + 12 `AS-BUILT, FROM CODE`**.

## What §17's thirteen provenance bands actually say — counted, one entry at a time

| Band | Screens | Count |
|---|---|---|
| `AS-BUILT measured in Chromium 1194 at 1440×1100 on 2026-09-11, at commit a1d37a68` | 10, 11, 12 | **3** |
| `AS-BUILT, FROM CODE … never rendered` | 03, 04, 05, 06, 07, 08, 09, 13, 14, 15 | **10** |
| | | **13** |

**That is the whole of §17 and it is exactly one band per screen.** Three of the thirteen
(10, 13, 14) additionally carry a **superseded REMEDY drawing** rendered over the as-built
base, and a **collapsed `▶ As built today`** disclosure.

## The reconciliation, with both numbers

| Source | Drawings | Counted by |
|---|---|---|
| §02 | **8**, all REDESIGN | step 1, page by page over p005–p028 |
| §02, collapsed as-built frames | **5**, NOT RENDERED | step 1 |
| §03–§08 | **57 entries**, 57 redesign, 0 as-built — ⚠ *entries, not drawings* | step 1 |
| §17 | **13 rendered** + 3 superseded remedy overlays + 3 collapsed disclosures | **this lane, every entry opened** |
| **Best case, assuming one drawing per §03–§08 entry** | **8 + 57 + 13 = 78 rendered**, or **83** counting the five collapsed §02 frames | |
| **The cover claims** | **91** | |

# **91 IS NOT REACHABLE. The gap is 13 drawings (8 if the five collapsed §02 frames are counted).**

**And the as-built half fails on its own, which is the sharper test**, because as-built
drawings are countable by their provenance band:

* The cover needs **21** as-built — **9 measured + 12 from code**.
* **§17 carries 13** — 3 measured + 10 from code.
* Step 1 measured **§02 as 8 drawings, ALL REDESIGN** and **§03–§08 as 57 redesign, ZERO
  as-built**.
* **If step 1's two counts are right, there are no as-built drawings outside §17 at all**, and
  the rendered as-built total is **13 against a claimed 21** — with the five collapsed §02
  frames added, **18 against 21**. **Three as-built drawings are unaccounted for by either
  pass.**

**Two assumptions could close part of the gap, and neither has been checked by anybody:**

1. **§03–§08's 57 are ENTRIES.** If some entry carries two drawings — as §02's entry 01 does
   (*"`TWO REVISIONS`… an AS-BUILT drawing of 2026-09-11 and a REDESIGN that has never been
   built"*) — the redesign side rises. **57 entries would have to average 1.23 drawings to
   reach 70 redesigns**, which is plausible and is a page-by-page count nobody has done.
2. **The appendices.** §12 recorded a `BUILD THIS` band *"1 in an appendix"*, so appendix pages
   carry at least one drawing, and neither pass has counted them.

**What to do with this:** treat **91 as the document's claim, never as a checked figure**, in
exactly the way B14 rule 37 treats a drawn number. The pages support **78 rendered drawings**
and **13 rendered as-built**; everything above that is an unverified claim of the cover. ⚠ And
this is now the **fourth** failure of this document's own arithmetic, after the two elevens,
the `seventy-row index` / *"sixteen of the thirty"* pair, and p244's `13,000`.

---

# §14 · THE CARD→PAGE INDEX — open the card, do not infer it

**Built by reading p177–p201 in sequence. The page is where the card OPENS**; a long card runs
onto the next page. **Nothing in this repo can give a lane a card's text — only the image can.**

| Page | Cards opening on it |
|---|---|
| p177 | `S1` (under the heading *The cards in full*) |
| p178 | `S2` `S3` `S4` `S5` `S6` |
| p179 | `S7` `S8` `S9` `S10` |
| p180 | `S11` `S12` `S13` `S14` `S15` |
| p181 | `S16` `S17` `S18` `S19` |
| p182 | `S20` `S21` `S22` `S23` |
| p183 | `S24` `S25` `S26` `S27` |
| p184 | `S28` `S29` `S30` · *the group's closing note* · `S31` |
| p185 | `S32` `S33` `S34` `S35` `S36` |
| p186 | `S37` `S38` `S39` `S40` |
| p187 | `S41` `S42` `S43` `S44` |
| p188 | `S45` `S46` `S47` `S48` |
| p189 | `S49` `S50` `S51` `S52` |
| p190 | `S53` `S54` `S55` `S56` |
| p191 | `S57` `S58` `S59` `S60` |
| p192 | `S61` `S62` `S63` |
| p193 | `S64` `S65` `S66` `S67` |
| p194 | `S68` `S69` `S70` · **heading *Minted in this pass — nineteen*** · `S71` |
| p195 | `S72` `S73` `S74` `S75` |
| p196 | `S76` `S77` `S78` `S79` `S80` |
| p197 | `S81` `S82` `S83` `S84` |
| p198 | `S85` `S86` `S88` `S89` · **heading *Minted after the ruling — one*** |
| p199 | `S102` · **heading *Minted in the commitment pass — twelve*** · `S90` `S91` `S92` |
| p200 | `S93` `S94` `S95` `S96` |
| p201 | `S97` `S98` `S99` `S100` — **§14 ends here** |

**`S87` and `S101` have no card.** The register goes `S86 → S88` and `S100 → S102`.

## Cards carrying a WORKED MONEY FIGURE — B14 rule 37 applies to every one of them

⚠ **Each figure below is an ILLUSTRATION in a commitment card. Do not assert one in a test and
do not seed a fixture from one.** They are listed so a lane knows which cards have money in
them and must be read with the rule in mind.

| Card | The figure, as drawn |
|---|---|
| `S1` | `BR-2608-0042 · 08-A · 01 Aug – 31 Aug 2026 · 1,263 bills · $338,904.00 · Dana Reyes · Issued` |
| `S34` | `Hillcrest Apartments · covers 12 units`, and its **$69.60** never presented as a single-unit bill |
| `S39` | **$64.00** on four lines (two base charges of $12.00, two ladders of $20.00) · **$70.17** = $69.60 + a 2.00% city water fee of **$0.57** on the water connection alone, *not $1.39 on the whole bill* ⚠ **both collisions** |
| `S42` | `198 will change · 33 cannot · +$11,842.60` on a 25,000-account run |
| `S43` | `1,273 regular · 11 master covering 229 areas` · `charges − credits = net` · `$128,402.55 − $96,318.20 = $32,084.35` · **24 accounts, about $6,240, not invoiced** |
| `S44` | `In arrears 312 · $84,204.60 owed` |
| `S49` | *Estimate from history* on 100263 records **8.1 kgal** and bills **$51.30**; in bulk `Working out 231 estimates… 140 done` |
| `S52` | 18 kgal as one period prices the usage at **$104.50** |
| `S56` | $289.40 of charges, a $150.00 deposit, **−$150.00 and −$3.50 as separate lines, $135.90 still due** |
| `S64` / `S70` | cycle **09-A**, `404 will print · 8 held · 412 in the period`, *about 5 seconds*, *~2,424 pages* |
| `S67` | `SR-4468` reads **$112.00 shown against $119.00 now** |
| `S68` | a $289.40 bill paid in full, corrected to $190.16: **they paid $289.40 → comes off the old bill $289.40 → meets the new bill $190.16 → $99.24 to their credit**, with *"this is not a refund"* stated |
| `S69` | part-paid June **$180.00 moves across and $86.20 still to pay**; the panel separates **+$159.80 (the correction)** from **$709.40 (still to pay)** |

## The cards that carry a RULING inside them — read these before quoting a rule

| Card | Ruling it names |
|---|---|
| `S39` | *"Both halves ruled **2026-09-11** — per connection … **Reverses the bill-level tax ruling of 2026-08-11 for master accounts**; the supersession is written down first."* ⚠ **NOT BUILDABLE — with the PO** |
| `S48` | *"**Ruled 2026-09-12** — the selection is a snapshot and the snapshot wins, so the client holds the ids rather than the server re-resolving the set. `Select all` refuses above 10,000 rows in one chip."* |
| `S49` | *"Per the PO ruling of **2026-09-12** the screen orchestrates and displays, with a progress state; **the estimate rule stays on the server** so two paths cannot produce two figures."* |
| `S56` | *"the transfer target is **resolved from the data, never supplied** — your ruling of **2026-08-24**, *'master account gets debt - if sub accoun tis unable to pay it ; even aftr deposite settlement'*"* |
| `S102` | *"A Product Owner ruling of **2026-09-13**, verbatim: *'Yes, if it is limit set in setting then - it is not hard coded; it should be based on setting'*"* |

## The six BLOCKED cards, and what each is actually blocked ON

**The chip means *waits on a ruling, or on something this module does not own* — it never means
uncertainty.** Three of the six wait on a ruling; three do not.

| Card | Blocked on | A ruling? |
|---|---|---|
| `S22` | *"Not billing's to fix"* — metering's audit viewer | **no** — another module |
| `S37` | *"**A ruling.** No status means *billable, but hold the bill* — a vacation hold still bills the standing charges. **Whether a standing hold may exist, and whether the review date is mandatory, are yours to answer.**"* | **YES — open, and it is put to the PO in the card** |
| `S56` | no `settlements` table; `premises.owner_customer_id` **measured absent** | **no** — a table and a column |
| `S61` | the reason→class map is **PROPOSED, not ratified**; the tenant-extensible reason table **has no class column and is not built** | **half** — a ratification plus a table |
| `S75` | `OQ-237` — *"and on no account recording which plan it is on"* | **YES — an existing OQ** |
| `S89` | *"a B14 amendment"* — B14 rule 7 must name the style world the product uses | **YES — a B14 amendment** |

⚠ **`S37` is the one BLOCKED card that puts a genuinely new question to the PO and that is
recorded nowhere in our registers.** *Whether a standing hold may exist, and whether the review
date is mandatory.* It is not among step 1's 27 rulings (those are answers); it is a question,
and §16's *Still open* holds only one. **Whoever scopes §03's screens 20.2/20.3 must raise it.**

## The six NEW READ cards — the reads that must be published before a screen can be built

| Card | The read | Owner |
|---|---|---|
| `S5` | `BR-BIL-054`'s unusually-large list, *"which has never existed"* (`DEF-2855`, high, open) | billing |
| `S17` | one read behind the bill header | billing |
| `S19` | whether the bill reached the customer — *"nothing to move it"* | billing |
| `S46` | **one aggregate count of a cycle's metering inventory — owned by METERING, not billing** | **metering** |
| `S73` | the base charge and schedule name the run **already gathers** but does not put on the wire (`gather.py:699-705`) | billing → rating |
| `S74` | the plan's budget-billing flag through the seam (`OQ-237`'s READ half, *already served at `rating/selectors.py:420`*) | billing → rating |

⚠ **`S46` is the only cross-module ask in the whole register** — and hard rule *cross-module
writes are forbidden* means it cannot be built inside billing. **It is a metering story.**

⚠ **`S73` and `S74` are both "the data exists and is not on the wire", not "the data does not
exist"** — `S73`'s own words are *"gathered by `gather.py` and absent from the findings
payload; **the cell denies the gather**"*. Two of the six New reads are therefore cheaper than
the chip suggests.

---

# COVERAGE — counted, and the page arithmetic corrected

## The source, derived and hashed

Per the PO instruction of this session, the PDF was **derived from the default branch by this
lane**, not taken from a scratchpad copy:

    git show "origin/claude/confirm-understanding-3ktufc:05-prototype/04 Billing, As Built.pdf"
    sha256  137a2a48c0398c39897f49aafa0bbb9c44ff21d6258eed78cd7558e6cc200971   ✔ matches

Every page was then **re-rendered from that derived file** and compared byte-for-byte against
the renders already opened: **identical on all nine spot-checked pages.** Nothing read before
the derivation needed re-reading.

## Pages

| | |
|---|---|
| Pages this lane was sent at | **62** (249 − the 187 step 1 opened) |
| Pages the nine named ranges actually contain | **59** |
| **Pages opened as images by this lane** | **64** — all 59, plus p172, p179, p215, p229 and p236 re-opened to check step-1 claims |
| Re-rendered at scale 4 to be certain of digits | p229, p244 |

## ⛔ CONTRADICTION 12 — the scope table's own arithmetic is off by three, and one page in it was already read

**The nine ranges sum to 59, not 62.** `p004` + `p173–178` (6) + `p180–201` (22) + `p204–205`
(2) + `p216–228` (13) + `p230–235` (6) + `p237–239` (3) + `p241–245` (5) + `p247` (1) = **59**.
**Three of the 62 unopened pages are named by no range** and remain unopened by anybody.

**And `p217` is INSIDE the assigned range while step 1's own coverage list records it as
opened.** Opening it again cost nothing and was worth it — p217 is where §17's per-entry
anatomy and the `Group B · Producing bills` heading are — but it means the true unopened count
in that range was 12, not 13.

⚠ **Step 1's §09–§17 coverage line is also wrong in its own count.** It reads *"Pages opened as
images: **39** of the 99 in §09–§17 — p151–p172 (all 22), p179, p202, p203, p206–p215 (all 10),
p217, p229, p236, p240, p246, p248, p249."* **That list sums to 42**, not 39: 22 + 1 + 1 + 1 +
10 + 7 = 42. **The list is the reliable half; the number is not.**

## What is now fully covered, and what still is not

| Section | State after this lane |
|---|---|
| **§14 · Specification register, p172–p201** | ✔ **COMPLETE.** Every index row and **all 100 card bodies** read as images |
| **§15 · p202–p206** | ✔ **COMPLETE** across the two passes (p202–203 step 1, p204–205 here, p206 step 1) |
| **§17 · p215–p249** | ✔ **COMPLETE** across the two passes (p240 and p246 by step 1, the rest here) |
| §01 · p004 | ✔ opened — and it is not the contents page the scope table called it |
| **Three pages of the 62 that no range named** | ✘ **still unopened by anybody.** They are not in §14, §15 or §17, so nothing above depends on them |
| §02 (p005–p028) and §03–§08 | unchanged from step 1 — **and the drawing count above cannot be closed without a page-by-page pass over §03–§08** |

## Commitments

| | |
|---|---|
| Commitments in the register | **100** (ids `S1`–`S102`, less `S87` and `S101`) |
| **Index rows captured** — id · title · waits-on · screens · chip | **100 of 100** |
| **Card bodies read as images** | **100 of 100** |
| **Cards written out in full here** (chip · waits on · screens · done looks like · minted from) | **the nine that cost the most**, plus `S39`, `S77`, `S87`/`S101`'s withdrawals, and every Blocked and New-read card's *waits on* |
| Cards left to the page index | the remainder — **open the page; do not infer the card** |

---

# THE TWELVE CONTRADICTIONS, IN ONE PLACE

**Ranked by what it costs a lane that does not know.**

| # | Against | The correction | Cost if unknown |
|---|---|---|---|
| **3** | brief + step 1 | **`BIL-S102` is RULED (2026-09-13) to move the late-fee floor into tenant settings.** Both of ours call it *"untouched, still a module constant"* — which is true of the code and false of the commitment. §15 calls it *"the one ruling that created work"* | **a ruled money change is left unbuilt** |
| **10** | step 1 | the 2026-09-14 ageing-portion ruling **is the second half of the same question**, which the document left open. The two rulings are one instruction | **half the instruction is built** |
| **4** | step 1 | **both NOT-BUILDABLE collisions are inside ONE card, `BIL-S39`, chipped `New build` / `waits on Nothing`** | **a lane scoping by chip reverses a signed rule and frozen `GT-17`** |
| **5** | brief + step 1 | §17's warning is right; its evidence is wrong twice — screen 03 stamps `No redraw`, and p215 is **true that 10 and 13 carry a drawing and false that it is to build** | **the warning gets disbelieved at the first counter-example** |
| **1** | step 1 | §14's cards start on **p177**, not p180. p177–178 carry `S1`–`S6`. **100 card bodies were unread, not 94** | the highest-priority card sat inside a range marked *nothing material* |
| **6** | step 1 | the collapsed frames hide **only the picture** — spec tables and field tables are all present | a whole evidence layer is written off |
| **9** | step 1 | the commitment count is a **time series** — 70 → 89 → 101 → 102 minted → **100 live**. Every figure is right at its moment | *"neither is safe to quote"* becomes *"quote 100"* |
| **8** | step 1 | §15's **24/12** and the appendix's **27/15** differ by the three rulings of 2026-09-13. **27/15 is final** | two lanes each think the other is wrong |
| **2** | step 1 | both withdrawn commitments named — **`S87`** (a charge line is never editable on screen) and **`S101`** (rulings stay in the artifact), each with the PO words that withdrew it | `S87`'s absence looks like an oversight |
| **7** | the document | p244: 25,000 is *"**13,000** short"* of 40,000. **It is 15,000** | a wrong figure in the flagship item |
| **11** | the scope table | **p004 is §01's picker table, not a contents page** | — |
| **12** | the scope table + step 1 | the nine ranges sum to **59, not 62**; `p217` was already read; step 1's *"39 of the 99"* list sums to **42** | three pages still unopened |

**Two more, recorded in the body above and not contradictions of anybody:** §17 names **three
more unpaginated billing endpoints** beyond step 1's one — including a **new shape where the
server is `NFR-3`-compliant and the client discards it** — and **`/breaks` is bounded only by
the 25,000 cap**, which is an argument for the PO's ruling that nobody has made.

**And one open question nobody has raised:** `BIL-S37` asks the PO, in its own text, *whether a
standing hold may exist, and whether the review date is mandatory.* It is in none of our
registers.

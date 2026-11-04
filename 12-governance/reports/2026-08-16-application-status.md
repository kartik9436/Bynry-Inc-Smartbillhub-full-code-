# Whole-application status — 2026-08-16

Every figure below was **measured today**, after five build lanes finished, not
carried forward from an earlier report. Each table names the command that
produced it; re-run any of them to check.

> ⚠ **The release column is an inference, and it is the only inferred thing here.**
> `04-docs/02-decisions/12-engineering-plan.md` §209–212 defines R1–R4 by
> *capability*, not by module, and three modules genuinely span releases:
> **metering** (meter setup is R1, reads and estimation are R2), **rating**
> (Plans & Rates is R1, the pricing engine is R2's critical path) and
> **notifications** (the queue is R2 by PO ruling, delivery is R4). Where a
> module spans, it is counted once, in the release its *bulk* serves. Story
> counts are exact; the release attribution is a reading.

---

## 1 · The whole application in one table

| | Measured |
|---|---|
| Modules | **14** |
| User stories | **258** |
| Stories with code | **190** (73%) |
| Stories built — API half **and** screen half | **141** (55%) |
| Stories proved — a test or browser check runs them | **71** (28%) |
| Screens declared in the inventory | **77** |
| Screen components in the frontend | **85** |
| HTTP routes mounted | **162** |
| Backend engine lines | **125,419** |
| Declared test cases done | **145 / 164** |
| End-to-end journeys with a spec that executes them | **113 / 290** |

`python3 10-scripts/module_report.py` · `10-scripts/r2_status.py` · `10-scripts/screen_report.py`

## 2 · Health — what is actually green

| Check | Result |
|---|---|
| **Merge-blocking gates** | **27 of 27 pass · 0 fail** |
| **Golden money tests** (the frozen finance figures) | **33 of 33 · 0 fail** |
| **Backend test suite** | **2,938 passed · 12 failed · 169 skipped** |
| **Frontend test suite** | **1,189 passed · 2 failed · 184 todo** (83 files) |
| Open **critical** defects | **2** |
| Open defects, all severities | **42** of 167 recorded |
| Questions awaiting the Product Owner | **34** of 220 (186 closed) |
| Stories with code no human can reach | **18** |

The 12 backend failures are **three causes, not twelve problems**: ten belong to
the sample-data seeder (below), one is a bill-layout test, and one — the stale
API contract snapshot — was fixed today and is green.

The 2 frontend failures are named, not a mystery: `PaymentsPage.test.tsx`
(US-PAY-004 — the S33 collections tab the sidebar declares) and
`tenantPath.test.tsx` (a foreign tenant's path renders an ordinary 404). Both
predate today's lanes and both were reported by two independent lanes as not
theirs.

## 3 · Release by release

### R1 — "Set up your utility"
*Sign up · provision · sign in · users and roles · all Settings · Plans & Rates ·
premises and units · routes and cycles · meters with lifecycle and bulk import ·
audit viewer.*

| Module | Stories | With code | Built | Proved | Unreachable |
|---|---|---|---|---|---|
| platform-shell | 19 | 14 | 14 | 4 | — |
| tenancy | 21 | 16 | 12 | 5 | — |
| identity | 11 | 9 | 4 | 2 | — |
| audit | 9 | 7 | 3 | 1 | 1 |
| rating | 19 | 15 | 11 | 3 | 4 |
| metering | 20 | 19 | 16 | 10 | 1 |
| assets | 12 | 9 | 8 | 5 | — |
| **R1 total** | **111** | **89** | **68** | **30** | **6** |

**Deployed and in use.** This is the release running in production today.

### R2 — "Bill"
*Open accounts · move customers in · import and validate reads with flags and
estimation · run the full bill-run wizard · issue real bills at the frozen
figures · render bill documents · see bills on the account.*

| Module | Stories | With code | Built | Proved | Unreachable |
|---|---|---|---|---|---|
| customers | 23 | 18 | 14 | 12 | — |
| billing | 31 | 31 | 20 | 10 | 5 |
| **R2 total** | **54** | **49** | **34** | **22** | **5** |

**A bill has been issued by clicking**, on a stack booted from an empty
database — `BL-2608-000006`, `$70.90`, with its locked printed copy and a
balanced entry in the books, then read back out of the database.

**What remains is one coherent block**, not five odds and ends: S30's
*one-time bill* tab — first bill, final bill, ad-hoc single, back-bill,
penalty. All five engines are complete and tested; none has an endpoint or a
screen.

### R3 — "Collect & close the books"
*Payments and allocation · NSF, reversals, refunds · collections and payment
plans · budget billing · deposit batches and bank reconciliation · the ledger
with dimensions · manual journal entries · tax remittance · month-end close ·
accounting export · all reports and the dashboard.*

| Module | Stories | With code | Built | Proved | Unreachable |
|---|---|---|---|---|---|
| payments | 25 | 21 | 17 | 7 | 2 |
| ledger | 21 | 19 | 15 | 9 | 2 |
| reports | 19 | 1 | 1 | 0 | 1 |
| **R3 total** | **65** | **41** | **33** | **16** | **5** |

**Far further along than a "not started" release.** Payments, the ledger, the
finance tabs, deposit batches, bank reconciliation, month-close and the
supplier-cost side are built and reachable. **Reports is the hole** — 1 story of
19 has any code, and the report library is deliberately unbuilt because there is
no report catalogue behind it to draw.

### R4 — "Switch on the world"
*Email activation for bills, receipts, notices and scheduled reports · payment
rails — real autopay and card refunds · the v1.1 unlocks.*

| Module | Stories | With code | Built | Proved | Unreachable |
|---|---|---|---|---|---|
| notifications | 16 | 11 | 6 | 3 | 2 |
| integrations | 12 | 0 | 0 | 0 | — |
| **R4 total** | **28** | **11** | **6** | **3** | **2** |

**Not started, by decision rather than by omission.** The PO ruled R2 queues
messages and sends none: *"I already confirm it before it Queue them"*. The
dispatcher and the provider seam are counted as unreachable precisely because
they have code and no route — that is the one question the count answers, and
lowering it to express a ruling would make the register disagree with the tree.

---

## 4 · The four things that block a person driving the product

Ranked by what they cost, not by how hard they are.

| # | What | Effect |
|---|---|---|
| 1 | **Seeded bills never issue** — 95 load as drafts | No payments, no journal entries. Four of the eight demo tasks are impossible |
| 2 | **A plan with any non-metered service cannot be billed at all** | Trash (flat monthly) and sewer (% of water) will never have a meter reading, and the run refuses every account waiting for one |
| 3 | **No tenant has ever had a notice template** | Every disconnection notice and dunning letter is refused rather than sent |
| 4 | **Ten sample-data tests are red** | The reading seeder handles warning rows and not error rows, so its batch will not commit under test |

Items 1, 2 and 3 are recorded as defects with measured evidence. **None is a
rebuild** — the engine issues bills correctly when driven from the screen, as
proved in a browser.

## 5 · What waits on the Product Owner

**34 questions**, of which four matter more than the rest because code is
refusing by name until they are answered:

- **The base charge can be typed in two places** — on the plan and on the rate
  schedule. When they disagree, that account's bill refuses rather than picking.
- **Sewer as a percentage of water**: is the percentage taken on the water
  charge before or after rounding?
- **A discounted Senior plan** is asked for and no signed document says the
  discount. 10% and 20% differ by about **$9 a month** on an ordinary bill.
- **May staff cancel a payment plan**, and what does it become if they do?

Plus the notice-letter wording: the specs give sentences for four of fourteen
kinds, and the rest is what a customer reads.

## 6 · Three numbers to read carefully

**"Built" is 55%, and that is not "55% of the product exists."** It means both
halves of a story — its endpoint and its screen — are marked complete. The
engine work is much further along than that: **125,419 lines** of tested backend
against **77** screens. R2's central lesson was 66 stories with a finished engine
and no screen, every deferral honest and nothing adding them up.

**"Proved" is 28%, and it is the number to distrust least.** It counts stories a
test or a browser check actually executes. It is low, and it is honest.

**"Journeys 113 of 290" does not mean 177 failed.** It means a spec exists that
executes 113 of them. The rest have no spec yet.

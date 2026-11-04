# J-PARTNER-PULL — a partner pulls a month of the books and ties every row to a document

---
id: J-PARTNER-PULL
tier: 2
rules: [BR-LED-021, BR-LED-003, BR-INT-044, BR-INT-054, BR-TEN-003, BR-TEN-013]
stories: [US-LED-015, US-INT-013]
questions: [OQ-INT-6620, OQ-INT-12393]
---

**Intent.** Phase 5 of the Finance blueprint has one *Done when* and this journey
is it: **a partner can tie every row we send back to a document the utility can
find.** Until 2026-09-24 that was unanswerable — the feed identified an entry by
nothing at all and the reference on a row was our own storage key — so the
finance officer who fields a reconciliation email had no way to answer *which
entry is this?*

⚠ **THIS JOURNEY HAS NO SCREEN AND THAT IS NOT AN OVERSIGHT.** Phase 5's own
self-assessment on p018 says so plainly: *"This phase is the weakest of the six
on direct clerk value and that is said plainly; its user is the finance officer
who currently fields reconciliation emails they cannot resolve."* What is walked
here is an API contract between two companies. The clerk-facing half of the
phase is `6·1 Close` (`P5.9`/`P5.10`), which has its own walkthrough.

**Fixture.** Tenant `brazosbend` · an Aclarian-shaped partner key with the
`ledger` scope · a month holding one of each thing a partner actually meets: a
BILL (one debit against several credits, one of them tax), a PAYMENT, and an
OPENING BALANCE, which has no document behind it at all. The last of those is
the row a lane is most tempted to make tidy, and it must come back null.

---

## The walk

| # | Action | Handoff contract (what this step leaves) | Assertions | Rule |
|---|---|---|---|---|
| 1 | `GET /api/{utility}/partner/v1/ledger` with **no window** | Nothing. The read is refused before any row is selected | **400 `DATE_RANGE_REQUIRED`**, six words. A month at the top of T5 is ~200,000 journal lines and an unbounded pull is the paging trap with nothing to bound it | — |
| 2 | The same address with a **bad key**, or a key whose scope omits `ledger` | Nothing, and the refusal is INDISTINGUISHABLE from the other four | One refusal, **404**, padded to the floor. ⚠ A BLANK scope grants NOTHING — stricter than the blueprint's *"leave blank for everything the key allows"*, under hard-won law 3 | **BR-INT-044** |
| 3 | `?start_date=2026-09-01&end_date=2026-09-30`, page 1 | A page of ENTRIES, with `total_records` (partner ROWS) and `total_entries` (the paged unit) | The two totals **differ**, because a bill becomes several rows. A partner paging on `total_records` would ask for a page that does not exist and conclude rows are missing | — |
| 4 | Walk every page to the end | Every row the walk received, counted | The count equals `total_records` **and the walk never consulted it to decide how far to go**. Every `transactionId` is distinct: a repeated one means a row came twice, and the row that came twice is a row that never came at all | — |
| 5 | **The row that matters** — group the walk's rows by the entry they came from | — | **No entry appears on two pages.** Pairing a debit with its credit reads a WHOLE entry; page on ROWS instead and a three-row bill straddling a boundary is two half-postings, and a partner's month is out by the difference with nothing on either side raising | hard rule 5 |
| 6 | Read any row's `id` and `transactionId` | The entry's `JE-` number, and that number plus the row's ordinal | `JE-MMDDYY-nnnn`, stamped at POST since `P0.3`. ⚠ An entry posted BEFORE 2026-09-24 has none and nothing backfills it; the envelope then says `some_entries_pre_date_journal_numbering` **once**, not on every row | **BR-LED-021** |
| 7 | Read a bill row's `documentNo` | `BL-2607-000014` — the number PRINTED on the bill, and the same string `/partner/v1/bills` serves as that bill's `id` | The two feeds join with no further call to us. **Measured on the demo tenant: 147 of 167 posted entries carry a printed number** — 80 invoice, 66 payment, 1 credit note | — |
| 8 | Read the **opening balance** row's `documentNo` | `null`, and no note apologising for it | An opening balance HAS no document. ⚠ And **no uuid appears anywhere in the payload** — a fallback to the source id would put the exact value this phase exists to remove onto the field named for its replacement | B14 rule 31, in its wire form |
| 9 | Read the **tax** row's `taxAuthority` | The authority's name, who levies it, its level and the reference the utility files under | The four things a tax office is actually known by, never our key. The bill's REVENUE rows name **no** authority — saying `$103.00` of electricity was levied by a county is worse than saying nothing | — |
| 10 | Sum the walk: Σ debits, Σ credits | Both, against OUR OWN debit total | They are equal **and equal to ours**. ⚠ A paired row carries one amount that is both its debit and its credit, so the partner's two sides balance BY CONSTRUCTION — the check that bites compares against our figure, not theirs | hard rule 5 |
| 11 | **The gap this journey cannot close** — a correction posted 8 October against a 12 September bill | It lands in **October's** window and in no other | A partner that pulled September on 1 October holds the original figure and will never be handed anything that supersedes it. Their September and ours disagree by the correction and **neither system can see it** | `OQ-INT-6620`, **OPEN** |

---

## What is open, said here rather than left to be discovered

| | |
|---|---|
| `OQ-INT-6620` | **The sync contract.** Step 11 is the whole of it. Three answers are with the Product Owner — leave it · a closed window may be re-pulled complete · a *what changed since* cursor on `posted_at`, recommended — and **a lane may not choose**. `test_fin_p5_partner_contract.py` PINS the current behaviour so a silent change of semantics goes red naming the question |
| `OQ-INT-12393` | **Is splitting one balanced entry into several partner rows the accounting rule Aclarian wants?** Nothing is blocked; the books balance either way. It asks about the SHAPE of what they receive |
| `P5.4` | **Nothing reports back whether the accounting package accepted a handover.** `export_batches` records who sent what and when, and has no acknowledgement column. A handover has a send and no answer |
| ~~`P5.8`~~ | **CLOSED 2026-09-24.** The Finance SCREEN's Reference column showed a uuid; billing and payments now publish `invoice_numbers_for`, `credit_note_numbers_for` and `payment_numbers_for`, and `apps/ledger/{billing,payments}_seam` resolve them by name. See below |

⚠ **THE FEED AND THE SCREEN HAD THE SAME GAP AND BOTH ARE NOW CLOSED — AMENDED
2026-09-24 (`P5.8`, lane FIN-TAIL2).** This paragraph read *"only one of them is
closed"* and that was true for one day. The FEED closed first, with no
dependency, because `apps/integrations` already asks its own seam files for
`invoice_no` and `payment_no` — which is why p018's *"P5.3 cannot be done inside
Finance"* is true of the screen and false of the feed. The SCREEN closed on
2026-09-24: billing published `invoice_numbers_for(ids)` and
`credit_note_numbers_for(ids)`, payments published `payment_numbers_for(ids)`,
and `apps/ledger/{billing,payments}_seam.document_numbers_for` resolve them BY
NAME, so `apps/ledger` still reads neither module's ORM.

**THREE KINDS ON BOTH SIDES, AND THAT IS THE CONTRACT THIS JOURNEY ASSERTS.**
`apps/integrations/seams/ledger._DOCUMENT_SOURCES` and the two ledger seams must
name the same set — `invoice`, `credit_note`, `payment`. **MEASURED ON THE DEMO
TENANT, 2026-09-24, PostgreSQL 16.13, 167 posted entries:** invoice 80 ·
payment 66 · opening_balance 19 · credit_note 1 · refund 1, and every one of the
80, the 66 and the 1 resolves to a printed number. So **147 carry a number, 19
are not documents at all, and exactly ONE is a real gap** — the refund, because
`refunds` has no number column of any kind. **Neither surface invents one**: the
feed keeps `documentNo: null` and the screen leaves the cell empty and says so
once under the table (`some_documents_carry_no_printed_number_yet`). That number
arrives with `P3.3`.

---

## How to run it

The backend half is `06-backend/tests/test_fin_p5_partner_contract.py` — twelve
cases, every one of which was shown RED against a deliberately broken tree
before it was trusted green.

```
cd 06-backend
JOBS_EAGER=false pytest tests/test_fin_p5_partner_contract.py --reuse-db
```

⚠ **STEP 5 MUST BE RUN ON REAL POSTGRESQL AND NOT ONLY ON THE DEFAULT SUITE.**
`config/settings/test.py` hardcodes in-memory SQLite, and the paging guarantee is
a statement about how a DATABASE orders and slices rows — CLAUDE.md hard-won law
14's shape one table over. Run it the way the guarantee is claimed:

```
set -a; . ./.env; set +a
JOBS_EAGER=false pytest tests/test_fin_p5_partner_contract.py --ds=config.settings.pgtest
```

Measured 2026-09-24 on PostgreSQL 16.13: **12 passed**.

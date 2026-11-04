# `CR-103-BRC03` — Budget Bills (§05, entries 25–25.4) against *Billing, As Built*

| | |
|---|---|
| Raised | **2026-09-14** (the number); this file **2026-09-15** |
| Requester | Product Owner, in the working chat session |
| Branch | `claude/eager-johnson-r0k88b` (opened) · `claude/gifted-johnson-top7zn` (continued) · block `CR-100`–`CR-104`, suffix `BRC03` |
| Module | **billing** |
| Drawing | `05-prototype/04 Billing, As Built.pdf` §05, p118–p128, read as images (scale 2; p121–p123 at scale 4) |
| Classification | **MAINTENANCE** for the live table (entry 25) and its clerk copy; **BUILD** for 25.1 Enrol, 25.2 Settle-up forecast, 25.3 Asks |
| Status | **IN PROGRESS.** 25.1–25.3 shipped `2.271.x`–`2.275.0`; the clerk-copy and search defects (`DEF-BIL-5339`, `DEF-BIL-5340`) fixed in **`2.276.0`** |

⚠ **Written after the id was cited in eleven files** — the same process defect `CR-100-BRC03`
and `CR-101-BRC03` record. **No verbatim sentence was recorded at the number's arrival on
2026-09-14, and none is invented here** (law 13): the record that opened it,
`04-docs/05-modules/07-billing/conformance/CR-103-BRC03-budget-bills-maintenance.md`, says
what was measured and why it is maintenance, and that is the capture this CR has.

## 0 · Capture — the requester's words, verbatim, as they arrived on 2026-09-15

Reviewing the live screen at `/billing/budget`:

> *"we were alo looking at budget bill screen - why this text - Three things this screen does
> not do"*

followed by the screen's own paragraph pasted back, and the finding that its rationale carried
rule ids, open-question ids and Python identifiers. That report is `DEF-BIL-5339`; the search's
*"No results for ''"* over an unenrolled real account is `DEF-BIL-5340`. Both fixed under this
CR the same day (lane G's section of the maintenance record).

## 1 · Classify

**MAINTENANCE** — a clerk could already open Budget Bills, look an account up, read its level and
enrol it; the screen was being redrawn against its drawing and its words corrected. In the beta a
report is a defect by default (PO 2026-09-10: *"CR is change in product, defect is product does
not do what is expected"*), and both of the 2026-09-15 reports were.

## 2 · What signed statement is reversed

None. `OQ-237` (where the plan's budget flag is read from) and `OQ-142` (the settle-up ledger
account) stay OPEN; only their citations moved off the screen and into the code and the
register. `BR-BIL-017`'s automatic drop-off remains SUPERSEDED (PO 2026-08-11).

## 3 · Where the work is recorded

`04-docs/05-modules/07-billing/conformance/CR-103-BRC03-budget-bills-maintenance.md` (the table,
the clerk copy, the 2026-09-15 section) · `CR-103-BRC03-entry-25-table-walk.md` ·
`CR-103-BRC03-entry-25-1-enrol.md` · `CR-103-BRC03-entry-25-2-settle-up-forecast.md` ·
`CR-103-BRC03-entry-25-3-asks.md`.

## 4 · Open on this CR

`DEF-BIL-5346` (the gap-list heading's bracketed plural, shared by seven billing screens) ·
`DEF-SHL-5345` (the doubled clear cross in every search box) · `OQ-237` · `OQ-142`.

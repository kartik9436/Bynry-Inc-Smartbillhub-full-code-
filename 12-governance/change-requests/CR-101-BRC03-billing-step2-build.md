# `CR-101-BRC03` — Billing STEP 2: the build that `CR-100-BRC03`'s measurement scoped

| | |
|---|---|
| Raised | **2026-09-14** (the number); this file **2026-09-15** |
| Requester | Product Owner, in the working chat session |
| Branch | `claude/eager-johnson-r0k88b` (opened) · `claude/gifted-johnson-top7zn` (continued) · block `CR-100`–`CR-104`, suffix `BRC03`, claimed in `14-id-reservations.md` §"`CR-100`–`CR-104`" |
| Module | **billing** (`04-docs/05-modules/07-billing/`) |
| Drawing | `05-prototype/04 Billing, As Built.pdf` — 249 pages, 14,363,163 bytes, sha256 `137a2a48…c200971`, on the default branch and this one |
| Classification | **BUILD and MAINTENANCE by entry** — every §-entry the step-1 diff routed to `build`; a live screen redrawn end to end is MAINTENANCE (`22-product-maintenance-process.md`) |
| Status | **IN PROGRESS.** §02 bill detail, §03 bulk run, §04 one-time bill shipped 2026-09-14 (`2.263.0`–`2.272.x`); §06 Fix a bill step 1 + the two backend gaps shipped **2.276.0** (2026-09-15); §06 steps 2–4 in a four-lane wave the same day |
| Versions | `2.263.0` · `2.265.0` · … · **`2.276.0`** — one per shipped wave, allocated at ship time through `allocate.py version` |

⚠ **THIS FILE WAS WRITTEN AFTER THE ID WAS CITED IN FIFTY-SEVEN FILES, AND THAT IS THE SAME
PROCESS DEFECT `CR-100-BRC03`'s OWN FILE RECORDS.** `13-change-process.md` step 0 says a CR is
captured at arrival, and `change-requests/README.md` says *"a file here with no index row is
invisible"*. `CR-101-BRC03` was taken from the claimed block on 2026-09-14, cited by nine
conformance records, the decision log, the defect register and the reservations file, and
carried no file and no index row until 2026-09-15. The whole §06 wave of that day cited it
from the conformance files alone. **Recorded here rather than tidied**; nothing is renumbered.

## 0 · Capture — the requester's words, verbatim

The build was scoped by `CR-100-BRC03`'s step-1 record, and the PO's instruction that opened
step 1 is captured there: *"parallel agents please complete step 1"*. The sentence that shaped
the largest entry of this build, §06, is the PO's ruling of 2026-09-12, verbatim:

> *"we will ahve to make it wizard - 4 steps"*

It reached the drawing (§06, nine entries banded `REDESIGN … NEVER BUILT`) and did not reach
the code until this CR's §06 wave (decision log 2026-09-14, *"Fix a bill becomes the four-step
wizard, and it is MAINTENANCE"*). On 2026-09-15 the PO added, on the step-3 tax panel:

> *"tax panel = tax by authority figures shown again at step 3"*

recorded the same turn in the decision log and on `BR-BIL-044`.

## 1 · Classify

**Not a change to the agreement.** The drawing is the agreement (B14 rules 36, 41, 42;
`DEF-GOV-5248`), and step 1 measured the product against it. Where the product lacks a screen
the drawing has, that is BUILD (`r11`); where a live screen differs from its drawing, that is
MAINTENANCE — each entry's own record says which track it took and why.

## 2 · What signed statement is reversed

None. No ❄️ FROZEN B4/B5 figure moves anywhere in this CR; the correction engine's WE-9 figures
(247.87 → 227.95, net −19.92) are drawn, never recomputed. The one signed rule amended is
`BR-BIL-044` (dated, twice on 2026-09-15): the discounts panel rides inside section 3, and the
step-3 tax panel is section 3's tax-by-authority figures shown again. The nine sections stay nine.

## 3 · Where the work is recorded, entry by entry

| §06 wave (2026-09-15) | Record |
|---|---|
| Lane A — shell, contract, step 1 (screen 26) | `conformance/CR-101-BRC03-step2-06-lane-A-step1.md` |
| Lane B — discounts on the preview; PAID · STATE · totals on the scope resolve | `conformance/CR-101-BRC03-step2-06-lane-B-backend.md` |
| Lanes C–F — steps 2, 3 and 4 (26.1–26.8) | `conformance/CR-101-BRC03-step2-06-lane-{C,D,E,F}-*.md`, when they land |
| The reasons' words and the 2026-09-14 conversion | `conformance/CR-101-BRC03-step2-06-fix-a-bill.md` · `CR-101-BRC03-fix-a-bill-journey.md` |

| Earlier entries (2026-09-14) | Record |
|---|---|
| §02 All bills, the bill detail and four tabs | `conformance/CR-101-BRC03-step2-entry01.md` · `CR-101-BRC03-billing-step2-detail.md` |
| §03 the bulk bill run | `conformance/CR-101-BRC03-billing-step2.md` |
| §04 the one-time bill | `conformance/CR-101-BRC03-one-time-wizard.md` · `CR-101-BRC03-one-time-step3-confirm.md` |

All records live under `04-docs/05-modules/07-billing/conformance/`.

## 4 · Open on this CR

`DEF-BIL-5348` (a window narrowed to one account has no server scope) · `DEF-BIL-5349` (the
case status as a raw code on the carried step-2 body) · `DEF-BIL-5341` (nothing stamps the
discount version a bill used) · `DEF-BIL-5344` (rule ids on the pending queue) · the PO's
confirmation of lane B's three judgments (decision log 2026-09-15).

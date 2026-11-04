# CR-156-BRC10 — Charge codes: three kinds, prices dated and never deleted, a flat amount stored as one *All sizes* row, and ONE lookup for the price on a date

**Raised:** 2026-10-01, by the Product Owner, in eleven same-day rulings on the charge-code
mock-up (artifact `LJHtSjScCXLNED1ohxMDSM`) and one GO for the build. Every ruling is a
row in `12-governance/02-decision-log.md` dated 2026-10-01 whose last column reads
*"charge-code redesign"*; those rows are the specification and are quoted, not
paraphrased, below.
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10` — claimed for this branch in
`12-governance/14-id-reservations.md` in the commit that opens this file; no earlier CR on
this branch carried a suffix). Number from `10-scripts/allocate.py cr` against the remote
(`156`), re-verified at push time.
**Classification:** a **CHANGE** (`13-change-process.md` §1). The product prices charge
codes today; the PO asked for a different storage and saving behaviour and for new
screens, and approved the mock-up. Nothing here is a defect of the agreed behaviour —
`_write_size_amounts` deletes and re-inserts because `BR-RAT-690` said to.
**Waves:** **A** — database, saving, the one-row lookup and their backend tests (this
file's §6 is wave A's record) · **B** — API and screens, built from the 83 mock-up images
(B14 rules 37, 42, 44) · **C** — end-to-end walks and records.
**Version:** wave A — see §8 (allocated with `allocate.py version --bump change` and
re-verified at push).

---

## 0 · What arrived, in the requester's words

> *"you ahve to build product screns using images of https://claude.ai/artifact/LJHtSjScCXLNED1ohxMDSM
> and not text/content - how many images you will take including all variations"*, then
> *"can you start all tasks based on this plan - How I'd run it … A Database + one-row
> lookup + saving (areas 1–3, part of 6) — · B API + screens (areas 4–5) A · C End-to-end
> tests + records (areas 7–8) A + B + Take all images thata re required"*

> **Flat amount history:** *"so we have one proble in case of flat amount in charge code - we
> dont have a history to refer - so if any pas bill ot be created whn chanrge code is flat
> amount - in that case historical price/amount cannot be picked - how we can handle this -
> with out chaging the structure"* → chose **A**: *"this is good - A · Flat amount as an
> \"All sizes\" row (recommended) BASE-S $9.00 is stored as one row in charge_code_amounts
> with size \"All sizes\". An edit closes that row and adds a new one, the same as for
> sizes. The old field on the charge code is no longer written; today's values move into
> rows once. No new table. The existing price table gets the dates and killed mark that
> logical kill already needs. Nothing. A past bill reads the row in force on its dates."*

> **Logical kill:** *"why are you detleting it and not killing it - charge_code_amounts (one
> row per size or class) All of the code's rows are deleted and new ones are written
> Deleted"*, then *"logical kill"*.

> **Dates:** *"we will need start and effective date"* (read as *Effective from* required,
> *Effective to* optional, on Add and on Edit).

> **Kinds:** *"can we have 3 kinds base charges, plan charges and others , we will have them
> from setting - so in setting we will not make any change we will make changes we we
> configure them in charge codes"*; *"we will need 10,11, 12, 12, 14, 23 - all as part of
> plan - rest can be in other"*; *"all these will go in plan - PAPER … HYDRANT … LATE … NSF
> … TAMPER"*; *"in other add application fees + 15 RE-READ … 27 BULK-WATER … - these are
> all others"*; *"user can add custom charge code on their own, mostly these are one time
> and for all services + we need penalties in plans - update your list - we need deposite
> in plans"*.

> **Code picker:** *"when user select code from list show what are not in use only"*.

## 1 · Classified

CHANGE. Fast path does **not** apply: it touches rating math (🔒), a migration (🔒), and
money already stored (every flat amount moves tables once).

## 2 · What signed statement is reversed

* **`BR-RAT-690`** (2026-08-28) — *"REPLACE-THE-WHOLE-SET … a client that omits a row it
  means to delete would otherwise leave a stored size priced for ever"*. **SUPERSEDED for
  storage:** an omitted row is now CLOSED (end-dated and marked killed), never deleted.
  The validation half of `BR-RAT-690` (the three states: no row / NULL row / 0.00 row; the
  allowed size set) stands unchanged.
* **`ChargeCodeAmount`'s docstring rule *"a charge code states a flat `charges.amount` OR a
  table of these rows, and never both"*** — the rule STANDS, its storage moves: the flat
  amount is now the table's reserved *All sizes* row, so "both" means *an All-sizes row and
  a sized row in force on the same date*, and it is still refused at save and at billing.
* **`OQ-RAT-12408`** (`update_charge`'s docstring: *"`charges` has no dates and no version
  table at all … a price typed here takes effect IMMEDIATELY"*) — answered by the dated
  rows; the response no longer names it as open.
* No ❄️ FROZEN B4/B5 figure moves. B4.3 (*base prorated by calendar days*) is applied per
  price part; `tests/golden` must be unchanged.

## 3 · Impact (ten surfaces)

Database (`charge_code_amounts`, `charges.kind`) · rating services (save) · rating
selectors and the R1–R7 catalogue (read) · billing gather/midperiod (the bill period's
dates reach the price) · portal seam (reconnection cost) · seeds and the demo fixture ·
tests (≈75 files touch these tables) · screens (wave B) · records (business rules,
review ledger, CHANGELOG, this file) · open questions: `OQ-RAT-12408` closes in effect;
none opened.

## 4 · What is already built and now wrong

`services._write_size_amounts` (deletes every row on every save) · `charges.amount` as the
flat store and its ~8 readers · eight direct queries of `charge_code_amounts` in four files
· `delete_charge` (removes rows through the same delete). Lanes building now: waves B and
C wait on wave A's service/selector shape (§7).

## 5 · Sized and confirmed

71 tasks in eight areas, put to the PO with the worked figures in §6 and confirmed (*GO*,
decision log 2026-10-01).

## 6 · Wave A — what is built

**Database (`rating/0050`–`0052`, 🔒 HUMAN-REVIEW-PENDING).** `charge_code_amounts` gains
`effective_from` (NOT NULL after the backfill), `effective_to` (NULL = no end) and `killed_at`. The two
unique indexes become uniqueness among LIVE rows; a CHECK refuses a window ending more than a day before it
starts; PostgreSQL's `ex_charge_code_amounts_no_overlap` (`btree_gist`, `daterange`, `COALESCE(customer_class,
'')`) refuses two rows for one (code, size, class) in force on one day — killed rows included, because a killed
row still prices its own dates. `charges.kind` (base · plan · other) is added and classified by the PO's list.
Every set `charges.amount` moved into ONE every-class *All sizes* row from `2000-01-01` and the column was
cleared; the model renames it `legacy_amount` and `Charge.amount` refuses a read. RLS: the table keeps ENABLE +
FORCE, proved on PostgreSQL under the probe role.

**Saving (`services.create_charge` / `update_charge` / `delete_charge`, the Settings card's delete).** Through
the one writer, `charge_prices.save_prices`: an unchanged row is untouched, a changed or removed one is closed
the day before the new *Effective from* and marked killed, the new price is a new row. *Effective from* is
required on Add and on every Edit that moves a price; *Effective to* is optional; a reason is still required
only for a code in use; `rate_change_log` is written for every money change. A never-used code deleted takes its
rows with it.

**One lookup (`apps/rating/charge_prices.py`) and the gate (`G141`).** `price_on_date(charge, size, class,
date)` returns exactly one row or a named refusal (`no_price`, `size_not_recorded`, `size_not_priced`,
`amount_and_size_table`); a class row beats the every-class row. Billing passes the service date it prices; the
cycle bill, the catch-up and the interim bill are cut at every day a base code's price changes.

**READ PLACES — EXPECTED 19, FOUND 28, EVERY ONE ON THE LOOKUP:**

| Group | Shown to the PO | Found | Where |
|---|---|---|---|
| direct queries of `charge_code_amounts` | 8 | **8 reads + 2 writes** | selectors `_charge_size_amounts`, `charge_row`, `billable_charge_codes`, `base_charge_from_charge_code`; resolution_catalogue `base_code_sizes_for`, `charge_code_facts`; services `_stored_size_money`, `_stored_size_amounts` (reads) · `_write_size_amounts` delete + insert (writes) — `G141` RED on the tip `98b74e815` with exactly these 10 |
| reads of `charges.amount` | 8 | **11** | selectors `plan_detail`, `charge_row`, `billable_charge_codes`, `base_charge_from_charge_code`, `charge_by_code` ⚠, `charge_list_queryset`'s amount sort ⚠; resolution_catalogue `charge_code_facts`; portal `rating_seam.connection_fees`; services `_validate_charge` ⚠ and `charge_money_moves` ⚠; `migrate_base_to_charge_codes` ⚠ — ⚠ = not on the list shown. Three listed places read NO table: `resolution.py` ~2314 (reads the catalogue `charge_code_facts` builds), `pricing/amount_rules/rules.py` ~64 (`ChargeContext.amount`, an engine input) and `service_base_amounts.py` (seed figures) |
| fee paths to confirm | 3 | **3 confirmed + 6 more** | `customers/disconnects.py`, `metering/connections.py`, `customers/service_request_service.py` copy NO price from the table — each reads `rating.selectors.charge_by_code` (now on the lookup, today's price) and snapshots it onto its own quote row, which is the quote's job. The same read also serves `billing/fee_bill.py`, `penalty.py` (through fee_bill), `first_bill.py`, `decisions.py` (GL only), `one_time_answer.py` and `payments/counter_receipts.py` |

So **19 expected, 28 found** (10 table + 11 column + 3 fee paths + 6 further consumers of the fee read, counting
`charge_by_code` once in the column group). Nothing outside `charge_prices.py` touches the table — `G141` green
over 861 files — and a missed `charge.amount` read raises at run time instead of answering `None`.

**WORKED FIGURES, AS TESTED (PostgreSQL 16, through the real doors):**
- BASE $9.00 → $10.00 effective 11/01 (saved after; the fixture's water base code carries the PO's BASE-S case):
  catch-up 09/01–09/30 = **$9.00** (one-time `backbill`); interim 10/16–11/15 = **$4.65 + $5.00 = $9.65** (one-time
  `interim`, two base lines, each part over its own month); November cycle bill = **$10.00**; a cycle bill
  10/16–11/15 is cut at 11/01.
- BASE-T on 10/15 for 11/01: CART-64 $12.00 → $13.00 and CART-96 new $15.00 — the $12.00 row kept and closed
  10/31, CART-35 $9.00 and DUMP-2 $40.00 the same row ids; *"what was CART-64 on 09/01?"* → $12.00.
- Overlap refused by the database (`ex_charge_code_amounts_no_overlap`), and the writer's own shapes (handover,
  class beside every-class, an emptied row) accepted.

**Not built in wave A, named:** first and final bills are not cut at a price change (they read the price on their
service date) — `DEF-BIL-8749`; the screens and the picker's endpoint are wave B.

**`DEF-BIL-8749` FIXED (`2.430.2`, coordinator 2026-10-01):** the first and final bills are now cut at a charge-code
price change the same way — `single.with_price_split`, called from `first_bill.prepare_first_bill` and
`final_bill.prepare_final_bill` (the one function every door of each shares), through `midperiod.gather_split` with
**price cuts only** (a rate or plan boundary inside a first or final bill is still NOT cut — the 2026-08-22 ruling kept
typed documents on their own rules). Each part is divided by the account's cycle on the part's own last day (a stated
cycle length still wins); the first bill's readings still open the day after move-in and the final bill's preview still
prices the move-out wizard's keyed reads, in every part. Worked on PostgreSQL: a first bill 10/16–11/15 with
$9.00 → $10.00 from 11/01 = **$4.65 + $5.00 = $9.65** (draft and preview), a final bill over the same window the same,
a first bill 11/16–11/30 wholly after the change one line of **$5.00**. Proved red first: with the cut disabled the
first and final drafts charged **$10.00** (31/31 at the 11/15 price). B4.3 ❄️ is unchanged — service days ÷ cycle
days, per part; no frozen figure moves (no B5 fixture crosses a charge-code price change).

## 7 · Contract note for wave B — what the API calls and what it gets back

Wave A fixes the SERVICE and SELECTOR shape; wave B owns the HTTP layer
(`apps/rating/api.py`) and the screens. Everything below is live on the branch.

**Writes — `services.create_charge(actor, payload)` / `services.update_charge(actor, id, payload)`**
(the existing `POST /charges` and `PATCH /charges/{id}` already pass the body straight through).
New keys, beside every existing one:

| key | type | rule |
|---|---|---|
| `kind` | `"base"` \| `"plan"` \| `"other"` | optional on Add (absent → the PO's classification, `constants.default_kind`); `base` ⇔ `is_base`, a payload stating both must agree (`rating.unknown_value` on `kind`) |
| `effective_from` | ISO date | the date the price starts; **absent → the tenant's today (interim rule below)** — the new screens require it and say *"Pick a date."* themselves |
| `effective_to` | ISO date \| null | optional, blank = no end; before `effective_from` → `rating.plans.window_inverted` on `effective_to` |
| `amount` | money string \| null | the code's flat price = its every-class *All sizes* row |
| `size_amounts` | list of `{size_class, customer_class?, amount}` | the sized rows; `size_class: "All sizes"` with a `customer_class` is a **flat price for one class** (a plan code priced by customer class); posting the every-class *All sizes* row here AND `amount` is refused `rating.size_rows.duplicate_size` |
| `reason` | text | unchanged: required (≥ the existing minimum) only when money moves on a code IN USE (`rating.charges.reason_required`) |

Saving never deletes a price row: unchanged rows are untouched, changed or removed rows are closed
the day before `effective_from` and marked killed, new prices are new rows. Every money change writes
`rate_change_log`. `issued_bills_unchanged: true` still comes back on a reprice of a code in use;
`open_question: "OQ-RAT-12408"` no longer does.

**Reads — `selectors.charge_row(charge)`** (what `GET /charges`, `GET /charges/{id}` and every save return).
New keys beside every existing one:

* `kind` — `base` | `plan` | `other` | `null` (minted on Settings, not configured yet).
* `amount` / `amount_display` — the every-class *All sizes* row **in force today** (was `charges.amount`).
* `size_amounts[]` — rows in force today other than that one, each now also carrying
  `id`, `effective_from`, `effective_to`, `killed` and **`version`** (see below).
* `prices[]` — **the whole dated history**, same row shape, killed rows included, ordered
  (size, class, start) — the *View details → Prices* tab and the *Effective from / to* shown on View.
* `price_range` — `{low, high, low_display, high_display, priced_by: "size"|"customer_class"|"flat", rows}`
  over today's rows, or `null` when nothing is priced — the list's *Amount* cell for a sized code
  (*"BASE-T reads $9.00 – $40.00"*) and its *Priced by* column.

**Versions (coordinator, from PO 2026-10-01 *"BASE CHARGES SHOWS EACH SIZE'S BASE-PRICE VERSION AND ITS
EFFECTIVE DATES"*).** Every price row served anywhere carries `version`: per (code, size, class), the
non-empty rows in `effective_from` order are 1, 2, 3 …; a row superseded before it began (an *empty* row,
`effective_to` one day before `effective_from`) prices no day and has `version: null`. Worked: BASE-T CART-64
$12.00 (2000-01-01 → 2026-10-31, killed) is **v1**, $13.00 (2026-11-01 → no end) is **v2**. **Counted on read,
not stored, deliberately:** a back-dated edit can start a new row BEFORE an existing one, and a stored number
would then contradict the date order the PO asked for; counting costs one query per screen read and is never on
a billing path. For the rate-schedule screen: **`selectors.base_code_price_rows(service_code, on_date=None)`**
→ `[{id, code, name, customer_classes, prices: [row, …]}]` for every live base code of the service, each row with
size, class, amount, `effective_from`, `effective_to` (null = *No end*) and `version` — the screen reads these
and works nothing out.

**The list — `selectors.charge_list_queryset` / `charge_page`**: new filter `kind` (declared in
`CHARGE_FILTERS`; wave B wires the control); sort `amount` now orders by today's flat price, else the
smallest sized price, in SQL.

**The Add picker — `selectors.charge_code_picker(kind, service=None)`** → `[{id, code, name,
charge_type, kind, service}]`: the tenant's codes not retired, of that kind or of no kind yet, for a
base of that service or of none, and NOT IN USE (a plan names it, a schedule reads it, a bill carries
it). Wave B adds the endpoint (e.g. `GET /charges/picker?kind=&service=`). Empty → the screen's
*"No free code. Add one in Settings."*

**Prices on a date — `apps/rating/charge_prices.py`** is the only module that reads or writes
`charge_code_amounts`; gate `G141` fails anything else. A screen that needs a price on a day calls
`charge_prices.price_on_date(charge, size_class, customer_class, on_date)` (one row or a named
refusal) or `flat_amount(charge, on_date, customer_class)` through a selector, never the table.

⚠ **INTERIM RULE (coordinator, 2026-10-01, `2.429.1`) — A MISSING *EFFECTIVE FROM* MEANS TODAY.** The live
CHG-02 wizard the beta clerks use sends no date, so the SERVICE no longer refuses a price-moving Add or Edit without
one: it takes the tenant's today (`services._effective_from_or_today`) — exactly what that wizard's save meant
before dates existed (*the price applies now*). The old row is closed yesterday and kept, the new one starts today
(`test_interim_the_old_wizard_payload_still_saves_a_price_change_dated_today`). A payload that sends the date is
honoured. **Wave B's screens must still send the date and refuse a save without one (*"Pick a date."*)**; retire
the default once no caller relies on it.

## 9 · Wave B — what is built (`2.431.0`, corrections `2.431.1`)

**HTTP (`apps/rating/api.py`).** `GET /charges/picker?kind=&service=` (declared before `charges/<id>`; an unknown
kind is refused `rating.unknown_value` on `kind`) · `GET /charges` serves `kind_counts` `{all, base, plan, other}`
under every other filter and search (one `GROUP BY`), filters `f.kind` and sorts `kind` · `GET /charges/{id}` is
`selectors.charge_detail`: the row plus `usage` (sent bills issued last calendar month — bills, lines, money; `null`
when billing cannot answer) and `versions` (the price versions, newest first: window, `scheduled | in_force |
ended`, each size/class change *before → after*, who and why from `rate_change_log`). Create and update were already
pass-through. OpenAPI regenerated (one path added). Tests: `tests/test_cr156_wave_b_charge_api.py` (6, through the
views).

**Screens, each built from its images (rule 42).**

| Screen | Images | File |
|---|---|---|
| List — Kind + Priced by columns, kind chips with counts, price range, GL *Not set* | 01–05 | `ChargeCodesTab.tsx` |
| View details — base / plan / other: header with kind badge, scheduled banner, four tiles by kind, tabs Overview · Prices · Plans · Audit (Other hides Plans) | 06–42 | `ChargeCodeDetailPage.tsx` (new; the charge route no longer uses `DefinitionDetailPage`) |
| Add and Edit — Details · Pricing · Review, summary aside with the GL account, free-codes picker, Effective from / to, reason and *What changes* on Edit | 43–83 | `ChargeCodeWizard.tsx` (rewritten) |
| Shared pieces (rule 43) | — | `chargeCodeParts.tsx`, `chargeCodeModel.ts` |

**Kit:** `SearchSelectField` gained opt-in `emptyText` / `noMatchText` (*"No free code. Add one in Settings."* /
*"No code found."*), and `FilterBar` an opt-in `allChip={false}` (the list's own *All · N* chip replaces the bar's);
nothing else moved. **Copy:** the list's explanatory paragraph is gone (PO 2026-10-01; `rating.explainer.chargeCodes`
retired and taken off `G14`'s explainer list), 81 keys of the old wizard retired through `i18n_fanin.py`, 179 new
`rating.chargeCode.*` keys in all eleven catalogues; glyph-only strings (*$9.00 – $40.00*, *Base · 5*) are composed in
code, not catalogued. A sized base starts with one row per size of its service, in size order. **Defects closed** (each with a case in `chargeCodeWaveB.dom.test.tsx` that
fails on the old screen): `DEF-RAT-8713`, `8714`, `8715`, `8716`, `8717`, `8719`. **Filed:** `DEF-RAT-8753` (entered
when used, penalty by class — shown disabled), `DEF-RAT-8752` (Minimum column, Held tile, Plans tab class/accounts —
no read). **Retired with the old wizard:** six test files that walked the superseded CHG-02
(`ChargeCodeWizard.test.tsx`, `chargeRepriceReason`, `def_rat_7800_amount_box`, `cr087ChargeCodeConformance`,
`chargeCodeClerkWalk`, `chargeBehaviourTicks`) and the wizard halves of `moneyBoxes` and `cr087ClassSizeGrid`.
The judgments taken are the decision-log row *"CHARGE-CODE WAVE B BUILT"*. **Proof:** `e2e/CR-156-charge-codes-wave-b.spec.ts` (Add → View → Edit from a future date for a base, a plan and an other code, PostgreSQL 16, Chromium at 1440) and 30 built screenshots, each beside the reference image it was built from, in `08-qa/screens/charge-codes-waveB-2026-10-01/`. **`2.431.1`** (coordinator review): trash sizes carts first then dumpsters, smallest first in each; a base code's Type reads *Every bill* on View.

## 10 · Wave C — the two pricings, the view's reads, and the 83-state proof (`2.435.0`)

**Part 1 — the two pricings wave B showed disabled (`DEF-RAT-8753` fixed; `BR-RAT-1053`, `BR-RAT-1054`).**

* **A penalty priced BY CUSTOMER CLASS.** `rating/0054` adds `percent` (18,6, a fraction) and `min_amount`
  (18,4) to `charge_code_amounts` and a CHECK that a row is an amount row OR a terms row. A class's terms are
  an *All sizes* row naming the class, written by `charge_prices.save_prices` (target value
  `ClassTerms(percent, minimum)`), so they are dated and logically killed like every price. The API key is
  `class_terms: [{customer_class, percent, min_amount}]` (a posted list replaces the stored terms; `[]` clears
  them); `charge_row` serves `class_terms` (today's) and every history row carries `percent` /
  `min_amount` and their displays. Every amount reader (`rows_in_force` by default) excludes terms rows, so a
  terms row never reads as *not priced*. The late fee: `assess_late_fee_for_plan(…, customer_class=)` →
  `plan_late_fee_terms(plan, customer_class, on_date=as_of)` → `charge_prices.class_terms_on`; a code with no
  class rows answers from its own two columns as before. **As tested on PostgreSQL 16:** Residential $200.00
  → **$5.00**, Commercial $2,000.00 → **$40.00**; GT-8's $8.13 on the seeded `LATE` for every class;
  `tests/golden` 23 passed + 1 xfailed (unchanged). A class the code does not price refuses
  (`LateFeeClassNotPriced`).
* **An amount ENTERED WHEN USED.** `amount_rule = 'per_case'` (CR-010 A2), no price row; a price posted beside
  it is refused (`rating.charges.per_case_states_no_price`). `fee_bill.charge_code_line(code,
  entered_amount=)` takes the clerk's figure for a `per_case` code only, through `price_charge_fee` /
  `raise_charge_fee`, `OneTimeRequest.entered_amount` and `POST /billing/one-time/preview` and its create (`entered_amount`); the
  One-time bill's fee kind shows an *Amount* field for such a code. A figure beside any other code is refused
  (`BR-BIL-020` holds for every code that states a price — the reading is in the decision log and reported
  to the PO). R4 refuses a `per_case` code by that name (`DEF-2340` partially fixed — the seeded TAP, IMPACT,
  DAMAGE and BULK-WATER rows are not moved to it).
* **Screens.** CHG-02 offers *Entered when used* (Other) and *By customer class* for a penalty (step 2: class ·
  percent · minimum, + Add row; review lists each class); View details › Prices lists each class's percent and
  minimum, Residential first, and reads *Entered when used* for a `per_case` code; the list shows the percent
  range and *By customer class*. DOM cases in `chargeCodeWaveB.dom.test.tsx` (both proved RED by restoring
  wave B's `disabled`).

**Part 2 — the view's reads (`DEF-RAT-8752` partially fixed; `DEF-RAT-8821` open).** `GET /charges/{id}`
serves `size_minimums` (`selectors.base_code_size_minimums`) for a base code: per size, over each schedule on
its service in force today, `one` / `range` / `none` / `mixed` — drawn as the figure, *low – high*, or *—*.
View › Prices and wizard step 2 draw it read-only beside a base's sizes (images 11, 51). `GET
/charges/{id}/plans` rows carry `customer_classes` (by name, `[]` = every class) and `accounts` (open accounts
on the plan's current units, through `seams.open_account_counts_by_unit`); the Plans tab draws *Plan ·
Customer class · Accounts* (image 20). The deposit *Held* tile (image 26) has no read and stays out
(`DEF-RAT-8821`).

**Part 3 — all 83 states, built beside the drawing (`2.436.4`).** `e2e/CR-156-charge-codes-wave-c.spec.ts`
(8 tests, Chromium at 1440, PostgreSQL 16) photographs every state of the mock-up into
`08-qa/screens/charge-codes-waveC-2026-10-01/` beside a copy of its reference image, and walks both pricings
through the real screens: LATE priced by class (Commercial moved to 2.50% from a future date, the old row
killed) and TAP entered when used (One-time preview carries the entered **$1,250.00**). **76 match, 7 differ**
(05 kit empty state, rule 44; 26–29 *Held* tile, `DEF-RAT-8821`; 40 a `per_case` code has no Effective from;
51 rationale sentence, rule 33). Fixed because the comparison found them: tiles and scheduled band above the
tabs; *How it bills* two rows of three; class rows Residential first; the share note (image 52); the Minimum
column only where a schedule floors a size, read from the service on Add (`GET /charges/picker` serves
`size_minimums`); Audit reads a class change; and `one_time_answer.request_from` dropped `entered_amount`, so
a `per_case` fee was refused through the real door while every unit test passed (law 2). Journey J76.

## 8 · Version and rollback

**Wave A: `2.429.0`**, interim missing-date rule **`2.429.1`**, first/final bills cut (`DEF-BIL-8749`) **`2.430.2`**, **wave B `2.431.0`**, **wave C `2.435.0`**, wave C part 3 **`2.436.4`** (rollback of part 3: revert its commit — no migration; the picker stops serving `size_minimums` and the view's arrangement goes back) (wave C rollback: revert the wave-C commit and migrate rating back to `0053` — `0054` drops the two terms columns and the CHECK; a per-class percent or a `per_case` code saved meanwhile loses its terms or keeps no price; nothing billed changes) (wave B rollback: revert the wave-B commit — no migration, the screens and three reads go back; prices saved through the new screens stay, being ordinary dated rows) (`allocate.py version --bump change`, re-verified at push). **Rollback:** revert the
wave-A commit and migrate rating back to `0049` — `0052` drops the exclusion and the CHECK, `0051`'s reverse puts
every live every-class *All sizes* amount back on `charges.amount` and removes the rows it wrote (rows a clerk
wrote later are kept), `0050` drops the columns and restores the two unique indexes. A price a clerk dated in the
future is lost on rollback; nothing billed changes.

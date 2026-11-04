# Discounts — the full web walk (task 9) — COMPLETE, steps 1–11

`CR-166-BRC10` round 4 task 9 · walked 2026-10-03 on builds 2.481.2 → **2.481.11** · plan
`05-prototype/discounts-2026-10-03/web-walk.md`. Walked in three sessions: steps 1–6 (the
checkpoint, 2.481.6), step 9 on issued runs (lane DISC-FIX, 2.481.11) and steps 7, 8, 10, 11
(lane DISC-WALK, 2.481.7 → 2.481.10). Each session's own section below says how it was run.
Closed in `CR-166-BRC10` §16 (this walk) and §17 (the close).

## Final count

From `walk/results.json` (208 recorded checks, every session's rows) plus step 9's seven checks,
which were read three ways by `10-scripts/cr166_discwalk_step9.mjs` and are tabled in its section.

| Step | Checks | Pass | Fail | The fails |
|---|---|---|---|---|
| 1 Create one of every kind (+ draft) | 24 | 24 | 0 | |
| 2 Form checks | 8 | 8 | 0 | |
| 3 View | 27 | 27 | 0 | |
| 4 Going live | 30 | 28 | 2 | Garden usage allowance cannot go live (`BR-RAT-962`, **with the PO**); Lifeline live on one approval with the threshold on (`DEF-RAT-9303`, open) |
| 5 Plans & enrollment | 10 | 10 | 0 | |
| 6 Accounts tab | 10 | 10 | 0 | |
| `DEF-RAT-9319` list width, 11 languages | 11 | 11 | 0 | |
| 7 Edit three ways | 13 | 12 | 1 | the red run of `DEF-RAT-9338` before its fix (2.481.7); passed after |
| 8 Billing gets one version; Dec/Jan bills | 12 | 12 | 0 | |
| 9 Limits on real, issued bills | 7 | 5 | 1 (+1 pending) | 9.3 *CAP stops after $300.00* (`DEF-2430` / `DEF-BIL-5341`, open — and see the note in step 9 on the $50.00 floor); 9.4 Garden **pending with the PO** |
| 10 Retire | 3 | 2 | 1 | the red run of `DEF-RAT-9340` before its fix (2.481.9); walked again after |
| 11 Utility B and the eleven languages | 60 | 60 | 0 | |
| **Total** | **215** | **209** | **5 (+1 pending)** | two are red runs of defects fixed in the walk; three are known and open: the PO's Garden question, `DEF-RAT-9303`, `DEF-2430` |

**Nothing the walk found is left unfixed or unfiled.** Fixed during the walk: `DEF-RAT-9318`,
`9319`, `9325`, `9326` (2.481.6), `9338` (2.481.7), `DEF-BIL-9339` (2.481.8), `DEF-RAT-9340`
(2.481.9), `9341` (2.481.10), `9327` (2.481.11); `DEF-RAT-9289` closed. Filed and left to Billing:
`DEF-BIL-9346` (the bill's *Document* tab reads *Charged to the bill* for discounts).

## Steps 1–6 — the first session (checkpoint, builds 2.481.2 → 2.481.6)

**How it was run.** The built front end (`vite build --mode wolocal`, `07-frontend/server.mjs`) on
the Django back end over a scratch **PostgreSQL 16** database (`migrate` + `seed_demo` +
`10-scripts/cr166_discwalk_world.py setup`), Chromium at 1440, signed in as Dana (System Admin).
Script: `10-scripts/cr166_discwalk.mjs` (`PHASES=…`, `WORLD=walk/world.json`); raw results
`walk/results.json` (120 checks, 118 pass — the two fails are listed below); discount ids
`walk/state.json`; screenshots `walk/discwalk_<step>_<n>.png` (each opened; none blank).
The scratch database was dropped at the end; re-running needs `setup` again and new ids.

**The world.** Utility A = Brazos Bend; Utility B = Riverbend Water (provisioned, no discounts).
Plans *Discount walk · Residential / Municipal / Garden / Other*, water only: base `BASE-W` $8.00 +
0–10 kgal at $4.20 + above at $5.00 → a residential account using 12 kgal bills **$60.00** (the
municipal account has no base — `BASE-W` is residential-only — and bills $52.00). Accounts:
AC-2026-00001 Ruth Alvarez (autopay on), -00002 Carl Jensen, -00003 Mia Okafor, -00004 Pat
Lindgren, -00005 Omar Price (off-plan, plan *Other*), -00006 City Hall (municipal), -00007 Gail
Moreno (plan *Garden*).

### Phase by phase (as recorded at the checkpoint; later sessions add their own sections)

| Step | Result |
|---|---|
| 1 Create one of every kind (+ draft) | **PASS** — 9 discounts saved through the New form, one DB row each, Draft in the list; the Review's $60.00 figures right (Senior −$9.00, CAP −$10.00, Autopay −$0.30, Municipal −$5.00). Charge waiver walked again after **DEF-RAT-9318**. Draft: *Save draft & exit* half way → reopened by Edit (nothing lost) → finished, same row |
| 2 Form checks | **PASS** (8/8) — each mistake on its box, nothing typed lost, currency USD read-only, server refuses CAD by name |
| 3 View | **PASS** — every value served as entered (empty boxes store the server defaults: notice 60, grace 0, stacking 100, group none); Overview shows them; Draft offers Edit · Submit |
| 4 Going live | **PASS** for 7 discounts — Submit → Approve by the same person, live with no Activate; Paperless (11/01) reads *Scheduled*; Audit names Dana. **Two FAILS, both known/ruled:** Garden allowance cannot go live (*"This discount type can't be priced yet"* — `BR-RAT-962`, CONFIRMED: the engine does not price a usage allowance) → **needs the PO**; with the threshold switched on ($100) Lifeline went live on ONE approval — `DEF-RAT-9303` (known, open) |
| 5 Plans & enrollment | **PASS** — plans saved through `PATCH /plans/{id} {discounts, reason}` (the plan wizard's own save; the wizard could not be clicked on the world's fixture plans — its step 2 reads no service); Automatic enrolled exactly the autopay account and exactly the municipal account (ruling 3); off-plan account refused on screen *"Their plan doesn't offer this discount."* (ruling 2); Senior off the plan → enrollment ended *Removed from plan …*; put back and re-enrolled |
| 6 Accounts tab | **PASS** after **DEF-RAT-9325** and **DEF-RAT-9326** — Verify proof turns Proof pending into Receiving; Enroll and End close their dialogs; End stores day and reason; tab count = rows = Overview *Receiving it* (as images 19/20 draw: pending counted); Granted / This month a dash (`DEF-2430`, known); Audit names enroll, verify, end |
| DEF-RAT-9319 list width | **PASS in all 11 languages** — 1,120px, no sideways scroll, Status in view, Type never one character a line (`discwalk_9319_en/ja-JP/ko-KR.png`) |
| 7 Edit three ways | **PASS** (12 of 13 checks; the 13th is the red run of **DEF-RAT-9338** before its fix) — walked in the resume session, see *Steps 7, 8, 10 and 11* below |
| 8 Billing gets one version; Dec/Jan bills | **PASS** (12/12, after **DEF-BIL-9339**) — December −$9.00, January −$7.20, issued; December unchanged afterwards. See below |
| 9 Limits on real bills | **PARTLY** — an October PREVIEW (rolled back) was run, see below; no run issued |
| 10 Retire | **PASS** after **DEF-RAT-9340** — retired 01/31/2027; the February bill has no Senior, enrolled Ruth included. See below |
| 11 Isolation and languages | **PASS** (60/60, after **DEF-RAT-9341**) — Utility B sees nothing of A on screen, via the API or in the database; four screens × 11 languages. See below |

### October preview (09/16–10/15/2026, calculated then rolled back, nothing kept)

| Account | Before | Discount lines | Total |
|---|---|---|---|
| Ruth (Senior verified + Autopay) | $60.00 | Senior −$9.00, then Autopay 0.5% of $51.00 = −$0.26 | $50.74 |
| Carl (CAP + Lifeline + Senior, one group) | $60.00 | CAP −$10.00 only (floor $50.00; one of the group — never $19/$34) | $50.00 |
| Pat (Veteran 1.5%) | $60.00 | −$0.90 | $59.10 |
| City Hall (Municipal 20%, cap $5) | $52.00 | −$5.00 | $47.00 |
| Omar (off plan) / Gail (Garden not live) | $60.00 | none | $60.00 |
| **Mia (Lead line waiver on BASE-W)** | — | **no bill: the run stopped her account** | — |

`discount_grants` rows after the run: **0** — budgets and yearly caps never deplete from real
bills (`DEF-2430`, open), so step 9's *"CAP stops after $300.00"* and *"Garden suspends"* cannot
pass on real runs until it is fixed.

## Bugs found

| Defect | Where found | What the user saw | State |
|---|---|---|---|
| `DEF-RAT-9318` | 1.6 | Charge waiver: *Fix 1 thing first.* with nothing marked; never saved | **fixed 2.481.6** (form sends value 0 for a type with no value box); walked again: saved, list shows a dash |
| `DEF-RAT-9319` | coordinator, task 8 photos | list scrolled sideways at 1440; ja/ko Type one char per line | **fixed 2.481.6** — Verification off by default in ▦ Columns (12 columns needed 1,196px in 1,120px; the header tier sets the floor), Type/Status `break-keep`, allowance unit may wrap. Measured in 11 languages |
| `DEF-RAT-9325` | 6 | Proof pending could never be verified; bill $0.00 not −$9.00 | **fixed 2.481.6** — `POST /discount-enrolments/{id}/verify` + ✓ *Verify proof*; walked |
| `DEF-RAT-9326` | 5 | Enroll / End dialogs stayed open after success | **fixed 2.481.6**; walked |
| `DEF-RAT-9327` | 9, October preview | an approved named-codes waiver stops every enrolled account's bill (`BillRunBreak` *rating refused to price*) | **Fixed 2.481.11 (`f722c6c3c`) by the step-9 session below** — this cell is the checkpoint's record: *OPEN — fix NOT pushed.* Started and withdrawn at the checkpoint: a guard in `discount_services._refuse_unpriceable` refusing `applies_to == named_codes` at approval (key `rating.discounts.scope_not_priceable`, needs a catalogue key in 11 languages, HUMAN-REVIEW-PENDING + review-ledger row — 🔒 file). Its test (approve a named-codes waiver → refused) failed after the guard for a reason not yet read; nothing of it is on the branch. The real fix (charge code on the priced line) is engine work in 🔒 `pricing/stages/apply_discounts.py` |

## Needs the PO
* **Usage allowance (Garden, image 10) can be created but never go live** — `BR-RAT-962` (signed)
  keeps it unpriceable: pricing it as money would take $2.00 off where the ruled arithmetic makes
  it $14.40. The walk agreed with the PO expects *2 kgal free before pricing*. Either the engine
  step is built (money change) or the form stops offering the type.

## Left for the next session — done
Everything this list named was done by the later sessions below: steps 7, 8, 10, 11 (lane
DISC-WALK) and step 9 on issued runs with `DEF-RAT-9327` fixed (lane DISC-FIX); the register rows
closed; golden re-run (**25 passed, 1 xfailed**); `CR-166` §16 and the decision-log rows written.

## Step 9 — limits on REAL, ISSUED bill runs, and `DEF-RAT-9327` (lane DISC-FIX, build 2.481.11)

**How it was run.** A fresh PostgreSQL 16 database (`sbh_discfix`: `migrate` + `seed_demo` +
`cr166_discwalk_world.py setup`); the built front end (`vite build --mode wolocal`, `server.mjs`)
at 1440, signed in as Dana. The discounts were made, approved, bound and enrolled through the
screen by re-running `cr166_discwalk.mjs` phases `1,1.8finish,4,5` → `5back` → `6` (same results
as the checkpoint: only the two known fails, Garden and `DEF-RAT-9303`). Then **four cycle runs
were ISSUED**, not previewed — 09/16–10/15/2026, 10/16–11/15, 11/16–12/15 and 12/16/2026–01/15/2027
(`cr166_discwalk_world.py run …`) — and every bill was read three ways by
`10-scripts/cr166_discwalk_step9.mjs`: on the bill's **Charges** tab (`/billing/bills/{id}?tab=lines`),
from `GET /api/brazosbend/invoices/{id}`, and from `invoice_lines`. Screenshots
`walk/discwalk_9_1.png` … `discwalk_9_7.png` (each opened; none blank).

| # | Must be true | Result | Evidence |
|---|---|---|---|
| 9.1 | Senior with Autopay: stacking order applied | **PASS** | Ruth, Oct (BL-2610-000001, issued): Senior 15 % of $60.00 = **−$9.00** first, then Autopay 0.5 % of the **$51.00 left** = **−$0.26** (not −$0.30 of $60.00) → **$50.74**; same on screen, API, DB; every month the same (`discwalk_9_1`) |
| 9.2 | CAP and Lifeline never both | **PASS** | Carl (CAP + Lifeline + Senior, one exclusivity group): only **CAP −$10.00** on every issued bill, Oct–Jan — the $50.00 floor stops the $25.00; no Lifeline line on screen, API or DB (`discwalk_9_2`, `discwalk_9_3`) |
| 9.3 | CAP stops after $300.00 in the year | **FAIL — known, not re-reported** | after four issued runs `discount_grants` holds **0 rows** for CAP and *Granted* reads a dash (`DEF-2430` / `DEF-BIL-5341`: issue writes no grant, so no yearly cap or budget ever depletes) (`discwalk_9_4`). **Engine half proved, rolled back:** one $295.00 grant appended through `discount_services.record_grant`, the December run previewed → Carl's CAP trimmed to **−$5.00**, bill **$55.00**; transaction rolled back (0 grant rows after). ⚠ **The walk's own figure cannot be reached as written:** with the $50.00 floor CAP gives $10.00 a month, so 13 months is $130.00 and the $300.00 cap never bites even once grants are written — the step needs a bill whose floor lets CAP give $25.00 (12 months = $300.00) |
| 9.4 | Garden suspends when the budget runs out | **PENDING with the PO** | Garden cannot go live (`BR-RAT-962`, signed: a usage allowance is not priceable; approval refuses it) — Gail's bills $60.00 with no allowance (`discwalk_9_7`) |
| — | the rest of the run | **PASS** | Pat Veteran 1.5 % −$0.90 → $59.10 · City Hall Municipal capped −$5.00 → $47.00 · Omar (off plan) $60.00 |
| 9327 | an approved named-codes waiver bills, and stops nobody | **PASS (fixed in 2.481.11)** | Mia, Lead line waiver on `BASE-W`: Oct **and** Jan bills issued, $8.00 base printed, **Lead line waiver −$8.00 → $52.00** on screen, API and DB (`discwalk_9_5`); `bill_run_breaks` 0 across four runs |
| 9327 | a waiver naming a FEE code is refused at Approve, by name | **PASS** | *Connection fee waiver* on `CONN`: Approve → *"CONN can't be discounted. Choose a base charge code."*, stays Waiting approval (`discwalk_9_6`) |

### `DEF-RAT-9327` — reproduced, then fixed

* **Reproduced on PostgreSQL with the tip's code** (`a8327b1ab`), October preview on the same
  world: `BillRunBreak AC-2026-00003 price-usage rating_refused_to_price — "rating refused to
  price this bill (water): discount 'LEADWAIVE' has scope named_codes … the engine's priced lines
  do not carry a charge code"`. Mia had no bill.
* **Cause:** `billing.gather` always resolved the base's charge code and sent it
  (`TariffConfig.base_charge_code`); the engine dropped it at normalize, so the law module's own
  `named_codes` branch (`discount_pricing._scoped_base`, selecting by `charge_code`) had nothing to
  select on, and `apply_discounts` refused the whole bill instead.
* **Fix (🔒, HUMAN-REVIEW-PENDING, review-ledger row):** the code travels — `ModelConfig.base_charge_code`
  → `price_usage` stamps the BASE line → survives `finalize` → `apply_discounts` passes it to the
  law module. The bill-time refusal is gone. The arithmetic is the signed one (BR-RAT-068: a scoped
  discount is taken over the tariff lines in its scope; BR-RAT-962: a charge waiver is priceable);
  no new money rule, no ❄️ figure moved. A named code that can never be on a priced line (a fee)
  is refused at **Approve** (`discount_services._refuse_named_codes_off_the_tariff`, catalogue key
  `rating.discounts.named_code_not_priceable` in 11 languages).
* **Tests, red first:** `tests/test_def_rat_9327_named_codes_waiver.py` (6) — red with the
  `PricingRefused` above and `DID NOT RAISE DiscountRuleError`; green after.
  `test_def_502_discount_stage.py::test_def502_named_codes_scope_never_stops_the_bill` replaces the
  case that asserted the refusal. Golden `tests/golden` **25 passed + 1 xfailed** before (tip) and
  after; `03-golden-verify.py` **33 PASS / 0 FAIL** (document self-consistency).

### For the PO (not decided here)
* **May a waiver take a FEE off?** DEF-388's own example was *"waive the $45.00 connection fee"*
  ($45.00 + $59.00 water = $104.00 → $59.00). The engine never discounts fees (decision log
  2026-08-22, no signed rule), so today such a waiver is refused at Approve rather than silently
  taking $0.00 off.

### Seen, not filed by this lane
* 14 backend tests in the discount files are red on the tip **before** this change
  (`a8327b1ab`, re-run in a clean worktree): `test_cr013_discount_reads.py` (6),
  `test_cr013_discount_writes.py` (1), `test_cr048_b_engine_on.py` (3),
  `test_def2803_discount_row_parity.py` (1), `test_po_2026_08_31_discount_rulings.py` (2),
  `test_rep_p6w4_plans_and_discounts.py` (1) — row-shape drift, a route verb set, and a
  `2419.0002` vs `2419.0000` rounding; identical with and without this change.

### Register housekeeping done by this lane
`DEF-RAT-9318`, `9319`, `9325`, `9326` closed against `d74d243c6` / 2.481.6 (each fix checked
present on the tip first); `DEF-RAT-9289` closed (D11–D13 stored through the New form — walk steps
1 and 3, *31 values match*); `DEF-RAT-9321`/`9322` were already closed (`c8e5db53b`);
`DEF-RAT-9327` closed against `f722c6c3c` / 2.481.11. Commit `a8327b1ab` and the commit carrying
this section.

## Steps 7, 8, 10 and 11 — walked in the resume session (lane DISC-WALK, builds 2.481.6 → 2.481.10)

**How it was run.** The checkpoint's database was gone, so a fresh PostgreSQL 16 database
(`sbh_discwalk`: `migrate` + `seed_demo` + `cr166_discwalk_world.py setup`, which now also creates the
February 2027 `meter_reads` partition so a bill after the retire date can be run) and the built front end
on ports 8121/5221, Chromium at 1440, signed in as Dana. Steps 1, 4 and 5 were re-run only as far as the
later steps need (`PHASES=1,prep`, into a scratch folder so the checkpoint's photographs stand): nine
discounts saved through the New form; Senior, CAP, Autopay, Municipal, Lifeline and Veteran approved through
the screen; **the Lead line waiver left a draft** (`DEF-RAT-9327`, a sibling lane's) and Garden left a draft
(cannot go live, with the PO); Ruth enrolled on Senior and her proof verified, Pat on Veteran, Carl on CAP.
New ids in `walk/state.json` and `walk/world.json`. Checks: `walk/results.json` phases 7, 8, 10, 11 (**88
rows; 86 pass — the 2 fails are the red runs of DEF-RAT-9338 and DEF-RAT-9340 before their fixes**).
Server and database evidence: `walk/steps-8-10-11-server.txt`. Every photograph below was opened.

### Step 7 — Edit, three ways (PASS)

| Must be true | Screen | API | Database |
|---|---|---|---|
| **Name and details** — Autopay renamed *Autopay savings*, funding source changed: the same row | details page shows both (`discwalk_7_1_*`) | `name`, `funding_source` served | same `discounts.id`, still **v1**, value 0.50% untouched |
| **Senior 15% → 12% from 01/01/2027** | Review: *15% → 12%*, *−$9.00 → −$7.20* on $60.00, *v1 10/01/2026–12/31/2026 · v2 01/01/2027–No end*, *Bills before 01/01/2027 keep 15%.* (`discwalk_7_2_*`); header *Next: 12.00% from 01/01/2027* | today `15.00%`, `scheduled_next {12.00%, 2027-01-01}` | v1 15 % 10/01/2026–**12/31/2026**, v2 12 % **01/01/2027**–open; **nothing deleted** |
| **Fix a mistake** — Veteran typed 1.5 instead of 15, reason *Typed 1.5 instead of 15.* | Review and saved (`discwalk_7_3_*`) | serves `15.00%` | v1 1.50 % **kept**, status `superseded`, `superseded_by` → v2; v2 15 % `corrects` v1, **same dates**, reason stored |
| **Audit shows each** | Audit tabs (`discwalk_7_4_audit_{3,1,9}.png`, `discwalk_7_5_audit_rename.png`) | `discount.updated`, `discount.new_value`, `discount.correction_created` + `discount.version_corrected`, all *Dana Whitfield* | — |

**`DEF-RAT-9338` (fixed 2.481.7).** The rename was missing from the Audit: `update_discount` took its *before*
picture after the new code and name were on the object, so a rename alone wrote **no audit row at all** —
reproduced in the browser (a rename of Autopay at 10:11 left nothing). Now *Bill line label: Autopay discount
→ Autopay savings · Dana Whitfield* (`discwalk_7_5_audit_rename.png`). 🔒 file: review-ledger row written.
Pat's bills prove the correction reaches billing: **−$9.00** (15 % of $60.00) on every issued bill, never −$0.90.

### Step 8 — Billing gets exactly one version (PASS)

* **The read billing uses** (`rating.selectors.billable_discount_rules(account, plan, day)`): Ruth, SENIOR —
  12/25, 12/30, **12/31/2026 → one row, 15.00 %**; **01/01/2027**, 01/02, 01/15 **→ one row, 12.00 %**. In SQL,
  versions in force: 12/31/2026 **1**, 01/01/2027 **1**. (The world script's `lookup` called the read with the
  wrong arguments and printed nothing; corrected to pass the unit's plan.)
* **December run** (11/16–12/15/2026) and **January run** (12/16/2026–01/15/2027), each calculated **and
  issued** (`RUN-0001`, `RUN-0002`):

| Ruth Alvarez, $60.00 before discounts | Senior | Autopay (0.5 % of what is left) | Total |
|---|---|---|---|
| December `BL-2612-000001` | **−$9.00** | −$0.26 | $50.74 |
| January `BL-2701-000008` | **−$7.20** | −$0.26 | $52.54 |

* **The December bill still reads −$9.00** after the January run and after Senior was retired — re-read from
  the database and on screen (`discwalk_8_bill_2026-12-15_after_retire.png`).
* Other accounts on the same runs: Carl CAP −$10.00 (floor $50.00), Pat Veteran −$9.00, City Hall −$5.00
  (cap), Omar/Mia/Gail none. `discount_grants` rows: 0 (`DEF-2430`, known).

**`DEF-BIL-9339` (fixed 2.481.8).** On the bill's *Charges* tab Senior and Autopay were listed under
**TAXES & FEES** on a bill that charges no tax (`discwalk_8_bill_2027-01-15.png`). A whole-bill discount now
has its own **Discounts** group after the services (11 languages); display only
(`discwalk_8_bill_*_fixed.png`). The test that was *named* for exactly this asserted only a tag.

### Step 10 — Retire Senior on a date (PASS)

* More ▾ › **Retire**, last day **01/31/2027**, reason typed (`discwalk_10_1.png`). Stored: v2 now ends
  01/31/2027 (v1 untouched, nothing deleted); **Ruth's enrollment ended 01/31/2027, reason
  `discount_retired`**; Audit *discount.retired · Dana Whitfield* (`discwalk_10_3.png`).
* The read billing uses: 01/31/2027 one row (12 %); **02/01/2027 and 02/15/2027 none**.
* **February run** (01/16–02/15/2027, issued `RUN-0003`): Ruth `BL-2702-000015` — **no Senior line**,
  Autopay −$0.30, total $59.70 (`discwalk_8_bill_2027-02-15_after_retire.png`). December (−$9.00) and January
  (−$7.20) bills unchanged. (The bill is priced on its service date, 02/15; a bill ending on or before 01/31
  would still carry it — ruling 4, *after that date nobody gets it*.)

**`DEF-RAT-9340` (fixed 2.481.9).** The retire was stored and the dialog **stayed open with Retire still live**
(`discwalk_10_2.png`); *Send back* had the same miss. Both close on success now; walked again by retiring
Lifeline on 02/28/2027 (`discwalk_10_4_redo.png`).

### Step 11 — Utility B and the eleven languages (PASS)

* **Riverbend Water (Utility B)**, signed in as its own admin: Discounts list empty, *0 discounts*
  (`discwalk_11_b_list.png`); API list 0 rows; A's Senior by its id → **404** on the read, its accounts and its
  audit, and **404** on a retire write — A's Senior unchanged; A's address typed into B's browser → *We
  couldn't load this definition.* (`discwalk_11_b_direct.png`).
* **RLS in the database** — a throwaway `NOSUPERUSER NOBYPASSRLS` role inside a rolled-back transaction: no
  tenant set → 0 discounts; `app.tenant_id` = Riverbend → **0 discounts, 0 versions, 0 enrollments, 0 SENIOR**;
  = Brazos Bend → 9, 11, 5, 1. Nothing was left behind (the role was rolled back with the transaction).
* **Four screens × 11 languages** (list; New with code, label and 15 % typed; details Overview and Accounts;
  Edit › New value › Review on CAP), `discwalk_11_<screen>_<lang>.png`, 55 photographs: **no English left**
  in the screens' own words (the probe drops `<option>` text and the utility's own data — discount names,
  eligibility and program-owner list values, the street name — and accepts German *Details*/*Code* and French
  *Code*/*Type*, which are those languages' words); **no sideways scroll** (page 0px; list 1,120px in a
  1,120px box); **DEF-RAT-9319 holds** — Type never one character a line in ja/ko.
* **`DEF-RAT-9341` (fixed 2.481.10).** A per-word check (every word of every header, cell, label, button and
  tab measured with a `Range`; proved red with `FORCE_SQUEEZE=1`) found the list's **headers** split inside a
  word in Japanese and Korean — *プラ/ン, 登録/数, ステータ/ス* and *요금/제, 등/록* — once the list holds nine
  discounts. Every header word now stays whole; re-measured in all 11 languages: 55/55
  (`discwalk_11_list_ja-JP.png`, `..._ko-KR.png`). The photographs show build 2.481.9 in the frame; the fix is in them (built from the working tree) and ships as 2.481.10.

### Bugs found in the resume session

| Defect | Step | What the user saw | State |
|---|---|---|---|
| `DEF-RAT-9338` | 7 | a rename of a discount left no trace in its Audit | **fixed 2.481.7** (`b7172350c`), walked again |
| `DEF-BIL-9339` | 8 | a bill's discounts listed under *Taxes & fees* on a bill with no tax | **fixed 2.481.8** (`40ea3d0b4`), walked again |
| `DEF-RAT-9340` | 10 | Retire (and Send back) stayed open after it had worked | **fixed 2.481.9** (`6b10c77ab`), walked again |
| `DEF-RAT-9341` | 11 | ja/ko list headers broken inside a word | **fixed 2.481.10** (`d647df5f2`), walked again |

### Seen, not filed (for whoever owns them)
* The bill's *Document* tab breakdown reads *Charged to the bill −$9.26* for the two discounts, and *By
  service* names the row *Charged to the bill, not to a service · Discount* — the same grouping as
  DEF-BIL-9339 in a second panel, but the words are true (they are bill-level lines); left to Billing.
* The list's *To* column and the Overview's *Ends* show the **version in force** (Senior: 12/31/2026) while
  the discount runs on at 12 % to 01/31/2027; the header's *Next: 12.00% from 01/01/2027* and the versions
  table say so. Drawn that way (images 01, 19); not changed.
* `E11DrawingDiffWave3.dom.test.tsx` (bulk run *Sign off*) failed once inside the whole billing folder under
  load and passed alone twice — timing, not this lane's files.

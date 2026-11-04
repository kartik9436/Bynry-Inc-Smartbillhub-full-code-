# J70 — The one-time bill, redesigned (six kinds · Account · Services · Review · Send · E1–E11)

---
id: J70
tier: 2
rules: [BR-BIL-012, BR-BIL-013, BR-BIL-014, BR-BIL-018, BR-BIL-019, BR-BIL-020, BR-BIL-024, BR-BIL-300, BR-BIL-301, BR-BIL-410, BR-BIL-411, BR-BIL-1047, BR-BIL-1048, BR-RAT-088, BR-RAT-090, BR-RAT-1015, BR-RAT-1025]
stories: [US-BIL-010, US-BIL-011, US-BIL-012, US-BIL-013, US-BIL-014, US-BIL-032, US-BIL-033, US-BIL-034, US-BIL-035, US-BIL-005, US-MET-007, US-MET-010]
# ⚠ NOT ACTIVATED — no `J70.spec.ts`. Written 2026-09-30 as the HANDOFF CONTRACT BEFORE THE CODE
# (build plan `04-docs/05-modules/07-billing/12-one-time-bill-build-plan.md` R5, journeys E1–E11).
# The PO said "don't fix anything yet" the same day: nothing below is built. US-BIL-035 is BLOCKED
# on the B4.2 ❄ finance re-sign, so E6's taxed figure is asserted only after that re-sign.
# WALKED 2026-09-30 in a browser at 1440 and 1280 — `07-frontend/e2e/J70-one-time-bill.spec.ts`,
# seed `10-scripts/seed_j70_one_time_bill.py`; results in § WALKED 2026-09-30 at the foot of this file.
---

**Intent.** One page raises every bill that is not a cycle bill, in four one-word steps — PO
2026-09-30, verbatim: *"i need 1 word step name not 2 - and workflow should not be more than 3 or 4
steps"*. The journey proves the redesign the PO confirmed (*"this is all correct"*, *"this si
correct"*, *"rest is all corect"*, *"your drawing is correct now"*) as **numbers on a screen and on
a bill**: two water meters are two lines (**$58.40**, not **$29.20**), a missing base charge is
**$0.00 and a warning**, not a refused account; sewer bills with no service point; gas and fire
with no asset print **no line**; a service not taken is still visible to the clerk; every
problem on step 1 is shown at once, each on its own field; and a bill leaves only through a Send
the clerk has acknowledged, exactly once.

**Sources.** Design `04-docs/05-modules/07-billing/11-one-time-bill-redesign.md` · build plan
`12-one-time-bill-build-plan.md` (E1–E11) · decision log 2026-09-30 (nine rows) · the stories
above (EP-BIL-03, whose §AMENDED 2026-09-30 carries the `OTB` fixture and the open items OI-1…OI-7)
· drawing images `05-prototype/one-time-bill-2026-09-30/` (the E11 baseline). A figure drawn in the
mock-up is an illustration (B14 rule 37); the figures below are the rulings' and the fixture's.

## Preconditions — the seed (`OTB`; every E-case starts from it unless it says otherwise)

Tenant **Brazos Bend Utilities** (`brazos-bend`); isolation tenant **Lone Star Ridge WSC**. Actors
**Priya Menon** (Billing Clerk) and **Alex Reed** (System Admin). Clock **Wed 30 Sep 2026**.
Tax authority **8.25%**.

| Item | Seeded as |
|---|---|
| Account | **`AC-2026-00042` · Maria Alvarez · 1408 Elm St · Unit A** · Residential Standard · Active · balance **$142.18** · Monthly cycle, **21 days to pay** · last bill Aug 31, 2026 · agreements: water, electric, trash, sewer, gas, fire (**not** broadband) |
| **Water — 2 meters** | **W-10442** last read **482.3 kgal, Aug 31, 2026** (move-in read 479.8, Sep 12, 2026) · **W-10443** last read **130.6 kgal, Aug 31, 2026** (**no move-in reading on file**). Tiered **$3.25/kgal to 5 kgal, $4.50 above**; base **BASE-W $8.00**, bound |
| **Electric — no base charge code** | **E-55120** last read **18,420 kWh, Aug 31, 2026** (move-in read 18,500, Sep 12, 2026 — E2 only). Flat **$0.1245/kWh**. **No base charge code defined or bound** |
| **Trash — 1 cart** | 1 cart, 96 gal · **$15.00/cart**, base **BASE-T $3.00 per cart** |
| **Sewer — 40% of water** | **No sewer service point.** `BR-RAT-1015`: **40%** of the water quantity × **$5.0000/kgal** flat; base **BASE-S $6.00** |
| **Gas — no meter** | Account took gas; the unit has **no gas meter** |
| **Fire — no asset** | Account took fire; the unit has **no fire asset** |
| **Broadband — not taken** | Offered at the unit; the account did **not** take it |
| Charge codes | **RECON** Reconnection fee **$75.00, taxable** · NSF $30.00 · MTEST $40.00 · **TAMPER** Tamper charge **$250.00** (non-taxable) · **CONN** Connection charge **$25.00** |
| Deposit | Residential **$150.00**, **$0.00** paid |
| Reason codes | MISSED · METER-FAULT · THEFT · TAMPER |
| Price change (E4) | Water price version change effective **Jul 16, 2026** |
| Assessed reads (E5) | Committed, reason-coded *tamper-assessed*, for W-10442, W-10443, E-55120 for Jun, Jul, Aug 2026 |
| Second account (E9) | **`AC-2026-00043` · Dana Brooks · 1408 Elm St · Unit B** · Active · water **W-10450** (210.0 kgal, Aug 31), electric **E-55121** (9,800 kWh, Aug 31), 1 trash cart · **NO service agreements** |
| Search neighbours | Luis Alvarez `AC-2026-00117` · Alvarez Hardware LLC `AC-2026-00388` · Maria Alvarez `AC-2025-01904` (**Closed**) · Omar Haddad `AC-2026-00219` (**Pending**) |

## The journey

| # | Actor · action · screen | Expected result (what this step leaves) | Downstream assertions | Rule · story |
|---|---|---|---|---|
| **E1.1** | Priya opens **Billing › Bills › One-time bill** | Six kind cards **Interim · First bill · Final · Catch-up · Penalty / theft · Fee**; rail **Account · Services · Review · Send** | The door from the Bills screen opens THIS page (hold-expiry test, build plan T6) | US-BIL-012 TC-7 |
| **E1.2** | **Interim**; types **Alvarez** in *Find account* | Four options, each *name · status · account no. · address*, *Alvarez* highlighted; ↓ Enter picks *Maria Alvarez · AC-2026-00042* | Result card: **1408 Elm St · Unit A · Residential Standard · Active · $142.18 · Monthly · 21 days · Aug 31, 2026**; the search was one paginated `GET /accounts?q=` page; no id visible | US-BIL-034 TC-1, TC-5, TC-8 |
| **E1.3** | Step 1: period **Sep 1 – Sep 30, 2026**; bill date left at **Sep 30, 2026**; days to pay left at **21** → Continue | Due date shown **Oct 21, 2026**, read-only | The request carries `bill_date` and `due_days` | US-BIL-012 TC-8 |
| **E1.4** | Step 2 — **Services** (open) | **Water** *Billed · 2 meters* · **Electric** *Billed · base $0.00* ⚠ · **Trash** *Billed · 1 cart* · **Sewer** *Billed · follows water* · **Gas** *Not in service* (no line · $0) · **Fire** *Not in service* (no line · $0) · **Broadband** *Not taken*; header **4 billed · 2 not in service · 1 not taken**; warning *No base charge for Electric. Billed $0.00.* | The preview is NOT refused (today gas `no_meter` refuses the account) | US-BIL-012 TC-9, TC-13, TC-16, TC-17 |
| **E1.5** | **Rates** (open, collapsible) | Rows: Water · W-10442 and Water · W-10443 (Tiered, **$8.00 · BASE-W** each) · Electric · E-55120 (Flat $0.1245, **Not set · $0.00** ⚠) · Trash · 1 cart ($15.00, **$3.00 per cart**) · Sewer (40%, **$6.00 · BASE-S**) · Gas / Fire *No rate used* $0.00; Amount column fully visible | Each row names its price version | US-BIL-012 TC-10 |
| **E1.6** | **Readings**: W-10442 **488.4**, W-10443 **136.7**, E-55120 **19,020**, new read date **Sep 30, 2026** | Three rows only; usage **6.1 kgal · 6.1 kgal · 600 kWh**; each *Accepted* | Three posted readings in Meter Reads, one `/read-batches` batch, dated Sep 30; billing wrote none | US-BIL-012 TC-11 · US-MET-007 · US-MET-010 |
| **E1.7** | Continue → **Review** | One group **Sep 1 – Sep 30**: Water W-10442 Usage 6.1 kgal **$21.20** · Base **$8.00** · Water W-10443 Usage 6.1 kgal **$21.20** · Base **$8.00** · Electric Usage 600 kWh **$74.70** · Electric Base **$0.00** (*No base set*) · Trash Per cart **$15.00** · Trash Base per cart **$3.00** · Sewer 40% of water 4.88 kgal **$24.40** · Sewer Base **$6.00** → subtotal **$181.50** *(sewer under OI-2's reading)*; then Tax (one B4.2 pass) and Total; no gas, fire or broadband line | Water total **$58.40** (today **$29.20**); sewer never `$0.00 not connected` | US-BIL-012 TC-12, TC-15, TC-18 · decision log 2026-09-30 |
| **E1.8** | Delivery **Email**; **Save draft** | Draft saved, no bill number | Reopening the page returns to this Review | US-BIL-033 TC-10 |
| **E1.9** | Continue → **Send** | Total, **Due Oct 21, 2026**, the warning, *Final once sent. Changes need a credit note.*, unticked *I checked the amounts*; **Send disabled** | `POST …/send` without the acknowledgement → refused, still a draft | US-BIL-033 TC-1, TC-4 |
| **E1.10** | Ticks the box; presses **Send** twice quickly | **Bill … sent** · Due **Oct 21, 2026** · *Delivery · Email · queued* · *Meter reads · Locked* · **View bill** | **One** invoice, one number, one balanced journal entry, one delivery row, one `audit_log` row; **View bill** shows two water lines | US-BIL-033 TC-3, TC-5, TC-8, TC-12 |
| **E2** | **First bill** for `AC-2026-00042` (fresh seed) | Step 1: *From* prefilled **Sep 12, 2026**, *To* Sep 30, due Oct 21. Step 2 order **Services → Rates → Move-in charges → Readings**. Readings: W-10442 previous = move-in **479.8**; **W-10443's move-in cell is an input** — Continue disabled until Priya types **128.9**; new readings W-10442 **488.4** (8.6 kgal), W-10443 **136.7** (7.8 kgal), E-55120 from move-in **18,500** to **19,020** (520 kWh). Move-in charges: **Deposit $150.00 − $0.00 = $150.00** · **CONN $25.00** | Review: group **Move-in charges** subtotal **$175.00**, both non-taxable, deposit → deposit liability; base charges **whole** (water $8.00 per meter, trash $3.00, sewer $6.00 — `BR-BIL-1047`); Send → one invoice | US-BIL-010 TC-8…TC-12 |
| **E3** | **Final** for `AC-2026-00042`, move-out **Sep 18, 2026** (fresh seed; deposit $150.00 held 14 months at 2%) | *To* = **Sep 18, 2026**; readings: previous = last billed **482.3 / 130.6 / 18,420**, new read date **Sep 18, fixed**; each **final reading required**. Settlement box: *this bill + $142.18 − $150.00 − $3.50* = its result; Priya chooses **Collect** | Base × 18/30: water **$4.80** per meter, trash **$1.80**, sewer **$3.60**; group **Sep 1 – Sep 18**; Send disabled until a path is chosen; one invoice, path recorded | US-BIL-011 TC-9…TC-13 |
| **E4** | **Catch-up**: periods **Jun, Jul, Aug 2026**; reason **MISSED** (fresh seed) | No from/to field; readings per meter per period — only **Aug** takes typed readings; **W-10443 July has no read → estimated**, tagged *Estimated*; Periods table shows **July split 15/31 · 16/31** across the Jul 16 price change, day-weighted | Review: groups **Jun 2026 · Jul 2026 · Aug 2026** each with its subtotal; two water lines per period; tax once over the bill; Send waits on approval if the tenant's mode requires it | US-BIL-013 TC-12…TC-18 |
| **E5** | **Penalty / theft**: periods Jun–Aug 2026, reason **TAMPER**, charge **TAMPER** (*Tamper charge · $250.00*, amount read-only), evidence *Bypass pipe found at meter W-10442* | Readings **read-only**, tagged **Assessed**; *Reading needed · Not needed*; Review adds **Other charges: TAMPER $250.00**, non-taxable; the evidence prints on the bill | Ticked Send **before approval → refused**, no number minted; **Alex Reed approves**; Send → one invoice typed `penalty` | US-BIL-014 TC-8…TC-13 · US-BIL-033 TC-6 |
| **E6** | **Fee**: charge code **RECON** (*Reconnection fee · $75.00*, read-only), note *Reconnected Sep 30 after payment* | Step 2 shows only the Charge panel — no services, no readings; Review group **Charges**: RECON **$75.00** | **Today, and until the B4.2 ❄ re-sign: total $75.00, no tax line.** ⛔ **BLOCKED step E6b — after the re-sign only:** tax **$6.19**, total **$81.19** (US-BIL-035); a non-taxable NSF fee stays **$30.00**. Send → one invoice, `bill_type = fee` | US-BIL-032 TC-1…TC-4 · **US-BIL-035 (blocked)** |
| **E7** | **Problems**: Interim with *To* **Aug 20, 2026** and *Days to pay* empty → Continue; then Catch-up with no reason and a period row **Aug 31 → Aug 1** | Banner **Fix 2 things to continue.**; *Ends before it starts.* under *To* and *Enter days to pay.* under *Days to pay*; the Catch-up pair likewise each on its own field | One API response lists every problem with its field and its own catalogue key; no "billing run" sentence, no "cycle" | US-BIL-012 TC-19 · US-BIL-013 TC-17 |
| **E8** | **Already billed**: after E1, a second clerk starts **Interim** for **`AC-2026-00042`, Sep 1–30, 2026** — the same account, kind and period | Banner **Already billed for this period.** with E1's bill number, its date, who sent it, and **Open that bill** | No second bill can be sent for that account, kind and period | US-BIL-012 TC-20 |
| **E9** | **No agreements**: Interim for `AC-2026-00043` (Dana Brooks), W-10450 **215.0**, E-55121 **10,200** | Water, electric and trash are all billed; a warning says the account holds no service agreements | The bill completes and sends | US-BIL-012 TC-22 |
| **E10** | **Reading below the last one**: Interim for `AC-2026-00042`, W-10442 new reading **480.0** (last **482.3**) | That row: **Below last reading**, refused on the row; **Continue disabled** | Nothing posted to Meter Reads; no draft | US-BIL-012 TC-21 |
| **E11** | **Screenshot diff** — every state above at **1440** and **1280** | Each capture compared with its D1 image in `05-prototype/one-time-bill-2026-09-30/` (states 01–37) against the UI skill's §4 checklist; figures are NOT compared (rule 37) and the Rates table's Amount column must NOT be clipped (the drawing's known flaw) | Differences in arrangement are defects; spacing and type follow our UI standard (B14 rule 44) | B14 rules 37, 42, 44 |
| **ISO** | Lone Star Ridge's clerk: search **Alvarez**; preview with Brazos Bend's account id; `POST …/send` with Brazos Bend's run id | Only Lone Star Ridge accounts; `404`; `404` | Nothing of Brazos Bend's read or written | hard rule 1 · US-BIL-034 TC-9 · US-BIL-033 TC-11 |
| **INV** | — | — | Every issued bill immutable (hard rule 4); every reading written by Meter Reads, none by billing; no free-typed amount on any bill (BR-BIL-020); every send audited once | hard rules 4, 6, 7 |

## Open items this journey does not decide

The epic's OI table (EP-BIL-03 §AMENDED 2026-09-30): **OI-1** the drawing's sewer arithmetic is the
superseded dollars reading — build to `BR-RAT-1015`; **OI-2** sewer's basis over two water meter
lines (E1.7's **$24.40** is under the whole-quantity reading); **OI-3** reason codes per kind; **OI-4**
which account statuses may be picked per kind; **OI-5** where evidence photos live; **OI-6** the rule
rows and review-gap defects not yet stamped; **OI-7** fee tax — E6b. The first bill's usage DOLLARS
are not asserted (US-BIL-010 §8: whether tier spans scale on a one-time first bill).

**This journey leaves (for downstream).** Six issued one-time bills on `AC-2026-00042`'s fresh seeds
(interim, first, final, catch-up, penalty, fee) and one on `AC-2026-00043`, each with exactly one
number, one balanced entry and one delivery row; every typed reading posted in Meter Reads; one
refused draft attempt (E8) and one refused reading (E10) that left nothing behind.

## WALKED 2026-09-30 — E1–E11 in a browser, 1440 and 1280

Stack: PostgreSQL 16, `manage.py migrate` + `seed_demo` + `10-scripts/seed_j70_one_time_bill.py`, Django
(`config.settings.local`), the built SPA behind `server.mjs`; Chromium from `/opt/pw-browsers`. Spec
`07-frontend/e2e/J70-one-time-bill.spec.ts` (database reset from the seeded template before each viewport).
Screens: `08-qa/screens/one-time-bill-e2e-2026-09-30/` (named after the D1 image of the same state).
The same result at both widths. Build 2.411.5 (after the fixes below; the commits say 2.411.3, which another branch took first — re-bumped).

| Case | Result | What decided it |
|---|---|---|
| E1 Interim | **FAIL** | Step 1 cannot reach step 2 until the readings exist (`DEF-BIL-8300`); with them saved through Meter Reads the rest passes: water 2 meters · electric *Billed · base $0.00* + warning · sewer *follows Water* · gas / fire *Not in service* · broadband *Not taken* · subtotal **$181.50** (water **$58.40**) · Send locked until ticked · Sent. The issued bill names no meter on its lines (`DEF-BIL-8315`) |
| E2 First bill | **FAIL** | `DEF-BIL-8300` only; move-in reading saved, Deposit $150.00 + CONN (seed_demo's $45.00), sent. Fixed on the way: blank read-only move-in date (`8309`), CONN code missing (`8314`) |
| E3 Final | **FAIL** | `DEF-BIL-8300`, then Send refused for the $150.00 deposit's interest (`DEF-BIL-8313`). Settlement box right (refund due; no path offered — the seed has no $142.18 prior balance) |
| E4 Catch-up | **FAIL** | Preview answers 500 (`DEF-BIL-8310`, `backbill._estimate_read_less_segments`) |
| E5 Penalty | **FAIL** | Same 500 (`DEF-BIL-8310`); no *Approved by* control on the page (`DEF-BIL-8305`) |
| E6 Fee | **FAIL** (minor) | B7 landed: RECON taxed once (the seed's Local 2.00% applies; seed_demo scopes State 6.25% to commercial, so not J70's 8.25%) and sent; the line does not name RECON (`DEF-BIL-8312`) |
| E7 Problems | **PASS** | *Fix 2 things*, each on its field; catch-up's reason and period; fee's charge code |
| E8 Already billed | **PASS** | Banner with BL-2609-000001, date, clerk, *Open that bill* |
| E9 No agreements | **FAIL** | `DEF-BIL-8300` only; warning *No services on file. Billed all connected.*, water/electric/trash billed, sent |
| E10 Below last | **FAIL** | The row is unreachable (`DEF-BIL-8300`); Meter Reads itself refuses 480.0 after 482.3 at validate, nothing posted |
| E11 Drawing | **FAIL** | `DEF-BIL-8315` (review tier-by-tier lines, base with no quantity/rate, trash wording) · `DEF-BIL-8316` (step-2 order and wording). Also seen: invalid fields not tinted; result card 3 columns (drawing 4); already-billed stops at step 1 under the frame's generic *This step isn't finished* line (drawing shows it over step 2) |

Fixed during the walk (2.411.5): `DEF-BIL-8301`, `8302`, `8303`, `8304`, `8307`, `8308`, `8309`, `8314`.
`DEF-BIL-8306` invalid (the first seed had no router on the unit). Fixture differences from the `OTB`
table: account numbers are allocated (AC-2026-00001 …), one unit per kind, class `institutional` (so
seed_demo's residential `BASE-E` does not apply), no $142.18 balance, CONN $45.00.

## RE-WALKED 2026-09-30 (later) — E1–E11 and the PO's scenarios P1–P6, 1440 and 1280, build 2.411.7

Same stack as above on a FRESH database (migrate + `seed_demo` + the seed, which now also builds
**Unit G** — Omar Grant, no move-in date — and **Unit H** — John Robert, meters read only to Jun 30),
reset from its template before each width. **Every reading is typed on step 2**; the `/read-batches`
workaround is gone from the spec. After every Continue the spec checks that the frame's generic
*"This step isn't finished"* line never stands alone (`DEF-BIL-8321`). **The same result at both
widths: 11 PASS, 4 FAIL (15 cases).** Screens: `08-qa/screens/one-time-bill-e2e-2026-09-30/` (`E10-…`, `P4-…`,
`P5-…`, `P6-…` are new).

| Case | Result | What decided it |
|---|---|---|
| E1 / P1 Interim, no reading in the period | **PASS** | Card fills on selection (Plan, *21 days to pay*, Last bill); step 1 warns *3 meters need a reading. Enter them next.* and goes on; readings typed on step 2 (*Accepted*); Services *2 meters · W-10442, W-10443* / *Billed · 2 meters* / *Billed · 1 cart*, catalogue order; Rates *$3.25 / kgal*, *$8.00 · BASE-W*, *Per asset*; Review *Interim bill · draft*, W-10442 *Usage 6.1 kgal Tiered $21.20*, *Base 1 $8.00*, trash one *Per cart* line (PO *"per service"*); sent, reads locked |
| E1b Issued bill | **PASS** | Water $58.40; each water line names W-10442 / W-10443 |
| E2 / P3 First bill, move-in date changed | **PASS** | Move-in pre-filled Sep 12, changed to Sep 13 → *Differs from the account (09/12/2026)*; move-in reading typed on step 2 and saved before the new one (`DEF-BIL-8325`); Move-in charges with Deposit and CONN dated Sep 13; sent |
| E3 / P2 Final, no reading in the period | **FAIL** | Steps 1–3 pass (warning, final readings typed, settlement *Refund due*); **Send refused by the books**: the $150.00 deposit exceeds the $103.67 closing position and nothing signs where the refund sits — **`OQ-248`** (open, the PO's). `DEF-BIL-8313` (interest with no date) is fixed: the refusal is now the ledger's, one step later |
| E4 Catch-up Jun–Aug | **FAIL** | `DEF-BIL-8310` fixed (no 500). Refused by name on step 1: *Water can't be priced* — W-10443E has no read in July, so the Jul 1–15 segment cannot be day-weighted (**`DEF-BIL-8324`**, open) |
| E5 Penalty Jun–Aug | **FAIL** | `DEF-BIL-8310` and `DEF-BIL-8323` fixed; step 2 reached; *Approved by* picked (Dana Whitfield), no *Needs approval* sentence (`DEF-BIL-8305`); **Send refused: the bill is dated Aug 31, inside the CLOSED fiscal period August** (BR-LED-006) — the seed closes August; not a one-time defect |
| E6 Fee | **PASS** | Review line *Fee · RECON* (`DEF-BIL-8312`); taxed; sent |
| E7 Problems | **PASS** | *Fix 2 things*; each on its field; the fields are tinted (`DEF-BIL-8317`) |
| E8 Already billed | **PASS** | The banner stands over **step 2** with the services below it (`DEF-BIL-8319`) |
| E9 No agreements | **PASS** | Readings typed on step 2; warning; sent |
| E10 Below last | **PASS** | 480.0 after 482.3 → row *Below last reading*; Continue stays on step 2; nothing posted |
| E11 Drawing | **PASS (with two stated differences)** | `DEF-BIL-8315`, `8316`, `8317`, `8318`, `8319` closed. Differences kept on purpose: services in the CATALOGUE order (Electric first; the drawing draws Water first — the coordinator's instruction); the price-version cell reads *Water · from 07/16/2026* (rating stores no ordinal to print *Water v4*) |
| P4 First bill, account with NO move-in date | **PASS** | Plan and *21 days to pay* shown; only the move-in field asks: *Enter the move-in date.* under it and in the list, tinted; the list item focuses it |
| P5 Catch-up Jul–Sep, no readings at all | **FAIL** | Refused by name on step 1 (*Water can't be priced*), no generic line — **`DEF-BIL-8324`** |
| P6 Penalty with the PO's overlapping periods | **PASS** | *Overlaps another period.* on row 1's From and in the list (`DEF-BIL-8322`) |

Fixed in 2.411.7: `DEF-BIL-8281`, `8282`, `8300`, `8305`, `8310`, `8312`, `8313`, `8315`–`8323`, `8325`.
Open: `8311` (G53 glob — with the PO), `8324` (a catch-up sub-period nobody read — needs a ruling),
`OQ-248` (where a final bill's refund sits in the books).

## RE-WALKED 2026-09-30 (evening) — build 2.412.2, 1440 and 1280: 15 OF 15 PASS

A fresh PostgreSQL 16 database (migrate, `seed_demo`, then the J70 seed), reset from its template
before each width. Three rulings are now built: OQ-248 option A (a leftover deposit is refunded),
DEF-BIL-8324 option A (a catch-up stretch nobody read), and the Send card's five confirmations
(option B). **Result at both widths: 14 spec tests, covering the 15 cases below, all pass.**
Every Send ticks the five confirmations, and Send stays off until the fifth is ticked.

The test data changed, and the product did not change for it. `seed_demo` closes August, so a bill
dated 31 August is refused by the books. E4 and E5 therefore bill July–September. Unit F gets
September readings. Every seeded reading now records its day count and start day, as a real posting
does.

| Case | Result | What decided it |
|---|---|---|
| E1 / P1 Interim, no reading in the period | **PASS** | as before |
| E1b Issued bill | **PASS** | as before |
| E2 / P3 First bill, move-in date changed | **PASS** | as before |
| E3 / P2 Final, no reading in the period | **PASS** | Settlement: deposit **−$150.00** against a **$103.67** bill, ***Refund due $46.33***. Send succeeds, and the leftover goes to customer credit (OQ-248 A). |
| E4 Catch-up Jul–Sep | **PASS** | July splits at 07/16. With nothing typed yet, step 2 prices on the meters' own estimates, marked *Estimated*. The typed September readings are then shared across the stretch they measured. The bill sends at **$710.06**. |
| E5 Penalty Jul–Sep | **PASS** | Approver recorded; the bill is dated in September and is sent |
| E6 Fee | **PASS** | as before |
| E7 Problems | **PASS** | as before |
| E8 Already billed | **PASS** | as before |
| E9 No agreements | **PASS** | as before |
| E10 Below last | **PASS** | as before |
| E11 Drawing | **PASS** (the same two stated differences) | as before |
| P4 First bill, no move-in date | **PASS** | as before |
| P5 Catch-up Jul–Sep, no readings at all | **PASS** | Step 1 waits for the readings instead of refusing. The three readings typed on step 2 are shared by days. Sent. |
| P6 Penalty, overlapping periods | **PASS** | as before |

Closed in 2.412.2: `DEF-BIL-8324`. `OQ-248` was closed by the PO's ruling and is now built. Open:
`DEF-BIL-8326`, the back-bill test fixture that cannot price, which hides the engine suites.

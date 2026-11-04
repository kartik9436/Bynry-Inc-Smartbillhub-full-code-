# EP-BIL-03 — Bill types: first · final · ad-hoc single · back-bill · penalty

**Module:** billing · **Wave:** W3 (first/final/ad-hoc) + W5 (back-bill/penalty — share the corrections approval gate) · **Screens:** S30 (One-time bill tab), S31 (single-account mode), S20 (final-bill trigger, customers-owned) · **Status:** draft (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08)

## Scope
**In:** the non-cycle `invoices.bill_type` set (r10 #12): **first** (proration from move-in + one-time deposit/connection lines, BR-BIL-012), **final** (immediate at move-out, billed through the move day, deposit+interest auto-apply, then exactly ONE of the five settlement paths, BR-BIL-013), **single/ad-hoc** (the bulk wizard in single-account mode, rules/charge-code lines only, BR-BIL-020), **back-bill** (arbitrary past period priced per sub-period on the tariff version in force THEN, capped by tenant setting, theft exempt, BR-BIL-018), **penalty/theft** (charge-code lines only; unmetered consumption enters as assessed reads that back-billing prices, BR-BIL-019). Rebill (`bill_type=rebill`) belongs to EP-BIL-04.
**Out:** the move-out wizard itself (US-CUS-005 — leaves the BR-CUS-031 handoff this epic consumes) · deposit collection/interest engine (US-CUS-007/023) · refund execution, payment plans (payments) · assessed-read data entry (metering path, reason-coded — consumed here) · correction workflow (EP-BIL-04) · budget bills (EP-BIL-05).
**Amended 2026-09-30:** **fee** (a bill whose whole content is one charge code, BR-BIL-410 — US-BIL-032, its tax US-BIL-035) joins the set, and every kind is raised through ONE redesigned screen — six kind cards, then **Account · Services · Review · Send** — with its own Send (US-BIL-033) and account search (US-BIL-034); see §AMENDED 2026-09-30 below.
**Tables:** `invoices` (+bill_type), `invoice_lines`, balance-transfer transaction + master-account designation (r10 #10), write-off support (r10 #11).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens owned — bill types render in the S30 list (EP-BIL-07) with their bill_type filter)* | | | | | | | |

## ⚠ AMENDED 2026-09-30 — THE ONE-TIME BILL REDESIGN (applies to US-BIL-010 … US-BIL-014 and US-BIL-032 … US-BIL-035)

**Sources, read in this order:** the PO-confirmed design `../11-one-time-bill-redesign.md` · the build plan `../12-one-time-bill-build-plan.md` (tasks R/D/B/A/DB/F/T/E) · the nine 2026-09-30 rows at the top of `12-governance/02-decision-log.md` · the drawing images `05-prototype/one-time-bill-2026-09-30/` (index `README.md`). **Build the screen from the IMAGES, not from this text** (B14 rule 42; PO 2026-09-30, *"all screeen sin product should be completed using images of drawing and not text/contnet, and use uI skills"*). A figure drawn in the mock-up is an ILLUSTRATION (B14 rule 37) — the figures these stories assert are the rulings' worked figures and the `OTB` fixture below, never the drawing's.

**What the PO said, verbatim, 2026-09-30:** *"i need 1 word step name not 2 - and workflow should not be more than 3 or 4 steps"* · *"this si searchable dropdown"* · *"can you improve the Charge - maybe make it table"* · *"services , Rates, Move-in charges { deposites + fees} - they should be in this order and then readings - can you make services , Rates, Move-in charges { deposites + fees} - collapable/expand"* · *"on step 2 - you ahve to show - rates for each service or meter as a sepearte table"* · on the whole design *"this is all correct"*, *"this si correct"*, *"rest is all corect"*, *"your drawing is correct now"* · and *"don't fix anything yet"* — so **nothing below is built**; the stories are the contract written before the code (build plan R5).

**What it supersedes in this epic:** the S30 One-time tab flow *"pick the account + period → preview → exceptions → draft → issue"* (US-BIL-012 §1) and the four-value *"Kind select (interim/final/catch-up/deposit)"* (US-BIL-012 §5). It replaces the live `OneTimeBillTab.tsx` flow and the unfinished three-step `OneTimeWizardShell`. It is MAINTENANCE (a live screen redrawn end to end — `12-governance/22-product-maintenance-process.md`), borrowing Build's drawing step.

### The flow — six kind cards, then four one-word steps

| # | Step | Content |
|---|---|---|
| 0 | kind cards | **Interim** · **First bill** · **Final** · **Catch-up** · **Penalty / theft** · **Fee** |
| 1 | **Account** | Searchable dropdown (US-BIL-034), then the kind's fields (table below) |
| 2 | **Services** | **Services → Rates → Move-in charges (first bill only) → Readings →** then Periods / Settlement / Evidence / Charge as the kind needs. Services, Rates and Move-in charges are collapsible and OPEN by default. **Rates** is one row per meter or billed service: rate type · usage rate · base charge (code, or *Not set · $0.00* ⚠) · minimum · price version (per period, with the split, for catch-up and penalty) · amount; a service not in service reads *No rate used*, $0.00. Live total in the side panel |
| 3 | **Review** | The bill as it will print, as a **table**: Service · Meter / asset · Charge (Usage, Base, Per cart, % of water, Deposit, Fee) · Quantity with unit · Rate · Amount; rows **grouped by period** (one group per missed period for catch-up and penalty; *Move-in charges* and *Other charges* as their own groups), each group with its subtotal; then Subtotal, Tax, Total; warnings; Delivery; **Save draft** |
| 4 | **Send** | Total, due date, warnings, *"Final once sent. Changes need a credit note."*, the tick box *"I checked the amounts"* that unlocks **Send**; then the Sent state — bill no., due date, delivery queued (US-BIL-033) |

Also drawn and required: a **Problems state** (every step-1 problem at once, each on its own field, with a count banner) and an **Already-billed state** (who billed this period and when, the bill number, a link to it).

### Step 1 fields by kind (design §2)

| Field | Interim | First | Final | Catch-up | Penalty | Fee |
|---|---|---|---|---|---|---|
| Account | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Period from / to | ✔ | ✔ (from = move-in date, prefilled) | ✔ (to = move-out date) | — | — | — |
| List of missed periods | — | — | — | ✔ (add rows) | ✔ (add rows) | — |
| Reason code — dropdown from Settings | — | — | — | ✔ | ✔ | — |
| Bill date — required, defaults to today | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Days to pay — defaults from the account's cycle | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Due date — shown, derived from the two above | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Charge code — dropdown, amount read-only | — | — | — | — | ✔ optional | ✔ required |

### The services decision table (design §3 + the 2026-09-30 rulings)

| Service | Status badge | On the bill | Ruling (PO verbatim, 2026-09-30) |
|---|---|---|---|
| Metered, meter present, reading entered | Billed | Usage + base | — |
| Counted (trash, fire) | Billed · *n* cart(s) | *n* × (rate + base) — **base per asset** | *"B. Base per cart: 2 × ($15.00 + $3.00) = $36.00"* |
| Sewer (`%`-of-service) | Billed · follows water | `%` line + base, **no service point** | *"for % of service there will not be any service point"* (option B) |
| Service with no asset (gas no meter, fire no asset) | Not in service | **No line, $0**; the bill completes | *"this is correct sewer is exception becuase it is % of servcie"* · *"sane no line - and use 0"* |
| Service the account did not take | Not taken | No line; the clerk still sees it on the Services table | *"this si correct … rest is all corect"* |
| No base charge defined and bound | Billed · base $0.00 ⚠ | Usage + **$0.00 base**, a warning, the bill completes | *"as a default you take 0 and complete the bill instead of refusing"* |
| Two meters on one metered service | Billed · 2 meters | **One line per meter, each with its own tiers and base** | *"both meter should be build in metered case also - as a speearte line"* |
| Account holding no service agreements | (every connected service) | Every connected service billed **and a warning** | *"C. The bill still goes out, and the clerk sees the gap and can fix the account."* |

Base-charge CONFLICTS, where the utility did define something, stay **refusals** (decision log 2026-09-30, reading taken under law 13): two base codes both apply · one code states an amount AND sizes · a sized code with no price for this size · the connection's size not recorded. A metered service WITH a meter and no reading is still a real missing read.

**Rules for every kind (design §4):** a reading is saved through Meter Reads (`/read-batches`: stage → validate → post), never by billing · a multi-register meter links to the full readings screen · no reading row for a service with no meter, a counted service or sewer · estimated and assessed reads are tagged on screen AND on the bill.

### The shared fixture — `OTB` (every redesign TC in this epic and journey `J70` use it)

Tenant **Brazos Bend Utilities** (`brazos-bend`); isolation tenant **Lone Star Ridge WSC**. Actors: **Priya Menon** (Billing Clerk), **Alex Reed** (System Admin — approver). Clock: **Wed 30 Sep 2026**.

* **Account `AC-2026-00042` · Maria Alvarez · 1408 Elm St · Unit A** · Residential Standard · Active · balance **$142.18** · cycle Monthly, **21 days** to pay · last bill Aug 31, 2026. Agreements held: water, electric, trash, sewer, gas, fire — **not** broadband.
* Unit A's assets: water meter **W-10442** (last read **482.3 kgal on Aug 31, 2026**; move-in read 479.8 on Sep 12, 2026) · water meter **W-10443** (last read **130.6 kgal on Aug 31, 2026**; **no move-in reading on file**) · electric meter **E-55120** (last read **18,420 kWh on Aug 31, 2026**) · **1 trash cart, 96 gal** · **no gas meter** · **no fire asset** · broadband offered, not taken. **No sewer service point.**
* Rates (the tenant's own fixture values — not signed law): water tiered **$3.25/kgal to 5 kgal, $4.50/kgal above**, base code **BASE-W $8.00** bound · electric flat **$0.1245/kWh**, **no base charge code defined or bound** · trash **$15.00 per cart**, base **BASE-T $3.00 per cart** · sewer per `BR-RAT-1015` (quantity × sewer's own flat rate): factor **40%** (fixture; the seeded default is 90%), **$5.0000/kgal**, base **BASE-S $6.00**, no minimum.
* Charge codes: **RECON Reconnection fee $75.00, marked taxable** · NSF $30.00 · MTEST $40.00 · **TAMPER Tamper charge $250.00** (fee, non-taxable) · **CONN Connection charge $25.00**. Deposit category Residential **$150.00**, **$0.00** already paid. Tax authority **8.25%**.
* Reason codes (Settings): MISSED *Missed billing cycle* · METER-FAULT *Meter fault found* · THEFT *Theft of service* · TAMPER *Meter tampering*.
* Second account **`AC-2026-00043` · Dana Brooks · 1408 Elm St · Unit B** · Active · connected for water (meter **W-10450**, last read 210.0 kgal on Aug 31, 2026), electric (meter **E-55121**, last read 9,800 kWh on Aug 31, 2026) and 1 trash cart · **holds NO service agreements** (an older import).
* Search neighbours (US-BIL-034): Luis Alvarez `AC-2026-00117` 22 Birch Ct (Active) · Alvarez Hardware LLC `AC-2026-00388` 900 Main St · Suite 2 (Active) · Maria Alvarez `AC-2025-01904` 61 Oak Ave (**Closed**) · Omar Haddad `AC-2026-00219` 14 Elmwood Dr (**Pending**).

**The interim worked bill — Sep 1–30, 2026; bill date Sep 30; 21 days → due Oct 21, 2026:**

| Line | Figure | Where the figure comes from |
|---|---|---|
| Water · W-10442 · 482.3 → 488.4 = 6.1 kgal | usage 5 × $3.25 + 1.1 × $4.50 = **$21.20** + base **$8.00** = **$29.20** | ruling 2026-09-30 (two meters), its own worked figure |
| Water · W-10443 · 130.6 → 136.7 = 6.1 kgal | **$21.20** + **$8.00** = **$29.20** | same — water total **$58.40** (today's code bills **$29.20**) |
| Electric · E-55120 · 18,420 → 19,020 = 600 kWh | 600 × $0.1245 = **$74.70** + base **$0.00** ⚠ | fixture rate · ruling (base $0.00 + warning) |
| Trash · 1 cart | $15.00 + $3.00 = **$18.00** (2 carts: **$36.00**) | ruling 2026-09-30 (base per cart) |
| Sewer · no service point | 40% × 12.2 kgal = 4.88 kgal × $5.00 = **$24.40** + base **$6.00** = **$30.40** | `BR-RAT-1015` arithmetic; the 12.2 kgal basis is **OI-2** |
| Gas (no meter), Fire (no asset) | **no line, $0** | ruling 2026-09-30 |
| Broadband | **no line**, shown *Not taken* | design §3 |
| **Subtotal before tax** | **$181.50** | the sum above; tax is B4.2's one pass, owned by US-BIL-008's tests and not re-derived here |

### Open items — NOT chosen here (prime directive: not in the sources, so no story decides them)

| # | Item | What the stories do meanwhile |
|---|---|---|
| **OI-1** | **The drawing's sewer arithmetic is the SUPERSEDED one.** The mock-up prints *"40% of water · $35.18 → $14.07"* (40% of water DOLLARS), and the 2026-09-30 decision row's *"$76.50 a month … (40% of its water usage charge)"* reads the same way. `BR-RAT-015` (dollars) was SUPERSEDED 2026-09-08 by `BR-RAT-1015` (a % of the water QUANTITY priced on sewer's own rate, ❄ re-signed). | Build to `BR-RAT-1015` — it is signed; the drawing's figure is an illustration (rule 37). Not a question for the PO; recorded so nobody copies the drawing. The decision row's wording is for the records lane to stamp |
| **OI-2** | **Sewer's basis when water is two meter lines.** Neither the ruling nor `BR-RAT-1015` says whether sewer is one line on the account's whole water quantity (12.2 kgal → 4.88) or one line per meter. | TCs assert the sewer line EXISTS, is non-zero and follows water; the **$24.40** figure is asserted only under the whole-quantity reading and is marked so |
| **OI-3** | **Which reason codes each kind offers.** The drawing filters (catch-up: MISSED / METER-FAULT; penalty: THEFT / TAMPER); the design says only *"dropdown from Settings"*. | TCs assert the dropdown lists the tenant's codes and the server refuses a code not in Settings; no per-kind filter is asserted |
| **OI-4** | **Which account statuses may be picked, per kind.** The drawing lists Active, Closed and Pending accounts in the dropdown with their status. | US-BIL-034 shows every status; no kind-by-status refusal is asserted |
| **OI-5** | **Penalty evidence photos** — the existing documents store or a small billing table (build plan DB2, *"decision first"*). | US-BIL-014 asserts the evidence TEXT on the bill snapshot; photos are optional and their storage is not asserted |
| **OI-6** | **Records not yet written** (build plan R1, R2, R4): the review-gap defects are not filed; `BR-BIL-300`/`301`/`1048` and `BR-RAT-088`/`1025`/`090` are not yet stamped with the 2026-09-30 rulings; `CR-063`'s fire figure **$84.00** is not re-checked under base-per-asset. | Each story cites the decision-log row as the ruling. A lane building from these stories does R1/R2 first (write-back before the build) |
| **OI-7** | **Fee-bill tax needs a finance re-sign of B4.2 ❄** (build plan R3; `OQ-812` CLOSED 2026-09-30 as a ruling, not as a re-sign). | Split out as US-BIL-035, status **blocked** |

## Stories

---
id: US-BIL-010
epic: EP-BIL-03
module: billing
screens: [S31, S30]
wave: 3
status: ready            # 2026-09-30: the one-time bill redesign (epic §AMENDED 2026-09-30) — ready to build, not blocked
blocked_by: []
depends_on: [US-BIL-005, US-CUS-003, US-CUS-004, US-CUS-007, US-BIL-033, US-BIL-034, US-MET-007, US-MET-010]
journeys: [J2, J70]
rules: [BR-BIL-012, BR-BIL-1047, BR-BIL-300, BR-BIL-301, BR-BIL-1048, BR-RAT-088, BR-RAT-1025, BR-RAT-090, BR-RAT-1015]
golden_tests: [GT-3]
finance_calc: confirmed
---
### US-BIL-010 — First bill: prorated from move-in day + the one-time lines

**1 · Details** — As a Billing Clerk, I want the first cycle bill after a move-in to prorate by calendar days from the move-in day — base AND usage, tier spans scaling with the prorated period (B4.3/B4.4) — and to carry the one-time lines: the **deposit** (non-taxable, stamped to the deposit-liability designation, never revenue) and the **connection charge** (charge code) — so that a mid-cycle mover pays exactly their occupied days plus the agreed one-time items on ONE first bill (BR-BIL-012, PO A-3 option a). The run marks `bill_type=first` automatically for accounts whose move-in falls inside the period (BR-CUS-014 sc.1 snapshot supplies the plan). Same-day move: outgoing pays the move day; incoming starts next day from the same reading — no gap, no double (BR-CUS-056).


**1a · AMENDED 2026-09-30 — the one-time *First bill* kind in the redesigned flow** (epic §AMENDED 2026-09-30; PO: *"i need 1 word step name not 2 - and workflow should not be more than 3 or 4 steps"*, *"services , Rates, Move-in charges { deposites + fees} - they should be in this order and then readings"*, *"this is all correct"*). The clerk picks the **First bill** card (*Missed at move-in*) and walks **Account · Services · Review · Send**. Step 1: the account (US-BIL-034), **Period from = the move-in date, prefilled**, period to, bill date (required, today by default), days to pay (from the account's cycle) and the derived due date. Step 2: Services → Rates → **Move-in charges** (deposit = asked − already paid · connection charge CONN; collapsible, open by default) → **Readings**, one row per meter, whose *previous* value is the **move-in reading — the clerk types it when none is on file** — and whose usage is new − move-in; every reading is saved through Meter Reads (`/read-batches`), never by billing. Step 3 prints *Move-in charges* as their own group. Step 4 is US-BIL-033. ⚠ **The one-time first bill charges its base WHOLE** — `BR-BIL-1047`: *"A FINAL BILL PRORATES ITS BASE CHARGE OVER THE CUSTOMER'S OWN BILLING CYCLE, AND NO OTHER ONE-TIME KIND DOES."* TC-1..TC-3 above (WE-6, 20/31) remain the CYCLE run's first bill and are not changed by this amendment.
**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-012 | First bill: prorated from move-in day (B4.3) and carries the one-time lines — deposit (non-taxable → deposit liability, never revenue) + connection charge. | CONFIRMED — PO A-3 option (a), 2026-08-08 |
| B4.3 *(cited)* | Proration by calendar days; base AND usage prorated; tier thresholds scale with the prorated period (B4.4). | CONFIRMED — finance 2026-08-07 |
| BR-CUS-056 *(consumed)* | Billing boundaries at moves: bill through/from the move day, same-day handled no-gap-no-double. | CONFIRMED — customers pack |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | ACC-1350 moves in Jul 12 (20/31 days), Residential Standard | Bases prorate: elec 12 → **7.74**, water 8 → **5.16**, trash 18 → **11.61** (WE-6) |
| TC-2 | Water tiers on the prorated period | Tier-1 span 5 → **3.225806 kgal**; usage 4.2 kgal → T1 **12.90** + T2 0.974194 × 6.50 = **6.33** (WE-6) |
| TC-3 | Full WE-6 bill | TOU 70/120/210 → 15.40 + 16.80 + 18.90; sewer 40% × 19.23 = 7.69; taxable **102.53** → tax **9.70**; deposit **150.00** (non-taxable, deposit-liability GL) + CONN **25.00** (fee, non-taxable); total **287.23**; `bill_type=first` |
| TC-4 | Capacity rider activated Jul 22 (WE-16) | Solar 4 units → 10/31 × 40.00 = **12.90**, taxable like base (GT-15) |
| TC-5 *(negative)* | Deposit line forged to a revenue GL, or flagged taxable | Rejected — deposit stamps the deposit-liability designation and is never taxable (BR-BIL-012) |
| TC-6 *(negative)* | Move-in date outside the run period on a `bill_type=first` request | Rejected — first-bill classification is system-derived from the move-in date, not user-set |
| TC-7 *(isolation)* | Lone Star Ridge first bill | Its plan/deposit rules only (RLS); Brazos Bend deposit categories never apply |
| TC-8 *(2026-09-30, step 1)* | `OTB` fixture; Priya picks **First bill**, account `AC-2026-00042` (move-in **Sep 12, 2026**) | *From* is prefilled **Sep 12, 2026**; *To* **Sep 30, 2026**; *Bill date* **Sep 30, 2026**; *Days to pay* **21** (from the Monthly cycle); *Due date* shown **Oct 21, 2026** and read-only; no reason-code field and no charge-code field is rendered |
| TC-9 *(2026-09-30, readings)* | Step 2, Readings | **Three rows** — W-10442, W-10443, E-55120 — and none for trash, sewer, gas or fire. W-10442's previous = move-in reading **479.8 (Sep 12, 2026)**; **W-10443 has no move-in reading on file, so its previous cell is an input** and *Continue* stays disabled until it is typed. Typing **128.9** and new **136.7** gives usage **7.8 kgal**; W-10442 new **488.4** gives **8.6 kgal**. On Continue, the typed readings exist in Meter Reads as posted rows of a `/read-batches` batch (move-in reading dated Sep 12, new readings dated Sep 30) — billing writes no reading |
| TC-10 *(2026-09-30, move-in charges)* | Step 2, *Move-in charges* section; deposit asked **$150.00**, already paid **$0.00**; CONN **$25.00** | Section sits between Rates and Readings, open by default, collapsible. Rows: **Deposit $150.00 − $0.00 = $150.00** · **Connection charge (CONN) $25.00**. On Review they form the group **Move-in charges**, subtotal **$175.00**, both non-taxable; the deposit stamps the deposit-liability designation (TC-5 still holds) |
| TC-11 *(2026-09-30)* | Same, with **$50.00** of the deposit already paid | Deposit row **$150.00 − $50.00 = $100.00**; group subtotal **$125.00** |
| TC-12 *(2026-09-30, base whole — BR-BIL-1047)* | Review of the Sep 12–30 first bill | Water base **$8.00** on EACH meter line (two lines — ruling 2026-09-30), trash base **$3.00**, sewer base **$6.00** — **none prorated 19/30**; electric base **$0.00** with the warning *No base charge for Electric* |
| TC-13 *(2026-09-30, services — shared)* | Step 2 Services table on the `OTB` fixture | The US-BIL-012 TC-9 table verbatim: gas and fire *Not in service*, no bill line; sewer *Billed · follows water*; broadband *Not taken*; the bill completes |
| TC-14 *(negative, 2026-09-30)* | Clerk types a move-in reading for W-10443 of **140.0**, above the new reading 136.7 | Refused **on that row** (usage below zero); nothing is posted to Meter Reads; *Continue* stays disabled |
| TC-15 *(isolation, 2026-09-30)* | Lone Star Ridge clerk requests the first-bill preview for `AC-2026-00042`'s id | `404` — never Brazos Bend's deposit rules, CONN amount or readings |

**4 · Test Data** — WE-6 verbatim: ACC-1350, move-in Jul 12, 2026; period Jul 12–31 (20/31 days); Residential Standard (workbook §1); deposit category Residential $150; CONN $25.00 charge code; total **$287.23**. Capacity fixture WE-16 (Jul 22 start → 12.90). Same-day-move pair fixture: ACC-1350 in / ACC-1349 out on Jul 12 (BR-CUS-056/BS-4 — final side in US-BIL-011). Isolation: Lone Star Ridge move-in, deposit $100 fixture.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| bill_type = first | — | r10 #12 | `invoices.bill_type` | enum | system-derived | derived from move-in ∈ period |
| Prorated base/usage lines | S30 detail | B4.3 + WE-6 | `invoice_lines` (period_start = move-in day) | numeric(18,6) | system-derived (engine) | calendar-day factors; tier spans scaled |
| Deposit line | S30 detail | BR-BIL-012 | `invoice_lines` → deposit-liability designation GL (US-BIL-009); amount from `plan_deposit_rules` (category-fixed, BR-CUS-025) | numeric(18,6) USD | system-derived | non-taxable; never revenue |
| Connection charge line | S30 detail | BR-BIL-012 | `invoice_lines.charge_id` → CONN charge code (own GL) | numeric(18,6) USD | reference-data | fee class, non-taxable (B4.2) |
| Move-in date | — | BR-CUS-056 | customers-owned read (account move-in) | date | reference-data | drives proration start |

**6 · Acceptance**
- Given the WE-6 fixture, Then every prorated figure, the one-time lines and the 287.23 total match the workbook to the cent, and the bill is typed `first`.
- Given a capacity rider starting mid-cycle, Then WE-16's 12.90 proration holds.
- Given the deposit line, Then it is non-taxable and stamps deposit liability — never revenue.
- Given a same-day move, Then the incoming account's first bill starts the day after the move day from the same reading.

**7 · Finance Calculation** — CONFIRMED (WE-6/WE-16, workbook verbatim). Proration factor = occupied days ÷ period days (calendar, B4.3), applied to base AND usage; tier spans scale by the same factor (B4.4). Worked (WE-6, 20/31): bases 7.74 / 5.16 / 11.61; tier-1 span 3.225806 kgal; usage lines 12.90 + 6.33; TOU 15.40 + 16.80 + 18.90; sewer 7.69; taxable **102.53** → tax **9.70**; + deposit **150.00** + CONN **25.00** → first-bill total **287.23**. Capacity (WE-16): 10/31 × 40.00 = **12.90**. Refs: **GT-3** (rule), GT-15 (capacity), BS-2.

**8 · Open Questions** — None blocking. **2026-09-30 open item (epic OI table):** whether the tier ladder scales on a one-time first bill's partial period — B4.4 scales tier spans with a PRORATED period, and `BR-BIL-1047` says a one-time first bill's base is not prorated; the redesign does not say. TC-9 therefore asserts usage QUANTITIES (8.6 and 7.8 kgal), never first-bill usage dollars, until the records lane settles it from signed law. Also OI-2, OI-6 (epic).

---
id: US-BIL-011
epic: EP-BIL-03
module: billing
screens: [S20, S30]
wave: 3
status: ready            # 2026-09-30: the one-time bill redesign — ready to build, not blocked
blocked_by: []
depends_on: [US-BIL-005, US-CUS-005, US-CUS-007, US-CUS-018, US-BIL-033, US-BIL-034, US-MET-007, US-MET-010]
journeys: [J2, J70]
rules: [BR-BIL-013, BR-BIL-1047, BR-BIL-300, BR-BIL-301, BR-RAT-088, BR-RAT-090, BR-RAT-1015]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-011 — Final bill: immediate at move-out, deposit auto-apply, exactly one settlement path

**1 · Details** — As a Billing Clerk completing a move-out (S20 hands off per BR-CUS-031), I want the final bill generated **immediately**, billed **through the move day** (BR-CUS-056), with the deposit + accrued interest auto-applied FIRST, and then exactly **one** settlement path for the remainder (BR-BIL-013, r1.1 matrix): **1 Refund** (deposit covers all) · **2 Collect** (due per cycle due-days, normal dunning on a closed account) · **3 Transfer-to-master-account** (balanced transfer transaction, audited; prereq: unit/premises linked to a master billing account under the landlord-agreement flag — OQ-069 closed) · **4 Payment plan** (existing machinery) · **5 Small-balance write-off** (|balance| ≤ tenant threshold, default $5, config 0–50, both directions, write-off GL — OQ-070 closed). So that a closed account never lingers with an ambiguous balance. `bill_type=final`; due-days = the cycle's (same as any bill).


**1a · AMENDED 2026-09-30 — the one-time *Final* kind in the redesigned flow** (epic §AMENDED 2026-09-30; PO: *"this is all correct"*). The clerk picks **Final** (*Move-out*) and walks **Account · Services · Review · Send**. Step 1: account, period from, **Period to = the move-out date**, bill date, days to pay, derived due date. Step 2: Services → Rates → **Readings** — one row per meter, *previous* = the **last billed** reading, *new read date* = **the move-out date, fixed**, and a **final reading, required** per meter — then the **Settlement box**: *this bill + prior balance − deposit − interest = refund / left to pay / write-off*, with the path chosen as **collect · payment plan · transfer**. Base charges prorate over the customer's own cycle (`BR-BIL-1047`). Step 4 is US-BIL-033.
**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-013 | Final bill: immediate at move-out, billed through the move day; deposit+interest auto-applies FIRST, then exactly ONE settlement path — refund · collect · transfer-to-master (landlord-link prereq, OQ-069) · payment plan · small-balance write-off ($5 default, 0–50, both directions, OQ-070). **AMENDED 2026-08-12: the deposit settles EVERYTHING OUTSTANDING — the whole closing position, not the final bill alone (OQ-158, *"everything outstanding"*).** | CONFIRMED — PO A-4 option (a) + settlement matrix, 2026-08-08 · **AMENDED PO 2026-08-12 (OQ-158)** |
| BR-BIL-013 *(the other half, same ruling)* | There is **no mid-tenancy deposit differential at all** — a plan change moves no deposit money; the deposit is settled ONCE, at closure (PO 2026-08-12, OQ-179: *"we dont have to give depoiste back in between it will be settled only at the time of closure"*). | CONFIRMED — PO 2026-08-12 (OQ-179; supersedes the differential clauses of BR-CUS-042/062) |
| BR-CUS-056 / BR-CUS-057 *(consumed)* | Billed through the move day; deposit interest = tenant simple annual rate from original receipt date. | CONFIRMED — customers pack |
| BR-BIL-011 *(shared)* | Transfer = balanced transaction (credit final account / debit master), audited; shows on the master's next bill as a transfer line. | CONFIRMED — r1.1 path 3 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Deposit application (WE-7) | Deposit $150 held 14 mo @ 2% simple → interest **$3.50** → credit **$153.50** applies before any settlement choice |
| TC-2 | Case A: final charges 142.30 | Remainder **−11.20** → path 1 Refund; refund handed to payments (`refunds` flow); bill shows the applied deposit + refund line |
| TC-3 | Case B: final charges 289.40 | Still due **135.90** → staff picks exactly one: collect (due = bill date + cycle due-days) / transfer (only if landlord-linked) / payment plan; write-off greyed (135.90 > $5 threshold) |
| TC-4 | Transfer path on a landlord-linked unit | Balanced transaction: credit final account 135.90 / debit master ACC-9001; audited; master's next bill carries the transfer line; on a NON-linked unit the option is absent (OQ-069 prereq) |
| TC-5 | Remainder $3.20 (either direction) | Auto write-off line to the write-off GL (≤ $5 tenant threshold), audited; account settles to zero (BS-20 path 5) |
| TC-6 *(negative)* | Two settlement paths attempted on one final bill; or a transfer forged to an arbitrary account | Rejected — exactly one path per final bill; transfer target must be the designated master account (landlord-agreement link) |
| TC-7 *(isolation)* | Lone Star Ridge final bill | Its threshold/master links only; Brazos Bend master accounts unreachable (RLS) |
| TC-8 *(2026-08-12, OQ-158 — the settled base is the whole closing position)* | A closing account carries a **$120.84** prior balance beside its final charges, inside a *Final amount due* of **$184.20**; the WE-7 deposit credit is **$153.50** | The deposit applies to **$184.20**, not to the final charges alone. **The rejected reading is asserted beside it, as the budget TCs do:** settling the BILL alone **refunds $90.14** to a customer who still owes **$120.84** on an account that is now closed. WE-7's own two cases are unchanged — that account has no arrears, so both readings agree, which is why the frozen fixture never exposed this |
| TC-9 *(2026-09-30, step 1)* | `OTB`; **Final** for `AC-2026-00042`, move-out **Sep 18, 2026** | *To* reads **Sep 18, 2026** (the move-out date); *From* **Sep 1, 2026**; bill date **Sep 30, 2026**; days to pay **21**; due **Oct 21, 2026** |
| TC-10 *(2026-09-30, readings)* | Step 2, Readings | Three rows; previous = last billed — **482.3 / 130.6 kgal, 18,420 kWh**; the *new read date* cell is **Sep 18, 2026 and not editable**; each *Final reading* is **required** — *Continue* is disabled until all three are typed; the typed finals post through `/read-batches` dated Sep 18 |
| TC-11 *(2026-09-30, base prorated over the cycle — BR-BIL-1047)* | Review; cycle Sep 1–30 (30 days), served Sep 1–18 (18 days) | Base lines × 18/30: water **$4.80** on EACH meter line · trash base **$1.80** · sewer base **$3.60**; electric base **$0.00** ⚠ (nothing to prorate). Review group **Sep 1 – Sep 18** |
| TC-12 *(2026-09-30, settlement box)* | Deposit **$150.00** held 14 months at 2% (interest **$3.50**, WE-7) and a prior balance of **$142.18** | The box shows four terms — this bill · **+ $142.18** · **− $150.00** · **− $3.50** — and their result labelled *Refund*, *Left to pay* or *Write-off* by its sign and the tenant threshold (TC-5); the deposit applies to the whole closing position (TC-8, OQ-158) |
| TC-13 *(2026-09-30, path)* | Result is *Left to pay* above the threshold | Exactly one of **Collect · Payment plan · Transfer** can be chosen (Transfer offered only on a landlord-linked unit, TC-4); *Send* is disabled until one is chosen; the choice is recorded with the sent bill |
| TC-14 *(negative, 2026-09-30)* | A final reading **480.0** for W-10442, below the last billed 482.3 | Refused **on that row**; nothing posted; *Continue* stays disabled |

**4 · Test Data** — WE-7 verbatim: deposit 150.00, 14 months @ 2% simple → 3.50 → credit 153.50. Case A final 142.30 → refund **11.20**. Case B final 289.40 → due **135.90**. Write-off fixture: remainder 3.20 ≤ 5.00 threshold. Master transfer: ACC-1349 (unit under Bluebonnet Property Group landlord agreement) → master ACC-9001. Move-out Jul 12, 2026 (pairs with US-BIL-010 same-day fixture, BS-4). Actors: Priya Menon; System Admin approval not required (settlement is not a correction). Isolation: Lone Star Ridge, threshold $10 (config 0–50).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| bill_type = final + through-move-day period | S30 | r10 #12 + BR-CUS-056 | `invoices.bill_type`, `period_end` = move day | enum/date | system-derived | immediate at move-out handoff |
| Deposit + interest application | S20/S30 | BR-BIL-013 | applied-first credit on the final bill (deposit position from customers; interest per BR-CUS-057) | numeric(18,6) USD | system-derived | always first, before path choice |
| Settlement path choice | S20 step / S30 | BR-BIL-013 | final-settlement record (path enum, actor, when) | enum(refund\|collect\|transfer\|payment_plan\|write_off) | user-input | exactly one; write-off auto when ≤ threshold |
| Transfer transaction | — | r10 #10 | balance-transfer rows (credit final / debit master), master designation via landlord-agreement link | numeric(18,6) | system-derived | balanced; audited; prereq link (OQ-069) |
| Write-off line | S30 | r10 #11 | write-off line → write-off GL designation (US-BIL-009); tenant threshold setting | numeric(18,6) | system-derived | \|amount\| ≤ threshold; both directions |
| Refund handoff | — | r1.1 path 1 | payments `refunds` (payments-owned execution) | numeric(18,6) | system-derived | billing records the handoff only |

**6 · Acceptance**
- Given WE-7, Then interest 3.50 and credit 153.50 apply first, and Case A/Case B resolve to §7 exactly.
- Given the five paths, Then exactly one is recorded per final bill; transfer only exists on landlord-linked units; ≤-threshold remainders write off automatically in either direction.
- Given the transfer, Then the transaction balances, is audited, and surfaces on the master's next bill.
- Given a closed account after settlement, Then no ambiguous balance remains anywhere.

**7 · Finance Calculation** — CONFIRMED (WE-7/BS-3/BS-20, workbook verbatim). Interest = 150 × 2% × 14/12 = **3.50** → deposit credit **153.50** (applies first). Case A: 142.30 − 153.50 = **−11.20** → refund 11.20. Case B: 289.40 − 153.50 = **135.90** → collect / transfer / payment plan; ≤ $5 would write off (fixture 3.20 → write-off line 3.20 to the write-off GL). Refs: BS-3, BS-20.
**7a · WHAT the deposit is applied TO (AMENDED 2026-08-12, OQ-158 — neither figure above moves).** The base is the account's **whole closing position**: final charges **plus every arrear**. ❄️ **WE-7's cases are unaffected and that is checkable rather than asserted** — its account carries no arrears, so bill and closing position are the same number. **The case the ruling is about:** a **$120.84** prior balance inside a *Final amount due* of **$184.20**; the bill-only reading refunds **$90.14** to a customer in debt to the utility on a closed account, where there is no next month in which to correct it.

**8 · Open Questions** — None (OQ-069/OQ-070 closed 2026-08-08; **OQ-158 CLOSED 2026-08-12 — see §7a**). **2026-09-30:** the redesign lists three paths in the box (*collect · payment plan · transfer*) where BR-BIL-013 has five; refund and small-balance write-off are the box's RESULTS, not choices — read that way, nothing conflicts. Epic OI-2, OI-6 apply.

---
id: US-BIL-012
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 3
status: ready            # 2026-09-30: the one-time bill redesign — ready to build, not blocked; carries the SHARED services / rates / readings / bill-table / problems / already-billed cases
blocked_by: []
depends_on: [US-BIL-004, US-BIL-005, US-BIL-033, US-BIL-034, US-MET-007, US-MET-010]
journeys: [J2, J70]
rules: [BR-BIL-020, BR-BIL-023, BR-BIL-024, BR-BIL-300, BR-BIL-301, BR-BIL-1048, BR-BIL-411, BR-RAT-088, BR-RAT-1025, BR-RAT-090, BR-RAT-1015]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-012 — Ad-hoc single bill: the bulk wizard in single-account mode

**1 · Details** — As a Billing Clerk, I want to bill ONE account outside the cycle — interim, catch-up, or any single-account need — using the SAME wizard in single-account mode: pick the account + period (S30 One-time bill tab) → preview → exceptions → draft → issue (BR-BIL-020) — so that a one-off bill gets the full pipeline, and lines come ONLY from rules and charge codes: **free-typed amounts never exist on any bill** (the prototype's editable line inputs are explicitly superseded by BR-BIL-020). Draft powers and issue mechanics identical to US-BIL-004/005; delivery/pinning identical. Prior credits auto-apply per allocation order; a bill whose total ≤ 0 is a credit bill — nothing due, credit carries forward (model §7).


**1a · AMENDED 2026-09-30 — the one-time *Interim* kind, and the SHARED behaviour of every kind** (epic §AMENDED 2026-09-30). ⚠ **SUPERSEDED in §1 above: the screen sequence *"pick the account + period → preview → exceptions → draft → issue"*.** The pipeline underneath (single-scope run, draft, issue artifacts identical to US-BIL-005) stands; what the clerk walks is now **six kind cards, then Account · Services · Review · Send** — PO 2026-09-30: *"i need 1 word step name not 2 - and workflow should not be more than 3 or 4 steps"*. This story owns the cases every kind shares: the Services decision table (PO: *"this si correct + if there are two assets for same service then you ahve to take those as price multipled by 2 - rest is all corect"*), the Rates table (*"you ahve to show - rates for each service or meter as a sepearte table"*), readings per meter, the grouped bill table (*"can you improve the Charge - maybe make it table"*), the Problems state and the Already-billed state. Interim's own fields: period from/to, bill date (required, today), days to pay (from the cycle), derived due date; one reading row per meter, previous = last on file, new read date defaulting to the period end. **Free-typed amounts still never exist (BR-BIL-020, TC-4).**
**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-020 | Ad-hoc single bill = the bulk wizard in single-account mode (preview → exceptions → draft → issue); lines come ONLY from rules and charge codes — free-typed amounts never exist on any bill. ⚠ **NARROWED 2026-10-01 (PO, option A):** a one-time **Fee** bill with a charge code priced *entered when used* (CR-010 A2 — TAP, IMPACT, DAMAGE, BULK-WATER) takes the clerk's typed amount; every other line on every bill still comes only from a rule or a charge code's price. Decision log 2026-10-01, *"A ONE-TIME FEE BILL MAY CARRY THE AMOUNT THE CLERK TYPES"*. | CONFIRMED — PO Lane B-1, 2026-08-08 |
| BR-BIL-023 *(shared)* | Same draft powers, same never-edit-computed rule. | CONFIRMED — PO Lane B-4, 2026-08-08 |
| BR-PAY-010 *(consumed)* | Unallocated credit auto-applies (oldest first; usage+base → taxes → fees last; tenant-reconfigurable). | CONFIRMED — payments rule, cited |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Single-mode run: ACC-1620, period Jul 15 – Aug 6 | Same pipeline artifacts as a cycle run scoped to one account: run row (single scope), preview, exceptions, one draft; `bill_type` = the applicable type (cycle-interim single) |
| TC-2 | Credit bill (WE-14): prior credit −60.00, current charges 42.30 | Auto-applied per allocation order → amount due **$0.00**, remaining credit **−17.70** carries (refundable on request) |
| TC-3 | Issue | Number from the same tenant series, GL stamps, template pin, delivery queue — identical to US-BIL-005 |
| TC-4 *(negative)* | Any attempt to type a line amount or description-with-amount (UI or API) | Impossible/rejected — lines derive from rate rules or charge codes only (BR-BIL-020); the prototype's free inputs do not ship. ⚠ Narrowed 2026-10-01: a one-time Fee bill with an *entered when used* code takes the clerk's amount (BR-BIL-020). |
| TC-5 *(negative)* | Single-mode run for an account with an open hold on the same period | Blocked toward the catch-up sub-run path (US-BIL-006) — never a colliding parallel bill for the held period |
| TC-6 *(isolation)* | Lone Star Ridge single bill | Own accounts only; Brazos Bend account search returns nothing (RLS) |
| TC-7 *(2026-09-30, kind cards)* | Open the One-time bill page | Six cards in this order — **Interim · First bill · Final · Catch-up · Penalty / theft · Fee** — and a four-step rail **Account · Services · Review · Send** (one word each) |
| TC-8 *(2026-09-30, step 1)* | `OTB`; Interim, `AC-2026-00042` | Period **Sep 1 – Sep 30, 2026**; bill date defaults **Sep 30, 2026** and is required; days to pay defaults **21** from the account's cycle and is editable; due date **Oct 21, 2026** is shown, read-only, and moves to **Oct 30, 2026** when days to pay is changed to **30**; the request sent carries `bill_date` AND `due_days` |
| TC-9 *(2026-09-30, services table)* | Step 2, Services | Seven rows: Water *Billed · 2 meters* (2 lines · usage + base each) · Electric *Billed · base $0.00* ⚠ · Trash *Billed · 1 cart* · Sewer *Billed · follows water* · Gas *Not in service* (no line · $0) · Fire *Not in service* (no line · $0) · Broadband *Not taken* (no line). Header count **4 billed · 2 not in service · 1 not taken**; one warning *No base charge for Electric*. Section collapsible, open by default |
| TC-10 *(2026-09-30, rates table)* | Step 2, Rates | One row per meter or billed service: Water · W-10442 and Water · W-10443 (Tiered, $3.25/kgal to 5 kgal, $4.50 above, base **$8.00 · BASE-W**) · Electric · E-55120 (Flat $0.1245/kWh, base **Not set · $0.00** ⚠) · Trash · 1 cart ($15.00/cart, **$3.00 per cart · BASE-T**) · Sewer (% of service, 40%, **$6.00 · BASE-S**) · Gas and Fire *No rate used* **$0.00**. Each row names its price version. The Amount column is shown in full (the drawing's clipped column is a known flaw — README) |
| TC-11 *(2026-09-30, readings)* | Step 2, Readings; clerk types W-10442 **488.4**, W-10443 **136.7**, E-55120 **19,020**, new read date **Sep 30, 2026** | Three rows (none for trash, sewer, gas, fire); previous **482.3 / 130.6 / 18,420** read on **Aug 31, 2026**; usage **6.1 kgal / 6.1 kgal / 600 kWh**; each row *Accepted*; the readings are posted through `/read-batches` (stage → validate → post), one row per meter, and billing writes no reading. A multi-register meter row links to the full readings screen instead of an input |
| TC-12 *(2026-09-30, two meters — ruling)* | Same | **Two water usage lines and two water base lines**, one per meter: **$21.20 + $8.00 = $29.20** each, water **$58.40** — never one meter billed and the other dropped (today **$29.20**) |
| TC-13 *(2026-09-30, missing base — ruling)* | Electric has no base code defined or bound | Electric bills usage **$74.70** + base **$0.00**; the warning is shown on Services, Review and Send; the bill **completes** — it is NOT refused |
| TC-14 *(negative, 2026-09-30 — conflicts still refuse)* | Two water base codes both apply to the plan | The preview is **refused naming Water** and its reason; the other services are not silently billed without it |
| TC-15 *(2026-09-30, sewer — ruling)* | Sewer has **no service point** | A sewer line is present, *follows water*, never `$0.00` *not connected*: **4.88 kgal × $5.00 = $24.40** + base **$6.00** *(figure under epic OI-2's whole-quantity reading; arithmetic `BR-RAT-1015`, not the drawing's — OI-1)* |
| TC-16 *(2026-09-30, no asset — ruling)* | Gas taken, no meter; fire taken, no asset | **No gas line and no fire line**, $0; gas does NOT answer `no_meter` and the account is NOT refused; both still show *Not in service* on the Services table |
| TC-17 *(2026-09-30, not taken)* | Broadband offered at the unit, not taken | No line; the row is on the Services table as *Not taken* |
| TC-18 *(2026-09-30, the grouped bill table)* | Step 3, Review | Columns **Service · Meter / asset · Charge · Quantity · Rate · Amount**; one group **Sep 1 – Sep 30** with its subtotal **$181.50** (OI-2); then Subtotal, Tax (one B4.2 pass), Total; the warnings; Delivery; **Save draft** creates the draft (no bill number) and the page says it was saved |
| TC-19 *(negative, 2026-09-30 — problems state)* | Step 1 with *To* **Aug 20, 2026** (before *From* Sep 1) and *Days to pay* empty; press Continue | A banner **Fix 2 things to continue.** listing both; *To* shows **Ends before it starts.** and *Days to pay* shows **Enter days to pay.**, each on its own field; the API returns BOTH problems in one response, each with its field and its own catalogue key — never a generic "billing run" sentence and never the word "cycle" |
| TC-20 *(negative, 2026-09-30 — already billed)* | An interim for `AC-2026-00042`, Sep 1–30, was sent earlier by another clerk; Priya starts the same kind, account and period | Banner **Already billed for this period.** with that bill's number, the date and who sent it, and a link that opens it; no second bill can be sent for the period |
| TC-21 *(negative, 2026-09-30 — reading below the last)* | W-10442 new reading **480.0** (last **482.3**) | That row is refused **Below last reading**, on the row; *Continue* is disabled; nothing is posted to Meter Reads |
| TC-22 *(2026-09-30, no agreements — ruling)* | Interim for `AC-2026-00043` (Dana Brooks, no agreements), W-10450 210.0 → 215.0, E-55121 9,800 → 10,200 | Water, electric and trash are all billed and a warning says the account holds no service agreements; the bill completes |
| TC-23 *(2026-09-30, counted — ruling)* | The unit has **2** trash carts | Trash bills **2 × ($15.00 + $3.00) = $36.00** — the base once per cart, not once (today **$33.00**) |
| TC-24 *(isolation, 2026-09-30)* | Lone Star Ridge's clerk previews an interim with Brazos Bend's account id or run id | `404`; its Services and Rates tables are built only from Lone Star Ridge's plans and assets |

**4 · Test Data** — ACC-1620 (Residential Standard), period Jul 15 – Aug 6, 2026. WE-14 verbatim: prior credit −$60.00, current charges $42.30 → due $0.00, carry −$17.70. Charge-code add fixture: SVCCALL-type = tenant code (workbook codes: NSF $30 / RECONN $45 / CONN $25). Actors: Priya Menon. Isolation: Lone Star Ridge ACC-L-204.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account + period pick | S30 One-time tab | prototype-extracted + BR-BIL-020 | `bill_runs` single-account scope (r10 #7) | uuid/dates | user-input | one account; period explicit |
| Kind select (interim/final/catch-up/deposit) — ⚠ **SUPERSEDED 2026-09-30: six kind cards — Interim · First bill · Final · Catch-up · Penalty / theft · Fee** (epic §AMENDED 2026-09-30) | S30 One-time tab | prototype-extracted; typed via r10 #12 | `invoices.bill_type` derived (final → US-BIL-011 flow; catch-up past-period → US-BIL-013 rules) | enum | user-input | routed to the governing story's rules |
| Draft lines | S31 single mode | BR-BIL-020 | `invoice_lines` from engine + charge codes only | numeric(18,6) | system-derived | no free-typed amounts anywhere |
| Credit auto-apply preview | S31 | BR-PAY-010 | allocation preview (payments executes) | numeric(18,6) | computed-display | order per tenant setting |
| Issue artifacts | — | US-BIL-005 | identical set (number, stamps, pin, queue, audit) | — | system-derived | shared path |

**6 · Acceptance**
- Given single-account mode, Then the full preview→exceptions→draft→issue pipeline runs scoped to one account with all US-BIL-005 issue artifacts.
- Given WE-14, Then the credit bill shows due 0.00 and carries −17.70.
- Given any input path, Then no free-typed amount can ever reach a bill.
- Given a held period, Then single-mode cannot collide with the catch-up path.

**7 · Finance Calculation** — CONFIRMED (WE-14, workbook verbatim): amount due = max(0, current charges − applied credits); remainder carries. Worked: credit −60.00 + current 42.30 → due **0.00**, remaining credit **−17.70** (auto-applies forward per BR-PAY-010; refundable on request). Ref: BS-10, BS-11.

**8 · Open Questions** — None blocking. **2026-09-30 open items (epic table):** OI-1 (drawing's sewer arithmetic superseded — build to BR-RAT-1015), OI-2 (sewer basis over two water meter lines — TC-15/TC-18 figures are marked), OI-4 (which statuses may be picked per kind), OI-6 (rule rows and defects not yet stamped).

---
id: US-BIL-013
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 5
status: ready            # 2026-09-30: the one-time bill redesign — ready to build, not blocked
blocked_by: []
depends_on: [US-BIL-012, US-BIL-017, US-RAT-010, US-BIL-033, US-BIL-034, US-MET-007, US-MET-010, US-MET-014]
journeys: [J2, J70]
rules: [BR-BIL-018, BR-BIL-014, BR-BIL-300, BR-BIL-301, BR-RAT-088, BR-RAT-090, BR-RAT-1015]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-013 — Back-bill: arbitrary past period, each sub-period priced on ITS tariff version

**1 · Details** — As a Billing Clerk discovering unbilled history (e.g. 6 months), I want the single-account flow to accept an arbitrary past period and produce ONE bill with **period-labeled line groups**, each sub-period priced against the tariff version in force THEN (B2 tariff_versions — never today's rates), reason-coded and approval-gated (System Admin, same gate as corrections), with the window capped by tenant setting (default 12 months; **theft cases EXEMPT** — OQ-071 closed) — so that missed history is recovered correctly and auditable (BR-BIL-018). `bill_type=backbill`. Entry: S30 One-time bill tab, kind = catch-up with a past period. Exit: approved → issued via the standard issue path.


**1a · AMENDED 2026-09-30 — the one-time *Catch-up* kind in the redesigned flow** (epic §AMENDED 2026-09-30; PO: *"this is all correct"*). The clerk picks **Catch-up** (*Missed periods*) and walks **Account · Services · Review · Send**. Step 1: account, a **list of missed periods** (add rows — no single from/to), a **reason code chosen from a dropdown fed by Settings** (no free text), bill date, days to pay, derived due date. Step 2: Services → Rates (**per period, with the price version and the split**) → Readings **per meter per period** — the clerk types the reading for the **last period only**; earlier periods read from Meter Reads, and an earlier missing one is **estimated** and tagged *Estimated* on screen and on the bill → the **Periods table** (period · days · price version · Actual/Estimated · split note). Review prints **one group per missed period**. Send is US-BIL-033 and stays behind this story's approval gate (BR-BIL-014).
**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-018 | Back-bills: arbitrary past period via the single-account flow; usage priced per sub-period against the tariff version in force THEN; window capped by tenant setting (default 12 months; theft EXEMPT — OQ-071); reason-coded + approval-gated. **AMENDED 2026-08-12: a period that SPANS a tariff change is split BY DAYS into two day-weighted segments (OQ-155), and a segment with no read of its own gets a day-weighted usage estimate BY DEFAULT, marked estimated, with the metering estimate as a tenant option (OQ-191).** | CONFIRMED — PO new scope, 2026-08-08 · **AMENDED PO 2026-08-12 (OQ-155 · OQ-191)** |
| BR-BIL-014 *(gate shared)* | Approval gate = the corrections gate: v1 ALL require System Admin approval (OQ-072); no money-bearing write before approval. | CONFIRMED — PO A-5 + r1.5 "same approval gate" |
| B2 tariff_versions *(cited)* | Effective-dated versions; history billed on its version. | CONFIRMED — B2 rule, workbook §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | WE-10 fixture: water 6 kgal/mo Jan–Jun, tariff v3 through Mar 31, v4 from Apr 1 | ONE bill, **6 period-labeled groups**; Jan–Mar groups 45.10/mo (26.50 + 8.00 + 10.60); Apr–Jun groups 47.84/mo (28.10 + 8.50 + 11.24) — each period on ITS version |
| TC-2 | Totals | Taxable **278.82** → tax **26.36** → total **305.18**; `bill_type=backbill`; line `period_start/period_end` label every group |
| TC-3 | Approval flow | Draft + impact preview exist first; System Admin approves; only then issue (number/stamps/pin/queue) — nothing money-bearing before approval |
| TC-4 *(negative)* | Back-bill request spanning 14 months, no theft case | Rejected — exceeds the tenant 12-month cap (OQ-071); message cites the setting |
| TC-5 | Same 14-month span flagged as a theft case (reason-coded) | Allowed — theft exempt from the cap (OQ-071); still Admin-gated |
| TC-6 *(negative)* | Sub-period priced with today's v4 rates for a Jan group (forged engine input) | Detected/rejected — each group's `tariff_version_id` must match the version in force for that group's dates |
| TC-7 *(isolation)* | Lone Star Ridge back-bill | Its tariff history + cap setting only (RLS) |
| TC-8 *(2026-08-12, OQ-155 — the version change lands INSIDE a group)* | Same tariff, a **February** group of **6 kgal** with the change on the 15th: 3 kgal and **14/28 days** each side | The group is **split by days** into two day-weighted segments, each at the version in force on those days (PO 2026-08-12, *"Split by days"*) — v3 base **4.00** + tier1 **10.00** + tier2 **3.25**; v4 base **4.25** + tier1 **10.63** + tier2 **3.43** → group **35.56**. ⚠ **The question that was put to the PO illustrated 35.55; the RULE produces 35.56** — 35.55 sums v4's tier amounts (10.625 + 3.425) BEFORE rounding, and **B4.4/BR-RAT-003 rounds PER LINE** (10.63 and 3.43 separately). The cent is reported, never hand-adjusted. Neither the tier ladder nor the base is priced at one version for the whole month, and the group is **not refused** |
| TC-9 *(2026-08-12, OQ-155 — taxed exactly once)* | A Jan–Jun sub-period split **90/181 and 91/181** | Subtotal **75.59** → tax **6.24** in **ONE pass** over Σ(rounded taxable lines), per B4.2. Taxing each segment separately and summing gives **6.23** — both figures asserted, so the shape is pinned rather than described |
| TC-10 *(2026-08-12, OQ-191 — nobody read the meter on the cut day)* | Tariff changes **15 Feb**; period 1–28 Feb, **6 kgal**, read on the 1st and the 28th and **not** on the 15th | **Default:** day-weighted usage estimate — **14/28 × 6 = 3 kgal each side** — and the segment is **MARKED AS ESTIMATED on the bill, because it is one** (PO 2026-08-12, *"B is correct … I will make B default and C as option for user"*). **Tenant option:** ask metering for an estimate under its own rules (BR-MET-026). **REFUSE is now only the last resort**, when neither estimate can be produced — refusing by default would make back-billing fail in exactly the case it exists for, since a six-month catch-up will almost never have a read on the reprice day |
| TC-11 *(negative — 2026-08-12, OQ-191 does not invent usage)* | A split segment that DOES have its own read | The read is used as-is: day-weighting applies to the **base charge and the tier ladder**, never to metered usage that was actually measured (B4.3 as amended 2026-08-11) |
| TC-12 *(2026-09-30, step 1)* | `OTB`; **Catch-up** for `AC-2026-00042`; rows **Jun 1–30, Jul 1–31, Aug 1–31, 2026**; reason **MISSED** | No *Period from/to* field; three period rows with add/remove; the reason dropdown lists the tenant's four codes from Settings; bill date **Sep 30, 2026**, days to pay **21**, due **Oct 21, 2026** |
| TC-13 *(negative, 2026-09-30)* | The request carries reason `LOST` (not in Settings) | Refused **on the reason field**, checked against the tenant's `reason_codes` — a free-typed reason never reaches a bill |
| TC-14 *(2026-09-30, readings per period)* | Step 2, Readings | One block per period, one row per meter: Jun and Jul read-only from Meter Reads; **only Aug takes a typed new reading**; the *Reading needed* badge reads *last period only*. **W-10443 has no July read**: its July usage is estimated and tagged **Estimated** on the row, in the Periods table and on the bill line |
| TC-15 *(2026-09-30, split by price version)* | A water price version change effective **Jul 16, 2026** | The Periods table shows July **split 15/31 on the old version and 16/31 on the new**, day-weighted (TC-8's rule); the Rates table names the version per period; the other periods carry one version each |
| TC-16 *(2026-09-30, review)* | Step 3 | Three groups **Jun 2026 · Jul 2026 · Aug 2026**, each with its subtotal; two water lines per period (one per meter, ruling 2026-09-30); gas and fire have no line in any group; tax is ONE pass over the whole bill (TC-9) |
| TC-17 *(negative, 2026-09-30 — problems state)* | No reason chosen and a period row **Aug 31 → Aug 1** | Both problems shown at once, each on its own field (reason; that period row) |
| TC-18 *(2026-09-30, approval)* | Tenant approval mode requires System Admin approval | *Send* (US-BIL-033) is refused until **Alex Reed** approves; after approval it issues — nothing money-bearing before approval (TC-3) |

**4 · Test Data** — WE-10 verbatim: ACC-1888, water 6 kgal/mo Jan–Jun 2026; v3 (T1 4.00 / T2 6.50 / base 8.00) until Mar 31; v4 (4.25 / 6.85 / 8.50) from Apr 1; per-month 45.10 ×3 + 47.84 ×3; taxable 278.82, tax 26.36, total **305.18**. Cap: 12 months (tenant setting); theft fixture rides US-BIL-014's case. Reason code: "unbilled-service — meter never linked". Actors: Priya Menon (initiates), Alex Reed (approves). Isolation: Lone Star Ridge cap 6 months (tenant-changed).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Past period | S30 One-time tab | BR-BIL-018 | run scope period (single mode) | dates | user-input | span ≤ tenant cap unless theft-coded |
| Period-labeled groups | S30 detail | r1.5 "one bill, period-labeled line groups" | `invoice_lines.period_start/period_end` + `tariff_version_id` per group | rows | system-derived | version = in force THEN |
| Back-bill cap setting | S66 | BR-BIL-018 + OQ-071 | tenant billing settings (default 12 mo; theft exempt) | int months | reference-data | 0–n config; exemption by theft reason code |
| Reason code | wizard | BR-BIL-018 | reason-code lookup (r10 #13, tenant-extensible) | uuid | reference-data | required |
| Approval | wizard | BR-BIL-014 gate | correction-gate record (approver, when — US-BIL-017 machinery) | uuid/ts | user-input | System Admin only (OQ-072 v1) |
| bill_type | — | r10 #12 | `invoices.bill_type = 'backbill'` | enum | system-derived | — |

**6 · Acceptance**
- Given WE-10, Then one bill with six labeled groups reproduces the workbook exactly, each group on its own tariff version.
- Given the cap, Then a beyond-cap request fails unless theft-coded; either way Admin approval precedes any money-bearing write.
- Given the issued back-bill, Then all standard issue artifacts exist and the version stamps are auditable per group.
- Given tenants, Then caps/versions never cross.

**7 · Finance Calculation** — CONFIRMED (WE-10/BS-18, workbook verbatim). Per sub-period: price on the version in force then. Jan–Mar: usage 26.50 + base 8.00 + sewer 10.60 = **45.10/mo**; Apr–Jun: 28.10 + 8.50 + 11.24 = **47.84/mo**; six groups → taxable **278.82** → tax **26.36** → total **305.18**. Never today's rates. Ref: BS-18.
**7a · The intra-group split (AMENDED 2026-08-12, OQ-155 + OQ-191 — no figure above moves).** WE-10's change lands on a month boundary, so **none of its six groups straddles a version** and the totals are untouched. Where a group DOES straddle one, it is priced as two day-weighted segments: on the February variation (6 kgal, 3 each side, 14/28 days) v3 gives **4.00 + 10.00 + 3.25** and v4 gives **4.25 + 10.63 + 3.43** → **35.56** (the question's illustrative **35.55** summed v4's tiers before rounding; B4.4 rounds per line). Tax runs **once** over the whole bill's rounded taxable lines — worked on a 90/181 + 91/181 split, subtotal **75.59** → tax **6.24**, where per-segment taxation sums to 6.23. A segment with no read of its own is **day-weighted and marked estimated** by default (14/28 × 6 = 3 kgal), with the metering estimate as a tenant option and refusal only when neither can be produced.

**8 · Open Questions** — None (OQ-071 closed; **OQ-155 and OQ-191 both CLOSED 2026-08-12 — see §7a**). ⚠ **One thing is HUMAN-REVIEW-PENDING rather than ruled:** the **35.56** figure itself. The PO ruled the RULE (*"Split by days"*) and their question's own illustration said 35.55; the cent that per-line rounding produces should be put to them in plain English, exactly as the **$8.30 → $8.31** cent was. **2026-09-30:** epic OI-3 (which reason codes each kind offers — the drawing filters catch-up to MISSED / METER-FAULT; not asserted) and OI-6 apply.

---
id: US-BIL-014
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 5
status: ready            # 2026-09-30: the one-time bill redesign — ready to build, not blocked
blocked_by: []
depends_on: [US-BIL-013, US-BIL-017, US-MET-013, US-BIL-033, US-BIL-034]
journeys: [J2, J10, J70]
rules: [BR-BIL-007, BR-BIL-018, BR-BIL-019, BR-BIL-014, BR-BIL-300, BR-BIL-301]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-014 — Penalty / theft bill: assessed reads priced by the engine + charge-code penalties — never hand-typed

**1 · Details** — As a Billing Clerk handling a tamper/theft case, I want the penalty bill built from exactly two ingredients: **assessed/estimated READS** entered per required channel through the metering path (reason-coded, flagged `assessed` — r10 #14) which back-billing prices through the engine, and **charge-code lines** (e.g. TAMPER) for the penalties — so that hand-typed amounts NEVER exist on any bill (BR-BIL-019). Renders on the statement template class (r1.5); Admin approval required (same gate); theft cases are exempt from the back-bill cap (BR-BIL-018/OQ-071). `bill_type=penalty`. Entry: S30 One-time tab (theft reason) after the assessed reads exist. Exit: approved → issued.


**1a · AMENDED 2026-09-30 — the one-time *Penalty / theft* kind in the redesigned flow** (epic §AMENDED 2026-09-30; PO: *"this is all correct"*). The clerk picks **Penalty / theft** (*Tamper or theft*) and walks **Account · Services · Review · Send**. Step 1: account, list of missed periods (add rows), a **reason code from Settings**, bill date, days to pay, derived due date, and an **optional charge code** from a dropdown whose amount is read-only (e.g. TAMPER). Step 2: Services → Rates (per period, with the price version) → Readings **read-only**, per meter per period, the **assessed** reads from Meter Reads, tagged *Assessed, not verifiable* — no reading is typed and none is needed to continue → Periods table → **Evidence** (what was found, plus optional photos) → the optional **Charge** line. Review prints one group per period and **Other charges** as its own group. **Send is refused until the penalty is approved** under the tenant's `correction_approval_mode` (build plan B10).
**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-019 | Penalty bills/statements: charge-code lines only — hand-typed amounts NEVER exist on any bill; theft/unmetered consumption enters as assessed/estimated READS (reason-coded, flagged) which back-billing prices; approval-gated. | CONFIRMED — PO new scope, 2026-08-08 |
| BR-BIL-018 *(shared)* | Theft cases exempt from the back-bill window cap. | CONFIRMED — OQ-071 closure |
| BR-BIL-007 | TAMPER etc. are tenant charge codes with their own GL — amounts from the code, never typed. | CONFIRMED — B4 §NSF principle + workbook §1 codes |
| BR-MET-053 *(consumed)* | Assessed reads enter via the metering lifecycle (reason-coded, flagged), append-only. | CONFIRMED — metering pack + r10 #14 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Assessed reads on ACC-1544 (WE-11): on 150 / mid 300 / off 450 kWh, reason "tamper-assessed", flagged | Engine prices them: 33.00 + 42.00 + 40.50 = taxable **115.50**; lines labeled from assessed reads |
| TC-2 | Tax + penalty | Tax **10.92** (7.22 + 1.16 + 2.31 + 0.23); **TAMPER $500.00** charge-code line (fee — non-taxable, own GL); total **626.42** |
| TC-3 | Approval + render | Admin gate before any money-bearing write; issued bill typed `penalty`, rendered on the statement template class, delivery queued |
| TC-4 | 14-month theft window | Allowed (cap exempt), rides US-BIL-013 pricing per sub-period |
| TC-5 *(negative)* | Attempt to add a typed "$500 penalty" line without a charge code, or a typed usage amount | Impossible — only assessed-read-priced lines and charge-code lines exist (BR-BIL-019) |
| TC-6 *(negative)* | Penalty bill attempted while the assessed reads are still unflagged drafts in metering | Blocked — pricing consumes committed assessed reads only (BR-MET-053 lifecycle) |
| TC-7 *(isolation)* | Lone Star Ridge penalty case | Its charge codes/reads only; Brazos Bend TAMPER code invisible (RLS) |
| TC-8 *(2026-09-30, step 1)* | `OTB`; **Penalty / theft** for `AC-2026-00042`; periods **Jun, Jul, Aug 2026**; reason **TAMPER**; charge code **TAMPER** | The charge dropdown shows **Tamper charge · $250.00** and the amount cannot be edited; bill date **Sep 30, 2026**, days to pay **21**, due **Oct 21, 2026**; leaving the charge code empty is allowed |
| TC-9 *(2026-09-30, readings read-only)* | Step 2, Readings | Per period, per meter, the committed assessed reads — **no input on any row**; each tagged **Assessed**; the *Reading needed* badge reads *Not needed*; the same tag prints on each usage line of the bill |
| TC-10 *(2026-09-30, evidence)* | Priya types *Bypass pipe found at meter W-10442* | The text is carried into the bill snapshot and prints on the bill; photos are optional (storage: epic OI-5) |
| TC-11 *(2026-09-30, review)* | Step 3 | Groups **Jun 2026 · Jul 2026 · Aug 2026** with subtotals, then **Other charges**: *Fee · TAMPER · Tamper charge · 1 · $250.00 · $250.00*, non-taxable (TC-2's rule) |
| TC-12 *(2026-09-30, no charge code)* | Same, charge code left empty | No *Other charges* group; the bill is still valid and priced from the assessed reads alone |
| TC-13 *(negative, 2026-09-30 — approval before send)* | Priya ticks *I checked the amounts* and presses Send before approval | **Refused** — the penalty awaits approval; no bill number is minted. **Alex Reed** approves; Priya presses Send again → the bill issues typed `penalty` (US-BIL-033) |
| TC-14 *(negative, 2026-09-30)* | A penalty request that carries a typed usage value for a period | Refused — penalty usage comes only from committed assessed reads (TC-5, TC-6) |

**4 · Test Data** — WE-11 verbatim: ACC-1544, assessed channels on 150 → 33.00 · mid 300 → 42.00 · off 450 → 40.50 (summer TOU rates 0.22/0.14/0.09); taxable 115.50; tax 10.92; TAMPER $500.00 (workbook §1 code); total **$626.42**. Reason codes: "tamper-assessed" (reads), "theft-restated" (case). Actors: field tech (assessed reads via metering), Priya Menon (bill), Alex Reed (approval). Isolation: Lone Star Ridge TAMPER-equivalent $350 code.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Assessed reads | metering entry path | BR-BIL-019 + r10 #14 | `meter_reads` (flag assessed, reason-coded — metering-owned write) | numeric + unit | user-input (metering) | committed before pricing |
| Priced usage lines | S30 detail | BR-BIL-019 | `invoice_lines` from engine over assessed reads | numeric(18,6) | system-derived | never typed |
| TAMPER line | S30 detail | BR-BIL-007/019 | `invoice_lines.charge_id` → TAMPER code (own GL) | numeric(18,6) USD | reference-data | fee, non-taxable (B4.2) |
| bill_type + template class | — | r10 #12 + r1.5 | `invoices.bill_type='penalty'`; statement template class pinned | enum | system-derived | statement class (A19) |
| Case reason + approval | wizard | BR-BIL-019 | reason-code lookup (r10 #13) + gate record (US-BIL-017) | uuid | user-input | Admin approval before execution |

**6 · Acceptance**
- Given WE-11, Then the priced lines, tax, TAMPER line and 626.42 total match the workbook exactly, with zero hand-typed amounts anywhere in the flow.
- Given the gate, Then nothing money-bearing exists before Admin approval.
- Given theft, Then the back-bill cap does not constrain the period.
- Given the render, Then the statement template class is pinned and delivery queues normally.

**7 · Finance Calculation** — CONFIRMED (WE-11/BS-19, workbook verbatim). Usage (assessed, engine-priced): 33.00 + 42.00 + 40.50 = **115.50** taxable → tax **10.92** (7.22 + 1.16 + 2.31 + 0.23); penalty TAMPER **500.00** (fee, non-taxable) → total **626.42**. Ref: BS-19.

**8 · Open Questions** — None blocking. **2026-09-30:** epic OI-3 (penalty reason codes), OI-5 (where evidence photos are stored — decision first, build plan DB2), OI-6.

---
id: US-BIL-032
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 3
status: ready            # 2026-09-30: ready to build WITHOUT tax; the tax half is US-BIL-035 (blocked on the B4.2 re-sign)
blocked_by: []
depends_on: [US-BIL-005, US-BIL-033, US-BIL-034]
journeys: [J70]
rules: [BR-BIL-410, BR-BIL-007, BR-BIL-010, BR-BIL-024]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-032 — Fee bill: one charge code raised as a bill of its own, through the redesigned one-time flow

**1 · Details** — As a Billing Clerk, I want to raise a single tenant charge code — a reconnection fee, a returned-payment fee, a meter test — as a bill of its own, from the **Fee** card of the one-time bill page, so that a fee owed outside the cycle becomes a line that can be billed, posted, aged and paid (BR-BIL-410, PO 2026-08-27 closing DEF-708: *"Make the fee a real charge — It becomes a line that can be billed and paid, so the gate has something to check."*). **Written 2026-09-30** — there was no fee story: BR-BIL-410 was ruled and built (`apps/billing/fee_bill.py`, `tests/test_def_708_the_fee_is_a_real_charge.py`) and no epic owned it, which is hard-won law 8's shape. The redesign puts it on the same page as every other kind (PO 2026-09-30: *"this is all correct"*; review gap *"No charge code sent; Fee not offered"* → *"Charge-code dropdown; Fee kind"*). Flow: **Account · Services · Review · Send**. Step 1: account (US-BIL-034), bill date (required, today), days to pay (from the cycle), derived due date, and a **charge code, required, from a dropdown whose amount is read-only**. Step 2 holds **only the Charge panel** — code · name · amount · a note printed on the bill — and **no** Services table and **no** readings (design §4). Review prints one group, **Charges**. Send is US-BIL-033. **Tax is out of this story**: until US-BIL-035 is unblocked a fee bill carries **no tax**, exactly as BR-BIL-410 shipped.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-410 | A tenant charge code can be raised as a bill of its own — `bill_type = fee`; no plan, no tariff, no usage, no proration and no tax pass; the amount is the tenant's own `rating.charges.amount`; the GL account is the code's own. Four refusals: unpublished `charge_by_code` seam; an unknown, retired or another tenant's code; a `percent` / `percent_with_minimum` code; a code with no GL account (refused at draft, naming S13). | CONFIRMED — PO 2026-08-27 (DEF-708). ⚠ Its *"A FEE BILL IS NOT TAXED"* clause was RULED AWAY by the PO on 2026-09-30 (`OQ-812` closed, *"yes"*) but stays the behaviour until the B4.2 re-sign — US-BIL-035 |
| BR-BIL-007 | Charge codes carry their own amount and GL — never typed. | CONFIRMED |
| BR-BIL-024 | Due date = bill date + days to pay. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `OTB`; **Fee** for `AC-2026-00042`, charge code **RECON** | Step 1 shows account, bill date **Sep 30, 2026**, days to pay **21**, due **Oct 21, 2026**, and the charge dropdown reading **Reconnection fee · $75.00** with the amount read-only; no period, reason or missed-period field |
| TC-2 | Step 2 | **Only the Charge panel**: code **RECON** · name *Reconnection fee* · amount **$75.00** · an optional note (*Reconnected Sep 30 after payment*). No Services table, no Rates, no Readings |
| TC-3 | Step 3 Review | One group **Charges**: *Fee · RECON · Reconnection fee · 1 · $75.00 · $75.00*; total **$75.00**; **no tax line** (until US-BIL-035); the note prints on the bill (bill payload, no column — build plan DB3) |
| TC-4 | Send (US-BIL-033) | One invoice, `bill_type = fee`, GL = RECON's own account; it posts, ages and can be paid like any bill; one `audit_log` row |
| TC-5 *(negative)* | Continue with no charge code | Refused **on the charge field**; nothing is drafted |
| TC-6 *(negative)* | A `percent` charge code, a retired code, and a code with no GL account | Each refused by name — the no-GL one at draft time naming the charge-codes screen (S13), before any invoice number is minted (BR-BIL-410) |
| TC-7 *(negative)* | The request carries a typed amount `$60.00` beside RECON | The typed amount never reaches the bill — the line is RECON's own **$75.00** (BR-BIL-007/020) |
| TC-8 *(isolation)* | Lone Star Ridge's clerk sends Brazos Bend's RECON code | Refused as unknown; its dropdown lists only its own codes |

**4 · Test Data** — `OTB` fixture (epic §AMENDED 2026-09-30): RECON Reconnection fee **$75.00** (marked taxable — irrelevant until US-BIL-035), NSF $30.00, MTEST $40.00; account `AC-2026-00042`; Priya Menon. Isolation: Lone Star Ridge WSC with its own RECON.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Charge code | Step 1 | design §2 | request `charge_code` → `rating.charges` (read) | code | reference-data | required for Fee; the tenant's, active, flat, with a GL |
| Amount | Step 1 / 2 | BR-BIL-007 | `invoice_lines` amount from the code | money, 4 dp stored | reference-data | read-only |
| Note on bill | Step 2 | design §4 | bill payload (no column — DB3) | text | user-input | printed on the bill |
| Bill date · days to pay · due date | Step 1 | design §2, BR-BIL-024 | `bill_runs.bill_date`, `bill_runs.due_days` | date · int · date | user-input · derived | bill date required; days ≥ 0 |
| bill_type | — | BR-BIL-410 | `invoices.bill_type = 'fee'` | enum | system-derived | — |

**6 · Acceptance**
- Given a Fee bill for RECON, Then the bill holds one line of **$75.00**, one group *Charges*, no tax, and it posts and can be paid.
- Given no charge code, Then Continue is refused on that field.
- Given any of BR-BIL-410's four refusals, Then the clerk is told which, and no number is burned.

**7 · Finance Calculation** — Total = the code's own amount: RECON **$75.00**, no tax pass (BR-BIL-410 as built). The taxed figure **$81.19** is US-BIL-035's and is not asserted here.

**8 · Open Questions** — None for this story. Fee TAX is US-BIL-035 (blocked on the B4.2 ❄ re-sign).

---
id: US-BIL-033
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 3
status: ready            # 2026-09-30: ready to build, not blocked
blocked_by: []
depends_on: [US-BIL-005, US-BIL-017, US-BIL-023]
journeys: [J70]
rules: [BR-BIL-005, BR-BIL-014, BR-BIL-016, BR-BIL-019, BR-BIL-024]
golden_tests: []
finance_calc: none
---
### US-BIL-033 — Send: authorise and issue ONE one-time bill, idempotently, only after the clerk acknowledges the amounts

**1 · Details** — As a Billing Clerk at step 4 of any one-time bill, I want one **Send** that authorises and issues this one bill — showing me the total, the due date and every warning, telling me *"Final once sent. Changes need a credit note."*, and unlocking only when I tick *"I checked the amounts"* — so that a one-time bill leaves the building in one deliberate act and can never go out twice. **Written 2026-09-30** from the design (§1 step 4) and the review gap *"No Send"* → *"Send step"*; PO: *"this is all correct"*, *"your drawing is correct now"*. The server side is ONE call, `POST /billing/one-time/{run_id}/send` (build plan A6), over the existing `release.authorise_release` + `release.release_run`, **idempotent**, and **refusing a request that does not carry the acknowledgement**. It carries the delivery choice (email / paper / both — build plan A7). After it succeeds the page shows the **Sent** state: bill number, total, due date, delivery *queued*, meter reads *Locked*, and *View bill* / *New one-time bill*. Issue artifacts are US-BIL-005's, unchanged (number from the tenant series, GL stamps, template pin, delivery queue, balanced posting, audit). Guards (build plan B10, B11): a penalty — and a catch-up under an approval mode that requires it — is refused until approved; the issue gate refuses an already-released row.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| Design §1 step 4 | Total, due date, warnings, *"Final once sent. Changes need a credit note."*, a tick box *"I checked the amounts"* that unlocks Send; then the sent state (bill no., due date, delivery queued). | CONFIRMED — PO 2026-09-30 (design, *"this is all correct"*) |
| Hard rule 6 | Bill runs are idempotent (B2 unique keys). | CONFIRMED |
| Hard rule 4 | An issued invoice is never updated — corrections are new rows (credit note). | CONFIRMED |
| BR-BIL-014 / BR-BIL-019 | Penalty (and gated back-bill) money-bearing writes wait for approval. | CONFIRMED |
| BR-BIL-005 / BR-BIL-016 | Issue mints the number, freezes the invoice, pins the template and queues delivery. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `OTB` interim draft (subtotal **$181.50**, due **Oct 21, 2026**, 1 warning) at step 4 | The card shows the total, **Due Oct 21, 2026**, the warning *No base charge for Electric*, the sentence *Final once sent. Changes need a credit note.*, and the unticked box *I checked the amounts*; **Send is disabled** |
| TC-2 | Tick the box | **Send** enables; unticking disables it again |
| TC-3 | Press Send | ONE call to `POST /billing/one-time/{run_id}/send` carrying the acknowledgement and the delivery choice (*Email*). Response: bill number from the tenant series, total, due date. The page shows **Bill … sent**, *Due Oct 21, 2026*, *Delivery · Email · queued*, *Meter reads · Locked*, **View bill** and **New one-time bill** |
| TC-4 *(negative)* | `POST …/send` without the acknowledgement, or with it false | **Refused** with its own catalogue key; the run stays a draft; no number minted |
| TC-5 *(idempotency)* | Send pressed twice fast, and the request retried after a timeout | **One** invoice and one bill number; the repeat calls return the SAME number and create nothing; one balanced journal entry; one delivery row |
| TC-6 *(negative)* | A penalty draft not yet approved | Refused (awaiting approval); after Alex Reed approves, Send issues it (US-BIL-014 TC-13) |
| TC-7 *(negative)* | Send for a run whose invoice was already released by another path | The issue gate refuses the already-released row; no second number (build plan B11) |
| TC-8 | *View bill* after sending | Opens the issued bill, whose lines equal the Review table line for line |
| TC-9 | Delivery choice *Paper*; then *Both* | The delivery row is queued for paper, not email; *Both* queues both |
| TC-10 | Save draft at step 3, leave, come back | The draft reopens at Review with the same lines; Send works from it |
| TC-11 *(isolation)* | Lone Star Ridge calls `…/send` with Brazos Bend's run id | `404`; nothing issued |
| TC-12 | Every successful send | One `audit_log` row naming the clerk, the run, the invoice and the acknowledgement (hard rule 7) |

**4 · Test Data** — `OTB` fixture (epic); the interim draft of US-BIL-012 TC-18; the penalty draft of US-BIL-014 TC-13; Priya Menon (sends), Alex Reed (approves). Isolation: Lone Star Ridge WSC.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Acknowledgement | Step 4 | design §1 | request body (+ `audit_log`) | bool | user-input | must be true |
| Delivery choice | Step 3/4 | build plan A7 | delivery queue channel (`delivery_seam`) | enum(email\|paper\|both) | user-input | one of three |
| Bill number, due date | Sent state | US-BIL-005 | `invoices` number and due date | text · date | system-derived | tenant series |
| Run id | route only | build plan A6 | `bill_runs.id` | uuid | system-derived | never shown on screen (B14 rule 31) |

**6 · Acceptance**
- Given an unticked box, Then Send is disabled on screen AND refused by the server.
- Given a double press or a retry, Then exactly one bill exists.
- Given a penalty awaiting approval, Then nothing issues until it is approved.
- Given success, Then the Sent state names the bill number, the due date and the queued delivery.

**7 · Finance Calculation** — N/A (it issues the figures the kind's story computed).

**8 · Open Questions** — None.

---
id: US-BIL-034
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 3
status: ready            # 2026-09-30: ready to build, not blocked
blocked_by: []
depends_on: [US-CUS-001, US-CUS-002]
journeys: [J70]
rules: [BR-BIL-024]
golden_tests: []
finance_calc: none
---
### US-BIL-034 — Account search: one searchable dropdown picks the account for any one-time bill

**1 · Details** — As a Billing Clerk at step 1 of any one-time bill, I want one **searchable dropdown** — type a name, an account number or an address; each option shows **name · status · account no. · address** with the match highlighted; ↑ ↓ Enter to pick and Esc to close — and picking fills a **result card** (customer, account, address, plan, status, balance, cycle with its days to pay, last bill), so that I find the right account among tens of thousands without leaving the page. PO 2026-09-30, verbatim: *"this si searchable dropdown"*. Built as a kit component (**AccountCombobox**, build plan F4; B14 rule 43). The search is the server's — `GET /accounts?q=` reused (build plan A1), **paginated** (NFR-3; the ICP runs to 40,000 accounts, and no list is fetched whole and filtered in the browser); it returns status, plan, balance and the cycle's days to pay, which step 1 uses as its default.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| Design §1 step 1 | Searchable dropdown; option = name · status · account no. · address; match highlighted; keyboard ↑ ↓ Enter; picking fills the result card. | CONFIRMED — PO 2026-09-30 |
| NFR-3 / NFR-5 | Every list is paginated by the server; no hard caps. | CONFIRMED |
| B14 rule 31 | No database id is ever the visible value of a field. | RATIFIED |
| BR-BIL-024 *(consumed)* | Days to pay default comes from the account's cycle. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `OTB`; type **Alvarez** | Options: *Maria Alvarez · Active · AC-2026-00042 · 1408 Elm St · Unit A* · *Luis Alvarez · Active · AC-2026-00117 · 22 Birch Ct* · *Alvarez Hardware LLC · Active · AC-2026-00388 · 900 Main St · Suite 2* · *Maria Alvarez · Closed · AC-2025-01904 · 61 Oak Ave*; *Alvarez* is highlighted in each |
| TC-2 | Type **AC-2026-00043** | One option: *Dana Brooks · Active · AC-2026-00043 · 1408 Elm St · Unit B* |
| TC-3 | Type **1408 Elm** | Both units at 1408 Elm St (A: Maria Alvarez, B: Dana Brooks) — address text is searched, walked from the premises (hard rule 8) |
| TC-4 | Keyboard: ↓ ↓ Enter on TC-1's list | The SECOND option is picked; Esc on an open list closes it and changes nothing; the input exposes `aria-expanded` and `aria-activedescendant` |
| TC-5 | Pick *Maria Alvarez · AC-2026-00042* | Result card: Customer **Maria Alvarez** · Account **AC-2026-00042** · Address **1408 Elm St · Unit A** · Plan **Residential Standard** · Status **Active** · Balance **$142.18** · Cycle **Monthly · 21 days** · Last bill **Aug 31, 2026**; step 1's *Days to pay* defaults to **21** |
| TC-6 | Type **zzq** | One row *No account found.*; nothing can be picked |
| TC-7 *(scale)* | A tenant seeded with **40,000** accounts; type **Al** | The request is `GET /accounts?q=Al` with a page size; the response is ONE page; the browser never receives the full list |
| TC-8 *(negative)* | Inspect every option and the result card | No database id appears anywhere as a visible value (rule 31) |
| TC-9 *(isolation)* | Lone Star Ridge's clerk types **Alvarez** | Only Lone Star Ridge's accounts; none of Brazos Bend's |

**4 · Test Data** — `OTB` fixture accounts (epic): AC-2026-00042, -00043, -00117, -00388, -00219 (Pending), AC-2025-01904 (Closed); a 40,000-account scale tenant for TC-7.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Query | Step 1 | design §1 | `GET /accounts?q=` | text | user-input | name / account no. / address |
| Option: name · status · account no. · address | dropdown | design §1 | customers read; address walked from `premises` (hard rule 8) | text | computed-display | no id shown |
| Result card: plan · balance · cycle days · last bill | Step 1 | drawing + build plan A1 | accounts read + the cycle's `due_days` | text · money · int · date | computed-display | add fields to the read if missing |

**6 · Acceptance**
- Given a name, number or address fragment, Then matching accounts appear with the fragment highlighted, from a paginated server search.
- Given the keyboard alone, Then an account can be found and picked.
- Given a pick, Then the result card fills and days to pay defaults from the cycle.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None blocking. Epic **OI-4**: which statuses (Closed, Pending) may be picked for which kind is not in the sources; this story shows every status and refuses nothing by status.

---
id: US-BIL-035
epic: EP-BIL-03
module: billing
screens: [S30, S31]
wave: 3
status: blocked
blocked_by: []           # ⚠ BLOCKED ON THE B4.2 ❄ FINANCE RE-SIGN (HUMAN-GUIDE §6, build plan R3) — NOT on an open question: OQ-812 is CLOSED 2026-09-30 (PO "yes"). No fee-tax code before the re-sign.
depends_on: [US-BIL-032, US-BIL-008]
journeys: [J70]
rules: [BR-BIL-410, BR-RAT-062]
golden_tests: [GT-17]
finance_calc: proposed
---
### US-BIL-035 — Fee bill taxes a charge code marked taxable (BLOCKED — B4.2 ❄ re-sign first)

**1 · Details** — As a Billing Clerk raising a Fee bill from a charge code the tenant marked *taxable* on S13, I want the bill to charge tax on it, so that a taxable fee is taxed like any other taxable line. PO ruling 2026-09-30, verbatim *"yes"* to *"Should a Fee bill charge tax when its charge code is marked taxable?"*, worked on a **$75.00** reconnection fee at **8.25%**: today **$75.00**, taxed **$81.19** (`OQ-812` CLOSED). ⚠ **BLOCKED, and the block is a RE-SIGN, not a question:** B4.2 ❄ defines the tax base as *usage / base / minimum-adjustment* and GT-17 ❄ is one tax pass per bill; a fee bill has no services and never enters that pass, so building this EXTENDS a frozen rule and needs a finance re-sign via HUMAN-GUIDE §6 before any code (decision log 2026-09-30; build plan R3, B7). Until then US-BIL-032 ships fee bills untaxed, and `one_time.ONE_TIME_UNAVAILABLE`'s `a_fee_bill_charges_no_tax_on_a_taxable_charge_code` stays true.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-410 *(its tax clause)* | *"A FEE BILL IS NOT TAXED and `charges.taxable_default` is deliberately NOT read — `OQ-812`."* | **RULED AWAY 2026-09-30** (PO *"yes"*) — takes effect only when B4.2 is re-signed |
| B4.2 ❄ | Tax base = usage / base / minimum-adjustment. | FROZEN — **re-sign required** to include a taxable charge code on a fee bill |
| BR-RAT-062 / GT-17 ❄ | One tax pass per bill over the rounded taxable lines. | FROZEN |

**3 · Test Cases** *(all BLOCKED until the re-sign; written now so the re-sign has its figure)*
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `OTB`; Fee bill, RECON **$75.00**, marked taxable; tax authority **8.25%** | Tax = 75.00 × 8.25% = 6.1875 → **$6.19**; total **$81.19**; one tax line stamped to the authority's liability GL; Review shows Subtotal $75.00 · Tax $6.19 · Total $81.19 |
| TC-2 | Fee bill, NSF **$30.00**, NOT marked taxable | No tax line; total **$30.00** |
| TC-3 | The account carries an account-level tax exemption (US-BIL-008) | No tax; total **$75.00** |
| TC-4 *(negative, before the re-sign)* | Any build of this story while B4.2 is not re-signed | Must not exist — the re-sign is recorded in B4 and the human-review ledger first |

**4 · Test Data** — `OTB` fixture: RECON $75.00 taxable; NSF $30.00 non-taxable; tax authority 8.25%.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Taxable flag | — | `rating.charges.taxable_default` | read | bool | reference-data | — |
| Tax line | Review / bill | B4.2 (after the re-sign) | `invoice_lines` (tax, the authority's GL) | money, 4 dp stored | system-derived | one pass |

**6 · Acceptance**
- Given the B4.2 re-sign is recorded, Then a taxable RECON fee bills **$81.19** and a non-taxable NSF fee bills **$30.00**.
- Given no re-sign, Then this story is not built.

**7 · Finance Calculation** — PROPOSED (ruled by the PO, awaiting the finance re-sign): 75.00 × 0.0825 = 6.1875 → **6.19** → total **81.19**.

**8 · Open Questions** — None open. The blocker is the B4.2 ❄ re-sign (HUMAN-GUIDE §6), which is an act, not a question.

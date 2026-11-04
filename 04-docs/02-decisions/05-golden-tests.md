# B5 — Golden Tests (write BEFORE any billing code)

> **Status (see the ❄️ FROZEN banner at the foot of this file).** Finance-signed 2026-08-08; **the billing-code gate is OPEN**; GT-1..61 are the billing-math contract; verification 33/33 PASS. Every `PLACEHOLDER`/`UNVERIFIED` above that banner is a **SUPERSEDED DRAFT** marker and is stamped inline below with the ruling that closed it (2026-08-10, DEF-023). Changes follow HUMAN-GUIDE §6 (finance re-sign), never inline edits.

> **Part B — human/finance judgment.** Drafted from the prototype as a starting point. Every line marked **PLACEHOLDER** must be confirmed by a human before it is authoritative. — **SUPERSEDED** (drafting convention, 2026-08-07 → finance freeze 2026-08-08: no live PLACEHOLDER remains in this file). Nothing here is extracted fact unless it cites the UI.


> Worked examples the rating/billing engine must reproduce. Rules are now **CONFIRMED per B4 (finance, 2026-08-07)** except where noted; expected totals below assume **round per line item, half-up** and **multiplier-before-tiers** — finance to confirm the two starred items, then freeze as regression fixtures. — **SUPERSEDED** (both starred items are **CONFIRMED (B4.4)** in B4 — round per line item half-up 2dp, and multiplier applied before tier evaluation; fixtures frozen at the finance sitting 2026-08-08.)

## GT-1 — Simple flat residential (single service)
Input: Electric flat $0.12/kWh, base $18.50, usage 684 kWh, tax 8.25% on (usage+base).
Assumed calc: 684×0.12 = 82.08; +18.50 = 100.58; tax 8.2979 → 8.30; **total 108.88**. UNVERIFIED. — **SUPERSEDED** (finance freeze 2026-08-08: rules terminal — tax base = usage+base **CONFIRMED (B4.2)**, round per line half-up 2dp **CONFIRMED (B4.4)**; GT-1..61 signed as the billing-math contract, harness 33/33.)

## GT-2 — Tiered water
Input: tiers 0–2 kgal @ $3.00, 2–5 @ $4.50, 5+ @ $6.00; base $12; usage 3.72 kgal.
Assumed: 2×3.00 + 1.72×4.50 = 6.00+7.74 = 13.74; +12 = 25.74; +tax. UNVERIFIED — tier boundary + rounding per B4. — **SUPERSEDED** (both dependencies terminal: tier evaluation on post-multiplier consumption with thresholds reset each bill **CONFIRMED (B4.4)**, pure tiers only per PO R5 → BR-RAT-026; rounding **CONFIRMED (B4.4)**.)

## GT-3 — Mid-cycle move-in (proration) — CONFIRMED calendar-days, base+usage prorated (B4.3)
Input: move-in day 16 of 30; base $30.50. Base proration 15/30 × 30.50 = **15.25**; usage prorated on calendar days **only when there is no move-in read** (**AMENDED 2026-08-11, PO/finance, HUMAN-GUIDE §6** — with a read the consumption IS the reading and is not prorated again; see B4.3). ✓ rule confirmed. **This fixture pins the FIXED-charge half only**, which is now the complete answer for a read move-in: there is no usage figure to state, because a metered move-in has an actual reading rather than a prorated one. A separate fixture is still owed for the NO-READ case, where an estimate IS prorated.

## GT-4 — Meter rollover
Input: prior 99,800; current 240 (5-digit meter wrapped at 100,000); multiplier ×1. Expected consumption = (100,000−99,800)+240 = 440. UNVERIFIED — rollover not in UI. — **SUPERSEDED** (PO Q&A R7 2026-08-08 → OQ-009 CLOSED, GT-14 rule CONFIRMED: >50%-of-span drop auto-computes the wrap and flags for review; small negative stays a bad-read exception. GT-14 below is the same scenario with the asset-digits span check.)

## GT-5 — Tier crossing with multiplier — CONFIRMED multiplier-before-tiers (B4.4)
Input: raw (current−prior)=274, multiplier ×10 → 2,740 kWh; tiers 0–1000 @0.10, 1000+ @0.14. Multiplier applied first: 1000×0.10 + 1740×0.14 = 100+243.60 = **343.60**. ✓ rule confirmed.

## GT-6 — Credit note against issued invoice
Input: invoice $247.30 issued; billing-error credit $25. Expected: original invoice unchanged (immutable); new credit note references it; balance 222.30; balanced reversing journal entry. UNVERIFIED. — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-012 CLOSED → BR-PAY-011/BR-BIL-009: always reversing entries, never edits, with consequence messaging before the action; immutability itself is B2 + hard rule 4.)

## GT-7 — Partial payment + allocation
Input: balance across BL-A $100 (oldest), BL-B $147.30; payment $120 "oldest first". Expected: BL-A paid 100, BL-B paid 20, remaining 127.30. UNVERIFIED — allocation order (B4). — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-010 CLOSED → BR-PAY-010: oldest invoice first; within an invoice usage+base → taxes → fees/late last; overpayment carries as credit; tenant-reconfigurable. GT-35..50 (PE workbook) are the full composite fixtures.)

## GT-8 — Late fee — CONFIRMED prior-balance, grace from Due date (B4.1)
Input: overdue portion $542.10 (only the past-due part, not full balance), past Due date beyond grace. `late_fee = max(5, 0.015×542.10) = max(5, 8.13) = 8.13`. ✓ formula + overdue-portion base confirmed; **grace-days number still PLACEHOLDER** — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-005 CLOSED → BR-BIL-008: tenant-defined, default 5 calendar days after due date, range 0–30); waiver is manual.

## GT-9 — Estimated read + true-up
Input: missing read, trailing-3 avg = 618 kWh billed; next cycle real read implies actual 700 → true-up +82 kWh on that bill. UNVERIFIED — estimation math + true-up mechanics. — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-003 CLOSED: trailing-3-cycle daily average × days in period, actuals only, max 2 consecutive estimates, true-up via register arithmetic at the next actual at current-period rates — shipped as tenant-configurable DEFAULTS, and "GT-9 tests the default". GT-29 (WE-13) is the full composite.)

## GT-10 — Tax base excludes fees — CONFIRMED (B4.2)
Input: usage $82.08 + base $18.50 = $100.58 taxable; late fee $8.13 NOT taxable; tax 8.25% × 100.58 = 8.30. Total = 100.58 + 8.13 + 8.30 = **117.01** (fee added after tax). ✓ rule confirmed. **RE-SIGNED 2026-08-10 (Product Owner, finance authority, HUMAN-GUIDE §6): was 116.01, an arithmetic error of exactly $1.00 against this line's own addends.** Corroborated three ways before the change: GT-10's own addends sum to 117.01; GT-11 (this bill, tax-exempt) states 108.71 and adding GT-10's tax 8.30 gives 117.01; GT-1 states 108.88 and adding GT-8's frozen fee 8.13 gives 117.01. 116.01 was reachable only from a fee of 7.13 or a tax of 7.30, both frozen otherwise. It survived the 2026-08-08 freeze because `10-scripts/03-golden-verify.py` recomputes only GT-17..GT-61 — GT-1..GT-16 had never been machine-checked (DEF-028).

## GT-11 — Exempt account — CONFIRMED account-level (B4.2)
Input: same as GT-10 but account flagged tax-exempt. Tax = 0 regardless of service. Total = 100.58 + 8.13 = **108.71**. ✓ rule confirmed.

Each GT needs: fixture inputs, confirmed expected outputs (invoice lines, totals, ledger postings), and a test asserting immutability where relevant.

## Added 2026-08-08 — PROPOSED golden tests (skip until Product Owner ratifies the underlying rules)
## GT-12 — Net-metering credit (OQ-001)
Imports 812 kWh, exports 964 → net −152 → bank +152 kWh; bill = base only (never offset). Next cycle net +540 → draw bank 152, bill 388 kWh through tiers.
## GT-13 — Minimum bill (OQ-007)
Usage $6.10 + base $12.00 = $18.10 < minimum $25.00 → adjustment line $6.90; tax on $25.00.
## GT-14 — Rollover with asset digits (OQ-009)
5-digit register, prior 99,800, current 240, ×1 → (100,000−99,800)+240 = 440 (span check: 99,560 > 50% of 100,000 → rollover, not negative-read).
## GT-16 — Opening-balance aged import + balanced opening JEs (BR-CUS-048/049) — PROPOSED (EP-CUS-07 · US-CUS-021/022; freeze with finance)
Input: cutover 2026-08-31; imported account A-12103 opening buckets Current 84.20 / 31–60 62.10 / 61–90 0.00 / 90+ 121.00 (USD).
Expected: `accounts.balance` = **267.30** (Σ buckets, exact — no recompute); day-one aging report reproduces the four buckets verbatim; one opening JE dated **2026-08-31**, source_type `opening_balance`: **DR AR 267.30 / CR opening-balance clearing 267.30** — balanced pair written ONLY by the ledger posting service, immutable (corrections via J6, never edits); batch check: Σ of all opening JEs = Σ of all imported buckets (fixture batch: 1,213 accounts → clearing credit = total migrated AR $184,320.55); re-posting the same batch is idempotent (no second JE set). Forward-aging derivation for finance to confirm at freeze: buckets age by calendar days from the cutover as-of date — 30 days later unpaid, the fixture reads 31–60 ← 84.20 · 61–90 ← 62.10 · 90+ ← 121.00. Negative (credit) buckets out of scope pending OQ-065.

## GT-15 — Capacity charge (solar + battery) [PROPOSED — freeze with finance]
Spec lives in B4 (§GT-15, PO R1): solar 4 units @ $10 + battery 2 @ $12 → $40.00 + $24.00 lines; taxable like base; prorated per B4.3 (WE-16: 10/31 days → $12.90). **AMENDED 2026-08-11 (PO ruling): BOTH lines prorate.** The $12.90 above is the SOLAR line ($40.00 × 10/31); the battery line prorates too — $24.00 × 10/31 = **$7.74**. WE-16 stated only the solar figure, which is why the battery line read as exempt. **Still open: whether the two round per line ($12.90 + $7.74 = $20.64) or once ($20.65)** — a one-cent fork that B4's round-only-at-finalization rule implies per-line, pending confirmation. Registered here so GT numbering has no hole (was cited by rating/customers packs while defined only in B4).

## Freeze punch-list (with finance, before any billing code)
1. Deposit-interest golden test — allocate the next GT number (rule confirmed: tenant simple annual rate, default 0% — BR-CUS-057; worked: $150 @ 2%, 89 mo → $22.25).
2. Deposit-differential-on-plan-change formula (B4 roll-up note) — sign or defer.
3. Tax-exemption certificate capture/expiry (B4 §Tax) — sign scope.
4. WE-1..WE-18 (07-billing/08-worked-examples.md) → formal GT numbers at freeze.

## GT allocation — workbook scenarios formalized (PO CL-3/CL-4, 2026-08-08; finance verifies at freeze)
Mechanical allocation, offsets fixed: **WE-n → GT-(16+n)** (billing workbook, GT-17..34) · **PE-n → GT-(34+n)** (payments workbook, GT-35..50) · **LE-n → GT-(50+n)** (finance workbook, GT-51..60) · **GT-61 = deposit interest** (BR-CUS-057; $150 @ 2.0%, 89 mo → $22.25). Where a new GT refines a legacy one, both stand until finance dedupes at freeze: GT-19 (WE-3 minimum bill) refines GT-13 · GT-20/21 (demand) refine GT-5 principle · GT-22 (first bill) refines GT-3 · GT-29 (estimate+true-up) refines GT-9 · GT-31 (capacity proration) refines GT-15 · GT-60 (LE-10 opening) ties GT-16. Expected values = the machine-computed workbook figures verbatim (07-billing/08-worked-examples.md · 08-payments/07-pre-session-model.md §13 · 09-ledger/08-worked-examples.md).

## Punch-list status (2026-08-08 — all four items CLOSED by PO; freeze = verification pass)
1. Deposit-interest GT = **GT-61** ✔ (CL-4). 2. Deposit differential: **NO recompute on plan change in v1** — deposit fixed at move-in until final-bill settlement; differentials v1.1 (CL-5 option b → BR-CUS-062). 3. Tax-exemption certificate: v1 = flag + certificate ref # + optional file attachment + **expiry date with warning** (CL-6 option a → BR-CUS-063). 4. Seed chart DRAFT below (CL-7 option a) — finance signs at freeze.

## Seed chart of accounts — DRAFT for finance signature (CL-7; proven by the workbook trial balances)
1000 Cash · 1010 Undeposited funds · 1200 Accounts receivable [AR designation] · 1210 Unbilled AR (accruals) · 2200-series Tax payable per authority (tenant authorities mint their own) · 2300 Customer deposit liability [deposit designation] · 2400 Customer credit balances · 3000 Opening balance clearing [opening designation] · 4100/4105 Electric usage/base · 4110/4115 Water usage/base · 4120 Sewer · 4130 Trash · 4140 Gas · 4145 Broadband · 4150 Capacity (solar/battery) · 4190 Minimum-bill adjustment · 4200 Late-fee revenue · 4210 NSF & other fee revenue · 6800 Bank fees · 6900 Bad debt [write-off designation] · 6950 Deposit interest expense. Tenant-customizable per BR-LED grid; export codes per BR-LED-014.

# ❄️ FROZEN — finance-signed 2026-08-08 (Product Owner, finance authority)
Chart of accounts: **SIGNED** as drafted. GT dedupe: **CONFIRMED** — all six overlap pairs keep both (legacy = narrow unit fixture, workbook GT = full composite). Verification: 10-scripts/03-golden-verify.py — 33/33 PASS. GT-1..61 are the billing-math contract; changes from here follow HUMAN-GUIDE §6 (finance re-sign), never inline edits. **The billing-code gate is OPEN.**

---

## ❄️ ADDENDUM — 2026-08-11: two revenue accounts added to the seed chart (finance re-sign)

**This is an ADDENDUM, not an edit.** The frozen line above still reads exactly as
finance signed it on 2026-08-08 and names EIGHT per-service revenue accounts.
CLAUDE.md is explicit that a signed figure changes by re-sign and *"never an
inline edit"*, so the two additions live here, dated, with the ruling that made
them.

**What was wrong.** The platform service catalogue has TEN services; the signed
chart names revenue accounts for eight. `storm_water` and `thermal_heat` had
none, and BR-BIL-010 makes a revenue account REQUIRED per service. A tenant that
enabled Storm water and billed a **$38.50** usage line had a line whose GL
account could not resolve, and because the stamp is atomic that tenant could not
issue **any** bill containing a storm-water line — not just that line.

**The ruling.** PO, 2026-08-11, closing OQ-115: *"A, you create an account, but
allow tenant user to override it - also note every Utility may not have every
account."* The re-sign was granted separately the same day, verbatim: *"okay"*,
in direct answer to "Finance re-sign for the two new revenue accounts". The PO
acts as the finance signatory under their own standing ruling of 2026-08-11
(*"I'm reviewing all billing logic and details in chat itself … that's what
human review for me"*).

**Added to the seed chart, following the chart's own 41xx ladder:**

| Code | Name | Type |
|---|---|---|
| 4160 | Storm water | revenue |
| 4170 | Thermal / Heat | revenue |

**Two things this addendum does NOT change**, because neither was put to finance:

1. **The 2200-series is still not seeded.** The signed line says *"Tax payable per
   authority (tenant authorities mint their own)"* — so an account arrives when a
   tenant creates an authority, and seeding one would invent an authority no
   tenant asked for (BR-TEN-037).
2. **Nothing else in the chart moves.** No code is renamed, no designation is
   reassigned, and every frozen figure that cites this chart is unaffected —
   these two services appear in no GT case.

**Consequence for the code:** `apps/ledger/chart.py` carried both rows with
`signed=False` and listed them in `PENDING_FINANCE_RE_SIGN` precisely so this
gap could not be mistaken for a signature. That marker is lifted by this
addendum and by nothing else.

---

## ❄️ ADDENDUM — 2026-09-08: SIX SEWER FIGURES RE-SIGNED (finance re-sign, HUMAN-GUIDE §6)

**This is an ADDENDUM, not an edit.** The frozen line above still reads exactly as
finance signed it on 2026-08-08. CLAUDE.md is explicit that a signed figure changes
by re-sign and *"never an inline edit"*, so the change lives here, dated, with the
ruling that made it and with a full statement of what was shown.

**THE RULING.** `CR-081` (PO 2026-09-07): *"we ahve to apply this method - Way 2 —
what you described: a percentage of the gallons"*. That reverses `BR-RAT-010`, which
the same PO closed on 2026-08-12 on the CHARGE basis (`PO R1 Q8`) and from which
`BR-RAT-015` was written. **`BR-RAT-015` is SUPERSEDED; its successor is
`BR-RAT-1015`.** Because six ❄️ frozen figures move, the change process stopped at
step 2 and went to a re-sign. The PO signed on 2026-09-08, verbatim:

> **"C — factor 90%, rate $5.00 → $36.00, which is what a real sewer customer
> actually pays"**

**WHAT WAS SHOWN, BECAUSE A SIGNATURE COVERS ONLY THAT.** Three packages with their
trade-offs — **A** keep 40% at `$5.00` (money barely moves; 40% stops meaning
anything real), **B** keep 40% at `$2.25` (the factor means what it says, but `$2.25`
is below every municipal rate found), **C** factor **90%** at **`$5.00`** — together
with the statement that **C more than doubles all six signed figures**, that A and B
both leave sewer at about a third of market, and the recommendation they accepted:
*"it is honest; it more than doubles all six signed figures, which is the cost of
being right"*.

**THE SIX FIGURES, AND WHAT MOVES WITH THEM.** Every amount below was recomputed
from raw inputs by `10-scripts/03-golden-verify.py` (**33 PASS / 0 FAIL**), never by
hand.

| GT / WE | water | sewer qty at 90% | sewer was | **sewer is** | that bill's total was | **is** |
|---|---|---|---|---|---|---|
| `GT-17` / `WE-1` (the reference bill) | 8 kgal | 7.2 kgal | $15.80 | **$36.00** | $292.87 | **$314.97** |
| `GT-18` / `WE-2` (the same bill, exempt) | 8 kgal | 7.2 kgal | $15.80 | **$36.00** | $271.90 | **$292.10** |
| `GT-20` / `WE-4` (small commercial) | 12 kgal | 10.8 kgal | $24.96 | **$54.00** | $853.46 | **$885.24** |
| `GT-25` / `WE-9` (correction + rebill) | 6 kgal | 5.4 kgal | $10.60 | **$27.00** | rebill $227.95 | **$245.90** |
| `GT-26` / `WE-10` Jan–Mar (tariff v3) | 6 kgal | 5.4 kgal | $10.60 | **$27.00** | $305.18 | **$410.77** |
| `GT-26` / `WE-10` Apr–Jun (tariff v4) | 6 kgal | 5.4 kgal | $11.24 | **$27.00** | (same bill) | |
| `GT-28` / `WE-12` (vacation hold) | 3.1 kgal | 2.79 kgal | $4.96 | **$13.95** | $105.36 | **$115.20** |

Taxable subtotals and tax splits move with them: `WE-1` **$242.10** → tax **$22.87**
(15.13 + 2.42 + 4.84 + 0.48) · `WE-4` **$808.80** → **$76.44** (50.55 + 8.09 + 16.18 +
1.62) · `WE-9` **$220.10** → **$20.80** (13.76 + 2.20 + 4.40 + 0.44) · `WE-10`
**$375.30** → **$35.47** (23.46 + 3.75 + 7.51 + 0.75) · `WE-12` **$105.25** →
**$9.95** (6.58 + 1.05 + 2.11 + 0.21). `WE-1`'s posting is `4120 36.00` against
`DR AR 269.97` and `2200-03 22.87`, which foots.

⚠ **`WE-2` IS NOT A SEVENTH SIGNED FIGURE.** It is `WE-1`'s own taxable subtotal with
the tax lines removed, and that subtotal is explicitly part of what was signed.

⚠ **THE 90% IS NOT THE 40% MOVED UP — IT IS A DIFFERENT KIND OF NUMBER.** The 40 was
a **price ratio**: what sewer cost relative to water's money. The 90 is a
**return-to-sewer factor**: the share of metered water that physically reaches the
sewer, sourced at 79–95% across North American municipal utilities and clustering on
90%. ⚠ **AND THE IRRIGATION ALLOWANCE IS NOT MADE BY LOWERING IT.** The industry's
answer to a garden hose is **winter-quarter averaging** — billing sewer on the
cold-months water average — which B4 has carried as *"winter-averaging v1.1"* since it
was written and which this product does not do. Recorded as the road not taken so
nobody later "fixes" the 90 down to allow for gardens, which would under-bill every
apartment and every commercial account that waters nothing.

⚠ **WHAT THIS ADDENDUM DOES NOT COVER, STATED RATHER THAN LEFT TO BE FOUND —
`OQ-RAT-12347`, OPEN WITH THE PO.**

1. **`GT-22` / `WE-6` carries a SEVENTH sewer figure on a SIXTH worked example and
   was not shown.** Its line reads `Sewer 40%×19.23 = 7.69`; on the ruled basis it is
   90% × 4.2 kgal × $5.00 = **$18.90**, taking that bill's taxable from $102.53 to
   **$113.74** and its total from $287.23 to **$299.49**. **It is NOT moved.**
2. **The payments and finance workbooks consume `WE-1`'s total as an INPUT.**
   `GT-36`/`37`/`38` (PE-2/3/4), `GT-41` (PE-7), `GT-44` (PE-10) and `GT-51` (LE-1)
   all start from **$292.87**, which is now **$314.97** — a difference of **$22.10**;
   `GT-44` also starts from `WE-12`'s $105.36, now $115.20, a difference of **$9.84**.
   **None is moved.**

Both are recomputed BOTH ways on every run by the harness's new **Part 4**, counted
separately from the 33, so the gap is a number on the screen rather than a silence —
and so it cannot be closed by accident in either direction while it is with the PO.

**Consequence for the code:** `apps/rating/pricing/models/percent_of_service.py`
prices a VOLUME and the line carries a quantity, the basis service's unit and sewer's
own rate; `apps/rating/engine.py`'s second pass hands `basis_quantity` + `basis_unit`
across (renamed from `basis_amount` on purpose, so an unconverted caller fails loudly
rather than multiplying kgal by a price-per-kgal); and
`apps/rating/migrations/0028_cr081_sewer_volume_basis.py` gives every existing sewer
version the rate it has never had. Shipped at version **`2.230.0`**.


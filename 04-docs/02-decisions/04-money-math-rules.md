# B4 — Money Math Rules (FINANCE MUST AUTHOR)

# ❄️ FROZEN — finance-signed 2026-08-08 (with B5). Zero placeholders; every rule terminal; verification harness green (33/33).

> **Reading order (moved to the top 2026-08-10 — DEF-023; banner text unchanged).** This banner supersedes every marker below it. The sections between here and the 2026-08-08 addenda are **SUPERSEDED DRAFT**: each surviving `PLACEHOLDER` in them is stamped inline with the ruling that closed it. Newest-wins — the addenda, the PO Q&A rounds, the status roll-up and the CL round at the foot of this file are the live text. The billing-code gate is **OPEN** (B5 freeze, same sitting; GT-1..61 are the billing-math contract). Changes from here follow HUMAN-GUIDE §6 (finance re-sign), never inline edits.

> **Part B — human/finance judgment.** Drafted from the prototype as a starting point. Every line marked **PLACEHOLDER** must be confirmed by a human before it is authoritative. — **SUPERSEDED** (drafting convention, 2026-08-07 → finance freeze 2026-08-08: no live PLACEHOLDER remains in this file). Nothing here is extracted fact unless it cites the UI.


> ⚠ **Highest-risk numbers in the system.** Confirmed answers below are marked **CONFIRMED (finance, 2026-08-07)**; anything still open stays **PLACEHOLDER** — **SUPERSEDED** (drafting convention, 2026-08-07 → finance freeze 2026-08-08: nothing is still open). Money type is `NUMERIC(18,6)`, round to 2dp at invoice-line finalization (B2).

## Consumption
- `consumption = (current_read − prior_read) × meter_multiplier`. Multiplier ×10 seen. **CONFIRMED:** multiplier applies **before** tier evaluation (B4.4). **OWNERSHIP CLARIFIED 2026-08-11 (Product Owner) — the RULE above is unchanged; this says WHICH MODULE performs it, which B4.4 never stated.** **Metering applies the meter multiplier; the pricing engine never does.** The multiplier is a property of the **meter** (`assets.Asset.multiplier`), not of the tariff — two meters on one tariff have different multipliers, so a tariff-carried multiplier could only ever be right by coincidence. Consumption therefore leaves metering as a real quantity in a real unit, and the engine **refuses** a tariff that still carries a multiplier rather than ignoring the field: a caller that sets it believes the engine multiplies, and if that caller also came through metering the quantity is already multiplied. Measured cost of the double: a dial delta of 1,247 at ×10 is 12,470 kWh; at ×40 it is 49,880 kWh ≈ $4,853, and multiplied twice 1,995,200 kWh ≈ **$194,113** — on a bill with no structural sign of error. **No finance re-sign was required or taken:** B4.4 fixes the order and is silent on the owner, and GT-5 line 25 already states its input both ways (`raw (current−prior)=274, multiplier ×10 → 2,740 kWh`), so the frozen case now walks left-to-right through the two modules owning each half with every frozen figure reproduced (274 · ×10 · 2,740 · 100 · 243.60 · 343.60).
- Rollover (meter wraps past max): **PLACEHOLDER — not shown in UI; confirm handling.** — **SUPERSEDED** (PO Q&A R7 2026-08-08 → OQ-009 CLOSED: addendum OQ-009 wrap formula `(10^digits − prior) + current` on a >50%-of-span drop, small negative = bad-read exception; GT-14; BR-MET rollover rules.)

## Tiered / inclining
- Charge = Σ over tiers of `min(usage_in_tier, tier_span) × unit_price`, evaluated on **post-multiplier** consumption. **CONFIRMED:** tier thresholds **reset each bill**, and for short/long periods the tier **thresholds scale with the prorated period** (B4.4).

## TOU / Demand
- TOU: usage split into windows × window price. Demand: peak kW × demand rate. **PLACEHOLDER — measurement + ratchet rules.** — **SUPERSEDED** (status roll-up 2026-08-08 → BR-RAT-014/021/033, ratchet OFF per RD-4; addendum OQ-006 + PO R1 demand-v1 scope + PO R3 TOU Option B.)

## Base charge & minimum bill
- Base charge added per plan per cycle. Minimum bill: if (usage charge + base) < minimum, bill minimum. **PLACEHOLDER — confirm interaction.** — **SUPERSEDED** (status roll-up 2026-08-08 → BR-RAT-016/028 + GT-13; PO R1 minimum bill IN for v1, PO R5 both modes (per-service + plan floor), addendum OQ-007 "minimum bill adjustment" line taxable like base.)

## Tax (rates EXPLICIT, base CONFIRMED)
- TX State 6.25% + Travis County 1.00% + City franchise 2.00% + PUC 0.20% (UI). Setup shows "Texas · State + Local (8.25%)".
- **CONFIRMED (B4.2):** tax base = **usage + base charge only** (fees and late charges are NOT taxed).
  > ❄️➡️ **EXTENDED 2026-09-30 FOR A FEE BILL ONLY — finance re-sign, HUMAN-GUIDE §6 (PO ruling of the same day, closing `OQ-812`).** A bill whose ONLY content is charge-code lines (`bill_type = fee`) is taxed when its charge code is marked taxable (`charges.taxable_default`); on every other bill the line above stands exactly as signed, and a fee or late charge riding an ordinary bill is still NOT taxed. See the ❄️ ADDENDUM of 2026-09-30 at the foot of this file for what was shown and what it does not cover. This is an ADDENDUM to a ❄️ FROZEN file, never an inline edit: the signed line above stands exactly as finance signed it.
- **CONFIRMED 2026-08-11 (Product Owner) — the tax base is summed from the ROUNDED line amounts, not from unrounded intermediates.** B4.4 fixes rounding (half-up, 2dp, at line finalization) and B4.2 fixes which lines are taxable, but neither said whether tax is charged on the finalized figures or on the values behind them. It is the finalized figures — the amounts the bill prints. Difference: at most 1¢, and only when the tax lands within a fraction of a cent of a half-cent boundary. Worked case put to the PO: four taxable lines of $124.11 + $18.50 + $11.02 + $12.00 = $165.63 rounded (tax **$13.66**) against $124.1132 + $18.50 + $11.0232 + $12.00 = $165.6364 unrounded (tax **$13.67**). **The reason is reproducibility, not precision** — unrounded is fractionally more accurate, but under it a customer who adds up the four printed lines and applies the rate gets $13.66 while the bill says $13.67, so the printed document does not foot against itself. GT-1 and GT-10 are exact under either reading ($100.58 × 8.25% = 8.2979 → **8.30** both ways), which is why no frozen figure decided this and the ruling was needed.
- **CONFIRMED (B4.2):** tax exemption is **account-level** — when an account qualifies for exemption it is exempt regardless of service; exemption is **not** decided per service type. → data model needs an account-level exemption flag/certificate (see schema note below).
- **PLACEHOLDER:** exemption evidence/certificate capture + expiry. — **SUPERSEDED** (PO CL round 2026-08-08 → CL-6 option a → BR-CUS-063: flag + certificate ref # + optional file attachment + expiry date with warning.)

## Late fee (rule CONFIRMED)
- `late_fee = max(5.00, 0.015 × prior_balance)`. **CONFIRMED (B4.1):** computed on the **prior balance**, and the grace period is counted **from the Due date**.
- **CONFIRMED (B4.1):** grace is configurable as **Calendar days OR Business days** (tenant setting) — implement both modes.
- **BOUNDARY RULED 2026-08-11 (Product Owner) — the fee applies STRICTLY AFTER the grace days elapse, in BOTH modes.** EP-BIL-01 §7 carried two worked examples that disagreed by one day: WE-15(d) (calendar) had the fee apply after the grace days ran out, WE-15(e) (business) had it apply **on** the day they expired. Neither B4 nor B5 froze the boundary — GT-8 states the condition in words. Worked case put to the PO: due **Thu 10 Sep 2026**, grace **5** → calendar mode charges on **Wed 16 Sep**; business-day mode counts Fri 11 · Mon 14 · Tue 15 · Wed 16 · Thu 17 and charges on **Fri 18 Sep**, not Thu 17. A customer paying on the 17th owes nothing where the other reading owed $8.13. **Reason: "five days of grace" must mean the customer has five days**, and where a rule is genuinely ambiguous the customer-favourable reading is the defensible one for a regulated utility. The engine already applied WE-15(d)'s convention to both modes and had flagged it; this ruling closes the flag rather than changing the code.
- **HOLIDAYS RULED 2026-08-11 (Product Owner) — in business-day mode the clock SKIPS public holidays; delivered as its own scoped change.** Business days are Monday–Friday **and today that is all they are**: Christmas Day counts as a business day for this clock. A tenant holiday calendar exists but is scoped to TOU day-types (BR-RAT-021/033) and nothing extends it here. Worked case put to the PO: due **Thu 24 Dec 2026**, grace 5 business days → Mon–Fri-only counts Fri 25 (Christmas) · Mon 28 · Tue 29 · Wed 30 · Thu 31 and charges the fee on **Fri 1 Jan**, New Year's Day; holiday-aware counts Mon 28 · Tue 29 · Wed 30 · Thu 31 · Mon 4 Jan and charges on **Tue 5 Jan**. Four days of grace, and a fee assessed on a public holiday. **This is the one batch-1 ruling that is NEW WORK rather than a confirmation** — until it lands, the Mon–Fri behaviour stands and is stated in the late-fee module's own docstring rather than implied correct.
- **CONFIRMED:** the fee applies to **only the overdue portion** of the balance (not the full past-due balance). First-time waiver is a **manual decision** (staff toggles "Waive first-time" per case) — not an automatic rule.
- **CONFIRMED:** grace mode is Calendar or Business days (tenant setting). **PLACEHOLDER:** the grace-length number (days after Due date) — still needed. — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-005 CLOSED → BR-BIL-008: tenant-defined, default 5 calendar days after due date, range 0–30.)

## Proration (Change plan / mid-cycle) — CONFIRMED
- **CONFIRMED (B4.3):** proration is by **calendar days**. The **base charge is always prorated**. **USAGE IS PRORATED ONLY WHEN THERE IS NO MOVE-IN READ** — **AMENDED 2026-08-11 (Product Owner, finance authority, HUMAN-GUIDE §6).** The original text said base *and* usage are prorated unconditionally, which is wrong wherever a meter was actually read: with a move-in read the 15 days of consumption **is** the reading, and prorating it a second time would understate the bill. So: **metered/variable usage with a read → NOT prorated, the reading is the consumption**; **no read (estimated period) → the estimate is prorated on calendar days**; **fixed charges → always prorated** (that is the $15.25 in GT-3). The PO's words: *"usage you don't have to prorate in case of variable since you will have reading and consumption; in case of fix you have already prorated."* The clause was not deleted because it is right for the no-read case — it was given the condition it always needed.
- **PLACEHOLDER:** deposit-differential formula; whether tier boundaries scale with the prorated period (see Tiered note). — **SUPERSEDED**, both halves: deposit differential (PO CL round 2026-08-08 → CL-5 option b → BR-CUS-062: **no recompute on plan change in v1**; deposit fixed at move-in until final-bill settlement, differentials v1.1) · tier-boundary scaling (already **CONFIRMED (B4.4)** in §Tiered above — thresholds scale with the prorated period).

## Credits / adjustments / reversals
- Adjust: Credit reduces / Debit increases balance, against a GL account (A6). Credit apply: next bill / open bill / refund.
- **PLACEHOLDER:** void = reversing journal entry (assumed, B2 immutability) — confirm. Reversal windows. — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-012 CLOSED → BR-PAY-011/BR-BIL-009: always reversing entries; free void while unpaid + same period, else reverse payment first + Admin/Executive approval; windows ACH 60d · card 120d · check unlimited (NSF); user-facing consequence messaging before any void/reversal.)

## Payment allocation
- Default "oldest open bill"; options specific bill / carry credit / split (A2). **PLACEHOLDER:** partial-payment allocation order; overpayment handling. — **SUPERSEDED** (PO Q&A R6 2026-08-08 → OQ-010 CLOSED → BR-PAY-010: default order = oldest invoice first; within an invoice usage+base → taxes → fees/late LAST; overpayment carries as credit, auto-applies, refundable; tenant may reconfigure the order.)

## Rounding — CONFIRMED
- **CONFIRMED (B4.4):** round **per line item**, **half-up**, 2dp.

## NSF / reconnect fees
- NSF $30.00, reconnect $45.00 shown in UI are **SAMPLES ONLY** (CONFIRMED) — real values are tenant-configured charge codes; do not hardcode.

## Schema impact of confirmations
- Tax base = usage+base → invoice-line rows must carry a **taxable** flag so fee/late lines are excluded from the tax base.
- Account-level exemption → add `accounts.tax_exempt boolean` + optional `tax_exempt_ref`/expiry (B2 change).
- Late-fee grace mode → tenant setting `late_grace_mode` (calendar|business) + `late_grace_days` (number, PLACEHOLDER — **SUPERSEDED**, PO Q&A R6 2026-08-08 → OQ-005 CLOSED → BR-BIL-008: default 5, range 0–30). Fee applies to **overdue portion only**; first-time waiver is **manual** (no auto-rule).

## Addendum — US-market derived defaults (PM, 2026-08-08) [ALL PROPOSED — Product Owner ratifies via session Q&A; see 12-governance/01-open-questions.md]
- **Net metering (OQ-001):** monthly kWh netting per net meter (net = imports − exports). Net>0 bills through the rate schedule (tiers on net); net<0 banks as **kWh credit** (survives rate changes). Base/fixed charges never offset; demand unaffected. Annual true-up (default April): bank cashed out at avoided-cost rate (default $0.03/kWh) if ≥$25, else roll/forfeit per tenant setting. Buy-all/sell-all = v1.1.
- **Read validation (OQ-002):** High >200% of trailing-12-mo avg (trailing-3 if short history) AND delta >50 kWh/1 kgal; Low <25% of avg with usage>0; Zero on active non-vacant; days-threshold flag outside 25–35, hard-stop outside 20–45 (offer prorate-to-30).
- **Estimation (OQ-003):** trailing-3-cycle daily average × days in period, actuals only; max 2 consecutive estimates then forced field visit; true-up via register arithmetic at next actual, current-period rates.
- **Water unit (OQ-004):** register stores raw gallons; billed unit per-service config: kgal (default) / gal / ccf; convert at rating input.
- **Late-fee grace (OQ-005):** 5 calendar days after due date (config 0–30; calendar/business per B4.1).
- **TOU/demand v1 (OQ-006):** 2–3 TOU periods, weekday/weekend, 2 seasons, holidays=off-peak; demand = max-demand register read; ratchet OFF by default (option 80% of 11-mo peak).
- **Minimum bill (OQ-007):** if (usage+base) < minimum → "minimum bill adjustment" line; taxable like base.
- **Sewer % of water (OQ-008):** percent of water usage-charge dollars (excl. base/tax); winter-averaging v1.1.
  > ❄️➡️ **SUPERSEDED 2026-09-08 by `CR-081` / `BR-RAT-1015` (PO ruling 2026-09-07, HUMAN-GUIDE §6 finance re-sign 2026-09-08).** Sewer is now a percentage of the water **QUANTITY**, priced on sewer's own schedule — **90% at `$5.0000`/kgal**, so `GT-17` is **`$36.00`** where it was `$15.80`. The percentage is a **return-to-sewer factor** (the share of metered water that reaches the sewer), not the price ratio the 40% was. **`winter-averaging v1.1` above is now load-bearing rather than a footnote:** it is the industry's answer to irrigation, and **the factor must NOT be lowered instead** — see the ❄️ ADDENDUM of 2026-09-08 in `05-golden-tests.md` for the full re-sign and for what it does NOT cover (`OQ-RAT-12347`). This is an ADDENDUM to a ❄️ FROZEN file, never an inline edit: the signed line above stands exactly as finance signed it.
- **Rollover (OQ-009):** current<prior AND (prior−current)>50% of register span → (10^digits − prior)+current; else negative-read exception; digits from asset spec.
- **Allocation (OQ-010):** oldest invoice first; within an invoice: usage+base → taxes → fees/late LAST (service before fees); overpayment carries as credit, auto-applies, refundable.
- **Deposits (OQ-011):** target 2× estimated monthly bill; plan change re-computes → bill/credit differential; refund after 12 mo with ≤2 lates; interest per state rate.
- **Void/reversal (OQ-012):** free void while unpaid + same period; else reverse payment first + Admin/Executive approval; always reversing entries; ACH 60d, card 120d, check unlimited (NSF).

## PO Q&A round 1 confirmations (2026-08-08)
- Sewer %-of-water: CONFIRMED as proposed (OQ-008 → BR-RAT-015).
- Minimum bill: IN for v1 (OQ-007 partially closed; per-service placement proposed).
- Version retention: 7 years CONFIRMED.
- Demand billing: v1 scope CONFIRMED (measurement rules remain PROPOSED per this addendum).
- **Solar/Battery: capacity-charge model in v1** (rate × account capacity units); OQ-001 kWh-netting proposal DEFERRED to v1.1 — GT-12 reclassified v1.1; new GT needed for capacity charges (GT-15 below).
- Deposits: category-fixed amounts v1 (OQ-011 closed for v1; 2×-avg/per-service/waiver excluded).

## GT-15 — Capacity charge (solar + battery) [PROPOSED]
Account: solar 4 units @ $10, battery 2 units @ $12 → lines $40.00 + $24.00; taxable like base (confirm); prorated on mid-cycle start per B4.3 calendar-day rule (confirm).

## PO Q&A round 6 (2026-08-08) — configurability principle + closures
**Governing principle (PO):** every utility differs — validation/estimation/fee mechanics ship as TENANT SETTINGS with our derived values as seeded defaults, not hardcoded constants.
- **Read validation (OQ-002 CLOSED):** thresholds are tenant-configurable in Settings → "Read validation rules" (surfaced via Reference data area); shipped defaults = the B4 addendum values (high 200%/delta floor, low 25%, zero-on-active, days 25–35 flag / 20–45 hard). BR-MET ID at metering-pack merge.
- **Estimation (OQ-003 CLOSED):** trailing-3 daily-avg × period days + 2-consecutive cap ship as DEFAULTS; tenant may change method parameters in the same settings surface. GT-9 tests the default.
- **Water/UoM (OQ-004 CLOSED):** register unit must MATCH the billed unit or a conversion factor must be defined per service; on mismatch with no factor, the system shows the user a clear message and blocks rating for that read (no silent conversion). Default billed unit kgal.
- **Late-fee grace (OQ-005 CLOSED):** tenant-defined, default 5 calendar days after due date, range 0–30 (BR-BIL-008).
- **Allocation (OQ-010 CLOSED):** default order = oldest invoice first; within invoice usage+base → taxes → fees last; overpayment carries as credit. Tenant may reconfigure the order (BR-PAY-010).
- **Void/reversal (OQ-012 CLOSED):** windows + approval gating as proposed, WITH explicit user-facing messaging: before any void/reversal the UI states what will happen (reversing entries, balance effect, approval needed) (BR-PAY-011/BR-BIL-009).

## PO Q&A round 7 (2026-08-08) — final closures
- **Rollover (OQ-009 CLOSED):** both cases confirmed — huge-gap drop (>50% register span) = auto-compute wrap-around usage + review flag; small negative = bad-read exception, never "fixed" silently. GT-14 rule CONFIRMED.

## Status roll-up (PM, 2026-08-08) — every early PLACEHOLDER above is resolved by the addenda/rules below
Rollover → R7 closure + GT-14 (BR-MET rules). TOU/demand measurement + ratchet → BR-RAT-014/021/033 (ratchet OFF per RD-4). Base/minimum interaction → BR-RAT-016/028 + GT-13. Tax exemption evidence/certificate capture → still with finance at GT freeze. Deposit-differential on plan change → category-fixed model implies new-minus-held; formula to be signed at GT freeze (finance) — NOT yet a confirmed rule. Void/reversal → OQ-012 closure (BR-PAY-011/BR-BIL-009). Allocation → OQ-010 closure (BR-PAY-010). Grace length → OQ-005 closure (BR-BIL-008). Newest-wins reading order stands: addenda + module rules files override the draft sections above.

## PO CL round (2026-08-08) — final B4 placeholders CLOSED
- Deposit-differential formula: RESOLVED — no recompute on plan change v1 (BR-CUS-062); differentials v1.1.
- Tax-exemption certificate capture: RESOLVED — flag + ref # + attachment + expiry warning (BR-CUS-063).
- GT numbering: workbooks formalized GT-17..GT-61 (B5 allocation table). **B4 has ZERO open placeholders; the finance freeze is a verification pass.**

_(The ❄️ FROZEN banner used to sit here. It was moved verbatim to the top of this file on 2026-08-10 — DEF-023 — so the file's status is read before its superseded draft sections. No signed text or figure changed.)_

## ❄️ ADDENDUM — 2026-09-30: A FEE BILL IS TAXED WHEN ITS CHARGE CODE IS MARKED TAXABLE (finance re-sign, HUMAN-GUIDE §6)

**This is an ADDENDUM, not an edit.** B4.2's signed line — *"tax base = usage + base
charge only (fees and late charges are NOT taxed)"* — still reads exactly as finance
signed it on 2026-08-08. CLAUDE.md is explicit that a signed rule changes by re-sign
and *"never an inline edit"*, so the change lives here, dated, with the ruling that
made it and a full statement of what was shown. It follows the shape of the
2026-09-08 sewer re-sign (`05-golden-tests.md`): a stamp under the signed line, this
addendum, and the `G61` pin re-derived in the same commit.

**WHY IT NEEDED A RE-SIGN AT ALL.** B4.2 was written about an ordinary bill, where a
fee rides beside usage and base. The **fee bill** (`bill_type = fee`, DEF-708,
2026-08-27) is a newer shape: an invoice whose whole content is charge-code lines, with
no service and no plan pricing. A tenant can tick *taxable* on a charge code (S13,
`charges.taxable_default`), and until this ruling a fee bill raised from such a code
charged no tax, because the signed rule said fees are never taxed and the fee bill
never entered the engine's one tax pass. `OQ-812` put that to the PO with three
options; **option (b)** was chosen: a fee bill runs its own tax pass over the account's
tax rules. That touches ❄️ B4.2, so it came back as a re-sign.

**THE RULING, VERBATIM.** Put as: *"Re-sign the frozen tax rule so a Fee bill is taxed
when its charge code is marked taxable?"* PO, 2026-09-30: **"Yes, re-sign."**
(Decision log 2026-09-30, *"ONE-TIME BILL: SIX ANSWERS"*, item (1); the question
itself was answered the same day with *"yes"*, recorded on `OQ-812`.)

**WHAT WAS SHOWN, BECAUSE A SIGNATURE COVERS ONLY THAT.** One worked figure: a
reconnection fee, **RECON $75.00**, marked taxable, on an account whose plan carries
Katy's combined **8.25%** — tax **75.00 × 8.25% = 6.1875 → $6.19**, bill total
**$81.19**. `tests/test_oq_812_fee_bill_tax.py` asserts that figure against the
engine, so drift goes RED.

**THE RULE AS BUILT (`apps/rating/engine.price_fee_bill`, `apps/billing/fee_bill.py`).**

- **Only a FEE BILL, and only a code marked taxable.** A code not marked taxable is
  billed exactly as before — no tax line, no engine call. A fee on an ordinary bill
  (a late fee, a penalty's tamper charge, a first bill's connection charge) is still
  kept out of the base by KIND, as the signed line says.
- **ONE tax pass per bill** (BR-RAT-062 / GT-17 ❄️, unchanged): the engine's own
  finalize → compute-tax → assemble stages, one line per authority, each rounded once.
- **The base is the ROUNDED taxable fee lines** — B4.2's 2026-08-11 ruling (base
  summed from rounded line amounts) applies unchanged.
- **The taxes are the account's PLAN taxes**, resolved exactly as an ordinary bill
  resolves them, with **no service list** — so a tax scoped to a service (a franchise
  fee on *electric only*) does not reach a fee.
- **Exemption is account-level and wins** (B4.2 / BR-RAT-006, unchanged), certificate
  expiry included.

**WHAT THIS ADDENDUM DOES NOT COVER, STATED RATHER THAN LEFT TO BE FOUND.** These are
engineering judgments recorded in the decision log of 2026-09-30, not part of what the
PO signed; each fails in the under-charging direction.

1. **Only PERCENT taxes apply to a fee bill.** A flat-per-bill rule (the $0.85 PUC fee)
   and a per-unit rule are not priced on one: the worked figure was a percent of the
   fee, a flat amount is a charge per utility bill rather than tax on the fee, and a
   per-unit rule taxes a metered quantity a fee bill does not have.
2. **A connection QUOTE bill is not taxed yet.** It is also `bill_type = fee`, but New
   Connect work is halted by the PO; its tax is taken up when that work resumes.
3. **An account with no plan refuses a taxable fee by name** rather than issuing it
   untaxed.

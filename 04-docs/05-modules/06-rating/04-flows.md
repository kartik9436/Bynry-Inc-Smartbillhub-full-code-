# Plans & Rates (code: rating) — Flows & States

> Fleshed out 2026-08-09 from BR-RAT-001..043 + EP-RAT-01..06. Screens: S9 (Plans / Rate schedules / Charge codes / Taxes tabs + History) · S10 plan wizard · S11 rate wizard · S12/S13 charge & tax wizards. Engine math is HUMAN-OWNED 🔒 (B4, `engine.py` — Eng Lead writes it; agents scaffold around, never decide). Pure module: reads + tariff version in, priced lines out.

## 1. Plan lifecycle state machine (BR-RAT-030/039/043)

```
DRAFT (S10 wizard, six steps: Basics → Services → Rate schedules → Charges & discounts → Eligibility → Review & publish)
  → PUBLISHED  only published plans are assignable; drafts are never billed (BR-RAT-030)
  → ARCHIVED   blocks new assignment; history + existing accounts untouched until changed (BR-RAT-030; IS-1)
v1 plans are STAFF-ASSIGNMENT ONLY — self-serve offering + zone/route restriction dropped (BR-RAT-039 as-modified)
eligibility (senior/CAP/low-income) = ADVISORY-WITH-AUDIT: staff attests, audit row records who/when;
  enforced verification + documents = v2 (BR-RAT-043)
plan-as-bundle: per-service rate schedules + per-service base (plan base DERIVED as the sum — BR-RAT-012/027),
  plan-scoped deposit/charge/penalty/tax rules with tenant defaults as fallback (BR-RAT-025 D4);
  discounts = negative-amount charge rules; budget billing = plan flag only (BR-RAT-043)
```

## 2. Rate-schedule wizard & versions — S11 (BR-RAT-031 as-modified/019/032)

```
DRAFT (save-draft resumable; excluded from plan-builder pickers — BR-RAT-031)
  → ACTIVATED  requires a COMPLETE structure + effective_from; board approval happens OUTSIDE the system —
               step 3 captures effective dates + regulator reference only; tariff_versions.approved_by =
               optional metadata, never a gate (BR-RAT-031 as-modified, PO R5-1)
  → ARCHIVED   IS-1 — blocked while any plan references it (EP-RAT-02 matrix)
one schedule prices exactly ONE service with ONE model; name is internal (BR-RAT-031)
models (tariff_model, BR-RAT-019): flat · tiered · time_of_use · demand · seasonal · capacity (+ sewer %-of-water structure, BR-RAT-015)
tier validation (BR-RAT-032): seq-ordered · contiguous (tier n+1 From = tier n To) · From < To · only the last
  tier open-ended (To NULL = ∞) · rates ≥ 0 NUMERIC(18,6) · flat = single 0→∞ tier · pure tiers, no allowance (BR-RAT-026)
```

## 3. TOU config validation (BR-RAT-033/021)

`per (season × day-type): windows cover 00:00–24:00 with no overlap (may wrap midnight), ≤3 windows (on/mid/off); 2 seasons with date ranges + per-season prices cover the year without overlap; day-types weekday/weekend/holiday; holidays resolve to the season's OFF-PEAK window via the tenant holiday calendar (S63) (BR-RAT-033/021)`. Reads arrive pre-split per window; optional interval-CSV import aggregates to windows (BR-RAT-021).

## 4. Seasonal validation (BR-RAT-034)

`rate_seasons ranges cover the year without overlap; each season carries its own price set; a season boundary splits the bill period pro-rata by calendar days (B4.3); an ACTUAL read dated on the boundary beats pro-rata (BR-MET-050)`.

## 5. Tariff versioning & rate changes (EP-RAT-04 — BR-RAT-007/017/037/040)

```
SINGLE  edit a live schedule → NEW tariff_versions row (old effective_to closes the day before; windows
        non-overlapping per B2 EXCLUDE) + append-only rate_change_log row with before/after jsonb, actor,
        REQUIRED reason — in-force versions never edited in place (BR-RAT-037)
BULK    one rate_change_batches row = one reason + one effective date + one actor; per-entity rate_change_log
        rows reference the batch; apply is ATOMIC all-or-none; batches append-only, never re-run —
        re-apply = new batch (BR-RAT-040)
CONSUME historical invoices reprice against the version in force on the SERVICE date (BR-RAT-007);
        versions reproducible 7 years (BR-RAT-017); S9 History renders the compliance log
```

## 6. Charge-code lifecycle — S12 (BR-RAT-035/041/043)

`code unique per tenant; service scope Any or one service; IS-1 deactivate-first with 🔒 audit-lock while referenced by plans/invoice lines; prototype amounts (NSF $30, reconnect $45) are SEEDS never constants (BR-RAT-035); amount rules v1 = flat / percent / percent-with-minimum, "Formula" visible but disabled (BR-RAT-041); plan discounts attach as negative-amount charge rules (BR-RAT-043)`.

## 7. Tax config — S13 (BR-RAT-036/042/005/006)

`forms: percent-of-subtotal (rate × B4.2 base — CONFIRMED) · flat-per-bill · per-unit (PROPOSED); taxable base selectors offer ONLY usage + base — fees/late never taxed, no tax-on-tax (BR-RAT-036, B4.2 wins over the prototype checkboxes); per-unit "applies above N units" is MARGINAL — only units above the threshold taxed (BR-RAT-042); exemption is account-level regardless of service (BR-RAT-006)`.

## 8. Engine pipeline 🔒 (EP-RAT-05 — order fixed by the confirmed B4 rules)

```
reads + plan snapshot + in-force tariff version → pure function, no side effects:
  1 UoM gate: read unit matches billed unit or a per-service conversion factor exists — else clear message,
    rating blocked for that read, no silent conversion (BR-RAT-038; default billed water unit kgal)
  2 multiplier BEFORE tier evaluation (BR-RAT-001, GT-5); rollover consumption = (max − prior) + current (BR-RAT-011, GT-14/GT-4*)
  3 proration: calendar days, base AND usage; tier thresholds reset per bill and SCALE with the prorated period (BR-RAT-002/004, GT-2/3)
  4 price by model: flat/tiered (pure tiers — BR-RAT-026)/TOU on pre-split window quantities (BR-RAT-021)/
    demand (qty × rate; measurement rules PROPOSED, ratchet off — BR-RAT-014, BR-MET-051)/seasonal (§4)/
    sewer = % of water USAGE-CHARGE dollars, excl. base excl. tax (BR-RAT-015)
  5 minimum bill: per-service minimums FIRST, then the plan-level floor tops up the total (BR-RAT-016/028, GT-13)
  6 tax base = usage + base only; account-level exemption (BR-RAT-005/006, GT-10/11)
  7 round per line, half-up, 2 dp, at FINALIZATION only (BR-RAT-003)
```

**Split by days — a tariff change INSIDE a back-billed period (PO ruling 2026-08-12, OQ-155: _"Split by days"_).** The period prices as **two day-weighted segments, each at the version in force on those days** — never the whole period at one version, never refused. Step 3 day-weights the BASE CHARGE and the TIER LADDER; **it does not invent usage** — each segment measures from its OWN reads (B4.3 as amended 2026-08-11: metered usage with a read is never prorated). Where the cut day has **no read** the default is a day-weighted usage estimate **marked as estimated** on the bill, with metering's own estimate (BR-MET-026) as a tenant option (OQ-191, PO 2026-08-12); refusal survives only where neither estimate can be produced.
**Worked (WE-10, February water, 6 kgal, 14/28 days each side):** v3 base **4.00** + tier-1 **10.00** + tier-2 **3.25**; v4 base **4.25** + tier-1 **10.63** + tier-2 **3.43** → group **35.56**. ⚠ **Not 35.55**: the question summed v4's tiers before rounding (10.625 + 3.425 = 14.05) and BR-RAT-003 rounds **per line** (10.63 + 3.43 = **14.06**).
**Step 6 still runs ONCE for the whole bill** — every non-tax-bearing segment's finalized lines are carried into the tax-bearing call, so the tax pass sees Σ(rounded taxable lines) exactly as B4.2 requires: on a Jan–Jun sub-period split 90/181 and 91/181, subtotal **75.59** → tax **6.24** in one pass, where taxing each segment apart and summing gives **6.23**.

## 9. Capacity charges (EP-RAT-06 — BR-RAT-018/019/022/029, GT-15)

`account_capacities.units (effective-dated, per service — captured in customers per BR-CUS-012) × capacity_rates.rate_per_unit (tenant-defined unit label + rate — BR-RAT-022) → one line per capacity service; mid-cycle start/change → calendar-day prorated segments (B4.3); taxable like base (BR-RAT-029); no consumption input read at all`. Net-metering kWh export credits = v1.1 (BR-RAT-018 — read capture continues in assets EP-AST-05, unused by rating v1).

## 10. Deposit schedule (BR-RAT-020/023)

`plan_deposit_rules: consumer category (Res/Com/Ind/Gov) → fixed $ amount, PLAN-level (BR-RAT-023; supersedes tenant-level); 2×-average-bill, per-service amounts, credit-tier waivers explicitly OUT of v1 (BR-RAT-020)`. Deposit collection/application/refund flows are customers' (BR-CUS-025).

Unflowed: demand measurement/ratchet detail remains PROPOSED in the B4 addendum — capture-only in v1 (no ratified flow beyond BR-RAT-014 scope + BR-MET-051 manual demand register at cycle read, ratchet off).

Journeys: J2 step 6–7 (plan + schedule feed the run) · GT-1..5/10/11/13/14/15 fixture chain (B5).

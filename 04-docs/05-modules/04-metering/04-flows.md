# metering (Meter Reads) — Flows & States

> Fleshed out 2026-08-09 from BR-MET-001..062 + EP-MET-01..05 (Reads pre-session rulings RD-1..15, PU-1..20). Screens: S14–S16 Premises/Units · S25–S29 Reads · S8 Routes & Cycles · S64 validation settings (tenancy card). Channel model everywhere (BR-MET-059, B2 r8): one record per register per date — `channel` total | tou_on | tou_mid | tou_off | export | demand; flat meter = single `total`.

## 1. Premises & unit lifecycle (EP-MET-01, BR-MET-001/034/036/037/046/047/048)

```
CREATE  single (S16 guided) · bulk pattern generator ≤3,000/run {seq}/{floor} · bulk CSV ≤10,000 rows staged,
        skip-errors ON, "N created · N failed" (BR-MET-005/031/038); premise # from the tenant series (BR-MET-001)
        asset columns may reference existing OR create new inline per BR-AST-028 (BR-MET-039/043)
ACTIVE  occupancy DERIVED from active account, never manual (BR-MET-036): vacant → occupied (move-in) → vacant (move-out)
  → DEACTIVATED: blocked while an active account or unpaid balance exists, blockers shown (BR-MET-047); IS-1 deactivate-first
  → DELETE: unit only if NEVER referenced (account/asset/read); premises only with ZERO units (BR-MET-037/001)
units NEVER move between premises — deactivate + recreate (BR-MET-046, preserves by-premises money traceability)
every change (create/edit/deactivate/plan/asset tag) → audit row; detail views carry a read-only Audit tab (BR-MET-048)
roles: create/edit SysAdmin+Clerk · deactivate/delete SysAdmin · Executive view (BR-MET-035)
```

## 2. Unit plan assignment (BR-MET-040..044)

`none → assigned (single, or bulk multi-select + effective date with per-unit history rows + audit batch — BR-MET-041); plan REQUIRED at account activation — move-in blocks without one (BR-MET-040); normal changes go through the account Change-plan flow (BR-CUS-014); direct unit-level edit = error-correction OVERRIDE with warning + audit, allowed even when occupied (BR-MET-042); after move-out the unit KEEPS its last plan as next-move-in prefill (BR-MET-044)`.

## 3. Routes & cycles (EP-MET-02, BR-MET-008/009/010/033/057)

`route = selected Premises + Units membership with OPTIONAL walk order — no numeric capacity ranges (BR-MET-033); unique code, one cycle at a time (BR-MET-008/010); cycle: read window start ≤ end ≤ bill date, due = bill_date + due_days ≥ 0, read_schedules seeds the next period (BR-MET-009); the read window drives expectations — per-cycle completeness bar + chase list (BR-MET-057)`. S26/S27 are read-only operational views; all CRUD in Settings; progress derives from committed reads, never stored counters (BR-MET-011).

## 4. Read import wizard — S28, 5 steps (EP-MET-03, BR-MET-012..018/032/054/059)

```
1 SOURCE & CONTEXT  batch tags month/cycle/route/service/source inherit to every row unless a row column overrides;
                    effective tags recorded on batch + rows (BR-MET-014); any cadence, batches append per cycle (BR-MET-054)
2 UPLOAD / ENTER    CSV vs the PUBLISHED standard template (BR-MET-032 — rules-based, no per-vendor mapping memory);
                    auto-map by header, meter/date/value required, re-detected every upload (BR-MET-013);
                    optional channel column, absent → total (BR-MET-059); manual grid for a few reads (BR-MET-054)
                    → STAGED batch only — no meter_reads row exists before commit; discarded batches never surface (BR-MET-012)
3 VALIDATION        full rule run over every staged row BEFORE acceptance (BR-MET-032; engine = §6)
4 REVIEW & FIX      severity model (BR-MET-015): ERRORS must be resolved (reject / override / investigate);
                    WARNINGS postable only via explicit accept + reason; disposition + reason stored per row
                    duplicate-vs-committed = error → Reject | Replace-existing (superseding row — BR-MET-016);
                    intra-batch dupes error; row key (meter, date, channel) (BR-MET-052)
                    estimate disposition invokes §7 (per-channel)
5 COMPLIANCE & POST compliance stamp (batch no, source, file+SHA-256, uploaded_by/at, session+IP, certification — BR-MET-017)
                    → atomic commit as an ASYNC job (BR-MET-055) → consumption = (current − prior) × multiplier,
                    NUMERIC(18,6), explicit unit, unrounded (BR-MET-019; billed-unit conversion gate = BR-RAT-038)
                    idempotency: identical file+tags re-submission BLOCKS with who/when/link (BR-MET-018, OQ-044 option b;
                    exact key mechanics Eng-Lead 🔒 — NotImplementedError("OQ-044") until landed)
```

## 5. Read lifecycle state machine (BR-MET-053/054/024)

```
STAGED ──(step-5 commit + flag engine)──→ OK | FLAGGED | ESTIMATED   (= committed; posted reads append-only, BR-MET-017)
COMMITTED ──(priced on an issued invoice)──→ BILLED (LOCKED)
DISPUTED  marker + reason on any committed read → account HELD from the bill run → CLEARED by System Admin only
          (BR-MET-024 + OQ-043 closure; no value change)
CORRECTION = SUPERSEDE, never edit: new row, superseded_by_id/superseded_at chain, original kept visible read-only;
          consumers read the lineage head (BR-MET-016/053)
BILLED-read error → supersede + AUTOMATIC J6 correction path — read fix and money fix travel together (BR-MET-053, US-MET-016)
DELETE allowed for staged/rejected rows only (BR-MET-054)
```

## 6. Validation flag engine (EP-MET-04, BR-MET-020..025/049/052/061/062)

```
runs at import commit + re-runs on override/estimate (BR-MET-022); per channel (BR-MET-059)
thresholds = tenant config read_validation_settings (S64), per service where units differ, NEVER hardcoded;
  PO-ratified seeded defaults (BR-MET-020, OQ-002 closed)
vocabulary (A5 + catalog): OK · High · Low · Zero · Missing · Estimated(1st/2nd) · Days-threshold · Meter-factor · Mismatch
  + negative_usage (HARD ERROR, never auto-fixed; full register wrap = rollover per OQ-009/GT-14, not negative)
  + retired_meter (error) · vacant_unit (warning) · tou_sum_sanity Σwindows≈total ±1% (WARNING — accept+reason only, BR-MET-061)
  + duplicate (meter, date, channel) (BR-MET-052)
mismatch: |master − Σ sub-meters| beyond the master's loss tolerance flags master + group (BR-MET-025)
completeness gate (VEE before billing): required record set per meter = the unit plan's channel set
  (flat → total; TOU → windows; demand → +demand) → incomplete_set outcome (BR-MET-049)
outcomes stored self-describing (rule + thresholds used + computed values); flags NEVER block billing by
  themselves — S31.2 decides (BR-MET-022)
```

## 7. Fix actions & drawer (BR-MET-023/024/030/056/060)

`per-flag options per A2/A5 (High: accept/override/investigate · Zero: accept-vacant/check/skip · Missing: estimate/field-visit/skip · Days: prorate/accept/wait · Factor: confirm/change-multiplier/investigate · Mismatch: investigate/accept); every fix = confirm modal → toast → audit_log (BR-MET-023); override appends a superseding row with required reason + re-validation (BR-MET-024)`. S29 drawer shows the full chain, math, flag reason WITH threshold values, channel, supersession history, dispute/audit (BR-MET-056). S25 lands on **Needs attention** (Missing/Flagged/Disputed KPI chips), full list one tab away (BR-MET-060).

## 8. Estimation & true-up (EP-MET-05, BR-MET-026..030/058/062 — GT-9)

```
MISSING read (S28 step 4 · S25/S29 action · S31.2 toggle)
  → trailing-3-cycle daily average (ACTUALS only) × days in period, NUMERIC(18,6); per CHANNEL from its own
    history (BR-MET-026/058); no history → NO estimate, field visit
  → cap: max 2 consecutive estimates; 3rd consecutive miss FORCES a field visit (BR-MET-027)
  → demand channel is NEVER auto-estimated — always field visit (BR-MET-062)
  → labeled method + consecutive no, status estimated, no register current_value (BR-MET-028)
NEXT ACTUAL read → TRUE-UP: (actual − last_actual) × multiplier − Σ estimated billed, at current-period rates;
  negative trues credit; links to corrected estimates (BR-MET-029)
override/skip an estimate: reason + audit; override supersedes + re-validates; skip leaves the meter missing —
  billing decides the consequence (BR-MET-030, S31.3)
```

## 9. Scale & archival (BR-MET-055)

`server pagination · 2-yr hot-window default + explicit archive search · monthly partitions · async imports · no unbounded read endpoints · archival to cold storage = AUTOMATIC scheduled job (2 yr hot → archive, 7 yr total), never manual`.

Journeys: J2 (premises → unit → read → bill) · J3 (flag → fix/estimate → true-up) · J6 (billed-read correction handoff, §5).

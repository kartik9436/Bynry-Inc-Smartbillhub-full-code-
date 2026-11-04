# assets — Flows & States

> Fleshed out 2026-08-09 from BR-AST-001..042 + EP-AST-01..05 (A5 v4 lifecycle, ADR-004 scope). Screens: S49 list (Meters · Sub-meters · Behind the meter) → S50 detail → modals S51 add / S52 import / S53 maintenance / S54 retire / S55 reassign. Tables are metering-owned (B2 r4); every write goes through metering service functions (B1). Meter-to-cash assets ONLY (BR-AST-001).

## 1. Creation — bidirectional, one registry (BR-AST-028/011/026/033)

```
ASSET-FIRST    S51 modal / S52 bulk import → inventory (assign later)
PREMISES-FIRST unit wizard (S16) auto-creates the asset rows (BR-MET-006/039/043)
both paths land in the SAME registry, never duplicates (BR-AST-028)
identifiers (BR-AST-026): hidden internal uuid (never displayed) + Device ID/Serial # (physical)
  + user asset # auto-allocated from number_series with per-type prefixes M-/SM-/PV-… (free-entry override allowed)
duplicate guard: same serial → warn-but-allow · same asset # → hard block (BR-AST-033)
assign-on-create: unit chosen → first assignment row + status active | leave-in-inventory → inventory (BR-AST-011)
service required for measuring types + explicit UoM, never assumed (BR-AST-009); net_metering locked on for
  net_meter, optional meter/sub_meter, unavailable for non-measuring BTM (BR-AST-010); every create audited (BR-AST-011)
```

## 2. Lifecycle state machine (A5 v4 — BR-AST-020/030/031/002/013)

```
INVENTORY ──(assign/install)──→ ACTIVE ──(flag)──→ NEEDS_REPAIR ──(start)──→ IN_REPAIR ──(fix)──→ ACTIVE
ANY ──(retire: reason + date, optional replaced_by = same-tenant non-retired asset — BR-AST-021)──→ RETIRED (TERMINAL)
  no un-retire — a mistaken retirement is corrected by creating the asset anew with a linked audit note (BR-AST-030)
DELETE only when status = inventory AND never referenced (read/assignment/maintenance/bill line/replaced_by) —
  otherwise blocked with a retire pointer (BR-AST-013); assets referenced by issued bills are audit-locked:
  retire, never hard-delete (BR-AST-002)
illegal transitions rejected server-side (BR-AST-020)
stages live in Reference data (seeded, tenant-renamable/extensible) — every stage maps to a behavior class
  available | in_service | out_of_service | terminal so billing logic survives tenant labels (BR-AST-031)
roles: repair transitions = Clerk allowed (BR-AST-038); retire + delete = System Admin only (BR-AST-032)
```

## 3. Assignment & move flows (BR-AST-017/021/022/035/036/037)

```
asset_assignments: append-only, non-overlapping, ≤1 current row (to_date NULL); corrections close+open rows,
  never edit (BR-AST-017)
ASSIGN   inventory → unit: single or bulk multi-select (BR-AST-036); assets attach to UNITS ONLY — account
         linkage flows through the unit on move-in/out (BR-AST-035)
REASSIGN S55: to-unit (keeps/sets active) | to-inventory (status → inventory — BR-AST-022) · effective date ·
         FINAL READ captured at effective date and linked to the closing assignment row (default on, BR-AST-022)
         unit→unit moves: single or file-import only, never bulk multi-select (BR-AST-036/038)
SUB-METERS: moving a parent prompts "move children too?" (default yes); independent sub-meter moves ALLOWED
         with a warning message — wrong tagging must be correctable (BR-AST-037)
RETIRE   of an assigned asset closes its assignment at the retire date (BR-AST-021)
```

## 4. Maintenance & test flow (S53 — BR-AST-018/007/027)

`log entry kind repair | inspection | test, append-only (BR-AST-018); test entries update assets.last_test_date; "Test due" = DERIVED display state from last_test_date + test_interval_months, never a stored status (BR-AST-007); interval start defaults backflow 12 mo / meter 96 mo, tenant fully controls per type (BR-AST-027)`. Repair entries drive the §2 repair transitions.

## 5. Edit flow (BR-AST-012)

`every edit audited with before/after; billing-affecting fields (multiplier, unit, net_metering, service) change FORWARD-ONLY once reads exist — stored reads and issued invoices never restated`.

## 6. Bulk import — S52 (BR-AST-023/034)

```
upload (template per BR-AST-034: asset# optional→auto, serial, type, service, UoM, multiplier, digits, mfr,
  model, install date, status, unit ref optional, opening read optional; cap 10,000 rows)
  → STAGED per-row validation, nothing written until commit (BR-AST-023)
  → premises/units must exist first — unmatched refs error (BR-AST-034)
  → skip-errors ON (default): valid rows only | OFF: all-or-nothing (BR-AST-023)
  → commit → batch + audit recorded; UoM stamped explicitly per row; summary ALWAYS "N uploaded · N failed"
    with error report (BR-AST-034)
re-upload matches on asset# and updates SPEC fields only — billing-affecting fields never via upload (BR-AST-034)
```

## 7. Net-meter reads (EP-AST-05 — BR-AST-029/010/025)

`a net meter's cycle read = TWO read records with read_type: one consumption + one export, same date (BR-AST-029 — supersedes the two-columns model BR-AST-024); export records on non-net assets rejected; missing export record on a net cycle → 0-value export record + review flag (BR-AST-029); channel reads feed rating as INPUTS only via the service interface — this module never computes/stores/displays credit money (BR-AST-025; kWh-credit math = rating v1.1 per BR-RAT-018)`.

Unflowed: photos/documents on assets = v2 (BR-AST-040) — (no ratified flow). S49/S50 list/detail mechanics are capability-matrix conformance (BR-AST-004..006/016/019/039/041), not flows.

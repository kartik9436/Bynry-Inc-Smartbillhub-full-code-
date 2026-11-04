# EP-TEN-08 — Settings → Numbering

**Module:** tenancy · **Wave:** W0 · **Screens:** S8 (Settings → Numbering — A1 addendum 2026-08-07, r8) · **Status:** draft

## Scope
**In:** the Numbering tab: editable number formats per series — Account, Bill, Payment, Adjustment (prototype panel) plus Asset (r4 Assets addendum: every asset carries an asset #) — each with prefix + tokens, a per-series next-number counter, and a live preview; Save with confirm/toast/audit. The right-hand **Document templates** panel is a read-only pointer list ("Edit wording in Settings → Templates") — navigation only, per r8.
**Out:** template content/designers (notifications module, wave 6 — S91–S106), the actual consumption of numbers at issue time (each issuing module calls the series service; billing stamps `invoice_no`, payments `payment.confirmation`-adjacent numbering, assets `asset #`), subscription-invoice numbering `SBH-INV-…` (Bynry side, B10 — separate series by design, wave 8).

## Capability matrix (list screens only — B9 conformance)
None — the tab is a form panel plus a read-only pointer list; no managed tables.

## Stories

---
```yaml
id: US-TEN-012
epic: EP-TEN-08
module: tenancy
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001]
journeys: []
rules: [BR-TEN-016, BR-TEN-024, BR-TEN-033, BR-TEN-035]
golden_tests: []
finance_calc: none
```
### US-TEN-012 — Number formats per series (prefix · next-number · preview)

**1 · Details** — As a System Admin, I want to define how account, bill, payment, adjustment, and asset numbers look — a literal prefix plus date/sequence tokens — and see a live preview with the next number, so that our documents match the numbering our customers and auditors already know. Entry: Settings → Numbering. Per-series fields: format string, next number, computed preview. Exit: Save (confirm + toast + audit) / Discard.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-035 | Number format grammar: literal characters + tokens `{YYYY}` `{YY}` `{MM}` `{DD}` (issue date, tenant timezone) and exactly one zero-padded sequence token `{0…0}` (pad = token length). Numbers are allocated by the series service **inside the issuing transaction**: per-tenant per-series monotonic counter; gaps from rolled-back transactions are acceptable; a number is never reused. **Format changes apply to future numbers only — issued numbers are never renumbered or reformatted** (they are stamped on immutable financial rows). Next-number is editable only forward (≥ current) to prevent collisions; uniqueness is guaranteed by B2 `UNIQUE (tenant_id, invoice_no)` and mirrored constraints per series | PROPOSED — grammar extracted from prototype defaults (`AC-{YYYY}-{00000}`, `BL-{YY}{MM}-{000000}`, `PY-{YY}{MM}{DD}-{0000}`, `ADJ-{000}`); forward-only rule derived from CLAUDE.md #4 immutability (proposed per PM task note: changing formats must NOT affect existing numbers) |
| BR-TEN-033 | The Document templates panel is navigation-only (→ Settings → Templates, notifications module); Numbering stores number formats only | CONFIRMED — A1 r8 addendum ("Numbering keeps number formats; its document-template list now points to Templates") |
| BR-TEN-024 | Sticky Save/Discard, atomic per-tab save, unsaved-changes guard | PROPOSED — see EP-TEN-05 |
| BR-TEN-016 | Save writes `audit_log` (`settings.numbering.updated`, before/after formats + counters) | PROPOSED |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Brazos Bend keeps defaults; issue a bill on Aug 8, 2026 with bill counter at 18,410 | Bill number `BL-2608-018410`; counter advances to 18,411; format string untouched |
| TC-2 | Change bill format to `BBU-{YYYY}{MM}-{000000}` and Save | Preview showed `BBU-202608-018411` before save; the NEXT issued bill uses the new format; all 18,410 existing bill numbers unchanged, searches on old numbers still resolve |
| TC-3 | Set account next-number from 568 to 1000 | Allowed (forward); next new account = `AC-2026-01000` |
| TC-4 (neg) | Format with no sequence token (`BL-{YY}{MM}`), two sequence tokens, or an unknown token `{QQ}` | Inline validation rejects with the specific problem; Save blocked |
| TC-5 (neg) | Set bill next-number backward to 500 | Rejected: "must be ≥ 18,411" — collision with issued numbers is impossible by construction |
| TC-6 (neg) | Two concurrent bill issuances during a run | Distinct sequential numbers, no duplicate, no deadlock (allocation inside issuing transaction) |
| TC-7 | Click a template row in the Document templates panel | Navigates to Settings → Templates; nothing editable on the Numbering tab itself |
| TC-8 (isolation) | Lone Star Ridge issues its first bill with default format | Gets `BL-2608-000001` — counters and formats are per-tenant; Brazos Bend's counter unaffected |

**4 · Test Data** — Brazos Bend series: Account `AC-{YYYY}-{00000}` next 569 → `AC-2026-00569` · Bill `BL-{YY}{MM}-{000000}` next 18,411 · Payment `PY-{YY}{MM}{DD}-{0000}` next 88 → `PY-260808-0088` · Adjustment `ADJ-{000}` next 41 → `ADJ-041` · Asset `AST-{00000}` next 1,205 → `AST-01205`. Issue date 2026-08-08, tenant timezone America/Chicago. Actor: Dana Whitfield.

**5 · Data Fields / Mapping** (B2 has no numbering storage — whole table proposed)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Series | S8 Numbering | prototype-extracted (4 fields) + A1 r4 (asset #) | **PROPOSED-SCHEMA:** number_series.series enum (account · bill · payment · adjustment · asset) | enum | reference-data | one row per series per tenant, UNIQUE (tenant_id, series) |
| Format string | S8 Numbering | prototype-extracted (default values) | **PROPOSED-SCHEMA:** number_series.format | text | user-input | BR-TEN-035 grammar |
| Next number | S8 Numbering | task-directed field (not visible in prototype — GAP noted, no OQ: standard counter semantics) | **PROPOSED-SCHEMA:** number_series.next_number bigint | int | user-input / system-derived (advances on issue) | forward-only edits |
| Preview | S8 Numbering | derived (format + next number + today) | — | text | computed-display | — |
| Issued numbers (context) | Bills/Accounts/… | B2 invoices.invoice_no, accounts.account_no, meters.meter_no | (stamped by issuing modules; immutable) | text | system-derived | UNIQUE per tenant |
| Document templates pointer list | S8 Numbering | prototype-extracted + r8 | reads notifications.notification_templates (names only) | — | computed-display | read-only here |

**6 · Acceptance** — Given a System Admin on the Numbering tab, When they edit a series format or next-number and Save, Then the preview matched the entry live, future issuances use the new format from the per-tenant counter, every previously issued number remains exactly as stamped, backward counter edits and malformed formats are rejected inline, and the template panel only navigates to Settings → Templates.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None (whether format changes touch existing numbers was judged derivable — proposed as the forward-only rule in BR-TEN-035, per immutability; gapless-sequence requirements for US utility invoices found no basis in spec or B-docs and gaps-allowed is the industry norm — flag at ratification if finance disagrees).

# T6-08 — Settings & reference-data gate day: Admin edits (audited before/after) · Clerk has no door · Executive views but cannot save

---
id: T6-08
tier: 6
roles: [System Admin, Billing Clerk, Executive]
gates: [BR-IDN-014, BR-IDN-009, BR-TEN-016, BR-TEN-024, BR-TEN-030, BR-TEN-034, BR-TEN-035, BR-TEN-036, BR-TEN-041, BR-TEN-042]
stories: [US-TEN-005, US-TEN-006, US-TEN-010, US-TEN-011, US-TEN-012, US-AUD-003]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Settings and reference data steer every downstream money computation, so their gate is strict and asymmetric (A4 addendum grid: System Admin Full · Billing Clerk none — not even read · Executive View). This day exercises Admin edits across the ratified settings surface with the BR-TEN-016 audit contract (every write = before/after; one atomic tab save = ONE audit row, BR-AUD-011), probes the Clerk's total absence of a door and the Executive's view-without-save, and re-touches the two in-family state locks: code immutability/audit-lock (BR-TEN-030/034) and the currency lock (BR-TEN-042, full journey T5-03).

**Fixture.** Tenant brazos-bend · Dana = System Admin · Priya = Billing Clerk · Marcus = Executive · reference lists seeded per BR-TEN-036 (payment methods incl. money order per BR-TEN-041 upgrade #1) · lookup entry "LEAK" (adjustment reason) with Used-by = 12 · lookup entry "TESTX" with Used-by = 0 · numbering series INV with issued numbers · first financial record exists (currency locked).

| # | Actor + action | Allowed? / Denied? | Expected outcome | Downstream assertions | Gate |
|---|---|---|---|---|---|
| 1 | Dana adds reference-data entry "GOODWILL" to the adjustment reason-code list (an owning-module list — write routes via that module's service fn, BR-TEN-031) | ALLOWED | Save → toast; code unique per list per tenant (case-insensitive) | New row available in new-record pickers; ONE audit row for the atomic save with before/after | BR-TEN-041 · BR-TEN-016 · BR-TEN-030 |
| 2 | Dana edits the S66 billing defaults tab (late-fee min/%/grace fallbacks) using sticky Save/Discard | ALLOWED | Staged edits; atomic per-tab save; Discard reverts; unsaved-changes prompt on navigation | ONE audit row for the tab save (BR-AUD-011); values affect FUTURE computations only (BR-TEN-020 family — nothing restates) | BR-TEN-041 · BR-TEN-024 |
| 3 | Dana edits the INV numbering series format (prefix + date tokens + sequence) | ALLOWED | Format changes apply to future numbers only; issued numbers never renumbered | Next issue uses the new format; historical invoice numbers byte-identical | BR-TEN-035 |
| 4 | STATE LOCK — Dana tries to edit code "LEAK" (Used-by 12), then hard-delete it | DENIED (both) | Code immutable once Used-by > 0 (name/detail stay editable); delete blocked by 🔒 audit-lock — deactivate is the offered door | Row unchanged; Used-by counts computed live from owning-module references, never cached (BR-TEN-029); zero writes | BR-TEN-030 · BR-TEN-034 |
| 5 | CONTRAST — Dana deactivates "LEAK" and hard-deletes "TESTX" (Used-by 0) after confirm | ALLOWED | Deactivate-first; delete only at zero references | "LEAK" vanishes from new-record pickers, still renders on existing records; "TESTX" gone; both audited | BR-TEN-034 · BR-TEN-029 |
| 6 | STATE LOCK — Dana tries Currency USD → CAD | DENIED | Locked once the first financial record exists — no role can cross this (full journey T5-03) | Currency USD everywhere; zero writes | BR-TEN-042 |
| 7 | Priya (Clerk) looks for Settings: the nav entry is absent; she calls `GET /api/tenant/settings` and `PUT /api/reference-data/adjustment-reasons` directly | DENIED (read AND write) | Settings & lookup tables = "—" for Billing Clerk: no access at all; the hidden nav was convenience — the server refuses both verbs | 403-class each; zero writes; zero settings payload served | A4 grid (BR-IDN-014) · BR-IDN-009 (users tab) |
| 8 | Marcus (Executive) opens every Settings tab and reads them | ALLOWED (view) | Settings = View for Executive: all tabs render, including reference data and the numbering series | No writes | A4 grid (BR-IDN-014) |
| 9 | Marcus edits a field and hits Save on the same tabs; replays via `PATCH /api/tenant/settings` | DENIED | View ≠ edit: save refused server-side regardless of the rendered, fillable form | 403-class; zero writes; zero audit rows (BR-TEN-016 audits executed writes only) | A4 grid · BR-TEN-016 |
| 10 | CROSS-CHECK — Dana filters S61 to module = tenancy, today | ALLOWED | Exactly the executed writes appear (steps 1, 2, 3, 5): one row per atomic save, each with before/after; the denied probes (4, 6, 7, 9) left nothing | Audit trail = the change history of tenant configuration; settings reads are never audited | BR-TEN-016 · BR-AUD-011 |

# T5-11 — Bill correction executed without approval (no money-bearing write before approval)

---
id: T5-11
tier: 5
guards: [BR-BIL-014, BR-BIL-004, NFR-15]
stories: [US-BIL-015, US-BIL-016, US-BIL-017]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Bill correction is an approval-gated WORKFLOW: reason code → scope → impact preview → approval → staged idempotent execution — and in v1 ALL corrections require System Admin approval, with **NO money-bearing write before approval** (BR-BIL-014, OQ-072 closed). The system must let a clerk build and preview the full correction but refuse execution until the approval exists; the preview itself must write nothing financial.

**Fixture.** Tenant brazos-bend · issued bill BL-2607-0142, $97.41 (money-triples row `flat,cycle,full`), paid in full · correction target per dataset row `flat,rebill,*`: credit note −97.41, rebill 76.35, customer delta 21.06 (BR-BIL-014 note in money-triples.csv) · actor Priya, Billing Clerk.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Priya opens the correction workflow on BL-2607-0142: picks reason code "meter-misread", scope single-bill, and generates the impact preview (credit note −97.41 · rebill lines 76.35 · GL reversals · balance delta 21.06 · payment re-allocation plan) | Preview renders — but is explicitly a PREVIEW; the Execute control is gated pending System Admin approval (disabled-with-reason, IS-6) | ZERO money-bearing rows written: no credit note, no rebill invoice, no journal lines, no allocation changes; only workflow rows (request, reason, scope, preview snapshot) exist | BR-BIL-014 |
| 2 | Priya attempts `POST /api/corrections/COR-0087/execute` without an approval record | Refused 403-class approval-required; IS-7 permission-denied posture naming the v1 rule (all corrections require System Admin approval) | Same zero-money assertions; original bill untouched (immutable anyway); ledger balanced, unchanged; delivery queue has no correction notices | BR-BIL-014 · BR-BIL-004 |
| 3 | Priya escalates the probe: bulk-correction scope (whole RUN-2607-A) and tries execute | Same refusal — bulk and single ride the identical gate | No per-bill execution rows; 1,240 issued invoices untouched | BR-BIL-014 |
| 4 | Adversarial probe: a second clerk "approves" — Billing Clerk role holds no correction-approval right | Approval refused: role gate (System Admin only in v1); IS-7 permission-denied; enforcement server-side | Approval record absent; execute still gated; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero money writes | BR-BIL-014 |
| 5 | RECOVERY — the ratified door: System Admin Dana reviews the impact preview and approves; Priya executes | Staged idempotent execution runs with per-bill results: credit note −97.41 references BL-2607-0142 (original untouched, GT-6), rebill 76.35 issues, GL reversals post balanced, payment re-allocates per plan, delivery + full audit | All money writes happen ONLY now, atomically per bill, each audited (BR-AUD-001); re-executing the approved correction is idempotent (no double credit) | BR-BIL-014 · BR-BIL-004 |

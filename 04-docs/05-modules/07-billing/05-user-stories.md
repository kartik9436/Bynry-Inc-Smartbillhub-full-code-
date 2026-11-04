# billing — User Stories (INDEX)
> Pack authored 2026-08-08 against the closed billing session (BR-BIL-001..029 all CONFIRMED; B2 Addenda r9/r10 approved; WE-1..18 + BS-1..23 fixtures).

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-BIL-001 | Run selection: cycle + period, idempotent run creation | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-002 | Step 2 "Check what we found": six preview tabs incl. the overcharge guardrail | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-003 | Step 3 exceptions: per-case tables, bulk actions, the missing-service choice | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-004 | Draft bills with the confirmed draft powers (exclude · re-rate · add charge line) | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-005 | Issue: mint numbers, freeze invoices, stamp GL + template, hand off posting, queue delivery | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-006 | Pending-billing queue + catch-up sub-runs (hold ≠ forget) | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-007 | Bill anatomy: one document, N GL-coded lines, one balanced entry | [EP-BIL-02-invoice-gl.md](06-epics/EP-BIL-02-invoice-gl.md) | draft | W3 |
| US-BIL-008 | Tax lines per authority + account-level exemption | [EP-BIL-02-invoice-gl.md](06-epics/EP-BIL-02-invoice-gl.md) | draft | W3 |
| US-BIL-009 | Finance account-mapping page + the balanced posting handoff contract | [EP-BIL-02-invoice-gl.md](06-epics/EP-BIL-02-invoice-gl.md) | draft | W3 |
| US-BIL-010 | First bill: prorated from move-in day + the one-time lines | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W3 |
| US-BIL-011 | Final bill: immediate at move-out, deposit auto-apply, exactly one settlement path | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W3 |
| US-BIL-012 | Ad-hoc single bill: the bulk wizard in single-account mode | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W3 |
| US-BIL-013 | Back-bill: arbitrary past period, each sub-period priced on ITS tariff version | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W5 |
| US-BIL-014 | Penalty / theft bill: assessed reads priced by the engine + charge-code penalties | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W5 |
| US-BIL-015 | Single-bill correction: credit note + rebill with impact preview | [EP-BIL-04-corrections.md](06-epics/EP-BIL-04-corrections.md) | draft | W5 |
| US-BIL-016 | Bulk corrections: scope selector, staged idempotent execution, per-bill results | [EP-BIL-04-corrections.md](06-epics/EP-BIL-04-corrections.md) | draft | W5 |
| US-BIL-017 | The approval gate + correction reason codes (reference data) | [EP-BIL-04-corrections.md](06-epics/EP-BIL-04-corrections.md) | draft | W5 |
| US-BIL-018 | Enrollment, eligibility & the level computation | [EP-BIL-05-budget-billing.md](06-epics/EP-BIL-05-budget-billing.md) | draft | W4 |
| US-BIL-019 | The budget bill: actuals monthly, variance on every bill, settle-up month | [EP-BIL-05-budget-billing.md](06-epics/EP-BIL-05-budget-billing.md) | draft | W4 |
| US-BIL-020 | Re-level at drift, off-budget after missed payments, per-account override ±30% | [EP-BIL-05-budget-billing.md](06-epics/EP-BIL-05-budget-billing.md) | draft | W4 |
| US-BIL-021 | Template CRUD, append-only versions, publish rights | [EP-BIL-06-templates-delivery.md](06-epics/EP-BIL-06-templates-delivery.md) | draft | W3 |
| US-BIL-022 | Pinning at issue + reprint renders the pinned version forever | [EP-BIL-06-templates-delivery.md](06-epics/EP-BIL-06-templates-delivery.md) | draft | W3 |
| US-BIL-023 | The outbound delivery queue + dispatcher (print/PDF v1 · email deferred → W6) | [EP-BIL-06-templates-delivery.md](06-epics/EP-BIL-06-templates-delivery.md) | draft | W3 |
| US-BIL-024 | Per-run delivery dashboard + re-queue | [EP-BIL-06-templates-delivery.md](06-epics/EP-BIL-06-templates-delivery.md) | draft | W3 |
| US-BIL-025 | S30 All-bills list (search, segments, dynamic columns, export) | [EP-BIL-07-bills-list.md](06-epics/EP-BIL-07-bills-list.md) | draft | W3 |
| US-BIL-026 | Bill detail: pinned document, line detail with GL, linkage & audit | [EP-BIL-07-bills-list.md](06-epics/EP-BIL-07-bills-list.md) | draft | W3 |
| US-BIL-027 | Void with plain-language consequence messaging (OQ-012 windows) | [EP-BIL-07-bills-list.md](06-epics/EP-BIL-07-bills-list.md) | draft | W5 |
| US-BIL-028 | Stamp the custom-field snapshot onto the invoice at issue | [EP-BIL-02-invoice-gl.md](06-epics/EP-BIL-02-invoice-gl.md) | draft | W2 |
| US-BIL-029 | The bill-run pipeline: seven stages, one contract each, no stage reaching around another | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | draft | W3 |
| US-BIL-030 | The terminal stages (assemble-document · post-to-ledger) and GT-1..61 as the refactor contract | [EP-BIL-02-invoice-gl.md](06-epics/EP-BIL-02-invoice-gl.md) | draft | W3 |
| US-BIL-031 | Document-only correction: the bill is right, the document is wrong | [EP-BIL-04-corrections.md](06-epics/EP-BIL-04-corrections.md) | draft | W5 |
| US-BIL-032 | Fee bill: one charge code raised as a bill of its own, through the redesigned one-time flow | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W3 |
| US-BIL-033 | Send: authorise and issue ONE one-time bill, idempotently, only after the clerk acknowledges the amounts | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W3 |
| US-BIL-034 | Account search: one searchable dropdown picks the account for any one-time bill | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | ready | W3 |
| US-BIL-035 | Fee bill taxes a charge code marked taxable (BLOCKED — B4.2 ❄ re-sign first) | [EP-BIL-03-bill-types.md](06-epics/EP-BIL-03-bill-types.md) | blocked | W3 |
| US-BIL-036 | Bulk run · Scope: what to bill, every refusal and warning at once, one screen | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | ready | W3 |
| US-BIL-037 | Bulk run · Check: every check on every account, problems by category and tag, fixed here or answered for all | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | ready | W3 |
| US-BIL-038 | Bulk run · Calculate: draft bills between Check and Sign off, priced at the period end | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | ready | W3 |
| US-BIL-039 | Bulk run · Sign off: a summary that adds up to Scope, usage and charges, payments, not in this run | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | ready | W3 |
| US-BIL-040 | Bulk run · Send: one acknowledged send, one failure breaks one bill, leftovers to Pending billing | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | ready | W3 |
| US-BIL-041 | Bulk run · Not in this run and catch-up: every account left out is listed and billed later from the run | [EP-BIL-01-bill-run.md](06-epics/EP-BIL-01-bill-run.md) | ready | W3 |

**41 stories · 7 epics.** Rules: [`02-business-rules.md`](02-business-rules.md) · Model: [`07-pre-session-model.md`](07-pre-session-model.md) · Fixtures: [`08-worked-examples.md`](08-worked-examples.md) (WE-1..18, BS-1..23) · Fields: [`03-field-map.md`](03-field-map.md) · Traceability: [`../../10-traceability-matrix.md`](../../10-traceability-matrix.md)

> Index note (2026-08-10): **US-BIL-028 was missing from this index** — it was authored into EP-BIL-02 by a later lane and never indexed. Added here with US-BIL-029/030. The index is regenerated at pack merge; this row is the truth in the meantime.

> Index note (2026-08-12, this lane): **US-BIL-031 was missing from this index** — the same defect the 2026-08-10 note records for US-BIL-028: it was authored into EP-BIL-04 by the corrections lane on 2026-08-11 and never indexed, so the count read 30 while seven epics held 31 stories. Added here. Its `status` also moved **blocked → draft** in the same commit, because the PO closed **OQ-103** on 2026-08-12 (*"Reissue a corrected copy"*) and the story is no longer waiting on a decision — only on the document-instance table.

> Index note (2026-09-30, the one-time bill redesign lane — build plan R5): **US-BIL-032…035 added** to EP-BIL-03 and **US-BIL-010…014 moved draft → ready**, each amended to the PO-confirmed redesign (`11-one-time-bill-redesign.md`). US-BIL-032 is the fee bill story nobody had written — BR-BIL-410 was ruled and built on 2026-08-27 with no epic owning it. US-BIL-035 (fee tax) is **blocked on the B4.2 ❄ finance re-sign**, not on a question (`OQ-812` CLOSED 2026-09-30). Journey `J70` covers E1–E11.

> Index note (2026-09-30, the bulk bill run redesign lane — build plan R3): **US-BIL-036…041 added** to EP-BIL-01, one per step of the redrawn run (Scope · Check · Calculate · Sign off · Send · Not in this run / catch-up), each with §3 test cases written before the code on the shared `BBR` fixture (EP-BIL-01 §AMENDED 2026-09-30) and journey `J72`. US-BIL-001 TC-4 (services scope) and TC-8's pricing half are stamped SUPERSEDED in place; US-BIL-001…006 are otherwise unchanged.

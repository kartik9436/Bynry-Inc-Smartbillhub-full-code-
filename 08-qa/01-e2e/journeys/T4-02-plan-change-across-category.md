# T4-02 — Plan change across consumer category (x = Residential plan → y = Commercial plan; deposit NO-recompute asserted)

---
id: T4-02
tier: 4
rules: [BR-CUS-062, BR-CUS-052, BR-CUS-041, BR-CUS-014, BR-CUS-029, BR-BIL-025, BR-RAT-023]
stories: [US-CUS-016, US-CUS-017, US-CUS-007, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = account on a Residential-category plan (deposit rule $150); y = same account moved to a Commercial-category plan (deposit rule $400 per `plan_deposit_rules`). The boundary matters because the OBVIOUS behavior — recompute the deposit differential — is exactly what the PO ruled OUT for v1: BR-CUS-062 says the deposit set at move-in STANDS until final-bill settlement; category-differential recompute is v1.1. This journey proves the change flows through plan snapshot, category, and template assignment while the deposit does NOT move — the assertion of absence is the point. (BR-CUS-042's differential amounts remain the ruled v1.1 basis; v1 behavior is governed by BR-CUS-062.)

**Fixture.** Tenant brazos-bend · ACC-1042, Residential Standard, deposit held **$150.00** (fixture `plan_deposit_rules` Residential; Small Commercial category amount $400.00 exists in the same fixture) · change effective next cycle start Aug 1.

**Fixture amendment (2026-08-22, CR-014 · DEF-556).** Seeded by `seed_journey_fixture.seed_t4_02`. The account is **ACC-2042** (the cohort's own range) and the change is effective the cycle after the seeded August one. Both `plan_deposit_rules` rows are real — Residential **150.00**, Small Commercial **400.00** — and so is the HELD position: `accounts.deposit_on_file = 150.00`, received 2026-07-01. ⚠ The held figure is part of the fixture and not an afterthought: with the rules alone, step 2's *"deposit held remains $150.00"* compares **0.00 to 0.00**, is satisfied, and proves nothing (DEF-108's shape).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk runs S23 Change-plan → "Small Commercial" (published, service-compatible), effective **next-cycle** Aug 1; category-change warning acknowledged | Account consumer category changes with warning + audit, forward-only (BR-CUS-052); snapshot chain appends per BR-CUS-029; unit synced | audit rows: plan change + category change, both with before/after; outbound-queue notification row | BR-CUS-052 · BR-CUS-041 · BR-CUS-014 sc.3 |
| 2 | Harness inspects the deposit position immediately after confirm | **NOTHING recomputes**: deposit held remains $150.00; no differential line, no billed $250, no credit, no refund row | deposit-liability GL for the account unchanged; S36 deposit tie-out (Σ deposits held = deposit GL) still exact — no drift introduced (BR-LED-007); zero payment/adjustment rows created | BR-CUS-062 |
| 3 | Aug cycle bill run issues the first bill on the new plan | Rating prices Aug entirely on the Commercial snapshot (no split — effective date = period start); template assignment resolves by the NEW category default (residential template → commercial template) unless a per-account override exists | Aug bill renders on the commercial-category template, pinned at issue (BR-BIL-026); no deposit line anywhere on the bill; balanced JE | BR-CUS-014 sc.6 · BR-BIL-025 |
| 4 | Move-out later closes the account (out-of-scope execution, contract asserted) | Final-bill handoff carries deposit disposition = the ORIGINAL $150 + accrued interest (BR-CUS-057) — settlement is where the deposit finally moves | handoff contract fields per BR-CUS-031 include deposit disposition $150-basis | BR-CUS-031 · BR-BIL-013 |
| 5 | **INVARIANCE** — what must NOT have changed | Deposit held $150.00 for the whole account life until settlement; July's issued bill (residential template pinned) renders byte-identical on reprint | No deposit differential transaction exists anywhere (payments, adjustments, ledger); prior snapshots immutable; deposit-liability GL balance unmoved by the plan change | BR-CUS-062 · BR-BIL-026 · hard rule 4 |

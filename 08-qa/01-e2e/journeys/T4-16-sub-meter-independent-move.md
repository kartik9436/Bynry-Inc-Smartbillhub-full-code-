# T4-16 — Sub-meter independent move with warning (x = child under master's group → y = child on another unit; reconciliation group recomputes)

---
id: T4-16
tier: 4
rules: [BR-AST-037, BR-MET-025, BR-MET-043, BR-MET-046, BR-MET-048]
stories: [US-AST-009, US-AST-006, US-MET-011]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = sub-meter SM-8801 parented to master M-MASTER-12 (its usage counted in the master's Σ-subs reconciliation); y = SM-8801 reassigned INDEPENDENTLY to another unit — allowed WITH a warning per the PO's R4 Q12 ruling ("allow but display the message"), because wrong tagging must be correctable. The boundary matters downstream in validation, not money: the master's mismatch check (|master − Σ subs| vs loss tolerance, BR-MET-025) recomputes its membership from the NEXT reads forward, while historical reads keep their original linkage — otherwise fixing a tag would rewrite last month's reconciliation story.

**Fixture.** Tenant brazos-bend · master M-MASTER-12 with children SM-8801, SM-8802 (loss tolerance tenant-set; the 3% is a sample) · Clerk moves SM-8801 alone to Vega Apts unit 105 on Aug 3 (the EP-AST-03 TC-8 fixture) · reassign captures SM-8801's final-read-on-old-unit per BR-MET-043.

**Fixture amendment (2026-08-22, CR-014).** Seeded by `seed_journey_fixture.seed_t4_16`. Master **M-MASTER-12** and children **SM-8801 + SM-8802** are the paragraph's own and the seeder refuses on anything but that exact pair — a group of one or of three changes the Σ-subs arithmetic this journey recomputes. Both children are created through the real `create_asset`, so BR-AST-003's parent requirement is the SERVICE's refusal rather than the fixture's assumption. The master's unit is deliberately attached to NO billing cycle: `billing_reads_for_unit` takes the latest head across a service point's assets, so a sub-metered unit inside a billed cycle would quietly change which read priced the bill.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk reassigns SM-8801 ALONE (parent stays) via the assets reassign flow | WARNING renders: "this sub-meter is moving independently of its parent M-MASTER-12"; on acknowledge: move executes; final read captured for the old assignment | warning ACKNOWLEDGEMENT recorded in audit_log; `asset_assignments` rows (old closed + new opened); parent M-MASTER-12 untouched | BR-AST-037 · BR-MET-043 |
| 2 | Harness inspects the master's reconciliation group | Master's Σ-subs membership recomputes forward: from Aug 3 the group = {SM-8802} only | next validation run evaluates |M-MASTER-12 − SM-8802| against the tolerance; SM-8801's new-unit reads validate under ITS new context | BR-MET-025 |
| 3 | Next read import + validation (Aug cycle) | Flag engine runs with the NEW membership; if the master now over-reads vs the shrunken group beyond tolerance, the Mismatch flag raises on master + group — a wanted signal, since an independent child move often MEANS the wiring changed | flags per BR-MET-021 vocabulary; fix actions per BR-MET-023; no auto-suppression of the mismatch because a move happened | BR-MET-025 · BR-MET-022 |
| 4 | Contrast: Clerk later moves parent M-MASTER-12 itself | Prompt "Move its sub-meters (SM-8802) too?" — DEFAULT YES; accepting moves children with their own assignment rows; declining moves the parent alone with the same independent-move warning | prompt shown only because the asset has children; each child's move gets its own history row + audit | BR-AST-037 |
| 5 | **INVARIANCE** — what must NOT have changed | Historical reads keep their ORIGINAL unit/parent linkage — past reconciliation results and any billed usage derived from them are untouched; units themselves never moved (only assets move; units never change premises) | read rows + past validation outcomes byte-identical; assignment history append-only; no invoice or JE affected anywhere in this journey (no money moves on a tagging fix) | BR-MET-046 · BR-MET-053 · hard rule 4 |

# T7-14 — Config change: overcharge guardrail % (next run's preview flags shift; issued flags stand)

---
id: T7-14
tier: 7
knob: overcharge_guardrail_pct 200% → 350% (S66 family; BR-BIL-021 config)
rules: [BR-BIL-029, BR-BIL-021, BR-TEN-016, BR-TEN-020]
stories: [US-TEN-010, US-BIL-002, US-BIL-004, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The guardrail flags any draft above the tenant-set % of the account's trailing average in the run PREVIEW before issue (BR-BIL-029, default 200%). Changing the % is a pure preview-behavior knob: the NEXT run's preview evaluates under the new threshold; flags recorded on already-previewed or knowingly-issued bills are historical facts and never re-evaluate. The fixture's flat account makes the ratio exact: backbill 292.23 against a 97.41 trailing average — above 200%, below 350% (both figures from money-triples; ratio harness-verified).

**Fixture.** Tenant brazos-bend, `overcharge_guardrail_pct=200` (r10 #6) · account ACC-1130: flat plan billed 97.41 every cycle (trailing average 97.41, money-triples `flat,cycle`) with a 3-month backbill draft of 292.23 (money-triples `flat,backbill`) · sibling account ACC-1131 with the identical backbill situation, run AFTER the change · Billing Clerk Dana Kim; System Admin Alex Reed.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Run A preview (S31 step 2 / S31.2) computes ACC-1130's 292.23 draft | FLAGGED: draft exceeds 200% of trailing average 97.41; flag visible in the preview overcharge tab | Flag is computed-display carried on the draft "until resolved or knowingly issued" (billing field map) | BR-BIL-029 |
| 2 | Dana knowingly issues the flagged bill (BL-2608-0290) | Issue proceeds — the guardrail informs, it does not block; the knowingly-issued flag state is recorded with the run | Issued invoice immutable; posting balanced; audit row for the issue action | BR-BIL-029 · IS-6 |
| 3 | Alex changes `overcharge_guardrail_pct` 200→350; atomic save | Toast → ONE audit row `billing_settings.updated`, before/after `{overcharge_guardrail_pct: 200→350}` | BR-TEN-016 shape · BR-AUD-011 one row | BR-TEN-016 · BR-BIL-021 |
| 4 | Run B preview computes ACC-1131's identical 292.23 draft | NOT flagged: the new 350% threshold clears it (draft/trailing ratio sits between the old and new thresholds — harness-verified) | Threshold read at PREVIEW time; the shift is the observable | BR-BIL-029 |
| 5 | Probe: Run A's recorded state after the change | ACC-1130's flag history unchanged — no retro-unflag, no re-evaluation of past previews or issued bills; BL-2608-0290 untouched | Preview evaluations are point-in-time facts | BR-TEN-020 |
| 6 | INVARIANCE — sweep drafts, issued bills, postings before/after step 3 | The settings save changed zero money rows and zero recorded flags; only Run B's evaluation differed; reprints render pinned documents unchanged | Settings change ≠ restatement | BR-TEN-020 · NFR-22 |

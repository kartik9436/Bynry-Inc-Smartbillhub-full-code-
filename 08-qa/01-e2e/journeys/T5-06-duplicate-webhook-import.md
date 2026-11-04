# T5-06 — Duplicate payment webhook & duplicate import file (file+tags)

---
id: T5-06
tier: 5
guards: [BR-PAY-003, BR-PAY-028, BR-PAY-023, BR-MET-018, NFR-16, NFR-2]
hard_rules: [6]
stories: [US-PAY-003, US-MET-010]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Every inbound money/data channel must swallow replays without double-posting: payment webhooks are idempotent on webhook_key (BR-PAY-003/028), lockbox/CSV payment batches on file+SHA-256+tags (BR-PAY-023), and read-import batches on file+tags with a collision block that shows who/when/link to the original (BR-MET-018, OQ-044 option b). Providers retry, staff re-upload — the system must record each real-world event exactly once. Exact key mechanics are Eng-Lead-owned 🔒; this journey asserts only the observable contract.

**Fixture.** Tenant brazos-bend · webhook payload webhook_key `wh_9f3a…` for a $97.41 payment on ACC-1042 (money-triples row `flat,cycle,full`, paid column) · lockbox file `lockbox-2026-07-28.csv` (SHA-256 stamped, 212 rows) · read file `reads-CYC-A-2026-07.csv` tagged month=2026-07 · cycle=CYC-A.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Rails provider delivers webhook `wh_9f3a…`; then redelivers the identical payload 3× (provider retry) | First delivery records the payment; replays hit the UNIQUE webhook_key → acknowledged as duplicate (success posture toward the provider so it stops retrying — mechanics 🔒), never re-processed | Exactly ONE payments row for wh_9f3a…; allocations built once (BR-PAY-010); account balance moved once; ledger balanced with one posting pair | BR-PAY-003 · BR-PAY-028 · hard rule 6 |
| 2 | Clerk uploads `lockbox-2026-07-28.csv`, commits the batch (212 payments), then re-uploads the SAME file with the same tags next morning | Staging refuses at batch creation: idempotency collision (file+SHA-256+tags) — 409 class, IS-7 failed state naming the original batch, who committed it, when, with link | No second batch row; payments count unchanged (212); no re-allocation; audit: the refusal itself writes nothing (BR-AUD-001 scope = executed actions) — the ORIGINAL batch's compliance stamp is the who/when shown | BR-PAY-023 · NFR-16 |
| 3 | Meter clerk re-submits `reads-CYC-A-2026-07.csv` with identical tags after the original batch committed | Collision blocks with who/when/link to the committed batch (OQ-044 option b); no staging rows created | meter_reads count unchanged; no superseding rows minted; billing inputs untouched | BR-MET-018 |
| 4 | Adversarial probe: same file content, ONE tag changed (route added) — and separately, one edited row (new SHA-256), same tags | Distinct key → accepted into STAGING both times (this is the contrast case); per-row duplicate-vs-committed validation then errors every row already posted (meter+date+channel) | Staged-only; zero committed duplicates possible while row errors stand (BR-MET-015/016, BR-MET-052 row-level duplicate rejection) | BR-MET-016 · BR-MET-052 · NFR-2 |
| 5 | RECOVERY — the ratified doors: a genuinely corrected file (new content) imports as a new batch and corrections flow as SUPERSEDE rows (BR-MET-016 replace-as-correction); a payment correction is a reversal + re-entry, never a replayed webhook | New batch commits only the corrected rows via supersede chains; originals immutable + linked | Lineage heads served to consumers; one real-world event = one financial record everywhere | BR-MET-016 · BR-PAY-002 |

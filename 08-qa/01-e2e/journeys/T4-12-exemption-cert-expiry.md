# T4-12 — Exemption certificate expiry (x = valid cert → y = expired: WARNING renders, never auto-untag)

---
id: T4-12
tier: 4
rules: [BR-CUS-063, BR-RAT-006, BR-BIL-004]
stories: [US-CUS-009, US-BIL-008]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = tax-exempt account with a valid certificate; y = the certificate's expiry date passes. The boundary is the PO's explicit CL-6 ruling inside BR-CUS-063: expired cert → **warning, not auto-untag — staff decide**. The tempting automation (flip the account back to taxed the day the cert lapses) is exactly what must NOT happen: a renewal may be in the mail, and silently re-taxing would surprise-bill an exempt entity. The system's whole job at the boundary is to make a human look.

**Fixture.** Tenant brazos-bend · ACC-1049 tax-exempt, cert ref TX-EX-88121, expiry **2026-07-31** · clock advances past Jul 31 · Aug cycle bill runs Aug 1.

**Fixture amendment (2026-08-22, CR-014 · DEF-556).** Seeded by `seed_journey_fixture.seed_t4_12`. The account is **ACC-2049**, not ACC-1049 — the ACC-2xxx range this cohort's accounts live in, so the flat ride and the signed LE cast can never share a number. The load-bearing parts are unchanged and are the paragraph's own: exemption ON, cert ref **TX-EX-88121**, expiry **2026-07-31** stored (never a stored flip — BR-CUS-063 CL-6 makes expired a DERIVED warning). The seeder additionally proves the account is READY for a run, because a zero-tax bill from an account that billed NOTHING reads exactly like a correct exemption and is not one.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Expiry date 2026-07-31 passes | NOTHING recomputes: the exemption flag stays ON; only the derived warning state flips (expired = computed from the stored expiry date, never a stored mutation) | account detail renders the expiry WARNING; no audit row for a change (nothing changed); no notification invented beyond the ratified warning surface | BR-CUS-063 |
| 2 | Aug cycle bill run executes with the cert expired | Rating still honors the exemption — flag ON means exempt, expiry does not gate the engine | Aug bill has zero tax lines (WE-2 shape); JE has no tax CR rows for the account | BR-CUS-063 · BR-RAT-006 |
| 3 | Adversarial probe: harness looks for any auto-untag job/trigger | None exists — no scheduled process, no bill-run side effect, flips the flag | exemption flag value byte-identical across the expiry boundary; account attribute history shows zero system-actor writes | BR-CUS-063 |
| 4 | Staff decision path A: Clerk records the RENEWED certificate (new ref + new expiry) | Evidence set updates; warning clears (derived) | audit row with before/after cert data; exemption uninterrupted | BR-CUS-063 |
| 5 | Staff decision path B (alternate fixture): Clerk decides the exemption ends and untags | Flag OFF by explicit human action only; NEXT bill taxes (the T4-11 transition run in reverse — next-bill-only, issued bills stand) | audit row names the staff actor; next issued bill carries tax lines; prior exempt bills untouched | BR-CUS-063 · BR-BIL-004 |
| 6 | **INVARIANCE** — what must NOT have changed | Across the expiry event itself (steps 1–3): zero writes to the account's tax state, zero bill deltas, zero ledger movement — the ONLY system output is the warning | every issued bill (taxed or exempt) byte-identical; the untag, when it happens, is always attributable to a named human in audit_log | BR-CUS-063 · hard rule 4 |

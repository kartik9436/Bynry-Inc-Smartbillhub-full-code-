# T5-15 — Unit picker on an occupied unit (one active account per unit)

---
id: T5-15
tier: 5
guards: [BR-CUS-017, BR-CUS-020, BR-MET-036]
stories: [US-CUS-003, US-CUS-004]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** At most ONE active account per unit (BR-CUS-017; occupancy is DERIVED from the active account, BR-MET-036) — and the wizards enforce it upstream: the S18/S19 unit pickers offer vacant/reserved units ONLY (BR-CUS-020). Two active accounts on one unit would double-bill one meter's consumption. The system must hide occupied units from the pickers AND refuse a forced create server-side.

**Fixture.** Tenant brazos-bend · Premises PRM-007 "Brazos Bend Apartments" · Unit 4B OCCUPIED by active account ACC-1042 · Unit 4C vacant · actor Priya, Billing Clerk.

**Fixture amendment (2026-08-22, CR-014 / DEF-556).** Unit 4B's occupant is **ACC-2042** (the CR-014 flat cohort account; ACC-1042 is the signed LE cast at 500 Main St). Unit 4C is seeded vacant. “Priya, Billing Clerk” is a persona name — the seeded cast carries the ROLE via the product's own sample staff (identity sample seam); the seeder prints the actual name.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Priya opens New Account wizard (S18) step 2 and searches PRM-007 units | Unit 4B is ABSENT from the picker (occupied); 4C offered (vacant); no disabled-4B row leaking tenancy details | Picker query filters to vacant/reserved; nothing written (wizard in progress) | BR-CUS-020 |
| 2 | Priya opens Move-In wizard (S19) step 1 — same probe | Same: only vacant/reserved units offered | Same | BR-CUS-020 |
| 3 | Adversarial probe: `POST /api/accounts {unit_id: <4B>, status: active, ...}` forcing the occupied unit | Refused: conflict (409 class) on the one-active-account-per-unit constraint (partial unique index per B2, enforcement mechanism PROPOSED-SCHEMA; the RULE is CONFIRMED); IS-7 failed state names the existing active account | Exactly ONE active account on 4B (ACC-1042); no second account row; no snapshot, deposit, or first-bill artifacts minted; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero writes | BR-CUS-017 |
| 4 | Race probe: two clerks submit move-ins for vacant 4C simultaneously | One wins; the loser hits the same unique-constraint conflict | Post-race: exactly one active account on 4C; occupancy derives to Occupied once (BR-MET-036) | BR-CUS-017 · BR-MET-036 |
| 5 | RECOVERY — the ratified door for a genuine tenant change on 4B: Move-Out wizard for ACC-1042 (final-bill handoff per BR-CUS-031/BR-BIL-013), unit derives Vacant, THEN Move-In creates the new account | Move-out closes ACC-1042 with its final bill; 4B reappears in the pickers; new move-in succeeds with its own snapshot + deposit | Unit history: sequential occupancy, never parallel; every lifecycle step audited | BR-CUS-020 · BR-CUS-017 |

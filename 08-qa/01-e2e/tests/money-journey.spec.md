# E2E — The Money Journey (spec, becomes .spec.ts when app boots)
1. Sign up (S1→S6) → dashboard with welcome toast
2. Settings: verify seeded lookups (S8)
3. Create premise + unit + meters (S16); create account (S18)
4. Import reads CSV, resolve one High flag (S28)
5. Run bills: findings → cases → generate (S29–S31.3)
6. Record payment against the bill (S22/S35) — verify balance, audit row
7. Reconcile the deposit batch (S38–S40)
8. Export GL summary (S42) — verify balanced totals
Assertions throughout: no cross-tenant data visible; issued bill immutable.

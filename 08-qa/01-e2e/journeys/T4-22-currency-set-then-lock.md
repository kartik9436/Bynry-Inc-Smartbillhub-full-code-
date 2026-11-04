# T4-22 — Currency set on a fresh tenant, then the lock engages (x = changeable USD → y = CAD locked by the first financial record)

---
id: T4-22
tier: 4
rules: [BR-TEN-042, BR-TEN-021, BR-TEN-020, NFR-37, BR-IDN-029, BR-BIL-026]
stories: [US-TEN-001, US-TEN-006, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = freshly provisioned tenant, currency USD, ZERO financial records — currency freely changeable from the seed list; y = first financial record issued in CAD — the BR-TEN-042 lock ARMS and the currency is one-per-tenant forever. This is the ALLOWED half of the transition the T5-03 break-path proves from the refusal side: the same rule, walked forward — choose freely before money exists, then watch the first invoice snap the lock shut. Currency support itself is a data change (ISO row + seed list), never code (NFR-37).

**Fixture.** Fresh tenant **maple-creek** provisioned via signup (idempotent, trial) · admin `pat@maplecreek.example` — the same email may exist in other tenants as a DIFFERENT user (per-tenant identity, BR-IDN-029), which is why the two-tenant fixture is legal · contrast tenant brazos-bend (USD, locked — T5-03 fixture) · maple-creek's first bill uses the money-triples row `flat,cycle,full`: **97.41** (stored NUMERIC(18,6) + CHAR(3) 'CAD').

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | maple-creek provisions; System Admin opens Settings → Regional | Tenant row carries default currency USD from seed; zero financial records → currency control EDITABLE, seed list USD/CAD/MXN/EUR/GBP (full ISO list behind) | provisioning atomic + idempotent; checklist flags Regional as un-reviewed; no lock state armed | BR-TEN-042 · BR-TEN-010 |
| 2 | Admin changes currency USD → **CAD**, saves | Tenant settings row updates — ALLOWED because no financial record exists; display formats are transforms only, storage stays NUMERIC(18,6) + CHAR(3) | toast + audit row with before/after; every subsequent money surface renders CAD symbols/format; nothing to restate (no history exists) | BR-TEN-042 · BR-TEN-020 |
| 3 | Tenant reaches its FIRST financial record: first bill issues at **97.41 CAD** | The lock ARMS: currency now immutable for the tenant's life; invoice + lines store CHAR(3) 'CAD' on every amount | issued bill renders CAD; balanced JE in CAD; audit; from this instant the Settings currency control renders disabled-with-reason naming the arming record | BR-TEN-042 |
| 4 | Admin attempts CAD → USD after the issue (UI, then `PATCH /api/tenant/settings`) | REFUSED both surfaces — the T5-03 refusal, now on this tenant: disabled control + 409/422 validation naming the lock; forward-only law would apply even to a v2 unlock (issued records keep their stored CHAR(3), explicit warning) | currency still CAD; the 97.41 bill renders CAD exactly as issued, forever; ledger unchanged (cross-ref T5-03 steps 1–3) | BR-TEN-042 · BR-TEN-021 |
| 5 | Tenant-isolation sweep: brazos-bend checked after every maple-creek step | — | brazos-bend still USD, its lock armed by ITS OWN first record; no cross-tenant read/write occurred (RLS FORCE); the shared admin email resolves to two unrelated user rows | BR-TEN-003 · BR-IDN-029 |
| 6 | **INVARIANCE** — what must NOT have changed | After the lock: every stored amount's CHAR(3); every issued document's rendered currency; the tenant's audit trail of the ONE legitimate pre-lock change | no money row was ever converted or restated; the pre-lock USD→CAD change touched only the settings row (no financial history existed to touch); adding a future currency to the platform = data change, no code (NFR-37) | BR-TEN-020 · BR-BIL-026 · NFR-37 · hard rule 4 |

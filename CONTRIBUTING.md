# Contributing

## Read first
`CLAUDE.md` (operating rules) and `04-docs/02-decisions/08-coding-conventions.md` (B8). Both are binding.

## Branches & PRs
- Branch from the default branch: `feat/<module>-<short-desc>`, `fix/...`, `04-docs/...`.
- Every PR uses the template checklist (tenant isolation, money immutability, audit writes).
- Screen IDs (S1–S48 from `04-docs/01-spec/01-screen-inventory.md`) are the ticket vocabulary — never renumber.
- Business rules are cited by ID (`BR-<MOD>-###` from `04-docs/05-modules/<module>/02-business-rules.md`).

## Human-only files (agents may scaffold around, never decide)
RLS policies (`06-backend/core/rls.py`) · rating math (`06-backend/apps/rating/engine.py`) · idempotency keys (`06-backend/core/idempotency.py`) · ledger posting (`06-backend/apps/ledger/posting.py`) · money rounding · migration ordering. CODEOWNERS enforces review on these paths.

## Tests that gate merge
- Golden tests (`06-backend/tests/golden/`) — must pass or be explicitly `xfail` with an A17/B4 reference.
- Tenant isolation (`06-backend/tests/test_tenant_isolation.py`) — a cross-tenant leak is a release blocker, no exceptions.
- Immutability (`06-backend/tests/test_immutability.py`).

## Commits
Conventional prefix + module: `feat(billing): ...`, `fix(payments): ...`, `docs(governance): ...`.

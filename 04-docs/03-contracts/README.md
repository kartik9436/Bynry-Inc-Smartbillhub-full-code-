# /contracts — the fixed contracts Claude Code builds against

These are the **stable interfaces**. Change them deliberately (they ripple across FE + BE).

- **API contracts:** see `../spec/11-api-contracts.md` (A11) — per-screen endpoints, params, response shapes, pagination. Treat as the FE/BE contract; version it here as it firms up.
- **Database schema:** see `../decisions/02-database-design-brief.md` (B2) — the authoritative Postgres 16 DDL, RLS, indexes, partitioning.
- **Domain model & IDs:** `../spec/03-domain-model.md` (A3) + `../spec/16-glossary.md` (A16) — entity names and vocabulary are contract-level; do not drift.
- **Status vocabularies / enums:** `../spec/05-state-machines.md` (A5) — enum values are contract-level.

Nothing else in /spec or /decisions is a hard contract; those are the reasoning behind these.

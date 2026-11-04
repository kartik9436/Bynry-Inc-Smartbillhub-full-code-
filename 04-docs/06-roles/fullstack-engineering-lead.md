# Role Profile — Full Stack Engineering Lead

## Mission
Own **how** it's built. Guard the architecture (B1), the schema (B2), the module boundaries, and every money-critical and isolation-critical line of code. The Eng Lead is the accountable human for the 🔒 files.

## Core skills

### Hard skills
| Skill | Applied to (this project) |
|---|---|
| Modular-monolith architecture | Enforce B1: modules own their tables, no cross-module writes, cross-module reads via service functions, rating stays pure; hold the extraction triggers honest |
| Postgres security engineering | RLS `ENABLE`+`FORCE` policies on every tenant table; session GUC propagation (request middleware + background jobs); immutability triggers; balanced-journal constraint |
| Financial-systems engineering | Double-entry ledger discipline; append-only corrections; idempotency for bill runs & webhooks; per-line half-up rounding at finalization only |
| Django at scale | Tenant-scoped base managers (no raw cross-tenant querysets), migration ordering, Celery topology, settings hygiene |
| API & contract design | Keep A11 the FE/BE contract; version deliberately; read-models for ≥3-entity screens (dashboard, account detail, billing findings) |
| Code review as a control | CODEOWNERS gatekeeping; review depth proportional to blast radius — a rating change gets adversarial review, a label change doesn't |
| CI/CD engineering | The four gates (lint, golden, isolation, migration-guard) stay green and stay mandatory |

### Judgment skills
- **Boundary instinct.** Detects module-boundary erosion in review (a billing service reaching into payments tables) before it calcifies.
- **Knows what must be boring.** Money paths use the dullest possible code — no cleverness where an auditor will read it.
- **Refuses silent scope in schema.** Every migration maps to a B2 section or an ADR; schema drift without paper trail gets reverted.
- **Sequencing discipline.** Platform → tenancy → identity → … migration order (B2 §7) is enforced, not aspirational.

## Build-phase responsibilities
1. Author the 🔒 human-only code: RLS policies, tenancy middleware, idempotency keys, ledger posting service, money rounding — with finance/product input where B4 requires.
2. Translate B2's DDL into ordered Django migrations; own every subsequent schema change.
3. Review every PR that crosses a module boundary or touches money; approve none blind.
4. Keep the rating module pure (inputs: reads + tariff version → output: priced lines) so B5 golden tests stay meaningful.
5. Decide asynchronous topology (queue choice, job idempotency, retry policy) and the read-model approach per A11.

## Decision rights
- **Owns:** architecture, schema & migrations, 🔒 files, technology choices within the approved stack, code standards (B8).
- **Consults:** finance via PM for any B4 interpretation; QA on gate design; FDE on implementation reality.
- **Never decides:** business-rule values (finance/product), scope/priority (PM), release go/no-go (QA).

## Definition of done (the bar this role holds)
Code merges when: it respects module ownership · runs under RLS with tenant context set · money stays `NUMERIC(18,6)` end to end · financial writes are append-only + audited · migrations are additive and ordered · the golden/isolation gates pass unmodified.

## Leverage prompts
- "Act as Eng Lead: review this PR for module-boundary, RLS, and immutability violations — cite CLAUDE.md rule numbers."
- "Act as Eng Lead: turn B2 §metering into ordered migrations with RLS applied per table."
- "Act as Eng Lead: design the idempotency key scheme for bill runs and payment webhooks (then hold for human sign-off)."

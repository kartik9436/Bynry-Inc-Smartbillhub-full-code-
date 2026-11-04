# ADR-002 — Top-level folder named `12-governance/`, not `reports/`

- **Status:** Accepted
- **Date:** 2026-08-07
- **Deciders:** PM

## Context
The product has a Reports module (S44–S47), `06-backend/apps/reports/`, and `04-docs/05-modules/12-reports/`. A fourth artifact named "reports" would be ambiguous in tickets and reviews.

## Decision
Product-governance monitoring lives in `12-governance/` (weekly status, risk register, decision log, metrics).

## Consequences
"Reports" unambiguously means the product feature everywhere else in the repo.

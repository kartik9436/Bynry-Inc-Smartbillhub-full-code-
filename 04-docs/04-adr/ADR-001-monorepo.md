# ADR-001 — Single monorepo for backend, frontend, QA, and docs

- **Status:** Accepted
- **Date:** 2026-08-07
- **Deciders:** PM / Eng Lead

## Context
Small team (1–2 builders), one product, FE/BE share the A11 contract. Separate repos would require cross-repo versioning of that contract during its most volatile phase.

## Decision
One repository: `06-backend/`, `07-frontend/`, `08-qa/`, `04-docs/` (the contract), plus governance and change-management. Handoff docs are versioned with the code they govern.

## Consequences
Atomic PRs across the contract. CI uses path filters. If team scale later demands split repos, `04-docs/03-contracts/` becomes the shared package first.

# ADR-003 — Subscription billing is platform-scoped and Stripe-processed
- **Status:** Accepted with modifications (PO 2026-08-08): NO Stripe/processor in v1; provision-only + manual ops; Bynry admin console = v2 · **Deciders:** Product Owner
## Context
S107–S109 introduce invoices the tenant pays Bynry, incl. implementation fees. Mixing these with customer billing would corrupt tenant financials and reporting.
## Decision
Platform tables (no tenant-RLS class), separate number series, no FKs into tenant billing; Stripe Billing on Bynry's own account; tokens only. Full model: B10.
## Consequences
Settings → Billing plan is the only surface; trace_lint can assert no cross-references; tenant suspension driven from subscription status.

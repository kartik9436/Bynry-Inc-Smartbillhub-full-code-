# Module — audit

Who did what, before/after, on every money action. Append-only, 7-yr retention, read-only API. The CROSS-CUTTING trail: every other module writes to it (through the audit-write service); this module owns the store, the write contract, the viewer and the lifecycle — it never re-authors the writers' stories.

**Owns (B2):** audit_log (append-only, RLS FORCE, monthly-partitioned per NFR-24/28; `tenant_id` not FK-constrained — survives tenant purge)
**Screens:** S61 Audit log viewer (A1 addendum, OQ-029 closure — tenant-scoped-only) · entries from S8 Settings→Security ("View audit log →") · per-entity Audit tabs as windows (account S21 · premises/unit detail · asset S50 — rendered by their owners over the audit read service) · S44 Compliance card "User activity audit" (feed owned here)
**Boundary rule (B1):** no other module writes this module's tables — writers call the audit-write service (sole write path, US-AUD-003); cross-module reads via service functions only.

**Pack authored (2026-08-09):** EP-AUD-01 write contract (table + seeded event-code catalog + payload standard + write service — W0, every W0 story already cites its rows) · EP-AUD-02 viewer (S61 + drawer/diff + entity read service + guarded export + compliance-stamp views — W1) · EP-AUD-03 lifecycle (2yr-hot→cold/7yr auto-archival per NFR-28/OQ-017, explicit archive search per the reads pattern, user-activity-audit IS-11 feed with reports R-2 deduped — W5). US-AUD-001..009 (05-user-stories.md index; stories in 06-epics/). BR-AUD-001..017 consolidate the ratified audit law by citation (02-business-rules.md). Pending, cited-not-decided: SC-3 security-event scope · SC-7/closed-tenant retention · event-code extensibility + Source/request-metadata anchoring (field-map AUD-D1/D2).

# audit — User Stories (INDEX)
> Pack authored 2026-08-09 against the ratified cross-cutting audit law (hard rule 7/NFR-18 · B2 §audit DDL + §3/§4/§5 · A1 S61 addendum + OQ-029/OQ-017 closures · NFR-13/15/24/28 · IS-6/9/11 + BR-SHL-016 · BR-CUS-045 · writer rules BR-TEN-016/038, BR-MET-017/045/048/055, BR-AST-011/012/019/023, BR-BIL/PAY/LED rows — consumed by citation, never re-authored). BR-AUD-001..017 consolidated in 02-business-rules.md.

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-AUD-001 | `audit_log`: the append-only, RLS-forced, monthly-partitioned trail table | [EP-AUD-01-write-contract.md](06-epics/EP-AUD-01-write-contract.md) | draft | W0 |
| US-AUD-002 | Event-code catalog (seeded-only) + the payload standard (who/when/tenant/entity/before→after, PII-masked) | [EP-AUD-01-write-contract.md](06-epics/EP-AUD-01-write-contract.md) | draft | W0 |
| US-AUD-003 | The audit-write service: sole write path, lightweight INSERT, async-safe, never a bottleneck | [EP-AUD-01-write-contract.md](06-epics/EP-AUD-01-write-contract.md) | draft | W0 |
| US-AUD-004 | S61: the tenant-scoped audit-log viewer (filter bar, table, roles) | [EP-AUD-02-viewer.md](06-epics/EP-AUD-02-viewer.md) | draft | W1 |
| US-AUD-005 | Detail drawer (JSON diff) + the entity-scoped read service behind every Audit tab | [EP-AUD-02-viewer.md](06-epics/EP-AUD-02-viewer.md) | draft | W1 |
| US-AUD-006 | CSV export under BR-SHL-016 guards (itself audited) + compliance-stamp views for import batches | [EP-AUD-02-viewer.md](06-epics/EP-AUD-02-viewer.md) | draft | W1 |
| US-AUD-007 | Auto-archival job: 2-yr hot → cold storage, 7-yr total, audited, never manual | [EP-AUD-03-lifecycle.md](06-epics/EP-AUD-03-lifecycle.md) | draft | W5 |
| US-AUD-008 | Archive search: explicit opt-in reads over cold storage (hot default untouched) | [EP-AUD-03-lifecycle.md](06-epics/EP-AUD-03-lifecycle.md) | draft | W5 |
| US-AUD-009 | "User activity audit" (A14 Compliance card): the IS-11 feed over the S61 dataset — owned here, reports dedups | [EP-AUD-03-lifecycle.md](06-epics/EP-AUD-03-lifecycle.md) | draft | W5 |
| US-AUD-010 | An automated action can say what it is: a named, versioned actor that is not a person (`CR-075` task `L1`) | [EP-AUD-01-write-contract.md](06-epics/EP-AUD-01-write-contract.md) | draft | W0 |

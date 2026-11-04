# audit — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).
> Consolidated from the US-AUD-001..009 §5 tables (pack authoring 2026-08-09); verified against B2 §audit DDL + §3 RLS + §4 indexes + §5 partitioning and NFR-24/28/30. The module owns ONE table (`audit_log`); every other surface is a read-model window over it. Discrepancies vs B2 in the section below.

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Row identity | — | B2 §audit | `audit_log.id` uuidv7; PK (tenant_id, created_at, id) | uuid | system-derived | DB-2 | OK (US-AUD-001) |
| Tenant scope | — | B2 §audit + §3 | `audit_log.tenant_id` NOT NULL, **no FK** (survives tenant purge, DDL comment) | uuid | system-derived | RLS USING + WITH CHECK; FORCE | OK (US-AUD-001) |
| Actor — a PERSON | S61 Actor | B2 §audit + A1 S61 | `audit_log.actor_user_id` (NULL **and no name** = an unnamed system job, job named in payload) | uuid | system-derived | display resolves to user; unnamed system actors labeled | OK (US-AUD-001/002) — narrowed by US-AUD-010 |
| Actor — NOT a person (what it is) | S61 Actor · Audit tabs | BR-AUD-019 · BR-RBS-015 | `audit_log.actor_kind` — `runbook` \| `job` \| `import` \| `integration` | text, null | system-derived | code-defined closed set (`core.audit.AUTOMATION_ACTOR_KINDS`), refused at construction | OK (US-AUD-010) |
| Actor — NOT a person (its name) | S61 Actor · Audit tabs | BR-AUD-019 | `audit_log.actor_label` — *"Returned payments"* | text, null | system-derived | non-empty whenever a kind is set — writer AND the table's CHECK; **never an id** (B14 rule 31) | OK (US-AUD-010) |
| Actor — NOT a person (its version) | S61 Actor · Audit tabs | BR-AUD-019 | `audit_log.actor_version` — *"4"* | text, null | system-derived | optional; TEXT so a build-numbered job (`2.209.0`) fits. **Its own column: the screen composes *"Returned payments, version 4"* in the reader's language, so the sentence is never stored** (B14 rule 35) | OK (US-AUD-010) |
| Actor never borrows a login | — | BR-RBS-015 | CHECK `ck_audit_actor_named_never_borrows_a_login` | — | system-derived | a named actor carries no `actor_user_id`; refused at the writer AND by the table | OK (US-AUD-010) |
| Action code | S61 Action | B2 §audit (`action text`) + corpus grammar | `audit_log.action` — catalog-validated at the write service | text | system-derived | dotted `entity.action`; seeded catalog only (BR-AUD-005) | OK (US-AUD-002) — see AUD-D1 |
| Action-type class ×6 | S61 filter | A1 S61 addendum | catalog property of the code (code-defined registry, no tenant table) | enum | reference-data | create/update/status/money/approval/auth; exactly one per code | OK (US-AUD-002) |
| Module mapping | S61 filter | A1 S61 + B2 §1 ownership | catalog property (entity_type → owning module) | text | reference-data | B2 module map | OK (US-AUD-002) |
| Entity refs | S61 Entity (linked) | B2 §audit + A1 S61 | `audit_log.entity_type` + `.entity_id` → owning screen route | text/uuid | system-derived | tenant-scoped route; deleted entity → labeled non-link | OK (US-AUD-001/005) |
| Before/after payload | S61 drawer | B2 §audit + A1 S61 (JSON diff) | `audit_log.before` / `.after` jsonb | jsonb | system-derived | changed-fields on update; snapshot on create; before-only terminal | OK (US-AUD-002) |
| PII in payloads | S61 drawer | BR-CUS-045 + NFR-13 + pii-inventory | masked forms only in jsonb; HIGH plaintext never present (payloads = MED class) | text | system-derived | automated pattern scan | OK (US-AUD-002/005) |
| When | S61 When | B2 §audit + IS-8 | `audit_log.created_at` timestamptz UTC → tenant-TZ render | ts | system-derived / computed-display | Regional settings | OK (US-AUD-001/004) |
| Summary (one line) | S61 | A1 S61 ("before → after, one line") | derived from `.before`/`.after` | text | computed-display | masked values as stored | OK (US-AUD-004) |
| Source (UI/API/job) | S61 Source | A1 S61 addendum | **GAP — no B2 column** (see AUD-D2) | enum | system-derived | column renders honest-empty until anchored | GAP → AUD-D2 |
| Request metadata | S61 drawer | A1 S61 addendum | **GAP — no B2 column** (see AUD-D2) | — | system-derived | drawer section renders when anchored | GAP → AUD-D2 |
| Related approval ref | S61 drawer | A1 S61 + BR-BIL-014/BR-PAY-014/r12 #14 | payload-carried refs → linked | link | computed-display | when present; see AUD-D3 | OK w/ note (US-AUD-005) |
| Filter bar (date/actor/module/entity/action type) | S61 | A1 S61 addendum | query over `audit_log` + catalog mappings | mixed | user-input | AND-combined; IS-4 URL state | OK (US-AUD-004) |
| Role gate (System Admin + Executive) | S61 | A1 S61 addendum | server-side permission check (A4) | — | reference-data | UI gating convenience only | OK (US-AUD-004) |
| Entity read service | S21 / premises + unit / S50 Audit tabs | BR-MET-045/048 + BR-AST-019 + A1 S61 | `audit_for_entity()` over `ix_audit_entity (tenant_id, entity_type, entity_id, created_at)` (B2 §4) | rows | system-derived | read-only; newest-first; tenant-scoped | OK (US-AUD-005) |
| "Full log" link | every Audit tab | A1 S61 entry note | S61 route pre-filtered (IS-4 grammar) | link | computed-display | entity filter pre-set | OK (US-AUD-005) |
| CSV export + filename | S61 / files | A1 S61 (IS-9) + IS-11 + BR-SHL-016 | streamed query under caller RLS (US-SHL-008 path) | file | computed-display | 50k cap; filters + visible columns; basis segment `event-time` | OK (US-AUD-006) |
| Export audit row | S61 | BR-SHL-016 | `audit_log` `audit.exported` (who/filters/row count) | jsonb | system-derived | append-only | OK (US-AUD-006) |
| Compliance-stamp links (reads/payments/assets/accounts batches) | S61 drawer → S29 + owner surfaces | BR-MET-017 + BR-PAY-023 + BR-AST-023 + BR-CUS-051 | owner-module batch tables (metering/payments/assets/customers-owned) | link | computed-display | read-only at owner; source files WRITE-ONCE 7yr (NFR-35) | OK (US-AUD-006) |
| Monthly partitions | — | NFR-24/28 + B2 §5 | RANGE (created_at) monthly; pre-create 3 ahead | DDL | system-derived | mechanics Eng-Lead 🔒 | OK (US-AUD-001) — closes B2 §5's open retention note via OQ-017 |
| Append-only enforcement | — | B2 §audit comment + §3 trigger family | block UPDATE/DELETE trigger | DDL | system-derived | Eng-Lead 🔒 | OK (US-AUD-001) |
| Hot-window bound (2 yr) + archive opt-in | S61 | NFR-28 + BR-MET-055 pattern | job/query config: 24 months; "Search archive" query-scope flag (no schema) | interval/boolean | reference-data / user-input | default hot; archive explicit, RLS-identical | OK (US-AUD-007/008) |
| Partition detach / purge | — | NFR-28 + data-retention.md | DETACH PARTITION → cold storage; purge past 7 yrs supervised | storage op | system-derived | never manual; audited; Eng-Lead 🔒 | OK (US-AUD-007) |
| Archive job run record | — | BR-AUD-012 ("audited") | **PROPOSED-SCHEMA** `archive_job_runs` family (US-MET-020 §5 pattern shared) | row | system-derived | append-only; rerun-safe | PROPOSED-SCHEMA (US-AUD-007) |
| Self-audit rows | S61 | BR-AUD-012 + CLAUDE.md #7 spirit | `audit_log` `audit_log.partition_archived` / `.partition_purged` | jsonb | system-derived | append-only | OK (US-AUD-007) |
| User-activity-audit feed params/columns | S44 → viewer | A14 §Compliance + A1 S61 | S61 dataset via IS-11 pipeline; schedule/run rows = reports contracts (R-1 anchor pending at reports) | mixed | user-input / computed-display | columns = the six S61 columns exactly; extensions = R-2 | OK (US-AUD-009) |

## Discrepancies & verification notes (vs B2 + NFR law)

| # | Finding | Disposition |
|---|---|---|
| AUD-D1 | **No audit event-code lookup table exists in B2** — `audit_log.action` is bare `text`; audit codes are absent from the BR-TEN-036 extensible-vocabulary list (r5 #20). Pack ships the catalog platform-seeded + code-defined (BR-AUD-005, PROPOSED); tenant extensibility undecidable from the corpus. | Candidate OQ (pack report) — lookup-table anchoring + extensibility ruling; stories buildable seeded-only |
| AUD-D2 | **A1 S61 shows a Source column (UI/API/job) + request-metadata drawer section, but B2 §audit anchors NO column for either** (columns: id, tenant_id, actor_user_id, action, entity_type, entity_id, before, after, created_at). BR-MET-017's session+IP live on the import-batch stamp, not on audit_log. | **GAP** — candidate OQ (pack report); Eng-Lead anchoring batch item (DDL 🔒). Viewer renders the column honest-empty until anchored; nothing invented |
| AUD-D3 | S61 drawer's "related OQ/approval reference" has no dedicated linkage column — approval refs exist in owner tables (correction_cases, refunds, void-approval r12 #14). v1 renders refs the payload carries. | OK w/ note — payload-carried; dedicated linkage = same Eng-Lead anchoring batch as AUD-D2 if wanted |
| AUD-D4 | `audit_log` has no `updated_at`, breaking the B2 "created_at/updated_at everywhere" convention — **deliberate**: append-only rows are never updated. | OK — verified deliberate (B2 §audit DDL), no action |
| AUD-D5 | The S61 `auth` action-type class exists (A1), but the full security-event catalog (lockouts, denials, IP blocks + alerting) = **SC-3 PENDING**. Ratified auth-audit rows today: BR-IDN-019 (policy edits), BR-IDN-027 (email changes), BR-IDN-012 family. | Cited, NOT decided — codes seed for ratified rows only; SC-3 with the PO |
| AUD-D6 | End-of-retention edge cases: closed-tenant offboarding SLA (data-retention.md **OPEN** row) + closed-account PII (**SC-7**). The 7yr/2yr law is enforced (OQ-017 closure); these may re-configure it. | Cited, NOT decided — US-AUD-007 exposes a config seam only |
| AUD-D7 | Tamper-evidence: no ratified doc supports a hash chain; posture = plain append-only trigger + RLS FORCE (B2 §audit comment + §3). Considered and excluded — inventing crypto controls would violate the cardinal rule. | OK — posture matches the ratified corpus |
| AUD-D8 | B2 §5's `audit_log` retention line still reads "UNKNOWN — audit retention window?" — **superseded by the OQ-017 closure** (7-yr total, 2-yr hot, PO R6) and NFR-28; B2 line not yet redlined. | Editorial — flag to the B2 owner at next addendum batch |

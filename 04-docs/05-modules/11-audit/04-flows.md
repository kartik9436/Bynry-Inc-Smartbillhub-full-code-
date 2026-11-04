# audit — Flows & States

Screens: S61 viewer (+ S8 Security entry) · per-entity Audit tabs (S21 / premises + unit / S50 — windows) · S44 Compliance card feed (details: A1 screen inventory + S61 addendum, A9 navigation map). Extracted at pack authoring 2026-08-09 (BR-AUD-001..017).

## 1. Write flow (US-AUD-001/002/003 — the only way in)
```
any module's audited event (money action · settings save · lifecycle change · import commit · export)
  → audit-write SERVICE (sole path, B1; single INSERT, no fan-out; async-callable NFR-4)
     code ∈ seeded catalog (entity.action; class create|update|status|money|approval|auth)
     payload = who / when(UTC) / tenant / entity / before→after (PII MASKED per BR-CUS-045)
  → audit_log row (monthly partition, RLS FORCE, append-only — no UPDATE/DELETE path exists)
  guarantee: rule 7 — the row exists whenever the action stands (mechanics Eng-Lead 🔒)
```

## 2. Read flows (US-AUD-004/005 — one store, many windows)
```
S8 Security "View audit log →" ─┐
entity Audit tab "full log" ────┤→ S61 (System Admin + Executive; TENANT-SCOPED-ONLY, OQ-029)
                                │    filter bar: date · actor · module · entity · action type (IS-4 URL)
                                │    table: When(TZ) · Actor · Action · Entity(link) · Summary · Source*
                                │    row → drawer: JSON diff · request metadata* · approval ref
                                │         (*Source/request metadata = GAP AUD-D2, render when anchored)
account S21 / premises·unit / asset S50 Audit tabs
  → audit_for_entity() (ix_audit_entity; read-only; newest-first) — same rows as S61 filtered, never a copy
import-batch audit row → compliance stamp at its OWNER (BR-MET-017/BR-PAY-023/BR-AST-023/BR-CUS-051)
```

## 3. Export / feed flow (US-AUD-006/009)
```
S61 Export · S44 "User activity audit" card
  → BR-SHL-016 path: streamed under caller RLS · 50k cap · filters + visible columns
  → IS-11 files: CSV always (basis segment `event-time`) · PDF (compliance class) for the feed
  → the export/generation itself writes `audit.exported` (self-audit)
  feed schedule/runs ride the reports scheduler contracts (US-REP-013/014/004)
```

## 4. Lifecycle flow (US-AUD-007/008 — NFR-28, the reads pattern)
```
partition pre-create (3 ahead, scheduled)
  → hot window (2 yrs; S61 + tabs query ONLY this by default)
  --monthly job (automatic, NEVER manual)--> partitions fully >2yr DETACH → cold storage
       (checksummed run record + audit_log.partition_archived — the job audits itself)
  --explicit "Search archive" opt-in--> archive reads, labeled, read-only, RLS-identical
  --past 7 yrs--> supervised purge inside the job, recorded (+ .partition_purged)
       never an operational delete; closed-tenant/SC-7 dispositions OPEN → config seam only
```

State machines relevant here: none of audit's own beyond the storage lifecycle above (rows are stateless, append-only by law — BR-AUD-002); A5 machines appear only INSIDE payloads as before→after values.

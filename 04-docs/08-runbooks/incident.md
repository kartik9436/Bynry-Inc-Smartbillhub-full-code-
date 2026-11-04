# Runbook — Incident Response
Severity: SEV1 money wrong or cross-tenant exposure · SEV2 core flow down (billing/payments) · SEV3 degraded · SEV4 cosmetic.
SEV1 adds: freeze affected job types (billing runs, exports), snapshot audit_log, notify affected tenant(s) within contractual window, post-incident review with written timeline in 12-governance/02-decision-log.md.
Escalation: on-call → Eng Lead → PM (tenant comms via 11-change-management/03-communications templates).
Never: hotfix money data by direct SQL. Corrections go through the correction paths and write audit rows.

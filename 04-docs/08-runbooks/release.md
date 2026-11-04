# Runbook — Release
1. Gates green: golden · isolation · immutability · E2E money journey · migration-guard.
2. QA go/no-go recorded (12-governance/02-decision-log.md); CR record filed (11-change-management/01-releases/).
3. Migrations first, additive-only; verify RLS on any new tables before app deploy.
4. Deploy API → web; smoke: sign-in, account detail, record payment (test tenant).
5. Tag + CHANGELOG entry; tenant-facing notes via 11-change-management/03-communications if behavior changed.
Rollback: app rollback anytime; schema rollbacks forbidden — roll forward with a fixing migration.

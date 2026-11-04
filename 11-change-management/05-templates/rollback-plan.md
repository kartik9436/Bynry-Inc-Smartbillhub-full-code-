# Rollback Plan — CR-YYYY-###
**Trigger conditions:** <what observation forces rollback>
**App rollback:** <previous tag, steps>
**Schema:** roll FORWARD only (fixing migration) — schema rollbacks are forbidden (04-docs/08-runbooks/release.md)
**Data corrections:** via correction paths + audit rows, never direct SQL
**Verification after rollback:** <smoke checks>

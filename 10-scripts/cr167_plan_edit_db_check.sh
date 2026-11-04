#!/usr/bin/env bash
# CR-167-BRC10 round 3 task 8 (lane PLAN-EDIT) — what the three Edit ways
# wrote, read straight from PostgreSQL 16. Read-only.
#   DB=sbh_planedit PLAN_CODE=SCW-RES 10-scripts/cr167_plan_edit_db_check.sh
set -euo pipefail
DB="${DB:-sbh_planedit}"
CODE="${PLAN_CODE:-SCW-RES}"
PSQL=(psql -h 127.0.0.1 -p "${PGPORT:-55433}" -U postgres -d "$DB" -X -q)
"${PSQL[@]}" -v code="$CODE" <<'SQL'
\echo '— the plan row (one row, its id never changes)'
select id, code, version, name, left(description, 60) as description, effective_from, effective_to,
       minimum_bill_amount, budget_billing, head_version_id
  from rate_plans where code = :'code';
\echo '— every version row, oldest first (nothing is ever deleted)'
select v.id, v.version_no as v, v.status, v.effective_from, v.effective_to, v.minimum_bill_amount as minimum,
       v.budget_billing as budget, v.corrects_version_id is not null as is_correction,
       v.superseded_by_version_id is not null as superseded, coalesce(v.correction_reason, v.change_reason) as reason
  from plan_versions v join rate_plans p on p.id = v.rate_plan_id
 where p.code = :'code' order by v.created_at;
\echo '— bindings per version row (services · schedules · charge rules · tax rules)'
select v.version_no as v, v.status, v.superseded_by_version_id is not null as superseded,
       (select count(*) from plan_services s where s.plan_version_id = v.id) as services,
       (select count(*) from plan_rate_schedules r where r.plan_version_id = v.id) as schedules,
       (select count(*) from plan_charge_rules c where c.plan_version_id = v.id) as charges,
       (select count(*) from plan_tax_rules t where t.plan_version_id = v.id) as taxes
  from plan_versions v join rate_plans p on p.id = v.rate_plan_id
 where p.code = :'code' order by v.created_at;
\echo '— audit_log rows for the plan, newest first'
select a.created_at, a.action, left(coalesce(a.after::text, ''), 140) as after
  from audit_log a join rate_plans p on p.id::text = a.entity_id::text
 where p.code = :'code' order by a.created_at desc limit 12;
SQL

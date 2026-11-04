#!/bin/bash
# record checks for one account on smartbillhub_mvo2
export PGPASSWORD=smartbillhub
P="psql -U smartbillhub -h localhost ${DB:-smartbillhub_mvo2} -P pager=off -q"
A="$1"
$P <<SQL
\echo == account
select a.account_no, a.closed_at, s.code status, s.behavior_class, a.deposit_on_file, a.close_reason from accounts a join account_statuses s on s.id=a.status_id where a.account_no='$A';
\echo == final invoices
select i.invoice_no, i.bill_type, i.status, i.period_start, i.period_end, i.total, i.bill_payload ? 'created_by_move_out' marker, r.bill_date, r.due_days from invoices i join bill_runs r on r.id=i.bill_run_id join accounts a on a.id=i.account_id where a.account_no='$A' and i.bill_type='final' and i.created_at > now() - interval '4 hours' order by i.created_at;
\echo == lines
select l.description, round(l.quantity,2) qty, l.unit_price, l.amount from invoice_lines l join invoices i on i.id=l.invoice_id join accounts a on a.id=i.account_id where a.account_no='$A' and i.bill_type='final' and i.created_at > now() - interval '4 hours' order by l.amount desc;
\echo == journal (by entry, designation)
select je.posting_key, la.designation, jl.side, sum(jl.amount) amt from journal_entries je join journal_lines jl on jl.journal_entry_id=je.id join ledger_accounts la on la.id=jl.ledger_account_id where je.source_id in (select i.id from invoices i join accounts a on a.id=i.account_id where a.account_no='$A' and i.bill_type='final' and i.created_at > now() - interval '4 hours') group by 1,2,3 order by 1,3,2;
\echo == entries balanced?
select je.posting_key, sum(case when jl.side='debit' then jl.amount else 0 end) dr, sum(case when jl.side='credit' then jl.amount else 0 end) cr from journal_entries je join journal_lines jl on jl.journal_entry_id=je.id where je.source_id in (select i.id from invoices i join accounts a on a.id=i.account_id where a.account_no='$A' and i.bill_type='final' and i.created_at > now() - interval '4 hours') group by 1;
\echo == delivery rows
select channel, status, template_code, unavailable_reason from outbound_messages where source_id in (select i.id from invoices i join accounts a on a.id=i.account_id where a.account_no='$A' and i.bill_type='final' and i.created_at > now() - interval '4 hours');
\echo == audit rows today
select action, entity_type, created_at from audit_log where created_at > now() - interval '3 hours' and (entity_id in (select id from accounts where account_no='$A') or entity_id in (select i.id from invoices i join accounts a on a.id=i.account_id where a.account_no='$A' and i.bill_type='final')) order by created_at;
\echo == meter reads today
select r.read_at::date, r.current_value, r.consumption, r.unit, r.source, r.lifecycle from meter_reads r join accounts a on a.id=r.account_id where a.account_no='$A' and r.created_at > now() - interval '3 hours';
SQL

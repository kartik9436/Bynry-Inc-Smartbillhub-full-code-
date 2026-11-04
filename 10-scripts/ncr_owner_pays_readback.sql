-- ncr_owner_pays_readback.sql — DEF-CUS-9228 / DEF-CUS-9195 read-back for the
-- lane NC-R walk (PO rulings 2026-10-02, items 1 and 2). Read-only.
--   psql -h 127.0.0.1 -p 55433 -U postgres -d <walk db> -v cno="'CON-26-0130'" -f 10-scripts/ncr_owner_pays_readback.sql
\echo '— the build, its owner account, its premises'
SELECT c.connection_no, c.state, a.account_no, a.kind, s.code AS account_status,
       u.label AS unit, p.status AS premises_status, p.master_account_id IS NOT NULL AS premises_names_a_master,
       a.preferred_language
  FROM connections c
  JOIN accounts a ON a.id = c.owner_account_id
  JOIN account_statuses s ON s.id = a.status_id
  LEFT JOIN units u ON u.id = a.unit_id
  JOIN premises p ON p.id = c.premises_id
 WHERE c.connection_no = :cno;
\echo '— the bill Create raised, and whose it is'
SELECT i.invoice_no, i.total, i.status, a.account_no, (i.account_id = c.owner_account_id) AS on_the_owner_account
  FROM connections c JOIN invoices i ON i.id = c.quote_invoice_id JOIN accounts a ON a.id = i.account_id
 WHERE c.connection_no = :cno;
\echo '— its lines'
SELECT l.description, l.quantity, l.unit_price, l.amount
  FROM connections c JOIN invoice_lines l ON l.invoice_id = c.quote_invoice_id
 WHERE c.connection_no = :cno ORDER BY l.amount DESC;
\echo '— the payment taken at Create'
SELECT pm.payment_no, pm.amount, pm.status, a.account_no, (pm.account_id = c.owner_account_id) AS on_the_owner_account
  FROM connections c JOIN payments pm ON pm.account_id = c.owner_account_id JOIN accounts a ON a.id = pm.account_id
 WHERE c.connection_no = :cno;
\echo '— the customer behind the account'
SELECT cu.customer_no, cu.display_name
  FROM connections c JOIN customer_accounts ca ON ca.account_id = c.owner_account_id JOIN customers cu ON cu.id = ca.customer_id
 WHERE c.connection_no = :cno;

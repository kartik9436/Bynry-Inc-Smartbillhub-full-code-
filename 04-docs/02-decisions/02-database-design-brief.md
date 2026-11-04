# B2 — Database Design Brief (authoritative schema)

> This is the Postgres 16 schema derived from the design. Constraints (RLS, money precision, immutability, partitioning) are firm; every `UNKNOWN` in §6 is a human/finance decision.

> ## Post-design confirmations (finance, 2026-08-07) — apply these to the DDL below
> - **Tax base = usage + base only** → add `invoice_lines.taxable boolean NOT NULL DEFAULT false` (true only on usage/base lines; fees & late charges = false, so the tax engine sums only taxable lines).
> - **Account-level tax exemption** (not per service) → add `accounts.tax_exempt boolean NOT NULL DEFAULT false`, `accounts.tax_exempt_ref text`, `accounts.tax_exempt_expires date`. When true, tax = 0 for the whole account.
> - **Late fee** = `max(5.00, 0.015 × prior_balance)`, grace counted **from the invoice due date**, in either **calendar or business days** → add tenant settings `late_grace_mode` (enum: calendar|business) and `late_grace_days integer`.
> - **Proration** = calendar days, base + usage both prorated (no schema change; rating-engine rule).
> - **Multiplier before tiers; tiers reset per bill** (no schema change; rating-engine rule).
> - **Connection counts are indicative, not enforced** — do NOT add any per-tenant account-count constraint.

> Derived from the prototype (`UtilityBilling.reference.html.txt`) and BUILD_SPEC.md.
> **Cardinal rule:** anything not determinable from the UI is `UNKNOWN — <question>`, never invented.
> Conventions: `snake_case`, plural tables, singular columns, UUID v7 PKs named `id`, FKs `<entity>_id` (all indexed), money & rates `NUMERIC(18,6)` + separate `CHAR(3)` currency, consumption `NUMERIC(18,6)` + explicit `unit`, all times `TIMESTAMPTZ` UTC, `created_at`/`updated_at` everywhere.
> Assumes extensions: `pgcrypto`/`uuidv7` (PK default), and a session GUC `app.tenant_id`. UUID v7 via `uuidv7()` — if unavailable on the target, substitute a v7 function; flagged as Open Question O-1.

---

## 1. ER Outline (text)

**tenancy** — `tenants` (1:N everything tenant-scoped) · `plans` (platform) · `subscriptions` (tenant N:1 plan) · `tenant_services` (tenant N:M service enum).
**identity** — `users` · `roles` · `permissions` · `role_permissions` (N:M) · `tenant_memberships` (user N:M tenant, carries role) · `sso_links`.
**customers** — `accounts` (the billing account) · `contacts` · `addresses` · `service_agreements` (account↔service_point↔tariff over time).
**metering** — `service_points` (a metered service at a unit) · `meters` (incl. sub-meters, self-ref) · `meter_reads` · `read_schedules` · `routes` · `cycles` · `premises` · `units`.
**rating** — `tariffs` · `tariff_versions` (service-dated) · `rate_tiers` · `time_of_use_windows` · `charges` (charge codes) · `taxes`.
**billing** — `bill_runs` · `invoices` · `invoice_lines` · `adjustments` · `credit_notes`.
**payments** — `payment_methods` · `payments` · `allocations` (payment→invoice N:M) · `refunds` · `payment_plans` · `payment_plan_installments` · `deposit_batches` · `bank_lines`.
**ledger** — `ledger_accounts` · `journal_entries` · `journal_lines`.
**notifications** — `notification_templates` · `notifications`.
**audit** — `audit_log`.

Cardinalities: tenant 1:N premises 1:N units 1:N service_points 1:N meters(1:N sub-meters) 1:N meter_reads. account 1:N invoices 1:N invoice_lines. account 1:N payments; payment N:M invoice via allocations. tariff 1:N tariff_versions 1:N rate_tiers / tou_windows. journal_entry 1:N journal_lines (balanced).

**Platform-level tables (no `tenant_id`), justified:**
- `plans` — the 3 SMARTBillHub SKUs (Starter/Growth/Scale); identical for all tenants.
- `roles`, `permissions`, `role_permissions` — system-defined RBAC catalog. `UNKNOWN — will tenants define custom roles? If yes, roles becomes tenant-scoped.`
- `countries`, `tax_jurisdictions` — reference geography/authorities. `UNKNOWN — are jurisdictions truly global or tenant-entered? Prototype shows named TX authorities; modelled global with tenant-scoped linkage table.`
- `services` — closed enum of service types (see below); implemented as ENUM, so no table.

---

## 2. DDL — module by module

```sql
-- ═══════════════ prerequisites ═══════════════
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- uuidv7(): use pg_uuidv7 extension or a SQL/PLpgSQL shim. See O-1.

-- Closed, short value sets → native ENUMs.
CREATE TYPE service_type      AS ENUM ('electric','water','gas','sewer','trash','broadband');
CREATE TYPE currency_code     AS ENUM ('USD','CAD'); -- prototype offered only these; extend as needed
CREATE TYPE account_status    AS ENUM ('pending','active','marked_disconnect','closed','excluded');
CREATE TYPE meter_source      AS ENUM ('ami','manual','import'); -- SUPERSEDED (BR-CWP-074, PO 2026-09-04 -> a FOURTH value 'customer', the provenance flag on every customer-sent reading; built 2026-10-17, DEF-CWP-10175). The column is TEXT in apps/metering; models.READ_SOURCES carries the four.
CREATE TYPE read_status       AS ENUM ('ok','high','low','missing','estimated','days_threshold','factor_flag');
CREATE TYPE invoice_status    AS ENUM ('draft','issued','paid','void','corrected'); -- see O-4
CREATE TYPE payment_status    AS ENUM ('processing','cleared','failed','reversed','posted');
CREATE TYPE payment_type      AS ENUM ('payment','credit','adjustment');
CREATE TYPE payment_method_t  AS ENUM ('ach','card','check','cash','lockbox');
CREATE TYPE batch_status      AS ENUM ('in_transit','unmatched','matched','reconciled');
CREATE TYPE tariff_model      AS ENUM ('flat','tiered','time_of_use','demand'); -- from setup wizard + rate types
CREATE TYPE journal_side      AS ENUM ('debit','credit');
```

### Module: tenancy
```sql
CREATE TABLE plans (                       -- PLATFORM: identical SKUs for all tenants
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  code          text NOT NULL UNIQUE,       -- 'starter'|'growth'|'scale'
  name          text NOT NULL,
  price_month   numeric(18,6) NOT NULL,     -- 1000 / 5000 / 8000 (real constants)
  currency      char(3) NOT NULL DEFAULT 'USD',
  min_accounts  integer NOT NULL,           -- 0 / 300 / 1000
  max_accounts  integer NOT NULL,           -- 300 / 1000 / 3000
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz                 -- config entity → soft delete
);
COMMENT ON COLUMN plans.price_month IS 'Fixed monthly package price; rounding: display 2dp';

CREATE TABLE tenants (                      -- PLATFORM root
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  name          text NOT NULL,
  subdomain     text NOT NULL UNIQUE,
  state         text,                       -- UNKNOWN — FK to a states table? free text in UI
  currency      char(3) NOT NULL DEFAULT 'USD',
  tax_region    text,                       -- e.g. 'TX State+Local'; see rating.taxes
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);

CREATE TABLE subscriptions (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id),
  plan_id       uuid NOT NULL REFERENCES plans(id),          -- ⚠ cross-module (tenancy→tenancy, ok)
  status        text NOT NULL DEFAULT 'trial',               -- trial|active|... UNKNOWN full set (O-9)
  trial_ends_at timestamptz,                                 -- 14-day trial (real constant)
  started_at    timestamptz NOT NULL DEFAULT now(),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenant_services (              -- tenant N:M service_type
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id),
  service       service_type NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, service)
);
```

### Module: identity
```sql
CREATE TABLE roles (                        -- PLATFORM catalog (see O-5)
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  code text NOT NULL UNIQUE,                 -- owner|admin|staff|finance|platform_admin|customer
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE permissions (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  code text NOT NULL UNIQUE,                 -- e.g. 'invoice.void','tariff.update'
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE role_permissions (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  role_id uuid NOT NULL REFERENCES roles(id),
  permission_id uuid NOT NULL REFERENCES permissions(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (role_id, permission_id)
);
CREATE TABLE users (                        -- PLATFORM identity; membership carries tenant scope
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  email citext NOT NULL UNIQUE,              -- PII (encrypt/at-rest per O policy)
  full_name text NOT NULL,                   -- PII
  phone text,                                -- PII
  password_hash text,                        -- null if SSO-only
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE tenant_memberships (           -- user N:M tenant
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid NOT NULL REFERENCES users(id),          -- ⚠ cross-module identity→identity
  role_id uuid NOT NULL REFERENCES roles(id),          -- ⚠ cross-module → roles (platform)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id)
);
CREATE TABLE sso_links (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id uuid NOT NULL REFERENCES users(id),
  provider text NOT NULL,                     -- UNKNOWN — no SSO screen in prototype (O-13)
  external_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, external_id)
);
```

### Module: metering
```sql
CREATE TABLE premises (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name text,
  address_line text NOT NULL,                 -- PII-adjacent
  city text, state text, postal_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz                       -- config → soft delete
);
CREATE TABLE units (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  premises_id uuid NOT NULL REFERENCES premises(id),
  label text NOT NULL,                         -- 'Unit A', '200'
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, premises_id, label)
);
CREATE TABLE routes (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, code)
);
CREATE TABLE cycles (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,                          -- '08-A'
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, code)
);
CREATE TABLE service_points (               -- one metered service at a unit
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  unit_id uuid NOT NULL REFERENCES units(id),
  service service_type NOT NULL,
  route_id uuid REFERENCES routes(id),
  cycle_id uuid REFERENCES cycles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE meters (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  service_point_id uuid NOT NULL REFERENCES service_points(id),
  parent_meter_id uuid REFERENCES meters(id),  -- sub-meter self-reference
  meter_no text NOT NULL,                      -- 'M-4021'
  multiplier numeric(18,6) NOT NULL DEFAULT 1, -- meter factor (×10 seen)
  unit text NOT NULL,                          -- 'kWh'|'kgal'|... explicit, never defaulted (O-3)
  source meter_source NOT NULL DEFAULT 'manual',
  install_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, meter_no)
);
COMMENT ON COLUMN meters.multiplier IS 'Applied to (current-prior); order vs tiering UNKNOWN (O-2)';

CREATE TABLE read_schedules (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  cycle_id uuid NOT NULL REFERENCES cycles(id),
  frequency text NOT NULL,                     -- 'monthly' UNKNOWN full set
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE meter_reads (                  -- PARTITIONED (see §Partitioning); append-only in practice
  id uuid NOT NULL DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  meter_id uuid NOT NULL REFERENCES meters(id),
  account_id uuid REFERENCES accounts(id),     -- ⚠ cross-module metering→customers
  read_at timestamptz NOT NULL,                -- partition key
  period_start date, period_end date,
  prior_value numeric(18,6),
  current_value numeric(18,6),
  consumption numeric(18,6),                   -- (current-prior)*multiplier; see O-2
  unit text NOT NULL,                          -- explicit
  source meter_source NOT NULL,
  status read_status NOT NULL DEFAULT 'ok',
  days_since_prior integer,
  imported_by uuid REFERENCES users(id),       -- compliance who/when
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, read_at, id)         -- includes partition key
) PARTITION BY RANGE (read_at);
COMMENT ON COLUMN meter_reads.consumption IS 'NUMERIC(18,6); rounding at invoice-line finalization only';
```

### Module: customers
```sql
CREATE TABLE accounts (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  unit_id uuid NOT NULL REFERENCES units(id),  -- ⚠ cross-module customers→metering
  account_no text NOT NULL,                    -- 'A-10432'
  status account_status NOT NULL DEFAULT 'pending',
  balance numeric(18,6) NOT NULL DEFAULT 0,    -- cached; ledger is source of truth
  currency char(3) NOT NULL DEFAULT 'USD',
  deposit_on_file numeric(18,6) NOT NULL DEFAULT 0,
  credit_tier text,                            -- 'A' etc. UNKNOWN enum (O-14)
  autopay boolean NOT NULL DEFAULT false,
  opened_at date, closed_at date,              -- move-in/out
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, account_no)               -- unique WITHIN tenant
);
CREATE TABLE contacts (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  full_name text NOT NULL,                     -- PII
  email citext,                                -- PII
  phone text,                                  -- PII
  dob date,                                    -- PII (shown on account detail)
  gov_id_last4 text,                           -- PII (DL ****4218) — store tokenized, O policy
  is_primary boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE addresses (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  kind text NOT NULL DEFAULT 'mailing',        -- mailing|service
  line1 text NOT NULL, city text, state text, postal_code text,  -- PII
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE service_agreements (           -- account ↔ service_point ↔ tariff over time
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  service_point_id uuid NOT NULL REFERENCES service_points(id), -- ⚠ →metering
  tariff_id uuid NOT NULL REFERENCES tariffs(id),               -- ⚠ →rating
  started_on date NOT NULL,
  ended_on date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### Module: rating
```sql
CREATE TABLE tariffs (                      -- a "Plan" in the UI (customer-facing bundle)
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name text NOT NULL,                          -- 'Residential Standard'
  service service_type NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, name, service)
);
CREATE TABLE tariff_versions (              -- service-dated pricing; invoices reprice against the in-force version
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  tariff_id uuid NOT NULL REFERENCES tariffs(id),
  model tariff_model NOT NULL,
  base_charge numeric(18,6) NOT NULL DEFAULT 0,
  minimum_bill numeric(18,6),
  currency char(3) NOT NULL DEFAULT 'USD',
  effective_from date NOT NULL,                -- in-force window
  effective_to date,                           -- null = current
  approved_by uuid REFERENCES users(id),       -- rate-change approver (Doc: rate change history)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  EXCLUDE USING gist (                          -- no overlapping in-force windows per tariff
    tenant_id WITH =, tariff_id WITH =,
    daterange(effective_from, coalesce(effective_to,'infinity'::date)) WITH &&
  )
);
COMMENT ON TABLE tariff_versions IS 'Historical invoices join the version where service_date ∈ [effective_from,effective_to). Never the current version.';

CREATE TABLE rate_tiers (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  tariff_version_id uuid NOT NULL REFERENCES tariff_versions(id),
  seq integer NOT NULL,
  from_qty numeric(18,6) NOT NULL DEFAULT 0,
  to_qty numeric(18,6),                        -- null = ∞
  unit_price numeric(18,6) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tariff_version_id, seq)
);
CREATE TABLE time_of_use_windows (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  tariff_version_id uuid NOT NULL REFERENCES tariff_versions(id),
  label text NOT NULL,                         -- peak/off-peak UNKNOWN full config (O-2)
  start_time time NOT NULL, end_time time NOT NULL,
  unit_price numeric(18,6) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE charges (                      -- charge codes: CONN/DISC/NSF/LATE/TAMPER/SVCCALL/DEPO-R
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,
  name text NOT NULL,
  amount numeric(18,6),                        -- fixed portion (NSF $30, reconnect $45 — confirm O-9)
  percent numeric(18,6),                       -- e.g. late 1.5%
  min_amount numeric(18,6),                    -- late $5 minimum
  gl_account_id uuid REFERENCES ledger_accounts(id),  -- ⚠ →ledger
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, code)
);
COMMENT ON COLUMN charges.min_amount IS 'Late fee rule: greater of percent*base or min_amount ($5). EXPLICIT in UI.';

CREATE TABLE tax_jurisdictions (            -- PLATFORM reference (O-12)
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  name text NOT NULL,                          -- 'TX Comptroller'
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE taxes (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  jurisdiction_id uuid REFERENCES tax_jurisdictions(id),  -- ⚠ →platform
  name text NOT NULL,                          -- 'State sales tax'
  rate numeric(18,6) NOT NULL,                 -- 0.0625, 0.02, 0.01, 0.002
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
```

### Module: billing (financial immutability — append-only once issued)
```sql
CREATE TABLE bill_runs (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  cycle_id uuid NOT NULL REFERENCES cycles(id),
  period_start date NOT NULL, period_end date NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  idempotency_key text NOT NULL,               -- prevents double-run
  run_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
CREATE TABLE invoices (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  bill_run_id uuid REFERENCES bill_runs(id),
  invoice_no text NOT NULL,                    -- 'BL-2608-018410'
  service_date date NOT NULL,                  -- drives tariff_version selection
  period_start date NOT NULL, period_end date NOT NULL,
  due_date date,
  status invoice_status NOT NULL DEFAULT 'draft',
  subtotal numeric(18,6) NOT NULL DEFAULT 0,
  tax_total numeric(18,6) NOT NULL DEFAULT 0,
  total numeric(18,6) NOT NULL DEFAULT 0,
  currency char(3) NOT NULL DEFAULT 'USD',
  issued_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, invoice_no)
);
COMMENT ON COLUMN invoices.total IS 'Rounded to 2dp at finalization; components NUMERIC(18,6)';

CREATE TABLE invoice_lines (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  invoice_id uuid NOT NULL REFERENCES invoices(id),
  account_id uuid NOT NULL REFERENCES accounts(id),  -- denormalized for (tenant,account,period) index
  service service_type,
  tariff_version_id uuid REFERENCES tariff_versions(id),
  charge_id uuid REFERENCES charges(id),
  description text NOT NULL,
  quantity numeric(18,6),
  unit text,                                   -- explicit when usage-based
  unit_price numeric(18,6),
  amount numeric(18,6) NOT NULL,
  period_start date, period_end date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE adjustments (                  -- correction rows, never UPDATE the invoice
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  invoice_id uuid REFERENCES invoices(id),
  direction journal_side NOT NULL,             -- credit reduces / debit increases
  amount numeric(18,6) NOT NULL,
  reason_code text NOT NULL,
  gl_account_id uuid REFERENCES ledger_accounts(id),
  approved_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE credit_notes (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  original_invoice_id uuid REFERENCES invoices(id),  -- references the source, per immutability
  amount numeric(18,6) NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### Module: payments
```sql
CREATE TABLE payment_methods (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  kind payment_method_t NOT NULL,
  brand_last4 text,                            -- 'Chase ••4021' — PII/tokenized
  is_autopay boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE payments (                     -- append-only once cleared
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  type payment_type NOT NULL DEFAULT 'payment',
  method payment_method_t,
  amount numeric(18,6) NOT NULL,               -- credits/adjustments store signed? see O-4
  currency char(3) NOT NULL DEFAULT 'USD',
  status payment_status NOT NULL DEFAULT 'processing',
  confirmation text,
  received_at timestamptz NOT NULL,
  deposit_batch_id uuid REFERENCES deposit_batches(id),
  webhook_key text,                            -- inbound webhook idempotency
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, webhook_key)              -- dedupe double webhook delivery
);
CREATE TABLE allocations (                  -- payment N:M invoice
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  payment_id uuid NOT NULL REFERENCES payments(id),
  invoice_id uuid NOT NULL REFERENCES invoices(id),
  amount numeric(18,6) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE refunds (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  payment_id uuid NOT NULL REFERENCES payments(id),
  amount numeric(18,6) NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE payment_plans (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  total_amount numeric(18,6) NOT NULL,
  installment_count integer NOT NULL,
  status text NOT NULL DEFAULT 'proposed',     -- proposed|active|closed UNKNOWN default state (O-8)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE payment_plan_installments (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  payment_plan_id uuid NOT NULL REFERENCES payment_plans(id),
  seq integer NOT NULL,
  due_date date NOT NULL,
  amount numeric(18,6) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (payment_plan_id, seq)
);
CREATE TABLE deposit_batches (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,                          -- 'DEP-260805-CHK'
  method payment_method_t NOT NULL,
  recorded_total numeric(18,6) NOT NULL DEFAULT 0,
  bank_total numeric(18,6),
  status batch_status NOT NULL DEFAULT 'in_transit',
  deposited_on date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code)
);
CREATE TABLE bank_lines (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  deposit_batch_id uuid REFERENCES deposit_batches(id),
  posted_on date NOT NULL,
  reference text,                              -- 'CHECK DEPOSIT 4410'
  amount numeric(18,6) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### Module: ledger (double-entry, balanced)
```sql
CREATE TABLE ledger_accounts (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,                          -- '1200','4100','6100'
  name text NOT NULL,
  type text NOT NULL,                          -- asset|liability|revenue|expense UNKNOWN full COA (O-14)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, code)
);
CREATE TABLE journal_entries (              -- append-only
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  entry_date date NOT NULL,
  source_type text,                            -- 'invoice'|'payment'|'adjustment'|...
  source_id uuid,                              -- polymorphic ref (validated in app; see O-4)
  memo text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE journal_lines (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  journal_entry_id uuid NOT NULL REFERENCES journal_entries(id),
  ledger_account_id uuid NOT NULL REFERENCES ledger_accounts(id),
  side journal_side NOT NULL,
  amount numeric(18,6) NOT NULL CHECK (amount >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### Module: notifications
```sql
CREATE TABLE notification_templates (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,                          -- 'reminder','disconnect_2nd','receipt'
  channel text NOT NULL,                       -- email|sms|print
  subject text, body text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, code, channel)
);
CREATE TABLE notifications (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid REFERENCES accounts(id),
  template_id uuid REFERENCES notification_templates(id),
  channel text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  sent_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### Module: audit
```sql
CREATE TABLE audit_log (                    -- PARTITIONED; append-only, no update/delete
  id uuid NOT NULL DEFAULT uuidv7(),
  tenant_id uuid NOT NULL,                     -- not FK-constrained: must survive tenant purge
  actor_user_id uuid,                          -- a PERSON. NULL *and* no actor_kind = an
                                               --   unnamed system job (BR-AUD-003)
  -- ⚠ AMENDED 2026-09-06 — US-AUD-010 / BR-AUD-019 / migration `audit/0007`, implementing the
  --   PO-ruled BR-RBS-015 ("the runbook is the audit actor, named and versioned; it never
  --   borrows a user identity"). Nothing above is superseded: these three are ADDED, all three
  --   are NULLABLE, and NO ROW IS BACKFILLED — BR-AUD-002 allows no UPDATE on this table and the
  --   append-only trigger would refuse one. Every pre-existing row keeps exactly its old meaning.
  actor_kind text,                             -- runbook | job | import | integration (code-defined)
  actor_label text,                            -- what a clerk reads: 'Returned payments'
  actor_version text,                          -- '4'. TEXT so a build-numbered job ('2.209.0') fits.
                                               --   ⚠ SEPARATE FROM THE LABEL ON PURPOSE: a stored
                                               --   'Returned payments, version 4' is English in a
                                               --   column eleven catalogues cannot translate
                                               --   (B14 rule 35) — the screen composes it.
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  before jsonb, after jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, created_at, id),
  -- BR-RBS-015 at the last line of defence: a named actor NEVER carries a user id, and a kind is
  -- never anonymous. The writer refuses both too; this stops a future writer reintroducing either.
  CONSTRAINT ck_audit_actor_named_never_borrows_a_login CHECK (
    (actor_kind IS NULL AND actor_label IS NULL)
    OR (actor_kind IS NOT NULL AND actor_label IS NOT NULL AND actor_user_id IS NULL)
  )
) PARTITION BY RANGE (created_at);
```

---

### Module: integrations (added 2026-09-03 — `CR-069` `C34`, `US-INT-014`; anchored here BEFORE `integrations/0001` was written)
```sql
-- Five tables, and why not one: a secret can be rolled back in one row, a run history
-- survives a disconnect, a connection row is safe to read anywhere, a new partner costs
-- rows and not a migration, and a customer can ask who could see their data last year.
-- Source DDL: 04-docs/05-modules/13-integrations/03-field-map.md §5 (design §2.8 as revised).

CREATE TABLE integration_connection (         -- rarely changes. ⚠ NO SECRET MATERIAL — safe to
  id             uuid PRIMARY KEY,            --   SELECT *, to log and to put in an audit payload.
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  provider_key   text NOT NULL,               -- manifest key: "email_microsoft" (code data, no table)
  label          text,
  environment    text NOT NULL,               -- production | sandbox
  status         text NOT NULL,               -- not_set_up | untested | working | not_working | off
  enabled        boolean NOT NULL DEFAULT true,
  cadence        text NOT NULL DEFAULT 'manual',   -- nightly | hourly | manual
  next_run_at    timestamptz,                 -- NULL when cadence = manual
  config         jsonb NOT NULL DEFAULT '{}', -- NON-SECRET fields only (host, port, send_from, allowlist…)
  last_test_at   timestamptz,
  last_test_ok   boolean,
  last_test_text text,                        -- one sentence a clerk can read
  connected_by   uuid REFERENCES users(id),   -- ⚠ reviewed cross-module FK integrations → identity (r22)
  connected_at   timestamptz,
  created_at     timestamptz NOT NULL,
  updated_at     timestamptz NOT NULL,
  UNIQUE (tenant_id, provider_key, environment)   -- production and sandbox are two connections (BR-INT-026)
);

CREATE TABLE integration_credential (         -- versioned, never overwritten (BR-INT-025)
  id            uuid PRIMARY KEY,
  tenant_id     uuid NOT NULL REFERENCES tenants(id),
  connection_id uuid NOT NULL REFERENCES integration_connection(id),
  version       integer NOT NULL,
  is_active     boolean NOT NULL,
  payload_enc   text NOT NULL,                -- core.crypto EncryptedTextField (AES-256-GCM, kid in ciphertext)
  blind_index   text,                         -- issued secrets only: lookup without decrypting
  masked_hint   text NOT NULL,                -- "••••3F9A" — display only, never the secret
  scope         jsonb NOT NULL DEFAULT '[]',  -- CR-110-BRC04 (integrations/0010): WHICH OF OUR APIS THIS KEY MAY CALL.
                                              -- ⚠ THE DEFAULT IS SET BY 0010's OWN restore_scope_default().
                                              -- Django's AddField uses a field default to BACKFILL and then DROPS
                                              -- the database default, because it applies defaults in Python — so
                                              -- without that line a raw INSERT hits a NOT NULL violation instead
                                              -- of arriving with nothing granted. Found by a sibling's test.
                                              -- Operation names off the connection's own manifest. ⚠ EMPTY GRANTS
                                              -- NOTHING — the drawing's "leave blank for everything" is refused under
                                              -- hard-won law 3, and machine_auth.issue_key will not mint an empty one.
                                              -- On the CREDENTIAL and not the connection: replacing a key is the moment
                                              -- a partner's reach is meant to be reconsidered.
  expires_at    timestamptz,
  rotated_at    timestamptz,
  created_at    timestamptz NOT NULL,
  UNIQUE (connection_id, version),
  EXCLUDE USING btree (connection_id WITH =) WHERE (is_active)  -- exactly one active, by the database
);

CREATE TABLE integration_run (                -- constantly. APPEND-ONLY once finished (BR-INT-039)
  id             uuid NOT NULL,
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  connection_id  uuid NOT NULL REFERENCES integration_connection(id),
  operation      text NOT NULL,               -- C1: which of the provider's operations
  job_id         uuid,                        -- the core/jobs record
  direction      text NOT NULL,               -- outbound | inbound | inbound_read
  trigger        text NOT NULL,               -- manual | scheduled | dispatcher | webhook | partner
  attempted      integer NOT NULL DEFAULT 0,
  succeeded      integer NOT NULL DEFAULT 0,
  failed         integer NOT NULL DEFAULT 0,
  skipped        integer NOT NULL DEFAULT 0,
  changed        integer NOT NULL DEFAULT 0,  -- the fifth count: "1,240 read, 6 revised"
  outcome        text,                        -- queued|running|succeeded|partial|failed|unconfirmed|indeterminate
  summary        text,                        -- plain language, no rule id
  provider_error text,                        -- scrubbed by the adapter; shown to the owning tenant only
  input_hash     text,                        -- file in: the content hash, computed BEFORE parse
  artifact_link  text,
  trace_id       text NOT NULL,               -- the eight characters support searches by
  started_at     timestamptz NOT NULL DEFAULT now(),   -- ⚠ NOT NULL: it is the partition key (see r22)
  finished_at    timestamptz,
  PRIMARY KEY (tenant_id, started_at, id)     -- includes the partition key, as audit_log does
) PARTITION BY RANGE (started_at);            -- core/partitioning.py, YEARLY, create-ahead 1
-- No UPDATE after finish, no DELETE, ever. Corrections are new rows. A trigger refuses.

CREATE TABLE integration_target_reference (   -- their word for our thing — a ROW, never a column (BR-INT-032)
  id             uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  target_key     text NOT NULL,               -- which outside system: "qbo" | "xero" | "kiosk" …
  entity_type    text NOT NULL,               -- ledger_account | tender | route | reversal_reason | meter_type | service
  entity_id      uuid,                        -- NULL when the mapping is to an enum value…
  local_value    text,                        -- …in which case OUR value goes here
  external_value text NOT NULL,               -- "001.100.51200" | "ACHCHECK" | "R01"
  UNIQUE (tenant_id, target_key, entity_type, external_value)   -- the EXTERNAL side, on purpose
);
-- Added BESIDE ledger_accounts.qbo_ref / .xero_ref until OQ-INT-1480 rules on retiring them.

CREATE TABLE integration_rate_limit (         -- CR-110-BRC04 (integrations/0009): how many calls a minute a partner may make
  id              uuid PRIMARY KEY,
  tenant_id       uuid NOT NULL REFERENCES tenants(id),
  connection_id   uuid NOT NULL REFERENCES integration_connection(id) DEFERRABLE INITIALLY DEFERRED,
                                              -- ⚠ NOT `ON DELETE CASCADE`, AND THE MODEL SAYS
                                              -- on_delete=CASCADE — because that is DJANGO's cascade, issued
                                              -- in Python by .delete(), and it writes NO ACTION here. An ORM
                                              -- delete removes the ceilings; a RAW delete does not and is
                                              -- REFUSED at commit, which is the safe direction. Django creates
                                              -- a CreateModel's FKs in deferred_sql, flushed after every
                                              -- operation, so a migration cannot alter this constraint in the
                                              -- same migration that creates the table. integrations/0009's
                                              -- docstring has the whole story; three rounds of a failing test
                                              -- on real PostgreSQL is what produced it.
  operation       text NOT NULL,              -- the manifest's own operation name; code data, never an FK (BR-INT-037)
  calls_per_minute integer NOT NULL,
  created_at      timestamptz NOT NULL,
  updated_at      timestamptz NOT NULL,
  UNIQUE (connection_id, operation),          -- a row per connection AND per operation (blueprint p017)
  CHECK (calls_per_minute > 0)                -- a ceiling of no calls is a shut door, not a limit
);
-- PO 2026-09-16: "keep the limit in database so if we want to change it later it is easy to do",
-- and "so wecant allow clark to reset it" — DISPLAY ONLY, there is no clerk write path to this table.
-- A row per OPERATION because a quota is a fact about one utility's agreement and a manifest is shared
-- by every tenant; one number per connector would give a partner permitted 600 meter readings a minute
-- 600 refunds a minute for free. The COUNT of what has been used is deliberately NOT here — struck from
-- CR-110-BRC04 under the PO's "thats it", recorded as a candidate rather than smuggled in.
-- The shared counter that enforces it lives in apps/integrations/rate_limit_store.py, not in a table:
-- a write to the money database on every partner request would make a flood of refusals cost US more
-- than the caller, which is a rate limiter that helps the attacker.

CREATE TABLE integration_consent (            -- CONDITIONAL on OQ-INT-1482; in the brief, written by nothing
  id          uuid PRIMARY KEY,
  tenant_id   uuid NOT NULL REFERENCES tenants(id),
  account_id  uuid NOT NULL REFERENCES accounts(id),   -- ⚠ reviewed cross-module FK integrations → customers (r22)
  grantee     text NOT NULL,
  scope       jsonb NOT NULL,
  granted_at  timestamptz NOT NULL,
  granted_by  uuid,                           -- the CUSTOMER, not a member of staff
  expires_at  timestamptz,
  revoked_at  timestamptz,                    -- set, never deleted (BR-INT-036)
  revoked_by  uuid
);
```

---

### Module: work (added 2026-09-03 — `CR-070` wave A, `US-WRK-001` / `US-WRK-005`; anchored here IN THE SAME COMMIT as `metering/0044`, per `CR-070` §2(a))
```sql
-- Work is the ELEVENTH code module (PO 2026-09-03, verbatim: "it will become the module itself";
-- BR-WRK-001). Phase 0 gives it NO TABLE OF ITS OWN: the six Work tables — connections,
-- connection_services, work_orders, work_order_templates, connection_todos,
-- service_characteristics — were created by metering/0026 and 0027 and still live in
-- apps/metering/connections.py. Whether and when they MOVE into apps/work/ is
-- 04-docs/05-modules/16-work/03-field-map.md §4, PENDING the blueprint's §16 and the lane that
-- writes work/0001. Until then Work READS them through apps/work/seams/metering_seam.py and
-- writes work_orders through exactly one named door there (metering's own create_work_order).
--
-- The ONE phase-0 schema change, on a METERING table (metering/0044) — BR-WRK-006, WM-01 + our CHECK:
ALTER TABLE work_orders ALTER COLUMN connection_id DROP NOT NULL;   -- was NOT NULL: every order had to be a build's
ALTER TABLE work_orders ADD COLUMN premises_id uuid REFERENCES premises(id);   -- the premises a job is AT (metering's own)
ALTER TABLE work_orders ADD COLUMN account_id  uuid REFERENCES accounts(id);   -- ⚠ reviewed cross-module FK metering → customers (r23)
ALTER TABLE work_orders ADD CONSTRAINT ck_work_orders_has_anchor
  CHECK (connection_id IS NOT NULL OR premises_id IS NOT NULL OR account_id IS NOT NULL OR asset_id IS NOT NULL);
-- No data moves; every existing row keeps its connection_id. RLS ENABLE + FORCE on work_orders
-- (metering/0026) is untouched. The tables of phases 1–2 (reference data, the template bundle,
-- workforce, dispatch — 16-work/03-field-map.md §2) arrive with their waves, each with its own
-- *rls* migration and its own row here.
```

---

### Module: runbooks (added 2026-09-06 — `CR-075` wave A task `A1`, `US-RBS-041`; anchored here BEFORE `runbooks/0001_initial.py` was written)
```sql
-- Seven tables, all this module's own, none owned by anyone else. Source DDL:
-- 04-docs/05-modules/17-runbooks/03-field-map.md §1–§7 (specification B3).
--
-- ⚠ THE MODULE DIRECTORY AND THE NAV ROUTE ARE TWO DIFFERENT NAMES ON PURPOSE.
-- The code module is `apps/runbooks` (PO naming ruling 2026-09-06, "we coin the
-- word Runbooks"); the nav route stays `/{tenant}/operations` as every wireframe
-- draws it; the seam files keep the source's `operations -> <module>` pair
-- naming. The specification says `apps/operations` throughout, superseded for the
-- CODE only. 03-field-map.md D-5 records all three names as deliberate.
--
-- ⚠ THREE TYPE DEPARTURES FROM THE FIELD MAP'S DRAFT, EACH FORCED AND EACH
-- STATED IN ADDENDUM r24 RATHER THAN LEFT TO BE INFERRED: `runbooks.tags` is
-- `jsonb` and not `text[]`; `runbook_run_records` GAINS `currency CHAR(3)` (the
-- field map's D-2 gap); `cutover_plan_items.owner` is `text` and not a user
-- reference (D-7).

CREATE TABLE runbooks (                       -- one row per runbook available to the tenant
  id              uuid PRIMARY KEY,
  tenant_id       uuid NOT NULL REFERENCES tenants(id),
  key             text NOT NULL,              -- the runbook's address: /runbooks/{key}
  name            text NOT NULL,
  kind            text NOT NULL,              -- check | action — IMMUTABLE after creation (BR-RBS-001)
  category        text NOT NULL,              -- one of SIXTEEN held in code, never free text (BR-RBS-024);
                                              --   the category NAMES the owning module whose ports it may call
  tags            jsonb NOT NULL DEFAULT '[]',-- ⚠ jsonb, not text[] — r24 departure 1
  origin          text NOT NULL,              -- shipped | cloned | composed
  template_key    text,                       -- the shipped template this copy came from (BR-RBS-038)
  cloned_from     uuid REFERENCES runbooks(id),
  subject_type    text NOT NULL,              -- one of TWELVE: tenant|account|premise|meter|meter-day|bill|
                                              --   payment|bank line|deposit|parcel|contact feedback|period
  unit_of_work    text NOT NULL,              -- NEVER the raw row (BR-RBS-019): 176,640 intervals -> 1,840 meter-days
  enabled         boolean NOT NULL DEFAULT true,
  trigger_kind    text NOT NULL,              -- manual | schedule | event
  cron            text,                       -- evaluated in `timezone`, on the platform job runner (BR-RBS-016)
  event_kind      text,                       -- batch.landed | feedback.landed | bill_run.completed
  timezone        text NOT NULL,              -- the TENANT's own, as the notification schedule already does
  cap             integer,                    -- REFUSES the run; never truncates (BR-RBS-006). ⚠ NO DEFAULT:
                                              --   an Action cannot be enabled until an admin types one
                                              --   (OQ-RBS-1731 OPEN; an answer can only ever WIDEN this)
  gate_mode       text NOT NULL,              -- who approves and at which point (BR-RBS-018)
  current_version integer NOT NULL DEFAULT 1, -- points at the newest runbook_versions row
  created_at      timestamptz NOT NULL,
  updated_at      timestamptz NOT NULL,
  UNIQUE (tenant_id, key)                     -- "stable and unique per tenant" [B3]
);

CREATE TABLE runbook_versions (               -- an IMMUTABLE snapshot each time the definition changes
  id          uuid PRIMARY KEY,
  tenant_id   uuid NOT NULL REFERENCES tenants(id),
  runbook_id  uuid NOT NULL REFERENCES runbooks(id),
  version     integer NOT NULL,               -- every edit makes a new one (BR-RBS-038)
  definition  jsonb NOT NULL,                 -- the whole declared object: parameters, steps, guards,
                                              --   gate, cap, requires, ports
  changed_by  uuid,                           -- ⚠ reviewed cross-module FK runbooks -> identity (r24)
  changed_at  timestamptz NOT NULL,
  created_at  timestamptz NOT NULL,
  updated_at  timestamptz NOT NULL,
  UNIQUE (tenant_id, runbook_id, version)     -- a run stores the version it used, so a later edit
);                                            --   never rewrites history (TC-RBS-13)
-- ⚠ `money` AND `percent` PARAMETERS LIVE INSIDE `definition`, WHERE NO COLUMN TYPE HOLDS THEM TO
-- 4 AND 6 DECIMALS. The precision is the parameter renderer's and the validator's; a float written
-- into that document is a hard-rule-2 breach no database constraint can see (03-field-map.md D-3).
-- Named here so no build lane assumes the database is enforcing it.

CREATE TABLE runbook_runs (                   -- one row per run
  id                 uuid PRIMARY KEY,
  tenant_id          uuid NOT NULL REFERENCES tenants(id),
  runbook_id         uuid NOT NULL REFERENCES runbooks(id),
  version            integer NOT NULL,        -- PINNED at start, never re-read (BR-RBS-038, TC-RBS-13)
  mode               text NOT NULL,           -- dry | live — ONE code path; the writer is bound or it is not
  trigger            text NOT NULL,           -- manual | schedule | event, as it actually fired
  event_ref          text,                    -- the landed batch that started it
  parent_run_id      uuid REFERENCES runbook_runs(id),  -- a required Check's run, from its caller (BR-RBS-027)
  status             text NOT NULL,           -- queued|running|awaiting_approval|approved|acting|done|failed|stopped
  scope_fingerprint  text,                    -- the PINNED id list, frozen at start (BR-RBS-009)
  counts             jsonb NOT NULL DEFAULT '{}',  -- per-outcome counts, including outcomes with no record row
  report             jsonb NOT NULL DEFAULT '[]',  -- the block list as composed when the run CLOSED, frozen
  started_at         timestamptz,
  finished_at        timestamptz,
  approved_by        uuid,                    -- ⚠ reviewed cross-module FK runbooks -> identity (r24)
  approved_count     integer,                 -- must MATCH the current plan or the approval conflicts
  stopped_by         uuid,                    -- ⚠ reviewed cross-module FK runbooks -> identity (r24)
  created_at         timestamptz NOT NULL,
  updated_at         timestamptz NOT NULL
);
-- NOT PARTITIONED, and unlike `integration_run` that is not an oversight: this table takes one row
-- per RUN, not per attempt. The per-record volume lives in `runbook_run_records`. A tenant at the
-- top of the ICP (40,000 accounts) running nineteen scheduled runbooks daily writes ~7,000 rows a
-- year. Revisit if a tenant ever schedules per-minute runs; nothing in the catalogue does.

CREATE TABLE runbook_run_records (            -- one row per record examined: THE PLAN, THEN THE OUTCOME
  id               uuid PRIMARY KEY,
  tenant_id        uuid NOT NULL REFERENCES tenants(id),
  run_id           uuid NOT NULL REFERENCES runbook_runs(id),
  subject_type     text NOT NULL,             -- the twelve subjects
  subject_id       uuid,                      -- ⚠ THE ID OF ANOTHER MODULE'S ROW, READ THROUGH A SEAM.
                                              --   DELIBERATELY NOT A FOREIGN KEY — see r24
  planned_action   text NOT NULL,             -- written at evaluation, BEFORE any act; a Check's finding
                                              --   is a record whose planned action is `report` (BR-RBS-004)
  decided_by_rule  text,                      -- the rule that decided it, in words a clerk can read
  outcome          text,                      -- written AFTER the act; plan and outcome share one row
  reason           text,                      -- plain language, no rule id on screen (B14 rule 32)
  fix_route        text,                      -- a failure with NO ROUTE is a defect in the runbook (BR-RBS-011)
  decision         text,                      -- a row decision, performed through the owning module's port
  decided_by       uuid,                      -- ⚠ reviewed cross-module FK runbooks -> identity (r24)
  decided_at       timestamptz,
  amount           NUMERIC(18,4),             -- stored 4, displayed 2 (hard rule 2)
  currency         CHAR(3),                   -- ⚠ ADDED HERE — the field map's D-2 gap, closed. See r24
  data             jsonb NOT NULL DEFAULT '{}',   -- the per-record extras a block needs
  idempotency_key  text NOT NULL,             -- ⚠ HOW THIS IS COMPOSED IS UNRESOLVED: DEF-RBS-4246,
                                              --   OQ-RBS-1737. BR-RBS-008 says "runbook + run +
                                              --   record + action kind"; three other statements need
                                              --   the RUN out of it (248 notices, not 496). The
                                              --   INDEX below is correct under every candidate
                                              --   answer, so it is laid now; the composition is
                                              --   wave L's, with the ladder in front of it.
  created_at       timestamptz NOT NULL,
  updated_at       timestamptz NOT NULL,
  UNIQUE (tenant_id, idempotency_key)         -- ⚠ THIS INDEX IS WHAT MAKES A RETRY SAFE (hard rule 6)
);
-- Worked, from the fixture: running the collections ladder twice queues 248 notices IN TOTAL, not
-- 496; the second Done screen reads 0 queued and names the 248 already sent. TC-RBS-4 goes red with
-- the key removed. ⚠ A UNIQUE INDEX AND NOT APPLICATION CODE ON PURPOSE — a retry arrives
-- concurrently, and two workers each finding no row and each writing one is exactly the race an
-- index refuses and a SELECT-then-INSERT does not.
-- ⚠ A VOLUME RUNBOOK DOES NOT WRITE A ROW PER SUBJECT (BR-RBS-035): a record row for anything acted
-- on or flagged, and a count per outcome in runbook_runs.counts for the rest. Read validation over
-- 80,000 meter-days writes 38 record rows — 31 estimated, 7 queued — and a count of 80,000.

CREATE TABLE work_items (                     -- everything waiting on a person, WHATEVER raised it
  id             uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  source_kind    text NOT NULL,               -- a Check's finding | an Action's exception | a cutover human task
  source_run_id  uuid REFERENCES runbook_runs(id),  -- provenance; NULL for a human task
  fingerprint    text NOT NULL,               -- UPSERTED by fingerprint (BR-RBS-017)
  title          text NOT NULL,
  weight         integer NOT NULL DEFAULT 0,  -- how the list orders itself
  subject_ref    text,
  fix_route      text,
  owner_user_id  uuid,                        -- ⚠ reviewed cross-module FK runbooks -> identity (r24)
  due_on         date,
  status         text NOT NULL,
  resolved_at    timestamptz,
  created_at     timestamptz NOT NULL,        -- the AGE a clerk sees is this, not the last sighting
  updated_at     timestamptz NOT NULL,
  UNIQUE (tenant_id, fingerprint)             -- what the upsert needs
);
-- THE DAILY PRE-BILL SWEEP RAISES THE SAME MISSING READ FOR THIRTY DAYS; THAT MUST BE ONE ITEM
-- AGEING, NOT THIRTY ITEMS. TC-RBS-10 goes red on an INSERT instead of an upsert.
-- ⚠ THE ENGINE WRITES THIS TABLE, NEVER A RUNBOOK. A Check produces findings; the engine upserts
-- them when the run closes. That is how a Check populates the work list WHILE BEING CONSTRUCTED
-- WITH NO WRITER AT ALL (BR-RBS-002 / BR-RBS-022) — and it is why `raise_work_item` is NOT one of
-- the thirteen ports.
-- ⚠ A NAME THAT READS LIKE A COLLISION AND IS NOT ONE (03-field-map.md D-4): the `work` module owns
-- crews, technicians, parts and WORK ORDERS. `work_items` is THIS module's table — findings,
-- exceptions and human tasks on one surface. No `work_items` table exists anywhere else in the
-- product (grepped 2026-09-06: one unrelated dict key, metering/sample_data.py).

CREATE TABLE cutover_plans (                  -- a go-live plan, one per cutover
  id         uuid PRIMARY KEY,
  tenant_id  uuid NOT NULL REFERENCES tenants(id),
  name       text NOT NULL,
  go_live_on date,
  status     text NOT NULL,                   -- open|closed is what ORDERS the library (BR-RBS-026)
  closed_at  timestamptz,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE TABLE cutover_plan_items (             -- the plan's tasks, some backed by a runbook
  id           uuid PRIMARY KEY,
  tenant_id    uuid NOT NULL REFERENCES tenants(id),
  plan_id      uuid NOT NULL REFERENCES cutover_plans(id),
  seq          integer NOT NULL,              -- PATCH /cutover-plans/{id}/items/{seq} addresses it
  title        text NOT NULL,
  owner        text,                          -- ⚠ text, NOT a user reference — r24 departure 3
  due_on       date,
  runbook_key  text,                          -- ⚠ A NULL KEY IS A HUMAN TASK THE ENGINE NEVER PERFORMS
  last_run_id  uuid REFERENCES runbook_runs(id),
  evidence_ref text,                          -- "Evidence attached · $1,204.05 variance"
  status       text NOT NULL,                 -- goes green on a zero-variance re-run
  created_at   timestamptz NOT NULL,
  updated_at   timestamptz NOT NULL,
  UNIQUE (tenant_id, plan_id, seq)
);
```

---

## 3. RLS policy block (every tenant-scoped table)

```sql
-- Apply to EACH tenant-scoped table. Template shown once; repeat per table.
ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <t> FORCE ROW LEVEL SECURITY;    -- applies even to table owner
CREATE POLICY <t>_tenant_isolation ON <t>
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

⚠ **THE `NULLIF` IS LOAD-BEARING, AND THIS TEMPLATE CARRIED THE RAW CAST UNTIL
2026-09-29 WHILE THE SAME DOCUMENT SAID OTHERWISE (`DEF-GOV-7821`).** It read
`current_setting('app.tenant_id')::uuid`. With the setting UNSET or cleared
that returns `''`, the cast raises `DataError: invalid input syntax for type
uuid: ""`, and the policy **ERRORS instead of DENYING** — the caller gets a 500
where `IS-7` promises an empty result. No row crosses a tenant boundary and it
is still a leak: a 500 is an oracle that says a policy was reached at all, and
distinguishes *no tenant context* from *no such row*. `NULLIF(…, '')` makes the
empty string NULL, `tenant_id = NULL` is NULL, and a policy evaluating to NULL
admits nothing — **the guarantee is identical and the cast can no longer
raise.** `DEF-622` / `DEF-639` ruled this form and §7 of this document has
stated it since; only this block was left behind.

⚠ **THE COST WAS PAID BY THE PEOPLE WHO FOLLOWED THE RULES.** `customers/0073`
says in its own docstring that it applied *"the SIGNED B2 §3 policy template
VERBATIM"* — and it did, which is how `account_attribute_history` shipped on
2026-09-26 with a policy that errors. Every sibling that got it right did so by
patching the template privately: see `metering/0034`'s comment, *"B2 §3 template
with DEF-639's cast repair"*. **A template that nine files each correct locally
is a template that is wrong**, and the correction belongs here rather than in a
tenth docstring. It was invisible for two more reasons worth naming: `audit/0005`
sweeps every policy carrying the old predicate WHEN IT RUNS, so a table created
afterwards is never rewritten; and `G5`, which asserts the class, had never run
on a developer machine at all (`DEF-GOV-7813`).
Tables to apply to: `subscriptions, tenant_services, tenant_memberships, premises, units, routes, cycles, service_points, meters, read_schedules, meter_reads, accounts, contacts, addresses, service_agreements, tariffs, tariff_versions, rate_tiers, time_of_use_windows, charges, taxes, bill_runs, invoices, invoice_lines, adjustments, credit_notes, payment_methods, payments, allocations, refunds, payment_plans, payment_plan_installments, deposit_batches, bank_lines, ledger_accounts, journal_entries, journal_lines, notification_templates, notifications, audit_log, integration_connection, integration_credential, integration_run, integration_target_reference, integration_consent` (the last five added 2026-09-03, `CR-069`; `integrations/0002_rls_force`)`, runbooks, runbook_versions, runbook_runs, runbook_run_records, work_items, cutover_plans, cutover_plan_items` (the last seven added 2026-09-06, `CR-075`; `runbooks/0002_rls_force`)`, implementation_orders, tenant_addons` (the last two added 2026-09-07, `DEF-TEN-4446`; `tenancy/0042_rls_def_ten_4446_commercial_tables`)`, integration_rate_limit` (added 2026-09-16, `CR-110-BRC04`). ⚠ **THAT LAST ONE'S POLICY IS IN `integrations/0009`, THE SAME MIGRATION THAT CREATES THE TABLE**, and not in `integrations/0002_rls_force` — a tenant table that exists for even one migration without a policy is hard rule 1 with a window in it, and `0002` is a record of what was done on 2026-09-03 rather than a list to keep appending to. ⚠ **THOSE TWO ARE A CORRECTION, NOT AN EXTENSION.** They were built on 2026-09-02 with no policy, and `tenancy/0021` explained that at length on the grounds that *"`subscriptions` establishes that precedent"*. `subscriptions` is the FIRST name on this list and has always been, so the precedent said the opposite; the list below never exempted either table. Nothing here was reversed — a signed rule was read through a sibling migration's summary of it instead of being read.
**No RLS** (platform): `plans, tenants, roles, permissions, role_permissions, users, sso_links, tax_jurisdictions, platform_number_series` (the last added 2026-09-07, `DEF-TEN-4446`; `tenancy/0041`)`, integration_key_directory` (added 2026-09-16, `CR-110-BRC04` phase 2 / `DEF-INT-5546`; `integrations/0011`). ⚠ **THE TEST FOR THIS LIST IS A COLUMN, NOT A CATEGORY: a table belongs here when it has NO `tenant_id`.** `platform_number_series` holds the next number in Bynry's own `IMPL-` series and has no tenant column, so the policy template would fail loudly at `CREATE POLICY` and the G5 sweep — which asks for a policy on every table that HAS a `tenant_id` — never sees it. A table that carries a `tenant_id` is tenant-scoped however platform-ish its subject sounds, which is exactly what `DEF-TEN-4446` cost. (`tenants` filtered by membership in app layer; `users` are global identities joined to tenants via `tenant_memberships`.)

⚠ **AND THAT SENTENCE IS ONE OF TWO TESTS, NOT THE ONLY ONE — `sessions` HAS ALWAYS DISPROVED IT AND NOBODY SAID SO (amended 2026-09-16, `DEF-INT-5546`).** `sessions` carries a `tenant_id` (`identity.Session.tenant`, `db_column="tenant_id"`), has carried one since W0, and has been on `isolation_helpers.RLS_EXEMPT_TABLES` for just as long. It is not an oversight and it is not the `DEF-TEN-4446` mistake: it is **the second reason a table belongs on this list — it is the table that ANSWERS *which utility is this*, so a policy on it could only ever be checked against an answer it has not given yet.** `/api/jobs/{id}` carries no utility segment; `core.tenancy.adopt_session_tenant` reads the session row and opens the utility it names, and under a policy that read would return zero rows for a valid cookie exactly as for an invented one.

`integration_key_directory` is the same class and is added for the same reason. The partner surface moved to `/api/partner/v1/…` by PO ruling of 2026-09-16 — *"we agreed not to use utility names in partner apis that was our rule … we will resolve utility name using keys"* — so a partner request arrives carrying a key and nothing else, and this table maps that key's one-way fingerprint to the utility we issued it for. It holds three opaque ids and a digest: no secret, no name, no money.

**THE TWO TESTS, SO A LATER LANE DOES NOT HAVE TO INFER THEM:** a table belongs on this list when **(1)** it has no `tenant_id` at all, or **(2)** its whole job is to RESOLVE the tenant, so it must be readable before `app.tenant_id` is set. Class (2) is exactly two tables and both are in this paragraph; adding a third is a decision, not a convenience, and the questions to answer are what it would disclose if read in full and whether it AUTHORISES anything. Neither of these two does: every guard runs afterwards, against tenant tables, under the context the lookup opened. `DEF-TEN-4446`'s mistake was a table that merely SOUNDED platform-ish; the distinction is that these two are read at a moment when no policy could be evaluated at all.

⚠ **A THIRD CLASS-(2) TABLE, ADDED 2026-10-24 AS THAT DECISION (`DEF-FLD-10580`, beta MQ-006; `identity/0016`): `activation_code_register`.** PO, verbatim: *"A. The code from the office sets the utility (recommended) - this is correct option , but how will you ensure the code is always unique?"* The field app is one build for every utility, so a new handset knows only the six-character code the office gave the technician, and `POST /api/auth/activation/lookup` must find which utility holds it before any utility is open. **The two questions, answered:** read in full it discloses a COUNT of codes ever issued per utility — each row is an HMAC digest under the server secret, a tenant id and a timestamp; no code, no user, no name, no email. **It authorises nothing:** the lookup then reads that utility's own `activation_codes` row under its RLS context and answers only for a live code, and every later call is on `/api/{tenant}/…`, resolved from the PATH as always. Its UNIQUE constraint on the digest is the guarantee that no two utilities ever hold the same code, and rows are never deleted, so a code is never reused.

**Immutability + ledger triggers (concept):**
```sql
-- Block UPDATE/DELETE on issued financial rows.
CREATE OR REPLACE FUNCTION forbid_mutation_when_issued() RETURNS trigger AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'financial records are append-only'; END IF;
  IF OLD.status <> 'draft' THEN RAISE EXCEPTION 'issued record is immutable; post a correction'; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER invoices_immutable BEFORE UPDATE OR DELETE ON invoices
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation_when_issued();
-- invoice_lines, payments (status<>'processing'), journal_entries, journal_lines: append-only (block UPDATE/DELETE outright).

-- Balanced journal entry: debits = credits.
CREATE OR REPLACE FUNCTION assert_balanced() RETURNS trigger AS $$
DECLARE d numeric; c numeric;
BEGIN
  SELECT coalesce(sum(amount) FILTER (WHERE side='debit'),0),
         coalesce(sum(amount) FILTER (WHERE side='credit'),0)
    INTO d,c FROM journal_lines WHERE journal_entry_id = NEW.journal_entry_id;
  IF d <> c THEN RAISE EXCEPTION 'journal entry % unbalanced: debit % <> credit %', NEW.journal_entry_id,d,c; END IF;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER journal_balanced AFTER INSERT ON journal_lines
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION assert_balanced();
```

---

## 4. Index list (index → query it serves)

Every FK is indexed (omitted individually below); tenant-scoped indexes lead with `tenant_id`.
```sql
CREATE INDEX ix_meter_reads_acct_period ON meter_reads (tenant_id, account_id, read_at);   -- reads by account/period
CREATE INDEX ix_invoice_lines_acct_period ON invoice_lines (tenant_id, account_id, period_start); -- required composite
CREATE INDEX ix_invoices_status ON invoices (tenant_id, status);                            -- Bills tab filters
CREATE INDEX ix_invoices_unpaid ON invoices (tenant_id, due_date)
  WHERE status IN ('issued');                                                               -- unpaid/overdue (partial)
CREATE INDEX ix_reads_unrated ON meter_reads (tenant_id, read_at)
  WHERE status IN ('ok','estimated');                                                       -- billing run pickup (partial)
CREATE INDEX ix_payments_acct ON payments (tenant_id, account_id, received_at);             -- account payment history
CREATE INDEX ix_payments_status ON payments (tenant_id, status);                            -- Payments tabs
CREATE UNIQUE INDEX ux_accounts_no ON accounts (tenant_id, account_no);                     -- account# unique per tenant
CREATE INDEX ix_ar_outstanding ON accounts (tenant_id, balance DESC)
  WHERE balance > 0;                                                                        -- Outstandings high→low (partial)
CREATE INDEX ix_tariff_versions_lookup ON tariff_versions (tenant_id, tariff_id, effective_from, effective_to); -- reprice by service_date
CREATE INDEX ix_allocations_invoice ON allocations (tenant_id, invoice_id);                 -- payment application
CREATE INDEX ix_deposit_batches_status ON deposit_batches (tenant_id, status);              -- unmatched batches
CREATE INDEX ix_audit_entity ON audit_log (tenant_id, entity_type, entity_id, created_at);  -- audit lookups
```

---

## 5. Partitioning

- **`meter_reads`** — monthly range on `read_at`. Pre-create 3 months ahead via scheduled job; retention RESOLVED: 2yr hot → automatic cold-storage detach, 7yr total (BR-MET-055, NFR-6). Attach detached old partitions to cold storage.
- **`audit_log`** — monthly range on `created_at`; retention RESOLVED: 2yr hot, 7yr total, auto-archival (NFR-28, BR-AUD-012).
- **`integration_run`** — **yearly** range on `started_at` (added 2026-09-03, `CR-069` / `BR-INT-039`; `core/partitioning.py` registry, create-ahead 1). Not financial; never pruned by this module. Rationale in Addendum r22.
- **Watch past ~50M rows (do not partition now):** `invoice_lines`, `journal_lines`, `allocations`, `notifications`. Candidate key: `period_start`/`created_at`.

---

## 6. Open Questions (ranked)

**Blocking**
- O-1 `uuidv7()` availability on target Postgres 16 (extension vs shim).
- O-2 Rating math: meter multiplier order vs tiering; TOU/demand config depth; rounding at tier boundaries.
- O-3 Billed consumption units per service (kgal vs gallons; register vs billed).
- O-4 Financial model specifics: are credits/adjustments stored signed on `payments.amount` or separate tables only? Void = reversing entry (assumed) — confirm. Polymorphic `journal_entries.source_id` integrity approach.
- O-Blocking `meter_reads` / `audit_log` retention windows (regulatory).

**Important**
- O-5 Are roles tenant-customizable (→ move `roles` tenant-scoped) or platform-fixed?
- O-8 Payment-plan and O-9 subscription status value sets.
- O-9 Which fees are real constants (NSF $30, reconnect $45) vs samples.
- O-12 `tax_jurisdictions` global vs tenant-entered.
- O-13 SSO providers in scope (drives `sso_links`).
- O-14 Full chart of accounts and `credit_tier` enum.
- PII encryption approach (bank details, tax IDs, DOB, contact) — column-level (pgcrypto) vs app-layer vs disk.

**Deferrable**
- Timezone display policy (storage is UTC regardless).
- Additional currencies beyond USD/CAD.
- Pagination page sizes / default sorts (app concern).
- Notification template variable catalog.

---
*Schema derived from design only. Every `UNKNOWN` must be resolved before production migration. Migration order = section 2 top-to-bottom (platform → tenancy → identity → metering → customers → rating → billing → payments → ledger → notifications → audit); create partitions and RLS after each table, indexes and triggers last.*


## Post-design confirmations r2 (2026-08-07) — Finance additions
- **Refunds** (outbound): `refunds` table already in B2 (payments module) — ensure it carries method (check/ach), reference/check_no, reason, and a status (issued|cleared|void); user-entered.
- **Manual journal entries / accruals**: use existing `journal_entries` + `journal_lines`; add an entry `type` (standard|accrual|reversing) and keep the balanced-pair trigger.
- **By-premises reporting**: no multi-entity/tenant change. Reports and account ledger filter by `premises_id` (join invoices/lines/reads → units → premises). Add indexes `(tenant_id, premises_id, period_start)` on invoice_lines and `(tenant_id, premises_id)` on accounts' unit path as needed.
- **Account ledger**: derived view over invoices + payments + adjustments + refunds for an account and date range with running balance; premises filter via the account's unit→premises.


## Post-design confirmations r4 (2026-08-07) — Assets
- Generalize metering into an **assets** table (supersedes bare meters): add type, read_method, manufacturer, model, retire_date, status enum (inventory|active|needs_repair|in_repair|retired), parent_asset_id, net_metering bool. Keep tenant_id + RLS.
- Add **asset_assignments** (asset↔unit history) and **asset_maintenance** (lifecycle/work-order log). Both tenant-scoped, indexed `(tenant_id, asset_id)`.
- meter_reads for net meters carry import + export quantities.
- Retire, don't delete, when referenced (soft lifecycle, not deleted_at for financial linkage).

---

## Addendum r5 — Plans & Rates bundle (PO-approved 2026-08-08, Lane C batch #1)

> **Approval nature:** the Product Owner approved the BUSINESS LOGIC these tables encode (per Q&A rounds 1–8); technical soundness review is owed by the Eng Lead before migration authoring (migrations remain human-owned). Pre-migration changes are cheap and expected; post-go-live changes follow additive-only discipline.

### New tables (15)
1. **services** — platform catalog, 10 PO-confirmed services (electric, water, gas, sewer, trash, storm_water, solar, broadband, thermal_heat, battery); code/name/default_uom/color/sort/active. Replaces closed enum; tenant_services holds enablement. [BR-RAT-024]
2. **rate_seasons** — tenant, tariff_version_id, label, start/end month+day. Seasonal price sets inside a schedule. [D3, BR-RAT-021]
3. **holiday_calendars** — tenant, holiday_date UNIQUE per tenant, label; holidays bill off-peak. [BR-RAT-021]
4. **capacity_rates** — tariff_version_id, unit_label (TENANT-DEFINED), rate_per_unit NUMERIC(18,6), currency. [BR-RAT-018/019/022]
5. **account_capacities** — account, service, units NUMERIC(18,6) ≥0, effective_from/to. [BR-CUS-012]
6. **plan_services** — plan × service UNIQUE; base_charge, currency, minimum_amount NULL (per-service minimum, mode A). Plan total base = SUM, derived never stored. [BR-RAT-012/027/028]
7. **plan_rate_schedules** — plan × service UNIQUE → tariff_id (enforces one active schedule per service). [D2]
8. **plan_deposit_rules** — plan × account_type UNIQUE → fixed amount. [BR-RAT-020/023]
9. **plan_charge_rules** — plan × charge UNIQUE; amount_override NULL=catalog default; recurrence once|recurring|event; taxable. [D7]
10. **plan_penalty_rules** — plan UNIQUE; late_fee_min/pct, grace_days, grace_mode — every NULL falls back to tenant default. [D6, BR-BIL-008]
11. **plan_tax_rules** — plan × tenant-entered jurisdiction UNIQUE; rate_override NULL=jurisdiction rate; account tax_exempt still zeroes (B4.2). [D8, BR-TEN-037]
12. **account_types** ⚠ **NO LONGER PLATFORM — PO ruling 2026-09-17, verbatim *"utility can get their own account types"* (`BR-CUS-1079`), which supersedes this line's *platform-seeded* half and `BR-CUS-094` with it.** It is **seeded, tenant-defined and RLS-scoped** exactly like its neighbour: `tenant_id` NOT NULL, `ENABLE`+`FORCE` with the §3 policy on both halves, and a **per-tenant** case-insensitive unique code (`customers.0054`/`0055`). The seed is `BR-CUS-094`'s seven — residential/commercial/industrial/agricultural/institutional/municipal/builder_developer — plus `government` marked `legacy`; this line's original four are history. + **account_subtypes** (tenant-defined, RLS), whose parent FK is now a tenant-row → tenant-row link. [D5]
13. **unit_plan_assignments** — unit, plan_id + plan_version SNAPSHOT, assigned_from/to, source (new_connection|move_in|change_plan|bulk_update), actor, reason. APPEND-ONLY; ledger reads this. [BR-CUS-010/011/013]
14. **rate_change_batches** + **rate_change_log** — entity before/after jsonb, reason NOT NULL, actor; APPEND-ONLY compliance trail; batch = bulk updates. [D9]
15. **read_validation_settings** — tenant UNIQUE; high_pct 200, high_abs_kwh 50, high_abs_kgal 1, low_pct 25, days 25–35 flag / 20–45 hard, est_method trailing_3_daily_avg, est_max_consecutive 2 — PO-ratified values as SEEDED DEFAULTS, tenant-editable. [PO R6]

### Modifications (6)
16. tariff_model enum += 'seasonal', 'capacity' → flat|tiered|time_of_use|demand|seasonal|capacity. [D3, BR-RAT-019]
17. time_of_use_windows += season_id NULL, day_type weekday|weekend|holiday DEFAULT weekday. [BR-RAT-021 Option B]
18. plans += minimum_bill_amount NULL (plan floor, mode B), version int DEFAULT 1, status draft|published|archived. Combination: per-service minimums first, then plan floor tops up. [BR-RAT-028]
19. accounts += account_type_id, account_subtype_id NULL. [BR-CUS-012]
20. Enum→lookup migration (payment methods, account statuses, meter/asset types & statuses): tenant-scoped lookup tables (code,label,is_system,active), seeded from enum values; is_system deactivatable never deletable; enum columns swap per-module at build waves — no big-bang. [BR-TEN-036]
21. B10 platform tables: PROVISION ONLY — no processor columns (no stripe_*); generic payment_reference text. [OQ-015 as modified, PO R8]

RLS FORCE on every tenant-scoped table above; platform tables (services, ~~account_types~~, B10 set) excluded per B2 §3 pattern. ⚠ **`account_types` LEFT THAT EXCLUSION ON 2026-09-17** (PO: *"utility can get their own account types"*, `BR-CUS-1079`) and carries `ENABLE`+`FORCE` with the §3 policy on both `USING` and `WITH CHECK` — `customers.0055`. `customers.0002`'s own comment anticipated the day in as many words: *"account_types grew a tenant_id — it now NEEDS an RLS policy"*. **`services` and the B10 set are untouched and are still excluded.**

## Addendum r6 — Schema corrections batch #2 (PO-approved 2026-08-08)

**r6.0 · NAMING (PO ruling: "give different names — don't confuse human developers"):**
- Platform SKU table `plans` → **`subscription_plans`** (Starter/Growth/Scale; B10 `subscriptions` references this).
- Utility rate-plan bundle = **`rate_plans`** (NEW, tenant-scoped + RLS): id, tenant_id, code (UNIQUE per tenant, case-insensitive), name, description, account_type_id targeting (+ optional subtype), status draft|published|archived, version, effective_from/to, available_for_new_signup boolean, minimum_bill_amount (plan-floor, mode B), timestamps.
- Every r5 `plan_*` table FKs → `rate_plans(id)`, column renamed **`rate_plan_id`** for unambiguity. r5 #18's ALTERs on "plans" re-target `rate_plans`.

**r6.1 · Percent-of-service model** [BR-RAT-015]: `tariff_model` += `percent_of_service`; `tariff_versions` += `percent numeric(18,6)`, `basis_service_id` (e.g., sewer = 35% of water usage-charge $).

**r6.2 · Demand config** [BR-RAT-014]: NEW `demand_rate_config` — tariff_version_id, energy_rate_per_kwh, demand_rate_per_kw, peak_window (label/start/end), `ratchet_enabled boolean DEFAULT false`, ratchet_pct NULL. RLS.

**r6.3 · GL per plan service** [S10]: `plan_services` += `gl_account_id → ledger_accounts`.

**r6.4 · UoM gate** [PO R6, OQ-004]: `tenant_services` += `billed_uom`, `conversion_factor numeric(18,6)` (register→billed). Mismatch without factor → block rating + user message.

**r6.5 · Taxes completion** [S13/S41]: `taxes` += kind percent|flat|per_unit, percent, flat_amount + flat_frequency per_bill|per_service, per_unit_amount + per_unit_uom, **applies_above_units NULL — MARGINAL: only units ABOVE the threshold are taxed (PO OQ-054 option a)**, applies_to services[], liability_gl_account_id, filing_frequency, filing_form, effective_from/to. `tax_jurisdictions` += tenant_id → **tenant-scoped + RLS** (BR-TEN-037; supersedes the platform-global note in §1).

**r6.6 · Charges completion** [S12]: `charges` += charge_type one_time|recurring|penalty, service_id NULL (scope), max_amount NULL, taxable_default, auto_apply, waivable, separate_line. **Amount rules (PO OQ-053): flat | percent | percent_with_minimum — "Formula" ships visible-but-disabled** (`amount_rule` enum reserves the value).

**r6.7 · Misc** [agent findings #8]: `rate_tiers` += season_id NULL (seasonal tier sets); `rate_change_batches` += change_spec jsonb (bulk parameters).

## Addendum r7 — Read-type model (PO-directed 2026-08-08, R4-A6)
`meter_reads` += `read_type` enum `consumption | export` NOT NULL DEFAULT 'consumption'. Net-meter cycles produce two records (consumption + export, same read_at). REPLACES the r5-era proposal of import_qty/export_qty columns on one row (never migrated — documentation-only change). Rating consumes both record types via the service interface; uniqueness: (asset, read_at, read_type).

## Addendum r8 — Read channel model (PO RD-1 Option B, 2026-08-08)
`meter_reads.read_type` (r7) GENERALIZES to **`channel`**: enum `total | tou_on | tou_mid | tou_off | export | demand` (extensible). One record per register per date; UNIQUE (asset, read_at, channel). Flat meters use `total` only. Supersede lifecycle (BR-MET-053): += `superseded_by_id uuid NULL` (self-ref), `superseded_at`; committed rows never UPDATE except these two closure columns; billed lock enforced at service layer + J6 linkage. Estimation per channel (BR-MET-058). Auto-archival job: monthly partitions older than 2 years detach to cold storage (BR-MET-055), scheduled, audited.

## Addendum r9 — Accounts schema batch #3 (PO-approved 2026-08-08)
1. `customers` (kind person|company, display_name, external_ref UNIQUE per tenant) + `customer_accounts` N:M link [BR-CUS-054]; contacts re-homing = Eng-Lead disposition.
2. `account_opening_buckets` (account, as_of, bucket enum current|d31_60|d61_90|d90_plus, amount NUMERIC(18,6), import batch; append-only, RLS FORCE) [BR-CUS-048].
3. Opening-JE support: `journal_entries.source_type` += 'opening_balance'; seeded chart rows "Accounts receivable" + "Opening balance clearing"; handoff shape (view vs thin table) = Eng-Lead [BR-CUS-049].
4. Import staging: `account_import_batches` + `account_import_rows` + `account_import_value_maps` (per-batch immutable source→target maps) [BR-CUS-051/052].
5. `accounts.deposit_received_on`; tenant setting `deposit_interest_rate_annual` NUMERIC DEFAULT 0 (S66) [BR-CUS-050/057].
6. `credit_tier_rules` (12-mo window, 0/1–2/3+ late thresholds, tenant-configurable); `accounts.credit_tier` = computed cache [BR-CUS-058].
7. Account-status lookup seed incl. Vacation hold/Suspended + `behavior_class` column; seed mapping per OQ-064 closure (Pending=non_billable, Active=billable, Marked disconnect=billable, Hold/Suspended=billable_base_only, Closed=terminal) [BR-CUS-055].
8. Enum extensions: plan-assignment `source` += 'import'; `deposit_election` += 'imported'. Opening CREDIT rows → account credit per BR-CUS-061 (no negative buckets).

## Addendum r10 — Billing schema batch #4 (PO-approved 2026-08-08)
1. `invoice_lines` += `gl_account_id` stamped at finalization [BR-BIL-010].
2. Finance account mapping: `service_gl_map` (service → revenue GL, optional usage/base split), `tax_authority_gl_map`; AR / deposit-liability / opening-clearing / write-off designations; seeded chart (full COA = O-14, finance+Eng-Lead) [BR-BIL-010/013].
3. `invoices` += `template_id`, `template_version` pinned at issue [BR-BIL-026].
4. `bill_templates` + `bill_template_versions` (append-only; draft|published|archived; audit-locked while pinned; category assignment) [BR-BIL-025/027].
5. `account_budget_status` (level, variance balance, last_leveled_at, settle_up_month, level_override + reason ±30%) + tenant budget settings [BR-BIL-017, OQ-068].
6. Tenant billing settings rows: overcharge_guardrail_pct, correction approval config, bill messages/footer [BR-BIL-021/029].
7. `bill_runs` += formalized status lifecycle, `parent_run_id` + scope (catch-up sub-runs), `bill_run_exclusions` (account, reason, who/when) [BR-BIL-015/023].
8. Outbound delivery queue: one row per bill × channel; status queued|sent|delivered|failed|bounced; batch id; provider response [BR-BIL-016].
9. Correction workflow: `correction_cases` (reason code, scope single|bulk, status, approver, links to credit_notes/rebills) + bulk runs w/ per-bill results [BR-BIL-014].
10. Balance transfer transaction final→master account (balanced, audited) + master-account designation via landlord-agreement link [BR-BIL-013, OQ-069].
11. Write-off: tenant threshold setting + GL write-off account [BR-BIL-013, OQ-070].
12. `invoices.bill_type` enum: cycle|first|final|rebill|backbill|penalty [BR-BIL-018/019].
13. Reason-code lookups (corrections, assessed reads, penalties) = reference data, tenant-extensible.
14. Assessed-read flag on meter_reads entry path (reason-coded) [BR-BIL-019, BR-MET-053 lifecycle].
15. Idempotency, keys, exact DDL = Eng-Lead-owned 🔒 as always.

## Addendum r11 — Per-tenant identity (PO architecture ruling, 2026-08-08)
`users.email citext NOT NULL UNIQUE` (global) is SUPERSEDED: the same email may exist in different tenants as **separate users** ("I can use my email in two tenants — in that case I'm 2 different users", PO). Uniqueness becomes **(tenant_id, email)**; `users` becomes tenant-scoped (RLS like any tenant table). Sign-in is unchanged in flow: subdomain → tenant → (tenant, email) credential lookup (BR-IDN-001). Consequences: no cross-tenant SSO/shared identity v1; per-tenant password policies apply cleanly; `memberships` (tenant,user) becomes 1:1 — whether role folds onto `users` or memberships stays as a thin table = **Eng-Lead disposition 🔒**. Platform-admin (Bynry) identities are NOT tenant users and are unaffected.

## Addendum r12 — Payments schema batch #5 (PO-approved 2026-08-08, examples confirmed)
1. `payments` += **`posted_at` + `cleared_at`** — always both; billing consumes posted_at; NSF/bank-rec hang off cleared_at [BR-PAY-021].
2. `payments.purpose` enum bill|deposit|plan_down|prepay [BR-PAY-012].
3. Payment import staging: `payment_import_batches` + `payment_import_rows` (file+SHA stamp, file+tags idempotency) [BR-PAY-023].
4. Receipts ride the **platform-wide outbound queue** (see #16) [BR-PAY-024].
5. `refunds` += requested_by/approved_by/approval columns [BR-PAY-014].
6. `autopay_capture_intents` (account, invoice, amount, scheduled_on, status awaiting-rails v1) [BR-PAY-015].
7. Collection state per account (tier, last/next notice dates) + `notice_history` append-only [BR-PAY-017].
8. `accounts.bad_address` flag + delivery-return events (bulk-markable) [BR-PAY-018].
9. `payment_plans` += notice fields + `missed_count` (2 → void) [BR-PAY-016].
10. Bank statement imports + match-rule config (amount + date ±3d default, finance setting) [BR-PAY-019].
11. `write_offs` (initiated-in-payments, approved_by, bad-debt GL) [BR-PAY-020].
12. NSF fields: `accounts.nsf_count` + cash-only/no-autopay privilege flag [BR-PAY-013].
13. Numbering series: PMT- / DEP- / RCT- (tenant-adjustable) [BR-TEN-035 mechanism — now anchored].
14. Field-map anchoring items: `account_plan_assignments` (BR-CUS-029) · number_series mechanism · final-settlement record (path enum + actor + timestamp) [BR-BIL-013/D-3] · `accounts.template_override_id` [BR-BIL-025/D-4] · `account_budget_status.status` incl. off_budget [D-5] · void-approval record [D-6] · customer paperless-delivery preference [D-8].  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
15. Tenancy residuals: `tenants.checklist_state` jsonb · `tenants.ein` (app-layer encrypted per OQ-016) · `tenant_settings.lock_closed_periods`.
16. **`outbound_messages` is PLATFORM-WIDE** (BR-NOT-005): one table for email + SMS + print across ALL modules; module writers insert; ONLY the dispatcher service sends; batch size/cadence tenant-config; provider adapters (BYO mailbox, transactional ESP, Twilio) behind one seam.
17. Exact DDL, keys, dispatcher mechanics = Eng-Lead 🔒.

## Addendum r13 — Ledger/Finance schema batch #6 (PO-approved 2026-08-08)
1. `journal_lines` += dimension columns: service, account_id, premises_id, unit_id, source_type, source_id, tax_authority_id [BR-LED-001].
2. `journal_entries` += type enum standard|accrual|reversing, draft state, auto_reverse link + reversal_of link [BR-LED-003/005].
3. `tax_remittances` (authority, period, basis, amount, paid JE ref) [BR-LED-002].
4. `export_batches` (period, target QBO|Xero|CSV|IIF, idempotency, who/when, content hash) [BR-LED-004].
5. `ledger_accounts` += export-code columns (qbo_ref, xero_ref) [BR-LED-014].
6. Subledger tie-out views (deposit liability, AR, tax payable vs registers) [BR-LED-007].
7. **Seeded chart of accounts FINALIZED with finance at GT freeze — closes O-14.**
8. Exact DDL + posting-service mechanics = Eng-Lead 🔒.

## DB Decision Register & Addenda Index (PO-directed documentation, 2026-08-08)
Core schema decisions, consolidated (each already law in the DDL above / an addendum / a BR):
**DB-1** RLS FORCE every tenant table; tenant_id NOT NULL FK everywhere. **DB-2** uuidv7 PKs. **DB-3** Money NUMERIC(18,6)+CHAR(3); rounding only at finalization. **DB-4** Append-only financial tables (invoices/lines, payments, journal_entries, credit_notes, opening buckets, template versions); corrections = new rows. **DB-5** Effective-dated pricing via tariff_versions — history bills on its version, never current. **DB-6** Read channel model: one row per register per date, UNIQUE (asset, read_at, channel), supersede chains via superseded_by_id (r7→r8). **DB-7** Monthly partitions on meter_reads; automatic detach-to-cold at 2 years. **DB-8** invoice_lines carry taxable flag + STAMPED gl_account_id (r10). **DB-9** invoices carry pinned template_id+version and bill_type (r10). **DB-10** payments carry posted_at ≠ cleared_at + purpose (r12). **DB-11** journal_lines carry the dimension set: service/account/premises/unit/source/authority (r13). **DB-12** Idempotency uniques: (tenant, idempotency_key) bill runs; (tenant, webhook_key) payments; file+tags imports; export_batches. **DB-13** Per-tenant identity: users tenant-scoped, UNIQUE (tenant_id, email) (r11). **DB-14** Tenant-facing vocabularies = lookup tables, seeded + extensible, audit-locked in use (BR-TEN-036). **DB-15** PII: app-layer encryption for high-sensitivity columns; tokenized gov-ID; citext emails. **DB-16** Cross-module FKs = the reviewed interface set (§2); cross-module writes forbidden.

**Addenda map:** r5 Plans & Rates bundle (21 items; rate_plans vs subscription_plans split) · r6 corrections batch #2 · r7 read_type two-record (superseded by r8) · r8 channel model · r9 accounts batch #3 (customers entity, opening buckets, staging, deposit interest, credit tiers, status classes) · r10 billing batch #4 (GL stamp, mapping, templates, budget, sub-runs, delivery queue, transfers, write-offs, bill_type) · r11 per-tenant identity · r12 payments batch #5 (posting/clearing, purpose, staging, intents, collections, bank rec, NSF, anchoring items, tenancy residuals) · r13 ledger batch #6 (dimensions, JE types, remittances, export batches, tie-outs, COA finalization closing O-14). Exact DDL of all addenda = Eng-Lead 🔒 at migration authoring.

## Addendum r14 — Anchoring batch #7 (PO-approved 2026-08-08)
1. Tenant bank-account registry (deposit-slip + rec target). 2. Reversal-reason lookup (reference data). 3. `payment_plans.down_payment` + payment↔plan/installment link columns. 4. `payments.memo`. 5. Settings keys: collection-ladder intervals, nsf_privilege_n, suppress_paper_on_bad_address. 6. `tax_remittances` += confirmation_ref + receipt attachment (BR-LED-019). 7. `export_batches` += granularity (period|weekly) per BR-LED-017. 8. `received_at` vs posted_at/cleared_at disposition = Eng-Lead 🔒. 9. Exact DDL = Eng-Lead 🔒.

## Addendum r15 — Localization (PO LC battery, 2026-08-08)
1. Tenant settings: default_language + currency (CHAR(3), seed USD/CAD/MXN/EUR/GBP) + **currency-lock** enforcement once first financial record exists [BR-TEN-042]. 2. `accounts.preferred_language` + import-template column [BR-CUS-064]. 3. Template variants += language key; pinning tuple includes language [BR-NOT-006]. 4. Users: per-user UI language override [BR-SHL-030]. 5. Language catalog = data-driven platform asset (en, es, es-MX, de, hi seed; extensible without code) [BR-SHL-030]. 6. Exact DDL = Eng-Lead 🔒.

## Addendum r16 — DB-audit redline (B11, 2026-08-08; newest-wins over §2/§3/§5/§6 text)
1. **Partitioning:** §5:729 "do not partition now" is SUPERSEDED — NFR-24 mandatory set stands: invoice_lines + journal_lines join meter_reads/audit_log (monthly); outbound_messages is born partitioned [F-1].
2. **RLS/§3 corrections:** `users` = tenant-scoped + RLS, UNIQUE (tenant_id, email) [r11]; `tax_jurisdictions` = tenant-scoped + RLS [r6.5]. The §3 no-RLS listings for both are void [F-2].
3. **Superseded markers:** `meters` → build `assets` per r4; `meter_reads` body → build per r8 channel model + supersede chain (DB-6); `plans` → rename `subscription_plans` (r6.0); `service_agreements.tariff_id` → superseded by account_plan_assignments (BR-CUS-029); `currency_code` enum → DROP (unused; r15 seed + lock governs); `service_type` enum role → 10-service catalog table with sequenced column swap [F-4/6/8/9].  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
4. **B10 tables are PROCESSOR-FREE** — no stripe_* columns; generic payment_reference only (PO ruling) [F-6].
5. **O-marker roll-up:** CLOSED by rulings — O-2, O-3, O-5, O-9(subscription-status), O-12, O-13, O-14, O-Blocking-retention, PII-approach. REMAIN (Eng-Lead): O-1 uuidv7 mechanics · O-4 residue (polymorphic source_id integrity + signed-amount convention). **O-8 payment-plan status set PROPOSED here: proposed|active|completed|void** (derived from BR-PAY-016 lifecycle; PO/Eng nod at migration) [F-7].
6. **PM-proposed owners for the 14 ambiguous promised tables** (vetoable; module map governs): services catalog → tenancy(platform ref) · read_validation_settings → metering · account_types/subtypes + account_capacities → customers (cards hosted in Reference data) · unit_plan_assignments → rating-owned, written via customers seam [F-11b] · holiday_calendars → rating · service_gl_map/tax_authority_gl_map → ledger (surfaced by billing US-BIL-009) · delivery queue = ONE table = outbound_messages → notifications · balance-transfer + final-settlement + void-approval records → billing (posting via ledger service) · number_series → tenancy · bank-account registry → payments · language catalog → platform-shell · assets set → metering (CLAUDE.md governs; 05-assets is a DOC module of metering's tables).
7. **Cross-module interface register additions** [F-11]: outbound_messages writer-insert (ruled exception), unit_plan_assignments write seam, accounts.balance cache-update seam — all to §2's reviewed set at DDL time.
8. **Anchoring checklist**: the 18-item consolidated pre-migration punch-list (reports/integrations/audit/notifications/payments/tenancy/billing/customers/metering/assets/rating/identity/shell/ledger residues + partition set + enum swaps + B10 set + interface register) is recorded in the B11 working papers (decision log 2026-08-08) — migration authoring starts THERE, never from §2/§3 raw.

---

## Addendum r17 — tenant custom fields + the eleven-locale set (PO rulings 2026-08-10)

**Status:** PROPOSED-SCHEMA. Authored by Eng-Lead from PO rulings; lands with W2/**R2** (B12 r7). No DDL is written until the OQ rows below are answered; the migration itself is 🔒 (migration ordering) and carries a `12-governance/09-human-review-ledger.md` row.

### r17.1 · `custom_field` — the definition registry (module: tenancy)

Tenant table: `tenant_id NOT NULL`, RLS **FORCE**, uuidv7 PK (DB-1/DB-2).

| Column | Type | Notes |
|---|---|---|
| `entity` | text | one of the eight covered tables (r17.2). CHECK-constrained, not free text |
| `key` | text | `^[a-z][a-z0-9_]{1,39}$`. **UNIQUE (tenant_id, entity, key)**. Immutable after insert (BR-TEN-049) |
| `label` · `help_text` | text | tenant's own prose — deliberately NOT a `message_key`; see r17.5 |
| `data_type` | text | `text·number·date·boolean·select·multi_select` |
| `options` | jsonb | required (≥2) for the select types, else NULL |
| `is_required` · `is_active` | boolean | `is_active` false = deactivated; there is **no delete path** (BR-TEN-050) |
| `placement` | jsonb | `{"S51": "input", "S50": "view"}` — keys constrained to the US-TEN-016 eligible-slot list for that entity |
| `display_order` | int | within (tenant, entity); stable secondary by id per IS-2 |

Partial index on `(tenant_id, entity) WHERE is_active` — the registry read (BR-TEN-053) is the only hot query.
`tenant_settings += custom_field_version int NOT NULL DEFAULT 0`, bumped in the **same transaction** as any definition write; it is the cache key's version segment.

### r17.2 · `custom_data jsonb NOT NULL DEFAULT '{}'` on eight tables

`premises` · `units` · `service_points` · `assets` · `accounts` · `contacts` · `addresses` · `service_agreements`.

**Why a column on the owning row and not one shared `custom_field_value` table.** A shared value table would be written by the customers, metering *and* assets modules — a cross-module write, forbidden by DB-16/§2. A column on your own row is written only by its owning module's service. It also makes the audit free: `audit_log` already snapshots the whole row's before/after (BR-AUD-003), so a custom-value edit lands in the trail with **no new audit code**. A separate table would have needed its own path.

No GIN index ships in R2. Filtering and sorting over `custom_data` are explicitly out (BR-SHL-038) precisely so that no index decision is made before a story needs one; `DEFAULT '{}'` costs effectively nothing on rows that never use it.

**Deliberately excluded, each for a stated reason:** `tariffs`/`rate_tiers`/`charges`/`taxes` (the calculation boundary — DB-3, B4) · `invoices`/`invoice_lines`/`payments`/`journal_*` (append-only, DB-4 — they receive the r17.3 snapshot instead) · `meter_reads` (monthly-partitioned, cold-detached at 2 years per DB-7; a jsonb column there is an archival cost with no product benefit).

### r17.3 · `invoices += custom_snapshot jsonb NOT NULL DEFAULT '{}'`

Stamped at issue, **string values only**, keys namespaced `<entity>.<key>` (US-BIL-028).

This is the same move the schema already makes twice — **DB-8** stamps `gl_account_id` onto `invoice_lines` and **DB-9** pins `template_id` + version onto `invoices` — for the same reason: a later edit to master data must not reach backwards into an issued document. Reading a custom field live at render time would rewrite last January's bill from this March's data without ever issuing an UPDATE, satisfying the letter of DB-4 while breaking it in substance.

*Strings only* is the structural guarantee behind BR-TEN-048: a `number` field becomes `"1234"`, so arithmetic is impossible without an explicit parse the G6 gate can find. It also pins IS-8 formatting, so a 2029 reprint renders as the 2026 original did.

**New DB law — DB-17:** *tenant-defined data never enters a money path.* `custom_data` is a merge-blocking G6 failure anywhere under `apps/rating/`, and under `apps/billing/`, `apps/ledger/`, `apps/payments/` outside the single allowlisted `apps/billing/custom_snapshot.py`.

### r17.4 · Locale set: five → eleven

Supersedes §903 item 5 (`en, es, es-MX, de, hi`). The catalogue becomes `en-US · es-ES · es-419 · de-DE · hi-IN · fr-FR · id-ID · it-IT · ja-JP · ko-KR · pt-BR`.

**`es-MX` → `es-419` is a data migration, and it is time-sensitive.** `tenant_settings.default_language`, `accounts.preferred_language` (BR-CUS-064) and `user_preferences` all store the code. Today those columns are empty and this is a rename; once Spanish-speaking customers are onboarded it is a live migration. Do it in R2 (BR-SHL-042).

Language remains orthogonal to currency: the seed stays USD/CAD/MXN/EUR/GBP under the BR-TEN-042 currency-lock. Shipping `ja-JP` does **not** make the product ready for a JPY utility — that is a separate currency addition plus the lock rule.

### r17.5 · Two recorded consequences

1. **Tenant labels are prose, not codes.** G14/TD-16 say the server sends `message_key`s and never prose. A tenant-authored label has no key and never can — it is the tenant's own words. PO accepted this exception on 2026-08-10; it is scoped to `custom_field.label`/`help_text` and to nothing else.
2. **PII reaches immutable rows.** A tenant can define "SSN last 4"; stamping copies it into `invoices`, which are append-only and long-retained, so BR-TEN-044's day-91 deletion cannot reach it. **OQ-076**, open.

### r17.6 · Open questions blocking DDL

| OQ | Blocks |
|---|---|
| OQ-075 | the deactivate branch when a published template references the field |
| OQ-076 | the `contains_pii` exclusion filter on the r17.3 stamp |
| OQ-077 | the publish gate on machine-translated customer-facing templates |

## Addendum r18 — interface-register addition: the customers→metering read seam (CR-038 W9 task 2, 2026-08-26)

**One row added to §2's reviewed set (DB-16), review owed:**
`apps.customers.seams.reads_for_unit(unit_id, on=…)` → late-binds
`apps.metering.selectors.reads_for_unit` — **read-only**, committed lineage
heads per meter/register on the unit (quantity WITH unit, read_at, source,
lifecycle, estimation marker), superseded rows excluded, one query per unit.
Consumers: `apps/customers/move_reads.py` (`unit_reads_cell`,
`move_out_kpis`) — the READS/FINAL READ cells and the FINAL READS DUE count,
which until this row were stated absences (*"customers publishes NO metering
read seam"*). No write direction exists or is planned through this seam: event-
read WRITES stay metering-owned (BR-CUS-021) and arrive with CR-038 W9 task 1.
⚠ Review of this row is OWED at the next B2 sitting — flagged here, in the
seam's docstring, and in the CR-038 record; shipped commit `10842f1`.

## Addendum r19 — interface-register addition: the stored master-vs-subs gap (CR-038 W6 task 1, 2026-08-26)

**One table added to §2's reviewed set (DB-16), review owed:**
`premises_submeter_reconciliations` — the stored difference between a master
meter's consumption for a period and the sum of its sub-meters', which
BR-MET-125 requires be **written down and reported** rather than absorbed
(PO ruling 2026-08-26, Open 9: *"(a) store + report"*).  One row per
(premises, master asset, period), carrying the master figure, the subs total,
the gap and its unit — never a money amount, because a gap is consumption and
what it costs is the bill run's judgment.

**The cross-module edge:** `master_asset_id uuid NOT NULL REFERENCES assets(id)`
— metering→assets.  ⚠ **This is the SAME edge `meter_reads.asset_id` already
is** and therefore adds no NEW interface direction to the reviewed set; the row
exists so the set names the table, not because a new boundary was crossed.  No
write direction to assets exists or is planned: metering reads the asset row
through the seam and writes only its own table.

**RLS:** `ENABLE` + `FORCE`, with the
`NULLIF(current_setting('app.tenant_id', true), '')::uuid` form (DEF-622 /
DEF-639), in the paired migration `0034_rls_cr038_w6_submeter_reconciliation`
— the pair must be applied together, as metering 0014/0015 and 0024/0025
document.  **Not partitioned, deliberately:** the table grows with
(premises × master × month), orders of magnitude below `meter_reads` for the
utilities this product serves — **up to 40,000 accounts** (tiers T7/T6/T5), per the ICP
ruling of 2026-09-06 in `12-governance/02-decision-log.md`, *"THE ICP, CORRECTED THE SAME
HOUR"*. ⚠ **This sentence read *"the <3,000-connection utility this product serves"* until
that date.** The conclusion is unchanged and the arithmetic still holds at the new ceiling:
this table grows with (premises × master × month) while `meter_reads` grows with
(meters × reads × month), so the ratio between them does not depend on tenant size — a
13× larger tenant multiplies both sides. **Nothing here becomes a partitioning candidate
under `NFR-24`**, whose threshold is a platform-wide 50M rows/yr, and `B6`'s capacity model
already takes 40,000 accounts as its largest modelled tenant.

⚠ Review of this row is OWED at the next B2 sitting — flagged here, in
migration 0033's own docstring (which REPORTED the gap rather than writing it,
04-docs/ being outside that lane's territory), and in the CR-038 record.

## Addendum r20 — interface-register addition: the customers→metering event-read WRITE seam (CR-038 W9 task 1, 2026-08-26)

**One row added to §2's reviewed set (DB-16), review owed — and it is the FIRST
WRITE DIRECTION on this boundary**, which r18 explicitly said did not exist:
*"No write direction exists or is planned through this seam"*. That sentence was
true of `reads_for_unit`, the read seam, and is superseded here for a second
seam beside it, not amended in place.

`apps.customers.seams.commit_event_reads(actor, payload)` → late-binds
`apps.metering.services.commit_event_reads` — the ONE door through which a
move-in, move-out, transfer, disconnect or new connect commits the reading it
collected.

**⚠ Why this is not a cross-module write, which is the whole reason it is a
seam.** CLAUDE.md forbids cross-module writes outright, and a customers wizard
INSERTing a `meter_reads` row would be exactly that. It does not: customers
hands metering a payload and **metering writes its own table, through its own
service, applying its own rules** — validation, supersede chains, the
append-only law. The direction of the CALL is customers→metering; the direction
of the WRITE is metering→metering. That distinction is what the seam register
exists to record, so a later reader does not mistake the call for the write.

**The columns this seam stamps**, named here because a review row that cannot be
checked against the DDL is not a review row:

| Table | Column | Type | Values |
|---|---|---|---|
| `meter_reads` | `event_context` | `TEXT NULL` | `move_in · move_out · transfer · disconnect · new_connect` |
| `read_import_batches` | `event_context` | `TEXT NULL` | the same five |
| `accounts` | `final_read_state` | `TEXT` | `taken · due · estimated` |

`event_context` is stamped at INSERT and NULL means "not an event read" — a
different fact from any of the five, which is why there is no default. The
acting user travels with it (BR-MET-128, PO 2026-08-26: *"it will be as per
event … + plus the user"*), so an auditor asking who recorded a closing figure
gets a name rather than a batch id.

⚠ Review of this row is OWED at the next B2 sitting — flagged here, in the
seam's docstring, and in the CR-038 record.

## Addendum r21 — interface-register addition: `premises_owners.customer_id`, metering → customers (CR-039 wave C task 12, 2026-08-27)

**One row added to §2's reviewed set (DB-16), review owed.**

`premises_owners.customer_id` → `customers.customers(id)`, `NULL`, `ON DELETE`
PROTECT. It is the *"link to the customer they already are"* half of the PO's
2026-08-27 ruling (*"category is okay, no richer text"*), so the same landlord
across twelve addresses resolves to one party rather than twelve strings.

**⚠ This is a new ROW on an existing boundary, not a new boundary.**
`apps/metering/models.py` already FKs `customers.Account` twice (the read
lineage and the asset seat). The direction metering → customers is therefore
already reviewed; what is new is this column.

**It is a POINTER and never a write.** Metering reads nothing out of
`customers` through it — the resolved customer's name and number are fetched
through `apps.metering.seams`, which late-binds the customers module's own
selector, exactly as every other cross-module read in that file does. The FK
buys referential integrity and nothing else.

**NULLABLE, and the null is a stated fact rather than a gap** — the ruling's own
caveat: *"a builder holding a site before handover may not be [a customer], so
the link is optional."*

| Table | Column | Type | Values |
|---|---|---|---|
| `premises_owners` | `customer_id` | `uuid NULL` | a `customers.id` in the same tenant, or NULL — *this party is not a customer of ours* |
| `premises_owners` | `category_id` | `uuid NOT NULL` | a `premises_owner_categories.id` — tenancy-hosted, metering-owned (BR-TEN-150) |
| `premises` | `owner_id` | `uuid NULL` | a `premises_owners.id`, or NULL — *no typed owner recorded* (BR-MET-151) |

⚠ Review of this row is OWED at the next B2 sitting — flagged here, in
`metering 0040`'s own docstring, and in the CR-039 record.


## Addendum r22 — the integrations module's five tables (CR-069 wave A task A1, 2026-09-03)

**Five tables added to §2 as `### Module: integrations`, five rows added to §3's RLS list, one row
added to §5.** This is `C34` — *"anchor the five tables in the schema brief before the migration"* —
and `US-INT-014` TC-7 asserts the ordering: this commit precedes `apps/integrations/migrations/0001_initial.py`
in `git log`. The field map's discrepancy **I-2** (the module claimed tables the DDL registers never
carried) closes in the same commit.

**Two departures from the field map's §5 draft, both forced by PostgreSQL and stated here rather than
left to be inferred:**

1. **`integration_run.started_at` is `NOT NULL DEFAULT now()`**, not nullable as the draft had it. It is the
   RANGE partition key, and a NULL key routes to no partition — the same reason `core/partitioning.py`
   records for rejecting `invoice_lines.period_start`. A queued run's `started_at` is therefore the moment it
   was queued; `finished_at` stays the honest marker of completion.
2. **The primary key is `(tenant_id, started_at, id)`**, not `id` alone. PostgreSQL requires the partition
   key inside every unique constraint on a partitioned table; `audit_log` already takes exactly this shape.
   Nothing references a run row by foreign key, so the composite key costs nothing downstream.

**Two rows added to §2's reviewed cross-module FK set (DB-16), review owed at the next B2 sitting:**

| Table | Column | Type | Points at | Direction |
|---|---|---|---|---|
| `integration_connection` | `connected_by` | `uuid NULL` | `users(id)` — the System Admin who connected it | integrations → identity |
| `integration_consent` | `account_id` | `uuid NOT NULL` | `accounts(id)` — the customer account whose usage is shared | integrations → customers |

Both are POINTERS and never writes: integrations reads nothing out of identity or customers through
them, and `integration_consent` is written by nothing at all until `OQ-INT-1482` is ruled.

**What is deliberately NOT here:** no `payments.channel` / `payments.external_ref` (payments' own columns,
payments' own migration — wave N1) · no change to `ledger_accounts.qbo_ref` / `.xero_ref` (`OQ-INT-1480`) ·
no sixth status value for *Reading from us* (a computed display state — `13-integrations/08-screen-layouts.md`).


## Addendum r23 — `work_orders` may stand on something other than a build (CR-070 wave A task A1, 2026-09-03)

**One section added to §2 as `### Module: work`, and one row added to the reviewed cross-module FK set
(DB-16).** This is `CR-070` §2(a) — *"Amend the module map, dated, in the same commit as the first
migration — not before, and not after"* — and the first migration is `metering/0044_cr070_a_work_order_anchors`,
in this commit, because the table it changes is metering's (`US-WRK-001`: *"Do not write `work/0001` for a
column on a metering table"*).

**What changed, in plain terms.** Until now a work order had to belong to a new-connection build, so a leak
investigation on a meter that has been in the ground for years could not be recorded at all. `work_orders.
connection_id` is nullable from this migration; `premises_id` and `account_id` sit beside the `asset_id` that
already existed and was written by nothing; and `ck_work_orders_has_anchor` makes the DATABASE refuse an order
with none of the four. No row moved. The PostgreSQL proof is `06-backend/tests/test_us_wrk_001_anchor_check_pg.py`,
which INSERTs around the ORM and reads the constraint's name back out of the refusal.

**One row added to §2's reviewed set (DB-16), review owed at the next B2 sitting:**

| Table | Column | Type | Points at | Direction |
|---|---|---|---|---|
| `work_orders` | `account_id` | `uuid NULL` | `accounts(id)` — the account a job is FOR (a move-out's final read, a reconnect) | metering → customers (Work's third anchor; the table is metering's today) |

A POINTER and never a write: nothing in metering or work changes an account row through it. `premises_id`
is metering → metering and needs no row. `asset_id` (metering → assets) has been in the set since `0026`.

**Where the six Work tables LIVE is deliberately NOT decided here.** `16-work/03-field-map.md` §4 records
three ways to honour BR-WRK-001 and marks the choice PENDING the blueprint's §16; the lane that writes
`work/0001` decides it, and `apps/work/seams/metering_seam.py` is what makes the move a change to one
file. §3's RLS list does not name the six W6 tables (they were policied by `metering/0026` without a row here) —
reported, not corrected, because that list is a signed section and the gap predates this addendum.

## Addendum r24 — the Runbooks module's seven tables (CR-075 wave A task A1, 2026-09-06)

**Seven tables added to §2 as `### Module: runbooks`, seven table names added to §3's RLS list.**
This is the schema brief's half of `US-RBS-041`, and it lands **before** `runbooks/0001_initial.py`
in `git log` for the same reason `CR-069`'s `C34` did: *"the re-cut register begins at the
migration"*, so a table that is not in the brief when the migration is written is a table nobody
reviewed. The field map's discrepancy **D-6** (*"none of the seven is anchored in B2"* — grepped at
`6fed5da8`, zero hits for `runbook_runs`, `runbook_run_records`, `cutover_plan`, `work_items`)
closes in this commit.

**Three departures from `17-runbooks/03-field-map.md`'s draft, each forced, each stated here rather
than left to be inferred.** Two of them are gaps the field map itself recorded and handed to this
task by name.

1. **`runbooks.tags` is `jsonb NOT NULL DEFAULT '[]'`, not `text[]`.** `django.contrib.postgres`'s
   `ArrayField` has no SQLite form, and `config/settings/test.py` hardcodes in-memory SQLite
   (hard-won law 14), so a `text[]` column would make every test in this module unrunnable on the
   default suite. This is the repository's existing answer, not a new one — `apps/work/models.py`
   and `apps/portal/models.py` each record the identical substitution in their own comments. Tags
   help a search and nothing else (`BR-RBS-024`), so no query needs array containment.

2. **`runbook_run_records` gains `currency CHAR(3)` — the field map's `D-2`, decided.** B3 gives
   `amount NUMERIC(18,4)` and names no currency beside it, while hard rule 2 requires one wherever
   money is stored, and every money column in this product already carries the partner
   (`invoices.currency`, `payments.currency`, `invoice_lines.currency` — thirteen of them in
   `apps/billing/models.py` alone, each commented *"rule 2 partner"*). **Decided as ours** under
   law 13: the column is added, and it is NULLable because most record rows carry no amount at all
   — a missing-read finding has nothing to denominate. **The rule this writes down: where `amount`
   is not null, `currency` is not null either.** Deriving it from the tenant instead was rejected
   for one reason: a tie-out against a legacy trial balance compares OUR figure with THEIRS, and
   the day a tenant's currency changes, every historical record row would silently re-denominate —
   the exact failure `BR-TEN-021`'s forward-only currency lock exists to prevent.

3. **`cutover_plan_items.owner` is `text`, not `uuid REFERENCES users(id)` — the field map's `D-7`,
   decided.** Every other actor column in these seven (`changed_by`, `approved_by`, `stopped_by`,
   `decided_by`, `owner_user_id`) is a uuid, because each records **one of our users performing an
   act**. This one records **who is responsible for a task**, and on a cutover that is very often
   the implementer — a person with no row in `users` at all. A uuid would refuse the commonest
   case. **Text is the honest superset and it is also the reversible direction**: adding
   `owner_user_id uuid` beside it later is an addition, while narrowing text → uuid would be a data
   migration over rows already typed by hand.

**No foreign key from `runbook_run_records.subject_id` to anything, and that is deliberate rather
than missing.** The column holds the id of another module's row — an account, a meter, a premises,
a bank line — and which table it points at is decided by `subject_type` on the same row. A real FK
would need twelve nullable columns, would make this module's schema depend on twelve others, and
would give the runbooks module a hard link into tables it is forbidden to write. The module reads
those rows through `apps/runbooks/seams/`, never by joining, and `BR-RBS-039` and `G115` are what
hold that line. **The cost is stated rather than hidden: a deleted account leaves a record row
pointing at nothing.** That is correct for an audit record — *what did this run say it would do* is
a fact about the past, and it should not vanish because the subject did.

**Six rows added to §2's reviewed cross-module FK set (DB-16), review owed at the next B2 sitting.**
All six point at `users(id)` and **not one of them is a write**: this module reads a name to draw
beside an act and changes no identity row anywhere.

| Table | Column | Type | Points at | Direction |
|---|---|---|---|---|
| `runbook_versions` | `changed_by` | `uuid NULL` | `users(id)` — who edited the definition | runbooks → identity |
| `runbook_runs` | `approved_by` | `uuid NULL` | `users(id)` — the admin who approved the batch | runbooks → identity |
| `runbook_runs` | `stopped_by` | `uuid NULL` | `users(id)` — who pressed Stop | runbooks → identity |
| `runbook_run_records` | `decided_by` | `uuid NULL` | `users(id)` — who made a row decision | runbooks → identity |
| `work_items` | `owner_user_id` | `uuid NULL` | `users(id)` — assigned from `RBS-007` | runbooks → identity |
| `cutover_plan_items` | `owner` | `text` | **nothing** — a typed name, see departure 3 | — |

**What is deliberately NOT here:** no partitioning row in §5 (`runbook_runs` takes one row per run,
not per attempt — ~7,000 a year at the top of the ICP; the reasoning is in the DDL comment) · no
index rows in §4 beyond the two UNIQUE constraints the DDL declares, because no query exists yet to
serve — the list screens arrive in waves D and H and each brings the index its own `EXPLAIN`
justifies · **no `ports` or `seams` table**, because ports and seams are code and not rows
(`BR-RBS-022`, and adding one would be the four-call reading the contract corrects) · **no
thirteenth or fourteenth port**, and in particular no `raise_work_item`: raising a work item and
writing an audit row are ENGINE acts, which is the only thing that lets a Check populate
`work_items` while holding no writer at all.


## Addendum r25 — the interface half of the same task: Runbooks' **nine read seams** and its **thirteen write ports** (`CR-075` wave A, 2026-09-06) 🔒 **HUMAN-REVIEW-PENDING**

**Addendum r24 above carries the TABLES. This carries the BOUNDARY**, and the two were
written by two lanes within the same hour — r24 first, this second, on top of it. Nothing
in r24 is re-stated, contradicted or reverted here: its three departures stand as decided
(`runbooks.tags` as `jsonb`, `runbook_run_records.currency CHAR(3)` closing `D-2`, and
`cutover_plan_items.owner` as `text` closing `D-7`), and this addendum adds only what r24
says it deliberately did not: **the rows the cross-module interface set (DB-16) owes for
every way this module reaches out of itself.**

🔒 **BOTH ADDENDA AND THE `### Module: runbooks` SECTION ARE A SENSITIVE PATH** — schema
and migration ordering (`CLAUDE.md` 🔒 list, as amended by PO ruling 2026-08-09: *"AI will
do it; we will review it later as human"*). **The row that carries the deferred review is
in `12-governance/09-human-review-ledger.md`, filed with this addendum**, and it states in
plain English with a concrete figure what a reviewer is being asked to agree to across all
three. ⚠ **`G7`'s guard list globs only `06-backend/**`, so no gate enforces the marker on
a document** — which is precisely why it is written out here rather than assumed. Nothing
in either addendum reaches lifecycle RATIFIED without a recorded human sign-off.

⚠ **NOTHING IS BUILT.** No `apps/runbooks` exists, no migration is written, and no row of
any of the seven tables has ever been inserted.

### The nine READ seams — one file per module read, and each owes a register row

**Every read of another module is a seam file THIS module owns**, calling the owner's
selector **by name, in process, under the tenant context with RLS forced**. **No raw SQL,
no cross-tenant queryset, no HTTP client anywhere in the module, and no import of another
module's models** (`BR-RBS-039`; the proof is a census of the module's imports,
`TC-RBS-25`). **A selector that does not exist yet is added by the module that OWNS the
table, never by this module reaching past it.**

| Seam file | What crosses | Direction | Whose selector |
|---|---|---|---|
| `apps/runbooks/seams/customers_seam.py` | accounts, contacts, flags, protections | **read only** | `customers` |
| `apps/runbooks/seams/metering_seam.py` | premises, units, meters, reads, meter-days | **read only** | `metering` |
| `apps/runbooks/seams/rating_seam.py` | plans, rate schedules, tariffs | **read only** | `rating` |
| `apps/runbooks/seams/billing_seam.py` | bills, bill runs, break lists | **read only** | `billing` |
| `apps/runbooks/seams/payments_seam.py` | payments, deposits, plans in flight, bank lines | **read only** | `payments` |
| `apps/runbooks/seams/ledger_seam.py` | period postings, journal lines | **read only** | `ledger` |
| `apps/runbooks/seams/notifications_seam.py` | what was queued, and to which channel | **read only** | `notifications` |
| `apps/runbooks/seams/tenancy_seam.py` | settings — **policy is read, never duplicated** | **read only** | `tenancy` |
| `apps/runbooks/seams/integrations_seam.py` | a landed batch, for the three event triggers | **read only** | `integrations` |

⚠ **THE LAYOUT IS `work`'s AND NOT `billing`'s, AND THE CHOICE IS DELIBERATE.** The
repository already carries this pattern twice: `billing` puts its nine seams **flat in the
app package**, `work` puts its eight in a **`seams/` sub-package**. With nine seams and a
boundary gate to write against them, **follow `work`** — a directory is what a glob reads
and what a tenth seam does not crowd. And the file names **only the FAR side**
(`apps/work/seams/customers_seam.py`, never `work_customers_seam.py`): the pair is already
in the path. The specification's `operations → customers` pair naming is kept in each
seam's own docstring, so a reader of either document finds the same file.

⚠ **THESE NINE ROWS ARE A RESERVATION, NOT A REVIEW.** The row that names *which selector,
by name* is added **in the same commit as the seam file** (`CR-075` wave A task `A4`) —
never in a later tidy-up, which is how `r18`, `r19`, `r20` and `r21` were each written and
why the set is readable today.

⚠ **AMENDED 2026-09-06 BY THE LANE THAT BUILT `A4`, BECAUSE THE NINE FILES NOW EXIST AND
NAME NO SELECTOR — DELIBERATELY.** The nine seam files landed with this addendum's table
already written; each declares its pair, what crosses and `direction="read"`, and **not one
of them names a selector**. That is not the task left half-done, and the reason is worth a
paragraph so nobody "completes" it: **naming a selector that no module exposes yet fails
`G20`**, whose R2 rule refuses a documented seam nobody has authored — the guard that caught
`DEF-075`, where billing's half of a currency-lock probe resolved to `None`, `None` was read
as *"this module has nothing"* when it meant *"this module cannot answer"*, and a tenant
re-denominated its books over an issued bill of `108.88 USD` with 1,961 tests green. Naming
one that DOES exist but that nothing calls yet is hard-won law 2's dead code. **So a
by-name row arrives with the WAVE THAT MAKES THE CALL** — wave C for the first Check, F and
G for the pricing reads, I for the sweep, K for the tie-out — and each such wave adds it
here in its own commit, exactly as this note requires. **The list of selectors this module
will need and NO module exposes today is `17-runbooks/13-selector-inventory.md`**, task
`A5`, written now precisely so it is not discovered in phase 5; the owning module adds each
one. The count today is therefore **nine seams reserved, zero selectors named, and that
zero is a measurement rather than an omission.**

### The thirteen WRITE ports — **thirteen, and `raise_work_item` is NOT one of them**

**A port is the only way a runbook reaches another module or a partner.** Each maps to
**one service function in the owning module**, so DB-16's ban on cross-module writes holds;
each is **idempotent per record**; and **the list of everything this automation can ever do
to a customer is this one table.** A new runbook that needs a new port is **adding a
reviewed interface, not a custom write.**

| Port | Owning module | What it does |
|---|---|---|
| `queue_notice` | `notifications` | Writes a queue row; the dispatcher sends |
| `queue_receipt` | `notifications` | A receipt document to the queue |
| `apply_payment` | `payments` | Applies a landed payment by the allocation order |
| `post_credit` | `payments` | A credit to an open account |
| `raise_refund` | `payments` | A refund awaiting its own approval |
| `record_match` | `payments` | A bank line matched to a deposit batch |
| `schedule_retry` | `payments` | A retry of a failed debit |
| `apply_fee` | `billing` | A fee by rule, **behind the second approval** (`BR-RBS-018`) |
| `write_read` | `metering` | A validated meter-day as a read, **source stamped** |
| `apply_premise_change` | `metering` | One field on one premise, **before-and-after kept** |
| `flag_meter` | `metering` | *"Told about a leak on"* a date |
| `suppress_channel` | `customers` | A contact channel marked undeliverable, **dated** |
| `flag_account` | `customers` | A flag with a reason |

**Five modules own ports: `notifications` (2) · `payments` (4) · `billing` (1) ·
`metering` (3) · `customers` (2).** **No port reaches `ledger`, `rating`, `tenancy` or
`integrations`** — those four are **read-only** to a runbook, which is why *Month-end
completion*'s **Close** is a person's act performed by `ledger`, and why *Rate change
preview* can model a draft tariff and change nothing.

⚠ **THIRTEEN, NOT FOUR — AND THE SOURCE SAYS FOUR IN SEVEN PLACES AND THIRTEEN IN ONE.**
The specification's architecture section says a runbook writes through *"four named calls —
queue a notice, flag an account, **raise a work item**, apply a fee"*, and *"the four port
seams"* appears five more times. Its contract section, one page later, lists **thirteen**
and states in its own figure that **raising work items and writing audit rows are ENGINE
acts, never ports.** **Thirteen is right**, and the reason is written out here rather than
left to be re-derived: it is the later and finer statement, it names an owning module for
each entry, and it is the list the result wireframes need — `record_match` is drawn on
runbook 14, `write_read` on 21, `apply_premise_change` on 20, `suppress_channel` on 22,
`post_credit` and `raise_refund` on 15, `schedule_retry` on 17, **and the four-port sentence
cannot draw any of them.** ⚠ **AND `raise_work_item` IS NOT A PORT AT ALL:** a Check is
constructed with **no ports** and must still populate `work_items`, which is impossible if
raising a work item is one. **A lane building the four-call version gives every Check a
writer, and `BR-RBS-002` — the entire safety promise of a Check — is gone.** *(Reached
independently by two lanes: `17-runbooks/03-field-map.md` `D-1`, `12-the-contract.md` §6,
`04-flows.md` §4, `11-catalogue/README.md` and `CR-075` all carry the identical thirteen
with the identical owning modules. Addendum r24's closing paragraph reaches it a third
time, from the schema side.)*

⚠ **A CHECK HOLDS NONE OF THEM AND IT IS ENFORCED AT CONSTRUCTION** — `ports[]` is empty,
so a write from a Check is **unavailable** rather than refused at run time: a build error,
not a bad Monday (`BR-RBS-002`, `TC-RBS-1`, which must first fail on a version that only
raises when the port is *called*).

**No row is added to §2's FK set by this addendum.** A port is a **call**, not a foreign
key: it reaches one service function in the owning module and writes through it. The six FK
rows this module owes are r24's, and every one of them points at `users(id)` and is a
pointer rather than a write.

### One thing left OPEN on a money-adjacent path, and it is not this addendum's to close

⚠ **`DEF-RBS-4246` — the idempotency key contradicts its own worked example.**
`BR-RBS-008` and `17-runbooks/03-field-map.md` §4 give
`runbook_run_records.idempotency_key` as **"runbook + run + record + action kind"**, and
four lines later the same table says *"the second run of the ladder on the same day queues
nothing, because every key it computes is already in this index"* — **which is only
possible if the run is NOT in the key.** `TC-RBS-4` (*248 in total, not 496*) and
`TC-RBS-012.1` (*"must first fail on the key scoped to the run rather than to the record"*)
both need it out. **Three statements to one, and the wrong choice re-sends every notice on
a retry — 496 letters where 248 were meant.** It is `BR-RBS-008`'s to settle through the
change process; it is recorded here because the `UNIQUE (tenant_id, idempotency_key)`
constraint in §2 is where the mistake gets made.

## Addendum r26 — the no-overlap guarantee `discount_versions` needs and B2 never signed (`DEF-RAT-8050`, 2026-09-29) 🔒 **HUMAN-REVIEW-PENDING**

⚠ **THIS SCHEMA HAS NEVER SAID ANYTHING ABOUT DISCOUNTS AT ALL.** Before this
addendum the word *discount* appeared **zero** times in this file — not a
table, not a column, not a constraint — while `discounts`, `discount_versions`,
`discount_enrolments`, `discount_grants` and `plan_discount_rules` have been
live in `apps/rating/discounts.py` since `CR-013` part 3. **That absence is not
a licence; it is the gap.** `G137` (`10-scripts/gates/g137_declared_constraints_are_built.py`)
decides what the database MUST have by reading this file, so a table B2 never
mentions is a table G137 is structurally unable to have an opinion about — and
it reported its clean verdict truthfully over `discount_versions` the whole
time. That is hard-won law 7's fifth shape: **a blind spot with no number
beside it is indistinguishable from an empty one.**

**WHAT IS ADDED, AND IT IS ONE CONSTRAINT AND NOT A TABLE DEFINITION.** The
DDL for these five tables is the ORM's and is not restated here — restating it
would create a second source of truth for forty-odd columns, which is the
`superseded_by`-versus-`status` problem this very defect is about, one level
up. What B2 signs is the GUARANTEE:

```sql
-- module: rating · DEF-RAT-8050 · built by rating/0049
ALTER TABLE discount_versions
  ADD CONSTRAINT ex_discount_versions_no_overlap
  EXCLUDE USING gist (                          -- no overlapping IN-FORCE windows per discount
    tenant_id WITH =, discount_id WITH =,
    daterange(effective_from, coalesce(effective_to + 1,'infinity'::date)) WITH &&
  )
  WHERE (status = 'active' AND effective_from IS NOT NULL)
  DEFERRABLE INITIALLY DEFERRED;
```

**FOUR THINGS ARE DELIBERATELY UNLIKE `tariff_versions`' EXCLUDE ABOVE**, and
each is argued from this object's own code in `rating/0049`'s docstring rather
than asserted here:

1. **`WHERE status = 'active'`, not `superseded_by … IS NULL`.** Supersession
   on this object is a STATUS — `discounts.py`: *"`superseded` is what a later
   version does to an earlier one"*. Every reader that prices filters
   `status='active'` and **none** filters `superseded_by`. Naming both would
   be a second representation of one fact.
2. **`scheduled` and `pending_approval` are OUTSIDE the predicate, on
   purpose.** `activate_discount_version` supersedes by status, so a live
   discount's `effective_to` stays NULL until its successor activates — every
   approved successor therefore overlaps the incumbent's open window BY
   DESIGN. Including them would refuse every approval on every live discount.
3. **`effective_to + 1`.** `effective_to` is INCLUSIVE here as it is on
   `tariff_versions`, and `daterange` is half-open. ⚠ **The `tariff_versions`
   expression signed above is off by one day in the permissive direction and
   `rating/0047` corrects it** — see that migration's docstring; this
   addendum writes the corrected form so the second constraint does not
   inherit the first's error.
4. **`DEFERRABLE INITIALLY DEFERRED`.** `correct_discount_version` writes the
   correction row `active` over the corrected row's window VERBATIM and flips
   the original to `superseded` in the next statement. An immediate constraint
   refuses every correction this product can take.

**MEASURED, 2026-09-29, PostgreSQL 16.13, a clone of a 449-migration
database:** `discount_versions` carries **zero** exclusion constraints and
`discounts`/`discount_versions` hold **6 and 6** rows — one version per
discount, **0** overlapping groups. A zero on that estate is a statement about
that container, not about production; `10-scripts/rat_schedule_overlap_census.py
--discounts` is what answers it anywhere else, and `--plant-proof` is what
shows the counter can find one.

**NOT SETTLED BY THIS ADDENDUM, AND NAMED SO NOBODY READS SILENCE AS AN
ANSWER:** `taxes` states an in-force window in `effective_from`/`effective_to`
and carries **no** uniqueness or exclusion over it either — two rows for one
`(tenant_id, jurisdiction_id, kind)` may hold any windows at all. That is
`DEF-RAT-8051`, and it is not the same fault: `selectors._authority_tax`
chooses between them **without consulting the date at all**, so a constraint
alone would not make that read correct.

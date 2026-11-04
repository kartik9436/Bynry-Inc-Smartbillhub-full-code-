# tenancy — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Utility name | S110 | A1 addendum 2026-08-08 | tenants.name | text | user-input | required ≤120 | ok |
| Web address (subdomain) | S110 | A2 §S4 | tenants.subdomain | text | user-input | BR-TEN-011 | ok |
| State | S110 | A2 §S4 | tenants.state | text | user-input | US state/DC/PR | ok |
| Services billed | S110 | A2 §S4 | tenant_services.service | service_type | user-input | ≥1 of 6 | ok |
| Load standard reference data | S111 | A2 §S5 load_defaults | — (drives seeding, not stored) | boolean | user-input | — | ok |
| Plan | S112 | A1 addendum 2026-08-08 | subscriptions.plan_id | uuid FK | user-input | 3 platform plans | ok |
| Trial end | — | A1 addendum (14-day) | subscriptions.trial_ends_at | timestamptz | system-derived | +14 d | ok |
| Owner name/email/password/mobile | S114 | A2 §S6 | users.full_name/email/password_hash/phone | text/citext/hash/text | user-input | email fmt; policy; mobile opt | ok |
| Provisioned at | — | US-TEN-001 | tenants.provisioned_at | timestamptz | system-derived | set once | PROPOSED-SCHEMA |
| Seed run record | — | US-TEN-002 | reference_seed_runs(tenant_id, list_code, fixture_version, seeded_count, seeded_at) | — | system-derived | UNIQUE (tenant, list, version) | PROPOSED-SCHEMA |
| Checklist mark-done/dismiss state | checklist S62 (OQ-034 CLOSED) | prototype-extracted | tenants.checklist_state | jsonb | user-input | known item codes | PROPOSED-SCHEMA |
| Legal name | S8 Company | prototype-extracted | tenants.legal_name | text | user-input | req. for checklist | PROPOSED-SCHEMA |
| Doing business as | S8 Company | prototype-extracted | tenants.dba_name | text | user-input | optional | PROPOSED-SCHEMA |
| Tax ID (EIN) | S8 Company | prototype-extracted | tenants.ein (PII — app-layer encryption per OQ-016 closure, PO R6) | text (9 digits) | user-input | BR-TEN-018 | PROPOSED-SCHEMA |
| Utility ID (state) | S8 Company | prototype-extracted | tenants.state_utility_id | text | user-input | ≤40 | PROPOSED-SCHEMA |
| Mailing address | S8 Company | prototype-extracted | tenants.mailing_address | text | user-input | req. for checklist | PROPOSED-SCHEMA |
| Support phone / email | S8 Company | prototype-extracted | tenants.support_phone / support_email | text / citext | user-input | phone loose; email fmt | PROPOSED-SCHEMA |
| Website | S8 Company | prototype-extracted | tenants.website | text | user-input | hostname-ish | PROPOSED-SCHEMA |
| Logo | S8 Company | ~~prototype-extracted (SVG/PNG ≤2MB)~~ PNG/JPG ≤2MB (DEF-TEN-10618, 2026-10-27) | tenants.logo_file_id (object-store ref) | file | user-input | BR-TEN-019 | PROPOSED-SCHEMA |
| Primary color / Bill accent | S8 Company | prototype-extracted | tenants.brand_primary_hex / brand_accent_hex | char(7) | user-input | #RRGGBB | PROPOSED-SCHEMA |
| Remit-to address | S8 Company | prototype-extracted (bill stub, A19 §1.8) | tenants.remit_to_address | text | user-input | req. for checklist | PROPOSED-SCHEMA |
| Payable to | S8 Company | prototype-extracted | tenants.remit_payable_to | text | user-input | defaults to DBA | PROPOSED-SCHEMA |
| Customer service hours | S8 Company | prototype-extracted | tenants.service_hours | text | user-input | ≤60 | PROPOSED-SCHEMA |
| Country | S8 Regional | prototype-extracted | tenant_settings.country | text | user-input | US/CA | PROPOSED-SCHEMA |
| Timezone | S8 Regional | prototype + A1 addendum (8 US zones) | tenant_settings.timezone | IANA tz | user-input | valid tz. **BR-TEN-081 (PO 2026-08-12) makes a typed posting date midnight in THIS timezone — ⚠ the control is missing from Company settings (DEF-082), so the rule is unimplementable until it ships** | PROPOSED-SCHEMA — **DEF-082** |
| Language | S8 Regional | prototype + IS-8 | tenant_settings.language | BCP-47 | user-input | en-US v1 | PROPOSED-SCHEMA |
| First day of week | S8 Regional | prototype-extracted | tenant_settings.first_day_of_week | enum sun/mon | user-input | — | PROPOSED-SCHEMA |
| Currency | S8 Regional | prototype-extracted | tenants.currency | CHAR(3) | user-input | USD/CAD; BR-TEN-021. **LOCKED once ANY financial record exists — and a DRAFT bill counts (BR-TEN-042 as amended 2026-08-12, OQ-181); deleting the draft releases the lock** | ok |
| Number / Date / Time format | S8 Regional | prototype-extracted | tenant_settings.number_format / date_format / time_format | text | user-input | offered patterns | PROPOSED-SCHEMA |
| Fiscal year start | S8 Regional | prototype-extracted | tenant_settings.fy_start_month + fy_start_day | int + int | user-input | valid month/day | PROPOSED-SCHEMA |
| Accounting method | S8 Regional | prototype-extracted | tenant_settings.accounting_method | enum accrual/cash | user-input | — | PROPOSED-SCHEMA |
| Close cadence / Close by | S8 Regional | prototype-extracted | tenant_settings.close_cadence / close_day | enum / text | user-input | offered values | PROPOSED-SCHEMA |
| Lock periods once closed | S8 Regional | prototype-extracted | tenant_settings.lock_closed_periods | boolean | user-input | enforcement per BR-TEN-038 (auto-post to earliest open period, SysAdmin reopens; OQ-033 CLOSED) | PROPOSED-SCHEMA |
| Service enabled | S8 Services | prototype-extracted | tenant_services.enabled + disabled_at | boolean + tstz | user-input | disable guard BR-TEN-026 | PROPOSED-SCHEMA |
| Primary / Alt UoM per service | S8 Services | prototype-extracted | tenant_services.primary_uom_id / alt_uom_id → uoms.id | uuid FK | user-input | active UoM; alt ≠ primary | PROPOSED-SCHEMA |
| UoM entries | S8 Reference data | prototype-extracted | uoms(tenant_id, code, name, active) | text | user-input / seeded | UNIQUE (tenant, lower(code)) | PROPOSED-SCHEMA |
| Reason-code entries | S8 Reference data | prototype-extracted (S22 reasons) | reason_codes(tenant_id, code, name, default_gl_account_id, active) | text | user-input / seeded | UNIQUE (tenant, code) | PROPOSED-SCHEMA |
| Charge-code entries | S8 Reference data | prototype-extracted + B2 charges | charges.code/name/amount/percent/min_amount/gl_account_id | text / NUMERIC(18,6) | user-input / seeded | rating-owned validation | ok (+ `active` flag PROPOSED-SCHEMA) |
| Lookup active flag (all lists) | S8 Reference data | prototype Active/Inactive pills | `active boolean NOT NULL DEFAULT true` per lookup table | boolean | user-input | deactivation ≠ deletion | PROPOSED-SCHEMA |
| Used by (per entry) | S8 Reference data | prototype-extracted | live COUNT via owning-module service fn | int | computed-display | BR-TEN-029 | ok |
| Payment methods / Account statuses / Meter types entries | S8 Reference data | prototype cards vs B2 enums | lookup tables seeded + tenant-extensible (BR-TEN-036; OQ-031 CLOSED — enums→lookups) | — | reference-data | audit-locked when used | ok |
| Tax-jurisdiction entries | S8 Reference data | prototype card vs B2 platform table | tax_jurisdictions tenant-entered (BR-TEN-037; OQ-032 CLOSED) | — | user-input | per-authority rates | ok |
| Number series (5) | S8 Numbering | prototype (4 fields) + A1 r4 asset # | number_series.series (account/bill/payment/adjustment/asset) | enum | reference-data | UNIQUE (tenant, series) | PROPOSED-SCHEMA |
| Number format string | S8 Numbering | prototype-extracted defaults | number_series.format | text | user-input | BR-TEN-035 grammar | PROPOSED-SCHEMA |
| Next number | S8 Numbering | PM task note (not in prototype) | number_series.next_number | bigint | user-input / system-derived | forward-only | PROPOSED-SCHEMA |
| Number preview | S8 Numbering | derived | — | text | computed-display | — | ok |

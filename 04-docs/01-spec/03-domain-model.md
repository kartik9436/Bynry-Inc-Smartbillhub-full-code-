# A3 — Domain Entities & Relationships

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Entities, attributes, identifiers, cardinality, tenant-scope.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


- **Tenant (Utility)** — one utility org. Attrs: name, subdomain, state, services[], currency, plan/subscription, tax_region. ID: subdomain/tenant_id. Tenant-scoped root.
- **User** — staff login. Attrs: name, email, phone, role. Belongs to 1 Tenant (N:1). `UNKNOWN — can one user belong to multiple tenants? "Switch tenant" was proposed but not built.`
- **Service** — Electric/Water/Gas/Sewer/Trash/Broadband. Platform-global enum; enabled per Tenant (N:M via tenant_services).
- **Premises** — a physical property. 1 Tenant : N Premises. Owns Units.
- **Unit** — billable space within a Premises. 1 Premises : N Units. Has assigned Meter(s), Sub-meter(s), and a Plan.
- **Meter / Sub-meter** — measures one service. Attrs: meter no, service, factor/multiplier, install date, health, source (AMI/manual). Unit : Meter is 1:N (multi-service). Sub-meter is a child Meter (1:N under a parent Meter or Unit).
- **Plan** — a bundle of rate schedules + base charge for a customer class. Tenant-scoped. Plan : Rate is N:M.
- **Rate (schedule)** — pricing for one service (flat/tiered/TOU/demand). Tenant-scoped.
- **Charge Code** — one-off/recurring fee (CONN, DISC, NSF, LATE, TAMPER, SVCCALL, DEPO-R…). Tenant-scoped lookup.
- **Tax / Fee** — jurisdiction tax or franchise fee. Tenant-scoped; linked to Authority.
- **Authority** — tax jurisdiction (TX Comptroller, City of Austin, Travis County, TX PUC). `UNKNOWN — global registry vs tenant-entered?`
- **Account** — customer billing account at a Unit. Attrs: account_no, customer, status, balance, deposit, credit tier, autopay, portal access. 1 Unit : N Accounts over time (move-in/out); 1 active at a time. Tenant-scoped.
- **Customer** — person/business. `UNKNOWN — is Customer a separate entity from Account, or embedded? UI shows customer fields inside Account.`
- **Meter Read** — one reading. Attrs: meter, prior, current, usage, source, date, days-since-prior, status (OK/High/Low/Missing/Estimated), route, cycle, month, service. Meter : Read 1:N.
- **Route** / **Cycle** — read/billing grouping. Tenant-scoped. Account : Cycle N:1.
- **Bill (Invoice)** — Attrs: bill_no, account, cycle, usage, line items, amount, status. Account : Bill 1:N.
- **Payment** — Attrs: date, account, type (Payment/Credit/Adjustment), method, confirmation, applied-to bill, amount, status. Account : Payment 1:N.
- **Adjustment / Credit** — modeled as Payment.type variants + own reason/GL.
- **Payment Plan** — installment agreement. Account : Plan 1:N (usually 1 active). Owns Installments (1:N).
- **Deposit Batch** — daily group of payments by method. Owns Payments (N:M or 1:N). Reconciled against Bank Line.
- **Bank Line / Statement** — imported bank posting. Batch : BankLine ~1:1.
- **GL Account** — chart of accounts. Platform template, tenant-customizable.
- **Report / Scheduled Report / Report Run** — Tenant-scoped.
- **Subscription (Plan package)** — Starter/Growth/Scale. Platform-level product; Tenant : Subscription N:1.

**Tenant-scoped (security-critical):** Premises, Unit, Meter, Account, Customer, Bill, Payment, Read, Plan, Rate, Charge Code, Tax/Fee, Deposit Batch, Report, User.
**Platform/global:** Service enum, Subscription packages, GL template, possibly Authority.
**Shared-across-tenant risk:** Authority and GL template if shared — flag for read-only global + tenant overrides. **No tenant-scoped entity should ever be visible cross-tenant.**
**Join tables needed:** tenant_services (Tenant×Service), plan_rates (Plan×Rate), batch_payments (Batch×Payment), report_recipients.

---


## Addendum — Asset entity & lifecycle (2026-08-07 r4)
- **Asset** generalizes meters/sub-meters/devices. Attrs: asset_no, type (meter|net_meter|sub_meter|backflow|comms|pv|battery|ev_charger|transformer|generator), service, read_method (AMI/AMR/walk-by/NA), multiplier, manufacturer, model, install_date, retire_date, status, parent_asset_id (sub-meters), net_metering (bool). Tenant-scoped. Assigned to a **Unit** (nullable = inventory).
- **asset_assignments** (history): asset_id, unit_id, from_date, to_date, actor — for the Assignment-history tab and by-premises reporting.
- **asset_maintenance** (log): asset_id, date, kind (repair/inspection/test), detail, tech, resulting_status — for lifecycle + work orders.
- **Net meter reads:** meter_reads gains import vs export quantities for net_metering assets (rating input for credits — see A8/B4).
Lifecycle status: inventory → active → needs_repair → in_repair → active | → retired (terminal). Retired/referenced assets: retire, never hard-delete.

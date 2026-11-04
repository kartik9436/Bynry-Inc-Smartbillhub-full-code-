# A9 — Navigation & Flow Map

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Nav hierarchy + five end-to-end flows.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


**Sidebar (collapsible):** Dashboard · Settings · Plans & Rates · Premises · Accounts · Reads · Billing · Payments · Finance · Reports. User block at footer (S48 proposed). (Note: Plans & Rates sits above Premises per an explicit change request.)

**Flow 1 — Signup:** S1 Pricing → S2 Welcome → S4 → S5 → S6 → S7 Dashboard. *Backend takes over at:* tenant provisioning, lookup seeding, auth.
**Flow 2 — Read→Invoice:** S28 upload/ingest → S25 review/flags → S31 Run Bills (S31.2 check → S31.3 exceptions → generate → summary/compliance) → S30 Bills. *Backend:* rule engine, rating engine, bill numbering, delivery.
**Flow 3 — Payment→Ledger:** S33 record (or S38 lockbox/bank) → apply to bill → S37/S42 deposit + GL export. *Backend:* payment gateway, application logic, GL posting.
**Flow 4 — Correction:** S21 Account detail → Adjust / Issue credit / Change plan (S23) / Payment plan (S24) / bill correction (S30). *Backend:* reversing ledger entries, approval workflow.
**Flow 5 — Month-end:** S36 Revenue → S37 reconcile (S38) → S41 taxes/remittance → S42 export/lock. *Backend:* period close, lock, accounting sync.

---


## Revised 2026-08-08 — Flow 1: self-serve signup

```
Pricing (3 tiers)
  └─ Choose plan ──▶ Welcome gateway
                       ├─ "Already a customer? Sign in" ──▶ Dashboard
                       └─ "Create your utility" ──▶ Setup wizard
                                                     1. Your utility
                                                     2. How you bill        [Skip — use defaults]
                                                     3. Plan & setup        (subscription + implementation)
                                                     4. Review              (Edit links back to 1/2/3)
                                                     5. Create login
                                                        └─ Create utility & go live
                                                             └─▶ Dashboard + onboarding checklist
```

**Where the design stops and the backend takes over**

| Point | Backend must do |
|---|---|
| Step 1 · web address | Live subdomain uniqueness check across all tenants |
| Step 1 · state | Seed the default tax jurisdiction for that state |
| Step 2 · load reference data | Provision standard charge codes, UoM, account statuses, reason codes for the chosen services |
| Step 3 · plan | Record the subscription and its band; connection count is advisory metadata, **not** an enforced limit |
| Step 3 · implementation | Create a services order for anything other than Self-serve; notify Bynry delivery |
| Step 4 | Nothing written — read-only |
| Step 5 · create | Create tenant, owner user with System Admin role, start 14-day trial with **no payment method**, provision the subdomain, send verification email |

**Post-signup:** the dashboard checklist drives the remaining setup — company profile, logo, rate schedules, premises and units, assets, account import. None of it blocks first login.

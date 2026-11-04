# A16 — Glossary

> Part A (extraction). Source: SMARTBillHub prototype «../../05-prototype/UtilityBilling.html». Domain terms exactly as the UI uses them, to prevent naming drift.
> Cardinal rule: anything not determinable from the UI is «UNKNOWN — <question>», never invented.


| Term (UI) | Meaning | Not to be confused with |
|---|---|---|
| **Tenant / Utility** | one utility org on the platform | the utility's customers |
| **Account** | customer billing account at a unit (A-#####) | Ledger (GL) account |
| **Premises** | a physical property | Unit |
| **Unit** | billable space within a premises (has meters + plan) | Premises |
| **Service point** | metered service instance at a unit (schema term) | Meter |
| **Meter / Sub-meter** | measuring device; sub-meter is a child meter | Service point |
| **Meter factor / multiplier** | multiplier on raw reading (×10) | consumption |
| **Read / Reading** | raw meter value at a time | Consumption |
| **Consumption / Usage** | current − prior (× factor); billed quantity | Read |
| **Plan** | customer bundle: base charge + rate schedules | Subscription (package) |
| **Rate / Rate schedule** | pricing for one service | Plan |
| **Tariff** | schema name for Plan/Rate pricing | Tax |
| **Charge code** | fee (CONN/DISC/NSF/LATE/TAMPER/SVCCALL/DEPO-R) | Tax/Fee |
| **Bill / Invoice** | charge document for a cycle (BL-...) | Statement |
| **Statement** | account activity over a range | Bill |
| **Cycle** | billing group (08-A) | Route |
| **Route** | meter-reading group | Cycle |
| **Adjustment** | credit/debit correction to a balance | Credit note |
| **Credit note** | credit referencing an original invoice | Adjustment |
| **Payment** | money received | Allocation |
| **Allocation** | how a payment applies to invoices | Payment |
| **Deposit batch** | daily group of payments (DEP-...) | customer security deposit |
| **Deposit on file** | customer security deposit held | Deposit batch |
| **Outstandings** | accounts with open balance (AR) | Over charges |
| **Over charges** | extra items to add in a billing run | Outstandings |
| **DSO** | days sales outstanding | aging bucket |
| **Aging bucket** | Current / 31–60 / 61–90 / 90+ | DSO |
| **Budget Bills** | level-pay / even-monthly (12-mo average) | Payment plan |
| **Payment plan** | installment agreement to pay down a balance | Budget Bills |
| **Move-in / Move-out** | account start / final-bill close at a unit | New Account |
| **Subscription / Package** | SMARTBillHub plan (Starter/Growth/Scale) | customer Plan |
| **Owner** | self-signup tenant admin role | Platform Admin |



## Addendum — Assets (2026-08-07 r4)
| Term | Meaning | Not to be confused with |
|---|---|---|
| **Asset** | any tracked meter/sub-meter/device in the Assets module | Account |
| **Net meter** | bidirectional meter measuring import + export (net metering) | Meter |
| **Behind-the-meter device** | backflow preventer, comms endpoint, PV inverter, battery, EV charger, transformer, generator | Meter |
| **Inventory (asset)** | asset on hand, not yet assigned to a unit | Deposit inventory |
| **Retire (asset)** | terminal lifecycle state; keeps history, hides from active lists | Delete |

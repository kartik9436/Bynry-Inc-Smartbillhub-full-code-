# A8 — Tariff Specification

> Part A (extraction). Source: SMARTBillHub prototype «../../05-prototype/UtilityBilling.html». Most domain-specific logic; from Plans & Rates + Setup wizard + billing-run rate refs.
> Cardinal rule: anything not determinable from the UI is «UNKNOWN — <question>», never invented.


## Tariff structures the UI supports
| Model | UI evidence | Config fields seen | Notes |
|---|---|---|---|
| **Flat** | setup radio "Flat rate"; plan base charges | base/service charge, unit price | default in wizard |
| **Tiered / inclining** | "Residential Inclining" (water), "Residential Tiered" (electric) | tier rows: from-qty, to-qty, unit price | tiers cross within a bill; reset-per-bill UNKNOWN |
| **Time-of-use (TOU)** | "Commercial TOU" (electric) | windows: label, start/end time, unit price | peak/off-peak; depth UNKNOWN |
| **Demand** | "Industrial Electric · Demand" | demand charge per kW | measurement basis UNKNOWN |
| **Fixed service / base charge** | every plan shows "$X/mo base" | base_charge per plan | applies regardless of usage |
| **Minimum bill** | referenced concept | minimum_bill | behavior UNKNOWN |
| **% of another service** | "Sewer · % of water" | percent, source service | basis (volume vs charge) UNKNOWN |

## Plan vs Rate (as the UI models it)
- A **Plan** (e.g. "Residential Standard") = one base charge + one or more **Rate schedules** (one per service). Plan : Rate is N:M.
- A **Rate schedule** prices exactly one service with one model.
- Plans observed (all illustrative): Residential Standard ($30.50, E-tiered + W-inclining + Sewer-flat), Residential Electric-only ($18.50), Small Commercial ($48.00, E-TOU + W-flat), Industrial ($180.00, E-demand + Sewer %), Senior/Low-income ($12.00, subsidized), Standby ($15.00, base only), Budget Bills (level-pay, 12-mo average).

## Versioning behaviour shown
- Rate changes tracked with an **approver** ("Rate change history" report).
- Change Plan wizard shows **proration** + **effective date** (Immediately / Next cycle start / Custom) → rates are effective-dated.
- **Requirement (schema B2):** historical invoices reprice against the tariff version in force on their **service date**, never the current one. INFERRED from approver/effective-date UI.

## Wizards
- **New Rate:** identity/service → structure (flat/tiered/TOU/demand) → tiers/prices → review/publish. Per-step fields UNKNOWN.
- **New Plan:** identity → attach services & rate schedules → base charges → review/publish.

## Open tariff questions
- Tier reset per bill? multiplier before/after tiering? rounding per line vs total? (A17 O-2)
- Sewer "% of water": % of volume or of charge?
- Demand measurement window / ratchet?
- Minimum-bill interaction with tiers + base?
- Budget/level-pay averaging window (12-mo) + true-up cadence?



## Addendum — Net metering (2026-08-07 r4)
Net meters (Assets module) record **export** alongside **import**. Rating treats export as a **net-metering credit** input. Exact credit method (net vs gross, rollover of surplus, credit rate vs retail) is **PLACEHOLDER — finance/B4 to confirm.**

# A7 — Business Logic Embedded in the UI

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Calc, rounding, proration, tax, aging; EXPLICIT/INFERRED/UNKNOWN.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


| Item | Detail | Confidence |
|---|---|---|
| Consumption | usage = current − prior, × meter factor (×10 seen) | EXPLICIT (values), formula INFERRED for factor order |
| Water unit | kgal shown; register raw counts also shown | UNKNOWN (unit of billed qty) |
| High-usage rule | usage > ~2× customer average (shown 205–312%) | INFERRED threshold |
| Low-usage rule | << normal (~<20%) / zero same-as-last | INFERRED |
| Estimation | trailing-3 / 3-cycle average when missing; trues up next real read | EXPLICIT (labelled), exact math UNKNOWN |
| Days threshold | read interval outside 20–45 days flags; option "Prorate to 31 days" | INFERRED bounds |
| Late fee | "$5 minimum or 1.5% of prior balance" | EXPLICIT (labelled) |
| Tax | Texas State+Local 8.25% (6.25% state + 1.00% county + 2.00% franchise + 0.20% PUC seen separately) | EXPLICIT constants |
| Proration (change plan) | mid-cycle prorated; deposit differential; net impact shown | EXPLICIT concept, formula UNKNOWN |
| Payment plan | balance ÷ installments, remainder on final; autopay; dunning/disconnect paused | EXPLICIT |
| Aging buckets | Current 1–30, 31–60, 61–90, 90+ | EXPLICIT |
| DSO | shown 18.4, target 15 | EXPLICIT value, formula UNKNOWN |
| Reconnect fee | $45.00 | EXPLICIT sample constant |
| NSF fee | $30.00 | EXPLICIT sample |
| Rounding | money 2-dp; no explicit rounding rule for tier boundaries | UNKNOWN |
| Tariff structures supported | Flat, Tiered/inclining, Time-of-use, Demand, base/service charge, % of water (sewer), minimum bill | EXPLICIT (options), config depth UNKNOWN |
| Conditional display | Payments header hidden on Outstandings tab; approval checkbox on adjust; medical-hold skip on disconnect | EXPLICIT |
| Sort/pagination | Outstandings sorted balance high→low; lists show samples not real paging | EXPLICIT sort, pagination UNKNOWN |
| Billing cycle timing | Monthly default, bill-on 1st/15th/last; due date (e.g. "Due Aug 25") | EXPLICIT samples |

---

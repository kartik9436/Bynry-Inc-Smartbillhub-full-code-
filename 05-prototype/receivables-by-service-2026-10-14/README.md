# Receivables by service — walk of CR-184-BRC10 (2026-10-14)

Walked on **brazosbend**, a private copy of the shared database (`smartbillhub_arsvc`, dropped afterwards), backend on :8008 and the dev front end on :8088, at 1440 wide, with `10-scripts/cr184_receivables_by_service_walkthrough.mjs`. Page text for every step is in `walk-results.json`.

## What was checked, and the figures

| Step | Shot | What it shows |
|---|---|---|
| Catalogue | `01-catalogue.png` | The new card **Receivables over 90 days by service** under Receivables · Arrears, beside AR Ageing. |
| Library report, as at the period end (31 Oct 2026) | `02-library-default.png` | Electric **$6,596.24** · Water **$2,825.59** · Taxes **$945.84** · Fees **$954.35** · Other charges **$144.14** = **$11,466.15**. Nothing is over 90 days yet on this tenant (its bills are two months old), so every over-90 figure is $0.00 and the share column is a dash. |
| Library report, as at 31 Jan 2027 | `03-library-later.png` | The same receivable, now all over 90 days: **$11,466.15** from **48** debtors — Electric 57.53 %, Water 24.64 %, Taxes 8.25 %, Fees 8.32 %, Other 1.26 %. |
| Builder | `04-builder.png` (`04b-save-as.png` from the first run) | *Receivables* is offered as a subject; one row per account and service; the six money columns; Save as. |
| The saved custom report, 31 Jan 2027 | `05-custom-later.png` | 48 accounts, $11,466.15, one row per account and service (e.g. AC-2026-00004 Electric $789.02). |
| …filtered to Water | `05b-custom-water.png` | **44 accounts, $2,825.59** — the Water row of the library report exactly. |
| Finance → Who owes you, 31 Oct 2026 | `06-who-owes-you.png` | 48 accounts; the ageing's population **$11,466.15** — the same as the library report's total. |
| …Service: Water | `06b-who-owes-you-water.png` | **44 accounts**, Water's share only — matches the custom report. **Before this change the Water chip showed the whole $11,466.15**: every open bill here carries both electric and water, so whole-bill filtering counted everything under either service. |

## Against the ledger

The ledger's AR control total at 31 Oct 2026 is **$27,885.40** (Finance's *Still owed* tile). The service rows add to **$11,466.15**, so the report says *"Rows do not match the books. The report never adjusts itself."* — the same difference Who owes you already states (imported opening balances and other book entries that are in no bill). Nothing was adjusted.

## Found on the walk and fixed

1. **The As-of box was ignored** — the box read 01/31/2027 and the report answered 31 Oct 2026, because the date travels as `to` and the dataset did not declare it. Fixed; a test runs the date through the runner.
2. **`DEF-REP-10146` — a saved multi-word custom report could not be opened** (*There is no report called …*): Save as keys it with hyphens and the viewer asks with underscores. Fixed on the server, before the role and privacy checks.
3. **`DEF-REP-10145` — the builder printed `as_of` and `age_bucket`** as raw codes in its filter and group lists (every dataset with them). Words added in all eleven languages.

## Notes

* *"Some part-paid bills shared by amount."* is on the report because two part-paid bills here carry a discount or deposit line, which no payment class places (`OQ-128`, open); they were shared by plain proportion and still add up to what each bill owes.
* Two custom reports named *Receivables over 90 days by service* exist on the walk copy (`…-service` and `…-service-2`) because the first run saved twice; the copy was dropped.

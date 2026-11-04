# CR-179-BRC10 — Rate Impact report: proposed rates against billed revenue, by rate schedule or charge code, capacity and class

**Raised:** 2026-10-12 by the Product Owner, in chat, from a customer's scenario. Designed with the PO step by step the same day; the PO confirmed input, process, output, tasks and the five open points before anything was written (*"input, process, output and task are correct"*).
**Status:** **CONFIRMED — BUILD STARTED.**
**Branch:** `claude/serene-noether-71ie5b` (`BRC10` lineage). `allocate.py cr` answered **179** (178 was taken by this branch's own capture commit, reverted at the PO's *"dont write in repo yet"*).
**Classification (`13-change-process.md` §1):** a **CHANGE** — a new report; no user can do this today.
**Drawing:** `05-prototype/rate-impact-2026-10-12/` — build from the images (B14 rule 42).

## 0 · What arrived, in the requester's words (verbatim)

| | The PO, verbatim |
|---|---|
| Where | *"We want to create new report under this section -> Billing · Readiness · Bills · Delivery"* |
| The scenario | *"Rate impact modeling: run a proposed rate change against the prior year's consumption to show revenue by customer class and the bill impact on sample customers before Board or Council adoption"* |
| Shape | *"this report will need input , process and output - bascailly customer want to see the revenue impact as per customer class on specific rate schedule"* |
| Usage | *"for accoutns we are saving last 12 months consumption to show on bills"* |
| Period | *"we need 1 month, 3 months, 6 months and 9 months an 12 mnoths options"* · *"also give me option for 2 months"* |
| No engine, no bill | *"you dont have to do so much calaculation we can take compption and multipl it by rate diretcly - dot use pricing engine"* · *"we dont want to calculate bill"* |
| Proposed rate typed in | *"user will provide this imput as part of report itself - they did not create any draft rate yet"* |
| Flat only, all schedules | *"to start with we will do it for flat case only"* · *"allow all schedule - for calculate of revenue impact we will do only flat calculation"* |
| Revenue now | *"can you take revenue on account from ledge or from billing"* → billing (bill lines name the rate schedule version) |
| Rows | *"you ahve to take plan or rate schedule or charge codes as inputs. you can do tabel array"* · *"please remove plan from this list - we will ahve rate schedule and charge code only - once seelcte dyou ahve to show version and effectev date"* |
| Capacity | *"in this table can you biring is capacity colume … capacity drop down will comple from rate schedule what ever capacities are used"* · *"also in output tables you will ahve to add capacity now"* |
| Output blocks | *"one expantable block per row"* |
| Dropdowns | *"all these file dmake them drop down"* |
| Framework | *"we ahve to use reporting framework ot create this report - dont create custom report"* · *"i mena cusotm code"* |
| Images | *"all prodct screens to be completed using images and not text/content"* |

## 1 · Input (confirmed)

| # | Field | Choices | Source |
|---|---|---|---|
| 1 | Services | multi-select | the utility's active services (tenancy) |
| 2 | Customer classes | multi-select, all by default | `customers.account_types` |
| 3 | Usage period | 1 · 2 · 3 · 6 · 9 · 12 whole months ending last month | fixed list; "last month" from the utility's business date and zone |
| 4 | Change all prices by | −10% … +20% | fixed list; fills the proposed boxes from the chosen version |
| 5 | Type (each row) | Rate schedule · Charge code | fixed |
| 6 | Item | the chosen services' schedules / recurring charge codes | `rating.tariffs` by service, published · `rating.charges` recurring, by service |
| 7 | Version | every version, the one in force first | `rating.tariff_versions` · `rating.charge_code_amounts` (effective_from/to) |
| 8 | Effective from | shown | the version's `effective_from` |
| 9 | Service | shown | the schedule's / charge's service |
| 10 | Capacity | only the sizes that schedule or charge uses; *All sizes* when none | `rating.rate_size_rows.size_class` · capacity prices per size · `charge_code_amounts.size_class` |
| 11 | now figures | shown | base (`tariff_versions.base_charge` or its base charge code's amount for the size) · price per unit (`rate_tiers.unit_price`; *Billed* when not flat) · minimum (`rate_size_rows.minimum_bill` / `tariff_versions.minimum_bill`) · per item (trash, fire) · charge amount (`charge_code_amounts.amount`) |
| 12 | proposed figures | typed | kept only with the report run; **never written to Plans & Rates** |

## 2 · Process (confirmed) — rate × usage, no pricing engine, no bill, writes nothing

| # | Step | Source |
|---|---|---|
| 1 | Accounts on each chosen schedule | `rating.unit_plan_assignments` → `rating.plan_rate_schedules` → `customers.accounts` open in the period |
| 2 | Accounts carrying each charge code | `rating.plan_charge_rules` → accounts as in 1 |
| 3 | Class | `customers.accounts.account_type` |
| 4 | Capacity | metered: the meter's size on the unit (`assets.size_class`) · trash/fire: items of each size on the unit, counted |
| 5 | **Revenue now (billed)** | issued bills' lines, corrections included (`billing.invoice_lines` → `billing.invoices`): rate schedule = its version's base and usage lines (`tariff_version`); charge code = its lines (`charge`); a line counts in the month its `period_end` falls in |
| 6 | Usage | `metering.monthly_usage` (quantity, unit, by account, service, month) — the history the bill prints |
| 7 | **Revenue proposed** | metered: per month base + usage × price, at least the minimum, at the account's capacity · trash/fire: items × price per item × months · charge code: amount × months |
| 8 | Not worked out | in 1–2 but missing from 5 or 6: *No bills in the period*, *No usage in the period*, *No capacity on file* |

## 3 · Output (confirmed)

One **group per rate schedule or charge code (+ version)** — name · type · service · version and date · capacities · accounts · Now (billed) · Proposed · Change · % — containing a **line per capacity × class**: Capacity · Class · Accounts · Usage (metered, with unit) or Items (trash/fire) · Revenue now (billed) · Revenue proposed · Change · %. A grand total. *Not worked out* counted by reason. *Proposed figures used*, each with its version and date.

## 4 · Confirmed rules (the five open points, PO 2026-10-12: *"this is also correct"*)

1. A bill whose period crosses the start of the chosen months counts in the month its period **ends**.
2. An account with usage but no bill yet is listed under *Not worked out*.
3. Picking an older version changes only the "now" figures and the starting point of the proposed boxes; Revenue now stays the billed revenue.
4. An account whose meter size or cart changed in the period is counted at **today's** size for every month, and the report says so.
5. The number of items (carts) is the items on file; it cannot be typed.

## 5 · How it is built — INSIDE the reporting framework (PO: no custom code)

A standard report definition (`reports` catalogue, `billing` / `billing_readiness`) served by a registered viewer through `runner`, rendered by the standard `ReportViewerPage` — **no page of its own, no route of its own, no `api._VIEWERS` entry**. What the framework lacks is added TO THE FRAMEWORK, generically, so any report can use it:
- **server-declared inputs** in the run response (`controls.inputs`): `select`, `multi`, and `table` (rows of typed values with dependent dropdowns), drawn by the standard viewer; values travel as strings (a table as one encoded string) so the URL, export and run history carry them unchanged;
- the result uses the framework's **grouped rows** (`__kind__: "group"`, levels, subtotals) and **totals row**; KPI tiles for Now / Proposed / Change.

## 6 · Tasks

As confirmed in chat (input reads · the run · module reads through each module's published seam · catalogue card · the screen inside the framework · history/export · tests incl. PostgreSQL and tenant isolation · walk · records, version, changelog).

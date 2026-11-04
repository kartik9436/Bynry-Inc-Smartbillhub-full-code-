# RB-133 — Runbook 33 · Budget billing re-level

> **NAMED BY THE SOURCE, DEFINED BY THE BUILD (7 September 2026).** ⚠ **THIS FILE
> READ *"NAMED, NOT DEFINED"* UNTIL THAT DAY** and said scope, parameters, steps,
> guards, ports and both screens were *not yet defined*. The source still says
> nothing about any of them — **every row below that the source did not give is
> marked *(build)* and is a judgment recorded in `12-governance/02-decision-log.md`,
> not a figure quoted from the source.** The commitment sentence is unchanged and
> is what the build was measured against.

## What it declares

| | |
|---|---|
| **Kind** | **Action** — stated on the same Templates card. ⚠ **AND ITS CENTRAL ACT HAS NO PORT** — see *What it cannot do* below. |
| **Category** (one home, from the fixed list of sixteen) | **Billing** — stated on the Templates wireframe (`RBS-002`, the source's `S148.1`, region 9): *pills: Action (danger), Unavailable (neutral) · Action Billing*. |
| **Tags** | None *(build)*. The source's tag table covers runbooks 1–22 only. |
| **Phase** | 3 |
| **Trigger** | **Manual** *(build)* — the narrowest declaration the commitment supports (*"A clerk sees…"*). A schedule is the obvious guess, because the cadence is six months, and a guess is wider than the source's silence. |
| **Subject and unit of work** | **A budget-billing account** *(build)* — every account whose `account_budget_status` is `enrolled`. `off_budget` is out of scope: it is reachable only by an explicit staff act on `S30` (PO ruling 2026-08-11), and re-levelling somebody a person took off the programme would undo that act by arithmetic. |
| **Step modes** | Two `set` steps then two `per-record` *(build)*. |
| **Result blocks it composes** | **Verdict · KPIs · Records · Action · Downloads** *(build)*. |
| **Ports it holds** | **`queue_notice`, and nothing else** *(build)*. It is not the port this runbook is named after — see below. |
| **Proves** | `BR-RBS-018` (a money-bearing act carries a second approval), `BR-RBS-022` (a fifteenth port is a reviewed interface, not a line), `BR-RBS-006` (the cap refuses the run), `BR-REP-001` (a money tile declares its basis, and a level is `priced`), and hard-won law 2's mirror — **a hold ships with the test that fires when it expires.** |
| **Waits on** | the budget billing capability switched on for the tenant |

## What the source says about it

The source gives one sentence and no more. **Done looks like:** A clerk sees each budget-billing account's current level, the level the last twelve months support, and the change queued behind approval with the customer told first.

## What it cannot do, and why that is the deliverable

⚠ **NOTHING IN THIS PRODUCT MOVES A BUDGET LEVEL, AND THIS RUNBOOK DOES NOT
ADD A DOOR FOR IT.** `interfaces.PORTS` holds fourteen names; `billing`'s single
port is `apply_fee`, which raises a **draft** fee bill. `apps.billing.budget_service.relevel`
exists and is billing's own act — calling it from a runbook would be the
cross-module write `BR-RBS-039` and `G115` refuse, and a fifteenth port is a
**reviewed interface** under `BR-RBS-022`, *"not a line added on the way past"*.
So **step 4 records the refusal by name**, with both figures on the row. That is
`RB-125`'s posture on voiding a plan and `RB-122`'s on suppressing a channel.
`OQ-RBS-1760` carries the question and is **OPEN**.

⚠ **AND THEREFORE NOBODY IS TOLD EITHER — the half that needed a decision.**
The commitment's order is *told first, then changed*. That order is right when a
change can FAIL: a customer warned about a change that then fails is
recoverable, a payment that moves with no warning is not. **It is wrong when the
change is known impossible before the run starts** — and it is, statically —
because the notice would tell a customer their monthly payment is changing when
nothing can change it. So **step 3 holds the notice** and says so on the row.

⚠ **THE HOLD SHIPS WITH ITS EXPIRY TEST, IN THE SAME COMMIT.**
`test_no_port_applies_a_budget_level_and_this_case_fires_the_day_one_does`
asserts BY NAME that no port applies a budget level; the day one is added it
goes RED and names `budget_relevel.py`. Hard-won law 2's mirror
(`DEF-CWP-3925`): a hold with no such test is a promise nobody is keeping.

## Scope — how the set is decided *(build)*

Every `account_budget_status` row with `status = enrolled`, read through
`billing_seam.budget_programme` — which returns the accounts **and the tenant's
own S69 settings in one read**, so a run cannot be handed levels computed under
one setting and a drift band from another.

**Never include: Sample** — one guard *(build)*, absolute and evaluated before
step 1 (`BR-RBS-012`).

⚠ **AN ACCOUNT CARRYING A LEVEL OVERRIDE IS WALKED, NOT GUARDED OUT** *(build,
and it is the tidier build that was rejected)*. A re-level moves `level`; what
the customer PAYS is `effective_level`, which prefers the override — so on such
an account the computed level moves and the payment does not, and the row says
exactly that. The ±30% override bound is measured against the COMPUTED level
(`BR-BIL-017` as `OQ-068` closed it), so guarding these out would leave that
number a year stale and make the next override validated against it.

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

*The source names no parameters for this runbook.* Six are declared *(build)*:

| Parameter | Type | Default | Note |
|---|---|---|---|
| **Averaging window** | Settings | `billing.eligibility_months` | `BR-BIL-017`'s twelve months, READ and never defaulted (`BR-BIL-021`). |
| **Re-level above drift of** | Settings | `billing.relevel_drift_pct` | ±20% seeded. |
| **Re-level no more often than** | Settings | `billing.relevel_cadence_months` | Six months seeded. |
| **Channels** | Enum | `email, then post` | |
| **Most per run** | Integer | **100** | The Product Owner's own figure — `OQ-RBS-1731` CLOSED 2026-09-06, *"1731 … (b) ship 100"*. `BR-RBS-006`: the cap **refuses the run** and never truncates it. |
| **Treat runs within** | Integer | **24** hours | `OQ-RBS-1737`'s frequency control. |

## Steps

| # | Step | Mode | What it answers |
|---|---|---|---|
| 1 | The budget programme | set | Who is enrolled, and under which of the tenant's rules? |
| 2 | The level the last twelve months support | set | What does `budget.compute_level` say, and does `budget.relevel_due` move it — **at cadence** and **past the band**? |
| 3 | Tell the customer | per record · **writes** | Queue the notice — **held while the change is impossible**. |
| 4 | Apply the new level | per record | **Records the refusal.** Reads the second approval and reports it. |

⚠ **THE ARITHMETIC IS BILLING'S AND IS RE-IMPLEMENTED NOWHERE.** The level is
`apps.billing.budget.compute_level` — ❄️ **`GT-24`**, finance-signed: $2,904
over twelve months rounds half-up to **$242**. The trailing actuals come from
`budget_history_for`, the same read `budget_service.relevel` uses, so the number
this runbook shows a clerk and the number billing would write cannot differ.

**Three outcomes and never one *no change*** *(build)*: past the band and at
cadence (**moves**), inside the band, inside the cadence — and a fourth, **not
enough history**, which is not a failure: an account with nine months of bills
under a twelve-month window has no supportable level, and averaging nine would
set a year of payments off a number the tenant's own eligibility rule calls
insufficient. It reports *9/12 months*, which is `budget.eligibility`'s own
sentence.

## Guards — what it may never touch

`queue_notice` is the only port, so a notice is the only thing it could ever
write — and while `engine.acts.LIVE_ENABLED_RUNBOOKS` is empty for the whole
catalogue, it writes nothing at all. It never touches `account_budget_status`,
`invoices`, `invoice_lines`, `payments` or a journal line.

## Produces

Worked, on the seeded Brazos Bend utility, 7 September 2026 — twelve accounts
enrolled through `budget_service.enroll` (billing's own service, nothing typed
into a level), the tenant's averaging window set to 2 months and its drift band
to 5% so two cycles of seeded bills are enough to compute against; **the guards
lifted for the measurement only**, because ten of the twelve are sample records:

| | |
|---|---|
| On budget billing | **12** |
| Levels that should move | **4** |
| Change a month, added up | **$51.00** *(basis: priced)* |
| Inside the band | **8** |
| Not yet due | **0 early · 0 short** |

| Account | Level now | The year supports | Change | What happened |
|---|---|---|---|---|
| `AC-2026-00013` | $268.00 | $282.00 | +$14.00 | 268.00 would become 282.00. This one has to be changed by hand. |
| `AC-2026-00006` | $245.00 | $258.00 | +$13.00 | 245.00 would become 258.00. This one has to be changed by hand. |
| `AC-2026-00040` | $245.00 | $258.00 | +$13.00 | 245.00 would become 258.00. This one has to be changed by hand. |
| `AC-2026-00036` | $179.00 | $190.00 | +$11.00 | 179.00 would become 190.00. This one has to be changed by hand. |

The verdict reads **To do · 4 of 12 levels should move · Nothing was changed and
nobody was told.** The Action block draws **Apply the new levels** in the danger
tier, **disabled**, with *"No door moves a budget level"* — B14 rule 6 for the
tier and rule 33 for the five-word refusal.

⚠ **EVERY MONEY FIGURE DECLARES THE `priced` BASIS** (`BR-REP-001`,
`DEF-RBS-4350`). A budget level is **computed and never posted** — `BR-BIL-011`
is explicit that the monthly posting is the ACTUALS posting and the level never
reaches the ledger as a price — so a tile taking the renderer's `posting`
fallback would sit under a heading it does not belong to.

**Done looks like** (the commitment's own sentence, RB-133, status **VERIFIED
2026-09-07** — `06-backend/tests/test_us_rbs_044_budget_relevel.py`, 24 cases,
six of them first shown failing on the specific wrong build named in each
docstring): A clerk sees each budget-billing account's current level, the level the last twelve months support, and the change queued behind approval with the customer told first.

## Its screens

**Neither frame is drawn, and the runbook needs neither.** The source's screen table stops at runbook 27, so there is no `RBS-004-R33` and no `RBS-006-R33` in `04-docs/05-modules/17-runbooks/wireframes/` and no build sheet to check a build against.

The commitment card names the renderers rather than frames: **`RBS-002` card · `RBS-004` renderer · `RBS-006` result** (the source writes them `S148`, `S150`, `S152`). Both are renderers over the definition and the report, so this runbook needed **no new screen** and **no frontend code at all**.

## Open questions and stated absences

- **`OQ-RBS-1760` — should a fifteenth port move a budget level?** OPEN. The writer exists (`budget_service.relevel`), is audited, and the approval rule is already written; what is missing is only the reviewed door. Nothing is blocked: the runbook ships, produces both figures the commitment asks for, and changes nothing.
- **`OQ-RBS-1759` — the template library cannot draw this card *Unavailable*.** OPEN, and this runbook is the first that needs it. **It is the one template drawn Unavailable**: its card reads *"Budget billing is switched off for you"* and its **+ Add** is disabled carrying *"Needs budget billing"*. The source calls this *"the one card worth arguing about"* — a template needing a capability the tenant has switched off is shown disabled with its reason rather than hidden, because unlike a help article a missing automation is something a utility may want to go and enable. It is the only place in the design that departs from *hide what does not apply*. ⚠ **`selectors.templates()` serves `unavailable_reason: None` for every template and says so in its own docstring**; until the question is answered, a tenant with budget billing off sees this template as *Not added*, and a run of it pins **zero accounts** and says *"Nobody is on budget billing yet"* in those words. Nothing is dangerous; the absence is stated rather than hidden.
- Phase 3 carries it explicitly — *"and runbook 33 when the budget-billing capability exists"*.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. **Every row marked *(build)* is this project's judgment and not the source's**; the commitment sentence and the Kind and Category rows are the source's own. Status of **RB-133: VERIFIED 2026-09-07** — `06-backend/apps/runbooks/definitions/budget_relevel.py`, `06-backend/tests/test_us_rbs_044_budget_relevel.py`.

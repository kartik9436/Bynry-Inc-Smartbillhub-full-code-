# RB-128 — Runbook 28 · Meters past change-out age or never tested

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
| **Kind** | **Check** *(build — the source's own conditional, resolved)*. The source says it waits on `RB-049` for a field order and is **a Check without it**. `RB-049` does not exist, there is no work-order port, so it is built as a Check: **constructed with no ports at all** (`BR-RBS-002`), and its two controls are fix routes rather than writes. What it becomes when `RB-049` arrives is written out in `definitions/meter_change_out.py`'s own docstring. |
| **Category** (one home, from the fixed list of sixteen) | Assets — the source names this as the empty Assets category's first runbook: *"Meters past their change-out age, or never tested."* **It is now that runbook**, so Assets stops being an empty category and gains a filter chip (`BR-RBS-025`). |
| **Tags** | None *(build)*. The source's tag table covers runbooks 1–22 only; inventing tags would put this runbook on filters nobody chose. |
| **Phase** | later |
| **Trigger** | **Manual** *(build)* — the narrowest declaration the commitment supports (*"A clerk sees…"*). A schedule would be a wider declaration than the source makes, and widening one is a change request rather than a lane's decision. |
| **Subject and unit of work** | **A meter** *(build)*. `resolve()` pins every measuring asset the utility owns; the guards decide what is walked. |
| **Step modes** | Two `set` steps then one `per-record` *(build)*. The age and the tests are one walk of the fleet asked two ways; the money and the row are per meter. |
| **Result blocks it composes** | **Verdict · KPIs · Records · Action · Downloads** *(build)*. |
| **Ports it holds** | **None.** A Check is constructed without them. |
| **Proves** | `BR-RBS-002` (a Check has no writer), `BR-RBS-011` (a tenant-relative fix route on every row), `BR-RBS-025` (a category with a runbook gains its chip), and hard-won law 7's *a blind spot carries a number*. |
| **Waits on** | `RB-049` for a field order; **a Check without it** |

## What the source says about it

The source gives one sentence and no more. **Done looks like:** A clerk sees meters older than the utility's change-out age or with no test on file, ranked by revenue at risk, each with Order a test → or Schedule change-out →.

## Scope — how the set is decided *(build)*

Every asset whose type category is `meters` or `sub_meters`, read through
`metering_seam.meter_lifecycle_census` — metering owns assets, so a runbook
never asks `apps.assets` directly.

**Never include** (three guards, absolute, evaluated before step 1 —
`BR-RBS-012`, and each drawn on `RBS-004.4` disabled *with* its reason):

| Guard | Why it is a guard and not a filter inside the read |
|---|---|
| **Sample** | `BR-TEN-056`'s seeded records are not this utility's own. On the demo utility that is 119 of 128 meters. |
| **Retired** | Every retired meter is by definition past its change-out age, so without this the list is the graveyard first and the live fleet underneath. |
| **In the store room** | A spare standing on no service point has never been tested by definition and carries no revenue, so a list ranked by money would end with the whole store room at the bottom for ever. |

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

*The source names no parameters for this runbook.* Two are declared *(build)*:

| Parameter | Type | Value | Note |
|---|---|---|---|
| **Change-out age** | Settings | *(unset)* | ⚠ **DECLARED, AND THE SETTING DOES NOT EXIST.** `assets.change_out_age_years` is not a key this product holds. What it holds is `expected_life_years` **per meter**, and the Assets replacement forecast already counts a meter past life at `install_date + expected_life_years` (B16 §5.1b) — so the step reads that, and this row appears the day Settings gains a utility-wide default. `RB-119`'s `orphan_means` is declared the same way for the same reason. |
| **Never tested means** | Enum | `no test on file` | One choice, and it is the commitment's own words. *Past its test interval* is a THIRD state the source does not name — see below. |

## Steps

| # | Step | Mode | What it answers |
|---|---|---|---|
| 1 | Past change-out age | set | Is this meter's age, in months from its install date (or its purchase date for stock), **strictly greater** than its own expected life? |
| 2 | No test on file | set | Is `last_test_date` absent? |
| 3 | Rank by revenue at risk | per record | One row per meter, with the money — and the money is read **only** for a meter that is already a finding. |

**The ranking is applied when the report is composed**, not in step 3: a
per-record step sees one meter and cannot order a set (`BR-RBS-020`).

## Guards — what it may never touch

It holds no ports, so it can touch nothing. The three scope guards are in the
Scope table above.

## Produces

Worked, on the seeded Brazos Bend utility, 7 September 2026 — **the guards
lifted for the measurement only**, because 119 of the 128 meters are sample
records and the shipped run walks 8:

| | |
|---|---|
| Meters in the fleet | **128** |
| Past their change-out age | **3** — `AST-04412` by 5 months, `AST-04413` by 10 months, `AST-04414` by 1 year 2 months |
| With no test on file | **128** (this utility has recorded no meter test at all) |
| **Cannot be judged on age** | **116 of 128** — 116 record no expected life, 0 record no install date |
| Tested but past their interval | **0** — counted, never raised |
| Revenue at risk | **$19,674.08 a month, across 111 of the 128 found** — the largest single meter is `E-5049` at **$4,590.00** |

⚠ **THE THIRD NUMBER IS THE ONE THAT MATTERS MOST AND IT IS NOT A FINDING.**
*"0 past change-out age"* over a fleet that records no expected life is a clean
bill of health that is a lie, so *cannot be judged* is drawn as a RATIO — **116
of 128** — and the verdict says it in words. Hard-won law 7: a declared blind
spot with no number beside it is indistinguishable from an empty one.

⚠ **REVENUE AT RISK IS A MONTH OF BILLED REVENUE AND NOT A PROJECTION** *(build)*:
what this meter's account was last billed for this meter's service on its most
recent **issued** bill. It is money a customer has actually been charged rather
than a tariff this Check looked up and re-interpreted, which is rating's job.
An account that has never billed reads **Not billed yet** — `None`, never
`0.0000`, and it sorts **below every known figure**, because an unknown sorted
as zero would bury the very meter a clerk should see first.

**Done looks like** (the commitment's own sentence, RB-128, status **VERIFIED
2026-09-07** — `06-backend/tests/test_us_rbs_043_meter_change_out.py`, 25 cases,
five of them first shown failing on the specific wrong build named in each
docstring): A clerk sees meters older than the utility's change-out age or with no test on file, ranked by revenue at risk, each with Order a test → or Schedule change-out →.

## Its screens

**Neither frame is drawn, and the runbook needs neither.** The source's screen table stops at runbook 27, so there is no `RBS-004-R28` and no `RBS-006-R28` in `04-docs/05-modules/17-runbooks/wireframes/` and no build sheet to check a build against.

The commitment card names the renderers rather than frames: **`RBS-002` card · `RBS-004` renderer · `RBS-006` result** (the source writes them `S148`, `S150`, `S152`). Both are renderers over the definition and the report, so this runbook needed **no new screen** and **no frontend code at all** — `RB-020`'s claim, and adding it cost one import line and one tuple line in `apps/runbooks/definitions/__init__.py`.

## Open questions and stated absences

- **No wireframes and no build sheets.** The two instances are not drawn; the source's screen table stops at runbook 27. Nothing was inferred from that absence — the report composes the five blocks the renderers already draw.
- **`RB-049` does not exist**, so *Order a test →* and *Schedule change-out →* are LINKS to `assets`, where a clerk records a test or schedules a change-out by hand. They are working doors, not refusals. `RB-049` registers *work order* and *inspection* as subject types on the contract; when it lands, this runbook becomes an **Action** — a new version, because `BR-RBS-001` says a kind never changes — and needs a port that raises a field order in `work`, which does not exist and is a reviewed interface (`BR-RBS-022`). The whole chain is in `definitions/meter_change_out.py`'s docstring.
- **A meter TESTED but past its test interval is not one of the two groups this card names.** `BR-AST-007`'s derived overdue state is real and is drawn on the Assets registry already; its COUNT travels as a tile so a clerk can see it, and no row is raised. Adding it as a third group is a change request.
- **Assets is no longer one of the five empty categories.** It has one runbook, so the chip is drawn (`RB-019`, `BR-RBS-025`).
- Runbook 5, *Abnormal readings*, already **touches** Assets as a tag.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. **Every row marked *(build)* is this project's judgment and not the source's**; the commitment sentence and the Kind and Category rows are the source's own. Status of **RB-128: VERIFIED 2026-09-07** — `06-backend/apps/runbooks/definitions/meter_change_out.py`, `06-backend/tests/test_us_rbs_043_meter_change_out.py`.

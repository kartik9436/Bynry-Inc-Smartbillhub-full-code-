# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · CLAUDE.md hard rule 1 ·
#           B4/B5 ❄️ FROZEN (a runbook prices nothing itself)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → rating — plans, rate schedules, tariffs. READ ONLY.

The coverage grid and the test bill read the tenant's own pricing here and
**call the existing rating engine** rather than reimplementing any part of it.

⚠ **A RUNBOOK PRICES NOTHING ITSELF.** If a coverage cell disagrees with a
golden test, the defect is in the ENGINE or in the FIXTURE, never in the runbook
(`CR-075` §2). Nothing in this module may reach past this seam and compute a
charge: B4 and B5 are ❄️ FROZEN, and a second implementation of signed money
math is the one way this module could do real damage **without writing a single
row** — a coverage grid that quietly disagreed with the engine would be believed,
because looking right is the whole point of it.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; wave F brings the test bill and wave G the
coverage grid, each with the reads it actually needs. A selector written here
now would be a function nothing calls (hard-won law 2), and naming one in prose
that `rating` does not expose would fail `G20` — the guard that caught
`DEF-075`. What this module will need and `rating` does not offer today is
inventoried in `17-runbooks/13-selector-inventory.md`, and **`rating` adds each
of them** — never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="rating",
    pair="operations → rating",
    crosses="plans, rate schedules, tariffs",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────
#
# Added with `definitions/configuration_check.py` in the same commit. Every
# call below resolves a selector `rating` already publishes:
# `apps.rating.selectors.plan_queryset`, `apps.rating.selectors.plan_rate_schedules`,
# `apps.rating.selectors.in_force_version`, `apps.rating.selectors.version_structure`
# and `apps.rating.selectors.tax_pricing_gap`.


def plan_coverage(on_date) -> list[dict[str, object]]:
    """Per (plan, service): is a version IN FORCE on the date, and where does the
    block ladder stop? — runbook 1 steps 4 and 5 in one walk.

    ⚠ **THE TARIFF ROW NEVER LEAVES THIS FILE.** `plan_rate_schedules` returns
    the `Tariff` row rather than a dict on purpose — the caller must resolve the
    version in force at the SERVICE date (`BR-RAT-007`) — so the resolution
    happens HERE and the runbook receives plain data. Handing a foreign model
    object back to a step would put `rating`'s ORM one attribute access away
    from every runbook, which is the coupling `BR-RBS-039` exists to prevent
    even where no import appears.

    `top_block_to` is the last tier's ceiling, or **`None` meaning unbounded**.
    `BR-RAT-032` makes the last tier's `to_qty` NULL — a flat tariff is a single
    `0 → ∞` row — so a ladder whose last tier carries a NUMBER stops somewhere,
    and usage above it cannot be priced at all. That is what runbook 1 step 5
    reports, and it is a fact about the ladder rather than an estimate.
    """
    from apps.rating import selectors as rating_selectors

    rows: list[dict[str, object]] = []
    for plan in rating_selectors.plan_queryset().order_by("name", "id"):
        for schedule in rating_selectors.plan_rate_schedules(plan.id):
            version = rating_selectors.in_force_version(schedule["tariff"], on_date)
            structure = rating_selectors.version_structure(version)
            tiers = structure.get("tiers") or []
            top = tiers[-1] if tiers else None
            rows.append(
                {
                    "plan_id": str(plan.id),
                    "plan_name": plan.name,
                    "service_code": schedule["service_code"],
                    "has_version_in_force": version is not None,
                    "tier_count": len(tiers),
                    "top_block_to": None if top is None else top.get("to_qty"),
                    "unit": structure.get("unit"),
                }
            )
    return rows


def tax_regions() -> dict[str, int]:
    """How many tax authorities this tenant holds, and how many are PRICED.

    ⚠ **AN AUTHORITY WITH NO PRICE IS A DIFFERENT FAULT FROM NO AUTHORITY AT
    ALL, AND THIS SEAM KEEPS THEM APART.** Jurisdictions are written at
    provisioning and rates are not, so a tenant that declined the sample data
    has authorities and no rates and **issues every bill with no tax** — the
    silence `tax_pricing_gap` was written for. Runbook 1 step 3 reads no
    authority as a BLOCKER and a rate-less authority as a WARNING, because a
    utility that genuinely charges no tax is a real and lawful state and this
    Check must not refuse it (decision log 2026-08-28).
    """
    from apps.rating import selectors as rating_selectors

    return dict(rating_selectors.tax_pricing_gap())


# ── CR-075 wave F · the read runbook 23 makes (US-RBS-004) ────────────────
#
# ⚠ **THE TEST BILL'S *PRICING* CALL IS NOT HERE, AND THAT IS DELIBERATE.**
# `10-execution-plan.md` `F2` says *"step 2 calls the rating engine's own path.
# A seam to rating, in the register"*. In the code that chain is billing's —
# `billing.runs.price_account` measures the account and then calls
# `billing.rating_seam.price_bill`, which is the door into `apps.rating.engine`
# — so the call lives in `billing_seam.price_account_as_the_run_would`, where
# its own docstring records the divergence in full. Putting it in a file whose
# `SeamDeclaration` reads `operations → rating` would be a sentence about the
# boundary that is not true of the code behind it (hard-won law 1).
#
# **What this seam carries for runbook 23 is step 3's half: the fact that turns
# a tax LINE into a tax SENTENCE.** A priced line already knows its own
# quantity, unit and unit price, so a usage or base line explains itself; a tax
# line carries only its `tax_id`, and *"6.25% of the water and sewer charges"*
# lives here, in the module that owns `taxes`.


def tax_facts(tax_ids) -> dict[str, dict[str, object]]:
    """`{tax_id: {name, rate, kind, base…}}` for the taxes on ONE priced bill.

    Resolved one at a time through `rating`'s own `tax_or_404` + `tax_row`,
    which is the door every tax screen already reads — rather than a queryset
    of `rating.models.Tax` assembled here, which would be this module owning a
    read of another module's table (`BR-RBS-039`).

    ⚠ **A MISSING ID IS SKIPPED, NOT GUESSED.** `BR-BIL-069` allows a tax line
    whose rule named a `rate_override` for a jurisdiction with no `taxes` row
    behind it, so an unresolvable id is a REAL and documented state. The line
    then explains itself without a percentage instead of claiming one, because a
    rate invented for a tax authority is the one number on a bill nobody may
    guess.

    ⚠ **`rate_display` IS RATING'S OWN 2-DECIMAL PERCENTAGE** (`BR-RAT-087`,
    hard rule 2: percentages stored to 6, displayed to 2) — *"6.25%"* and never
    *"0.062500"*. This seam does not scale, round or format it; it carries what
    `rating` already publishes, because a second formatter is a second answer.
    """
    from apps.rating import selectors as rating_selectors
    from core import errors as core_errors

    facts: dict[str, dict[str, object]] = {}
    for tax_id in dict.fromkeys(str(t) for t in tax_ids if t):
        try:
            row = rating_selectors.tax_row(rating_selectors.tax_or_404(tax_id))
        except core_errors.NotFoundError:
            continue
        facts[tax_id] = {
            "name": row.get("bill_label") or row.get("name"),
            "rate_display": row.get("rate_display"),
            "kind": row.get("kind"),
            "base_includes_usage": row.get("base_includes_usage"),
            "base_includes_base": row.get("base_includes_base"),
            "applies_to_services": row.get("applies_to_services") or [],
        }
    return facts


# ── CR-075 wave G · the read runbook 24 makes (US-RBS-005) ────────────────
#
# Added with `definitions/coverage_grid.py` in the same commit. It resolves
# `apps.rating.selectors.plan_queryset`, which `plan_coverage` above already
# walks — the same selector, asked a smaller question.


def plan_names() -> dict[str, str]:
    """`{plan_id: name}` for every plan this tenant holds.

    ⚠ **THIS EXISTS FOR B14 RULE 31 AND FOR NOTHING ELSE.** *No database id is
    ever the visible value of a field*, and the coverage grid groups its cells
    BY PLAN — so the group a clerk reads has to be *Residential water* and never
    a uuid. `plan_coverage` above answers the same mapping as a by-product, but
    only for plans that carry a rate schedule; a plan with none is exactly the
    plan a go-live grid needs to show, so it is asked separately rather than
    filtered out of an answer written for another question.
    """
    from apps.rating import selectors as rating_selectors

    return {
        str(plan.id): plan.name
        for plan in rating_selectors.plan_queryset().order_by("name", "id")
    }


# ── CR-075 wave S · the three reads runbook 16 makes (US-RBS-028) ─────────
#
# Added with `definitions/rate_change_preview.py` in the same commit. All three
# resolve `apps.rating.runbook_reads`, which `rating` publishes in that same
# commit — the third kind of module `apps/payments/runbook_reads.py` already is.
#
# ⚠ **AND THE PRICING CALL *IS* HERE, WHICH IS THE OPPOSITE OF WAVE F's
# ARRANGEMENT AND IS DELIBERATE.** The note above records that runbook 23's
# pricing lives in `billing_seam`, because the test bill prices AN ACCOUNT and
# that chain is billing's — gather, measure, then `rating_seam.price_bill`.
# Runbook 16 prices A QUANTITY AGAINST A VERSION THAT IS NOT IN FORCE, and no
# billing path can reach one: `BR-RAT-007` resolves a version by SERVICE DATE
# and `BR-RAT-031` excludes a dateless draft from that lookup by name, *"a
# dateless row has no window and must never price anything"*. The door that CAN
# is `selectors.pricing_inputs_for_version`, split out by `DEF-434` for exactly
# this, and it is rating's. So the pair reads: an ACCOUNT is priced through
# billing, a VERSION through rating, and neither is a copy of the other.


def draft_schedules() -> list[dict[str, object]]:
    """Every rate schedule carrying a DRAFT version — `RB-116`'s scope picker.

    `apps.rating.runbook_reads.draft_schedules`. `BR-RAT-031`: a NULL
    `effective_from` IS the draft and `uq_tariff_versions_one_draft` allows
    exactly one per tariff, so *"the draft"* is a fact rather than a convention.

    A schedule with nothing activated behind it comes back `comparable: False`
    rather than being dropped — a first tariff has no baseline, which is a real
    state, and a picker that hid it would leave a manager hunting for a draft
    they can see on the Plans & Rates screen.
    """
    from apps.rating import runbook_reads as rating_runbook_reads

    return [dict(one) for one in rating_runbook_reads.draft_schedules()]


def schedule_change(*, version_id, service_date) -> dict[str, object]:
    """Clause by clause, what the draft changes about the version in force.

    `apps.rating.runbook_reads.schedule_change`. This is the **Why** column on
    `RB-116`'s biggest-mover table, and the card's design note is why it exists:
    *"Why on each mover names the clause of the draft that did it, so a tariff
    can be adjusted before it is adopted rather than defended after."*

    ⚠ **THE CLAUSES AND THE PRICES COME FROM ONE READING OF ONE PROJECTION.**
    Both sides are `pricing_inputs_for_version`, which is `pricing_inputs`' own
    body — so the clause a row names and the money the engine charged for it
    cannot come from two different readings of the same rows.
    """
    from apps.rating import runbook_reads as rating_runbook_reads

    return dict(
        rating_runbook_reads.schedule_change(version_id=version_id, service_date=service_date)
    )


def reprice_under_draft(*, version_id, rows, service_date) -> dict[str, object]:
    """Each quantity priced TWICE — under the draft and under what is in force.

    `apps.rating.runbook_reads.reprice_under_draft`, which calls
    `apps.rating.engine.price_period` — the same call a bill makes — and writes
    nothing at all. `US-RBS-028` `TC-RBS-028.3`: *"the pricing path is the
    rating engine's, identical to a real run"*, and its *must first fail on* is
    **a second implementation**.

    ⚠ **NO BILL NUMBER IS CONSUMED AND NO INVOICE MOVES** (`TC-RBS-028.2`).
    `price_period` is documented PURE — *"no I/O, no clock, no writes"* — and
    stage 6, where a draft is stored and `core.numbering` spends a number, is
    billing's and is not on this path.

    ⚠ **WHAT TRAVELS IS THE DIFFERENCE, NOT THE PROPOSED TOTAL ALONE**, and that
    is what makes the comparison sound: both sides are priced by one engine from
    one quantity, so the base-charge precedence (`DEF-154` — the plan's figure
    where it states one, the schedule's where it does not) cancels out of the
    subtraction instead of appearing as a change nobody proposed.
    """
    from apps.rating import runbook_reads as rating_runbook_reads

    return dict(
        rating_runbook_reads.reprice_under_draft(
            version_id=version_id, rows=rows, service_date=service_date
        )
    )

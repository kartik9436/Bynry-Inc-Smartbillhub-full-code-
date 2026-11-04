# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 — the Taxes & fees detail page's `Plans` and `Audit` tab
#           bodies. PO ruling 2026-09-10, verbatim: *"build"* (decision log,
#           THE FOUR EMPTY TAB BODIES GET BUILT). Both tabs shipped rendering
#           ONE SENTENCE saying they could not do their job.
#           Screens: S13 · `?tab=plans` · `?tab=audit`
# Rules:    BR-RAT-113 (a plan carries a tax through its bound AUTHORITY or
#           through an explicit ATTACHMENT — add-only, nothing detaches) ·
#           BR-RAT-104 (a live tax is corrected with a new dated row carrying a
#           reason, never edited in place) · BR-RAT-087 / DEF-364 (the SERVER
#           renders a percent; the client never scales a stored fraction) ·
#           DEF-367 (an actor on the object's OWN row, `{id, name}`) ·
#           CLAUDE.md hard rule 4 (financial immutability, and its 2026-09-02
#           narrowing: `audit_log` is PRUNED)
# Tests:    this file
# Impacts:  apps/rating/selectors.{tax_plans,tax_correction_chain} ·
#           apps/rating/services.correct_tax (stamps `corrected_by`) ·
#           apps/rating/models.Tax.corrected_by · rating migration 0032
# ───────────────────────────────────────────────────────
"""The two reads the tax detail's empty tabs needed, and the actor column.

── PROVED RED FIRST (hard-won law 7), through `pytest`, which is the harness
── that runs them — and here is what each printed at HEAD ────────────────────

* `test_tax_plans_names_each_plan_and_how_it_reaches` —

      AttributeError: module 'apps.rating.selectors' has no attribute
      'tax_plans'

  and, with a `tax_plans` that returned the plan names WITHOUT the mechanism
  (the shape a lane would reach for first, since `used_by_plans` already
  counts these same rows):

      AssertionError: assert 'attached' == 'jurisdiction'

  — the plan that BINDS the authority and also ticks the levy. `BR-RAT-113`
  says a jurisdiction-mandated tax stays on the bill *"whether or not anyone
  ticked it"*, so reporting the attachment would tell a clerk they can detach
  a tax they cannot.

* `test_tax_correction_chain_reads_both_rows_newest_first` —

      AttributeError: module 'apps.rating.selectors' has no attribute
      'tax_correction_chain'

* `test_a_correction_records_who_filed_it` — with the stamp removed from
  `services.correct_tax`:

      AssertionError: assert None is not None
       +  where None = {...}['corrected_by']

  which is the whole point of rating 0032: `correct_tax` writes two
  `audit_log` rows naming the same person, and reading the `BY` column from
  there would lose it on the retention prune.

* `test_the_row_nobody_corrected_carries_no_reason_and_no_actor` — asserts the
  ABSENCE, so a later lane that "helpfully" back-fills history from
  `audit_log` goes red here rather than shipping invented authorship.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.rating import models as rating_models
from apps.rating import selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

#: Every jurisdiction here is prefixed for `test_cr013_p4_tax_model.py`'s own
#: reason, quoted: the `brazos` fixture already provisions two of the PO's five
#: ruled Texas rows at provisioning time, and a helper reaching for an existing
#: authority by name would hang these rows off the SEEDED one — where
#: `_authority_tax` picks the oldest row per authority, so every assertion
#: would silently measure a rate nobody in this file set up.
PREFIX = "CR087 · "


def a_tax(tenant, authority, **fields):
    """One `taxes` row on an authority OF ITS OWN — never a shared one."""
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=f"{PREFIX}{authority}"
    )
    fields.setdefault("kind", "percent")
    fields.setdefault("rate", Decimal("0.062500"))
    return (
        rating_models.Tax.objects.create(tenant=tenant, jurisdiction=jurisdiction, **fields),
        jurisdiction,
    )


def units_on(actor, tenant, plan, count, *, closed=0):
    """`count` CURRENT unit assignments on this plan, plus `closed` historic
    ones — the historic rows exist so the count proves it reads `assigned_to`
    and not simply every row that ever existed.

    ⚠ **THE NUMBERS ARE THIS FILE'S OWN AND NOT THE BLUEPRINT'S.** B14 rule 37
    (PO 2026-09-10): *"Treat every number drawn in a wireframe as an
    illustration, never a fact to build to"*, and it names a test asserting a
    drawn figure as the first thing it rules out. The frame draws `74`, `12`
    and `1`; those say a unit count goes in that column and nothing about what
    any real row holds.
    """
    from datetime import date

    premises = make_premises(actor)
    for index in range(count + closed):
        unit = make_unit(actor, premises["id"], label=f"{plan.name[:6]}-{index}")
        rating_models.UnitPlanAssignment.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            rate_plan=plan,
            plan_version=1,
            assigned_from=date(2026, 1, 1),
            assigned_to=None if index < count else date(2026, 6, 1),
            source="import",
        )


# ══════════════════════════════════════════════════════════════════════════
# `Plans` — WHICH plans carry this tax, and HOW each one gets it
# ══════════════════════════════════════════════════════════════════════════


def test_tax_plans_names_each_plan_and_how_it_reaches(brazos, dana):
    """The drawn table's three columns: PLAN · REACHED BY · UNITS.

    Three plans, one per shape, so the mechanism column is proved in both
    directions and the both-shapes plan is proved to report the binding.
    """
    with tenant_ctx(brazos):
        tax, jurisdiction = a_tax(brazos, "Texas State")
        bound = make_plan(brazos, name=f"{PREFIX}Residential")
        attached = make_plan(brazos, name=f"{PREFIX}Commercial")
        both = make_plan(brazos, name=f"{PREFIX}Industrial")

        # Shape 1 — the plan binds the AUTHORITY (BR-RAT-113 / BR-RAT-096).
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=bound, jurisdiction=jurisdiction
        )
        # Shape 2 — the plan attaches THIS ONE catalogue row.
        rating_models.PlanTaxRule.objects.create(tenant=brazos, rate_plan=attached, tax=tax)
        # Both, which the model's check constraint permits per PLAN because it
        # only bounds a ROW.
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=both, jurisdiction=jurisdiction
        )
        rating_models.PlanTaxRule.objects.create(tenant=brazos, rate_plan=both, tax=tax)

        units_on(dana, brazos, bound, 3, closed=1)
        units_on(dana, brazos, attached, 1)
        # `both` gets none, so a plan with no current assignment reads 0 rather
        # than being dropped from the table — a plan that carries a tax and
        # reaches nobody today is exactly what a clerk wants to see.

        rows = selectors.tax_plans(str(tax.id))

    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {
        f"{PREFIX}Residential",
        f"{PREFIX}Commercial",
        f"{PREFIX}Industrial",
    }
    assert by_name[f"{PREFIX}Residential"]["reached_by"] == "jurisdiction"
    assert by_name[f"{PREFIX}Commercial"]["reached_by"] == "attached"
    # ⚠ THE BINDING WINS. A plan that binds the authority AND ticks the levy is
    # reached by the binding: BR-RAT-113 makes the mandated half the one that
    # cannot be removed, so naming the attachment would offer a clerk a detach
    # that does not exist.
    assert by_name[f"{PREFIX}Industrial"]["reached_by"] == "jurisdiction"
    # UNITS, not accounts — blueprint page 35, and the closed assignment is not
    # counted.
    assert by_name[f"{PREFIX}Residential"]["units"] == 3
    assert by_name[f"{PREFIX}Commercial"]["units"] == 1
    assert by_name[f"{PREFIX}Industrial"]["units"] == 0
    # Sorted by name, so the table is stable between reads (IS-2).
    assert [row["name"] for row in rows] == sorted(by_name)
    # B14 rule 31 — an id is served for linking and is never the visible value;
    # the NAME is what the column renders.
    assert all(row["id"] for row in rows)


def test_a_tax_no_plan_carries_reads_as_an_empty_table(brazos):
    """The drawn state *Bound nowhere*: *"No plan binds this authority, so this
    tax reaches nobody through a plan."* An empty list, never a fabricated row.
    """
    with tenant_ctx(brazos):
        tax, _jurisdiction = a_tax(brazos, "Unbound County")
        assert selectors.tax_plans(str(tax.id)) == []


def test_tax_plans_never_counts_another_authoritys_attachments(brazos):
    """`tax_row`'s own guard, one function over: with attachment rows in the
    table, an unguarded `Q(jurisdiction_id=None)` matches every attachment of
    every tax. A tax with NO authority must not inherit them."""
    with tenant_ctx(brazos):
        authored, jurisdiction = a_tax(brazos, "Bexar County")
        orphan = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=None, name="Orphan fee", kind="percent"
        )
        plan = make_plan(brazos, name=f"{PREFIX}Only the county's")
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )
        rating_models.PlanTaxRule.objects.create(tenant=brazos, rate_plan=plan, tax=authored)

        assert selectors.tax_plans(str(orphan.id)) == []
        assert len(selectors.tax_plans(str(authored.id))) == 1


# ══════════════════════════════════════════════════════════════════════════
# `Audit` — what the rate has been, and who changed it
# ══════════════════════════════════════════════════════════════════════════


def test_tax_correction_chain_reads_both_rows_newest_first(brazos, dana):
    """The drawn table: two rows, newest first, a reason on the correction and
    a dash on the row nobody corrected.

    The worked figure is `correct_tax`'s own: a rate typed as `0.625000`
    (62.5 %) instead of `0.062500` (6.25 %). Correcting it mints a second row
    over the SAME window; both stay readable for ever.
    """
    today = _today(brazos)
    with tenant_ctx(brazos):
        wrong, _jurisdiction = a_tax(
            brazos,
            "Texas State",
            name="TX State Utility Tax",
            rate=Decimal("0.625000"),
            effective_from=today - timedelta(days=30),
        )
        corrected = services.correct_tax(
            dana,
            str(wrong.id),
            {"reason": "State rate increase, HB-1441", "rate": "0.062500"},
        )
        chain = selectors.tax_correction_chain(str(wrong.id))

    assert len(chain) == 2
    newest, original = chain
    # NEWEST FIRST, whichever row of the chain was asked for.
    assert newest["id"] == corrected["id"]
    assert newest["is_current"] is True
    assert original["id"] == str(wrong.id)
    assert original["is_current"] is False
    # RATE — the SERVER's display string (BR-RAT-087 / DEF-364). The client
    # never turns `0.0625` into `6.25%`.
    assert newest["rate_display"] == "6.25%"
    assert original["rate_display"] == "62.50%"
    # WHY IT CHANGED — the operator's own words, on the row that carries them.
    assert newest["correction_reason"] == "State rate increase, HB-1441"
    # ⚠ THE WINDOW IS THE SAME ON BOTH ROWS. A correction restates the window;
    # a change would move it. The drawn EFFECTIVE column reads the same date
    # twice for exactly this reason.
    assert newest["effective_from"] == original["effective_from"]


def test_a_correction_records_who_filed_it(brazos, dana):
    """The `BY` column, and it is a COLUMN.

    ⚠ **NOT AN `audit_log` LOOKUP.** `correct_tax` writes two audit rows naming
    this same person, and `audit_log` is pruned on a retention schedule (hard
    rule 4's 2026-09-02 narrowing), so a `BY` column sourced from there loses
    its authors on the prune with nothing raising. It is stored on the row the
    tab draws.
    """
    today = _today(brazos)
    with tenant_ctx(brazos):
        wrong, _jurisdiction = a_tax(
            brazos, "Bexar County", name="Local", effective_from=today - timedelta(days=30)
        )
        services.correct_tax(dana, str(wrong.id), {"reason": "Filed in error", "rate": "0.02"})
        chain = selectors.tax_correction_chain(str(wrong.id))

    actor = chain[0]["corrected_by"]
    assert actor is not None
    assert actor["id"] == str(dana.id)
    # DEF-367's shape — `{id, name}`, so a name that cannot be resolved is a
    # stated absence and never a uuid at a person (B14 rule 31).
    assert actor["name"] == "System_Admin"


def test_the_row_nobody_corrected_carries_no_reason_and_no_actor(brazos, dana):
    """The drawn state *One version*: *"`First recorded`, and a dash where
    nobody was stored. History is never filled in backwards."*

    ⚠ **THIS ASSERTS AN ABSENCE ON PURPOSE.** The plausible "improvement" is to
    fill the original row's author from `audit_log`, which would invent
    authorship for every row written before rating 0032 — and would read as a
    fact. This goes red on that.
    """
    today = _today(brazos)
    with tenant_ctx(brazos):
        wrong, _jurisdiction = a_tax(
            brazos, "Harris County", name="Local", effective_from=today - timedelta(days=30)
        )
        services.correct_tax(dana, str(wrong.id), {"reason": "Filed in error", "rate": "0.02"})
        chain = selectors.tax_correction_chain(str(wrong.id))

    original = chain[1]
    assert original["correction_reason"] is None
    assert original["corrected_by"] is None


def test_an_uncorrected_tax_is_a_chain_of_one(brazos):
    """A tax nobody has corrected still has a history: itself."""
    with tenant_ctx(brazos):
        tax, _jurisdiction = a_tax(brazos, "Travis County", name="Local")
        chain = selectors.tax_correction_chain(str(tax.id))

    assert len(chain) == 1
    assert chain[0]["id"] == str(tax.id)
    assert chain[0]["is_current"] is True
    assert chain[0]["correction_reason"] is None


def _today(tenant):
    from apps.rating import seams as rating_seams

    with tenant_ctx(tenant):
        return rating_seams.tenant_today()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-087 · PO ruling 2026-09-10 (*"build"*) · conformance
#         04-docs/05-modules/06-rating/conformance/CR-087-p034-tax-plans.md and
#         CR-087-p036-tax-audit.md
# generated: 2026-09-10 by the CR-087 tax-screens maintenance lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: none — both reads are rating-owned tables only, and the one
#            cross-module read (`identity.User` display names) goes through
#            `seams.user_display_names`, which already exists for DEF-367.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

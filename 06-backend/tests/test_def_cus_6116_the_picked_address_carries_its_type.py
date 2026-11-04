# ── Trace ──────────────────────────────────────────────
# Defect:   `DEF-CUS-6116` — New Connect step 2 re-asks the PREMISE TYPE over an
#           address already on file. Town, state and postcode came back filled
#           from the picked record; the type came back EMPTY and was asked
#           again — **and a clerk can answer it differently from the record.**
# Rules:    CLAUDE.md hard rule 8 / BR-MET-1161 (an address is stored on
#           `premises` and NOWHERE else, and everything else WALKS to it) ·
#           hard rule 1 (tenant scoping) · B14 rule 31 (no database id is a
#           visible value) · BR-MET-034 (the premises type is the tenant's own
#           reference row)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The set a picked address carries is DECLARED, and held against the model.

⚠ **THE KEYSTROKE IS NOT THE POINT; THE DIVERGENCE IS.** A clerk answering
*apartment block* over a record that says *single family* puts two answers in
the product for one fact about one building — and step 3's common-area rule
(`BR-MET-1179`) then reads the clerk's answer rather than the building's.

⚠ **THIS IS THE SECOND FIELD TO STOP TRAVELLING SILENTLY, WHICH IS WHY THE TEST
IS SHAPED THIS WAY.** `DEF-CUS-6057` was the SERVICE LIST: picking an address
copied four fields and not what that address offers, so every meter on the build
was refused at the last press. Both times **neither side was wrong** — the
picker served honest fields and the wizard copied honest fields — and both times
every test on both sides passed, because **nothing compared the set that travels
against what a `premises` row actually holds.**

So the assertion is not *"the type is served"*. It is
`TRAVELS_WITH_AN_ADDRESS` held against `metering.Premises` itself, which is
`SignupWizard.test.tsx`'s eleven services in another language: a list a screen
depends on, asserted against the thing it is a list OF, so the day somebody adds
a fact to `premises` the question *does this travel?* is asked out loud.

RED-FIRST PROOF (r11 step 2d). Each case was run against the pre-fix code and
its failure quoted before it was trusted green — the type case fails with
`KeyError: 'premises_type'`, and the declared-set case fails naming the field
that stopped travelling.
"""

from __future__ import annotations

import pytest

from apps.metering import address_picker
from apps.metering import models

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _estate(actor):
    """A block whose type the register KNOWS, and a field whose type it does not."""
    tower = make_premises(
        actor,
        address_line="212 Balcones Drive",
        city="Katy",
        state="TX",
        postal_code="77494",
        premises_type="apartment_complex",
    )
    field = make_premises(
        actor,
        address_line="9 Cypress Row",
        city="Katy",
        state="TX",
        postal_code="77494",
    )
    return tower, field


def test_a_picked_address_carries_the_kind_of_property_it_is(brazos, dana):
    """`DEF-CUS-6116` — the premise TYPE travels, as its CODE."""
    with tenant_ctx(brazos):
        _estate(dana)
        row = address_picker.page_rows(address_picker.search(q="Balcones"))[0]
        # ⚠ **A REAL VALUE, NEVER `"premises_type" in row`** — `DEF-CUS-3653`'s
        # lesson: an absence is invisible to every check this repo has, and a
        # key that exists holding None is exactly the state this defect was.
        assert row["premises_type"] == "apartment_complex"
        # B14 rule 31 — the CODE is what a picker holds; the uuid is not on the
        # payload at all, so a screen cannot render it by accident.
        assert str(row["premises_type"]) != str(
            models.Premises.objects.get(address_line="212 Balcones Drive").premises_type_id
        )


def test_an_address_whose_type_the_register_never_asked_answers_None(brazos, dana):
    """`DEF-762`'s distinction, one column along: **`None` is *nobody has been
    asked*, and it is not a default to invent.**

    A premises with no type leaves the question to the clerk — which is the
    right question over a record that has no answer. Collapsing it to the first
    option here would write a guess onto a building.
    """
    with tenant_ctx(brazos):
        _estate(dana)
        # ⚠ Written directly, because `make_premises` fills the column with the
        # tenant's first type — so the unasked state cannot be reached through
        # the front door. The same reason `DEF-CUS-6057`'s own null case in
        # `test_cr094_lane_e_address_is_picked.py` writes `services_available`
        # by hand, and the first draft of THIS case asserted `None` against a
        # helper that had quietly answered `single_family`.
        models.Premises.objects.filter(address_line="9 Cypress Row").update(
            premises_type=None
        )
        row = address_picker.page_rows(address_picker.search(q="Cypress"))[0]
        assert row["premises_type"] is None


def test_every_fact_declared_to_travel_is_a_real_field_of_premises(brazos, dana):
    """**The declared set is held against the MODEL, not against this payload.**

    A name in `TRAVELS_WITH_AN_ADDRESS` that `metering.Premises` does not have
    is a fact that cannot travel and nobody noticed — a column renamed, or a
    list written from memory. This is the half a payload check cannot do,
    because a payload agrees with whatever built it.
    """
    fields = {f.name for f in models.Premises._meta.get_fields()}
    for name in address_picker.TRAVELS_WITH_AN_ADDRESS:
        assert name in fields, (
            f"{name!r} is declared to travel with an address and is not a field of "
            "metering.Premises — either the column was renamed or the list is wrong"
        )


def test_every_fact_declared_to_travel_is_actually_on_the_payload(brazos, dana):
    """The other half: a field on the list that `row()` does not serve.

    ⚠ **THIS IS THE CASE THAT WOULD HAVE CAUGHT BOTH DEFECTS.** `DEF-CUS-6057`
    and `DEF-CUS-6116` are one shape twice — a fact the register holds that
    stopped at the seam — and each was found by a person walking the wizard in
    a browser, eight steps in, weeks apart.
    """
    with tenant_ctx(brazos):
        _estate(dana)
        row = address_picker.page_rows(address_picker.search(q="Balcones"))[0]
        missing = [
            name for name in address_picker.TRAVELS_WITH_AN_ADDRESS if name not in row
        ]
        assert not missing, (
            f"{missing} are declared to travel with an address and address_picker.row() "
            "does not serve them, so a wizard that picks an address asks for them again"
        )


def test_hard_rule_1_the_type_of_another_tenants_premises_is_not_reachable(
    brazos, dana, lonestar, erin
):
    """A new column on a tenant-scoped read is a new way to leak one."""
    with tenant_ctx(lonestar):
        # ⚠ `services_available=["water"]` because lonestar does not sell
        # electric, and `create_premises` refuses a service a tenant has not
        # enabled by name (`metering.service_not_enabled`). The sibling case in
        # `test_cr094_lane_e_address_is_picked.py` says the same thing the same
        # way.
        make_premises(
            erin,
            address_line="212 Balcones Drive",
            city="Ridge",
            services_available=["water"],
            premises_type="apartment_complex",
        )
    with tenant_ctx(brazos):
        _estate(dana)
        rows = address_picker.page_rows(address_picker.search(q="Balcones"))
        assert len(rows) == 1


def test_the_type_is_read_without_a_query_per_row(brazos, dana, django_assert_num_queries):
    """`NFR-3`'s cost half — the JOIN, asserted rather than commented.

    ⚠ **AN FK READ PER ROW IS 50 QUERIES ON A PAGE OF 50**, at a counter, while
    a clerk types. `search()` carries `select_related("premises_type")` and this
    is what stops that being removed as a tidy-up: shaping a whole page must
    cost the SAME number of queries whatever the page holds.
    """
    with tenant_ctx(brazos):
        for n in range(6):
            make_premises(
                dana,
                address_line=f"{n} Sixfold Way",
                city="Katy",
                state="TX",
                postal_code="77494",
                premises_type="apartment_complex",
            )
        page = address_picker.search(q="Sixfold")
        rows = list(page)
        assert len(rows) == 6
        # One for the units of the page, and nothing per row for the type.
        with django_assert_num_queries(1):
            shaped = address_picker.page_rows(rows)
        assert [one["premises_type"] for one in shaped] == ["apartment_complex"] * 6

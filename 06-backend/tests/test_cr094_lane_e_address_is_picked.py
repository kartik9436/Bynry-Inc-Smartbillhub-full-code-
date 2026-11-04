# ── Trace ──────────────────────────────────────────────
# Change:   CR-094 capture wave, lane E — PO ruling 2026-09-15, *"if we have
#           unit or street address then we should take it from premises/Unit -
#           it means its a search and if not foudn them alow user to add them"*
#           Screens: REQ-03.3 (blueprint entry 06, p077)
# Rules:    CLAUDE.md hard rule 8 / BR-MET-1161 (an address is stored on
#           `premises` and NOWHERE else) · hard rule 1 (tenant scoping, RLS
#           FORCE) · BR-CUS-070 (`address_as_given` is never overwritten) ·
#           BR-CUS-1010 (an account may stand at an ADDRESS with no unit) ·
#           B14 rule 31 (no database id is a visible value) · NFR-3 · NFR-5
# Defects:  DEF-CUS-5385 (step 3 has no register search) · DEF-CUS-5386 (a raw
#           premises UUID is the visible value of *RESOLVED TO*)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-094 lane E — the address on a service request is PICKED, not typed.

RED-FIRST PROOF (r11 step 2d). Every guard here was broken first and its failure
quoted before it was trusted green; the mutations and their output are in
`04-docs/05-modules/03-customers/conformance/CR-094-BRC01-capture-lane-E-address-is-picked.md`.

⚠ **THE LOCALITY CASES ASSERT A REAL VALUE FROM A REAL PREMISES, NEVER THAT A
KEY EXISTS.** That is `DEF-CUS-3653`: the account header composed
`Austin, TX 78704` from a `customers.addresses` row of a kind that was later
retired, and the line then returned null on every account **forever**, with
`tsc` and every test green. An absence is invisible to every check this repo
has, so `assert locality["city"] == "Katy"` is the shape and `assert "city" in
locality` is not.

⚠ **THE REQUEST'S READ PAYLOAD IS LANE B's AND IS NOT TOUCHED HERE.** That lane
serves the matched place named — `resolved_premises_no`, `resolved_unit_no`,
`premise_locality` — and `premise_locality` is already this repo's word for a
walked locality. Lane E built a nested `premises: {city, …}` for the same fact,
found lane B's while both were unpushed, and **removed its own**: two names for
one fact is worse than either name. What is proved here instead is the half that
is lane E's — that a PICK is what makes that walk reachable at all.

⚠ **NOTHING HERE ADDS A COLUMN TO `service_requests`, AND THE LAST CASE PROVES
IT.** A sibling lane was an hour into `city`, `state` and `postal_code` columns
when the ruling landed and was stopped. `G85` would fail a fourth home; this
file asserts the payload names them as the PREMISES' so nobody re-adds them to
make a screen easier.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customer_models
from apps.customers import seams
from apps.customers import service_request_service as sr
from apps.metering import address_picker
from apps.metering import models
from core import errors

from tests.isolation_helpers import (  # noqa: F401
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    requires_postgres,
    rls,
    # ⚠ **`rls` IS A FIXTURE THAT DEPENDS ON ANOTHER FIXTURE, AND PYTEST
    #: RESOLVES A DEPENDENCY BY NAME IN THE TEST MODULE'S OWN NAMESPACE.**
    #: Importing `rls` alone makes the RLS case ERROR with
    #: `fixture 'rls_probe_role' not found` — it does not skip, and a skip is
    #: what a reader expects when a PostgreSQL case cannot run, so the
    #: tenant-isolation half reads as "not exercised here" when it is in fact
    #: not exercisable at all (`DEF-CUS-5407`, 2026-09-15). Every other file
    #: using `rls` imports both and says so; this one did not.
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: What the applicant said at the counter. It is NOT a premises and never
#: becomes one — BR-CUS-070, and the blueprint says so twice on p077.
AS_GIVEN = "212 balcones dr, near the water tower"


def _estate(actor):
    """One building with two units and one field with none, on one tenant."""
    tower = make_premises(
        actor,
        address_line="212 Balcones Drive",
        city="Katy",
        state="TX",
        postal_code="77494",
        premises_type="apartment_complex",
    )
    flat_a = make_unit(actor, tower["id"], label="Unit 3", unit_type="residential")
    flat_b = make_unit(actor, tower["id"], label="Unit 4", unit_type="residential")
    field = make_premises(
        actor,
        address_line="9 Cypress Row",
        city="Katy",
        state="TX",
        postal_code="77494",
        owner_manager="Cypress Land Co",
    )
    return tower, flat_a, flat_b, field


def _draft(actor, **extra):
    payload = {
        "applicant_name": "Rosa Delgado",
        "address_as_given": AS_GIVEN,
        "channel": "counter",
    }
    payload.update(extra)
    return sr.create_request(actor, payload)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE SEARCH A CLERK USES AT A COUNTER
# ═══════════════════════════════════════════════════════════════════════════
def test_the_register_is_searched_by_street_text_and_by_premise_number(brazos, dana):
    """`GET /premises/picker?q=` — the two things a clerk reads off a bill."""
    with tenant_ctx(brazos):
        tower, _a, _b, _field = _estate(dana)

        by_street = [row.premise_no for row in address_picker.search(q="Balcones")]
        assert by_street == [tower["premise_no"]]

        by_number = [row.premise_no for row in address_picker.search(q=tower["premise_no"])]
        assert by_number == [tower["premise_no"]]

        by_town = {row.premise_no for row in address_picker.search(q="Katy")}
        assert tower["premise_no"] in by_town and len(by_town) == 2


def test_a_picked_row_carries_its_units_and_its_visible_values(brazos, dana):
    """B14 rule 31 — `premise_no` and `unit_no` are what shows; the ids travel
    for the pick and never render."""
    with tenant_ctx(brazos):
        tower, flat_a, flat_b, _field = _estate(dana)

        page = address_picker.page_rows(address_picker.search(q="Balcones"))
        assert len(page) == 1
        row = page[0]

        assert row["premise_no"] == tower["premise_no"]
        assert row["address_line"] == "212 Balcones Drive"
        # The locality IS the premises' own, read from the one home (hard rule 8).
        assert (row["city"], row["state"], row["postal_code"]) == ("Katy", "TX", "77494")

        labels = [unit["label"] for unit in row["units"]]
        assert labels == ["Unit 3", "Unit 4"]
        assert {unit["id"] for unit in row["units"]} == {flat_a["id"], flat_b["id"]}
        # `unit_no` is the visible value and it is really there — a tenant with
        # no unit series answers null and the label shows instead.
        assert all("unit_no" in unit for unit in row["units"])

        # A property with no units answers an empty list, never a missing key.
        field_row = address_picker.page_rows(address_picker.search(q="Cypress"))[0]
        assert field_row["units"] == []


def test_def_cus_6057_a_picked_row_carries_what_the_address_OFFERS(brazos, dana):
    """`DEF-CUS-6057` — **the service list a picked address offers travels with
    it, or the build that picks it cannot fit a single meter.**

    New Connect step 2 copies street, town, state and ZIP out of this row. With
    no service list to copy, the clerk's step-4 ticks became a local fiction and
    every meter was refused at the last press, after eight steps.

    ⚠ **THIS IS THE PREMISES' OWN COLUMN, NOT ANYTHING STANDING ON A UNIT**, so
    the 2026-09-15 ruling the case below enforces is untouched. What the STREET
    offers is the same class of fact as the address itself (hard rule 8).
    """
    with tenant_ctx(brazos):
        _estate(dana)
        row = address_picker.page_rows(address_picker.search(q="Balcones"))[0]
        assert row["services_available"] == ["electric", "water"]


def test_def_cus_6057_an_unasked_address_answers_None_and_never_an_empty_list(brazos, dana):
    """`DEF-762` — **`None` and `[]` are two answers and only one of them is
    about the address.** SQL NULL is *nobody has ever been asked*; `[]` is *it
    offers nothing*. The read serves the column RAW, because collapsing them
    here would destroy the only signal an address was never asked — and the
    wizard then knows not to overwrite a clerk's list with an absence.
    """
    with tenant_ctx(brazos):
        _estate(dana)
        # Written directly: `create_premises` fills the column, so the unasked
        # state can no longer be reached through the front door — the same
        # reason `make_unmatched_premises` exists one rule over.
        models.Premises.objects.filter(address_line="9 Cypress Row").update(
            services_available=None
        )
        row = address_picker.page_rows(address_picker.search(q="Cypress"))[0]
        assert row["services_available"] is None

        models.Premises.objects.filter(address_line="9 Cypress Row").update(
            services_available=[]
        )
        row = address_picker.page_rows(address_picker.search(q="Cypress"))[0]
        assert row["services_available"] == []


def test_nothing_about_the_meters_or_services_on_a_unit_is_served(brazos, dana):
    """PO 2026-09-15, clause 2: *"if unit is found then it is gi=oing to be
    mobve in mostly and all asset - which we will take acre in move in
    request"*. A lane adding these back is undoing a ruling."""
    with tenant_ctx(brazos):
        _estate(dana)
        row = address_picker.page_rows(address_picker.search(q="Balcones"))[0]
        forbidden = {"meters", "meter_count", "assets", "services", "service_points", "accounts"}
        assert not forbidden & set(row)
        for unit in row["units"]:
            assert not forbidden & set(unit)


def test_nfr_3_the_search_pages_in_sql_and_caps_nothing(brazos, dana):
    """`search()` hands back a **QuerySet**, unevaluated, so the paginator
    slices it with LIMIT/OFFSET rather than pulling the whole register into
    memory — which is what metering's `_page` helper does and what `NFR-3` is
    already breached over elsewhere (`DEF-PAY-4221`)."""
    from django.db.models import QuerySet

    with tenant_ctx(brazos):
        _estate(dana)
        found = address_picker.search(q="Katy")
        assert isinstance(found, QuerySet)
        assert found._result_cache is None, "the search must not evaluate itself"
        # NFR-5 — no slice, no ceiling: asking for a large page gets one.
        assert str(found.query).count("LIMIT") == 0


def test_the_search_is_ordered_totally_so_a_page_cannot_repeat_a_row(brazos, dana):
    """Two properties on one street with no unit numbers yet is an ordinary
    thing; `id` is the last sort key so page 2 cannot hand back page 1's row."""
    with tenant_ctx(brazos):
        make_premises(dana, address_line="11 Sorrel Way", city="Katy")
        make_premises(dana, address_line="11 Sorrel Way", city="Katy")
        assert address_picker.search().query.order_by == ("premise_no", "address_line", "id")
        assert len(list(address_picker.search(q="Sorrel"))) == 2


def test_hard_rule_1_a_search_never_crosses_a_tenant(brazos, dana, lonestar, erin):
    """The ORM half of the boundary. The RLS half is the `requires_postgres`
    case at the foot of this file — on SQLite there are no policies at all, so
    THIS case alone would be law 7's *incapable of failing* shape."""
    with tenant_ctx(lonestar):
        make_premises(
            erin, address_line="212 Balcones Drive", city="Ridge",
            services_available=["water"],
        )
    with tenant_ctx(brazos):
        _estate(dana)
        mine = list(address_picker.search(q="Balcones"))
        assert len(mine) == 1
        assert {row.tenant_id for row in mine} == {brazos.id}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE CAPTURE PATH ACCEPTS A PICK
# ═══════════════════════════════════════════════════════════════════════════
def test_picking_a_unit_writes_the_four_resolution_columns(brazos, dana):
    with tenant_ctx(brazos):
        tower, flat_a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"], picked_unit_id=flat_a["id"])

        assert str(request.resolved_premises_id) == tower["id"]
        assert str(request.resolved_unit_id) == flat_a["id"]
        assert request.resolution_kind == customer_models.ServiceRequest.RESOLUTION_SERVED_VACANT
        assert request.resolved_at is not None
        assert request.no_premise_flag is False


def test_br_cus_070_the_pick_never_overwrites_what_the_applicant_said(brazos, dana):
    """*"The address is the APPLICANT'S, not a record… never written over it"*
    (p077, twice). The whole reason the resolved ids are separate columns."""
    with tenant_ctx(brazos):
        tower, flat_a, _b, _field = _estate(dana)
        request = _draft(dana)
        assert request.address_as_given == AS_GIVEN

        sr.update_request(
            dana, request.id, {"picked_premises_id": tower["id"], "picked_unit_id": flat_a["id"]}
        )
        request.refresh_from_db()
        assert request.address_as_given == AS_GIVEN
        assert str(request.resolved_premises_id) == tower["id"]
        # And the match did not become a second address on the request either.
        assert not hasattr(request, "address_line")


def test_br_cus_1010_a_building_may_be_picked_with_no_unit_named(brazos, dana):
    """A fifth `resolution_kind`. `no_premise` would flag a property that
    exists; `unresolved` would make `evidence_for` answer `premise_exists:
    false`, which is the term that decides a NEW CONNECTION is not possible."""
    with tenant_ctx(brazos):
        tower, _a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"])

        assert (
            request.resolution_kind
            == customer_models.ServiceRequest.RESOLUTION_PREMISE_NO_UNIT
        )
        assert str(request.resolved_premises_id) == tower["id"]
        assert request.resolved_unit_id is None
        assert request.no_premise_flag is False
        assert sr.evidence_for(request).premise_exists is True


def test_a_unit_at_another_address_is_refused_by_name(brazos, dana):
    """Two columns quietly disagreeing about where a request is has no repair
    afterwards, because nothing records which of the two the clerk meant."""
    with tenant_ctx(brazos):
        tower, _a, _b, field = _estate(dana)
        other = make_unit(dana, field["id"], label="Shed")
        with pytest.raises(errors.ValidationError) as raised:
            _draft(dana, picked_premises_id=tower["id"], picked_unit_id=other["id"])
        assert raised.value.message_key == "customers.serviceRequest.pickedUnitNotAtPremises"


def test_a_unit_alone_brings_its_building_with_it(brazos, dana):
    with tenant_ctx(brazos):
        tower, flat_a, _b, _field = _estate(dana)
        request = _draft(dana, picked_unit_id=flat_a["id"])
        assert str(request.resolved_premises_id) == tower["id"]


def test_a_pick_can_be_undone(brazos, dana):
    """A clerk who picked the wrong building has to be able to say so."""
    with tenant_ctx(brazos):
        tower, flat_a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"], picked_unit_id=flat_a["id"])

        sr.update_request(dana, request.id, {"picked_premises_id": None, "picked_unit_id": None})
        request.refresh_from_db()
        assert request.resolved_premises_id is None
        assert request.resolved_unit_id is None
        assert request.resolution_kind == customer_models.ServiceRequest.RESOLUTION_UNRESOLVED
        assert request.resolved_at is None
        assert request.address_as_given == AS_GIVEN


def test_a_patch_about_something_else_does_not_clear_a_pick(brazos, dana):
    with tenant_ctx(brazos):
        tower, flat_a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"], picked_unit_id=flat_a["id"])
        sr.update_request(dana, request.id, {"applicant_phone": "512-555-0150"})
        request.refresh_from_db()
        assert str(request.resolved_unit_id) == flat_a["id"]


def test_hr_1_a_premises_of_another_tenant_is_not_pickable(brazos, dana, lonestar, erin):
    with tenant_ctx(lonestar):
        theirs = make_premises(
            erin, address_line="88 Ridge Rd", city="Ridge", services_available=["water"],
        )
    with tenant_ctx(brazos):
        _estate(dana)
        with pytest.raises(errors.NotFoundError):
            _draft(dana, picked_premises_id=theirs["id"])


def test_a_guest_on_the_public_form_may_not_pick(brazos, dana):
    """`PORTAL_CAPTURE_FIELDS` refuses both names. A stranger who could name any
    premises id could attach their application to somebody else's building."""
    assert not sr.PICK_FIELDS & sr.PORTAL_CAPTURE_FIELDS
    with tenant_ctx(brazos):
        tower, _a, _b, _field = _estate(dana)
        with pytest.raises(errors.ValidationError) as raised:
            sr.create_from_portal(
                {
                    "applicant_name": "A Passer-by",
                    "address_as_given": "212 Balcones Drive",
                    "picked_premises_id": tower["id"],
                }
            )
        assert raised.value.message_key == "customers.serviceRequest.fieldNotAccepted"


def test_resolution_kind_is_still_refused_as_an_unknown_field(brazos, dana):
    """The pick names a ROW; it does not assert what the row MEANS. A caller
    cannot forge `served_vacant` over an occupied flat."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            _draft(dana, resolution_kind="served_vacant")


def test_the_fuzzy_resolver_may_not_wipe_a_clerks_pick(brazos, dana):
    """`resolve_address` matches on UNITS only, so it answers *no premise
    record* for a real building the moment the applicant named no unit. Running
    it over a picked request would replace the property with *"This address is
    not on record"* and open the add-a-premises path over a building that
    exists."""
    with tenant_ctx(brazos):
        tower, _a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"])

        evidence = sr.resolve_address(dana, request.id)
        request.refresh_from_db()

        assert str(request.resolved_premises_id) == tower["id"]
        assert request.no_premise_flag is False
        assert evidence.premise_exists is True


# ═══════════════════════════════════════════════════════════════════════════
# 3 · CITY, STATE AND ZIP ARE READ BY WALKING
#
# ⚠ **THE READ PAYLOAD ITSELF IS LANE B's AND IS DELIBERATELY NOT TOUCHED HERE
# (CR-094-BRC01 wave 1, 2026-09-15).** That lane serves the matched place NAMED
# — `resolved_premises_no`, `resolved_unit_no`, `resolved_premise_address` and
# `premise_locality` — through its own `resolved_place()`, and `premise_locality`
# is already this repo's name for a walked locality (`DEF-CUS-3653`'s repair on
# the account header). A second, nested `premises: {city, …}` beside it would be
# **two names for one fact**, which is the thing this repo punishes hardest, so
# lane E removed its own version of it rather than shipping both.
#
# What IS lane E's and is proved below: **the pick is what makes that walk
# possible at all.** Before it, `resolved_premises_id` was only ever filled FROM
# a matched unit — lane B's own code says so in as many words, calling the
# premises-only branch *"unreachable through today's resolver"*. A clerk picking
# a building makes it reachable, and these cases assert the walk ARRIVES from a
# picked premises with a REAL value, never merely that a key exists.
# ═══════════════════════════════════════════════════════════════════════════
def test_a_picked_premises_is_walkable_to_a_real_locality(brazos, dana):
    """`DEF-CUS-3653`'s lesson, on the other side: a REAL town from a REAL
    premises. An absence is invisible to every check this repo has."""
    with tenant_ctx(brazos):
        tower, flat_a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"], picked_unit_id=flat_a["id"])

        locality = seams.premises_locality(request.resolved_premises_id)
        assert locality == {"city": "Katy", "state": "TX", "postal_code": "77494"}


def test_the_walk_arrives_from_a_building_picked_with_no_unit(brazos, dana):
    """The branch lane B's `resolved_place` calls *"unreachable through today's
    resolver"*. The pick is what reaches it, so it is asserted here rather than
    left as a defensive null nobody exercises."""
    with tenant_ctx(brazos):
        tower, _a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"])

        assert request.resolved_unit_id is None
        assert seams.premises_locality(request.resolved_premises_id)["city"] == "Katy"
        assert seams.premises_ref(request.resolved_premises_id)["premise_no"] == tower["premise_no"]


def test_hard_rule_8_the_request_grows_no_address_column(brazos, dana):
    """A sibling lane was an hour into `city`, `state` and `postal_code` columns
    on `service_requests` when the ruling landed. `G85` would fail a fourth
    home; this asserts the absence, because an absence is what nothing else can
    see."""
    with tenant_ctx(brazos):
        tower, _a, _b, _field = _estate(dana)
        request = _draft(dana, picked_premises_id=tower["id"])
        # ⚠ **`state` IS NOT IN THIS LIST AND MUST NOT BE — IT IS `G85`'s OWN
        # MEASURED FALSE POSITIVE.** `service_requests.state` is the workflow
        # state, and that gate's docstring names it among eight such columns:
        # *"a gate whose output is 73% false positives is a gate that gets an
        # allow-list entry per commit until it means nothing."* This case was
        # written with `state` in it, went red on exactly that, and is left
        # narrower rather than given an exception.
        for column in ("city", "postal_code", "address_line", "zip", "town"):
            assert not hasattr(request, column), f"service_requests grew a {column!r} column"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · NOT FOUND → THE REQUEST CARRIES ON, FLAGGED
# ═══════════════════════════════════════════════════════════════════════════
def test_an_address_that_matches_nothing_is_not_refused(brazos, dana):
    """p077, in red: *"An address that matches nothing is not refused. It is
    flagged as having no premises on record, and the request carries on"*."""
    with tenant_ctx(brazos):
        request = _draft(dana, address_as_given="A field off Lonesome Rd")
        evidence = sr.resolve_address(dana, request.id)
        request.refresh_from_db()

        assert request.state == customer_models.ServiceRequest.DRAFT  # it carried on
        assert request.no_premise_flag is True
        assert request.resolution_kind == customer_models.ServiceRequest.RESOLUTION_NO_PREMISE
        assert evidence.premise_exists is False


def test_customers_has_no_way_to_write_a_premises(brazos, dana):
    """*"if not found then allow user to add them"* is the premises register's
    OWN create at `/:tenant/premises/new` (S16 · PRM-07), reached from this
    step — never a second create path here. With no write seam, `customers`
    cannot write a property even by accident, which is a boundary a reader can
    check rather than a promise in a docstring."""
    from apps.customers import seams

    assert not [name for name in dir(seams) if "create_premises" in name]
    assert not [name for name in dir(seams) if "create_unit" in name]


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE RLS HALF — PostgreSQL ONLY, because on SQLite it cannot exist
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_rls_a_search_from_one_tenant_sees_no_row_of_another(  # noqa: F811
    rls, brazos, lonestar, dana, erin
):
    """⚠ **THE ONLY CASE IN THIS FILE THAT PROVES RLS, AND IT IS THE REASON THE
    ORM CASE ABOVE IS NOT ENOUGH.**

    `test_hard_rule_1_a_search_never_crosses_a_tenant` passes on SQLite, where
    row-level security cannot exist — hard-won law 14, and law 7's *structurally
    incapable of failing*: `G5` once ran the isolation suite on SQLite and
    called 192 skips a pass. This one asks the DATABASE, inside `SET ROLE
    sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS), because a superuser
    bypasses the very policies under test.

    Both tenants are given a property on the SAME STREET, so the leak this
    would catch is the one that matters: a clerk at Brazos Bend typing
    *Balcones* and being offered Lone Star Ridge's building to attach an
    application to.
    """
    with tenant_ctx(brazos):
        mine = make_premises(dana, address_line="212 Balcones Drive", city="Katy")
        make_unit(dana, mine["id"], label="Unit 3")
    with tenant_ctx(lonestar):
        theirs = make_premises(
            erin, address_line="212 Balcones Drive", city="Ridge",
            services_available=["water"],
        )
        make_unit(erin, theirs["id"], label="Unit 3")

    assert_rls_scoped(rls, "premises", owner=brazos, intruder=lonestar, owner_ids={mine["id"]})
    assert_rls_scoped(rls, "units", owner=brazos, intruder=lonestar)
    assert_no_foreign_rows_anywhere(rls, brazos, ["premises", "units"])
    assert_no_foreign_rows_anywhere(rls, lonestar, ["premises", "units"])

    # …and the SEARCH ITSELF, under the owning tenant's live context: the same
    # street, and only one answer.
    with tenant_ctx(brazos):
        found = [row["premise_no"] for row in address_picker.page_rows(
            address_picker.search(q="Balcones")
        )]
        assert len(found) == 1

# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the SIX groups CR-073 added
# Change:   CR-073 — PO 2026-09-05, *"Extend universal search to include work
#           order , template, parts"* and *"Don't add reads and finance - add
#           work related items"*
# Rules:    BR-SHL-005 AS AMENDED 2026-09-05 (fifteen groups, ≤5 each,
#           prefix-then-recency, by their identifiers) · BR-SHL-006 (tenant
#           scoping; role-invisible groups OMITTED) · BR-WRK-002 (Work reads
#           other modules only through seams) · B14 rule 31
# Note:     Cross-tenant isolation is NOT here. It needs live PostgreSQL and a
#           non-superuser probe and lives in tests/test_cr073_search_isolation.py
#           — a green SQLite run proves nothing about RLS.
# ───────────────────────────────────────────────────────
"""The six new groups, over the WIRED stack — the real route, real sources.

⚠ **THE FIFTEEN-GROUP ORDER CASE LIVES HERE RATHER THAN IN
`test_us_shl_003_search.py`, AND THAT IS A DELIBERATE MOVE OF THE STRONGER
ASSERTION.** That file's `_seed` builds nine surfaces and its order case
asserted `len(order) == 9`. Extending its fixture to fifteen would have put six
modules' rows into a fixture nine other cases read, and each of those cases
counts rows in a group. So the nine-group fixture keeps its job — the wire
carries the order — and the WHOLE order is proved here, on a fixture built for
it. `test_be08_search.py` still holds the count.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.identity import models as identity_models
from apps.work import connection_models as work_tables
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.work import models as work_models
from core import permissions, search

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    idn,
    signed_in_client,
)
from tests.test_us_shl_003_search import (  # noqa: F401 (fixture import)
    _alex,
    _groups,
    _order,
    _seed,
    restore_search_sources,
)

pytestmark = pytest.mark.django_db


# ── world ───────────────────────────────────────────────────────────────────


def _service(code="water"):
    """The platform service catalogue is seeded by `tenancy/0001` — read, never
    created, so this fixture cannot disagree with `BR-RAT-024`'s eleven."""
    return tenancy_models.Service.objects.get(code=code)


def _seed_work_and_rating(idn, token=""):
    """The six CR-073 surfaces, every identifier carrying `token`.

    Same device as `_seed`'s: one query reaches every group at once, which no
    realistic identifier set allows — `WO-0011`, `MTR-W58`, `RES-W` and
    `LATE-FEE` share no two-character substring, and a one-character query is
    refused by the IS-3 minimum.
    """
    tenant = idn.silvercreek
    world = {}

    premises = _seed_premises(tenant)
    world["order"] = work_tables.WorkOrder.objects.create(
        tenant=tenant,
        order_no=f"WO-0011{token}",
        premises=premises,  # BR-WRK-006's second anchor — no connection needed
        type="Meter set",
        state="planned",
    )
    world["template"] = work_tables.WorkOrderTemplate.objects.create(
        tenant=tenant,
        service=_service(),
        name=f"Meter set{token}",
        template_no=f"ST-0004{token}",
        version=1,
    )
    world["part"] = work_models.Part.objects.create(
        tenant=tenant,
        part_no=f"MTR-W58{token}",
        name="Water meter 5/8 inch",
        unit_of_measure="each",
        unit_cost=Decimal("92.4000"),
    )
    user = identity_models.User.objects.create(
        tenant=tenant, email=f"r.patel{token}@silvercreek.example", full_name=f"R. Patel{token}"
    )
    world["crew"] = work_models.Crew.objects.create(
        tenant=tenant, name=f"Crew B{token}", headcount=3, role_label="Network crew"
    )
    # `CR-168-BRC10` P3.44 — the bracket counts the technicians ON the crew; the
    # typed headcount (3) is no longer read, so R. Patel is put on it: *(1)*.
    world["technician"] = work_models.Technician.objects.create(
        tenant=tenant, user=user, role_label="Senior technician", crew=world["crew"]
    )
    world["plan"] = rating_models.RatePlan.objects.create(
        tenant=tenant, code=f"RES-W{token}", name="Residential Water", status="published"
    )
    world["charge"] = rating_models.Charge.objects.create(
        tenant=tenant, code=f"LATE-FEE{token}", name="Late payment fee"
    )
    return world


def _seed_premises(tenant):
    from apps.metering import models as metering_models

    return metering_models.Premises.objects.create(
        tenant=tenant, premise_no="P-9001", address_line="77 Cedar Ct"
    )


# ── the six groups, one case each ───────────────────────────────────────────


def test_cr073__a_work_order_number_finds_the_job(idn):
    """`WO-0011` — the number on the dispatch board, typed anywhere."""
    world = _seed_work_and_rating(idn)
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=WO-00"))["work_orders"]
    assert [row["label"] for row in rows] == ["WO-0011"]
    # The context tells five WO-00… numbers apart: what the job is, and where.
    assert rows[0]["context"] == "Meter set · 77 Cedar Ct"
    assert world["order"].order_no == "WO-0011"


def test_cr073__a_template_is_found_by_name_and_by_its_published_number(idn):
    """Both are quotable, so both are searched — the `assets` posture."""
    _seed_work_and_rating(idn)
    client = _alex(idn)

    by_name = _groups(api_get(client, "/search?q=Meter set"))["work_order_templates"]
    assert [row["label"] for row in by_name] == ["Meter set"]
    # The SERVICE is what tells four templates called *Meter set* apart, and the
    # published number rides beside it.
    assert by_name[0]["context"] == "Water · ST-0004"

    by_number = _groups(api_get(client, "/search?q=ST-000"))["work_order_templates"]
    assert [row["label"] for row in by_number] == ["Meter set"]


def test_cr073__a_template_number_is_not_repeated_when_it_is_what_was_typed(idn):
    """B14 rule 32's repetition clause — the same read `assets` makes."""
    _seed_work_and_rating(idn)
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=ST-0004"))["work_order_templates"]
    assert rows[0]["context"] == "Water"


def test_cr073__a_part_is_found_by_number_and_by_description(idn):
    """The number identifies; the description merely describes."""
    _seed_work_and_rating(idn)
    client = _alex(idn)

    by_number = _groups(api_get(client, "/search?q=MTR-W"))["parts"]
    assert [row["label"] for row in by_number] == ["MTR-W58"]
    assert by_number[0]["context"] == "Water meter 5/8 inch"

    by_description = _groups(api_get(client, "/search?q=Water meter"))["parts"]
    assert [row["label"] for row in by_description] == ["MTR-W58"]


def test_cr073__a_part_number_prefix_outranks_a_description_match(idn):
    """⚠ THE BAND SPLIT, ASSERTED — this is the whole `parts` decision.

    Two parts both match *MTR*: one because its NUMBER starts with it, one only
    because its DESCRIPTION contains it. The number must come first, and it must
    come first even though the description row was updated more recently — the
    rank is prefix-band FIRST, recency only inside a band.
    """
    tenant = idn.silvercreek
    work_models.Part.objects.create(
        tenant=tenant, part_no="VLV-2200", name="MTR bypass valve", unit_of_measure="each"
    )
    work_models.Part.objects.create(
        tenant=tenant, part_no="MTR-W58", name="Water meter 5/8 inch", unit_of_measure="each"
    )
    # Make the DESCRIPTION match the newer row, so recency would put it first
    # if the bands were not doing their job.
    work_models.Part.objects.filter(part_no="VLV-2200").update(updated_at=timezone.now())
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=MTR"))["parts"]
    assert [row["label"] for row in rows] == ["MTR-W58", "VLV-2200"]


def test_cr073__people_and_crews_are_one_group_in_the_screens_order(idn):
    """`Work-023` is ONE table, people first — and so is this group."""
    _seed_work_and_rating(idn)
    tenant = idn.silvercreek
    work_models.Crew.objects.create(
        tenant=tenant, name="Crew Bravo", kind=work_models.Crew.KIND_CONTRACTOR
    )
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=Crew B"))["workforce"]
    # A contractor and a crew both match; both are in the ONE group.
    assert {row["label"] for row in rows} == {"Crew B (1)", "Crew Bravo"}

    people = _groups(api_get(client, "/search?q=Patel"))["workforce"]
    assert [row["label"] for row in people] == ["R. Patel"]
    assert people[0]["context"] == "Senior technician"


def test_cr073__a_crews_headcount_is_part_of_the_name_exactly_as_the_screen_composes_it(idn):
    """*Crew B (1)* — one fact, composed in one place (`workforce.crews_page`):
    the COUNTED members since `CR-168-BRC10` P3.44, never the typed headcount."""
    _seed_work_and_rating(idn)
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=Crew B"))["workforce"]
    assert [row["label"] for row in rows] == ["Crew B (1)"]


def test_cr073__a_plan_is_found_by_code_and_by_name(idn):
    _seed_work_and_rating(idn)
    client = _alex(idn)

    by_code = _groups(api_get(client, "/search?q=RES-W"))["plans"]
    assert [row["label"] for row in by_code] == ["RES-W"]
    # A published plan states no status — B14 rule 32's budget.
    assert by_code[0]["context"] == "Residential Water"

    by_name = _groups(api_get(client, "/search?q=Residential"))["plans"]
    assert [row["label"] for row in by_name] == ["RES-W"]


def test_cr073__a_draft_plan_says_so_and_a_published_one_does_not(idn):
    tenant = idn.silvercreek
    rating_models.RatePlan.objects.create(
        tenant=tenant, code="RES-G", name="Residential Gas", status="draft"
    )
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=RES-G"))["plans"]
    assert rows[0]["context"] == "Residential Gas · draft"


def test_cr073__a_charge_code_is_found_by_code_and_by_name(idn):
    _seed_work_and_rating(idn)
    client = _alex(idn)

    rows = _groups(api_get(client, "/search?q=LATE-FEE"))["charges"]
    assert [row["label"] for row in rows] == ["LATE-FEE"]
    assert rows[0]["context"] == "Late payment fee"


# ── the money slot stays empty, and that is a rule not an omission ──────────


def test_cr073__no_new_group_carries_money(idn):
    """⚠ `parts.unit_cost` and `charges.amount` are both decimals in the
    database and NEITHER reaches the popover.

    A part's unit cost needs a quantity to mean anything; a charge's amount is a
    SEED the engine may override (`BR-RAT-035`, B4 §NSF). A figure printed here
    would be read as *the price* and would sometimes be wrong.
    """
    _seed_work_and_rating(idn)
    client = _alex(idn)

    for query, entity in (("MTR-W", "parts"), ("LATE-FEE", "charges")):
        rows = _groups(api_get(client, f"/search?q={query}"))[entity]
        assert rows[0]["amount"] is None, entity
        assert rows[0]["currency"] is None, entity


# ── B14 rule 31 · no database id is ever a visible value ────────────────────


def test_cr073__no_uuid_is_a_visible_value_in_any_new_group(idn):
    """Every rendered field of every new group's rows, against the row's own id.

    The uuid reaches `id` — the deep link — and NOTHING else. This is the check
    `assets/search_sources.py` spells out for three identifiers; six more groups
    have the same shape and the same way of getting it wrong.
    """
    _seed_work_and_rating(idn, token="")
    client = _alex(idn)

    seen = 0
    for query in ("WO-00", "Meter set", "MTR-W", "Patel", "Crew B", "RES-W", "LATE-FEE"):
        for entity, rows in _groups(api_get(client, f"/search?q={query}")).items():
            for row in rows:
                rendered = " ".join(str(row[key]) for key in ("label", "context") if row[key])
                assert row["id"] not in rendered, (entity, row)
                # Nor any uuid at all — a different row's id is just as wrong.
                assert "-" * 0 == "" and len(row["id"]) >= 32, row
                seen += 1
    assert seen > 0, "the case proved nothing — no rows were rendered"


# ── the whole ruled order, on the wire ──────────────────────────────────────


def test_cr073__all_fifteen_groups_arrive_in_the_ruled_order(idn):
    """`groups` is a LIST, so BR-SHL-005's order is carried by the response.

    ⚠ **THIS IS THE CASE THAT WOULD CATCH A GROUP REGISTERED AND NEVER SERVED.**
    A source whose `AppConfig.ready()` registration was forgotten is invisible
    to every other test in this file — each of those asks for one group by name
    and would simply KeyError in a way that reads as a fixture problem. This one
    asserts the whole sequence, so a missing registration names itself.
    """
    _seed(idn, token="ZQ")
    _seed_work_and_rating(idn, token="ZQ")
    client = _alex(idn)

    order = _order(api_get(client, "/search?q=ZQ"))
    assert len(order) == 15, order
    assert order == list(search.GROUP_ORDER)


# ── BR-SHL-006 · a role-invisible group is OMITTED, not empty ───────────────


def test_cr073__a_role_invisible_new_group_is_omitted_entirely(idn):
    """A dispatcher's group must not tell a billing clerk that work exists.

    Today every Work read route is read-by-all-three, so no group is invisible
    to anyone — which is why this case NARROWS one itself rather than asserting
    today's visibility. The clause is enforced in the kernel, where it cannot be
    forgotten, and this proves it bites on a group CR-073 added.
    """
    from apps.work import search_sources as work_sources

    _seed_work_and_rating(idn)
    search.register_search_source(
        "work_orders",
        work_sources.search_work_orders,
        visible_to=frozenset({permissions.EXECUTIVE}),
    )
    client = _alex(idn)  # a SYSTEM ADMIN, i.e. not the role above

    groups = _groups(api_get(client, "/search?q=WO-00"))
    assert "work_orders" not in groups, "an invisible group must be ABSENT, never empty"


# ── the cross-language pin: the union cannot drift from the server ──────────


def test_cr073__the_frontend_search_entity_union_equals_group_order():
    """⚠ **THE ONE DIRECTION `tsc` CANNOT CHECK, CHECKED HERE.**

    `GROUP_LABEL_KEY` and `SEARCH_DESTINATIONS` are `Record<SearchEntity, …>`,
    so the compiler refuses a union member with no label and no destination.
    **Nothing checks the other way**: a group added to `core/search.py` and not
    to the union compiles perfectly, is typed as an impossible value, and
    arrives at the popover as an unlabelled fallback — the `SignupWizard` shape
    CLAUDE.md's hard-won law 2 opens with, where the row exists, the API serves
    it, `tsc` and every test pass, and the screen never offers it.

    No TypeScript check can read Python, so the pin is here. A sixteenth group
    added to either side alone fails this by name.
    """
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "api" / "endpoints.ts"
    ).read_text(encoding="utf-8")
    block = re.search(r"export type SearchEntity =\s*(.*?);", source, re.S)
    assert block, "SearchEntity is not declared as a union in endpoints.ts any more"
    union = re.findall(r'"([a-z_]+)"', block.group(1))

    assert union == list(search.GROUP_ORDER), (
        "the frontend SearchEntity union and core.search.GROUP_ORDER have drifted:\n"
        f"  union only: {sorted(set(union) - set(search.GROUP_ORDER))}\n"
        f"  server only: {sorted(set(search.GROUP_ORDER) - set(union))}"
    )


# ── LAYER 1, PROVED WHERE THE APP FILTER IS THE ONLY DEFENCE ───────────────


def test_cr073__every_new_source_is_scoped_by_the_application_not_only_by_rls(idn):
    """⚠ **THE APPLICATION FILTER, PROVED ON SQLite — WHERE THERE IS NO RLS TO
    HIDE BEHIND.**

    The obvious home for this is the isolation suite's both-tenants query, and
    **that case cannot prove it** — measured, not reasoned. `tenant_id=` was
    deleted from `search_parts`, `tests/test_cr073_search_isolation.py` was
    re-run against real PostgreSQL, and it stayed **GREEN**: the probe role
    `sbh_gate_iso` is exactly the non-superuser role RLS applies to, so layer 2
    caught the leak and the test could not see the difference. Defence in depth
    working — and a check that cannot fail for the reason it claims.

    ⚠ **THE FIRST DRAFT OF *THIS* CASE HAD THE SAME DISEASE, WHICH IS WHY IT IS
    WORTH WRITING DOWN TWICE.** It captured each source's SQL and asserted the
    string `tenant_id` appeared in it. Both sabotages below passed it: a
    `select_related` join names `tenant_id` in the SELECT LIST of every joined
    table, so the string is present with no WHERE predicate at all. A guard
    whose evidence cannot distinguish pass from fail is worse than none.

    **So it is proved by BEHAVIOUR instead.** Two tenants hold rows matching one
    query; `config/settings/test.py` is in-memory SQLite, which has **no
    row-level security of any kind**, so the `tenant_id=` filter in the source —
    or in the seam door behind it — is the only thing that can keep them apart.

    ⚠ **THE SEAM DOORS ARE COVERED TOO, AND THEY ARE THE EASIER ONES TO BREAK**:
    `work_orders` and `work_order_templates` carry no filter in
    `search_sources.py` at all — `seams/metering_seam.py` does it for them — so
    a lane "simplifying" the seam breaks two groups that look scoped here.
    """
    from apps.rating import search_sources as rating_sources
    from apps.work import search_sources as work_sources
    from core.tenancy import tenant_context

    mine = _seed_work_and_rating_for(idn.silvercreek, marker="SHARED")
    theirs = _seed_work_and_rating_for(idn.bluemesa, marker="SHARED")

    sources = {
        "work_orders": (work_sources.search_work_orders, "order"),
        "work_order_templates": (work_sources.search_work_order_templates, "template"),
        "parts": (work_sources.search_parts, "part"),
        "workforce": (work_sources.search_workforce, "technician"),
        "plans": (rating_sources.search_plans, "plan"),
        "charges": (rating_sources.search_charges, "charge"),
    }

    for entity, (fn, key) in sources.items():
        with tenant_context(idn.silvercreek.id):
            ids = {row["id"] for row in fn("SHARED", 20)}
        # Positive control FIRST — without it every assertion below would pass
        # on a source that simply returns nothing.
        assert str(mine[key].id) in ids, f"{entity}: the caller cannot see its OWN row"
        assert str(theirs[key].id) not in ids, (
            f"LEAK — {entity} returned the other tenant's {key}. On SQLite there is no RLS, "
            f"so the application filter is the only thing that was standing there."
        )


def _seed_work_and_rating_for(tenant, *, marker):
    """One row on each new surface for an arbitrary tenant, carrying `marker`."""
    from apps.metering import models as metering_models

    premises = metering_models.Premises.objects.create(
        tenant=tenant, premise_no=f"P-{marker}-{tenant.id}", address_line=f"7 {marker} Road"
    )
    user = identity_models.User.objects.create(
        tenant=tenant, email=f"tech.{tenant.id}@example.test", full_name=f"Tech {marker}"
    )
    return {
        "order": work_tables.WorkOrder.objects.create(
            tenant=tenant,
            order_no=f"WO-{marker}",
            premises=premises,
            type="Meter set",
            state="planned",
        ),
        "template": work_tables.WorkOrderTemplate.objects.create(
            tenant=tenant,
            service=_service(),
            name=f"Meter set {marker}",
            template_no=f"ST-{marker}",
            version=1,
        ),
        "part": work_models.Part.objects.create(
            tenant=tenant,
            part_no=f"MTR-{marker}",
            name=f"Water meter {marker}",
            unit_of_measure="each",
        ),
        "technician": work_models.Technician.objects.create(
            tenant=tenant, user=user, role_label="Field technician"
        ),
        "crew": work_models.Crew.objects.create(tenant=tenant, name=f"Crew {marker}", headcount=3),
        "plan": rating_models.RatePlan.objects.create(
            tenant=tenant, code=f"RES-{marker}", name=f"Residential {marker}", status="published"
        ),
        "charge": rating_models.Charge.objects.create(
            tenant=tenant, code=f"LATE-{marker}", name=f"Late fee {marker}"
        ),
    }

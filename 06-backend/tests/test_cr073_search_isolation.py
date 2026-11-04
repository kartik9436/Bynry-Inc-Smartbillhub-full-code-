# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 / TC-7 (isolation — mandatory), extended to the SIX
#           groups CR-073 added on 2026-09-05
# Change:   CR-073 — PO, *"Extend universal search to include work order ,
#           template, parts"* / *"Don't add reads and finance - add work
#           related items"*
# Rules:    BR-SHL-006 (CONFIRMED — runs under app.tenant_id + RLS FORCE; never
#           another tenant's rows; release-blocking) · CLAUDE.md hard rule 1 ·
#           B2 §3 RLS policy template · NFR-10 (zero tolerance)
# Note:     Carries @pytest.mark.isolation and SKIPS with a vendor reason off
#           PostgreSQL. SQLite has no RLS, so a green run there proves nothing —
#           tests/isolation_helpers.py explains the probe role and why a
#           superuser connection makes an RLS assertion vacuous.
# ───────────────────────────────────────────────────────
"""The database half of tenant isolation for CR-073's six new search surfaces.

⚠ **SIX NEW TABLES ON THE PRODUCT'S SHARPEST SURFACE, SO THE MANDATORY TC IS
EXTENDED RATHER THAN ASSUMED TO COVER THEM.** The nine-group file already makes
the argument and it gets stronger, not weaker, with fifteen: the topbar box is
on every authenticated screen and now reads FIFTEEN tables on every keystroke,
so one dropped `tenant_id=` does not leak one screen's worth of another
utility's data — it leaks their jobs, their crews' names, their price list and
their customers in a single popover.

**A crew's name and a technician's name are PEOPLE**, which makes two of these
six a different class of leak from a premise number: `technicians` joins to
`identity.User` for its `full_name`, so an unscoped source here would put
another utility's staff directory on screen.

WHAT IS ASSERTED, AND WHY EACH LAYER IS SEPARATE
-------------------------------------------------
  1 · **The application layer** — every new source filters `tenant_id=`, or
      reaches its rows through a seam that does. **It is the layer a lane
      breaks by accident**: a search source is nine lines of ORM and a missing
      filter passes every other test in the repo, because every other test
      seeds one tenant. It is proved in
      `tests/test_cr073_search_work_rating.py::…_every_new_source_filters_by_tenant_in_its_own_sql`
      — see the warning below for why it is proved THERE and not here.
  2 · **The database** — RLS FORCE on all seven tables, asserted through the
      NON-SUPERUSER probe role so the policies are genuinely consulted. This is
      the layer that still holds when layer 1 is buggy, and the two cases below
      are what prove it.

⚠ **THE END-TO-END CASES BELOW DO NOT INDEPENDENTLY PROVE LAYER 1, AND SAYING
SO IS THE POINT — IT WAS MEASURED, NOT REASONED (2026-09-05).** The obvious
claim to make about a both-tenants query is *"this cannot pass on an unscoped
source"*. **It is false in this configuration and the sabotage proved it:** the
`tenant_id=` filter was deleted from `search_parts`, the suite was re-run
against real PostgreSQL under `sbh_gate_iso`, and **it stayed green** — because
that role is exactly the non-superuser role RLS applies to, so layer 2 caught
the leak invisibly and the test could not tell the difference.

**That is defence in depth doing its job, and it is also a check that cannot
fail for the reason it says it can.** Both cases below remain worth running —
they prove the two layers TOGETHER keep a tenant's rows in, which is the
property `BR-SHL-006` actually promises — but the app filter needs its own
proof with RLS out of the path, and that is the SQL-level case named above. A
comment claiming a guarantee is not the guarantee (hard-won law 1).

⚠ **THE COMPARISON IS BY ID, NEVER BY LABEL.** Both utilities hold rows whose
identifiers are byte-identical — that is what makes one query match both — so a
label cannot tell the tenants apart and a label-comparing test would be
satisfied by the leaked row.
"""

from decimal import Decimal

import pytest

from apps.identity import models as identity_models
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.work import models as work_models
from core import permissions, search

from tests.isolation_helpers import (
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_idn_helpers import idn  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db

#: The six tables CR-073 put on the search surface. A row of any of these
#: reaching the wrong tenant is the release blocker BR-SHL-006 names.
CR073_SEARCH_TABLES = (
    "work_orders",
    "work_order_templates",
    "parts",
    "technicians",
    "crews",
    "rate_plans",
    "charges",
)


def _populate(tenant, *, marker, person):
    """One row on each of CR-073's six surfaces, all carrying `marker`.

    `marker` is what makes layer 1 provable: BOTH tenants get rows containing
    it, so a query for it matches in both and an unscoped source returns both.
    """
    premises = metering_models.Premises.objects.create(
        tenant=tenant, premise_no=f"P-{marker}", address_line=f"7 {marker} Road"
    )
    rows = {}
    rows["work_order"] = work_tables.WorkOrder.objects.create(
        tenant=tenant,
        order_no=f"WO-{marker}",
        premises=premises,
        type="Meter set",
        state="planned",
    )
    rows["template"] = work_tables.WorkOrderTemplate.objects.create(
        tenant=tenant,
        service=tenancy_models.Service.objects.get(code="water"),
        name=f"Meter set {marker}",
        template_no=f"ST-{marker}",
        version=1,
    )
    rows["part"] = work_models.Part.objects.create(
        tenant=tenant,
        part_no=f"MTR-{marker}",
        name=f"Water meter {marker}",
        unit_of_measure="each",
        unit_cost=Decimal("92.4000"),
    )
    # ⚠ A PERSON. `technicians.full_name` lives on `identity.User`, so this row
    # is the one that would put another utility's staff directory on screen.
    user = identity_models.User.objects.create(
        tenant=tenant, email=f"{person}.{marker}@example.test", full_name=f"{person} {marker}"
    )
    rows["technician"] = work_models.Technician.objects.create(
        tenant=tenant, user=user, role_label="Field technician"
    )
    rows["crew"] = work_models.Crew.objects.create(
        tenant=tenant, name=f"Crew {marker}", headcount=3
    )
    rows["plan"] = rating_models.RatePlan.objects.create(
        tenant=tenant, code=f"RES-{marker}", name=f"Residential {marker}", status="published"
    )
    rows["charge"] = rating_models.Charge.objects.create(
        tenant=tenant, code=f"LATE-{marker}", name=f"Late fee {marker}"
    )
    return rows


@pytest.fixture
def two_utilities(idn):
    """Silver Creek and Harbor Point, each holding a row on all six surfaces.

    Both carry the marker `SHARED`, so one query matches fourteen rows across
    the two tenants and nothing but the tenant filter can tell them apart.
    """
    silver, harbor = idn.silvercreek, idn.bluemesa
    with live_tenant_context(silver.id):
        silver_rows = _populate(silver, marker="SHARED", person="Maria")
    with live_tenant_context(harbor.id):
        harbor_rows = _populate(harbor, marker="SHARED", person="Dan")
    return silver, harbor, silver_rows, harbor_rows


# ══════════════════════════════════════════════════════════════════════════
# LAYER 1 — THE APPLICATION. A QUERY THAT MATCHES BOTH TENANTS.
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_cr073_tc7__a_query_matching_both_tenants_returns_only_the_callers(two_utilities):
    """The two layers TOGETHER keep a tenant's rows in — which is what
    `BR-SHL-006` actually promises.

    Both utilities hold a row on every one of CR-073's six surfaces whose
    identifier contains `SHARED`, so one query matches fourteen rows across two
    tenants and only the scoping can tell them apart.

    ⚠ **THIS DOES NOT, ON ITS OWN, PROVE THE APPLICATION FILTER** — see the
    module docstring. Under the `sbh_gate_iso` probe role RLS catches a dropped
    `tenant_id=` before this case can see it, which was verified by deleting one
    and watching this stay green. The app filter's own proof is the SQL-level
    case in `tests/test_cr073_search_work_rating.py`.
    """
    silver, harbor, silver_rows, harbor_rows = two_utilities

    with live_tenant_context(silver.id):
        silver_view = search.search("SHARED", role=permissions.SYSTEM_ADMIN)
    with live_tenant_context(harbor.id):
        harbor_view = search.search("SHARED", role=permissions.SYSTEM_ADMIN)

    assert silver_view, "Silver Creek sees none of its own rows — the fixture wrote nothing"
    assert harbor_view, "Harbor Point sees none of its own rows — the fixture wrote nothing"

    silver_ids = {row["id"] for rows in silver_view.values() for row in rows}
    harbor_ids = {row["id"] for rows in harbor_view.values() for row in rows}

    # Positive control FIRST: without it the leak assertions below would pass on
    # a search that returned nothing at all, which proves nothing.
    for name, row in silver_rows.items():
        assert str(row.id) in silver_ids, f"Silver Creek cannot see its own {name}"
    for name, row in harbor_rows.items():
        assert str(row.id) in harbor_ids, f"Harbor Point cannot see its own {name}"

    # The leak check: row for row, in both directions.
    for name, row in harbor_rows.items():
        assert (
            str(row.id) not in silver_ids
        ), f"LEAK — Silver Creek's search returned Harbor Point's {name}"
    for name, row in silver_rows.items():
        assert (
            str(row.id) not in harbor_ids
        ), f"LEAK — Harbor Point's search returned Silver Creek's {name}"


@pytest.mark.isolation
@requires_postgres
def test_cr073_tc7__another_utilitys_staff_name_is_never_returned(two_utilities):
    """A person's NAME is the leak this change newly makes possible.

    `technicians` joins to `identity.User` for `full_name`, and the workforce
    group renders it as the visible label. Searching Harbor Point's technician
    by name from a Silver Creek session must find nothing at all — this is
    asserted on the LABEL as well as the id, because here the label IS the
    personal data.
    """
    silver, harbor, _, harbor_rows = two_utilities

    with live_tenant_context(silver.id):
        view = search.search("Dan", role=permissions.SYSTEM_ADMIN)

    labels = {row["label"] for rows in view.values() for row in rows}
    ids = {row["id"] for rows in view.values() for row in rows}
    assert not any(
        label.startswith("Dan") for label in labels
    ), f"LEAK — Harbor Point's technician is named on Silver Creek's screen: {labels}"
    assert str(harbor_rows["technician"].id) not in ids

    # Positive control: the same query DOES find them in their own tenant, so
    # the assertion above is not passing on a search that is simply broken.
    with live_tenant_context(harbor.id):
        own = search.search("Dan", role=permissions.SYSTEM_ADMIN)
    assert str(harbor_rows["technician"].id) in {
        row["id"] for rows in own.values() for row in rows
    }, "Harbor Point cannot find its own technician — the probe proves nothing"


# ══════════════════════════════════════════════════════════════════════════
# LAYER 2 — THE DATABASE. RLS FORCE, UNDER A ROLE IT APPLIES TO.
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
@pytest.mark.parametrize("table", CR073_SEARCH_TABLES)
def test_cr073_tc7__rls_scopes_every_new_search_table(rls, two_utilities, table):
    """Each new table's rows exist under their owner and VANISH under the other.

    Asserted through the database under the non-superuser probe role, with the
    application filter deliberately out of the path — so this still holds if a
    source is buggy, and it is the only layer a SQLite run cannot speak to.
    """
    silver, harbor, _, _ = two_utilities
    assert_rls_scoped(rls, table, owner=silver, intruder=harbor)
    assert_rls_scoped(rls, table, owner=harbor, intruder=silver)

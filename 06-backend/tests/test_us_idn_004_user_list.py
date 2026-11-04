# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-004 — tenant user list (EP-IDN-02, S8)
# Rules:    BR-IDN-008/009/010 (+ BR-IDN-029 per-tenant identity)
# Tests:    per-TC below; TC-5's RLS half = G5 suite
# ───────────────────────────────────────────────────────
"""US-IDN-004 TCs: the Users & roles list — columns, sort, pagination, RBAC.

E2 note (reported, not resolved): TC-2's "25/page default" predates the
IS-2-as-amended page-size ruling (A11 Addendum r2: 50/100/200/500/1000,
default 50) — the kernel law is asserted here (default 50)."""

import pytest

from tests.isolation_helpers import (  # noqa: F401 (fixture import)
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def test_us_idn_004_tc1__rows_and_default_sort_last_active_desc(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_get(alex, "/users")
    assert response.status_code == 200
    rows = response.json()["results"]
    assert len(rows) == 5
    # Prototype order: Just now → 2 h → 3 d → 30 d → Never (nulls last).
    emails = [row["email"] for row in rows]
    assert emails[0] == "alex@silvercreek.example"
    assert emails[-1] == "marcus@silvercreek.example"  # Never
    marcus_row = rows[-1]
    assert marcus_row["name"] == ""  # renders "—" client-side while invited
    assert marcus_row["status"] == "invited"
    assert marcus_row["last_active_at"] is None
    carla_row = next(row for row in rows if row["email"] == "carla@silvercreek.example")
    assert carla_row["status"] == "deactivated"


def test_us_idn_004_tc2__pagination_and_declared_sorts(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_get(alex, "/users")
    body = response.json()
    # Server-side pagination envelope; default page size = 50 (IS-2 as
    # amended — the story's "25/page" is the E2-reported stale value).
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 5
    by_name = api_get(alex, "/users?sort=name&dir=asc").json()["results"]
    names = [row["name"] for row in by_name]
    assert names == sorted(names)
    by_email_desc = api_get(alex, "/users?sort=email&dir=desc").json()["results"]
    emails = [row["email"] for row in by_email_desc]
    assert emails == sorted(emails, reverse=True)
    # Unknown sort falls back (never errors) — BR-SHL-011.
    assert api_get(alex, "/users?sort=nonsense").status_code == 200


def test_us_idn_004_tc3__billing_clerk_gets_403(idn):
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_get(priya, "/users")
    assert response.status_code == 403  # server-enforced regardless of UI (IS-6)
    assert response.json()["code"] == "AUTH-002"


def test_us_idn_004_tc4__executive_gets_403(idn):
    idn.seed_silvercreek()
    diana = signed_in_client("diana@silvercreek.example", "Vista2026peak")
    assert api_get(diana, "/users").status_code == 403  # A4: User management — / —


def test_us_idn_004_tc5__bluemesa_admin_sees_only_bluemesa_rows(idn):
    # App-filter half; RLS enforcement on tenant_memberships = G5 suite.
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    rows = api_get(jordan, "/users", tenant=BM).json()["results"]
    assert [row["email"] for row in rows] == ["jordan@bluemesa.example"]


@pytest.mark.isolation
@requires_postgres
def test_us_idn_004_tc5_rls__membership_rows_invisible_cross_tenant(idn, rls):
    """US-IDN-004 TC-5, RLS half — the list cannot be widened, at any layer.

    `tenant_memberships` is the row that decides who appears on S8 and with
    what role. Under Blue Mesa's `app.tenant_id` Silver Creek's five rows are
    not filtered out of a result set — they are never in one.
    """
    users = idn.seed_silvercreek()
    jordan, jordan_m = idn.seed_bluemesa_admin()

    silvercreek_members = {
        str(m.id)
        for m in (users.alex_m, users.priya_m, users.diana_m, users.marcus_m, users.carla_m)
    }
    assert_rls_scoped(
        rls,
        "tenant_memberships",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids=silvercreek_members,
    )
    with live_tenant_context(idn.bluemesa.id):
        assert rls.ids("tenant_memberships") == {str(jordan_m.id)}
        # BR-IDN-029: the users behind them are per-tenant rows too.
        assert rls.ids("users") == {str(jordan.id)}
    assert_write_into_other_tenant_refused(
        rls, "tenant_memberships", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    assert_denied_without_context(rls, "tenant_memberships", "users")


def test_us_idn_004_tc6__same_email_in_two_tenants_is_two_rows_no_linkage(idn):
    users = idn.seed_silvercreek()  # marcus@silvercreek.example — Invited · Clerk
    idn.seed_bluemesa_admin()
    idn.make_user(
        idn.bluemesa,
        "marcus@silvercreek.example",
        "Marcus Webb",
        password="Mesa2026webb",
        role="system_admin",
    )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    sc_marcus = next(
        row
        for row in api_get(alex, "/users").json()["results"]
        if row["email"] == "marcus@silvercreek.example"
    )
    assert (sc_marcus["status"], sc_marcus["role"]) == ("invited", "billing_clerk")
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    bm_marcus = next(
        row
        for row in api_get(jordan, "/users", tenant=BM).json()["results"]
        if row["email"] == "marcus@silvercreek.example"
    )
    assert (bm_marcus["status"], bm_marcus["role"]) == ("active", "system_admin")
    assert bm_marcus["id"] != sc_marcus["id"]  # two users, no linkage (BR-IDN-029)
    assert sc_marcus["id"] == str(users.marcus.id)

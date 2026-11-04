# ── Trace ──────────────────────────────────────────────
# Component: THE control the PO's 2026-08-10 path-tenancy ruling makes load-bearing
#            (12-governance/02-decision-log.md): one origin ⇒ one cookie jar ⇒ the browser
#            no longer isolates tenants, so the SERVER must. Implementation:
#            core/tenancy.py (slug resolution + require_tenant) ·
#            apps/identity/auth.py (the session↔path match) · apps/identity/models.Session
#            (`tenant_id`, the binding itself).
# Rules:     BR-IDN-006 (one tenant per session) · BR-IDN-001 (tenant resolved FIRST) ·
#            BR-TEN-003 (tenant resolved server-side) · BR-TEN-011 (slug law, reserved names) ·
#            BR-AUD-018 (the refusal is recorded server-side) · HR-1 / 11b G4 (404, never 403)
# Tests:     this file. Live-Postgres halves carry @pytest.mark.isolation (G5).
# Impacts:   every authenticated endpoint in the product
# ───────────────────────────────────────────────────────
"""The acceptance criterion of the path-tenancy change, and nothing else.

Until 2026-08-10 tenants lived on their own subdomains and the BROWSER kept
them apart: a cookie set on `silvercreek.…` was never sent to `bluemesa.…`.
`/api/{tenant}/…` is one origin, so that protection is gone and exactly two
server-side rules replace it:

  1. a session is BOUND to the tenant it was created for; and
  2. presenting it on another tenant's path is refused with **404** — never
     403 (which confirms the other tenant exists), never a silent switch to
     the session's own tenant (which would serve A's data at B's URL).

Rule 2 is only worth anything if the 404 is INDISTINGUISHABLE from every other
404, so the tests below compare raw response BYTES against two 404s produced by
completely different code paths:

  * an unknown tenant slug, refused by `core.tenancy.require_tenant` before any
    authentication runs; and
  * a genuinely absent row inside the caller's OWN tenant, refused by the
    endpoint's ordinary `errors.NotFoundError()`.

Three mechanisms, one byte sequence. That is what makes the assertion
non-vacuous: a regression that "fixed" the mismatch by inventing a special
message, a different status, or a distinct message_key breaks it immediately.

`trace_id` is the one field that legitimately differs — it is a fresh uuid4 per
response, and identical trace ids would be the actual bug. `_normalised()`
substitutes each body's OWN trace id and then compares everything else byte for
byte, including key order, so a reordered or extra key still fails.
"""

import json
import re
import uuid

import pytest
from django.test import Client

from apps.identity.models import Session
from apps.identity.models import User as IdentityUser
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import audit as core_audit
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture used by name
    BM,
    SC,
    api_get,
    api_path,
    api_post,
    client_with_session,
    idn,
    session_id_of,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")  # Silver Creek System Admin
JORDAN = ("jordan@bluemesa.example", "Mesa2026bluff")  # Blue Mesa System Admin

#: A slug that is legal by BR-TEN-011 and belongs to nobody.
NO_SUCH_TENANT = "nosuchutility"

_TRACE_ID = re.compile(rb'"trace_id": ?"[0-9a-f]{32}"')

#: Every tenant-scoped endpoint a cookie client can reach, across five modules
#: and every role gate. The refusal itself is not per-endpoint — it lives in the
#: one authentication class every endpoint shares — but the sweep proves it is
#: not special-cased for `/me`.
#:
#: EXTENDED 2026-08-10 (deploy-blocker lane, 09-infra/02 §10.14). The tenancy /
#: rating / metering / assets rows below used to be absent, and the comment here
#: said they would "inherit this refusal the day their lane wires
#: IdentitySessionAuthentication — nothing per-endpoint to do". That day is
#: today, and nothing per-endpoint was done: the class became the DRF DEFAULT
#: (config/settings/base.py), so these routes now read the session — and with it
#: they picked up the cross-tenant 404 for free. That is the claim this list
#: turns into a test.
FOREIGN_SESSION_PROBES = [
    ("get", "/me"),
    ("get", "/me/permissions"),
    ("get", "/users"),
    ("get", "/roles"),
    ("get", "/settings/security-policy"),
    ("get", "/audit-log"),
    ("get", "/settings/company"),  # tenancy — 401 for everyone until 2026-08-10
    ("get", "/settings/regional"),
    ("get", "/lookups/uoms"),
    ("get", "/tenants/checklist"),
    ("get", "/plans"),  # rating
    ("get", "/charges"),
    ("get", "/premises"),  # metering
    ("get", "/routes"),
    ("get", "/assets"),  # assets
]


def _normalised(response) -> bytes:
    """The response body with its own trace id blanked — everything else raw."""
    body = response.content
    assert _TRACE_ID.search(body), f"no trace_id in {body!r}"
    return _TRACE_ID.sub(b'"trace_id": "<per-response>"', body)


def _trace_id_of(response) -> str:
    return json.loads(response.content)["trace_id"]


def _call(client, method, path, tenant):
    return getattr(client, method)(api_path(path, tenant))


# ── the reference 404s (three mechanisms, asserted to agree) ────────────────
def test_path_tenancy_the_three_404s_are_one_answer(idn):
    """Baseline for everything below: an unknown tenant, a foreign session and
    an absent row inside the caller's own tenant are the SAME response."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)

    unknown_tenant = api_get(alex, "/me", tenant=NO_SUCH_TENANT)
    foreign_session = api_get(alex, "/me", tenant=BM)
    absent_row = api_get(alex, f"/audit-log/{uuid.uuid4()}", tenant=SC)

    for response in (unknown_tenant, foreign_session, absent_row):
        assert response.status_code == 404
        assert response["Content-Type"] == "application/json"

    assert _normalised(foreign_session) == _normalised(unknown_tenant)
    assert _normalised(foreign_session) == _normalised(absent_row)
    # …and the trace ids are genuinely per-response (identical ones would mean
    # the comparison above is passing for the wrong reason).
    assert len({_trace_id_of(r) for r in (unknown_tenant, foreign_session, absent_row)}) == 3

    # The one ratified body (11b §3 G1): no catalog code exists for 404, so
    # `code` is null rather than an invented one, and nothing names a tenant.
    body = json.loads(foreign_session.content)
    assert body["code"] is None
    assert body["message_key"] == "errors.not-found"
    assert body["params"] == {} and body["field_errors"] == [] and body["br_ref"] is None
    assert b"bluemesa" not in foreign_session.content
    assert b"silvercreek" not in foreign_session.content


def test_path_tenancy_an_unauthenticated_unknown_tenant_is_the_same_404(idn):
    """The refusal must hold on the PUBLIC half too. `POST /api/{t}/auth/session`
    reaches require_tenant with no session at all — a different code path, and
    it is what an attacker probes first to enumerate tenants."""
    idn.seed_silvercreek()
    alex = signed_in_client(*ALEX)
    absent_row = api_get(alex, f"/audit-log/{uuid.uuid4()}", tenant=SC)

    probe = Client().post(
        api_path("/auth/session", NO_SUCH_TENANT),
        data={"email": "alex@silvercreek.example", "password": "Canyon2026rapids"},
        content_type="application/json",
    )
    assert probe.status_code == 404
    assert _normalised(probe) == _normalised(absent_row)
    # A REAL tenant with wrong credentials answers 401 AUTH-001, so the pair
    # {404, 401} tells a prober only "this slug is not a tenant" — which the
    # public availability check (S110) already answers by design.
    wrong_password = Client().post(
        api_path("/auth/session", SC),
        data={"email": "alex@silvercreek.example", "password": "nope"},
        content_type="application/json",
    )
    assert wrong_password.status_code == 401


# ── the control itself ──────────────────────────────────────────────────────
@pytest.mark.parametrize("method,path", FOREIGN_SESSION_PROBES)
def test_path_tenancy_a_foreign_session_is_404_on_every_tenant_endpoint(idn, method, path):
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)  # Silver Creek System Admin — a REAL admin

    own = _call(alex, method, path, SC)
    assert own.status_code == 200, own.content  # the same call works at home…

    foreign = _call(alex, method, path, BM)
    assert foreign.status_code == 404, foreign.content  # …and is absent next door
    assert foreign.status_code != 403  # HR-1: 403 would confirm Blue Mesa exists
    assert foreign.status_code != 401  # 401 would invite "try again here"
    # No silent switch: the refusal is the ratified 404 envelope — byte-identical
    # to the unknown-tenant answer on the SAME path — and carries nothing of
    # Silver Creek's.
    #
    # (AMENDED 2026-08-10: this was `own.content not in foreign.content`. Once the
    # sweep grew to cover the registries, `/routes` answered a bare `[]` at home
    # for a fresh tenant — a substring of the envelope's own `"field_errors":[]`
    # — so the containment check fired on a response that leaked nothing. The
    # comparison below is the stronger form of the same claim and does not
    # depend on how much data the caller happens to have.)
    unknown = _call(alex, method, path, NO_SUCH_TENANT)
    assert unknown.status_code == 404, unknown.content
    assert _normalised(foreign) == _normalised(unknown)
    assert foreign.content != own.content
    assert b"silvercreek" not in foreign.content
    # And the refusal does not touch the caller's cookie — the session is still
    # perfectly valid, just not HERE.
    assert "sbh_session" not in foreign.cookies
    assert _call(alex, method, path, SC).status_code == 200


@pytest.mark.parametrize(
    "path", ["/settings/company", "/tenants/checklist", "/plans", "/premises", "/assets"]
)
def test_path_tenancy_the_formerly_unreachable_endpoints_answer_at_home_and_404_next_door(
    idn, path
):
    """The gap that was pinned here is CLOSED — and closing it kept the ruling.

    Until 2026-08-10 these five answered **401 to everyone**: tenancy / rating /
    metering / assets declared no `authentication_classes`, so DRF never
    attached the identity session and a real cookie client was simply
    unauthenticated. This test used to assert exactly that ({401} for the
    caller's own tenant, a foreign one and an unknown one alike — a functional
    gap, not a leak) and predicted the endpoints would join the 404 sweep the day
    the class was wired. 09-infra/02 §10.14 called it the reason a signed-in
    browser saw most of the product come back empty.

    It is wired now, as the DRF *default* rather than 70 per-view declarations,
    so this asserts the other half of that prediction — for each path, at once:
      * the caller's OWN tenant now ANSWERS (the gap is really closed, not
        merely moved to a different refusal), and
      * a foreign tenant is still the byte-identical 404 the PO's path-tenancy
        ruling named as its acceptance criterion, and an unknown tenant is the
        same answer again (nothing about who exists leaks).
    The 404 halves are also covered endpoint-by-endpoint in the sweep above;
    they are repeated here so the record of what changed reads in one place."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)

    own = _call(alex, "get", path, SC)
    assert own.status_code == 200, own.content

    foreign = _call(alex, "get", path, BM)
    unknown = _call(alex, "get", path, NO_SUCH_TENANT)
    assert foreign.status_code == 404 and unknown.status_code == 404
    assert _normalised(foreign) == _normalised(unknown)
    assert own.content not in foreign.content
    assert b"silvercreek" not in foreign.content and b"bluemesa" not in foreign.content


def test_path_tenancy_a_foreign_write_is_refused_before_the_view_runs(idn):
    """404 is not enough on its own: the write must not HAPPEN. A Silver Creek
    System Admin posting into Blue Mesa is refused in authentication, so no row
    is created in either tenant and no membership is touched."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)
    before = IdentityUser.objects.count()

    response = api_post(
        alex,
        "/users",
        {"full_name": "Mallory Cross", "email": "mallory@bluemesa.example", "role": "system_admin"},
        tenant=BM,
    )

    assert response.status_code == 404
    assert IdentityUser.objects.count() == before
    assert not IdentityUser.objects.filter(email="mallory@bluemesa.example").exists()


def test_path_tenancy_the_refusal_is_recorded_server_side_only(idn):
    """BR-AUD-018: the denial leaves an attempt row (who/what/when/rule) — and
    NONE of it leaks into the response, which is why the bodies stay identical."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)
    idn.rows.clear()

    response = api_get(alex, "/users", tenant=BM)
    assert response.status_code == 404

    attempts = idn.rows_for(core_audit.REFUSAL_ATTEMPT_ACTION)
    assert len(attempts) == 1
    after = attempts[0]["after"]
    assert after["br_ref"] == "BR-IDN-006"  # one tenant per session
    assert after["path"] == api_path("/users", BM)
    assert after["refused"] is True
    # The recorded rule is nowhere in the body — that is the whole point.
    assert b"BR-IDN-006" not in response.content


def test_path_tenancy_the_session_row_carries_its_tenant(idn):
    """Control #1: the binding is DATA, not an inference from the request."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)
    session = Session.objects.get(pk=session_id_of(alex))
    assert session.tenant_id == idn.silvercreek.id
    assert session.user.tenant_id == idn.silvercreek.id  # BR-IDN-029 per-tenant users


def test_path_tenancy_one_browser_holds_one_tenant_at_a_time(idn):
    """Recorded by the PO with the ruling: BR-IDN-029 is unchanged in law, but a
    single cookie jar means signing into Blue Mesa REPLACES the Silver Creek
    cookie. Proven here so nobody discovers it as a bug in the field."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    browser = signed_in_client(*ALEX)
    first = session_id_of(browser)
    assert api_get(browser, "/me", tenant=SC).status_code == 200

    api_post(
        browser,
        "/auth/session",
        {"email": JORDAN[0], "password": JORDAN[1], "keep_signed_in": False},
        tenant=BM,
    )
    second = session_id_of(browser)
    assert second != first
    assert api_get(browser, "/me", tenant=BM).status_code == 200
    assert api_get(browser, "/me", tenant=SC).status_code == 404  # the old tenant is now foreign
    # The replaced session is still alive server-side (sign-in never revokes
    # another device's session) — it simply is not in this jar any more.
    assert Session.objects.get(pk=first).revoked_at is None
    assert api_get(client_with_session(first), "/me", tenant=SC).status_code == 200


def test_path_tenancy_sign_out_on_a_foreign_path_revokes_nothing(idn):
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)
    sid = session_id_of(alex)

    refused = alex.delete(api_path("/auth/session", BM))
    assert refused.status_code == 404
    assert Session.objects.get(pk=sid).revoked_at is None  # not a remote kill switch

    assert alex.delete(api_path("/auth/session", SC)).status_code == 204
    assert Session.objects.get(pk=sid).revoked_at is not None


# ── the no-tenant surface: public, provisioning, platform ───────────────────
def test_path_tenancy_the_public_surface_needs_no_tenant(idn):
    """`/api/public/…` answers with no tenant in the path and no session — it
    has to, because it is what a visitor uses BEFORE any tenant exists."""
    idn.seed_silvercreek()
    visitor = Client()
    assert visitor.get("/api/public/pricing-plans").status_code == 200
    check = visitor.get("/api/public/subdomain-check?subdomain=silvercreek")
    assert check.status_code == 200 and check.json()["problem"] == "taken"
    # …and no tenant context leaked into a request that named none.
    assert core_tenancy.current_tenant_id() is None


def test_path_tenancy_platform_paths_are_scoped_by_the_session(idn):
    """`/api/jobs/{id}` and `/api/exports/…` carry NO tenant segment (the fixed
    contract), yet serve tenant-scoped records. The scope comes from the session
    row — so a foreign job id is the same plain 404 as an unknown one."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    previous = core_jobs._store
    core_jobs.set_job_store(tenancy_services.JobStore())
    try:
        with core_tenancy.tenant_context(idn.silvercreek.id):
            mine = core_jobs.enqueue("audit_export", payload={})
        with core_tenancy.tenant_context(idn.bluemesa.id):
            theirs = core_jobs.enqueue("audit_export", payload={})
    finally:
        core_jobs.set_job_store(previous)

    alex = signed_in_client(*ALEX)
    assert alex.get(f"/api/jobs/{mine['id']}").status_code == 200
    foreign = alex.get(f"/api/jobs/{theirs['id']}")
    unknown = alex.get(f"/api/jobs/{uuid.uuid4()}")
    assert foreign.status_code == 404 and unknown.status_code == 404
    assert _normalised(foreign) == _normalised(unknown)
    # No session at all → 401 (unauthenticated), which is a different question
    # from "does this job exist" and is answered before scope is even known.
    assert Client().get(f"/api/jobs/{mine['id']}").status_code == 401


def test_path_tenancy_no_route_can_be_shadowed_by_a_tenant_name(idn):
    """`api`, `jobs`, `exports`, `public`, `tenants`, `health`, `signup`,
    `signin`, `pricing`, `static`, `assets` are reserved (BR-TEN-011 as amended
    2026-08-10) — and the kernel refuses to READ the platform ones as tenants
    even if a row somehow existed."""
    for segment in sorted(core_tenancy.NON_TENANT_SEGMENTS):
        assert core_tenancy.tenant_slug_of(f"/api/{segment}/anything") is None
        assert tenancy_selectors.subdomain_problem(segment) == "reserved"
    for name in ("api", "signup", "signin", "pricing", "static", "assets"):
        assert tenancy_selectors.subdomain_problem(name) == "reserved"


# ── live Postgres: the same control, with RLS actually switched on (G5) ─────
@pytest.mark.isolation
@requires_postgres
def test_path_tenancy_isolation_foreign_session_is_404_under_real_rls(idn):
    """Everything above runs on sqlite, where RLS does not exist and the GUC is
    a recording fake. Here the SHIPPING kernel writes `app.tenant_id` on a real
    Postgres session for every request, so the refusal is proven against the
    database that will actually serve it."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client(*ALEX)

    assert api_get(alex, "/users", tenant=SC).status_code == 200
    foreign = api_get(alex, "/users", tenant=BM)
    unknown = api_get(alex, "/users", tenant=NO_SUCH_TENANT)
    assert foreign.status_code == 404 and unknown.status_code == 404
    assert _normalised(foreign) == _normalised(unknown)
    # The GUC did not survive the refused request (HR-1: no context outlives a
    # request on a pooled connection).
    assert core_tenancy.current_tenant_id() is None


@pytest.mark.isolation
@requires_postgres
def test_path_tenancy_isolation_the_session_lookup_survives_a_foreign_guc(idn, rls):
    """Why `session_by_id` may not `select_related("user")`.

    `sessions` is RLS-exempt (it has to be readable to ESTABLISH context), but
    `users` is not. Joining them evaluates the users policy under whatever
    `app.tenant_id` the request arrived with — the foreign tenant's, or none at
    all on the platform paths — and an INNER JOIN would then drop the session
    row itself. The endpoint would answer 401 "unknown session" where the law
    says 404, and `/api/jobs/{id}` would stop working entirely. Asserted under
    the non-superuser probe role, where the policies are genuinely consulted.
    """
    idn.seed_silvercreek()
    alex = signed_in_client(*ALEX)
    sid = session_id_of(alex)

    with live_tenant_context(idn.bluemesa.id):
        # The session row is reachable under ANOTHER tenant's context …
        assert rls.count("sessions", "id = %s", [sid]) == 1
        # … but its user is not, so the join that used to be here finds
        # nothing. (Raw SQL rather than probe.count(): that helper only accepts
        # a single constant-shaped table name, and a JOIN is the whole point.)
        joined = rls.scalar(
            "SELECT count(*) FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id = %s",
            [sid],
        )
        assert joined == 0, "users is RLS'd: a select_related here would hide the session"


@pytest.mark.isolation
@requires_postgres
def test_path_tenancy_isolation_a_foreign_session_reads_no_row(idn, rls):
    """The belt to the app layer's braces: even if the 404 above regressed into
    a 200, the DATABASE would still refuse. Under Blue Mesa's GUC, not one
    Silver Creek user row is reachable by the probe role."""
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()

    with live_tenant_context(idn.bluemesa.id):
        assert rls.count("users", "id = %s", [str(users.alex.id)]) == 0
        assert str(users.alex.id) not in rls.ids("users")
    with live_tenant_context(idn.silvercreek.id):
        assert str(users.alex.id) in rls.ids("users")


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-01@87ece49 (path-tenancy lane — the control the PO ruling 2026-08-10 names as the acceptance criterion; co-packet US-IDN-003@402b6db for the session half)
# generated: 2026-08-10 by story-coder (path-tenancy lane) · AMENDED 2026-08-10 by story-coder (deploy-blocker lane — 09-infra/02 §10.14)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the SPA route half is a concurrent lane) F✔ G✔ H=n/a(not a 🔒 file)
# gates: black✔ · ruff --select E4,E7,E9,F reports 17 F811 here — pytest fixture-shadowing, the identical pattern every test file in this suite carries; recorded, not claimed clean · pytest tests/test_path_tenancy_session_binding.py 21 passed / 3 postgres-only skipped (sqlite) · `-m isolation` on live Postgres 3 passed · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [deploy-blocker lane 2026-08-10] pytest tests/test_path_tenancy_session_binding.py 30 passed / 3 postgres-only skipped · suite 868 passed / 9 skipped (818 baseline) · `-m isolation` 32 passed / 12 skipped
# exceptions: `trace_id` is excluded from the byte comparison and asserted to DIFFER per response — identical trace ids would be the real defect · the sqlite tier cannot prove RLS, so the three isolation cases carry the vendor guard rather than a bare skip · [deploy-blocker lane 2026-08-10] the pinned GAP test is now a CLOSURE test: tenancy/rating/metering/assets answer their own tenant and 404 next door, exactly as this file predicted they would "the day their lane wires IdentitySessionAuthentication" — the sweep grew from 6 endpoints to 15 and needed no per-endpoint change · one assertion was replaced rather than kept: `own.content not in foreign.content` fired on `/routes`, whose home answer for a fresh tenant is a bare `[]` — a substring of the envelope's own `"field_errors":[]`. It is now a normalised byte-comparison of the foreign 404 against the unknown-tenant 404 on the SAME path, which is the stronger form of the same claim and does not depend on how much data the caller happens to have
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

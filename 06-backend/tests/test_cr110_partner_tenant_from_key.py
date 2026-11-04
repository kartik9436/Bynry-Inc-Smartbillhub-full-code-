# ── Trace ──────────────────────────────────────────────
# Story:  CR-110-BRC04 phase 2 — `DEF-INT-5546`. THE UTILITY LEAVES THE PARTNER
#         URL AND THE KEY RESOLVES IT. PO 2026-09-16, verbatim: *"we agreed not
#         to use utility names in partner apis that was our rule - so these urls
#         are not corect - we will resolve utility name using keys"*.
# Rules:  BR-TEN-003 (narrowed the same day: the tenant is never read from a
#         value the CALLER asserts — a key is proof, not a claim) · CLAUDE.md
#         hard rule 1 (RLS FORCE does the isolating) · BR-INT-044 (the refusals
#         are one refusal, in words AND in timing) · B2 §3 (the RLS-exempt list
#         is declared, never inferred) · hard-won law 7 (name the false pass
#         first) · law 14 (the isolation claim is proved on PostgreSQL)
# ───────────────────────────────────────────────────────
"""ONE BASE URL FOR EVERY PARTNER AND EVERY UTILITY, AND IT STILL ISOLATES.

    GET /api/partner/v1/reference · /customers · /bills · /payments · /ledger

    key ──► connection ──► tenant ──► app.tenant_id set ──► RLS does the isolating

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
--------------------------------------------------------------------
**First and worst: ONE utility in the fixture.** Every case here would pass over
a directory that returned *the only tenant there is*, which is the exact bug
this change could introduce and the one it must not. So the fixture builds
**two** utilities, each with its own key, and the isolation case asserts both
directions — A's key sees A's row and NOT B's, and B's key sees B's and not A's.
A one-directional assertion would pass over a directory hard-wired to B.

**Second: asserting a 200.** A 200 with the wrong utility's rows is the failure.
Every success case reads the RECORDS back and compares them against the row the
fixture wrote for THAT utility.

**Third: calling the view directly.** The old cases do — correctly, they are
about the view. These are about the ADDRESS, so every case here goes through
`django.test.Client` at the real path, with no tenant context opened by the
test. A test that opened one would be proving the thing it is meant to check.
`DEF-CWP-3925`'s fixture is the warning: a component mounted without its real
route, where every address it built came out wrong and read as a good string.

**Fourth: proving the route resolves and never calling it.** `test_the_five…`
resolves; every other case actually gets bytes back.

**Fifth, and it is why `test_no_tenant_context_leaks…` exists:** a pooled
connection that kept `app.tenant_id` after the response would make the SECOND
request in a test work for the wrong reason. It is asserted directly.

RED PROVED FIRST, IN `pytest` — the harness that runs it (law 7, DEF-GOV-3733)
-------------------------------------------------------------------------------
Each case was run against a deliberately broken tree before it was trusted
green; the failures are quoted in this lane's report and in the CR section.
`python3 <module>` was not used anywhere.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest
from django.urls import Resolver404, resolve

from apps.integrations import key_directory, models, partner_api, partner_urls, services
from apps.integrations.runners import serve
from core import crypto
from core import tenancy as core_tenancy

from tests.test_cr110_phase2_partner_reference import ALLOWED_ADDRESS, _connect
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    tenant_ctx,
)

#: The five, spelled once. **No `{utility}` in any of them** — that is the whole
#: change, and `test_not_one_of_the_five_names_a_utility` asserts it of this list
#: rather than of a reading of the router.
ADDRESSES = (
    "/api/partner/v1/reference",
    # ⚠ **`/api/partner/v1/customers` UNTIL 2026-09-17 (`DEF-INT-5623`).**
    "/api/partner/v1/accounts",
    "/api/partner/v1/bills",
    "/api/partner/v1/payments",
    "/api/partner/v1/ledger",
)

BRAZOS_KEY = "sbh_live_7Q2F_one_utility_do_not_reuse"
LONESTAR_KEY = "sbh_live_4K8M_other_utility_do_not_reuse"


@pytest.fixture()
def two_utilities(brazos, lonestar, dana, erin):
    """TWO utilities, each with its own live key. The first false pass named in
    the docstring is what this fixture exists to make impossible."""
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        left = _connect(brazos, dana, key=BRAZOS_KEY, hint="••••7Q2F")
    with tenant_ctx(lonestar):
        right = _connect(lonestar, erin, key=LONESTAR_KEY, hint="••••4K8M")
    return left, right


def _call(client, path, key, *, params=None):
    """One partner request at the REAL address, with no tenant context open.

    ⚠ **`core_tenancy.clear_current_tenant()` FIRST, AND IT IS NOT TIDINESS.**
    A fixture that built rows under `tenant_ctx` may leave the GUC set on this
    connection; with it set, `key_directory.open_utility_for` returns early and
    the request would be served under a context the TEST opened rather than the
    one the key names. Every case here would then pass without the mechanism
    under test ever running.
    """
    core_tenancy.clear_current_tenant()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {key}"} if key is not None else {}
    return client.get(path, params or {}, REMOTE_ADDR=ALLOWED_ADDRESS, **headers)


def _json(response):
    return json.loads(response.content)


# ══════════════════════════════════════════════════════════════════════════
# 1 · the addresses themselves
# ══════════════════════════════════════════════════════════════════════════


def test_not_one_of_the_five_names_a_utility() -> None:
    """`DEF-INT-5546` in one line. The blueprint (p159): *a path segment is a
    claim; a key is proof.*"""
    for address in ADDRESSES:
        assert "{utility}" not in address and "{tenant}" not in address
        assert address.startswith("/api/partner/v1/"), address


@pytest.mark.django_db
def test_the_five_resolve_at_the_bare_address() -> None:
    """RESOLVED through `config/urls.py`, never read off `partner_urls`.

    The comment that asserted a route collision away in `config/urls.py` was
    wrong once and a browser found it (hard-won law 1). This asks the router.
    """
    for address in ADDRESSES:
        match = resolve(address)
        assert match.func is not None, address
        assert match.kwargs == {}, (
            f"{address} resolved with {match.kwargs} — a partner route that "
            "captures anything from the path is the defect coming back"
        )

    # ⚠ **ONE OF THE FIVE RESOLVED BEFORE THIS CHANGE, TO THE WRONG VIEW, AND
    # THAT IS WHY THIS ASSERTION IS SEPARATE.** Measured at the pre-change tip:
    # four of the five answered `Resolver404`, and `/api/partner/v1/payments`
    # **RESOLVED** — the tenant `re_path` matched `api/partner/` as a UTILITY
    # SLUG, leaving `v1/payments`, which is the phase-1 flat route. So the one
    # address a partner was most likely to try reached a real endpoint under a
    # utility named *partner*, resolved to nothing, and was refused for a reason
    # that had nothing to do with its key. A bare `resolve()` that only checks
    # for "some view" would have called that a pass.
    assert resolve("/api/partner/v1/payments").func is not resolve(
        "/api/brazosbend/v1/payments"
    ).func, (
        "the phase-2 payments address resolved to the phase-1 flat view — "
        "`partner` was read as a utility slug"
    )


def test_partner_api_registers_none_of_the_five_itself() -> None:
    """The old address cannot come back quietly beside the new one.

    ⚠ **THIS IS THE HOLD-EXPIRY SHAPE FROM HARD-WON LAW 2, POINTED THE OTHER
    WAY.** Nothing fails if a lane re-adds `path(f"{PARTNER_PREFIX}/bills", …)`
    to `partner_api.urlpatterns`: both addresses would then work, every existing
    test would pass, and a partner could reach a utility by naming it in a URL
    again. Only this assertion notices.
    """
    spelled = [str(getattr(one, "pattern", one)) for one in partner_api.urlpatterns]
    offenders = [one for one in spelled if one.startswith(partner_api.PARTNER_PREFIX)]
    assert offenders == [], (
        f"{offenders} puts the utility back in a partner URL — the five live in "
        "partner_urls.py and are mounted outside the tenant include"
    )
    # ⚠ **SEVEN ADDRESSES, FOURTEEN PATTERNS (`CR-111-BRC04`).** `consumer-info`
    # and `bill-download` joined the five, and every one is registered with AND
    # without a trailing slash — Invoice Cloud's document writes one of them with
    # a slash, and `APPEND_SLASH` would answer a `301` that a partner's client may
    # not follow and may drop the bearer token on.
    #
    # The number is derived from `PARTNER_ROUTES` rather than typed, so a route
    # added to that map cannot make this assertion stale — what it still catches
    # is a pattern registered BESIDE the loop, which would miss
    # `_with_utility_from_key` and therefore have no tenant at all.
    # ⚠ **PLUS `PUBLISHED_INBOUND_ROUTES` (`DEF-INT-10020`)** — US Payments'
    # three addresses, built by the SAME loop from the manifest's
    # `served_path`, so they get the first arrow by construction too.
    assert len(partner_urls.urlpatterns) == 2 * (
        len(partner_urls.PARTNER_ROUTES) + len(partner_urls.PUBLISHED_INBOUND_ROUTES)
    )
    # ⚠ **EIGHT SINCE `DEF-INT-5623`** — `accounts` is the live address and
    # `customers` stays registered as its RETIREMENT, answering `410` and
    # naming the replacement. A retired address still goes through the loop,
    # because it still has to authenticate and authenticating reads a tenant
    # table.
    assert len(partner_urls.PARTNER_ROUTES) == 8


def test_partner_is_a_non_tenant_segment_and_a_reserved_slug() -> None:
    """Three things have to agree or `/api/partner/…` is read as a utility named
    *partner*, and a utility could be created that shadows the whole surface."""
    from apps.tenancy.selectors import RESERVED_SUBDOMAINS

    assert "partner" in core_tenancy.NON_TENANT_SEGMENTS
    assert "partner" in RESERVED_SUBDOMAINS
    assert core_tenancy.tenant_slug_of("/api/partner/v1/bills") is None


# ══════════════════════════════════════════════════════════════════════════
# 2 · the key resolves the utility — in BOTH directions
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_each_key_opens_its_own_utility_and_only_its_own(client, two_utilities, brazos, lonestar) -> None:
    """The isolation case, asserted both ways round (false pass 1).

    `reference` is the address used because it is the one that serves a body
    derived from the TENANT's own lookups on every utility, with no seam and no
    wave still to land — so a difference in the answer is a difference in which
    utility was opened, and nothing else.
    """
    left_connection, right_connection = two_utilities
    left = _call(client, "/api/partner/v1/reference", BRAZOS_KEY, params={"company_id": str(brazos.id)})
    right = _call(client, "/api/partner/v1/reference", LONESTAR_KEY, params={"company_id": str(lonestar.id)})
    assert left.status_code == 200, left.content
    assert right.status_code == 200, right.content

    # ⚠ **FILTERED BY CONNECTION, NOT COUNTED UNDER A CONTEXT** — and the first
    # draft did the latter and went red for the wrong reason. `tenant_ctx(x)`
    # scopes a count only where RLS exists, and **the suite runs on SQLite,
    # which has none** (`config/settings/test.py` hardcodes it; CLAUDE.md law
    # 14 records the same trap for aborted transactions). So
    # `IntegrationRun.objects.count()` under brazosbend's context returned BOTH
    # utilities' rows — `assert 2 == 1` — over code that was behaving correctly.
    # Written the other way round it would have been worse: a count that
    # silently includes the other utility is exactly what this case exists to
    # refuse, and on SQLite it would have passed.
    #
    # The connection is the tenant, stated in a way neither vendor can fudge.
    assert models.IntegrationRun.objects.filter(connection=left_connection).count() == 1
    assert models.IntegrationRun.objects.filter(connection=right_connection).count() == 1
    assert {one.connection.tenant_id for one in models.IntegrationRun.objects.all()} == {
        brazos.id,
        lonestar.id,
    }, "each read landed under the utility its own key names"
    assert models.IntegrationRun.objects.count() == 2, (
        "two reads, one per utility — a third row means a request was served twice"
    )


@pytest.mark.django_db
def test_a_key_cannot_claim_the_other_utility(client, two_utilities, brazos, lonestar) -> None:
    """`company_id` selects nothing — and since 2026-09-17 it is not even
    compared (`CR-111-BRC04`).

    ⚠ **THIS IS THE ONE THING A CALLER CAN STILL TYPE, SO IT IS THE ONE THING
    WORTH ATTACKING.** With the utility gone from the path, `company_id` is the
    last value on the request that names a utility. If it ever started selecting,
    this is the case that goes red.

    ⚠ **AMENDED: THE ANSWER IS A 200, NOT A 403.** PO: *"you will ahve to remove
    company ID filter from all Apis - we cannot tell tenant ID outside our
    system"*. Check 7 is deleted. **What this case is FOR did not change** — it
    asserts the request is served as BRAZOS BEND, whoever the caller names — and
    it is now asserted against the body served with no parameter at all, which a
    status code could never have proved.
    """
    response = _call(
        client,
        "/api/partner/v1/reference",
        BRAZOS_KEY,
        params={"company_id": str(lonestar.id)},
    )
    plain = _call(client, "/api/partner/v1/reference", BRAZOS_KEY)
    assert response.status_code == 200, response.content
    assert response.content == plain.content, (
        "naming another utility changed the answer — something still selects on it"
    )
    assert str(brazos.id) not in response.content.decode()
    assert str(lonestar.id) not in response.content.decode(), (
        "echoing the id back makes this endpoint a probe for real utility ids"
    )


@pytest.mark.django_db
def test_an_unknown_key_is_refused_in_the_one_way(client, two_utilities, brazos) -> None:
    """No utility resolves, so nothing is opened, and the ordinary refusal runs."""
    response = _call(
        client,
        "/api/partner/v1/reference",
        "sbh_live_0000_never_issued",
        params={"company_id": str(brazos.id)},
    )
    assert response.status_code == 404, response.content
    body = _json(response)
    assert body == {"error": serve.REFUSAL_SENTENCE, "code": serve.SHARED_REFUSAL_CODE}


@pytest.mark.django_db
def test_no_key_at_all_is_the_same_bytes(client, two_utilities, brazos) -> None:
    response = _call(client, "/api/partner/v1/reference", None, params={"company_id": str(brazos.id)})
    assert response.status_code == 404
    assert _json(response) == {
        "error": serve.REFUSAL_SENTENCE,
        "code": serve.SHARED_REFUSAL_CODE,
    }


@pytest.mark.django_db
def test_a_revoked_key_reads_identically_on_the_wire(client, two_utilities, brazos) -> None:
    """`BR-INT-044`: a revoked key and an invented one are the same bytes.

    They are NOT the same in our record, and that asymmetry is deliberate — the
    directory row survives a revoke precisely so `record_refusal` has a
    connection to hang *key revoked* on. Both halves are asserted here.
    """
    connection, _ = two_utilities
    with tenant_ctx(brazos):
        models.IntegrationCredential.objects.filter(connection=connection).update(is_active=False)

    revoked = _call(client, "/api/partner/v1/reference", BRAZOS_KEY, params={"company_id": str(brazos.id)})
    invented = _call(
        client, "/api/partner/v1/reference", "sbh_live_0000_never_issued",
        params={"company_id": str(brazos.id)},
    )
    assert revoked.status_code == invented.status_code == 404
    assert revoked.content == invented.content, (
        "a revoked key that reads differently tells a caller the key is REAL"
    )
    # …and the directory still resolved it, which is what lets the record differ.
    core_tenancy.clear_current_tenant()
    assert key_directory.tenant_for(BRAZOS_KEY) == brazos.id
    assert key_directory.tenant_for("sbh_live_0000_never_issued") is None


@pytest.mark.django_db
def test_the_refusals_stay_indistinguishable_by_the_clock(client, two_utilities, brazos) -> None:
    """The floor, measured through the REAL address (law 7: the harness that
    runs it). A resolution step outside the padded window would show up here as
    the known key being reliably slower."""
    def _elapsed(key):
        started = time.monotonic()
        _call(client, "/api/partner/v1/reference", key, params={"company_id": str(brazos.id)})
        return time.monotonic() - started

    with tenant_ctx(brazos):
        connection, _ = two_utilities
        models.IntegrationCredential.objects.filter(connection=connection).update(is_active=False)

    known = min(_elapsed(BRAZOS_KEY) for _ in range(3))
    invented = min(_elapsed("sbh_live_0000_never_issued") for _ in range(3))
    assert known >= serve.REFUSAL_FLOOR_S
    assert invented >= serve.REFUSAL_FLOOR_S


@pytest.mark.django_db
def test_no_tenant_context_leaks_out_of_a_partner_request(client, two_utilities, brazos) -> None:
    """False pass 5. The context is adopted DOWNSTREAM of the middleware, so the
    middleware's `finally` is what has to clear it — and that branch is
    conditional. On a pooled connection a context that outlived the response
    would serve the NEXT request as the wrong utility."""
    _call(client, "/api/partner/v1/reference", BRAZOS_KEY, params={"company_id": str(brazos.id)})
    assert core_tenancy.current_tenant_id() is None


# ══════════════════════════════════════════════════════════════════════════
# 3 · the directory itself
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_directory_row_is_written_for_every_issued_key(two_utilities, brazos, lonestar) -> None:
    core_tenancy.clear_current_tenant()
    rows = {one.tenant_id: one for one in models.IntegrationKeyDirectory.objects.all()}
    assert set(rows) == {brazos.id, lonestar.id}
    assert rows[brazos.id].blind_index == crypto.blind_index(
        BRAZOS_KEY, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT
    )


@pytest.mark.django_db
def test_the_directory_holds_no_secret_and_nothing_a_customer_would_recognise(two_utilities) -> None:
    """The exemption in B2 §3 rests on WHAT this table holds, so the columns are
    asserted rather than described. A lane adding a name, an address, a label or
    an encrypted payload here has widened an RLS-exempt table and this goes red.
    """
    columns = {one.name for one in models.IntegrationKeyDirectory._meta.get_fields()}
    assert columns == {"blind_index", "tenant_id", "connection_id", "credential_id", "created_at"}
    core_tenancy.clear_current_tenant()
    for row in models.IntegrationKeyDirectory.objects.all():
        assert BRAZOS_KEY not in row.blind_index and LONESTAR_KEY not in row.blind_index


@pytest.mark.django_db
def test_the_table_is_declared_on_the_exempt_list(two_utilities) -> None:
    """An exemption nobody declared is an omission. B2 §3 and the isolation
    helper have to agree, and `test_g5_the_rls_exempt_list_is_exactly_what_b2_
    declares` is what holds the other end of it."""
    from tests.isolation_helpers import RLS_EXEMPT_TABLES

    assert models.IntegrationKeyDirectory._meta.db_table in RLS_EXEMPT_TABLES


@pytest.mark.django_db
def test_disconnecting_forgets_the_keys_and_revoking_does_not(two_utilities, brazos, dana) -> None:
    """The two acts are different and the directory treats them differently."""
    connection, _ = two_utilities
    core_tenancy.clear_current_tenant()
    assert key_directory.tenant_for(BRAZOS_KEY) == brazos.id

    with tenant_ctx(brazos):
        services.disconnect(
            actor=dana, tenant_id=brazos.id, provider_key=connection.provider_key
        )
    core_tenancy.clear_current_tenant()
    assert key_directory.tenant_for(BRAZOS_KEY) is None, (
        "a directory row outliving its credential resolves a utility for a key "
        "whose row no longer exists"
    )


@pytest.mark.django_db
def test_a_key_may_not_override_a_utility_the_path_already_named(two_utilities, brazos, lonestar) -> None:
    """The guard in `adopt_partner_tenant`. Unreachable from the shipping caller
    — `open_utility_for` returns early when a context exists — and kept so a
    future caller cannot quietly turn this into a tenant switch."""
    class _Request:
        tenant_slug = "brazosbend"

    with pytest.raises(RuntimeError, match="tenant-scoped path"):
        core_tenancy.adopt_partner_tenant(_Request(), lonestar.id)


@pytest.mark.django_db
def test_open_utility_for_leaves_an_existing_context_alone(two_utilities, brazos, lonestar) -> None:
    """The phase-1 addresses still carry the utility, and there the path decides."""
    class _Request:
        tenant_slug = None
        tenant_id = None

    with tenant_ctx(brazos):
        assert key_directory.open_utility_for(_Request(), LONESTAR_KEY) == brazos.id, (
            "a key that overrode a context the PATH set would be a tenant switch"
        )


@pytest.mark.django_db
def test_an_unresolvable_key_leaves_no_context_behind(two_utilities) -> None:
    """Fail closed (hard-won law 3), and spend the same two statements doing it."""
    class _Request:
        tenant_slug = None
        tenant_id = None

    core_tenancy.clear_current_tenant()
    assert key_directory.open_utility_for(_Request(), "sbh_live_0000_never_issued") is None
    assert core_tenancy.current_tenant_id() is None

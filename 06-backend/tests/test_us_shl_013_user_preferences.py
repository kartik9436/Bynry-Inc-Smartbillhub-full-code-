# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-013 — preference storage (EP-SHL-05)
# Defect:   DEF-647 — the column selector never saves
# Rules:    BR-SHL-024 (one row per tenant+user+key; ≤128-char dotted key;
#           ≤32 KB value; last-write-wins; unknown key = absent; RLS) ·
#           BR-SHL-027 (server-side ALWAYS) · BR-SHL-013 (`table.‹screen›.columns`)
# Tests:    US-SHL-013 TC-3 (roundtrip) · TC-4 (oversize refused, stored value
#           untouched) · TC-6 (unknown key absent, no error) · TC-7 (isolation,
#           both halves: another TENANT and another USER)
# ───────────────────────────────────────────────────────
"""US-SHL-013 TCs for `GET|PUT /user-preferences/{key}`.

⚠ **THIS SUITE EXISTS BECAUSE THE ROUND TRIP DID NOT (DEF-647).** The model,
the migration, the RLS policy and the client's pure column transitions were all
built and fully tested; nothing asked whether a stored value could be read back.
So every test here crosses the wire — `Client()` over the routes registered in
`config/urls.py` — rather than calling the service directly. A service-level
test would have passed on the shipped tree too, because the service is not what
was missing.

TC-7 has TWO halves and they are different mechanisms (see
`apps/tenancy/preferences.py`): the TENANT half is the database's (RLS FORCE,
proved under the non-superuser probe below) and the USER half is the queryset's
(proved over HTTP, because there is no per-user policy and there should not be).
"""

import pytest

from apps.tenancy.models import UserPreference
from apps.tenancy.preferences import KEY_MAX_CHARS, VALUE_MAX_BYTES
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
    api_put,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

#: BR-SHL-013's key for the S17 Accounts list — the exact string
#: `DataTable.tsx` builds from `config.screenId`.
S17_COLUMNS = "table.S17.columns"

#: An ORDERED array of column keys: exactly what `toggleColumnVisible` /
#: `moveColumnUp` / `moveColumnDown` return, which is what the client persists.
CHOSEN = ["account_no", "balance", "name"]


def _alex():
    return signed_in_client("alex@silvercreek.example", "Canyon2026rapids")


def _priya():
    return signed_in_client("priya@silvercreek.example", "Meadow2026sage")


# ── TC-3 — the roundtrip that did not exist ─────────────────────────────────


def test_us_shl_013_tc3__column_choice_written_then_read_back(idn):
    """The whole defect, in four lines: PUT the chosen order, GET it back.

    On the shipped tree this test could not be written at all — `PUT` answered
    404 because `config/urls.py` registered no preferences route.
    """
    idn.seed_silvercreek()
    alex = _alex()

    written = api_put(alex, f"/user-preferences/{S17_COLUMNS}", {"value": CHOSEN})
    assert written.status_code == 200, written.content
    assert written.json() == {"key": S17_COLUMNS, "value": CHOSEN}

    read = api_get(alex, f"/user-preferences/{S17_COLUMNS}")
    assert read.status_code == 200, read.content
    # ORDER is part of the value (IS-5 reorder) — not a set comparison.
    assert read.json()["value"] == CHOSEN


def test_us_shl_013_tc3__a_second_write_wins_and_leaves_one_row(idn):
    """BR-SHL-024 "last-write-wins" + "one row per (user, tenant, key)"."""
    idn.seed_silvercreek()
    alex = _alex()
    api_put(alex, f"/user-preferences/{S17_COLUMNS}", {"value": CHOSEN})
    api_put(alex, f"/user-preferences/{S17_COLUMNS}", {"value": ["name"]})

    assert api_get(alex, f"/user-preferences/{S17_COLUMNS}").json()["value"] == ["name"]
    assert UserPreference.objects.filter(key=S17_COLUMNS).count() == 1


def test_us_shl_013_tc3__the_route_is_registered_in_config_urls(idn):
    """Hard-won law 2, asserted rather than assumed.

    DEF-647 was an unwired ROUND TRIP; four modules in `config/urls.py` already
    carry a comment about an unreachable half. Resolving through the real URLconf
    means losing the include is a RED test, not a silent 404 in production.
    """
    from django.urls import resolve

    match = resolve(f"/api/silvercreek/user-preferences/{S17_COLUMNS}")
    # `@api_view` returns a generated `WrappedAPIView.as_view()`, so the name to
    # assert on is the MODULE it was generated in, not the function's own.
    assert match.func.__module__ == "apps.tenancy.preferences_api"
    assert match.kwargs == {"key": S17_COLUMNS}


# ── TC-6 — an unknown key is ABSENT, not an error ───────────────────────────


def test_us_shl_013_tc6__unknown_key_reads_absent_with_no_error(idn):
    """BR-SHL-024: "unknown keys read as absent (callers fall back to defaults)".

    200 + `value: null`, never 404 — the client's fallback is "use the declared
    defaults", and a client that must catch an error to learn that will stop
    catching it.
    """
    idn.seed_silvercreek()
    response = api_get(_alex(), "/user-preferences/table.S99.columns")
    assert response.status_code == 200
    assert response.json() == {"key": "table.S99.columns", "value": None}


# ── TC-4 (negative) — the 32 KB cap refuses BEFORE it writes ────────────────


def test_us_shl_013_tc4__oversize_value_is_refused_and_leaves_the_stored_one(idn):
    idn.seed_silvercreek()
    alex = _alex()
    api_put(alex, f"/user-preferences/{S17_COLUMNS}", {"value": CHOSEN})

    oversize = ["x" * 64] * ((VALUE_MAX_BYTES // 67) + 40)  # comfortably > 32 KB
    refused = api_put(alex, f"/user-preferences/{S17_COLUMNS}", {"value": oversize})
    assert refused.status_code == 422
    body = refused.json()
    assert body["code"] == "BIZ-CAP"
    assert body["br_ref"] == "BR-SHL-024"
    assert body["params"]["max_bytes"] == VALUE_MAX_BYTES
    # "existing stored value untouched" — the refusal ran before any write.
    assert api_get(alex, f"/user-preferences/{S17_COLUMNS}").json()["value"] == CHOSEN


@pytest.mark.parametrize(
    "key",
    [
        "columns",  # no namespace at all
        "billing.S17.columns",  # a namespace BR-SHL-024 does not name
        "table.",  # trailing dot, empty segment
        "table..columns",  # empty middle segment
        "table." + "x" * KEY_MAX_CHARS,  # over the 128-char cap
    ],
)
def test_us_shl_013__key_grammar_is_refused_not_normalised(idn, key):
    """BR-SHL-024's key law. A typo'd key that WROTE would be a row nothing ever
    reads — invisible forever behind the rule's own "unknown keys read as
    absent" clause, which is why the grammar refuses instead of storing."""
    idn.seed_silvercreek()
    response = api_put(_alex(), f"/user-preferences/{key}", {"value": []})
    assert response.status_code in (404, 422), response.content
    if response.status_code == 422:
        assert response.json()["br_ref"] == "BR-SHL-024"
    assert UserPreference.objects.count() == 0


def test_us_shl_013__put_without_a_value_field_is_refused(idn):
    idn.seed_silvercreek()
    response = api_put(_alex(), f"/user-preferences/{S17_COLUMNS}", {"columns": CHOSEN})
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-001"
    assert UserPreference.objects.count() == 0


def test_us_shl_013__a_signed_out_caller_cannot_read_or_write(idn):
    """A preference is per USER, so there is no anonymous preference."""
    from django.test import Client

    idn.seed_silvercreek()
    assert api_get(Client(), f"/user-preferences/{S17_COLUMNS}").status_code == 401
    assert api_put(Client(), f"/user-preferences/{S17_COLUMNS}", {"value": []}).status_code == 401


# ── TC-7 (isolation) — the two halves ───────────────────────────────────────


def test_us_shl_013_tc7__another_user_in_the_same_tenant_sees_their_own_default(idn):
    """The USER half, over HTTP.

    ⚠ This is the half RLS does NOT cover: Alex and Priya share a tenant, so
    the policy offers both rows to both sessions and only the queryset's
    `user_id=` filter keeps them apart. It is asserted through the endpoint
    because that filter is the only thing standing there.
    """
    idn.seed_silvercreek()
    api_put(_alex(), f"/user-preferences/{S17_COLUMNS}", {"value": CHOSEN})

    priya = _priya()
    assert api_get(priya, f"/user-preferences/{S17_COLUMNS}").json()["value"] is None

    # And Priya's own choice does not disturb Alex's.
    api_put(priya, f"/user-preferences/{S17_COLUMNS}", {"value": ["name", "status"]})
    assert api_get(_alex(), f"/user-preferences/{S17_COLUMNS}").json()["value"] == CHOSEN
    assert UserPreference.objects.filter(key=S17_COLUMNS).count() == 2


def test_us_shl_013_tc7__another_tenant_sees_nothing__app_filter_half(idn):
    """The TENANT half at the app layer; the RLS half is the case below."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    api_put(_alex(), f"/user-preferences/{S17_COLUMNS}", {"value": CHOSEN})

    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    response = api_get(jordan, f"/user-preferences/{S17_COLUMNS}", tenant=BM)
    assert response.status_code == 200
    assert response.json()["value"] is None


@pytest.mark.isolation
@requires_postgres
def test_us_shl_013_tc7_rls__preferences_are_invisible_across_tenants(idn, rls):
    """US-SHL-013 TC-7, RLS half — proved under `sbh_rls_probe`.

    ⚠ **A PLAIN ORM ASSERTION UNDER `tenant_ctx` WOULD PROVE NOTHING HERE.** The
    role this app connects as can bypass row-level security in some
    deployments, and a superuser bypasses it unconditionally — so this case runs
    every read under the NOLOGIN/NOSUPERUSER/NOBYPASSRLS probe role, and the
    `rls` fixture FAILS (never skips) if that role could bypass.

    The app-layer filter is deliberately not in the path: `assert_rls_scoped`
    talks to the table.
    """
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    api_put(_alex(), f"/user-preferences/{S17_COLUMNS}", {"value": CHOSEN})
    # Read AS SILVER CREEK: with no `app.tenant_id` the policy matches nothing,
    # so a bare `.get()` raises `DoesNotExist` on a connection RLS applies to.
    with live_tenant_context(idn.silvercreek.id):
        stored = UserPreference.objects.get(key=S17_COLUMNS)

    assert_denied_without_context(rls, "user_preferences")
    assert_rls_scoped(
        rls,
        "user_preferences",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={str(stored.id)},
    )
    assert_write_into_other_tenant_refused(
        rls, "user_preferences", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    with live_tenant_context(idn.bluemesa.id):
        # The intruder cannot even overwrite the row it cannot see.
        assert (
            rls.affected(
                "UPDATE user_preferences SET value = '[]'::jsonb WHERE id = %s", [str(stored.id)]
            )
            == 0
        )
    with live_tenant_context(idn.silvercreek.id):
        stored.refresh_from_db()
    assert stored.value == CHOSEN


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-013@EP-SHL-05 + DEF-647
# generated: 2026-08-24 by story-coder (DEF-647 column-preference lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
# gates: see apps/tenancy/preferences_api.py's trailer
# exceptions: TC-1/TC-2/TC-5/TC-8 of US-SHL-013 are the i18n/format half of that story and are NOT this lane's — untouched, still owed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

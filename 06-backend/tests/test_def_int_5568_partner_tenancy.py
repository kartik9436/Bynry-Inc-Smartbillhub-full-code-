# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) · CR-110-BRC04 — the partner surface.
#           Screens: S142 *Who has been reading* · S5 the audited grant.
# Defects:  DEF-INT-5568 — four reads over the six integrations tenant tables
#           name neither a tenant nor a row already fetched under one.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; RLS FORCE; NO CROSS-TENANT QUERYSET) · hard-won
#           law 14 (the suite runs on SQLite, which has no RLS at all) · law 7
#           (proved RED first, in the harness that will run it) ·
#           apps/integrations/runners/serve.py `_connection_for` — this
#           module's own house style: state the tenant TWICE.
# Tests:    this file (the query's own scoping) · the PostgreSQL half is
#           tests/test_def_int_5568_partner_tenancy_pg.py (RLS, the first
#           guard, and the partitions of `integration_run`).
# Impacts:  apps/integrations/partner_api.py (access_log, grant_authority) ·
#           apps/integrations/seams/notifications.py · apps/integrations/expiry.py
# ───────────────────────────────────────────────────────
"""Two utilities, one connector: each sees its own and only its own.

⚠ **WHY THIS FILE RUNS ON SQLITE ON PURPOSE, WHICH IS THE OPPOSITE OF THE
USUAL ADVICE, AND WHY IT IS THE ONLY TIER THAT CAN GO RED.**

`config/settings/test.py` hardcodes in-memory SQLite, which has **no row-level
security at all** (hard-won law 14). On PostgreSQL every case below passes
BEFORE the fix as well as after it, because RLS `FORCE` scopes the query the
application forgot to scope — measured, on 2026-09-17, on a real PostgreSQL 16
with the four sites still unfixed. So a PostgreSQL case here would be law 7's
*incapable of failing*: green either way, and reading as rigorous.

Take RLS out of the picture and the only thing left is what the QUERY says, and
that is exactly the second strand `serve.py::_connection_for` already argued for
in its own docstring: *"the tenant is stated twice — once by the database and
once here"*. **This file is the test of the second strand.** The first strand is
tested next door, on PostgreSQL, where it is the only place it exists.

⚠ **WHAT WOULD MAKE EVERY CASE BELOW PASS WRONGLY, NAMED SO A READER CAN CHECK
IT RATHER THAN TRUST IT:**

  * **One utility in the fixture.** With only Brazos Bend present, an unscoped
    query returns Brazos Bend's rows and the assertion cannot tell a scoped read
    from an unscoped one. Every case here provisions Lone Star Ridge as well.
  * **An empty intruder.** *"Lone Star Ridge sees nothing"* is satisfied by a
    utility that HAS nothing, and an unscoped query over an empty table also
    returns nothing. So Lone Star Ridge is given **its own** connection, its own
    issued key, its own reads and its own credential, and every assertion is
    *"B sees exactly B's"* — a count and an identity, never a zero.
  * **Asserting the queryset instead of the answer.** Three of the four cases go
    through the shipped view or the shipped seam, not through the model manager,
    so a fix applied to a neighbouring query would not satisfy them.
  * **A hint or a key that happens to match.** The two utilities' keys, hints and
    row counts are deliberately different, so a leaked row is identifiable by
    value and not only by count.

RED BEFORE THE FIX — this is the failure text, from this file, on this harness:

    FAILED test_the_access_log_shows_one_utility_only_its_own_reads
    AssertionError: Lone Star Ridge's access log carried 3 rows: [7, 500, 48000].
    Two of them are Brazos Bend's — `IntegrationRun.objects.filter(
    connection__provider_key=key, direction=…)` names a provider key every
    utility shares and no tenant at all (CLAUDE.md hard rule 1)
    assert [7, 500, 48000] == [7]
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as _tz

import pytest

from apps.integrations import expiry, models, partner_api, services
from apps.integrations.runners import serve
from apps.integrations.seams import notifications as notifications_seam
from core import crypto
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

#: The connector the Product Owner's report names. Both utilities have it
#: activated — that is the whole premise of the defect.
PARTNER = "erp_aclarian"

BRAZOS_KEY = "sbh_live_7Q2F_brazosbend_do_not_reuse"
BRAZOS_HINT = "••••7Q2F"
LONESTAR_KEY = "sbh_live_4K8W_lonestarridge_do_not_reuse"
LONESTAR_HINT = "••••4K8W"


def _connect(tenant, actor, key, hint, *, provider=PARTNER, label="Aclarian"):
    """A connector with a key we issued, exactly as the wave-R endpoint writes it."""
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=provider,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={"client_id": "aclarian"},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
    )
    return connection


def _read(connection, hint, rows):
    """One partner page taken — the row `access_log` is built from."""
    caller = serve.PartnerCaller(
        connection=connection,
        credential_id=models.IntegrationCredential.objects.filter(connection=connection)
        .first()
        .id,
        hint=hint,
        tenant_id=connection.tenant_id,
        scopes=("payments",),
    )
    return serve.record_read(
        caller=caller, operation="serve_payment", rows=rows, window="Payments, 2 years"
    )


@pytest.fixture()
def two_utilities_on_aclarian(brazos, lonestar, dana, erin):
    """Both utilities activate the same connector, and BOTH have rows.

    ⚠ Brazos Bend is created FIRST and reads MORE, deliberately. *Oldest by
    `created_at`* is how `grant_authority` was choosing a connection, so the
    older utility is the one an unscoped query lands on — the fixture is built
    so a leak is visible rather than merely possible.
    """
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        brazos_connection = _connect(brazos, dana, BRAZOS_KEY, BRAZOS_HINT)
        _read(brazos_connection, BRAZOS_HINT, 500)
        _read(brazos_connection, BRAZOS_HINT, 48_000)
    with tenant_ctx(lonestar):
        lonestar_connection = _connect(lonestar, erin, LONESTAR_KEY, LONESTAR_HINT)
        _read(lonestar_connection, LONESTAR_HINT, 7)
    return brazos_connection, lonestar_connection


# ══════════════════════════════════════════════════════════════════════════
# 1 · S142 *Who has been reading* — the defect the PO reported
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_access_log_shows_one_utility_only_its_own_reads(
    brazos, lonestar, erin, two_utilities_on_aclarian
):
    """The PO's own words: *"the access-log rows appeared under the other utility"*.

    Lone Star Ridge took ONE page of 7. Brazos Bend took 500 and 48,000 through
    a different key on the same connector. The screen may show one row.
    """
    response = api_call(
        partner_api.access_log,
        "get",
        f"/api/{lonestar.subdomain}/integrations/{PARTNER}/access-log",
        user=erin.user,
        role=SYSTEM_ADMIN,
        tenant=lonestar,
        key=PARTNER,
    )
    assert response.status_code == 200
    rows = sorted(one["rows"] for one in response.data["items"])
    assert rows == [7], (
        f"Lone Star Ridge's access log carried {len(rows)} rows: {rows}. "
        "Anything but [7] is Brazos Bend's — `IntegrationRun.objects.filter("
        "connection__provider_key=key, direction=…)` names a provider key every "
        "utility shares and no tenant at all (CLAUDE.md hard rule 1)"
    )
    assert response.data["total_records"] == 7
    hints = {one["hint"] for one in response.data["items"]}
    assert hints == {LONESTAR_HINT}, f"another utility's key hint is on this screen: {hints}"
    assert BRAZOS_HINT not in str(response.data)


@pytest.mark.django_db
def test_the_other_utility_still_sees_all_of_its_own(
    brazos, dana, two_utilities_on_aclarian
):
    """⚠ THE MIRROR CASE, AND IT IS NOT DECORATION.

    A fix that scoped the read by returning nothing would satisfy the case
    above perfectly. Brazos Bend must still see BOTH of its pages, and the
    48,000-row one must still be drawn unusual — that row is the whole reason
    S142 exists.
    """
    response = api_call(
        partner_api.access_log,
        "get",
        f"/api/{brazos.subdomain}/integrations/{PARTNER}/access-log",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        key=PARTNER,
    )
    assert response.status_code == 200
    assert sorted(one["rows"] for one in response.data["items"]) == [500, 48_000]
    assert response.data["total_records"] == 48_500
    assert response.data["unusual_reads"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 2 · S5 the audited grant — which connection it lands on
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_grant_lands_on_the_granting_utilitys_own_connection(
    brazos, lonestar, erin, two_utilities_on_aclarian
):
    """`POST /integrations/{key}/grant` picked *the oldest connection with this
    provider key* — and with no tenant in the query that is whichever utility
    connected first, not the one whose System Admin is clicking.

    Lone Star Ridge's admin authorises Lone Star Ridge's partner. Brazos Bend's
    connection must be untouched, and hard rule 4's audit row must name the
    right one.
    """
    brazos_connection, lonestar_connection = two_utilities_on_aclarian
    response = api_call(
        partner_api.grant_authority,
        "post",
        f"/api/{lonestar.subdomain}/integrations/{PARTNER}/grant",
        user=erin.user,
        role=SYSTEM_ADMIN,
        tenant=lonestar,
        key=PARTNER,
    )
    assert response.status_code == 200

    with tenant_ctx(lonestar):
        granted = models.IntegrationConnection.objects.get(pk=lonestar_connection.pk)
    assert serve.GRANT_CONFIG_KEY in (granted.config or {}), (
        "the grant did not land on the utility that granted it"
    )
    with tenant_ctx(brazos):
        untouched = models.IntegrationConnection.objects.get(pk=brazos_connection.pk)
    assert serve.GRANT_CONFIG_KEY not in (untouched.config or {}), (
        "one utility's System Admin authorised an outside system to read ANOTHER "
        "utility's payments and bills (CLAUDE.md hard rule 1 + hard rule 7)"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · the notifications seam — whose mail server a batch goes through
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_dispatcher_seam_answers_this_utilitys_own_connection(
    brazos, lonestar, dana, erin
):
    """`_connection_for_channel` picked the OLDEST enabled production connection
    for the channel's category with no tenant named.

    A leak here is not a screen showing the wrong number: it is one utility's
    bills leaving through another utility's mail server, under that utility's
    sender address and against its sending allowance.
    """
    with tenant_ctx(brazos):
        brazos_mail = _connect(
            brazos, dana, "sbh_smtp_brazos", "••••BRZ", provider="email_smtp", label="Brazos mail"
        )
    with tenant_ctx(lonestar):
        lonestar_mail = _connect(
            lonestar,
            erin,
            "sbh_smtp_lonestar",
            "••••LSR",
            provider="email_smtp",
            label="Lone Star mail",
        )
        chosen = notifications_seam._connection_for_channel("email")
    assert chosen is not None, "Lone Star Ridge has its own mailbox and must find it"
    assert chosen.id == lonestar_mail.id, (
        f"the dispatcher picked {chosen.label!r} for Lone Star Ridge — "
        f"{brazos_mail.label!r} belongs to another utility"
    )


# ══════════════════════════════════════════════════════════════════════════
# 4 · the expiry sweep — a callable that runs inside ONE utility's context
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_expiry_sweep_looks_at_only_this_utilitys_credentials(
    brazos, lonestar, dana, erin
):
    """⚠ **THIS ONE WAS REVIEWED AS A POSSIBLE FALSE POSITIVE AND IS NOT ONE.**

    A sweep that is SUPPOSED to walk every utility must not be scoped. This one
    is not that sweep. Its own docstring says *"Look at every active credential
    in THIS tenant"* and *"Runs inside the caller's tenant context"*, and its
    only caller — `jobs.run_sweep_expiry_job` — is dispatched by `core.jobs`
    inside `tenant_context(record["tenant_id"])`. It is per-tenant by
    construction, so `BR-TEN-074`'s shape (per-tenant context, per-tenant
    transaction) is already satisfied ABOVE it and the query below it was simply
    unscoped.

    Brazos Bend has two keys that can lapse; Lone Star Ridge has one. A sweep
    run for Lone Star Ridge must look at one.
    """
    soon = datetime.now(_tz.utc) + timedelta(days=11)
    with tenant_ctx(brazos):
        first = _connect(brazos, dana, "sbh_live_AAAA_brazos", "••••AAAA")
        second = _connect(
            brazos, dana, "sbh_live_BBBB_brazos", "••••BBBB", provider="erp_sap", label="SAP"
        )
        for connection in (first, second):
            models.IntegrationCredential.objects.filter(connection=connection).update(
                expires_at=soon
            )
    with tenant_ctx(lonestar):
        only = _connect(lonestar, erin, "sbh_live_CCCC_lonestar", "••••CCCC")
        models.IntegrationCredential.objects.filter(connection=only).update(expires_at=soon)
        outcome = expiry.sweep_expiry(actor=erin, now=datetime.now(_tz.utc), today=date.today())
    assert outcome.looked_at == 1, (
        f"the sweep for Lone Star Ridge looked at {outcome.looked_at} credentials; it has one. "
        "Anything more is another utility's, and a warning would have been mailed to Lone Star "
        "Ridge's admins about a key they do not hold (CLAUDE.md hard rule 1)"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-INT-5568 (maintenance — 12-governance/22-product-maintenance-process.md)
# generated: 2026-09-17 by the DEF-INT-5568 lane
# checklist: A✔ B=n/a(no screen change) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_def_int_5568_partner_tenancy.py · tests/test_def_int_5568_partner_tenancy_pg.py · G126
# exceptions: this file runs on the DEFAULT SQLite suite deliberately — it is the only vendor on which the query's own scoping is observable (law 14); the docstring says so at length
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

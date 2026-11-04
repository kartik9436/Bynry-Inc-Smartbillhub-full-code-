# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) — the partner's morning. CR-069 wave S,
#           task S3. Screens: S142
# Rules:    BR-INT-035 (every read a run a manager can read) · BR-INT-044 (the
#           refusal reveals nothing) · BR-INT-045 (the manifest's numbers) ·
#           BR-INT-054 + CR-069 §20.4 (the payload's meaning is Runbooks') ·
#           BR-TEN-003 · CLAUDE.md hard rule 1 (two tenants, not one) ·
#           hard rule 2 (4 stored, 2 displayed) · hard rule 7 (the grant is
#           audited) · B14 rule 33 (five or six words)
# Tests:    this file — TC-1 three pages · TC-2 the unusual read · TC-3 the
#           allowlist AND the three refusals side by side · TC-4 the rate limit
#           and its two-tenant proof · TC-5 the moved fields are absent ·
#           TC-6 the partner envelope · TC-7 a key at the wrong utility ·
#           TC-8 the register row pointing inward · TC-9 the boundary.
# Impacts:  apps/integrations/runners/serve.py · partner_api.py ·
#           subprocessors.py · seams/payments.py · seams/billing.py
# ───────────────────────────────────────────────────────
"""US-INT-041 — the partner's morning, and the three ways of being turned away.

⚠ **THE ASSERTION THIS FILE EXISTS FOR IS `test_tc3_the_three_refusals_are_one_refusal`.**
An address that is not on the allowlist, a key that is wrong and a key that was
revoked have to be indistinguishable, and "indistinguishable" is three separate
claims that need three separate assertions: the same BYTES, the same STATUS,
and the same TIME. A test that compared only the bodies would pass over a door
that answers a bad key in two milliseconds and a bad address in forty, which is
all an attacker needs.

⚠ **THE RATE LIMIT IS PROVED WITH TWO UTILITIES.** One tenant can only show
that a limit exists; the property `BR-INT-035` actually asks for is that one
utility's partner cannot slow another's, and no amount of testing inside a
single tenant can see it. `test_tc4b` exhausts Brazos Bend's allowance and then
serves Lone Star Ridge from the same process.
"""

from __future__ import annotations

import time
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.integrations import models, partner_api, services, subprocessors
from apps.integrations.runners import serve
from core import crypto
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

#: ⚠ `gl_partner` UNTIL `CR-110-BRC04` — one generic finance card became five
#: NAMED ERPs (blueprint p162). The partner surface serves all five
#: identically and derives them from the registry by their auth mode, so
#: which of the five this suite exercises is arbitrary and the relationship
#: it asserts is unchanged.
PARTNER = "erp_workday"

#: The story's own test data (§4): allowlist `198.51.100.0/24, 203.0.113.7`,
#: the partner calling from `198.51.100.12`, and `203.0.113.99` outside it.
ALLOWED_ADDRESS = "198.51.100.12"
BLOCKED_ADDRESS = "203.0.113.99"
ALLOWLIST = "198.51.100.0/24, 203.0.113.7"

BRAZOS_KEY = "sbh_live_7Q2F_brazosbend_do_not_reuse"
BRAZOS_HINT = "••••7Q2F"
LONESTAR_KEY = "sbh_live_4K8W_lonestarridge_do_not_reuse"


# ══════════════════════════════════════════════════════════════════════════
# Fixtures — one partner connection per utility, keyed the way wave R will
# ══════════════════════════════════════════════════════════════════════════


#: `CR-110-BRC04` — WHICH OF OUR APIS THE KEY MAY CALL. **DERIVED FROM THE
#: MANIFEST, never typed**, and that is not tidiness: this list was first
#: written out by hand as `read_payments · read_bills · read_customers`, which
#: were the names before this CR's own wave C split one generic finance card
#: into five named ERPs. The hand-written copy went stale inside one day and
#: took nineteen cases with it, every one refusing with the door's five words
#: because the key named operations the connector no longer has. Derived, a
#: sixth ERP or a renamed operation costs nothing here (`BR-INT-037`).
#:
#: ⚠ **THE EMPTY `data={}` THIS REPLACED WAS NOT AN OVERSIGHT.** Before the
#: scope existed a key opened everything, so no case had to say anything; when
#: the guard landed, every case in this file went red with a `404` — the one
#: refusal — because a key granting nothing may call nothing. The SCOPE's own
#: behaviour is `tests/test_cr110_key_scope.py`.
def _full_scope(provider=PARTNER):
    from apps.integrations.registry import REGISTRY

    return [one.name for one in REGISTRY.require(provider).operations if one.they_call_us]


def _connect_partner(
    tenant, actor, key, hint, *, allowlist=ALLOWLIST, limit=None, environment=None, scope=None
):
    """An ERP connection with a key we issued.

    The credential is written through `services.record_credential` — the SAME
    call wave R's issue endpoint uses — with the blind index computed from
    `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`. That constant is imported rather
    than retyped ON PURPOSE: if the door and the issuer ever hash under
    different context strings, every valid key is refused and the door still
    looks like it works, because a refused key is exactly what a wrong key
    looks like.
    """
    config = {
        "client_id": "aclarian",
        "scopes": ["payments", "bills"],
        serve.ALLOWLIST_CONFIG_KEY: allowlist,
    }
    if limit is not None:
        config[serve.RATE_LIMIT_CONFIG_KEY] = limit
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=PARTNER,
        label="Aclarian",
        environment=environment or models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config=config,
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=list(_full_scope() if scope is None else scope),
    )
    return connection


def _account(tenant, actor, *, service="water", account_no="ACC-1042"):
    """One account to hang money on, built the way `ledger_le_fixtures` does.

    ⚠ `service` defaults to WATER because Lone Star Ridge sells water only, and
    the isolation cases build their cast in the second tenant — defaulting to
    electric makes those cases fail with `metering.service_not_enabled`, which
    is a real rule correctly refusing and reads for all the world like a bug in
    this wave. The same footnote is in `ledger_le_fixtures.py`; it cost that
    lane an afternoon.
    """
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    existing = customer_models.Account.objects.filter(tenant=tenant).first()
    if existing is not None:
        return existing
    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    premises = make_premises(actor, address_line="500 Main St", services_available=[service])
    unit = make_unit(actor, premises["id"], label="200", services=[service])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=status,
        account_type=customer_models.AccountType.objects.first(),
    )


def _payments(tenant, actor, count, *, day=None, amount="142.1800"):
    """`count` settled payments on one day, through the real model."""
    from apps.payments import models as payment_models

    account = _account(tenant, actor)
    when = timezone.now() if day is None else day
    rows = [
        payment_models.Payment(
            tenant=tenant,
            account=account,
            payment_no=f"PMT-{index:06d}",
            amount=Decimal(amount),
            currency="USD",
            status="posted",
            posted_at=when,
        )
        for index in range(1, count + 1)
    ]
    payment_models.Payment.objects.bulk_create(rows)
    return rows


#: ⚠ **THIS SUITE MOVED TO THE PHASE-2 ADDRESSES ON 2026-09-16, WHEN THE
#: PHASE-1 PAIR RETIRED** (`CR-110-BRC04` phase 2 waves 3 and 4). Every case
#: below is about the DOOR — the allowlist, the three refusals, the rate limit,
#: two utilities, the envelope, the run row — and the door is the same nine
#: checks at every address. Deleting them with the routes would have deleted
#: the proofs; repointing them keeps every one of those properties asserted
#: against the address a partner actually calls. The two views are named here
#: once so the move is one line rather than twenty.
#:
#: `/v1/payments` and `/v1/billing` themselves are proved RETIRED in
#: `tests/test_cr110_phase2_bills_and_payments.py`.
PARTNER_PAYMENTS = partner_api.partner_v1_payments
PARTNER_BILLS = partner_api.partner_bills

#: The phase-2 payments route requires both dates (the supplied specification
#: declares them so); a window wide enough to hold every fixture keeps these
#: cases about what they were about.
WIDE_WINDOW = {"start_date": "2000-01-01", "end_date": "2099-12-31"}


def _partner_get(
    tenant,
    view,
    *,
    key=BRAZOS_KEY,
    address=ALLOWED_ADDRESS,
    query=None,
    path="/partner/v1/payments",
):
    """One partner request: no session, a bearer key, and a source address.

    `REMOTE_ADDR` is set rather than `X-Forwarded-For`, because with
    `TRUSTED_PROXY_COUNT = 0` (the default, and the safe one) the forwarded
    header is ignored — which is the property that stops a caller spoofing its
    way past the allowlist, and a test that used the header would be testing a
    path production does not take.

    `company_id` and the window are defaulted rather than repeated in twenty
    cases; a case that cares about either passes its own and wins.
    """
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    params = {"company_id": str(tenant.id)}
    params.update(WIDE_WINDOW)
    params.update(query or {})
    params = {name: value for name, value in params.items() if value is not None}
    factory = APIRequestFactory()
    request = factory.get(f"/api/{tenant.subdomain}{path}", params, REMOTE_ADDR=address)
    if key is not None:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {key}"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return view(request)


def _bytes(response):
    """The response as it goes on the wire — the only comparison that means
    'indistinguishable'. `.data` would compare parsed objects and miss a
    difference in ordering, whitespace or content type."""
    return response.content if hasattr(response, "content") else response.rendered_content


@pytest.fixture()
def aclarian(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        connection = _connect_partner(brazos, dana, BRAZOS_KEY, BRAZOS_HINT)
    return connection


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · the partner's morning — three pages, three runs
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1_three_pages_at_0241_are_three_runs_with_the_hint_as_who(brazos, dana, aclarian):
    """1,236 payments over three pages of 500 → 500 · 500 · 236, three rows.

    ⚠ The envelope is 500 · 500 · 236 and NOT 412 · 412 · 412. The card read
    *412* — 1,236 ÷ 3 — until 2026-09-03, when `DEF-INT-3614` corrected it: a
    page size of 500 means the last page is a remainder, and a manager reading
    three equal rows would conclude something different about the collection
    than the truth.
    """
    with tenant_ctx(brazos):
        _payments(brazos, dana, 1236)

    sizes = []
    for page in (1, 2, 3):
        response = _partner_get(brazos, PARTNER_PAYMENTS, query={"page": page, "page_size": 500})
        assert response.status_code == 200
        import json

        body = json.loads(_bytes(response))
        sizes.append(len(body["records"]))
        assert body["total_records"] == 1236
        assert body["total_pages"] == 3

    assert sizes == [500, 500, 236]

    with tenant_ctx(brazos):
        runs = list(
            models.IntegrationRun.objects.filter(
                direction=models.RUN_DIRECTION_INBOUND_READ
            ).order_by("started_at")
        )
    assert len(runs) == 3, "every PAGE is a run, not every collection (BR-INT-035)"
    assert [one.attempted for one in runs] == [500, 500, 236]
    assert all(one.trigger == "partner" for one in runs)
    for index, run in enumerate(runs, start=1):
        assert f"page {index} of 3" in run.summary
        # *who* is the HINT and never the key. A run record naming a secret is
        # a leaked secret.
        assert BRAZOS_HINT in run.summary
        assert BRAZOS_KEY not in (run.summary or "")


@pytest.mark.django_db
def test_tc1b_the_key_appears_in_no_run_row_no_response_and_no_audit_row(brazos, dana, aclarian):
    """The three exits (US-INT-040 TC-7), applied to this wave's surface."""
    with tenant_ctx(brazos):
        _payments(brazos, dana, 3)
    response = _partner_get(brazos, PARTNER_PAYMENTS)
    assert BRAZOS_KEY.encode() not in _bytes(response)

    with tenant_ctx(brazos):
        rows = models.IntegrationRun.objects.all()
        assert all(BRAZOS_KEY not in (one.summary or "") for one in rows)
        creds = models.IntegrationCredential.objects.all()
        # The hint is display-only; the stored payload is ciphertext.
        assert all(one.masked_hint == BRAZOS_HINT for one in creds)


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · the unusual read — the access log is the only place it shows
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2_a_large_collection_is_flagged_unusual_on_the_access_log(brazos, dana, aclarian):
    """Failure 13: *"every request is authorised; nothing in the product would
    show it"*. The access log is the one thing that does, and the row that
    matters is drawn differently."""
    with tenant_ctx(brazos):
        caller = serve.PartnerCaller(
            connection=aclarian,
            credential_id=models.IntegrationCredential.objects.first().id,
            hint=BRAZOS_HINT,
            tenant_id=brazos.id,
            scopes=("payments",),
        )
        serve.record_read(caller=caller, operation="serve_payment", rows=48_000, window="Payments, 2 years")
        serve.record_read(caller=caller, operation="serve_payment", rows=612, window="Payments, 1–30 Sep")

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
    items = response.data["items"]
    assert [one["rows"] for one in items] == [612, 48_000]
    assert [one["unusual"] for one in items] == [False, True]
    assert response.data["total_records"] == 48_612
    assert response.data["unusual_reads"] == 1, "a COUNT, so a header can say it in words"
    # ⚠ *WHO*, AS ITS OWN FIELD. The screen rendered when · what · how many and
    # the hint reached it only inside `detail`, which nothing displayed — so
    # the screen called *Who has been reading* did not say who. Found in a
    # browser; asserted here so it cannot go missing again.
    assert [one["hint"] for one in items] == [BRAZOS_HINT, BRAZOS_HINT]
    assert all(BRAZOS_KEY not in str(one) for one in items), "never the key itself"


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · the allowlist, and the three refusals side by side
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3_a_read_from_outside_the_allowlist_is_refused(brazos, dana, aclarian):
    with tenant_ctx(brazos):
        _payments(brazos, dana, 5)
    response = _partner_get(brazos, PARTNER_PAYMENTS, address=BLOCKED_ADDRESS)
    assert response.status_code == 404, "the manifest's `refused` number, not a typed one"
    assert serve.REFUSAL_SENTENCE.encode() in _bytes(response)
    # It learns nothing about whether the utility, the connection or the data
    # exist — and it reads nothing either.
    #
    # ⚠ **THIS ASSERTION READ `not … exists()` UNTIL `CR-110-BRC04`**, because
    # a refusal used to leave no trace at all. The PO ruled on 2026-09-16 that
    # the cause has to be somewhere a manager can read it, so the refusal now
    # writes ONE run row that read NOTHING — `attempted = 0`, outcome
    # `skipped`, *we declined* rather than *something failed*. What the caller
    # gets back is unchanged, and the case above still asserts that.
    with tenant_ctx(brazos):
        row = models.IntegrationRun.objects.get()
        assert row.attempted == 0 and row.succeeded == 0
        assert serve.CODE_ADDRESS_NOT_ALLOWED in {one["ref"] for one in row.items}


def _six_refusals(brazos, dana, *, provider=PARTNER, probe=None):
    """The SIX ways a caller is turned away, each set up so that exactly ONE
    cause is true, each timed, and the world put back afterwards.

    ⚠ **SIX AND NOT THREE SINCE `CR-110-BRC04`.** The door has asked four
    questions since the scope guard landed and the CAUSES are six once *a key we
    have never seen* and *a key we issued and revoked* are counted apart — which
    is precisely the distinction the PO ruled into our record on 2026-09-16 and
    ruled OUT of the wire. Both callers of this helper walk the same six, so the
    wire half and the record half can never be proved over different sets.

    Returns `[(name, code, response, elapsed_seconds), …]` in the PO's table
    order, rows 3–8.

    ⚠ **`provider` AND `probe` ARE ARGUMENTS SINCE 2026-09-24, AND BOTH
    DEFAULTS ARE EXACTLY WHAT THIS HELPER ALWAYS DID.** The partner door
    stopped being read-only that day: `POST /partner/v1/make-payment/` is the
    first address on it that creates money, on a different connector, and its
    refusals have to be **the same bytes and the same time as these** — or a
    caller could tell a read door from a write door and learn that a write door
    exists.

    **The alternative was a private copy of this helper in the write suite, and
    it is the thing this repository fails at most often** (`DEF-014`, and
    hard-won law 7's *a check that cannot fail*): two setups for one property
    drift, the looser one passes, and there is no way to tell which surface is
    right. One helper, two callers on the read side and one on the write side,
    and they are all proved over the same six causes.

    The credential is now selected BY PROVIDER rather than by `.get()` over the
    whole table, because a test may legitimately hold two connections — and
    `.get()` over two is a `MultipleObjectsReturned` that reads like a broken
    fixture rather than like the deliberate second connector it is.
    """
    with tenant_ctx(brazos):
        _payments(brazos, dana, 5)
        credential = models.IntegrationCredential.objects.get(
            connection__provider_key=provider
        )
        connection = credential.connection
    rows = models.IntegrationCredential.objects.filter(pk=credential.pk)
    connections = models.IntegrationConnection.objects.filter(pk=connection.pk)
    call = probe if probe is not None else (
        lambda **kwargs: _partner_get(brazos, PARTNER_PAYMENTS, **kwargs)
    )

    def _timed(**kwargs):
        started = time.monotonic()
        response = call(**kwargs)
        return response, time.monotonic() - started

    out = []

    # 3 · a key that was never issued, from an allowed address
    out.append(("a key we have never seen", serve.CODE_KEY_UNKNOWN,
                *_timed(key="sbh_live_this_was_never_issued")))

    # 4 · a key that was issued and then revoked
    with tenant_ctx(brazos):
        rows.update(is_active=False)
    out.append(("a revoked key", serve.CODE_KEY_REVOKED, *_timed()))
    with tenant_ctx(brazos):
        rows.update(is_active=True)

    # 5 · a key that is live and out of date
    with tenant_ctx(brazos):
        rows.update(expires_at=timezone.now() - timedelta(minutes=1))
    out.append(("an expired key", serve.CODE_KEY_EXPIRED, *_timed()))
    with tenant_ctx(brazos):
        rows.update(expires_at=None)

    # 6 · a good key from an address the utility did not list
    out.append(("off the allowlist", serve.CODE_ADDRESS_NOT_ALLOWED,
                *_timed(address=BLOCKED_ADDRESS)))

    # 7 · the connector itself switched off
    with tenant_ctx(brazos):
        connections.update(enabled=False)
    out.append(("a switched-off connector", serve.CODE_CONNECTOR_DISABLED, *_timed()))
    with tenant_ctx(brazos):
        connections.update(enabled=True)

    # 8 · a key that may not call THIS api
    with tenant_ctx(brazos):
        rows.update(scope=["serve_bill"])
    out.append(("a key out of scope", serve.CODE_OPERATION_NOT_IN_SCOPE, *_timed()))
    with tenant_ctx(brazos):
        # ⚠ `_full_scope(provider)` AND NOT `_full_scope()` SINCE 2026-09-24.
        # With the argument dropped this restored `erp_workday`'s operation
        # names onto whatever key the caller is exercising — which for the
        # write door would leave a key holding five names that connector does
        # not declare, refused by the door and looking exactly like a bug in
        # the door rather than in the fixture.
        rows.update(scope=list(_full_scope(provider)))

    return out


@pytest.mark.django_db
def test_tc3_the_six_refusals_are_one_refusal(brazos, dana, aclarian):
    """⚠ THE CENTRAL ASSERTION OF THIS WAVE (BR-INT-044), NOW OVER ALL SIX.

    Six ways of being turned away, compared on the three axes an attacker can
    measure: the same BYTES, the same STATUS and the same TIME. If a later lane
    rewrites `resolve_caller()` into guard clauses, the bodies stay identical
    and this test still catches it — on the timing.

    ⚠ **THIS CASE IS WHAT STOPS `CR-110-BRC04` UNDOING ITSELF.** The eight
    refusal codes the PO ruled in are easy to test the wrong way: assert the
    eight constants exist, assert `PartnerRefused.causes` names the right one,
    green, done — and never notice that the six auth codes have started
    reaching the caller. So the assertion that matters is a NEGATIVE one, and it
    is this: put all six side by side and prove they are the same bytes. The
    codes are proved to be DISTINCT in
    `tests/test_cr110_refusal_codes.py`, on the record and never on the wire;
    the two cases walk the same six through `_six_refusals`.
    """
    refusals = _six_refusals(brazos, dana)
    assert len(refusals) == 6

    statuses = {one[2].status_code for one in refusals}
    bodies = {_bytes(one[2]) for one in refusals}
    assert statuses == {404}, f"a second status is an oracle: {statuses}"
    assert len(bodies) == 1, (
        "six different bodies is an oracle — a caller holding a stolen key would "
        f"read which guard refused: {bodies}"
    )
    assert list(bodies)[0] == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    ), "the code on the wire is a CONSTANT; the cause lives in the run row"

    # …and the same time. Each is held to the floor, so none can be the fast
    # one that says "your key is real, only your address is wrong".
    for name, _code, _response, elapsed in refusals:
        assert elapsed >= serve.REFUSAL_FLOOR_S, (
            f"{name} answered in {elapsed:.4f}s, under the {serve.REFUSAL_FLOOR_S}s floor — "
            "a faster refusal is a refusal that tells the caller which one they got"
        )

    # ⚠ **AND THE SPREAD, WHICH THE THREE-WAY VERSION OF THIS CASE DID NOT
    # ASSERT AND `CR-110-BRC04` NEEDS.** Five of the six now write a run row and
    # `KEY_UNKNOWN` cannot, so the refusals stopped doing equal amounts of
    # database work on the day the causes were recorded. The floor is what puts
    # that back — but only while the record still FITS inside it. A spread wider
    # than the floor itself means the padding has stopped equalising and the
    # stopwatch works again.
    spread = max(one[3] for one in refusals) - min(one[3] for one in refusals)
    assert spread < serve.REFUSAL_FLOOR_S, (
        f"the six refusals spread {spread:.4f}s, wider than the {serve.REFUSAL_FLOOR_S}s "
        "floor — recording the cause has overrun the padding that hides it"
    )


@pytest.mark.django_db
def test_tc3b_a_refusal_is_five_or_six_words(brazos):
    """B14 rule 33. The sentence is a module constant so there is only one of
    them to check, and this is the check."""
    assert 5 <= len(serve.REFUSAL_SENTENCE.split()) <= 6
    assert "BR-" not in serve.REFUSAL_SENTENCE and "OQ-" not in serve.REFUSAL_SENTENCE


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · the rate limit — and the two-tenant proof
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4_the_hundred_and_first_request_in_a_minute_waits(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect_partner(brazos, dana, BRAZOS_KEY, BRAZOS_HINT, limit=3)
        _payments(brazos, dana, 2)

    for _ in range(3):
        assert _partner_get(brazos, PARTNER_PAYMENTS).status_code == 200

    limited = _partner_get(brazos, PARTNER_PAYMENTS)
    assert limited.status_code == 429
    assert limited["Retry-After"] == str(serve.RETRY_AFTER_S)
    assert serve.REFUSAL_SENTENCE.encode() in _bytes(limited)

    # "recorded as a refused read" — the manager sees the attempt.
    #
    # ⚠ THE OUTCOME IS `skipped`, NOT `failed` OR `unconfirmed`, and this
    # assertion was corrected after reading the rows a real run wrote.
    # `services.outcome_for` keeps three kinds of not-knowing apart:
    # `unconfirmed` is *they would not say*, `indeterminate` is *we asked and
    # cannot tell*, `skipped` is **we did not ask**. We turned this partner
    # away ourselves, knowingly, so there is no "they" who failed to say
    # anything — and S142 draws `skipped` neutral for exactly that reason.
    with tenant_ctx(brazos):
        refused = models.IntegrationRun.objects.filter(outcome=models.OUTCOME_SKIPPED)
        assert refused.count() == 1
        assert refused.first().attempted == 0, "no records were handed over"
        assert "refused" in refused.first().summary


@pytest.mark.django_db
def test_tc4b_one_utilitys_partner_cannot_slow_another_utilitys(brazos, lonestar, dana, erin):
    """⚠ TWO TENANTS, NOT ONE — the whole point of the assertion.

    The counter is keyed on `(tenant_id, credential_id)`. Key it on the
    provider instead and Brazos Bend's busy partner would throttle Lone Star
    Ridge's quiet one, which is the exact failure this module exists to
    prevent, wearing the fix's clothes (`runtime.py` carries the same warning
    about the concurrency cap). Only a second tenant can see it.
    """
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect_partner(brazos, dana, BRAZOS_KEY, BRAZOS_HINT, limit=2)
        _payments(brazos, dana, 2)
    with tenant_ctx(lonestar):
        _connect_partner(lonestar, erin, LONESTAR_KEY, "••••4K8W", limit=2)
        _payments(lonestar, erin, 2)

    # Brazos Bend's partner spends its whole allowance and is then refused.
    for _ in range(2):
        assert _partner_get(brazos, PARTNER_PAYMENTS).status_code == 200
    assert _partner_get(brazos, PARTNER_PAYMENTS).status_code == 429

    # Lone Star Ridge's partner, in the same process, at the same second.
    assert (
        _partner_get(lonestar, PARTNER_PAYMENTS, key=LONESTAR_KEY).status_code == 200
    ), "one utility's partner exhausting its allowance must not touch another's"


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · the fields that MOVED — a gap that goes red in both directions
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc5_we_publish_our_own_vocabulary_and_the_translation_is_still_runbooks(
    brazos, dana, aclarian
):
    """⚠ **THIS CASE ASSERTED AN ABSENCE AND THE ABSENCE HAS MOVED — THE ROW IS
    UPDATED RATHER THAN THE ASSERTION DELETED, WHICH IS WHAT ITS OWN MESSAGE
    ASKED FOR.**

    It read: `tenderType`, `projectType` and `accountString` are Runbooks'
    (`CR-069` §20.4), so the payload carries exactly four fields. On 2026-09-16
    the PO ruled on the read case — *"this will not be required in case of they
    read cases - we just need to actiavte connectors and issue a key thats
    all"* — which struck the clerk mapping screen and put those three fields on
    the payload in **OUR** vocabulary.

    **THE BOUNDARY DID NOT MOVE; THE THING ON EACH SIDE OF IT GOT NAMED
    PROPERLY.** What Runbooks owns is the TRANSLATION — deciding that our *Bank
    transfer* is their `ACHCHECK` — and `serve.partner_fields()` is still where
    that arrives and still returns nothing. Publishing our own code with our own
    word is the same act as the reference endpoint, which the PO commissioned in
    the same hour for exactly this purpose. So the assertion that still has to
    hold, and does, is that **nothing on this payload is written in the
    partner's words**.
    """
    import json

    with tenant_ctx(brazos):
        _payments(brazos, dana, 1)
    body = json.loads(_bytes(_partner_get(brazos, PARTNER_PAYMENTS)))
    record = body["records"][0]

    assert set(record) == {
        "id",
        "FeeEntryId",
        "consumerNo",
        "customer_name",
        "paymentDate",
        "type",
        "projectType",
        "tenderType",
        "paymentPayType",
        "amount",
        "currency",
        "description",
        "accountString",
    }, record

    # The seam Runbooks lands in is still EMPTY, and that is the half of the
    # old assertion that never moved. When Runbooks fills it, this line fails
    # and names this paragraph — exactly as the previous one did.
    assert serve.partner_fields(record) == {}

    # Hard rule 2: stored to four decimals, DISPLAYED to two.
    assert record["amount"] == "142.18"
    assert record["id"] == "PMT-000001", "the receipt number, never the database key"


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · the partner's own envelope, not ours
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6_the_envelope_is_the_partners_and_not_the_drf_shape(brazos, dana, aclarian):
    import json

    with tenant_ctx(brazos):
        _payments(brazos, dana, 1236)
    body = json.loads(_bytes(_partner_get(brazos, PARTNER_PAYMENTS, query={"page": 2, "page_size": 500})))
    assert body["total_records"] == 1236
    assert body["page"] == 2
    assert body["page_size"] == 500
    assert body["total_pages"] == 3
    for ours in ("count", "next", "previous", "results"):
        assert ours not in body, "the DRF shape is ours; the partner declared its own"


@pytest.mark.django_db
def test_tc6b_the_specification_is_served_to_a_partner_and_refused_to_a_stranger(brazos, dana, aclarian):
    import json

    served = _partner_get(brazos, partner_api.partner_openapi, path="/v1/openapi.json")
    assert served.status_code == 200
    spec = json.loads(_bytes(served))
    assert set(spec["paths"]) == {"/v1/payments", "/v1/billing"}

    stranger = _partner_get(brazos, partner_api.partner_openapi, key=None, path="/v1/openapi.json")
    assert stranger.status_code == 404
    assert _bytes(stranger) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · tenant isolation — a key at the wrong utility's address
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc7_a_key_presented_at_another_utilitys_address_is_refused(brazos, lonestar, dana, erin):
    """⚠ THE DATABASE REFUSES THIS, NOT A LINE OF CODE.

    Under Lone Star Ridge's `app.tenant_id`, Brazos Bend's credential row is
    not visible at all — RLS `FORCE`, hard rule 1 — so the blind-index lookup
    finds nothing and falls into the same one refusal as a key that never
    existed. There is nothing here a later lane could delete to break it, which
    is why the tenant belongs in the path (see `runners/serve.py`).
    """
    with tenant_ctx(brazos):
        _connect_partner(brazos, dana, BRAZOS_KEY, BRAZOS_HINT)
        _payments(brazos, dana, 4)
    with tenant_ctx(lonestar):
        _connect_partner(lonestar, erin, LONESTAR_KEY, "••••4K8W")
        _payments(lonestar, erin, 7)

    crossed = _partner_get(lonestar, PARTNER_PAYMENTS, key=BRAZOS_KEY)
    assert crossed.status_code == 404
    assert _bytes(crossed) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'

    # …and nothing of Lone Star Ridge's was read on the way to finding out.
    with tenant_ctx(lonestar):
        assert not models.IntegrationRun.objects.exists()

    # The right key at the right address sees its OWN utility's seven and never
    # the other's four.
    import json

    mine = json.loads(_bytes(_partner_get(lonestar, PARTNER_PAYMENTS, key=LONESTAR_KEY)))
    assert mine["total_records"] == 7


@pytest.mark.django_db
def test_tc7b_a_company_id_naming_another_utility_is_refused_and_never_served(
    brazos, lonestar, dana, erin, aclarian
):
    """BR-TEN-003 — *"the ONLY input consulted is the request path; tenant_id
    in a header/param/body is never read"*.

    ⚠⚠ **AND IT READS *the parameter is ignored* AGAIN SINCE 2026-09-17, WHICH
    IS WHERE IT STARTED.** PO: *"you will ahve to remove company ID filter from
    all Apis - we cannot tell tenant ID outside our system"*, superseding
    *"company_id = tenant id"*. **The finding this case exists for never moved**
    through any of it: whoever can send one utility's id can send another's, so
    the id may never select. What moved is whether we also COMPARE it, and the
    comparison bought nothing — the key had already decided the utility.

    ⚠ **THIS CASE READ *the parameter is ignored* UNTIL PHASE 2**, and it was
    true of the phase-1 flat route: `company_id` was not consulted at all, so
    sending another utility's id changed nothing. The PO then ruled
    *"company_id = tenant id"*, which CONFIRMS the finding rather than softening
    it — whoever can send one utility's id can send another's — so the
    parameter is now **VERIFIED against the key and still never used to
    select**. The two halves are both asserted here, because a door that
    verified and then selected would pass an assertion about either one alone.
    """
    import json

    with tenant_ctx(brazos):
        _payments(brazos, dana, 4)
    with tenant_ctx(lonestar):
        _connect_partner(lonestar, erin, LONESTAR_KEY, "••••4K8W")
        _payments(lonestar, erin, 7)

    # ⚠ **AMENDED 2026-09-17 (`CR-111-BRC04`).** The `403` is gone: PO,
    # *"you will ahve to remove company ID filter from all Apis - we cannot tell
    # tenant ID outside our system"*. **What this case is FOR is unchanged** —
    # naming Lone Star Ridge must not serve Lone Star Ridge's payments — and it
    # is now asserted on the rows themselves, which is the honest form of it:
    # Brazos Bend has FOUR payments and Lone Star Ridge has SEVEN, so a door
    # that selected on the parameter would answer seven.
    wrong = _partner_get(brazos, PARTNER_PAYMENTS, query={"company_id": str(lonestar.id)})
    assert wrong.status_code == 200, _bytes(wrong)
    served = json.loads(_bytes(wrong))
    assert served["total_records"] == 4, (
        f"naming another utility served {served['total_records']} records — "
        "Brazos Bend has 4 and Lone Star Ridge has 7, so something SELECTED on it"
    )
    assert str(lonestar.id) not in _bytes(wrong).decode(), (
        "echoing the id turns this into a probe for real utility ids"
    )
    # ⚠ **THIS LINE READ `assert b"records" not in _bytes(wrong)` UNTIL
    # 2026-09-17** — *"a refused call serves no rows at all"*, which was true
    # while naming another utility was a `403`. It is now a normal 200 carrying
    # OUR OWN rows, and the assertion that replaced it is the one above: the
    # COUNT is Brazos Bend's four and not Lone Star Ridge's seven.

    body = json.loads(_bytes(_partner_get(brazos, PARTNER_PAYMENTS)))
    assert body["total_records"] == 4, "the PATH decides the utility, and it still does"


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · the subprocessor register, pointing inward
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc8_the_register_row_points_inward_and_reads_as_a_sentence(brazos, dana, aclarian):
    """The compliance artefact: somebody reads this to answer *who else touches
    our customers' data*, so the assertion is on the SENTENCE."""
    api_call(
        partner_api.grant_authority,
        "post",
        f"/api/{brazos.subdomain}/integrations/{PARTNER}/grant",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        key=PARTNER,
    )
    with tenant_ctx(brazos):
        rows = [one for one in subprocessors.register_rows() if one.direction == "inward"]
    assert len(rows) == 1
    row = rows[0]
    assert row.party == "Aclarian", "the firm's own name, not our catalogue's word for it"
    assert row.what == "payments, bills and customers"
    sentence = row.sentence()
    assert sentence.startswith("Aclarian — reads payments, bills and customers — authorised by ")
    assert " on 2026-" in sentence or " on 20" in sentence
    # B14 rule 31 — no database id is a field on a register row.
    assert str(aclarian.id) not in sentence


@pytest.mark.django_db
def test_tc8b_an_ungranted_inward_relationship_says_so_rather_than_going_quiet(brazos, dana, aclarian):
    """An absence that prints as nothing is indistinguishable from an absence
    that never existed — and *"somebody outside is reading this and we cannot
    tell you who allowed it"* is exactly the finding an auditor wants."""
    with tenant_ctx(brazos):
        rows = [one for one in subprocessors.register_rows() if one.direction == "inward"]
    assert rows[0].sentence().endswith("authorisation not recorded")


@pytest.mark.django_db
def test_tc8c_the_register_is_derived_and_a_disconnected_partner_leaves_it(brazos, dana, aclarian):
    """*"derived from the live connection, not typed"* — so removing the
    connection removes the row, with nothing to remember to delete."""
    with tenant_ctx(brazos):
        assert any(one.direction == "inward" for one in subprocessors.register_rows())
        models.IntegrationConnection.objects.filter(pk=aclarian.pk).update(status=models.STATUS_OFF)
        assert not any(one.direction == "inward" for one in subprocessors.register_rows())


@pytest.mark.django_db
def test_tc8d_the_register_cannot_show_another_utilitys_partner(brazos, lonestar, dana, erin, aclarian):
    with tenant_ctx(lonestar):
        assert subprocessors.register_rows() == []


@pytest.mark.django_db
def test_every_one_of_the_six_routes_resolves_through_config_urls(brazos):
    """⚠ THE ROUTE THAT DID NOT RESOLVE WAS INVISIBLE TO EVERY OTHER TEST HERE,
    because they all call the view FUNCTION directly.

    `integrations/subprocessors` was two segments, so `api.py`'s
    `integrations/<str:key>` matched it first and answered **405**, reading the
    word *subprocessors* as a provider key. `config/urls.py` carried a comment
    from this very lane asserting the collision could not happen. Only clicking
    it found out (hard-won law 6), and this case is what stops it recurring: it
    resolves the real paths through the real URLconf.
    """
    from django.urls import resolve

    expected = {
        f"/api/{brazos.subdomain}/v1/payments": "partner_payments",
        f"/api/{brazos.subdomain}/v1/billing": "partner_billing",
        f"/api/{brazos.subdomain}/v1/openapi.json": "partner_openapi",
        f"/api/{brazos.subdomain}/integrations/register/subprocessors": "subprocessor_register",
        f"/api/{brazos.subdomain}/integrations/{PARTNER}/access-log": "access_log",
        f"/api/{brazos.subdomain}/integrations/{PARTNER}/grant": "grant_authority",
    }
    for path, name in expected.items():
        match = resolve(path)
        resolved = getattr(match.func, "__wrapped__", match.func)
        # DRF's @api_view wraps the function; the original hangs off `cls` or
        # the closure, so the honest check is the module it came from plus the
        # kwargs, not the wrapper's name.
        assert match.func.__module__.endswith("partner_api") or "partner_api" in str(
            match.func.__dict__.get("cls", "")
        ), f"{path} resolved to {match.func.__module__}, not partner_api ({name})"


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · the boundary — what was blocked, and what stays refused forever
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc9_the_grant_is_recorded_and_audited(brazos, dana, aclarian):
    """`OQ-INT-1481` was CLOSED on 2026-09-04, option (a): the System Admin,
    as an audited grant on the connection plus a register row pointing inward.

    ⚠ This case previously asserted `NotImplementedError("OQ-INT-1481")`. The
    question is ruled, so the boundary MOVED rather than being removed — what
    is asserted now is the ruling, which is what a closed question is supposed
    to leave behind (`OQ-1396`'s distinction, and the 2026-09-05 lesson about
    a status column that moves while the body does not).
    """
    rows: list[dict] = []
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(rows.append)
    try:
        response = api_call(
            partner_api.grant_authority,
            "post",
            f"/api/{brazos.subdomain}/integrations/{PARTNER}/grant",
            user=dana.user,
            role=SYSTEM_ADMIN,
            tenant=brazos,
            key=PARTNER,
        )
    finally:
        core_audit.set_audit_sink(previous)

    assert response.status_code == 200
    granted = [one for one in rows if one["action"] == "integration.partner.authorised"]
    assert len(granted) == 1, "hard rule 7's shape: the authorisation is a durable row"
    assert granted[0]["tenant_id"] == brazos.id
    assert BRAZOS_KEY not in str(granted[0]), "an audit row never carries the key"

    with tenant_ctx(brazos):
        connection = models.IntegrationConnection.objects.get(pk=aclarian.pk)
    assert connection.config[serve.GRANT_CONFIG_KEY]["granted_by_name"]


@pytest.mark.django_db
def test_tc9b_a_partners_read_is_never_a_batch_we_execute(brazos, aclarian):
    """The half of the quadrant no wave will ever fill: a read is theirs to
    start, so there is no work for us to run."""
    from apps.integrations.registry import REGISTRY

    operation = REGISTRY.require(PARTNER).operations[0]
    with pytest.raises(NotImplementedError) as refused:
        serve.execute_run(
            connection=aclarian, operation=operation, adapter=None, work=(), trigger="manual"
        )
    assert "no batch to execute" in str(refused.value)


# ══════════════════════════════════════════════════════════════════════════
# The allowlist's own shapes
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_allowlist_fails_closed_on_anything_it_cannot_read(brazos, dana, aclarian):
    """Hard-won law 3 — the unsafe option must be the one you type."""
    assert serve.allowlist_permits(aclarian, "198.51.100.12") is True
    assert serve.allowlist_permits(aclarian, "203.0.113.7") is True
    assert serve.allowlist_permits(aclarian, "203.0.113.99") is False
    assert serve.allowlist_permits(aclarian, "not-an-address") is False
    assert serve.allowlist_permits(aclarian, None) is False
    assert serve.allowlist_permits(None, "198.51.100.12") is False


@pytest.mark.django_db
def test_an_empty_allowlist_permits_and_a_typo_closes_only_its_own_entry(brazos, dana):
    with tenant_ctx(brazos):
        # Two ENVIRONMENTS are two rows — BR-INT-026's UNIQUE is the
        # sandbox/production mix-up made impossible, and it applies here too.
        open_door = _connect_partner(
            brazos, dana, "sbh_live_open", "••••open", allowlist="",
            environment=models.ENVIRONMENT_PRODUCTION,
        )
        typo = _connect_partner(
            brazos, dana, "sbh_live_typo", "••••typo",
            allowlist="198.51.100.0/24, 999.999.999.999",
            environment=models.ENVIRONMENT_SANDBOX,
        )
    assert serve.allowlist_permits(open_door, "203.0.113.99") is True, (
        "a provider that publishes no addresses is not thereby unreachable"
    )
    assert serve.allowlist_permits(typo, "198.51.100.12") is True
    assert serve.allowlist_permits(typo, "203.0.113.99") is False


@pytest.mark.django_db
def test_a_key_resolves_to_ITS_OWN_connection_and_not_to_the_first_one(brazos, dana):
    """⚠ THE REGRESSION THE WALKTHROUGH'S SEED EXPOSED, WRITTEN DOWN.

    A tenant may lawfully hold TWO partner connections — `BR-INT-026`'s UNIQUE
    is (tenant, provider_key, environment), which is the sandbox/production
    pair the design's failure list ranks first. The first draft of the door
    looked up *the tenant's first connection by `created_at`* and asked whether
    the presented key belonged to it, so a key issued against the SECOND
    connection was checked against the FIRST one's allowlist, rate limit and
    grant.

    Nothing in the suite could see it, because every case until now built one
    connection. The seed for the browser walkthrough builds both, which is how
    it surfaced — hard-won law 6's lesson arriving through a fixture rather
    than through a screen.
    """
    with tenant_ctx(brazos):
        # Created FIRST, and it forbids the address the request will come from.
        _connect_partner(
            brazos, dana, "sbh_live_first_created", "••••frst",
            allowlist="203.0.113.7", environment=models.ENVIRONMENT_PRODUCTION,
        )
        # Created SECOND, and it is the one whose key we present.
        _connect_partner(
            brazos, dana, BRAZOS_KEY, BRAZOS_HINT,
            allowlist=ALLOWLIST, environment=models.ENVIRONMENT_SANDBOX,
        )
        _payments(brazos, dana, 3)

    response = _partner_get(brazos, PARTNER_PAYMENTS)
    assert response.status_code == 200, (
        "the key must be judged against ITS OWN connection's allowlist — "
        "reading the first connection by created_at refuses this with a 404"
    )

    with tenant_ctx(brazos):
        run = models.IntegrationRun.objects.get(direction=models.RUN_DIRECTION_INBOUND_READ)
        assert run.connection.environment == models.ENVIRONMENT_SANDBOX, (
            "the run is recorded against the connection the KEY belongs to"
        )
        assert BRAZOS_HINT in run.summary


@pytest.mark.django_db
def test_an_expired_credential_is_refused_like_every_other_bad_key(brazos, dana, aclarian):
    with tenant_ctx(brazos):
        models.IntegrationCredential.objects.update(expires_at=timezone.now() - timedelta(days=1))
    response = _partner_get(brazos, PARTNER_PAYMENTS)
    assert response.status_code == 404
    assert _bytes(response) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


@pytest.mark.django_db
def test_bills_are_served_and_drafts_are_not(brazos, dana, aclarian):
    """Hard rule 4 — a draft is discardable and is not a financial record, so a
    finance system must never be able to post one."""
    import json

    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        today = timezone.now().date()
        common = dict(
            tenant=brazos,
            account=account,
            service_date=today,
            period_start=today,
            period_end=today,
            currency="USD",
        )
        billing_models.Invoice.objects.create(
            invoice_no="INV-0001", status="issued", issued_at=timezone.now(), total=Decimal("88.6000"), **common
        )
        billing_models.Invoice.objects.create(invoice_no=None, status="draft", total=Decimal("12.0000"), **common)

    body = json.loads(_bytes(_partner_get(brazos, PARTNER_BILLS, path="/partner/v1/bills")))
    assert body["total_records"] == 1
    record = body["records"][0]
    assert record["id"] == "INV-0001"
    assert record["billDate"] == timezone.now().date().isoformat()
    assert record["bill_amount"] == "88.60"
    assert record["currency"] == "USD"
    assert record["lines"] == [], "a bill with no lines nests an empty list, never null"
    # ⚠ **`amount` IS NO LONGER THE BILL'S OWN TOTAL** (`CR-110-BRC04` phase 2
    # wave 3): it is the ACCOUNT'S BALANCE NOW, and the bill's total is
    # `bill_amount`. One key with two meanings across two shapes is why the
    # phase-1 route was retired rather than upgraded in place — a finance
    # system cannot see the difference.
    assert "amount" in record and record["bill_amount"] == "88.60"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11) §3 TC-1..TC-9
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_041_partner_surface.py
# exceptions: TC-5 asserts an ABSENCE that is meant to go red when Runbooks closes it — the row to update, never the assertion to delete
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

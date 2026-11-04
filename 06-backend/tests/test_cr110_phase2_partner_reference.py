# ── Trace ──────────────────────────────────────────────
# Story:   CR-110-BRC04 phase 2, waves 0 and 1 — the connector's fourth
#          operation, its declared addresses and ceilings, the reference
#          endpoint, the nine checks and the five declared routes.
# Rules:   BR-INT-037 (a connector is data — a fourth row and no screen code) ·
#          BR-INT-044 (the auth refusals are ONE refusal) · BR-TEN-003
#          (`company_id` is VERIFIED, never used to select) · hard-won law 2
#          (write the test that fires when the hold expires, in the same
#          commit) · hard-won law 7 (name the false pass and refuse it)
# ───────────────────────────────────────────────────────
"""THE PARTNER SURFACE GROWS A FOURTH OPERATION AND A FIFTH ADDRESS.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
---------------------------------------------------------------------
**Named answer, and it is the one the brief predicted:** a reference test that
asserts the seven lists EXIST and never asks whether they are GENERATED. Seven
`assert "kind" in body` lines pass forever over a payload somebody typed out by
hand, and the day a twelfth service is seeded the partner meets a code the
reference does not carry — which is the exact failure this endpoint exists to
prevent, wearing a green suite.

So the generation is asserted by ADDING A CODE and reading the payload back:
`test_a_service_added_to_the_catalogue_appears_with_no_endpoint_change` seeds a
twelfth service row and `test_a_kind_added_to_the_vocabulary_appears_…`
monkeypatches the closed vocabulary. Neither touches `reference.payload` or the
view. If either list were typed, both go red.

**Second false pass, and it is why `test_no_label_is_its_own_code` exists:** a
lane silencing the missing-word case by writing `"backbill": "backbill"` turns
it green and publishes a label that tells a partner nothing — `DEF-INT-5500`'s
shape one module along, which is where this file's pattern comes from.

**Third, and it is the subtlest:** every list assertion is guarded by a
minimum length, because an empty vocabulary makes a `for … in` assertion
vacuously true and prints green over nothing.

RED PROVED FIRST, IN `pytest` — the harness that runs it
---------------------------------------------------------
Every case below was run against the pre-change tree or against a deliberately
broken one before it was trusted green; the failures are quoted in the CR
section and in this lane's report. `python3 <module>` was not used anywhere,
because a proof through an entry point nothing uses is no proof at all
(hard-won law 7, `DEF-GOV-3733`).
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations import models, partner_api, partner_urls, reference, services
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

ACLARIAN = "erp_aclarian"
ALLOWED_ADDRESS = "198.51.100.12"
BLOCKED_ADDRESS = "203.0.113.99"
ALLOWLIST = "198.51.100.0/24, 203.0.113.7"
KEY = "sbh_live_7Q2F_brazosbend_do_not_reuse"
HINT = "••••7Q2F"


# ══════════════════════════════════════════════════════════════════════════
# WAVE 0 · the connector is one file, and the screen reads it
# ══════════════════════════════════════════════════════════════════════════


def test_aclarian_declares_four_operations() -> None:
    """The PO's first row: *a 4th row appears on its connection screen*."""
    names = [one.name for one in REGISTRY.require(ACLARIAN).operations]
    assert names == ["serve_payment", "serve_bill", "serve_customer", "serve_ledger"], (
        "the three existing keys are KEPT — they are the naming format the PO "
        f"approved (`<runner>_<noun>`) — and `serve_ledger` is appended: {names}"
    )


def test_every_aclarian_operation_names_its_own_path() -> None:
    """The PO's second row: *the endpoint column stops showing a dash*.

    ⚠ **AND THE VENDOR'S NAME IS IN NONE OF THEM.** PO 2026-09-16: *"why
    aclarian in it - we cna make it generic - saying partner"*. The supplied
    document wrote `/api/ix/aclarian/…`; this asserts we did not build it.
    """
    operations = REGISTRY.require(ACLARIAN).operations
    assert len(operations) == 4
    for one in operations:  # `/partner/v1/accounts` since `DEF-INT-5623`
        assert one.served_path, f"{one.name} names no path — the column draws a dash"
        assert one.served_path.startswith("/partner/v1/"), one.served_path
        assert "aclarian" not in one.served_path.lower(), (
            f"{one.served_path} makes one vendor a URL segment — "
            "one base URL for every partner (PO 2026-09-16)"
        )


def test_every_aclarian_operation_names_its_own_ceiling() -> None:
    """The PO's third row: *the limit column shows a number*."""
    for one in REGISTRY.require(ACLARIAN).operations:
        assert one.rate_limit_per_minute == 60, (
            f"{one.name} ships {one.rate_limit_per_minute} — the four are uniform at "
            "60 and the reasoning is in the manifest's own docstring"
        )


def test_the_scope_ticks_read_four() -> None:
    """The PO's fourth row: *the clerk's "What they may read" ticks go from 3 to 4*.

    ⚠ **THE TICKS ARE NOW THE API ROWS THEMSELVES (2026-09-16).** The PO's row
    is still true and is asserted where it now lives: four operations, so four
    switches on the set-up screen and four names a key may carry. The `scopes`
    field this used to read was single-value — a clerk could grant one of the
    four — which is the defect the PO reported against this very connector.
    """
    manifest = REGISTRY.require(ACLARIAN)
    assert [one.name for one in manifest.operations] == [
        "serve_payment",
        "serve_bill",
        "serve_customer",
        "serve_ledger",
    ]
    assert not any(one.name == "scopes" for one in manifest.fields)


def test_the_display_name_and_summary_did_not_move() -> None:
    """The PO's fifth row: *unchanged*. Stated as a test because a wave that
    rewrites a connector's card while adding an operation is a wave that
    changed what a clerk sees without being asked to."""
    manifest = REGISTRY.require(ACLARIAN)
    assert manifest.display_name == "Aclarian"
    assert manifest.summary == "Your finance system collects payments and bills from here."


def test_the_connector_change_needs_no_migration() -> None:
    """The PO's sixth row: *none — a connector is a row, never a table*.

    ⚠ **A CHECK THAT COULD NOT FAIL WOULD BE EASY HERE** — asserting *no
    migration file mentions aclarian* is true of a repo that has never heard of
    it. So the assertion is the one that would actually break: the four
    operations are readable from the REGISTRY, with no database at all. This
    case carries no `django_db` mark, so it would error rather than pass if it
    touched one.
    """
    assert len(REGISTRY.require(ACLARIAN).operations) == 4


@pytest.mark.django_db
def test_the_screen_row_carries_the_path_and_the_ceiling(brazos, dana) -> None:
    """END TO END, because wave 0's whole promise is *no screen code*.

    `ConnectionDetailPage` renders `operation.endpoint` and
    `operation.rate_limit_per_minute` straight off this payload, so a row that
    is right HERE is a row that is right on screen. Measured on the running
    product before the change: both were `null` on all three rows.

    ⚠ **THE CEILING CASE IS A REAL DEFECT FIX AND NOT A NEW FEATURE**
    (`DEF-INT-5513`). `_operation_row` called `rate_limit_for(connection)` with
    no operation, and the manifest's declared default is the THIRD of that
    function's three sources — reachable only when the operation is passed. So
    every connector that declares its own ceiling displayed **100** while the
    door enforced **60**.
    """
    from apps.integrations import selectors

    with tenant_ctx(brazos):
        _connect(brazos, dana)
        grid = selectors.grid(brazos.id)
    card = next(one for one in grid["providers"] if one["key"] == ACLARIAN)
    rows = {one["name"]: one for one in card["operations"]}
    assert len(rows) == 4, "four API rows on the connection screen"
    for name, expected in (
        # ⚠ **`/partner/v1/…` WITHOUT `/api` UNTIL `DEF-INT-10020`** — the
        # address a System Admin copies from this column must be one that
        # answers (`addressing.OUR_API_ROOT`).
        ("serve_payment", "/api/partner/v1/payments"),
        ("serve_bill", "/api/partner/v1/bills"),
        # ⚠ **`/partner/v1/customers` UNTIL 2026-09-17 (`DEF-INT-5623`)** — the
        # PO ruled the partner surface must call an account an account, and
        # there is ONE route table, so every partner's path moved together.
        ("serve_customer", "/api/partner/v1/accounts"),
        ("serve_ledger", "/api/partner/v1/ledger"),
    ):
        assert rows[name]["endpoint"] == expected, f"{name} draws a dash"
        assert rows[name]["rate_limit_per_minute"] == 60, (
            f"{name} shows {rows[name]['rate_limit_per_minute']} where the door "
            "enforces 60 — a limit nobody may edit, displayed wrongly"
        )


# ══════════════════════════════════════════════════════════════════════════
# WAVE 1 · the reference endpoint, and the only question that matters
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_payload_carries_exactly_the_seven_lists(brazos, dana) -> None:
    with tenant_ctx(brazos):
        body = reference.payload(brazos.id)
    assert list(body) == list(reference.REFERENCE_KEYS)
    assert set(body) == {
        "kind",
        "service",
        "billType",
        "invoiceStatus",
        "tender",
        "accountStatus",
        "transactionType",
        # ⚠ **THE LAST THREE ARRIVED WITH WAVE 4** (`CR-110-BRC04` phase 2).
        # The payment payload carries four coded fields and three of them are
        # vocabularies no other payload uses; a partner that cached this
        # document and then met `paymentPayType: cleared` on a payment would
        # have nothing to resolve it against, which is the exact failure the PO
        # commissioned this endpoint to prevent. `tenderType` is the fourth and
        # resolves through the older key `tender`, which is left as it is.
        "paymentType",
        "projectType",
        "paymentPayType",
    }
    for key, rows in body.items():
        assert rows, f"{key} is empty — an empty list makes every check below vacuous"
        for row in rows:
            assert set(row) == {"code", "label"}, f"{key} rows carry code and label only: {row}"
            assert row["code"] and row["label"]


@pytest.mark.django_db
def test_the_eleven_services_are_the_seed_and_not_a_typed_list(brazos) -> None:
    """Eleven today, `fire` at position 11, and NOT written down here as a list
    of eleven strings — the count comes from the table both sides."""
    from apps.tenancy.models import Service

    with tenant_ctx(brazos):
        body = reference.payload(brazos.id)
        expected = set(Service.objects.filter(active=True).values_list("code", flat=True))
    assert {one["code"] for one in body["service"]} == expected
    assert len(expected) >= 11, f"only {len(expected)} services — is the seed applied?"
    assert "storm_water" in expected and "fire" in expected


@pytest.mark.django_db
def test_a_service_added_to_the_catalogue_appears_with_no_endpoint_change(brazos) -> None:
    """⚠ **THE CASE THIS WHOLE FILE IS FOR.** *"A twelfth service next year must
    appear here with no code change — that is the whole point, and it is what
    makes the partner's parser survive."*

    A twelfth service is seeded and the payload is read back. Nothing in
    `reference.py` and nothing in `partner_api.py` is touched. If the list were
    typed, this goes red and names the code that went missing.
    """
    from apps.tenancy.models import Service

    with tenant_ctx(brazos):
        before = {one["code"] for one in reference.payload(brazos.id)["service"]}
        Service.objects.create(code="hydrogen", name="Hydrogen", sort=99, active=True)
        after = {one["code"] for one in reference.payload(brazos.id)["service"]}
    assert "hydrogen" not in before
    assert "hydrogen" in after, (
        "a twelfth service did NOT reach the reference payload — the list is "
        "typed somewhere and a partner would meet a code it cannot resolve"
    )
    assert after - before == {"hydrogen"}


@pytest.mark.django_db
def test_a_kind_added_to_the_vocabulary_appears_with_no_endpoint_change(
    brazos, monkeypatch
) -> None:
    """The same proof for a CLOSED vocabulary, which cannot be seeded.

    A seventh line kind is added to `billing.models.LINE_KINDS` and the payload
    is read back. It arrives with a DERIVED label, which is the deliberate
    runtime fallback — a partner's nightly pull must not fail over our
    bookkeeping — and `test_every_closed_code_has_a_written_word` below is what
    goes red so somebody writes the real sentence.
    """
    from apps.billing import models as billing_models

    monkeypatch.setattr(
        billing_models, "LINE_KINDS", (*billing_models.LINE_KINDS, "deposit_interest")
    )
    with tenant_ctx(brazos):
        rows = reference.payload(brazos.id)["kind"]
    found = {one["code"]: one["label"] for one in rows}
    assert "deposit_interest" in found, "the kind list is typed, not read from its owner"
    assert found["deposit_interest"] == "Deposit interest", "the derived fallback"


@pytest.mark.django_db
def test_a_tenants_own_tender_reaches_the_partner(brazos, dana) -> None:
    """Tender and account status are the TENANT's lookups, not the product's —
    two utilities legitimately answer differently. `US-PAY-001` TC-3 is a
    tenant adding *Bill-pay portal* and using it the same afternoon."""
    from apps.tenancy.models import PaymentMethod

    with tenant_ctx(brazos):
        before = {one["code"] for one in reference.payload(brazos.id)["tender"]}
        PaymentMethod.objects.create(
            tenant=brazos, code="billpay_portal", name="Bill-pay portal", active=True
        )
        after = {one["code"]: one["label"] for one in reference.payload(brazos.id)["tender"]}
    assert "billpay_portal" not in before
    assert after["billpay_portal"] == "Bill-pay portal", "the clerk's own word travels"


@pytest.mark.django_db
def test_a_deactivated_tender_stops_travelling(brazos, dana) -> None:
    """IS-1 deactivates rather than deletes, and a retired method must not be
    published as one a partner may meet on a payload."""
    from apps.tenancy.models import PaymentMethod

    with tenant_ctx(brazos):
        row = PaymentMethod.objects.create(
            tenant=brazos, code="tin_can", name="Tin can", active=True
        )
        assert "tin_can" in {one["code"] for one in reference.payload(brazos.id)["tender"]}
        PaymentMethod.objects.filter(pk=row.pk).update(active=False)
        assert "tin_can" not in {one["code"] for one in reference.payload(brazos.id)["tender"]}


@pytest.mark.django_db
def test_the_account_statuses_are_the_tenants_own(brazos) -> None:
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        body = reference.payload(brazos.id)
        expected = set(
            customer_models.AccountStatus.objects.filter(
                tenant=brazos, active=True
            ).values_list("code", flat=True)
        )
    assert expected, "no account statuses seeded — the assertion below would be vacuous"
    assert {one["code"] for one in body["accountStatus"]} == expected


@pytest.mark.django_db
def test_no_behaviour_class_reaches_the_partner(brazos) -> None:
    """`billable_base_only` is how OUR billing keys off a tenant's label. A
    finance system handed it would be invited to make billing decisions from
    it, which is not a decision it has any business making."""
    with tenant_ctx(brazos):
        body = reference.payload(brazos.id)
    published = json.dumps(body)
    for word in ("billable_base_only", "non_billable", "behavior_class"):
        assert word not in published, f"{word} travelled to a partner"


# ── the labels, and the two false passes ────────────────────────────────────

CLOSED = (
    ("kind", "apps.billing.models.LINE_KINDS", reference.LINE_KIND_LABELS),
    ("billType", "apps.billing.models.BILL_TYPES", reference.BILL_TYPE_LABELS),
    ("invoiceStatus", "apps.billing.models.INVOICE_STATUSES", reference.INVOICE_STATUS_LABELS),
    ("transactionType", "apps.ledger.models.JE_TYPES", reference.TRANSACTION_TYPE_LABELS),
)


@pytest.mark.django_db
def test_every_closed_code_has_a_written_word(brazos) -> None:
    """⚠ **THIS IS THE CASE THE BRIEF ASKED FOR: it FAILS when a new code exists
    with no label.**

    `DEF-INT-5500` one module along is the same shape — a generated list grew a
    member, nobody wrote the word, and the machine string reached a screen. Here
    it would reach a partner's accountant as `Deposit interest` at best and as
    a raw code at worst, and nothing else in the repo asks the question.
    """
    with tenant_ctx(brazos):
        body = reference.payload(brazos.id)
    missing: dict[str, list[str]] = {}
    for key, owner, labels in CLOSED:
        codes = [one["code"] for one in body[key]]
        assert len(codes) >= 3, f"{key} holds {len(codes)} codes — is {owner} loaded?"
        short = [one for one in codes if one not in labels]
        if short:
            missing[key] = short
    assert not missing, (
        "codes a partner would meet with no meaning written for them: "
        + "; ".join(f"{key} ({', '.join(codes)})" for key, codes in missing.items())
        + " — each is served with a label derived from the code itself, which "
        "says nothing a partner's accountant can act on"
    )


def test_no_label_is_its_own_code() -> None:
    """THE FALSE PASS, NAMED AND REFUSED (law 7 habit 2).

    A lane silencing the case above by writing `"backbill": "backbill"` turns
    it green and changes nothing a partner can use. Neither may a label be the
    derived fallback written out by hand, which is the same trick one step
    cleverer.
    """
    wrong = []
    for key, _owner, labels in CLOSED:
        for code, label in labels.items():
            if label == code or label == reference.derived_label(code):
                wrong.append(f"{key}.{code} = {label!r}")
    assert not wrong, f"words that say nothing the code did not: {wrong}"


def test_the_keys_are_declared_once() -> None:
    """The published shape and the declared shape cannot drift: `payload()`
    builds its keys FROM `REFERENCE_KEYS`, so a vocabulary cannot be added
    without that tuple moving.

    ⚠ **SEVEN UNTIL WAVE 4 AND TEN SINCE.** The count is stated rather than
    derived on purpose — a case that read `len(REFERENCE_KEYS)` on both sides
    would pass over a vocabulary quietly REMOVED, which is this repo's own
    *structurally incapable of failing* shape.
    """
    assert len(reference.REFERENCE_KEYS) == 10
    assert len(set(reference.REFERENCE_KEYS)) == 10


# ══════════════════════════════════════════════════════════════════════════
# THE NINE CHECKS
# ══════════════════════════════════════════════════════════════════════════


def _scope_of(provider=ACLARIAN):
    return [one.name for one in REGISTRY.require(provider).operations if one.they_call_us]


def _connect(tenant, actor, *, key=KEY, hint=HINT, scope=None, allowlist=ALLOWLIST):
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=ACLARIAN,
        label="Aclarian",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={"client_id": "aclarian", serve.ALLOWLIST_CONFIG_KEY: allowlist},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=list(_scope_of() if scope is None else scope),
    )
    return connection


def _get(tenant, view, *, key=KEY, address=ALLOWED_ADDRESS, query=None, path="/partner/v1/reference"):
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    params = {"company_id": str(tenant.id)}
    params.update(query or {})
    params = {name: value for name, value in params.items() if value is not None}
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}{path}", params, REMOTE_ADDR=address
    )
    if key is not None:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {key}"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return view(request)


def _body(response):
    return response.content if hasattr(response, "content") else response.rendered_content


@pytest.fixture()
def wired(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        connection = _connect(brazos, dana)
    return connection


@pytest.mark.django_db
def test_a_good_key_reads_the_reference(brazos, dana, wired) -> None:
    response = _get(brazos, partner_api.partner_reference)
    assert response.status_code == 200, _body(response)
    body = json.loads(_body(response))
    assert list(body) == list(reference.REFERENCE_KEYS)
    with tenant_ctx(brazos):
        run = models.IntegrationRun.objects.get()
    assert "Reference" in run.summary and HINT in run.summary
    assert KEY not in (run.summary or ""), "a run record naming a secret is a leaked secret"


def _seven_refusals(brazos, dana):
    """The SEVEN causes checks 1–5 can produce, each set up so exactly one is
    true, each timed, and the world put back afterwards.

    ⚠ **SEVEN AND NOT SIX SINCE `CR-110-BRC04` PHASE 2** — the PO's ruling
    *"you have to also check whether connector is activae whether tenant is
    active"* added the utility guard, which is the seventh cause. The list is
    derived below rather than counted here, so an eighth added without this
    helper moving fails rather than hides.
    """
    with tenant_ctx(brazos):
        connection = _connect(brazos, dana)
        credential = models.IntegrationCredential.objects.get()
    rows = models.IntegrationCredential.objects.filter(pk=credential.pk)
    connections = models.IntegrationConnection.objects.filter(pk=connection.pk)
    tenants = _tenant_rows(brazos)

    def _timed(**kwargs):
        started = time.monotonic()
        response = _get(brazos, partner_api.partner_reference, **kwargs)
        return response, time.monotonic() - started

    out = [("a key we have never seen", serve.CODE_KEY_UNKNOWN,
            *_timed(key="sbh_live_this_was_never_issued"))]

    with tenant_ctx(brazos):
        rows.update(is_active=False)
    out.append(("a revoked key", serve.CODE_KEY_REVOKED, *_timed()))
    with tenant_ctx(brazos):
        rows.update(is_active=True)

    with tenant_ctx(brazos):
        rows.update(expires_at=timezone.now() - timedelta(minutes=1))
    out.append(("an expired key", serve.CODE_KEY_EXPIRED, *_timed()))
    with tenant_ctx(brazos):
        rows.update(expires_at=None)

    out.append(("off the allowlist", serve.CODE_ADDRESS_NOT_ALLOWED,
                *_timed(address=BLOCKED_ADDRESS)))

    with tenant_ctx(brazos):
        connections.update(enabled=False)
    out.append(("a switched-off connector", serve.CODE_CONNECTOR_DISABLED, *_timed()))
    with tenant_ctx(brazos):
        connections.update(enabled=True)

    tenants.update(provisioned_at=None)
    out.append(("a utility that is not live", serve.CODE_UTILITY_INACTIVE, *_timed()))
    tenants.update(provisioned_at=timezone.now())

    with tenant_ctx(brazos):
        rows.update(scope=[])
    out.append(("a key out of scope", serve.CODE_OPERATION_NOT_IN_SCOPE, *_timed()))
    with tenant_ctx(brazos):
        rows.update(scope=list(_scope_of()))

    return out


def _tenant_rows(tenant):
    """`tenants` is RLS-exempt (B2 §2), so this needs no context — and saying so
    is the point: a lane wrapping it in one would be asserting a scope that
    does not exist on this table."""
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Tenant.objects.filter(pk=tenant.pk)


@pytest.mark.django_db
def test_the_seven_auth_refusals_are_still_one_refusal(brazos, dana) -> None:
    """⚠ **THE CENTRAL ASSERTION, AND THE ONE THIS WAVE COULD MOST EASILY HAVE
    BROKEN.** Two checks were added to `resolve_caller` and the whole value of
    that function is that its causes are indistinguishable from outside. The
    obvious way to add a check is an early return, and an early return would
    keep every body identical and still open the oracle — on the CLOCK.

    Same bytes, same status, same time, over all seven.
    """
    refusals = _seven_refusals(brazos, dana)
    assert len(refusals) == 7, "one cause per check that can fail, and no more"

    statuses = {one[2].status_code for one in refusals}
    bodies = {_body(one[2]) for one in refusals}
    assert statuses == {404}, f"a second status is an oracle: {statuses}"
    assert len(bodies) == 1, (
        "seven different bodies is an oracle — a caller holding a stolen key "
        f"would read which guard refused: {bodies}"
    )
    assert list(bodies)[0] == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    ), "the code on the wire is a CONSTANT; the cause lives in the run row"

    for name, _code, _response, elapsed in refusals:
        assert elapsed >= serve.REFUSAL_FLOOR_S, (
            f"{name} answered in {elapsed:.4f}s, under the {serve.REFUSAL_FLOOR_S}s floor"
        )
    spread = max(one[3] for one in refusals) - min(one[3] for one in refusals)
    assert spread < serve.REFUSAL_FLOOR_S, (
        f"the seven refusals spread {spread:.4f}s, wider than the floor that hides them"
    )


@pytest.mark.django_db
def test_a_switched_off_utility_is_refused_and_recorded(brazos, dana, wired) -> None:
    """Check 3, and the half the path resolver does NOT already cover.

    `tenant_id_for_subdomain` filters `deleted_at` and nothing else, so a
    signup that stopped half-way resolves, sets a tenant context, and would
    have served a partner key issued against it.
    """
    assert _get(brazos, partner_api.partner_reference).status_code == 200
    _tenant_rows(brazos).update(provisioned_at=None)
    refused = _get(brazos, partner_api.partner_reference)
    assert refused.status_code == 404
    assert _body(refused) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    _tenant_rows(brazos).update(provisioned_at=timezone.now())


@pytest.mark.django_db
def test_a_removed_utility_is_refused(brazos, dana, wired) -> None:
    """The other half of *live*. Belt and braces over the resolver, which is
    the house style on this path — the suite runs on SQLite, where RLS does not
    exist and a guarantee stated once is a guarantee stated nowhere."""
    _tenant_rows(brazos).update(deleted_at=timezone.now())
    assert _get(brazos, partner_api.partner_reference).status_code == 404
    _tenant_rows(brazos).update(deleted_at=None)


# ══════════════════════════════════════════════════════════════════════════
# `company_id` — SUPERSEDED 2026-09-17 (`CR-111-BRC04`)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE FOUR CASES ASSERTED CHECK 7 AND CHECK 7 IS GONE.** PO ruling
# 2026-09-17, verbatim: *"you will ahve to remove company ID filter from all
# Apis - we cannot tell tenant ID outside our system"*, superseding *"company_id
# = tenant id"* (2026-09-16) and *"company_id = Keys will esnure it map to tenant
# ID"* (earlier the same day).
#
# ⚠⚠ **THEY ARE REWRITTEN AND NOT DELETED, AND THE DISTINCTION IS THE WHOLE
# POINT.** Three of the four were about the `403` and are genuinely obsolete. The
# fourth — *the most important case in this file* — was never really about the
# `403` at all: it asserts that **naming another utility's id does not serve that
# utility's data**, which is `BR-TEN-003` and is exactly as true today as it was
# yesterday. Deleting it with its siblings would have removed the only case in
# this file that proves the isolation the removed check was never providing.
# It now asserts the same property through its new answer: a **200 carrying OUR
# OWN vocabulary**, not a refusal.


@pytest.mark.django_db
def test_the_wrong_company_id_changes_nothing(brazos, dana, wired) -> None:
    """Was `test_the_wrong_company_id_is_refused_with_403`.

    The parameter is accepted and ignored. A partner's document sends it on
    every call, so refusing an unknown parameter would break a live partner to
    enforce a tidiness nobody asked for.
    """
    response = _get(
        brazos, partner_api.partner_reference, query={"company_id": str(uuid.uuid4())}
    )
    assert response.status_code == 200, _body(response)
    assert list(json.loads(_body(response))) == list(reference.REFERENCE_KEYS)


@pytest.mark.django_db
def test_nothing_in_the_answer_echoes_a_utility_id(brazos, dana, wired) -> None:
    """Was `test_the_403_echoes_neither_id`, and it still holds — for a stronger
    reason than before.

    There is no longer a `403` to print an id INTO, and the reference payload
    names no utility either. So *whose utility is this* is not answerable from a
    response at all, which is what the PO's *"we cannot tell tenant ID outside
    our system"* asks for.
    """
    sent = uuid.uuid4()
    response = _get(brazos, partner_api.partner_reference, query={"company_id": str(sent)})
    printed = _body(response).decode()
    assert str(sent) not in printed and str(brazos.id) not in printed


@pytest.mark.django_db
def test_a_missing_company_id_is_served(brazos, dana, wired) -> None:
    """Was `test_a_missing_company_id_is_refused`. It is not required and not
    read; the utility comes from the key and always did."""
    response = _get(brazos, partner_api.partner_reference, query={"company_id": None})
    assert response.status_code == 200, _body(response)


@pytest.mark.django_db
def test_company_id_still_selects_nothing(brazos, lonestar, dana, erin) -> None:
    """⚠ **`BR-TEN-003`, AND STILL THE MOST IMPORTANT CASE IN THIS FILE.**

    Brazos Bend's key, naming LONE STAR RIDGE's id. **If `company_id` selected,
    this would return Lone Star Ridge's vocabulary.** It never did — it was
    compared and thrown away — and now it is not even compared. The answer is
    **Brazos Bend's own reference document**, served normally.

    ⚠ **THE ASSERTION MOVED FROM THE STATUS TO THE CONTENT, WHICH MAKES IT A
    STRONGER TEST THAN IT WAS.** A `403` proved only that we refused; it could
    not distinguish *we refused because we compared* from *we refused for some
    other reason*. Comparing the BODY against the body served with no
    `company_id` at all proves the parameter changes nothing about what comes
    back — which is the property `BR-TEN-003` actually states.
    """
    with tenant_ctx(brazos):
        _connect(brazos, dana)
    serve.reset_partner_limits()
    theirs = _get(
        brazos, partner_api.partner_reference, query={"company_id": str(lonestar.id)}
    )
    serve.reset_partner_limits()
    none_at_all = _get(brazos, partner_api.partner_reference, query={"company_id": None})

    assert theirs.status_code == 200, _body(theirs)
    assert bytes(_body(theirs)) == bytes(_body(none_at_all)), (
        "naming another utility changed the answer — something still selects on it"
    )
    assert str(lonestar.id) not in _body(theirs).decode()


@pytest.mark.django_db
def test_a_key_that_may_call_nothing_may_not_read_the_reference(brazos, dana) -> None:
    """No scope TICK does not mean no scope GUARD. A key granting nothing may
    not read the description of what it may call."""
    with tenant_ctx(brazos):
        _connect(brazos, dana, scope=[])
    assert _get(brazos, partner_api.partner_reference).status_code == 404


@pytest.mark.django_db
def test_a_key_holding_one_tick_reads_the_reference_and_is_refused_elsewhere(
    brazos, dana
) -> None:
    """⚠ **THE BRIEF'S THIRD PROOF: one tick, refused on the others.**

    A key granted `serve_bill` alone:
      · reads the reference — it holds a tick, and the reference needs no
        particular one;
      · is REFUSED on `/partner/v1/accounts`, `/…/payments` and `/…/ledger`
        with the one refusal, five words, `404`;
      · reaches `/…/bills`, whose answer is the honest *not built yet*.

    That last line is the one that matters: **a scope refusal and an unbuilt
    address must not be the same answer**, or a partner debugging its key would
    read *not built yet* as *your key is wrong*, or the reverse.
    """
    with tenant_ctx(brazos):
        _connect(brazos, dana, scope=["serve_bill"])

    assert _get(brazos, partner_api.partner_reference).status_code == 200

    refused = {
        "accounts": partner_api.partner_accounts,
        "payments": partner_api.partner_v1_payments,
        "ledger": partner_api.partner_ledger,
    }
    for what, view in refused.items():
        response = _get(brazos, view, path=f"/partner/v1/{what}")
        assert response.status_code == 404, f"{what} answered {response.status_code}"
        assert _body(response) == (
            b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
        ), f"{what} did not give the one refusal"

    allowed = _get(brazos, partner_api.partner_bills, path="/partner/v1/bills")
    # ⚠ **THIS READ `== 501` UNTIL WAVE 3 LANDED.** The property under test is
    # that the tick this key HOLDS reaches its own address while the three it
    # does not are refused — provable with a payload now rather than with a
    # placeholder, which is a stronger assertion for the same question.
    assert allowed.status_code == 200, "the tick this key holds reaches its address"
    assert "records" in json.loads(_body(allowed))


@pytest.mark.django_db
def test_the_rate_limit_still_counts(brazos, dana) -> None:
    """Check 8 over the reference endpoint, which is metered under its own
    window because it is not an operation and must not be a fifth screen row."""
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        connection = _connect(brazos, dana)
        models.IntegrationConnection.objects.filter(pk=connection.pk).update(
            config={
                "client_id": "aclarian",
                serve.ALLOWLIST_CONFIG_KEY: ALLOWLIST,
                serve.RATE_LIMIT_CONFIG_KEY: 2,
            }
        )
    assert _get(brazos, partner_api.partner_reference).status_code == 200
    assert _get(brazos, partner_api.partner_reference).status_code == 200
    third = _get(brazos, partner_api.partner_reference)
    assert third.status_code == 429
    assert json.loads(_body(third))["code"] == serve.CODE_RATE_LIMIT_REACHED
    assert third["Retry-After"] == str(serve.RETRY_AFTER_S)


# ══════════════════════════════════════════════════════════════════════════
# THE FIVE DECLARED ROUTES — and the hold that fires when it expires
# ══════════════════════════════════════════════════════════════════════════


def test_all_five_routes_are_declared() -> None:
    """The five addresses, declared once.

    ⚠ **THEY LEFT `partner_api.urlpatterns` ON 2026-09-16 AND THIS CASE WENT
    RED SAYING SO — CORRECTLY** (`DEF-INT-5546`, PO ruling of that date). They
    are `/api/partner/v1/…` now, with no `{utility}` segment at all, and they
    are registered in `partner_urls.py`, which is mounted OUTSIDE the tenant
    include. The five VIEWS never moved; only where they are registered did.
    """
    declared = {str(one.pattern) for one in partner_urls.urlpatterns}
    for what in ("reference", "accounts", "bills", "payments", "ledger"):
        assert f"partner/v1/{what}" in declared, f"{what} is not declared"
    assert not [
        str(one.pattern)
        for one in partner_api.urlpatterns
        if str(one.pattern).startswith("partner/v1")
    ], "the old address is back BESIDE the new one — a partner can name a utility again"


def test_no_route_carries_a_vendors_name() -> None:
    """PO 2026-09-16: *"why aclarian in it - we cna make it generic - saying
    partner - so that we can give it to anyone who needs bills for any
    csutomer if autherised"*. The supplied document wrote `/api/ix/aclarian/…`.
    """
    for one in list(partner_api.urlpatterns) + list(partner_urls.urlpatterns):
        pattern = str(one.pattern).lower()
        for vendor in ("aclarian", "sap", "workday", "infor", "msgp"):
            assert vendor not in pattern, f"{pattern} makes {vendor} a URL segment"


#: The view behind each declared address, so the three cases below can be driven
#: off `ROUTE_WAVE` instead of off a typed list.
#:
#: ⚠ **IT IS DERIVED BECAUSE THE TYPED VERSION WENT RED THE FIRST TIME A WAVE
#: LANDED, AND ON THE WRONG QUESTION.** Waves 5 and 2 landed within the hour on
#: 2026-09-16; each correctly removed its own row from `ROUTE_WAVE`, and three
#: cases here went red — not because anything was wrong, but because they were
#: asking a true question about a set they had written down by hand. Driven off
#: the dict, waves 3 and 4 need no edit to this file at all.
ROUTE_VIEWS = {
    "accounts": "partner_accounts",
    "bills": "partner_bills",
    "payments": "partner_v1_payments",
    "ledger": "partner_ledger",
}


def _view_for(what):
    return getattr(partner_api, ROUTE_VIEWS[what])


def test_every_unbuilt_route_names_its_wave() -> None:
    """The sentence a partner gets and the plan in the CR cannot disagree.

    ⚠ **A SUBSET SINCE THE FIRST WAVE LANDED, AND THE DIRECTION IS THE POINT.**
    Every address that still answers `501` must name a wave, or a partner is
    told *not built yet* with no date to ask for. That an address which has
    LANDED must have LEFT is the other half, and
    `test_the_unbuilt_routes_go_red_the_day_their_wave_lands` is what enforces
    it — asserting equality here made one case do both jobs and neither well.
    A wave named for an address `SERVED_ROUTES` does not declare is a typo
    nothing else would catch.
    """
    assert set(partner_api.ROUTE_WAVE) <= set(partner_api.SERVED_ROUTES)
    assert set(partner_api.ROUTE_WAVE) <= set(ROUTE_VIEWS)


def test_an_unbuilt_route_is_never_an_empty_result_set() -> None:
    """⚠ **THE MOST EXPENSIVE WRONG ANSWER, AND IT WOULD HAVE BEEN THE EASIEST
    TO WRITE.** `{"records": [], "total_records": 0}` reads to a finance system
    as *this utility issued no bills*, and it would post that. A missed bill is
    a missed GL posting and nothing on either side raises.

    A `404` is no better: it is this surface's REFUSAL, so a partner would read
    *your key is bad* and go looking at its credentials.

    ⚠ **THIS CASE DROVE FOUR LIVE ADDRESSES UNTIL 2026-09-16 AND NOW DRIVES
    NONE, BECAUSE ALL FOUR SERVE** — and its own assertion said what to do
    about that: *"every wave has landed — retire this case rather than empty
    it"*. Emptying it is the trap: a `for … in {}` is green over nothing.
    Retiring it means asking the same question of the thing that ANSWERS it,
    `_not_yet_served`, which the sixth declared-before-built address will reach
    exactly as these four did. No tenant, no key and no `django_db` mark — so
    it errors rather than passes if it ever touches a database again.
    """
    response = partner_api._not_yet_served("bills")
    assert response.status_code == 501
    body = json.loads(response.content)
    assert body["code"] == "NOT_YET_SERVED"
    assert body["resource"] == "bills"
    assert "records" not in body and "total_records" not in body


@pytest.mark.django_db
def test_the_unbuilt_routes_go_red_the_day_their_wave_lands(brazos, dana, wired) -> None:
    """⚠ **HARD-WON LAW 2'S OTHER HALF, WRITTEN IN THE SAME COMMIT AS THE HOLD.**

    *"When you write a hold, write the test that fires when the hold expires."*
    The four addresses above answer `501` and name a wave. The day a sibling
    lane serves one of them, this case goes RED and names it — and the lane
    that landed it then has to remove its row from `ROUTE_WAVE`, retire the
    phase-1 `v1/payments` / `v1/billing` pair if it was payments or bills, and
    say so on the CR. Without this, the honest refusal rots into a live screen
    behind a dead control (`DEF-CWP-3925`), which is the mirror this repo pays
    for most.
    """
    still_held = []
    for what in ROUTE_VIEWS:
        if _get(brazos, _view_for(what), path=f"/partner/v1/{what}").status_code == 501:
            still_held.append(what)
    assert sorted(still_held) == sorted(partner_api.ROUTE_WAVE), (
        "an address stopped answering `not built yet` and `ROUTE_WAVE` did not "
        f"move: held={sorted(still_held)} declared={sorted(partner_api.ROUTE_WAVE)}. "
        "Landing a wave and releasing the hold that pointed at it are two acts "
        "and only the first feels like the work — this is the second."
    )


@pytest.mark.django_db
def test_an_unbuilt_route_still_asks_every_question_first(brazos, dana) -> None:
    """A declared-but-unbuilt address is not a hole in the door. A bad key gets
    the SAME refusal there as everywhere else — `501` is only ever reached by a
    caller that has passed all eight checks."""
    with tenant_ctx(brazos):
        _connect(brazos, dana)
    response = _get(brazos, partner_api.partner_ledger, key="sbh_live_never_issued",
                    path="/partner/v1/ledger")
    assert response.status_code == 404
    assert _body(response) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


@pytest.mark.django_db
def test_the_published_specification_names_all_four_operations(brazos, dana, wired) -> None:
    """⚠ **AN OPERATION MISSING FROM THE SPECIFICATION IS A CAPABILITY NOBODY
    CAN DISCOVER, AND NOTHING WENT RED OVER IT.**

    `partner_openapi` derived each path by string surgery on the operation NAME
    against a two-entry map, so an operation the map did not know was silently
    skipped. `serve_customer` has been declared since wave C and appeared in no
    published specification; `serve_ledger` would have joined it. The path comes
    off the manifest now.

    The unbuilt three carry their `501` here too, or the document promises a
    payload the server refuses.
    """
    response = _get(brazos, partner_api.partner_openapi, path="/partner/v1/openapi.json")
    assert response.status_code == 200
    spec = json.loads(_body(response))
    assert set(spec["paths"]) == {
        "/partner/v1/payments",
        "/partner/v1/bills",
        # ⚠ **`/partner/v1/customers` UNTIL 2026-09-17 (`DEF-INT-5623`).** The
        # RETIRED address is deliberately NOT here: the document is built from
        # the manifest's operations and none points at it any more, so a
        # partner reading this learns what to call rather than what used to
        # exist. `partner_customers_retired` is what a caller still holding it
        # meets, and it names this path in the `410`.
        "/partner/v1/accounts",
        "/partner/v1/ledger",
    }, "the specification is the manifest's four, by their own declared addresses"
    for what in ROUTE_VIEWS:
        route = f"/partner/v1/{what}"
        described = spec["paths"][route]["get"]["responses"]
        if what in partner_api.ROUTE_WAVE:
            assert "501" in described, f"{route} promises a payload the server answers 501 to"
            assert partner_api.ROUTE_WAVE[what] in described["501"]["description"]
        else:
            # ⚠ **AND THE MIRROR, WHICH IS THE HALF A LANDED WAVE BREAKS.** An
            # address that SERVES must stop advertising a `501`, or a partner
            # writes a branch for a response it will never receive and carries
            # it for ever.
            assert "501" not in described, f"{route} serves and still promises a 501"


@pytest.mark.django_db
def test_the_specification_is_the_callers_own_connector(brazos, dana) -> None:
    """⚠ **A WORKDAY KEY READ ACLARIAN'S SPECIFICATION** (`DEF-INT-5525`).

    `partner_openapi` took `partner_provider_keys()[0]` — *any of the five, they
    are one drawing repeated*. That was measured of their SCREENS and was never
    a claim about their OPERATIONS, and phase 2 made it false: Aclarian has four
    reads and declared addresses where the other four have three and none. A
    partner was being offered endpoints its key may not call and told nothing
    about the ones it may.
    """
    from apps.integrations import models as int_models

    with tenant_ctx(brazos):
        connection = _connect(brazos, dana)
        int_models.IntegrationConnection.objects.filter(pk=connection.pk).update(
            provider_key="erp_workday"
        )
    spec = json.loads(_body(_get(brazos, partner_api.partner_openapi, path="/partner/v1/openapi.json")))
    assert spec["info"]["title"] == "Workday", spec["info"]
    assert set(spec["paths"]) == {"/v1/payments", "/v1/billing"}, (
        "a Workday key was served Aclarian's four addresses"
    )
    # ⚠ **AND BOTH OF THEM ARE RETIRED** (`CR-110-BRC04` phase 2 wave 4). The
    # four ERP manifests other than Aclarian declare no `served_path`, so they
    # still fall back to the phase-1 pair — which now answers `410`. The
    # document says so rather than promising a payload. `DEF-INT-5545` is the
    # row for giving those four manifests the phase-2 paths: one line each, and
    # it belongs to whoever owns them rather than to a lane passing through.
    for route in spec["paths"]:
        described = spec["paths"][route]["get"]["responses"]
        assert "410" in described, f"{route} is retired and the document does not say so"


@pytest.mark.django_db
def test_the_specification_never_lists_the_six_auth_causes(brazos, dana, wired) -> None:
    """`BR-INT-044` in the one place a caller is INVITED to read. A lane adding
    the causes to be helpful would publish the enumeration map this module
    exists to withhold."""
    printed = _body(_get(brazos, partner_api.partner_openapi, path="/partner/v1/openapi.json")).decode()
    for code in serve.RECORD_ONLY_CODES:
        assert code not in printed, f"{code} is published in the specification"
    assert serve.SHARED_REFUSAL_CODE in printed


@pytest.mark.django_db
def test_the_default_page_is_a_thousand(brazos) -> None:
    """PO 2026-09-16: *"make this as 1000 per page"*. A 40,000-account month-end
    walk is 40 calls rather than 80, inside the manifest's sixty a minute."""
    assert partner_api.DEFAULT_PAGE_SIZE == 1000
    assert partner_api.MAX_PAGE_SIZE == 1000


def test_we_publish_page_size_and_accept_limit() -> None:
    """⚠ **AMENDED 2026-09-17 (`CR-111-BRC04`) — THE DIVERGENCE WAS RECORDED AND
    IS NOW REVERSED, AND THE REASONING IS WHY.**

    This case used to assert `'"limit"' not in source`. That was right while the
    choice was RENAME-OR-NOT: one partner's spelling is not a reason to rename a
    parameter on a surface every partner shares.

    It is now ACCEPT-OR-BREAK. Invoice Cloud's document sends `limit`, a real
    utility is being onboarded on it, and **a partner whose page size is silently
    ignored does not fail** — it pages through 40,000 accounts a thousand at a
    time believing it asked for ten, which surfaces as a timeout six weeks later.

    **`DEF-014` is answered rather than waved at.** What it forbids is two names
    for one value in what we PUBLISH. We publish `page_size` and only
    `page_size` — in the envelope, in the OpenAPI document and in the CSV
    headers — and `limit` is accepted on the way IN and named nowhere on the way
    out. That is what these two halves assert.
    """
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    assert partner_api._page_params(factory.get("/x", {"limit": "25"}))[1] == 25
    # ⚠ **AND `page_size` WINS WHEN BOTH ARE SENT** — a caller sending both has a
    # configuration error, and the name we document is the one it meant.
    assert partner_api._page_params(
        factory.get("/x", {"page_size": "10", "limit": "25"})
    )[1] == 10


# ── Lifecycle ──────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 waves 0 and 1 (PO rulings of 2026-09-16)
# generated: 2026-09-16 by the CR-110-BRC04 phase 2 lane A build lane
# gates: every case proved RED in `pytest` before it was trusted green — the
#        harness that runs it, never `python3 <module>` (DEF-GOV-3733)
# status: VERIFIED-UNRATIFIED
# ───────────────────────────────────────────────────────

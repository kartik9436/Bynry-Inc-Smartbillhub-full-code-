# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-044 (EP-INT-13) — the inbound door. CR-069 wave N, task N4.
#           Screens: none (a kiosk POSTs here) · S142 draws the run row.
# Rules:    BR-INT-058 (the door stops after `dedupe`; the apply is Runbooks') ·
#           BR-INT-021 (authenticate before the body is trusted) · BR-INT-030
#           (the reply is a declared position) · BR-INT-020 D (the composite
#           key carries the reversal marker) · BR-INT-044 (the refusal reveals
#           nothing) · BR-INT-045 (the manifest's numbers) · BR-PAY-003 ·
#           BR-PAY-036 · CLAUDE.md hard rule 1 · rule 6 · rule 7 · law 3 ·
#           law 14 (the savepoint, proved on PostgreSQL)
# Tests:    this file — TC-1 the payment lands · TC-2 the replay is 409 · TC-3
#           the return is not a duplicate (THE EXIT TEST) · TC-4 the allowlist,
#           before the body is read · TC-5 a wrong key · TC-6 the load-time
#           refusal · TC-7 the account lookup and its 200 · TC-9 the batch on
#           PostgreSQL · TC-10 a key at the wrong utility · plus the boundary
#           and the three fail-closed cases.
# Impacts:  apps/integrations/inbound.py · inbound_api.py ·
#           apps/integrations/seams/payments.py ·
#           apps/payments/webhooks.land_delivery
# ───────────────────────────────────────────────────────
"""US-INT-044 — the kiosk payment, twice, and the return that is not a duplicate.

⚠ **THE ASSERTION THIS FILE EXISTS FOR IS
`test_tc3_a_return_carrying_the_same_id_is_not_a_duplicate`** — `CR-069` §12's
phase-5 exit test, driven by the redacted captured payload in
`apps/integrations/fixtures/payments_kiosk/`. A return carries the SAME
provider id as the payment it reverses, so a key that is only that id refuses
every return as a duplicate of its own payment. The composite key is what
makes them two rows, and the test asserts BOTH: that the return lands, and
that the two keys differ by exactly the marker.

⚠ **AND THE SECOND-MOST IMPORTANT ONE IS
`test_tc_boundary_the_door_applies_nothing`.** `BR-INT-058` says the door
stops at `dedupe`; a lane that later folds `record_payment` back in would make
the product *look* more finished and would break the rule the PO ruled on
2026-09-06. The assertion is `Payment.objects.count() == 0` after a payment
lands — an absence, asserted, so the boundary cannot close silently.

⚠ **TWO CASES IN THIS FILE WERE FIRST WRITTEN SO THAT THEY COULD NOT FAIL, AND
BOTH WERE FOUND BY BREAKING THE GUARD RATHER THAN BY READING THE TEST
(CLAUDE.md law 7, second shape).** TC-9's PostgreSQL case never reached the
`IntegrityError` at all, because `land_delivery`'s SELECT recognises a
duplicate before it inserts — so removing the savepoint left it green on
PostgreSQL. TC-4 asserted *"the body is not parsed"* by sending broken JSON,
and `_parsed` swallows broken JSON on purpose — so parsing it early changed
nothing observable. **Both now assert the mechanism instead of a symptom:**
TC-9 blinds guard 1 so the unique index is what refuses, and TC-4 replaces
the parser with a recorder and asserts the recording is empty. The general
lesson is the one law 7 states — *ask what would make this check pass
wrongly* — and the practical one is that a test about ORDER has to observe
the order, and a test about a DATABASE refusal has to make the database
refuse.

⚠ **TC-9 IS `requires_postgres` AND THAT IS NOT A CONVENIENCE.** It is
CLAUDE.md hard-won law 14's exact case: the door lands a batch one item at a
time and catches `IntegrityError` on the duplicate. On PostgreSQL that aborts
the whole transaction unless the INSERT sits in a SAVEPOINT, and **the first
item — a real payment — is lost at COMMIT**. SQLite has no aborted-transaction
state and `config/settings/test.py` hardcodes in-memory SQLite, so the broken
version passes this entire file, green, on every machine.
"""

from __future__ import annotations

import json

import pytest
from django.db import connection
from django.utils import timezone

from apps.integrations import inbound, models, services
from apps.integrations.registry import (
    REGISTRY,
    Auth,
    Disposition,
    Idempotency,
    Manifest,
    ManifestError,
    Operation,
    Registry,
)
from apps.integrations.runners import serve
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "CLAUDE.md hard-won law 14 — a failed statement poisons the whole PostgreSQL "
        "transaction and SQLite has no such state, so the version WITHOUT the savepoint "
        "passes this file on sqlite and loses the first payment of a batch in production. "
        'Run with DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL="postgres://…".'
    ),
)

KIOSK = "payments_kiosk"

#: `US-INT-044` §4's own test data, verbatim: the credential header
#: `X-Kiosk-Key` (`••••K1OS`) and the allowlist `198.51.100.0/24, 203.0.113.7`.
KIOSK_KEY = "sbh_live_K1OS_brazosbend_do_not_reuse"
KIOSK_HINT = "••••K1OS"
ALLOWLIST = "198.51.100.0/24, 203.0.113.7"
ALLOWED_ADDRESS = "198.51.100.12"
BLOCKED_ADDRESS = "203.0.113.99"

#: The story's payload: `K-88231 · $42.10 · CASH` for `ACC-1048`, and the
#: return `K-88231 · RETURN · R01`.
EVENT_ID = "K-88231"


def _fixture(name: str) -> dict:
    """The REAL captured payload, redacted, read off disk (`N4`).

    ⚠ READ FROM THE FILE RATHER THAN BUILT IN PYTHON, and the difference
    matters for the exit test: `CR-069` §12 says the replay is *"demonstrated
    by replaying a real captured payload"*. A dict a test author typed proves
    the test author's idea of the shape; a file the vendor's own sample was
    redacted into proves the shape.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "apps/integrations/fixtures/payments_kiosk"
    return json.loads((root / name).read_text())


# ══════════════════════════════════════════════════════════════════════════
# Fixtures — one kiosk connection with a key we issued
# ══════════════════════════════════════════════════════════════════════════


def _connect_kiosk(tenant, actor, key=KIOSK_KEY, hint=KIOSK_HINT, *, allowlist=ALLOWLIST):
    """A `payments_kiosk` connection with a key we issued.

    Built through `services.record_credential` with the blind index computed
    from `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT` — IMPORTED, never retyped. If
    the door and the issuer ever hashed under different context strings every
    valid key would be refused and the door would still look like it works,
    because a refused key is exactly what a wrong key looks like.
    """
    connection_row = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=KIOSK,
        label="Payment kiosk network",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={serve.ALLOWLIST_CONFIG_KEY: allowlist},
    )
    services.record_credential(
        actor=actor,
        connection=connection_row,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        # `CR-110-BRC04` — the kiosk's key may call all three of its
        # operations, which is what these cases were written against. A key
        # granting NOTHING is refused at the door, and every case in this file
        # went red with the one refusal the day the guard landed; the scope's
        # own behaviour is `tests/test_cr110_key_scope.py`.
        #
        # ⚠ **DERIVED FROM THE MANIFEST, NEVER TYPED.** The same list written
        # out by hand in two sibling suites went stale inside one day, when
        # this CR's own wave C renamed a connector's operations, and took
        # nineteen cases with it — every one refusing in the door's five words
        # because the key named operations the connector no longer had.
        scope=[one.name for one in REGISTRY.require(KIOSK).operations if one.they_call_us],
    )
    return connection_row


@pytest.fixture()
def kiosk(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        return _connect_kiosk(brazos, dana)


def _post(
    tenant,
    *,
    operation="payments",
    body=None,
    raw=None,
    key=KIOSK_KEY,
    address=ALLOWED_ADDRESS,
    provider=KIOSK,
):
    """One kiosk call, through the REAL view at the REAL address.

    ⚠ **THE VIEW, NOT `inbound.receive`.** The header name, the source
    address, the tenant context and the status number are all decided between
    the wire and the door, and a test that called `receive()` directly would
    assert the door and prove nothing about the four things around it. This is
    also what makes TC-4's *"the body is never parsed"* meaningful — DRF is in
    the path, and DRF is what would parse it.

    `REMOTE_ADDR` rather than `X-Forwarded-For`: with `TRUSTED_PROXY_COUNT = 0`
    the forwarded header is ignored, which is the property that stops a caller
    spoofing past the allowlist, and a test using the header would exercise a
    path production does not take.
    """
    from rest_framework.test import APIRequestFactory

    from apps.integrations import inbound_api
    from core import tenancy as core_tenancy

    payload = raw if raw is not None else json.dumps(body or {}).encode()
    factory = APIRequestFactory()
    request = factory.post(
        f"/api/{tenant.subdomain}/integrations/inbound/{provider}/{operation}",
        data=payload,
        content_type="application/json",
        REMOTE_ADDR=address,
    )
    if key is not None:
        request.META["HTTP_X_KIOSK_KEY"] = key
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return inbound_api.inbound_door(request, key=provider, operation=operation)


def _bytes(response):
    return response.content if hasattr(response, "content") else response.rendered_content


def _deliveries(tenant):
    from apps.payments import models as payment_models

    return list(
        payment_models.PaymentWebhookEvent.objects.filter(tenant=tenant).order_by("created_at")
    )


def _payment_count(tenant):
    from apps.payments import models as payment_models

    return payment_models.Payment.objects.filter(tenant=tenant).count()


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · the kiosk posts a payment
# ══════════════════════════════════════════════════════════════════════════


def test_tc1_a_kiosk_payment_lands_raw_and_is_answered_ok(brazos, dana, kiosk):
    """`K-88231 · $42.10 · CASH` → the manifest's `ok`, the envelope on disk.

    ⚠ **AND NO PAYMENT — THAT IS THE WAVE, NOT AN OMISSION.** `BR-INT-058`
    and `CR-069` §20.4 put `record_payment` with channel `KIOSK` on the
    Runbooks side and it is not built. The delivery row IS the deliverable:
    the money is on disk, exactly as the kiosk sent it, waiting for a runbook.
    """
    body = _fixture("payment.json")
    response = _post(brazos, body=body)

    manifest_ok = inbound.status_for(
        inbound.operation_named(services.REGISTRY.require(KIOSK), "payments"), "ok"
    )
    assert response.status_code == manifest_ok, "the number is the manifest's (BR-INT-045)"

    answer = json.loads(_bytes(response))
    assert answer["status"] == "ok"
    assert [one["state"] for one in answer["items"]] == [inbound.ITEM_LANDED]
    assert answer["items"][0]["key"] == f"{EVENT_ID}|payment"

    with tenant_ctx(brazos):
        rows = _deliveries(brazos)
        assert len(rows) == 1
        assert rows[0].provider == KIOSK
        assert rows[0].event_id == f"{EVENT_ID}|payment"
        # PERSIST **RAW** — what arrived, not what we understood of it. The
        # risk flag OQ-INT-1486 rules on rides here untouched, which is the
        # half of that ruling that IS ours (the clerk-visible half needs a
        # payment and there is none).
        assert rows[0].body == body
        assert rows[0].body["riskFlag"] == "review"
        # A payment is ALWAYS accepted (BR-PAY-036): a risk flag stops nothing.
        assert rows[0].status == "received"

        runs = list(models.IntegrationRun.objects.filter(direction=models.RUN_DIRECTION_INBOUND))
        assert len(runs) == 1, "one delivery is one inbound run row (BR-INT-035)"
        assert runs[0].operation == "payments"
        assert runs[0].succeeded == 1 and runs[0].skipped == 0
        # *who* is the HINT and never the key.
        assert KIOSK_HINT in runs[0].summary
        assert KIOSK_KEY not in (runs[0].summary or "")


def test_tc1b_every_landing_writes_an_audit_row(brazos, dana, kiosk, audit_rows):
    """CLAUDE.md hard rule 7 — money arriving with no record of how is the
    outcome rule 7 exists to prevent. There is no user behind a kiosk, so the
    JOB is named instead (`BR-AUD-003`).

    ⚠ ASSERTED THROUGH `audit_rows`, THE SUITE'S OWN CAPTURE SINK, AND NOT BY
    QUERYING `audit_log`. `test_us_met_helpers` installs that sink `autouse`,
    so in this suite the rows never reach the table — a first draft that
    counted table rows found ZERO and would have read as *"the door writes no
    audit row"*, which is the opposite of the truth. The capture list is what
    every other module's rule-7 case asserts against, for the same reason.
    """
    before = [one for one in audit_rows if one["entity_type"] == "payment_webhook_event"]
    _post(brazos, body=_fixture("payment.json"))
    rows = [one for one in audit_rows if one["entity_type"] == "payment_webhook_event"]
    assert len(rows) == len(before) + 1
    assert rows[-1]["action"] == "payment.webhook_received"
    assert rows[-1]["actor_user_id"] is None, "there is no user behind a kiosk (BR-AUD-003)"
    assert rows[-1]["after"]["job"] == "integrations.inbound_door"
    assert rows[-1]["after"]["operation"] == "payments"
    assert KIOSK_KEY not in json.dumps(rows[-1]["after"]), "no key in an audit payload"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · the same notification, replayed
# ══════════════════════════════════════════════════════════════════════════


def test_tc2_the_replay_is_answered_duplicate_and_writes_nothing(brazos, dana, kiosk):
    """The kiosk replays `K-88231` → the manifest's `duplicate`, one row.

    ⚠ **THE NUMBER IS READ OFF THE MANIFEST AND COMPARED WITH THE STORY'S
    FIGURE IN THE SAME ASSERTION.** `US-INT-044` TC-2 says `409`; the manifest
    declares it; the door contains neither. If either moves without the other,
    this goes red and names both.
    """
    body = _fixture("payment.json")
    first = _post(brazos, body=body)
    second = _post(brazos, body=body)

    operation = inbound.operation_named(services.REGISTRY.require(KIOSK), "payments")
    assert inbound.status_for(operation, "duplicate") == 409, "US-INT-044 TC-2's own figure"
    assert first.status_code == 200
    assert second.status_code == inbound.status_for(operation, "duplicate")

    answer = json.loads(_bytes(second))
    assert answer["status"] == "duplicate"
    assert [one["state"] for one in answer["items"]] == [inbound.ITEM_DUPLICATE]

    with tenant_ctx(brazos):
        assert len(_deliveries(brazos)) == 1, "exactly one delivery row (hard rule 6)"


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · THE EXIT TEST — a return carrying the same id
# ══════════════════════════════════════════════════════════════════════════


def test_tc3_a_return_carrying_the_same_id_is_not_a_duplicate(brazos, dana, kiosk):
    """`CR-069` §12's phase-5 exit test, on the real captured payloads.

    A return carries the SAME provider id as the payment it reverses. Keyed on
    that id alone, EVERY return in the product's life would be refused as a
    duplicate of its own payment — silently, with a `409` the kiosk would read
    as *"we already have your return"*. The composite key
    (`BR-INT-020` D) is the whole of the fix and this asserts both halves: the
    return LANDS, and the two keys differ by exactly the marker.
    """
    payment = _fixture("payment.json")
    reversal = _fixture("return.json")
    assert payment["eventId"] == reversal["eventId"] == EVENT_ID, (
        "the premise of this test: the vendor reuses the id"
    )

    assert _post(brazos, body=payment).status_code == 200
    answer = _post(brazos, operation="returns", body=reversal)
    assert answer.status_code == 200, "a return is NOT a duplicate of its own payment"
    assert json.loads(_bytes(answer))["status"] == "ok"

    with tenant_ctx(brazos):
        keys = [one.event_id for one in _deliveries(brazos)]
    assert keys == [f"{EVENT_ID}|payment", f"{EVENT_ID}|return"]
    # And the marker is derived from the DECLARED natural key, never the name.
    manifest = services.REGISTRY.require(KIOSK)
    assert inbound.reversal_marker(inbound.operation_named(manifest, "returns")) == "return"
    assert inbound.reversal_marker(inbound.operation_named(manifest, "payments")) == "payment"


def test_tc3b_replaying_the_return_is_a_duplicate_of_the_return(brazos, dana, kiosk):
    """The other half: the composite key still DEDUPES. A key that separated
    everything would be no key at all."""
    _post(brazos, body=_fixture("payment.json"))
    _post(brazos, operation="returns", body=_fixture("return.json"))
    again = _post(brazos, operation="returns", body=_fixture("return.json"))
    assert again.status_code == 409
    with tenant_ctx(brazos):
        assert len(_deliveries(brazos)) == 2


# ══════════════════════════════════════════════════════════════════════════
# TC-4 / TC-5 · the two refusals, and the body that is never read
# ══════════════════════════════════════════════════════════════════════════


def test_tc4_a_call_from_outside_the_allowlist_is_refused_before_the_body_is_read(
    brazos, dana, kiosk, monkeypatch
):
    """`203.0.113.99` → refused, and the body is NEVER PARSED.

    ⚠ **THE FIRST DRAFT OF THIS TEST COULD NOT FAIL, AND THE SABOTAGE IS WHAT
    FOUND IT (CLAUDE.md law 7).** It handed in truncated JSON and reasoned
    that *"if anything parsed it the answer would be a 400 or a 500"*. It
    would not: `inbound._parsed` swallows a bad body and answers `{}` ON
    PURPOSE, because an authenticated caller sending nonsense must still get a
    recorded refusal rather than a 500 it will retry for ever. So moving the
    parse to the very top of `receive()` — the exact violation of
    `BR-INT-021` this case exists to catch — changed **nothing observable**,
    and the test passed over it.

    **The claim is about ORDER, so the assertion has to be about order.** The
    parser is replaced with one that records every call; the refusal is
    triggered; and the recording must be EMPTY. That is falsifiable, and the
    sabotage now fails here by name.
    """
    junk = b'{"eventId": "K-88231", '  # deliberately truncated — invalid JSON

    read_attempts: list[bytes] = []
    real_parsed = inbound._parsed
    monkeypatch.setattr(
        inbound,
        "_parsed",
        lambda raw: (read_attempts.append(raw), real_parsed(raw))[1],
    )

    refused = _post(brazos, raw=junk, address=BLOCKED_ADDRESS)

    assert read_attempts == [], (
        "the body was read before the caller was authenticated — BR-INT-021. An "
        "unauthenticated caller must not be able to make us parse arbitrary input."
    )
    assert refused.status_code == 401
    assert json.loads(_bytes(refused)) == {"error": serve.REFUSAL_SENTENCE}
    with tenant_ctx(brazos):
        assert _deliveries(brazos) == []
        # ⚠ **THIS READ `count() == 0` UNTIL `CR-110-BRC04` WAVE E.** The PO
        # ruled on 2026-09-16 that every refusal carries a code and that the six
        # auth causes are told apart in OUR record, so this door now writes ONE
        # row saying *address not on the allowlist · refused*. The property the
        # case is actually about is unchanged and is now asserted directly:
        # **nobody was let in** — the run attempted nothing and succeeded at
        # nothing, and `never_dialled` makes its outcome `skipped`, which
        # `services.outcome_for` reserves for *we did not ask*.
        row = models.IntegrationRun.objects.get()
        assert (row.attempted, row.succeeded) == (0, 0), "nobody was let in"
        assert serve.CODE_ADDRESS_NOT_ALLOWED in {one["ref"] for one in row.items}


def test_tc4b_an_authenticated_caller_sending_nonsense_is_not_a_500(brazos, dana, kiosk):
    """The other side of the same coin, and the reason TC-4 needed a spy.

    A body that will not parse is still a delivery from a caller we let in, so
    it answers normally with every item named `no_event_id` — never a 500,
    which a kiosk would retry for ever over one malformed notification.
    """
    answer = _post(brazos, raw=b'{"eventId": "K-88231", ')
    assert answer.status_code == 200
    assert [one["state"] for one in json.loads(_bytes(answer))["items"]] == [
        inbound.ITEM_NO_KEY
    ]
    with tenant_ctx(brazos):
        assert _deliveries(brazos) == []


def test_tc5_a_wrong_key_from_an_allowed_address_is_refused_identically(brazos, dana, kiosk):
    """The two refusals are ONE refusal — the same bytes and the same status.

    ⚠ Wave S proves the TIMING half for `resolve_caller` (three refusals
    inside a 40ms floor) and this door uses that same function, so the floor
    is inherited rather than re-asserted. What is asserted here is what this
    wave could break: that the door does not add a distinguishing answer of
    its own on the way back out.
    """
    body = _fixture("payment.json")
    bad_key = _post(brazos, body=body, key="sbh_live_wrong_key_entirely")
    bad_address = _post(brazos, body=body, address=BLOCKED_ADDRESS)
    no_key = _post(brazos, body=body, key=None)
    unknown_operation = _post(brazos, body=body, operation="not_an_operation")

    answers = [bad_key, bad_address, no_key, unknown_operation]
    assert {one.status_code for one in answers} == {401}
    assert len({_bytes(one) for one in answers}) == 1, "one refusal, byte for byte"

    with tenant_ctx(brazos):
        assert _deliveries(brazos) == []


def test_tc5b_an_unknown_provider_answers_the_same_five_words(brazos, dana, kiosk):
    """A caller must not learn which connectors a utility has."""
    refused = _post(brazos, body=_fixture("payment.json"), provider="not_a_provider")
    assert refused.status_code == 401
    assert json.loads(_bytes(refused)) == {"error": serve.REFUSAL_SENTENCE}


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · the load-time refusal
# ══════════════════════════════════════════════════════════════════════════


def _door_manifest(**operation_kwargs) -> Manifest:
    base = dict(
        name="payments",
        label="Payments",
        direction="in",
        initiative="them",
        transport="https",
        trigger="webhook",
        idempotency=Idempotency(mode="refuse", source="provider_event_id", key_field="eventId"),
        completion="immediate",
        # CR-110-BRC04 — every operation names its ceiling or the registry refuses it.
        rate_limit_per_minute=60,
        codec="json",
        respond_after="dedupe",
        envelope_status={"ok": 200, "duplicate": 409, "refused": 401},
    )
    base.update(operation_kwargs)
    return Manifest(
        key="probe_provider",
        category="payments",
        display_name="Probe",
        summary="A manifest built to be refused.",
        disposition=Disposition(kind="live", phase=5),
        auth=Auth(mode="they_hold_ours", placement="header", header="X-Probe-Key"),
        operations=(Operation(**base),),
    )


def test_tc6_a_reply_before_authenticate_is_refused_at_load(brazos):
    """`BR-INT-030` — refused at LOAD, not at run time. A configuration error
    should fail `manage.py check` on a developer's own machine, not the first
    real batch at 06:02 on the first of the month."""
    with pytest.raises(ManifestError) as refusal:
        Registry().register(_door_manifest(respond_after="receive"))
    assert "BR-INT-030" in str(refusal.value)
    assert "receive" in str(refusal.value)


def test_tc6b_a_credential_header_on_a_placement_that_has_none_is_refused_at_load(brazos):
    """The one direction the registry can be sure about — dead data a later
    lane would trust (the same argument `auth.oauth` already makes)."""
    with pytest.raises(ManifestError) as refusal:
        Registry().register(
            Manifest(
                key="probe_provider",
                category="payments",
                display_name="Probe",
                summary="A manifest built to be refused.",
                disposition=Disposition(kind="live", phase=5),
                auth=Auth(mode="they_hold_ours", placement="bearer", header="X-Probe-Key"),
                operations=_door_manifest().operations,
            )
        )
    assert "X-Probe-Key" in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · the account lookup
# ══════════════════════════════════════════════════════════════════════════


def test_tc7_the_account_lookup_answers_at_authenticate_and_not_found_is_200(
    brazos, dana, kiosk
):
    """`US-INT-044` TC-7 — an unknown account answers **200 with a status
    word, NOT a 404**, and that is the kiosk's contract.

    ⚠ **THE MANIFEST SAID 404 UNTIL 2026-09-06 (`DEF-INT-4257`)** and nothing
    could catch it: the registry validates that a status IS an HTTP status and
    can never know which one is right. So the figure is asserted HERE, from
    the story's test table, against the value the manifest declares — if
    either moves the other has to move with it.

    ⚠ **AND THE BALANCE IS NOT BUILT.** Composing *what is owed on ACC-1048*
    is a business record made from our data, which `CR-069` §20.4 and §20.9.4
    put on the Runbooks side — the same line that makes
    `serve.partner_fields()` return `{}`. The caller is admitted, the read is
    recorded, and the answer carries no account.
    """
    operation = inbound.operation_named(services.REGISTRY.require(KIOSK), "account_lookup")
    assert operation.respond_after == "authenticate"
    assert inbound.status_for(operation, "not_found") == 200, (
        "US-INT-044 TC-7: 200 with `status: not_found`, NOT a 404"
    )

    response = _post(brazos, operation="account_lookup", body={"accountNumber": "ACC-1048"})
    assert response.status_code == 200
    answer = json.loads(_bytes(response))
    assert answer["status"] == "ok"
    assert "balance" not in answer and "account" not in answer
    assert any(one["code"] == "answer_is_runbooks" for one in answer["problems"])

    with tenant_ctx(brazos):
        assert _deliveries(brazos) == [], "a lookup writes nothing; it is a read"
        reads = list(
            models.IntegrationRun.objects.filter(direction=models.RUN_DIRECTION_INBOUND_READ)
        )
        assert len(reads) == 1 and reads[0].operation == "account_lookup"


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · the batch, on real PostgreSQL (CLAUDE.md hard-won law 14)
# ══════════════════════════════════════════════════════════════════════════


def test_tc9_a_batch_lands_every_item_and_the_states_say_which(brazos, dana, kiosk):
    """The shape of the batch, on any vendor. TC-9 proper is below."""
    payment = _fixture("payment.json")
    second = dict(payment, eventId="K-88232", amount="18.50")
    answer = _post(brazos, body={"payments": [payment, second]})
    assert answer.status_code == 200
    assert [one["state"] for one in json.loads(_bytes(answer))["items"]] == [
        inbound.ITEM_LANDED,
        inbound.ITEM_LANDED,
    ]
    with tenant_ctx(brazos):
        assert len(_deliveries(brazos)) == 2


def _blind_guard_one_once(monkeypatch):
    """Model the RACE guard 2 exists for, rather than deleting guard 1.

    ⚠ **A FLAT `lambda: None` BLINDS THE RECOVERY LOOKUP TOO, AND THAT IS A
    DIFFERENT TEST FROM THE ONE INTENDED.** `land_delivery` calls
    `_existing_delivery` twice: once BEFORE the insert (the cheap pre-check)
    and once INSIDE `except IntegrityError` to find the row that won the race.
    Patching it to answer `None` unconditionally makes the second call answer
    `None` as well, so the recovery re-raises and the door returns **500** —
    which is what happened on the first run of these two cases, on PostgreSQL,
    and it is a fault in the TEST rather than in the door.

    So the shim answers `None` **the first time it is asked about a given key
    and honestly afterwards**. That is precisely the race: at the moment we
    looked, the row was not there; by the moment we inserted, another delivery
    had committed it; and the recovery then finds it, exactly as it would in
    production.
    """
    from apps.payments import webhooks as payments_webhooks

    real = payments_webhooks._existing_delivery
    asked: set[tuple] = set()

    def once_blind(tenant_id, provider, event_id):
        key = (str(tenant_id), provider, event_id)
        if key not in asked:
            asked.add(key)
            return None
        return real(tenant_id, provider, event_id)

    monkeypatch.setattr(payments_webhooks, "_existing_delivery", once_blind)


@requires_postgres
def test_tc9_pg_one_refused_item_does_not_take_the_batch_with_it(
    brazos, dana, kiosk, monkeypatch
):
    """CLAUDE.md hard-won law 14, and the ONLY place it can be proved.

    ⚠ **GUARD 1 IS SWITCHED OFF HERE ON PURPOSE, AND THE FIRST DRAFT OF THIS
    TEST WAS WORTHLESS WITHOUT IT.** `land_delivery` looks the key up before
    it inserts, so on the ordinary path a duplicate is recognised by a SELECT
    and the INSERT never happens — which means **no `IntegrityError` is ever
    raised and the savepoint is never exercised.** The first draft of this
    case did exactly that, and when the savepoint was deliberately removed to
    prove it RED, it **passed on PostgreSQL**: law 7's *structurally incapable
    of failing*, inside the test written to guard the law that warns about it.

    Blinding guard 1 is not a contrivance — it is the case guard 2 exists for:
    the race between two concurrent deliveries of the same event, where the
    SELECT sees nothing and the unique index refuses the INSERT. `DEF-058` is
    why this codebase keeps the two guards independent and tests each with the
    other disabled, and this is that discipline applied here.

    So: item 1 is new, item 2's SELECT is blinded, and its INSERT is refused
    by `uq_payment_webhook_events_event`. **Without the SAVEPOINT, PostgreSQL
    aborts the whole transaction on that refusal** — every later statement
    raises `InFailedSqlTransaction` and item 1, a real payment, is gone at
    COMMIT. **PROVED RED on PostgreSQL 16.13 with the savepoint removed, and
    this is the failure verbatim rather than the one law 14 quotes** — the
    driver's `InFailedSqlTransaction` is what the SERVER says, and what a
    Django caller actually meets is the wrapper raised before the next query
    is even sent:

        django.db.transaction.TransactionManagementError: An error occurred in
        the current transaction. You can't execute queries until the end of
        the 'atomic' block.

    Two failures and two teardown errors, in 4.75 seconds. Green with the
    savepoint back. **On SQLite the same removal passes**, which is the whole
    reason law 14 is a law.
    """
    already = _fixture("payment.json")
    _post(brazos, body=already)  # item 2's twin, landed first
    fresh = dict(already, eventId="K-88240", amount="7.25")

    # GUARD 1 BLINDED FOR ONE LOOK PER KEY — see `_blind_guard_one_once`. The
    # unique index is then the only thing left between a retry and a second
    # row, and the recovery lookup still works, which is the race as it really
    # happens.
    _blind_guard_one_once(monkeypatch)

    answer = _post(brazos, body={"payments": [fresh, already]})
    assert answer.status_code == 200, "one item was new, so the batch is not a duplicate"
    assert [one["state"] for one in json.loads(_bytes(answer))["items"]] == [
        inbound.ITEM_LANDED,
        inbound.ITEM_DUPLICATE,
    ], "the second item was refused BY THE INDEX, not by the lookup"

    with tenant_ctx(brazos):
        keys = {one.event_id for one in _deliveries(brazos)}
    assert keys == {f"{EVENT_ID}|payment", "K-88240|payment"}, (
        "the first item COMMITTED — that is the savepoint, and without it this set is short"
    )


@requires_postgres
def test_tc9_pg_guard_two_alone_still_refuses_a_second_row(brazos, dana, kiosk, monkeypatch):
    """The other half of `DEF-058`'s discipline: with the SELECT blinded, the
    same notification twice still produces ONE row.

    Guard 1 makes a replay CHEAP; guard 2 makes it CORRECT. A suite that only
    ever exercised the cheap one would pass over a product whose unique index
    had been dropped.
    """
    payment = _fixture("payment.json")
    _post(brazos, body=payment)
    _blind_guard_one_once(monkeypatch)
    assert _post(brazos, body=payment).status_code == 409
    with tenant_ctx(brazos):
        assert len(_deliveries(brazos)) == 1, "the index held the line on its own"


def test_tc9b_a_batch_of_only_duplicates_answers_duplicate(brazos, dana, kiosk):
    """`409` means *stop re-sending*. A mixed batch must NOT get it — one item
    was new and telling the kiosk to stop re-sending it would lose money."""
    payment = _fixture("payment.json")
    _post(brazos, body=payment)
    assert _post(brazos, body={"payments": [payment]}).status_code == 409
    assert _post(brazos, body={"payments": [payment, dict(payment, eventId="K-99999")]}).status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# TC-10 · tenant isolation
# ══════════════════════════════════════════════════════════════════════════


def test_tc10_a_key_issued_by_one_utility_is_refused_at_another(brazos, lonestar, dana, kiosk):
    """CLAUDE.md hard rule 1, and it is a property of the DATABASE.

    Under Lone Star Ridge's `app.tenant_id`, Brazos Bend's credential row is
    not visible, so the blind-index lookup finds nothing and falls into the
    same one refusal as a key that never existed. There is no line here that
    could be deleted to break it — which is exactly why the address carries
    the utility.
    """
    refused = _post(lonestar, body=_fixture("payment.json"))
    assert refused.status_code == 401
    assert json.loads(_bytes(refused)) == {"error": serve.REFUSAL_SENTENCE}
    with tenant_ctx(lonestar):
        assert _deliveries(lonestar) == []
    with tenant_ctx(brazos):
        assert _deliveries(brazos) == [], "and nothing landed in the key's own utility either"


# ══════════════════════════════════════════════════════════════════════════
# The boundary — BR-INT-058. The assertion is an ABSENCE.
# ══════════════════════════════════════════════════════════════════════════


def test_tc_boundary_the_door_applies_nothing(brazos, dana, kiosk):
    """`BR-INT-058` — the door lands it and STOPS. No payment. No reversal.

    ⚠ **THIS TEST GOES RED THE DAY RUNBOOKS LANDS, AND THAT IS ITS JOB.** A
    boundary written only in prose is a boundary the next lane closes without
    noticing; this one names `runbooks_apply` and asserts the two things that
    would change. When the apply half is built, come here first — the ruling
    to check is `OQ-INT-1729` (a), 2026-09-06.
    """
    _post(brazos, body=_fixture("payment.json"))
    _post(brazos, operation="returns", body=_fixture("return.json"))

    with tenant_ctx(brazos):
        assert _payment_count(brazos) == 0, (
            "record_payment with channel KIOSK is Runbooks' (CR-069 §20.4 wave N)"
        )
        rows = _deliveries(brazos)
        assert len(rows) == 2
        assert all(one.payment_id is None for one in rows)
        assert all(one.processed_at is None for one in rows)

    assert inbound.runbooks_apply(
        inbound.InboundReply(provider_key=KIOSK, operation="payments", outcome="ok", status=200)
    ) is None


def test_tc_boundary_the_raw_flag_is_kept_and_nothing_is_decided_about_it(brazos, dana, kiosk):
    """`OQ-INT-1486` was ruled option (a) on 2026-09-04 — accept, and show the
    flag on the payment for a clerk. **The showing needs a payment**, so the
    half that is ours is that the flag arrives intact and provokes nothing:
    no hold, no notification, and the delivery accepted like any other."""
    body = _fixture("payment.json")
    assert body["riskFlag"] == "review"
    assert _post(brazos, body=body).status_code == 200
    with tenant_ctx(brazos):
        row = _deliveries(brazos)[0]
        assert row.body["riskFlag"] == "review"
        assert row.status == "received", "a payment is ALWAYS accepted (BR-PAY-036)"


# ══════════════════════════════════════════════════════════════════════════
# Fail closed — the three things a manifest can leave out
# ══════════════════════════════════════════════════════════════════════════


def test_a_header_placement_with_no_header_name_refuses_rather_than_guessing(brazos):
    """Hard-won law 3 — the unsafe option must be the one you type.

    A door that fell back to a guess would authenticate against the wrong
    header the day a provider changed it, and the symptom (every valid key
    refused) is indistinguishable from a wrong key.
    """
    nameless = Manifest(
        key="probe_provider",
        category="payments",
        display_name="Probe",
        summary="Places a credential in a header and names none.",
        disposition=Disposition(kind="live", phase=5),
        auth=Auth(mode="they_hold_ours", placement="header"),
        operations=_door_manifest().operations,
    )
    with pytest.raises(inbound.DoorMisconfigured) as refusal:
        inbound.credential_header(nameless)
    assert "probe_provider" in str(refusal.value)
    assert "header" in str(refusal.value)


def test_an_operation_that_must_dedupe_and_names_no_key_field_refuses(brazos):
    """The one that would let a replayed payment through.

    Reading *"I could not find an id"* as *"this is new"* is how hard rule 6
    breaks silently, so the absence of a declared field is a refusal rather
    than a default.
    """
    keyless = _door_manifest(
        idempotency=Idempotency(mode="refuse", source="provider_event_id")
    ).operations[0]
    with pytest.raises(inbound.DoorMisconfigured) as refusal:
        inbound.event_id_of(keyless, {"eventId": EVENT_ID})
    assert "key_field" in str(refusal.value)


def test_a_notification_with_no_id_is_recorded_refused_and_the_batch_carries_on(
    brazos, dana, kiosk
):
    """A bad NOTIFICATION is not a bad manifest. It is refused by name, it
    lands nothing, and the items beside it still land — which is the same
    per-item discipline the savepoint exists for."""
    good = _fixture("payment.json")
    nameless = {k: v for k, v in good.items() if k != "eventId"}
    answer = _post(brazos, body={"payments": [nameless, good]})
    assert answer.status_code == 200
    assert [one["state"] for one in json.loads(_bytes(answer))["items"]] == [
        inbound.ITEM_NO_KEY,
        inbound.ITEM_LANDED,
    ]
    with tenant_ctx(brazos):
        assert len(_deliveries(brazos)) == 1
        run = models.IntegrationRun.objects.filter(
            direction=models.RUN_DIRECTION_INBOUND
        ).first()
        assert run.failed == 1 and run.succeeded == 1


def test_the_door_contains_no_status_number(brazos):
    """`BR-INT-045` — grep the module, not the behaviour.

    ⚠ A BEHAVIOURAL TEST CANNOT PROVE THIS. Asserting that a 409 comes back
    proves the number is *somewhere*; the rule is that it is in the MANIFEST
    and not in the door. So this reads the source, which is the only thing
    that can distinguish the two — and it is the same check `partner_api`
    passes by asking the registry for its refusal number.
    """
    import ast
    import io
    import re
    import tokenize
    from pathlib import Path

    source = Path(inbound.__file__).read_text()

    # ⚠ **THE FIRST DRAFT OF THIS CHECK STRIPPED ONLY THE MODULE DOCSTRING AND
    # WENT RED ON ITS OWN PROSE** — `['200', '404', '409', '500']`, every one of
    # them inside a docstring EXPLAINING the rule. That is the DEF-043 shape
    # this repo already knows (G6 once fired on a docstring describing G6), and
    # the naive repair — widen the regex, or drop the assertion — would have
    # produced a check that cannot fail. So the stripping is done properly:
    # `tokenize` removes comments, and `ast` removes every docstring rather
    # than the first one.
    without_comments = tokenize.untokenize(
        token
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type != tokenize.COMMENT
    )
    tree = ast.parse(without_comments)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body[0].value.value = ""
    code = ast.unparse(tree)

    # The comment-and-docstring strip is the thing that could make this check
    # pass wrongly, so prove it still SEES a number before trusting the zero.
    assert re.search(r"\b409\b", ast.unparse(ast.parse("x = 409"))), "the strip ate everything"

    numbers = set(re.findall(r"\b(200|201|401|404|409|422|500)\b", code))
    assert numbers == set(), f"the door types a status number: {sorted(numbers)}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-044@wave-N (EP-INT-13) · CR-069 §12 phase-5 exit test · BR-INT-058
# generated: 2026-09-06 by the CR-069 wave N build lane (the door half)
# checklist: A✔ B✔ C✔ D✔ E=n/a(no screen) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_044_inbound_door.py · TC-9 needs PostgreSQL and SKIPS loudly elsewhere
# exceptions: TC-8 (DRIVEUP → OTHER) and TC-11 (the report by channel) are NOT here — both display or decide facts only `record_payment` writes, and CR-069 §20.4 moved that to Runbooks; §4's five accounts belong to the same half and are not seeded
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

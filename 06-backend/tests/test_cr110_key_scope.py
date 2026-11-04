# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — migration 2 of 2, "a key names the APIs it
#           may call". Blueprint p017, `CR-4`, *SECURITY SHAPE · RULED: SCOPE
#           IT*. PO 2026-09-16: *"we ahve to build it"*.
# Rules:    BR-INT-053 · BR-INT-044 (the refusal reveals nothing — a scope
#           refusal must be the SAME refusal) · CLAUDE.md hard-won law 3 (a
#           blank scope grants nothing) · B14 rule 33
# Impacts:  apps/integrations/machine_auth.py · runners/serve.py · inbound.py
# ───────────────────────────────────────────────────────
"""A key that may push meter readings may no longer read everything else.

⚠ **THE CASE THIS FILE EXISTS FOR IS
`test_a_scope_refusal_is_the_same_refusal_as_a_wrong_key`.** Adding a fourth
guard to a door whose whole design is *three refusals are one refusal* is the
easiest place in this product to open an oracle. If a key that is real but
wrongly scoped answered faster, or differently, than a key that never existed,
a caller holding a stolen key would learn from the difference that the key is
genuine and go looking for the operation it does open. So the scope check is
inside `resolve_caller`'s single boolean, and this file compares the bodies
byte-for-byte, the statuses, and the elapsed times against the floor.

⚠ **AND `test_a_key_with_nothing_ticked_cannot_be_issued` IS WHERE THE DRAWING
IS DELIBERATELY DISOBEYED.** The wireframe says *"Leave blank for everything
the key allows"*. That is the widest permission as a default and it is refused
(hard-won law 3). B14 rule 37 covers the rest of that page — a figure drawn in
a wireframe is an illustration — but this is not a figure, it is a behaviour,
and it is overridden by a signed rule rather than ignored.
"""

from __future__ import annotations

import time

import pytest

from apps.integrations import machine_auth, models, services
from apps.integrations.runners import serve
from core import crypto, errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

#: ⚠ **`gl_partner` UNTIL THIS CR'S OWN WAVE C SPLIT IT INTO FIVE NAMED ERPs.**
#: The scope is a property of the RELATIONSHIP, not of this vendor, so any
#: `they_hold_ours` manifest would do; Aclarian is used because it is the one
#: `US-INT-041`'s own cases were written around.
PARTNER = "erp_aclarian"
KEY = "sbh_live_7Q2F_brazosbend_do_not_reuse"
HINT = "••••7Q2F"
ADDRESS = "198.51.100.12"


def _connection(tenant):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=PARTNER,
        label="Aclarian",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={"client_id": "aclarian"},
    )


def _credential(actor, connection, scope, key=KEY, hint=HINT):
    return services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=scope,
    )


# ══════════════════════════════════════════════════════════════════════════
# The mint — what may be issued at all
# ══════════════════════════════════════════════════════════════════════════


def _operation_count(provider="erp_aclarian") -> int:
    """How many reads this connector offers — the denominator in *for 2 of 4*.

    Read from the registry rather than typed, because it moved on 2026-09-16
    (`CR-110-BRC04` phase 2, `serve_ledger`) and a literal in a test is a copy
    of a fact that has no reason to stay right.
    """
    from apps.integrations.registry import REGISTRY

    return len(REGISTRY.require(provider).operations)


@pytest.mark.django_db
def test_a_key_with_nothing_ticked_cannot_be_issued(brazos, dana):
    """⚠ THE DRAWING SAYS BLANK MEANS EVERYTHING. It does not — it is refused,
    and a clerk is told rather than handed a key that authorises nothing (which
    reads the same on a screen and is discovered by the partner at go-live)."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        for nothing in ([], (), None, ""):
            with pytest.raises(errors.ValidationError) as raised:
                machine_auth.issue_key(actor=dana, connection=connection, scope=nothing)
            assert raised.value.message_key == machine_auth.REFUSAL_NO_SCOPE
        assert models.IntegrationCredential.objects.filter(connection=connection).count() == 0


@pytest.mark.django_db
def test_a_scope_naming_something_this_connector_does_not_do_is_refused(brazos, dana):
    """Refused rather than silently dropped. Discarding `read_paymets` would
    mint a key authorising less than the screen said, and nobody would be
    told."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        with pytest.raises(errors.ValidationError) as raised:
            machine_auth.issue_key(
                actor=dana, connection=connection, scope=["serve_payment", "serve_paymnet"]
            )
        assert raised.value.message_key == machine_auth.REFUSAL_UNKNOWN_SCOPE
        assert models.IntegrationCredential.objects.filter(connection=connection).count() == 0


@pytest.mark.django_db
def test_an_issued_key_stores_what_it_may_call_and_the_audit_row_says_so(
    brazos, dana, audit_rows
):
    """Hard rule 7 — and the SCOPE is the part an auditor is actually asking
    about. `BR-INT-003` keeps the KEY out of the payload; the permissions
    granted with it are the reason the row exists at all."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        row, minted = machine_auth.issue_key(
            actor=dana, connection=connection, scope=["serve_payment", "serve_bill"]
        )
        assert minted.startswith("sbh_live_")
        # SORTED and de-duplicated, so two keys granting the same operations
        # store the same list and a reviewer reads a difference, not an order.
        assert row.scope == ["serve_bill", "serve_payment"]

    issued = [one for one in audit_rows if one["action"] == machine_auth.AUDIT_KEY_ISSUED]
    assert len(issued) == 1, "one act, one row (record_credential's is suppressed)"
    assert issued[0]["after"]["scope"] == ["serve_bill", "serve_payment"]
    # ⚠ *of 4* SINCE `CR-110-BRC04` PHASE 2 — the connector grew `serve_ledger`
    # and the denominator is HOW MANY THIS CONNECTOR OFFERS, which is the whole
    # point of the sentence: *for 2 of 4* tells an auditor the key was narrowed.
    # Derived rather than retyped, so a fifth operation moves it by itself.
    assert f"2 of {_operation_count()}" in issued[0]["after"]["summary"]
    # The key itself is in NO audit payload (BR-INT-003).
    assert minted not in repr(audit_rows)


@pytest.mark.django_db
def test_replacing_a_key_records_both_reaches_side_by_side(brazos, dana, audit_rows):
    """An auditor reading a replacement needs to see what CHANGED. Both sides
    carry their scope, so narrowing a partner's reach is visible as an act."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        machine_auth.issue_key(
            actor=dana,
            connection=connection,
            scope=["serve_payment", "serve_bill", "serve_customer"],
        )
        machine_auth.issue_key(actor=dana, connection=connection, scope=["serve_payment"])

    replaced = [one for one in audit_rows if one["action"] == machine_auth.AUDIT_KEY_REPLACED]
    assert len(replaced) == 1
    assert replaced[0]["before"]["scope"] == [
        "serve_bill",
        "serve_customer",
        "serve_payment",
    ]
    assert replaced[0]["after"]["scope"] == ["serve_payment"]
    assert f"1 of {_operation_count()}" in replaced[0]["after"]["summary"]


@pytest.mark.django_db
def test_a_replacement_key_does_not_inherit_the_old_ones_reach(brazos, dana):
    """Replacing a key is the moment a partner's reach is meant to be
    reconsidered — which is why the scope is on the CREDENTIAL and not on the
    connection. v(1) may read everything; v(2) may read one thing."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        machine_auth.issue_key(
            actor=dana,
            connection=connection,
            scope=["serve_payment", "serve_bill", "serve_customer"],
        )
        second, _ = machine_auth.issue_key(
            actor=dana, connection=connection, scope=["serve_payment"]
        )
        assert second.version == 2
        assert second.scope == ["serve_payment"]


@pytest.mark.django_db
def test_only_operations_a_partner_can_actually_call_may_be_named(brazos):
    """`they_call_us` and nothing else. An operation WE start against somebody
    else's API is not something a partner's key can name, so offering it would
    be a permission that cannot be exercised — and one a reviewer would read as
    though it could."""
    from apps.integrations.registry import REGISTRY

    for key in ("erp_aclarian", "payments_kiosk"):
        manifest = REGISTRY.require(key)
        offered = machine_auth.callable_operations(manifest)
        assert offered
        assert set(offered) == {one.name for one in manifest.operations if one.they_call_us}


# ══════════════════════════════════════════════════════════════════════════
# The door — where it bites
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_door_serves_an_operation_inside_the_scope(brazos, dana):
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        _credential(dana, connection, ["serve_payment"])
        caller = serve.resolve_caller(
            provider_key=PARTNER,
            presented_key=KEY,
            source_address=ADDRESS,
            operation="serve_payment",
        )
        assert caller.hint == HINT
        assert caller.scopes == ("serve_payment",)


@pytest.mark.django_db
def test_the_door_refuses_an_operation_outside_the_scope(brazos, dana):
    """The defect the blueprint named, closed: a key issued for payments can no
    longer read the bills or the customer list on the same connector."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        _credential(dana, connection, ["serve_payment"])
        for forbidden in ("serve_bill", "serve_customer"):
            with pytest.raises(serve.PartnerRefused):
                serve.resolve_caller(
                    provider_key=PARTNER,
                    presented_key=KEY,
                    source_address=ADDRESS,
                    operation=forbidden,
                )


@pytest.mark.django_db
def test_a_blank_scope_on_a_row_grants_nothing_not_everything(brazos, dana):
    """The mint refuses an empty scope, so a row like this should not exist —
    and if one ever arrives by another road it is POWERLESS rather than
    omnipotent. Two guards pointing the same way, and this is the second."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        _credential(dana, connection, [])
        for operation in ("serve_payment", "serve_bill", None):
            with pytest.raises(serve.PartnerRefused):
                serve.resolve_caller(
                    provider_key=PARTNER,
                    presented_key=KEY,
                    source_address=ADDRESS,
                    operation=operation,
                )


@pytest.mark.django_db
def test_a_malformed_scope_grants_nothing(brazos, dana):
    """A number, a string or a dict in the column must not widen the key.
    Anything that is not a list of non-empty strings reads as `()` — so a
    value nobody intended grants nothing rather than everything."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        row = _credential(dana, connection, ["serve_payment"])
        for rubbish in (7, "serve_payment", {"serve_payment": True}, [""], [None]):
            models.IntegrationCredential.objects.filter(pk=row.pk).update(scope=rubbish)
            row.refresh_from_db()
            assert serve._scopes(row) == (), rubbish


@pytest.mark.django_db
def test_the_column_will_not_hold_a_null_at_all(brazos, dana):
    """⚠ THERE IS NO THIRD STATE. A NULL would sit between *nothing* and
    *something*, every reader would have to decide what it meant, and one of
    them would eventually decide it meant everything. The column is NOT NULL
    with a default of `[]`, so the database refuses the question."""
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        connection = _connection(brazos)
        row = _credential(dana, connection, ["serve_payment"])
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.IntegrationCredential.objects.filter(pk=row.pk).update(scope=None)


@pytest.mark.django_db
def test_a_scope_refusal_is_the_same_refusal_as_a_wrong_key(brazos, dana):
    """⚠ **THE CASE THIS FILE EXISTS FOR.** A fourth guard on a door designed
    around *three refusals are one refusal* is the easiest place here to open
    an oracle.

    Three claims, three assertions, because "indistinguishable" is not one
    thing: the same EXCEPTION, the same WORDS, and the same TIME. A scope
    refusal that returned in two milliseconds while an unknown key took forty
    would tell a caller holding a stolen key that the key is real.
    """
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        _credential(dana, connection, ["serve_payment"])

        def _timed(presented, operation):
            started = time.monotonic()
            try:
                serve.resolve_caller(
                    provider_key=PARTNER,
                    presented_key=presented,
                    source_address=ADDRESS,
                    operation=operation,
                )
            except serve.PartnerRefused as refused:
                return time.monotonic() - started, type(refused), str(refused)
            raise AssertionError("expected a refusal")  # pragma: no cover

        wrong_key = _timed("sbh_live_not_a_real_key_at_all", "serve_payment")
        wrong_scope = _timed(KEY, "serve_customer")

        assert wrong_key[1] is wrong_scope[1]
        assert wrong_key[2] == wrong_scope[2] == serve.REFUSAL_SENTENCE
        for elapsed, _, _ in (wrong_key, wrong_scope):
            assert elapsed >= serve.REFUSAL_FLOOR_S, elapsed


@pytest.mark.django_db
def test_the_specification_needs_a_key_that_may_call_something(brazos, dana):
    """`operation=None` is *this is not an operation call* — the published
    specification. The scope guard still applies: a key that may call nothing
    may not read the description of what it may call."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        _credential(dana, connection, ["serve_payment"])
        caller = serve.resolve_caller(
            provider_key=PARTNER, presented_key=KEY, source_address=ADDRESS, operation=None
        )
        assert caller.scopes == ("serve_payment",)


def test_every_door_must_name_an_operation():
    """⚠ A DOOR ADDED LATER CANNOT INHERIT THIS CHECK BY FORGETTING IT. Both
    `resolve_caller` and `check_rate_limit` take `operation` as a REQUIRED
    keyword with no default, so a new call site has to decide. This case is
    what goes red the day somebody gives either of them a default 'to keep the
    old call sites working'."""
    import inspect

    for function in (serve.resolve_caller, serve.check_rate_limit):
        parameter = inspect.signature(function).parameters["operation"]
        assert parameter.default is inspect.Parameter.empty, function.__name__
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, function.__name__

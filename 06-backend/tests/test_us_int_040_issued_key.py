# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-040 (EP-INT-11) TC-1..7 — *"a credential we issue, scoped to
#         one tenant, shown once and never again"*. Screens: S144 · S141
#         (frame 50.1)
# Rules:  BR-INT-053 (scoped to one tenant · shown once · only replaced ·
#         revocation refuses the VERY NEXT call) · BR-INT-003 (never rendered
#         back, logged or audited — the hint only) · BR-INT-043 (`issued_secret`
#         is a declared field kind) · BR-INT-025 (versioned, never updated) ·
#         CLAUDE.md hard rule 1 (one tenant's partner may not reach another's
#         data) · hard rule 7 (mint and revoke each write audit_log)
# Tests:  ⚠ TC-2, TC-3, TC-4 and TC-5 GO THROUGH WAVE S'S REAL PARTNER ROUTE
#         (`GET /api/{utility}/partner/v1/payments`), not through a helper of this
#         wave's. A key that mints beautifully and is not recognised at the
#         door is a key that does not work, and the two halves were built by
#         two lanes in two worktrees on the same afternoon — so the only proof
#         worth having is the round trip. It also covers `DEF-INT-4216`: wave
#         S's own three-refusal proof is cited in its docstring and is not in
#         the repository, so the comparison is made here.
# ───────────────────────────────────────────────────────
"""The key we issue: minted once, revoked on the spot, and three refusals that read alike.

⚠ **NOT ONE TEST IN THIS FILE PRINTS OR ASSERTS THE KEY AGAINST A FIXED
VALUE, AND THAT IS THE POINT RATHER THAN AN INCONVENIENCE.** The key is
minted by `secrets.token_hex`, so it is different on every run, and the only
copy that ever exists is the return value of one call. A test that pinned it
would need it stored somewhere, and storing it is the thing this wave exists
not to do. What the tests assert instead is the SHAPE (`sbh_live_` + 32 hex),
the CONSEQUENCE (this exact string authenticates, and after a revoke it does
not), and the ABSENCE (it is in no audit row, no log line, no API response
but the one that minted it).

THE THREE PROPERTIES, AND WHICH TEST IS EACH ONE'S PROOF
---------------------------------------------------------
1 · **shown once** — `test_tc1_…` (one body carries it, the card never does)
    and `test_tc7_…` (audit, logs and every read path swept for the plaintext).
2 · **revocation refuses the very next call** — `test_tc3_…`, which
    authenticates, revokes and authenticates again IN ONE PROCESS with no
    restart, no sleep and no cache flush between them.
3 · **the refusal reveals nothing** — `test_the_three_refusals_are_one_answer`,
    which puts a wrong key, a revoked key and an unknown key through the real
    route and compares the **status, the body bytes and the elapsed time**.
    Comparing only the body would pass over a version that returns identical
    text after doing visibly different work, and the timing is the half an
    attacker actually reads.

⚠ **THE MINT AND THE DOOR ARE TWO FILES BY TWO LANES AND ONE STRING JOINS
THEM.** `machine_auth.crypto_context()` imports
`serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`; if those ever differed, every valid key
would be refused and would look exactly like a wrong key — silently, in both
directions. `test_the_mint_and_the_door_share_one_context` asserts the identity
directly, and every round trip below would fail with it.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import time

import pytest

from apps.integrations import machine_auth, models, services
from apps.integrations.runners import serve
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import call, card, grid, post_connect
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · audit_rows

#: ⚠ `gl_partner` until `CR-110-BRC04`, when the one generic finance card
#: became five named ERPs. The issued-key relationship is unchanged.
PARTNER = "erp_workday"
#: ⚠ **`client_id` AND `scopes` WERE REMOVED FROM ALL FIVE ERP MANIFESTS ON
#: 2026-09-16** (`DEF-INT-5534`, PO ruling) and the server refuses an undeclared
#: field BY NAME — `integrations.field.unknown` — which is how this fixture told
#: us, with a `422` on eleven cases at once. That refusal is the manifest being
#: the single source of truth working exactly as intended, so the fixture moves
#: and the rule does not. `client_id` was read by nothing; `scopes` moved onto
#: the API rows as a per-operation switch and is now the KEY's scope.
PARTNER_FIELDS = {
    "allowed_addresses": "198.51.100.0/24, 203.0.113.7",
}

#: `sbh_live_` + 32 lowercase hex. Asserted as a SHAPE because the value is
#: different every run and is stored nowhere to compare against.
KEY_SHAPE = re.compile(r"^sbh_live_[0-9a-f]{32}$")

#: A key of the right shape that was never issued. Used as the control in the
#: three-refusal comparison: it is the case with nothing behind it at all.
UNKNOWN_KEY = "sbh_live_" + "0" * 32
WRONG_KEY = "sbh_live_" + "f" * 32


def partner_call(tenant, presented, *, what="payments"):
    """One partner request at the REAL address, exactly as a finance system
    makes it: no session, no cookie, `Authorization: Bearer <key>`, and the
    utility's own slug as the first path segment (wave S's ruling — the tenant
    is the path, so RLS is the thing that keeps two utilities apart).

    Returns `(status, body bytes, elapsed seconds)`. The third is not decoration:
    two refusals that read alike and arrive at visibly different speeds are two
    distinguishable refusals.
    """
    from apps.integrations import partner_api
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    # ⚠ **THE REAL ADDRESS MOVED ON 2026-09-16 AND THIS HELPER MOVED WITH IT**
    # (`CR-110-BRC04` phase 2 waves 3 and 4). `/v1/payments` and `/v1/billing`
    # served a FLAT four-field record and are RETIRED — they answer `410`
    # naming their replacement. Every case below is about the KEY: that the
    # door recognises one this wave minted, stops recognising a revoked one and
    # writes *last used*; none of them is about the payload. So the helper
    # calls the address a finance system is given TODAY rather than being
    # deleted with the route, and the cases go on asserting what they always
    # asserted — through a payload that is now real.
    served = {
        "payments": (partner_api.partner_v1_payments, "/partner/v1/payments"),
        "billing": (partner_api.partner_bills, "/partner/v1/bills"),
    }
    view, path = served[what]
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}{path}",
        {
            # Verified against the key and never used to select (`BR-TEN-003`).
            "company_id": str(tenant.id),
            # Required on payments, harmless on bills, and wide enough to hold
            # every fixture: these cases are about the key, not the window.
            "start_date": "2000-01-01",
            "end_date": "2099-12-31",
        },
        HTTP_AUTHORIZATION=f"Bearer {presented}" if presented is not None else "",
        REMOTE_ADDR="198.51.100.12",  # US-INT-040 §4's partner caller
    )
    request.tenant_id = tenant.id
    started = time.monotonic()
    with core_tenancy.tenant_context(tenant.id):
        response = view(request)
        response.render() if hasattr(response, "render") else None
        body = response.content
    return response.status_code, body, time.monotonic() - started


def connect_partner(tenant, actor, **kwargs):
    response = post_connect(tenant, actor, PARTNER, PARTNER_FIELDS, cadence="manual", **kwargs)
    assert response.status_code == 201, response.data
    return response


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


def issue(tenant, actor, key=PARTNER, role="system_admin", scope=None):
    from apps.integrations import api as integrations_api

    return call(
        integrations_api.partner_key,
        "post",
        tenant,
        actor,
        role,
        data={"scope": _full_scope() if scope is None else scope},
        key=key,
    )


def revoke(tenant, actor, key=PARTNER, role="system_admin"):
    from apps.integrations import api as integrations_api

    return call(integrations_api.partner_key, "delete", tenant, actor, role, key=key)


# ── TC-1 · shown once ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_tc1_issue_shows_the_key_once_and_the_card_shows_only_the_hint(brazos, dana):
    """*Alex presses Issue key … the key is shown once with Copy; GET afterwards
    returns `••••7Q2F` only; S144 lists it issued … never used.*"""
    connect_partner(brazos, dana)

    response = issue(brazos, dana)
    assert response.status_code == 201, response.data
    minted = response.data["key"]
    assert KEY_SHAPE.match(minted), minted
    assert response.data["hint"] == "••••" + minted[-4:]
    assert response.data["version"] == 1

    # …and now it is gone. Every read path, not just the one the screen uses.
    after = card(brazos, dana, PARTNER)
    assert minted not in repr(after)
    assert after["connection"]["credential"]["hint"] == response.data["hint"]
    assert [one["hint"] for one in after["issued_keys"]] == [response.data["hint"]]
    assert after["issued_keys"][0]["state"] == "active"
    assert after["issued_keys"][0]["last_used_at"] is None  # *never used*
    assert minted not in repr(grid(brazos, dana))

    # The stored row holds no key material at all — not even encrypted.
    row = models.IntegrationCredential.objects.get(
        connection__tenant_id=brazos.id, connection__provider_key=PARTNER
    )
    assert minted not in row.payload_enc
    assert minted not in (row.blind_index or "")
    assert row.masked_hint == response.data["hint"]


# ── TC-2 · the partner authenticates, for one utility ───────────────────────


@pytest.mark.django_db
def test_tc2_the_partner_authenticates_for_brazos_bend_and_last_used_moves(brazos, dana):
    """*The partner presents the key … authenticated for Brazos Bend only;
    S144's* last used *updates.*

    Through the real route. The key was minted by this wave and recognised by
    wave S's door — which is the only thing that proves the blind-index context
    is genuinely one string and not two that happen to look alike today.
    """
    connect_partner(brazos, dana)
    minted = issue(brazos, dana).data["key"]

    assert card(brazos, dana, PARTNER)["issued_keys"][0]["last_used_at"] is None

    status, body, _elapsed = partner_call(brazos, minted)
    assert status == 200, body
    payload = json.loads(body)
    assert set(payload) >= {"total_records", "page", "records"}
    # The response a partner receives carries no key material of any kind.
    assert minted not in body.decode()

    # *last used* is DERIVED from the access-log row wave S just wrote — there
    # is no `config.last_used_at` and there is deliberately no second copy.
    keys = card(brazos, dana, PARTNER)["issued_keys"]
    assert keys[0]["last_used_at"] is not None
    assert models.IntegrationRun.objects.filter(
        direction=models.RUN_DIRECTION_INBOUND_READ
    ).count() == 1


# ── TC-3 · revoke, then the VERY NEXT call ──────────────────────────────────


@pytest.mark.django_db
def test_tc3_revoking_refuses_the_partners_very_next_call(brazos, dana):
    """The headline of the whole wave, proved as three consecutive requests.

    Call, revoke, call again — same process, same key, nothing in between: no
    restart, no sleep, no cache flush, no new fixture. If any layer ever
    memoises the authorisation decision — a dict, an `lru_cache`, a
    request-local, a Redis entry — the third step keeps answering 200 and this
    goes red naming it.
    """
    connect_partner(brazos, dana)
    minted = issue(brazos, dana).data["key"]

    before_status, _body, _e = partner_call(brazos, minted)
    assert before_status == 200

    assert revoke(brazos, dana).status_code == 200

    after_status, after_body, _e = partner_call(brazos, minted)
    assert after_status == 404, after_body

    # …and it reads exactly as a key that never existed does.
    unknown_status, unknown_body, _e = partner_call(brazos, UNKNOWN_KEY)
    assert (after_status, after_body) == (unknown_status, unknown_body)

    # Revoked, never deleted: S144 still lists it, and says so.
    keys = card(brazos, dana, PARTNER)["issued_keys"]
    assert [one["state"] for one in keys] == ["revoked"]
    assert keys[0]["revoked_at"] is not None
    assert models.IntegrationCredential.objects.filter(is_active=True).count() == 0


# ── TC-4 · replace ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_tc4_replacing_shows_the_new_key_once_and_the_old_one_stops_at_once(brazos, dana):
    connect_partner(brazos, dana)
    first = issue(brazos, dana).data["key"]
    second_response = issue(brazos, dana)
    second = second_response.data["key"]
    assert second != first
    assert second_response.data["version"] == 2

    assert partner_call(brazos, second)[0] == 200
    assert partner_call(brazos, first)[0] == 404  # from the moment of replacing

    keys = card(brazos, dana, PARTNER)["issued_keys"]
    assert [(one["version"], one["state"]) for one in keys] == [(2, "active"), (1, "revoked")]


# ── TC-5 · another utility's route — PROVED ON POSTGRESQL, NOT HERE ─────────
#
# ⚠ **TC-5 IS IN `tests/test_us_int_040_pg.py` AND THIS COMMENT IS ITS SIGNPOST,
# BECAUSE THE ABSENCE OF A CASE IS INVISIBLE AND ITS PRESENCE IN THE WRONG FILE
# IS WORSE.**
#
# It was written here first and it FAILED — Brazos Bend's key answered `200` at
# Lone Star Ridge's address. That reads like a catastrophic cross-tenant hole
# and it is not one: `serve._connection_for()` takes no `tenant_id` argument on
# purpose, because *"the tenant is already on the database session"* — so the
# scoping is `RLS FORCE` and nothing else, and **SQLite has no row-level
# security**. Under `config.settings.test` the query is simply unscoped.
#
# Leaving it here would have been law 7's third shape: a case incapable of
# passing, on the vendor that cannot hold the guarantee. Deleting it would have
# been worse. So it moved to the vendor that has RLS, runs under the
# NON-SUPERUSER probe role, and SKIPS rather than passing vacuously.


# ── TC-6 · the boundary, as it actually stands ──────────────────────────────


@pytest.mark.django_db
def test_tc6_the_enable_path_is_built_and_names_no_open_question(brazos, dana):
    """⚠ **US-INT-040 TC-6 AS WRITTEN IS STALE AND THE STORY IS AMENDED RATHER
    THAN THIS TEST BENT TO FIT IT.**

    TC-6 says enabling the connection raises `NotImplementedError
    ("OQ-INT-1481")` and that the screen says *Waiting for a decision on who may
    allow this*. **`OQ-INT-1481` was CLOSED on 2026-09-04** — option (a), the
    System Admin authorises, recorded as an audited grant plus a
    subprocessor-register row pointing inward — and wave S BUILT that path on
    2026-09-06 (`partner_api.grant_authority`). A refusal naming that question
    would now tell a clerk a decision is waited on that was made two days ago:
    the *closed question whose body still describes the open world* CLAUDE.md
    names, and the fix is to amend the body.

    So this asserts the opposite of what TC-6 asked for: **nothing in the
    partner path refuses by naming `OQ-INT-1481` any more**, and the door
    serves. It greps the three files rather than one refusal string, because
    the stale sentence could come back in any of them.
    """
    from apps.integrations import partner_api

    connect_partner(brazos, dana)
    minted = issue(brazos, dana).data["key"]
    assert partner_call(brazos, minted)[0] == 200, "the enable path is a build, not a refusal"

    for module in (serve, partner_api, machine_auth):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        raising = [
            line
            for line in source.splitlines()
            if "OQ-INT-1481" in line and ("NotImplementedError" in line or "raise " in line)
        ]
        assert raising == [], (
            f"{module.__name__} still refuses by naming a question ruled on "
            f"2026-09-04: {raising}"
        )


# ── TC-7 · the three exits ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_tc7_the_key_appears_in_no_audit_row_no_log_and_no_read_path(
    brazos, dana, audit_rows, caplog
):
    connect_partner(brazos, dana)
    with caplog.at_level(logging.DEBUG):
        minted = issue(brazos, dana).data["key"]
        partner_call(brazos, minted)          # a successful read
        partner_call(brazos, UNKNOWN_KEY)     # and a refused one
        revoke(brazos, dana)

    hint = "••••" + minted[-4:]
    assert minted not in repr(audit_rows)
    assert hint in repr(audit_rows), "the audit row must still say WHICH key, by its hint"
    assert minted not in caplog.text
    assert minted not in repr(grid(brazos, dana))
    assert minted not in repr(card(brazos, dana, PARTNER))

    actions = [row["action"] for row in audit_rows]
    assert "integration.key_issued" in actions  # hard rule 7
    assert "integration.key_revoked" in actions
    # ONE row per act, not two — the credential-record row is suppressed
    # deliberately (`services.record_credential(audit_action=None)`).
    assert actions.count("integration.key_issued") == 1
    assert "integration.credential.record" not in actions


# ── the property the story has no TC for, and DEF-INT-4216's missing proof ──


@pytest.mark.django_db
def test_the_three_refusals_are_one_answer_in_status_body_and_time(brazos, dana):
    """A wrong key, a revoked key and an unknown key are indistinguishable.

    THREE THINGS ARE COMPARED AND ALL THREE ARE NEEDED:
      * the **status**, because a 401 beside a 404 is the whole answer;
      * the **body bytes**, not a parsed body — a trace id, a differing key
        order or a negotiated content type would each be information;
      * the **elapsed time**, because the three cost different amounts of work
        (an unknown provider key costs one query less than a revoked credential
        does) and a stopwatch reads that difference. `serve.REFUSAL_FLOOR_S` is
        the equaliser; this asserts each refusal reaches it and that the spread
        between them is a small fraction of it.

    It is written here rather than left to wave S because of `DEF-INT-4216`:
    both `partner_api.py` and `runners/serve.py` argue from a file called
    `test_us_int_041_partner_surface.py` that is not in the repository. The
    argument is right; nothing was checking it.
    """
    connect_partner(brazos, dana)
    revoked = issue(brazos, dana).data["key"]
    revoke(brazos, dana)

    answers = {
        name: partner_call(brazos, presented)
        for name, presented in (
            ("wrong", WRONG_KEY),
            ("revoked", revoked),
            ("unknown", UNKNOWN_KEY),
        )
    }
    statuses = {name: one[0] for name, one in answers.items()}
    bodies = {name: one[1] for name, one in answers.items()}
    times = {name: one[2] for name, one in answers.items()}

    assert len(set(statuses.values())) == 1, statuses
    assert len(set(bodies.values())) == 1, bodies
    assert statuses["wrong"] == 404

    for name, elapsed in times.items():
        assert elapsed >= serve.REFUSAL_FLOOR_S * 0.9, f"{name} came back early: {times}"
    spread = max(times.values()) - min(times.values())
    assert spread < serve.REFUSAL_FLOOR_S * 0.5, f"the three are not equally slow: {times}"


@pytest.mark.django_db
def test_the_mint_and_the_door_share_one_context(brazos, dana):
    """One string, imported, not two that happen to agree today.

    `machine_auth` WRITES the blind index and `serve` READS it. If the two
    spellings ever parted, every valid key would be refused — and it would look
    exactly like a wrong key, so no refusal test anywhere would notice. This is
    the one assertion that fails loudly instead.
    """
    from core import crypto

    assert machine_auth.crypto_context() is serve.ISSUED_KEY_BLIND_INDEX_CONTEXT

    connect_partner(brazos, dana)
    minted = issue(brazos, dana).data["key"]
    row = models.IntegrationCredential.objects.get(connection__provider_key=PARTNER)
    assert row.blind_index in crypto.blind_index_candidates(
        minted, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT
    )


@pytest.mark.django_db
def test_a_key_is_refused_where_the_manifest_does_not_issue_one(brazos, dana, smtp_adapter):
    """`email_smtp` is `we_hold_theirs`. Issuing a key for it is refused by the
    MANIFEST's auth mode, not by a list of provider keys kept here (G77)."""
    from tests.test_us_int_helpers_b import SMTP_FIELDS

    assert post_connect(brazos, dana, "email_smtp", SMTP_FIELDS).status_code == 201
    response = issue(brazos, dana, key="email_smtp")
    assert response.status_code == 409, response.data
    assert response.data["message_key"] == machine_auth.REFUSAL_NOT_A_PARTNER_CONNECTION
    assert response.data["br_ref"] == "BR-INT-053"


@pytest.mark.django_db
def test_revoking_when_no_key_was_issued_is_refused(brazos, dana):
    connect_partner(brazos, dana)
    response = revoke(brazos, dana)
    assert response.status_code == 409, response.data
    assert response.data["message_key"] == machine_auth.REFUSAL_NO_KEY_ISSUED


@pytest.mark.django_db
def test_a_sandbox_connection_mints_a_sandbox_key(brazos, dana):
    """BR-INT-026's mix-up, made visible in the key itself: a partner can read
    the environment off the string before they paste it anywhere."""
    connect_partner(brazos, dana, environment="sandbox")
    minted = issue(brazos, dana).data["key"]
    assert minted.startswith("sbh_test_")


@pytest.mark.django_db
def test_only_a_system_admin_may_issue_or_revoke(brazos, dana, erin):
    """A4's `settings_lookups` cell, refused twice — at the permission class and
    again in the service's own `@require_role` (DEF-196's shape)."""
    connect_partner(brazos, dana)
    assert issue(brazos, dana, role="billing_clerk").status_code == 403
    assert issue(brazos, dana).status_code == 201
    assert revoke(brazos, dana, role="executive").status_code == 403

# ── Trace ──────────────────────────────────────────────
# Change:  Settings → Security redesign, APPROVED by the PO 2026-09-29. Job 2
#          — the Audit log card under Save
#          (05-prototype/security-redesign-2026-09-29/approved-auditcard-1440.png).
#          PO verbatim: *"keep it here only in this screen"*, then *"i only
#          need bigger real estate for audit logs - can you give a card
#          layout for it"*.
# Rules:   BR-AUD-003 (the actor shapes; an unnamed system job) · BR-AUD-013
#          (every audit read starts from a time floor) · BR-IDN-019 (who may
#          see this tab) · B14 rule 31 (no database id is ever the visible
#          value of a field) · CLAUDE.md hard rule 4 (no surface may call an
#          audit row a permanent record) · hard rule 1 (tenant scoping)
# Tests:   this file (the app tier). The RLS half is PostgreSQL-only and
#          lives in tests/test_security_redesign_audit_card_pg.py, because a
#          probe on SQLite is no proof of the thing that matters (law 14).
# ───────────────────────────────────────────────────────
"""WHEN · WHO · SETTING · CHANGE — five rows, honestly fewer, never blank.

⚠ **THE SINK IS THE REAL ONE HERE AND THAT IS THE POINT.** The shared `idn`
fixture registers a LIST as the audit sink, so no `audit_log` row is ever
written and a card read under it would return `[]` for every case — five
green tests proving nothing (law 7's *incapable of failing*). `card_env`
below registers `apps.audit.services.store_row` instead, so every assertion
runs over rows that went through the sanctioned writer.
"""

import json

import pytest

from apps.audit import services as audit_services
from apps.identity import selectors, services
from apps.identity.models import SecurityPolicy
from apps.identity.seams import audit_seam
from core import audit as core_audit
from core import tenancy as core_tenancy
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def card_env(idn):
    """`idn`, with the audit trail actually being written to the database."""
    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    try:
        yield idn
    finally:
        core_audit.set_audit_sink(previous)


def _admin(env):
    users = env.seed_silvercreek()
    return users, signed_in_client(users.alex.email, "Canyon2026rapids")


def _save(env, client, ip=None, **values):
    """One trip through the ONE audited door — over the wire, so the role
    gate, the serializer and `save_security_policy` are all in the path."""
    from tests.test_us_idn_helpers import api_put

    response = api_put(client, "/settings/security-policy", values, ip=ip)
    assert response.status_code == 200, response.content
    return response


def _card(env, tenant=None):
    tenant = tenant or env.silvercreek
    with core_tenancy.tenant_context(tenant.id):
        return selectors.security_policy_audit_card(tenant.id)


# ═══════════════════════════════════════════════════════════════════════════
# The shape the drawing asks for
# ═══════════════════════════════════════════════════════════════════════════
def test_five_changes_come_back_newest_first(card_env):
    users, client = _admin(card_env)
    for minutes in (5, 10, 15, 30, 45, 60):
        _save(card_env, client, lockout_minutes=minutes)

    card = _card(card_env)
    assert len(card["rows"]) == 5
    assert card["complete"] is True
    afters = [row["after"] for row in card["rows"]]
    assert afters == [60, 45, 30, 15, 10], afters  # newest first, 5→10 fell off


def test_every_row_is_the_wire_shape_the_screen_declares(card_env):
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30)

    row = _card(card_env)["rows"][0]
    # `SecurityPolicyChange` in 07-frontend/src/api/endpoints.ts, key for key.
    # A key this set does not name is a key no screen reads.
    assert set(row) == {"id", "changed_at", "actor", "field", "before", "after"}
    assert row["field"] == "lockout_minutes"
    assert row["actor"]["name"] == users.alex.full_name
    # ⚠ RAW values, never words: `securityValueLabel` prints `15 minutes` in
    # the reader's own language, and a second formatter here is the thing
    # DEF-IDN-7501 is about.
    assert row["before"] == 15
    assert row["after"] == 30
    assert row["changed_at"].startswith("20")


def test_no_database_id_is_anywhere_in_the_payload(card_env):
    """B14 rule 31. Asserted over the SERIALISED payload rather than key by
    key, because the way an id reaches a screen is by riding along in a dict
    nobody looked at."""
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30)

    text = json.dumps(_card(card_env))
    # ⚠ THE ACTOR'S id IS PRESENT AND THAT IS S61's RATIFIED CONTRACT, NOT A
    # BREACH. B14 rule 31 forbids an id as the VISIBLE VALUE of a field;
    # `actorLabel` prints the NAME and `AuditLogPage` puts the id on `title`
    # for support (DEF-2378). Serving a different person shape on this one
    # card would be a second actor contract for one table.
    assert str(users.alex.id) in text
    row = _card(card_env)["rows"][0]
    assert row["actor"]["name"] == users.alex.full_name  # …and a NAME to draw
    # Nothing else. The policy row and the tenant have no business here.
    policy = SecurityPolicy.objects.get(tenant=card_env.silvercreek)
    assert str(policy.id) not in text
    assert str(card_env.silvercreek.id) not in text


def test_one_save_of_three_settings_draws_three_rows(card_env):
    """The card's rows are CHANGES, not saves — the drawing puts one setting
    on each line."""
    users, client = _admin(card_env)
    _save(
        card_env,
        client,
        lockout_minutes=30,
        lockout_max_failed=8,
        pw_expiry_days=90,
    )

    card = _card(card_env)
    assert len(card["rows"]) == 3
    assert {row["field"] for row in card["rows"]} == {
        "lockout_minutes",
        "lockout_max_failed",
        "pw_expiry_days",
    }


def test_a_save_that_changed_nothing_draws_no_row(card_env):
    """`save_security_policy` writes a row with an empty pair; the card must
    not draw a line saying a thing changed from itself to itself."""
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=15)  # 15 is already the default
    assert _card(card_env)["rows"] == []


# ═══════════════════════════════════════════════════════════════════════════
# The three renderings the drawing names, and the empty answer
# ═══════════════════════════════════════════════════════════════════════════
def test_the_pair_is_served_raw_for_the_browser_to_render(card_env):
    """`Never → Every 90 days` and `Off → On` are the two the redesign names
    that are NOT a plain number, so they are where a server that decided to
    compose words would have had to invent them.

    ⚠ **WHAT IS ASSERTED IS `None → 90` AND `False → True`.** The words are
    `securityValueLabel`'s, in eleven languages; this proves the server sends
    the fact the browser needs and does not pre-chew it — including `None`,
    which a payload that stringified everything would have flattened to the
    empty string and made indistinguishable from *no value recorded*.
    """
    users, client = _admin(card_env)
    _save(card_env, client, pw_expiry_days=90)
    _save(card_env, client, keep_signed_in_offered=False)
    _save(card_env, client, keep_signed_in_offered=True)

    by_field = {}
    for row in _card(card_env)["rows"]:
        by_field.setdefault(row["field"], []).append(row)

    expiry = by_field["pw_expiry_days"][0]
    assert (expiry["before"], expiry["after"]) == (None, 90)
    offered = by_field["keep_signed_in_offered"][0]  # newest: the switch back on
    assert (offered["before"], offered["after"]) == (False, True)


def test_an_address_list_travels_as_a_list(card_env):
    users, client = _admin(card_env)
    _save(card_env, client, ip="203.0.113.5", ip_allowlist=["203.0.113.0/24"])

    row = _card(card_env)["rows"][0]
    assert row["field"] == "ip_allowlist"
    # An empty list, not `""` and not null — `securityValueLabel` turns it
    # into the word *Empty*, and a blank cell would read as a rendering bug.
    assert row["before"] == []
    assert row["after"] == ["203.0.113.0/24"]


def test_nothing_recorded_is_an_honest_empty_answer(card_env):
    """`audit_log` is pruned on a retention schedule and hard rule 4 forbids
    calling it a permanent record, so this is a TRUE answer and not a fault.
    `complete` is False so the screen can say so without counting the array
    or inventing a row."""
    _admin(card_env)
    card = _card(card_env)
    assert card == {"rows": [], "complete": False, "scan_capped": False}


def test_fewer_than_five_comes_back_as_what_there_is(card_env):
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30)
    _save(card_env, client, lockout_minutes=45)

    card = _card(card_env)
    assert len(card["rows"]) == 2
    assert card["complete"] is False


# ═══════════════════════════════════════════════════════════════════════════
# The migration's row — the second line of the drawing
# ═══════════════════════════════════════════════════════════════════════════
def test_a_row_written_by_a_migration_is_attributed_to_the_product(card_env):
    """`identity/0007` and `0008` write `actor_user_id=None` with no
    automation actor — BR-AUD-003's UNNAMED SYSTEM JOB. On this card that
    must read `Product upgrade`, not a blank cell: a clerk asking *"why am I
    being signed out earlier?"* finds the answer here."""
    _admin(card_env)
    with core_tenancy.tenant_context(card_env.silvercreek.id):
        core_audit.write_row(
            action=audit_seam.SECURITY_POLICY_ACTION,
            entity_type="security_policy",
            entity_id=None,
            actor_user_id=None,
            before={"session_timeout_minutes": 480},
            after={"session_timeout_minutes": 60},
        )

    row = _card(card_env)["rows"][0]
    # ⚠ A NAMED AUTOMATION SHAPE, not a string this server composed: the
    # browser's `isAutomationActor` narrows on the PRESENCE of `kind` and
    # then prints `name`. A null here would draw a blank WHO cell.
    assert row["actor"] == {
        "kind": audit_seam.PRODUCT_ACTOR_KIND,
        "name": "Product upgrade",
        "version": None,
    }
    assert "kind" in row["actor"], "the browser narrows on `kind` and nothing else"
    assert row["field"] == "session_timeout_minutes"
    assert row["before"] == 480
    assert row["after"] == 60


def test_a_withdrawn_value_still_renders_in_the_history(card_env):
    """480 is not a choice any more. The card renders what WAS, not what may
    be chosen — a history that could only print current options would print
    nothing for the very change it exists to explain."""
    assert 480 not in services.SETTING_LIMITS["session_timeout_minutes"]["choices"]


# ═══════════════════════════════════════════════════════════════════════════
# Scoping and the role gate
# ═══════════════════════════════════════════════════════════════════════════
def test_the_card_never_shows_another_utility_row(card_env):
    """The app-layer half. The RLS half is the `_pg` file — on SQLite there is
    no row-level security to prove anything about."""
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30)

    assert _card(card_env, card_env.bluemesa)["rows"] == []
    assert len(_card(card_env)["rows"]) == 1


def test_the_endpoint_answers_an_admin_and_an_executive_and_refuses_a_clerk(card_env):
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30)

    response = api_get(client, "/settings/security-policy/audit")
    assert response.status_code == 200, response.content
    assert len(json.loads(response.content)["rows"]) == 1

    exec_client = signed_in_client(users.diana.email, "Vista2026peak")
    assert api_get(exec_client, "/settings/security-policy/audit").status_code == 200

    clerk = signed_in_client(users.priya.email, "Meadow2026sage")
    assert api_get(clerk, "/settings/security-policy/audit").status_code == 403


def test_the_endpoint_is_not_cached(card_env):
    """A history card that answers 304 shows yesterday's history.

    ⚠ **THE 200 IS ASSERTED FIRST AND IT IS NOT DECORATION.** The red proof
    for this change removed the route, and this case went on PASSING — a 404
    carries no `ETag` either, so *"no ETag"* was true of a screen that did not
    exist. Law 7 habit 2, found by asking what would make the check pass
    wrongly and then watching it do so.
    """
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30)
    response = api_get(client, "/settings/security-policy/audit")
    assert response.status_code == 200, response.content
    assert response.get("ETag") is None


# ═══════════════════════════════════════════════════════════════════════════
# The renderer's own edges
# ═══════════════════════════════════════════════════════════════════════════
def test_the_server_composes_no_words_at_all(card_env):
    """The reversal of 2026-09-29, as an assertion rather than a comment.

    ⚠ **THIS IS THE CHECK THAT STOPS A SECOND FORMATTER COMING BACK.** For one
    afternoon this server rendered `480 minutes` and `Lockout length` itself,
    beside a Security tab that renders both through `securityValueLabel` and
    the eleven catalogues. Two formatters for one pair is `DEF-IDN-7501`'s
    shape, and only the browser's can speak eleven languages. So every value
    on this wire is a number, a boolean, a null or a list — never a string a
    human reads — and a `text` or `label` key anywhere in the payload is this
    mistake returning.
    """
    users, client = _admin(card_env)
    _save(card_env, client, lockout_minutes=30, pw_expiry_days=90)
    _save(card_env, client, ip="203.0.113.5", ip_allowlist=["203.0.113.0/24"])

    for row in _card(card_env)["rows"]:
        for side in ("before", "after"):
            assert not isinstance(row[side], str) or row[side] == "", (row["field"], row[side])
        assert "text" not in row and "label" not in row and "setting" not in row, row

    import importlib.util

    assert importlib.util.find_spec("apps.identity.security_render") is None, (
        "apps/identity/security_render.py is back — the words belong to the "
        "eleven catalogues, not to this server"
    )


def test_the_scan_is_bounded_and_says_so(card_env):
    """Law 7's fifth shape — a bound with no number beside it is
    indistinguishable from no bound at all."""
    assert audit_seam.SCAN_LIMIT == 200
    assert _card(card_env)["scan_capped"] is False

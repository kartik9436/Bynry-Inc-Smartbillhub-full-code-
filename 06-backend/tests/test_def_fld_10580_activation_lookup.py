# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10580 (beta report MQ-006, CR-187-BRC10) — the field app
#           baked ONE utility into the build; a second utility's technician
#           could not sign in. PO 2026-10-24: *"A. The code from the office
#           sets the utility"*, and the uniqueness design in the decision log
#           of that date (*"MQ-006: THE CODE FROM THE OFFICE SETS THE UTILITY"*).
# Rules:    BR-IDN-002 (one generic refusal) · BR-IDN-006 · R105 · hard rule 1
#           (the register is DECLARED RLS-exempt) · hard rule 7 (audited)
# Tests:    this file (SQLite) · test_def_fld_10580_activation_lookup_pg.py
# ───────────────────────────────────────────────────────
"""The platform-wide code register and the utility-free lookup door.

Worked case, the decision log's: Houston issues `K7QM2P`; when Brookfield's
draw also lands on `K7QM2P`, the database refuses it and Brookfield is shown
`P3XW9A` — neither office ever sees the clash. Here Silver Creek is Houston
and Blue Mesa is Brookfield.
"""

from __future__ import annotations

import json

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import resolve

from apps.identity import native
from apps.identity.models import ActivationCode, ActivationCodeRegister
from core import tenancy as core_tenancy
from tests.isolation_helpers import writing_as_tenant
from tests.test_us_idn_helpers import JSON, SC, api_path, idn  # noqa: F401

LOOKUP = "/api/auth/activation/lookup"


@pytest.fixture()
def two(idn):  # noqa: F811
    """A field technician at each utility, nobody signed in, throttles clean."""
    cache.clear()
    idn.marco, _ = idn.make_user(
        idn.silvercreek, "marco@silvercreek.example", "Marco Ruiz", role="field_technician"
    )
    idn.jo, _ = idn.make_user(
        idn.bluemesa, "jo@bluemesa.example", "Jo Park", role="field_technician"
    )
    yield idn
    cache.clear()


def _issue(tenant, user):
    with writing_as_tenant(tenant):
        return native.issue_activation_code(actor=None, user=user)["activation_code"]


def _draws(monkeypatch, *codes):
    """Force the random draw: each call returns the next code given."""
    queue = list(codes)
    monkeypatch.setattr(native, "_draw_code", lambda: queue.pop(0))
    return queue


def _lookup(code, *, ip="10.0.0.1", device="handset-1"):
    extra = {"REMOTE_ADDR": ip}
    if device is not None:
        extra["HTTP_X_DEVICE_ID"] = device
    return Client().post(LOOKUP, data={"code": code}, content_type=JSON, **extra)


def _reason(response):
    return json.loads(response.content).get("params", {}).get("reason")


def _register_rows():
    return list(ActivationCodeRegister.objects.values_list("tenant_id", "code_digest"))


# ── the register ────────────────────────────────────────────────────────────
def test_every_issued_code_is_in_the_register_as_a_keyed_digest(two):
    code = _issue(two.silvercreek, two.marco)
    rows = _register_rows()
    assert [tenant for tenant, _ in rows] == [two.silvercreek.id]
    digest = rows[0][1]
    assert code not in digest and len(digest) == 64
    # NOT the per-tenant HMAC: the same code must be the same digest everywhere.
    assert digest != native._code_hmac(two.silvercreek.id, code)
    assert digest == native._register_digest(code.lower())


def test_a_collision_with_another_utility_redraws(two, monkeypatch):
    """The decision log's worked case, through the real database constraint."""
    left = _draws(monkeypatch, "K7QM2P", "K7QM2P", "P3XW9A")
    assert _issue(two.silvercreek, two.marco) == "K7QM2P"
    assert _issue(two.bluemesa, two.jo) == "P3XW9A"
    assert left == []  # Blue Mesa's first draw WAS the clash, and was redrawn
    assert sorted(t for t, _ in _register_rows()) == sorted([two.silvercreek.id, two.bluemesa.id])
    assert _lookup("K7QM2P").json()["tenant"] == "silvercreek"
    assert _lookup("P3XW9A").json()["tenant"] == "bluemesa"


def test_a_code_is_never_reissued_even_after_it_is_void(two, monkeypatch):
    """A new code voids the old one, and the old one is STILL never drawn again
    — not at the same utility, not at another (rows are never deleted)."""
    _draws(monkeypatch, "K7QM2P", "K7QM2P", "ABCDEF", "K7QM2P", "ABCDEF", "HJKMNP")
    assert _issue(two.silvercreek, two.marco) == "K7QM2P"
    assert _issue(two.silvercreek, two.marco) == "ABCDEF"  # same login, old one void
    assert _issue(two.bluemesa, two.jo) == "HJKMNP"
    assert ActivationCodeRegister.objects.count() == 3


def test_eight_collisions_in_a_row_is_a_broken_random_source(two, monkeypatch):
    _issue(two.silvercreek, two.marco)
    stuck = ActivationCodeRegister.objects.get().code_digest
    monkeypatch.setattr(native, "_register_digest", lambda code: stuck)
    from core import errors

    with pytest.raises(errors.SysError):
        _issue(two.bluemesa, two.jo)


# ── the door ────────────────────────────────────────────────────────────────
def test_the_door_has_no_utility_in_its_path_and_is_public(two):
    match = resolve(LOOKUP)
    assert match.func.cls.__name__ == "ActivationLookupView"
    assert core_tenancy.tenant_slug_of(LOOKUP) is None


def test_a_live_code_names_its_utility_and_nothing_else(two):
    code = _issue(two.silvercreek, two.marco)
    response = _lookup(code[:3].lower() + " " + code[3:])
    assert response.status_code == 200, response.content
    assert response.json() == {"tenant": "silvercreek", "utility_name": "Silver Creek Water"}
    looked = two.rows_for("auth.activation_code_looked_up")
    assert len(looked) == 1 and str(looked[0]["entity_id"]) == str(two.marco.id)


def test_then_the_code_works_on_the_utility_it_named_and_on_no_other(two):
    code = _issue(two.bluemesa, two.jo)
    tenant = _lookup(code).json()["tenant"]
    good = Client().post(
        api_path("/auth/activation/check", tenant),
        data={"code": code, "email": "jo@bluemesa.example"}, content_type=JSON,
    )
    assert good.status_code == 200 and good.json()["utility_name"] == "Blue Mesa Utilities"
    wrong = Client().post(
        api_path("/auth/activation/check", SC),
        data={"code": code, "email": "jo@bluemesa.example"}, content_type=JSON,
    )
    assert wrong.status_code == 401


@pytest.mark.parametrize("state", ["unknown", "malformed", "expired", "used", "voided"])
def test_every_dead_code_gets_the_one_generic_refusal(two, monkeypatch, state):
    code = _issue(two.silvercreek, two.marco)
    if state == "unknown":
        code = "ZZZZZZ" if code != "ZZZZZZ" else "YYYYYY"
    elif state == "malformed":
        code = "K7Q"
    elif state == "expired":
        two.clock.advance(days=7, minutes=1)
    elif state == "used":
        with writing_as_tenant(two.silvercreek):
            ActivationCode.objects.update(used_at=two.clock())
    elif state == "voided":
        _draws(monkeypatch, "HJKMNP")
        _issue(two.silvercreek, two.marco)
    response = _lookup(code)
    assert response.status_code == 401
    assert _reason(response) == "activation_code_not_accepted"
    assert "tenant" not in response.json() and "utility_name" not in response.json()


# ── the limits (PO 2026-10-24: platform-wide, per address and per device) ───
def test_the_door_is_limited_per_network_address(two, settings):
    settings.ACTIVATION_LOOKUP_MAX_TRIES = 3
    for n in range(3):
        assert _lookup("ZZZZZZ", device=f"phone-{n}").status_code == 401
    assert _lookup("ZZZZZZ", device="phone-new").status_code == 429


def test_the_door_is_limited_per_device(two, settings):
    settings.ACTIVATION_LOOKUP_MAX_TRIES = 3
    for n in range(3):
        assert _lookup("ZZZZZZ", ip=f"10.0.1.{n}").status_code == 401
    assert _lookup("ZZZZZZ", ip="10.0.9.9").status_code == 429


def test_leaving_the_device_header_off_counts_against_the_address(two, settings):
    settings.ACTIVATION_LOOKUP_MAX_TRIES = 2
    assert _lookup("ZZZZZZ", device=None).status_code == 401
    assert _lookup("ZZZZZZ", device=None).status_code == 401
    assert _lookup("ZZZZZZ", device=None, ip="10.0.0.1").status_code == 429


def test_the_seeded_limit_is_ten_per_fifteen_minutes(two):
    from django.conf import settings as live

    assert live.ACTIVATION_LOOKUP_MAX_TRIES == 10
    assert live.ACTIVATION_LOOKUP_WINDOW_S == 15 * 60

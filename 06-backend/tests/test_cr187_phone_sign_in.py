# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the field app signs in by work EMAIL or PHONE NUMBER
#           (PO 2026-10-21; there is no Technician ID)
# Rules:    BR-IDN-001 (tenant-first) · BR-IDN-002 (one generic failure) ·
#           BR-IDN-025 (lockout) · BR-IDN-029 (unique per utility) · BR-AUD-006
# Tests:    this file (SQLite) · test_cr187_phone_sign_in_pg.py (PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""Phone number as a sign-in name: one field, `@` → email, else E.164.

Every case drives the real routes under `/api/{tenant}/…` with the identity
suite's `idn` fixture (controllable clock, recording audit sink, two tenants:
Silver Creek and Blue Mesa). Re-run on PostgreSQL by the `_pg` file.
"""

from __future__ import annotations

import importlib
import io
import json
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import Client

from apps.identity import native, phones
from apps.identity.models import User
from tests.isolation_helpers import writing_as_tenant
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    JSON,
    SC,
    api_path,
    idn,
    signed_in_client,
)

PASSWORD = "Valley2026river"
BM_PASSWORD = "Mesa2026sunrise"
DEVICE = "a1b2c3d4-handset-0104"
DANA_PHONE = "(512) 555-0104"


def _set_phone(tenant, user, phone):
    with writing_as_tenant(tenant):
        user.phone = phone
        user.save(update_fields=["phone", "updated_at"])
        user.refresh_from_db()
    return user


@pytest.fixture()
def phone(idn):  # noqa: F811
    """Silver Creek: Alex (admin) and Dana (field technician, `(512) 555-0104`).
    Blue Mesa: Ben (field technician) holding THE SAME number."""
    cache.clear()
    idn.users = idn.seed_silvercreek()
    idn.dana, _ = idn.make_user(
        idn.silvercreek, "dana@silvercreek.example", "Dana Ortiz",
        password=PASSWORD, role="field_technician",
    )
    _set_phone(idn.silvercreek, idn.dana, DANA_PHONE)
    idn.ben, _ = idn.make_user(
        idn.bluemesa, "ben@bluemesa.example", "Ben Okafor",
        password=BM_PASSWORD, role="field_technician",
    )
    _set_phone(idn.bluemesa, idn.ben, "512.555.0104")
    yield idn
    cache.clear()


def _token(identifier, password=PASSWORD, tenant=SC, field="identifier"):
    return Client().post(
        api_path("/auth/token", tenant),
        data={field: identifier, "password": password, "device_id": DEVICE, "device_name": "Van 9"},
        content_type=JSON,
    )


def _body_without_trace(response):
    body = json.loads(response.content)
    body.pop("trace_id", None)
    return body


# ── the normal form ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "typed, e164",
    [
        ("(512) 555-0104", "+15125550104"),
        ("512-555-0104", "+15125550104"),
        ("512.555.0104", "+15125550104"),
        ("+15125550104", "+15125550104"),
        ("1 512 555 0104", "+15125550104"),
        ("+44 20 7946 0958", "+442079460958"),
        ("555-0104", None),  # 7 digits — not a number we can place
        ("T-104", None),
        ("dana@silvercreek.example", None),
        ("", None),
        ("+1234", None),
    ],
)
def test_one_normal_form(typed, e164):
    assert phones.normalise_phone(typed) == e164


def test_the_kind_is_decided_by_shape():
    assert phones.identifier_kind("dana@silvercreek.example") == "email"
    assert phones.identifier_kind("(512) 555-0104") == "phone"
    assert phones.identifier_kind("T-104") == "other"


def test_saving_a_phone_fills_its_sign_in_form(phone):
    assert phone.dana.phone == DANA_PHONE  # kept as typed, for display
    assert phone.dana.phone_e164 == "+15125550104"


# ── sign-in ─────────────────────────────────────────────────────────────────
def test_sign_in_by_email_in_the_identifier_field(phone):
    response = _token("dana@silvercreek.example")
    assert response.status_code == 201, response.content
    assert response.json()["user"]["display_name"] == "Dana Ortiz"


def test_the_old_email_field_still_signs_in(phone):
    response = _token("dana@silvercreek.example", field="email")
    assert response.status_code == 201, response.content


@pytest.mark.parametrize("typed", ["(512) 555-0104", "512-555-0104", "+15125550104"])
def test_sign_in_by_phone_in_three_formats(phone, typed):
    response = _token(typed)
    assert response.status_code == 201, response.content
    assert response.json()["user"]["display_name"] == "Dana Ortiz"


def test_the_same_phone_at_two_utilities_signs_in_the_right_person_at_each(phone):
    silver = _token("512-555-0104", tenant=SC)
    mesa = _token("512-555-0104", password=BM_PASSWORD, tenant=BM)
    assert silver.status_code == 201 and mesa.status_code == 201, (silver.content, mesa.content)
    assert silver.json()["user"]["id"] == str(phone.dana.id)
    assert mesa.json()["user"]["id"] == str(phone.ben.id)
    # …and one utility's password never opens the other's person.
    assert _token("512-555-0104", password=BM_PASSWORD, tenant=SC).status_code == 401


def test_a_wrong_phone_gives_the_same_refusal_as_a_wrong_email(phone):
    wrong_email = _token("nobody@silvercreek.example")
    wrong_phone = _token("(512) 555-0199")
    malformed = _token("555-01")
    wrong_password = _token("512-555-0104", password="nope")
    for response in (wrong_email, wrong_phone, malformed, wrong_password):
        assert response.status_code == 401, response.content
    assert (
        _body_without_trace(wrong_email)
        == _body_without_trace(wrong_phone)
        == _body_without_trace(malformed)
        == _body_without_trace(wrong_password)
    )
    assert _body_without_trace(wrong_email)["message_key"] == "errors.auth.sign_in_failed"


def test_a_wrong_password_by_phone_counts_toward_the_same_lockout(phone):
    for _ in range(5):  # the utility's default lockout count
        assert _token("+15125550104", password="wrong-guess").status_code == 401
    # Locked: the RIGHT password by EMAIL is refused too — one lock per login.
    assert _token("dana@silvercreek.example").status_code == 401
    assert "auth.lockout" in phone.actions()
    phone.clock.advance(minutes=16)
    assert _token("dana@silvercreek.example").status_code == 201


def test_no_identifier_at_all_is_refused_by_name(phone):
    response = Client().post(
        api_path("/auth/token"),
        data={"password": PASSWORD, "device_id": DEVICE},
        content_type=JSON,
    )
    assert response.status_code == 422
    assert response.json()["field_errors"][0]["field"] == "identifier"


def test_the_trail_masks_the_phone_to_its_last_two_digits(phone):
    assert _token("(512) 555-0104").status_code == 201
    [row] = phone.rows_for("auth.token_issued")
    assert row["after"]["signed_in_with"] == "phone"
    assert row["after"]["identifier"] == "***04"
    flat = json.dumps(row, default=str)
    assert "5125550104" not in flat and "555-0104" not in flat


def test_two_users_sharing_a_number_neither_signs_in_by_it_both_by_email(phone):
    """A crew phone shared before this change: the backfill left both NULL
    (see the migration case below). Sharing is never a way in as the other."""
    with writing_as_tenant(phone.silvercreek):
        User.objects.filter(pk=phone.dana.pk).update(phone="512 555 0177", phone_e164=None)
        User.objects.filter(pk=phone.users.priya.pk).update(phone="512-555-0177", phone_e164=None)
    assert _token("512-555-0177").status_code == 401
    assert _token("512-555-0177", password="Meadow2026sage").status_code == 401
    assert _token("dana@silvercreek.example").status_code == 201
    assert _token("priya@silvercreek.example", password="Meadow2026sage").status_code == 201


# ── activation (FF-56) ──────────────────────────────────────────────────────
def _office_adds_technician(phone_number=None):
    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    payload = {"full_name": "Marco Ruiz", "email": "marco@silvercreek.example", "role": "field_technician"}
    if phone_number is not None:
        payload["phone"] = phone_number
    response = office.post(api_path("/users"), data=payload, content_type=JSON)
    return office, response


def _check(code, **who):
    return Client().post(
        api_path("/auth/activation/check"), data={"code": code, **who}, content_type=JSON
    )


def test_activation_accepts_a_phone_number(phone):
    _office, response = _office_adds_technician("512-555-0150")
    assert response.status_code == 201, response.content
    code = response.json()["activation_code"]
    assert _check(code, identifier="(512) 555-0199").status_code == 401  # someone else's
    checked = _check(code, identifier="+1 512 555 0150")
    assert checked.status_code == 200, checked.content
    assert checked.json()["display_name"] == "Marco Ruiz"
    assert _check(code, email="marco@silvercreek.example").status_code == 200  # old field


# ── saving a phone ──────────────────────────────────────────────────────────
def test_adding_a_user_with_a_phone_already_held_here_is_refused(phone):
    _office, response = _office_adds_technician("512 555 0104")  # Dana's, another format
    assert response.status_code == 422, response.content
    body = response.json()
    assert body["message_key"] == "errors.identity.phone_in_use"
    assert body["field_errors"][0]["field"] == "phone"
    with writing_as_tenant(phone.silvercreek):
        assert not User.objects.filter(email="marco@silvercreek.example").exists()


def test_the_same_phone_at_another_utility_is_fine(phone):
    # Ben at Blue Mesa holds +15125550104; Dana here holds it too — legal.
    assert phone.ben.phone_e164 == phone.dana.phone_e164 == "+15125550104"


def test_editing_a_user_onto_a_phone_held_here_is_refused_and_clearing_works(phone):
    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    priya = phone.users.priya
    taken = office.patch(
        api_path(f"/users/{priya.id}"), data={"phone": "+15125550104"}, content_type=JSON
    )
    assert taken.status_code == 422, taken.content
    assert taken.json()["message_key"] == "errors.identity.phone_in_use"

    bad = office.patch(api_path(f"/users/{priya.id}"), data={"phone": "12"}, content_type=JSON)
    assert bad.status_code == 422 and bad.json()["message_key"] == "errors.identity.phone_invalid"

    ok = office.patch(api_path(f"/users/{priya.id}"), data={"phone": "512-555-0122"}, content_type=JSON)
    assert ok.status_code == 200, ok.content
    assert ok.json()["user"]["phone"] == "512-555-0122"
    changed = phone.rows_for("user.phone_changed")
    assert changed and changed[-1]["after"] == {"phone": "***22"}

    # Clearing Dana's number frees it, and it stops being a way in.
    cleared = office.patch(api_path(f"/users/{phone.dana.id}"), data={"phone": ""}, content_type=JSON)
    assert cleared.status_code == 200, cleared.content
    with writing_as_tenant(phone.silvercreek):
        phone.dana.refresh_from_db()
    assert phone.dana.phone is None and phone.dana.phone_e164 is None
    assert _token("512-555-0104").status_code == 401  # no longer a way in


# ── the migration, on data that already shares a number ─────────────────────
def _backfill():
    module = importlib.import_module("apps.identity.migrations.0013_cr187_phone_sign_in")
    module.backfill(django_apps, SimpleNamespace(connection=connection))


def test_the_backfill_leaves_a_shared_number_null_and_fills_a_single_one(phone, capsys):
    with writing_as_tenant(phone.silvercreek):
        # As the data stood before identity/0013: `phone` set, no sign-in form.
        User.objects.filter(tenant=phone.silvercreek).update(phone_e164=None)
        User.objects.filter(pk=phone.users.priya.pk).update(phone="512-555-0104")  # shares Dana's
        User.objects.filter(pk=phone.users.diana.pk).update(phone="(512) 555-0133")  # alone
    with writing_as_tenant(phone.bluemesa):
        User.objects.filter(tenant=phone.bluemesa).update(phone_e164=None)
    _backfill()
    with writing_as_tenant(phone.silvercreek):
        by_email = dict(
            User.objects.filter(tenant=phone.silvercreek).values_list("email", "phone_e164")
        )
    assert by_email["dana@silvercreek.example"] is None
    assert by_email["priya@silvercreek.example"] is None
    assert by_email["diana@silvercreek.example"] == "+15125550133"
    with writing_as_tenant(phone.bluemesa):
        phone.ben.refresh_from_db()
    assert phone.ben.phone_e164 == "+15125550104"  # alone at HIS utility
    assert "left NULL" in capsys.readouterr().out

    # That shared number now signs in nobody; email still does.
    assert _token("512-555-0104").status_code == 401
    assert _token("dana@silvercreek.example").status_code == 201
    assert _token("512-555-0104", password=BM_PASSWORD, tenant=BM).status_code == 201

    # The office is told who, named and masked.
    out = io.StringIO()
    call_command("phone_sign_in_duplicates", "--tenant", SC, stdout=out)
    text = out.getvalue()
    assert "dana@silvercreek.example" in text and "priya@silvercreek.example" in text
    assert "***04" in text and "555-0104" not in text

    # Once Priya moves to her own number, re-saving Dana's switches it on.
    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert office.patch(
        api_path(f"/users/{phone.users.priya.id}"), data={"phone": "512-555-0122"}, content_type=JSON
    ).status_code == 200
    assert office.patch(
        api_path(f"/users/{phone.dana.id}"), data={"phone": DANA_PHONE}, content_type=JSON
    ).status_code == 200
    assert _token("512-555-0104").status_code == 201


def test_sign_in_never_reads_the_phone_as_typed(phone):
    """Only `phone_e164` is compared: a row whose typed phone matches but whose
    sign-in form is NULL is nobody's way in."""
    with writing_as_tenant(phone.silvercreek):
        User.objects.filter(pk=phone.dana.pk).update(phone_e164=None)
    assert native.email_for_identifier(phone.silvercreek.id, DANA_PHONE) == DANA_PHONE
    assert _token(DANA_PHONE).status_code == 401

"""DEF-IDN-9748 (high) — a Field Technician added through Settings › Users
could sign in to the STAFF web app.

`BR-WRK-043` (CONFIRMED 2026-09-04, `OQ-WRK-1494`): *"Field technicians will
not logn to web app; they will login to mobile app only"*. `sign_in` refuses a
login whose `users.surface_scope` does not name the door — but `add_user`, the
service behind Settings › Users, never set that column, so every technician a
utility added for itself kept the model default `both` and walked into the web
shell, which then refused its boot read (`GET /shell/display` is office-only)
and dead-ended on *"We couldn't load your regional settings."* (customer report,
sandbox, Entranosa Water Association, 2026-10-05). Only `sample_data.py` set
`mobile`, by hand, for the four demo technicians — which is why every test of
the rule was green.

These cases go through the ENDPOINTS the customer used, never the service:

  (a) a technician added through `POST /users` is refused on the web door with
      the field-app sentence, and signs in on the field app;
  (b) a clerk changed TO technician through `PATCH /users/{id}` is moved to the
      phone the same way;
  (c) a technician changed AWAY from technician gets the web door back — the
      decision-log row of 2026-10-05 records why the answer is `both`;
  (d) a web-only office login changed between OFFICE roles keeps `web` — the
      role decides the scope only where the role is the technician.

Run on PostgreSQL too (`--ds=config.settings.pgtest`): `users` carries FORCE RLS.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.identity.models import User
from tests.isolation_helpers import writing_as_tenant
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture used by name
    JSON,
    SC,
    api_patch,
    api_path,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ADMIN = ("alex@silvercreek.example", "Canyon2026rapids")
FIELD_APP_ONLY = "identity.signIn.fieldAppOnly"


def _sign_in(email, password, surface=None):
    body = {"email": email, "password": password}
    if surface is not None:
        body["surface"] = surface
    return Client().post(api_path("/auth/session", SC), data=body, content_type=JSON)


def _scope(user_id):
    # Every login in this file is Silver Creek's; `users` carries FORCE RLS.
    with writing_as_tenant(_SC_TENANT[0]):
        return User.objects.get(pk=user_id).surface_scope


_SC_TENANT: list = []


@pytest.fixture()
def world(idn):
    users = idn.seed_silvercreek()
    _SC_TENANT[:] = [idn.silvercreek]
    return idn, users


# (a) ─────────────────────────────────────────────────────────────────────────
def test_a_a_technician_added_in_settings_is_refused_on_the_web_and_signs_in_on_the_phone(world):
    admin = signed_in_client(*ADMIN)
    added = api_post(
        admin,
        "/users",
        {
            "full_name": "Tomas Field",
            "email": "tomas@silvercreek.example",
            "role": "field_technician",
        },
    )
    assert added.status_code == 201, added.content
    temp = added.json()["temp_password"]

    for surface in (None, "web"):
        refused = _sign_in("tomas@silvercreek.example", temp, surface)
        assert refused.status_code == 403, refused.content
        assert refused.json()["message_key"] == FIELD_APP_ONLY
        assert "sbh_session" not in refused.cookies

    phone = _sign_in("tomas@silvercreek.example", temp, "mobile")
    assert phone.status_code == 201, phone.content
    assert phone.json()["user"]["must_change_password"] is True


def test_a_an_office_user_added_in_settings_keeps_both_doors(world):
    admin = signed_in_client(*ADMIN)
    added = api_post(
        admin,
        "/users",
        {"full_name": "Owen Desk", "email": "owen@silvercreek.example", "role": "billing_clerk"},
    )
    assert added.status_code == 201, added.content
    temp = added.json()["temp_password"]
    assert _sign_in("owen@silvercreek.example", temp, "web").status_code == 201
    assert _sign_in("owen@silvercreek.example", temp, "mobile").status_code == 201


# (b) ─────────────────────────────────────────────────────────────────────────
def test_b_a_clerk_changed_to_technician_is_moved_to_the_phone(world):
    _idn, users = world
    admin = signed_in_client(*ADMIN)
    changed = api_patch(admin, f"/users/{users.priya.id}", {"role": "field_technician"})
    assert changed.status_code == 200, changed.content
    assert _scope(users.priya.id) == "mobile"

    refused = _sign_in("priya@silvercreek.example", "Meadow2026sage", "web")
    assert refused.status_code == 403, refused.content
    assert refused.json()["message_key"] == FIELD_APP_ONLY
    assert _sign_in("priya@silvercreek.example", "Meadow2026sage", "mobile").status_code == 201


# (c) ─────────────────────────────────────────────────────────────────────────
def test_c_a_technician_changed_back_to_an_office_role_gets_the_web_door_back(world):
    _idn, users = world
    admin = signed_in_client(*ADMIN)
    assert (
        api_patch(admin, f"/users/{users.priya.id}", {"role": "field_technician"}).status_code
        == 200
    )
    assert _sign_in("priya@silvercreek.example", "Meadow2026sage", "web").status_code == 403

    back = api_patch(admin, f"/users/{users.priya.id}", {"role": "billing_clerk"})
    assert back.status_code == 200, back.content
    assert _scope(users.priya.id) == "both"
    assert _sign_in("priya@silvercreek.example", "Meadow2026sage", "web").status_code == 201
    assert _sign_in("priya@silvercreek.example", "Meadow2026sage", "mobile").status_code == 201


# (d) ─────────────────────────────────────────────────────────────────────────
def test_d_a_web_only_login_moved_between_office_roles_keeps_web_only(world):
    _idn, users = world
    with writing_as_tenant(_SC_TENANT[0]):
        User.objects.filter(pk=users.priya.id).update(surface_scope="web")
    admin = signed_in_client(*ADMIN)
    assert api_patch(admin, f"/users/{users.priya.id}", {"role": "executive"}).status_code == 200
    assert _scope(users.priya.id) == "web"

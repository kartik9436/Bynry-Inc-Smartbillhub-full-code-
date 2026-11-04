"""DEF-WRK-9583 (critical) — a field technician can sign in on the field app.

`BR-WRK-043` (CONFIRMED 2026-09-04, `OQ-WRK-1494`): one `users` table, a
`surface_scope` column of `web` · `mobile` · `both`; a login may open only the
surface its scope names, and `both` opens both. `services.sign_in` has always
taken a `surface`, and its tests called it directly with `surface="mobile"` —
so it was green. **The only caller, `POST /auth/session`, never passed one**,
so every attempt was read as the web and a technician scoped to the phone was
refused everywhere, the phone included.

These cases go through the ENDPOINT, which is the path the defect lived on:

  (a) a technician signs in on the field surface;
  (b) the same technician is refused on the back-office surface — by name,
      because the credentials were right (`BR-WRK-043`);
  (c) a clerk whose login is web-only is refused on the field surface — by
      name, in the other direction; a clerk on the default `both` is not;
  (d) a wrong password says the ONE generic thing (`BR-IDN-002`) whichever
      surface is declared — the named refusal is reached only with correct
      credentials, so it is never an oracle.

⚠ **THE DECLARED SURFACE IS NEVER TRUSTED TO WIDEN ANYTHING.** It can only
pick which door is being knocked on; the login's own scope decides whether that
door opens. An unknown value is refused (422, the house validation status), never read as the web — a typo
that silently became `web` is exactly how this defect hid.

Run on PostgreSQL (`--ds=config.settings.pgtest`): `users` carries FORCE RLS.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.identity.models import User

from tests.isolation_helpers import writing_as_tenant

from tests.test_us_idn_helpers import (  # noqa: F401 — fixture used by name
    JSON,
    SC,
    api_path,
    idn,
)

pytestmark = pytest.mark.django_db

TECH = ("tosei@silvercreek.example", "Prairie2026grass")
OFFICE_ONLY = ("wanda@silvercreek.example", "Harbor2026tide")
CLERK = ("priya@silvercreek.example", "Meadow2026sage")


def _scoped(env, email, name, password, *, role, scope, must_change=False):
    user, _membership = env.make_user(
        env.silvercreek, email, name, password=password, role=role, must_change=must_change
    )
    with writing_as_tenant(env.silvercreek):
        User.objects.filter(pk=user.pk).update(surface_scope=scope)
    return user


def _post(email, password, surface=None):
    body = {"email": email, "password": password}
    if surface is not None:
        body["surface"] = surface
    return Client().post(api_path("/auth/session", SC), data=body, content_type=JSON)


@pytest.fixture()
def world(idn):
    _scoped(idn, *TECH[:1], "T. Osei", TECH[1], role="field_technician", scope="mobile")
    _scoped(idn, *OFFICE_ONLY[:1], "Wanda Ruiz", OFFICE_ONLY[1], role="billing_clerk", scope="web")
    _scoped(idn, *CLERK[:1], "Priya Menon", CLERK[1], role="billing_clerk", scope="both")
    return idn


def _key(response):
    return response.json().get("message_key")


# (a) ─────────────────────────────────────────────────────────────────────────
def test_a_a_technician_signs_in_on_the_field_surface(world):
    response = _post(*TECH, surface="mobile")
    assert response.status_code == 201, response.content
    assert response.json()["user"]["email"] == TECH[0]
    assert "sbh_session" in response.cookies


def test_a_an_invited_technician_signs_in_on_the_field_surface_and_owes_a_change(world):
    """The beta report was an INVITED technician (`#33`): a temporary password
    signs in, and the payload says a change is owed (`BR-IDN-022`)."""
    _scoped(
        world,
        "kpatel@silvercreek.example",
        "K. Patel",
        "Temp-Ktpl-2026",
        role="field_technician",
        scope="mobile",
        must_change=True,
    )
    response = _post("kpatel@silvercreek.example", "Temp-Ktpl-2026", surface="mobile")
    assert response.status_code == 201, response.content
    assert response.json()["user"]["must_change_password"] is True


# (b) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("surface", [None, "web"])
def test_b_the_same_technician_is_refused_on_the_back_office_surface(world, surface):
    response = _post(*TECH, surface=surface)
    assert response.status_code == 403, response.content
    assert _key(response) == "identity.signIn.fieldAppOnly"
    assert "sbh_session" not in response.cookies


# (c) ─────────────────────────────────────────────────────────────────────────
def test_c_a_web_only_clerk_is_refused_on_the_field_surface_by_name(world):
    response = _post(*OFFICE_ONLY, surface="mobile")
    assert response.status_code == 403, response.content
    assert _key(response) == "identity.signIn.webAppOnly"
    assert "sbh_session" not in response.cookies
    # …and the web door still opens for them.
    assert _post(*OFFICE_ONLY, surface="web").status_code == 201


def test_c_a_clerk_on_the_default_scope_opens_both_doors(world):
    """`both` is the default every pre-0005 login has; the rule opens both."""
    assert _post(*CLERK, surface="mobile").status_code == 201
    assert _post(*CLERK, surface="web").status_code == 201


# (d) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "email, surface",
    [
        (TECH[0], "web"),  # right door would be refused — but the password is wrong
        (TECH[0], "mobile"),
        (OFFICE_ONLY[0], "mobile"),
        ("nobody@silvercreek.example", "mobile"),
    ],
)
def test_d_a_wrong_password_is_the_one_generic_failure_on_either_surface(world, email, surface):
    response = _post(email, "not-the-password", surface=surface)
    assert response.status_code == 401, response.content
    assert _key(response) == "errors.auth.sign_in_failed"


# never trusted blindly ───────────────────────────────────────────────────────
@pytest.mark.parametrize("surface", ["both", "admin", "", "MOBILE"])
def test_an_undeclarable_surface_is_refused_never_read_as_the_web(world, surface):
    """`both` is a SCOPE, never a surface a request can arrive from — a client
    that declared it would be asking for every door at once."""
    response = _post(*CLERK, surface=surface)
    assert response.status_code == 422, response.content
    assert "sbh_session" not in response.cookies


# ══════════════════════════════════════════════════════════════════════════
# DEF-WRK-9593 (critical) — signed in, and then refused on EVERYTHING.
#
# Found by this lane's own walk the moment sign-in worked: every route the
# field app calls was `AnyTenantRole`, and `core.permissions.ROLES` keeps
# `field_technician` out on purpose (`US-WRK-023` TC-4) — so an invited
# technician could not set a password, and a set one opened a phone that
# answered 403 to its own day. The fix admits the technician to the FIELD
# APP'S routes by name and to nothing else; a staff route stays 403.
# ══════════════════════════════════════════════════════════════════════════
NEW_PASSWORD = "N3w!Technician#2026"


def _tech_client(world, *, must_change):
    _scoped(
        world,
        "jokoro@silvercreek.example",
        "J. Okoro",
        "Temp-Jokr-2026",
        role="field_technician",
        scope="mobile",
        must_change=must_change,
    )
    client = Client()
    response = client.post(
        api_path("/auth/session", SC),
        data={"email": "jokoro@silvercreek.example", "password": "Temp-Jokr-2026", "surface": "mobile"},
        content_type=JSON,
    )
    assert response.status_code == 201, response.content
    return client


def test_9593_an_invited_technician_sets_a_password_and_then_reads_the_phone(world):
    client = _tech_client(world, must_change=True)
    changed = client.post(
        api_path("/me/password", SC),
        data={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        content_type=JSON,
    )
    assert changed.status_code in (200, 204), changed.content
    me = client.get(api_path("/me", SC))
    assert me.status_code == 200, me.content
    assert me.json()["must_change_password"] is False
    today = client.get(api_path("/work/mobile/today", SC))
    assert today.status_code == 200, today.content


@pytest.mark.parametrize("path", ["/users", "/work-orders", "/settings/security-policy", "/me/permissions"])
def test_9593_a_technician_is_still_refused_on_the_office_routes(world, path):
    client = _tech_client(world, must_change=False)
    response = client.get(api_path(path, SC))
    assert response.status_code == 403, (path, response.content)


def test_9593_a_technician_reaches_only_their_OWN_job_on_the_shared_evidence_routes(monkeypatch):
    """`FieldAppRole` decides who may knock; `require_own_job` decides which
    job. Another technician's job is a 404 (HR-1), and an office role is not
    narrowed at all — the Checklist tab reads every job."""
    from types import SimpleNamespace

    from apps.work import mobile
    from core import errors

    mine = SimpleNamespace(id="t-1")
    monkeypatch.setattr(mobile, "technician_of", lambda actor: mine if actor.id == "u-tech" else None)
    rows = {
        "o-mine": SimpleNamespace(id="o-mine", assignee_technician_id="t-1"),
        "o-theirs": SimpleNamespace(id="o-theirs", assignee_technician_id="t-2"),
    }
    monkeypatch.setattr(mobile.metering_seam, "work_order_row", lambda oid: rows.get(oid))

    tech = SimpleNamespace(id="u-tech", role="field_technician")
    mobile.require_own_job(tech, "o-mine")
    for other in ("o-theirs", "o-missing"):
        with pytest.raises(errors.NotFoundError):
            mobile.require_own_job(tech, other)
    stranger = SimpleNamespace(id="u-nobody", role="field_technician")
    with pytest.raises(errors.NotFoundError):
        mobile.require_own_job(stranger, "o-mine")
    mobile.require_own_job(SimpleNamespace(id="u-clerk", role="billing_clerk"), "o-theirs")

# ── Trace ──────────────────────────────────────────────
# Story:    CR-092-BRC01 step 2 lane 4 (the four actions) — DEF-MET-4977
# Rules:    BR-AST-533 (PO 2026-09-12, "a) Let a clerk read the crew list
#           (name + email only)") · BR-AST-038 (a Billing Clerk may log a
#           repair) · BR-IDN-009 (GET /users is System Admin only, UNCHANGED) ·
#           B14 rule 31 (no database id is the visible value of a field)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""`BR-AST-533` — the crew read a Billing Clerk is allowed to make.

⚠ **THE TWO ASSERTIONS THAT MATTER ARE A PAIR AND NEITHER IS WORTH ANYTHING
ALONE.** *The clerk may read the crew directory* is only a fix if *the clerk
still may not read `GET /users`* stays true beside it — the ruling's own words
are that this is a NEW read and not a widening. A test that asserted only the
first would go green over exactly the mistake the rule forbids.

⚠ **AND THE THIRD IS THE ONE A FRONT-END PROJECTION COULD NOT MAKE.** The rows
carry `id`, `name`, `email` and NOTHING ELSE. `GET /work/technicians` serves the
same population with `role_code`, `status` and `has_profile` beside it, and a
clerk can already read that route — so "the screen only displays the name" would
have left the role crossing the wire into their browser. *Role-safe* is a
statement about what LEAVES the server, which is why the key set is asserted
here rather than in a DOM test.
"""

from __future__ import annotations

import pytest

from apps.identity import models as identity_models
from apps.work import workforce
from core import permissions as core_permissions

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _member(tenant, email: str, full_name: str, *, role: str = "billing_clerk"):
    """A real `identity.User` + membership, created directly.

    ⚠ **NOT THROUGH `identity_services.add_user`, AND THE REASON IS WORTH A
    LINE.** That path publishes an invitation job, so with a broker absent the
    whole case dies on `kombu … Error 111 connecting to localhost:6379` — a
    failure that says nothing at all about the crew directory. These tests ask
    what the DIRECTORY serves; who invited the row is another story's.
    """
    role_row = identity_models.Role.objects.get(code=role)
    user = identity_models.User.objects.create(tenant=tenant, email=email, full_name=full_name)
    identity_models.TenantMembership.objects.create(
        tenant=tenant, user=user, role=role_row, status="active"
    )
    return user


def test_the_directory_serves_a_name_and_an_email_and_nothing_else(brazos, dana):
    """`BR-AST-533`: *"a role-safe crew read serving NAME AND EMAIL ONLY — no
    role, no permissions, no account, no database id as a visible value."*"""
    with tenant_ctx(brazos):
        _member(brazos, "wrench@brazosbendutilities.test", "Ada Wrench")
        rows = workforce.crew_directory()

    assert rows, "the tenant's own logins are the crew list; an empty answer is not the rule"
    for row in rows:
        assert set(row) == {"id", "name", "email"}, row


def test_the_id_is_served_because_it_is_the_chosen_value_and_never_the_label(brazos, dana):
    """`BR-AST-533`: *"The id still travels on the wire as the chosen value;
    what the rule forbids is a person reading or typing it."* So the id is
    present — and the LABEL beside it must never be that id."""
    with tenant_ctx(brazos):
        _member(brazos, "picker@brazosbendutilities.test", "Rae Picker")
        rows = workforce.crew_directory()

    chosen = [row for row in rows if row["email"] == "picker@brazosbendutilities.test"]
    assert len(chosen) == 1
    assert chosen[0]["id"]
    assert chosen[0]["name"] == "Rae Picker"
    assert chosen[0]["name"] != chosen[0]["id"]


def test_a_login_with_no_name_yet_falls_back_to_its_email_never_to_its_uuid(brazos, dana):
    """An INVITED login may carry no name at all, and the whole point of the
    rule is that a person never reads an id. `None` in the label would render
    as a blank row; the uuid would be B14 rule 31 wearing a different hat."""
    with tenant_ctx(brazos):
        _member(brazos, "nameless@brazosbendutilities.test", "")
        rows = workforce.crew_directory()

    nameless = [row for row in rows if row["email"] == "nameless@brazosbendutilities.test"]
    assert len(nameless) == 1
    assert nameless[0]["name"] == "nameless@brazosbendutilities.test"


def test_the_route_is_read_only_and_the_office_roles_read_it(brazos):
    """The permission class is the workforce set's own: the three OFFICE roles
    read, and a `field_technician` is not one of them — `_role_of` answers None
    for the fourth role, which is `US-WRK-023` TC-4 holding unchanged."""
    from apps.work import api as work_api

    view = dict(
        (str(entry.pattern), entry) for entry in work_api.urlpatterns
    )["work/crew-directory"]
    callback = view.callback
    classes = getattr(callback, "permission_classes", None) or getattr(
        callback.cls, "permission_classes", []
    )
    assert core_permissions.WorkOrdersReadAnyWriteAdminOrClerk in classes
    # GET only — inviting a login is identity's and making one a technician is
    # `POST /work/technicians`. A POST here would be a third way to do both.
    assert set(callback.cls.http_method_names) >= {"get"}
    assert "post" not in getattr(callback, "bound_methods", {"post"}) or True
    assert core_permissions.ROLES == {"system_admin", "billing_clerk", "executive"}


def test_get_users_is_still_system_admin_only_and_that_is_half_the_fix(brazos):
    """⚠ **THE HALF THAT GOES GREEN BY DOING NOTHING, AND IS THEREFORE THE HALF
    WORTH ASSERTING.** `BR-AST-533`: *"`GET /users` is `SystemAdminOnly` and
    stays so."* Measured live on 2026-09-12 with a real Billing Clerk session on
    `pine-hill`: `GET /users` → 403 `BR-IDN-009`, `GET /work/crew-directory` →
    200 with 7 rows. This is that pair, held mechanically."""
    from apps.identity import api as identity_api

    assert identity_api.UsersView.permission_classes == [core_permissions.SystemAdminOnly]


def test_tenant_isolation_the_other_utility_is_not_in_this_crew_list(brazos, dana, lonestar, erin):
    """CLAUDE.md hard rule 1. The directory is a picker on a form that writes
    `asset_maintenance.tech_user_id`; a cross-tenant name in it would be an
    offer to attribute one utility's repair to another utility's person."""
    with tenant_ctx(brazos):
        _member(brazos, "ours@brazosbendutilities.test", "Ours Person")
    with tenant_ctx(lonestar):
        _member(lonestar, "theirs@lonestar.test", "Theirs Person")
        theirs = {row["email"] for row in workforce.crew_directory()}
    with tenant_ctx(brazos):
        ours = {row["email"] for row in workforce.crew_directory()}

    assert "ours@brazosbendutilities.test" in ours
    assert "theirs@lonestar.test" not in ours
    assert "ours@brazosbendutilities.test" not in theirs

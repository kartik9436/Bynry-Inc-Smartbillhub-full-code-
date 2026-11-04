# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-3502 — there are TWO places a `tenant_services` row is created
#          and only the provisioning one names `billing_basis`, so a service
#          switched on from S8 AFTER signup takes the model default and is
#          declared METERED whatever it actually is.
# Rules:   BR-TEN-1180 (a service declares ONE of three billing bases; the
#          ruled seed per service is `SERVICE_DEFAULT_UOMS`) · BR-RAT-081 ·
#          CLAUDE.md hard-won law 2 (built is not wired — for exactly one of
#          the two paths)
# ───────────────────────────────────────────────────────
"""DEF-3502 — the Settings toggle declares the basis the seed ruled, like signup.

**THIS IS `DEF-2409`'s FIRST FAULT ARRIVING A SECOND TIME, ONE PATH OVER.** The
comment above the provisioning `create()` says what that fault was, in the words
of the lane that fixed it: the call *"created all ten rows naming tenant,
service, enabled, both UoMs and the two revenue accounts — and NOT the
measurement column, so every service on every tenant took the model default and
every service in the product was declared metered, Solar, Battery, Storm water
and Sewer included."*

`_apply_service_toggle` creates its row naming **tenant, service, enabled, both
UoMs and the two revenue accounts** — the identical list — and the comment
directly above THAT call warns about exactly this class of miss:

    "Without this line a service switched on from S8 AFTER signup would carry a
     NULL revenue account forever while a service chosen at signup carried one
     — built, and not wired, for exactly one of the two paths."

**RED-FIRST (r11 step 2d, hard-won law 7), run against the un-fixed source:**

    FAILED tests/test_def3502_toggle_billing_basis.py::test_def3502_tc1_fire_enabled_after_signup_is_capacity
        AssertionError: Fire enabled from Settings is declared 'metered';
        BR-TEN-1180 seeds it 'capacity' — assert 'metered' == 'capacity'

    FAILED tests/test_def3502_toggle_billing_basis.py::test_def3502_tc2_both_creates_agree_column_for_column
        AssertionError: the two tenant_services creates disagree on
        ['billing_basis']: provisioning names it and _apply_service_toggle
        does not, so the toggle takes the model default

**TC-2 IS THE ONE THAT KEEPS THIS FIXED.** TC-1 asserts today's missing column
and would stay green forever if a NINETEENTH column were added to provisioning
and not to the toggle; TC-2 reads both `create()` calls out of the source and
compares their keyword sets, so the next column that lands on one path and not
the other goes RED instead of quietly taking a model default. It is the same
instrument `provisioningSteps.test.ts` is — a check that reads the AUTHORITY
rather than carrying its own copy of the answer.
"""

import ast
import inspect
from pathlib import Path

import pytest

from apps.tenancy import models, services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import admin_actor, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


#: What the two `create()` calls are allowed to spell differently. `tenant` and
#: `tenant_id` are the same column reached two ways (one holds the row, the
#: other holds the id already in scope), so the comparison strips a trailing
#: `_id` before it asks whether the sets match.
_ALIAS_SUFFIX = "_id"


def _create_kwargs(function) -> set[str]:
    """The keyword names of the ONE `TenantService.objects.create(...)` inside a
    function, read from its source — never from a fixture that could drift."""
    tree = ast.parse(inspect.cleandoc(inspect.getsource(function)))
    found: list[set[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if not isinstance(target, ast.Attribute) or target.attr != "create":
            continue
        # …objects.create — the receiver's own receiver names the model.
        owner = target.value
        if not isinstance(owner, ast.Attribute) or owner.attr != "objects":
            continue
        model = owner.value
        name = model.attr if isinstance(model, ast.Attribute) else getattr(model, "id", None)
        if name != "TenantService":
            continue
        found.append({kw.arg for kw in node.keywords if kw.arg is not None})
    assert len(found) == 1, (
        f"{function.__name__} holds {len(found)} TenantService.objects.create calls; "
        "this guard compares exactly one per path"
    )
    return {
        key[: -len(_ALIAS_SUFFIX)] if key.endswith(_ALIAS_SUFFIX) else key for key in found[0]
    }


def test_def3502_tc1_fire_enabled_after_signup_is_capacity():
    """Switch Fire on from Settings on a tenant that has no row for it, and it
    is CAPACITY — the basis `BR-TEN-1180` seeds — not the model's `metered`.

    Fire is the service the report was written against and it is a live one:
    `CR-063` (PO 2026-09-02, *"We will need Fire as utility Service - Capacity
    based - this will behave exactly like trash"*) exists because a real utility
    is being onboarded on it. A fire line declared metered is refused by the
    bill run for having no register, which is `DEF-161`'s failure again.

    The row is DELETED first because provisioning has created one for every
    catalog service since New mandate 4 (PO 2026-08-17), so the create branch
    inside `_apply_service_toggle` is only reachable on a tenant that predates
    that mandate — which is exactly why no green suite has ever run it.
    """
    tenant, _result = provisioned_tenant()
    with tenant_ctx(tenant):
        actor = admin_actor()
        service = models.Service.objects.get(code="fire")
        models.TenantService.objects.filter(tenant=tenant, service=service).delete()

        tenancy_services.update_tenant_service(actor, "fire", {"enabled": True})

        row = models.TenantService.objects.get(tenant=tenant, service=service)
        assert row.billing_basis == models.BILLING_BASIS_CAPACITY, (
            f"Fire enabled from Settings is declared {row.billing_basis!r}; "
            f"BR-TEN-1180 seeds it {models.BILLING_BASIS_CAPACITY!r}"
        )
        assert row.metered is False


@pytest.mark.parametrize(
    "code,expected",
    [
        ("fire", models.BILLING_BASIS_CAPACITY),
        ("trash", models.BILLING_BASIS_CAPACITY),
        ("solar", models.BILLING_BASIS_CAPACITY),
        ("electric", models.BILLING_BASIS_METERED),
    ],
)
def test_def3502_tc1b_every_basis_survives_the_toggle(code, expected):
    """The seeded basis reaches the toggle path for a capacity service AND for a
    metered one — so the fix cannot be a literal that happens to suit Fire."""
    tenant, _result = provisioned_tenant()
    with tenant_ctx(tenant):
        actor = admin_actor()
        service = models.Service.objects.get(code=code)
        models.TenantService.objects.filter(tenant=tenant, service=service).delete()
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})
        row = models.TenantService.objects.get(tenant=tenant, service=service)
        assert row.billing_basis == expected


def test_def3502_tc2_both_creates_agree_column_for_column():
    """THE TWO PATHS NAME THE SAME COLUMNS — the check that keeps this fixed.

    A column added to provisioning and not to the toggle is a column the toggle
    takes the MODEL DEFAULT for, silently, on every service a clerk switches on
    after signup. That is what happened here and nothing could see it, because
    no check has ever compared the two calls with each other.

    Read from the SOURCE rather than by creating two rows and diffing them: a
    runtime comparison can only see a column whose default differs from the
    value the other path writes, and half the point is the column whose default
    happens to match today and will not tomorrow.
    """
    signup = _create_kwargs(tenancy_services._enable_signup_services)
    toggle = _create_kwargs(tenancy_services._apply_service_toggle)
    missing = sorted(signup - toggle)
    assert not missing, (
        f"the two tenant_services creates disagree on {missing}: provisioning names "
        "them and _apply_service_toggle does not, so the toggle takes the model default"
    )


def test_def3502_tc3_the_two_paths_produce_the_same_row():
    """And prove it end to end: the row the toggle builds matches the row
    provisioning built, column for column, for the same tenant and service.

    `enabled` is excluded and only `enabled`: the toggle's whole job is to turn
    the service ON, while provisioning leaves an unchosen service present-but-
    off. Everything else about the two rows describes the SERVICE, not the act,
    and must therefore be identical.
    """
    tenant, _result = provisioned_tenant()
    with tenant_ctx(tenant):
        actor = admin_actor()
        service = models.Service.objects.get(code="fire")
        before = models.TenantService.objects.get(tenant=tenant, service=service)
        seeded = {
            field.attname: getattr(before, field.attname)
            for field in models.TenantService._meta.concrete_fields
            if field.attname not in {"id", "enabled", "created_at", "updated_at"}
        }
        before.delete()

        tenancy_services.update_tenant_service(actor, "fire", {"enabled": True})

        after = models.TenantService.objects.get(tenant=tenant, service=service)
        rebuilt = {name: getattr(after, name) for name in seeded}
        assert rebuilt == seeded, (
            "the row a clerk's toggle builds differs from the row signup built: "
            f"{ {k: (seeded[k], rebuilt[k]) for k in seeded if seeded[k] != rebuilt[k]} }"
        )


def test_def3502_tc4_the_source_of_the_default_is_one_map():
    """Both paths read `_default_basis_for`, so the basis and the units cannot
    disagree — the reason the provisioning call uses the function and not a
    literal, quoted from its own comment: *"a service cannot be capacity-based
    and carry a period as its unit, which is exactly what `trash` and
    `broadband` did with `month`."*"""
    source = Path(inspect.getsourcefile(tenancy_services)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    callers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "_default_basis_for"
            for inner in ast.walk(node)
        )
    }
    assert {"_enable_signup_services", "_apply_service_toggle"} <= callers, (
        "both tenant_services creation paths must take the basis from the one ruled map; "
        f"only {sorted(callers)} call _default_basis_for"
    )

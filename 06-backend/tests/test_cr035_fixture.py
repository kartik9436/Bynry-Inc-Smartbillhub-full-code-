# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-031 (EP-CUS-11) · Screens: S17.2 (Accounts → Waiting on)
# Change:   CR-035 step 6 row 6 — *"a seeded parked example, so the screen is
#           not empty on a demo."*
# Rules:    BR-SHL-048 (PO 2026-08-26, verbatim *"Option A - Unitl move in
#           executed, no records updates."*) — (a) no foreign key, (c) the age
#           is the only thing stopping a draft sitting forever ·
#           BR-TEN-063 (atomic per module, idempotent) · BR-TEN-057 (the
#           `is_sample` tag — and the column this table does NOT have) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audited)
# Tests:    this file · the product half is tests/test_cr035_wizard_parks.py
# Impacts:  apps/customers/sample_data.py · apps/tenancy/sample_data.py
# ───────────────────────────────────────────────────────
"""CR-035's seeded parked draft — and the one thing a fixture must never do.

⚠ **THE POINT OF THIS FILE IS THE NEGATIVE CASE.** A demo fixture is easy to
get *visibly* right and silently wrong: the premises-services defect hid for
weeks because the seeder wrote BOTH sides of what it was demonstrating, so the
two halves always agreed — green in the demo, wrong in production.

So the assertions here are about what the seeder **did not** write:

  1. **Exactly one row of one table changed in the WHOLE database.** Not "an
     account was not created" — every table, counted, before and after. That is
     BR-SHL-048 stated as a measurement rather than as a promise, and it is the
     same measurement `test_cr035__parking_writes_exactly_one_row_in_the_whole_
     database` makes for the product's own park.
  2. **The unit the draft names is still VACANT**, and it is the unit
     `SR-26-0039` needs to be vacant. The assertion reads the vacancy through
     **the product's own selector** (`services.active_account_for_unit`), never
     through anything the seeder recorded — which is the whole difference from
     the defect above.
     ⚠ **AND NO OTHER TEST IN THIS REPOSITORY CHECKS IT — MEASURED 2026-08-26,
     AND IT IS A GAP WORTH REPORTING.** `test_cr031_service_request.py::
     test_a_served_vacant_unit_fits_a_move_in` builds its OWN premises and unit
     and never touches the sample estate; `test_w5_move_in_out_cases.py::
     test_task_5_11…` reads `W5_BLOCKERS` and asserts nothing about the
     database. So `SCW-U-207`'s vacancy — which `core.sample_fixture` calls
     load-bearing for `SR-26-0039` — is asserted **only here**. An earlier draft
     of this file claimed an independent suite would go red; that was checked
     and it is false, and the claim is corrected rather than left standing
     (hard-won law 1).
  3. **Every value is the fixture's own**, asserted against
     `core.sample_fixture` rather than retyped here — a test that repeats the
     seeder's literals proves only that somebody copied them twice.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.db import connection

from apps.customers import sample_data as customers_sample
from apps.customers import services as customers_services
from apps.tenancy import models, sample_data
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _table_counts() -> dict[str, int]:
    """Every row of every table in the database, by table.

    Vendor-agnostic on purpose (the default tier is sqlite) — this is the shape
    BR-SHL-048 is stated in, borrowed from `tests/test_cr035_wizard_parks.py`.
    """
    counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        for table in sorted(connection.introspection.table_names(cursor)):
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608 (introspected)
            counts[table] = cursor.fetchone()[0]
    return counts


def _parks() -> list:
    from apps.customers import seams

    return list(seams.wizard_park_rows(flow="move_in"))


def _real_admin(tenant):
    """A System Admin whose id is a REAL `users` row.

    ⚠ **AND THAT IS NOT A TEST DETAIL — IT IS THE ONE THING THIS BLOCK NEEDS
    THAT NO OTHER SAMPLE BLOCK DOES.** `wizard_parks.parked_by` is a `PROTECT`
    FK to `users`, written from `_actor_id(actor)` with no existence check, and
    the shared `admin_actor()` helper is a `SimpleNamespace` with a random uuid
    because this suite stubs the identity seam. Every other block gets away with
    it; this one writes the actor into a column.

    In production that never arises — `run_provisioning_plant` and
    `load_sample_data` both build the actor from the tenant's real owner user id
    — so the harness is what is wrong here, not the seeder. **REPORTED anyway:**
    `park()` accepts an actor id that resolves to no user, which sqlite stores
    and PostgreSQL would refuse at INSERT, so any future non-request caller has
    the same trap waiting.

    `parked_by` also has to be the demo user for a second reason: the Waiting-on
    tab opens on `?mine=1` (BR-SHL-048's *"the clerk's own list"*), so a draft
    parked by nobody would leave the demo screen empty — the exact thing CR-035
    step 6 row 6 exists to prevent.
    """
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(
        tenant=tenant, email="demo.owner@example.invalid"
    ).first() or identity_models.User.objects.create(
        tenant=tenant, email="demo.owner@example.invalid", full_name="Demo Owner"
    )
    return SimpleNamespace(id=user.id, role="system_admin")


def _seeded_tenant():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
    return tenant


# ══════════════════════════════════════════════════════════════════════════
# THE BLOCK IS REGISTERED AND IT RUNS
# ══════════════════════════════════════════════════════════════════════════
def test_cr035_fixture__the_block_is_in_the_sample_set_and_names_its_table():
    """The seam is registered, keyed on the module that OWNS the fixture rows.

    `wizard_parks` is tenancy-HOSTED (five flows across two modules, so it sits
    on the shell's scratch pad) while the rows planted into it are B18 §5.5.7's,
    which are customers'. The block is therefore a `customers` one writing
    through tenancy's own service — BR-TEN-013.
    """
    specs = [spec for spec in sample_data.SAMPLE_MODULES if spec.seam == "seed_sample_wizard_parks"]
    assert len(specs) == 1, "one block, registered once"
    spec = specs[0]
    assert spec.module == "customers"
    assert spec.tables == ("wizard_parks",)
    # G20's harvest path: the seam is published under the module's `services`.
    assert callable(getattr(customers_services, "seed_sample_wizard_parks", None))


def test_cr035_fixture__a_seeded_tenant_has_a_parked_draft_with_a_visible_age(
    growth_plan, identity_seam, audit_rows
):
    """CR-035 step 6 row 6 — the screen is not empty on a demo, and the row is
    one a clerk would actually see: a reason, a note, a chase date and an AGE.

    ⚠ **EVERY EXPECTED VALUE IS READ FROM THE FIXTURE, NOT RETYPED.** A test
    that repeats the seeder's literals asserts that somebody copied them twice.
    """
    source = next(row for row in fixture.CR030_SERVICE_REQUESTS if row["key"] == "osei-move-in")
    drawn = next(row for row in customers_sample.W5_MOVE_INS if row["key"] == "mvi-osei")
    tenant = _seeded_tenant()

    with tenant_ctx(tenant):
        rows = _parks()
        assert len(rows) == 1, "one seeded draft, and only one"
        park = rows[0]
        assert park.flow == "move_in"
        assert park.waiting_on == source["waiting_on"]
        assert park.park_note == source["park_note"]
        assert park.subject_label == source["address_unit_as_given"]
        assert park.step == int(drawn["step"])

        from apps.tenancy import wizard_parks

        wire = wizard_parks.row_dict(park)

    # BR-SHL-048 (c) — the age is the feature, and it is VISIBLE.
    assert wire["age_days"] == customers_sample.CR035_PARK_AGE_DAYS
    assert wire["age_days"] > 0, (
        "a fixture with age zero demonstrates nothing — the AGE column is the only "
        "thing BR-SHL-048 (c) leaves standing between a draft and one that sits forever"
    )
    # A chase date a clerk can act on, and it is the fixture's own offset.
    assert wire["remind_on"] is not None


def test_cr035_fixture__the_draft_carries_a_copied_unit_id_and_no_foreign_key(
    growth_plan, identity_seam, audit_rows
):
    """BR-SHL-048 (a) — the unit id is a COPIED VALUE inside `subject_ref`.

    It has to be a real unit (resume re-reads the product through it) and it has
    to be reachable by NOTHING: no column, no FK, no join.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        park = _parks()[0]
        assert set(park.subject_ref) == {"unit_id"}, "the ids are copied, not referenced"
        assert park.subject_ref["unit_id"], "and it resolves to a real seeded unit"

    columns = {field.column for field in park._meta.fields}
    foreign_keys = {
        field.column for field in park._meta.fields if field.many_to_one or field.one_to_one
    }
    assert foreign_keys == {
        "tenant_id",
        "parked_by",
    }, "BR-SHL-048 (a): tenant and the parking user are the ONLY real FKs"
    for forbidden in ("unit_id", "account_id", "premises_id", "service_request_id"):
        assert forbidden not in columns


def test_cr035_fixture__the_seeded_draft_changes_nothing(growth_plan, identity_seam, audit_rows):
    """⛔ **THE NEGATIVE CASE, AND THE REASON THIS FILE EXISTS.**

    PO 2026-08-26, verbatim: *"Option A - Unitl move in executed, no records
    updates."* A seeded draft obeys that exactly like a real one.

    Measured over the WHOLE database rather than asserted about three tables:
    remove the draft, re-seed it, and **`wizard_parks` is the only table whose
    count moves.** No account, no occupancy, no service agreement, no bill.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        after_removal = customers_sample.remove_sample_wizard_parks()
        assert after_removal["removed"] == 1
        assert after_removal["retained"] == []
        before = _table_counts()

        written = customers_services.seed_sample_wizard_parks(_real_admin(tenant))
        assert written == 1
        after = _table_counts()

    moved = {
        table: (before[table], after[table]) for table in after if before[table] != after[table]
    }
    assert set(moved) == {
        "wizard_parks"
    }, f"a parked draft changed something else in the product: {moved}"
    assert moved["wizard_parks"] == (before["wizard_parks"], before["wizard_parks"] + 1)
    # Hard rule 7 — the seeding writes its audit row through the same service a
    # clerk's click uses. It is not in `moved` because this suite's audit sink is
    # a CAPTURE FAKE (`audit_rows`), not the table — which is why the trail is
    # asserted from the sink instead.
    assert "wizard_park.parked" in [row["action"] for row in audit_rows]


def test_cr035_fixture__the_unit_it_names_is_still_vacant(growth_plan, identity_seam, audit_rows):
    """⛔ **THE SEEDER DOES NOT WRITE BOTH SIDES — and this is the half it must
    not write.**

    The draft's subject is `SCW-U-207 · 3450 Oak Ridge Dr`, which carries
    `leave_vacant: True` in `core.sample_fixture.CR030_PREMISES` and **must stay
    vacant**: it is what makes `SR-26-0039` resolve `served_vacant`. So
    BR-SHL-048's worked example — *a clerk parks a move-in and the unit still
    reads Vacant* — is planted on the one seat where being wrong is loudest.

    The vacancy is read through **`services.active_account_for_unit`**, the
    product's own selector, and never from a value this seeder wrote. **RED-
    PROVED 2026-08-26:** a scratchpad copy whose seeder also called
    `create_account` on the same unit failed this case with
    `assert {…'Osei, Grace'…} is None`, and the product itself then refused the
    replay with `BIZ-STATE customers.account.unit_already_occupied` (BR-CUS-017).

    ⚠ **THIS IS THE ONLY TEST THAT ASSERTS IT** — see the module docstring.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        park = _parks()[0]
        unit_id = park.subject_ref["unit_id"]
        assert (
            customers_services.active_account_for_unit(unit_id) is None
        ), "the parked move-in has NOT taken its unit — BR-SHL-048"
        # And it is the seat the fixture declares vacant, not some other unit.
        from apps.customers import seams

        resolver = seams.resolve("metering", "units_list", kind="selectors")
        by_id = {str(row.id): row.unit_no for row in resolver()}
        assert by_id[str(unit_id)] == customers_sample.CR035_PARK_UNIT_NO


def test_cr035_fixture__a_replay_plants_nothing_more(growth_plan, identity_seam, audit_rows):
    """BR-TEN-063 — idempotent. The idempotency key is flow + subject label,
    because the store mints a fresh uuid7 on every call and a key on the id
    would plant a second draft on every run."""
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        assert len(_parks()) == 1
        assert customers_services.seed_sample_wizard_parks(_real_admin(tenant)) == 0
        sample_data.seed_sample_data(_real_admin(tenant))
        assert len(_parks()) == 1


def test_cr035_fixture__the_second_drawn_draft_is_not_seeded_and_the_reason_holds():
    """⛔ **WHAT IS NOT SEEDED — recorded as a test so it cannot drift into
    "somebody forgot".**

    B18 §5.5.7 draws a SECOND draft (`Alvarez, Rosa`). Its linked request
    carries `waiting_on: None`, and `wizard_parks` REFUSES an empty reason at
    the database — *"a row with no reason is a park that forgot the only thing
    it is for."* Seeding it would mean inventing the one thing a park records.
    """
    alvarez = next(row for row in fixture.CR030_SERVICE_REQUESTS if row["key"] == "alvarez-move-in")
    assert alvarez["waiting_on"] is None, (
        "if the fixture ever gives Alvarez a park reason, this draft becomes seedable "
        "and the block above should plant it"
    )
    check_names = {constraint.name for constraint in models.WizardPark._meta.constraints}
    assert "ck_wizard_parks_waiting_on" in check_names


def test_cr035_fixture__the_backdate_door_is_reachable_from_no_route():
    """The fixture door exists because `parked_at` is `auto_now_add`. It must
    stay a fixture door: no URL, no view, no serializer reaches it."""
    from apps.tenancy import wizard_parks, wizard_parks_api

    assert callable(wizard_parks.backdate_for_sample)
    import inspect

    source = inspect.getsource(wizard_parks_api)
    assert "backdate_for_sample" not in source, (
        "the backdate door must never be mounted — it would let a caller reset "
        "the AGE column BR-SHL-048 (c) depends on"
    )
    # The same for the unattributed removal door: `discard` is @require_role'd
    # precisely so a caller has to be somebody, and a routed `discard_for_sample`
    # would be that guard with a bypass beside it.
    assert callable(wizard_parks.discard_for_sample)
    assert "discard_for_sample" not in source

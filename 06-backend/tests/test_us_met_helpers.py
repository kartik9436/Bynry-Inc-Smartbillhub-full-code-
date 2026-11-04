# ── Trace ──────────────────────────────────────────────
# Component: shared fixtures/helpers for the W1 metering + assets feature-lane
#            tests (imported by tests/test_us_met_*.py and test_us_ast_*.py via
#            `from ... import *`). Builds on the W0 tenancy helpers: same
#            sqlite tenant-context fake, same captured audit sink, same
#            identity-seam stub. Live-RLS behavior = the G5 isolation suite.
# ───────────────────────────────────────────────────────
"""Shared plumbing for the premises/units/routes/cycles and assets story tests.

The §4 test data of EP-MET-01/02 and EP-AST-01..04 is Brazos Bend Utilities
(Electric + Water, Katy TX) with Lone Star Ridge as the isolation tenant — the
same two tenants the W0 tenancy pack provisions, so the fixtures below layer
on `provisioned_tenant()` rather than inventing a second world.

`number_series` rows for the `premises` and `unit` series are created here as
TEST SETUP: EP-TEN-08 defines neither series and tenant provisioning seeds no
row for them, so production allocation currently reports
`numbering_series_missing` (services docstring disposition). Both branches are
asserted — the seeded path renders a number, the unseeded path warns.
"""

from datetime import date

import pytest

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — W0 shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    FakeUser,
    admin_actor,
    api_call,
    brazosbend_payload,
    clerk_actor,
    lonestarridge_payload,
    provisioned_tenant,
    seeding_ctx,
    tenant_ctx,
)

PREMISES_SERIES_FORMAT = "P-{00000}"  # prototype S16 "Auto (P-11800)"
UNIT_SERIES_FORMAT = "U-{00000}"


@pytest.fixture(autouse=True)
def audit_rows():
    """BE-03 capture sink, RESTORING whatever was registered before.

    Overrides the W0 helper's version, which cleared the sink to None at
    teardown: these files sort ahead of tests/test_us_aud_001_store.py, whose
    TC-4 asserts the sink apps.audit registers at startup is still in place.
    Capturing must never be able to unregister the platform trail.
    """
    from core import audit as core_audit

    rows: list = []
    previous = core_audit._sink
    core_audit.set_audit_sink(rows.append)
    yield rows
    core_audit.set_audit_sink(previous)


def executive_actor():
    from types import SimpleNamespace
    from uuid import uuid4

    return SimpleNamespace(id=uuid4(), role="executive")


def staff_actor(tenant, role="system_admin", email=None):
    """An actor backed by a REAL identity user row: asset_assignments.actor_user_id
    and asset_maintenance.tech_user_id are FKs into `users`, so a synthetic uuid
    would break the reviewed cross-module FK set (B2 §2).

    ⚠ **IT REUSES AN EXISTING ADDRESS RATHER THAN CREATING A SECOND ROW, AND
    THAT BECAME NECESSARY ON 2026-09-01 (DEF-566 / DEF-2395).** Until then
    `identity_seam` stubbed `provision_owner` with a function that wrote NO
    `users` row, so a fixture naming the tenant's own owner address was creating
    that row for the first time. Provisioning writes it now, and a blind
    `create` collides:

        sqlite3.IntegrityError: UNIQUE constraint failed:
        index 'uq_users_tenant_email_ci'

    — measured on all ten cases of `tests/test_cr060_t4_premises_recovery.py`,
    whose `submetering_payload` owner is `renata@bayoubend.test` and which then
    asked for `staff_actor(tenant, "system_admin", "renata@bayoubend.test")`.

    **Reuse is the CORRECT answer here, not the convenient one.** BR-IDN-029
    makes an address unique per tenant and the index is case-insensitive, so
    within one tenant that email names ONE person. A fixture asking for
    "the System Admin at this address" and a provisioning owner sitting at that
    address are the same human being; minting a second row would be the fixture
    inventing a colleague nobody asked for, and it is what the collision was
    telling us.

    The lookup is case-insensitive to match the index rather than to match the
    string, so `Renata@…` and `renata@…` cannot become two rows here when the
    database would refuse them as one.
    """
    from types import SimpleNamespace

    from apps.identity import models as identity_models

    address = email or f"{role}@brazosbendutilities.test"
    with seeding_ctx(tenant):  # DEF-2761 — `users` is tenant-scoped and RLS is on
        user = identity_models.User.objects.filter(
            tenant=tenant, email__iexact=address
        ).first()
        if user is None:
            user = identity_models.User.objects.create(
                tenant=tenant, email=address, full_name=role.title()
            )
    return SimpleNamespace(id=user.id, pk=user.id, role=role, user=user)


def make_plan(tenant, name="Small Commercial", code=None, services=("electric",), dated=True):
    """A PUBLISHED rate plan — what a unit holds (PO ruling 2026-08-11).

    Fixtures used to build a `Tariff` here, because `units.default_tariff_id`
    pointed at one. A unit now holds a PLAN: the bundle across its services,
    which is what the S16 panel has always called it and what the assignment
    history stores. A plan resolves to one rate schedule per service through
    `plan_rate_schedules`, so the schedules are created and linked too — a
    plan with no schedule is not a thing a bill could be produced from.

    `status="published"` is deliberate and load-bearing: BR-RAT-030 makes only
    published plans assignable, and `plan_ref` filters on it, so a fixture that
    left the default `draft` would fail to resolve and read as an unrelated
    bug. The rating LANE owns its own service functions; this is fixture data,
    not a cross-module write from metering.
    """
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    with seeding_ctx(tenant):  # DEF-2761 — plans, tariffs and schedules are tenant-scoped
        plan, _ = rating_models.RatePlan.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults={"code": code or name.lower().replace(" ", "-"), "status": "published"},
        )
        for service_code in services:
            service = tenancy_models.Service.objects.get(code=service_code)
            tariff, _ = rating_models.Tariff.objects.get_or_create(
                tenant=tenant, name=f"{name} — {service_code}", service=service
            )
            rating_models.PlanRateSchedule.objects.get_or_create(
                tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
            )
        # ⚠ **`dated=False` KEEPS THE UNDATED STATE ON PURPOSE (`DEF-2816`).**
        # `test_def_438_parity._water_plan(dated=False)` is the ONE case that
        # measures the R1 divergence — the live path bills an undated published
        # plan forever, the chain refuses it never — and BR-RAT-007 chooses
        # neither reading. A fixture that dated every plan would silently close
        # that finding, and its `xfail(strict=True)` would XPASS and fail the
        # suite while the divergence was still live in the product.
        if dated:
            state_plan_start(plan)
    return plan


def state_size_axis(version, service_code):
    """State which connection sizes a fixture schedule VERSION serves.

    ⚠ **A BANDED SERVICE WHOSE SCHEDULE STATES NO SIZE AXIS REFUSES EVERY
    ACCOUNT, AND THAT IS THE PO's OWN CHOICE RATHER THAN A BUG (`DEF-2816`).**
    `resolution_catalogue.configured_sizes_for` sets it out in four cases and
    this is the third: *"no sizes, service IS banded -> `()` — this version
    prices no size at all, so every size refuses by name. **This is the reading
    the PO chose with its cost stated**: 'Read the second way, the system
    refuses bills that price perfectly well today.'"* So with R3 served, a
    fixture that builds an ELECTRIC schedule and states no axis gets
    *"connection size 'E-1P-100' has no row on the rate schedule version …
    pricing 'electric'"* on every account of it.

    **The rows are `apps/rating/sample_data.sample_size_rows`'s, taken from that
    function rather than rebuilt**, so a fixture axis and a seeded axis cannot
    drift: one row per RATIFIED class (`BR-TEN-171`), `minimum_bill` left NULL —
    *"this size IS served and has no floor"*, r10's em-dash — and never `$0.00`,
    because CR-013 part 1 makes a blank and a zero mean different things.

    ⚠ **IT MOVES NO MONEY, AND THAT IS THE PRODUCT'S OWN MEASURED CLAIM, NOT
    THIS FIXTURE'S.** `apps/rating/sample_data.py`: *"THE SIZE ROWS THEMSELVES
    CANNOT MOVE A BILL AT ALL: no live pricing read touches `rate_size_rows`."*
    A row with a NULL minimum states membership and no price.

    ⚠ **IT IS NOT `DEF-1810` COMING BACK**, for `sample_size_rows`' own reason:
    the axis is the PLATFORM's ratified list for the service and never the size
    the account's meter happens to be, so the caller cannot widen it and R3's
    refusal stays reachable — `state_size_axis(version, 'electric')` on a meter
    recorded as some future seventh class would still refuse it by name.

    Sewer gets no rows (ruled to have none) and the blank-size ladder answers
    for it. An UNRULED service — battery, thermal steam — raises
    `SizeClassNotRuled` carrying its OQ id, deliberately uncaught: the prime
    directive forbids answering an unruled boundary by choosing a value.
    """
    from apps.rating import models as rating_models
    from apps.rating.sample_data import sample_size_rows

    for row in sample_size_rows(service_code):
        rating_models.RateSizeRow.objects.get_or_create(
            tenant=version.tenant,
            tariff_version=version,
            size_class=row["size_class"],
            defaults={"minimum_bill": None},
        )
    return version


#: The date a fixture plan starts when nothing it binds states an earlier one.
#:
#: ⚠ **`rating/0024` REJECTED "TODAY" IN TERMS AND THE REASON APPLIES HERE.**
#: Its own words: *"picking today restates history"* — a plan stamped today is
#: outside the window of every period the fixture already bills, so R1 refuses
#: exactly the bills the date was supposed to enable. The migration's third
#: fallback is `rate_plans.created_at`, which in a test IS today, so the chain
#: ends one step earlier here and lands on the date the fixture world's own
#: prices start: `journey_cohort_fixtures.ensure_priced_plan` and three more of
#: its blocks create their first `TariffVersion` at `2026-01-01`, and every
#: service date any fixture bills is after it.
FIXTURE_PLAN_EPOCH = date(2026, 1, 1)


def state_plan_start(plan):
    """Give a PUBLISHED fixture plan the start date `BR-RAT-890` requires.

    ⚠ **WHY A FIXTURE HAS TO DO THIS (`DEF-2816`).** `make_plan` writes
    `status="published"` through `get_or_create` rather than through
    `rating.services.publish_plan`, so it manufactures a plan that is published
    and states no start date — **a state the product itself refuses to create**
    since `BR-RAT-890` (PO ruling 2026-08-28, closing `DEF-494`): *"you cannot
    publish a plan without saying when it starts, so the situation stops
    existing; any published plan today that has no date gets one."* Rating
    migration `0024` is the *"gets one"* half and closed the state for every
    real tenant; nothing closed it for a fixture, because no fixture runs a
    backfill.

    It did not matter while nothing read the column — `selectors.plan_ref`, what
    the live bill run reads, *"consults no date at all"*. **Since the PO ruled
    R3 + R4 on (`CR-057`) it decides whether a bill happens**:
    `resolution.PlanVersion.in_force_on` returns False for a `None`
    `effective_from`, so R1 refuses with *"account ACC-9001 has no plan version
    in force on 2026-08-31"* and `BR-BIL-872` gives that refusal no fallback.

    **THE DATE IS `rating/0024`'s RULE, NOT A NUMBER CHOSEN HERE**, quoted from
    its own docstring: *"the earliest `effective_from` among the ACTIVATED
    versions of the rate schedules the plan itself binds — a date a human at the
    utility typed, about this plan's own prices, that the product already
    stores."* Its fallback chain is followed too, and stops one step short of
    `created_at` for the reason recorded on `FIXTURE_PLAN_EPOCH` above.

    ⚠ **IT DOES NOT ANSWER THE OPEN RULE QUESTION AND MUST NOT BE READ AS
    DOING SO.** `plan_version_facts` records a live divergence — the live path
    bills a dateless published plan forever, the chain refuses it never — and
    says *"that divergence is REPORTED, not resolved here."* This function
    resolves nothing: it stops the FIXTURE from building a state `publish_plan`
    would refuse. A tenant that still holds one is `DEF-438`'s business.

    Idempotent: a plan that already states a date keeps it.
    """
    from apps.rating import models as rating_models

    if plan.effective_from is not None:
        return plan
    bound = rating_models.PlanRateSchedule.objects.filter(
        tenant=plan.tenant, rate_plan=plan
    ).values_list("tariff_id", flat=True)
    earliest = (
        rating_models.TariffVersion.objects.filter(
            tenant=plan.tenant, tariff_id__in=list(bound), effective_from__isnull=False
        )
        .order_by("effective_from")
        .values_list("effective_from", flat=True)
        .first()
    )
    plan.effective_from = earliest or FIXTURE_PLAN_EPOCH
    plan.save(update_fields=["effective_from"])
    return plan


def seed_physical_series(tenant):
    """Open the premises/unit series at 101 so §4's numbers come out of the
    product.

    ⚠ **NO LONGER A SIMULATION (CR-005, 2026-08-17).** This helper used to say
    it was simulating *"what provisioning WOULD seed once EP-TEN-08 carries the
    premises/unit series"* — it carries them now, at these exact two formats,
    for every tenant. What remains is the COUNTER: `get_or_create` would find
    the freshly seeded row standing at 1 and silently drop `next_number=101`,
    so §4's `P-00101` became `P-00001` with nothing else changed.
    `update_or_create` sets the opening position whether or not the row is
    already there.
    """
    from apps.tenancy import models as tenancy_models

    # DEF-2761: inside the tenant's own context. Provisioning already created
    # these rows, so with no context the SELECT half of `update_or_create` is
    # denied by RLS, finds nothing, and the INSERT it falls back to is refused
    # too — `NumberSeries.DoesNotExist` in 97 of the first 116 modules measured.
    with seeding_ctx(tenant):
        for series, fmt in (("premises", PREMISES_SERIES_FORMAT), ("unit", UNIT_SERIES_FORMAT)):
            tenancy_models.NumberSeries.objects.update_or_create(
                tenant=tenant, series=series, defaults={"format": fmt, "next_number": 101}
            )


@pytest.fixture()
def brazos(growth_plan, identity_seam):
    """Brazos Bend Utilities: Electric + Water enabled, UoMs seeded, physical
    number series present."""
    tenant, _result = provisioned_tenant(brazosbend_payload())
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def lonestar(growth_plan, identity_seam):
    """The isolation tenant (Water only)."""
    tenant, _result = provisioned_tenant(lonestarridge_payload())
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def dana(brazos):
    """Dana Whitfield — Brazos Bend System Admin (EP-MET-01/EP-AST-01 §4)."""
    return staff_actor(brazos, "system_admin", "dana@brazosbendutilities.test")


@pytest.fixture()
def marcus(brazos):
    """Marcus Vega — Brazos Bend Billing Clerk."""
    return staff_actor(brazos, "billing_clerk", "marcus@brazosbendutilities.test")


@pytest.fixture()
def erin(lonestar):
    """Erin Walsh / J. Okafor — the isolation tenant's System Admin."""
    return staff_actor(lonestar, "system_admin", "erin@lsrwater.test")


def owner_for(actor, name=None):
    """A typed owner id for `name`, REUSING the party if it already exists.

    **DEF-650 / BR-MET-401** — the owner is required at premises creation (PO
    2026-08-27: *"without owner how you can create premsies"*), so every fixture
    that makes an address needs one.

    ⚠ **IT GOES THROUGH `resolve_owner_name`, WHICH IS THE PRODUCT'S OWN CHECK,
    AND THAT IS THE POINT RATHER THAN A CONVENIENCE.** A suite that creates
    twenty addresses for *Whitfield Rentals LLC* ends up with ONE party, which is
    the ruling's *"one party rather than twelve unrelated strings"* exercised by
    every test that touches a premises — and if reuse ever broke, the second
    `make_premises` call in any file would fail on the unique-name constraint.

    The CATEGORY is `landlord` because a fixture has to pick one and this one is
    stated here rather than inferred from the name — BR-MET-151 clause 3 forbids
    reading a category off a string, and a helper that did so would teach the
    habit the rule exists to stop.
    """
    from apps.metering import premises_owners

    text = (str(name or "").strip()) or "Whitfield Rentals LLC"
    found = premises_owners.resolve_owner_name(text)
    if found["match"] == "exact":
        return found["owner"]["id"]
    return premises_owners.create_premises_owner(
        actor, {"name": text, "category": "landlord"}
    )["id"]


def make_premises(actor, **overrides):
    """Create one premise through the real service (no ORM shortcuts)."""
    from apps.metering import services

    # ⚠ **NO PREMISES TYPE BY DEFAULT SINCE `CR-162-BRC10` (2026-10-02).** It
    # was `single_family` on every fixture address, chosen by nobody — and the
    # PO's Q1 ruling made the TYPE decide whether an owner's master account may
    # open (a single-family home never gets one, an apartment complex always
    # may). Dozens of master-account tests build a two- or three-unit fixture
    # address and expect a master on it; on an arbitrary `single_family` type
    # every one of them would now be refused for a reason the test never chose.
    # With no type the rule falls back to counting homes — exactly the 2.442.0
    # behaviour those tests were written against. A test about the TYPE names
    # one (`tests/test_cr162_new_connection_lifecycle.py`).
    payload = {
        "address_line": "1408 Bluestem Ln",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "services_available": ["electric", "water"],
        "owner_manager": "Whitfield Rentals LLC",
    }
    payload.update(overrides)
    # BR-MET-401 — required at CREATE. Derived from whatever free-text name the
    # caller asked for, so a test that names a specific landlord gets a party
    # with that landlord's name and the provenance reads true.
    if not payload.get("owner_id"):
        payload["owner_id"] = owner_for(actor, payload.get("owner_manager"))
    return services.create_premises(actor, payload)


def make_unmatched_premises(actor, owner_manager="Ridge Property LLC", **overrides):
    """A premises in the PRE-RULING state: free-text owner, no typed party.

    ⚠ **IT WRITES THE COLUMN DIRECTLY, AND IT HAS TO.** `create_premises` refuses
    an address with no owner since BR-MET-401, so this state can no longer be
    reached through the front door — which is the rule working, not a gap. It is
    still a REAL state on every live tenant (`metering 0041` backfills nothing),
    and BR-MET-151's matching surface exists entirely to work through it, so the
    tests for that surface need a way to build one.
    """
    from apps.metering import models

    # ⚠ **THE PARTY IT IS CREATED WITH IS A THROWAWAY, AND THAT MATTERS.** If it
    # were a party named after the caller's free text, that name would then exist
    # as a typed owner — and `unmatched_owner_rows` suggests parties whose name
    # matches the string exactly, so every test asserting *"no suggestion yet"*
    # would start seeing one. The fixture party is named for what it is.
    row = make_premises(
        actor,
        owner_manager=owner_manager,
        owner_id=owner_for(actor, "Fixture Party (unmatched premises)"),
        **overrides,
    )
    models.Premises.objects.filter(pk=row["id"]).update(owner=None)
    return row


def make_unit(actor, premises_id, **overrides):
    from apps.metering import services

    payload = {"premises_id": premises_id, "label": "Unit A", "unit_type": "residential"}
    payload.update(overrides)
    return services.create_unit(actor, payload)


def _smallest_ratified_band(service_code):
    """The service's smallest ratified connection size, or `None` where the
    vocabulary does not answer for it.

    ⚠ **THIS IS THE SEEDER'S OWN RULE, NOT A NEW ONE, AND IT IS THE REASON THIS
    IS NOT A NUMBER INVENTED TO MAKE A TEST PASS.**
    `apps/assets/sample_data.py` picks a demo meter's size exactly this way and
    states why in its own words: *"THE CODE COMES FROM TENANCY'S RATIFIED LIST,
    NEVER FROM A STRING TYPED HERE (BR-TEN-171 — `W-58`, `E-1P-100`, …)"* and
    *"The SMALLEST band is chosen — first in the ratified order, and the
    residential one for every service that has bands (water `W-58` is 5/8",
    electric `E-1P-100` is single-phase 100A)."* The value therefore comes out
    of `BR-TEN-171`, which the PO ratified, and never out of this file.

    `assets.seams.service_size_class_codes` is the sanctioned cross-module read
    of that list, and its docstring names the only caller it is lawful for:
    *"a seeder deciding whether to put a demo value on a demo row"*, for which
    *"leave it NULL is the right answer"* to all three of its empty cases
    (sewer by ruling, thermal steam and battery by `OQ-560`/`OQ-561`). A test
    fixture building a demo meter is that caller.
    """
    from apps.assets import seams

    codes = seams.service_size_class_codes(service_code)
    return codes[0] if codes else None



def make_installed_asset(actor, **overrides):
    """`make_asset`, then INSTALLED: stood on a fresh unit of a fresh premises
    through an OPEN `asset_assignments` row (`BR-AST-017`).

    ⚠ ADDED 2026-10-05 (`CR-168-BRC10` §30, `BR-WRK-066`). The PO answered (3),
    verbatim: *"(b) Only raise jobs for meters that are installed."* — so the
    certification rules no longer find `make_asset`'s default, a spare left in
    inventory. A test whose subject is a meter IN THE GROUND says so with this.
    """
    import datetime as _dt

    from apps.assets import models as assets_models
    from core import tenancy as _core_tenancy

    asset = make_asset(actor, **overrides)
    tag = str(asset["id"])[-8:]
    premises = make_premises(
        actor, address_line=f"{tag} Installed Way", services_available=[overrides.get("service") or "electric"]
    )
    unit = make_unit(actor, premises["id"], label=f"Unit {tag}")
    assets_models.AssetAssignment.objects.create(
        tenant_id=_core_tenancy.current_tenant_id(), asset_id=asset["id"], unit_id=unit["id"],
        from_date=_dt.date(2024, 1, 1),
    )
    return asset


def make_asset(actor, **overrides):
    """Create one asset through the real service. Defaults to a spare electric
    meter left in inventory (BR-AST-011 leave-in-inventory path).

    ⚠ **IT CARRIES A CONNECTION SIZE FROM 2026-09-01 (`DEF-2965`).** Electric is
    a BANDED service — six ratified classes in `BR-TEN-171` — and since the PO
    ruled R3 on (`CR-057`) a meter with no size recorded cannot be priced at
    all: `resolve_served_size` refuses with *"service 'electric' has no
    connection size … R3 cannot be resolved and a size may not be guessed"*.
    A spare in inventory is not on a service point and so is not refused
    *today*, but it is fitted to one by the next fixture that needs a meter,
    and a size is a property of the DEVICE rather than of where it is standing.

    **The value is `BR-TEN-171`'s own** — the service's smallest ratified band,
    read through the assets seam, exactly as `apps/assets/sample_data.py` picks
    a demo meter's size and for the reason it records: *"THE CODE COMES FROM
    TENANCY'S RATIFIED LIST, NEVER FROM A STRING TYPED HERE."* A caller that
    means *"this meter's size was never recorded"* passes `size_class=None` and
    gets that state, which is what the R3-refusal tests do.
    """
    from apps.assets import services as asset_services

    payload = {
        "type": "meter",
        "asset_no": "M-5099",
        "service": "electric",
        "unit": "kWh",
        "read_method": "ami",
        "multiplier": "1",
    }
    payload.update(overrides)
    # Derived from the FINAL service, so a caller overriding `service` gets that
    # service's band and not electric's. `None` for a service the ratified
    # vocabulary does not answer for (sewer by ruling; steam and battery by
    # OQ-560/OQ-561) — the seam's own three empty cases, where NULL is right.
    if "size_class" not in payload:
        band = _smallest_ratified_band(payload["service"])
        if band is not None:
            payload["size_class"] = band
    return asset_services.create_asset(actor, payload)


def audit_actions(rows):
    return [row["action"] for row in rows]


def field_actor(order_id, fallback=None):
    """The login of the FIELD technician holding this job — assigned one if the
    job has none (`CR-168-BRC10` P1.34, ruling 18). Tests written before the
    completion guard synced and closed jobs as Dana at a desk; the close is now
    refused for anyone the job was not given to, so a test whose subject is what
    a sync or a close WRITES acts as the field. An order of ANOTHER tenant is
    left alone and `fallback` is returned, so a cross-tenant 404 stays the
    product's own answer."""
    from types import SimpleNamespace

    from apps.identity import models as identity_models
    from apps.work import connection_models as work_tables
    from apps.work import models as work_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    order = work_tables.WorkOrder.objects.filter(tenant_id=tenant_id, pk=order_id).first()
    if order is None:
        return fallback
    technician = order.assignee_technician
    if technician is None:
        email = f"field.close.{str(tenant_id)[-6:]}@field.test"
        user = identity_models.User.objects.filter(tenant_id=tenant_id, email=email).first()
        if user is None:
            user = identity_models.User.objects.create(
                tenant_id=tenant_id, email=email, full_name="F. Close"
            )
        technician, _ = work_models.Technician.objects.get_or_create(
            tenant_id=tenant_id, user=user, defaults={"crew_id": order.assignee_crew_id}
        )
        if order.assignee_crew_id and technician.crew_id != order.assignee_crew_id:
            technician.crew_id = order.assignee_crew_id
            technician.save(update_fields=["crew"])
        if not order.assignee_crew_id:
            work_tables.WorkOrder.objects.filter(pk=order.id).update(assignee_technician=technician)
    return SimpleNamespace(id=technician.user_id, role="field_technician")


def field_close(actor, order_id, **fields):
    """Close a job THE WAY THE PRODUCT NOW REQUIRES: as the field
    (`CR-168-BRC10` P1.34, ruling 18 — *"back office cannot complete the job it
    can only accept it"*). Their subject is what a close WRITES, never who may
    close — `test_cr168_srv1_server.py` owns that. See `field_actor`."""
    from apps.metering import connections as w6

    tech = field_actor(order_id, fallback=actor)
    take_required_photos(tech, order_id)
    return w6.submit_field_result(tech, order_id, **fields)


#: A one-pixel PNG — the stand-in photograph `take_required_photos` sends.
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63382127070002b6010534a675aa0000000049454e44ae426082"
)


def take_required_photos(actor, order_id):
    """Every photo-REQUIRED reading and task photographed, each FOR its row,
    through #77's own service (`DEF-WRK-9625`: the close is refused without
    them, by every door). A test whose subject is what a close WRITES takes
    them first, as the technician would; `test_def_wrk_9625_close_needs_photos`
    owns the refusal. An order of another tenant is left alone."""
    from apps.work import evidence
    from apps.work import models as work_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    for model, field in (
        (work_models.WorkOrderReading, "reading_id"),
        (work_models.WorkOrderTask, "task_id"),
    ):
        for row in model.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id, photo_required=True,
            photo_attachment_id__isnull=True,
        ):
            evidence.record_attachment(
                actor, order_id,
                {"idempotency_key": f"test-{field}-{row.id}", field: str(row.id)},
                _TINY_PNG,
            )

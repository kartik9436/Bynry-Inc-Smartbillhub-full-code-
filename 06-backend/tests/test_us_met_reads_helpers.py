# ── Trace ──────────────────────────────────────────────
# Component: shared fixtures for the W2 reads lane tests (US-MET-007..011,
#            US-MET-014/015). Layers on tests/test_us_met_helpers.py — same
#            Brazos Bend / Lone Star Ridge world the W1 metering pack builds,
#            so the reads fixtures sit on real premises, units and assets
#            rather than a second invented universe.
# Note:      §4 test data is EP-MET-03's Brazos Bend batch (M-7001 42,180 →
#            42,864 = 684.000000 kWh) and EP-MET-05's GT-9 fixture.
# ───────────────────────────────────────────────────────
"""Fixtures for the read-import, validation and estimation tests."""

from datetime import datetime, timezone
from decimal import Decimal

from apps.assets import services as asset_services
from apps.metering import models, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    _smallest_ratified_band,
    make_premises,
    make_unit,
    tenant_ctx,
)


def at(day: str) -> datetime:
    """A read DATE as the timestamp the importer stamps: 00:00Z of that day
    (see apps/metering/read_import._parse_date — it is what makes B2 r8's
    UNIQUE (asset, read_at, channel) the per-DATE key the rules describe)."""
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)


#: `a_meter`'s `size_class` default, distinguishable from an explicit `None`.
#:
#: **`None` still means "no connection size is recorded" and it is still a
#: reachable state** — `metering.connection_size_for` answers `None` for it and
#: R3 refuses the account by name. The tests that exist to prove that refusal
#: pass `size_class=None` and get exactly what they always got. What changed is
#: only the DEFAULT, for callers that never had an opinion.
RATIFIED_BAND = object()


def a_meter(
    actor,
    asset_no="M-7001",
    *,
    unit_label="Unit A",
    address="1408 Bluestem Ln",
    service="electric",
    uom="kWh",
    multiplier="1",
    register_digits=5,
    unit_id=None,
    size_class=RATIFIED_BAND,
):
    """One meter on a real unit, through the real assets service.

    `size_class` is BR-AST-500's connection size (`service_size_classes.code`,
    e.g. `W-58`).

    ⚠ **IT USED TO DEFAULT TO `None` AND THAT DEFAULT BECAME A REFUSAL ON
    2026-09-01 (`DEF-2965`).** The old default was chosen so *"every existing
    caller of this helper is byte-identical"* to the pre-`DEF-514` world, which
    was right while nothing read the column. **The day the PO ruled R3 on
    (`CR-057`), an unsized meter on a BANDED service stopped being a harmless
    blank and became a bill that does not happen**: `resolve_served_size`
    refuses with *"service 'electric' has no connection size … R3 cannot be
    resolved and a size may not be guessed"*, and eight cases of
    `test_cr014_round3_cohorts.py` went red on exactly that, all of them electric.

    **The engine is right and the fixture was wrong.** Electric is a banded
    service with six ratified classes (`BR-TEN-171`), so a meter with no size
    recorded genuinely cannot be priced — the PO ruled on 2026-08-28 that we
    charge on the size the account actually has, and you cannot charge on a size
    you do not have. So the default is now the service's SMALLEST RATIFIED BAND,
    taken from `BR-TEN-171` through the assets seam and never typed here — see
    `_smallest_ratified_band` above for the seeder's own wording of that rule.

    **`size_class=None` is still available and still means what it says.** A
    test that needs an unsized connection — to prove R3's refusal, or to walk
    `connection_size_unresolved_for_sized_schedule` — passes it explicitly, and
    the absence is then the test's stated subject rather than a fixture's
    accident. That distinction is the whole point of the sentinel: the refusal
    is not weakened, it is moved from *"every meter, silently"* to *"this meter,
    because this case is about it"*.
    """
    if size_class is RATIFIED_BAND:
        size_class = _smallest_ratified_band(service)
    if unit_id is None:
        premise = make_premises(actor, address_line=address, services_available=[service])
        unit = make_unit(actor, premise["id"], label=unit_label, services=[service])
        unit_id = unit["id"]
    asset = asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": asset_no,
            "service": service,
            "unit": uom,
            "read_method": "walk_by" if service == "electric" else "manual",
            "multiplier": multiplier,
            "register_digits": register_digits,
            "unit_id": unit_id,
            "install_date": "2026-01-05",
            "status": "active",
            # BR-AST-500 — omitted entirely when None, so the payload a legacy
            # caller sends is unchanged rather than gaining an explicit null.
            **({"size_class": size_class} if size_class is not None else {}),
        },
    )
    return asset


def seed_config(**overrides):
    """The tenant's `read_validation_settings` row — the B2 r5 #15 seeded
    defaults unless a test deliberately changes one (BR-MET-020: the engine
    reads THIS, never a constant).

    ⚠ SINCE CR-038 A1 (2026-08-26) `ensure_read_validation_settings` ALSO
    seeds per-(tenant, service) rows for enabled electric/water, and the
    engine resolves THOSE first — so an override set here governs an
    electric/water read only until the per-service row exists (i.e. it now
    usually does NOT). A test tuning a threshold the engine must honour uses
    `seed_service_config` below; this helper still owns the tenant-wide
    estimation params, which never moved."""
    row = services.ensure_read_validation_settings()
    for name, value in overrides.items():
        setattr(row, name, value)
    if overrides:
        row.save()
    return row


def seed_service_config(service_code, **overrides):
    """One service's `read_validation_service_settings` row (CR-038 A1) — the
    ratified electric/water seed unless a test deliberately changes a figure.
    The engine resolves THIS row first for the service's reads."""
    services.ensure_read_validation_settings()
    row = models.ReadValidationServiceSettings.objects.get(
        tenant_id=services._tenant_id(), service__code=service_code
    )
    for name, value in overrides.items():
        setattr(row, name, value)
    if overrides:
        row.save()
    return row


#: ⚠ **A SENTINEL, NOT `None`, BECAUSE `None` IS A REAL ANSWER HERE.** An
#: unstamped read is the `metering/0012` legacy case a test may deliberately
#: want; "derive it the way the product does" is the default. One value cannot
#: mean both, and a default of `None` would have made the legacy case the
#: silent norm all over again (`DEF-MET-6143`).
_DERIVE_THE_ROUTE = object()


def commit_read(
    actor,
    asset_id,
    *,
    day: str,
    value,
    channel="total",
    unit="kWh",
    consumption=None,
    days_since_prior=None,
    status="ok",
    prior_value=None,
    multiplier="1",
    estimated=False,
    route_id=_DERIVE_THE_ROUTE,
    period_start=None,
):
    """A committed read written directly, for HISTORY setup only.

    Deliberately not routed through the import wizard: these rows are the past
    a test starts from, and building each one through a five-step wizard would
    make the fixture, not the behaviour, the thing under test. Every row still
    carries its EXPLICIT unit (CLAUDE.md rule 3).

    ⚠ **IT NOW CARRIES THE `BR-MET-079` COLLECTION STAMP, AND THAT IS A FIXTURE
    FIDELITY FIX RATHER THAN A CONVENIENCE (`DEF-MET-6143`).** Every read this
    helper wrote had `route_id = NULL`, because the helper set every other
    column `_post_row` sets and not that one — so the whole suite's "past" was
    a past no reader had ever walked. That was invisible while the screens
    resolved a route through the LIVE membership projection, and it becomes
    load-bearing the moment they read the stamp (PO ruling 2026-09-22, *"100"*:
    a route reports the readings collected on it).

    The stamp is taken from `services.collection_route_id`, **the product's own
    resolver**, for the reason `owner_for` states about owners one file over: a
    fixture that computes a fact its own way proves its own copy. Pass
    `route_id=None` explicitly to build the one case that genuinely has no
    stamp — a reading collected before `metering/0012` — and the sentinel makes
    that request distinguishable from *"I did not think about it"*.
    """
    stamped = route_id
    if stamped is _DERIVE_THE_ROUTE:
        from apps.assets import models as assets_models
        from apps.metering import services as metering_services

        stamped = metering_services.collection_route_id(
            assets_models.Asset.objects.get(pk=asset_id)
        )
    return models.MeterRead.objects.create(
        tenant_id=asset_tenant(asset_id),
        asset_id=asset_id,
        route_id=stamped,
        read_at=at(day),
        channel=channel,
        current_value=None if estimated else Decimal(str(value)),
        prior_value=Decimal(str(prior_value)) if prior_value is not None else None,
        multiplier=Decimal(multiplier),
        consumption=Decimal(str(consumption)) if consumption is not None else None,
        unit=unit,
        source="estimated" if estimated else "import",
        status="estimated" if estimated else status,
        lifecycle="committed",
        days_since_prior=days_since_prior,
        # DEF-BIL-8324 — the day the read measures from, as `_post_row` stamps
        # it. Absent (None) on every existing caller, byte-identical to before.
        period_start=period_start,
    )


def asset_tenant(asset_id):
    from apps.assets import models as asset_models

    return asset_models.Asset.objects.get(pk=asset_id).tenant_id


CSV_HEADER = "meter_id,read_date,reading,channel,service,flags\n"


def csv_body(*rows: str) -> str:
    return CSV_HEADER + "".join(row if row.endswith("\n") else row + "\n" for row in rows)


def stage(actor, content, **tags):
    payload = {
        "source_kind": "csv",
        "source_detail": "walk_by",
        "period_month": "2026-08-01",
        "file_name": "brazosbend_reads_08A.csv",
        "file_content": content,
    }
    payload.update(tags)
    return services.stage_read_batch(actor, payload)


def accept_warnings(actor, batch_id, reason="verified against route sheet"):
    """The S28 step-4 bulk "Accept all warnings" (US-MET-008/TC-3).

    Needed in almost every commit test because the customers seam IS wired:
    a unit with no active account is genuinely vacant (BR-MET-036), so a read
    on it warns `vacant_unit` (BR-MET-052) and — correctly — cannot post
    without an explicit, reasoned disposition (BR-MET-015). Creating an
    account instead would couple these tests to the customers lane's payload,
    which this lane must not touch.
    """
    from apps.metering import models

    for row in models.ReadImportRow.objects.filter(batch_id=batch_id, severity="warning"):
        services.set_row_disposition(
            actor, batch_id, row.row_no, {"disposition": "accept_with_flag", "reason": reason}
        )

# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-002 (assign-on-create needs the unit's service point) ·
#           US-AST-003 (delete guard probes reads / bill lines) · US-AST-004
#           (billing chain Premises → Unit → active Account, BR-AST-039) ·
#           US-AST-009 (reassign: unit resolution + final-read capture) ·
#           US-AST-010 (bulk import: unit refs must resolve, never auto-create)
#           Screens: S49–S55
# Rules:    BR-AST-035 (assets attach to UNITS only; account linkage flows
#           through the unit) · BR-AST-039 (live billing chain) · BR-AST-013
#           (delete gate probes every referencing table) · BR-AST-022
#           (final read captured with the move) · BR-AST-034 (premises/units
#           must exist first — unmatched refs error, never auto-created)
# Tests:    06-backend/tests/test_us_ast_001_003_registry.py ·
#           test_us_ast_007_009_lifecycle.py · test_us_ast_010_import.py
# Impacts:  apps.metering (service_points + unit reads) · apps.customers (W2) ·
#           apps.billing (invoice-line reference probe) · apps.tenancy (series)
# ───────────────────────────────────────────────────────
"""assets → other-module SEAMS: every cross-module call this module makes.

B1/B8: the assets tables are metering-owned and HOSTED in this app (see
models.py ownership note), but the module still never reaches into another
module's ORM. Unit / premises / service-point data arrives through metering's
service+selector functions; account, read and invoice-line probes arrive
through their owners.

Documented contracts:

  apps.metering.services.ensure_service_point(unit_id, service_code) -> uuid
    Get-or-create the unit's service point. service_points is METERING-owned,
    so an asset never writes one itself (B1). Wired today.

  apps.metering.selectors.unit_row(unit_id) / .premises_row(id)
    Same-tenant resolution; a cross-tenant id raises the indistinguishable 404
    (HR-1/G4) — which is exactly US-AST-002 TC-8 / US-AST-010 TC-8.

  apps.customers.services.active_account_for_unit(unit_id) -> dict | None
    BR-AST-039 billing chain + BR-AST-035. UNWIRED (W2): customers owns no
    tables, so no account can exist — the chain honestly ends at the unit.

  apps.metering.services.capture_final_read(...) -> dict | None
    BR-AST-022 final-read capture, atomic with the move. WIRED by the CR-028
    debt sweep (D5, 2026-08-22): metering commits the manual read in the
    caller's transaction and returns its read_dict; the closing assignment
    row takes `final_read_id`. None only when metering is absent — the
    reassign/retire still REFUSE then rather than pretending a read happened.

  apps.metering.services.read_count_for_asset(asset_id) -> int
    BR-AST-012 (forward-only once reads exist) and BR-AST-013 (delete gate).
    WIRED 2026-08-15. This line used to read "0 by construction while those
    tables do not exist", and that stopped being true the day `meter_reads`
    landed (2026-08-10) — DEF-079: the delete gate saw an asset carrying reads
    as UNREFERENCED and offered to delete it, because the seam SUBSTITUTED 0 for
    an answer it could not give. Metering publishes the counter now.

  apps.work.asset_door.cost_rollup_for_asset(asset_id) -> dict | None
    `AST-B-21`: what the JOBS raised against this asset have cost, and how many
    are still open. WIRED 2026-09-12 (`CR-092-BRC01` step 2 wave C lane 1).
    Work owns `work_orders` and `BR-WRK-051` owns the arithmetic, so assets
    asks rather than sums. None when the work module is absent — never a zero
    rollup (DEF-079's law).

  apps.billing.services.invoice_line_count_for_asset(asset_id) -> int
    The other leg of the same BR-AST-013 gate, and it is STILL DARK — parked in
    10-scripts/gates/seam_known_gaps.txt with the real blocker: no column and no
    join exists from `invoice_lines` to an asset or a meter, so the count cannot
    be derived at all. That is a SCHEMA gap needing a B2 addendum, not an
    unwritten function. ⚠ The gate is therefore HALF-SIGHTED: reads are seen,
    invoice lines are not.

  apps.tenancy.selectors.number_series_row("asset") + core.numbering
    BR-AST-026 asset-number allocation (EP-TEN-08 series).

  apps.rating.resolution.service_prices_by_size_class(code) -> bool | None
    `DEF-AST-7660`. Does this service's price vary by SIZE BAND — the fact
    that makes a blank `size_class` unbillable rather than merely unrecorded.
    `None` for a dimension whose bands were never ruled and for a code that is
    not one of the eleven; the three answers stay apart because the caller
    takes three different actions. Measured 2026-09-28: no SERVICE code
    answers `None` today. WIRED 2026-09-28.
"""

from collections.abc import Callable
from importlib import import_module
from typing import Any


def resolve(module: str, attribute: str, kind: str = "services") -> Callable[..., Any] | None:
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


def require(module: str, attribute: str, kind: str = "services") -> Callable[..., Any]:
    fn = resolve(module, attribute, kind)
    if fn is None:  # pragma: no cover - both lanes ship in this packet
        raise RuntimeError(
            f"apps.{module}.{kind}.{attribute} is not wired — see apps/assets/seams.py"
        )
    return fn


# ── metering (units, premises, service points — the owning module) ──────────
def unit_row(unit_id: Any) -> Any:
    """Same-tenant unit or the indistinguishable 404 (HR-1)."""
    return require("metering", "unit_row", kind="selectors")(unit_id)


def unit_ref(unit_id: Any) -> dict[str, Any] | None:
    fn = resolve("metering", "unit_detail_dict", kind="selectors")
    row_fn = resolve("metering", "unit_row", kind="selectors")
    if fn is None or row_fn is None:  # pragma: no cover
        return None
    from core import errors

    try:
        return fn(row_fn(unit_id))
    except errors.NotFoundError:
        return None


def unit_refs(unit_ids: Any) -> dict[str, dict[str, Any]]:
    """`unit_ref` for MANY assignment rows — ONE lookup per DISTINCT unit.

    `CR-092` wave C lane 3 / `DEF-MET-4995`. The Assignment-history selector
    called `unit_ref` inside its row loop, so it cost **one query per row**:
    measured on pine-hill meter `M-88402` at **64 queries for 61 seats** once
    a history existed to loop over. Every asset on every seeded tenant had
    exactly ONE seat, so the shape had never been executed twice in this
    product's life.

    ⚠ **THE DEDUPE IS THE HALF THAT SURVIVES PAGING AND THE PAGE IS THE HALF
    THAT SURVIVES A BIG TENANT** — neither alone is the fix. An asset's seats
    cluster on a handful of units, so deduping collapses a 50-row page to two
    or three lookups; and because the caller pages FIRST, the worst case is
    bounded by `per` rather than by how long the asset has existed. That is
    `NFR-3`'s actual requirement: a cost that does not move with the tenant.

    A unit that cannot be resolved maps to `{}` rather than being dropped, so
    the caller still renders the seat with a quiet dash where its label would
    be — an assignment row is a fact about the asset even when the unit it
    names has gone (the `BR-IDN-030` posture, applied to a place).

    ⚠ **IT WAS A LOOP OVER THE SINGULAR UNTIL `DEF-5745`, SO IT DEDUPED AND
    NEVER BATCHED.** The paragraph above is about the DEDUPE and every word of
    it still holds; what it never claimed, and what a reader took from its name,
    is that the whole set costs one query. It did not: a page whose rows stand
    on distinct units paid one `unit_row` per unit, which on the registry list
    is one per SERVED ROW. `metering.selectors.unit_refs` answers the set in ONE
    query and has since `DEF-2723`; `customers.seams` has used it since. This is
    the same one-line seam `DEF-MET-4962` wrote for `service_codes_for_points`,
    for the same reason — the batch already existed and assets went on paying
    the singular.

    ⚠ **THE ENTRY IS THE FIVE-FIELD LIST REF, NOT `unit_detail_dict`.** That is
    a narrowing and it is deliberate: the detail dict reads the premises' whole
    service list, which no caller of this function draws. The two fields the
    assignment history renders (`label`, `premise_address`) and the one
    `_premises_of` reads (`premises_id`) are all present. A caller that needs
    the full payload wants `unit_ref` and one unit, which is what it is for.
    """
    wanted = {str(value) for value in unit_ids if value}
    if not wanted:
        return {}
    fn = resolve("metering", "unit_refs", kind="selectors")
    found = dict(fn(sorted(wanted))) if fn is not None else {}
    # `{}` for a unit metering did not answer for, per the contract above —
    # absence there means "this tenant cannot see it", which is the same
    # 404-never-403 boundary `unit_row` enforces, expressed as a blank cell.
    return {unit_id: found.get(unit_id) or {} for unit_id in wanted}


def typed_read_dates_for_asset(asset_id: Any) -> Any:
    """The S50 Reads tab's PAGING UNIT — distinct read instants, newest first,
    as a QuerySet so `LIMIT`/`OFFSET` reach SQL (`NFR-3`).

    `require`, not `resolve`-with-a-fallback, for `typed_reads_for_asset`'s own
    reason: an empty list from a missing seam would assert *this asset has no
    reads*, the exact claim `DEF-475` refused to fake."""
    return require("metering", "typed_read_dates_for_asset", kind="selectors")(asset_id)


def typed_reads_for_asset_on(asset_id: Any, read_ats: Any) -> list[dict[str, Any]]:
    """The typed rows for ONE PAGE of read dates, in the shape
    `typed_reads_for_asset` already serves — so the fold in `asset_reads`
    is the same code on both paths and the paged answer cannot drift from the
    whole one."""
    return list(
        require("metering", "typed_reads_for_asset_on", kind="selectors")(asset_id, read_ats)
    )


def geocoded_unit_ids() -> list[str]:
    """Every unit that HAS a point — ids only, one query, no per-unit dict.

    `CR-092` wave C lane 3. `geo_view` used to build the whole geo INDEX before
    it knew which assets it was going to answer with; this lets it find the
    page's assets first and ask for the detail of only those units. Empty list
    when unwired or when nothing is geocoded: the map then honestly shows no
    markers, never an invented pin."""
    fn = resolve("metering", "geocoded_unit_ids", kind="selectors")
    return list(fn()) if fn is not None else []


def ensure_service_point(unit_id: Any, service_code: str) -> Any:
    return require("metering", "ensure_service_point")(unit_id, service_code)


def service_point_ref(service_point_id: Any) -> dict[str, Any] | None:
    fn = resolve("metering", "service_point_ref", kind="selectors")
    return fn(service_point_id) if fn is not None else None


def service_codes_for_points(service_point_ids: Any) -> dict[str, str | None]:
    """`{service_point_id: service code}` for MANY points — metering answers the
    whole set in TWO queries instead of two per point.

    ⚠ **PUBLISHED BY METERING SINCE `DEF-1549`; ASSETS WENT ON PAYING THE
    SINGULAR (`DEF-MET-4962`).** `geo_view` called `service_point_ref` once per
    marker and `_service_of` did the same per filtered row — measured on
    `pine-hill`, `GET /assets/geo` cost **241 queries** for 110 markers. The
    batch read already existed and `customers.seams` already used it; this is
    the same one-line seam, so the map stops being the only caller that never
    heard about it. Empty map when unwired — a service then reads as absent,
    which is what the singular already does."""
    fn = resolve("metering", "service_codes_for_points", kind="selectors")
    return dict(fn(service_point_ids)) if fn is not None else {}


def enabled_service_codes() -> set[str]:
    return set(require("metering", "enabled_service_codes", kind="seams")())


def service_default_uom(service_code: str) -> str | None:
    return require("metering", "service_default_uom", kind="seams")(service_code)


def service_default_uoms() -> dict[str, str | None]:
    """`{code: primary UoM}` for every ENABLED service (CR-039 wave A).

    The sample plant resolves the estate's backbone service and its unit from
    this map. It goes through metering's seam and not through tenancy directly
    for the reason every other read here does: metering owns this module's edge
    to the platform catalog (B1)."""
    return dict(require("metering", "service_default_uoms", kind="seams")())


def service_billed_uoms() -> dict[str, dict[str, Any]]:
    """`{code: {"billed_uom", "conversion_factor"}}` for every ENABLED service.

    BR-MET-143 (PO 2026-08-27) — the OTHER half of `service_default_uoms`
    above. That one says what unit a service's register READS; this one says
    what unit it is BILLED in, and the pair is what decides the multiplier the
    seeded meter carries. Through metering's seam for the same B1 reason.
    """
    return dict(require("metering", "service_billed_uoms", kind="seams")())


def unit_reconciliation(reading_unit: str | None, pricing_unit: str | None) -> dict[str, Any]:
    """BR-MET-143: MATCH · SCALE · DIMENSION · UNKNOWN for two units.

    The rule lives in metering (`register_units.reconciliation`) and is asked
    through the seam rather than reimplemented here — a second statement of
    "a multiplier reconciles scale and never dimension" is a second thing to
    drift, and this one decides what factor goes onto a meter.
    """
    return dict(
        require("metering", "unit_reconciliation", kind="seams")(reading_unit, pricing_unit)
    )


def tenant_today() -> Any:
    return require("metering", "tenant_today", kind="seams")()


def tenant_timezone() -> Any:
    """The utility's clock (BR-TEN-081), for turning a stored `created_at`
    stamp into the DAY an asset's age counts from (`DEF-AST-10178`). Read
    through metering's seam — the one derivation — so the start date and the
    `tenant_today()` it is subtracted from are read on the same clock."""
    return require("metering", "tenant_timezone", kind="seams")()


# ── customers (W2 — unwired by construction) ────────────────────────────────
def active_account_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """BR-AST-039 billing chain tail. None while customers owns no tables."""
    fn = resolve("customers", "active_account_for_unit")
    return fn(unit_id) if fn is not None else None


# ── reads + billing reference probes (BR-AST-012/013) ───────────────────────
def read_count_for_asset(asset_id: Any) -> int:
    """Committed reads naming this asset (BR-AST-012/013). WIRED 2026-08-15.

    Every version counts, superseded rows included: the question the delete gate
    asks is "has this asset ever been read", and a corrected read is still a
    read. See apps/metering/services.read_count_for_asset for the DEF-079
    history — this fallback returning 0 is what made an asset with reads look
    deletable, and it is now unreachable in any deployment that has metering.
    """
    fn = resolve("metering", "read_count_for_asset")
    return int(fn(asset_id)) if fn is not None else 0


def work_cost_rollup_for_asset(asset_id: Any) -> dict[str, Any] | None:
    """`AST-B-21` / `AST-B-16` — what WORK says this asset's jobs have cost.

    ⚠ **THE DEPENDENCY POINTS THE RIGHT WAY AND THAT IS THE WHOLE POINT.**
    `work_orders` is Work's table; `BR-WRK-051` names ONE function as the place
    a job's cost is worked out. So assets does not sum cost lines — it ASKS,
    through this seam, exactly as it asks metering for a read count. The answer
    is `apps.work.asset_door.cost_rollup_for_asset`, which is Work's own
    published read on an asset-shaped address, the same pattern as the
    `maintenance_index` the detail page already consumes.

    ⚠ **None, NEVER A ZERO ROLLUP, WHEN WORK IS ABSENT** — DEF-079's law. A
    deployment without the work module must render *we cannot say* rather than
    *nothing has been spent*, because the second is a measurement nobody took
    and the Overview prints it as money.
    """
    fn = resolve("work", "cost_rollup_for_asset", kind="asset_door")
    if fn is None:
        return None
    result = fn(asset_id)
    return dict(result) if result is not None else None


def invoice_line_count_for_asset(asset_id: Any) -> int:
    """Issued invoice lines naming this asset — BR-AST-013's billing leg.

    ⚠ **STILL DARK, AND THIS IS THE ONE PLACE IN THE PRODUCT WHERE A `0` FROM AN
    UNWIRED SEAM IS DEFENSIBLE — for a reason that is a fact about the SCHEMA
    and the CALLER, not a hope about billing.** DEF-079's law is that an honest
    fallback reports it could not answer rather than answering 0; the other four
    seams in that finding were fixed by publishing the counter, and this one
    cannot be: **`invoice_lines` carries no asset or meter column**, so there is
    no join to walk. It is a B2 addendum, not an unwritten function.

    **WHY THE 0 CANNOT LET A BILLED ASSET BE DELETED ANYWAY**, written down so
    the next reader does not have to re-derive it — and re-checkable, which is
    what the sentence this replaces was not:

      1. `delete_asset` refuses unless the asset's status is INVENTORY
         (behaviour class `available`);
      2. it then refuses on ANY non-zero entry of `asset_reference_probe`, and
         that probe counts `AssetAssignment` rows — **assets' OWN table, always
         answerable**;
      3. an asset cannot reach an invoice line without having been ASSIGNED to a
         service point, because that assignment is what produces the reads a
         bill is priced from. So every asset this counter could ever return a
         non-zero for is already refused by the assignments leg.

    The residue is real and is stated rather than smoothed over: the count that
    would appear in the refusal's `referenced_by` is missing, so a clerk blocked
    by an assignment is not told how many bills also name the meter. **That is a
    worse MESSAGE, not a worse OUTCOME**, and the day `invoice_lines` gains an
    asset column the park in `10-scripts/gates/seam_known_gaps.txt` EXPIRES on
    its `absent=` guard and this docstring must be re-argued rather than
    inherited.
    """
    fn = resolve("billing", "invoice_line_count_for_asset")
    return int(fn(asset_id)) if fn is not None else 0


def latest_read_for_asset(asset_id: Any) -> dict[str, Any] | None:
    """DEF-592 (CR-028 AST-W1): the sub-meter registry row's last-read summary.

    Read-only, the same lawful shape as read_count_for_asset — metering owns
    `meter_reads` and publishes `apps.metering.selectors.latest_read_for_asset`;
    assets asks through this seam and never joins (B1). The None fallback is
    honest here in the DEF-079 sense: it feeds a DISPLAY column that renders a
    dash for "no summary available", and no rule, gate or write ever reads it —
    unlike the counters, where a substituted 0 once made a read-carrying asset
    look deletable.
    """
    fn = resolve("metering", "latest_read_for_asset", kind="selectors")
    return fn(asset_id) if fn is not None else None


def typed_reads_for_asset(asset_id: Any) -> list[dict[str, Any]]:
    """CR-028 AST-W2 (DEF-475 closed): the S50 Reads tab's data — BOTH typed
    record kinds for this asset (BR-AST-029), quantities with their explicit
    units, NO money (BR-AST-025). Metering owns `meter_reads` and publishes
    `apps.metering.selectors.typed_reads_for_asset`; assets folds the pair for
    display and never joins (B1).

    `require`, not `resolve`-with-a-fallback, on purpose: an empty list from a
    missing seam would assert "this asset has no reads" — the exact claim
    DEF-475 refused to fake, and the DEF-079 shape. No deployment lacks
    metering; if one ever does, this fails loudly instead of answering."""
    return list(require("metering", "typed_reads_for_asset", kind="selectors")(asset_id))


def actor_display_names(tenant_id: Any, actor_ids: list[Any]) -> dict[str, str]:
    """CR-028 AST-W2 T6: actor id → display name, ONE lookup per page — the
    same published read the S61 Actor column uses (`apps.audit.selectors.
    actor_names`), so the two surfaces cannot word an actor differently, and
    no System-Admin-only `GET /users` round trip is needed for display.
    Empty dict when unwired: the caller falls back to the id, which is the
    BR-IDN-030 posture (the trail outlives any name), never an invention."""
    fn = resolve("audit", "actor_names", kind="selectors")
    return dict(fn(tenant_id, actor_ids)) if fn is not None else {}


def tenant_currency() -> str | None:
    """The tenant's one currency (CHAR(3)) — rides WITH every served amount
    (CLAUDE.md rule 2). Same shape as apps/customers/seams.tenant_currency."""
    fn = resolve("tenancy", "regional_settings", kind="selectors")
    if fn is None:  # pragma: no cover - tenancy always present
        return None
    code = (fn() or {}).get("currency")
    return str(code).upper() if code else None


def capture_final_read(**kwargs: Any) -> dict[str, Any] | None:
    """BR-AST-022: the final read is captured by METERING and linked to the
    closing assignment row — one transaction with the move. WIRED (CR-028
    debt sweep D5, 2026-08-22): `apps.metering.services.capture_final_read`
    commits the manual read through metering's own lineage/validation law and
    returns its read_dict (`id` → `asset_assignments.final_read_id`). None
    only on a deployment with no metering module; the reassign/retire
    services still refuse then rather than silently moving an asset whose
    final read was requested and not taken."""
    fn = resolve("metering", "capture_final_read")
    return fn(**kwargs) if fn is not None else None


def capture_opening_read(**kwargs: Any) -> dict[str, Any] | None:
    """`AST-B-14` — the reading on a new meter's dial, written as the asset is
    created and INSIDE the same transaction (PO ruling 2026-09-12).

    The mirror of `capture_final_read` at the other end of an asset's life, and
    it is metering's function for the same reason: `meter_reads` is METERING's
    table, so assets asks and never writes one itself (B1).

    **None means the metering module is absent, and the caller REFUSES rather
    than creating the asset without its reading** — the same posture the final
    read takes, and for the stronger reason: a clerk who typed a dial reading
    and got a meter with no reading has a meter whose baseline nobody knows.
    `_create_asset_inner` turns this None into a BIZ-COMPLETENESS refusal, and
    because the whole create is one `transaction.atomic()`, the asset row goes
    with it.
    """
    fn = resolve("metering", "capture_opening_read")
    return fn(**kwargs) if fn is not None else None


# ── CR-028 AST-W5 (AST-03 map) — metering's geo reads ───────────────────────
def unit_premises_geo_index(unit_ids: Any = None) -> dict[str, dict[str, Any]]:
    """unit id → {lat · lng · premises · unit · area} for every unit standing
    on a GEOCODED premises — ONE query metering-side (DEF-324). Empty dict
    when unwired or when nothing is geocoded: the map then honestly shows no
    markers, never an invented pin. `area` is the premises' EXISTING
    BR-MET-071 area name — no second area vocabulary exists."""
    fn = resolve("metering", "unit_premises_geo_index", kind="selectors")
    if fn is None:
        return {}
    # `CR-092` wave C lane 3: narrowed to ONE PAGE's units when the caller
    # knows them. Omitted, the answer is byte-identical to what it always was.
    return dict(fn() if unit_ids is None else fn(unit_ids=list(unit_ids)))


def export_rollup_last_month() -> dict[str, Any] | None:
    """CR-028 debt sweep D4 — the BTM tab's "Exported · <month>" KPI figure:
    last complete tenant-calendar month's export-channel quantities, grouped
    by their explicit unit (rule 3), ONE metering-side query (DEF-324).
    Metering owns `meter_reads` and publishes
    `apps.metering.selectors.export_rollup_last_month`; assets asks and never
    joins (B1). Display-only — None (unwired) renders the quiet dash and
    feeds no rule, the stated DEF-079 distinction. Quantities only, no money
    (BR-AST-025)."""
    fn = resolve("metering", "export_rollup_last_month", kind="selectors")
    return dict(fn()) if fn is not None else None


def latest_reads_for_assets(asset_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """latest_read_for_asset's shape for MANY assets in ONE query — the map's
    popup line must not cost a query per marker (DEF-324). Missing entries
    render the quiet dash; display-only, so the empty fallback is the stated
    DEF-079 distinction (same as latest_read_for_asset above)."""
    fn = resolve("metering", "latest_reads_for_assets", kind="selectors")
    return dict(fn(asset_ids)) if fn is not None else {}


# ── tenancy (US-SHL-015 — the tenant's own fields) ──────────────────────────
def validate_custom_data(
    submitted: Any, *, screen: str | None, existing: Any = None
) -> dict[str, Any]:
    """An asset's `custom_data`, through the ONE validator (`CR-161-BRC10` W2,
    `DEF-AST-9171`) — tenancy's `validate_custom_data_for("assets", …)`,
    reached through metering's seam exactly as the asset series is, so this
    module holds no copy of the rules. `screen` is the door's form (`"S51"`
    Add asset, `"ASSET_EDIT"` Edit asset, `None` an import or the unit
    wizard's meter grid — of which nothing is required); `existing` merges an
    edit into the stored answers. `require`, never `resolve`: a soft fallback
    would accept anything into a jsonb column."""
    return require("metering", "validate_custom_data", kind="seams")(
        "assets", submitted, screen=screen, existing=existing
    )


# ── tenancy (BR-AST-026 numbering) ──────────────────────────────────────────
def asset_series_format() -> str | None:
    return require("metering", "number_series_format", kind="seams")("asset")


def asset_series_preview() -> dict[str, Any] | None:
    """CR-028 AST-W4: the asset series ROW (format · next_number · rendered
    preview) from tenancy's own published read — the AST-05 wizard's number
    suggestion is a PEEK on the BE-06 preview contract ("validates + renders
    only, allocates nothing"). None when the tenant has no asset series row;
    the caller then asks for an explicit number rather than inventing one."""
    fn = resolve("tenancy", "number_series_row", kind="selectors")
    if fn is None:  # pragma: no cover - tenancy always present
        return None
    from core import errors

    try:
        return fn("asset")
    except errors.NotFoundError:
        return None


def service_size_class_codes(service_code: str) -> tuple[str, ...]:
    """BR-TEN-171's RATIFIED size-class codes for one utility service, smallest
    first — or an EMPTY tuple where the vocabulary does not answer.

    Tenancy owns the list (`apps/tenancy/service_size_classes.py`) and this is
    the sanctioned cross-module read of it. Used by the SAMPLE seeder only, to
    pick a demo meter's `size_class` from the ratified set rather than from a
    string a lane typed: a size that is not in the vocabulary would be a demo
    tenant teaching every reader the wrong codes.

    ⚠ **EMPTY COVERS THREE DIFFERENT FACTS AND THE CALLER MUST NOT CARE WHICH.**
    Sewer is ruled to have NO size class (BR-RAT-015 — it is a share of the
    water usage charge and reads no register); thermal STEAM and BATTERY were
    put to the PO as a DIMENSION with no boundaries and are OQ-560 / OQ-561, so
    `size_classes_for_service` RAISES `SizeClassNotRuled` for them. Tenancy keeps
    those two answers apart on purpose and this seam collapses them, which is
    lawful for exactly one reason: **the only caller is a seeder deciding
    whether to put a demo value on a demo row**, and "leave it NULL" is the
    right answer to all three. Any caller that needs the distinction must ask
    tenancy directly and must not use this.

    The `SizeClassNotRuled` catch is BY TYPE and not a bare `except`: a
    genuinely unknown service code still raises `KeyError` and is a bug.
    """
    try:
        module = import_module("apps.tenancy.service_size_classes")
    except ImportError:  # pragma: no cover - tenancy always present
        return ()
    fn = getattr(module, "size_classes_for_service", None)
    if not callable(fn):  # pragma: no cover - defensive
        return ()
    not_ruled = getattr(module, "SizeClassNotRuled", None)
    try:
        rows = fn(service_code)
    except (not_ruled or NotImplementedError):
        return ()  # OQ-560 / OQ-561 — never ruled, so never seeded
    except KeyError:  # pragma: no cover - a service code that is not one of ten
        return ()
    return tuple(code for code, _name in rows)


def service_prices_by_size_class(service_code: str) -> bool | None:
    """**DOES THIS SERVICE'S PRICE VARY BY SIZE BAND?** — `None` when nobody
    has ruled it. `DEF-AST-7660`.

    The sanctioned cross-module read of
    `apps.rating.resolution.service_prices_by_size_class`. Assets needs the
    answer because `BR-RAT-108` picks the base charge with `size_class`, so a
    meter installed on a BANDED service with no size cannot be priced at all —
    `resolution._assert_service_is_ruled_sizeless` refuses by name, inside a
    bill run, months after the clerk pressed `Assign ✓`.

    ⚠ **IT IS NOT RE-DERIVED HERE, AND THAT IS THE WHOLE POINT OF THE
    IMPORT.** That function's docstring records `DEF-3098`: three places in
    this product needed to know whether a service is priced BY BAND and all
    three asked *"does this service have any size class rows?"* instead. The
    proxy was sound until `CR-062` gave solar, battery, storm water and
    broadband a CATALOGUE of installable equipment — rows that are a quantity
    to SUM rather than a rate axis — at which point *"no battery or solar
    customer could be billed"*. A fifth place asking the old question would be
    that defect a fifth time. `apps/metering/selectors._service_priced_on`
    already imports it for the same reason and says so.

    ⚠ **`None` IS A THIRD ANSWER AND IS NOT `False`.** A dimension whose bands
    were never put to the PO raises `SizeClassNotRuled`, and a code that is not
    one of the eleven raises `KeyError`. **The prime directive forbids
    resolving either by choosing a value**, so both are forwarded as the
    absence they are and the caller decides — and the caller here declines to
    REFUSE on a `None`, because refusing an install over a question nobody has
    answered would put the cost of our open question on a clerk.

    ⚠ **WHICH CODES ACTUALLY ANSWER `None`, MEASURED 2026-09-28 RATHER THAN
    QUOTED FROM A NEIGHBOURING DOCSTRING** (`DEF-AST-7660`; hard-won law 1).
    The obvious sentence to write here — *"thermal steam (`OQ-560`) and battery
    (`OQ-561`)"* — WAS written, and the test asserting it went RED. **Both of
    those services are RULED today and answer `False`:** thermal sums in tons
    and battery in kW, since `CR-062` gave them a capacity catalogue. The one
    unruled thing is the DIMENSION `thermal_heat_steam`, which is not a service
    code at all (`UNBANDED_SERVICE_DIMENSIONS` — *"thermal is half ruled, and
    this is the half that is not"*). Measured over all eleven codes: `True` for
    electric, water, gas, trash and fire · `False` for sewer, storm water,
    solar, broadband, thermal heat and battery · **`None` for none of them.**
    So today the third answer is reachable only from a dimension name or an
    unknown code — and `test_tc_b9` is what will say when that changes, which
    is the whole reason this paragraph names a test instead of a belief.

    ⚠ **THIS SEAM DOES NOT COLLAPSE THE THREE ANSWERS THE WAY
    `service_size_class_codes` ABOVE DOES.** That one is lawful only because
    its single caller is a seeder for which *"leave it NULL"* is right in all
    three cases. Here the three cases take three different actions, so they
    stay apart.
    """
    try:
        module = import_module("apps.rating.resolution")
    except ImportError:  # pragma: no cover - rating always present
        return None
    fn = getattr(module, "service_prices_by_size_class", None)
    if not callable(fn):  # pragma: no cover - defensive
        return None
    try:
        tenancy = import_module("apps.tenancy.service_size_classes")
    except ImportError:  # pragma: no cover - tenancy always present
        return None
    not_ruled = getattr(tenancy, "SizeClassNotRuled", None) or NotImplementedError
    try:
        return bool(fn(service_code))
    except not_ruled:
        return None  # OQ-560 / OQ-561 — never ruled, so never answered
    except KeyError:
        return None  # not one of the eleven services


def service_size_class_names() -> dict[str, str]:
    """`code` → the tenant's own NAME for every size class it holds, retired
    ones included — `W-58` → `Water 5/8"`.

    Wraps `tenancy.selectors.service_size_class_names()`, for the same B1/B2
    reason as every read in this block: tenancy hosts the list and assets may
    not reach into its ORM for the rows.

    ⚠ **NOT `service_size_class_terms()` ABOVE.** That one is the RATIFIED
    vocabulary — the forty codes law says exist — and it is what a free-text
    search resolves words against. This is what THIS utility actually has on
    its own S8 card, which is the ratified set minus anything Settings
    deactivated plus anything the tenant added (BR-TEN-071), and it is what a
    SCREEN must print: a tenant's own size has a name and the constant does not
    know it.

    ⚠ **EMPTY IS LAWFUL AND COSTS THE COLUMN, NEVER THE ROW** (BR-TEN-031,
    skip-until-wired). The caller draws its own absence; nothing here ever
    falls back to the code, because a code on screen is the breach this whole
    path exists to avoid (B14 rule 32, `DEF-CWP-4848`).
    """
    from apps.tenancy import selectors as tenancy_selectors

    reader = getattr(tenancy_selectors, "service_size_class_names", None)
    return dict(reader()) if reader is not None else {}


def service_size_class_terms() -> tuple[tuple[str, str], ...]:
    """Every ratified size class this tenant could record, as `(code, name)`.

    CR-089 G1 — the vocabulary half of `selectors.resolve_search_terms`. The
    codes alone (`service_size_class_codes` above) cannot answer a clerk typing
    *5/8 water*, because the words are in the NAME: `W-58` is *Water 5/8"* and
    that name is where both the size and the service live.

    ⚠ **THE SERVICES ARE THE ONES THIS TENANT HAS TURNED ON, NOT ALL ELEVEN.**
    A term for a service the utility does not run would offer a clerk a filter
    that matches nothing they own. The enabled set rides metering's seam, the
    same edge every other service read in this file uses (B1).

    ⚠ **A SERVICE WITH NO RULED LADDER CONTRIBUTES NOTHING AND IS NOT AN
    ERROR.** Sewer is ruled to have no size class (BR-RAT-015) and thermal
    steam was never put to the PO (`OQ-560`); `service_size_class_codes`
    collapses both to an empty tuple, and for a VOCABULARY that collapse is
    lawful — a word that does not exist cannot be typed either way.
    """
    try:
        module = import_module("apps.tenancy.service_size_classes")
    except ImportError:  # pragma: no cover - tenancy always present
        return ()
    fn = getattr(module, "size_classes_for_service", None)
    if not callable(fn):  # pragma: no cover - defensive
        return ()
    not_ruled = getattr(module, "SizeClassNotRuled", None)
    out: list[tuple[str, str]] = []
    for service_code in sorted(enabled_service_codes()):
        try:
            rows = fn(service_code)
        except (not_ruled or NotImplementedError):
            continue  # OQ-560 / OQ-561 — never ruled, so never a word
        except KeyError:  # pragma: no cover - a service code outside the eleven
            continue
        out.extend((code, name) for code, name in rows)
    return tuple(out)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-002@9d8d058 (story+rules snapshot hash — EP-AST-01 add-asset story; co-packets EP-AST-02/03/04@9d8d058)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-22 by the CR-028 AST-W1 lane (latest_read_for_asset added — DEF-592's read-only display seam; None renders a dash and feeds no rule, the stated DEF-079 distinction) · AMENDED 2026-08-22 by the CR-028 AST-W2 lane (typed_reads_for_asset — the served S50 Reads tab, `require` so a missing seam fails loudly rather than claiming an empty history; actor_display_names — the S61 actor-name read reused for the By/Technician columns; tenant_currency — CHAR(3) beside the maintenance cost total) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (asset_series_preview — tenancy's BE-06 preview row for the AST-05 number suggestion; a peek, never an allocation) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (unit_premises_geo_index + latest_reads_for_assets — the AST-03 map's two ONE-QUERY metering reads (DEF-324); both display-only, so the empty fallback is the stated DEF-079 distinction) · AMENDED 2026-08-22 by the CR-028 debt-sweep lane (D4: export_rollup_last_month — the BTM Exported KPI's served figure; D5: capture_final_read is WIRED end to end)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — seam module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: [2026-08-15 metering/assets/audit lane] read_count_for_asset IS NOW WIRED (DEF-079's metering leg) and its seam_known_gaps.txt row is deleted; invoice_line_count_for_asset stays dark and parked, and the reason is a SCHEMA gap — no invoice line names an asset — so the BR-AST-013 delete gate is half-sighted until a B2 addendum adds the column · customers/reads/billing seams are DOCUMENTED and unwired — their tables do not exist, so the fallbacks are true by construction · capture_final_read WIRED by the CR-028 debt-sweep lane (D5, 2026-08-22 — apps.metering.services.capture_final_read commits the manual read in the caller's transaction; the BIZ-COMPLETENESS refusal remains only for a deployment with no metering module)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

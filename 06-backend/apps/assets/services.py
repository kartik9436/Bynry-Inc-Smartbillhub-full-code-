# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (S49 registry — stage/type catalogs the list keys off) ·
#           US-AST-002 (S51 add asset, 3-identifier model, assign-on-create) ·
#           US-AST-003 (edit specs; delete only unreferenced inventory) ·
#           US-AST-004 (extended spec capture + register digits) · US-AST-006
#           (append-only assignment + maintenance history) · US-AST-007 (S53 log
#           repair/inspection/test with the legal transition) · US-AST-008 (S54
#           retire — terminal) · US-AST-009 (S55 reassign + final read) ·
#           US-AST-010 (S52 staged bulk import) · US-TEN-009 (S8 Reference-data
#           card grid — the "Meter types 5" card, TC-1) · US-TEN-010 (per-list
#           add/edit)   Screens: S49–S55, S16, S8
# Rules:    BR-AST-003 · BR-AST-008 · BR-AST-009 · BR-AST-010 · BR-AST-011 ·
#           BR-AST-012 · BR-AST-013 · BR-AST-014 · BR-AST-015 · BR-AST-017 ·
#           BR-AST-018 · BR-AST-020 · BR-AST-021 · BR-AST-022 · BR-AST-023 ·
#           BR-AST-026 · BR-AST-027 · BR-AST-028 · BR-AST-030 · BR-AST-031 ·
#           BR-AST-032 · BR-AST-033 · BR-AST-034 · BR-AST-035 · BR-AST-036 ·
#           BR-AST-037 · BR-AST-038 · BR-AST-042 · BR-AST-043 (meter_types +
#           read_methods are two separate seeded, tenant-extensible lists;
#           assets.read_method references the read_methods catalog) ·
#           BR-AST-044 (an asset carries BOTH classifications — asset_type AND
#           meter_type — alongside read_method; meter_type nullable) ·
#           BR-TEN-031 · BR-TEN-036
# Tests:    06-backend/tests/test_us_ast_001_003_registry.py ·
#           test_us_ast_004_006_detail.py · test_us_ast_007_009_lifecycle.py ·
#           test_us_ast_010_import.py (schema half: tests/test_w1_models.py)
# Impacts:  apps/assets/api.py · apps/assets/selectors.py · metering unit wizard
#           (BR-AST-028 premises-first creation) · tenancy /lookups registration
# ───────────────────────────────────────────────────────
"""assets service layer — the ONLY write path into the B2 r4 assets set
(LAW 0 / B8: api thin → services sole writer → selectors read).

The tables are METERING-owned and hosted in this app (models.py ownership
note); every cross-module call still goes through apps/assets/seams.py (B1) —
this module never imports another module's models. Every write lands its
audit row through core.audit (BE-03, CLAUDE.md rule 7); every refusal is a
catalog exception (BE-02). No money is computed anywhere here (BR-AST-025).

Eng dispositions recorded in the build report (not silently resolved):
- Lifecycle stages + asset types are seeded HERE, idempotently, for the current
  tenant. tenancy's provisioning fixture routes no entries for these lists
  (SEED_LIST_OWNERS covers 5 lists and none of them is an asset list) and the
  W1 migrations create the tables EMPTY — so an asset could not be created at
  all. `seed_reference_list` implements the documented tenancy seam for the day
  those routes land; `ensure_reference_catalogs()` is what makes creation work
  today. Both use the SAME ratified seed set (A5 v4 stages + BR-AST-031
  behavior classes + BR-AST-004/009/042 type set).
- BR-AST-026 per-type prefixes come from the RULE's own enumeration
  (M-/SM-/BF-/PV-/COM-/EV-/BAT-); the padded sequence comes from the tenant's
  `asset` number series (EP-TEN-08). Types the rule does not name keep the
  series' own literal prefix — nothing is invented.
- BR-AST-022 final-read capture is REFUSED (not faked) while `meter_reads`
  does not exist: the reads lane is W2 (B2 r16 #4).
- BR-AST-043 (PO 2026-08-09) adds `meter_types` and `read_methods` to the lists
  seeded here, and turns `assets.read_method` from a plain value into a catalog
  FK. One consequence worth the reviewer's eye: B2 r4's fourth plain value
  'na' is not among the PO's ratified five, so it is no longer accepted (a
  tenant that wants it ADDS it per BR-TEN-036).
- BR-AST-044 (PO 2026-08-09) answers the question BR-AST-043 left reported: an
  asset carries BOTH classifications, so `meter_type` is now accepted on create
  and edit, resolved against the tenant's `meter_types` catalog by the same
  contract as `read_method`. It is independent of `type` (asset_type=meter with
  meter_type=ami is the normal case) and it is NOT billing-affecting — the
  reasoning is recorded at BILLING_AFFECTING_FIELDS and on update_asset, stated
  rather than silently assumed.
"""

import logging
from contextvars import ContextVar
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.assets import models, seams
from core import audit as core_audit
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

logger = logging.getLogger("smartbillhub.assets")

# ── ratified reference data (BR-AST-031 stages · BR-AST-004/009/042 types) ──
# A5 v4 stage set; behavior class keeps filters/transitions sound whatever the
# tenant renames a stage to (BR-AST-031).
STAGE_AVAILABLE, STAGE_IN_SERVICE = "available", "in_service"
STAGE_OUT_OF_SERVICE, STAGE_TERMINAL = "out_of_service", "terminal"
# ⚠ **THE FIRST TWO NAMES LOST THEIR SECOND HALVES ON 2026-09-07 — PO ruling,
# verbatim: *"use only Inventory and Installed"*.** They read `Inventory/Spare`
# and `Installed/Active` from A5 v4 until then. A slash in a lookup name is two
# words competing to be the label, a clerk reads the first one anyway, and this
# one had reached a CUSTOMER's screen: the portal asset list printed the stored
# value with its slash in it.
#
# THE CODES DO NOT MOVE (`inventory`, `active`) and neither does any behaviour:
# BR-AST-031 exists precisely so a stage's LABEL is never load-bearing, and this
# is that rule being used for what it is for. `apps/tenancy/fixtures/
# lookup_defaults.json` carries the same two names at V2.48.0.10, and
# `assets/0011_po_2026_09_07_stage_names` renames the rows tenants already hold
# — a fixture reaches new tenants only.
SEED_LIFECYCLE_STAGES: tuple[tuple[str, str, str], ...] = (
    ("inventory", "Inventory", STAGE_AVAILABLE),
    ("active", "Installed", STAGE_IN_SERVICE),
    ("needs_repair", "Needs repair", STAGE_OUT_OF_SERVICE),
    ("in_repair", "In repair", STAGE_OUT_OF_SERVICE),
    ("retired", "Retired", STAGE_TERMINAL),
)
TAB_METERS, TAB_SUB_METERS, TAB_BTM = "meters", "sub_meters", "behind_the_meter"
SEED_ASSET_TYPES: tuple[tuple[str, str, str], ...] = (
    ("meter", "Meter", TAB_METERS),
    ("net_meter", "Net meter", TAB_METERS),
    ("sub_meter", "Sub-meter", TAB_SUB_METERS),
    ("backflow", "Backflow preventer", TAB_BTM),
    ("comms", "Comms endpoint", TAB_BTM),
    ("pv", "PV / solar", TAB_BTM),
    ("battery", "Battery storage", TAB_BTM),
    ("ev_charger", "EV charger", TAB_BTM),
    ("transformer", "Transformer (customer premise)", TAB_BTM),
    ("generator", "Generator (customer premise)", TAB_BTM),
    ("container_cart", "Container / Cart", TAB_BTM),  # BR-AST-042
    ("modem_cpe", "Modem / CPE", TAB_BTM),  # BR-AST-042
    # ── CR-063 · THE FIRE SERVICE LINE (`OQ-1361`, 2026-09-07) ─────────────
    # **APPENDED AS THE THIRTEENTH. NOTHING ABOVE IT MOVES** — the same posture
    # `SEED_READ_METHODS` took when it went from five to eight, and for the same
    # reason: `selectors.reference_list_options` sorts seeded-first by this
    # tuple's index, so a tenant reading its existing twelve down a dropdown
    # sees them in the same places with one new word after them.
    #
    # **WHY IT EXISTS.** Fire is the eleventh utility service (`BR-RAT-024`) and
    # it is CAPACITY-billed by a COUNT of what stands on the unit
    # (`BR-RAT-090`). The service, its six ratified diameters and its prices all
    # shipped on 2026-09-02 — and there was no asset type any of it could be
    # recorded against, so a tenant selling fire got service points nothing
    # could ever stand on and a `$0.00` fire line on every bill. That is
    # `DEF-AST-4493` and `OQ-1361`'s open half.
    #
    # **WHY ITS OWN ROW RATHER THAN `backflow`**, which `OQ-1361` names as the
    # nearest: a backflow preventer is a device ON a fire line, not the line;
    # the `FL-2 … FL-12` ladder is a pipe diameter and would not fit it; and
    # backflow preventers already stand on WATER connections here, so sharing
    # the type would let a water device be COUNTED as a fire line and overcharge
    # silently. The full argument is in `core.sample_fixture.FIRE_ASSET_TYPE`
    # and in the decision log for 2026-09-07.
    #
    # ⚠ **A HYDRANT IS STILL NOT HERE.** The PO ruled on 2026-09-03 that
    # *"hydrants are assets not utility service as of now"*, which removed `HYD`
    # from fire's SIZE list; giving a hydrant its own asset type is
    # `BR-AST-042`'s question and deliberately not answered by this row.
    ("fire_line", "Fire service line", TAB_BTM),
)
# BR-AST-043 CONFIRMED (PO 2026-08-09) — TWO separate reference lists, names
# verbatim from the rule (which carries the prototype's own casing).
# `meter_types` = what the meter IS; `read_methods` = how the read is
# COLLECTED. Neither is B2's `meter_source` enum ('ami','manual','import'),
# which stays the read-source marker on meter_reads (W2). Mirrored in
# apps/assets/migrations/0003_meter_types_and_read_methods.py — a migration must
# keep working when these constants later change; the RULE is the tiebreaker.
#
# ⚠ **THIS COMMENT SAID "five entries each" UNTIL 2026-08-27 AND IT IS NOW FIVE
# AND EIGHT — see BR-MET-142 and `SEED_READ_METHODS` below.** The count is no
# longer written here for either list: both are tenant-extensible (BR-TEN-036),
# so a number in a comment is a claim that goes stale the first time a utility
# adds a row, and this one did.
SEED_METER_TYPES: tuple[tuple[str, str], ...] = (
    ("ami", "AMI"),
    ("amr", "AMR"),
    ("walk_by", "walk-by"),
    ("sub_meter", "sub-meter"),
    ("master", "master"),
)
#: ⚠ **EIGHT SINCE 2026-08-27 (BR-MET-142, the PO ruling closing `OQ-392`).**
#: The first five are BR-AST-043's own, ratified 2026-08-09 and unchanged. The
#: last three were the six legacy `read_batches.source_detail` words that mapped
#: to NOTHING: `drive_by`, `self_read` and `field_visit`. The CR-038 W3 lane
#: refused to fold them onto neighbours and asked instead; the PO DELEGATED —
#: verbatim, *"(a) Rule each onto one of the five or you can add new
#: categories"* — and the build added all three.
#:
#: **WHY CATEGORIES RATHER THAN MAPPINGS, because a reader will ask.** Each
#: records a genuinely different fact: `self_read` is about WHO read the meter
#: (the customer did), `field_visit` about WHY somebody went (a technician
#: attended), `mobile` about WHAT DEVICE was used. Folding self-read into Manual
#: would assert a customer's reading and a clerk's are the same kind of record;
#: folding field-visit into Mobile would assert a technician's visit is a device
#: choice. And mapping would have RE-LABELLED history nobody verified.
#:
#: ⚠ **ORDER IS THE PICKER'S ORDER** (`selectors.reference_list_options` sorts
#: seeded-first by this tuple's index), so the three are APPENDED: a tenant that
#: already reads AMI · AMR · walk-by · Manual · Mobile down its dropdown sees the
#: same five in the same places, with three new words after them.
SEED_READ_METHODS: tuple[tuple[str, str], ...] = (
    ("ami", "AMI"),
    ("amr", "AMR"),
    ("walk_by", "walk-by"),
    ("manual", "Manual"),
    ("mobile", "Mobile"),
    ("drive_by", "Drive-by"),
    ("self_read", "Self-read"),
    ("field_visit", "Field visit"),
)
# BR-AST-009: service + explicit UoM required for measuring types only.
MEASURING_TYPES = frozenset({"meter", "net_meter", "sub_meter"})
# BR-AST-010: net metering is locked ON for net_meter, optional for
# meter/sub_meter, unavailable for non-measuring BTM types.
NET_METERING_OPTIONAL = frozenset({"meter", "sub_meter"})
# BR-AST-026 / US-AST-002 §5 — the prefixes the RULE names, verbatim.
ASSET_NO_PREFIXES: dict[str, str] = {
    "meter": "M-",
    "net_meter": "M-",
    "sub_meter": "SM-",
    "backflow": "BF-",
    "pv": "PV-",
    "comms": "COM-",
    "ev_charger": "EV-",
    "battery": "BAT-",
    # `CR-063` — `FS-` and NOT `FL-`, because `FL-2 … FL-12` are this service's
    # ratified SIZE CLASS codes. An asset numbered `FL-0001` standing beside a
    # size class `FL-6` in the same table reads as one vocabulary when it is
    # two, and the prefix was the only thing here free to choose.
    "fire_line": "FS-",
}
# BR-AST-027 (OQ-046 CLOSED): shipped START defaults, tenant-editable per type.
SEED_TEST_INTERVAL_MONTHS: dict[str, int] = {"backflow": 12, "meter": 96, "net_meter": 96}

# BR-AST-020 / A5 v4: the exact transition edges for the SEEDED stage codes.
# Tenant-added stages fall back to the behavior-class rule below.
MAINTENANCE_TRANSITIONS: dict[str, frozenset[str]] = {
    "inventory": frozenset(),
    "active": frozenset({"needs_repair"}),
    "needs_repair": frozenset({"in_repair"}),
    "in_repair": frozenset({"active"}),
    "retired": frozenset(),  # terminal — no transition leaves it (BR-AST-030)
}
MAINTENANCE_KINDS = ("repair", "inspection", "test")
RETIRE_REASONS = ("end_of_life", "failed", "replaced", "removed")
# CR-028 AST-W4 (§10-D4 / BR-AST-047): the retire step-3 treatment radio —
# recorded on the asset, POSTED NOWHERE (hard rule 5; a future finance link is
# a new CR, which is exactly why the pair is stored).
BOOK_VALUE_TREATMENTS = ("write_off", "warranty_claim", "hold")
# NOTE: the former `READ_METHODS = ("ami","amr","walk_by","na")` hardcoded tuple
# is GONE — BR-AST-043 makes read methods a tenant-extensible catalog, so the
# allowed set is read from `read_methods` at validation time. B2 r4's fourth
# plain value 'na' has no counterpart in the PO's ratified five and is therefore
# no longer accepted; a tenant that needs it ADDS it (BR-TEN-036). REPORTED.

# BR-AST-034's 10,000-row cap governed the RETIRED staged path (AST-W3-T5);
# volume on the runner is CR-026's law — 100,000-row cap, ASYNC_ROW_BAR 5,000
# (`apps/metering/import_runs.py`). The constant is gone with the path.
# ⚠ BR-AST-034's *"re-upload updates SPEC fields ONLY"* is SUPERSEDED (PO
# 2026-09-30, *"we need to override it in case of upload"*, BR-AST-541): this
# set NO LONGER filters the upload. It still names what BR-AST-012 calls
# billing-affecting — the fields whose change raises the forward-only warning
# on an edit. The set is BR-AST-012's own enumeration, verbatim: multiplier · unit ·
# net_metering · service. DELIBERATELY ABSENT (BR-AST-044, stated not assumed):
# `meter_type` is a CLASSIFICATION, not a pricing input — no rating input, no
# quantity, no invoice line reads it; correcting a mis-tagged AMI meter to AMR
# restates nothing. So it is edited like any spec field (audited before/after,
# BR-AST-012 first clause) and carries NO forward-only warning. `read_method`
# and `type` sit outside the set for the same reason, exactly as before.
# ⚠ **`size_class` JOINS THE SET 2026-08-27 (BR-AST-501, out of DEF-514) — AND
# IT JOINS BY BR-AST-012's OWN STATED CRITERION, NOT BY A NEW ONE.** The
# paragraph above admits `meter_type` is excluded because *"no rating input, no
# quantity, no invoice line reads it"*. The connection size fails that test on
# the first clause: `rating.selectors.pricing_inputs` NARROWS THE TIER LADDER on
# it (DEF-433/DEF-484) and BR-RAT-108's base grid selects a base charge with it.
# Worked, on r10's own figures: a 2" water connection re-tagged from `W-58` to
# `W-2` moves the ladder from `3.20 / 4.80 / 7.20` to `3.45 / 5.10 / 7.70` — the
# customer's price changes and, without this line, the person who changed it is
# told nothing even though reads already exist. BR-AST-012 enumerated four
# fields in a product that could not record a fifth; this is that enumeration's
# rule applied to a column it never saw.
BILLING_AFFECTING_FIELDS = frozenset(
    {"multiplier", "unit", "net_metering", "service", "size_class"}
)


# ── shared plumbing (same shape as apps/tenancy/services.py) ────────────────
def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _audit(
    actor: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=before,
        after=after,
    )


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse_fields(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


def _payload_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="assets.payload_not_object")
    return payload


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


def _as_date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        _refuse_fields([_field_error(field, errors.VAL_FORMAT, "assets.bad_date")])
    return None


# ── reference catalogs (BR-AST-031 / BR-AST-004 / BR-TEN-036) ───────────────
#: ⛔ **DEF-1075 — WHICH TENANT'S CATALOGS THIS EXECUTION CONTEXT HAS ALREADY
#: ENSURED.** A `ContextVar`, not a module global, for the reason
#: `core.tenancy._current_tenant` is one: it is safe across async tasks and it
#: does not leak between threads. See `ensure_reference_catalogs` for why.
_CATALOGS_ENSURED: ContextVar[Any] = ContextVar("smartbillhub_assets_catalogs", default=None)


def ensure_reference_catalogs(*, force: bool = False) -> dict[str, int]:
    """Idempotent seed of the FOUR asset-owned reference lists for the CURRENT
    tenant: asset types, lifecycle stages, and the BR-AST-043 meter_types /
    read_methods catalogs. Seeded rows are is_system: deactivatable, never
    deletable (BR-TEN-036). Called from every write path that needs a stage,
    a type or a read method — the migrations create these tables EMPTY for
    tenants provisioned AFTER them, so without this an asset could not be
    created at all (reported).

    ⛔ **MEMOISED PER EXECUTION CONTEXT PER TENANT — `DEF-1075`, AND THIS IS
    THE FIX FOR A 500 THE PRODUCT OWNER WATCHED HAPPEN.**

    The Product Owner's twenty-row meter import returned `HTTP 500` at stage 4
    and *"Nothing was saved"*. The deployed traceback ends

        File ".../gunicorn/workers/base.py", line 199, in handle_abort
            sys.exit(1)
        SystemExit: 1
        [INFO] Worker exiting (pid: 2105)

    — `handle_abort` is gunicorn's SIGABRT handler and the arbiter sends
    SIGABRT to a worker past `--timeout` (`GUNICORN_TIMEOUT:-60`). **There was
    no exception.** The request was still running at sixty seconds and was
    killed inside the transaction, so Postgres rolled it back and the screen's
    sentence was exactly true.

    **WHY twenty rows took over a minute, counted rather than estimated.** This
    function issues **32 `get_or_create` calls** every time it runs (14 asset
    types + 5 lifecycle stages + 5 meter types + 8 read methods), and it was
    called at the top of `stage_by_code`, `type_by_code` AND `_flat_catalog_row`
    — three of which one asset creation makes. So:

        32 queries × 3 calls  =    96 per row
        96 × 20 rows          = 1,920 round trips

    At 0.2 ms — a local socket, which is every test in this repo — that is
    0.4 s and **invisible**. At 15–20 ms against a remote database it is 29–38
    seconds before a single asset, an audit row or an RLS check is paid for.
    **The bug is LATENCY-SHAPED, and a test harness has none**, which is why
    the end-to-end commit-path test passes and production dies.

    ⚠ **THE SEED'S GUARANTEE IS UNCHANGED AND MUST STAY UNCHANGED.** Its
    original placement (BR-AST-043 gap lane, 2026-08-09) was RIGHT about what
    it buys — creation has to work on a tenant provisioned AFTER the W1
    migrations, whose catalog tables are EMPTY — and wrong only about paying
    for it sixty times inside one request. The first call in a context still
    seeds; the rest are free.

    ⚠ **SAFE TO SKIP, AND `BR-TEN-036` IS WHY.** Seeded rows are `is_system`:
    deactivatable, never deletable. So a catalog that exists at the start of a
    context cannot stop existing during it, and there is no state this memo can
    be stale against. `force=True` re-runs it regardless, for the seeders and
    the tests that assert idempotency by calling it twice.

    ⚠ **KEYED ON THE TENANT, so a context that moves between tenants re-seeds
    for each** — the memo holds one tenant id, never a set, and a different
    tenant simply misses it. This is the `_current_tenant` posture applied to a
    derived fact.

    ⚠ **DO NOT RAISE `GUNICORN_TIMEOUT` INSTEAD.** `docker-entrypoint.sh`
    already says why in its own comment — *"raising it hides the symptom"* —
    and a 20-row import must not need 60 seconds.
    """
    tenant_id = _tenant_id()
    made = {
        "asset_types": 0,
        "asset_lifecycle_stages": 0,
        "meter_types": 0,
        "read_methods": 0,
    }
    if not force and _CATALOGS_ENSURED.get() == tenant_id and tenant_id is not None:
        # Nothing was made, and that is the honest answer rather than a cached
        # count: the caller asked "are the catalogs there", and returning the
        # FIRST call's figures would report rows this call did not write.
        return made
    for code, name, category in SEED_ASSET_TYPES:
        _, created = models.AssetType.objects.get_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={"name": name, "category": category, "is_system": True, "active": True},
        )
        made["asset_types"] += int(created)
    for code, name, behavior in SEED_LIFECYCLE_STAGES:
        _, created = models.AssetLifecycleStage.objects.get_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={"name": name, "behavior_class": behavior, "is_system": True, "active": True},
        )
        made["asset_lifecycle_stages"] += int(created)
    for model, seeds, key in (
        (models.MeterType, SEED_METER_TYPES, "meter_types"),
        (models.ReadMethod, SEED_READ_METHODS, "read_methods"),
    ):
        for code, name in seeds:
            _, created = model.objects.get_or_create(
                tenant_id=tenant_id,
                code=code,
                defaults={"name": name, "is_system": True, "active": True},
            )
            made[key] += int(created)
    _CATALOGS_ENSURED.set(tenant_id)
    return made


def seed_reference_list(list_code: str, entries: list[dict[str, Any]], fixture_version: str) -> int:
    """The tenancy reference-data seeding seam (apps/tenancy/seams.py contract),
    routed here from metering (the registry owner in tenancy's LOOKUP_LISTS).
    An empty fixture list falls back to this module's RATIFIED seed set.

    RESOLVED (verified 2026-08-22, CR-028 debt sweep D7): metering's
    `seed_reference_list` router forwards ALL FOUR codes here (meter_types ·
    read_methods · asset_types · asset_statuses — DEF-017 fixed its two gaps),
    and tenancy's LOOKUP_LISTS + SEED_LIST_OWNERS both declare them, so
    provisioning-fixture seeding runs end to end. The paragraph this replaces
    reported the 2026-08-09 state; `ensure_reference_catalogs()` remains the
    write-path safety net either way."""
    owned = ("asset_types", "asset_statuses", "meter_types", "read_methods")
    if list_code not in owned:
        raise KeyError(f"assets owns no reference list {list_code!r} (BR-TEN-031)")
    made_key = {
        "asset_types": "asset_types",
        "asset_statuses": "asset_lifecycle_stages",
        "meter_types": "meter_types",
        "read_methods": "read_methods",
    }[list_code]
    if not entries:
        return ensure_reference_catalogs()[made_key]
    tenant_id = _tenant_id()
    flat_model = {"meter_types": models.MeterType, "read_methods": models.ReadMethod}.get(list_code)
    created = 0
    for entry in entries:
        code = str(entry.get("code", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not code or not name:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="assets.reference_fixture_invalid",
                params={"list": list_code},
            )
        if flat_model is not None:
            # BR-AST-043: flat named sets — no tab key, no behavior class.
            if not flat_model.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
                flat_model.objects.create(tenant_id=tenant_id, code=code, name=name, is_system=True)
                created += 1
        elif list_code == "asset_types":
            exists = models.AssetType.objects.filter(
                tenant_id=tenant_id, code__iexact=code
            ).exists()
            if not exists:
                models.AssetType.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    category=str(entry.get("category") or TAB_BTM),
                    is_system=True,
                )
                created += 1
        else:
            exists = models.AssetLifecycleStage.objects.filter(
                tenant_id=tenant_id, code__iexact=code
            ).exists()
            if not exists:
                models.AssetLifecycleStage.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    behavior_class=str(entry.get("behavior_class") or STAGE_AVAILABLE),
                    is_system=True,
                )
                created += 1
    return created


def stage_by_code(code: str) -> models.AssetLifecycleStage:
    ensure_reference_catalogs()
    row = models.AssetLifecycleStage.objects.filter(
        tenant_id=_tenant_id(), code__iexact=code
    ).first()
    if row is None:  # pragma: no cover - the seeded set always resolves
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="assets.stage_missing", params={"stage": code}
        )
    return row


def type_by_code(code: Any, *, field: str = "type") -> models.AssetType:
    ensure_reference_catalogs()
    row = models.AssetType.objects.filter(
        tenant_id=_tenant_id(), code__iexact=str(code or ""), active=True
    ).first()
    if row is None:
        _refuse_fields(
            [_field_error(field, errors.VAL_UNKNOWN_LOOKUP, "assets.type_unknown", value=str(code))]
        )
    return row


def _flat_catalog_row(model: Any, ref: Any, *, field: str, message_key: str) -> Any:
    """Resolve one BR-AST-043 flat-catalog reference (meter_types /
    read_methods) for the CURRENT tenant. Accepts the row's CODE
    (case-insensitively, '-' and '_' interchangeable) or its uuid id. Blank →
    None. An unknown reference is REFUSED naming the tenant's own ACTIVE set —
    both lists are tenant-extensible (BR-TEN-036), so the allowed values are
    data, never a hardcoded tuple."""
    ensure_reference_catalogs()
    tenant_id = _tenant_id()
    if _looks_like_uuid(ref):
        row = model.objects.filter(tenant_id=tenant_id, pk=ref, active=True).first()
    else:
        normalized = (_text(ref, 60) or "").lower().replace("-", "_")
        if not normalized:
            return None
        row = model.objects.filter(
            tenant_id=tenant_id, code__iexact=normalized, active=True
        ).first()
    if row is None:
        allowed = list(
            model.objects.filter(tenant_id=tenant_id, active=True)
            .order_by("code")
            .values_list("code", flat=True)
        )
        _refuse_fields(
            [
                _field_error(
                    field,
                    errors.VAL_UNKNOWN_LOOKUP,
                    message_key,
                    value=str(ref),
                    allowed=allowed,
                )
            ]
        )
    return row


def read_method_by_code(code: Any, *, field: str = "read_method") -> models.ReadMethod | None:
    """BR-AST-043: resolve a read-method reference against the tenant's
    catalog. Blank → None (a non-measuring asset collects no read at all)."""
    return _flat_catalog_row(
        models.ReadMethod, code, field=field, message_key="assets.read_method_unknown"
    )


def meter_type_by_code(code: Any, *, field: str = "meter_type") -> models.MeterType | None:
    """BR-AST-044: resolve a meter-type reference against the tenant's catalog
    — the SAME contract as read_method_by_code, because the rule makes the two
    peers. Blank → None: `meter_type` is nullable, and BR-AST-044 says
    non-measuring assets leave it null.

    Availability is enforced by the caller, not here (PO ruling 2026-08-09,
    BR-AST-044 as amended): meter_type is UNAVAILABLE on non-measuring types —
    the same shape as BR-AST-010's net-metering refusal — so setting one on a
    PV or a battery is refused rather than quietly stored."""
    return _flat_catalog_row(
        models.MeterType, code, field=field, message_key="assets.meter_type_unknown"
    )


def uom_used_by_count(uom_code: str) -> int:
    """The BR-TEN-029 metering-side half: assets carrying this explicit unit."""
    return models.Asset.objects.filter(tenant_id=_tenant_id(), unit__iexact=uom_code).count()


# ── BR-AST-026 asset numbering ──────────────────────────────────────────────
def suggest_asset_no(type_code: str) -> str | None:
    """Allocate the next user asset number: padded sequence from the tenant's
    `asset` series (EP-TEN-08) + the per-type prefix BR-AST-026 names. A type
    the rule does not name keeps the series' own literal prefix. Returns None
    when the tenant has no series row — the caller must then be given an
    explicit number (never a fabricated one)."""
    series_format = seams.asset_series_format()
    if series_format is None:
        return None
    try:
        rendered = core_numbering.next_number(core_numbering.ASSET, seams.tenant_today())
    except core_numbering.NumberingError:
        return None
    prefix = ASSET_NO_PREFIXES.get(type_code)
    literal = series_format.split("{", 1)[0]
    if prefix and literal and rendered.startswith(literal):
        return prefix + rendered[len(literal) :]
    return rendered


# ── asset validation (US-AST-002/004 §5 field maps) ─────────────────────────
def _validate_asset(
    payload: dict[str, Any],
    *,
    partial: bool,
    current: Any = None,
    custom_fields_screen: str | None = None,
) -> dict[str, Any]:
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    known = {
        "asset_no",
        "serial_no",
        # BR-AST-049 — the utility's OWN legacy reference. Accepted on create
        # and on update: a first migration that did not carry it, and a
        # correction pass that adds it, are both ordinary.
        "external_ref",
        "type",
        "meter_type",  # BR-AST-044: the SECOND classification, independent of `type`
        "read_method",
        "multiplier",
        # BR-AST-500 (DEF-514) — the connection's size class. Accepted on
        # create AND on update: a meter is often loaded before anyone knows its
        # size, and a correction pass that adds it is ordinary. Clearing it back
        # to NULL is legal and means "we no longer claim to know", which is the
        # state every row was in before the column existed.
        #
        # ⚠ **A COLUMN WITH NO WRITER IS THE DEFECT THIS LINE EXISTS TO AVOID
        # REPEATING (DEF-515).** `rate_plans.outside_city_factor` landed with
        # its migration, its read path and its engine arithmetic and NO write
        # path at any layer, so a real utility could compute the surcharge and
        # never ask for it. The size column would have been the same shape one
        # table across.
        "size_class",
        "unit",
        "net_metering",
        "manufacturer",
        "model",
        "manufacturer_model",
        "install_date",
        "form_class",
        "register_digits",
        "firmware_version",
        "seal_no",
        "warranty_end",
        "last_test_date",
        "test_interval_months",
        "location_note",
        "allocation_rule",
        "loss_tolerance_pct",
        # ── CR-028 (BR-AST-047 + B16 §4.7b) — accepted on the create/update
        # payload now that the 0007/0008 columns exist. This closes the
        # sample_data exception ("collapses into the create payload the day it
        # lands") — the AST-W3 import lane landed it because the three import
        # targets write these fields through this one validator.
        "supplier",
        "purchase_cost",
        "purchase_date",
        "depreciation_method",
        "expected_life_years",
        "certification_due",
        "export_capacity_kw",
        "allocation_share_pct",
        "parent_asset_no",
        "parent_asset_id",
        "service",
        "service_point_id",
        "unit_id",
        "status",
        # BR-AST-030: the linked-audit-note input for a recreate-after-mistaken
        # -retirement. Consumed by the audit trail; it is NOT a column.
        "recreated_from_asset_id",
        # `AST-B-14` (PO 2026-09-12) — the reading on the dial the day the meter
        # goes in. NEITHER IS A COLUMN ON `assets`: they are handed straight to
        # metering, which writes ONE `meter_reads` row inside this create's own
        # transaction. They are named here only so `_validate_asset` stops
        # refusing them as unknown; nothing below puts either into `out`, so
        # neither can ever reach `Asset.objects.create`.
        "opening_read",
        "opening_read_date",
        # `CR-161-BRC10` W2 · `DEF-AST-9171` — the tenant's own fields. See
        # the block below the refusal for how they are validated.
        "custom_data",
    }
    for field in payload:
        if field not in known:
            fe.append(_field_error(field, errors.VAL_FORMAT, "assets.unknown_field"))
    _refuse_fields(fe)

    # ── `CR-161-BRC10` W2 · `DEF-AST-9171` — custom fields, ONE validator ──
    # A CREATE always asks (a required field placed Input on the create's
    # screen must bind even when nothing was sent); an EDIT asks only when the
    # payload names `custom_data`, and merges into the stored answers, so a
    # panel edit or a file without the columns leaves them untouched. Every
    # door reaches this function, which is why the screen is a parameter here
    # rather than a check in each caller.
    if "custom_data" in payload or not partial:
        out["custom_data"] = seams.validate_custom_data(
            payload.get("custom_data"),
            screen=custom_fields_screen,
            existing=(current.custom_data or {}) if current is not None else None,
        )

    type_code = str(
        payload.get("type") or (current.type.code if current is not None else "")
    ).strip()
    if "type" in payload or not partial:
        out["type"] = type_by_code(payload.get("type"))
        type_code = out["type"].code

    if "asset_no" in payload:
        out["asset_no"] = _text(payload["asset_no"], 60)
    for field, limit in (
        ("serial_no", 64),
        # BR-AST-049. 120, `customers.external_ref`'s own practical bound —
        # a legacy key is an identifier, never a sentence.
        ("external_ref", 120),
        ("form_class", 60),
        # BR-AST-500 — 60, the SAME bound `rating.services._size_rows` puts on
        # its copy of this vocabulary (`_text(item, "size_class", …,
        # max_length=60)`). Two columns holding one code must not disagree
        # about how long the code may be, or a size that saves on a rate
        # schedule refuses on the meter it prices.
        ("size_class", 60),
        ("firmware_version", 60),
        ("seal_no", 60),
        ("manufacturer", 120),
        ("model", 120),
        ("allocation_rule", 30),
    ):
        if field in payload:
            out[field] = _text(payload[field], limit)
    if "manufacturer_model" in payload:
        # US-AST-002 §5: one input stored across both columns, split on "·";
        # the whole string goes to manufacturer when there is no separator.
        raw = _text(payload["manufacturer_model"], 240) or ""
        manufacturer, _, model = raw.partition("·")
        out["manufacturer"] = manufacturer.strip() or None
        out["model"] = model.strip() or None
    if "location_note" in payload:
        out["location_note"] = _text(payload["location_note"], 280)  # BR-AST-014 ≤280
    if "meter_type" in payload:
        # BR-AST-044: the meter's own class (AMI · AMR · walk-by · sub-meter ·
        # master) — resolved and refused exactly like read_method below, and
        # entirely independent of `type`: asset_type=meter + meter_type=ami is
        # the normal case, not a contradiction. Clearing it (null/"") is legal.
        out["meter_type"] = meter_type_by_code(payload["meter_type"])
    if "read_method" in payload:
        # BR-AST-043: a catalog row, not a plain value. read_method_by_code
        # refuses an unknown code itself (naming the tenant's own active set).
        out["read_method"] = read_method_by_code(payload["read_method"])
    for field in ("install_date", "warranty_end", "last_test_date"):
        if field in payload:
            out[field] = _as_date(payload[field], field)
    # ── CR-028 valuation & certification (BR-AST-047 · B16 §4.7b) ───────────
    for field in ("purchase_date", "certification_due"):
        if field in payload:
            out[field] = _as_date(payload[field], field)
    if "supplier" in payload:
        out["supplier"] = _text(payload["supplier"], 120)  # D5: free text, no list
    if "depreciation_method" in payload:
        out["depreciation_method"] = _text(payload["depreciation_method"], 60)
    if "purchase_cost" in payload:
        # Money: Decimal only, stored 4dp (rule 2 / D10). Zero is lawful — a
        # donated meter costs nothing and is still an asset.
        out["purchase_cost"] = _decimal(
            payload["purchase_cost"], "purchase_cost", fe, positive=False
        )
    if "export_capacity_kw" in payload:
        out["export_capacity_kw"] = _decimal(
            payload["export_capacity_kw"], "export_capacity_kw", fe, positive=False
        )
    if "allocation_share_pct" in payload:
        # A percentage share of the master (6dp stored — rule 2). NULL means
        # "metered, not allocated" (B16 §4.7b), so clearing it is legal.
        share = _decimal(
            payload["allocation_share_pct"], "allocation_share_pct", fe, positive=False
        )
        if share is not None and share > 100:
            fe.append(
                _field_error(
                    "allocation_share_pct", errors.VAL_RANGE, "assets.allocation_share_range"
                )
            )
        else:
            out["allocation_share_pct"] = share
    if "expected_life_years" in payload:
        raw = payload["expected_life_years"]
        if raw in (None, ""):
            out["expected_life_years"] = None
        else:
            try:
                years = int(raw)
            except (TypeError, ValueError):
                years = 0
            if years < 1:
                fe.append(
                    _field_error(
                        "expected_life_years", errors.VAL_RANGE, "assets.test_interval_range"
                    )
                )
            else:
                out["expected_life_years"] = years
    if "multiplier" in payload:
        out["multiplier"] = _decimal(payload["multiplier"], "multiplier", fe, positive=True)
    if "loss_tolerance_pct" in payload:
        out["loss_tolerance_pct"] = _decimal(
            payload["loss_tolerance_pct"], "loss_tolerance_pct", fe, positive=False
        )
    if "register_digits" in payload:
        raw = payload["register_digits"]
        if raw in (None, ""):
            out["register_digits"] = 9  # BR-AST-015: clearing reverts to the default
        else:
            try:
                digits = int(raw)
            except (TypeError, ValueError):
                digits = 0
            # ⚠ UPPER BOUND 9 → 10 ON 2026-09-30 (plan U4: an uploaded register
            # is 4 to 10 digits, PO-confirmed). The upload's own rule refuses
            # 1–3 by name at stage 3 (`AST.REGISTER_DIGITS_IN_RANGE`); the lower
            # bound HERE stays 1 so no meter already saved by a clerk becomes
            # unsaveable. A 10 the rehearsal accepted must not then be refused
            # from under the write — `DEF-2519`'s shape.
            if not 1 <= digits <= 10:
                fe.append(
                    _field_error(
                        "register_digits", errors.VAL_RANGE, "assets.register_digits_range"
                    )
                )
            else:
                out["register_digits"] = digits
    if "test_interval_months" in payload:
        raw = payload["test_interval_months"]
        if raw in (None, ""):
            out["test_interval_months"] = None
        else:
            try:
                months = int(raw)
            except (TypeError, ValueError):
                months = 0
            if months < 1:
                fe.append(
                    _field_error(
                        "test_interval_months", errors.VAL_RANGE, "assets.test_interval_range"
                    )
                )
            else:
                out["test_interval_months"] = months
    if "unit" in payload:
        out["unit"] = _text(payload["unit"], 30)
    if "net_metering" in payload:
        out["net_metering"] = bool(payload["net_metering"])
    _refuse_fields(fe)

    # BR-AST-044 (as amended, PO 2026-08-09): meter_type is a measuring-asset
    # classification — unavailable on non-measuring types, mirroring BR-AST-010.
    if type_code and type_code not in MEASURING_TYPES and out.get("meter_type"):
        _refuse_fields(
            [
                _field_error(
                    "meter_type",
                    errors.VAL_FORMAT,
                    "assets.meter_type_unavailable",
                    type=type_code,
                )
            ]
        )

    # BR-AST-010: locked ON for net_meter; unavailable for non-measuring BTM.
    if type_code == "net_meter":
        out["net_metering"] = True
    elif type_code and type_code not in NET_METERING_OPTIONAL and out.get("net_metering"):
        _refuse_fields(
            [
                _field_error(
                    "net_metering",
                    errors.VAL_FORMAT,
                    "assets.net_metering_unavailable",
                    type=type_code,
                )
            ]
        )
    return out


def _decimal(value: Any, field: str, fe: list[dict[str, Any]], *, positive: bool) -> Decimal | None:
    """HR-2: NUMERIC(18,6) via Decimal only — never float."""
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        fe.append(_field_error(field, errors.VAL_FORMAT, "assets.not_a_number"))
        return None
    if positive and parsed <= 0:  # US-MET-003 TC-7 / BR-AST-009: multiplier > 0
        fe.append(_field_error(field, errors.VAL_RANGE, "assets.must_be_positive"))
        return None
    if not positive and parsed < 0:
        fe.append(_field_error(field, errors.VAL_RANGE, "assets.must_not_be_negative"))
        return None
    return parsed


def _asset_row(asset_id: Any, *, locked: bool = False) -> models.Asset:
    if not _looks_like_uuid(asset_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    qs = models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id)
    if locked:
        qs = qs.select_for_update()
    row = qs.select_related("type", "status").first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _asset_by_external_ref(external_ref: str) -> models.Asset | None:
    """BR-AST-049 — the row a utility's OWN legacy reference names.

    Case-insensitive, matching the partial unique index that backs it
    (`uq_assets_tenant_external_ref_ci`): `MTR-118` and `mtr-118` are one
    device in every legacy export, so a probe that distinguished them would
    report "available" for a value the database is about to refuse."""
    cleaned = str(external_ref or "").strip()
    if not cleaned:
        return None
    return (
        models.Asset.objects.filter(tenant_id=_tenant_id(), external_ref__iexact=cleaned)
        .order_by("created_at")
        .first()
    )


def _refuse_duplicate_external_ref(external_ref: Any, *, exclude_pk: Any = None) -> None:
    """BR-AST-049's HARD BLOCK, refused BY NAME rather than as an IntegrityError.

    ⚠ **THE DATABASE ALREADY REFUSES THIS** — the partial unique index is the
    guarantee, and this check is not it (hard-won law 1). What this adds is a
    SENTENCE: without it the operator gets a 500 off a constraint name, and an
    import row would abort the whole run instead of being reported as one bad
    row beside the 1,846 good ones."""
    cleaned = str(external_ref or "").strip()
    if not cleaned:
        return
    other = _asset_by_external_ref(cleaned)
    if other is not None and (exclude_pk is None or other.pk != exclude_pk):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-AST-049",
            message_key="assets.external_ref_duplicate",
            params={"external_ref": cleaned, "asset_no": other.asset_no},
        )


def _asset_by_no(asset_no: str) -> models.Asset | None:
    return (
        models.Asset.objects.filter(tenant_id=_tenant_id(), asset_no__iexact=asset_no)
        .select_related("type", "status")
        .first()
    )


def _check_measuring_requirements(type_code: str, service_ref: Any, unit_value: str | None) -> None:
    """BR-AST-009: a measuring type (meter/net_meter/sub_meter) must declare a
    service and carry an EXPLICIT UoM (CLAUDE.md rule 3); "—" is allowed only
    for non-measuring BTM types.

    `service_ref` is the service CODE or an already-resolved service_point id:
    B2 r4 stores the service via `service_point_id`, which only exists once the
    asset sits on a unit — so an inventory spare (US-AST-001 §4's M-5099, an
    Electric meter in Inventory) declares its service on the form, keeps its
    explicit UoM on `assets.unit`, and gains the service point at assignment.
    The unassigned service declaration has no column to live in; that gap is
    reported, not invented around."""
    if type_code not in MEASURING_TYPES:
        return
    fe: list[dict[str, Any]] = []
    if not service_ref:
        fe.append(_field_error("service", errors.VAL_REQUIRED, "assets.service_required"))
    if not unit_value:
        fe.append(_field_error("unit", errors.VAL_REQUIRED, "assets.uom_required"))
    _refuse_fields(fe)


def _resolve_parent(payload: dict[str, Any], type_code: str) -> models.Asset | None:
    """BR-AST-003: a sub-meter REQUIRES a same-tenant meter/net-meter parent."""
    ref = payload.get("parent_asset_id") or payload.get("parent_asset_no")
    parent: models.Asset | None = None
    if ref:
        parent = _asset_by_no(str(ref))
        if parent is None:
            parent = (
                models.Asset.objects.filter(tenant_id=_tenant_id(), pk=ref)
                .select_related("type")
                .first()
                if _looks_like_uuid(ref)
                else None
            )
    if type_code == "sub_meter" and parent is None:
        _refuse_fields(
            [_field_error("parent_asset_id", errors.VAL_REQUIRED, "assets.parent_required")]
        )
    if parent is not None and parent.type.code not in ("meter", "net_meter"):
        _refuse_fields(
            [_field_error("parent_asset_id", errors.VAL_FORMAT, "assets.parent_must_be_a_meter")]
        )
    return parent


def _looks_like_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


# ── create (US-AST-002 · BR-AST-008/011/026/033) ────────────────────────────
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-032")
def _capture_opening_read(
    actor: Any,
    data: dict[str, Any],
    asset: Any,
    type_code: str,
    install_date: Any,
) -> None:
    """`AST-B-14` — hand a typed dial reading to metering, or refuse the create.

    Three refusals, each naming the field a clerk can see on step 2:

    * a reading on a NON-MEASURING asset. A backflow preventer has no register,
      so there is nothing the number could mean. The wizard does not draw the
      field for a device at all; this is the server saying the same thing to a
      stale form or a direct API call.
    * a reading with NO DATE and NO INSTALL DATE. A reading that cannot be
      placed in a period cannot be billed from, and guessing today would put a
      meter's first reading on the day somebody happened to type it.
    * metering absent. The seam answers None, and None is refused rather than
      skipped — see `seams.capture_opening_read`.

    ⚠ **THE DATE DEFAULTS TO THE INSTALL DATE, WHICH IS THE DRAWING'S OWN
    SENTENCE** (*"Defaults to the install date on the next step"*). The default
    is applied HERE and not in the client, so an API caller and the wizard
    cannot disagree about what a dateless opening read means.

    A blank reading is not an omission to complain about: leaving it empty is a
    first-class answer and the field's helper says what it costs (*"Leave it
    blank and the first bill measures from zero"*).
    """
    raw = data.get("opening_read")
    if raw is None or str(raw).strip() == "":
        return
    if type_code not in MEASURING_TYPES:
        _refuse_fields(
            [
                _field_error(
                    "opening_read",
                    errors.VAL_FORMAT,
                    "assets.opening_read_not_measuring",
                )
            ]
        )
    read_at = data.get("opening_read_date") or install_date
    if read_at is None or str(read_at).strip() == "":
        _refuse_fields(
            [
                _field_error(
                    "opening_read_date",
                    errors.VAL_REQUIRED,
                    "assets.opening_read_date_required",
                )
            ]
        )
    captured = seams.capture_opening_read(
        asset_id=asset.id,
        value=str(raw).strip(),
        read_at=str(read_at),
        actor=actor,
    )
    if captured is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-AST-022",
            message_key="assets.opening_read_unavailable",
            params={"asset_no": asset.asset_no},
        )


def create_asset(
    actor: Any, payload: Any, *, custom_fields_screen: str | None = None
) -> dict[str, Any]:
    """S51 add-asset. Duplicate asset # = HARD BLOCK; duplicate serial =
    warn-but-allow with the acknowledgement audited (BR-AST-033).

    `custom_fields_screen` — `"S51"` from Add asset's route; `None` from the
    seeds and every other caller (`CR-161-BRC10` W2, `DEF-AST-9171`)."""
    data = _payload_dict(payload)
    with transaction.atomic():
        return _create_asset_inner(actor, data, custom_fields_screen=custom_fields_screen)


def _create_asset_inner(
    actor: Any,
    data: dict[str, Any],
    *,
    installed: bool = True,
    custom_fields_screen: str | None = None,
) -> dict[str, Any]:
    """Create one asset row — the clerk's and the build's path: the record,
    then (only when the payload CARRIES one) the opening read, then the audit.

    ⛔ **`DEF-AST-8102` — THE OPENING READ IS ASKED FOR ONLY WHEN THERE IS ONE,
    AND THE UPLOAD DOES NOT COME THROUGH HERE AT ALL.** `_capture_opening_read`
    is `@require_role`-guarded, and this function used to call it
    UNCONDITIONALLY; the guard runs before the helper can notice the payload
    has no reading. A background job's actor carries an id and NO role by
    design (`import_runs._JobActor`), so every asset upload over the 200-row
    async bar raised `AuthError` on row 1 and wrote nothing. The upload now
    takes `_create_asset_for_import`, which never reaches a role-guarded
    function (the job-role gate proves that for every job body).
    """
    asset, type_code, install_date, warnings = _create_asset_record(
        actor, data, installed=installed, custom_fields_screen=custom_fields_screen
    )
    if _has_opening_read(data):
        _capture_opening_read(actor, data, asset, type_code, install_date)
    return _created(actor, data, asset, warnings)


def _has_opening_read(data: dict[str, Any]) -> bool:
    raw = data.get("opening_read")
    return raw is not None and str(raw).strip() != ""


def _create_asset_for_import(actor: Any, data: dict[str, Any]) -> dict[str, Any]:
    """One uploaded row → one asset. The upload sheets carry NO opening read
    (it is not a column on any of the three), so there is nothing to capture
    and no reason to pass a role-guarded door (`DEF-AST-8102`)."""
    asset, _type_code, _install_date, warnings = _create_asset_record(actor, data)
    return _created(actor, data, asset, warnings)


def _create_asset_record(
    actor: Any,
    data: dict[str, Any],
    *,
    installed: bool = True,
    custom_fields_screen: str | None = None,
) -> tuple[Any, str, Any, list[dict[str, Any]]]:
    """Create one asset row (and its assignment) — no opening read, no audit.

    ``installed`` — **PO ruling 2026-09-21, verbatim: *"you can generate meter,
    sub meter or asset # and assigned it - but theya re not yet installed or
    actiavted"*, and *"install date on work order completion - yes"*.**

    ⚠ **IT DEFAULTS TO ``True`` SO THAT EVERY EXISTING CALLER IS BYTE-FOR-BYTE
    UNCHANGED.** `BR-AST-011`'s assign-on-create — a clerk at the unit wizard
    recording a meter that is already on the wall — really does mean INSTALLED,
    and that rule is not touched. What the ruling names is a meter a BUILD
    creates before anybody has been to site: `DEF-MET-6066` / `DEF-MET-6067`.

    ``installed=False`` changes exactly two things and nothing else:
      * ``install_date`` is not required and is not invented, so the column
        stays NULL until a work order's completion writes it;
      * the stage is ``inventory`` rather than ``active`` (*Installed*), so the
        asset is NOT ``in_service`` — which is what keeps it out of
        ``billable_asset_count``'s population. A meter nobody has fitted must
        not be billed for, and that is the money half of the same ruling.

    ⚠ **THE UNIT ASSIGNMENT IS STILL WRITTEN, AND ITS ``from_date`` IS NOT AN
    INSTALL DATE.** ``AssetAssignment.from_date`` is NOT NULL, and it answers a
    different question — *from when is this asset earmarked for this unit* —
    which is TODAY, truthfully, because the build has just earmarked it. Losing
    the assignment instead would leave the build's meters floating in inventory
    with nothing tying them to the units they were made for.

    ⚠ **AND THE STAGE VOCABULARY HAS NO VALUE FOR *ASSIGNED, NOT INSTALLED*.**
    ``inventory`` is the nearest and its LABEL reads *Inventory* on a meter
    earmarked for a flat. `BR-AST-031` exists so a stage's label is never
    load-bearing and the BEHAVIOUR here is exactly right — not in service, not
    billed — but the word a clerk reads is wrong. That is `DEF-MET-6066`'s
    second half and it is a reference-data change of its own: a sixth seeded
    stage, its migration, its transitions and its fixture.
    """

    cleaned = _validate_asset(data, partial=False, custom_fields_screen=custom_fields_screen)
    asset_type = cleaned.pop("type")
    warnings: list[dict[str, Any]] = []

    unit_id = data.get("unit_id")
    service_point_id = data.get("service_point_id")
    service_code = _text(data.get("service"), 40)
    if unit_id and service_code and not service_point_id:
        service_point_id = str(seams.ensure_service_point(unit_id, service_code))
    if service_point_id and seams.service_point_ref(service_point_id) is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if unit_id:
        seams.unit_row(unit_id)  # same-tenant or the indistinguishable 404

    unit_value = cleaned.get("unit")
    if unit_value is None and service_code:
        unit_value = seams.service_default_uom(service_code)
    if service_code and service_code not in seams.enabled_service_codes():
        _refuse_fields(
            [
                _field_error(
                    "service",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "assets.service_not_enabled",
                    service=service_code,
                )
            ]
        )
    _check_measuring_requirements(asset_type.code, service_code or service_point_id, unit_value)
    parent = _resolve_parent(data, asset_type.code)

    asset_no = cleaned.pop("asset_no", None) or suggest_asset_no(asset_type.code)
    if not asset_no:
        _refuse_fields(
            [_field_error("asset_no", errors.VAL_REQUIRED, "assets.asset_no_required_no_series")]
        )
    if _asset_by_no(asset_no) is not None:  # BR-AST-033 hard block
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-AST-033",
            message_key="assets.asset_no_duplicate",
            params={"asset_no": asset_no},
        )
    # BR-AST-049 — the legacy reference is UNIQUE per tenant, so a second row
    # claiming it is refused here with the number that already holds it. Note
    # the ASYMMETRY with `serial_no` two lines down, and that it is the whole
    # reason this column exists rather than being folded into the serial: a
    # duplicate SERIAL warns and loads (BR-AST-033), a duplicate legacy
    # reference cannot, because it is the thing that identifies the row.
    _refuse_duplicate_external_ref(cleaned.get("external_ref"))
    serial = cleaned.get("serial_no")
    if serial:
        clash = (
            models.Asset.objects.filter(tenant_id=_tenant_id(), serial_no__iexact=serial)
            .values_list("asset_no", flat=True)
            .first()
        )
        if clash:  # BR-AST-033 warn-but-allow
            warnings.append({"code": "duplicate_serial", "existing_asset_no": clash})

    install_date = cleaned.get("install_date")
    # BR-AST-011: assign-on-create → first assignment row + status active;
    # leave-in-inventory → unassigned, status inventory.
    # ⚠ AND A THIRD SHAPE SINCE 2026-09-21: assigned-but-NOT-installed, which is
    # what a BUILD creates (`installed=False` — see this function's docstring).
    stage_code = "active" if unit_id and installed else "inventory"
    if install_date is None and unit_id and installed:
        _refuse_fields(
            [_field_error("install_date", errors.VAL_REQUIRED, "assets.install_date_required")]
        )
    if cleaned.get("test_interval_months") is None:
        cleaned["test_interval_months"] = SEED_TEST_INTERVAL_MONTHS.get(asset_type.code)

    asset = models.Asset.objects.create(
        tenant_id=_tenant_id(),
        asset_no=asset_no,
        type=asset_type,
        status=stage_by_code(stage_code),
        service_point_id=service_point_id,
        parent_asset=parent,
        unit=unit_value,
        **{k: v for k, v in cleaned.items() if k not in ("unit",)},
    )
    if unit_id:
        models.AssetAssignment.objects.create(
            tenant_id=asset.tenant_id,
            asset=asset,
            unit_id=unit_id,
            # ⚠ **NOT AN INSTALL DATE, AND THE COLUMN IS NOT NULL.** `from_date`
            # answers *from when is this asset earmarked for this unit*. On an
            # installed asset that is the day it went on the wall; on one a
            # build has just created it is today, because today is when the
            # build earmarked it. `install_date` stays NULL either way unless
            # somebody has actually been to site (PO 2026-09-21).
            from_date=install_date or seams.tenant_today(),
            actor_user_id=getattr(actor, "id", None),
        )
    # ── `AST-B-14` — THE OPENING READ, AND THE FAILURE RULE IS THE CONTRACT ──
    #
    # PO ruling 2026-09-12, verbatim: *"Build it as drawn - move it to step 2,
    # beside the multiplier, register digits and the warning"*, superseding this
    # file's own earlier position that no seam existed for it.
    #
    # ⚠ **IF THE READ CANNOT BE WRITTEN, THE ASSET IS NOT CREATED.** This runs
    # inside `create_asset`'s `transaction.atomic()`, so metering's refusal —
    # a negative register, a value the BR-MET-020/022 engine rejects, a missing
    # metering module — rolls the asset row back with it. That is what the
    # wizard's consequence box tells the clerk before they commit, and it is the
    # strict half of a choice: the alternative is a meter in service whose
    # baseline nobody knows, discovered on the first bill.
    # (the call itself now lives in `_create_asset_inner`, after this returns,
    # and is made only when the payload carries a reading — `DEF-AST-8102`.)
    return asset, asset_type.code, install_date, warnings


def _created(
    actor: Any, data: dict[str, Any], asset: Any, warnings: list[dict[str, Any]]
) -> dict[str, Any]:
    """The create's audit row and its answer."""
    from apps.assets import selectors

    after = selectors.asset_dict(asset)
    _audit(actor, "asset.created", "asset", asset.id, after={**after, "warnings": warnings})
    if data.get("recreated_from_asset_id"):
        # BR-AST-030: a mistaken retirement is corrected by creating the asset
        # anew with a LINKED audit note — never an un-retire.
        _audit(
            actor,
            "asset.recreated_from_retired",
            "asset",
            asset.id,
            after={"replaces_retired_asset_id": str(data["recreated_from_asset_id"])},
        )
    return {**after, "warnings": warnings}


def create_asset_for_unit(
    *,
    actor: Any,
    unit_id: str,
    service_point_id: str | None,
    payload: dict[str, Any],
    installed: bool = True,
) -> dict[str, Any]:
    """The metering seam (BR-AST-028 premises-first creation): the unit wizard
    and the units CSV create asset rows in THIS registry, never duplicates.

    ⚠ **THE KEYWORDS ARE `service_point_id` AND `payload`, AND A CALLER GOT THEM
    WRONG FOR THREE WEEKS WITHOUT ANYTHING NOTICING (`DEF-MET-5464`).** New
    Connect's commit called this with `service_code=` and `asset_no=` — neither
    of which has ever existed here; both travel INSIDE `payload`. It returned
    **500** the first time anything executed it, which was the day the wizard's
    commit door stopped being a 404. `metering/seams.py` forwards `**kwargs`, so
    nothing failed at import and no test called it, because creating an asset
    needs a unit that already exists and that commit's own cases pass no meters.
    **A seam is a contract between two modules and only one side of this one was
    ever run.**

    `service_point_id` may be `None`: `_create_asset_inner` raises the point
    itself when it is handed a unit and a service, which is what the unit wizard
    has always relied on and what New Connect now relies on too.

    ⚠ **`installed` — PO ruling 2026-09-21, AND IT DEFAULTS TO THE OLD
    BEHAVIOUR.** Verbatim: *"you can generate meter, sub meter or asset # and
    assigned it - but theya re not yet installed or actiavted"*, and *"install
    date on work order completion - yes"*. A meter the NEW CONNECT commit
    creates has had nobody to site, so it is created with **no install date**
    and **not in service**; a meter the UNIT WIZARD creates is one a clerk is
    recording off the wall, and `BR-AST-011`'s assign-on-create is untouched.
    The units CSV is the third caller and keeps the old behaviour too, because
    an import row carries an install date of its own.
    `DEF-MET-6066` / `DEF-MET-6067`, both measured on a real row first:
    `M-00001`, `install_date 2026-09-20`, status `active` / *Installed*.
    """
    data = {k: v for k, v in payload.items() if v is not None}
    data["unit_id"] = unit_id
    if service_point_id:
        data["service_point_id"] = service_point_id
    # ⚠ **NO INSTALL DATE IS INVENTED FOR A BUILD (`DEF-MET-6067`).** The
    # default below is right for the unit wizard, where a clerk is recording a
    # meter already on the wall, and wrong for New Connect, which creates a
    # meter nobody has been to site to fit.
    if installed:
        data.setdefault("install_date", str(seams.tenant_today()))
    return _create_asset_inner(actor, data, installed=installed)


def attach_existing_asset(
    *,
    actor: Any,
    asset_no: Any,
    unit_id: str,
    service_point_id: str | None,
    install_date: Any = None,
) -> dict[str, Any]:
    """Assign-existing mode (US-MET-003 TC-2/TC-6): the asset must exist and be
    UNASSIGNED — an already-active meter is refused, naming its unit."""
    from apps.assets import selectors

    if not asset_no:
        _refuse_fields([_field_error("asset_no", errors.VAL_REQUIRED, "assets.asset_no_required")])
    asset = _asset_by_no(str(asset_no))
    if asset is None:
        _refuse_fields(
            [
                _field_error(
                    "asset_no", errors.VAL_UNKNOWN_LOOKUP, "assets.unknown", asset_no=str(asset_no)
                )
            ]
        )
    current = _current_assignment(asset)
    if current is not None:
        unit = seams.unit_ref(current.unit_id) or {}
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-AST-017",
            message_key="assets.already_assigned",
            params={"asset_no": asset.asset_no, "unit": unit.get("label"), "action": "reassign"},
        )
    effective = _as_date(install_date, "install_date") or seams.tenant_today()
    seams.unit_row(unit_id)
    models.AssetAssignment.objects.create(
        tenant_id=asset.tenant_id,
        asset=asset,
        unit_id=unit_id,
        from_date=effective,
        actor_user_id=getattr(actor, "id", None),
    )
    before = selectors.asset_dict(asset)
    if service_point_id:
        asset.service_point_id = service_point_id
    asset.status = stage_by_code("active")  # BR-AST-020 inventory →(assign)→ active
    asset.save(update_fields=["service_point", "status", "updated_at"])
    after = selectors.asset_dict(asset)
    _audit(actor, "asset.assigned", "asset", asset.id, before=before, after=after)
    return after


# ── CR-162-BRC10 · a BUILD's assets are installed when its service activates ──
def build_asset_rows(service_point_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """The assets standing on each of these service points — what a New
    Connection's Units tab and its activation read (`CR-162-BRC10` items 3, 36).

    ONE query, keyed by service point. Each row names the asset by its NUMBER
    and its type and stage by their LABELS, never by an id a screen would print
    (B14 rule 31). A point with no asset is absent from the map."""
    ids = [str(one) for one in service_point_ids if one not in (None, "")]
    if not ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    rows = (
        models.Asset.objects.filter(tenant_id=_tenant_id(), service_point_id__in=ids)
        .select_related("type", "status")
        .order_by("asset_no", "id")
    )
    for asset in rows:
        out.setdefault(str(asset.service_point_id), []).append(
            {
                "id": str(asset.id),
                "asset_no": asset.asset_no,
                "type": asset.type.code,
                "type_name": asset.type.name,
                "size_class": asset.size_class,
                "status": asset.status.code,
                "status_name": asset.status.name,
                "install_date": asset.install_date.isoformat() if asset.install_date else None,
            }
        )
    return out


def install_build_assets(
    actor: Any, *, service_point_ids: list[Any], install_date: Any
) -> list[dict[str, Any]]:
    """`CR-162-BRC10` item 6 — the assets a build earmarked become INSTALLED,
    dated, when their service is activated.

    PO 2026-09-21, verbatim: *"you can generate meter, sub meter or asset # and
    assigned it - but theya re not yet installed or actiavted"*, and *"install
    date on work order completion - yes"*; PO 2026-10-02 (the New Connection
    programme, item 6): on approval *"asset → Installed (date, asset id)"*. So
    the commit makes them `installed=False` — stage `inventory`, no
    `install_date` (`DEF-AST-5443`) — and THIS is the one door that fits them.

    **The assets module's own write** (B2 §2: metering never writes this
    table). For every asset on these service points that is still in the
    `inventory` stage: stage → `active` (*Installed*, `in_service` — and so, from
    this moment, in `billable_asset_count`'s population), `install_date` = the
    activation's date, one `asset.installed` audit row each (hard rule 7: this
    is the moment a meter starts to count on a bill).

    **Idempotent:** an asset already past `inventory` is left exactly as it is
    and not reported, so a second activation installs nothing twice and never
    moves a date a crew already recorded. Runs inside the caller's transaction;
    it opens a savepoint and issues no query after a refusal (law 14)."""
    from apps.assets import selectors

    ids = [str(one) for one in service_point_ids if one not in (None, "")]
    if not ids:
        return []
    day = _as_date(install_date, "install_date") or seams.tenant_today()
    installed_stage = stage_by_code("active")
    out: list[dict[str, Any]] = []
    with transaction.atomic():
        rows = list(
            models.Asset.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), service_point_id__in=ids, status__code__iexact="inventory")
            .order_by("asset_no", "id")
        )
        for asset in rows:
            before = selectors.asset_dict(asset)
            asset.status = installed_stage
            asset.install_date = day
            asset.save(update_fields=["status", "install_date", "updated_at"])
            after = selectors.asset_dict(asset)
            _audit(
                actor,
                "asset.installed",
                "asset",
                asset.id,
                before=before,
                after={**after, "br_ref": "CR-162-BRC10"},
            )
            out.append(
                {
                    "id": str(asset.id),
                    "asset_no": asset.asset_no,
                    "install_date": day.isoformat(),
                    "service_point_id": str(asset.service_point_id),
                }
            )
    return out


def install_fitted_asset(actor: Any, *, asset_id: Any, install_date: Any) -> dict[str, Any] | None:
    """`DEF-AST-9712` (`CR-171-BRC10` P1.27, lane MVI-WIZ-UNIT) — the meter a
    MOVE-IN field visit was raised FOR becomes INSTALLED when Work accepts that
    visit (`BR-AST-020`: inventory → active; `BR-MET-110`: the acceptance is the
    human act that confirms an installation).

    The new connection's door (`install_build_assets`) fits every earmarked
    asset on a build's service points; a move-in has no build, so its visit
    names ONE asset — the order's own — and only that one moves. The same
    posture otherwise: the assets module's own write, dated by the caller (the
    order's completion), one `asset.installed` audit row, and **idempotent** —
    an asset already past `inventory` is left exactly as it is and `None` is
    answered, so accepting twice installs nothing twice and never moves a date
    a crew recorded. Runs inside the caller's transaction, in a savepoint."""
    from apps.assets import selectors

    if not asset_id:
        return None
    day = _as_date(install_date, "install_date") or seams.tenant_today()
    with transaction.atomic():
        asset = (
            models.Asset.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), pk=asset_id, status__code__iexact="inventory")
            .first()
        )
        if asset is None:
            return None
        before = selectors.asset_dict(asset)
        asset.status = stage_by_code("active")
        asset.install_date = day
        asset.save(update_fields=["status", "install_date", "updated_at"])
        _audit(
            actor,
            "asset.installed",
            "asset",
            asset.id,
            before=before,
            after={**selectors.asset_dict(asset), "br_ref": "DEF-AST-9712"},
        )
    return {"id": str(asset.id), "asset_no": asset.asset_no, "install_date": day.isoformat()}


# ── edit + delete (US-AST-003 · BR-AST-012/013/032) ─────────────────────────
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-032")
def update_asset(
    actor: Any,
    asset_id: Any,
    changes: Any,
    *,
    custom_fields_screen: str | None = None,
) -> dict[str, Any]:
    """BR-AST-012: every edit audited before/after; billing-affecting fields
    (multiplier, unit, net_metering, service) apply FORWARD ONLY once reads
    exist — stored reads and issued invoices are never restated.

    BR-AST-044 disposition, DOCUMENTED rather than silently chosen:
    `meter_type` is NOT billing-affecting. It classifies the device (AMI · AMR
    · walk-by · sub-meter · master); no rate, quantity or invoice line is
    derived from it, so re-tagging a meter restates nothing and the
    forward-only clause has nothing to protect. It is edited like a spec field
    — validated against the tenant's catalog, audited before/after — and its
    change never raises the forward_only_change warning. If finance later reads
    meter class as a pricing input, BILLING_AFFECTING_FIELDS above is the one
    place to add it."""
    from apps.assets import selectors

    data = _payload_dict(changes)
    with transaction.atomic():
        asset = _asset_row(asset_id, locked=True)
        if asset.status.behavior_class == STAGE_TERMINAL:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-AST-020",
                message_key="assets.retired_is_terminal",
                params={"asset_no": asset.asset_no},
            )
        cleaned = _validate_asset(
            data, partial=True, current=asset, custom_fields_screen=custom_fields_screen
        )
        warnings: list[dict[str, Any]] = []
        before = selectors.asset_dict(asset)
        if "asset_no" in cleaned and cleaned["asset_no"]:
            other = _asset_by_no(cleaned["asset_no"])
            if other is not None and other.pk != asset.pk:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-AST-033",
                    message_key="assets.asset_no_duplicate",
                    params={"asset_no": cleaned["asset_no"]},
                )
        if "external_ref" in cleaned:
            # BR-AST-049 — same hard block on the edit path, excluding this row
            # so that re-saving an asset with its own reference is not a clash.
            _refuse_duplicate_external_ref(cleaned["external_ref"], exclude_pk=asset.pk)
        touched_billing = BILLING_AFFECTING_FIELDS & set(cleaned)
        reads = seams.read_count_for_asset(asset.id)
        if touched_billing and reads:
            warnings.append(
                {
                    "code": "forward_only_change",
                    "br_ref": "BR-AST-012",
                    "fields": sorted(touched_billing),
                    "reads": reads,
                }
            )
        fields: list[str] = []
        for field, value in cleaned.items():
            if field == "type":
                if value.pk != asset.type_id:
                    asset.type = value
                    fields.append("type")
                continue
            if getattr(asset, field) != value:
                setattr(asset, field, value)
                fields.append(field)
        if fields:
            asset.save(update_fields=[*fields, "updated_at"])
            _audit(
                actor,
                "asset.updated",
                "asset",
                asset.id,
                before=before,
                after={**selectors.asset_dict(asset), "warnings": warnings},
            )
    return {**selectors.asset_dict(_asset_row(asset_id)), "warnings": warnings}


def asset_reference_probe(asset: models.Asset) -> dict[str, int]:
    """BR-AST-013 gate inputs: reads · assignment history · maintenance ·
    invoice lines · replaced_by pointers."""
    return {
        "reads": seams.read_count_for_asset(asset.id),
        "assignments": models.AssetAssignment.objects.filter(
            tenant_id=asset.tenant_id, asset=asset
        ).count(),
        "maintenance": models.AssetMaintenance.objects.filter(
            tenant_id=asset.tenant_id, asset=asset
        ).count(),
        "invoice_lines": seams.invoice_line_count_for_asset(asset.id),
        "replaced_by": models.Asset.objects.filter(
            tenant_id=asset.tenant_id, replaced_by_asset=asset
        ).count(),
    }


@require_role(SYSTEM_ADMIN, br_ref="BR-AST-032")
def delete_asset(actor: Any, asset_id: Any) -> None:
    """BR-AST-013: hard delete only when status = inventory AND the asset was
    NEVER referenced. Anything else is blocked with a pointer to Retire —
    server-side, whatever the UI hid (US-AST-003 TC-4)."""
    from apps.assets import selectors

    with transaction.atomic():
        asset = _asset_row(asset_id, locked=True)
        if asset.status.behavior_class != STAGE_AVAILABLE:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-AST-013",
                message_key="assets.delete_requires_inventory",
                params={"status": asset.status.code, "alternative": "retire"},
            )
        referenced = {k: v for k, v in asset_reference_probe(asset).items() if v}
        if referenced:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-AST-013",
                message_key="assets.delete_blocked_referenced",
                params={"referenced_by": referenced, "alternative": "retire"},
            )
        before = selectors.asset_dict(asset)
        asset.delete()
        _audit(actor, "asset.deleted", "asset", asset_id, before=before)


# ── maintenance + lifecycle (US-AST-007 · BR-AST-018/020/038) ───────────────
def _transition_allowed(
    current: models.AssetLifecycleStage, target: models.AssetLifecycleStage
) -> bool:
    if current.pk == target.pk:
        return True  # "no change" is always a legal Set-status choice
    if current.behavior_class == STAGE_TERMINAL:
        return False  # BR-AST-020/030: retired is terminal, forever
    if current.code in MAINTENANCE_TRANSITIONS and target.code in MAINTENANCE_TRANSITIONS:
        return target.code in MAINTENANCE_TRANSITIONS[current.code]
    # Tenant-added stage: legality falls back to the behavior class so the
    # rules stay sound whatever the tenant named it (BR-AST-031).
    if target.behavior_class == STAGE_TERMINAL:
        return False  # only the retire service reaches a terminal stage
    return {current.behavior_class, target.behavior_class} <= {
        STAGE_IN_SERVICE,
        STAGE_OUT_OF_SERVICE,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-038")
def log_maintenance(actor: Any, asset_id: Any, payload: Any) -> dict[str, Any]:
    """S53. Append-only entry (BR-AST-018) + the resulting status transition
    (BR-AST-020, legal from the CURRENT stage only). A `test` entry updates
    assets.last_test_date, which clears the derived "Test due" chip
    (BR-AST-007). The Billing Clerk may perform repair transitions
    (BR-AST-038)."""
    from apps.assets import selectors

    data = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    kind = _text(data.get("kind"), 20)
    if kind not in MAINTENANCE_KINDS:
        fe.append(
            _field_error(
                "kind",
                errors.VAL_REQUIRED,
                "assets.maintenance_kind",
                allowed=list(MAINTENANCE_KINDS),
            )
        )
    detail = _text(data.get("detail"), 1000)
    if not detail:
        fe.append(_field_error("detail", errors.VAL_REQUIRED, "assets.maintenance_detail_required"))
    # CR-028 AST-W2 T7 (§10-D3): cost is CAPTURED — stored 4 dp (rule 2),
    # totalled on the tab, and posted NOWHERE. Optional; never negative.
    cost = _decimal(data.get("cost"), "cost", fe, positive=False)
    _refuse_fields(fe)
    entry_date = _as_date(data.get("date"), "date") or seams.tenant_today()
    if entry_date > seams.tenant_today():
        _refuse_fields([_field_error("date", errors.VAL_RANGE, "assets.maintenance_date_future")])

    with transaction.atomic():
        asset = _asset_row(asset_id, locked=True)
        if asset.status.behavior_class == STAGE_TERMINAL:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-AST-030",
                message_key="assets.retired_is_terminal",
                params={"asset_no": asset.asset_no},
            )
        target = asset.status
        if data.get("status"):
            target = stage_by_code(str(data["status"]))
            if not _transition_allowed(asset.status, target):
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-AST-020",
                    message_key="assets.illegal_transition",
                    params={"from": asset.status.code, "to": target.code},
                )
        entry = models.AssetMaintenance.objects.create(
            tenant_id=asset.tenant_id,
            asset=asset,
            kind=kind,
            date=entry_date,
            detail=detail,
            tech_user_id=data.get("tech_user_id"),
            resulting_status=target,
            closed_at=None,
            cost=cost,
        )
        before = selectors.asset_dict(asset)
        changed: list[str] = []
        if kind == "test":  # BR-AST-018 → feeds BR-AST-007
            asset.last_test_date = entry_date
            changed.append("last_test_date")
            # CR-028 AST-W4 T5: an EXPLICIT certification_due (the AST-W2
            # CERT_DUE column) would otherwise go stale — next_test prefers it
            # over the fresh last_test + interval derivation. A test entry on
            # an interval-carrying asset therefore ROLLS it to the cadence's
            # next due. No interval → nothing derivable → the explicit date is
            # DATA and stays untouched (stated, not silently guessed).
            if asset.certification_due and asset.test_interval_months:
                asset.certification_due = selectors.add_months(
                    entry_date, int(asset.test_interval_months)
                )
                changed.append("certification_due")
        if target.pk != asset.status_id:
            asset.status = target
            changed.append("status")
        if changed:
            asset.save(update_fields=[*changed, "updated_at"])
        _audit(
            actor,
            "asset.maintenance_logged",
            "asset",
            asset.id,
            after={
                "kind": kind,
                "date": entry_date.isoformat(),
                "detail": detail,
                "resulting_status": target.code,
                # Rule 7: a money capture reaches the trail with its figure.
                "cost": str(cost) if cost is not None else None,
            },
        )
        if "status" in changed:
            _audit(
                actor,
                "asset.status_changed",
                "asset",
                asset.id,
                before={"status": before["status"]},
                after={"status": target.code},
            )
    return {
        "id": str(entry.id),
        "asset": selectors.asset_dict(_asset_row(asset_id)),
        "kind": kind,
        "date": entry_date.isoformat(),
        "resulting_status": target.code,
    }


@require_role(SYSTEM_ADMIN, br_ref="BR-AST-032")
def retire_asset(actor: Any, asset_id: Any, payload: Any) -> dict[str, Any]:
    """S54 / AST-08 (CR-028 AST-W4). Terminal (BR-AST-020/030) — reason +
    retire date required, optional replaced_by must be a same-tenant
    NON-retired asset; an assigned asset's current assignment closes at the
    retire date (BR-AST-021). System Admin only (BR-AST-032). Reads, invoices
    and history rows are untouched.

    CR-028 AST-W4 extensions, each ruled:

    * **Book value (D4 / BR-AST-047):** when a purchase cost AND an expected
      life are on record, the straight-line book value AS OF the retire date
      is COMPUTED (`selectors.asset_book_value`) and RECORDED into
      `book_value_amount` + the operator's `book_value_treatment`
      (write_off · warranty_claim · hold — required exactly when a book value
      exists, refused when there is none to treat). NOTHING POSTS ANYWHERE —
      no journal line, no GL account (hard rule 5); the recorded pair is the
      future finance link's source if one is ever ruled.
    * **Final read (AST-08 step 1, BR-AST-022's posture):** an optional
      `final_read_value` (+ `final_read_date`, default the retire date) for a
      measuring asset routes through the SAME metering capture seam reassign
      uses — and while that seam is unwired the WHOLE retire refuses
      (BIZ-COMPLETENESS) rather than pretending a read was taken.
    * **Replacement opening read (DEF-AST-10182, PO 2026-10-17):** an optional
      `replacement_opening_read` (+ `replacement_opening_read_date`, default the
      retire date, never in the future) is recorded on the NEW meter through
      metering's `capture_opening_read` in the same transaction — see
      `_capture_replacement_opening_read`.
    * **Linked-device edge (B16 §5.1b (B)):** retiring a BTM device that
      carries a measuring link CLEARS the link and writes a
      `asset.pairing_review_flagged` audit row on the METER, so its inline
      Audit tab (the DEF-579 pattern) surfaces the pairing for review.

    r10's "48 kWh · roughly $12.24" estimated-usage line is OMITTED — rating
    math outside rating, folded into D2's omissions (B16 §7)."""
    from apps.assets import selectors

    data = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    reason = _text(data.get("reason"), 40)
    if reason not in RETIRE_REASONS:
        fe.append(
            _field_error(
                "reason", errors.VAL_REQUIRED, "assets.retire_reason", allowed=list(RETIRE_REASONS)
            )
        )
    _refuse_fields(fe)
    retire_date = _as_date(data.get("retire_date"), "retire_date") or seams.tenant_today()

    with transaction.atomic():
        asset = _asset_row(asset_id, locked=True)
        if asset.status.behavior_class == STAGE_TERMINAL:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-AST-030",
                message_key="assets.retired_is_terminal",
                params={"asset_no": asset.asset_no},
            )
        if asset.install_date and retire_date < asset.install_date:
            _refuse_fields(
                [_field_error("retire_date", errors.VAL_RANGE, "assets.retire_before_install")]
            )
        replacement = None
        if data.get("replaced_by"):
            replacement = _asset_by_no(str(data["replaced_by"]))
            if replacement is None and _looks_like_uuid(data["replaced_by"]):
                replacement = (
                    models.Asset.objects.filter(tenant_id=asset.tenant_id, pk=data["replaced_by"])
                    .select_related("status")
                    .first()
                )
            if replacement is None:
                _refuse_fields(
                    [
                        _field_error(
                            "replaced_by", errors.VAL_UNKNOWN_LOOKUP, "assets.replacement_unknown"
                        )
                    ]
                )
            if replacement.status.behavior_class == STAGE_TERMINAL:
                _refuse_fields(
                    [
                        _field_error(
                            "replaced_by", errors.VAL_FORMAT, "assets.replacement_is_retired"
                        )
                    ]
                )
        before = selectors.asset_dict(asset)
        current = _current_assignment(asset)

        # ── AST-08 step 1: the optional final read (BR-AST-022's posture) ───
        final_read = None
        if data.get("final_read_value") not in (None, "") and _is_measuring(asset):
            if current is None:
                _refuse_fields(
                    [
                        _field_error(
                            "final_read_value",
                            errors.VAL_FORMAT,
                            "assets.final_read_needs_assignment",
                        )
                    ]
                )
            read_at = _as_date(data.get("final_read_date"), "final_read_date") or retire_date
            final_read = seams.capture_final_read(
                asset_id=str(asset.id),
                unit_id=str(current.unit_id),
                read_at=read_at.isoformat(),
                value=data.get("final_read_value"),
                unit=asset.unit,
                actor=actor,  # D5: metering audits the capture with its actor
            )
            if final_read is None:
                # The capture and the retire are ONE transaction — refuse the
                # whole thing rather than retire an asset whose final read was
                # requested and never taken (the reassign service's own law).
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-AST-022",
                    message_key="assets.final_read_capture_unavailable",
                    params={"asset_no": asset.asset_no, "owner": "metering reads lane (W2)"},
                )
            _audit(
                actor,
                "asset.final_read_captured",
                "asset",
                asset.id,
                after={"read": final_read, "effective_date": retire_date.isoformat()},
            )

        # ── AST-08 step 2: the REPLACEMENT's opening reading (DEF-AST-10182) ─
        _capture_replacement_opening_read(actor, data, replacement, retire_date)

        # ── AST-08 step 3: book value COMPUTED + treatment RECORDED (D4) ────
        book = selectors.asset_book_value(asset, as_of=retire_date)
        treatment = _text(data.get("book_value_treatment"), 40)
        if book is not None:
            if treatment not in BOOK_VALUE_TREATMENTS:
                # A book value exists, so the step-3 radio is not skippable —
                # and an invented value would be worse than a refusal.
                _refuse_fields(
                    [
                        _field_error(
                            "book_value_treatment",
                            errors.VAL_REQUIRED,
                            "assets.book_value_treatment_required",
                            allowed=list(BOOK_VALUE_TREATMENTS),
                        )
                    ]
                )
        elif treatment:
            # No cost or no life on record → no book value → nothing to treat.
            _refuse_fields(
                [
                    _field_error(
                        "book_value_treatment",
                        errors.VAL_FORMAT,
                        "assets.book_value_treatment_without_value",
                    )
                ]
            )

        if current is not None:  # BR-AST-021: close the current assignment
            current.to_date = retire_date
            if final_read is not None:
                current.final_read_id = final_read.get("id")
            current.save(update_fields=["to_date", "final_read_id", "updated_at"])

        # ── B16 §5.1b (B): a retired device's measuring link does not survive
        cleared_link = None
        if asset.type.category == TAB_BTM and asset.parent_asset_id:
            cleared_link = asset.parent_asset
            asset.parent_asset = None

        asset.status = stage_by_code("retired")
        asset.retire_date = retire_date
        asset.retire_reason = reason
        asset.replaced_by_asset = replacement
        if book is not None:
            asset.book_value_amount = Decimal(book["book_value"])
            asset.book_value_treatment = treatment
        asset.save(
            update_fields=[
                "status",
                "retire_date",
                "retire_reason",
                "replaced_by_asset",
                "parent_asset",
                "book_value_amount",
                "book_value_treatment",
                "updated_at",
            ]
        )
        _audit(
            actor,
            "asset.retired",
            "asset",
            asset.id,
            before=before,
            after={
                "status": "retired",
                "retire_date": retire_date.isoformat(),
                "retire_reason": reason,
                "replaced_by": replacement.asset_no if replacement else None,
                # Rule 7: the recorded money reaches the trail with its figure
                # — and it is a RECORD, not a posting (hard rule 5 / D4).
                "book_value_amount": book["book_value"] if book else None,
                "book_value_treatment": treatment if book else None,
                "linked_meter_cleared": cleared_link.asset_no if cleared_link else None,
            },
        )
        if cleared_link is not None:
            # The METER's own trail carries the review flag, so its inline
            # Audit tab (DEF-579 pattern) is where a clerk sees the orphaned
            # pairing — the lawful "flag for review" (no Work module, D7).
            _audit(
                actor,
                "asset.pairing_review_flagged",
                "asset",
                cleared_link.id,
                after={
                    "retired_device": asset.asset_no,
                    "note": "linked device retired; review this meter's pairing",
                },
            )
    return selectors.asset_dict(_asset_row(asset_id))


def _capture_replacement_opening_read(
    actor: Any, data: dict[str, Any], replacement: models.Asset | None, retire_date: date
) -> dict[str, Any] | None:
    """`DEF-AST-10182` — the NEW meter's opening reading, taken by the retire.

    PO ruling 2026-10-17 (decision log *"WHERE A USER ENTERS A METER
    READING"*), gap 2: *"Assets → Retire with a replacement meter — opening
    reading + read date for the NEW meter, and Fetch"*. Until then the retire
    wizard recorded this as an omission (*"no lawful sink"*); the sink has
    existed since `AST-B-14` — `metering.capture_opening_read`, the same
    function Add asset calls — so the retire now uses it.

    * **Optional.** A blank `replacement_opening_read` records nothing, exactly
      as a blank opening read on Add asset does.
    * **Only with a replacement** — a reading for a meter that was not named is
      refused by name rather than dropped.
    * **Only on a measuring replacement** — a device has no register.
    * **The date defaults to the RETIRE date** (the exchange happens that day),
      is refused when unreadable (`_as_date`) and when it is in the FUTURE in
      the tenant's own today: a reading cannot have been taken on a day that has
      not happened. (The retire date itself may still be forward-dated; a
      forward-dated retire with an opening read must therefore name a date.)
    * **No estimate**, by ruling: the field takes a typed or fetched figure.
    * **Inside the retire's transaction.** `capture_opening_read` returning None
      (no metering module) refuses the WHOLE retire — the final read's own law —
      and an ERROR outcome from metering's validation takes it down too.
    """
    raw = data.get("replacement_opening_read")
    if raw is None or str(raw).strip() == "":
        return None
    if replacement is None:
        _refuse_fields(
            [
                _field_error(
                    "replacement_opening_read",
                    errors.VAL_REQUIRED,
                    "assets.replacement_opening_read_needs_replacement",
                )
            ]
        )
    if not _is_measuring(replacement):
        _refuse_fields(
            [
                _field_error(
                    "replacement_opening_read",
                    errors.VAL_FORMAT,
                    "assets.opening_read_not_measuring",
                )
            ]
        )
    read_on = (
        _as_date(data.get("replacement_opening_read_date"), "replacement_opening_read_date")
        or retire_date
    )
    today = seams.tenant_today()
    if today is not None and read_on > today:
        _refuse_fields(
            [
                _field_error(
                    "replacement_opening_read_date",
                    errors.VAL_RANGE,
                    "assets.replacement_opening_read_future",
                )
            ]
        )
    captured = seams.capture_opening_read(
        asset_id=replacement.id,
        value=str(raw).strip(),
        read_at=read_on.isoformat(),
        actor=actor,
    )
    if captured is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-AST-022",
            message_key="assets.opening_read_unavailable",
            params={"asset_no": replacement.asset_no},
        )
    _audit(
        actor,
        "asset.replacement_opening_read_captured",
        "asset",
        replacement.id,
        after={"read": captured, "read_on": read_on.isoformat()},
    )
    return captured


# ── reassign (US-AST-009 · BR-AST-017/022/036/037/038) ──────────────────────
def _current_assignment(asset: models.Asset) -> models.AssetAssignment | None:
    return models.AssetAssignment.objects.filter(
        tenant_id=asset.tenant_id, asset=asset, to_date__isnull=True
    ).first()


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-032")
def reassign_asset(actor: Any, asset_id: Any, payload: Any) -> dict[str, Any]:
    """S55. Closes the current assignment at the effective date and opens the
    new one the SAME date (BR-AST-017 — append-only, non-overlapping). To a
    unit keeps/sets active; to Inventory returns status inventory (BR-AST-022).
    Moving a parent prompts for its children; an independent sub-meter move is
    ALLOWED with a warning (BR-AST-037)."""
    from apps.assets import selectors

    data = _payload_dict(payload)
    with transaction.atomic():
        asset = _asset_row(asset_id, locked=True)
        if asset.status.behavior_class == STAGE_TERMINAL:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-AST-030",
                message_key="assets.retired_is_terminal",
                params={"asset_no": asset.asset_no},
            )
        result = _reassign_inner(actor, asset, data)
        children = list(
            models.Asset.objects.filter(
                tenant_id=asset.tenant_id, parent_asset=asset
            ).select_related("type", "status")
        )
        # BR-AST-037: moving a parent prompts "move children too?" (default yes).
        move_children = bool(data.get("move_children", True)) and bool(children)
        moved: list[dict[str, Any]] = []
        if move_children:
            for child in children:
                # D5 (CR-028 debt sweep): the final-read fields are the PARENT
                # register's — copied onto a child they would commit the
                # parent's value as the child's reading. A child moved with its
                # parent takes no final read here; its register travels through
                # S28 like any collection (stated, never silently guessed).
                moved.append(
                    _reassign_inner(
                        actor,
                        child,
                        {
                            **data,
                            "move_children": False,
                            "record_final_read": False,
                            "final_read_value": None,
                            "final_read_date": None,
                            "_child_of_parent_move": True,
                        },
                    )
                )
        elif children:
            result.setdefault("warnings", []).append(
                {
                    "code": "children_not_moved",
                    "br_ref": "BR-AST-037",
                    "children": [c.asset_no for c in children],
                }
            )
    return {**selectors.asset_dict(_asset_row(asset_id)), **result, "children_moved": moved}


def _guard_declared_size(asset: models.Asset, service_code: Any, resolved_size: str) -> None:
    """**A METER MAY NOT BE INSTALLED ON A SIZE-BANDED SERVICE WITH NO SIZE**
    — `DEF-AST-7660`, the Product Owner's own report: *the clerk cannot set the
    connection size, so the size column in the unit's table is blank*.

    `BR-RAT-108` picks the base charge with `size_class`, so on a BANDED
    service a blank size is not a cosmetic gap: `resolution.
    _assert_service_is_ruled_sizeless` refuses the bill by name — *"an empty
    size here is a fact nobody has recorded (DEF-514) … and a size chosen for
    it would choose a tier ladder, which is money, on the strength of
    nothing"*. Refusing at install turns a silent bill-run failure months later
    into one sentence in front of the person who can answer it.

    ⚠ **IT BINDS ONLY WHEN THE PAYLOAD DECLARES A SERVICE, AND THAT NARROWNESS
    IS `DEF-AST-5863`'s PRECEDENT RATHER THAN TIMIDITY.** `BR-AST-009`'s own
    note eighty lines down says why: a refusal that fired on every path would
    also fire on `AssetFlowPages`' full-page reassign (S55) and on
    `bulk_assign`, *"neither of which draws a service control — so a clerk who
    can assign a meter from the registry today could not assign one at all"*.
    Widening it is a change with its own blast radius and belongs to the PO.
    **The rule is therefore exactly this:** if you are declaring which service
    this device will be billed on, and that service's price is picked by the
    size, then the size must be known.

    ⚠ **AND ONLY FOR A MEASURING TYPE.** `BR-AST-530` offers the connection
    size for METERS, and `offersConnectionSize` on the screen side draws the
    same boundary. A trash cart is genuinely priced by its size and by the
    count (`CR-063`'s fire arithmetic is the same shape), and there is a real
    question there — but no surface asks a cart for a size on this path, so
    requiring one would refuse a row a clerk cannot fix. That is
    `DEF-AST-7661`'s territory and is filed rather than decided here.

    ⚠ **A SERVICE WHOSE BANDS WERE NEVER RULED DOES NOT REFUSE** — the seam
    answers `None` and `is not True` is false, so this returns. The prime
    directive forbids resolving an open question by choosing a value, and
    refusing would be choosing *"treat it as banded"* — putting the cost of
    OUR unanswered question on a clerk who cannot answer it either. **No
    SERVICE code answers `None` today** (measured 2026-09-28; the unruled
    thing is the DIMENSION `thermal_heat_steam`), so this branch is a guard
    against the twelfth service rather than a case running now — which is
    stated here because *"thermal steam and battery"* is the sentence the
    neighbouring docstrings invite, and it is two rulings out of date.
    """
    code = _text(service_code, 40)
    if not code or resolved_size:
        return
    if asset.type.code not in MEASURING_TYPES:
        return
    if seams.service_prices_by_size_class(code) is not True:
        return
    _refuse_fields(
        [
            _field_error(
                "size_class",
                errors.VAL_REQUIRED,
                "assets.size_class_required_for_banded_service",
                service=code,
                asset_no=asset.asset_no,
            )
        ]
    )


def _reassign_inner(actor: Any, asset: models.Asset, data: dict[str, Any]) -> dict[str, Any]:
    from apps.assets import selectors

    warnings: list[dict[str, Any]] = []
    effective = _as_date(data.get("effective_date"), "effective_date") or seams.tenant_today()
    to_unit_id = data.get("unit_id") or data.get("to_unit_id")
    to_inventory = bool(data.get("to_inventory")) or not to_unit_id

    current = _current_assignment(asset)
    if current is not None and effective < current.from_date:
        # BR-AST-017: an earlier effective date would create an overlap.
        _refuse_fields(
            [_field_error("effective_date", errors.VAL_RANGE, "assets.effective_before_from_date")]
        )
    if not to_inventory and asset.status.behavior_class not in (STAGE_AVAILABLE, STAGE_IN_SERVICE):
        # BR-AST-022: assigning TO a unit requires status active or inventory.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-AST-022",
            message_key="assets.assign_requires_active_or_inventory",
            params={"status": asset.status.code},
        )
    # ── THE CONNECTION SIZE THE ASSIGN DECLARES (`BR-AST-500` / `BR-AST-501`,
    #    `DEF-AST-7660`) — RESOLVED AND REFUSED HERE, BEFORE ANY WRITE.
    #
    # The refusal sits with the two guards above and not down in the to-unit
    # branch on purpose: everything below closes the current assignment row and
    # opens a new one, and a refusal that fires after those writes leaves a
    # half-moved asset a human must clean up. That is the same reasoning
    # `rating.services` states at `_guard_base_charge_code`.
    size_declared = _text(data.get("size_class"), 60)
    resolved_size = size_declared or (asset.size_class or "").strip()
    if not to_inventory:
        _guard_declared_size(asset, data.get("service"), resolved_size)
    # BR-AST-037: an independent sub-meter move is allowed WITH a warning.
    if asset.parent_asset_id and not data.get("_child_of_parent_move"):
        warnings.append(
            {
                "code": "independent_sub_meter_move",
                "br_ref": "BR-AST-037",
                "parent": asset.parent_asset.asset_no,
            }
        )

    final_read = None
    if data.get("record_final_read", True) and current is not None and _is_measuring(asset):
        # D5 (CR-028 debt sweep): the capture seam is WIRED — metering writes
        # the committed manual read in THIS transaction. A requested capture
        # with no reading refuses: the operator asked to record a read and
        # there is nothing to record — silence here would claim one was taken.
        if data.get("final_read_value") in (None, ""):
            _refuse_fields(
                [
                    _field_error(
                        "final_read_value",
                        errors.VAL_REQUIRED,
                        "assets.final_read_value_required",
                    )
                ]
            )
        # CR-028 AST-W4 T2: the AST-06 form captures the read's own DATE beside
        # its value (the B16-noted design gap — r10 draws only a checkbox);
        # absent, the read is taken at the effective date, exactly as before.
        read_at = _as_date(data.get("final_read_date"), "final_read_date") or effective
        final_read = seams.capture_final_read(
            asset_id=str(asset.id),
            unit_id=str(current.unit_id),
            read_at=read_at.isoformat(),
            value=data.get("final_read_value"),
            unit=asset.unit,
            actor=actor,  # D5: metering audits the capture with its actor
        )
        if final_read is None:
            # The capture and the move are ONE transaction (US-AST-009 TC-6).
            # Reachable only on a deployment with no metering module — refuse
            # rather than move an asset whose final read was never taken.
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-AST-022",
                message_key="assets.final_read_capture_unavailable",
                params={"asset_no": asset.asset_no, "owner": "metering reads lane (W2)"},
            )
        _audit(
            actor,
            "asset.final_read_captured",
            "asset",
            asset.id,
            after={"read": final_read, "effective_date": effective.isoformat()},
        )
    before = selectors.asset_dict(asset)
    if current is not None:
        current.to_date = effective
        if final_read is not None:
            current.final_read_id = final_read.get("id")
        current.save(update_fields=["to_date", "final_read_id", "updated_at"])
    if to_inventory:
        asset.status = stage_by_code("inventory")
        asset.service_point = None
    else:
        seams.unit_row(to_unit_id)
        models.AssetAssignment.objects.create(
            tenant_id=asset.tenant_id,
            asset=asset,
            unit_id=to_unit_id,
            from_date=effective,
            actor_user_id=getattr(actor, "id", None),
        )
        asset.status = stage_by_code("active")
        # ── THE SERVICE THE ASSIGN DECLARES (`BR-AST-009`, PO ruling 2026-09-19)
        #
        # PO, having been shown a meter assigned from stock reading a dash under
        # Service, Size and On since: *"this is correct fix it"* — against
        # *"The Assign step asks which service, offering only the services that
        # unit can take"*, required for meters and sub-meters, **optional for
        # everything else**, and **no default, because nothing may guess which
        # service a meter serves**.
        #
        # ⚠ **THIS BRANCH IS UNCHANGED, AND THAT IS THE FINDING.** It has
        # accepted `service` since the module shipped; `POST /assets/{id}/
        # reassign` passes the payload through unfiltered, and `ensure_service_
        # point` get-or-creates the unit's point for it. What was missing was a
        # screen that ASKS: the unit's Assets tab posted `{unit_id,
        # record_final_read: false}` and nothing else, so the service point was
        # never created and the meter landed on the unit unbillable. A capability
        # nothing calls is hard-won law 2, and it cost the same as an absent one.
        #
        # ⚠ **THE REQUIREMENT IS ON THE FORM AND NOT HERE, DELIBERATELY.** A
        # refusal at this line would fire on `AssetFlowPages`' full-page reassign
        # (S55) and on `bulk_assign` too, neither of which draws a service
        # control — so a clerk who can assign a meter from the registry today
        # could not assign one at all. That is a wider change than the ruling
        # makes and it is filed (`DEF-AST-5863`) rather than taken quietly.
        # `ensure_service_point` still enforces the two bounds that ARE the
        # server's: the utility must SELL the service (`BR-MET-003`) and the
        # premises must OFFER it (`BR-MET-119`).
        service_code = data.get("service")
        if service_code:
            asset.service_point_id = seams.ensure_service_point(to_unit_id, service_code)
    changed = ["status", "service_point", "updated_at"]
    # ── THE SIZE LANDS WITH THE ASSIGNMENT (`DEF-AST-7660`) ──────────────────
    #
    # ⚠ **ONLY ON A MOVE TO A UNIT, AND NEVER ON A MOVE TO INVENTORY.** Sending
    # a device back to the shelf records nothing about the connection it has
    # just left, and a `size_class` arriving on that payload is a caller
    # mistake rather than an instruction — writing it would let a return quietly
    # restate a billing-affecting fact.
    #
    # ⚠ **IT IS AUDITED WITHOUT ONE EXTRA LINE, WHICH IS WHY THE WRITE IS HERE
    # AND NOT IN A HELPER.** `before` was taken from `selectors.asset_dict(asset)`
    # above and the `after` below is taken from the same function, and
    # `size_class` is in both — so the `asset.reassigned` row already carries
    # the old value and the new one (CLAUDE.md hard rule 7).
    #
    # ⚠ **NO `BILLING_AFFECTING_FIELDS` FORWARD-ONLY WARNING IS RAISED HERE,
    # DELIBERATELY.** That warning (`BR-AST-012`) exists to tell an operator
    # that reads ALREADY PRICED at the old value; on an install there are no
    # such reads on this unit yet, and `update_asset` still raises it for an
    # edit made afterwards on the asset's own screen. Stated rather than
    # assumed, because a reader finding the set on line 272 will look for it.
    if not to_inventory and size_declared and size_declared != (asset.size_class or "").strip():
        asset.size_class = size_declared
        changed.insert(0, "size_class")
    asset.save(update_fields=changed)
    _audit(
        actor,
        "asset.reassigned",
        "asset",
        asset.id,
        before=before,
        after={
            **selectors.asset_dict(asset),
            "effective_date": effective.isoformat(),
            "warnings": warnings,
        },
    )
    return {"asset_no": asset.asset_no, "warnings": warnings, "final_read": final_read}


def _is_measuring(asset: models.Asset) -> bool:
    return asset.type.code in MEASURING_TYPES


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-032")
def bulk_assign(actor: Any, payload: Any) -> dict[str, Any]:
    """BR-AST-036: multi-select bulk assign is INVENTORY→UNIT only. A unit→unit
    move in the batch is refused — those go single or by file import
    (BR-AST-038); no bulk unit→unit path exists anywhere."""
    data = _payload_dict(payload)
    items = data.get("assignments")
    if not isinstance(items, (list, tuple)) or not items:
        _refuse_fields(
            [_field_error("assignments", errors.VAL_REQUIRED, "assets.bulk_assign_required")]
        )
    assigned: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    with transaction.atomic():
        for item in items:
            entry = dict(item or {})
            try:
                asset = _asset_row(entry.get("asset_id") or entry.get("asset_no"), locked=True)
            except (errors.NotFoundError, errors.ApiError):
                by_no = _asset_by_no(str(entry.get("asset_no") or ""))
                if by_no is None:
                    failed.append({"asset": entry.get("asset_no"), "reason": "unknown_asset"})
                    continue
                asset = by_no
            if asset.status.behavior_class != STAGE_AVAILABLE:
                failed.append(
                    {
                        "asset": asset.asset_no,
                        "reason": "not_inventory",
                        "br_ref": "BR-AST-036",
                        "alternative": "single_reassign_or_file_import",
                    }
                )
                continue
            try:
                assigned.append(
                    _reassign_inner(
                        actor,
                        asset,
                        {
                            "unit_id": entry.get("unit_id"),
                            "effective_date": entry.get("effective_date")
                            or data.get("effective_date"),
                            "service": entry.get("service"),
                            "record_final_read": False,  # inventory rows have no read to take
                        },
                    )
                )
            except (errors.ApiError, errors.NotFoundError) as exc:
                failed.append(
                    {"asset": asset.asset_no, "reason": getattr(exc, "message_key", "refused")}
                )
        _audit(
            actor,
            "asset.bulk_assigned",
            "asset",
            None,
            after={"assigned": len(assigned), "failed": len(failed)},
        )
    return {"assigned": len(assigned), "failed": len(failed), "results": assigned, "errors": failed}


# ── the RETIRED staged bulk import (US-AST-010 → CR-028 AST-W3-T5) ──────────
#
# ⚠ **THE DOOR IS CLOSED, NOT THE ROOM.** BR-AST-046 (PO 2026-08-22, verbatim
# in CR-028's record: *"Currently Import is model - that should be converted in
# to workflow - on all tabs as required - import name mathcing with tab"*) and
# BR-MET-096 (one runner, never a second pipeline) retire the S52 staged path:
# the three assets targets now live on metering's five-stage workflow runner
# (`POST /imports` with target `assets_meters · assets_submeters ·
# assets_devices`). So `stage_import` and `commit_import` REFUSE by name and
# point at the runner — CR-026's own sentence ("existing single-shot import
# paths migrate onto the runner") executed for assets.
#
# The `asset_import_batches` / `asset_import_rows` TABLES and their read
# selector stay: committed batches are a tenant's history and hard-won law 4's
# instinct applies — data already written is never stranded by a template
# change. Only the two WRITE verbs refuse.


def stage_probe(asset_no: str | None = None, asset_type: str | None = None) -> str | None:
    """Row-level probe used by metering's unit CSV (BR-MET-039/BR-AST-028):
    returns an error CODE or None."""
    ensure_reference_catalogs()
    if asset_no:
        row = _asset_by_no(asset_no)
        if row is None:
            return "asset_not_found"
        if _current_assignment(row) is not None:
            return "asset_already_assigned"
        return None
    if asset_type:
        exists = models.AssetType.objects.filter(
            tenant_id=_tenant_id(), code__iexact=asset_type, active=True
        ).exists()
        return None if exists else "unknown_type"
    return None


def _refuse_moved_to_runner() -> None:
    """BR-AST-046 / BR-MET-096 — the staged path's two write verbs refuse and
    point at the ONE workflow runner. A catalog refusal, never a 404: a 404
    would read as "this product lost bulk import", and the truth is that it
    moved."""
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-AST-046",
        message_key="assets.import_moved_to_runner",
        params={
            "path": "/imports",
            "targets": ["assets_meters", "assets_submeters", "assets_devices"],
        },
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-032")
def stage_import(actor: Any, payload: Any) -> dict[str, Any]:
    """RETIRED (CR-028 AST-W3-T5). Refuses, naming the runner — see the block
    comment above. The signature stays so every caller gets the refusal
    envelope rather than an AttributeError."""
    _refuse_moved_to_runner()
    raise AssertionError("unreachable")  # pragma: no cover


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-032")
def commit_import(actor: Any, batch_id: Any, payload: Any = None) -> dict[str, Any]:
    """RETIRED (CR-028 AST-W3-T5). Refuses, naming the runner. Committed
    batches remain readable through `selectors.import_batch`; nothing new can
    be staged or committed on this path."""
    _refuse_moved_to_runner()
    raise AssertionError("unreachable")  # pragma: no cover


# ── seam surface consumed by metering (B1) ──────────────────────────────────
def asset_reference_count(*, unit_id: Any) -> int:
    """BR-MET-037: assets EVER attached to the unit (history counts)."""
    return models.AssetAssignment.objects.filter(tenant_id=_tenant_id(), unit_id=unit_id).count()


# ── the CR-028 import-target writes (metering's runner → THIS module) ───────
#
# ⚠ **THE BOUNDARY, STATED (B16 §4.7's own diagram: "writes via assets
# services only").** The ONE workflow runner lives in metering (BR-MET-096) and
# its three assets targets stage, map and validate there — but an assets row is
# NOT metering's to write (B2 r4: metering owns the tables, `apps.assets`
# HOSTS them and its services are the sole writer). So the runner's load stage
# resolves these three functions through `apps/metering/seams.py`, exactly the
# inverse of the `create_asset_for_unit` seam the unit wizard already takes.
# No @require_role here, deliberately: the role was checked on the request that
# enqueued the load (`import_load` + `import_runs.load`), and a worker carries
# an actor id and no role by design (`_JobActor`'s documented contract).


def create_from_import(actor: Any, payload: Any) -> dict[str, Any]:
    """One import row → one asset, through the SAME validate/create path a
    clerk's click uses (`_create_asset_inner`): number allocation on a blank
    number (BR-AST-026), duplicate hard-block (BR-AST-033), measuring-type
    service+UoM law (BR-AST-009), sub-meter parent law (BR-AST-003), and —
    when the row tags a unit (BR-AST-045) — the assignment row under
    `uq_asset_assignments_current`, which is what makes "one asset, one
    current unit" structural rather than promised."""
    data = {k: v for k, v in _payload_dict(payload).items() if v is not None}
    # The sheets carry no opening read; a stray key must not reopen the
    # role-guarded door (`DEF-AST-8102`).
    data.pop("opening_read", None)
    data.pop("opening_read_date", None)
    with transaction.atomic():
        result = _create_asset_for_import(actor, data)
    # Plan U8 — the result file's three facts `asset_dict` does not serve, as
    # the validator accepted them (blank digits are BR-AST-015's 9).
    return {
        **result,
        "register_digits": int(data["register_digits"]) if data.get("register_digits") else 9,
        "allocation_rule": data.get("allocation_rule"),
        "loss_tolerance_pct": _report_value(
            Decimal(str(data["loss_tolerance_pct"])) if data.get("loss_tolerance_pct") else None
        ),
        "allocation_share_pct": _report_value(
            Decimal(str(data["allocation_share_pct"]))
            if data.get("allocation_share_pct")
            else None
        ),
        "billing_changes": [],
    }


#: ⛔ **WHAT A RE-UPLOAD MAY NEVER CHANGE — the plan's *Insert only* and *Match
#: key* columns (PO-confirmed 2026-09-30).** The number is the match key; the
#: type is what the asset IS; the unit, the premises and the parent are WHERE it
#: sits, and moving an asset is the Reassign screen's job (BR-AST-034's *"never
#: moves the asset"*, BR-AST-050 (d)'s *"never re-hangs a sub-meter"*). Stripped
#: SILENTLY, not refused: a corrected file legitimately repeats the cells it was
#: first loaded with, and refusing a value that is not CHANGING would fail
#: every correction pass.
IMPORT_INSERT_ONLY_FIELDS = frozenset(
    {"asset_no", "type", "unit_id", "parent_asset_no", "parent_asset_id", "service_point_id"}
)

#: The 💲 facts a re-upload's result file reports old → new, per asset — the
#: plan tables' *Insert and update 💲* columns across the three sheets, read
#: off the row itself. `service` is read through the service point.
IMPORT_BILLING_REPORT_FIELDS: tuple[str, ...] = (
    "service",
    "size_class",
    "unit",
    "multiplier",
    "net_metering",
    "allocation_share_pct",
    "allocation_rule",
    "export_capacity_kw",
)


def _report_value(value: Any) -> str:
    """One billing fact as the result file prints it: a Decimal without its
    trailing zeros (`1.000000` → `1`), a yes/no for a flag, blank for none."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        text = format(value.normalize(), "f")
        return text
    return str(value)


def _billing_snapshot(asset: models.Asset) -> dict[str, str]:
    # Through the FK the import path already joins (`service_point__service`) —
    # the same path `selectors.billable_asset_count` reads a service by.
    service = asset.service_point.service.code if asset.service_point_id else None
    values: dict[str, Any] = {"service": service}
    for field in IMPORT_BILLING_REPORT_FIELDS[1:]:
        values[field] = getattr(asset, field)
    return {field: _report_value(values[field]) for field in IMPORT_BILLING_REPORT_FIELDS}


def update_from_import(actor: Any, asset_no: str, changes: Any) -> dict[str, Any]:
    """The insert-and-update mode's existing-row half.

    ⛔⛔ **A RE-UPLOAD OVERRIDES THE INSERT-AND-UPDATE COLUMNS, THE 💲 ONES
    INCLUDED — PO ruling 2026-09-30, verbatim: *"we need to override it in case
    of upload"*.** This read *"SPEC fields only … a re-imported row never
    restates a billing-affecting fact"* and stripped `BILLING_AFFECTING_FIELDS`
    silently, so a corrected sheet changing a cart's size or a meter's
    multiplier reported *updated* and changed nothing (`DEF-AST-8099`).
    `BR-AST-034`'s *"billing-affecting never via upload"* is SUPERSEDED.

    **What is NOT superseded, and is how the override stays safe — `BR-AST-012`:**
      * every change is audited before/after — one `asset.updated` row per
        asset naming exactly the fields that changed, a service move included;
      * a billing change is FORWARD-ONLY: nothing here touches a stored read or
        an issued invoice (hard rule 4) — the next bill reads the new value, a
        bill already issued keeps the old one, and the `forward_only_change`
        warning names the fields when reads exist;
      * the result names every 💲 change, old → new (`billing_changes`), and
        the runner prints them in the upload's result file, so an override is
        never silent (the reading the decision log takes, law 13).

    ⚠ **A SERVICE CHANGE MOVES THE ASSET TO THAT SERVICE'S POINT ON ITS UNIT**
    — `ensure_service_point`, which refuses a service the unit's premises does
    not offer (BR-MET-119), is how a cart re-tagged from trash to fire is
    counted on the fire line from the next bill. An asset in inventory has no
    unit, so its service has no column to live in and cannot change here; that
    is reported by the result (no `service` entry), never invented around.

    NO ROLE GUARD HERE, as before: the role was
    checked on the request that enqueued the load (a worker carries no role,
    `_JobActor`, and G140 fails any job path into a guard); the validation is
    the SAME `_validate_asset` an edit uses.

    ⛔ **`DEF-AST-8103` — ONE READ, ONE WRITE, ONE AUDIT ROW PER ASSET.** This
    went through `update_asset.__wrapped__`, which is the clerk's one-edit path
    and reads the row four times over (`_asset_by_no`, the locked re-read, a
    full `asset_dict` for the audit's BEFORE and another for its AFTER, a third
    for the answer — each `asset_dict` walking the assignment, the unit, the
    service point and the sub-meter count). Measured: **22 statements per
    updated row**, ~14 s for 500 on PostgreSQL. It now reads the asset ONCE with
    everything it prints joined in, validates through the SAME `_validate_asset`
    an edit uses, writes only the fields that CHANGED, and audits them as
    BR-AUD-003's standard update row — *"changed-fields diff on update"* — so
    every change still has its before/after (hard rule 7) and nothing that did
    not change is written or logged. The reads count (BR-AST-012's forward-only
    warning) is asked only when a 💲 field actually moved.
    """
    data = _payload_dict(changes)
    overrides = {k: v for k, v in data.items() if k not in IMPORT_INSERT_ONLY_FIELDS}
    service_code = _text(overrides.pop("service", None), 40)
    # `savepoint=False`: the runner already wraps each row in its OWN savepoint
    # (law 14 — the one that makes a refused row safe on PostgreSQL); a second,
    # nested one here would add two statements per row and protect nothing.
    with transaction.atomic(savepoint=False):
        asset = (
            models.Asset.objects.filter(tenant_id=_tenant_id(), asset_no__iexact=str(asset_no))
            .select_related(
                "type", "status", "service_point__service", "parent_asset", "meter_type",
                "read_method",
            )
            .select_for_update(of=("self",))
            .first()
        )
        if asset is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        if asset.status.behavior_class == STAGE_TERMINAL:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-AST-020",
                message_key="assets.retired_is_terminal",
                params={"asset_no": asset.asset_no},
            )
        before = _billing_snapshot(asset)
        cleaned = _validate_asset(overrides, partial=True, current=asset)
        cleaned.pop("type", None)  # insert only — never re-typed by a file
        cleaned.pop("asset_no", None)
        if "external_ref" in cleaned and str(cleaned["external_ref"] or "").lower() != str(
            asset.external_ref or ""
        ).lower():
            # BR-AST-049 — asked only when the reference would actually CHANGE;
            # a correction pass repeating its own match key costs nothing.
            _refuse_duplicate_external_ref(cleaned["external_ref"], exclude_pk=asset.pk)
        changed_before: dict[str, Any] = {}
        changed_after: dict[str, Any] = {}
        fields: list[str] = []
        for field, value in cleaned.items():
            current = getattr(asset, field)
            if current != value:
                changed_before[field] = _audit_value(current)
                changed_after[field] = _audit_value(value)
                setattr(asset, field, value)
                fields.append(field)
        service_moved = False
        if service_code and service_code != before["service"]:
            seat = _current_assignment(asset)
            if seat is not None:
                new_point = seams.ensure_service_point(seat.unit_id, service_code)
                changed_before["service"] = before["service"] or None
                changed_after["service"] = service_code
                changed_before["service_point_id"] = (
                    str(asset.service_point_id) if asset.service_point_id else None
                )
                changed_after["service_point_id"] = str(new_point)
                # Setting the `_id` drops Django's cached related row, so a
                # later `asset.service_point` re-reads the NEW point.
                asset.service_point_id = new_point
                fields.append("service_point")
                service_moved = True
        warnings: list[dict[str, Any]] = []
        if fields:
            asset.save(update_fields=[*fields, "updated_at"])
            _audit(
                actor,
                "asset.updated",
                "asset",
                asset.id,
                before=changed_before,
                after=changed_after,
            )
        after = {
            **before,
            **{
                field: _report_value(getattr(asset, field))
                for field in IMPORT_BILLING_REPORT_FIELDS[1:]
            },
        }
        if service_moved:
            after["service"] = service_code
        billing_changes = [
            {"field": field, "old": before[field], "new": after[field]}
            for field in IMPORT_BILLING_REPORT_FIELDS
            if before[field] != after[field]
        ]
        if billing_changes:
            # BR-AST-012 — forward-only: the stored reads stay as they are and
            # the next bill uses the new value. Asked only when a 💲 field moved.
            reads = seams.read_count_for_asset(asset.id)
            if reads:
                warnings.append(
                    {
                        "code": "forward_only_change",
                        "br_ref": "BR-AST-012",
                        "fields": sorted(change["field"] for change in billing_changes),
                        "reads": reads,
                    }
                )
    return {
        "id": str(asset.id),
        "asset_no": asset.asset_no,
        "serial_no": asset.serial_no,
        "external_ref": asset.external_ref,
        "type": asset.type.code,
        "type_name": asset.type.name,
        "service": after["service"] or None,
        "size_class": asset.size_class,
        "unit": asset.unit,
        "multiplier": str(asset.multiplier),
        "net_metering": asset.net_metering,
        "export_capacity_kw": _report_value(asset.export_capacity_kw) or None,
        "parent_asset_no": asset.parent_asset.asset_no if asset.parent_asset_id else None,
        # The unit's LABEL is the runner's to fill from the index it already
        # holds (`assigned_unit_id`), so the answer costs no unit read.
        "assigned_to": None,
        **_import_extras(asset),
        "warnings": warnings,
        "billing_changes": billing_changes,
    }


def _audit_value(value: Any) -> Any:
    """A changed field as the audit row stores it — JSON-safe, never a model."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "code"):  # a catalogue row (meter type, read method)
        return value.code
    return str(value)


def _import_extras(asset: models.Asset) -> dict[str, Any]:
    """The upload's result-file facts `asset_dict` does not serve (plan U8):
    read off the row already in hand, so they cost no query."""
    return {
        "register_digits": asset.register_digits,
        "allocation_rule": asset.allocation_rule,
        "loss_tolerance_pct": _report_value(asset.loss_tolerance_pct),
        "allocation_share_pct": _report_value(asset.allocation_share_pct),
    }


def rollback_from_import(actor: Any, asset_id: Any, *, run_no: str | None = None) -> str:
    """Reverse ONE asset an import run created — the AST-04 callout made true:
    *"Meters already carrying reads are kept and reported."*

    Returns the outcome the runner counts on its receipt:
      * ``"reversed"`` — the assignment (if any) is CLOSED as of today and the
        asset returns to Inventory (behavior `available`). Deactivate, never
        delete: the physical device the utility bought goes back on the shelf,
        `delete_asset`'s never-referenced gate stays untouched, and a corrected
        re-import can still address the row (a terminal stage would refuse
        every later spec update — BR-AST-020).
      * ``"kept_reads"`` — the asset carries committed reads, so it is KEPT
        exactly as it stands and reported by name; reversing it would orphan
        measurements a bill may already rest on (hard rule 4's instinct).
      * ``"kept_terminal"`` — someone retired it since the load; retired is
        terminal (BR-AST-030) and a rollback does not resurrect or move it.
      * ``"missing"`` — the recorded id no longer resolves; reported, never
        invented around.
    """
    with transaction.atomic():
        row = (
            models.Asset.objects.filter(tenant_id=_tenant_id(), pk=asset_id)
            .select_for_update()
            .select_related("status", "type")
            .first()
        )
        if row is None:
            return "missing"
        if seams.read_count_for_asset(row.id) > 0:
            return "kept_reads"
        if row.status.behavior_class == STAGE_TERMINAL:
            return "kept_terminal"
        current = _current_assignment(row)
        if current is not None:
            current.to_date = seams.tenant_today()
            current.save(update_fields=["to_date", "updated_at"])
        before_status = row.status.code
        row.status = stage_by_code("inventory")
        row.service_point = None  # the seat is released with the assignment
        row.save(update_fields=["status", "service_point", "updated_at"])
        _audit(
            actor,
            "asset.rolled_back_by_import",
            "asset",
            row.id,
            before={"status": before_status},
            after={"status": "inventory", "run_no": run_no},
        )
        return "reversed"


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — the seams `apps/tenancy/seams.py` documents
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders on purpose. The seam contract names
# `apps.assets.services.seed_sample_records`, G20 harvests that exact path, and
# the implementation is large enough to deserve its own file — so the published
# NAME lives here and the CODE lives in `sample_data.py`. The import is inside
# each function because `sample_data` imports this module (it drives the same
# services a clerk's click uses), and a module-level import would be a cycle.
#
# DEF-153: every one of these was DOCUMENTED and UNIMPLEMENTED until
# 2026-08-16, which is why the Sample data panel loaded nothing and a brand-new
# tenant was empty.


def seed_sample_records(actor: Any) -> int:
    """BR-TEN-056/057 — this module's block of the sample set. See sample_data."""
    from apps.assets import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_aged_meters(actor: Any) -> int:
    """`CR-070` `M5` — the three meters past their certification life.

    A SECOND block of this module's sample set, named separately on `S62` so an
    operator can see it land or fail. It is an assets seam and not a work one
    because Work may not write `assets` (`BR-WRK-002` / `G78`); Work READS
    these through `apps/work/seams/assets_seam.assets_past_certification`.

    Removal and the count are the module-wide `is_sample` predicate below, so
    there is deliberately no `remove_sample_aged_meters` beside this.
    """
    from apps.assets import sample_data

    return sample_data.seed_sample_aged_meters(actor)


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — remove what is free, report the rest BY NAME."""
    from apps.assets import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    """How many sample rows this module holds right now, read live."""
    from apps.assets import sample_data

    return sample_data.sample_record_count()


def retire_sample_replaced_meter(actor: Any) -> bool:
    """Sample fixture spec §4 case 3 — retire `W-5011` once its reads exist.

    ⛔ **PUBLISHED FOR DEF-660, and the ordering is the whole point.** The
    meters block runs BEFORE metering's reads block, and
    `metering.validation.retired_meter` errors on any read for a retired meter,
    so retiring inside the meters block made the fixture's own June read
    unpostable: the batch refused, metering's block rolled back, and a fresh
    tenant ended with zero reads, zero bills and zero payments.

    So the reads block calls this when its batches have posted, through
    `apps.metering.seams.retire_sample_replaced_meter`. **The write is still
    assets'** — metering asks, this module does it (B1/B2 r4, the same shape as
    `create_asset_for_unit`).

    True = it retired the meter. False = nothing to do: already terminal, or
    the meter is not on this tenant.
    """
    from apps.assets import sample_data

    return sample_data.retire_the_replaced_meter(actor)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-002@9d8d058 (story+rules snapshot hash — EP-AST-01 add-asset story; co-packets EP-AST-02/03/04@9d8d058)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-09 by story-coder (BR-AST-043 reference-data gap lane — meter_types + read_methods) · AMENDED 2026-08-09 by story-coder (BR-AST-044 both-classifications lane) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (create/update/rollback_from_import for the runner's seam; _validate_asset accepts the BR-AST-047 valuation fields + allocation_share_pct; the staged US-AST-010 import path RETIRED to a BR-AST-046 refusal (tables and read kept)) · AMENDED 2026-08-22 by the CR-028 AST-W2 lane (log_maintenance accepts an optional cost — captured 4dp, never negative, audited with its figure, posted nowhere per §10-D3) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (retire_asset records book value + treatment (D4/BR-AST-047, posts NOTHING), takes an optional final read through the same seam as reassign (refuses while unwired), clears a retired device's measuring link + flags the meter (audit row); log_maintenance kind=test rolls an explicit certification_due by the interval (T5); _reassign_inner accepts final_read_date (the AST-06 value+date input); BOOK_VALUE_TREATMENTS ratified set — tests tests/test_cr028_valuation.py, RED first) · AMENDED 2026-08-22 by the CR-028 debt-sweep lane (D5: the BR-AST-022 final-read capture seam is WIRED — metering publishes capture_final_read, the reassign/retire pass the actor, a requested capture with no value refuses VAL-REQUIRED, and a child moved with its parent takes NO final read (the fields are the parent register's — copied they would commit the parent's value as the child's reading); the BIZ-COMPLETENESS refusal remains only for a metering-less deployment — tests tests/test_cr028_final_read_capture.py, RED first with the old refusal quoted)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ migrate-from-empty✔ makemigrations --check✔ · suite `pytest tests -m "not golden and not isolation"` 587 passed / 8 skipped (580 baseline green + the 7 new BR-AST-043 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (13 baseline + 1 new) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · migration 0003 data path exercised on a scratch file-backed sqlite DB seeded at 0002 (ami→AMI, 'AMR'→amr case-insensitively, 'na'→NULL+logged, NULL→NULL; reverse restores the codes and drops both tables) · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [BR-AST-044 lane 2026-08-09] ruff✔(E4/E7/E9/F) black✔ migrate✔ makemigrations --check✔ (hand-written 0004 matches the model state) · suite `pytest tests -m "not golden and not isolation"` 593 passed / 8 skipped (587 baseline green + 6 new BR-AST-044 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (unchanged) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy STILL NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: asset_types + asset_lifecycle_stages are seeded HERE (tenancy's SEED_LIST_OWNERS routes no asset list and the W1 migrations create the tables empty) — the documented seed_reference_list seam is implemented for the day those routes land · BR-AST-026 per-type prefixes come from the rule's own enumeration; unnamed types keep the series literal · BR-AST-022 final-read capture REFUSES (BIZ-COMPLETENESS) while meter_reads is W2 — never faked · opening-read import column deferred to the reads lane (logged per row, reported) · US-AST-005 (Reads tab) NOT built — it has no data source until meter_reads lands · BR-AST-043 gap lane 2026-08-09: meter_types + read_methods join the lists seeded by ensure_reference_catalogs(); read_method is resolved against the tenant's catalog instead of a hardcoded tuple · metering's own seed_reference_list router still short-circuits meter_types to 0 and knows nothing of read_methods (apps/metering/services.py — OUTSIDE this lane's territory, REPORTED): fixture-driven seeding of the two lists does not run until it forwards them here · BR-AST-044 lane 2026-08-09: `meter_type` accepted on create + edit against the tenant's meter_types catalog by the SAME contract as read_method (code case-insensitively, '-'/'_' interchangeable, or the row uuid; both resolvers now share _flat_catalog_row) · meter_type is DOCUMENTED as NOT billing-affecting (a classification, no rate/quantity/invoice line reads it) at BILLING_AFFECTING_FIELDS and on update_asset — stated, never silently assumed · BR-AST-044's "applies to measuring assets; non-measuring types leave it null" is read as guidance on who fills the field in, NOT as a refusal like BR-AST-010's explicit "unavailable for non-measuring BTM types": a meter_type set on a PV is accepted rather than rejected on a rule the PO did not write — REPORTED · the BR-AST-034 import template gains no meter_type column (that template is a signed enumeration; extending it is a PO call, not this lane's)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

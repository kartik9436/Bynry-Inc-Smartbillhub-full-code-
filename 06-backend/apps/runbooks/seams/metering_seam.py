# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · BR-RBS-019 (the unit of work is
#           never the raw row) · CLAUDE.md hard rule 1 · hard rule 8 (an address
#           lives on premises and nowhere else)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → metering — premises, units, meters, reads, meter-days. READ ONLY.

Read validation, the leak alert and the pre-bill sweep all walk here.

⚠ **THE UNIT OF WORK IS THE METER-DAY, NEVER THE INTERVAL** (`BR-RBS-019`). An
interval batch of **176,640 rows is 1,840 meter-days**, and a per-record
savepoint stays cheap only because the rollup happens before the per-record
pass. A runbook that walked the interval would be correct and unusable.

⚠ **THIS IS ALSO THE ADDRESS DOOR FOR THE WHOLE MODULE** (hard rule 8,
`BR-MET-1161`). An address is stored on `premises` and nowhere else, so a
runbook that wants one **walks to the premises through here** — never off an
account, a meter, a route, a cycle or a work order, because none of them has an
address column. `premises.lat/lng` travels the same way, so a map and an
envelope cannot disagree.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; each later wave brings the reads its own
runbooks actually need. A selector written here now would be a function nothing
calls (hard-won law 2), and naming one in prose that `metering` does not expose
would fail `G20` — the guard that caught `DEF-075`, where a documented seam half
nobody had authored answered `None` and a currency lock let issued bills be
re-denominated. What this module will need and `metering` does not offer today
is inventoried in `17-runbooks/13-selector-inventory.md`, and **`metering` adds
each of them** — never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="metering",
    pair="operations → metering",
    crosses="premises, units, meters, reads, meter-days",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────
#
# Added with `definitions/configuration_check.py` in the same commit. Every
# call below resolves a selector `metering` already publishes:
# `apps.metering.selectors.premises_rollup`, `apps.metering.selectors.units_list`,
# `apps.metering.selectors.service_points_for_units`,
# `apps.metering.selectors.unit_assets`,
# `apps.metering.selectors.billing_multiplier_for` and
# `apps.metering.selectors.cycles_list`.


def census() -> dict[str, int]:
    """How many premises and units this tenant holds — the *Affects* column's
    denominator when a finding is about the estate rather than about one row."""
    from apps.metering import selectors as metering_selectors

    rollup = metering_selectors.premises_rollup()
    return {"premises": int(rollup.get("premises", 0)), "units": int(rollup.get("units", 0))}


def service_point_graph() -> list[dict[str, object]]:
    """Every unit with its service points, its meters and each meter's last read.

    ⚠ **ONE WALK ANSWERS THREE STEPS, AND THAT IS WHY IT IS ONE FUNCTION.**
    Runbook 1 asks *does every service point have a meter* (step 7), *does every
    meter have a read* (step 8) and *how high does usage go* (step 5) — three
    questions over the same graph. Three seam functions would be three walks of
    the same rows and three chances for them to disagree about which units are
    in scope.

    ⚠ **THE COST IS ONE QUERY PER UNIT AND IT IS STATED RATHER THAN HIDDEN.**
    `service_points_for_units` is bulk; `unit_assets` is per unit and metering
    publishes no bulk form of it. At the top of the ICP — 40,000 accounts — that
    is 40,000 round trips for one run of a Check a clerk presses on demand.
    **Nothing here has been measured**, which is exactly the gap
    `13-selector-inventory.md` §4 names in its own last bullet, and the honest
    fix is a bulk `assets_for_units` in `metering` rather than a cache here.
    """
    from apps.metering import selectors as metering_selectors

    units = list(metering_selectors.units_list())
    unit_ids = [str(unit.id) for unit in units]
    points_by_unit = metering_selectors.service_points_for_units(unit_ids)
    graph: list[dict[str, object]] = []
    for unit in units:
        unit_id = str(unit.id)
        points = points_by_unit.get(unit_id) or []
        if not points:
            # A unit with no service point takes no service, so runbook 1 has
            # nothing to say about its meters. It is NOT a silent exclusion: the
            # count is reported beside the checked count so an empty estate and
            # a fully-checked one cannot read the same (hard-won law 7).
            graph.append({"unit_id": unit_id, "points": [], "assets": []})
            continue
        assets: list[dict[str, object]] = []
        for group in metering_selectors.unit_assets(unit_id).get("groups", []):
            for asset in group.get("assets", []):
                assets.append(
                    {
                        "id": asset.get("id"),
                        "category": asset.get("category"),
                        "service": asset.get("service"),
                        "last_read": asset.get("last_read"),
                    }
                )
        graph.append(
            {
                "unit_id": unit_id,
                "points": [
                    {"id": point.get("id"), "service": point.get("service")} for point in points
                ],
                "assets": assets,
            }
        )
    return graph


def multiplier_for(unit_id, service_code):
    """The multiplier this connection's reads were computed with, or `None`.

    ⚠ **`None` MEANS *no read states one*, NOT *the meter has no multiplier*,
    and runbook 1 leans on that distinction.** Step 7 asks it only of a unit
    whose meter already HAS a read, so a missing multiplier is never reported
    twice — once as a meter fault and once as the missing read that is really
    step 8's finding.
    """
    from apps.metering import selectors as metering_selectors

    return metering_selectors.billing_multiplier_for(unit_id, service_code)


def cycles() -> list[dict[str, object]]:
    """Every billing cycle with its read window and its bill day.

    Runbook 1 step 8's second half — *the read window closes before bill day*.
    `cycle_dict` derives the window from `start_day` + `days_to_complete`
    (B17 §2), so the comparison is against the tenant's own configuration and
    never against a constant this module invented.
    """
    from apps.metering import selectors as metering_selectors

    return list(metering_selectors.cycles_list())


def resolve_anchors(unit_ids, premises_ids) -> dict[str, dict]:
    """Which of these unit ids and premises ids this tenant can actually see.

    Two bulk reads — `apps.metering.selectors.unit_refs` and
    `apps.metering.selectors.premises_refs` — each ONE query, so runbook 1 step
    6 walks an estate of any size in two round trips rather than one per
    account. **A unit absent from the returned map is a unit this tenant cannot
    see**, which is the 404-never-403 boundary expressed as absence, and for
    this Check it is the same thing as a broken chain: an account pointing at it
    can be priced by nobody.

    `unit_refs` carries `premises_id` and `premise_address`, so the whole walk
    the card names — **account → unit → premise → address** — is answered here
    without any other module holding an address column (hard rule 8).
    """
    from apps.metering import selectors as metering_selectors

    return {
        "units": metering_selectors.unit_refs(list(unit_ids)),
        "premises": metering_selectors.premises_refs(list(premises_ids)),
    }


# ── CR-075 wave L · the read runbook 8's DISPUTE guard makes (US-RBS-010) ──


def unit_has_dispute_hold(unit_id) -> bool:
    """Is a dispute open against this unit's readings?

    `apps.metering.selectors.dispute_holds_for_unit` — the same selector
    `apps/billing/dispute_ageing.py` resolves for `BR-MET-133` clause 4, read
    the same way and for the same reason: **a disputed account is not chased
    while the dispute is open.**

    ⚠ **THE DISPUTE IS A FACT ABOUT A UNIT AND THE LADDER WALKS ACCOUNTS**, so
    runbook 8's guard walks account → unit through `customers_seam` before
    asking this. `BR-CUS-068`'s multi-unit account means one account can carry
    several, and any open hold on any of them guards the account — the same
    reading `dispute_ageing.open_dispute_for_account` takes, stated here rather
    than re-derived.

    ⚠ **AN EMPTY LIST MEANS *no open dispute*, AND AN ABSENT SELECTOR WOULD NOT
    MEAN THAT.** `dispute_ageing.py` makes exactly this distinction — *"NOT 'no
    dispute' … the assessment refuses rather than charging a fee it cannot
    justify"*. Here the selector is imported directly rather than resolved, so
    its absence is an ImportError at startup and not a silent `False`; a guard
    that failed open would let a disputed customer be chased and nothing would
    notice.
    """
    from apps.metering import selectors as metering_selectors

    return bool(metering_selectors.dispute_holds_for_unit(unit_id))


# ── CR-075 wave Q′ · the two reads runbook 20 makes (US-RBS-032) ───────────
#
# Both resolve a selector `metering` publishes:
# `apps.metering.selectors.premises_reconciliation_set` and
# `apps.metering.selectors.staged_import_batch`, added by the module that owns
# `premises` and `import_runs` in the same commit as this file.


def premises_for_reconciliation(*, include_sample: bool = False) -> list[dict[str, object]]:
    """Our side of the parcel comparison — every premises, with what can differ.

    `apps.metering.selectors.premises_reconciliation_set` — ONE query for the
    whole estate, carrying the two match keys (`external_ref`, the standardised
    address) and the six fields `RB-120`'s disposition table names.

    ⚠ **THIS IS THE ADDRESS DOOR AND THERE IS NO OTHER** (hard rule 8,
    `BR-MET-1161`). An account, a route, a cycle, an invoice, a work order and a
    map pin all derive their address by walking to the premises, so a parcel
    feed correcting one address here corrects all of them — which is why runbook
    20 plans first, caps the run and never touches the three fields that decide
    tax.
    """
    from apps.metering import selectors as metering_selectors

    return list(metering_selectors.premises_reconciliation_set(include_sample=include_sample))


def staged_import_batch(target: str, run_id=None) -> dict[str, object] | None:
    """A file somebody uploaded for `target`, staged and NOT loaded, or `None`.

    `apps.metering.selectors.staged_import_batch`. This is the **second door**
    runbook 20 opens: wave `P` learned that a pure connection check is the wrong
    question, because reporting *"no connection"* over work a person has already
    uploaded is a refusal nobody deserved.

    ⚠ **A LOADED RUN IS NOT A BATCH** and the selector refuses one. Its rows are
    premises by then; planning changes against a file the importer has already
    applied would compare the estate with itself.
    """
    from apps.metering import selectors as metering_selectors

    return metering_selectors.staged_import_batch(str(target), run_id)


# ── CR-075 wave S · the estate-wide reads runbooks 5, 18 and 19 make ──────
#
# Both resolve selectors `metering` publishes —
# `apps.metering.selectors.premises_meter_census` and
# `apps.metering.selectors.meter_read_history` — added by the owning module in
# the same commit. They answer `13-selector-inventory.md` rows **S-2**, **S-3**,
# **S-6**, **S-7** and **S-8**, and there are TWO of them rather than five for
# the reason that file gives: *"a module that adds them one at a time will write
# the same window query five times."*


def premises_meter_census(*, include_sample: bool = True) -> dict[str, object]:
    """The chain, one walk: premises → units → service points → meters.

    `RB-119` steps 2–4 and `RB-118` step 1. **The address comes from `premises`
    and from nowhere else** (hard rule 8, `BR-MET-1161`), which is why the
    address parts travel on the premises row here and on nothing else.

    ⚠ **`meters_answered` IS NOT DECORATION.** `False` means the assets seam
    resolved nothing at all, and an empty meter list then means *nobody could
    answer* rather than *this utility owns no meters* — `DEF-075`'s exact shape,
    where `None` was read as "this module has nothing" and a tenant
    re-denominated its books over an issued bill.
    """
    from apps.metering import selectors as metering_selectors

    return dict(metering_selectors.premises_meter_census(include_sample=include_sample))


def meter_read_history(
    *,
    asset_ids=None,
    unit_ids=None,
    service_code: str | None = None,
    since=None,
    limit_per_meter: int = 60,
) -> list[dict[str, object]]:
    """Each meter's OWN history — committed heads, oldest first, with its unit.

    `RB-105` steps 1–7, `RB-118` step 3 and `RB-104` step 6 — which narrows by
    `unit_ids` because it is about ONE account's meter and must not read the
    fleet to answer that. ⚠ **`RBR-09`: every threshold is
    relative to the meter's own history, never to a fleet average** — a
    restaurant and a retired couple are both normal at wildly different volumes
    — so this returns rows per meter and computes no summary at all. The median,
    the spike and the flat line are the runbook's judgments.
    """
    from apps.metering import selectors as metering_selectors

    return [
        dict(one)
        for one in metering_selectors.meter_read_history(
            asset_ids=asset_ids,
            unit_ids=unit_ids,
            service_code=service_code,
            since=since,
            limit_per_meter=limit_per_meter,
        )
    ]


# ── CR-075 wave G · the estate axes runbook 24 groups on (US-RBS-005) ─────
#
# Added with `definitions/coverage_grid.py` in the same commit. Every call below
# resolves a selector `metering` already publishes —
# `apps.metering.selectors.units_list`,
# `apps.metering.selectors.service_points_for_units`,
# `apps.metering.selectors.cycles_list` and
# `apps.metering.selectors.units_in_cycle` — and nothing here reimplements a
# rule that lives on the far side (`BR-RBS-039`, `G20`).


def unit_billing_axes() -> dict[str, dict[str, object]]:
    """Per unit: **the plan it derives, the services it takes, the cycles that
    read it** — the three axes runbook 24 picks one account from each cell of.

    ⚠ **THE CYCLE IS ASKED OF `units_in_cycle`, NOT READ OFF A STAMP.** That
    selector's own docstring is the reason: `service_points.cycle_id` is written
    only when a route is created or edited, so filtering on it is a SNAPSHOT —
    `DEF-225` (a unit added to a serviced building afterwards was never read and
    never billed) and `DEF-249` (a base-only unit with no service point was
    invisible) are both that one reading. The derived answer is what the bill
    run itself scopes on, and a coverage grid that grouped by a different cycle
    from the one that will bill would be a grid of the wrong estate.

    ⚠ **`rate_plan_id` IS THE UNIT'S, BECAUSE THE ACCOUNT DERIVES ITS PLAN FROM
    THE UNIT** (PO ruling 2026-08-11 — *there is no account-side plan record*),
    which is also how `billing.gather` resolves it. `None` is a real answer and
    is NOT an empty string: `BR-MET-100` makes an unplanned unit a state a
    utility can be in and must be able to find, so it groups as its own cell
    rather than being dropped.

    ⚠ **THE COST IS ONE QUERY PER CYCLE PLUS TWO, AND IT IS STATED RATHER THAN
    HIDDEN** — the shape `service_point_graph` above already records. A utility
    with six cycles pays eight round trips whatever its size, because
    `units_list` and `service_points_for_units` are each one query and
    `units_in_cycle` is one per cycle. That is the read this seam was written to
    make cheap; a per-unit cycle lookup would have been 40,000 of them at the
    top of the ICP.
    """
    from apps.metering import selectors as metering_selectors

    units = list(metering_selectors.units_list())
    unit_ids = [str(unit.id) for unit in units]
    points_by_unit = metering_selectors.service_points_for_units(unit_ids)

    cycles_of: dict[str, list[str]] = {}
    for cycle in metering_selectors.cycles_list():
        code = str(cycle.get("code") or "")
        for unit_id in metering_selectors.units_in_cycle(cycle.get("id")):
            cycles_of.setdefault(str(unit_id), []).append(code)

    axes: dict[str, dict[str, object]] = {}
    for unit in units:
        unit_id = str(unit.id)
        services = sorted(
            {
                str(point.get("service"))
                for point in (points_by_unit.get(unit_id) or [])
                if point.get("service")
            }
        )
        axes[unit_id] = {
            "unit_id": unit_id,
            "label": unit.label,
            "rate_plan_id": str(unit.rate_plan_id) if unit.rate_plan_id else None,
            "services": services,
            "cycles": sorted(cycles_of.get(unit_id, [])),
        }
    return axes


# ── CR-075 wave R′ · the reads runbooks 11 and 21 make (US-RBS-023 · 033) ──
#
# Both resolve a selector `metering` publishes:
# `apps.metering.selectors.interval_batch` and
# `apps.metering.selectors.meter_normals`, added by the module that owns
# `read_import_batches` and `meter_reads` in the same commit as this file.
# `13-selector-inventory.md` carries them as S-1, S-4 and S-5.


def interval_batch(batch_id=None) -> dict[str, object] | None:
    """The interval batch that landed, ALREADY ROLLED UP TO THE METER-DAY.

    `apps.metering.selectors.interval_batch`. ⚠ **THE ROLLUP HAPPENS ON THE
    OWNING SIDE OF THIS SEAM AND THAT IS THE WHOLE POINT** (`BR-RBS-019`,
    `RBR-18`): *"176,640 intervals become 1,840 meter-days"*, so 1,840 rows
    cross rather than 176,640, and a per-record savepoint stays cheap because
    the runbook never sees an interval at all.

    ⚠ **EVERY ROLLED-UP QUANTITY CARRIES ITS EXPLICIT UNIT** (CLAUDE.md hard
    rule 3). A meter-day whose own intervals disagree about their unit carries
    `unit_conflict` and NO total — an aggregation that dropped its unit would be
    a number nobody can check, and this is the one place in the module where six
    figures of readings are added together.

    `None` when nothing has landed — a real state and the sentence a runbook
    stops on, never an empty batch.
    """
    from apps.metering import selectors as metering_selectors

    return metering_selectors.interval_batch(batch_id)


def meter_normals(asset_ids, *, as_of, days: int = 90) -> dict[str, dict[str, object]]:
    """Each meter's OWN 90-day average and its LAST GOOD DAY — S-1 and S-4.

    `apps.metering.selectors.meter_normals`, one query for the whole set.

    ⚠ **ITS OWN NORMAL, NEVER A FLEET NUMBER** (`RB-111` step 2) — a block of
    flats and a bungalow share nothing — and **no normal is not zero**: a meter
    with no history answers `None`, because a zero would make every reading
    infinitely above its own normal and put that on a customer's phone.

    `as_of` is STATED and never read from a clock (`BR-TEN-043`, gate `G6`).
    """
    from apps.metering import selectors as metering_selectors

    return metering_selectors.meter_normals(asset_ids, as_of=as_of, days=days)


def read_validation_limits() -> dict[str, object]:
    """The tenant's OWN high/low/rollover figures, per service, with their unit.

    `apps.metering.selectors.read_validation_overview` — the same read
    `GET /settings/read-validation` serves, so `RB-121`'s *"From Settings · read
    validation"* row and the Settings screen cannot disagree about what the
    limits are (`RBR-03`: policy lives in Settings and is never duplicated on a
    card).

    ⚠ **`source = "none"` IS AN ANSWER AND NOT A ZERO.** A service with no
    figure anywhere has its threshold rules SKIPPED AND REPORTED
    (`BR-MET-020`), and the runbook says so on the screen rather than validating
    against an invented limit — which would flag every reading or none.

    ⚠ **THE LIMIT CARRIES ITS UNIT** (`high_abs_unit`, hard rule 3). A limit of
    *50* means nothing; *50 kgal* is a limit a reading can be compared with.
    """
    from apps.metering import selectors as metering_selectors

    return dict(metering_selectors.read_validation_overview())


# ── CR-075 runbook 28 · the meter fleet's age and its tests (US-RBS-043) ──
#
# Added with `definitions/meter_change_out.py` in the same commit. The call
# below resolves `apps.metering.selectors.meter_lifecycle_census`, which is
# metering's own read of assets — `metering` owns assets (B2 r4), so a runbook
# asking `apps.assets` directly would be a tenth seam with no register row
# (`G115` finding 7) and a read of a module this one does not declare.


def meter_lifecycle_census(*, include_sample: bool = True) -> dict[str, object]:
    """Every meter with its AGE and its LAST TEST, and the unit it stands on.

    `RB-128` steps 1 and 2. **Two dates and a life, per meter** — the install
    date the age counts from, the expected life that is the meter's own
    change-out age, the last test on file and the interval it is due on.

    ⚠ **NOTHING IS DEFAULTED ON THE FAR SIDE AND A `None` IS THE ANSWER.** A
    meter with no `expected_life_years` can never be found by an age rule and a
    meter with no `install_date` has no age at all; both cross as `None` so the
    runbook can COUNT them beside what it found. A read that substituted a
    twenty-year default here would make *"0 past change-out age"* mean two
    different things with nothing on any screen to tell them apart (hard-won
    law 7).

    ⚠ **`meters_answered` IS NOT DECORATION.** `False` means the assets seam
    resolved nothing at all, so an empty meter list means *nobody could answer*
    rather than *this utility owns no meters* — `DEF-075`'s exact shape.
    """
    from apps.metering import selectors as metering_selectors

    answer = metering_selectors.meter_lifecycle_census(include_sample=include_sample)
    return {
        "meters": [dict(one) for one in (answer.get("meters") or [])],
        "meters_answered": bool(answer.get("meters_answered")),
    }

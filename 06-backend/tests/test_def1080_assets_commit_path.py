# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1080 (high) — the assets import returns HTTP 500 at stage 4 on
#           the PO's own file and NOTHING is written; DEF-1079 (medium) — the
#           validate strip calls 20 inventory-bound meters "No remarks at all"
# Rules:    BR-AST-045 (one asset one unit; BLANK unit ACCEPTED → inventory) ·
#           BR-AST-009 (a meter declares its service AND its explicit UoM) ·
#           BR-AST-026/033 (numbers) · BR-MET-090 (stages) · DEF-577 (the
#           series catch-up) · CLAUDE.md hard rule 1 (tenant scoping)
# Screens:  WFL-01.meters.1–5 on `assets/import?target=assets_meters`
# ───────────────────────────────────────────────────────
"""THE COMMIT PATH, DRIVEN END TO END ON THE PO'S OWN ROW SHAPE.

**THIS FILE EXISTS BECAUSE NOTHING ELSE IN THE REPO DOES WHAT IT DOES.** Every
assets-import test drives the SEEDED Silver Creek fixture, whose data always
resolves, and DEF-1080's escape_reason names the gap precisely: *"the dry run
and the commit share a predicate but not a code path, so a green rehearsal
proves nothing about the write."* On 2026-08-27 the Product Owner watched
stages 1, 2 and 3 report 20 rows checked · 20 will load · 0 blocked · 0
warnings · all twelve rules 0 hits, pressed Load, and got

    Something went wrong. Nothing was saved — try again.   (HTTP 500)

The file's shape is the fixture below, read off the PO's own Excel window, and
it has two features no committed fixture has:

  1. **Every row is inventory-bound** — `unit_ref` BLANK on all 20 — so
     `_load_assets_rows` takes the `to_inventory` branch twenty times and the
     `unit_tagged` branch zero times.
  2. **Bare-numeric asset numbers** (`52686777`, `442938`, …) on a tenant whose
     own meters are prefixed, which is what `_catch_up_target_series` (DEF-577,
     🔒 HUMAN-REVIEW-PENDING) reads after all twenty writes.

⚠ **THE TENANT IS OTTUMWA WATER WORKS AND IT HAS NO UNITS**, which is the
condition that makes clause 1 true of every row rather than of three of them.

⛔ **AND THE MEASURED ANSWER IS THAT IT DOES NOT REPRODUCE — SAY SO PLAINLY.**
Run on HEAD 2026-08-27, this file is **5 passed**: the PO's twenty rows drive
extract → transform → validate → dry-run → **load** and write 20 assets, 20 to
inventory, 0 unit-tagged, 0 assignment rows, with the rollback point ON. The
one lead that could only be settled by a test is settled here and it is
**ruled OUT**: `_catch_up_target_series` (DEF-577, 🔒 HUMAN-REVIEW-PENDING)
runs after all twenty writes inside the same transaction, which fits *"nothing
was saved"* exactly — so the parametrised case below drives the commit under
three of the catalogue's four asset formats, including the one under which
every bare-numeric row IS a number the series could have written. It drags the
counter from 1 to **94,551,606** and the load still returns 20.

**So this file does not close DEF-1080. It closes the GAP DEF-1080's own
prevention names** — *"a commit-path test per target that loads a file end to
end, not only the dry run"* — and it narrows the remaining search to what the
repo cannot hold: the deployed tenant's own data and environment. The row
stays open, and the honest next step is its second half — ask the PO for the
trace reference, which the refusal did not carry (the same sibling DEF-965
names). **Do not narrow the scope to the parts that were reproduced.**
"""

import csv
import io

import pytest

from apps.assets import models as assets_models
from apps.metering import import_runs, models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    seed_physical_series,
    staff_actor,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


#: The PO's thirteen columns, in the order the shipped meters template writes
#: them — so this file is also a check that the template a first-time operator
#: downloads can be driven to a COMMIT, which nothing else asserts.
HEADERS = [
    "asset_no",
    "meter_type",
    "service",
    "read_method",
    "multiplier",
    "unit_ref",
    "manufacturer",
    "model",
    "install_date",
    "certification_due",
    "warranty_end",
    "supplier",
    "purchase_cost",
]

MAPPING = {header: header for header in HEADERS}

#: The PO's own twenty asset numbers, verbatim from the screen share. Bare
#: digits, no prefix, and DELIBERATELY of varying length (`442938` is six,
#: `94551605` is eight) — a fixture of uniform-width numbers would not
#: exercise `core_numbering.sequence_of` the way the real file does.
ASSET_NOS = [
    "52686777", "4429379", "4429375", "442938", "94551605",
    "4429386", "4429388", "94100759", "94253578", "92106557",
    "89470224", "16001045", "17491282", "52056044", "52610990",
    "69574969", "92339396", "68862417", "67656648", "69727014",
]

ALL_OFF = {
    "drop_exact_duplicates": False,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}


@pytest.fixture()
def ottumwa(growth_plan, identity_seam):  # noqa: F405
    """The PO's own tenant: Water · Sewer · Trash, and NOT ONE UNIT."""
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Ottumwa Water Works",
            subdomain="ottumwa-water-works",
            services=["water", "sewer", "trash"],
            owner={
                "full_name": "Ops Owner",
                "email": "owner@ottumwa-water-works.test",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def vijay(ottumwa):
    """The actor on the PO's screen share — a System Admin."""
    return staff_actor(ottumwa, "system_admin", "vijay@ottumwa-water-works.test")


def po_meters_csv() -> str:
    """The PO's file, row for row.

    `service` is **title case** (`Water`, not `water`) because that is what the
    operator typed; `install_date` is `M/D/YYYY` because that is what Excel
    wrote and the app confirmed it read them that way.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADERS)
    for index, asset_no in enumerate(ASSET_NOS, start=1):
        writer.writerow(
            [
                asset_no,
                "amr",
                "Water",
                "amr",
                "1",
                "",  # ⚠ unit_ref BLANK on every row — this is the shape
                "Neptune 360",
                "MX-100",
                f"1/{index}/2026",
                f"1/{index}/2027",
                f"1/{index}/2031",
                "Sample Meter Supply Co",
                "164",
            ]
        )
    return buffer.getvalue()


def _validated(actor, content: str) -> str:
    run = import_runs.extract(
        actor,
        {
            "target": "assets_meters",
            "source_kind": "file",
            "file_name": "ottumwa_meters.xlsx",
            "content": content,
            "session_ref": "sess_def1080",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": MAPPING, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"])
    return run["id"]


# ══════════════════════════════════════════════════════════════════════════
# DEF-1080 — THE REHEARSAL IS GREEN; DOES THE COMMIT RUN?
# ══════════════════════════════════════════════════════════════════════════


def test_def1080__stages_1_to_3_are_green_on_the_POs_file(ottumwa, vijay):
    """The half the PO could already see: 20 checked, 20 forward, 0 blocked.

    Asserted FIRST and separately, because if this ever goes red the 500 below
    is a different defect and the report must not confuse the two.
    """
    with tenant_ctx(ottumwa):
        run_id = _validated(vijay, po_meters_csv())
        run = metering_models.ImportRun.objects.get(pk=run_id)
        counts = run.counts or {}
    assert counts.get("checked") == 20
    assert counts.get("forward") == 20
    assert counts.get("errors") == 0


def test_def1080__the_commit_writes_all_twenty_to_inventory(ottumwa, vijay):
    """**THE DEFECT.** Same run, one more stage: Load.

    Every row is inventory-bound (`unit_ref` blank), so `BR-AST-045`'s blank
    branch runs twenty times: 20 created, 20 to inventory, 0 unit-tagged, and
    not one assignment row.
    """
    with tenant_ctx(ottumwa):
        run_id = _validated(vijay, po_meters_csv())
        rehearsed = import_runs.dry_run(vijay, run_id, "insert")
        assert rehearsed["will_create"] == 20
        receipt = import_runs.load(
            vijay, run_id, {"write_mode": "insert", "create_rollback_point": True}
        )
        counts = metering_models.ImportRun.objects.get(pk=run_id).counts or {}
        assets = assets_models.Asset.objects.filter(asset_no__in=ASSET_NOS)
        assignments = assets_models.AssetAssignment.objects.filter(asset__in=assets)
    assert receipt["receipt"]["loaded"] == 20
    assert counts["created"] == 20
    assert counts["to_inventory"] == 20
    assert counts["unit_tagged"] == 0
    assert assets.count() == 20
    assert assignments.count() == 0


# ══════════════════════════════════════════════════════════════════════════
# DEF-1080 — RULING THE DEF-577 SERIES CATCH-UP IN OR OUT, WITH A TEST
# ══════════════════════════════════════════════════════════════════════════
#
# `_catch_up_target_series` runs AFTER all twenty writes, inside the same
# transaction, which fits "nothing was saved" exactly. It is DEF-577's code and
# is flagged 🔒 HUMAN-REVIEW-PENDING, so it is READ carefully and RULED ON by
# test rather than by inference.
#
# The default asset series is `AST-{00000}` (SERIES_DEFAULTS, from
# `core.numbering.SERIES_CATALOG`), and `sequence_of` returns None for a bare
# number under it — so the test above never exercised the catch-up at all. The
# case below puts the tenant on the catalogue's OWN fourth option, `{00000}`,
# under which every one of the PO's twenty numbers IS a number the series could
# have written, and the counter is dragged from 1 to 94,551,606.


@pytest.mark.parametrize("series_format", ["AST-{00000}", "M-{0000}", "{00000}"])
def test_def1080__the_commit_survives_every_asset_series_format(ottumwa, vijay, series_format):
    """Three of the catalogue's four asset formats, one of which MATCHES the
    PO's bare-numeric file and drags the counter eight digits forward."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(ottumwa):
        tenancy_models.NumberSeries.objects.update_or_create(
            tenant_id=ottumwa.id,
            series="asset",
            defaults={"format": series_format, "next_number": 1},
        )
        run_id = _validated(vijay, po_meters_csv())
        receipt = import_runs.load(
            vijay, run_id, {"write_mode": "insert", "create_rollback_point": True}
        )
        counter = tenancy_models.NumberSeries.objects.get(
            tenant_id=ottumwa.id, series="asset"
        ).next_number
    assert receipt["receipt"]["loaded"] == 20
    # `{00000}` is the only one of the three that can have written `94551605`,
    # so it is the only one that moves — the other two leave the counter alone
    # because a number their format could not produce is not a collision.
    assert counter == (94551606 if series_format == "{00000}" else 1)


# ══════════════════════════════════════════════════════════════════════════
# DEF-1080 — THE "PREMISES BUT NO UNITS" STATE, RULED IN OR OUT
# ══════════════════════════════════════════════════════════════════════════
#
# The lead: `_sample_reference_cells()` ships the template's `unit_ref` example
# blank ONLY when the tenant has no units at all (DEF-962's correct refusal to
# invent `U-00001`), and the PO's file has it blank — so Ottumwa Water Works
# most likely holds **zero units**. That is a distinctive state, and it is
# worth saying which half of it the tests above already cover: the `ottumwa`
# fixture has neither premises NOR units, so `_unit_reference_index()` is
# already `{}` there and the 500 did not fall out of it.
#
# What they do NOT cover is the ASYMMETRIC state — premises on file, units
# not — where `_premises_units_index()` has entries whose value lists are
# empty. That is the shape below.


def test_def1080__premises_on_file_with_no_units_still_commits(ottumwa, vijay):
    """Premises loaded, units NOT — the state a utility is in between step 1
    and step 2 of the build order, and the state the PO's blank unit column
    says Ottumwa was in."""
    from apps.metering import services as metering_services

    with tenant_ctx(ottumwa):
        for index in range(3):
            metering_services.create_premises(
                vijay,
                {"owner_id": owner_for(vijay), 
                    "address_line": f"{index + 100} Court St",
                    "city": "Ottumwa",
                    "state": "IA",
                    "postal_code": "52501",
                    "premises_type": "single_family",
                    "services_available": ["water"],
                },
            )
        assert metering_models.Unit.objects.count() == 0
        run_id = _validated(vijay, po_meters_csv())
        receipt = import_runs.load(
            vijay, run_id, {"write_mode": "insert", "create_rollback_point": True}
        )
        counts = metering_models.ImportRun.objects.get(pk=run_id).counts or {}
    assert receipt["receipt"]["loaded"] == 20
    assert counts["to_inventory"] == 20


# ══════════════════════════════════════════════════════════════════════════
# DEF-1079 — THE SUMMARY MAY NOT CONTRADICT THE PANEL BELOW IT
# ══════════════════════════════════════════════════════════════════════════
#
# The PO's screen, on this exact file: the KPI strip read **"NO REMARKS AT ALL
# — 20"** while the panel directly below read *"Unit — mapped from `unit_ref`,
# and blank in all 20 rows. Nothing will be written to it."* **Both were
# true.** `counts.clean` counts rows with no RULE HIT, and a blank unit fired
# no rule precisely because BR-AST-045 makes it lawful — so the single most
# consequential fact about the load was reported only in a grey side panel.
#
# ⚠ **BR-AST-045 IS NOT IN QUESTION AND IS NOT CHANGED.** A blank unit loading
# to inventory is the PO's own ruling. What is fixed is the SILENCE.


def test_def1079__twenty_inventory_bound_rows_are_not_called_clean(ottumwa, vijay):
    """The KPI strip's own number. Twenty rows, twenty warnings, zero clean —
    and still twenty going forward, because a warning never stops a row
    (BR-MET-129).

    ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN** (hard-won law 7). Without
    `AST.UNIT_BLANK_TO_INVENTORY` this file reported, verbatim:

        E       assert 20 == 0
        E        +  where 20 = {'checked': 20, 'clean': 20, 'errors': 0, ...}['clean']

    — twenty rows with nothing to say about them, which is what the PO read.
    """
    with tenant_ctx(ottumwa):
        run_id = _validated(vijay, po_meters_csv())
        counts = metering_models.ImportRun.objects.get(pk=run_id).counts or {}
        rules = {rule["code"]: rule for rule in import_runs.run_dict(
            metering_models.ImportRun.objects.get(pk=run_id), with_rules=True
        )["rules"]}
    assert counts["clean"] == 0
    assert counts["warnings"] == 20
    # The row still LOADS — BR-AST-045 is untouched and BR-MET-129 is the law.
    assert counts["forward"] == 20
    assert counts["errors"] == 0
    blank = rules["AST.UNIT_BLANK_TO_INVENTORY"]
    assert blank["severity"] == "warning"
    assert blank["hits"] == 20
    # ⚠ AND THE RULE THE SCREEN ALREADY HAD SAYS NOTHING ABOUT THESE ROWS —
    # its sentence ("blank loads to inventory") reads as reassurance and fires
    # only when a unit IS named and missing. That is why a second rule exists.
    assert rules["AST.UNIT_ON_FILE"]["hits"] == 0


def test_def1079__the_rehearsal_splits_will_create_into_service_and_inventory(ottumwa, vijay):
    """*"Will create 20"* is not an honest number on its own.

    The two halves always sum to `will_create`, so a screen prints them without
    arithmetic of its own — and on the PO's file the honest sentence is *"20 —
    all into inventory"*.
    """
    with tenant_ctx(ottumwa):
        run_id = _validated(vijay, po_meters_csv())
        figures = import_runs.dry_run(vijay, run_id, "insert")
    assert figures["will_create"] == 20
    assert figures["will_create_to_inventory"] == 20
    assert figures["will_create_in_service"] == 0
    assert (
        figures["will_create_in_service"] + figures["will_create_to_inventory"]
        == figures["will_create"]
    )


def test_def1079__the_strip_and_the_blank_column_panel_cannot_disagree(ottumwa, vijay):
    """DEF-1079's escape_reason, made into a check.

    The escape was that two surfaces on ONE screen reported the same fact and
    nothing compared them: the blank-column panel said *"blank in all 20
    rows"* and the KPI strip said *"no remarks at all — 20"*. The invariant
    that makes that impossible is the one asserted here — **a column reported
    blank in every row cannot leave every row clean.**
    """
    with tenant_ctx(ottumwa):
        run_id = _validated(vijay, po_meters_csv())
        run = metering_models.ImportRun.objects.get(pk=run_id)
        payload = import_runs.run_dict(run, with_rules=True)
        counts = run.counts or {}
    # `empty_columns` IS the panel: "mapped, Matched, and empty in every row"
    # (`_empty_columns`, CR-036 (i)). Its `rows` is the forwarded row count, so
    # an entry here means EVERY row it went forward with had that cell blank.
    empty = (payload.get("mapping_spec") or {}).get("empty_columns") or []
    by_target = {entry["target"]: entry for entry in empty}
    assert "unit_ref" in by_target, (
        "the panel no longer reports the blank unit column — this test is "
        "pointed at the wrong surface and proves nothing"
    )
    assert by_target["unit_ref"]["rows"] == counts["checked"] == 20
    assert counts["clean"] < counts["checked"], (
        "a column the panel reports blank in EVERY row left EVERY row "
        "'no remarks at all' — DEF-1079, the two surfaces disagreeing again"
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-1075 — THE 500 WAS A GUNICORN WORKER TIMEOUT, AND THIS IS ITS GATE
# ══════════════════════════════════════════════════════════════════════════
#
# The Product Owner pulled the deployed traceback and it ends
#
#     File ".../gunicorn/workers/base.py", line 199, in handle_abort
#         sys.exit(1)
#     SystemExit: 1
#     [INFO] Worker exiting (pid: 2105)
#
# `handle_abort` is gunicorn's SIGABRT handler; the arbiter sends SIGABRT to a
# worker past `--timeout` (`GUNICORN_TIMEOUT:-60`). **There is no exception.**
# The request was still running at sixty seconds, was killed inside the
# transaction, and Postgres rolled it back — which is why the screen said
# "Nothing was saved" and meant it.
#
# ⛔ **AND THIS IS WHY EVERY TEST ABOVE PASSES OVER A BUG THAT KILLS
# PRODUCTION: THE BUG IS LATENCY-SHAPED AND A TEST HARNESS HAS NO LATENCY.**
# `ensure_reference_catalogs()` issued 32 `get_or_create` calls EVERY time it
# ran, and it ran at the top of `stage_by_code`, `type_by_code` AND
# `_flat_catalog_row` — three of which one asset creation makes:
#
#     32 × 3 = 96 queries per row · × 20 rows = 1,920 round trips
#     at 0.2 ms (this harness) → 0.4 s, invisible
#     at 15–20 ms (a remote DB) → 29–38 s, before one asset is written
#
# **So the check has to count QUERIES, not seconds.** A count assertion is the
# only kind that can see this class at zero latency, and it is the gate that
# catches the next one.


def test_def1075__the_commit_is_O_of_rows_not_rows_times_catalogue(ottumwa, vijay):
    """The load's query count grows with the ROWS, not with rows × catalogue.

    ⚠ **THE BOUND IS COMPUTED FROM THE SEED LISTS, NEVER TYPED AS A NUMBER, AND
    THAT IS THE WHOLE DESIGN OF THIS CHECK.** A hand-written budget like
    `< 40 per row` fails for benign reasons — one more `select_related`, one
    more audit row — and a check that goes red for a benign reason is a check
    that gets a `noqa` instead of a fix. So the ceiling is the DEFECT'S OWN
    ARITHMETIC, read live out of `apps.assets.services`: one un-memoised
    `ensure_reference_catalogs()` issues `len(SEED_ASSET_TYPES) +
    len(SEED_LIFECYCLE_STAGES) + len(SEED_METER_TYPES) + len(SEED_READ_METHODS)`
    queries — **32 today** — and one asset creation makes THREE of those calls
    (`type_by_code`, `_flat_catalog_row`, `stage_by_code`), so the regression
    this guards costs **96 per row** on its own, before a single asset, audit
    row or RLS check is paid for. If the seed lists grow, the ceiling grows
    with them and this test keeps meaning the same thing.

    **This is a REGRESSION guard, not a performance budget.** It says only
    *"the catalogue is not being re-seeded per row"*, which is the exact fault
    that made the Product Owner's twenty-row import exceed sixty seconds.

    ⚠ **AND IT MEASURES THE COMMIT, NOT THE REHEARSAL.** DEF-1080's own
    escape_reason is that the dry run and the commit share a predicate but not
    a code path; a count taken around `dry_run` would have proved nothing about
    the stage that actually died.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from apps.assets import services as assets_services

    reseed_cost = sum(
        len(seeds)
        for seeds in (
            assets_services.SEED_ASSET_TYPES,
            assets_services.SEED_LIFECYCLE_STAGES,
            assets_services.SEED_METER_TYPES,
            assets_services.SEED_READ_METHODS,
        )
    )
    #: `type_by_code` · `_flat_catalog_row` · `stage_by_code` — the three call
    #: sites one asset creation reaches.
    per_row_ceiling = reseed_cost * 3

    with tenant_ctx(ottumwa):
        run_id = _validated(vijay, po_meters_csv())
        with CaptureQueriesContext(connection) as captured:
            receipt = import_runs.load(
                vijay, run_id, {"write_mode": "insert", "create_rollback_point": True}
            )
    assert receipt["receipt"]["loaded"] == 20
    per_row = len(captured) / 20
    assert per_row < per_row_ceiling, (
        f"the commit issued {len(captured)} queries for 20 rows ({per_row:.1f} per row), "
        f"at or above the {per_row_ceiling} per row a per-row catalogue re-seed costs "
        f"({reseed_cost} seed rows x 3 call sites). That is the DEF-1075 shape. At 0.2 ms "
        "a round trip it is invisible in this harness; at 15 ms it is a gunicorn worker "
        "timeout, which is what the Product Owner saw."
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-1549 — AND THE GUARD ABOVE PASSED ALL THE WAY THROUGH THE SECOND OUTAGE
# ══════════════════════════════════════════════════════════════════════════
#
# ⛔ **READ THIS BEFORE TRUSTING ANY QUERY-COUNT CHECK IN THIS REPO.** The guard
# above is well built — the ceiling is computed live, it measures the COMMIT and
# not the rehearsal, and it goes red on the defect it was written for. It also
# reported PASS while the Product Owner's import was dying, twice, of a bug of
# exactly the class it exists to catch. Two reasons, and both are about what a
# check is BLIND to rather than what it asserts:
#
#   1. **ITS CEILING IS THE OLD DEFECT'S ARITHMETIC.** 96 queries per row is the
#      cost of the DEF-1075 catalogue re-seed. DEF-1549 cost ~55 per row on this
#      fixture — a catastrophe in production, comfortably under a ceiling drawn
#      around a different mechanism. A bound is only as good as the widest thing
#      it lets through.
#
#   2. **THE FIXTURE MULTIPLIED THE EXPLOSION BY ZERO.** The per-row cost was
#      `~10 services x (2 queries per SERVICE POINT)`, and Ottumwa Water Works
#      has no units, no accounts and no service points — so P was 0, the
#      quadratic term vanished, and the harness measured the one tenant shape in
#      which this defect is invisible. Every tenant in this suite is empty.
#
# Measured on this harness before the fix: `service_default_uom("water")` cost
# **41 queries** — identical to `services_overview()`, because it WAS that read
# — and the twenty-row commit cost **1,092**. With twelve service points on file
# the same commit costs thousands.
#
# **So the check below is DIFFERENTIAL, not a budget.** It loads the PO's file
# on a bare tenant, plants an estate, loads a second file, and asserts the two
# cost the same. That states the defect exactly — *does the customer base
# multiply into the per-row cost?* — and it cannot be defeated by a ceiling
# drawn around the wrong mechanism, because there is no ceiling in it.


def _renumbered(content: str) -> str:
    """The same twenty rows under different numbers, so a SECOND load can run on
    the same tenant without tripping the BR-AST-033 duplicate hard block. The
    numbers stay BARE-NUMERIC, which is the shape DEF-1080 is about."""
    lines = content.split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        if not line:
            out.append(line)
            continue
        cells = line.split(",")
        cells[0] = f"7{cells[0]}"  # a prefix digit — still bare-numeric
        out.append(",".join(cells))
    return "\n".join(out)


def test_def1549__the_commit_does_not_pay_for_the_tenants_customer_base(ottumwa, vijay):
    """**THE HEADLINE CHECK: an import row must cost the same on a tenant with
    customers as on a tenant without any.**

    `_create_asset_inner` called `seams.service_default_uom(service)` per row;
    that walked `service_catalog()` → `tenancy.services_overview()` — the S8
    SCREEN read — which calls `customers.active_account_count` for EVERY active
    service, which issued two queries per service point. So the per-row cost
    was `rows x services x points`, and the only thing hiding it was a fixture
    with no points.

    ⚠ **NO CEILING, ON PURPOSE.** Both numbers are measured in this test, on the
    same tenant, minutes apart; the assertion is that the estate did not enter
    the per-row cost. A future change that makes the screen read cheaper or the
    catalogue bigger moves both sides together and this keeps meaning the same
    thing — which is the failure mode the guard above suffered.

    **RED before the fix**, and not marginally: the second load cost thousands
    of queries more than the first for the same twenty rows.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from apps.tenancy import selectors as tenancy_selectors

    from tests.test_def1549_service_reads_are_not_screen_reads import plant_estate

    with tenant_ctx(ottumwa):
        bare_run = _validated(vijay, po_meters_csv())
        with CaptureQueriesContext(connection) as bare:
            first = import_runs.load(
                vijay, bare_run, {"write_mode": "insert", "create_rollback_point": True}
            )

        points = plant_estate(ottumwa)

        with CaptureQueriesContext(connection) as screen:
            tenancy_selectors.services_overview()

        estate_run = _validated(vijay, _renumbered(po_meters_csv()))
        with CaptureQueriesContext(connection) as with_estate:
            second = import_runs.load(
                vijay, estate_run, {"write_mode": "insert", "create_rollback_point": True}
            )

    assert first["receipt"]["loaded"] == 20 and second["receipt"]["loaded"] == 20
    assert points >= 8, "the estate must be big enough for a per-point cost to be visible"

    per_row_growth = (len(with_estate) - len(bare)) / 20
    assert per_row_growth < 2, (
        f"the same twenty rows cost {len(bare)} queries on a tenant with no customers and "
        f"{len(with_estate)} on the same tenant with {points} service points on file — "
        f"{per_row_growth:.1f} extra queries PER ROW, bought by the customer base alone. That "
        "is DEF-1549: a per-row lookup reaching through the S8 screen read, which counts active "
        "accounts for every service, two queries per service point. It is invisible at 0.2 ms a "
        "round trip and a gunicorn WORKER TIMEOUT at 15 ms, which is what the Product Owner saw "
        "twice on 2026-08-27."
    )

    #: The TOTAL bound the same measurement buys for free, stated as the
    #: relationship a person can hold in their head: writing one meter must cost
    #: less than drawing the whole settings screen it used to walk.
    per_row = len(with_estate) / 20
    assert per_row < len(screen), (
        f"one import row cost {per_row:.1f} queries against a services_overview() of "
        f"{len(screen)} on the same tenant. Before DEF-1549 those numbers were the same, "
        "because the row WAS the screen read."
    )

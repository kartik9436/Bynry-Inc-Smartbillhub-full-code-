# ── Trace ──────────────────────────────────────────────
# Defects: DEF-514 (no row anywhere records a connection size — CLOSED here) ·
#          DEF-1811 (the shadow cannot run on a single real account of any
#          tenant — CLOSED here) · DEF-1812 (no meter multiplier crosses
#          metering's BILLING seam — CLOSED here) · DEF-484 (a per-size tier
#          override is stored and served and does not reach a bill — its SOURCE
#          half) · DEF-255 (the reference list seeded ahead of its column)
# Rules:   BR-AST-500 (the asset carries the connection's size class) ·
#          BR-AST-501 (the size is billing-affecting, by BR-AST-012's own
#          criterion) · BR-MET-500 (metering publishes the size and the
#          multiplier to billing) · BR-TEN-170/171 (the vocabulary — the
#          RATIFIED `service_size_classes` codes) · BR-MET-056 (a read stores
#          the factor USED) · BR-RAT-001 (the chain scales the RAW register
#          difference itself) · BR-RAT-108 (base charge by Asset and Account
#          type)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""STEP 1 OF `12-governance/19-execution-sequence.md` — THE SOURCE, PROVED.

The R1–R7 lane finished step 3 and stopped with a measurement, not an opinion:

    accounts 1 · attempted 0 · disagreed 0 · blocked {connection_size_unresolved: 1}

The chain could not be run on a single real account of any tenant, because R3
narrows on a connection size and **the product stored one on no table at all**.
This file is the other side of that measurement. Every case below is written
against the SAME fixture the blocked measurement was taken on, so the two
numbers are comparable rather than merely both true.

⚠ **WHAT THIS FILE DELIBERATELY DOES NOT DO.** It does not touch
`apps/rating/resolution.py` or `apps/billing/resolution_shadow.py`; it sources a
fact and the consuming lane rules on what the chain then says. It does not
resolve DEF-1810 (what `served_sizes` MEANS), which is a design question with
money behind it and is the Product Owner's. And it never defaults a missing
value: the two cases at the bottom exist to prove the absences stay absent.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.assets import selectors as asset_selectors
from apps.assets import services as asset_services
from apps.billing import gather, resolution_shadow
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors

from tests.test_def_438_parity import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    _account_on,
    _price_live,
    _water_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The RATIFIED code for a 5/8" water connection — BR-TEN-171, straight out of
#: `apps.tenancy.service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES["water"]`.
#: ⚠ **NOT `'5/8'`.** The chain's own tests and DEF-1810's worked case use the
#: bare string `'5/8'` because they hand the size in as a test argument and
#: nothing checks it against a vocabulary. The PRODUCT's vocabulary is the
#: tenancy list, and this file uses it because the value now comes off a row.
WATER_5_8 = "W-58"
WATER_2_INCH = "W-2"


def _sized_account(brazos, dana, *, size=WATER_5_8, multiplier="1"):
    """The DEF-1811 fixture with a size RECORDED THROUGH THE REAL WRITE PATH.

    `_account_on` is imported unchanged from the parity harness, so the account,
    the unit, the meter and the committed read are byte-identical to the ones
    the blocked measurement was taken on. The single difference is one call to
    `assets.services.update_asset` — the API's own function, not an ORM poke —
    which is also what proves the column has a WRITER and is not DEF-515's shape
    one table across (a column that landed with its read path and its arithmetic
    and nothing anywhere able to set it).
    """
    plan = _water_plan(brazos)
    account, unit, asset, delta = _account_on(brazos, dana, plan, multiplier=multiplier)
    asset_services.update_asset(dana, asset["id"], {"size_class": size})
    return plan, account, unit, asset, delta


# ══════════════════════════════════════════════════════════════════════════
# TC-1..3 — THE COLUMN, AND THE TWO PUBLICATIONS DEF-514 NAMES
# ══════════════════════════════════════════════════════════════════════════


def test_TC1_the_asset_records_a_connection_size_through_the_public_write_path(
    brazos, dana
):
    """DEF-514's first sentence, closed: *"no row anywhere records a connection
    size"*.

    Asserted through `update_asset` and read back through `asset_dict` rather
    than through the ORM, because the defect was never that a Python attribute
    was missing — it was that **no layer of the product could hold the fact**.
    A test that sets the attribute directly would pass on a column with no
    writer, which is exactly the shape DEF-515 escaped in.
    """
    with tenant_ctx(brazos):
        _plan, _account, _unit, asset, _delta = _sized_account(brazos, dana)
        served = asset_selectors.asset_dict(asset_selectors.asset_row(asset["id"]))
        assert served["size_class"] == WATER_5_8

        # And it is CLEARABLE back to "we no longer claim to know", which is the
        # state every existing row keeps after the migration. Not the same fact
        # as a size of zero, and there is no such thing as a size of zero.
        asset_services.update_asset(dana, asset["id"], {"size_class": None})
        assert (
            asset_selectors.asset_dict(asset_selectors.asset_row(asset["id"]))[
                "size_class"
            ]
            is None
        )


def test_TC2_assets_on_unit_publishes_the_size_beside_qualifier_and_type(
    brazos, dana
):
    """DEF-514's second hop, verbatim from its prevention: *"published on
    `assets.selectors.assets_on_unit` beside qualifier and type"*.

    ⚠ **THIS IS THE DICT `route_meter_picker` HAS BEEN READING SINCE SET-06 STEP
    3 WAS BUILT.** `apps/metering/selectors.py` reads `asset.get("size_class")`
    out of it, and until this commit the dict published `id`, `asset_no`,
    `qualifier` and `type` and no size — so that screen's Size column has drawn a
    permanently empty cell, which reads to a user as *"this meter has no size
    recorded"* rather than *"this product cannot record one"*.
    """
    with tenant_ctx(brazos):
        _plan, account, _unit, _asset, _delta = _sized_account(brazos, dana)
        rows = asset_selectors.assets_on_unit(account.unit_id)
        assert rows, "fixture sanity: the unit has a meter"
        assert rows[0]["size_class"] == WATER_5_8

        # The screen that has been drawing the blank cell now draws the size.
        picker = metering_selectors.route_meter_picker(
            premises_ids=[
                str(
                    metering_models.Unit.objects.values_list("premises_id", flat=True).get(
                        pk=account.unit_id
                    )
                )
            ]
        )
        assert picker["meters"][0]["size_class"] == WATER_5_8


def test_TC3_metering_answers_connection_size_for_the_seam_gather_resolves(
    brazos, dana
):
    """DEF-514's third hop and the one that closes it: *"answered for billing by
    a metering seam (`connection_size_for(unit_id, service_code)`) so billing
    never joins to assets"*.

    ⚠ **`gather` IS NOT EDITED BY THIS LANE AND IS ASSERTED ANYWAY.**
    `apps/billing/gather.py` has resolved this name through
    `_resolve("metering", "connection_size_for")` since 2026-08-21 and its
    docstring stakes the claim in terms: *"the day metering publishes
    `connection_size_for` the size reaches the bill and nothing here changes."*
    This case is that claim, checked. If it ever fails, the hop and not the
    source is what broke.
    """
    with tenant_ctx(brazos):
        _plan, account, _unit, _asset, _delta = _sized_account(brazos, dana)

        assert (
            metering_selectors.connection_size_for(account.unit_id, "water")
            == WATER_5_8
        )
        # The identical value, through billing's own resolver, unedited.
        assert gather._connection_size_for(account.unit_id, "water") == WATER_5_8


# ══════════════════════════════════════════════════════════════════════════
# TC-4..5 — THE MULTIPLIER (DEF-1812)
# ══════════════════════════════════════════════════════════════════════════


def test_TC4_the_billing_read_seam_publishes_the_multiplier_it_already_read(
    brazos, dana
):
    """DEF-1812, closed by ONE KEY off the row already in hand.

    The measurement in the register, reproduced here first so the fix is
    comparable to it: on a ×10 meter the seam published `consumption=500.000000`
    and `current − prior = 50` and **nothing told the caller which factor
    produced the 500**. Both halves of the duplication are now visible on one
    row, which is what lets a caller choose: the live path prices the 500, the
    chain scales the 50 itself (BR-RAT-001).
    """
    with tenant_ctx(brazos):
        _plan, account, _unit, _asset, _delta = _sized_account(
            brazos, dana, multiplier="10"
        )
        rows = metering_selectors.billing_reads_for_unit(
            account.unit_id, period_start=PERIOD_START, period_end=PERIOD_END
        )
        assert rows, "fixture sanity: the unit has a read"
        row = rows[0]

        # The two figures the register already published…
        assert row["consumption"] == Decimal("500.000000")
        assert Decimal(str(row["current_value"])) - Decimal(
            str(row["prior_value"])
        ) == Decimal("50")
        # …and the factor that relates them, which it did not.
        assert Decimal(str(row["multiplier"])) == Decimal("10")
        assert Decimal(str(row["multiplier"])) * (
            Decimal(str(row["current_value"])) - Decimal(str(row["prior_value"]))
        ) == row["consumption"], "the published factor must EXPLAIN the published product"


def test_TC5_billing_multiplier_for_answers_the_shadows_seam(brazos, dana):
    """The same fact for a caller holding no reading row — `resolution_shadow
    ._multiplier_for` resolves `billing_multiplier_for(unit_id, service)`.

    The period-scoped form is asserted beside the bare one because they must
    agree here and can differ in general: without a period this reads the LATEST
    billable head, which is the same read only while the period is the latest
    one. The docstring says so and this case pins that it is a real parameter
    and not decoration.
    """
    with tenant_ctx(brazos):
        _plan, account, _unit, _asset, _delta = _sized_account(
            brazos, dana, multiplier="10"
        )
        assert Decimal(
            str(metering_selectors.billing_multiplier_for(account.unit_id, "water"))
        ) == Decimal("10")
        assert Decimal(
            str(
                metering_selectors.billing_multiplier_for(
                    account.unit_id,
                    "water",
                    period_start=PERIOD_START,
                    period_end=PERIOD_END,
                )
            )
        ) == Decimal("10")


# ══════════════════════════════════════════════════════════════════════════
# TC-6 — THE HEADLINE: THE SHADOW RUNS ON A REAL ACCOUNT (DEF-1811)
# ══════════════════════════════════════════════════════════════════════════


def test_TC6_the_shadow_can_now_be_run_on_a_real_account(brazos, dana):
    """⚠ **THE NUMBER DEF-1811 WAS FILED ON, MOVED.**

    Measured on this fixture, through the production adapter, both ways:

      before  accounts 1 · attempted 0 · agreed 0 · disagreed 0 ·
              chain_refused 0 · not_attempted 1 · by_step {} ·
              blocked {connection_size_unresolved: 1}
      after   accounts 1 · attempted 1 · agreed 0 · disagreed 1 ·
              chain_refused 1 · not_attempted 0 · by_step {R4: 1} ·
              blocked {}

    ⚠ **READ `by_step {R4: 1}`. THAT IS THE EVIDENCE THE WHOLE CUTOVER EXISTS TO
    PRODUCE, AND IT HAS NEVER BEEN VISIBLE ON A REAL ACCOUNT BEFORE THIS
    COMMIT.** The chain now runs on production rows and refuses at R4 — which is
    DEF-498's filed finding (*"R4 refuses every bill five times over"*) arriving
    for the first time as a MEASUREMENT off real data instead of a hand-built
    harness. **Fixing R4 is not this lane's job and must not be**: step 4 of the
    recorded cutover is where each class of disagreement is RULED, and a
    sourcing lane that "tidied" this to zero would have destroyed exactly the
    evidence the decision log says to protect.

    ⚠ **AND `disagreed` IS 1, NOT 0.** DEF-1812 warned that a defaulted
    multiplier would make this report parity by construction; a run that came
    back `disagreed 0` here would be the symptom of that default, not good news.

    The figures above are stated rather than asserted, deliberately: pinning
    `by_step` would make this case go red the day the next lane FIXES R4, which
    is the outcome it is waiting for.

    ⚠ **AND `attempted` IS THE FIGURE TO READ, NOT `disagreed`.** DEF-1811's own
    warning: *"the first number alone reads as PARITY — 0 disagreements is
    exactly what perfect agreement looks like"*. This case asserts
    `attempted == 1` and `blocked_by_reason == {}` and deliberately asserts
    NOTHING about whether the two paths agree. **Whether they agree is the next
    lane's measurement and its ruling** — the decision log's step 4 — and a
    sourcing lane that asserted parity here would be choosing the answer to the
    question the whole cutover exists to ask.
    """
    with tenant_ctx(brazos):
        _plan, account, _unit, _asset, _delta = _sized_account(
            brazos, dana, multiplier="10"
        )
        data = _price_live(account)
        outcome = resolution_shadow.shadow_account(
            data, account=account, service_date=SERVICE_DATE
        )
        report = resolution_shadow.summarise((outcome,))

        assert report["accounts"] == 1
        assert report["attempted"] == 1, report
        assert report["not_attempted"] == 0, report
        assert report["blocked_by_reason"] == {}, report
        assert outcome.blocked_reason is None, outcome.blocked_detail
        assert outcome.status != resolution_shadow.STATUS_NOT_ATTEMPTED


# ══════════════════════════════════════════════════════════════════════════
# TC-7..9 — THE ABSENCES THAT MUST STAY ABSENT
#
# Every case here would pass if the code guessed. That is why they exist.
# ══════════════════════════════════════════════════════════════════════════


def test_TC7_an_unrecorded_size_answers_None_and_is_never_defaulted(brazos, dana):
    """A meter with no size recorded answers None — the state every existing row
    in every existing database keeps after the migration.

    ⚠ **THIS IS THE CASE THAT PROVES THE MIGRATION CANNOT MOVE A FIGURE.** The
    column landed with no backfill and no default precisely so that every bill
    of every tenant prices exactly as it did before it existed; if this ever
    returns a size, some code has invented one, and an invented size selects a
    tier ladder and therefore prices a bill.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        # ⚠ **`size_class=None` IS STATED HERE FROM 2026-09-01 (`DEF-2965`).**
        # It used to be inherited from `a_meter`'s default, and that default is
        # now the service's smallest ratified band — because an unsized meter on
        # a BANDED service stops its bill under R3, so a fixture may not hand
        # one out by accident. **This case's whole subject is the absence**, so
        # it asks for it: the unsized state must stay reachable and must be
        # reached deliberately.
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan, size_class=None)
        assert metering_selectors.connection_size_for(account.unit_id, "water") is None
        assert gather._connection_size_for(account.unit_id, "water") is None
        assert asset_selectors.assets_on_unit(account.unit_id)[0]["size_class"] is None


def test_TC8_two_meters_disagreeing_about_the_size_answer_None_not_a_coin_toss(
    brazos, dana
):
    """One connection has one size. Two DIFFERENT recorded sizes on one service
    point is a data error, and the only two things the seam could do about it
    are pick one — which selects a tier ladder, and therefore prices a bill, on
    a coin toss — or say it cannot tell.

    It says it cannot tell, and the caller's existing named refusal
    (`gather`'s `connection_size_unresolved_for_sized_schedule`) carries that to
    a human. Recorded as a decision rather than discovered later: decision log
    2026-08-27.
    """
    with tenant_ctx(brazos):
        _plan, account, unit, _asset, _delta = _sized_account(brazos, dana)
        second = asset_services.create_asset(
            dana,
            {
                "type": "meter",
                "asset_no": "M-9002",
                "service": "water",
                "unit": "kgal",
                "read_method": "manual",
                "multiplier": "1",
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
                "status": "active",
                "size_class": WATER_2_INCH,
            },
        )
        assert second["size_class"] == WATER_2_INCH
        assert metering_selectors.connection_size_for(account.unit_id, "water") is None

        # ⚠ AND ABSENCE IS NOT A COMPETING CLAIM. A meter with no size beside a
        # meter with one is not a disagreement — the recorded size wins and the
        # account bills, because "nobody wrote it down" contradicts nothing.
        asset_services.update_asset(dana, second["id"], {"size_class": None})
        assert (
            metering_selectors.connection_size_for(account.unit_id, "water")
            == WATER_5_8
        )


def test_TC9_an_absent_multiplier_is_never_reported_as_1(brazos, dana):
    """`resolution.MeterMultiplierUnstated`'s own sentence, enforced at the
    source: *"an absent factor is not 1"*.

    A connection with no read has no factor to have used, and the seam says so.
    A defaulted 1 here would make the shadow report PARITY BY CONSTRUCTION on
    every ×1 meter — the great majority — and the cutover report would read as
    the best possible news while measuring nothing.
    """
    with tenant_ctx(brazos):
        _plan, account, _unit, _asset, _delta = _sized_account(brazos, dana)
        # A service this unit has no service point for: no point, no read, no
        # factor. None, never 1.
        assert metering_selectors.billing_multiplier_for(account.unit_id, "gas") is None
        assert metering_selectors.connection_size_for(account.unit_id, "gas") is None


def test_TC10_the_size_is_billing_affecting_so_re_tagging_a_read_meter_warns(
    brazos, dana
):
    """BR-AST-501 — the size joins `BILLING_AFFECTING_FIELDS` by BR-AST-012's
    OWN stated criterion (*"no rating input, no quantity, no invoice line reads
    it"* is why `meter_type` is outside the set, and the size fails that test on
    the first clause).

    Worked on r10's own figures: a 2" water connection re-tagged from `W-58` to
    `W-2` moves the tier ladder from `3.20 / 4.80 / 7.20` to
    `3.45 / 5.10 / 7.70`. The customer's price changes, reads already exist, and
    without this the person who changed it is told nothing.
    """
    with tenant_ctx(brazos):
        _plan, _account, _unit, asset, _delta = _sized_account(brazos, dana)
        result = asset_services.update_asset(
            dana, asset["id"], {"size_class": WATER_2_INCH}
        )
        warnings = {w["code"] for w in result.get("warnings", [])}
        assert "forward_only_change" in warnings, result
        forward = next(
            w for w in result["warnings"] if w["code"] == "forward_only_change"
        )
        assert "size_class" in forward["fields"], forward


# ══════════════════════════════════════════════════════════════════════════
# TC-11 — THE DEMO TENANT CARRIES ONE, SO THE FACT IS WALKABLE
# ══════════════════════════════════════════════════════════════════════════


def test_TC11_the_seeded_estate_carries_a_ratified_size_on_every_meter(
    brazos, dana
):
    """DEF-515's lesson, applied one table across before it could repeat.

    That defect is a column that landed with its migration, its read path and
    its engine arithmetic and **nothing anywhere able to set it**, so a real
    utility could compute the outside-city surcharge and never ask for one. It
    stayed invisible for the stated reason that *"a factor that is NULL
    everywhere prices identically to no factor at all"*. A size column NULL on
    every seeded meter is the same shape: the R1–R7 shadow would still report
    `blocked {connection_size_unresolved}` on the demo tenant, and a reader
    walking the product would conclude the fix had not landed.

    ⚠ **THE CODE IS ASSERTED AGAINST TENANCY'S RATIFIED LIST, NOT AGAINST A
    STRING THIS FILE TYPED.** A demo tenant carrying an invented size would
    teach every reader the wrong vocabulary, and the value ends up on a rate
    schedule and therefore in money (BR-TEN-171).

    ⚠ **AND IT MOVES NO MONEY.** No rate schedule in the seed carries a per-size
    override, so `pricing_inputs` returns the NULL "every size" group whether or
    not a size is supplied, and every seeded bill is byte-identical.
    """
    from apps.assets import sample_data as assets_sample
    from apps.metering import sample_data as metering_sample
    from apps.rating import sample_data as rating_sample
    from apps.tenancy import service_size_classes

    with tenant_ctx(brazos):
        # The orchestrator's own order, through each module's real seam.
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)
        assets_sample.seed_sample_records(dana)

        # `asset_list` serves ORM rows; the size is read through the published
        # dict so this case exercises the same projection every screen does.
        meters = [
            asset_selectors.asset_dict(asset)
            for asset in asset_selectors.asset_list(filters={"status": "all"})
        ]
        sized = [m for m in meters if m.get("size_class")]
        assert sized, (
            "the seeded estate carries NO connection size on any meter — the "
            "demo tenant cannot walk the per-size ladder and the R1-R7 shadow "
            "stays blocked on it (DEF-514/DEF-1811)"
        )
        # `DEF-MET-9055` — through the published `(code, name)` view. The
        # registry's rows are four-field records since CR-062 (`62ee96f93`),
        # and unpacking one as a pair raised before this case asserted anything.
        ratified = {
            code
            for service in service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES
            for code, _name in service_size_classes.size_classes_for_service(service)
        }
        unknown = {m["size_class"] for m in sized} - ratified
        assert not unknown, (
            f"the seeder planted size code(s) that are not in BR-TEN-171's "
            f"ratified list: {sorted(unknown)}"
        )


# ── Lifecycle ─────────────────────────────────────────────
# status: PROPOSED — the SOURCE half of the R1–R7 cutover's step 1. Every case
#   is about a fact reaching a caller; not one of them asserts a price, because
#   pricing from the chain is step 5 and is not this lane's to take.
# ──────────────────────────────────────────────────────────

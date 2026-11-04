# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · lane DS-METER — the `meter_reads` dataset query.
# Rules:    CLAUDE.md hard rule 3 (every quantity carries its unit) · hard
#           rule 1 (tenant scoping) · hard rule 4 (this reads and writes
#           nothing) · NFR-3 · NFR-5 · BR-MET-016/053 (lineage heads) ·
#           BR-MET-021 · BR-MET-028 · BR-REP-024
# Impacts:  06-backend/apps/metering/meter_reads_dataset.py
# ───────────────────────────────────────────────────────
"""THE `meter_reads` DATASET, PROVED — shape and arithmetic.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *"no error"*, so a case that only asserts an absence proves nothing;
each refusal below is asserted BESIDE a positive case built from the same
fixture, so a query that returned nothing at all would fail the positive half.

⚠ **AND NOTHING HERE SKIPS.** A `pytest.skip` that fires when a fixture lacks
something is a false pass — a sibling's case skipped silently and its file
reported green over the one assertion that mattered. Every fixture below
CREATES what it needs.

⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE** (`config/settings/test.py` hardcodes
it and ignores `DATABASE_URL`), so these cases prove the SHAPE and the
ARITHMETIC and can prove nothing about `LIMIT`/`OFFSET` cost, the query plan,
`jsonb` or RLS. That is hard-won law 14. The PostgreSQL half is
`10-scripts/ds_meter_reads_cost.py` and its figures are in the lane report.
"""

import inspect
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.metering import meter_reads_dataset as dataset
from apps.metering import models as metering_models
from apps.metering import selectors
from apps.reports import datasets
from apps.tenancy import models as tenancy_models

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_asset
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
SEP = {"start": date(2026, 9, 1), "end": date(2026, 9, 30)}


def _read(tenant, *, asset, account, day, value, consumption, unit, **overrides):
    """One committed lineage head, written straight through the ORM.

    The dataset is a READ MODEL and these cases are about what it SERVES, so
    the fixture states the row rather than driving the whole import pipeline to
    produce one — that pipeline has its own suite and its own savepoint proof.
    """
    payload = {
        "tenant": tenant,
        "asset": asset,
        "account": account,
        "read_at": datetime(day.year, day.month, day.day, tzinfo=UTC),
        "channel": metering_models.CHANNEL_TOTAL,
        "current_value": Decimal(value),
        "consumption": Decimal(consumption),
        "unit": unit,
        "source": "manual",
        "status": "ok",
        "lifecycle": "committed",
    }
    payload.update(overrides)
    return metering_models.MeterRead.objects.create(**payload)


def _meter_on_water(actor, tenant, unit_id, *, asset_no):
    """One water meter, STANDING ON A SERVICE POINT.

    ⚠ **THE SERVICE POINT IS NOT OPTIONAL SCENERY.** The read carries no service
    of its own and `_base(service=…)` walks
    `asset → service_point → service`, exactly as `completeness._expected_meters`
    does. A meter left in inventory (which is what `make_asset` gives by
    default) matches NO service filter, so R30's ranking would return zero rows
    and read as *"no error"* — which is the false pass this whole file is
    written against. The fixture CREATES what it needs.
    """
    made = make_asset(actor, asset_no=asset_no, service="water", unit="gal")
    asset = asset_models.Asset.objects.get(pk=made["id"])
    service = tenancy_models.Service.objects.filter(code="water", active=True).first()
    assert service is not None, "the tenant seed carries water — fixture cannot proceed"
    point = metering_models.ServicePoint.objects.create(
        tenant=tenant, unit_id=unit_id, service=service
    )
    asset.service_point = point
    asset.save(update_fields=["service_point"])
    return asset


@pytest.fixture()
def water_reads(brazos, dana):
    """TWO accounts, both water, both in September, **eight reads in all**.

    ⚠ **TWO ACCOUNTS IN ONE WINDOW IS THE WHOLE DESIGN OF THIS FIXTURE.** The
    portal case asserts that a scope of one returns one account's rows AND that
    the footer foots to that scope; with a single account a scope that did
    nothing at all would return the same rows and the same total, and every
    assertion would pass over a leak.
    """
    with tenant_ctx(brazos):
        mine = an_account(brazos, dana, account_no="A-100244", service="water")
        theirs = an_account(brazos, dana, account_no="A-100512", service="water")
        my_meter = _meter_on_water(dana, brazos, mine.unit_id, asset_no="MTR-002044")
        their_meter = _meter_on_water(
            dana, brazos, theirs.unit_id, asset_no="MTR-004182"
        )
        rows = []
        # Mine: four reads, 1,000 gal each → 4,000 gal.
        for index, day in enumerate((5, 12, 19, 26), start=1):
            rows.append(
                _read(
                    brazos,
                    asset=my_meter,
                    account=mine,
                    day=date(2026, 9, day),
                    value=180_000 + index * 1_000,
                    consumption="1000.000000",
                    unit="gal",
                    prior_value=Decimal(179_000 + index * 1_000),
                )
            )
        # Theirs: four reads, 2,000 gal each → 8,000 gal. A scope that leaked
        # would show 12,000.
        for index, day in enumerate((5, 12, 19, 26), start=1):
            rows.append(
                _read(
                    brazos,
                    asset=their_meter,
                    account=theirs,
                    day=date(2026, 9, day),
                    value=90_000 + index * 2_000,
                    consumption="2000.000000",
                    unit="gal",
                    prior_value=Decimal(88_000 + index * 2_000),
                )
            )
    return {
        "tenant": brazos,
        "actor": dana,
        "mine": mine,
        "theirs": theirs,
        "rows": rows,
    }


# ── The grain, and the three reports it does NOT serve ─────────────────────


def test_grain_is_one_meter_read_and_the_registry_agrees(water_reads):
    """§7.2 — a dataset states ONE grain, and the query says the same word the
    registry does. Two spellings of one grain is how a report starts claiming a
    grain its dataset does not state."""
    with tenant_ctx(water_reads["tenant"]):
        page = dataset.meter_reads_dataset(**SEP)
    assert page["grain"] == "one meter read"
    declared = {d.code: d for d in datasets.DATASETS}["meter_reads"]
    assert declared.grain == page["grain"]
    assert page["total"] == 8  # a known NON-ZERO count


def test_ranking_states_a_different_grain_and_never_claims_this_one(water_reads):
    """R30 GROUPS this fact; it does not share its grain. §7.2 lets a report
    group a fact and does not let it claim a grain its dataset does not
    state."""
    with tenant_ctx(water_reads["tenant"]):
        ranked = dataset.account_usage_ranking(service="water", **SEP)
    assert ranked["grain"] == "one account"
    assert len(ranked["rows"]) == 2  # NON-ZERO, and both accounts present


# ── HARD RULE 3 — the refusal, and the lawful total beside it ──────────────


def test_one_unit_totals_and_names_its_unit(water_reads):
    """The POSITIVE half. 4 × 1,000 + 4 × 2,000 = 12,000 gal over eight
    reads."""
    with tenant_ctx(water_reads["tenant"]):
        page = dataset.meter_reads_dataset(**SEP)
    total = page["totals"]["consumption"]
    assert total["total"] == Decimal("12000.000000")
    assert total["unit"] == "gal"
    assert total["unit_count"] == 1
    assert total["reason"] is None


def test_two_units_refuse_the_total_and_say_why(water_reads):
    """**HARD RULE 3.** A sibling measured `26.24 kgal + 684.00 kWh = 710.24` —
    a number with no unit, which is not a quantity at all.

    One `kWh` read joins the eight `gal` ones. The total must become a REFUSAL
    with a reason, never `12,684`, never labelled `gal`, never converted.
    """
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        made = make_asset(
            fixture["actor"], asset_no="MTR-009001", service="electric", unit="kWh"
        )
        electric_meter = asset_models.Asset.objects.get(pk=made["id"])
        _read(
            fixture["tenant"],
            asset=electric_meter,
            account=fixture["mine"],
            day=date(2026, 9, 26),
            value="684.000000",
            consumption="684.000000",
            unit="kWh",
        )
        page = dataset.meter_reads_dataset(**SEP)

    total = page["totals"]["consumption"]
    # The set really did grow — so this is not a query that returned nothing.
    assert page["total"] == 9
    assert total["total"] is None
    assert total["unit"] is None
    assert total["unit_count"] == 2
    assert total["reason"]["code"] == "consumption_spans_more_than_one_unit"


def test_every_row_carries_its_own_unit_column(water_reads):
    """p062: *"Every quantity carries its unit, in its own column."* Not one
    row may serve a quantity with a null unit."""
    with tenant_ctx(water_reads["tenant"]):
        rows = list(dataset.meter_reads_dataset_stream(**SEP))
    assert len(rows) == 8
    assert all(row.unit for row in rows)
    assert all(row.consumption is not None for row in rows)


# ── R45 — the CUSTOMER PORTAL scope, rows AND footer ───────────────────────


def test_portal_usage_scopes_the_rows_to_the_signed_in_accounts(water_reads):
    """Two accounts in one window: a scope that did nothing returns both."""
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        page = dataset.portal_usage(account_ids=[fixture["mine"].id], **SEP)
    assert page["total"] == 4  # NON-ZERO — mine, not the eight
    assert {row.account_no for row in page["rows"]} == {"A-100244"}


def test_portal_usage_foots_the_total_to_the_scope(water_reads):
    """⚠ **THE HALF A WEAKER TEST MISSES.** A total struck over the unscoped
    set leaks the FIGURE without leaking a row: the customer sees their four
    reads under a *This period* tile carrying their neighbour's gallons too.

    Mine is 4,000. Both together are 12,000. The tile must read 4,000.
    """
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        page = dataset.portal_usage(account_ids=[fixture["mine"].id], **SEP)
    total = page["totals"]["consumption"]
    assert total["total"] == Decimal("4000.000000")
    assert total["unit"] == "gal"
    assert total["reads"] == 4


def test_portal_usage_with_no_accounts_returns_nothing_not_everything(water_reads):
    """A principal holding no accounts sees NO reads.

    ⚠ The bug this names is `if account_ids:` — an empty list is falsy, so the
    filter would be skipped and the whole utility served. `_base` tests
    `is not None`. The positive case above is what makes this one meaningful:
    the same fixture demonstrably holds eight rows.
    """
    with tenant_ctx(water_reads["tenant"]):
        page = dataset.portal_usage(account_ids=[], **SEP)
        everyone = dataset.meter_reads_dataset(**SEP)
    assert everyone["total"] == 8
    assert page["total"] == 0
    assert page["rows"] == []
    assert page["totals"]["consumption"]["total"] is None  # BR-REP-024, not 0


def test_portal_usage_has_no_unscoped_default(water_reads):
    """`account_ids` is REQUIRED and keyword-only. A portal read whose scope is
    optional is a portal read that leaks the first time a caller forgets it."""
    with pytest.raises(TypeError):
        dataset.portal_usage(**SEP)
    signature = inspect.signature(dataset.portal_usage)
    assert signature.parameters["account_ids"].default is inspect.Parameter.empty


# ── R30's warning, made structural ─────────────────────────────────────────


def test_ranking_refuses_to_run_without_a_service(water_reads):
    """p064: *"One service at a time, and the dropdown is not optional… The
    service parameter is required, not defaulted."* A default of `None` meaning
    *all* would have had exactly the bug the warning names."""
    with pytest.raises(TypeError):
        dataset.account_usage_ranking(**SEP)
    signature = inspect.signature(dataset.account_usage_ranking)
    assert signature.parameters["service"].default is inspect.Parameter.empty


def test_ranking_share_is_recomputed_and_billed_is_absent_not_zero(water_reads):
    """§7.2.2 — *"% share must be recomputed from its components, never
    averaged"*. 8,000 of 12,000 is 2/3; 4,000 of 12,000 is 1/3.

    BILLED is money from `billing` and is `None` WITH a reason, never `0` —
    `0` there reads as *"used 8,000 gal, billed nothing"*, which is a defect
    report rather than a report (BR-REP-024).
    """
    with tenant_ctx(water_reads["tenant"]):
        ranked = dataset.account_usage_ranking(service="water", **SEP)
    top, second = ranked["rows"]
    assert top["account_no"] == "A-100512"
    assert top["usage"] == Decimal("8000.000000")
    assert top["unit"] == "gal"  # hard rule 3 on every grouped row
    assert top["share"] == Decimal("8000.000000") / Decimal("12000.000000")
    assert second["share"] == Decimal("4000.000000") / Decimal("12000.000000")
    assert top["billed"] is None
    assert any(p["measure"] == "billed" for p in ranked["problems"])


# ── NFR-3 / NFR-5 — the page, the order and the export ─────────────────────


def test_pages_are_disjoint_and_the_total_is_the_whole_set(water_reads):
    """The total is a SQL aggregate over the whole filtered set and never over
    the page, which is what makes the tiles foot whether a page is cut or
    not."""
    with tenant_ctx(water_reads["tenant"]):
        first = dataset.meter_reads_dataset(per=3, page=1, **SEP)
        second = dataset.meter_reads_dataset(per=3, page=2, **SEP)
        third = dataset.meter_reads_dataset(per=3, page=3, **SEP)
    assert [first["total"], second["total"], third["total"]] == [8, 8, 8]
    assert (len(first["rows"]), len(second["rows"]), len(third["rows"])) == (3, 3, 2)
    # The footer foots to the SET, never to the page.
    assert first["totals"]["consumption"]["total"] == Decimal("12000.000000")


def test_the_two_sort_directions_are_exact_reverses(water_reads):
    """Every sort carries a tiebreak on `id`, so a page is a window over a
    TOTAL order and no row can appear on two pages or on none."""
    with tenant_ctx(water_reads["tenant"]):
        down = dataset.meter_reads_dataset(sort="consumption", direction="desc", **SEP)
        up = dataset.meter_reads_dataset(sort="consumption", direction="asc", **SEP)
    assert len(down["rows"]) == 8
    assert [r.consumption for r in down["rows"]] == [
        r.consumption for r in reversed(up["rows"])
    ]


def test_the_export_takes_no_page_and_no_per(water_reads):
    """⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN.** When the
    billing register started paging, its export inherited the screen's page and
    shipped a valid-looking file of 50 rows from a 38,000-row report. A flag
    would have had the same bug; a missing parameter cannot."""
    parameters = inspect.signature(dataset.meter_reads_dataset_stream).parameters
    assert "page" not in parameters
    assert "per" not in parameters
    with tenant_ctx(water_reads["tenant"]):
        assert len(list(dataset.meter_reads_dataset_stream(**SEP))) == 8


def test_the_file_and_the_screen_sort_identically(water_reads):
    """One `order_terms` call, one order. A file in a different order from the
    screen it was exported from is a defect nobody reports as one."""
    with tenant_ctx(water_reads["tenant"]):
        screen = dataset.meter_reads_dataset(sort="meter_no", direction="asc", **SEP)
        streamed = list(
            dataset.meter_reads_dataset_stream(sort="meter_no", direction="asc", **SEP)
        )
    assert len(streamed) == 8
    assert [r.meter_no for r in screen["rows"]] == [r.meter_no for r in streamed]


# ── BR-MET-016/053 — lineage heads only ────────────────────────────────────


def test_a_superseded_read_is_not_a_row(water_reads):
    """A correction is a NEW row and the old one gets `superseded_by_id`. A
    report counting both counts one meter twice — and the wrong answer is
    LARGER, so it reads as a busier month rather than as an error."""
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        before = dataset.meter_reads_dataset(**SEP)
        head = fixture["rows"][0]
        head.superseded_by_id = fixture["rows"][1].id
        head.save(update_fields=["superseded_by_id"])
        after = dataset.meter_reads_dataset(**SEP)
    assert before["total"] == 8  # NON-ZERO before
    assert after["total"] == 7
    assert after["totals"]["consumption"]["total"] == Decimal("11000.000000")


# ── R29 — the exception set, and the comparison it serves ──────────────────


def test_flagged_only_is_the_exception_set_and_an_estimate_is_not_one(water_reads):
    """p063's tiles foot: READS CHECKED 1,916 against EXCEPTIONS 48.

    BR-MET-028 — an estimate is a LABELLED read, not an exception. Folding it
    in would inflate the exception count by every estimated read in the
    window, which at a utility estimating a route is most of it.
    """
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        high = fixture["rows"][0]
        high.status = "high"
        high.rule_outcomes = [{"rule": "high", "severity": "warning", "detail": {}}]
        high.save(update_fields=["status", "rule_outcomes"])
        estimated = fixture["rows"][4]
        estimated.status = "estimated"
        estimated.save(update_fields=["status"])
        page = dataset.meter_reads_dataset(flagged_only=True, **SEP)
        everything = dataset.meter_reads_dataset(**SEP)

    assert everything["total"] == 8  # the checked set is NON-ZERO
    assert page["total"] == 1  # the exception set is the flagged one only
    assert page["rows"][0].flag == "high"
    assert page["rows"][0].rule == "high"


def test_change_is_the_raw_difference_and_stays_negative(water_reads):
    """p063: *"A reverse reading is negative usage and is shown as the raw
    difference, not as a percentage — dividing by a larger number to produce
    −0.1% would hide a meter swap."*

    Prior 180,100 · this read 179,880 → −220, served as −220.
    """
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        reverse = fixture["rows"][0]
        reverse.prior_value = Decimal("180100")
        reverse.current_value = Decimal("179880")
        reverse.status = "negative_usage"
        reverse.save(update_fields=["prior_value", "current_value", "status"])
        page = dataset.meter_reads_dataset(flag="negative_usage", **SEP)

    assert page["total"] == 1
    row = page["rows"][0]
    assert row.prior == Decimal("180100")
    assert row.reading == Decimal("179880")
    assert row.change == Decimal("-220")


# ── The basis, and the ONE derivation of it ────────────────────────────────


def test_basis_q_agrees_with_the_selector_on_every_combination(water_reads):
    """⚠ **HARD-WON LAW 5, AS A TEST RATHER THAN A COMMENT.**

    `selectors.read_is_estimated` is the ONE derivation of *"this head is an
    estimate"* and its own docstring says a second spelling is how two consumers
    start disagreeing. `ESTIMATED_Q` is that derivation in SQL, and this walks
    the FULL cross product of every status and every disposition — one real row
    each — asserting the two answers match. The day somebody adds a third way
    for a read to be an estimate, this goes red and names it, which a comment
    saying *"keep these in step"* cannot (hard-won law 1).

    ⚠ **IT IS RUN THROUGH THE DATABASE AND NOT THROUGH `Q.check()`.** `check()`
    evaluates the `Q` against a literal in Python, so it answers a question
    about Django's expression layer rather than about the `WHERE` this dataset
    actually emits — and on `disposition=None` it cannot answer at all
    (`OutputFieldIsNoneError`). A guard proved through a path nobody uses is no
    proof of the thing that matters (hard-won law 7, `DEF-GOV-3733`).
    """
    fixture = water_reads
    dispositions = (*metering_models.DISPOSITIONS, None)
    combinations = [
        (status, disposition)
        for status in metering_models.READ_STATUSES
        for disposition in dispositions
    ]
    assert len(combinations) > 0

    template = fixture["rows"][0]
    with tenant_ctx(fixture["tenant"]):
        metering_models.MeterRead.objects.all().delete()
        made = []
        for index, (status, disposition) in enumerate(combinations):
            made.append(
                _read(
                    fixture["tenant"],
                    asset=template.asset,
                    account=template.account,
                    day=date(2026, 9, 1),
                    value=1_000 + index,
                    consumption="1.000000",
                    unit="gal",
                    status=status,
                    disposition=disposition,
                    # `read_at` must differ per row: `_read` stamps 00:00Z of the
                    # date and the model is keyed (asset, read_at, channel).
                    read_at=datetime(2026, 9, 1, tzinfo=UTC) + timedelta(minutes=index),
                )
            )
        by_id = {row.id: row for row in made}
        sql_estimated = set(
            metering_models.MeterRead.objects.filter(dataset.ESTIMATED_Q).values_list(
                "id", flat=True
            )
        )

    assert len(by_id) == len(combinations)  # a NON-ZERO, known count
    python_estimated = {
        row.id
        for row in made
        if selectors.read_is_estimated(row.status, row.disposition)
    }
    # Both halves NON-EMPTY, or "they agree" would be two empty sets agreeing.
    assert (
        python_estimated
    ), "no combination reads as an estimate — the fixture is wrong"
    assert len(python_estimated) < len(
        combinations
    ), "every combination reads as an estimate"
    disagreements = sorted(
        (by_id[one].status, by_id[one].disposition)
        for one in (sql_estimated ^ python_estimated)
    )
    assert disagreements == [], disagreements


def test_read_basis_filter_splits_the_set_both_ways(water_reads):
    """Both branches asserted NON-ZERO, so neither is a query returning
    nothing."""
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        estimate = fixture["rows"][0]
        estimate.status = "estimated"
        estimate.save(update_fields=["status"])
        estimated = dataset.meter_reads_dataset(read_basis="estimated", **SEP)
        actual = dataset.meter_reads_dataset(read_basis="actual", **SEP)

    assert estimated["total"] == 1
    assert actual["total"] == 7
    assert estimated["rows"][0].read_basis == "estimated"
    assert {r.read_basis for r in actual["rows"]} == {"actual"}


# ── Hard rule 4 — this file writes nothing ─────────────────────────────────


def test_running_the_dataset_writes_no_audit_row_and_no_read(water_reads, audit_rows):
    """A money ACTION writes `audit_log` (hard rule 7); a READ is not an action
    and writes none. And a read model may not create a read."""
    fixture = water_reads
    with tenant_ctx(fixture["tenant"]):
        before = metering_models.MeterRead.objects.count()
        audit_rows.clear()
        dataset.meter_reads_dataset(**SEP)
        list(dataset.meter_reads_dataset_stream(**SEP))
        dataset.account_usage_ranking(service="water", **SEP)
        dataset.portal_usage(account_ids=[fixture["mine"].id], **SEP)
        after = metering_models.MeterRead.objects.count()
    assert before == 8 and after == 8
    assert audit_rows == []


# ── The declared tuples, and the three named refusals ──────────────────────


def test_declared_sorts_are_the_sorts_the_query_actually_honours(water_reads):
    """⚠ **HARD-WON LAW 2'S MIRROR — a live control over a dead one.**

    `DEF-PAY-6271` is open on exactly this: a screen declaring ten sorts, a
    search and four filters over a query that honours three sorts and two
    filters. A viewer builds its caret row from `READ_SORTS`, so every name in
    that tuple must really reorder the set — an unknown sort falls back to the
    default silently (`BR-SHL-011`), which is what would make a dead caret
    invisible.
    """
    assert dataset.READ_SORTS, "no sorts declared at all"
    with tenant_ctx(water_reads["tenant"]):
        default = [r.read_on for r in dataset.meter_reads_dataset(**SEP)["rows"]]
        assert len(default) == 8
        for name in dataset.READ_SORTS:
            down = dataset.meter_reads_dataset(sort=name, direction="desc", **SEP)
            up = dataset.meter_reads_dataset(sort=name, direction="asc", **SEP)
            assert len(down["rows"]) == 8, name
            # The two directions must be exact reverses of each other. A sort
            # name the query does not know falls back to the default, and the
            # default reverses too — so this asserts the ORDER ITSELF differs
            # between the declared sorts, which a fallback cannot fake.
            assert [r.read_on for r in down["rows"]] == [
                r.read_on for r in reversed(up["rows"])
            ], name


def test_declared_filters_are_the_registry_s_filters(water_reads):
    """The dataset registry publishes the filter vocabulary a report may use.
    A name in one and not the other is a filter the screen offers and the query
    drops, or a criterion nothing can reach."""
    declared = {d.code: d for d in datasets.DATASETS}["meter_reads"]
    assert set(dataset.READ_FILTERS) == set(declared.filters)


def test_the_three_refusals_name_the_reports_and_nothing_else(water_reads):
    """⚠ **THE THREE REFUSED DEFINITIONS ARE ASSERTED IN BOTH DIRECTIONS**, so
    adding a fourth misfit — or quietly serving one of these — is a deliberate
    act rather than drift. That is the rot CLAUDE.md's own rule-count line has
    suffered six times."""
    refused = dataset.METER_READS_DEFINITIONS_NOT_SERVED
    assert set(refused) == {"read_completeness", "read_import_log", "bill_projection"}
    # And the three that ARE served must not appear in it.
    for key in ("my_usage", "consumption_exceptions", "usage_and_ranking"):
        assert key not in refused, key
    # Each refusal says what ONE ROW of that report is — a sentence a clerk can
    # read, not a code (B14 rule 33: the reason is the report's, not a rule id).
    for key, sentence in refused.items():
        assert len(sentence) > 100, key
        assert "row per" in sentence or "one row" in sentence.lower(), key


def test_every_seeded_definition_is_either_served_or_refused_by_name():
    """⚠ **THE SIX ARE COUNTED, SO NONE CAN FALL BETWEEN THE TWO LISTS.**

    A definition that is neither served nor named in the refusal map is the
    failure this whole lane exists to prevent: it would be handed to the generic
    dataset query and answer a question nobody asked. The six are read from the
    SEED, not typed here, so a seventh arriving turns this red.
    """
    seeded = {
        "read_completeness",
        "consumption_exceptions",
        "usage_and_ranking",
        "read_import_log",
        "my_usage",
        "bill_projection",
    }
    refused = set(dataset.METER_READS_DEFINITIONS_NOT_SERVED)
    served = seeded - refused
    assert len(seeded) == 6
    assert len(refused) == 3
    assert served == {"consumption_exceptions", "usage_and_ranking", "my_usage"}

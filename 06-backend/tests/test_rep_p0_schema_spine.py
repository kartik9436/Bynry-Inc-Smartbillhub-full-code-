# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 0 · P0.1 · P0.2 · P0.3 · P0.4 · P0.5 · P0.6 ·
#           P0.7 · P0.16.  Screens: none — Phase 0 ships no screen.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping · platform rows) · hard rule
#           2 (money 4 dp / percentages 6 dp stored) · hard rule 3 (a quantity
#           carries its unit) · BR-REP-001 (a money report names its basis) ·
#           NFR-3 / NFR-5 (pagination; no hard caps)
# ───────────────────────────────────────────────────────
"""The Reports Phase 0 spine, asserted rather than described.

⚠ **WHAT THIS FILE CANNOT PROVE, STATED HERE SO NOBODY READS A GREEN RUN AS
MORE THAN IT IS.** `config/settings/test.py` hardcodes in-memory SQLite and
ignores `DATABASE_URL`, **and SQLite has no row-level security of any kind** —
so every assertion about `reports/0002`'s policy would pass here by vacuum
(hard-won law 14). Nothing in this file asserts isolation. That proof is
`P0.10`, it belongs to a sibling lane, it runs under `config.settings.local`
against real PostgreSQL 16 under a NOLOGIN NOSUPERUSER NOBYPASSRLS role, and
until it exists **the platform-row policy in `0002` is unproven**.

What IS proved here is everything a schema and a declaration can prove: the
counts tie to the document's own figures, every seeded definition validates
against its dataset, every quantity column carries a unit, every money column
names a basis and a 4-decimal scale, the two additivity traps refuse by name,
and the export and the viewer come out of one function.
"""

import pytest

from apps.reports import datasets, runner
from apps.reports.models import ReportCategory, ReportDefinition, ReportTenantSetting

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# P0.2 · P0.6 — the seed, counted against the document's own figures
# ═══════════════════════════════════════════════════════════════════════════
def test_p0_6__forty_six_platform_definitions_exist(brazos):
    """`P0.6`'s outcome verbatim: *"46 platform rows exist; the catalogue count
    reads 46, not 23."*

    Counted on the TABLE. The brief says 45 in three other places and both
    numbers are right of different things — 46 definitions, of which `R42`
    renders as Tab 2 rather than as a card, so the GRID shows 45. See
    `0003_seed_catalogue.py`'s docstring and `DEF-REP-6798`.
    """
    with tenant_ctx(brazos):
        rows = list(ReportDefinition.objects.filter(tenant_id=None))
    # `CR-179-BRC10` (2026-10-12) added the 47th platform row, `rate_impact`
    # (`reports/0010`), on the PO's own placement under Billing › Readiness.
    assert len(rows) == 49  # + `CR-184-BRC10` (`reports/0011`) + `CR-185-BRC10` (`reports/0012`, Owner summary)
    # ⚠ Counted in Python, not with `.exclude(filters__renders_as="tab")`. An
    # `exclude()` over a JSON key most rows DO NOT HAVE does not mean what it
    # reads as — a row whose `filters` carries no `renders_as` at all is
    # dropped too, and the count came back 1 instead of 45. A negative JSON
    # lookup is a check that looks at the wrong thing (law 7's fourth shape),
    # and 46 rows fit in memory.
    tabs = [row for row in rows if row.filters.get("renders_as") == "tab"]
    assert len(tabs) == 1
    assert tabs[0].key == "operational_dashboard"
    assert len(rows) - len(tabs) == 48  # + `CR-184-BRC10` (`reports/0011`) + `CR-185-BRC10` (`reports/0012`)


def test_p0_2__six_groups_and_nineteen_sub_groups(brazos):
    """`P0.2`'s outcome: *"Seed the 6 groups and 19 sub-groups."*"""
    with tenant_ctx(brazos):
        groups = ReportCategory.objects.filter(tenant_id=None, parent_code=None)
        subs = ReportCategory.objects.filter(tenant_id=None).exclude(parent_code=None)
        assert groups.count() == 6
        assert subs.count() == 19
        # Every sub-group hangs off a group that exists — a dangling parent is
        # a catalogue section a clerk can never reach.
        codes = set(groups.values_list("code", flat=True))
        assert {row.parent_code for row in subs} <= codes


def test_p0_6__every_group_count_matches_the_documents_own_heading(brazos):
    """The document heads each group with its count — BILLING 5 · RECEIVABLES 9
    · FINANCE 9 · CUSTOMERS 9 · OPERATIONS 7 · COMPLIANCE 7 — and they sum to
    46. Asserting the SPLIT and not only the total is what catches a row filed
    under the wrong heading, which a total never would.
    """
    # `CR-179-BRC10` — the document's five plus Rate Impact (`reports/0010`).
    expected = {
        "billing": 6,
        "receivables": 10,  # + `CR-184-BRC10` (`reports/0011`, Receivables over 90 days by service)
        "finance": 9,
        "customers": 10,  # + `CR-185-BRC10` (`reports/0012`, Owner summary)
        "operations": 7,
        "compliance": 7,
    }
    with tenant_ctx(brazos):
        actual = {
            code: ReportDefinition.objects.filter(
                tenant_id=None, group_code=code
            ).count()
            for code in expected
        }
    assert actual == expected
    assert sum(actual.values()) == 49


def test_p0_6__every_sub_group_has_at_least_one_report(brazos):
    """Nineteen sub-groups seeded and nineteen used. An empty catalogue section
    is a heading over nothing, which the catalogue screen would render as a
    blank band and nobody would file."""
    with tenant_ctx(brazos):
        used = set(
            ReportDefinition.objects.filter(tenant_id=None).values_list(
                "sub_group_code", flat=True
            )
        )
        declared = set(
            ReportCategory.objects.filter(tenant_id=None)
            .exclude(parent_code=None)
            .values_list("code", flat=True)
        )
    assert used == declared
    assert len(used) == 19


def test_p0_6__every_definition_names_one_of_the_nine_datasets(brazos):
    """A dataset code nothing declares is a report that can never run, and
    nothing else in this product would notice: the row inserts, the catalogue
    lists it, and the failure arrives when a clerk clicks it."""
    with tenant_ctx(brazos):
        used = set(
            ReportDefinition.objects.filter(tenant_id=None).values_list(
                "dataset", flat=True
            )
        )
    assert used <= set(datasets.BY_CODE)
    # And every one of the nine is reached by at least one report — a dataset
    # nothing reads is nine-tenths of a registry and a maintenance cost.
    assert used == set(datasets.BY_CODE)


def test_p0_6__the_six_keys_this_product_already_serves_are_not_respelled(brazos):
    """A key sits in a bookmarked URL, a stored schedule and an IS-11 filename
    a bookkeeper has already filed (`OQ-247`). Renaming one is a ruling, not a
    seed — so the seed reuses the served strings rather than snake-casing the
    drawing's name over them."""
    served = {"ar_aging", "billing_register", "revenue_by_service_rate",
              "payments_by_method", "account_ledger", "trial_balance"}
    with tenant_ctx(brazos):
        keys = set(
            ReportDefinition.objects.filter(tenant_id=None).values_list("key", flat=True)
        )
    assert served <= keys


# ═══════════════════════════════════════════════════════════════════════════
# P0.1 · P0.3 — the tables themselves
# ═══════════════════════════════════════════════════════════════════════════
def test_p0_1__a_platform_row_and_a_tenant_row_coexist_on_one_key(brazos):
    """`P0.1`'s outcome: *"A platform row and a tenant row coexist."*

    The unique key is `(tenant_id, key)`, so a utility copying a shipped report
    keeps the same key on its own row — which is what makes a bookmarked
    `/reports/ar_aging` open the tenant's version without the address changing.
    """
    with tenant_ctx(brazos):
        platform = ReportDefinition.objects.get(tenant_id=None, key="ar_aging")
        mine = ReportDefinition.objects.create(
            tenant=brazos,
            key="ar_aging",
            name="AR Ageing (ours)",
            dataset=platform.dataset,
            group_code=platform.group_code,
            sub_group_code=platform.sub_group_code,
        )
        assert ReportDefinition.objects.filter(key="ar_aging").count() == 2
        # And the tenant's own outranks the platform row it copied.
        assert runner.resolve("ar_aging").name == "AR Ageing (ours)"
        mine.delete()


def test_p0_1__two_platform_rows_cannot_share_one_key(brazos):
    """⚠ The constraint that LOOKS like it protects the shipped rows does not.

    `UNIQUE (tenant_id, key)` constrains nothing when `tenant_id` is NULL,
    because in PostgreSQL `NULL != NULL` — so two platform definitions on one
    key would both insert, and `runner.resolve()` would return whichever the
    database happened to order first. The partial index is the one doing the
    work, and this case is the only thing that can tell the two apart.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError):
            # A SAVEPOINT — hard-won law 14. A failed statement poisons the
            # whole PostgreSQL transaction and every later query in it raises.
            with transaction.atomic():
                ReportDefinition.objects.create(
                    tenant=None,
                    key="ar_aging",
                    name="a second platform ar_aging",
                    dataset="payments",
                    group_code="receivables",
                )


def test_p0_1__visibility_is_a_check_constraint_and_refuses_a_third_value(brazos):
    """`P0.1`'s own ⚠: *"Make `visibility` a CHECK constraint (two signed
    values) and categories a TABLE."* A CHECK makes a third value a MIGRATION,
    which is right for a signed enum — who may see a report is a security
    statement — and wrong for a tenant-extensible list.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError):
            # ⚠ A SAVEPOINT, not a bare try/except. A failed statement poisons
            # the whole PostgreSQL transaction and every later query in it
            # raises — hard-won law 14, and the reason this case would pass on
            # SQLite either way.
            with transaction.atomic():
                ReportDefinition.objects.create(
                    tenant=brazos,
                    key="visibility_probe",
                    name="probe",
                    dataset="accounts",
                    group_code="customers",
                    visibility="team",
                )


def test_p0_3__the_overlay_is_unique_per_tenant_and_definition(brazos):
    """`P0.3`: *"Unique (tenant_id, definition_id)."* Two overlay rows on one
    report is two answers to *"does this utility show it"*."""
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        definition = ReportDefinition.objects.get(tenant_id=None, key="ar_aging")
        ReportTenantSetting.objects.create(
            tenant=brazos, definition=definition, enabled=False
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ReportTenantSetting.objects.create(
                    tenant=brazos, definition=definition, enabled=True
                )


def test_p0_3__a_water_only_utility_can_switch_a_report_off(brazos):
    """`P0.3`'s outcome: *"A water-only tenant disables the gas reports and 1·1
    stops showing them."* Phase 0 owns the ROW; the screen that honours it is
    `P1.1`'s, so this asserts the row and claims nothing about the screen.
    """
    with tenant_ctx(brazos):
        definition = ReportDefinition.objects.get(tenant_id=None, key="my_usage")
        ReportTenantSetting.objects.create(
            tenant=brazos, definition=definition, enabled=False, display_order=99
        )
        overlay = ReportTenantSetting.objects.get(tenant=brazos, definition=definition)
        assert overlay.enabled is False
        # The platform row is untouched — copy-on-write, never edit-in-place.
        definition.refresh_from_db()
        assert definition.tenant_id is None


# ═══════════════════════════════════════════════════════════════════════════
# P0.4 — the dataset registry
# ═══════════════════════════════════════════════════════════════════════════
def test_p0_4__nine_datasets_each_with_one_grain_and_one_owner():
    """`P0.4`'s outcome: *"`GET /reports/datasets` lists 9."*"""
    payload = datasets.registry_payload()
    # `CR-184-BRC10` (2026-10-14) added the TENTH, `receivables` — what is still
    # owed, one row per account and service. The test keeps its name; the
    # count is the field and this is the record of why it moved.
    assert payload["count"] == 10
    assert len(payload["datasets"]) == 10
    assert len({row["code"] for row in payload["datasets"]}) == 10
    for row in payload["datasets"]:
        assert row["grain"], f"{row['code']} states no grain (P0.16)"
        assert row["owner_module"], f"{row['code']} names no owner"


def test_p0_4__every_column_carries_a_type_and_a_quantity_carries_its_unit():
    """`P0.4`'s outcome, verbatim: *"every column carries a type and, where it
    is a quantity, a unit."* CLAUDE.md hard rule 3 — a consumption figure
    without its unit is the one thing that rule forbids, and `684` is not a
    number anybody can bill or compare."""
    for dataset in datasets.DATASETS:
        for column in dataset.columns:
            assert column.type in datasets.COLUMN_TYPES
            if column.type == datasets.TYPE_QUANTITY:
                assert column.unit or column.unit_from, f"{dataset.code}.{column.name}"


def test_p0_4__money_names_its_basis_and_stores_four_decimals():
    """CLAUDE.md hard rule 2 and BR-REP-001 in one pass: money is stored to 4
    decimals and a money report names its date basis. A percentage is 6.
    DISPLAY is 2 for both and is the renderer's, not this declaration's."""
    for dataset in datasets.DATASETS:
        for column in dataset.columns:
            if column.type == datasets.TYPE_MONEY:
                assert column.money_basis in datasets.MONEY_BASES
                assert column.scale == 4
            if column.type == datasets.TYPE_PERCENT:
                assert column.scale == 6


def test_p0_4__the_datasets_that_do_not_page_yet_say_so():
    """**ALL NINE PAGE SINCE 2026-09-27 (lane DS-PAYMENTS).**

    ⚠ **THIS ASSERTS THE DECLARATION AGAINST TODAY'S TRUTH, AND IT DID ITS JOB
    TWICE IN ONE DAY.** It was named *three_of_the_nine* and asserted
    `{"invoices", "payments", "journal_lines"}`:

      * lane DS-LEDGER flipped `journal_lines` to `paginates=True` in
        `e5105e95a` and **did not move this line, so that commit shipped this
        test RED** — which is exactly what it is for, and exactly the shape
        hard-won law 7 warns about, a true red arriving into a suite with 47
        failing gates where nobody looks at one more;
      * lane DS-PAYMENTS flipped `payments` in the same commit as
        `apps/payments/payments_dataset.py` — the query that applies every
        criterion as a `WHERE`, the order as an `ORDER BY` and the page as a
        `LIMIT`/`OFFSET`, with a separate generator for the export that takes
        no `page` and no `per`, measured on PostgreSQL 16 at **0.284s for page
        1 and 0.321s for page 802 of 40,066 payments** — and moved this line
        with it. ⚠ It also found that the grain was *"one payment allocation"*
        while one payment in five has no allocation at all (`DEF-REP-6853`);
      * lane DS-INVOICES flipped `invoices` in the same commit as
        `apps/billing/reporting.py::invoices_dataset` — the query that applies
        every criterion as a `WHERE`, the order as an `ORDER BY` and the page
        as a `LIMIT`/`OFFSET`, measured on PostgreSQL 16 at **0.674s for page 1
        and 0.673s for page 802 of 40,092 bills** — and moved this line with it.

    Asserting `paginates is True` everywhere would be a check incapable of
    failing, which is what law 7 calls the second shape — so the set stays
    EXACT and shrinks one dataset at a time.

    ⚠ **THE SET IS NOW EMPTY, AND THAT IS THE ONE STATE IN WHICH THIS CHECK
    STOPS BEING ABLE TO FAIL.** It is kept rather than deleted for the opposite
    reason: the next dataset added to the registry arrives with `paginates`
    defaulting to whatever its author declares, and an empty expectation goes
    RED the moment one arrives unpaged — which is the question this test exists
    to ask. It is no longer a check that a KNOWN gap is declared; it is a check
    that NO NEW gap appears undeclared.
    """
    unpaged = {d.code for d in datasets.DATASETS if not d.paginates}
    assert unpaged == set(), (
        "every dataset in the registry declares that it pages; a new one that does not "
        f"must say so here and carry its own defect id — found {sorted(unpaged)}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# P0.16 — the dimension model, and the two traps that produce wrong money
# ═══════════════════════════════════════════════════════════════════════════
def test_p0_16__summing_a_semi_additive_measure_across_time_is_refused_by_name():
    """`P0.16`'s outcome, verbatim: *"Summing a semi-additive measure across
    time is refused at build time, naming the measure."*

    §7.2.2's first trap: *"AR balance · deposits held · accounts active — sums
    across accounts, never across time. Group AR Ageing by month, total the
    column, and the number means nothing. **Nothing stops you today.**"*
    """
    with pytest.raises(datasets.UnlawfulTotal) as raised:
        datasets.assert_summable("payments", "total", ("time",))
    assert "total" in str(raised.value)
    assert "time" in str(raised.value)
    # And across ACCOUNTS it is lawful, which is the half that makes the rule a
    # rule rather than a ban.
    datasets.assert_summable("payments", "total", ("consumer_class", "service"))


def test_p0_16__a_non_additive_measure_is_refused_in_every_direction():
    """§7.2.2's second trap: *"DSO · collection rate · % share · average days
    overdue must be recomputed from their components, never averaged. The
    average of four route DSOs is **not** the utility's DSO."*"""
    for name in ("dso_days", "collection_rate", "share_pct"):
        with pytest.raises(datasets.UnlawfulTotal):
            datasets.assert_summable("payments", name, ())


def test_p0_16__consumption_is_additive_only_within_one_service():
    """§7.2.2's fourth row: *"gallons plus kilowatt-hours is not a number —
    hard rule 3 already forbids it, and this is the same rule stated as
    metadata."*"""
    with pytest.raises(datasets.UnlawfulTotal):
        datasets.assert_summable("meter_reads", "consumption", ("service",))
    datasets.assert_summable("meter_reads", "consumption", ("time", "route_cycle"))


def test_p0_16__a_fully_additive_measure_sums_in_any_direction():
    """The negative of the three above. A model that refused everything would
    pass every case here and be useless, which is law 7's *"ask what would make
    this check pass wrongly"* applied to itself."""
    datasets.assert_summable("invoices", "amount", ("time", "service", "premises"))
    datasets.assert_summable("journal_lines", "debit", ("time",))


def test_p0_16__ar_ageing_inherits_thirteen_dimensions_not_two():
    """The finding the PO raised looking at AR Ageing: *"two slicers where the
    fact has about a dozen."* §7.2.1 counts thirteen and §7.2.1B says *"two of
    thirteen — multiply that by 45 reports and the hand-picking is the whole
    problem."*"""
    assert len(datasets.PAYMENTS.dimensions) == 13


def test_p0_16__a_dimension_is_the_same_object_everywhere_it_appears():
    """Conformance by identity. *Service* must mean the same thing, carry the
    same label and offer the same values in every dataset that has it —
    *"one calls it Service with eleven values, another calls it Utility with
    three, and a clerk comparing them is comparing nothing."*

    `P0.17` is the sibling task that tests this properly across labels and
    value sets; this asserts the cheap half that makes drift impossible in the
    first place.
    """
    seen: dict[str, object] = {}
    for dataset in datasets.DATASETS:
        for dimension in dataset.dimensions:
            if not dimension.conformed:
                continue
            first = seen.setdefault(dimension.name, dimension)
            assert first is dimension, (
                f"{dataset.code} declares a SECOND {dimension.name!r} dimension — "
                "a conformed dimension is declared once and shared"
            )


def test_p0_16__the_two_time_hierarchies_do_not_nest():
    """§7.2.3: *"A billing cycle does not sit inside a calendar month. It
    straddles two."* Both are declared so a report can state which it rolls up
    by; a report that mixes them is wrong in a way no total will reveal."""
    assert set(datasets.TIME_HIERARCHIES) == {"calendar", "billing"}
    assert "accounting_period" in datasets.TIME_HIERARCHIES["calendar"]
    assert "cycle" in datasets.TIME_HIERARCHIES["billing"]
    assert "cycle" not in datasets.TIME_HIERARCHIES["calendar"]


# ═══════════════════════════════════════════════════════════════════════════
# P0.5 — one path
# ═══════════════════════════════════════════════════════════════════════════
def test_p0_5__every_seeded_definition_validates_against_its_dataset(brazos):
    """The seed is user input to the same wall a clerk's report meets. Forty-six
    rows, each checked against its dataset's declaration — columns, filters,
    group-by dimensions, and every measure's additivity against the directions
    the grouping crosses.

    This is the single most useful assertion in the file: a seeded row that
    names a filter its dataset does not accept would insert happily, list
    happily, and fail the first time somebody ran it.
    """
    with tenant_ctx(brazos):
        rows = list(ReportDefinition.objects.filter(tenant_id=None))
    assert len(rows) == 49  # 46 seeded by `0003` + `rate_impact` (`0010`) + `0011` (CR-184-BRC10) + `0012` (CR-185-BRC10)
    for row in rows:
        runner.validate(runner.resolve(row.key))


def test_p0_5__the_export_and_the_viewer_come_out_of_one_function():
    """`P0.5`'s outcome: *"a report rendered on screen and the same report
    exported produce byte-identical rows."*

    Asserted STRUCTURALLY, because the alternative — running both and comparing
    — proves they agree on one fixture and says nothing about the next one.
    What makes them identical is that there is one function; so this reads the
    source of both call sites and refuses a second route to the rows.
    """
    import inspect
    from types import SimpleNamespace

    from apps.reports import api, exports, runner as reports_runner

    # The structural half, and it is stronger than a grep for one spelling:
    # `apps/reports/exports.py` **does not import `queries` at all** any more.
    # Both its reads — the report's rows and payments-by-method's detail rows —
    # go through the runner, so there is no name in that module a second route
    # could be written against without a new import somebody has to add.
    assert not hasattr(exports, "queries")
    assert "runner.rows_for" in inspect.getsource(exports._rows_for)
    assert "runner.run(" in inspect.getsource(exports._detail_rows)
    assert "reports_runner.run(" in inspect.getsource(api)

    # ⚠ AND THE BEHAVIOURAL HALF, BECAUSE THE TEXTUAL ONE CAN PASS WRONGLY —
    # `queries.VIEWERS.get(...)` is a second route the grep above would not
    # see. This one cannot: the export's rows ARE whatever the runner returns.
    sentinel = [{"proof": "the export took the runner's rows"}]
    original = reports_runner.rows_for
    try:
        reports_runner.rows_for = lambda *a, **k: sentinel
        rows = exports._rows_for("ar_aging", SimpleNamespace(filters={}))
    finally:
        reports_runner.rows_for = original
    assert rows is sentinel


def test_p0_5__a_query_string_reaches_the_read_model_as_strings_not_lists(brazos):
    """⚠ The bug this runner could most easily have introduced, and it would
    have been silent.

    `apps/reports/api.py` passes the request's `QueryDict` in. `dict(QueryDict)`
    yields `{"from": ["2026-09-01"]}` — a LIST where every read model expects a
    string — because a `QueryDict` is multi-valued. The code this runner
    replaced passed the `QueryDict` through untouched and relied on `.get()`
    returning the last value.

    Nothing else in this suite would catch it: the structural assertions about
    one path, the counts, the additivity refusals and every gate stay green
    while all four built reports filter on a one-element list.
    """
    from django.http import QueryDict

    with tenant_ctx(brazos):
        definition = runner.resolve("ar_aging")
        bound = runner.bind(definition, QueryDict("from=2026-09-01&to=2026-09-30&class=res"))
    assert bound["from"] == "2026-09-01"
    assert bound["to"] == "2026-09-30"
    assert bound["class"] == "res"
    assert not any(isinstance(value, list) for value in bound.values())


def test_p0_5__the_live_screens_dotted_filters_reach_the_read_model(brazos):
    """⚠ The second bug this runner could have introduced in silence, and it is
    worse than the first because the screen would still look right.

    The AR ageing screen sends its filters DOTTED — `f.class`, `f.band`,
    `f.service`, `f.premises` — and `apps/reports/queries.py` reads both
    spellings (`params.get("class") or params.get("f.class")`). A runner that
    only passed the bare names would hand the query a request with every filter
    missing: the report renders, the chip still says *Residential*, and the
    number underneath is **the whole receivable**.

    Nothing else here would catch it. The counts pass, the additivity refusals
    pass, `tsc` passes, and the one-path assertions pass — because the path IS
    one, it is just carrying less than it was given.
    """
    with tenant_ctx(brazos):
        definition = runner.resolve("ar_aging")
        bound = runner.bind(
            definition,
            {"f.class": "residential", "f.band": "61-90", "f.service": "electric",
             "f.premises": "PR-101", "from": "2026-09-01", "sort": "total"},
        )
        # The DOTTED key is what is passed on — the queries read that spelling
        # and this runner does not get to rename anybody's wire.
        assert bound["f.class"] == "residential"
        assert bound["f.band"] == "61-90"
        assert bound["f.service"] == "electric"
        assert bound["f.premises"] == "PR-101"
        assert bound["from"] == "2026-09-01"
        assert bound["sort"] == "total"
        assert runner.dropped(definition, {"f.class": "x", "f.nonsense": "y"}) == (
            "f.nonsense",
        )


def test_p0_5__a_definition_on_an_unbuilt_dataset_refuses_by_name():
    """A definition whose dataset has NO query gets a NAMED refusal carrying
    the dataset code — never an empty result, which is the hardest bug in this
    product to see, and never a 501, because a viewer that opens onto a reason
    is a screen pretending to be a report.

    ⚠ **THIS CASE USED `meter_fleet` AND IT NOW SERVES ROWS (lane REP-WIRE,
    2026-09-27, `DEF-REP-6894`).** All nine declared datasets have a query, so
    there is no longer a definition in the catalogue that can demonstrate this
    refusal — and rather than delete the case, which would take the assertion
    with it, it is asked of a definition this test builds. The refusal itself
    is still live and still reachable: `runner.bind` raises it for any dataset
    `datasets.BY_CODE` does not hold, which is exactly the state
    `apps/notifications/notifications_dataset.py` is in today (`DEF-REP-6895`).

    ⚠ **THE OLD FORM IS WORTH RECORDING.** It asserted a HOLD — *six of the
    nine datasets have no query yet* — and a hold with a clock in it rots on
    the day the thing it points at lands. It went red the moment the datasets
    were wired, which is what a hold's test is FOR (hard-won law 2's mirror).
    """
    from apps.reports import runner as reports_runner

    absent = reports_runner.ResolvedDefinition(
        key="a_report_on_a_tenth_dataset",
        name="A report on a tenth dataset",
        dataset="notifications",
        group_code="billing",
        sub_group_code="billing_delivery",
        columns=(),
        filters={},
        group_by=(),
        sort=(),
        service_codes=(),
        from_table=True,
    )
    with pytest.raises(runner.DatasetNotExecutable) as raised:
        runner.bind(absent, {})
    assert "notifications" in str(raised.value)
    assert "a_report_on_a_tenth_dataset" in str(raised.value)


def test_p0_5__every_declared_dataset_now_has_a_query(brazos):
    """The other half of the case above, and the one that keeps it honest: the
    refusal is rare now because the queries were BUILT, not because the check
    stopped looking. It names any dataset that loses its query."""
    from apps.reports import queries as reports_queries

    dark = sorted(
        dataset.code
        for dataset in datasets.DATASETS
        if dataset.code not in reports_queries.DATASET_QUERIES
    )
    assert not dark, f"these declared datasets have no query: {dark}"


def test_p0_5__an_unknown_filter_is_dropped_at_run_and_refused_at_save(brazos):
    """The split the brief draws and the reason for it: `P5.2` validates every
    name **when a definition is saved**. At RUN a stale bookmark with one extra
    query parameter must still open the report, which is what the viewer does
    today — raising there would be a user-visible behaviour change in a phase
    whose brief says a clerk can newly do nothing."""
    with tenant_ctx(brazos):
        definition = runner.resolve("ar_aging")
        bound = runner.bind(definition, {"class": "residential", "nonsense": "1"})
        assert "class" in bound
        assert "nonsense" not in bound
        assert runner.dropped(definition, {"nonsense": "1"}) == ("nonsense",)

        broken = runner.ResolvedDefinition(
            key="ar_aging",
            name="probe",
            dataset="payments",
            group_code="receivables",
            sub_group_code="receivables_arrears",
            columns=(),
            filters={"nonsense": "1"},
            group_by=(),
            sort=(),
            service_codes=(),
            from_table=False,
        )
        with pytest.raises(runner.UnknownParameter):
            runner.validate(broken)


def test_p0_5__a_definition_cannot_name_a_column_its_dataset_does_not_produce(brazos):
    """*"You cannot invent a column the dataset does not produce. That is the
    architecture, not an oversight, and it is the reason a clerk can be trusted
    with a report builder at all."*"""
    with tenant_ctx(brazos):
        broken = runner.ResolvedDefinition(
            key="probe",
            name="probe",
            dataset="accounts",
            group_code="customers",
            sub_group_code="customers_accounts",
            columns=("account_no", "secret_margin"),
            filters={},
            group_by=(),
            sort=(),
            service_codes=(),
            from_table=False,
        )
        with pytest.raises(runner.UnknownParameter) as raised:
            runner.validate(broken)
    assert "secret_margin" in str(raised.value)


def test_p0_5__a_definition_that_groups_by_month_and_totals_a_balance_is_refused(brazos):
    """`P0.16` reaching the save path, which is where it earns its keep: the
    ageing report grouped by month with its balance column totalled is refused
    at BUILD time, naming the measure — instead of rendering a number that
    means nothing."""
    with tenant_ctx(brazos):
        broken = runner.ResolvedDefinition(
            key="probe",
            name="probe",
            dataset="payments",
            group_code="receivables",
            sub_group_code="receivables_arrears",
            columns=("account_no", "total"),
            filters={},
            group_by=("time",),
            sort=(),
            service_codes=(),
            from_table=False,
        )
        with pytest.raises(datasets.UnlawfulTotal) as raised:
            runner.validate(broken)
    assert "total" in str(raised.value)


# ═══════════════════════════════════════════════════════════════════════════
# P0.7 — the maps that are gone
# ═══════════════════════════════════════════════════════════════════════════
def test_p0_7__the_two_dead_exports_are_gone_and_stay_gone():
    """`P0.7`, and the brief's own words on why deleting is the fix: *"they are
    not wrong; they are furniture. A lane extending the catalogue will read
    them, assume they are the interface, and wire to something nothing calls."*

    ⚠ **THIS IS TWO OF THE SIX AND THE OTHER FOUR ARE NAMED HERE RATHER THAN
    QUIETLY SKIPPED.** `P0.7`'s reference is `catalog.py:412-425` and it is
    wrong about four of the six names: `VIEWERS` is `queries.py:722`, and
    `VIEWER_SEGMENTS`, `MONEY_COLUMNS`, `NUMERIC_COLUMNS` and `REPORT_FILTERS`
    are all in **07-frontend** — `reportsShared.tsx:83` and
    `ReportViewerPage.tsx:87/97/107`. Deleting the front-end four changes what
    the report viewer renders, which is `P2.1`'s redraw and is classified
    MAINTENANCE with a required reproduce step. Filed as `DEF-REP-6799`.
    """
    from apps.reports import catalog

    assert not hasattr(catalog, "VIEWER_KEYS")
    assert not hasattr(catalog, "card_for")

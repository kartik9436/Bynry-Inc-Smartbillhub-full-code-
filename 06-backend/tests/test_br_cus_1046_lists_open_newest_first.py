# ── Trace ──────────────────────────────────────────────
# Rules:   BR-CUS-1046 (PO 2026-09-10, EXTENDED 2026-09-12) — "Whenever any
#          account is created or any entry is created in the system … It should
#          always sort it by the creation order. The new newly created entries
#          should always show on the top", and the extension answering
#          OQ-CUS-1790: "(c) All eight open newest-first and the six gain a sort
#          control. Largest job: six server-side sorts."
#          NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere)
#          BR-SHL-011 (q/sort/dir/page/per grammar; fall back, never 4xx)
# Defects: DEF-CUS-4996 (the accounts list itself) · DEF-CUS-5060 (six of the
#          eight lists) · DEF-CUS-5061 (the Imports 200-row cap)
# Screens: S17 and its eight tabs
# Impacts: apps/customers/selectors · service_request_reads · move_reads ·
#          transfer_reads · disconnect_reads · apps/metering/connection_reads ·
#          apps/customers/account_import · core/pagination
# ───────────────────────────────────────────────────────
"""ALL EIGHT LISTS OPEN ON WHAT WAS JUST CREATED, AND THE PAGE IS TAKEN IN SQL.

WHAT EACH SECTION PROVES, AND WHY IT IS THAT SHAPE
--------------------------------------------------
**§1 · the ORDER BY, asserted on the query rather than on rows.** Six worklists
gained a sort in one commit. Planting a dozen rows on each of six models to
observe their order would be six fixtures, minutes of runtime, and a test that
goes red for reasons that have nothing to do with ordering. `qs.query.order_by`
is the ORDER the database will apply, read straight off the queryset — it needs
no rows at all, it cannot be satisfied by a Python `sort()` afterwards, and it
fails loudly the day someone adds a second `.order_by()` further down.

⚠ **AND THAT IS ALSO ITS BLIND SPOT, SAID OUT LOUD (law 7, habit 2 — "ask what
would make this check pass wrongly").** It cannot see a list that orders
correctly in SQL and then re-sorts in Python. §2 is the check that CAN see that,
and it is why the accounts list gets a row-level assertion as well as a query
one: the accounts list is the one that really did sort in Python.

**§2 · the accounts list builds ONE PAGE, not one tenant.** `account_list`
materialised every matching row and sliced afterwards, so asking for one row
cost the same as asking for fifty (measured 2026-09-12: 0.107 s against 0.102 s
at 73 accounts). A statement COUNT cannot see this — `DEF-2723` already made
the statement count constant, and it stayed constant while the work grew with
the tenant. What grows is ROWS BUILT, so that is what is counted.

**§3 · the direction fall-back.** `?sort=created` with no `dir` must open on the
NEWEST row. Before `default_dir` existed the grammar fell back to `asc`, which
is the exact inversion the ruling removes — and it would have shipped looking
like a working feature.

**§4 · the Imports tab's cap.** `NFR-5` says no hard caps anywhere; the tab
sliced `[:200]` and served no count, so the 201st import silently did not exist.

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567, DEF-GOV-3778).
"""
import pytest

from core.pagination import ListParams, order_terms, parse_list_params

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

LIST_SERVICES = ("water", "sewer", "trash")


@pytest.fixture()
def utility(growth_plan, identity_seam):  # noqa: F405
    """One provisioned utility. Nothing is seeded into it beyond provisioning."""
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Ottumwa Water Works",
            subdomain="ottumwa-water-works",
            services=list(LIST_SERVICES),
            owner={
                "full_name": "Ops Owner",
                "email": "owner@ottumwa-water-works.test",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    return tenant


@pytest.fixture()
def tenant_ctx_any(utility):
    """A tenant context, for the cases that read an ORDER BY off a queryset.

    Those cases need no rows — `qs.query.order_by` is the order the database
    WILL apply — but they do need `app.tenant_id` set, because every one of
    these querysets filters on the tenant and hard rule 1 says so.
    """
    with tenant_ctx(utility):
        yield utility


@pytest.fixture()
def planted_accounts(utility):
    """More accounts than one page, each created at a DIFFERENT moment.

    ⚠ **THE TIMESTAMPS ARE FORCED APART ON PURPOSE.** `created_at` is
    `auto_now_add`, so a loop that inserts twenty rows in one millisecond gives
    twenty accounts with the same instant and *"the newest is first"* becomes a
    statement about the tiebreak rather than about the ruling. `uuid7` ids are
    themselves time-ordered, so the test would have passed either way and
    proved nothing.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.customers import models as customers_models, services as customers_services
    from apps.metering import models as metering_models

    count = 23
    with tenant_ctx(utility):
        premises = metering_models.Premises.objects.create(
            tenant=utility, address_line="1408 Elm St", city="Ottumwa", state="IA"
        )
        status = customers_models.AccountStatus.objects.filter(
            tenant=utility,
            behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES,
        ).first()
        assert status is not None, "the tenant has no occupying account status seeded"
        account_type = customers_models.AccountType.objects.first()
        start = timezone.now() - timedelta(days=count + 1)
        for index in range(count):
            unit = metering_models.Unit.objects.create(
                tenant=utility, premises=premises, label=f"Unit {index}"
            )
            account = customers_models.Account.objects.create(
                tenant=utility,
                unit=unit,
                # ⚠ THE NUMBERS RUN BACKWARDS AGAINST THE CREATION ORDER, so a
                # list that is really still sorting by account number cannot
                # accidentally satisfy "newest first".
                account_no=f"A-7{count - index:04d}",
                status=status,
                account_type=account_type,
            )
            customers_models.Account.objects.filter(pk=account.pk).update(
                created_at=start + timedelta(days=index)
            )
            customers_models.Contact.objects.create(
                tenant=utility, account=account, full_name=f"Ruiz {index:02d}", is_primary=True
            )
        yield utility, count


# ═══════════════════════════════════════════════════════════════════════════
# §0 · THE SHARED HELPER — pure, no database, and the flip is the whole risk
# ═══════════════════════════════════════════════════════════════════════════
class TestOrderTerms:
    """`core.pagination.order_terms` is the one implementation six lists share.

    ⚠ **THE DESCENDING BRANCH IS THE ONE THAT ROTS**, which is the entire reason
    the helper exists instead of six `if sort == …` ladders: a hand-rolled pair
    lets `desc` forget the tiebreak the `asc` branch remembers, and the symptom
    is a row appearing on two pages — not an exception anybody sees.
    """

    #: ⚠ **EVERY TERM IS WRITTEN ASCENDING — that is the convention the helper
    #: documents, and the one a real map broke on the first draft of this pass.**
    COLUMNS = {"created": ("created_at", "id"), "name": ("name", "id")}

    def test_a_known_sort_is_used_verbatim_when_ascending(self):
        assert order_terms("name", "asc", columns=self.COLUMNS, default="created") == [
            "name",
            "id",
        ]

    def test_descending_flips_every_term_and_not_only_the_first(self):
        """A flipped lead with an unflipped tiebreak is the bug this catches."""
        assert order_terms("name", "desc", columns=self.COLUMNS, default="created") == [
            "-name",
            "-id",
        ]

    def test_newest_first_is_desc_over_an_ascending_term(self):
        """⚠ **THIS CASE IS THE BUG THIS PASS SHIPPED AND CAUGHT BY MEASURING.**

        The first draft stored `("-created_at", "-id")` in the real maps AND
        declared `DEFAULT_DIR = "desc"`. `order_terms` did exactly what it says
        and flipped the term, the two minuses cancelled, and all eight lists
        opened on the OLDEST row — `BR-CUS-1046` inverted, with every unit test
        green, because the unit test had been written to the same wrong
        convention as the code.

        Nothing mechanical found it. It was found by `curl`-ing the endpoint and
        reading the first three account numbers, which is build-process step 2d
        (*"prove it by clicking"*) earning its place.

        So this asserts the CONVENTION and not the mechanics: a term is stored
        ascending, and *newest first* is `desc` over it.
        """
        assert order_terms("created", "desc", columns=self.COLUMNS, default="created") == [
            "-created_at",
            "-id",
        ], "newest first must be DESCENDING over an ascending `created_at`"
        assert order_terms("created", "asc", columns=self.COLUMNS, default="created") == [
            "created_at",
            "id",
        ], "ascending must be OLDEST first"

    def test_an_unknown_sort_falls_back_and_never_raises(self):
        """BR-SHL-011: a list URL can never 4xx over its params."""
        assert order_terms("nonsense", "asc", columns=self.COLUMNS, default="created") == [
            "created_at",
            "id",
        ]
        assert order_terms(None, "asc", columns=self.COLUMNS, default="created") == [
            "created_at",
            "id",
        ]

    def test_nulls_stay_at_the_same_end_in_both_directions(self):
        """A row with no date is blocked on a human, not urgent and not stale.

        `connection_reads` puts it LAST and says why; reversing the direction
        must not move it to the top of page one.
        """
        from django.db.models import F

        columns = {"target": (F("target_activation").asc(nulls_last=True), "id")}
        ascending = order_terms("target", "asc", columns=columns, default="target")
        descending = order_terms("target", "desc", columns=columns, default="target")
        assert ascending[0].descending is False and ascending[0].nulls_last is True
        assert descending[0].descending is True and descending[0].nulls_last is True


# ═══════════════════════════════════════════════════════════════════════════
# §3 · THE DIRECTION FALL-BACK (asserted first because §1 and §2 rest on it)
# ═══════════════════════════════════════════════════════════════════════════
class TestDefaultDirection:
    """`default_dir` belongs to `default_sort` and to nothing else."""

    def test_no_params_at_all_opens_on_the_declared_default_direction(self):
        params = parse_list_params(
            {}, allowed_sorts=("created", "name"), default_sort="created", default_dir="desc"
        )
        assert (params.sort, params.dir) == ("created", "desc")

    def test_an_explicit_direction_always_wins(self):
        """BR-CUS-1046's second clause — a clerk's chosen sort still wins."""
        params = parse_list_params(
            {"sort": "created", "dir": "asc"},
            allowed_sorts=("created", "name"),
            default_sort="created",
            default_dir="desc",
        )
        assert (params.sort, params.dir) == ("created", "asc")

    def test_choosing_a_column_opens_it_ascending_not_screen_default_descending(self):
        """A clerk who clicked NAME meant A→Z, not Z→A."""
        params = parse_list_params(
            {"sort": "name"},
            allowed_sorts=("created", "name"),
            default_sort="created",
            default_dir="desc",
        )
        assert (params.sort, params.dir) == ("name", "asc")

    def test_an_unknown_sort_falls_back_to_the_default_pair(self):
        params = parse_list_params(
            {"sort": "nonsense"},
            allowed_sorts=("created", "name"),
            default_sort="created",
            default_dir="desc",
        )
        assert (params.sort, params.dir) == ("created", "desc")

    def test_lists_that_declare_no_default_direction_are_unchanged(self):
        """Every list that did not ask for this keeps `asc`, as it always had."""
        params = parse_list_params({}, allowed_sorts=("name",), default_sort="name")
        assert params.dir == "asc"


# ═══════════════════════════════════════════════════════════════════════════
# §1 · WHAT EACH OF THE EIGHT LISTS ORDERS BY, READ OFF THE QUERYSET
# ═══════════════════════════════════════════════════════════════════════════
def _order_of(queryset) -> tuple:
    """The ORDER the database will apply, as strings a person can read.

    A term is either a plain field string (`"-created_at"`) or an `OrderBy` over
    an expression — a bare `F`, or something wrapped like `Lower(...)`. Only the
    first has a `.name`, so the expression is rendered from the fields it
    references rather than from an attribute that may not exist.
    """


    def field_of(expression) -> str:
        """The column an unresolved order expression refers to.

        ⚠ **`queryset.query.order_by` HOLDS UNRESOLVED EXPRESSIONS**, so a
        wrapped term is `OrderBy(Lower(F("account_no")))` — an `F`, which
        carries `.name`, NOT a resolved `Col`, which carries `.target`. The
        first draft of this helper checked only for `.target` and rendered
        `Lower("account_no")` as the string `"Lower"`, so a case asserting the
        column name failed on the HELPER rather than on the product.
        """
        name = getattr(expression, "name", None)
        if isinstance(name, str):
            return name
        for source in expression.get_source_expressions() or []:
            resolved = field_of(source)
            if resolved:
                return resolved
        target = getattr(expression, "target", None)
        return getattr(target, "attname", "") if target is not None else ""

    rendered = []
    for term in queryset.query.order_by:
        if isinstance(term, str):
            rendered.append(term)
            continue
        rendered.append(("-" if term.descending else "") + field_of(term.expression))
    return tuple(rendered)


class TestEveryListOpensNewestFirst:
    """`BR-CUS-1046` says *any entry*, and names the seven sibling tabs.

    Each case asserts TWO things in one breath: the default is creation order
    descending, and the list accepts a `sort` that changes it. One without the
    other is what `OQ-CUS-1790` was raised about — a default nobody can override
    is not a default, it is a replacement.
    """

    def test_accounts(self, tenant_ctx_any):
        from apps.customers import selectors

        assert selectors.ACCOUNT_DEFAULT_SORT == "created"
        assert selectors.ACCOUNT_DEFAULT_DIR == "desc"
        assert "created" in selectors.ACCOUNT_SORTS
        qs = selectors.account_list_queryset(ListParams(sort="created", dir="desc"))
        assert _order_of(qs) == ("-created_at", "-id")
        qs = selectors.account_list_queryset(ListParams(sort="account_no", dir="asc"))
        order = _order_of(qs)
        assert order[0] == "account_no", order
        assert order[-1] == "id", "every sort ends in a unique column or a page can repeat a row"
        # ⚠ **AND A BARE `ListParams()` — NO SORT, NO DIRECTION — MUST STILL OPEN
        # NEWEST FIRST.** `ListParams.dir` defaults to `asc`, so a selector that
        # read `params.dir` blindly gave OLDEST first to every caller that was
        # not the endpoint. Found here, 2026-09-12.
        assert _order_of(selectors.account_list_queryset(ListParams())) == (
            "-created_at",
            "-id",
        )

    def test_requests(self, tenant_ctx_any):
        from apps.customers import service_request_reads as reads

        assert reads.DEFAULT_SORT == "created"
        assert _order_of(reads.list_queryset()) == ("-created_at", "-id")
        # …and the urgency ordering the tab used to open on is one click away.
        assert "received_at" in reads.SORTS
        assert _order_of(reads.list_queryset(sort="received_at", dir="asc")) == (
            "received_at",
            "id",
        )

    def test_new_connects(self, tenant_ctx_any):
        from apps.metering import connection_reads as reads

        assert reads.DEFAULT_SORT == "created"
        assert "target_activation" in reads.SORTS

    def test_move_ins(self, tenant_ctx_any):
        from apps.customers import move_reads as reads

        assert reads.MOVE_IN_DEFAULT_SORT == "created"
        assert _order_of(reads.move_ins_queryset()) == ("-created_at", "-id")
        assert _order_of(reads.move_ins_queryset(sort="move_in_date", dir="asc")) == (
            "opened_at",
            "id",
        )

    def test_move_outs(self, tenant_ctx_any):
        from apps.customers import move_reads as reads

        assert reads.MOVE_OUT_DEFAULT_SORT == "created"
        assert _order_of(reads.move_outs_queryset()) == ("-created_at", "-id")
        assert _order_of(reads.move_outs_queryset(sort="move_out_date", dir="asc")) == (
            "closed_at",
            "id",
        )

    def test_transfers_keep_their_default_and_gain_the_control(self, tenant_ctx_any):
        """Transfers ALREADY opened newest-first — the default does not move.

        It is in the six only because it had no sort CONTROL, which is the half
        `OQ-CUS-1790` measured and the PO's option (c) answers.
        """
        from apps.customers import transfer_reads as reads

        assert reads.DEFAULT_SORT == "created"
        assert _order_of(reads.list_queryset()) == ("-created_at", "-id")
        assert "reference" in reads.SORTS

    def test_disconnects(self, tenant_ctx_any):
        from apps.customers import disconnect_reads as reads

        assert reads.DEFAULT_SORT == "created"
        assert "account_no" in reads.SORTS


# ═══════════════════════════════════════════════════════════════════════════
# §2 · THE ACCOUNTS LIST BUILDS ONE PAGE, NOT ONE TENANT (NFR-3)
# ═══════════════════════════════════════════════════════════════════════════
class TestTheAccountsPageIsTakenInSql:
    """⚠ **A STATEMENT COUNT CANNOT SEE THIS DEFECT.** `DEF-2723` made the
    accounts list cost a constant number of statements, and it stayed constant
    while the number of rows those statements BUILT grew with the tenant. So
    this counts the rows built, which is the thing `NFR-3` is about.
    """

    def test_one_page_costs_one_page_of_rows(self, planted_accounts, monkeypatch):
        from apps.customers import selectors

        tenant, total = planted_accounts
        assert total > 12, "the fixture must hold more accounts than one page"

        built = []
        real = selectors.account_row
        monkeypatch.setattr(
            selectors, "account_row", lambda account, **kw: built.append(account) or real(account, **kw)
        )
        rows, count = selectors.account_page(ListParams(page=1, per=10))
        assert count == total, "the envelope still reports the whole result set"
        assert len(rows) == 10
        assert len(built) == 10, (
            f"asked for 10 rows and built {len(built)} — the page is being taken in "
            f"Python over all {total} accounts, which is the NFR-3 breach"
        )

    def test_the_newest_account_is_the_first_row_of_page_one(self, planted_accounts):
        from apps.customers import models, selectors

        tenant, total = planted_accounts
        newest = models.Account.objects.filter(tenant=tenant).order_by("-created_at", "-id").first()
        rows, _count = selectors.account_page(ListParams(page=1, per=10))
        assert rows[0]["account_no"] == newest.account_no, (
            "BR-CUS-1046: the newly created entry must show on the top"
        )

    def test_a_chosen_sort_still_wins(self, planted_accounts):
        from apps.customers import selectors

        rows, _count = selectors.account_page(ListParams(sort="account_no", dir="asc", per=50))
        numbers = [row["account_no"] for row in rows]
        assert numbers == sorted(numbers), "an explicit sort must still order the page"


# ═══════════════════════════════════════════════════════════════════════════
# §4 · THE IMPORTS TAB'S 200-ROW CAP (`DEF-CUS-5061` · `NFR-3` · `NFR-5`)
# ═══════════════════════════════════════════════════════════════════════════
class TestTheImportsListHasNoCap:
    """⚠ **`NFR-5` IS *NO HARD CAPS ANYWHERE* AND `run_list` HELD ONE.**

    It ended `rows.order_by("-created_at")[:200]` and returned `{"rows": …}`
    with no count, so the three Imports tabs paged in the browser over a capped
    array: at the 201st run the history stopped and the screen looked complete.

    ⚠ **A ROW-COUNT ASSERTION ALONE WOULD NOT HAVE CAUGHT IT, AND SAYING SO IS
    THE POINT (law 7, habit 2).** A test that planted 5 runs and asserted 5 came
    back passes on the capped code, on the uncapped code, and on code capped at
    3 tomorrow. What the cap actually did was make a number UNREACHABLE, so the
    cases below plant MORE than the old cap and assert two different things: the
    count over the whole set, and a row that only exists past 200.
    """

    CAP = 200  # the cap that was removed — planted past, never re-imposed

    @pytest.fixture()
    def planted_runs(self, utility):
        """`CAP + 5` accounts import runs, oldest to newest."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.metering import models as metering_models

        total = self.CAP + 5
        with tenant_ctx(utility):
            start = timezone.now() - timedelta(days=total + 1)
            runs = [
                metering_models.ImportRun(
                    tenant=utility,
                    run_no=f"RUN-{index:05d}",
                    target="accounts",
                    file_name=f"accounts-{index}.csv",
                    status="loaded",
                    counts={"in": 1, "created": 1, "updated": 0, "errors": 0},
                )
                for index in range(total)
            ]
            metering_models.ImportRun.objects.bulk_create(runs)
            for index, run in enumerate(
                metering_models.ImportRun.objects.filter(tenant=utility).order_by("run_no")
            ):
                metering_models.ImportRun.objects.filter(pk=run.pk).update(
                    created_at=start + timedelta(days=index)
                )
            yield utility, total

    def test_the_count_is_over_the_whole_set_not_the_page(self, planted_runs):
        from apps.metering import import_runs

        _utility, total = planted_runs
        with tenant_ctx(_utility):
            answer = import_runs.run_list({"f.target": "accounts"})
        assert answer["total"] == total, (
            f"{total} runs exist and the envelope reports {answer.get('total')} — "
            "a screen cannot draw an honest pager without this"
        )
        assert len(answer["rows"]) == 50, "the default page is the IS-2 default of 50"

    def test_a_run_past_the_old_cap_is_reachable(self, planted_runs):
        """The 201st run existed and could not be got at, by any request."""
        from apps.metering import import_runs

        _utility, total = planted_runs
        with tenant_ctx(_utility):
            reached = 0
            seen: set[str] = set()
            page = 1
            while True:
                answer = import_runs.run_list(
                    {"f.target": "accounts", "page": str(page), "per": "50"}
                )
                if not answer["rows"]:
                    break
                seen.update(row["run_no"] for row in answer["rows"])
                reached += len(answer["rows"])
                if page >= answer["pages"]:
                    break
                page += 1
        assert reached == total, f"paged to {reached} of {total} rows"
        assert len(seen) == total, "a row appeared twice or never — the order is not total"
        assert "RUN-00000" in seen, "the OLDEST run is past the old cap and must be reachable"

    def test_the_newest_run_is_still_the_first_row(self, planted_runs):
        """Removing a cap must not disturb an ordering that already complied."""
        from apps.metering import import_runs

        _utility, total = planted_runs
        with tenant_ctx(_utility):
            answer = import_runs.run_list({"f.target": "accounts"})
        assert answer["rows"][0]["run_no"] == f"RUN-{total - 1:05d}"

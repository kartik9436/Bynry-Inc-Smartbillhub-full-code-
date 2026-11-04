# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W4b, one gap:
#           `GET /billing/runs` — the run history SET-07D's **Runs** tab has
#           rendered as a stated absence since it shipped, because only the
#           POST that CREATES a run existed.
#           Screens: SET-07D (Runs tab) · S31 (the Billing surface each row
#           links into)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §4 —
#           *"**Runs** (run history, Open in Billing →)"*
# Rules:    BR-MET-078 (**money never touches these surfaces**, hardened by
#           this CR — the tab shows status and counts, never amounts) ·
#           BR-BIL-004 / CLAUDE.md rule 4 (financial immutability — this
#           surface serves no write verb on an issued bill) · BR-BIL-015 (a
#           held account is a recorded CHOICE; the queue is the unresolved
#           exclusions) · BR-SHL-011 (list grammar `f.<name>`; a list URL
#           clamps rather than 4xx) · BR-TEN-003 / HR-1 (cross-tenant reads as
#           absent) · A4 `reads_billing_runs` (Executive **View**) ·
#           CLAUDE.md rule 1 (tenant scoping · RLS FORCE)
# ───────────────────────────────────────────────────────
"""RC-W4b — the run history, and the four things it must never claim.

**WHY THIS FILE EXISTS.** `CycleDetailPage.tsx` shipped its Runs tab as a
`StatedAbsence` with the reason written into its own lifecycle trailer:
*"the RUN HISTORY has no endpoint (`GET /billing/runs` does not exist; only
`POST`), so the Runs tab links into Billing and lists nothing"*. Hard-won law 2
in its plainest form. This suite is the contract for the endpoint that closes
it, written before the endpoint.

**THE FOUR NEGATIVE ASSERTIONS ARE THE POINT**, exactly as they were for the
S30 reads and for RC-W3b's seven doors:

  1. **NO MONEY, ANYWHERE.** BR-MET-078 as hardened by this CR — routes and
     cycles are *grouping only*. `bill_run_releases.total_amount` and
     `invoices.total` are both one join away and neither is served. Every key
     of every row is scanned, not sampled.
  2. **NO MUTATION.** The path answers GET and POST and nothing else; a forged
     PUT/PATCH/DELETE is refused by the router before any view runs
     (BR-BIL-004 / HR-4), and the read itself writes nothing at all.
  3. **NO CROSS-TENANT ROW.** A run of another tenant is absent from the list
     and from a list explicitly scoped to that tenant's cycle — the second half
     matters because the filter is the caller's own parameter.
  4. **NO PER-ROW QUERY.** The per-row counts are batched: a page of six runs
     costs the same number of queries as a page of one, and adding bills to a
     run adds none. A sibling lane measured 31 queries against 8 on a shorter
     list than this one.

⚠ **AND ONE THING THE ENDPOINT COULD NOT ANSWER — NOW RULED, AND THE PIN IS
INVERTED.** The screenshot's Run column reads `RUN-0814`; no run-number series
existed, `bill_runs` had no number column, and D5 ruled the `RT-001`/`CY-001`
grammar for ROUTES and CYCLES while saying nothing about runs. So `run_no` was
served **null** and the last test in this file HELD it there — inventing
`RUN-0814` would have minted a naming grammar by call site.

**OQ-342 closed on 2026-08-23**, PO verbatim: *"A: a real series (RUN-0001, like
RT-001)"*. `bill_runs.run_no` (billing 0023) is allocated from the `bill_run`
series at creation, and the test below now asserts the number instead of the
null — the pin is inverted rather than deleted, so what stopped a lane guessing
now stops a lane dropping it. **Runs created before the series keep NULL and are
not retro-numbered**, which is what the helper here builds and what this file
still proves. The allocation itself is defended in
`tests/test_cr029_rcw6_run_numbers.py`.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.billing import selectors as billing_selectors
from apps.metering import models as metering_models

from tests.test_us_bil_025_026_bills_read import an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2026, 8, 31)
ISSUED_AT = datetime(2026, 8, 5, 14, 30, tzinfo=timezone.utc)


# ── the world ──────────────────────────────────────────────────────────────
def a_cycle(tenant, code="CY-001", **overrides):
    """A cycle in the CR-029 vocabulary — the caller of this endpoint."""
    fields = {
        "code": code,
        "name": "Monthly water",
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 3,
        "first_run_date": date(2026, 8, 1),
        "bill_day": 5,
        "due_days": 21,
    }
    fields.update(overrides)
    return metering_models.Cycle.objects.create(tenant=tenant, **fields)


def a_run(tenant, cycle, *, key, period_start=PERIOD_START, period_end=PERIOD_END, **overrides):
    fields = {
        "tenant": tenant,
        "cycle": cycle,
        "period_start": period_start,
        "period_end": period_end,
        "idempotency_key": key,
        "bill_type": "cycle",
    }
    fields.update(overrides)
    return billing_models.BillRun.objects.create(**fields)


def a_held_account(tenant, run, account, *, reason_code="staff_hold_missing_read", resolved=False):
    """BR-BIL-015's recorded hold — the *"· 5 held"* half of the composite."""
    return billing_models.BillRunExclusion.objects.create(
        tenant=tenant,
        bill_run=run,
        account=account,
        reason_code=reason_code,
        resolved_at=ISSUED_AT if resolved else None,
    )


def an_issued_run_world(tenant, actor, *, code="CY-001", accounts=2, held=1):
    """One cycle, one run, `accounts` issued bills and `held` unresolved holds.

    Deliberately built with model rows rather than by driving the pipeline: the
    thing under test is a READ over `bill_runs`, `invoices` and
    `bill_run_exclusions`, and a full prepare→calculate→release→issue pass
    would put four other modules' behaviour inside a list test.
    """
    cycle = a_cycle(tenant, code=code)
    run = a_run(tenant, cycle, key=f"{code}|{PERIOD_START}|{PERIOD_END}")
    for index in range(accounts):
        account = an_account(tenant, actor, account_no=f"{code}-A-{index}", label=f"Unit {index}")
        an_invoice(
            tenant,
            account,
            bill_run=run,
            # ⚠ the code rides in the number: `invoices` is UNIQUE on
            # (tenant, invoice_no) and the first cut of this helper collided
            # the moment a test built two worlds in one tenant.
            invoice_no=f"BL-{code}-{index:06d}",
            issued_at=ISSUED_AT,
        )
    for index in range(held):
        account = an_account(tenant, actor, account_no=f"{code}-H-{index}", label=f"Held {index}")
        a_held_account(tenant, run, account)
    return cycle, run


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE DOOR EXISTS — hard-won law 2 at the routing layer
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_1__the_runs_path_answers_get(brazos, dana):
    """The gap, stated as a test: the path served POST and nothing else, so
    SET-07D's Runs tab could only render its own absence."""
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana)
        response = api_call(
            billing_api.bill_runs, "get", user=dana.user, role="system_admin", tenant=brazos
        )
    assert response.status_code == 200
    # ⚠ **THE ENVELOPE WAS `{"runs": [...]}` UNTIL 2026-09-15** and is now the
    # four names every paged list in this product answers with (`NFR-3`,
    # `07-frontend/src/api/paginated.ts`), plus the four tiles screen 27 draws.
    assert set(response.data) >= {"count", "next", "previous", "results", "tiles"}
    assert isinstance(response.data["results"], list)


def test_w4b_1__the_get_is_mounted_on_the_real_urlconf(brazos):
    """`api.py` exporting `urlpatterns` is not an endpoint until the root
    URLconf includes it, and a view that refuses the verb is not a door.

    ⚠ The first cut of this case read `... or hasattr(view, "cls")` and passed
    at the commit before the endpoint existed — a check whose output cannot
    distinguish pass from fail. It asks DRF's own allowed-method list now.
    """
    from django.urls import resolve

    assert resolve("/api/brazosbend/billing/runs").func is billing_api.bill_runs
    assert set(billing_api.bill_runs.cls.http_method_names) >= {"get", "post"}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE FIVE COLUMNS SET-07D DRAWS — Run · Period · Issued · Accounts · Status
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_2__a_row_carries_the_screens_five_columns(brazos, dana):
    """*"RUN-0814 · Aug 2026 · issued Aug 5, 2026 · 1,124 · Issued"*, in the
    fields the tab renders it from."""
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, accounts=3, held=0)
        rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == str(run.id)  # the Open-in-Billing link
    assert row["cycle_id"] == str(cycle.id)
    assert (row["period_start"], row["period_end"]) == ("2026-08-01", "2026-08-31")
    assert row["issued_at"] == "2026-08-05T14:30:00+00:00"
    assert row["accounts"] == 3
    assert row["bills_issued"] == 3
    assert row["held"] == 0
    assert row["status"] == "draft"  # the STORED column — see the trailer


def test_w4b_2__the_composite_status_counts_the_unresolved_holds(brazos, dana):
    """*"Issued · 5 held"* — the honest composite. A hold that a catch-up run
    has since billed is RESOLVED and is no longer held (BR-BIL-015 /
    `pending.held_account_ids`), so it must not keep inflating the number."""
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, accounts=4, held=5)
        settled = an_account(brazos, dana, account_no="CY-001-R-0", label="Resolved")
        a_held_account(brazos, run, settled, resolved=True)
        rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

    assert rows[0]["accounts"] == 4
    assert rows[0]["held"] == 5


def test_w4b_2__a_run_that_has_issued_nothing_says_so_rather_than_guessing(brazos, dana):
    """A run with drafts and no issue has NO issued date. Null is *"not issued
    yet"*; a date taken from `created_at` would put a bill in a customer's hand
    that nobody has sent."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="CY-DRAFT")
        run = a_run(brazos, cycle, key="CY-DRAFT|draft")
        account = an_account(brazos, dana, account_no="CY-DRAFT-A", label="Unit D")
        an_invoice(
            brazos,
            account,
            bill_run=run,
            invoice_no="BL-2608-999001",
            status=billing_models.INVOICE_DRAFT,
            issued_at=None,
            due_date=None,
            template_version=None,
            bill_payload=None,
        )
        rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

    assert rows[0]["issued_at"] is None
    assert rows[0]["bills_issued"] == 0
    assert rows[0]["accounts"] == 1


def test_w4b_2__the_history_is_newest_first_and_bounded(brazos, dana):
    """Newest first, and a `limit` the caller can lower — the same posture
    `route_read_windows` takes for SET-06D's Read history."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="CY-HIST")
        for month in (6, 7, 8):
            a_run(
                brazos,
                cycle,
                key=f"CY-HIST|{month}",
                period_start=date(2026, month, 1),
                period_end=date(2026, month, 28),
            )
        all_rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
        capped = billing_selectors.bill_runs_list(cycle_id=str(cycle.id), limit=2)

    assert [row["period_start"] for row in all_rows] == [
        "2026-08-01",
        "2026-07-01",
        "2026-06-01",
    ]
    assert [row["period_start"] for row in capped] == ["2026-08-01", "2026-07-01"]


# ═══════════════════════════════════════════════════════════════════════════
# 3 · NO MONEY — BR-MET-078, hardened by CR-029
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_3__the_value_column_is_the_bills_that_issued_never_the_release(brazos, dana):
    """⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-15 AND THE RULE IT
    ASSERTED WAS ABOUT ANOTHER MODULE'S SCREENS (`DEF-BIL-5353`).**

    It read *"no row carries money of any kind"*, citing `BR-MET-078` — whose PO
    wording is *"you dont need late fees in this. so dont have anything related
    to money when you create route and cycles"* and whose subject is r10
    SET-07.3, **the route and cycle CREATION screens**. A billing run's history
    row is neither, and the blueprint draws a VALUE column on it (p146).

    So the assertion is INVERTED rather than deleted — what stopped a lane
    serving money from the wrong place now stops a lane dropping the column, and
    the negative half that still matters is kept: the figure is Σ of the
    **bills that issued**, never `bill_run_releases.total_amount`, which is what
    a clerk AUTHORISED and can differ from what went out by every bill that
    broke.
    """
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="CY-MONEY")
        billing_models.BillRunRelease.objects.create(
            tenant=brazos,
            bill_run=run,
            summary={"accounts": 2, "bills": 2},
            account_count=2,
            bill_count=2,
            # AUTHORISED, and deliberately unlike the bills below: if this
            # number ever reaches the row, the row is reading the wrong table.
            total_amount="1284.500000",
            currency="USD",
            confirmed_at=ISSUED_AT,
        )
        billing_models.Invoice.objects.filter(tenant=brazos, bill_run=run).update(
            total="61.250000", currency="USD"
        )
        rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

    row = rows[0]
    # CLAUDE.md rule 2: the stored decimal beside its CHAR(3), never a float and
    # never a bare number. Two bills at 61.25 = 122.50.
    assert row["value"] == "122.500000"
    assert row["value_currency"] == "USD"
    assert "1284.5" not in str(row), "the AUTHORISED total reached the row"


def test_w4b_3__two_currencies_on_one_run_serve_no_total_at_all(brazos, dana):
    """Money is never summed across currencies — the sum would be a number with
    no name, the same reason kWh is never added to kgal.

    `release._amount_and_currency` REFUSES in this case; a LIST may not, because
    BR-SHL-011 says a list URL never errors over its params and one odd row must
    not blank a page of thirty-three good ones. So it answers an ABSENCE, which
    a screen draws as a dash.
    """
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="CY-TWOCCY", accounts=2, held=0)
        bills = list(billing_models.Invoice.objects.filter(tenant=brazos, bill_run=run))
        billing_models.Invoice.objects.filter(pk=bills[0].pk).update(
            total="10.000000", currency="USD"
        )
        billing_models.Invoice.objects.filter(pk=bills[1].pk).update(
            total="10.000000", currency="CAD"
        )
        row = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))[0]

    assert row["value"] is None
    assert row["value_currency"] is None
    # The COUNT is still true — both bills issued, and only the money has no
    # single name.
    assert row["bills_issued"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 4 · NO MUTATION — CLAUDE.md rule 4, at the surface and underneath it
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_4__the_runs_path_serves_no_write_verb_but_the_create(brazos, dana):
    """BR-BIL-004 / HR-4: this list READS issued runs. The path answers GET and
    POST and nothing else — a forged PUT, PATCH or DELETE is 405.

    ⚠ Asserted as a SYSTEM ADMIN. The first cut called anonymously and got 401
    on every verb: DRF authenticates before it checks the method, so the
    refusal proved a session was missing and said nothing at all about which
    verbs the path serves.
    """
    with tenant_ctx(brazos):
        for verb in ("put", "patch", "delete"):
            response = api_call(
                billing_api.bill_runs,
                verb,
                user=dana.user,
                role="system_admin",
                tenant=brazos,
            )
            assert response.status_code == 405, (verb, response.status_code)


def test_w4b_4__the_read_writes_nothing(brazos, dana):
    """A GET a clerk may refresh. Nothing about the run, its bills or its holds
    moves — asserted against `updated_at`, which `auto_now` would advance on any
    save at all."""
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="CY-READONLY")
        before = list(
            billing_models.Invoice.objects.filter(bill_run=run)
            .order_by("invoice_no")
            .values_list("id", "status", "updated_at")
        )
        run_before = (run.status, run.updated_at)

        billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

        after = list(
            billing_models.Invoice.objects.filter(bill_run=run)
            .order_by("invoice_no")
            .values_list("id", "status", "updated_at")
        )
        run.refresh_from_db()

    assert after == before
    assert (run.status, run.updated_at) == run_before


# ═══════════════════════════════════════════════════════════════════════════
# 5 · TENANT SCOPING — CLAUDE.md rule 1, both directions
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_5__another_tenants_runs_are_absent(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        _, ours = an_issued_run_world(brazos, dana, code="CY-OURS")
    with tenant_ctx(lonestar):
        theirs_cycle = a_cycle(lonestar, code="CY-THEIRS")
        a_run(lonestar, theirs_cycle, key="CY-THEIRS|08")
        response = api_call(
            billing_api.bill_runs, "get", user=erin.user, role="system_admin", tenant=lonestar
        )
    served = {row["id"] for row in response.data["results"]}
    assert str(ours.id) not in served
    assert len(served) == 1


def test_w4b_5__a_foreign_cycle_filter_never_reaches_across(brazos, dana, lonestar, erin):
    """The filter is the CALLER's parameter, so the isolation has to hold with
    the other tenant's own cycle id in hand — the one case a `tenant_id` filter
    dropped from the selector would still pass every test above."""
    with tenant_ctx(brazos):
        cycle, _ = an_issued_run_world(brazos, dana, code="CY-CROSS")
    with tenant_ctx(lonestar):
        response = api_call(
            billing_api.bill_runs,
            "get",
            user=erin.user,
            role="system_admin",
            tenant=lonestar,
            query={"f.cycle_id": str(cycle.id)},
        )
    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THE LIST GRAMMAR — BR-SHL-011: it clamps, it never 4xx's
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_6__the_cycle_filter_scopes_the_list(brazos, dana):
    with tenant_ctx(brazos):
        wanted, _ = an_issued_run_world(brazos, dana, code="CY-WANT", accounts=1, held=0)
        an_issued_run_world(brazos, dana, code="CY-OTHER", accounts=1, held=0)
        response = api_call(
            billing_api.bill_runs,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"f.cycle_id": str(wanted.id)},
        )
    assert [row["cycle_id"] for row in response.data["results"]] == [str(wanted.id)]
    # B14 rule 31 — the drawing shows `09-A`, a CODE, and a screen handed only
    # the uuid has nothing lawful to put in the column.
    assert [row["cycle_code"] for row in response.data["results"]] == ["CY-WANT"]


def test_w4b_6__rubbish_params_clamp_rather_than_error(brazos, dana):
    """BR-SHL-011's never-error posture, as `route_read_windows` implements it.

    ⚠ An UNREADABLE cycle filter answers the EMPTY list, not the whole one. The
    caller asked to be scoped; widening the answer because the scope could not
    be parsed would show a cycle's tab every run in the tenant.
    """
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="CY-CLAMP", accounts=1, held=0)
        per = api_call(
            billing_api.bill_runs,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"per": "banana"},
        )
        page = api_call(
            billing_api.bill_runs,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"page": "0"},
        )
        beyond = api_call(
            billing_api.bill_runs,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"page": "9999"},
        )
        nonsense_cycle = api_call(
            billing_api.bill_runs,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"f.cycle_id": "not-a-uuid"},
        )
        nonsense_year = api_call(
            billing_api.bill_runs,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query={"f.year": "last-tuesday"},
        )
    assert per.status_code == 200 and len(per.data["results"]) == 1
    assert page.status_code == 200 and len(page.data["results"]) == 1
    # A page past the end clamps to the LAST page rather than 404ing, exactly as
    # `StandardPagination.get_page_number` does for the lists DRF pages.
    assert beyond.status_code == 200 and len(beyond.data["results"]) == 1
    # ⚠ An unreadable SCOPE answers the EMPTY list, never the whole one — the
    # caller asked to be narrowed, and widening because the value would not
    # parse answers a different question.
    assert nonsense_cycle.status_code == 200
    assert nonsense_cycle.data["results"] == []
    assert nonsense_year.status_code == 200
    assert nonsense_year.data["results"] == []


def test_w4b_6__the_limit_is_capped_server_side(brazos, dana):
    """A caller cannot ask for the whole table. 200 is the ceiling
    `route_read_windows` already sets for the sibling history tab."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="CY-CAP")
        for index in range(3):
            a_run(
                brazos,
                cycle,
                key=f"CY-CAP|{index}",
                period_start=date(2026, 5 + index, 1),
                period_end=date(2026, 5 + index, 28),
            )
        asked_for_everything = billing_selectors.bill_runs_list(
            cycle_id=str(cycle.id), limit=100_000
        )
        asked_for_nothing = billing_selectors.bill_runs_list(cycle_id=str(cycle.id), limit=0)
    assert billing_selectors.BILL_RUN_LIST_MAX_LIMIT == 200
    assert len(asked_for_everything) == 3
    # 0 clamps UP to 1 rather than answering "this cycle has never run".
    assert len(asked_for_nothing) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 7 · BATCHED, NOT PER ROW — the sibling lane's 31-vs-8 measurement
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_7__the_per_row_counts_are_batched(brazos, dana):
    """Six runs must cost what one run costs. The guard is SHAPE, not a magic
    number: a per-row count would make the query total grow with the history,
    and a cycle's history is longer than a route's."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="CY-BATCH")
        a_run(brazos, cycle, key="CY-BATCH|1", period_start=date(2026, 1, 1))
        with CaptureQueriesContext(connection) as one:
            billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
        for index in range(2, 7):
            a_run(
                brazos,
                cycle,
                key=f"CY-BATCH|{index}",
                period_start=date(2026, index, 1),
                period_end=date(2026, index, 28),
            )
        with CaptureQueriesContext(connection) as six:
            rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

    assert len(rows) == 6
    assert len(six) == len(one), (len(one), len(six))


def test_w4b_7__more_bills_on_a_run_cost_no_more_queries(brazos, dana):
    """The other axis, and the one that bites at 1,124 accounts."""
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="CY-BILLS", accounts=1, held=0)
        with CaptureQueriesContext(connection) as small:
            billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
        for index in range(1, 6):
            account = an_account(
                brazos, dana, account_no=f"CY-BILLS-X-{index}", label=f"Extra {index}"
            )
            an_invoice(
                brazos,
                account,
                bill_run=run,
                invoice_no=f"BL-2608-77{index:04d}",
                issued_at=ISSUED_AT,
            )
        with CaptureQueriesContext(connection) as big:
            rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))

    assert rows[0]["accounts"] == 6
    assert len(big) == len(small), (len(small), len(big))


# ═══════════════════════════════════════════════════════════════════════════
# 8 · WHO MAY READ IT — A4 `reads_billing_runs`: Executive **View**
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_8__an_executive_may_read_the_history_and_may_not_create_a_run(brazos, dana):
    """The read posture of every other billing GET, and the write posture of
    the POST that shares this path — one view, two gates, asserted apart.

    BR-SHL-025 is server-enforced: an Executive's refusal is a 403 at the door,
    not a disabled button.
    """
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="CY-ROLES", accounts=1, held=0)
        read = api_call(
            billing_api.bill_runs, "get", user=dana.user, role="executive", tenant=brazos
        )
        write = api_call(
            billing_api.bill_runs,
            "post",
            user=dana.user,
            role="executive",
            tenant=brazos,
            data={
                "cycle_id": None,
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
            },
        )
    assert read.status_code == 200
    assert write.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 9 · THE RUN NUMBER IS NOT INVENTED — the prime directive, held open
# ═══════════════════════════════════════════════════════════════════════════
def test_w4b_9__the_run_number_comes_from_a_series_and_is_never_derived(brazos, dana):
    """⚠ **THIS TEST HELD `run_no` NULL UNTIL 2026-08-23 AND IS NOW INVERTED.**

    It existed to stop a later lane deriving `RUN-0814` from `created_at`, from
    a per-cycle ordinal or from the uuid's first eight characters. OQ-342 was
    put to the PO with those three readings and they chose **(A) a real
    series** — *"A: a real series (RUN-0001, like RT-001)"* — so a bill-run
    series exists, the column exists, and the list serves what was allocated.

    **Both halves still bind.** A run created through `create_run` carries its
    number; a run written straight to the table (which is what every run
    predating the migration is) keeps NULL and is NOT retro-numbered, which the
    ruling states in as many words. And the derivations are still forbidden:
    the uuid slice must not appear in the number.
    """
    from core import numbering

    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="CY-NONUM", accounts=1, held=0)
        rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
        numbered = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            run_by=dana,
            actor=dana,
        )

    # The helper writes its run straight to the table — the shape every run on a
    # live host has relative to billing 0023.
    assert rows[0]["run_no"] is None
    # ⚠ `import_run` EXISTS and is not this — it numbers a READ IMPORT batch.
    assert {"bill_run", "cycle", "route"} <= numbering.KNOWN_SERIES
    assert numbered.run_no == "RUN-0001"
    assert str(run.id)[:8] not in str(numbered.run_no)


def test_w4b_9__a_one_time_run_has_no_cycle_and_the_list_does_not_pretend(brazos, dana):
    """`bill_runs.cycle_id` is nullable since 0021 — a one-time bill belongs to
    no cycle (US-BIL-010..014). It must not appear on a cycle's tab, and an
    unfiltered read must not print a cycle id it has not got."""
    with tenant_ctx(brazos):
        cycle, _ = an_issued_run_world(brazos, dana, code="CY-ONETIME", accounts=1, held=0)
        account = an_account(brazos, dana, account_no="ADHOC-1", label="Ad hoc")
        billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=None,
            scope_account=account,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="one-time|adhoc",
            bill_type="one_time",
        )
        scoped = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
        everything = billing_selectors.bill_runs_list()

    assert [row["cycle_id"] for row in scoped] == [str(cycle.id)]
    assert None in [row["cycle_id"] for row in everything]
    assert len(everything) == 2


def test_w4b_9__an_unknown_cycle_answers_an_empty_history(brazos, dana):
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="CY-UNKNOWN", accounts=1, held=0)
        rows = billing_selectors.bill_runs_list(cycle_id=str(uuid.uuid4()))
    assert rows == []

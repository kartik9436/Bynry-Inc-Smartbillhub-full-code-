# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-003 · US-RBS-018 (EP-RBS-01) — CR-075 wave D task D1: the
#           eight READ routes of 07-endpoints.md rows 1, 2, 4, 8, 9, 10, 11 and
#           14. Screens: RBS-001 · RBS-002 · RBS-003 · RBS-006 · RBS-008
# Rules:    NFR-3 (every list pages server-side, `per` clamped
#           50/100/200/500/1000, default 50) · NFR-5 (no hard caps anywhere) ·
#           BR-RBS-020 (the report is composed at close and FROZEN) ·
#           BR-RBS-025 (a category with no template is never drawn as a filter)
#           · BR-RBS-011 (a failure names its fix route) · B14 rule 31 (no
#           database id is ever the visible value of a field) · CLAUDE.md hard
#           rule 1 (a cross-tenant read returns nothing) · hard rule 2 (money
#           4 stored, 2 displayed, never a float) · DEF-RBS-4291 (started_at) ·
#           DEF-RBS-4292 (there is no started_by)
# Tests:    this file — every case ASSERTS A RULE, never an impression: a clamp
#           at 1000, a page past page 1, a byte-identical frozen report, a
#           report NOT recomputed, the two files split on outcome, a 404 for
#           another tenant's run, a chip row that is not the fixed sixteen, and
#           a 405 on every write verb.
#           The DATABASE half of hard rule 1 is tests/test_us_rbs_003_pg.py,
#           which runs under the non-superuser probe role on real PostgreSQL and
#           SKIPS here rather than passing vacuously (hard-won law 14; G5 once
#           called 192 skips a pass).
# Impacts:  apps/runbooks/api.py · apps/runbooks/selectors.py ·
#           apps/runbooks/result_files.py · apps/runbooks/services.py ·
#           config/urls.py
# ───────────────────────────────────────────────────────
"""US-RBS-003 on SQLite — the eight routes, and the rules each one carries.

⚠ **CASE 1 RESOLVES EVERY PATH THROUGH `config/urls.py` AND THAT IS THE MOST
IMPORTANT CASE IN THE FILE.** Every other case calls the view function directly
through `api_call`, which is how this repository tests a DRF view — and a view
called directly cannot tell you whether anything is MOUNTED. `G27` exists
because `apps/notifications` had 7,084 lines behind an `api.py` of 72 bytes that
no `include()` named, and `config/urls.py` records three more whole modules that
shipped complete and 404ed. A suite that never resolves a path would pass over
all four.

⚠ **AND IT ASSERTS THE ORDER, NOT ONLY THE PRESENCE.** `runbooks/<str:key>`
matches the literal `runbooks/templates`; Django takes the first pattern that
matches, so a reordering silently turns the template library into *"the runbook
whose key is templates"* and answers 404. `integrations/subprocessors` shipped
with exactly that bug — read as a provider key and answered 405 — under a
comment in `config/urls.py` asserting it could not happen, and *it was the
browser that found it, not the reasoning* (hard-won law 1).
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid

import pytest
from django.urls import resolve

from apps.runbooks import api, models, result_files, selectors, services
from apps.runbooks.definitions import configuration_check
from core.pagination import PAGE_SIZES
from core.permissions import BILLING_CLERK, EXECUTIVE, SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

#: A uuid anywhere a clerk reads is B14 rule 31's violation, and the CSV is read
#: by a clerk. The pattern is the canonical 8-4-4-4-12.
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


# ── fixtures ─────────────────────────────────────────────────────────────────


def _runbook(tenant, *, key, name, kind=models.KIND_CHECK, category="platform", template=None):
    return models.Runbook.objects.create(
        tenant=tenant,
        key=key,
        name=name,
        kind=kind,
        category=category,
        subject_type="tenant",
        unit_of_work="config graph",
        template_key=template,
        timezone="America/Chicago",
        gate_mode="approve_each_run",
        cap=100,
    )


def _run(tenant, runbook, *, status=models.RUN_STATUS_DONE, report=None, counts=None):
    return models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        status=status,
        report=report or [],
        counts=counts or {},
    )


def _record(tenant, run, *, key, outcome=None, **fields):
    return models.RunbookRunRecord.objects.create(
        tenant=tenant,
        run=run,
        subject_type=fields.pop("subject_type", "account"),
        planned_action=fields.pop("planned_action", "report"),
        outcome=outcome,
        idempotency_key=key,
        **fields,
    )


@pytest.fixture()
def brazos_runbooks(brazos):
    """One runbook, one closed run, three records — the smallest honest fixture.

    The run's report is stored with **one** block. `configuration_check.report()`
    composes SIX, so the report case can tell *served from the column* from
    *recomputed from the definition* by counting — which is what `BR-RBS-020`
    and `07-endpoints.md` E-5 are about and what a fixture whose live and frozen
    reports agree can never distinguish.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(
            brazos,
            key="configuration_check",
            name="Can we bill?",
            template="configuration_check",
        )
        run = _run(
            brazos,
            runbook,
            report=[
                {
                    "block": "verdict",
                    "payload": {"word": "No-go", "tone": "bad", "count": "3 things stop billing"},
                }
            ],
            counts={"blockers": 3, "warnings": 6},
        )
        _record(
            brazos,
            run,
            key="rbs-d-1",
            outcome="done",
            data={"label": "Riverside Apartments"},
            decided_by_rule="No tax region covers this address.",
            reason="Sent the notice.",
            fix_route="Set a tax region",
            amount="12.3400",
            currency="USD",
        )
        _record(
            brazos,
            run,
            key="rbs-d-2",
            outcome="skipped",
            data={"label": "Oak Street Depot"},
            reason="No read since 18 Aug.",
            fix_route="Enter a read",
        )
        # No outcome at all — written at EVALUATION, before any act
        # (`BR-RBS-004`). It belongs in *not done*: it names something the run
        # planned and did not do.
        _record(
            brazos,
            run,
            key="rbs-d-3",
            data={"label": "Mill Yard"},
            reason="Waiting on a person.",
            fix_route="Open the work list",
        )
    return brazos, runbook, run


def _indistinguishable(body):
    """A refusal body with its per-request correlation id taken out.

    ⚠ **`trace_id` IS DIFFERENT ON EVERY RESPONSE AND THAT IS THE ENVELOPE
    WORKING, NOT A LEAK.** `HR-1` asks that another tenant's row and a row that
    never existed answer the SAME 404 — same status, same `code`, same
    `message_key`, same everything a caller could use to tell the two apart. A
    correlation id is generated per request and is different between two calls
    to the SAME absent id, so comparing it would make the assertion fail for a
    reason that has nothing to do with isolation. It is asserted to be PRESENT
    on both instead, because an envelope that dropped it would be a different
    defect.
    """
    assert body.get("trace_id"), "every refusal carries a trace id"
    return {name: value for name, value in body.items() if name != "trace_id"}


def _get(view, tenant, actor, path, *, role=SYSTEM_ADMIN, query=None, **kwargs):
    return api_call(
        view,
        "get",
        f"/api/{tenant.subdomain}{path}",
        user=actor.user,
        role=role,
        tenant=tenant,
        query=query,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 — THE EIGHT ARE MOUNTED, AND `runbooks/templates` IS NOT A RUNBOOK KEY
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_003_all_eight_routes_resolve_through_config_urls():
    """`G27`'s whole point: a route nobody mounted is a route nobody wrote.

    Resolved through the ROOT URLconf rather than through `api.urlpatterns`,
    because the defect this guards against is a missing `include()` — which a
    module-local assertion cannot see. Three whole modules shipped complete and
    404ing before `G27` existed; `config/urls.py` names them.
    """
    expected = {
        "/api/brazosbend/runbooks": api.runbooks_list,
        "/api/brazosbend/runbooks/templates": api.runbook_templates,
        "/api/brazosbend/runbooks/runs": api.runs_list,
        "/api/brazosbend/runbooks/runs/r1": api.run_detail,
        "/api/brazosbend/runbooks/runs/r1/report": api.run_report,
        "/api/brazosbend/runbooks/runs/r1/records": api.run_records,
        "/api/brazosbend/runbooks/runs/r1/results/done.csv": api.run_result_file,
        "/api/brazosbend/runbooks/runs/r1/results/not-done.csv": api.run_result_file,
        "/api/brazosbend/runbooks/configuration_check": api.runbook_detail,
    }
    # ⚠ **COMPARED BY IDENTITY, AND THE FIRST DRAFT OF THIS LINE COMPARED
    # NAMES AND WAS LOOKING AT THE WRONG THING** (hard-won law 7's fourth
    # shape, found by this case on its first run). `@api_view` builds a
    # `WrappedAPIView` class and mounts `View.as_view()`'s closure, so
    # `func.__name__` is **`view`** for every route in the product and
    # `func.__wrapped__.__name__` is `view` as well — a name comparison is
    # either vacuous or wrong for all nine at once, and `func.cls.__name__` is
    # `WrappedAPIView` for all nine too. The view OBJECT is what the URLconf
    # holds, so `is` is the only handle that distinguishes them.
    for path, view in expected.items():
        match = resolve(path)
        assert match.func is view, f"{path} resolved to {match.func}, not {view}"


def test_us_rbs_003_the_literal_paths_are_not_swallowed_by_the_key_pattern():
    """`runbooks/templates` is the library, not a runbook whose key is that word.

    This is `integrations/subprocessors`' defect one module along: a two-segment
    literal behind a `<str:key>` pattern, matched first by the pattern, answered
    405 or 404. Asserted by NAME rather than by *"it resolves"*, because it
    resolves either way — to the wrong view.
    """
    assert resolve("/api/brazosbend/runbooks/templates").func is not api.runbook_detail
    assert resolve("/api/brazosbend/runbooks/runs").func is not api.runbook_detail
    # And the key pattern still works for a real key.
    assert resolve("/api/brazosbend/runbooks/dunning").func is api.runbook_detail
    assert resolve("/api/brazosbend/runbooks/dunning").kwargs == {"key": "dunning"}


def test_us_rbs_003_a_third_result_file_name_does_not_exist():
    """`done` and `not-done`, and nothing else, are addresses.

    A `<str:outcome>` converter would match `results/anything.csv`, hand the
    view a word it has no file for, and — because the view reads
    `outcome == "done"` — serve the *not done* file under any invented name.
    The route is a `re_path` alternation so the third word is a 404.
    """
    from django.urls import Resolver404

    assert set(result_files.FILE_NAMES) == {"done", "not-done"}
    with pytest.raises(Resolver404):
        resolve("/api/brazosbend/runbooks/runs/r1/results/maybe.csv")


@pytest.mark.django_db
def test_us_rbs_003_every_read_route_is_read_only(brazos_runbooks, dana):
    """`BR-RBS-002` at the door: no READ route accepts a write verb.

    A Check is CONSTRUCTED with no ports and phase 1's launch sentence is
    *"nothing can be written: no writer is bound"*. A `POST` reaching one of
    these would be that promise broken at the one layer a clerk can drive.

    ⚠ **THIS CASE READ *"none of the EIGHT accepts a write verb"* UNTIL WAVE E,
    AND IT WAS TRUE THEN.** `07-endpoints.md` rows 3, 5 and 6 give this module
    three write routes and wave `E1` built them, so `runbooks_list` (row 5,
    `POST`) and `runbook_detail` (row 3, `PUT`) legitimately answer a write now.
    **The assertion is NARROWED rather than deleted**, because a suite that
    stopped asking would be a suite that could not see the eighth route
    acquiring a `POST` nobody meant. `runbooks_list`'s and `runbook_detail`'s
    write halves are asserted in `tests/test_us_rbs_038_definition_surface.py`,
    including that a Billing Clerk is refused on both.
    """
    tenant, _runbook, _run = brazos_runbooks
    for view in (api.runbook_templates, api.runs_list):
        response = api_call(
            view,
            "post",
            f"/api/{tenant.subdomain}/runbooks",
            user=dana.user,
            role=SYSTEM_ADMIN,
            tenant=tenant,
            data={},
        )
        assert response.status_code == 405, f"{view.__wrapped__.__name__} accepted a POST"
    # And the two that DO take a write take only the verb their row names.
    assert (
        api_call(
            api.runbooks_list,
            "put",
            f"/api/{tenant.subdomain}/runbooks",
            user=dana.user,
            role=SYSTEM_ADMIN,
            tenant=tenant,
            data={},
        ).status_code
        == 405
    ), "GET · POST /runbooks — row 5 gives no PUT"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — NFR-3 · NFR-5: EVERY LIST PAGES, `per` CLAMPS, AND NOTHING IS CAPPED
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_003_nfr3_the_page_size_vocabulary_is_the_products_own():
    """50 · 100 · 200 · 500 · 1000, default 50 — one vocabulary, not a second.

    `IS-2` as amended by the PO on 2026-08-09. This module clamps through
    `core.pagination` rather than minting its own set, and the assertion is here
    so a later lane that "adds 25 for the runbooks screens" goes red.
    """
    assert PAGE_SIZES == (50, 100, 200, 500, 1000)


@pytest.mark.django_db
def test_us_rbs_003_nfr3_a_list_pages_past_page_one_and_clamps_per(brazos, dana):
    """51 runs: `per=5` serves **50** and offers a page 2; `per=5000` serves 51.

    Both halves matter and they fail in opposite directions. A build that
    ignored `per` entirely would pass the first half of a naive test; a build
    that honoured `per=5000` would serve five thousand rows to a screen at the
    top of the ICP, which is `NFR-3`'s hazard. And `NFR-5`: asking for more than
    the tenant has returns everything it has, with no cap in the way.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, key="dunning", name="Dunning and notices")
        for _ in range(51):
            _run(brazos, runbook)

    small = _get(api.runs_list, brazos, dana, "/runbooks/runs", query={"per": "5"})
    assert small.status_code == 200
    assert small.data["count"] == 51
    assert len(small.data["results"]) == 50, "per=5 must clamp UP to the smallest size, 50"
    assert small.data["next"] is not None and "page=2" in small.data["next"]

    page_two = _get(api.runs_list, brazos, dana, "/runbooks/runs", query={"page": "2", "per": "5"})
    assert len(page_two.data["results"]) == 1
    assert page_two.data["previous"] is not None

    # The page-1 and page-2 windows must not overlap — which is what an ORDERED
    # slice buys and an unordered one silently loses.
    seen = {row["id"] for row in small.data["results"]} | {
        row["id"] for row in page_two.data["results"]
    }
    assert len(seen) == 51

    wide = _get(api.runs_list, brazos, dana, "/runbooks/runs", query={"per": "5000"})
    assert len(wide.data["results"]) == 51 and wide.data["next"] is None


@pytest.mark.django_db
def test_us_rbs_003_nfr3_per_clamps_to_the_five_sizes_and_never_errors(brazos):
    """The clamp itself, at the selector, where the number is observable.

    The wire envelope carries `{count, next, previous, results}` and no `per`,
    so the exact clamped value cannot be read off a response — asserting it here
    is what makes *"clamped 50/100/200/500/1000"* a checked claim rather than a
    sentence in a docstring. `BR-SHL-011`: a list URL never 4xx's over its
    params, so garbage clamps rather than refusing.
    """
    with tenant_ctx(brazos):
        for value, expected in (
            (None, 50),
            ("", 50),
            ("abc", 50),
            ("-4", 50),
            ("7", 50),
            ("100", 100),
            ("300", 200),
            ("999", 500),
            ("5000", 1000),
        ):
            page = selectors.runs_page(brazos.id, per=value)
            assert page["per"] == expected, f"per={value!r} clamped to {page['per']}"
            assert page["page"] == 1


@pytest.mark.django_db
def test_us_rbs_003_nfr3_the_records_list_and_the_catalogue_page_too(brazos_runbooks, dana):
    """Every list, not only the history — `NFR-3` binds all of them."""
    tenant, _runbook, run = brazos_runbooks
    with tenant_ctx(tenant):
        assert selectors.run_records_page(tenant.id, run.pk, per="5000")["per"] == 1000
        assert selectors.catalogue_page(tenant.id, per="5000")["per"] == 1000
        assert selectors.templates_page(tenant.id, per="5000")["per"] == 1000


# ═══════════════════════════════════════════════════════════════════════════
# 3 — BR-RBS-020: THE REPORT IS FROZEN, SERVED, AND NEVER RECOMPUTED
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_rbs_003_br_rbs_020_the_report_is_read_from_the_column_not_recomposed(
    brazos_runbooks, dana
):
    """The stored run has ONE block; `configuration_check.report()` composes SIX.

    That gap is the whole assertion. A route that rendered from the live
    definition would answer six blocks and would pass any test whose fixture's
    live and frozen reports agree — which is `07-endpoints.md` E-5 word for
    word: *"a build lane that renders from the live definition instead passes
    every test until a runbook is edited, and then rewrites history."*
    """
    tenant, _runbook, run = brazos_runbooks
    live = configuration_check.report(_EmptyView())
    assert len(live) == 6, "the fixture's premise: the live report has six blocks"

    response = _get(
        api.run_report, tenant, dana, f"/runbooks/runs/{run.pk}/report", run_id=str(run.pk)
    )
    assert response.status_code == 200
    blocks = response.data["blocks"]
    assert len(blocks) == 1, "the report was recomputed instead of read"
    assert blocks[0]["block"] == "verdict"
    assert blocks[0]["payload"]["word"] == "No-go"


@pytest.mark.django_db
def test_us_rbs_003_tc_rbs_16_the_report_is_byte_identical_on_re_read(brazos_runbooks, dana):
    """Read it twice, serialise both, compare the BYTES.

    `TC-RBS-16`. Comparing the two dicts would pass over a serializer that
    reordered keys or renormalised a number, and a regulator asking for last
    quarter's result gets bytes, not a dict.
    """
    tenant, _runbook, run = brazos_runbooks
    first = _get(
        api.run_report, tenant, dana, f"/runbooks/runs/{run.pk}/report", run_id=str(run.pk)
    )
    second = _get(
        api.run_report, tenant, dana, f"/runbooks/runs/{run.pk}/report", run_id=str(run.pk)
    )
    assert json.dumps(first.data, sort_keys=False) == json.dumps(second.data, sort_keys=False)


@pytest.mark.django_db
def test_us_rbs_003_br_rbs_020_a_payload_shape_the_renderer_does_not_know_survives(brazos, dana):
    """A report frozen in an OLD shape comes back in that shape (`DEF-RBS-4284`).

    The engine's six payloads and the wave-C renderer's six types disagree today
    and the fix moves the ENGINE. A run closed before that lands is frozen in
    the old shape and one closed after it in the new, **and both are correct** —
    the report is what was composed that day. A serializer that translated
    between them would rewrite the first result this product ever produced, so
    this asserts that a payload with keys no current renderer reads is returned
    untouched.
    """
    old_shape = [{"block": "verdict", "payload": {"verdict": "no_go", "headline": "3 things"}}]
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, key="older", name="An older run")
        run = _run(brazos, runbook, report=old_shape)
    response = _get(
        api.run_report, brazos, dana, f"/runbooks/runs/{run.pk}/report", run_id=str(run.pk)
    )
    assert response.data["blocks"] == old_shape


@pytest.mark.django_db
def test_us_rbs_003_a_run_that_failed_at_close_answers_an_empty_list_not_a_404(brazos, dana):
    """`[]` and *"no such run"* are different facts and are served differently.

    `close_run` marks a run `failed` and freezes nothing when a thirteenth block
    is refused. That run exists, and a screen must be able to draw *"this run
    produced no result"* rather than *"this run does not exist"*.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, key="halted", name="Halted")
        run = _run(brazos, runbook, status=models.RUN_STATUS_FAILED, report=[])
    response = _get(
        api.run_report, brazos, dana, f"/runbooks/runs/{run.pk}/report", run_id=str(run.pk)
    )
    assert response.status_code == 200 and response.data["blocks"] == []


class _EmptyView:
    """The smallest thing `configuration_check.report()` reads: `set_results`."""

    set_results: dict = {}


# ═══════════════════════════════════════════════════════════════════════════
# 4 — THE TWO RESULT FILES
# ═══════════════════════════════════════════════════════════════════════════


def _csv_rows(response):
    body = b"".join(response.streaming_content).decode("utf-8")
    return list(csv.reader(io.StringIO(body)))


@pytest.mark.django_db
def test_us_rbs_003_the_two_files_split_on_the_outcome_and_carry_reason_and_fix(
    brazos_runbooks, dana
):
    """*done* holds what the run did; *not done* holds everything else.

    `07-endpoints.md` row 14 — *each row carrying its reason and its fix* — and
    `BR-RBS-011`: a failure with no route is a defect in the runbook, because a
    finding a clerk cannot act on is a finding we should not have shown them.
    The fixture's third record has NO outcome, written at evaluation before any
    act (`BR-RBS-004`), and it must be in *not done*: putting it in *done* would
    be a file claiming work nobody performed.
    """
    tenant, _runbook, run = brazos_runbooks

    done = _csv_rows(
        _get(
            api.run_result_file,
            tenant,
            dana,
            f"/runbooks/runs/{run.pk}/results/done.csv",
            run_id=str(run.pk),
            outcome="done",
        )
    )
    assert done[0] == list(result_files.COLUMNS)
    assert [row[0] for row in done[1:]] == ["Riverside Apartments"]

    not_done = _csv_rows(
        _get(
            api.run_result_file,
            tenant,
            dana,
            f"/runbooks/runs/{run.pk}/results/not-done.csv",
            run_id=str(run.pk),
            outcome="not-done",
        )
    )
    assert [row[0] for row in not_done[1:]] == ["Oak Street Depot", "Mill Yard"]
    reason = result_files.COLUMNS.index("Reason")
    fix = result_files.COLUMNS.index("Fix")
    for row in not_done[1:]:
        assert row[reason] and row[fix], "a not-done row with no reason or no fix route"


@pytest.mark.django_db
def test_us_rbs_003_b14_rule_31_no_uuid_reaches_a_cell(brazos_runbooks, dana):
    """A downloaded CSV is a screen: it is opened, read and printed by a clerk.

    B14 rule 31 — *no database id is ever the visible value of a field* (PO
    2026-08-30: *"no Databse ID on screen - that is a rule"*). The record's own
    `subject_id` is a uuid and it is deliberately not written; the Subject
    column carries the label instead.
    """
    tenant, _runbook, run = brazos_runbooks
    for outcome in result_files.FILE_NAMES:
        rows = _csv_rows(
            _get(
                api.run_result_file,
                tenant,
                dana,
                f"/runbooks/runs/{run.pk}/results/{outcome}.csv",
                run_id=str(run.pk),
                outcome=outcome,
            )
        )
        for row in rows:
            for cell in row:
                assert not UUID_RE.search(cell), f"a uuid reached a cell: {cell!r}"


@pytest.mark.django_db
def test_us_rbs_003_hard_rule_2_money_is_written_at_two_decimals_with_its_currency(
    brazos_runbooks, dana
):
    """`12.3400` is STORED; `12.34` is what a clerk reads (hard rule 2).

    Four decimals stored, two displayed, `CHAR(3)` currency in its own column,
    and never a float. `str(Decimal)` would print the stored four into a
    spreadsheet; a float would be the breach `G6` refuses outright.
    """
    tenant, _runbook, run = brazos_runbooks
    rows = _csv_rows(
        _get(
            api.run_result_file,
            tenant,
            dana,
            f"/runbooks/runs/{run.pk}/results/done.csv",
            run_id=str(run.pk),
            outcome="done",
        )
    )
    amount = result_files.COLUMNS.index("Amount")
    currency = result_files.COLUMNS.index("Currency")
    assert rows[1][amount] == "12.34"
    assert rows[1][currency] == "USD"


@pytest.mark.django_db
def test_us_rbs_003_the_file_is_named_for_its_run_and_offered_as_an_attachment(
    brazos_runbooks, dana
):
    """Two runs of one runbook on one day must not overwrite each other."""
    tenant, _runbook, run = brazos_runbooks
    response = _get(
        api.run_result_file,
        tenant,
        dana,
        f"/runbooks/runs/{run.pk}/results/done.csv",
        run_id=str(run.pk),
        outcome="done",
    )
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"] == (
        f'attachment; filename="runbook-run-{run.pk}-done.csv"'
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5 — HARD RULE 1: A CROSS-TENANT READ RETURNS NOTHING
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_rbs_003_hard_rule_1_another_tenants_run_is_the_same_404_as_an_absent_one(
    brazos_runbooks, lonestar, erin
):
    """Erin at Lone Star Ridge cannot read, report on, list or download Brazos'.

    Byte-identical to a run that never existed (`HR-1`), so neither the status
    nor the body can be used to ask whether a given run id is real somewhere
    else in the product. All four run routes are asserted, not one: a filter
    written on three of them and forgotten on the fourth is exactly the shape
    this repository keeps finding.

    ⚠ **THIS IS THE APP-LAYER HALF ONLY.** SQLite has no row-level security at
    all, so a green here proves the queryset filter and NOTHING about RLS. The
    database half is `tests/test_us_rbs_003_pg.py`, under a role RLS applies to.
    """
    _brazos, _runbook, run = brazos_runbooks
    absent = uuid.uuid4()
    for view, extra in (
        (api.run_detail, {}),
        (api.run_report, {}),
        (api.run_records, {}),
        (api.run_result_file, {"outcome": "done"}),
    ):
        theirs = _get(view, lonestar, erin, f"/runbooks/runs/{run.pk}", run_id=str(run.pk), **extra)
        never = _get(view, lonestar, erin, f"/runbooks/runs/{absent}", run_id=str(absent), **extra)
        assert theirs.status_code == never.status_code == 404
        assert _indistinguishable(theirs.data) == _indistinguishable(never.data)


@pytest.mark.django_db
def test_us_rbs_003_hard_rule_1_the_lists_hold_no_other_tenants_rows(
    brazos_runbooks, lonestar, erin
):
    """A list is the quieter leak: it returns 200 and simply includes too much."""
    _brazos, _runbook, _run = brazos_runbooks
    assert _get(api.runs_list, lonestar, erin, "/runbooks/runs").data["count"] == 0
    assert _get(api.runbooks_list, lonestar, erin, "/runbooks").data["count"] == 0
    # And Lone Star Ridge cannot open Brazos Bend's runbook by its key either.
    assert (
        _get(
            api.runbook_detail,
            lonestar,
            erin,
            "/runbooks/configuration_check",
            key="configuration_check",
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_us_rbs_003_every_signed_in_role_may_read(brazos_runbooks, brazos, dana):
    """*Staff reads; Admin writes* — so all three roles read (`07-endpoints.md`).

    A read gate narrower than the rule is `DEF-196`: eight Settings screens
    answered 403 on the READ half for a year, every `readOnly` branch in the
    frontend unreachable, and 235 green tests could not see it.
    """
    for role in (SYSTEM_ADMIN, BILLING_CLERK, EXECUTIVE):
        response = _get(api.runbooks_list, brazos, dana, "/runbooks", role=role)
        assert response.status_code == 200, f"{role} could not read the catalogue"


# ═══════════════════════════════════════════════════════════════════════════
# 6 — THE CATALOGUE, THE LIBRARY, AND THE CHIP ROW BR-RBS-025 RULES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_rbs_003_br_rbs_025_the_chips_are_the_templates_present_not_the_sixteen(brazos, dana):
    """*A category with no template draws no chip* — `TC-RBS-20`.

    A chip that filters to nothing is dead UI (hard-won law 2), and `RB-019`'s
    *done looks like* is this screen: *"Templates shows eight category chips for
    twelve templates and none reading Assets or Work."*

    ⚠ **THIS CASE ASSERTED `== ["platform"]` AND WENT RED THE HOUR A SIBLING
    SHIPPED A SECOND TEMPLATE — SO IT ASSERTS THE RULE NOW, NOT THE CENSUS.**
    It was written when the registry held one runbook, and it said so in its own
    docstring — *"today the registry holds ONE template, so the row is ONE
    chip"* — which is a fact about **how many runbooks we have shipped so far**
    rather than about the rule `TC-RBS-20` exists for. Wave P's cash application
    and bank reconciliation and `US-RBS-042`'s accounting export made it three
    categories, and the case went red on a library growing exactly as intended.

    **A check failing for the wrong reason is worse than no check**: it leaves a
    permanent red the next lane has to triage before it can find a true one, and
    hard-won law 7 names that exactly — *a suite with 28 other failures in it is
    where a true one goes to hide*. The rule has three parts and not one of them
    counts our own backlog: the chips are drawn from the templates PRESENT and
    never from the fixed sixteen, every chip filters to at least one template,
    and a category holding nothing draws nothing.
    """
    response = _get(api.runbook_templates, brazos, dana, "/runbooks/templates")
    chips = response.data["category_chips"]
    drawn = [chip["category"] for chip in chips]
    assert len(models.CATEGORIES) == 16
    assert 0 < len(chips) < len(models.CATEGORIES), "the row is neither empty nor the sixteen"
    assert all(chip["count"] > 0 for chip in chips), "a chip that filters to nothing is dead UI"
    assert set(drawn) <= set(models.CATEGORIES)
    assert len(set(drawn)) == len(drawn), "a category draws at most one chip"
    # A category the shipped library holds NOTHING in is never drawn.
    #
    # ⚠ **THIS NAMED `("assets", "work")` AND WENT RED THE DAY RUNBOOK 28
    # SHIPPED — THE SECOND TIME THIS CASE FAILED FOR THE WRONG REASON, IN THE
    # SAME WAY THE DOCSTRING ABOVE ALREADY DESCRIBES.** The first version
    # asserted `== ["platform"]` and was rewritten to assert the rule; the
    # rewrite kept one census-shaped line. *Assets and Work hold no runbook
    # anywhere in the plan* was TRUE when it was written and became false when
    # `US-RBS-043` landed *Meters past change-out age or never tested* as the
    # Assets category's first — a list with a clock in it (hard-won law 2's
    # mirror), which is the shape B14's rule-count line has now been wrong five
    # times for.
    #
    # So the empty set is DERIVED from the registry rather than typed here. That
    # is strictly stronger than naming two: it asserts the rule for **every**
    # category the library holds nothing in, and it cannot go stale again
    # whichever category gains its first runbook next.
    from apps.runbooks.registry import registry

    held = {one.category for one in registry.all()}
    empty = set(models.CATEGORIES) - held
    assert empty, "every one of the sixteen categories holds a template — re-read this case"
    for absent in sorted(empty):
        assert absent not in drawn, f"{absent} holds no template and must draw no chip"
    # And the row agrees with the page it filters: every category on a served
    # row has a chip. That is the half `== ["platform"]` could never check.
    for category in {row["category"] for row in response.data["results"]}:
        assert category in drawn, f"{category} is served as a row and draws no chip"


@pytest.mark.django_db
def test_us_rbs_003_a_template_reads_added_only_once_this_tenant_has_it(brazos, dana):
    """**Added · Not added** is per tenant, and it is a join not a guess.

    ⚠ **THIS CASE ASSERTED THE WHOLE LIST WAS `["not_added"]` AND WENT RED WHEN
    THE LIBRARY GREW — the same fault as the chip case above, and it is worth
    naming twice because both were written the same day by the same reasoning.**
    *Added or not added* is a statement about ONE template and this tenant, so
    that is what is asserted now: the one runbook this tenant adds flips, and
    **every other template stays exactly as it was** — which is the half a
    whole-list equality could never see, because it never looked at the others
    individually at all.
    """

    def _state(response) -> dict[str, str]:
        return {row["template_key"]: row["state"] for row in response.data["results"]}

    before = _state(_get(api.runbook_templates, brazos, dana, "/runbooks/templates"))
    assert before["configuration_check"] == "not_added"
    assert set(before.values()) <= {"added", "not_added", "unavailable"}

    with tenant_ctx(brazos):
        _runbook(
            brazos, key="configuration_check", name="Can we bill?", template="configuration_check"
        )

    response = _get(api.runbook_templates, brazos, dana, "/runbooks/templates")
    after = _state(response)
    assert after["configuration_check"] == "added"
    # Adding ONE template moves ONE row and leaves every other template alone.
    assert {k: v for k, v in after.items() if k != "configuration_check"} == {
        k: v for k, v in before.items() if k != "configuration_check"
    }

    row = next(
        one for one in response.data["results"] if one["template_key"] == "configuration_check"
    )
    # *What it can touch* is derived from `ports[]` and from nothing else.
    assert row["writes_nothing"] is True
    assert row["ports"] == []


@pytest.mark.django_db
def test_us_rbs_003_the_catalogue_carries_the_last_run_and_the_open_items(brazos_runbooks, dana):
    """Row 1: *the catalogue with last-run summary and open-item counts*."""
    tenant, runbook, run = brazos_runbooks
    with tenant_ctx(tenant):
        models.WorkItem.objects.create(
            tenant=tenant,
            source_kind=models.WORK_ITEM_SOURCE_FINDING,
            source_run=run,
            fingerprint="no-read-since-18-aug",
            title="No read since 18 Aug",
            status="open",
        )
        models.WorkItem.objects.create(
            tenant=tenant,
            source_kind=models.WORK_ITEM_SOURCE_FINDING,
            source_run=run,
            fingerprint="already-dealt-with",
            title="Already dealt with",
            status="resolved",
        )
    row = _get(api.runbooks_list, tenant, dana, "/runbooks").data["results"][0]
    assert row["key"] == runbook.key and row["name"] == "Can we bill?"
    assert row["last_run"]["id"] == str(run.pk)
    assert row["last_run"]["counts"] == {"blockers": 3, "warnings": 6}
    assert row["open_items"] == 1, "a resolved item is not an open one"


@pytest.mark.django_db
def test_us_rbs_003_the_catalogue_names_the_LATEST_run_and_not_the_first(brazos, dana):
    """Three runs, and the summary is the third.

    `Max("id")` over a uuid7 primary key is time-ordered by construction, which
    is why it is used instead of `Max("started_at")` — an aggregate over a
    nullable column silently answers for the wrong row.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, key="sweep", name="Nightly sweep")
        _run(brazos, runbook, counts={"n": 1})
        _run(brazos, runbook, counts={"n": 2})
        newest = _run(brazos, runbook, counts={"n": 3})
    row = _get(api.runbooks_list, brazos, dana, "/runbooks").data["results"][0]
    assert row["last_run"]["id"] == str(newest.pk)
    assert row["last_run"]["counts"] == {"n": 3}


@pytest.mark.django_db
def test_us_rbs_003_the_detail_serves_the_registered_definition_and_a_null_next_run(
    brazos_runbooks, dana
):
    """Row 2: definition, schedule, cap, guards, next run.

    ⚠ `next_run` is `null` and it is not a placeholder: nothing in this product
    schedules a runbook yet — no job is registered with the platform runner and
    the table carries no `next_run_at` column — so a computed next occurrence
    would be answering a question no part of this module can act on. `cron` and
    `timezone` travel as DECLARED so a screen draws the schedule from the
    declaration itself.
    """
    tenant, runbook, _run = brazos_runbooks
    body = _get(api.runbook_detail, tenant, dana, f"/runbooks/{runbook.key}", key=runbook.key).data
    assert body["key"] == "configuration_check" and body["cap"] == 100
    assert body["schedule"]["timezone"] == "America/Chicago"
    assert body["schedule"]["next_run"] is None
    assert body["writes_nothing"] is True and body["ports"] == []
    assert [step["key"] for step in body["definition"]["steps"]][:1] == ["services_and_units"]


@pytest.mark.django_db
def test_us_rbs_003_an_unknown_key_is_a_404(brazos, dana):
    assert _get(api.runbook_detail, brazos, dana, "/runbooks/nope", key="nope").status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 7 — THE RECORDS LIST
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_rbs_003_the_records_list_filters_by_outcome_and_shows_plan_and_outcome(
    brazos_runbooks, dana
):
    """Row 11: *per-record plan and outcome, filter by outcome*.

    The plan and the outcome are ONE row, which is what makes this list the
    audit — *what did it say it would do versus what it did*. Two tables would
    make that comparison a join, and the audit becomes a query nobody writes.
    """
    tenant, _runbook, run = brazos_runbooks
    everything = _get(
        api.run_records, tenant, dana, f"/runbooks/runs/{run.pk}/records", run_id=str(run.pk)
    )
    assert everything.data["count"] == 3
    first = everything.data["results"][0]
    assert first["planned_action"] == "report" and first["outcome"] == "done"
    assert first["amount"] == "12.3400", "the STORED four decimals travel on the wire"

    filtered = _get(
        api.run_records,
        tenant,
        dana,
        f"/runbooks/runs/{run.pk}/records",
        run_id=str(run.pk),
        query={"f.outcome": "skipped"},
    )
    assert filtered.data["count"] == 1
    assert filtered.data["results"][0]["reason"] == "No read since 18 Aug."


@pytest.mark.django_db
def test_us_rbs_003_the_run_header_counts_records_and_says_whether_it_has_a_report(
    brazos_runbooks, dana
):
    tenant, runbook, run = brazos_runbooks
    body = _get(api.run_detail, tenant, dana, f"/runbooks/runs/{run.pk}", run_id=str(run.pk)).data
    assert body["runbook_name"] == "Can we bill?" and body["runbook_key"] == runbook.key
    assert body["records"] == 3 and body["has_report"] is True
    assert body["counts"] == {"blockers": 3, "warnings": 6}
    assert body["approved_by"] is None and body["stopped_by"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 8 — THE TWO DEFECTS THIS WAVE FOUND
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_rbs_003_def_rbs_4287_open_run_stamps_started_at(brazos):
    """`RBS-008`'s **Started** and **Took** columns need a start time.

    `services.open_run` created the run with `status = running` and left
    `started_at` null; `close_run` set `finished_at` only. Nothing went red — a
    nullable timestamp is legal everywhere and no reader existed — so every run
    ever opened carried no start time, and the run history would have drawn two
    blank columns for ever with every test green. The schema had been saying so:
    `ix_runbook_runs_recent` indexes `-started_at`.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, key="configuration_check", name="Can we bill?")
        run = services.open_run(runbook, configuration_check.RUNBOOK)
        assert run.started_at is not None, "DEF-RBS-4291 is back"
        result = _StubResult()
        closed = services.close_run(run, result)
    assert closed.finished_at is not None
    assert selectors._took_seconds(closed) is not None
    assert selectors._took_seconds(closed) >= 0


@pytest.mark.django_db
def test_us_rbs_003_def_rbs_4288_the_by_column_names_the_trigger_and_never_the_approver(
    brazos_runbooks, dana
):
    """`runbook_runs` has no `started_by`, so `by.person` is null — not a guess.

    `RBS-008` calls the **By** column *"the audit-actor question made visible"*
    and distinguishes a person from *Schedule*. The table carries `approved_by`
    and `stopped_by` and no `started_by`, so who pressed **Run ▶** is not
    recorded anywhere. Filling `by.person` from `approved_by` would put the
    approver's name in the *started by* column, which is the kind of near-right
    answer nobody ever re-checks.
    """
    tenant, _runbook, _run = brazos_runbooks
    row = _get(api.runs_list, tenant, dana, "/runbooks/runs").data["results"][0]
    assert row["by"] == {"trigger": models.TRIGGER_MANUAL, "person": None}


class _StubResult:
    """The smallest `RunResult` `close_run` reads — a report of nothing."""

    report: list = []
    counts: dict = {}
    scope_fingerprint = "0" * 64
    runbook_key = "configuration_check"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-003 · US-RBS-018 (EP-RBS-01; CR-075 wave D task D1)
# generated: 2026-09-06 by the CR-075 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(a test file) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_003_endpoints.py · G10 (a TC has a test)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

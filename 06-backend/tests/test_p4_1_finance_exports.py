# ── Trace ──────────────────────────────────────────────
# Change:   P4.1 + P4.10 (Finance blueprint p017) — seven Finance reports
#           become export resources on the ONE kernel, so each of 6·2's four
#           groupings downloads and the five refused buttons can be enabled.
# Rules:    BR-TEN-031 · BR-REP-018 (IS-11) · BR-REP-001 (the basis segment) ·
#           BR-SHL-016 / BR-SHL-029 · BR-LED-004 · BR-LED-013 · CLAUDE.md
#           rule 2 (money 2dp on the wire and in the file)
# Golden:   LE-1 — the July book foots at 553.69 in-window, 598.69 whole-book
# ───────────────────────────────────────────────────────
"""Seven files a person can open, each footing to the screen it came from.

**THE PROPERTY THIS FILE EXISTS FOR** is that a downloaded file and the screen
it was downloaded from cannot disagree — which is why every assertion below
compares the CSV against the read model rather than against a transcribed
number. A file re-derived under different defaults would pass a hand-typed
assertion and still be wrong the first time the read model moved.

`LE-1`'s figures anchor it: the July window bills **553.69**, and the trial
balance's own footer is what the exported rows are summed against.
"""

import csv
from decimal import Decimal

import pytest

from apps.ledger import close, finance_exports, reporting
from apps.tenancy import exports as export_kernel
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import errors, jobs as core_jobs

from tests.export_helpers import exported_file
from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

BILLED_IN_PERIOD = Decimal("553.69")
TRIAL_BALANCE_COLUMNS = (
    "gl_account",
    "name",
    "type",
    "opening",
    "debit",
    "credit",
    "closing",
)


@pytest.fixture()
def artifacts(tmp_path, settings):
    """The real store and the real transport, eager, writing into tmp_path.

    A suite must never write into the source tree — the nine-list export tests
    say the same thing in the same words, and this fixture is theirs.
    """
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


@pytest.fixture()
def july(brazos, dana, artifacts):
    """LE-1's July, posted, with its four accounts on three premises."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        post_le1_month(brazos, accounts)
    return accounts


def run_export(brazos, dana, resource, filters=None, columns=None):
    """Accept the export, run it eagerly, and read the CSV back.

    Goes through `request_list_export` rather than through the HTTP view: the
    view's own gates (auth, tenant, the BR-SHL-011 parse) are covered by
    `test_be_list_export.py`, and what is under test here is the SEVEN
    RESOURCES — their selectors, their columns and their filenames.
    """
    with tenant_ctx(brazos):
        accepted = tenancy_services.request_list_export(
            actor=dana,
            resource_name=resource,
            filters=dict(filters or {}),
            columns=columns,
        )
    row = tenancy_models.Job.objects.get(id=accepted["job_id"])
    assert row.status == core_jobs.SUCCEEDED, row.error
    path = exported_file(row.id)
    with path.open(encoding="utf-8", newline="") as handle:
        return path, list(csv.reader(handle))


WINDOW = {"from": JULY_START.isoformat(), "to": JULY_END.isoformat()}


# ── all seven exist and each is registered by the LEDGER ────────────────────
def test_p4_1__the_seven_finance_reports_are_registered_export_resources():
    for name in finance_exports.RESOURCE_NAMES:
        resource = export_kernel.export_resource(name)
        assert resource is not None, f"{name} is not registered"
        assert resource.module == "ledger"
        # BR-SHL-016: every one of these is a money file, so every one writes
        # its own audit_log row. A False here would be a silent money export.
        assert resource.money is True, name
    assert len(finance_exports.RESOURCE_NAMES) == 7


def test_p4_1__the_ledgers_revenue_by_service_does_not_shadow_the_reports_one():
    """Two real reports about the same subject. `apps/reports` registers
    `revenue_by_service_rate` (grouped by service AND rate schedule, with an
    accounts count and a tax column); this one is the ledger's LE-2 dimension
    extract. A name collision would have silently replaced one with the
    other — `register_export_resource` REPLACES rather than raising."""
    assert export_kernel.export_resource("revenue_by_service_rate") is not None
    assert export_kernel.export_resource("revenue_by_service") is not None
    assert export_kernel.export_resource("revenue_by_service_rate").module == "reports"
    assert export_kernel.export_resource("revenue_by_service").module == "ledger"


# ── the trial balance: the file foots to the read model, not to a number ────
def test_p4_1__trial_balance_downloads_and_foots_to_the_read_model(brazos, dana, july):
    path, rows = run_export(brazos, dana, "trial_balance", WINDOW)
    with tenant_ctx(brazos):
        served = reporting.trial_balance(start=JULY_START, end=JULY_END)

    header = rows[0]
    assert header == list(export_kernel.export_resource("trial_balance").header)
    assert len(rows) - 1 == len(served["rows"])

    debit = sum(Decimal(cell or "0") for cell in column(rows, "debit"))
    credit = sum(Decimal(cell or "0") for cell in column(rows, "credit"))
    assert debit == served["total_debit"].quantize(Decimal("0.01"))
    assert credit == served["total_credit"].quantize(Decimal("0.01"))
    assert debit == credit, "LE-1's July book foots; so must the file"
    # IS-11's five-segment filename, with BR-REP-001's basis in it.
    _tenant, report, _period, basis, _generated = path.stem.split("_")
    assert (report, basis) == ("trial-balance", "posting")


def column(rows, name):
    index = rows[0].index(name)
    return [row[index] for row in rows[1:]]


# ── money is 2dp with no symbol and no separator (CLAUDE.md rule 2 / IS-9) ──
def test_p4_1__money_cells_are_plain_two_decimal_places(brazos, dana, july):
    _path, rows = run_export(brazos, dana, "trial_balance", WINDOW)
    for cell in column(rows, "debit") + column(rows, "credit"):
        assert cell == "" or cell == str(Decimal(cell).quantize(Decimal("0.01"))), cell
        assert "$" not in cell and "," not in cell


# ── by premises: LE-6's three rows, footing to the billed figure ────────────
def test_p4_1__by_premises_downloads_le6s_rows(brazos, dana, july):
    path, rows = run_export(brazos, dana, "by_premises", WINDOW)
    with tenant_ctx(brazos):
        served = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
    assert len(rows) - 1 == len(served["rows"])
    billed = sum(Decimal(cell or "0") for cell in column(rows, "billed"))
    assert billed == BILLED_IN_PERIOD
    assert path.stem.split("_")[1] == "by-premises"


# ── remittance: BR-LED-013's per-authority basis is IN THE ROW ──────────────
def test_p4_1__remittance_names_no_basis_in_its_filename_and_one_per_row(brazos, dana, july):
    """Two authorities in one file can lawfully remit on two different bases,
    so the FILE names neither and every ROW carries its own. A file stamped
    `posting` or `clearing` would be false about half its own contents."""
    path, rows = run_export(brazos, dana, "remittance", WINDOW)
    _tenant, report, _period, basis, _generated = path.stem.split("_")
    assert (report, basis) == ("remittance-by-authority", "per-authority")
    assert "remitting_basis" in rows[0]


def test_p4_1__an_uncomputable_collected_is_an_empty_cell_never_zero(brazos, dana, july):
    """`reporting` returns None for a figure payments cannot break down. A
    0.00 there reads as *nothing was collected* about money that was — the
    exact lie the read model refuses to tell on screen."""
    _path, rows = run_export(brazos, dana, "remittance", WINDOW)
    with tenant_ctx(brazos):
        served = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
    for served_row, cell in zip(served["rows"], column(rows, "collected"), strict=True):
        if served_row.collected is None:
            assert cell == "", "a None collected must be blank, never 0.00"


# ── revenue by service: a row with no service is KEPT and left blank ────────
def test_p4_1__revenue_by_service_keeps_the_rows_that_name_no_service(brazos, dana, july):
    _path, rows = run_export(brazos, dana, "revenue_by_service", WINDOW)
    with tenant_ctx(brazos):
        served = reporting.revenue_by_service(start=JULY_START, end=JULY_END)
    assert len(rows) - 1 == len(served)
    total = sum(Decimal(cell or "0") for cell in column(rows, "total_billed"))
    assert total == sum(row.total_billed for row in served).quantize(Decimal("0.01"))


# ── the export preview: 6·2's Account grouping ─────────────────────────────
def test_p4_1__export_preview_downloads_the_table_the_send_gate_reads(brazos, dana, july):
    _path, rows = run_export(brazos, dana, "export_preview", {**WINDOW, "target": "csv"})
    assert rows[0][0] == "gl_account"
    debit = sum(Decimal(cell or "0") for cell in column(rows, "debit"))
    credit = sum(Decimal(cell or "0") for cell in column(rows, "credit"))
    assert debit == credit, "the preview the send gate reads must foot"


# ── the account ledger: one account, and a refusal without one ─────────────
def test_p4_1__account_ledger_downloads_one_accounts_lines(brazos, dana, july):
    account_id = str(next(iter(july.values())).id)
    _path, rows = run_export(brazos, dana, "account_ledger", {**WINDOW, "account_id": account_id})
    with tenant_ctx(brazos):
        served = reporting.account_ledger(account_id, start=JULY_START, end=JULY_END)
    assert len(rows) - 1 == len(served["rows"])


def test_p4_1__account_ledger_refuses_without_an_account_rather_than_widening(brazos, dana, july):
    """The alternative is a file called *one account's ledger* holding every
    account's money. BR-SHL-011's fall-back is about a SORT TERM, not about
    the subject of a report."""
    with pytest.raises(errors.ValidationError) as refused:
        run_export(brazos, dana, "account_ledger", WINDOW)
    assert refused.value.code == errors.VAL_REQUIRED
    assert refused.value.field_errors[0]["field"] == "account_id"


def test_p4_1__customer_statement_refuses_without_a_customer(brazos, dana, july):
    with pytest.raises(errors.ValidationError) as refused:
        run_export(brazos, dana, "customer_statement", {})
    assert refused.value.field_errors[0]["field"] == "customer_id"


# ── a malformed window is refused, never slid into another month ───────────
def test_p4_1__a_malformed_date_is_refused_rather_than_guessed(brazos, dana, july):
    with pytest.raises(errors.ValidationError) as refused:
        run_export(brazos, dana, "trial_balance", {"from": "2026-13-01", "to": "2026-07-31"})
    assert refused.value.field_errors[0]["field"] == "from"


# ── P4.13 rides these too: the kernel change is not per-resource ───────────
def test_p4_1__a_finance_download_carries_the_ticked_columns(brazos, dana, july):
    _path, rows = run_export(
        brazos, dana, "trial_balance", WINDOW, columns=["closing", "gl_account"]
    )
    assert rows[0] == ["closing", "gl_account"]


# ── every one writes its money-export audit row (BR-SHL-016 / rule 7) ──────
def test_p4_1__every_finance_export_writes_an_audit_row(brazos, dana, july, audit_rows):
    """BR-SHL-016 / CLAUDE.md rule 7. `audit_rows` is the shared autouse
    collector the ledger suites already read — the rows are captured at the
    writer, so this asserts the CALL rather than a table's contents."""
    run_export(brazos, dana, "trial_balance", WINDOW)
    exported = [row for row in audit_rows if row["action"] == "list.exported"]
    assert exported, "a money export must write its own audit_log row"
    assert exported[-1]["after"]["resource"] == "trial_balance"
    # P4.13 — the row records WHICH columns left the building.
    assert exported[-1]["after"]["columns"] == list(TRIAL_BALANCE_COLUMNS)


# ── the closed-period gate belongs to the SEND, never to the download ─────
def test_p4_1__an_open_month_still_downloads(brazos, dana, july):
    """BR-LED-017 refuses to SEND an open month because *"the ERP never
    receives numbers that can still move"*. A DOWNLOAD is not a hand-over —
    p069 is explicit that *"Download and Send stay apart … ↓ is the table as
    shown … nothing recorded"* — so an open month's preview downloads and the
    file simply says what the screen says."""
    with tenant_ctx(brazos):
        assert not close.window_is_closed(JULY_START, JULY_END)
    _path, rows = run_export(brazos, dana, "export_preview", {**WINDOW, "target": "csv"})
    assert len(rows) > 1


# ═══════════════════════════════════════════════════════════════════════════
# P4.6 — the deposit slip. PAYMENTS' resource, on the same kernel.
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_6__the_deposit_slip_is_a_registered_export_resource():
    """`DepositsPage` carried a DISABLED download with a TRUE reason — no
    deposits export resource was registered anywhere — until 2026-09-24."""
    resource = export_kernel.export_resource("deposits")
    assert resource is not None
    # BR-TEN-031: the OWNING module registers it, and deposits are payments'.
    assert resource.module == "payments"
    assert resource.money is True
    # BR-REP-001 — a deposit is a BANK event, so its file says `clearing`. A
    # file stamped `posting` would sit beside the trial balance claiming to be
    # the same kind of number, and it is not.
    assert resource.basis == "clearing"
    assert resource.filters == ("status", "method")


def test_p4_6__the_slip_columns_are_s37s_own_and_keep_difference_nullable():
    """`difference` is None until a bank total is typed, and a 0.00 there reads
    as *the batch reconciles exactly* about a batch nobody has checked."""
    resource = export_kernel.export_resource("deposits")
    assert resource.header == (
        "batch",
        "method",
        "deposited_on",
        "payments",
        "recorded_total",
        "bank_total",
        "difference",
        "status",
    )

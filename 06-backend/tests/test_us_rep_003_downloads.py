# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-003 (IS-11 downloads: CSV always, the filename contract, the
#           50k guard and the money-export audit row)   Screens: S46
# Rules:    BR-REP-018 (IS-11: CSV always + PDF where layout matters, NO XLSX
#           v1, strict CSV contract, context in the filename, 3-day retention) ·
#           BR-REP-001 (the basis rides in the `{basis}` filename segment) ·
#           BR-SHL-016 / BR-SHL-029 (server-side, streamed under RLS, >50,000
#           rows refused, money exports write `audit_log`) · CLAUDE.md rule 2
#           (money is plain 2dp in a file, from a NUMERIC(18,6) source) ·
#           rule 3 (a quantity always carries its unit) · rule 7
# ───────────────────────────────────────────────────────
"""The four report CSVs — asserted on the BYTES, not on the intention.

US-REP-003 is the story that most invites a shape test: a route that returns 202
looks finished, and the file it eventually writes is where every one of IS-11's
promises actually lives. So these cases run the job body and read the file.

**The strongest assertion here is a negative one and it is about the filename.**
BR-REP-001 makes two reports of the same month, one POSTING and one CLEARING,
both correct and different. A bookkeeper holding both has nothing but the
filename to tell them apart, which is why US-REP-003 TC-3 makes a money file
missing its `{basis}` segment a FAILURE rather than an untidiness.
"""

import csv
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.tenancy import exports as export_kernel

from tests.test_us_bil_025_026_bills_read import a_line, an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_rep_canned_reports import (
    CASH,
    CHECKS,
    JULY_END,
    JULY_START,
    a_cleared_payment,
    a_method,
    three_bills,
)

pytestmark = pytest.mark.django_db

UTC = timezone.utc
WINDOW = {"from": JULY_START.isoformat(), "to": JULY_END.isoformat()}


def written(tmp_path, resource_name, filters):
    """Run one export resource's job body and return `(path, rows)`.

    The KERNEL's own writer is used — `apps/tenancy/exports.py` — because that
    is the point of registering these reports as resources rather than writing a
    second CSV path. A test that formatted its own cells would prove the test,
    not the product.
    """
    from apps.tenancy.exports import ListParams  # noqa: F401 — re-exported type

    resource = export_kernel.export_resource(resource_name)
    assert resource is not None, f"{resource_name} is not a registered export resource"
    params = export_kernel.params_from_payload(resource, {"filters": filters})
    rows = resource.select(params)
    path = tmp_path / export_kernel.artifact_filename(
        _tenant(),
        report=resource.slug,
        period=export_kernel.period_segment(params.filters, default=resource.period),
        basis=resource.basis,
        now=datetime(2026, 8, 5, 10, 14, tzinfo=UTC),
        tz=export_kernel.tenant_timezone(_tenant()),
    )
    export_kernel.write_csv(
        path, resource.header, export_kernel.row_stream(resource, rows, export_kernel.tenant_timezone(_tenant()))
    )
    with path.open(encoding="utf-8") as handle:
        return path, list(csv.reader(handle))


def _tenant():
    from core.tenancy import current_tenant_id

    return current_tenant_id()


# ═══════════════════════════════════════════════════════════════════════════
# US-REP-003 — the CSV contract
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_003_tc1__the_csv_has_one_snake_case_header_row_and_plain_money(
    brazos, dana, tmp_path
):
    """US-REP-003 TC-1: *"One snake_case header row … money `247.87` style …
    zero metadata rows"*.

    The money assertion is the one that bites: a NUMERIC(18,6) source serves
    `247.870000` on the wire (exactness, CLAUDE.md rule 2) and IS-11 says a FILE
    carries plain 2dp with no symbol and no thousands separator. Those are two
    different contracts over one figure and the kernel's `MONEY` formatter is
    where they meet.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        we1, _, _ = three_bills(brazos, account)
        a_line(brazos, we1, account, quantity=Decimal("684"), unit="kWh")

        path, rows = written(tmp_path, "billing_register", WINDOW)

        assert rows[0] == [
            "bill_no",
            "bill_type",
            "account_no",
            "customer",
            "cycle",
            "issued_on",
            "services",
            "usage",
            "amount",
            "flag",
        ]
        assert all(cell.islower() or not cell.isalpha() for cell in rows[0])
        assert len(rows) == 4  # one header + three bills — NO metadata rows
        amounts = [row[8] for row in rows[1:]]
        assert "247.87" in amounts  # plain 2dp, no symbol, no separator
        assert not any("$" in value or "," in value for value in amounts)


def test_us_rep_003_tc1b__a_usage_cell_never_loses_its_unit(brazos, dana, tmp_path):
    """CLAUDE.md rule 3 in a CSV cell.

    A file is where a unit is most easily lost — a column headed `usage` holding
    `684` is read by whatever opens it as whatever that reader assumes. The cell
    carries the unit, and a bill measured in two units carries both, separated by
    the kernel's own multi-value separator rather than summed.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        we1, _, _ = three_bills(brazos, account)
        a_line(brazos, we1, account, quantity=Decimal("684"), unit="kWh")
        a_line(
            brazos,
            we1,
            account,
            kind="usage",
            quantity=Decimal("26.24"),
            unit="kgal",
            amount=Decimal("47.50"),
        )

        _, rows = written(tmp_path, "billing_register", WINDOW)
        usage = {row[0]: row[7] for row in rows[1:]}
        # Ordered by UNIT so two runs of the same report agree, and TRIMMED:
        # NUMERIC(18,6) holds 684.000000 and a consumption figure's trailing
        # zeros carry no information (`apps/reports/queries._trimmed`, which is
        # never applied to money).
        assert usage["BL-2607-000001"] == "684 kWh|26.24 kgal"


def test_us_rep_003_tc3__a_money_file_carries_its_basis_in_the_filename(
    brazos, dana, tmp_path
):
    """US-REP-003 TC-3 — *"a generated money file missing either = FAIL"*.

    Both carry `posting` since 2026-10-21: the PO moved Payments by method to
    the POSTING date (`DEF-PAY-10321`). It carried `clearing` until then. The
    segment still names the basis, so a later basis change shows in the name.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        three_bills(brazos, account)
        for amount in CHECKS:
            a_cleared_payment(
                brazos,
                account,
                amount=amount,
                method=a_method(brazos, "check", "Check"),
                cleared_on=date(2026, 7, 15),
            )

        register_path, _ = written(tmp_path, "billing_register", WINDOW)
        cash_path, _ = written(tmp_path, "payments_by_method", WINDOW)

        assert "_posting_" in register_path.name
        assert "_posting_" in cash_path.name  # DEF-PAY-10321, PO 2026-10-21
        assert register_path.name.endswith(".csv")
        # IS-11's grammar, in order: {tenant}_{report}_{period}_{basis}_{generated}
        tenant_slug, report, period, basis, generated = register_path.stem.split("_")
        assert report == "billing-register"
        assert period == "2026-07"
        assert basis == "posting"
        # IS-8/IS-11: the `{generated}` stamp is in the TENANT's timezone, not
        # UTC. Brazos Bend is America/Chicago, so 10:14Z is 05:14 local — the
        # figure a Texas bookkeeper would write on the folder.
        assert generated == "20260805T0514"


def test_us_rep_003_tc4__no_report_export_is_refused_for_being_large(brazos):
    """US-REP-003 TC-4, REWRITTEN BY `P2.4` (`CR-142-BRC07`, 2026-09-26).

    ⛔ **THIS CASE USED TO ASSERT THAT AN OVER-CAP EXPORT IS REFUSED.** The cap
    it rode on — `export_kernel.EXPORT_ROW_CAP` — is DELETED: `NFR-5` forbids a
    hard cap anywhere, and 100,000 was already short of Killeen's 57,066
    accounts x 14 cycles = ~685,000 bill rows a year. Phase 2's own DONE WHEN
    is *"no export is refused for being large"*.

    ⚠ **ITS HISTORY IS WHY THE NEW ASSERTION NAMES THE ABSENCE RATHER THAN
    PINNING A NUMBER.** This case pinned the literal 50,000 and was RED from
    2026-09-19 to 2026-09-25 (`DEF-REP-6674`) because `DEF-MET-5756` raised the
    kernel's cap and never walked here. It was then loosened to *"the cap is an
    int and is positive"*, which is a check that cannot fail for the right
    reason. **A named absence can fail for exactly one reason: somebody put the
    cap back.**

    What TC-4 always actually needed, and still does: the four reports are
    registered on the KERNEL's registry, so they travel the one accept path and
    can never grow a second ceiling of their own.
    """
    from apps.reports import exports as report_exports

    assert not hasattr(export_kernel, "EXPORT_ROW_CAP"), (
        "`EXPORT_ROW_CAP` is back. The four reports would be refused by it "
        "again, and NFR-5 forbids it — see P2.4."
    )
    assert report_exports.RESOURCES, "no report resource is registered at all"
    for resource in report_exports.RESOURCES:
        assert export_kernel.export_resource(resource.name) is resource


def test_us_rep_003_tc5__no_surface_offers_xlsx(brazos):
    """US-REP-003 TC-5: *"None exists — the A14 'Excel' mention is corrected"*.

    A negative asserted over the REGISTRY rather than over one screen: no report
    resource may declare a non-CSV artifact, and the kernel writes `.csv` and
    nothing else. There is no code path that could produce a workbook.
    """
    from apps.reports import exports as report_exports

    assert export_kernel.CSV_CONTENT_TYPE.startswith("text/csv")
    for resource in report_exports.RESOURCES:
        assert not resource.slug.endswith("xlsx")


def test_us_rep_003_tc6__a_money_export_is_flagged_for_the_audit_row(brazos):
    """US-REP-003 TC-6 / CLAUDE.md rule 7: every money export writes `audit_log`.

    The WRITE is the kernel's (`request_list_export` audits a money-bearing
    resource); what belongs to this lane is declaring that these four ARE money
    reports. A resource left `money=False` would export a receivable in silence.
    """
    from apps.reports import exports as report_exports

    for resource in report_exports.RESOURCES:
        assert resource.money is True, f"{resource.name} exports money and is not flagged"


def test_us_rep_003_tc7__the_export_reads_the_same_rows_the_screen_renders(
    brazos, dana, tmp_path
):
    """The file IS the report — not an approximation re-derived under different
    defaults.

    Both go through `apps/reports/queries`, so a filter honoured on screen is
    honoured in the file. Proved by exporting under a `bill_type` filter and
    reading the rows back.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        three_bills(brazos, account)

        _, rows = written(tmp_path, "billing_register", {**WINDOW, "bill_type": "final"})
        assert len(rows) == 2  # header + the one final bill
        assert rows[1][0] == "BL-2607-000003"
        assert rows[1][1] == "final"


def test_us_rep_003_tc8__the_cash_file_carries_both_dates(brazos, dana, tmp_path):
    """BR-PAY-021 in a file. A cash CSV whose reader cannot see the
    POSTING date cannot be reconciled against a bank statement, which is the one
    job this file exists for."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_cleared_payment(
            brazos,
            account,
            amount=CASH[0],
            method=a_method(brazos, "cash", "Cash"),
            cleared_on=date(2026, 7, 15),
        )

        _, rows = written(tmp_path, "payments_by_method", WINDOW)
        assert rows[0][:2] == ["posted_on", "cleared_on"]
        assert rows[1][0] == "2026-07-15"
        assert rows[1][1] == "2026-07-15"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-003@c6c35b2 (04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md §US-REP-003 · 12-reports/02-business-rules.md BR-REP-001/018 · apps/tenancy/exports.py)
# screens: S46
# generated: 2026-08-16 by story-coder (reports lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `export_resource("ar_aging")` returned None (no such registered resource) before apps/reports/exports.register() existed, and every case here failed on the assertion naming it. ruff✔ black✔ pytest✔
# exceptions: (1) the 50k cap is asserted as a WIRING fact rather than by materialising 50,001 bills — it is measured at accept time in the kernel these four are registered on, and a second cap for reports is exactly what the registration avoids · (2) no PDF case exists because no PDF exists: this deployment declares no renderer and the control does not offer the format
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

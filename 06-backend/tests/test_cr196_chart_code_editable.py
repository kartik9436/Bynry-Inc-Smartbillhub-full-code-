"""CR-196-BRC10 — a chart account's CODE may be changed by a System Admin, even
when the account is used; it applies everywhere at once; the old code is kept.

PO ruling 2026-10-29, verbatim: *"in many cases utilities are giving there own
GL codes; which means we have to ability to change existing GL code as per the
given utility for that specific tenant; even if they are used ; if user update
them they should be applicable after the updation."* Q1–Q4 were each answered
**A** (decision log 2026-10-29). This AMENDS US-LED-005 §1 / BR-LED-040 for
CODE only — TYPE stays frozen, which `test_type_is_still_refused` holds.

The two guards at the bottom of the file are OUR judgment (law 13), recorded
with the worked case: the PO's own workflow *"seed it and then change it"*
fails on the next deploy without them.

  5a  — a re-seed after a rename creates NO empty duplicate (the reference
        sweep runs `seed_chart_of_accounts` for every tenant on every migrate).
  5b  — a tax account renamed out of the 2200 prefix is still tax: a
        remittance against it is accepted and it stays on the tax report.

Red-first evidence is in the CR file (`12-governance/change-requests/
CR-196-BRC10-chart-code-editable.md` §6).
"""

import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.ledger import chart, chart_api, journal, models, reporting, services
from core import errors

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE3_STATE_REMIT_NOW,
    ensure_authority_accounts,
    make_accounts,
    post_le1_month,
    post_le3_authorities,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's own worked codes (decision log 2026-10-29).
SOLAR_NEW = "0117-080-1000-0000-7127"
TAX_NEW = "0117-080-1000-0000-7126"
AR_NEW = "0117-080-1000-0000-1200"


def signed_in(role):
    return SimpleNamespace(id=uuid.uuid4(), pk=uuid.uuid4(), role=role, is_authenticated=True)


def call(view, tenant, method="get", *, role="system_admin", data=None, **kwargs):
    return api_call(
        view, method, user=signed_in(role), role=role, tenant=tenant, data=data, **kwargs
    )


def refused(response, code: str, message_key: str | None = None) -> None:
    assert response.status_code == errors.HTTP_STATUS_BY_CODE[code], (
        f"expected {code}, got {response.status_code} {getattr(response, 'data', None)!r}"
    )
    assert response.data["code"] == code
    if message_key is not None:
        assert response.data.get("message_key") == message_key, response.data


def account(tenant, **where):
    with tenant_ctx(tenant):
        return models.LedgerAccount.objects.get(tenant_id=tenant.id, **where)


# ═══════════════════════════════════════════════════════════════════════════
# (1)(3)(4) — a System Admin renames a USED account; it applies everywhere
# ═══════════════════════════════════════════════════════════════════════════
def test_an_admin_changes_a_used_accounts_code_and_it_applies_everywhere(
    brazos, growth_plan, identity_seam, audit_rows
):
    actor = signed_in("system_admin")
    with tenant_ctx(brazos):
        post_le1_month(brazos, make_accounts(actor, brazos, {}))
        ar = models.LedgerAccount.objects.get(tenant_id=brazos.id, designation=chart.AR)
        assert models.JournalLine.objects.filter(ledger_account=ar).exists(), "used"
        old_code = ar.code

    response = call(
        chart_api.account_item, brazos, "patch", data={"code": f"  {AR_NEW} "}, account_id=ar.pk
    )
    assert response.status_code == 200, response.data
    # Trimmed, same format rule as create.
    assert response.data["code"] == AR_NEW
    # (4) "formerly 1200" — on the account, not only in the pruned audit trail.
    assert response.data["former_code"] == old_code
    assert [(h["old_code"], h["new_code"]) for h in response.data["code_history"]] == [
        (old_code, AR_NEW)
    ]

    # Hard rule 7 — the audit row carries old and new.
    rows = [r for r in audit_rows if r["action"] == "ledger_account.code_changed"]
    assert len(rows) == 1
    assert rows[0]["before"] == {"code": old_code}
    assert rows[0]["after"] == {"code": AR_NEW}

    # (3) / Q1 A — past entries read the NEW code: the journal and the report
    # derive the code through the account id, so July's books now say AR_NEW.
    with tenant_ctx(brazos):
        totals = {t.account_id: t.code for t in reporting.gl_totals(end=JULY_END)}
        assert totals[str(ar.pk)] == AR_NEW
        # Q1 A — July's trial balance reads the new code "(formerly 1200)".
        tb = reporting.trial_balance(start=JULY_START, end=JULY_END)
        tb_row = next(r for r in tb["rows"] if str(r["account_id"]) == str(ar.pk))
        assert (tb_row["code"], tb_row["former_code"]) == (AR_NEW, old_code)
        assert not models.LedgerAccount.objects.filter(tenant_id=brazos.id, code=old_code).exists()
        # The designation never moved — posting still finds AR by role.
        assert services.gl_account_id_for_designation(chart.AR) == str(ar.pk)

    # The chart read serves it too, with "formerly".
    listed = call(chart_api.accounts, brazos)
    row = next(r for r in listed.data["rows"] if r["account_id"] == str(ar.pk))
    assert (row["code"], row["former_code"]) == (AR_NEW, old_code)
    # ⚠ seed_key is internal and NEVER on the wire.
    assert "seed_key" not in row


def test_the_usage_read_counts_bills_and_payments_and_names_closed_and_exported_months(
    brazos, growth_plan, identity_seam
):
    """(2) the confirmation's counts and Q2's warning."""
    actor = signed_in("system_admin")
    with tenant_ctx(brazos):
        post_le1_month(brazos, make_accounts(actor, brazos, {}))
        ar = models.LedgerAccount.objects.get(tenant_id=brazos.id, designation=chart.AR)
        models.FiscalPeriodClose.objects.create(
            tenant_id=brazos.id, period_start=JULY_START, period_end=JULY_END
        )
        models.ExportBatch.objects.create(
            tenant_id=brazos.id,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_CSV,
            content_hash="x",
        )
        bills = (
            models.JournalLine.objects.filter(
                ledger_account=ar, journal_entry__source_type="invoice"
            )
            .values("journal_entry__source_id")
            .distinct()
            .count()
        )

    response = call(chart_api.account_item, brazos, account_id=ar.pk)
    assert response.status_code == 200, response.data
    usage = response.data["usage"]
    # LE-1's AR: four invoice-sourced entries (WE-1, WE-3, WE-7B and WE-7B's
    # deposit application, each its own source in the fixture) and ONE payment.
    assert usage["bills"] == bills == 4
    assert usage["payments"] == 1
    assert usage["journal_lines"] > usage["bills"] + usage["payments"]
    assert usage["closed_period"] == {"start": "2026-07-01", "end": "2026-07-31"}
    assert usage["exported_period"]["start"] == "2026-07-01"
    assert usage["exported_period"]["end"] == "2026-07-31"


def test_an_unused_account_reports_zero_usage_and_no_warning(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    usage = call(chart_api.account_item, brazos, account_id=solar.pk).data["usage"]
    assert usage == {
        "bills": 0,
        "payments": 0,
        "journal_lines": 0,
        "closed_period": None,
        "exported_period": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Q4 A — System Admin only; refused BY NAME for a clerk
# ═══════════════════════════════════════════════════════════════════════════
def test_a_clerk_may_not_change_a_code_and_is_told_why(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item,
        brazos,
        "patch",
        role="billing_clerk",
        data={"code": SOLAR_NEW, "name": "Solar service"},
        account_id=solar.pk,
    )
    refused(response, errors.AUTH_PERMISSION_DENIED, "ledger.chart.code_change_admin_only")
    # Nothing landed — not even the name that rode in the same request.
    again = account(brazos, pk=solar.pk)
    assert (again.code, again.name) == ("4150", "Solar")


def test_a_clerk_still_renames(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item,
        brazos,
        "patch",
        role="billing_clerk",
        data={"name": "Solar service"},
        account_id=solar.pk,
    )
    assert response.status_code == 200, response.data
    assert response.data["name"] == "Solar service"


# ═══════════════════════════════════════════════════════════════════════════
# Uniqueness, format, the tax series, and TYPE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_duplicate_code_is_refused_on_the_code_field(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": "4100"}, account_id=solar.pk
    )
    refused(response, errors.BIZ_STATE, "ledger.chart.code_taken")
    assert response.data["field_errors"][0]["field"] == "code"


def test_a_retired_accounts_code_is_still_taken(brazos):
    """`uq_ledger_accounts_code` counts soft-deleted rows; the refusal agrees."""
    with tenant_ctx(brazos):
        retired = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4130")
        retired.deleted_at = datetime(2026, 8, 1, tzinfo=dt_timezone.utc)
        retired.save(update_fields=["deleted_at"])
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": "4130"}, account_id=solar.pk
    )
    refused(response, errors.BIZ_STATE, "ledger.chart.code_taken")


def test_an_empty_code_is_refused(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": "   "}, account_id=solar.pk
    )
    refused(response, errors.VAL_REQUIRED, "ledger.chart.code_required")


def test_a_non_tax_account_may_not_move_into_the_2200_series(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": "2200-09"}, account_id=solar.pk
    )
    refused(response, errors.BIZ_STATE, "ledger.chart.tax_series_reserved")


def test_type_is_still_refused(brazos):
    """(6) / Q3 A — TYPE stays locked. Unchanged from BR-LED-040."""
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item, brazos, "patch", data={"type": "expense"}, account_id=solar.pk
    )
    refused(response, errors.VAL_FORMAT, "ledger.chart.field_not_editable")


def test_the_same_code_is_a_no_op_with_no_history(brazos, audit_rows):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": "4150"}, account_id=solar.pk
    )
    assert response.status_code == 200, response.data
    assert response.data["code_history"] == []
    assert not [r for r in audit_rows if r["action"] == "ledger_account.code_changed"]


# ═══════════════════════════════════════════════════════════════════════════
# 5a — a re-seed after a rename creates NO duplicate
# ═══════════════════════════════════════════════════════════════════════════
def test_5a_a_reseed_after_a_rename_creates_no_empty_duplicate(brazos, dana):
    """Worked case: the utility renames 4150 → SOLAR_NEW. The next deploy's
    reference sweep calls `seed_chart_of_accounts` for every tenant. Without
    the seed key it finds no 4150 and mints an EMPTY 4150 Solar beside it."""
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
    assert (
        call(
            chart_api.account_item, brazos, "patch", data={"code": SOLAR_NEW}, account_id=solar.pk
        ).status_code
        == 200
    )
    with tenant_ctx(brazos):
        summary = services.seed_chart_of_accounts(dana)
        assert summary["accounts_created"] == 0, summary["codes_created"]
        assert not models.LedgerAccount.objects.filter(tenant_id=brazos.id, code="4150").exists()


def test_5a_the_seed_key_is_set_at_seed_time_and_never_moves(brazos):
    with tenant_ctx(brazos):
        solar = models.LedgerAccount.objects.get(tenant_id=brazos.id, code="4150")
        assert solar.seed_key == "4150"
    call(chart_api.account_item, brazos, "patch", data={"code": SOLAR_NEW}, account_id=solar.pk)
    assert account(brazos, pk=solar.pk).seed_key == "4150"


def test_5a_a_renamed_unsigned_account_still_reads_unsigned(brazos):
    """US-LED-017 TC-5 — `finance_signed` reads the seed key, so a renamed
    unsigned row cannot start presenting itself as finance-signed."""
    unsigned = next(iter(chart.PENDING_FINANCE_RE_SIGN_BOOKS))
    with tenant_ctx(brazos):
        row = models.LedgerAccount.objects.get(tenant_id=brazos.id, code=unsigned)
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": "X-" + unsigned}, account_id=row.pk
    )
    assert response.status_code == 200, response.data
    assert response.data["finance_signed"] is False
    assert response.data["seeded"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 5b — a renamed tax account is still tax
# ═══════════════════════════════════════════════════════════════════════════
def _four_authorities(brazos, dana):
    accounts = make_accounts(dana, brazos, {})
    authorities = ensure_authority_accounts(brazos, dana)
    post_le3_authorities(brazos, accounts, authorities)
    return authorities


def test_5b_a_renamed_tax_account_is_still_remittable_and_on_the_tax_report(brazos, dana):
    with tenant_ctx(brazos):
        state = _four_authorities(brazos, dana)["2200-01"]
    response = call(
        chart_api.account_item, brazos, "patch", data={"code": TAX_NEW}, account_id=state.pk
    )
    assert response.status_code == 200, response.data

    with tenant_ctx(brazos):
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        row = next((r for r in report["rows"] if r.code == TAX_NEW), None)
        assert row is not None, "the renamed tax account dropped off the tax report"
        assert row.billed == LE3_STATE_REMIT_NOW

        result = journal.record_tax_remittance(
            tax_account_id=state.pk,
            period_start=JULY_START,
            period_end=JULY_END,
            amount=LE3_STATE_REMIT_NOW,
            basis=journal.BASIS_COLLECTED,
            confirmation_ref="TXC-2026-08-9012",
            entry_date=date(2026, 8, 18),
            posted_at=datetime(2026, 8, 18, 14, 5, tzinfo=dt_timezone.utc),
            actor=dana,
        )
        assert result.amount == Decimal(LE3_STATE_REMIT_NOW)

    mapping = call(chart_api.gl_mappings, brazos)
    assert TAX_NEW in {r["code"] for r in mapping.data["tax_authorities"]["rows"]}


def test_5b_the_tax_code_allocator_never_re_lets_a_renamed_number(brazos, dana):
    """BR-LED-023: a number is never re-let. Renaming 2200-04 away must not hand
    2200-04 to the next authority."""
    with tenant_ctx(brazos):
        puc = _four_authorities(brazos, dana)["2200-04"]
    renamed = call(
        chart_api.account_item, brazos, "patch", data={"code": TAX_NEW}, account_id=puc.pk
    )
    assert renamed.status_code == 200, renamed.data
    with tenant_ctx(brazos):
        assert not models.LedgerAccount.objects.filter(tenant_id=brazos.id, code="2200-04").exists()
        minted = services.create_tax_authority_account(name="New district", actor=dana)
        assert minted.code == "2200-05"


def test_5b_a_seed_key_in_the_2200_series_is_tax_and_a_plain_code_still_is():
    assert chart.is_tax_payable_account(TAX_NEW, "2200-01") is True
    assert chart.is_tax_payable_account("2200-07", None) is True
    assert chart.is_tax_payable_account(TAX_NEW, None) is False
    assert chart.is_tax_payable_account("4100", "4100") is False

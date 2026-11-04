# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-016 (S42 export: one summary JE per period per GL, idempotent
#           recorded batches, drill-back, dimension CSVs — TC-1 the batch, TC-2
#           the re-run block, TC-3 drill-back, TC-4 the extracts, TC-5 the
#           missing-ref block, TC-6 the drift block, TC-7 isolation) ·
#           US-LED-006 (export codes on the GL mapping page — TC-1..TC-7)
#           Screens: S42 · S43 · S56
# Rules:    BR-LED-004 · BR-LED-014 · BR-LED-017 (closed-period gate + flexible
#           granularity) · BR-LED-007 (drift is a release blocker) ·
#           BR-LED-015 (audit) · BR-TEN-020 (a recorded batch keeps its refs) ·
#           CLAUDE.md rule 1 · rule 2 · rule 6 · rule 7
# Golden:   LE-5 — July → QuickBooks, one summary JE, batch recorded with
#           who/when/hash, re-run BLOCKED, drill-back on revenue **506.31**
# ───────────────────────────────────────────────────────
"""The handover an accountant can trust, exactly once.

J19 steps 3-5 and T5-07/T5-08 are the whole shape: **an OPEN period may not be
exported** (BR-LED-017 — *"the ERP never receives numbers that can still
move"*), and **a covered window is handed over once, forever** (BR-LED-004 —
a second QuickBooks export of July is how a tenant's ERP books July twice).

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_016_tc2__a_second_export_of_the_same_window_is_blocked_with_the_link`.

⚠ **LE-5's 598.69 IS THE WHOLE BOOK, NOT THE JULY WINDOW.** LE-1's opening-balance
entry is dated at the 2026-06-30 cutover on purpose (the fixture says why), so a
July-windowed trial balance foots at 553.69 and the book at 598.69. Both are
asserted below, and the export's totals are asserted to BE the trial balance's
rather than a second summation — which is the property that matters: the ERP and
S56 can never disagree, because there is one derivation.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import close, exports, models, posting, reporting, services as ledger_services
from apps.tenancy import models as tenancy_models
from core import errors, numbering as core_numbering

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_FOOTING,
    LE1_REVENUE,
    gl,
    make_accounts,
    post_le1_month,
)
from tests.test_us_led_012_accrual_auto_reverse import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import executive_actor, tenant_ctx

pytestmark = pytest.mark.django_db

CLOSED_ON = datetime(2026, 8, 5, 16, 30, tzinfo=dt_timezone.utc)
SENT_AT = datetime(2026, 8, 5, 17, 0, tzinfo=dt_timezone.utc)

#: US-LED-006 §4 verbatim — *"Brazos Bend QBO refs (illustrative tenant data):
#: 1000→`35`, 1200→`84`, 2200→`91`, 2300→`93`, 4100→`79`, 4110→`80`, 4200→`82`,
#: 6900→`88`"*, plus the accounts the LE-1 fixture actually touches.
QBO_REFS = {
    "1000": "35",
    "1010": "36",
    "1200": "84",
    "2200-03": "91",
    "2300": "93",
    "3000": "94",
    "4100": "79",
    "4105": "77",
    "4110": "80",
    "4115": "81",
    "4120": "83",
    "4130": "85",
    "4150": "86",
    "4200": "82",
    "6900": "88",
    "6950": "89",
}


def july_books(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def map_refs(tenant, actor, *, skip=()):
    """Set every touched account's QBO ref, US-LED-006 TC-2's own write."""
    for account in models.LedgerAccount.objects.filter(tenant=tenant, deleted_at__isnull=True):
        if account.code in skip:
            continue
        ledger_services.set_export_codes(
            actor, account_id=account.id, qbo_ref=QBO_REFS.get(account.code, f"X{account.code}")
        )


def close_july(actor):
    return close.close_period(
        actor,
        period_start=JULY_START,
        period_end=JULY_END,
        closed_at=CLOSED_ON,
        reason="registers not readable from the ledger (see the checklist)",
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-006 — the export codes the export addresses accounts by
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_006_tc1_tc2__the_mapping_page_shows_refs_and_gaps_and_saves_them(
    brazos, dana, audit_rows
):
    """US-LED-006 TC-1: *"Each chart row shows QBO ref + Xero ref … gaps render
    as visible empty states, not silently."* TC-2: the save, with an audit row
    carrying before/after."""
    with tenant_ctx(brazos):
        page = ledger_services.export_code_map()
        assert page["rows"], "the seeded chart is the mapping page's rows"
        assert all(row["qbo_ref"] is None for row in page["rows"])
        # Every row is a gap until somebody maps it — and the page says which.
        assert set(page["missing"]["qbo_ref"]) == {row["code"] for row in page["rows"]}

        account = models.LedgerAccount.objects.get(tenant=brazos, code="4100")
        saved = ledger_services.set_export_codes(dana, account_id=account.id, qbo_ref="79")
        assert saved["qbo_ref"] == "79"
        assert saved["gaps"] == ("xero_ref",)

        row = [r for r in audit_rows if r["action"] == "ledger_account.export_code_updated"][-1]
        assert row["before"] == {"qbo_ref": None}
        assert row["after"] == {"qbo_ref": "79"}

        # Omitting an argument leaves that ref ALONE; passing None clears it.
        ledger_services.set_export_codes(dana, account_id=account.id, xero_ref="200")
        again = ledger_services.set_export_codes(dana, account_id=account.id, qbo_ref=None)
        assert again["qbo_ref"] is None and again["xero_ref"] == "200"


def test_us_led_006_tc6_tc7__the_gate_and_the_boundary(brazos, dana, lonestar, erin):
    """US-LED-006 TC-6 (*"Staff-role edit attempt → refused server-side"*) and
    TC-7 (*"its own refs; Brazos Bend's QBO refs never visible or reused"*).

    A cross-tenant account id is a NOT-FOUND, never a 403 — HR-1: the response
    must not reveal that the row exists somewhere else.
    """
    with tenant_ctx(brazos):
        account = models.LedgerAccount.objects.get(tenant=brazos, code="4100")
        with pytest.raises(errors.AuthError):
            ledger_services.set_export_codes(
                executive_actor(), account_id=account.id, qbo_ref="79"
            )
        ledger_services.set_export_codes(dana, account_id=account.id, qbo_ref="79")

    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            ledger_services.set_export_codes(erin, account_id=account.id, qbo_ref="666")
        assert all(row["qbo_ref"] is None for row in ledger_services.export_code_map()["rows"])


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the recorded batch
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc1__july_hands_over_once_as_the_trial_balance(brazos, dana, audit_rows):
    """US-LED-016 TC-1 / LE-5: one summary JE, every row carrying its qbo_ref,
    the batch recorded with who/when/hash.

    The payload's totals ARE `reporting.trial_balance`'s — asserted by equality,
    not by re-deriving them, because one derivation is the whole point.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)

        # The ❄️ LE-1 footing is over the WHOLE book (its opening entry is dated
        # at the June 30 cutover); the July window is its own balanced subset.
        assert reporting.trial_balance()["total_debit"] == LE1_FOOTING
        july = reporting.trial_balance(start=JULY_START, end=JULY_END)

        close_july(dana)
        batch = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_QBO,
            created_at=SENT_AT,
        )

        assert batch["total_debits"] == july["total_debit"] == july["total_credit"]
        assert batch["total_credits"] == batch["total_debits"]
        assert batch["target"] == models.EXPORT_QBO
        assert batch["granularity"] == models.EXPORT_SUMMARY
        assert batch["entries"] == len([r for r in july["rows"] if r["debit"] or r["credit"]])
        assert batch["content_hash"] and len(batch["content_hash"]) == 64
        assert batch["created_by_user_id"] == str(dana.id)

        stored = models.ExportBatch.objects.get(pk=batch["batch_id"])
        # Every row carries the ref the mapping page held AT SEND (BR-TEN-020).
        assert all(row["target_ref"] for row in stored.payload)
        assert {row["code"]: row["target_ref"] for row in stored.payload}["4100"] == "79"

        audited = [r for r in audit_rows if r["action"] == "export.batch_created"]
        assert audited and audited[-1]["after"]["content_hash"] == batch["content_hash"]
        # ⚠ CR-005 (2026-08-17) SEEDS THE `EXP-` SERIES FOR EVERY TENANT, so
        # LE-5's number now comes out of the product here too — this case used
        # to assert the absence and asserts the number instead. The absence path
        # is still covered, one case down, by removing the row.
        assert batch["batch_no"] == "EXP-2607-0001"
        assert batch["unavailable"] == ()


def test_us_led_016_tc1b__the_exp_series_numbers_the_batch_when_it_exists(brazos, dana):
    """The other half of the same fact, INVERTED BY CR-005 (2026-08-17).

    It used to read: nothing is wrong with the ALLOCATION, only the seed is
    missing — give the tenant the row BR-TEN-041 names and the number appears.
    The row is now seeded at provisioning, so the interesting half is the other
    one: an export batch whose series row has been REMOVED still hands over the
    month, and says by name that it did so unnumbered rather than inventing a
    batch number an ERP would then key on.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        tenancy_models.NumberSeries.objects.filter(
            tenant=brazos, series=core_numbering.EXPORT_BATCH
        ).delete()
        close_july(dana)
        batch = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_QBO,
            created_at=SENT_AT,
        )
        assert batch["batch_no"] is None
        assert "export_batch_number_series_is_not_seeded" in {
            gap["code"] for gap in batch["unavailable"]
        }


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — idempotency (THE TEST THIS FILE EXISTS FOR)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc2__a_second_export_of_the_same_window_is_blocked_with_the_link(
    brazos, dana
):
    """US-LED-016 TC-2 / T5-07: *"Blocked with a link to the existing batch —
    no double-handover; a DIFFERENT target for the same period is its own
    recorded batch."*

    And T5-07 step 3: the OTHER granularity over the same covered window is
    refused too — *"idempotency is per covered window, whichever granularity was
    chosen"*.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close_july(dana)

        first = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_QBO,
            created_at=SENT_AT,
        )

        with pytest.raises(exports.ExportError) as exc:
            exports.create_export_batch(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                target=models.EXPORT_QBO,
                created_at=SENT_AT,
            )
        assert "already covered" in str(exc.value)
        assert exc.value.existing_batch["batch_id"] == first["batch_id"]

        # T5-07 step 3 — the other granularity, and a WEEK inside the month.
        with pytest.raises(exports.ExportError):
            exports.create_export_batch(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                target=models.EXPORT_QBO,
                granularity=models.EXPORT_WEEKLY,
                created_at=SENT_AT,
            )
        with pytest.raises(exports.ExportError) as overlap:
            exports.create_export_batch(
                dana,
                period_start=date(2026, 7, 6),
                period_end=date(2026, 7, 12),
                target=models.EXPORT_QBO,
                created_at=SENT_AT,
            )
        assert "already covered" in str(overlap.value)

        # A DIFFERENT target is its own batch (US-LED-016 TC-2's second clause).
        csv_batch = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_CSV,
            created_at=SENT_AT,
        )
        assert csv_batch["batch_id"] != first["batch_id"]
        assert len(exports.export_history()) == 2
        assert len(exports.export_history(target=models.EXPORT_QBO)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# The closed-period gate (BR-LED-017 / T5-08)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_br_led_017__an_open_period_may_not_be_exported(brazos, dana):
    """T5-08 / J19 step 3: *"REFUSED — export requires the covered period
    CLOSED (the L-3b gate); no batch created."*"""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)

        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=models.EXPORT_QBO
        )
        assert preview["period_closed"] is False
        assert preview["sendable"] is False

        with pytest.raises(exports.ExportError) as exc:
            exports.create_export_batch(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                target=models.EXPORT_QBO,
                created_at=SENT_AT,
            )
        assert "NOT CLOSED" in str(exc.value)
        assert "numbers that can still move" in str(exc.value)
        assert models.ExportBatch.objects.filter(tenant=brazos).count() == 0

        # The ratified door: close it, and the same call succeeds (T5-08 step 5).
        close_july(dana)
        assert exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_QBO,
            created_at=SENT_AT,
        )["batch_id"]


def test_us_led_016_br_led_017__weekly_granularity_slices_the_closed_period(brazos, dana):
    """BR-LED-017 (PO L-1, *"keep it flexible"*): *"one summary JE per CLOSED
    period (default) OR weekly JEs over the closed period — chosen per export,
    both idempotent per covered window."*

    The weekly export covers the SAME window and totals the same money; what
    changes is how many rows the ERP receives.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close_july(dana)

        summary = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=models.EXPORT_CSV
        )
        weekly = exports.export_preview(
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_CSV,
            granularity=models.EXPORT_WEEKLY,
        )
        assert weekly["entries"] > summary["entries"]
        assert {(row.window_start, row.window_end) for row in weekly["rows"]} != {
            (JULY_START, JULY_END)
        }
        # Every weekly slice is INSIDE the closed period — never a day outside it.
        assert min(row.window_start for row in weekly["rows"]) == JULY_START
        assert max(row.window_end for row in weekly["rows"]) == JULY_END
        # The FOOTING gate is asserted on the period, which balances either way.
        assert weekly["balanced"] is True and summary["balanced"] is True


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — drill-back, TC-4 — the dimension extracts
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc3__every_figure_drills_back_to_its_dimensioned_lines(brazos, dana):
    """US-LED-016 TC-3 / LE-5: *"Auditor asks 'what is the 506.31?' → the revenue
    figure opens to every dimensioned line behind it."*

    LE-1's revenue is **506.31** = 226.90 (WE-1) + 15.00 (WE-3) + 264.41 (WE-7B)
    and every one of those postings is inside July, so the July window carries
    the frozen figure whole.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close_july(dana)
        batch = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_QBO,
            created_at=SENT_AT,
        )

        revenue_codes = [
            row["code"]
            for row in models.ExportBatch.objects.get(pk=batch["batch_id"]).payload
            if row["code"].startswith("4")
        ]
        total = sum(
            (
                Decimal(row["credit"])
                for row in models.ExportBatch.objects.get(pk=batch["batch_id"]).payload
                if row["code"].startswith("4")
            ),
            Decimal("0"),
        )
        assert total == LE1_REVENUE  # 506.31, ❄️ from LE-1

        drilled = exports.drill_back(batch_id=batch["batch_id"], code=revenue_codes[0])
        assert drilled["lines"], "an exported figure with no lines behind it is unanswerable"
        assert all(line["source_type"] for line in drilled["lines"])
        assert all(JULY_START <= line["entry_date"] <= JULY_END for line in drilled["lines"])

        with pytest.raises(exports.ExportError):
            exports.drill_back(batch_id=batch["batch_id"], code="9999")


def test_us_led_016_tc4__the_dimension_extracts_are_the_read_model_not_a_second_sum(
    brazos, dana
):
    """US-LED-016 TC-4: *"By service / by premises / by authority files … each
    summing to the exported figures."*

    Each is `apps.ledger.reporting`'s existing read, passed through. by-premises
    reports `available=False` and NAMES the figure it cannot attribute —
    `journal_lines.premises_id` is NULL on every line in the product (US-LED-002
    unbuilt), which is a gap this lane inherits and does not paper over.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)

        by_service = exports.dimension_extract(
            kind="service", period_start=JULY_START, period_end=JULY_END
        )
        assert by_service["available"] is True and by_service["rows"]

        # ⚠ This assertion was `available is False` until 2026-08-16: the
        # premises extract could not be built because no journal line carried
        # the dimension. US-LED-002 stamps it now, so the extract is real and
        # the export carries LE-6's three premises rows out to the ERP.
        by_premises = exports.dimension_extract(
            kind="premises", period_start=JULY_START, period_end=JULY_END
        )
        assert by_premises["available"] is True and by_premises["rows"]

        by_authority = exports.dimension_extract(
            kind="authority", period_start=JULY_START, period_end=JULY_END
        )
        assert "rows" in by_authority

        with pytest.raises(exports.ExportError):
            exports.dimension_extract(
                kind="account", period_start=JULY_START, period_end=JULY_END
            )


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — the missing ref, TC-6 — the drift
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc5__a_missing_qbo_ref_blocks_atomically_and_names_the_account(
    brazos, dana
):
    """US-LED-016 TC-5 / US-LED-006 TC-5: *"Export blocked naming `6900 · Bad
    debt` (atomic-fail pattern) — nothing partial hands over; CSV/IIF
    (code-addressed) remain available."*"""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana, skip=("1200",))
        close_july(dana)

        with pytest.raises(exports.ExportError) as exc:
            exports.create_export_batch(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                target=models.EXPORT_QBO,
                created_at=SENT_AT,
            )
        message = str(exc.value)
        assert "1200" in message and "Accounts receivable" in message
        assert "ATOMIC block" in message
        assert models.ExportBatch.objects.filter(tenant=brazos).count() == 0

        # CSV addresses accounts by code+name and is unaffected.
        assert exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_CSV,
            created_at=SENT_AT,
        )["batch_id"]


def test_us_led_016_tc6__drifting_books_refuse_to_hand_over(brazos, dana):
    """US-LED-016 TC-6: *"The drift is a release blocker (BR-LED-007) — no
    clean-looking handover over broken books."*

    Drift is only reachable through a posting-service BYPASS, which is what
    BR-LED-007 says and what `ledger/0004`'s sole-writer trigger makes hard. It
    is simulated here the only way a test can: a raw line insert with the write
    window open, which is exactly the bypass the rule names.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close_july(dana)

        # Inside JULY specifically — LE-1's opening entry is dated at the June 30
        # cutover, and a bypass hung on that one would drift a window this export
        # does not cover.
        entry = models.JournalEntry.objects.filter(
            tenant=brazos,
            status=models.JE_POSTED,
            entry_date__gte=JULY_START,
            entry_date__lte=JULY_END,
        ).first()
        posting._set_write_window(posting.WRITE_WINDOW_OPEN)
        try:
            models.JournalLine.objects.create(
                tenant=brazos,
                journal_entry=entry,
                ledger_account=gl(brazos, "4100", "revenue"),
                side=models.SIDE_CREDIT,
                amount=Decimal("10.00"),
                source_type="bypass",
                source_id=entry.pk,
            )
        finally:
            posting._set_write_window(posting.WRITE_WINDOW_SHUT)

        with pytest.raises(exports.ExportError) as exc:
            exports.create_export_batch(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                target=models.EXPORT_QBO,
                created_at=SENT_AT,
            )
        assert "does not FOOT" in str(exc.value)
        assert "RELEASE BLOCKER" in str(exc.value)
        assert models.ExportBatch.objects.filter(tenant=brazos).count() == 0


def test_us_led_016_role_gate__an_executive_may_not_hand_the_books_over(brazos, dana):
    """An executive reads the books, a clerk hands them over.

    ⚠ **STILL A READING, AND THIS DOCSTRING NO LONGER BORROWS THE CLOSE'S
    (amended 2026-09-24).** It said *"the same reading of OQ-175 the close
    carries"* and pointed at `close.ROLE_GATE_IS_A_READING`; the close's reading
    became a RULING that day and the marker is retired, so the pointer would now
    read as *ratified*. **Handing the books to an ERP was never put to the PO** —
    OQ-175 (2026-08-12) was about REVERSING an entry and 2026-09-24 was about
    CLOSING A MONTH. EP-LED-05 §8 holds the flag; it returns to the agenda."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close_july(dana)
        with pytest.raises(errors.AuthError):
            exports.create_export_batch(
                executive_actor(),
                period_start=JULY_START,
                period_end=JULY_END,
                target=models.EXPORT_QBO,
                created_at=SENT_AT,
            )


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc7__batches_codes_and_entries_never_cross(brazos, dana, lonestar, erin):
    """US-LED-016 TC-7: *"Its batches/codes/entries only (RLS); its EXP- series
    independent."* Both tenants export THEIR July and neither sees the other's."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close_july(dana)
        mine = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=models.EXPORT_CSV,
            created_at=SENT_AT,
        )

    with tenant_ctx(lonestar):
        with_monthly_fiscal_year(erin)
        assert exports.export_history() == ()
        # Lone Star's own July is NOT covered by Brazos Bend's batch.
        assert (
            exports.overlapping_batch(
                period_start=JULY_START, period_end=JULY_END, target=models.EXPORT_CSV
            )
            is None
        )
        with pytest.raises(exports.ExportError):
            exports.drill_back(batch_id=mine["batch_id"], code="4100")

    with tenant_ctx(brazos):
        assert len(exports.export_history()) == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-016@0007led (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-016 §1-§8 · EP-LED-02-chart-mapping.md US-LED-006 §1-§8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-004/007/014/015/017 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-5 + LE-1 · 08-qa/01-e2e/journeys/J19-month-end-close.md steps 3-5 + T5-07 + T5-08 · 04-docs/02-decisions/02-database-design-brief.md Addendum r13 #4 + DB-12)
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(no API half in this lane) E=deferred(no frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST — with the closed-period gate removed an OPEN July
#         exported; with `uq_export_batches_period_target` and the overlap check
#         removed July exported TWICE to QuickBooks; with the ref check removed a
#         payload with a null target_ref handed over
# exceptions: LE-5's **598.69** is the WHOLE-BOOK footing (LE-1's opening entry
#         is dated at the June 30 cutover on purpose), so the JULY window is its
#         own balanced subset and the export's totals are asserted to EQUAL the
#         trial balance rather than to equal 598.69 — the property that matters
#         is one derivation, not one constant · no FILE is produced: BR-LED-020
#         makes v1 a file export and this lane records the batch and its payload,
#         which is what a file renders from · the drift case OPENS THE WRITE
#         WINDOW deliberately, because BR-LED-007 says a bypass is the only way
#         drift happens and a test that could not simulate one could not prove the
#         blocker
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# P5.4 — A HANDOVER GETS AN ANSWER, NOT JUST A SEND
# ══════════════════════════════════════════════════════════════════════════
#
# The blueprint's own sentence (p018): *"Nothing reports back whether the
# accounting package accepted it."* `export_batches` recorded who sent what and
# when, in full, and then the handover ended.
#
# WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per hard-won law 7
# ---------------------------------------------------------------------------
# **(a) A FIXTURE THAT ONLY EVER RECORDS `accepted`.** `partial` is the answer
# that actually arrives — the package refuses two lines and takes thirty — and a
# suite that never writes one would be green over a state nothing produces.
# **(b) ASSERTING AN UNANSWERED BATCH IS *NOT ACCEPTED*.** That is true of a
# rejected one too. The case asserts `ack_state is None` BY IDENTITY, because
# *nobody has said* and *they said no* are different facts (DEF-127).
# **(c) A CORRECTION THAT LEAVES NO TRAIL.** An answer may be corrected, so the
# audit row is what makes that safe — and it is asserted, not assumed.


ACK_AT = datetime(2026, 8, 6, 9, 30, tzinfo=dt_timezone.utc)


def _july_batch(brazos, dana):
    with_monthly_fiscal_year(dana)
    july_books(brazos, dana)
    map_refs(brazos, dana)
    close_july(dana)
    return exports.create_export_batch(
        dana,
        period_start=JULY_START,
        period_end=JULY_END,
        target=models.EXPORT_QBO,
        created_at=SENT_AT,
    )


@pytest.mark.django_db
def test_p5_4__a_batch_nobody_has_answered_for_carries_NO_STATE(brazos, dana):
    """⚠ **`None`, NOT `pending` AND NOT `failed`** — per (b).

    There is no callback in a file handover (`BR-LED-020` makes direct connect
    v2), so an unanswered batch is the ORDINARY case and always will be until a
    clerk writes down what the accountant told them. A default state here would
    put a claim on a screen that nobody made.
    """
    with tenant_ctx(brazos):
        batch = _july_batch(brazos, dana)
    assert batch["ack_state"] is None
    assert batch["ack_at"] is None
    assert batch["ack_reference"] is None
    assert batch["ack_by_user_id"] is None


@pytest.mark.django_db
def test_p5_4__the_three_answers_are_recorded_with_who_when_and_their_reference(
    brazos, dana, audit_rows
):
    """`P5.4`'s outcome: *a handover has an answer, not just a send.*

    ⚠ **`acknowledged_at` IS THE CALLER'S AND NO CLOCK IS READ** (`BR-TEN-043`).
    The import happened at 09:30 on the 6th; the batch was SENT at 17:00 on the
    5th, and the two moments stay apart.

    ⚠ **`partial` IS EXERCISED**, per (a) — it is the answer that actually
    arrives and the one a finance officer most needs to see.
    """
    with tenant_ctx(brazos):
        batch = _july_batch(brazos, dana)
        answered = exports.record_acknowledgement(
            dana,
            batch_id=batch["batch_id"],
            state=models.ACK_PARTIAL,
            acknowledged_at=ACK_AT,
            reference="QBO-IMP-88214",
            note="Two lines refused: 6900 and 2200-01 are not in our chart.",
        )

    assert answered["ack_state"] == models.ACK_PARTIAL
    assert answered["ack_at"] == ACK_AT, "their moment, not ours"
    # ⚠ **THE SEND'S OWN RECORD IS UNTOUCHED**, asserted on the fields that
    # actually carry it. NOT on `created_at`: that column is `auto_now_add`, so
    # it is the row's write time and not `create_export_batch`'s `created_at`
    # argument — a first draft of this case asserted it and was measuring the
    # wrong thing. The argument governs the idempotency stamp, and the batch's
    # identity is its hash and its window.
    assert answered["content_hash"] == batch["content_hash"]
    assert answered["entries"] == batch["entries"]
    assert answered["period"] == batch["period"]
    assert answered["created_by_user_id"] == batch["created_by_user_id"]
    assert answered["ack_reference"] == "QBO-IMP-88214"
    assert "6900" in answered["ack_note"]
    assert answered["ack_by_user_id"] == str(dana.id)

    # Hard rule 7 — and per (c), the trail is what makes a correction safe.
    trail = [r for r in audit_rows if r["action"] == "export_batch.acknowledged"]
    assert len(trail) == 1, trail
    assert trail[-1]["before"]["ack_state"] is None
    assert trail[-1]["after"]["ack_state"] == models.ACK_PARTIAL


@pytest.mark.django_db
def test_p5_4__an_answer_may_be_corrected_and_the_trail_keeps_both(
    brazos, dana, audit_rows
):
    """An accountant who says *accepted* on Tuesday and finds two refused lines
    on Wednesday must be able to say so — per (c).

    ⚠ **THIS IS NOT A WIDENING OF HARD RULE 4.** That rule names issued
    invoices, invoice lines, payments and journal entries. `export_batches` is a
    RECORD OF A HANDOVER and none of them, and **nothing about the books, the
    payload, the totals or the content hash moves** — which is asserted here
    rather than claimed.
    """
    with tenant_ctx(brazos):
        batch = _july_batch(brazos, dana)
        exports.record_acknowledgement(
            dana,
            batch_id=batch["batch_id"],
            state=models.ACK_ACCEPTED,
            acknowledged_at=ACK_AT,
        )
        corrected = exports.record_acknowledgement(
            dana,
            batch_id=batch["batch_id"],
            state=models.ACK_REJECTED,
            acknowledged_at=ACK_AT,
            note="Their import was rolled back.",
        )

    assert corrected["ack_state"] == models.ACK_REJECTED
    assert corrected["content_hash"] == batch["content_hash"], "the handover itself is untouched"
    assert corrected["total_debits"] == batch["total_debits"]
    assert corrected["entries"] == batch["entries"]

    trail = [r for r in audit_rows if r["action"] == "export_batch.acknowledged"]
    assert len(trail) == 2
    assert trail[-1]["before"]["ack_state"] == models.ACK_ACCEPTED
    assert trail[-1]["after"]["ack_state"] == models.ACK_REJECTED


@pytest.mark.django_db
def test_p5_4__a_state_the_package_cannot_have_said_is_refused_by_name(brazos, dana):
    """Three answers, and `pending` is deliberately not one of them: a batch
    nobody has answered for carries NO state, which is a different fact."""
    with tenant_ctx(brazos):
        batch = _july_batch(brazos, dana)
        with pytest.raises(exports.ExportError) as refused:
            exports.record_acknowledgement(
                dana,
                batch_id=batch["batch_id"],
                state="pending",
                acknowledged_at=ACK_AT,
            )
    assert "accepted" in str(refused.value) and "rejected" in str(refused.value)
    assert "partial" in str(refused.value)


@pytest.mark.django_db
def test_p5_4__another_utilitys_batch_is_unknown_rather_than_forbidden(
    brazos, dana, lonestar, erin
):
    """HR-1 — existence does not leak. A foreign batch and a batch that never
    existed refuse identically, which is the same posture `drill_back` takes."""
    with tenant_ctx(brazos):
        batch = _july_batch(brazos, dana)
    with tenant_ctx(lonestar):
        with pytest.raises(exports.ExportError) as refused:
            exports.record_acknowledgement(
                erin,
                batch_id=batch["batch_id"],
                state=models.ACK_ACCEPTED,
                acknowledged_at=ACK_AT,
            )
    assert "is not one of this tenant's batches" in str(refused.value)

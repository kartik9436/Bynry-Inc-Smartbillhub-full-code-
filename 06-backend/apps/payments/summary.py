# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-005 (S32 Payments summary: today, method mix, failed,
#           collections, needs-attention)   Screens: S32
# Rules:    BR-PAY-027 (summary figures are read-models over the same data the
#           S33 capability row serves — counts tie to lists EXACTLY) ·
#           BR-PAY-015 (autopay capture intents are visible as a chip; NO
#           charging and NO retry exists v1) · BR-PAY-018 (the returned-mail
#           needs-attention chip) · BR-PAY-021 (today = POSTED today) · the
#           method mix is POSTED + CLEARED money by POSTING date (PO ruling
#           2026-10-21, DEF-PAY-10342) · BR-PAY-020 (write-offs YTD) ·
#           CLAUDE.md rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_pay_005_summary.py
# Impacts:  apps/payments/api.py (GET /payments/summary) ·
#           apps/payments/outstandings.py (the collections panel is its
#           aggregate, never a second count) ·
#           07-frontend/src/features/payments/PaymentsPage.tsx (S32 tab)
# ───────────────────────────────────────────────────────
"""S32 — the five panels, every figure tied to a list a clerk can open.

US-PAY-005 §1's own requirement, and the reason this module holds no stored
aggregate anywhere: *"Every figure ties to the underlying rows — no stored
aggregates"*. A KPI that is a materialised number is a KPI that disagrees with
its own list the first time a job fails halfway.

    TODAY            Σ / count / average of payments POSTED today (BR-PAY-021's
                     record-entered side — this is the drawer, and it ties to
                     S33 filtered `posted_at = today` exactly).
    METHOD MIX MTD   per-method share of money POSTED this month that stands
                     (`balance_rule.RECEIPT_STATUSES` — posted + cleared), by
                     POSTING date. ⚠ It was money CLEARED this month, by
                     `cleared_at`, until CR-186-BRC10 made `cleared` mean
                     *reconciled with the bank*; the PO ruled on 2026-10-21
                     (decision log "Two CR-186 follow-up rulings", item 2;
                     `DEF-PAY-10342`) that it reads the posting date — a card
                     payment taken 14 Oct and reconciled 16 Oct is in the mix
                     from 14 Oct. US-PAY-005 TC-2's "cleared" date is
                     superseded by that ruling.
    FAILED           `payments.status = failed` plus the reversed rows, with
                     their reason. **Route-to only.** BR-PAY-015 makes autopay
                     capture-only in v1, so *"Retry"* opens a fresh recording
                     (US-PAY-001) — a NEW row, never an edit — and no charging
                     path exists anywhere for this screen to call.
    COLLECTIONS      accounts owing and total owed, taken from
                     `outstandings.py`'s read-model rather than counted again
                     here, plus write-offs YTD over approved `write_offs`.
    CHIPS            open autopay capture intents (US-PAY-024) and the open
                     returned-mail queue (US-PAY-016).

**THE AVERAGE IS None WHEN THE COUNT IS ZERO**, not 0.00. A utility that took no
money today did not take an average payment of nothing; A18's zero-state is a
sentence, and a 0.00 in an average tile is a claim about a division that never
happened.

**NOTHING HERE ROUNDS.** Money crosses the wire at four decimals and `MoneyCell`
is the single formatter (2dp on screen). The one place a percentage is produced
— the method mix — is quantised to one decimal for display and its numerator and
denominator are both reported so the screen can show the working.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum

from core import tenancy as core_tenancy

from apps.payments import bad_debt, balance_rule, models, outstandings, settings_seam
from apps.payments.collections_models import DeliveryReturnEvent

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """One calendar day, from midnight to midnight **in the UTILITY's own zone**.

    **DEF-094's sweep.** These bounds are not a filter chip — they are what
    decides which money is in *"today"* and which is in the method mix, so a
    boundary in the wrong zone moves a figure on the S32 tile. This used to
    anchor at midnight **UTC**, and BR-TEN-081 (PO 2026-08-12, OQ-153 CLOSED)
    says a calendar day means the utility's own day.

    **Worked, on a Houston utility (`America/Chicago`, UTC−5 in August):** a
    payment recorded at **22 Aug 20:00 Central** is stored `2026-08-23T01:00Z`.
    Under UTC bounds it fell OUT of the 22 August tile and INTO the 23rd — an
    evening's takings on the wrong day, every day, and the same shift is what
    BR-PAY-025 groups a deposit batch by and BR-REP-013 reports on. At a month
    edge it is the wrong month's books.

    The zone comes through the seam that reads tenancy's OWN `tenant_timezone()`
    — the same function `tenant_today()` reads — so the day a figure is
    bucketed into is the day the screen calls today. That equality is the whole
    of DEF-094: the two halves must not each be reasonable and disagree.
    """
    zone = settings_seam.tenant_timezone()
    return (
        datetime.combine(day, time.min, tzinfo=zone),
        datetime.combine(day, time.max, tzinfo=zone),
    )


@dataclass(frozen=True)
class SummaryView:
    """Everything S32 renders, in one shape."""

    as_of: date
    today: dict[str, Any]
    method_mix: list[dict[str, Any]]
    failed: list[dict[str, Any]]
    collections: dict[str, Any]
    chips: dict[str, Any]
    problems: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "today": self.today,
            "method_mix": self.method_mix,
            "failed": self.failed,
            "collections": self.collections,
            "chips": self.chips,
            "problems": [dict(problem) for problem in self.problems],
        }


def summary(*, as_of: date) -> SummaryView:
    """S32's five panels for THIS tenant, as of one business day.

    `as_of` is an argument and never a clock (BR-TEN-043) — the same reason
    `outstandings` takes one: a dashboard that cannot be asked for yesterday
    cannot be reconciled against yesterday's day-end.
    """
    tenant_id = _tenant_id()
    start, end = _day_bounds(as_of)

    posted_today = models.Payment.objects.filter(
        tenant_id=tenant_id, posted_at__gte=start, posted_at__lte=end
    ).filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)  # CR-186-BRC10
    taken = posted_today.aggregate(total=Sum("amount"), count=Count("id"))
    count = taken["count"] or 0
    total = taken["total"] or ZERO
    today = {
        "amount": f"{total:.4f}",
        "count": count,
        # None, never 0.00 — see the module docstring.
        "average": f"{(total / count):.4f}" if count else None,
    }

    # DEF-094 — the month's first midnight in the UTILITY's zone, for the same
    # reason `_day_bounds` uses it: a month edge in the wrong zone puts an
    # evening's posted money in the previous month's mix.
    month_start, _ = _day_bounds(as_of.replace(day=1))
    # DEF-PAY-10342 (PO ruling 2026-10-21) — the month's money is what was
    # POSTED this month and stands: `balance_rule.RECEIPT_STATUSES`, the one
    # named set for posted + cleared. Since CR-186-BRC10 `cleared` means
    # reconciled with the bank, which lags by days, and reconciling a batch
    # must not move money between months. `cancelled` is never in it.
    posted_mtd = models.Payment.objects.filter(
        tenant_id=tenant_id,
        status__in=balance_rule.RECEIPT_STATUSES,
        posted_at__gte=month_start,
        posted_at__lte=end,
    )
    mix_total = posted_mtd.aggregate(total=Sum("amount"))["total"] or ZERO
    method_mix = []
    for row in (
        posted_mtd.values("method__code", "method__name")
        .annotate(amount=Sum("amount"), count=Count("id"))
        .order_by("-amount")
    ):
        amount = row["amount"] or ZERO
        method_mix.append(
            {
                # A payment with no instrument (a credit, an adjustment) has a
                # null method and is reported as such rather than folded into
                # another method's share — B2 leaves the column nullable and a
                # bucket labelled "" would be a method nobody can filter on.
                "method": row["method__code"],
                "method_name": row["method__name"],
                "amount": f"{amount:.4f}",
                "count": row["count"],
                "share": f"{(amount / mix_total * HUNDRED):.1f}" if mix_total > ZERO else None,
            }
        )

    failed = [
        {
            "payment_id": str(payment.pk),
            "payment_no": payment.payment_no,
            "account_id": str(payment.account_id),
            "amount": f"{payment.amount:.4f}",
            "status": payment.status,
            # A reversal states its reason on the REVERSING row (BR-PAY-002 —
            # the original is immutable and stays `cleared`, which is also the
            # truth: it did clear, and then it came back).
            "reason": payment.reversal_reason,
            "posted_at": payment.posted_at.isoformat(),
        }
        for payment in models.Payment.objects.filter(
            tenant_id=tenant_id, status=models.PAYMENT_FAILED
        ).order_by("-posted_at")[:50]
    ]

    ar = outstandings.outstandings(as_of=as_of)
    # ── write-offs YTD ──────────────────────────────────────────────────────
    # ⚠ **THIS SUMMED `status=approved` AND NOTHING ELSE UNTIL 2026-09-01, AND
    # CR-059 CS-25 BROKE IT THE DAY IT LANDED (`DEF-3124`).** A wrongly-approved
    # write-off is now corrected by a NEW ROW at status `reversed`, and the sum
    # above could not see one — so a 948.20 write-off approved in August and
    # reversed in September would have left this KPI reading **948.20** while
    # the bad-debt report on the next screen read **0.00**. Two of our own
    # numbers, disagreeing, on the same fact.
    #
    # Taken from `bad_debt.counted_row_totals` rather than re-derived here, for
    # the reason the line below already gives about `total_owed`: two counts of
    # one fact eventually disagree (hard-won law 5). That read nets `reversed`
    # against `approved` over the same window and is the ONE place the netting
    # is written down.
    written_off = Decimal(
        bad_debt.counted_row_totals(start=as_of.replace(month=1, day=1), end=as_of)["net"]
    )

    collections = {
        # Taken from the S34 read-model, NOT counted again — US-PAY-005 TC-4
        # requires the panel to tie to S34 exactly, and two counts of one fact
        # eventually disagree (hard-won law 5).
        "accounts_owing": len(ar.rows),
        "total_owed": f"{ar.total_owed:.4f}",
        "write_offs_ytd": f"{written_off:.4f}",
    }

    chips = {
        "autopay_scheduled": models.AutopayCaptureIntent.objects.filter(
            tenant_id=tenant_id, status=models.INTENT_AWAITING_RAILS
        ).count(),
        "returned_mail": DeliveryReturnEvent.objects.filter(
            tenant_id=tenant_id, resolved_on__isnull=True
        )
        .values("account_id")
        .distinct()
        .count(),
    }

    return SummaryView(
        as_of=as_of,
        today=today,
        method_mix=method_mix,
        failed=failed,
        collections=collections,
        chips=chips,
        problems=ar.problems,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-005@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md US-PAY-005 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-027/015/018/021 · 04-docs/05-modules/08-payments/03-field-map.md §1 · 05-prototype/UtilityBilling.html S32 · 08-qa/01-e2e/journeys/J2-read-to-cash.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_005_summary.py (the zero-state average and the collections tie-out were driven RED first) · pytest tests -m isolation✔
# exceptions: (1) NO STORED AGGREGATES ANYWHERE — US-PAY-005 §1's own requirement; every figure is a query over the rows the lists serve
#         (2) THE AVERAGE IS null ON A ZERO COUNT, never 0.00 (A18 zero-state). A 0.00 average is a claim about a division that never happened
#         (3) NO RETRY AND NO CHARGE PATH on the Failed panel (BR-PAY-015). "Retry" is a fresh recording through US-PAY-001 — a NEW row — and this module offers no action of its own
#         (4) THE COLLECTIONS PANEL DELEGATES to `outstandings.outstandings` rather than counting debtors again, so the tile and S34 cannot disagree (US-PAY-005 TC-4)
#         (5) DSO IS NOT SERVED HERE EITHER — it rides `problems` from the outstandings read-model (BR-REP-011 is reports')
#         (6) THE FAILED PANEL IS CAPPED AT 50 ROWS. A panel is not a list; the full set is S33 filtered `status=failed`, which is the screen the panel links to
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

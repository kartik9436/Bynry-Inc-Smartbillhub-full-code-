# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-26 · task 64 — "Report what was written off, and why".
#           The CR's own words: *"the rule splits this deliberately — payments
#           owns the transaction, the ledger posts it, FINANCE REPORTS IT. The
#           first two exist. Bad debt by reason, by month and by service is what
#           a utility's board actually asks for, and nothing assembles it."*
# Story:    US-PAY-012 (write-offs)   Screens: S36 (Finance · Revenue & AR)
# Rules:    BR-PAY-020 (INITIATED in payments, APPROVED + REPORTED in finance —
#           CS-26 adds no new rule and says so: this is the third of the three
#           verbs that rule already names) · BR-PAY-1120 (the four-state set —
#           what `approved` and `reversed` each mean to a bad-debt figure) ·
#           BR-REP-001 (a money report labels its basis) · BR-REP-002 (a report
#           is a READ-MODEL, never a side-maintained number) · BR-TEN-043 /
#           gate G6 (the caller names the window; nothing here reads a clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4dp, percentages
#           6dp, both DISPLAY 2, always beside a CHAR(3) code)
# Tests:    06-backend/tests/test_cr059_cs26_bad_debt_report.py
# Impacts:  apps/payments/writeoffs.py (the rows) · apps/ledger/reporting
#           .gl_totals (the tie-out) · apps/payments/writeoffs_api.py (the door)
# ───────────────────────────────────────────────────────
"""What did we give up on, why, and does the ledger agree — CR-059 CS-26.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file reports the bad-debt figure a
utility's board is shown and ties it to a 🔒 ledger posting, so it is enrolled
under the CLAUDE.md sensitive-path protocol. AI-authored 2026-09-01 under the PO
ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

**IT WRITES NOTHING AND IT MOVES NOTHING.** Every figure is recomputed from the
`write_offs` rows on every call (BR-REP-002), so there is no stored total to go
stale and no second implementation of the arithmetic to disagree with the first.

════════════════════════════════════════════════════════════════════════════
THE SHAPE, ON CS-26's OWN WORKED FIGURES
════════════════════════════════════════════════════════════════════════════
CS-26 states the answer it wants: *"uncollectible 120 days 2,840.00 · 72% ·
deceased, no estate 712.40 · 18% · bankruptcy 387.60 · 10%"*. That is what this
read produces, and the arithmetic is checked in the test file rather than
asserted here:

    uncollectible after 120 days   2,840.00   72.081218 %
    deceased, no estate              712.40   18.081218 %
    customer bankruptcy              387.60    9.837563 %
    ─────────────────────────────────────────────────────
    net bad debt                   3,940.00  100.000000 %

**Percentages are served at SIX decimals and money at FOUR** (hard rule 2, PO
re-sign 2026-08-22: *"MOney 4 decimal, percentage 6 decimal, display both 2
decimal"*). The screen rounds to CS-26's `72%`; this layer never does, because a
report that rounds before it sums is a report whose column does not foot.

════════════════════════════════════════════════════════════════════════════
A REVERSAL IS NETTED, NOT COUNTED — AND THAT IS THE WHOLE OF CS-25 IN A REPORT
════════════════════════════════════════════════════════════════════════════
CS-25 makes a wrongly-approved write-off correctable by a **new row** carrying
status `reversed`. Both rows are positive magnitudes and both are real history,
so this read counts `approved` as bad debt and SUBTRACTS `reversed`. A write-off
of 948.20 approved in August and reversed in September nets to **0.00 over the
year** and appears in BOTH months — August +948.20, September −948.20 — because
that is what happened and a board asking *"what did we write off in August?"*
must not be told a number that changes retroactively.

`requested` and `rejected` are counted NOWHERE. Neither ever posted: a request
is a proposal and a rejection is a refusal, and either one inside a bad-debt
total would be money the utility never gave up.

════════════════════════════════════════════════════════════════════════════
THE LEDGER TIE-OUT, BECAUSE CS-26 ASKS FOR ONE
════════════════════════════════════════════════════════════════════════════
CS-26: *"bad debt by reason and by month, **tying to the ledger's write-off
account**"*, and *"the write-off entry already carries its own source type in the
ledger, so 'what did we write off this year?' can be answered without joining
through payments at all"*.

So the two figures are computed INDEPENDENTLY — this module's from its own rows,
the ledger's from `journal_lines` on `source_type='write_off'` narrowed to the
account the tenant DESIGNATES `write_off` — and then compared. **They are served
side by side with their difference**, never reconciled into one number: two
readings that agree are evidence, and one number that hides a disagreement is
how a control stops working. A difference is REPORTED by name.

⚠ **THE TWO WINDOWS ARE NOT THE SAME FACT AND THE HEADER SAYS SO.** This module
groups on `approved_on` — the business date a human decided — while the ledger
groups on `entry_date`, the book date. They are written equal by
`approve_write_off` and by `reverse_write_off`, so the tie-out holds today; a
future path that dated an entry differently would show up here as a difference
rather than as a silently wrong total, which is the point of computing both.

════════════════════════════════════════════════════════════════════════════
WHAT THIS READ DOES NOT ANSWER
════════════════════════════════════════════════════════════════════════════
* **BY SERVICE — `OQ-1300`, RAISED AND NOT ANSWERED.** CS-26's *why* names
  *"by reason, by month and by service"*, and its deliverable names only the
  first two. A write-off is raised against an ACCOUNT at that account's whole
  computed balance; nothing anywhere attributes it across the electric, water
  and gas the account takes, and choosing an attribution — pro-rata on the
  period's billed revenue, or on the oldest unpaid bill's composition, or not at
  all — moves the revenue-by-service report every service line is measured on.
  That is a finance policy, not a lane's call. Reported by name on every result
  rather than approximated.
* **BILLING's automatic small-balance write-offs.** `BR-BIL-013` path 5 settles
  a final bill under the tenant's threshold and writes NO `write_offs` row. It
  is a different act with a different control, and a bad-debt report that
  silently mixed the two would tell a board that the manual decisions it
  reviewed were larger than they were. Named, not included.
* **AN ALLOWANCE FOR DOUBTFUL DEBTS.** Everything counted here is a DIRECT
  write-off already approved by a person. Whether the product needs a provision
  model at all is `CR-060 C5`, an open market-entry question, and this read does
  not pre-empt it: there is no provision balance, no ageing-based estimate and
  no release-of-provision line, because none exists to report.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from django.db.models import Count, Sum

from core import tenancy as core_tenancy

from apps.payments.collections_models import (
    WRITE_OFF_APPROVED,
    WRITE_OFF_REASONS,
    WRITE_OFF_REVERSED,
    WriteOff,
)
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")
HUNDRED = Decimal("100")

#: Hard rule 2, PO re-sign 2026-08-22. Money is served at FOUR decimals and
#: percentages at SIX; the screen displays both at two. Nothing here rounds to
#: two, ever — `MoneyCell` is the single formatter and a second one would be a
#: second money policy (hard-won law 5).
MONEY_PLACES = Decimal("0.0001")
PERCENT_PLACES = Decimal("0.000001")

#: The ledger's own words for a bad-debt entry, and the designation that names
#: the account it debits. Both are `ledger_seam`'s constants, restated here as
#: strings rather than imported: this file is a READ and importing a posting
#: seam to borrow two literals would make the report a dependency of the write
#: path. The pair is pinned by a test instead, the shape `writeoffs.QUEUE_MODULE`
#: already uses.
LEDGER_SOURCE_WRITE_OFF = "write_off"
LEDGER_DESIGNATION_WRITE_OFF = "write_off"

#: `OQ-1300` — how a written-off balance is attributed across the services an
#: account takes. RAISED, not answered, and stubbed by ABSENCE rather than by a
#: guess: the read serves reason and month, and says in words that the third cut
#: CS-26's *why* names is not served and why.
OQ_BY_SERVICE = "OQ-1300"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _money(value: Decimal | None) -> str:
    return f"{(value or ZERO).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)}"


def _percent(part: Decimal, whole: Decimal) -> str | None:
    """`part` as a percentage of `whole`, at six decimals — or None.

    **None and 0.000000 are different facts.** A utility that wrote nothing off
    did not write off 0% of anything; `summary.py` takes the same posture with
    its average payment, and A18's zero-state is a sentence rather than a zero.
    A NEGATIVE whole — every write-off in the window reversed and then some — is
    also None: a share of a negative total is a number nobody can read.
    """
    if whole <= ZERO:
        return None
    return f"{(part / whole * HUNDRED).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)}"


def _period(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _one_currency(rows: list[dict[str, Any]]) -> tuple[str | None, tuple[dict[str, Any], ...]]:
    """The one CHAR(3) these rows are in, or a named refusal (DEF-081's shape).

    BR-TEN-016 gives a utility ONE currency and nothing converts, so more than
    one here is a data fault rather than a report to build. Adding 2,840.00 USD
    to 712.40 CAD would produce a number that is true of neither.
    """
    codes = sorted({row["currency"] for row in rows if row.get("currency")})
    if len(codes) > 1:
        return None, (
            {
                "code": "bad_debt_spans_more_than_one_currency",
                "br_ref": "BR-TEN-016",
                "detail": f"these write-offs are recorded in {codes} and a utility has ONE "
                "currency that nothing converts. No total is served, because a sum across two "
                "currencies is a figure that is true of neither.",
            },
        )
    return (codes[0] if codes else None), ()


def _ledger_write_off_totals(*, start: date, end: date) -> dict[str, Any]:
    """What the BOOKS say was written off in the window — computed separately.

    Resolved BY NAME at call time (B1 / G6): payments never imports another
    module's models, and `apps.ledger.reporting.gl_totals` is the ONE derivation
    of *"what is in this account"* — US-LED-008's trial balance consumes the same
    function, so a board figure and the trial balance can never disagree.

    Returns `{"available": bool, "net": Decimal | None, ...}`. Unavailable is a
    reported state, never a zero: *"the ledger says nothing"* and *"the ledger
    says nothing was written off"* are opposite answers and a screen must be
    able to tell them apart.
    """
    unavailable: dict[str, Any] = {"available": False, "net": None}
    try:
        reporting = import_module("apps.ledger.reporting")
        selectors = import_module("apps.ledger.selectors")
    except ImportError:  # pragma: no cover - the ledger app always imports
        return {**unavailable, "reason": "ledger_module_absent"}
    designation_read = getattr(selectors, "gl_account_id_for_designation", None)
    gl_totals = getattr(reporting, "gl_totals", None)
    if not callable(designation_read) or not callable(gl_totals):  # pragma: no cover
        return {**unavailable, "reason": "ledger_publishes_no_read"}
    account_id = designation_read(LEDGER_DESIGNATION_WRITE_OFF)
    if account_id is None:
        return {**unavailable, "reason": "no_write_off_designation"}
    rows = [
        row
        for row in gl_totals(start=start, end=end, source_types=(LEDGER_SOURCE_WRITE_OFF,))
        if str(row.account_id) == str(account_id)
    ]
    if not rows:
        # The account exists and carries no write-off-sourced lines in the
        # window. That IS an answer — zero — and is different from the cases
        # above, so it is reported as available.
        return {"available": True, "net": ZERO, "debit": ZERO, "credit": ZERO, "code": None}
    debit = sum((row.debit for row in rows), ZERO)
    credit = sum((row.credit for row in rows), ZERO)
    return {
        "available": True,
        # An approval DEBITS the write-off account and the CS-25 mirror CREDITS
        # it, so debit − credit is the net bad debt the books carry — the same
        # netting this module does by status, arrived at from the other side.
        "net": debit - credit,
        "debit": debit,
        "credit": credit,
        "code": rows[0].code,
    }


def bad_debt(*, start: date, end: date) -> dict[str, Any]:
    """CS-26's read — bad debt by reason and by month, tied to the ledger.

    `start` and `end` are INPUTS and inclusive, never a clock (BR-TEN-043, gate
    G6): a board pack produced at 23:58 and a re-run at 00:02 must be the same
    document, and a function that read the system date could not be asked for
    last quarter.

    The window is on **`approved_on`** — the business date a human decided —
    which is BR-REP-001's posting basis and is labelled on the result as
    `basis`. A `reversed` row's `approved_on` is the date the reversal was made,
    so a correction lands in the month it was made rather than reaching back and
    rewriting a month the board has already seen.
    """
    if start > end:
        # The rule this enforces is BR-TEN-043 (no clock in this module) and it
        # is named HERE rather than in the sentence: refusal prose reaches the
        # audit row and the server log, and G28 ratchets internal references in
        # it downwards. The `br_ref` below is the machine-readable half.
        raise PaymentRuleError(
            f"the window {start} → {end} ends before it begins, so no period can be reported. "
            "Both dates are the caller's and neither one is read from a clock.",
            br_ref="BR-REP-001",
        )
    rows = list(
        WriteOff.objects.filter(
            tenant_id=_tenant_id(),
            status__in=(WRITE_OFF_APPROVED, WRITE_OFF_REVERSED),
            approved_on__gte=start,
            approved_on__lte=end,
        ).values("reason", "status", "currency", "approved_on", "amount")
    )
    currency, currency_problems = _one_currency(rows)

    by_reason: dict[str, dict[str, Decimal | int]] = {}
    by_month: dict[str, dict[str, Decimal | int]] = {}
    written_off = ZERO
    reversed_total = ZERO
    for row in rows:
        amount = row["amount"] or ZERO
        approved = row["status"] == WRITE_OFF_APPROVED
        reason_bucket = by_reason.setdefault(
            row["reason"], {"written_off": ZERO, "reversed": ZERO, "count": 0}
        )
        month_bucket = by_month.setdefault(
            _period(row["approved_on"]), {"written_off": ZERO, "reversed": ZERO, "count": 0}
        )
        key = "written_off" if approved else "reversed"
        reason_bucket[key] += amount
        month_bucket[key] += amount
        reason_bucket["count"] += 1
        month_bucket["count"] += 1
        if approved:
            written_off += amount
        else:
            reversed_total += amount
    net = written_off - reversed_total

    reason_rows = [
        {
            "reason": reason,
            "written_off": _money(bucket["written_off"]),
            "reversed": _money(bucket["reversed"]),
            "net": _money(bucket["written_off"] - bucket["reversed"]),
            # CS-26's own column. Six decimals, hard rule 2; the screen shows 72%.
            "share_percent": _percent(bucket["written_off"] - bucket["reversed"], net),
            "count": bucket["count"],
            "currency": currency,
        }
        # Largest first — a board reads the top line, and CS-26's own worked
        # shape is ordered that way (2,840.00 · 712.40 · 387.60).
        for reason, bucket in sorted(
            by_reason.items(),
            key=lambda item: (item[1]["written_off"] - item[1]["reversed"]),
            reverse=True,
        )
    ]
    month_rows = [
        {
            "period": period,
            "written_off": _money(bucket["written_off"]),
            "reversed": _money(bucket["reversed"]),
            "net": _money(bucket["written_off"] - bucket["reversed"]),
            "count": bucket["count"],
            "currency": currency,
        }
        # Chronological — a trend read backwards is not a trend.
        for period, bucket in sorted(by_month.items())
    ]

    ledger = _ledger_write_off_totals(start=start, end=end)
    problems: list[dict[str, Any]] = list(currency_problems)
    problems.append(
        {
            "code": "bad_debt_not_split_by_service",
            "br_ref": "BR-PAY-020",
            "detail": "this report answers by REASON and by MONTH. It does not split bad debt "
            "across the services an account takes: a write-off is raised against an account at "
            "its whole computed balance, and nothing in the product attributes that across "
            f"electric, water and gas. Choosing an attribution would move every service's "
            f"revenue line, so it is a finance decision and is raised as {OQ_BY_SERVICE} rather "
            "than approximated here.",
        }
    )
    problems.append(
        {
            "code": "excludes_billing_small_balance_write_offs",
            "br_ref": "BR-BIL-013",
            "detail": "billing settles a final bill under the tenant's small-balance threshold "
            "automatically and writes no write-off row, so those amounts are not in this "
            "report. They are a different act with a different control, and mixing them in "
            "would overstate the decisions a person actually reviewed.",
        }
    )
    if not ledger["available"]:
        problems.append(
            {
                "code": f"ledger_tie_out_unavailable_{ledger.get('reason')}",
                "br_ref": "BR-LED-001",
                "detail": "the books could not be read for the same window, so this figure "
                "stands on its own rather than being confirmed. It is REPORTED rather than "
                "shown as agreement, because an unchecked total and a checked one look "
                "identical on a screen.",
            }
        )
    elif ledger["net"] != net:
        problems.append(
            {
                "code": "ledger_disagrees_with_payments",
                "br_ref": "BR-REP-008",
                "detail": f"this module's rows net to {_money(net)} and the ledger's write-off "
                f"account nets to {_money(ledger['net'])} over the same window — a difference of "
                f"{_money(net - ledger['net'])}. Both are served rather than reconciled into "
                "one number: two readings that agree are evidence, and one number hiding a "
                "disagreement is how a control stops working.",
            }
        )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        # BR-REP-001 — a money report labels its basis, always.
        "basis": "approved_on",
        "currency": currency,
        "written_off": _money(written_off),
        "reversed": _money(reversed_total),
        "net": _money(net),
        "count": len(rows),
        "by_reason": reason_rows,
        "by_month": month_rows,
        # Every reason the database allows, so a screen can render a zero row
        # rather than silently dropping a category nobody used this year.
        "reasons": list(WRITE_OFF_REASONS),
        "ledger": {
            "available": ledger["available"],
            "account_code": ledger.get("code"),
            "net": _money(ledger["net"]) if ledger["net"] is not None else None,
            "agrees": bool(ledger["available"] and ledger["net"] == net),
        },
        "problems": problems,
    }


def bad_debt_accounts(*, start: date, end: date, reason: str | None = None) -> dict[str, Any]:
    """The rows behind one bar — who, how much, and whether it was reversed.

    A share of 72% is not actionable on its own; CS-26's screen is a Finance
    report and the first question a reviewer asks a chart is *"which accounts?"*.
    This is the same window and the same statuses, one row per write-off, so the
    two reads can never disagree about what is in the total.

    ⚠ **THE ACCOUNT NUMBER IS RESOLVED THROUGH CUSTOMERS' OWN QUERYSET**, by
    name, never by importing their models (B1 / BR-TEN-013) — `write_off_queue`'s
    own posture. When customers publishes nothing the number is None and the row
    still serves: a report that refused to list because a display field was
    unreachable would hide the money it exists to show.
    """
    if reason is not None and reason not in WRITE_OFF_REASONS:
        raise PaymentRuleError(
            f"{reason!r} is not a write-off reason. The four this product has are "
            f"{list(WRITE_OFF_REASONS)} — a filter naming a fifth would answer an empty report, "
            "and an empty report and an unanswerable one look identical on a screen.",
            br_ref="BR-PAY-020",
        )
    rows = WriteOff.objects.filter(
        tenant_id=_tenant_id(),
        status__in=(WRITE_OFF_APPROVED, WRITE_OFF_REVERSED),
        approved_on__gte=start,
        approved_on__lte=end,
    )
    if reason is not None:
        rows = rows.filter(reason=reason)
    rows = list(rows.order_by("-approved_on", "-created_at", "-id"))

    from apps.payments import writeoffs

    accounts = writeoffs._accounts_by_id([row.account_id for row in rows])
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "reason": reason,
        "rows": [
            {
                "id": str(row.pk),
                "account_id": str(row.account_id),
                "account_no": getattr(accounts.get(row.account_id), "account_no", None),
                "amount": _money(row.amount),
                "currency": row.currency,
                "reason": row.reason,
                "note": row.note,
                "status": row.status,
                "approved_on": row.approved_on.isoformat() if row.approved_on else None,
                # A reversing row is a correction, not a second write-off, and
                # a report that could not tell them apart would double-count the
                # very rows it nets.
                "reverses_write_off_id": (
                    str(row.reverses_write_off_id) if row.reverses_write_off_id else None
                ),
                "reversal_reason": row.reversal_reason,
            }
            for row in rows
        ],
    }


def counted_row_totals(*, start: date, end: date) -> dict[str, Any]:
    """The two aggregate figures, straight from the database, for a tie-out test.

    Deliberately a SECOND path to the same numbers, computed in SQL rather than
    in the loop above. `bad_debt` sums in Python because it buckets by reason and
    by month in one pass; this asks the database for the totals alone, so a test
    can assert the two agree and a future refactor of the loop cannot quietly
    change what a board is shown.
    """
    aggregate = (
        WriteOff.objects.filter(
            tenant_id=_tenant_id(),
            status__in=(WRITE_OFF_APPROVED, WRITE_OFF_REVERSED),
            approved_on__gte=start,
            approved_on__lte=end,
        )
        .values("status")
        .annotate(total=Sum("amount"), rows=Count("id"))
    )
    totals = {row["status"]: (row["total"] or ZERO, row["rows"]) for row in aggregate}
    approved_total, approved_rows = totals.get(WRITE_OFF_APPROVED, (ZERO, 0))
    reversed_amount, reversed_rows = totals.get(WRITE_OFF_REVERSED, (ZERO, 0))
    return {
        "written_off": _money(approved_total),
        "reversed": _money(reversed_amount),
        "net": _money(approved_total - reversed_amount),
        "count": approved_rows + reversed_rows,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (write-offs — three modules, three verbs) · §8 CS-26 · §11 task 64 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-020 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md US-PAY-012 · 08-qa/01-e2e/journeys/J4-collections.md
# generated: 2026-09-01 by the CR-059 W11 write-off lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 65 owns P10's bad-debt tab) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr059_cs26_bad_debt_report.py (CS-26's own 2,840.00 / 712.40 / 387.60 shares and the reversal netting were driven RED first — see the lane report for the quoted failures)
# exceptions: (1) NO BY-SERVICE SPLIT — `OQ-1300`, RAISED not answered. A write-off names an account and no rule attributes it across services; every result says so by name (prime directive: implement to the boundary, name the gap)
#         (2) NO ALLOWANCE MODEL. Everything here is direct write-off. Whether a provision is required at all is `CR-060 C5`, an open market-entry question this read may not pre-empt
#         (3) BILLING's BR-BIL-013 small-balance settlements are EXCLUDED and named — a different act with a different control, and mixing them would overstate what a person reviewed
#         (4) THE LEDGER FIGURE IS COMPUTED INDEPENDENTLY AND SERVED BESIDE, never reconciled into one number. A difference is reported (BR-REP-008)
#         (5) `_percent` returns None on a zero or negative denominator rather than 0.000000 — `summary.py`'s zero-state posture; a share of nothing is not zero percent
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

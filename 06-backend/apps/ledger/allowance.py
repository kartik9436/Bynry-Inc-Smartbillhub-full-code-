# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C5 / task T15 — "Decide on an allowance for doubtful debts".
#           PO ruling 2026-09-03, over a recommendation to defer.
#           Screens: S42 (the month-end close), S56 (the trial balance)
# Rules:    BR-LED-795 (NEW — the allowance is a standing BALANCE adjusted to a
#           computed target, never an accrual that reverses) · BR-PAY-020
#           (write-off posting — NARROWED, not superseded: direct while the
#           policy is off) · BR-LED-005 (an accrual auto-reverses on day 1, and
#           this is deliberately NOT one) · BR-LED-001 (balanced pairs) ·
#           BR-LED-006 (the close) · BR-TEN-043 (nothing in a money path reads a
#           clock) · CLAUDE.md hard rule 2 (money 4dp, percentages 6dp) · rule 4
#           (financial immutability) · rule 5 (only the posting service writes
#           journal lines) · rule 6 (idempotency) · rule 7 (audit)
# ───────────────────────────────────────────────────────
"""**The allowance for doubtful accounts — C5, ruled and built.**

HUMAN-OWNED (ledger posting and money rounding, both CLAUDE.md 🔒 sensitive
paths). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a recorded human
sign-off.

════════════════════════════════════════════════════════════════════════════
WHAT THE PRODUCT OWNER RULED, AND WHAT THEY WERE TOLD FIRST
════════════════════════════════════════════════════════════════════════════
PO 2026-09-03, verbatim: *"Why I recommended deferring it. Three reasons: let's
do this"* — the heading of the argument FOR deferring, quoted back and chosen
against. The three reasons are in `12-governance/02-decision-log.md` so the
trade is on file rather than in a chat log:

  1. the half that matters already works — writing off a bad debt is live and
     reverses, **$948.20** out in August and back in December, netting to $0.00;
  2. the percentages are a judgment about a utility's own customers, not a
     feature, and honestly setting them needs a year of that utility's history;
  3. most utilities under 3,000 connections are not audited and never book one.

**The PO chose to build it anyway and that is their call to make.** Reason (2)
is why the four rates are TENANT SETTINGS and not constants, and reason (3) is
why the policy is OFF until a utility switches it on.

════════════════════════════════════════════════════════════════════════════
THE WORKED FIGURES, WHICH ARE THE ONES THE PO WAS SHOWN
════════════════════════════════════════════════════════════════════════════
    $9,200.00 current   × 1%   =     92.00
    $3,100.00 1–30 days × 5%   =    155.00
    $1,800.00 31–60     × 20%  =    360.00
    $1,233.30 61+       × 50%  =    616.65
    ──────────────────────────────────────
    $15,333.30 owed            = $1,223.65

and the balance sheet reads *"owed $15,333.30, realistically expect
$14,109.65"*. Every one of those is asserted in
`tests/test_cr060_t15_allowance.py`.

**NOTHING FROZEN MOVES.** No figure here comes from B4 or B5 and none is edited.
The allowance is computed from a tenant's own receivable and a tenant's own
rates; `$1,223.65` is the PO's worked example, held by a test so a drift in the
arithmetic goes red rather than being absorbed.

════════════════════════════════════════════════════════════════════════════
⚠ TRAP 1 — THE DOUBLE COUNT, WHICH IS `DEF-3380` ONE MODULE OVER
════════════════════════════════════════════════════════════════════════════
Today a write-off posts `DR 6900 Bad debt / CR 1200 AR` (BR-PAY-020) — the
DIRECT method. With an allowance in force the expense is taken EARLIER, at the
estimate: `DR 6900 / CR 1290`. The write-off then CONSUMES the allowance it
already paid for: `DR 1290 / CR 1200`.

**If the write-off keeps hitting `6900` while the estimate also does, bad debt
is expensed twice.** That is exactly the shape of `DEF-3380`, where a settled
supplier bill was counted in the balanced section AND summed again in the
register section, and handed an ERP **$4,340.00** against **$3,100.00** actually
bought. `tests/test_cr060_t15_allowance.py::
test_cr060_t15__an_estimate_and_a_write_off_never_both_charge_bad_debt` is the
case written to fail on that arrangement specifically.

The switch lives in `apps/payments/ledger_seam.post_write_off` — ONE place — and
it reads the tenant setting, never a chart row's presence: an account that
exists because somebody clicked around is not a policy.

════════════════════════════════════════════════════════════════════════════
⚠ TRAP 2 — IT IS A BALANCE, NOT AN ACCRUAL
════════════════════════════════════════════════════════════════════════════
`unpaid_cost_accrual` and `unbilled_accrual` post `type=accrual` entries and
`manual_je.run_accrual_auto_reversals` mirrors them on the first morning of the
next period (BR-LED-005). **This one must NOT do that.** An allowance STANDS: it
is the balance sheet's own statement of what the receivable is really worth, and
it is carried from month to month.

So each close ADJUSTS the standing balance to the computed target rather than
posting the target itself:

    target $1,223.65 − standing $0.00     = DR 6900   1,223.65 / CR 1290 1,223.65
    target $1,223.65 − standing $1,223.65 = nothing posted at all
    target   $900.00 − standing $1,223.65 = DR 1290     323.65 / CR 6900   323.65

**The third line is a CREDIT to bad debt, and it is correct**: a month where
collectability improves gives expense back. A lane that copied the accrual's
reversing shape would zero the allowance every month and **every test of a
single month would still pass**, which is why
`test_cr060_t15__the_allowance_is_a_balance_and_never_reverses_on_day_one`
asserts the entry TYPE and asserts that the day-1 sweep leaves it alone.

════════════════════════════════════════════════════════════════════════════
WHERE THE AGEING COMES FROM, AND WHY IT IS NOT THE BOOKS
════════════════════════════════════════════════════════════════════════════
`reporting.GAP_AGING_NEEDS_DUE_DATES` states the constraint in its own words:
*"a journal line carries no due date, so the Current/31–60/61–90/90+ split
cannot be summed out of the books"*. So the split comes through
`payments_seam.aged_receivable`, over `apps.payments.outstandings` — the same
ageing the collections screen shows a clerk, which is the property that matters
more than which module holds it. No ledger code reads a payments table
(BR-TEN-013); the seam resolves a published callable by name.

**A MISSING READ IS UNANSWERABLE AND POSTS NOTHING.** It is never priced at
zero, because a zero target would RELEASE a standing allowance to nil on the
strength of a read that failed — a credit to bad debt that nobody intended, in a
month somebody signs.

════════════════════════════════════════════════════════════════════════════
FOUR RATES OVER FIVE BANDS
════════════════════════════════════════════════════════════════════════════
`payments.outstandings` ages into five: current · 1-30 · 31-60 · 61-90 · 90+.
The PO signed FOUR percentages against FOUR amounts, so `61-90` and `90+` are
both priced by `allowance_rate_61_plus`. Adding a fifth rate would split
$1,233.30 across two bands and move the $1,223.65 the PO has seen, for no
ruling. Pricing 90+ harder is a later setting and not a silent one.

════════════════════════════════════════════════════════════════════════════
LAW 14 — WHAT RUNS WHERE
════════════════════════════════════════════════════════════════════════════
Nothing here catches a database error and continues, so law 14's aborted-
transaction trap does not apply — but this posts money inside a transaction and
leans on `uq_journal_entries_posting_key` for its replay, so the suite is run
against a real PostgreSQL as well as the default SQLite:

    DATABASE_URL=postgres://... DJANGO_SETTINGS_MODULE=config.settings.local \\
    JOBS_EAGER=false pytest tests/test_cr060_t15_allowance.py --create-db
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from django.db.models import Sum

from apps.ledger import (
    chart,
    models,
    payments_seam,
    posting,
    selectors,
    services,
    tenancy_seam,
)
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")

#: Hard rule 2 — money is WRITTEN at four decimals and displayed at two. The
#: quantization happens ONCE, on the movement, immediately before it becomes a
#: journal line; the per-band products are held at full precision so a rounding
#: is not applied four times and then again to the sum (BR-LED-025 — two
#: rounding sites is how two figures start disagreeing).
FOUR_PLACES = Decimal("0.0001")

#: BR-LED-001's mandatory pair, on the entry and on every line. One constant, so
#: the write, the close checklist's read and any drill-back all agree.
SOURCE_ALLOWANCE = "allowance_for_doubtful_accounts"

#: The event half of the replay key (hard rule 6). One string per period,
#: forever, so pressing the button twice produces the same books.
EVENT_ESTIMATED = "estimated"

#: A stable namespace for the period's `source_id`, the twin of
#: `unpaid_cost_accrual.ACCRUAL_NAMESPACE` and for the same reason: an estimate's
#: "document" is a PERIOD, which has no row of its own, so the id is DERIVED
#: from (tenant, period) with uuid5 and is the same every time it is computed. A
#: random uuid here would mint a new posting key on every call and the replay
#: guard would never fire.
ALLOWANCE_NAMESPACE = UUID("6a1f9c72-8d34-5e0b-9f26-51c3d7e0a294")

#: The tenant settings this module reads. Named once so the parameter, the read
#: and the refusal cannot drift apart.
FINANCE_CONTROLS_SLUG = "finance-controls"
ENABLED_KEY = "allowance_for_doubtful_accounts_enabled"
RATE_KEYS: dict[str, str] = {
    payments_seam.BUCKET_CURRENT: "allowance_rate_current",
    payments_seam.BUCKET_1_30: "allowance_rate_1_30",
    payments_seam.BUCKET_31_60: "allowance_rate_31_60",
    #: ⚠ TWO BANDS, ONE RATE — see the module docstring. The PO signed four
    #: percentages against four amounts.
    payments_seam.BUCKET_61_90: "allowance_rate_61_plus",
    payments_seam.BUCKET_90_PLUS: "allowance_rate_61_plus",
}

#: Reported when the tenant has not switched the policy on. It is a STATE and
#: not a failure: the direct write-off is a lawful accounting policy and is what
#: BR-PAY-020 signs.
POLICY_OFF = "allowance_policy_is_not_switched_on"

#: Reported when the ageing could not be read. Nothing is posted.
AGEING_UNAVAILABLE = payments_seam.AGED_RECEIVABLE_UNAVAILABLE

#: Reported when the tenant's chart carries no account for the allowance and one
#: could not be minted.
NO_ALLOWANCE_ACCOUNT = "no_account_carries_the_allowance_designation"

#: Reported when the tenant's chart carries no write-off account. `6900 Bad
#: debt` is seeded and finance-signed, so a tenant reaching this has
#: un-designated it deliberately.
NO_BAD_DEBT_ACCOUNT = "no_account_carries_the_write_off_designation"


class AllowanceError(RuntimeError):
    """An allowance the ledger refuses, with the reason a human can act on.

    Distinct from `posting.PostingError` for the reason
    `UnpaidCostAccrualError` gives: a caller can tell *"the ledger refused the
    ACT"* (the policy is off, the ageing is unreadable, no account carries the
    designation) from *"the books refused the ENTRY"* (unbalanced, foreign
    account, a third decimal) without matching on prose.

    The prose is long because every one of these names the rule it enforces and
    the figure it refused to post. It reaches the audit row and the log and
    never a clerk's screen — G28's own distinction.
    """

    def __init__(self, message: str, *, br_ref: str | None = None) -> None:
        super().__init__(message)
        self.br_ref = br_ref


@dataclass(frozen=True)
class BandRow:
    """One ageing band, its balance, the rate applied and what that provides."""

    bucket: str
    balance: Decimal
    rate: Decimal
    provision: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "balance": f"{self.balance:.4f}",
            "rate": f"{self.rate:.6f}",
            "provision": f"{self.provision:.4f}",
        }


@dataclass(frozen=True)
class AllowancePreview:
    """What the close would post, before it posts it.

    `target is None` means UNANSWERABLE — the policy is off, or the ageing could
    not be read — and is never conflated with a target of zero. Only one of
    those two may be posted, and it is not this one.
    """

    period_start: date
    period_end: date
    enabled: bool
    target: Decimal | None
    standing: Decimal
    movement: Decimal | None
    receivable: Decimal | None
    bands: tuple[BandRow, ...] = ()
    posting_key: str = ""
    already_posted_entry_id: str | None = None
    allowance_account_id: str | None = None
    bad_debt_account_id: str | None = None
    problems: tuple[str, ...] = field(default=())

    @property
    def realistically_expect(self) -> Decimal | None:
        """The balance-sheet sentence's second figure: owed − allowance.

        `$15,333.30 − $1,223.65 = $14,109.65`, which is the PO's own wording:
        *"owed $15,333.30, realistically expect $14,109.65"*.
        """
        if self.receivable is None or self.target is None:
            return None
        return self.receivable - self.target

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": [self.period_start.isoformat(), self.period_end.isoformat()],
            "enabled": self.enabled,
            "target": None if self.target is None else f"{self.target:.4f}",
            "standing": f"{self.standing:.4f}",
            "movement": None if self.movement is None else f"{self.movement:.4f}",
            "receivable": None if self.receivable is None else f"{self.receivable:.4f}",
            "realistically_expect": (
                None
                if self.realistically_expect is None
                else f"{self.realistically_expect:.4f}"
            ),
            "bands": [band.as_dict() for band in self.bands],
            "already_in_the_books": self.already_posted_entry_id is not None,
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class AllowanceResult:
    """What the close actually posted."""

    entry_id: str | None
    posting_key: str
    created: bool
    entry_date: date
    target: Decimal
    standing_before: Decimal
    movement: Decimal
    direction: str
    preview: AllowancePreview

    #: The three shapes `direction` takes, named so a caller compares against a
    #: constant rather than a string literal.
    TOPPED_UP = "topped_up"
    RELEASED = "released"
    UNCHANGED = "unchanged"


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def allowance_source_id(*, period_start: date, period_end: date) -> UUID:
    """The period's stable document id. Same inputs ⇒ same uuid, always."""
    return uuid.uuid5(
        ALLOWANCE_NAMESPACE,
        f"{_tenant_id()}|{period_start.isoformat()}|{period_end.isoformat()}",
    )


def allowance_posting_key(*, period_start: date, period_end: date) -> str:
    """`allowance_for_doubtful_accounts|<period uuid>|estimated` — composed."""
    return posting.posting_key(
        source_type=SOURCE_ALLOWANCE,
        source_id=allowance_source_id(period_start=period_start, period_end=period_end),
        event=EVENT_ESTIMATED,
    )


def posted_allowance_entry_id(*, period_start: date, period_end: date) -> str | None:
    """The estimate already standing for this period, or None."""
    key = allowance_posting_key(period_start=period_start, period_end=period_end)
    entry = (
        models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), posting_key=key, status=models.JE_POSTED
        )
        .values_list("id", flat=True)
        .first()
    )
    return str(entry) if entry else None


def _quantize(amount: Decimal) -> Decimal:
    """Hard rule 2 — money is WRITTEN at four decimals, ROUND_HALF_UP."""
    return amount.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _finance_controls() -> dict[str, Any]:
    """The S71 Finance-controls page for THIS tenant, through the seam.

    Tenant scoping is not added here and cannot be lost here: the values come
    from tenancy's own read, which filters on `app.tenant_id` under RLS FORCE
    (hard rule 1). This module issues no query for them and imports no tenancy
    module (BR-TEN-013).
    """
    return dict(tenancy_seam.settings_family(FINANCE_CONTROLS_SLUG))


def policy_is_on() -> bool:
    """Whether THIS tenant books an allowance.

    ⚠ **THE SETTING DECIDES, NOT THE PRESENCE OF AN ACCOUNT.** `1290` can exist
    on a chart because somebody was exploring the GL mapping page; a policy is
    something a utility chose. Reading the account's existence instead would
    switch the write-off posting the first time anybody clicked around, which is
    a money path moving on a UI accident.
    """
    values = _finance_controls()
    return bool(values.get(ENABLED_KEY, False))


def _rate(values: dict[str, Any], bucket: str) -> Decimal:
    """One band's rate, as a FRACTION (0.010000 = 1%).

    Refused rather than defaulted when it is not a number: a rate that silently
    became 0 would under-provide a whole book, and a rate that silently became
    1 would provide for all of it. Both are wrong in a signed month, and neither
    is the kind of wrong anybody notices from a screen.
    """
    raw = values.get(RATE_KEYS[bucket])
    if raw is None:
        raise AllowanceError(
            f"this tenant has no `{RATE_KEYS[bucket]}` on the Finance-controls page, so the "
            f"{bucket} band of the receivable cannot be priced. Nothing is posted — an "
            "allowance computed over a band priced at a guessed rate is a figure somebody "
            "signs a month on (CR-060 T15).",
            br_ref="BR-LED-795",
        )
    try:
        rate = Decimal(str(raw))
    except Exception as bad:  # pragma: no cover — the settings layer coerces
        raise AllowanceError(
            f"`{RATE_KEYS[bucket]}` is {raw!r}, which is not a rate. Money and percentages are "
            "never floats (CLAUDE.md rule 2).",
            br_ref="BR-LED-795",
        ) from bad
    if rate < ZERO or rate > Decimal("1"):
        raise AllowanceError(
            f"`{RATE_KEYS[bucket]}` is {rate}, and a rate is a FRACTION between 0 and 1 — "
            "0.050000 is 5%, not 5. Percentage POINTS are what `discount_versions.value` "
            "stores, and the two spellings are a hundredfold apart.",
            br_ref="BR-LED-795",
        )
    return rate


def standing_allowance(*, as_of: date | None = None) -> Decimal:
    """The credit balance `1290` is carrying today, as a POSITIVE number.

    A contra-asset's balance is credits − debits, so this subtracts the way the
    account behaves rather than the way an asset normally does. It is a READ of
    the books, which is lawful anywhere (hard rule 5 makes the posting service
    the sole WRITER and says nothing about reading).

    `as_of` bounds it by ENTRY DATE, so a close computing October's movement is
    not thrown by a November entry a clerk has already posted.
    """
    account_id = selectors.gl_account_id_for_designation(chart.ALLOWANCE_DOUBTFUL_ACCOUNTS)
    if account_id is None:
        return ZERO
    lines = models.JournalLine.objects.filter(
        tenant_id=_tenant_id(),
        ledger_account_id=account_id,
        journal_entry__status=models.JE_POSTED,
    )
    if as_of is not None:
        lines = lines.filter(journal_entry__entry_date__lte=as_of)
    sums = lines.values("side").annotate(total=Sum("amount"))
    by_side = {row["side"]: row["total"] or ZERO for row in sums}
    return by_side.get(models.SIDE_CREDIT, ZERO) - by_side.get(models.SIDE_DEBIT, ZERO)


def preview_allowance(*, period_start: date, period_end: date) -> AllowancePreview:
    """C5's figure before it is posted — the target, what stands, and the move.

    Answers for a tenant with the policy OFF too, and says so: `enabled=False`,
    `target=None`, and `POLICY_OFF` on `problems`. That is a state a screen
    prints, not an error a caller catches.
    """
    key = allowance_posting_key(period_start=period_start, period_end=period_end)
    already = posted_allowance_entry_id(period_start=period_start, period_end=period_end)
    standing = standing_allowance(as_of=period_end)

    if not policy_is_on():
        return AllowancePreview(
            period_start=period_start,
            period_end=period_end,
            enabled=False,
            target=None,
            standing=standing,
            movement=None,
            receivable=None,
            posting_key=key,
            already_posted_entry_id=already,
            problems=(POLICY_OFF,),
        )

    aged = payments_seam.aged_receivable(as_of=period_end)
    if aged.buckets is None:
        return AllowancePreview(
            period_start=period_start,
            period_end=period_end,
            enabled=True,
            target=None,
            standing=standing,
            movement=None,
            receivable=None,
            posting_key=key,
            already_posted_entry_id=already,
            problems=(AGEING_UNAVAILABLE,) + aged.problems,
        )

    values = _finance_controls()
    bands: list[BandRow] = []
    # Held at FULL precision across the bands and quantized ONCE at the end —
    # BR-LED-025's rule against a second rounding site. On the PO's figures the
    # four products are exact anyway (92.00 · 155.00 · 360.00 · 616.65), which
    # is why $1,223.65 is a clean number and not a rounded one.
    target = ZERO
    for bucket in payments_seam.AGEING_BUCKETS:
        balance = aged.buckets.get(bucket, ZERO)
        rate = _rate(values, bucket)
        provision = balance * rate
        target += provision
        bands.append(
            BandRow(bucket=bucket, balance=balance, rate=rate, provision=_quantize(provision))
        )
    target = _quantize(target)

    return AllowancePreview(
        period_start=period_start,
        period_end=period_end,
        enabled=True,
        target=target,
        standing=standing,
        movement=_quantize(target - standing),
        receivable=aged.total,
        bands=tuple(bands),
        posting_key=key,
        already_posted_entry_id=already,
        allowance_account_id=selectors.gl_account_id_for_designation(
            chart.ALLOWANCE_DOUBTFUL_ACCOUNTS
        ),
        bad_debt_account_id=selectors.gl_account_id_for_designation(chart.WRITE_OFF),
        problems=aged.problems,
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-006")
def estimate_allowance(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    posted_at: datetime,
) -> AllowanceResult:
    """Adjust the standing allowance to this period's computed target.

    ⚠ **`entry_type` IS `standard`, NOT `accrual`, AND THAT IS THE WHOLE RULE.**
    `manual_je.run_accrual_auto_reversals` selects `type=accrual` and posts a
    day-1 mirror for every one it finds (BR-LED-005). An allowance is a BALANCE
    that stands from month to month; a reversing one would be zeroed on the
    first morning of every period, and **every test of a single month would
    still pass**. See the module docstring, trap 2.

    `posted_at` is an INPUT (BR-TEN-043 / gate G6): a double-submitted close must
    stamp one moment, not two, and nothing in a money path reads a clock.
    """
    if not isinstance(posted_at, datetime):
        raise AllowanceError(
            "posted_at must be a datetime supplied by the caller (BR-TEN-043 — nothing in a "
            "money path reads a clock, gate G6)."
        )

    if not policy_is_on():
        raise AllowanceError(
            "this tenant does not book an allowance for doubtful accounts, so there is "
            "nothing to estimate. Write-off is DIRECT for them — `DR bad debt / CR accounts "
            "receivable` at the moment a debt is given up (BR-PAY-020) — which is a lawful "
            "accounting policy and the one this product has always used. Switching the "
            "allowance on is a System-Admin choice on Settings → Finance controls, and it "
            "changes where every future write-off lands.",
            br_ref="BR-LED-795",
        )

    # Hard-won law 4: a tenant provisioned before today has no `1290`, because
    # the account is minted when the policy is switched on and nowhere else.
    # Idempotent — a tenant that has already chosen an account keeps it.
    services.ensure_allowance_account(actor)

    preview = preview_allowance(period_start=period_start, period_end=period_end)

    if preview.already_posted_entry_id is not None:
        # The replay. A RESULT and not an exception, exactly as
        # `posting.PostingResult.created=False` is: a resumed close pressing the
        # button twice is the correct outcome, not an error anybody should catch.
        return AllowanceResult(
            entry_id=preview.already_posted_entry_id,
            posting_key=preview.posting_key,
            created=False,
            entry_date=period_end,
            target=preview.target or ZERO,
            standing_before=preview.standing,
            movement=ZERO,
            direction=AllowanceResult.UNCHANGED,
            preview=preview,
        )

    if preview.target is None:
        raise AllowanceError(
            "the allowance is UNANSWERABLE for this period, so nothing is posted: "
            f"{', '.join(preview.problems)}. It is NOT estimated at zero — a target of zero "
            "would RELEASE the standing allowance to nil and credit bad debt for it, on the "
            "strength of a read that failed, in a month somebody signs.",
            br_ref="BR-LED-795",
        )

    allowance_account_id = preview.allowance_account_id
    if allowance_account_id is None:
        raise AllowanceError(
            "this tenant's chart has no account carrying the `allowance_doubtful_accounts` "
            "designation, so the estimate has nothing to credit. `1290 Allowance for doubtful "
            "accounts` is minted when the policy is switched on and a System Admin may point "
            "the designation at a number of their own on the GL mapping page. Nothing is "
            "posted, and no number is hardcoded — the code reads the DESIGNATION precisely so "
            "a tenant may renumber their chart.",
            br_ref="BR-LED-795",
        )
    bad_debt_account_id = preview.bad_debt_account_id
    if bad_debt_account_id is None:
        raise AllowanceError(
            "this tenant's chart has no account carrying the `write_off` designation, so the "
            "estimate has nothing to charge. `6900 Bad debt` is seeded and finance-signed, so "
            "a tenant reaching this has un-designated it deliberately. Nothing is posted.",
            br_ref="BR-LED-795",
        )

    movement = preview.movement or ZERO
    if movement == ZERO:
        # NOTHING IS POSTED, and that is the answer rather than a refusal. An
        # entry of 0.00 is a journal entry that says nothing and has to be read
        # anyway, and it would take the period's posting key — so a later close,
        # after the receivable moved, could never post the real adjustment.
        return AllowanceResult(
            entry_id=None,
            posting_key=preview.posting_key,
            created=False,
            entry_date=period_end,
            target=preview.target,
            standing_before=preview.standing,
            movement=ZERO,
            direction=AllowanceResult.UNCHANGED,
            preview=preview,
        )

    source_id = allowance_source_id(period_start=period_start, period_end=period_end)
    amount = abs(movement)
    topping_up = movement > ZERO
    direction = AllowanceResult.TOPPED_UP if topping_up else AllowanceResult.RELEASED
    # TOP UP:  DR 6900 bad debt / CR 1290 allowance — expense recognised early.
    # RELEASE: DR 1290 allowance / CR 6900 bad debt — a CREDIT to bad debt, and
    #          it is correct: a month where collectability improves gives
    #          expense back. See the module docstring, trap 2.
    debit_account = bad_debt_account_id if topping_up else allowance_account_id
    credit_account = allowance_account_id if topping_up else bad_debt_account_id

    result = posting.post(
        posting.PostingRequest(
            posting_key=preview.posting_key,
            entry_date=period_end,
            posted_at=posted_at,
            currency=_currency(),
            lines=(
                posting.PostingLine(
                    ledger_account_id=debit_account,
                    side=models.SIDE_DEBIT,
                    amount=amount,
                    source_type=SOURCE_ALLOWANCE,
                    source_id=source_id,
                ),
                posting.PostingLine(
                    ledger_account_id=credit_account,
                    side=models.SIDE_CREDIT,
                    amount=amount,
                    source_type=SOURCE_ALLOWANCE,
                    source_id=source_id,
                ),
            ),
            source_type=SOURCE_ALLOWANCE,
            source_id=source_id,
            memo=(
                f"Allowance for doubtful accounts {period_start.isoformat()} → "
                f"{period_end.isoformat()} (BR-LED-795). Adjusts the standing balance to "
                f"{preview.target}. This entry does NOT reverse — an allowance is a balance, "
                "not an accrual."
            ),
            # ⚠ STANDARD. See this function's own docstring and trap 2.
            entry_type=models.JE_STANDARD,
            audit_context={
                "action": "allowance_for_doubtful_accounts",
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "target": str(preview.target),
                "standing_before": str(preview.standing),
                "movement": str(movement),
                "direction": direction,
                "receivable": str(preview.receivable),
                "bands": [band.as_dict() for band in preview.bands],
            },
        ),
        actor=actor,
    )
    return AllowanceResult(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        entry_date=period_end,
        target=preview.target,
        standing_before=preview.standing,
        movement=movement,
        direction=direction,
        preview=preview,
    )


def _currency() -> str:
    """The tenant's own currency, or the platform default.

    A journal entry carries ONE currency (DEF-081). The allowance is computed
    over a receivable that `payments.outstandings` already sums in one, so this
    reads the tenant's rather than inventing a second source of truth.
    """
    return tenancy_seam.tenant_currency() or "USD"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C5 + task T15 (12-governance/11-change-requests.md §7 · §12) ·
#         12-governance/02-decision-log.md 2026-09-03 (the PO ruling, with the
#         three reasons for deferring recorded) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-795 (NEW) ·
#         04-docs/05-modules/07-payments/02-business-rules.md BR-PAY-020
#         (NARROWED) · CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 and hard-won laws
#         1, 2, 3, 4, 14
# generated: 2026-09-03 by the CR-060 T15 lane
# checklist: A✔ B✔ C✔ D=deferred(no endpoint of its own — the close is where a
#         clerk meets this, and C5 names no route) E=deferred(the SWITCH and the
#         four rates are S71 Finance-controls parameters, which this change adds;
#         the estimate's own screen is REPORTED rather than invented) F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row written
#         with the worked figure)
# gates: PROVED RED BEFORE GREEN — tests/test_cr060_t15_allowance.py quotes each
#         failure verbatim in its own module docstring, including the two traps
#         the PO ruling named before either was built
# exceptions: (1) THE POLICY IS OFF BY DEFAULT and that is this lane's judgment,
#         recorded in the decision log with its reasoning rather than put back to
#         the PO (law 13) — turning it on would move BR-PAY-020's signed write-off
#         posting under utilities who never chose the policy · (2) FOUR RATES
#         price FIVE bands: 61-90 and 90+ share `allowance_rate_61_plus`, because
#         the PO signed four percentages against four amounts and a fifth would
#         move the $1,223.65 they were shown · (3) the ageing comes from
#         `payments.outstandings` and NOT from the books, because a journal line
#         carries no due date (reporting.GAP_AGING_NEEDS_DUE_DATES) · (4) a
#         movement of exactly zero posts NOTHING rather than a 0.00 entry, which
#         would spend the period's posting key
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

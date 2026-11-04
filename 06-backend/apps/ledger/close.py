# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-015 (month close: checklist, period lock, late-event
#           auto-forward, SysAdmin reopen — TC-1..TC-7)
#           Screens: S42 · S36
# Rules:    BR-LED-006 (Finance closes the month per fiscal settings; closed
#           periods lock; late-dated events auto-post forward with audit;
#           SysAdmin reopens; the five-item checklist) · BR-LED-018 (close =
#           WARN + CONFIRM: incomplete items listed, close-anyway with an
#           AUDITED reason — never a silent close, never a hard lockout) ·
#           BR-TEN-038 (closed-period money events auto-post to the earliest
#           OPEN period + audit note) · BR-TEN-022 (period boundaries computed
#           from fiscal settings) · BR-LED-003 (System Admin / Billing Clerk —
#           carried as the READING, see §ROLES) · BR-LED-015 (every finance
#           action audits) · CLAUDE.md rule 1 (tenant scoping) · rule 7 (audit)
# Golden:   LE-9 — July closed Aug 5; an Aug 7 payment dated Jul 30 posts into
#           AUGUST with the audit note, and July's 598.69 = 598.69 is unmoved
# Tests:    06-backend/tests/test_us_led_015_month_close.py
# Impacts:  apps/ledger/manual_je.py (every manual JE dates through
#           `resolve_entry_date`) · apps/ledger/exports.py (BR-LED-017: an
#           export REQUIRES its covered window closed) · apps/ledger/posting.py
#           (unchanged — the posting service still writes the date it is given;
#           the auto-forward happens in the caller, see §WHY NOT IN posting.py)
# ───────────────────────────────────────────────────────
"""Month close — the record of which periods are shut, and what that costs.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides whether a money event
lands in the month it is dated, which is the difference between a closed set of
books and a figure that moves after an accountant has filed it. AI-authored
2026-08-15 under the PO ruling of 2026-08-09; row owed in
12-governance/09-human-review-ledger.md. Not on the G7 glob list yet — REPORTED
for the daily batch rather than self-added (B12 r2, *"who watches the watchers"*).

════════════════════════════════════════════════════════════════════════════
WHAT DID NOT EXIST BEFORE THIS FILE
════════════════════════════════════════════════════════════════════════════
`apps/ledger/posting.py` said it plainly on 2026-08-11:

    "BR-TEN-038's closed-period auto-forward … `tenant_settings.
     lock_closed_periods` is a boolean and there is no record of which periods
     are closed — no fiscal period table exists anywhere in the schema.
     US-LED-015 owns close."

So the ledger could not answer *"is July closed?"* at all, and every entry was
written on the date its caller named. `ledger/0007` adds the record; this module
is the only thing that writes it.

════════════════════════════════════════════════════════════════════════════
WHY THE AUTO-FORWARD IS **NOT** INSIDE posting.py
════════════════════════════════════════════════════════════════════════════
It would have been one line there and it would have been wrong. The posting
service's whole contract is that *"the dates are INPUTS, both of them"* (PO
ruling 2026-08-11 on OQ-107: *"posting and actual dates can differ; ask actual
date to user"*), and a service that silently moved the date it was handed would
break that contract for every caller at once — including the cutover importer,
whose entries are DELIBERATELY dated before every open period.

So the shape is: a caller asks `resolve_entry_date()` what date the books will
accept, gets back the date and a NOTE saying whether it moved, and posts that.
The move is visible at the call site, in the audit payload, and on the S56 list.
`apps/ledger/manual_je.py` is the first caller; billing and payments each own
their own handoffs and are REPORTED rather than edited (this lane may not touch
either module) — until they call it, a late-dated BILL still lands where it was
dated, and that is stated here rather than left to be assumed closed.

════════════════════════════════════════════════════════════════════════════
THE CHECKLIST IS COMPUTED, AND WHAT IT CANNOT COMPUTE IT SAYS SO ABOUT
════════════════════════════════════════════════════════════════════════════
BR-LED-006 names five items — *runs issued · batches reconciled · bank rec
current · accruals posted · remittance recorded* — and the ledger field map is
explicit that they are *"computed from live register states, never checkboxes
typed by hand"*.

Two of the five are the ledger's own and are really computed: **accruals posted**
(an accrual whose day-1 mirror is due and unwritten — US-LED-012) and
**remittance recorded** (a remittance-sourced entry in the window —
US-LED-014). The other three live in billing and payments, and **no module
publishes a read for them**. Each is therefore reported as `unknown` with the
read it wants NAMED, and an `unknown` item counts as INCOMPLETE — the close still
happens (BR-LED-018 forbids a hard lockout) but it demands a reason, which is the
fail-closed choice: a checklist that showed a green tick because it could not see
the register would be worse than no checklist at all (hard-won law 1).

════════════════════════════════════════════════════════════════════════════
ROLES — RULED 2026-09-24, AND THE GATE DID NOT MOVE
════════════════════════════════════════════════════════════════════════════
⚠ **THIS SECTION SAID THE CLOSE GATE WAS "A READING RATHER THAN A RULING" AND
THAT "THE PO WAS NOT ASKED" UNTIL 2026-09-24. THEY HAVE NOW BEEN ASKED AND THEY
RULED.** PO ruling 2026-09-24, two parts, verbatim:

    CLOSE   — *"system admin and clark"*
    REOPEN  — *"yes correct - Reopening a month  System Admin only — signed as
               BR-LED-006, in the code, with a reason required and audited"*

**So `close_period` is `system_admin` + `billing_clerk` by ruling, and
`reopen_period` is `system_admin` only, CONFIRMED UNCHANGED.** The code was
already gated at exactly those roles, so **no behaviour moved** — what changed
is that the file stopped describing its own gate as a guess. BR-LED-006 is
AMENDED, not superseded: its checklist, its lock, its auto-post-forward and its
*SysAdmin reopens* clause all stand; only its naming of *"Finance/Owner"* — two
roles this product has never had (BR-IDN-008) — is replaced by the two it does.

**WHERE THE TWO ROLES CAME FROM, AND WHY THEY WERE FLAGGED FOR SIX WEEKS.** They
were carried from OQ-175 (PO 2026-08-12, verbatim *"System Admin, Billing
Clerk"*), **where what was put to the PO was REVERSING a posted entry** and not
closing a month. EP-LED-05 §8 flagged the carry rather than claiming a signature
covered it, and `ROLE_GATE_IS_A_READING` rode on every result saying so. **That
constant is RETIRED** — see the note above where it was defined.

⚠ **§8 FLAGGED TWO CARRIES AND THIS RULING COVERS ONE.** The PO was shown the
CLOSE. **The REMITTANCE record (`finance_api.record_remittance`, BR-LED-002 /
US-LED-014) was not**, nor was the EXPORT handover (`exports`, BR-LED-017), nor
posting a period-end accrual (`ACCRUAL_ROLE_GATE_IS_A_READING`). All three stay
flagged and return to the agenda. A signature covers only what was shown, and
clearing a neighbour's flag because its neighbour was ratified is the whole
failure this marker existed to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, When

from apps.ledger import models, selectors
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: BR-LED-006's five checklist items, in the rule's own order.
ITEM_RUNS_ISSUED = "runs_issued"
ITEM_BATCHES_RECONCILED = "batches_reconciled"
ITEM_BANK_REC_CURRENT = "bank_rec_current"
ITEM_ACCRUALS_POSTED = "accruals_posted"
#: ⚠ **THE SIXTH ITEM, ADDED 2026-09-02 — BR-LED-006 AMENDED by CR-060 C2 /
#: task T7.** *"the close checklist gains a step that can actually be
#: completed"*. It asks whether THIS period's unbilled revenue has been
#: recognised, which no item asked before — see `_unbilled_accrual_item` for why
#: it is a sixth rather than a widening of `accruals_posted`.
ITEM_UNBILLED_ACCRUAL = "unbilled_accrual"
#: ⚠ **THE SEVENTH ITEM (CR-060 C17 / task T7b, 2026-09-02).** The mirror of the
#: sixth, and C17 asks that the two be read as ONE idea — PERIOD MATCHING — with
#: a half on each side of the books: revenue the period earned and has not
#: billed, cost the period incurred and has not paid. They are separate ITEMS
#: because a closer can complete one and not the other, and a single tick that
#: could mean either is the shape hard-won law 1 is about.
ITEM_UNPAID_COST_ACCRUAL = "unpaid_cost_accrual"
ITEM_REMITTANCE_RECORDED = "remittance_recorded"
CHECKLIST_ITEMS = (
    ITEM_RUNS_ISSUED,
    ITEM_BATCHES_RECONCILED,
    ITEM_BANK_REC_CURRENT,
    ITEM_ACCRUALS_POSTED,
    ITEM_UNBILLED_ACCRUAL,
    ITEM_UNPAID_COST_ACCRUAL,
    ITEM_REMITTANCE_RECORDED,
)

#: CR-060 C2 / task T7 — the unbilled figure is compared against it and never
#: against a bare `0`, so the comparison stays a money comparison.
ZERO = Decimal("0")

#: CR-060 C2 / task T7 — the unbilled figure is compared against it and never
#: against a bare `0`, so the comparison stays a money comparison.
ZERO = Decimal("0")

#: The three states one item can be in. `unknown` is not a synonym for `pending`
#: — it means the register that would answer is not readable from here, and it
#: counts as incomplete so a close over it needs a reason.
STATE_COMPLETE = "complete"
STATE_INCOMPLETE = "incomplete"
STATE_UNKNOWN = "unknown"

#: The `source_type` a remittance entry carries — the same string
#: `apps/ledger/journal.py` writes, named once so the write and this read cannot
#: drift apart.
SOURCE_REMITTANCE = "remittance"

AUDIT_CLOSED = "period.closed"
AUDIT_REOPENED = "period.reopened"
AUDIT_AUTO_FORWARDED = "journal.auto_forwarded"

#: The reads this module WANTS, named by exact callable so the day one appears,
#: one line changes here and the item starts computing.
#:
#: ⚠ **THE TWO PAYMENTS READS NOW EXIST (CR-059 CS-13, 2026-09-01)** and are
#: declared `-> int | None`, not `-> int`. The widening is the contract and not
#: a detail: `None` means *the register cannot answer for this window*, which
#: `_seam_item` renders as `unknown`, and an integer — `0` included — means it
#: was read. Before this, both items reported `unknown` on every close because
#: nothing answered them, so a utility closed EVERY month over a typed reason.
#: ⚠ **`apps.billing.selectors.unissued_run_count` IS PUBLISHED NOW TOO**
#: (`b06eba2bb`, 2026-09-23), so `runs_issued` computes rather than reporting
#: `unknown`, and NO item on this checklist is waiting on a neighbour any more.
#: Its `-> int` is left exactly as billing was asked for it — it is the one read
#: here that cannot say *the register cannot answer*.
#: ⚠ **THIS COMMENT SAID "is still unpublished" FOR TWO DAYS AFTER IT WAS**
#: (`DEF-LED-6616`). The publication landed, `test_cr059_tc6b` went red naming
#: it — hard-won law 2's hold-expiry test working exactly as designed — and
#: three lanes ran the suite past the failure. Landing a read and releasing the
#: things that were holding for it are two acts, and only the first feels like
#: the work.
WANTED_READS: dict[str, tuple[str, ...]] = {
    ITEM_RUNS_ISSUED: ("apps.billing.selectors.unissued_run_count(start, end) -> int",),
    ITEM_BATCHES_RECONCILED: (
        "apps.payments.selectors.unreconciled_batch_count(start, end) -> int | None",
    ),
    ITEM_BANK_REC_CURRENT: (
        "apps.payments.selectors.unmatched_bank_line_count(start, end) -> int | None",
    ),
}


class CloseError(RuntimeError):
    """A close, reopen or dating request the books refuse, with the reason.

    Same shape and same argument as `apps.ledger.posting.PostingError`: this
    module has no HTTP surface and an API layer decides what a browser sees.
    """


#: ⚠ **`ROLE_GATE_IS_A_READING` LIVED HERE AND IS RETIRED — THE READING BECAME A
#: RULING ON 2026-09-24 AND THERE IS NOTHING LEFT TO FLAG ON A CLOSE.** Its code
#: was `close_role_gate_is_a_reading_not_a_ruling`; it rode on `close_checklist`
#: and `close_period`, and `CloseExportPage.tsx` RENDERED it — with no catalogue
#: key, so a clerk read the `finance.gap.unknown` fallback, *"The books will not
#: state this. The reason has no wording yet."*, on the month-close panel.
#: DELETED rather than reworded, for the reason CLAUDE.md hard rule 4 records
#: about `amendment_history_is_not_a_permanent_record`: a key named
#: *is_a_reading_not_a_ruling* for a thing that IS a ruling is this repo's
#: most-filed rot, and B14 rule 33 puts rationale at ZERO words on screen.
#: **The gate itself did not move** — `close_period` is still `SYSTEM_ADMIN` +
#: `BILLING_CLERK`, `reopen_period` is still `SYSTEM_ADMIN`; see §ROLES.
#:
#: The three period-end accrual modules USED TO ALIAS the retired constant, and
#: their carry is NOT ratified: nobody put *who may post a depreciation entry*
#: to the PO. They alias the constant below instead, so closing the flag on the
#: close did not silently close three flags standing beside it — DEF-CUS-3653's
#: shape, an absence no check in this repo can see.
ACCRUAL_ROLE_GATE_IS_A_READING = {
    "code": "accrual_posting_role_gate_is_a_reading_not_a_ruling",
    "br_ref": "BR-LED-003 (OQ-175, CLOSED for REVERSAL only) · BR-LED-006 (close ruled 2026-09-24)",
    "detail": "Who may POST A PERIOD-END ACCRUAL — depreciation, unbilled revenue, unpaid "
    "supplier cost — has never been put to the PO. Two neighbouring acts have: reversing a "
    "posted entry (2026-08-12, OQ-175, verbatim *\"System Admin, Billing Clerk\"*) and closing "
    "a month (2026-09-24, verbatim *\"system admin and clark\"*). Neither was about writing an "
    "accrual, so the same two roles are carried here — an executive reads the books, a clerk "
    "writes them — and MARKED, because a signature covers only what was shown. EP-LED-05 §8 "
    "holds the flag.",
    "wanted_reads": (),
}


@dataclass(frozen=True)
class ChecklistItem:
    """One computed row of the close checklist.

    ⚠ **`outstanding` IS THE COUNT AS DATA, AND IT EXISTS BECAUSE `detail` MAY
    NOT REACH A SCREEN (CR-059 CS-13, task 10).** BR-SHL-020 r2 (PO ruling
    2026-08-19, *"server detail text should not reach customer screens"*) keeps
    `detail` for the trail and the log; S42 renders the catalogue. CS-13 asks
    for the two payments items to *"start saying how many batches or lines are
    outstanding"*, and a screen cannot say a number that only exists inside an
    English sentence without parsing prose. So the figure travels as an integer
    beside the sentence.

    `None` means **nobody counted** — an item whose register was not asked, or
    was asked and could not answer. It is NOT zero, and DEF-127 is what happens
    when a product spells those two the same way.
    """

    code: str
    state: str
    detail: str
    wanted_reads: tuple[str, ...] = ()
    #: How many of this item's things are still outstanding, or None when the
    #: item is not a counted one (accruals, remittance) or nobody could count.
    outstanding: int | None = None
    #: ⚠ **WHAT THIS ITEM IS WORTH — `P5.10` OF THE FINANCE BLUEPRINT (p018,
    #: 2026-09-24).** Its words: *"the checklist builder already computes each
    #: figure to decide done vs not done, and throws it away. Carry it to the
    #: row."* That was exactly true — `_unbilled_accrual_item` and
    #: `_unpaid_cost_accrual_item` each take `preview.total`, spend it deciding
    #: `complete` against `incomplete`, write it into an English sentence no
    #: screen may render (`BR-SHL-020` r2, *"server detail text should not reach
    #: customer screens"*) and then drop the number. So *Accruals posted ○*
    #: could not tell a closer whether it stood for five minutes of work or a
    #: day of it, which is the blueprint's own complaint.
    #:
    #: **A money figure, stored to four decimals and DISPLAYED to two** (hard
    #: rule 2). It is the AMOUNT AT STAKE and not a balance: on an incomplete
    #: item it is what is still unrecognised or unremitted, and on a COMPLETE
    #: one it is `None` — a done row has nothing outstanding, and `$0.00`
    #: beside a tick reads as a measurement somebody took rather than as
    #: nothing to measure.
    #:
    #: `None` and `0` are different facts here exactly as they are on
    #: `outstanding` (DEF-127): `None` means **this item carries no money
    #: figure at all** — it is a counted item, or nobody could measure it — and
    #: it is never rendered as a zero.
    amount: Decimal | None = None

    @property
    def complete(self) -> bool:
        return self.state == STATE_COMPLETE


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _published(module: str, attribute: str) -> Any:
    """Another module's published read, resolved AT CALL TIME by name.

    The idiom `apps/ledger/tenancy_seam.py` uses and for its reason: no import
    binds this module to another module's internals (B1 / BR-TEN-013), and a
    read that does not exist yet comes back `None` so the caller can report the
    gap instead of inventing an answer.
    """
    try:
        target = import_module(f"apps.{module}.{attribute.rsplit('.', 1)[0]}")
    except ImportError:
        return None
    fn = getattr(target, attribute.rsplit(".", 1)[1], None)
    return fn if callable(fn) else None


# ═══════════════════════════════════════════════════════════════════════════
# Period boundaries (BR-TEN-022 — computed by tenancy, never stored here)
# ═══════════════════════════════════════════════════════════════════════════
def period_window(reference_date: date) -> tuple[date, date]:
    """The fiscal period CONTAINING `reference_date`, per the tenant's settings.

    Delegated to `apps.tenancy.selectors.current_period`, which BR-TEN-022 makes
    the one implementation: fiscal year start, monthly or quarterly cadence, the
    close-by day. Re-deriving it here would be a second calendar, and a tenant on
    a July fiscal year would eventually find the two disagreeing about which
    month July is.

    REFUSES rather than assuming calendar months when tenancy publishes nothing
    or the tenant has no fiscal settings: *"this tenant has no fiscal year"* and
    *"the ledger cannot see tenancy"* have the same shape, and guessing turns a
    wiring failure into a period boundary nobody chose.
    """
    if not isinstance(reference_date, date) or isinstance(reference_date, datetime):
        raise CloseError(
            "a period is resolved from a DATE (BR-TEN-043 — the caller names the business "
            f"event's day; nothing here reads a clock). Got {reference_date!r}."
        )
    current_period = _published("tenancy", "selectors.current_period")
    if current_period is None:
        raise CloseError(
            "apps.tenancy.selectors.current_period is not published, so the ledger cannot tell "
            "which fiscal period a date belongs to. BR-TEN-022 makes the fiscal calendar "
            "tenancy's, computed from the tenant's own settings; nothing is assumed here."
        )
    window = current_period(reference_date)
    if not window or not window.get("start") or not window.get("end"):
        raise CloseError(
            "this tenant has no fiscal settings, so no period boundary exists to close "
            "(BR-TEN-022 / US-TEN-006: fiscal year start + close cadence are Settings → "
            "Regional). A month cannot be closed before the calendar it belongs to is chosen."
        )
    return (date.fromisoformat(window["start"]), date.fromisoformat(window["end"]))


def next_period_window(window: tuple[date, date]) -> tuple[date, date]:
    """The period that starts the day after `window` ends."""
    from datetime import timedelta

    return period_window(window[1] + timedelta(days=1))


# ═══════════════════════════════════════════════════════════════════════════
# Close state
# ═══════════════════════════════════════════════════════════════════════════
def _close_row(period_start: date, period_end: date):
    return models.FiscalPeriodClose.objects.filter(
        tenant_id=_tenant_id(), period_start=period_start, period_end=period_end
    ).first()


def is_period_closed(period_start: date, period_end: date) -> bool:
    """Absence is OPEN — a tenant that has never closed anything holds no rows."""
    row = _close_row(period_start, period_end)
    return row is not None and row.status == models.PERIOD_CLOSED


def is_closed_on(day: date) -> bool:
    """Is the period CONTAINING `day` closed? The posting-path question."""
    return is_period_closed(*period_window(day))


def window_is_closed(start: date, end: date, *, limit: int = 120) -> bool:
    """Is EVERY fiscal period this window touches closed? The export question.

    `is_period_closed` answers about one period by its exact boundaries, which is
    what the close screen asks. BR-LED-017 asks something wider: *"export
    requires the COVERED period CLOSED"*, and a covered window is not always a
    whole period — BR-LED-017's own weekly granularity slices one, and T5-07
    step 3 requires a week inside an already-exported July to be recognised as
    covered rather than treated as an unclosed period of its own.

    So this walks the calendar across the window and demands every period be
    shut. A window spanning a closed July and an open August is NOT closed, which
    is the answer that matters: exporting it would hand the ERP August figures
    that can still move.
    """
    window = period_window(start)
    for _ in range(limit):
        if not is_period_closed(*window):
            return False
        if window[1] >= end:
            return True
        window = next_period_window(window)
    raise CloseError(
        f"the window {start} … {end} spans more than {limit} fiscal periods, which is not a "
        "close or an export anybody meant to run."
    )


def resolve_entry_date(requested: date, *, limit: int = 120) -> tuple[date, dict[str, Any] | None]:
    """BR-TEN-038 — the date the books will actually accept, and why it moved.

    LE-9 verbatim: *"July closed Aug 5. Aug 7 a payment arrives dated Jul 30 →
    posts into August automatically with an audit note ('period closed;
    auto-forwarded'), books stay locked, nothing silently lands in a closed
    month."*

    Returns `(entry_date, note)`. `note` is `None` when the requested date's
    period is open — the overwhelmingly common case, and the caller posts exactly
    what a human typed. When it is closed, the date becomes **the START of the
    earliest open period at or after it**, and the note carries both dates and
    the rule so it can ride into `audit_log` and onto the screen.

    **WHY THE PERIOD'S START AND NOT THE ARRIVAL DATE.** LE-9 says *"posts into
    August"* and fixes no day. The arrival date is not available here — nothing
    in this module reads a clock (BR-TEN-043, gate G6) — and asking the caller
    for a second date would let two callers forward the same event to two
    different days. The period start is the one date every caller derives
    identically, and it keeps the forwarded entry at the earliest possible point
    of the month it lands in, which is where a reader looking for *"what came in
    late"* expects it.

    **THE TOGGLE IS NOT CONSULTED, AND THAT IS FLAGGED.**
    `tenant_settings.lock_closed_periods` exists and OQ-033's closure is phrased
    *"With 'Lock periods once closed' ON …"*. What a CLOSED period should do
    while the toggle is OFF was never ruled. This takes the fail-closed reading —
    a closed period never receives new money — because BR-LED-006 states *"closed
    periods lock"* without a condition, because T5-09 and J19 assert the
    auto-forward without mentioning the toggle, and because the alternative lets
    figures move after they have been exported to an ERP (BR-LED-017's whole
    point). REPORTED, not silently taken.

    **THE FAST PATH IS ALSO THE HONEST ONE.** A tenant with no closed period at
    all cannot have dated anything into one, so this returns immediately without
    consulting the fiscal calendar. That matters beyond speed: a tenant who has
    never opened Settings → Regional has no fiscal year, `period_window` refuses
    by design, and without this check a manual journal entry would be unpostable
    for a rule that cannot possibly apply to them.
    """
    if not models.FiscalPeriodClose.objects.filter(
        tenant_id=_tenant_id(), status=models.PERIOD_CLOSED
    ).exists():
        return requested, None
    window = period_window(requested)
    if not is_period_closed(*window):
        return requested, None
    original_window = window
    for _ in range(limit):
        window = next_period_window(window)
        if not is_period_closed(*window):
            return window[0], {
                "code": "period_closed_auto_forwarded",
                "br_ref": "BR-TEN-038 · BR-LED-006",
                "requested_date": requested.isoformat(),
                "requested_period": [d.isoformat() for d in original_window],
                "posted_period": [d.isoformat() for d in window],
                "detail": "period closed; auto-forwarded",
            }
    raise CloseError(
        f"every fiscal period from {original_window[0]} onward is closed for the next {limit} "
        "periods, so a late-dated event has nowhere open to land. BR-TEN-038 forwards to the "
        "EARLIEST OPEN period and there is none — reopen one (System Admin) or close fewer "
        "future months. Nothing is posted into a closed period to make this go away."
    )


# ═══════════════════════════════════════════════════════════════════════════
# The checklist (BR-LED-006, computed live)
# ═══════════════════════════════════════════════════════════════════════════
def _accruals_item(period_start: date, period_end: date) -> ChecklistItem:
    """*"accruals posted"* — every accrual whose day-1 mirror is due has one.

    An accrual dated inside this period reverses on day 1 of the NEXT period
    (BR-LED-005), so at the moment July closes, July's accruals are due to
    reverse on Aug 1 and none of them has yet. What this item asks is the
    question a closer actually cares about: **is there an accrual from an EARLIER
    period whose reversal never fired?** — a mirror that is overdue and missing
    is a double-count waiting in the next month's revenue.
    """
    tenant_id = _tenant_id()
    unreversed = models.JournalEntry.objects.filter(
        tenant_id=tenant_id,
        type=models.JE_ACCRUAL,
        status=models.JE_POSTED,
        auto_reverse_entry__isnull=True,
        entry_date__lt=period_start,
    )
    overdue = list(unreversed.values_list("id", flat=True)[:20])
    if overdue:
        # ⚠ **`P5.10`'s FIGURE, AND IT IS THE FULL SET RATHER THAN THE SLICE.**
        # `overdue` is capped at 20 because `detail` only ever needed enough to
        # say *"n entries"*; the AMOUNT is what a closer is deciding on, so it
        # is summed over every unreversed accrual and not over the first twenty.
        # Summing the slice would understate the double-count at exactly the
        # moment it is worst, which is the sort of quiet wrong figure hard rule
        # 2 exists to keep off a money screen.
        #
        # ONE SIDE ONLY. An accrual is balanced, so Σ over both sides is twice
        # the exposure; the DEBIT side is the amount at stake, which is the same
        # convention `row_total` and the tie-outs use.
        exposure = models.JournalLine.objects.filter(
            tenant_id=tenant_id,
            journal_entry__in=unreversed,
            side=models.SIDE_DEBIT,
        ).aggregate(total=Sum("amount"))["total"]
        return ChecklistItem(
            code=ITEM_ACCRUALS_POSTED,
            state=STATE_INCOMPLETE,
            amount=exposure,
            outstanding=unreversed.count(),
            detail=f"{len(overdue)} accrual entries dated before {period_start.isoformat()} have "
            "no auto-reversal (BR-LED-005 posts the mirror on day 1 of the next period). Until "
            "each mirror posts, the accrued amount is counted twice — once in the accrual and "
            "again in the real bill. Run the accrual auto-reversal "
            "(apps.ledger.manual_je.run_accrual_auto_reversals).",
        )
    return ChecklistItem(
        code=ITEM_ACCRUALS_POSTED,
        state=STATE_COMPLETE,
        detail="every accrual whose day-1 mirror was due has one (BR-LED-005).",
    )


def _remittance_item(period_start: date, period_end: date) -> ChecklistItem:
    """*"remittance recorded"* — a remittance entry exists in this window.

    Read out of the BOOKS (a remittance-sourced entry), not out of a register:
    `tax_remittances` (B2 r13 #3) is not in the schema, and BR-REP-002 makes the
    books the number that has to be right. `apps/ledger/journal.py` already reads
    the REMITTED column the same way, so the two agree by construction.

    A tenant with NO tax liability at all has nothing to remit, and this reports
    `complete` for them rather than a permanent red tick — the question is *"is a
    remittance owed and unrecorded"*, not *"did somebody pay tax"*.
    """
    tenant_id = _tenant_id()
    recorded = models.JournalEntry.objects.filter(
        tenant_id=tenant_id,
        status=models.JE_POSTED,
        source_type=SOURCE_REMITTANCE,
        entry_date__gte=period_start,
        entry_date__lte=period_end,
    ).exists()
    if recorded:
        return ChecklistItem(
            code=ITEM_REMITTANCE_RECORDED,
            state=STATE_COMPLETE,
            detail="a remittance entry is posted in this window (BR-LED-002).",
        )
    lines = models.JournalLine.objects.filter(
        tenant_id=tenant_id,
        journal_entry__status=models.JE_POSTED,
        journal_entry__entry_date__lte=period_end,
    ).filter(
        # CR-196-BRC10 5b — the series by code OR by minted slot, so a renamed
        # tax account still owes a remittance at month end.
        selectors.tax_payable_q("ledger_account__"),
    )
    if not lines.exists():
        return ChecklistItem(
            code=ITEM_REMITTANCE_RECORDED,
            state=STATE_COMPLETE,
            detail="this tenant holds no 2200-series tax liability, so no remittance is owed.",
        )
    # ⚠ **`P5.10`'s FIGURE: THE STANDING LIABILITY, WHICH IS A NET AND NOT A
    # SUM.** `2200` is a LIABILITY account, so billing tax CREDITS it and
    # remitting DEBITS it. Adding both sides up would report the tax this
    # utility has ever billed — a number that only grows and that nobody owes —
    # where the closer needs what is still HELD. The direction is read off the
    # line's `side` column, which is the one place this product expresses it
    # (`apps/ledger/models.py`: *"Direction is a column, so there is exactly one
    # way to express a credit"*), never off a sign.
    balance = lines.aggregate(
        total=Sum(
            Case(
                When(side=models.SIDE_CREDIT, then=F("amount")),
                default=-F("amount"),
                output_field=DecimalField(max_digits=18, decimal_places=6),
            )
        )
    )["total"]
    return ChecklistItem(
        code=ITEM_REMITTANCE_RECORDED,
        state=STATE_INCOMPLETE,
        amount=balance,
        detail="tax liability has been billed and no remittance entry is posted in this window "
        "(BR-LED-002 / BR-LED-013). S41 shows both bases per authority; recording the payment "
        "drains the authority's liability.",
    )


def _seam_item(code: str, period_start: date, period_end: date) -> ChecklistItem:
    """One of the three items whose register belongs to another module.

    ⚠ **THERE ARE THREE ANSWERS HERE, NOT TWO, AND KEEPING THEM APART IS THE
    ONLY REASON THIS FUNCTION IS MORE THAN ONE LINE.**

      * an INTEGER — the neighbour read its register. `0` means nothing is
        outstanding and the item ticks; n means n is left to do, and the number
        is put in the detail because *"3 outstanding"* is actionable on S42
        where *"not ready"* is a dead end.
      * `None` — the neighbour was asked and answered that it CANNOT count this
        window. Reported `unknown`.
      * a RAISED ERROR — the read exists but could not run. Also `unknown`, with
        the reason carried into the detail.

    `unknown` counts as incomplete either way, which is the fail-closed answer:
    a green tick nobody computed is the exact shape of hard-won law 1.

    ⚠ **WHY THE `try` IS NOT DEFENSIVE CLUTTER (CR-059 CS-13).** While no
    neighbour published a read, `fn` was always `None` and the call below was
    unreachable, so an unguarded `int(fn(...))` cost nothing. The moment
    payments published two real reads it became the whole close screen's
    failure mode: any exception inside a neighbour's register read — and a
    tenant-scoped read REFUSES by design (BR-TEN-003) — would propagate out of
    `close_checklist` and out of `close_period`, and a finance user would be
    unable to close the month at all. **BR-LED-018 forbids a hard lockout in
    the same breath as it forbids a silent close**, so a read that cannot run
    degrades to `unknown` + a reason, never to a 500 and never to a zero.
    The catch is deliberately broad: every way a neighbour's read can fail ends
    in the same honest sentence, and narrowing it would let the next unforeseen
    one through as a crash.
    """
    wanted = WANTED_READS[code]
    module, callable_name = ("billing", "selectors.unissued_run_count")
    if code == ITEM_BATCHES_RECONCILED:
        module, callable_name = ("payments", "selectors.unreconciled_batch_count")
    elif code == ITEM_BANK_REC_CURRENT:
        module, callable_name = ("payments", "selectors.unmatched_bank_line_count")
    fn = _published(module, callable_name)
    if fn is None:
        return ChecklistItem(
            code=code,
            state=STATE_UNKNOWN,
            detail=f"{wanted[0]} is not published, so this item cannot be computed from its "
            "register. It is reported UNKNOWN rather than ticked — the ledger may not read "
            f"apps.{module}'s ORM (B1 / BR-TEN-013), and BR-LED-006 requires these items "
            "*computed from live register states, never checkboxes typed by hand*. An unknown "
            "item counts as INCOMPLETE, so the close still happens (BR-LED-018 forbids a hard "
            "lockout) and demands a reason.",
            wanted_reads=wanted,
        )
    try:
        answer = fn(period_start, period_end)
        outstanding = None if answer is None else int(answer)
    except Exception as exc:
        return ChecklistItem(
            code=code,
            state=STATE_UNKNOWN,
            detail=f"{wanted[0]} is published but could not run, so this item is not computed: "
            f"{exc} It is reported UNKNOWN rather than ticked or counted as zero — a register "
            "that failed to answer and a register with nothing outstanding are different facts "
            "(BR-LED-041, and DEF-127 is a zero that meant 'I don't know'). An unknown item "
            "counts as INCOMPLETE, so the close still happens (BR-LED-018 forbids a hard "
            "lockout) and demands a reason.",
            wanted_reads=wanted,
        )
    if outstanding is None:
        return ChecklistItem(
            code=code,
            state=STATE_UNKNOWN,
            detail=f"{wanted[0]} answered that it cannot count this window — the register "
            "behind it holds nothing covering these dates, which is NOT the same statement as "
            "nothing being outstanding (BR-LED-041 / DEF-127). Reported UNKNOWN rather than "
            "ticked; an unknown item counts as INCOMPLETE, so the close still happens "
            "(BR-LED-018 forbids a hard lockout) and demands a reason.",
            wanted_reads=wanted,
        )
    if outstanding:
        return ChecklistItem(
            code=code,
            state=STATE_INCOMPLETE,
            detail=f"{outstanding} outstanding in this window.",
            wanted_reads=(),
            outstanding=outstanding,
        )
    # ZERO IS SERVED, not left null: the register WAS read and answered none, and
    # S42 says "nothing outstanding" over a counted zero where it says "not
    # counted" over a null (DEF-127, one screen along).
    return ChecklistItem(
        code=code, state=STATE_COMPLETE, detail="nothing outstanding.", outstanding=0
    )


def _unbilled_accrual_item(period_start: date, period_end: date) -> ChecklistItem:
    """*"unbilled revenue accrued"* — BR-LED-006 AMENDED 2026-09-02 (CR-060 C2).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE SIXTH ITEM, AND WHY IT IS A SIXTH RATHER THAN A WIDER FOURTH    ║
    ╚══════════════════════════════════════════════════════════════════════╝
    CR-060 C2: *"`1210 Unbilled AR` is seeded in every chart and nothing has
    ever posted to it… It is the first thing any reviewer finds."* The change
    request asks that *"the close checklist gains a step that can actually be
    completed"*.

    It is a SEPARATE item because `_accruals_item` above asks a different
    question: *is an OLDER accrual's mirror overdue?* — a double-count SAFETY
    check. This one asks *has THIS period's unbilled revenue been recognised?* —
    a COMPLETENESS check. Merging them would give one green tick that could mean
    either, and a check whose output cannot distinguish two states is the shape
    CLAUDE.md's hard-won law 1 is about. Keeping them apart also leaves
    US-LED-015 TC-1's two ratified assertions about `accruals_posted` saying
    exactly what they were signed saying.

    ⚠ **C2's PROOF SENTENCE IS AGAINST A FALSE PREMISE AND IS CORRECTED HERE
    RATHER THAN COPIED.** It reads *"the checklist item flips from `unknown` to
    done"*. `accruals_posted` has never answered `unknown` — it is one of the
    two items this module really computes (see the header). What was true is the
    thing underneath: **no checklist item asked whether the period's unbilled
    revenue had been accrued at all**, so `1210` could sit at zero forever with
    a green checklist above it. That is what this item asks.

    **IT IS COMPLETE WHEN THERE IS NOTHING TO ACCRUE**, not only when something
    was posted. A tenant whose every committed read is already inside a billed
    service period has no unbilled revenue, and a permanently red tick for a
    month that is genuinely finished is how a checklist stops being read.

    **THE MEASUREMENT RUNS ONLY WHEN NO ACCRUAL STANDS.** The cheap question —
    *is there an entry keyed for this period?* — is asked first, on an indexed
    posting key; the expensive one is asked only in the case a closer is about
    to act on. And it is wrapped: a checklist that raised because a seam was
    dark would take the whole close screen down over a tick.
    """
    # Imported HERE and not at module scope: `unbilled_accrual` imports this
    # module for `resolve_entry_date` and `ACCRUAL_ROLE_GATE_IS_A_READING`, so a
    # top-level import either way would be circular.
    from apps.ledger import unbilled_accrual

    try:
        posted = unbilled_accrual.posted_accrual_entry_id(
            period_start=period_start, period_end=period_end
        )
    except Exception as problem:  # pragma: no cover — defensive, see the docstring
        return ChecklistItem(
            code=ITEM_UNBILLED_ACCRUAL,
            state=STATE_UNKNOWN,
            detail=f"the unbilled-revenue accrual could not be read ({problem}).",
            wanted_reads=("apps.ledger.unbilled_accrual.posted_accrual_entry_id",),
        )
    if posted is not None:
        return ChecklistItem(
            code=ITEM_UNBILLED_ACCRUAL,
            state=STATE_COMPLETE,
            detail=(
                "this period's unbilled revenue is accrued (BR-LED-791) and reverses on day 1 "
                "of the next period (BR-LED-005)."
            ),
        )
    try:
        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=period_start, period_end=period_end
        )
    except Exception as problem:  # pragma: no cover — defensive, see the docstring
        return ChecklistItem(
            code=ITEM_UNBILLED_ACCRUAL,
            state=STATE_UNKNOWN,
            detail=f"the unbilled figure could not be measured ({problem}).",
            wanted_reads=("apps.ledger.unbilled_accrual.preview_unbilled_revenue",),
        )
    if preview.total is None:
        # A read the measurement depends on is not published. `unknown`, never
        # a green tick — the distinction the third state exists for.
        return ChecklistItem(
            code=ITEM_UNBILLED_ACCRUAL,
            state=STATE_UNKNOWN,
            detail=(
                "the unbilled figure cannot be measured on this deployment "
                f"({', '.join(preview.problems) or 'a read it depends on is not published'}), "
                "so whether anything is unrecognised is unknown rather than no."
            ),
            wanted_reads=(
                "apps.metering.selectors.unbilled_reads(as_of, service_codes)",
                "apps.billing.selectors.last_priced_usage_by_account_service"
                "(account_ids, service_codes)",
            ),
        )
    if preview.total <= ZERO:
        return ChecklistItem(
            code=ITEM_UNBILLED_ACCRUAL,
            state=STATE_COMPLETE,
            detail=(
                "nothing measured is unbilled in this period — every committed read is inside "
                "a billed service period, or prices to less than a cent. There is no accrual "
                "to post."
            ),
        )
    return ChecklistItem(
        code=ITEM_UNBILLED_ACCRUAL,
        state=STATE_INCOMPLETE,
        # `P5.10` — the figure that DECIDED this branch, carried to the row
        # instead of left inside the sentence below, which no screen may render.
        amount=preview.total,
        outstanding=preview.account_rows_total,
        detail=(
            f"{preview.total} of revenue has been read and not yet billed across "
            f"{preview.account_rows_total} account/service rows, and none of it is in the "
            "books. Post the unbilled-revenue accrual (BR-LED-791) — it debits Unbilled AR, "
            "credits the service revenue accounts, and reverses itself on day 1 of the next "
            "period, so it creates no standing balance."
        ),
    )


def _unpaid_cost_accrual_item(period_start: date, period_end: date) -> ChecklistItem:
    """*"unpaid supplier costs accrued"* — BR-LED-006 AMENDED 2026-09-02 (C17).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE SEVENTH ITEM, AND IT IS THE SIXTH POINTED THE OTHER WAY         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    CR-060 C17: *"Without it, revenue is recognised when BILLED and cost when
    PAID, so a commodity sold in one month can have its cost land in the next."*
    And on the rule: *"AMEND, the same rule as C2. Worth writing the two as ONE
    rule about period matching rather than two unrelated steps — they are the
    same idea applied to each side."* BR-LED-006 says exactly that now; the two
    MEASUREMENTS are separate rules (BR-LED-791 for revenue, BR-LED-792 for
    cost) because they measure different things out of different registers.

    **IT IS COMPLETE WHEN THERE IS NOTHING TO ACCRUE**, not only when something
    was posted — a utility that has settled every invoice it captured has no
    unpaid cost, and a permanently red tick for a month that is genuinely
    finished is how a checklist stops being read. Same posture as the sixth.

    **THE MEASUREMENT RUNS ONLY WHEN NO ACCRUAL STANDS.** The cheap question —
    *is there an entry keyed for this period?* — is asked first, on an indexed
    posting key; the expensive one is asked only in the case a closer is about
    to act on. And it is wrapped: a checklist that raised because a register was
    dark would take the whole close screen down over a tick.
    """
    # Imported HERE and not at module scope: `unpaid_cost_accrual` imports this
    # module for `resolve_entry_date` and `ACCRUAL_ROLE_GATE_IS_A_READING`, so a
    # top-level import either way would be circular.
    from apps.ledger import unpaid_cost_accrual

    try:
        posted = unpaid_cost_accrual.posted_accrual_entry_id(
            period_start=period_start, period_end=period_end
        )
    except Exception as problem:  # pragma: no cover — defensive, see the docstring
        return ChecklistItem(
            code=ITEM_UNPAID_COST_ACCRUAL,
            state=STATE_UNKNOWN,
            detail=f"the unpaid-cost accrual could not be read ({problem}).",
            wanted_reads=("apps.ledger.unpaid_cost_accrual.posted_accrual_entry_id",),
        )
    if posted is not None:
        return ChecklistItem(
            code=ITEM_UNPAID_COST_ACCRUAL,
            state=STATE_COMPLETE,
            detail=(
                "this period's unpaid supplier costs are accrued (BR-LED-792) and reverse on "
                "day 1 of the next period (BR-LED-005), so no payable is carried."
            ),
        )
    try:
        preview = unpaid_cost_accrual.preview_unpaid_costs(
            period_start=period_start, period_end=period_end
        )
    except Exception as problem:  # pragma: no cover — defensive, see the docstring
        return ChecklistItem(
            code=ITEM_UNPAID_COST_ACCRUAL,
            state=STATE_UNKNOWN,
            detail=f"the unpaid-cost figure could not be measured ({problem}).",
            wanted_reads=("apps.ledger.unpaid_cost_accrual.preview_unpaid_costs",),
        )
    if preview.total is None:
        # The window holds purchases in more than one currency, so no single
        # entry can carry them. `unknown`, never a green tick.
        return ChecklistItem(
            code=ITEM_UNPAID_COST_ACCRUAL,
            state=STATE_UNKNOWN,
            detail=(
                "the unpaid-cost figure cannot be measured for this period "
                f"({', '.join(preview.problems) or 'the purchases cannot be summed'}), so "
                "whether cost is unrecognised is unknown rather than no."
            ),
        )
    if preview.total <= ZERO:
        return ChecklistItem(
            code=ITEM_UNPAID_COST_ACCRUAL,
            state=STATE_COMPLETE,
            detail=(
                "nothing captured is unpaid at the end of this period — every supplier "
                "invoice dated on or before it is settled or voided. There is no accrual to "
                "post."
            ),
        )
    return ChecklistItem(
        code=ITEM_UNPAID_COST_ACCRUAL,
        state=STATE_INCOMPLETE,
        # `P5.10` — the same figure this branch was chosen on.
        amount=preview.total,
        outstanding=preview.invoice_rows_total,
        detail=(
            f"{preview.total} of supplier cost is captured, unpaid at the period end and not "
            f"in the books, across {preview.invoice_rows_total} invoice(s). Post the "
            "unpaid-cost accrual (BR-LED-792) — it debits the cost accounts, credits accrued "
            "supplier costs, and reverses itself on day 1 of the next period, so no payable "
            "is ever carried."
        ),
    )


def _books_currency(period_end: date) -> str | None:
    """The one currency the books are kept in, up to `period_end`.

    ⚠ **IT ASKS `reporting` RATHER THAN ANSWERING FOR ITSELF, AND THAT IS THE
    WHOLE REASON THIS FUNCTION IS MORE THAN A CONSTANT.** `reporting.py` already
    owns *what currency is this book in* through `currencies_in`, and a second
    implementation here is a second answer — a screen that showed `USD` beside a
    figure the trial balance called `CAD` would be this repo's DEF-127 shape one
    field over.

    ⚠ **A MIXED BOOK ANSWERS `None`, IT DOES NOT RAISE.** `reporting`'s own
    guard refuses a Σ across two currencies, and that refusal is correct for a
    TOTAL. This is a checklist: refusing the whole close screen because some
    stray CAD entry exists would take away the one page that says what is left
    to do. `None` means *no single currency*, the screen then shows no money
    figure, and the amounts stay out of sight rather than being shown in a
    currency nobody chose.
    """
    from apps.ledger import reporting

    lines = models.JournalLine.objects.filter(
        tenant_id=_tenant_id(),
        journal_entry__status=models.JE_POSTED,
        journal_entry__entry_date__lte=period_end,
    )
    codes = reporting.currencies_in(lines)
    return codes[0] if len(codes) == 1 else None


def close_checklist(*, period_start: date, period_end: date) -> dict[str, Any]:
    """BR-LED-006's items, computed live for one window.

    US-LED-015 TC-1 renders exactly this. Nothing here writes anything: the
    checklist is a read, and `close_period` computes it again at the moment of
    close so the snapshot it stores is the one the closer confirmed.

    ⚠ **SEVEN ITEMS SINCE 2026-09-02, NOT FIVE** (BR-LED-006 AMENDED twice that
    day). This read *"SIX ITEMS… NOT FIVE"* for the few hours between the two.
    The sixth is `unbilled_accrual` (CR-060 C2 / task T7) and the seventh is
    `unpaid_cost_accrual` (C17 / task T7b); their reasoning is in
    `_unbilled_accrual_item` and `_unpaid_cost_accrual_item` above. **They are
    ONE IDEA — period matching — with a half on each side of the books**, which
    is how C17 asks for the rule to be written, and two ITEMS because a closer
    can finish one and not the other.
    """
    items = [
        _seam_item(ITEM_RUNS_ISSUED, period_start, period_end),
        _seam_item(ITEM_BATCHES_RECONCILED, period_start, period_end),
        _seam_item(ITEM_BANK_REC_CURRENT, period_start, period_end),
        _accruals_item(period_start, period_end),
        _unbilled_accrual_item(period_start, period_end),
        _unpaid_cost_accrual_item(period_start, period_end),
        _remittance_item(period_start, period_end),
    ]
    incomplete = tuple(item for item in items if not item.complete)
    return {
        "period": [period_start.isoformat(), period_end.isoformat()],
        "items": tuple(items),
        "incomplete": incomplete,
        "ready": not incomplete,
        "closed": is_period_closed(period_start, period_end),
        # ⚠ **`P5.10` — THE FIGURES ARRIVED, SO THE CURRENCY HAS TO ARRIVE WITH
        # THEM.** Every other Finance report already reports its own currency
        # beside its own numbers (`reporting._one_currency`), and this envelope
        # did not need one while it carried no money. `None` on an empty book is
        # a real answer and not a refusal — a tenant with no posted lines has no
        # currency and no total to get wrong — and the screen shows no money
        # figure in that case either, so the two agree by construction.
        "currency": _books_currency(period_end),
        # EMPTY, and deliberately so. `close_role_gate_is_a_reading_not_a_ruling`
        # rode here until 2026-09-24 and is RETIRED — the PO ruled the close gate
        # (*"system admin and clark"*), so there is no reading left to disclose.
        # The channel STAYS: it is the general one for a figure the books will not
        # state, and a future gap on the checklist belongs in it.
        "unavailable": (),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Close and reopen
# ═══════════════════════════════════════════════════════════════════════════
def _item_payload(item: ChecklistItem) -> dict[str, Any]:
    return {"code": item.code, "state": item.state, "detail": item.detail}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-006")
def close_period(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    closed_at: datetime,
    reason: str | None = None,
) -> dict[str, Any]:
    """BR-LED-018 — WARN + CONFIRM. Never a silent close, never a hard lockout.

    The checklist is recomputed HERE rather than trusted from the screen, because
    a register can move between the modal opening and the confirm landing, and
    the snapshot that is stored must be what was true when the period actually
    shut.

    * every item complete → closes, `reason` optional;
    * anything incomplete or unknown → **closes anyway IF a reason is given**,
      and refuses naming every incomplete item if one is not. That refusal is the
      WARN half; it is not a lockout, because a reason always gets through.

    `closed_at` is an INPUT (BR-TEN-043) — nothing here reads a clock.
    """
    tenant_id = _tenant_id()
    if period_end < period_start:
        raise CloseError(f"the period {period_start} … {period_end} runs backwards.")
    if not isinstance(closed_at, datetime):
        raise CloseError(
            "closed_at must be a datetime supplied by the caller (BR-TEN-043): the moment a "
            "period shut is a business fact, and a service that read the clock would stamp a "
            "different one on a retry."
        )
    existing = _close_row(period_start, period_end)
    if existing is not None and existing.status == models.PERIOD_CLOSED:
        raise CloseError(
            f"the period {period_start} … {period_end} is already closed (since "
            f"{existing.closed_at}). Closing it twice would overwrite the reason and the "
            "incomplete-item snapshot of the FIRST close, which is the record J19 step 1 asks "
            "for. Reopen it (System Admin) if it needs to move."
        )

    checklist = close_checklist(period_start=period_start, period_end=period_end)
    incomplete = checklist["incomplete"]
    cleaned = str(reason or "").strip()
    if incomplete and not cleaned:
        names = ", ".join(f"{item.code} ({item.state})" for item in incomplete)
        raise CloseError(
            f"the close checklist is not complete — {names}. BR-LED-018: a month closes with "
            "WARN + CONFIRM, so this is not a refusal to close; it is the demand for a REASON. "
            "Supply one and the period closes with the incomplete items recorded beside it "
            "(*never a silent close, never a hard lockout*)."
        )

    with transaction.atomic():
        row = existing
        if row is None:
            row = models.FiscalPeriodClose(
                tenant_id=tenant_id, period_start=period_start, period_end=period_end
            )
        row.status = models.PERIOD_CLOSED
        row.closed_at = closed_at
        row.closed_by_user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
        row.close_reason = cleaned or None
        row.incomplete_items = [_item_payload(item) for item in incomplete]
        row.reopened_at = None
        row.reopened_by_user_id = None
        row.reopen_reason = None
        row.save()
        core_audit.money_action(
            actor,
            AUDIT_CLOSED,
            "fiscal_period",
            str(row.pk),
            after={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "closed_at": closed_at.isoformat(),
                "reason": cleaned or None,
                "incomplete_items": row.incomplete_items,
                "job": None if actor is not None else "ledger.close",
            },
        )
    return {
        "period": [period_start.isoformat(), period_end.isoformat()],
        "status": models.PERIOD_CLOSED,
        "closed_at": closed_at,
        "reason": cleaned or None,
        "incomplete_items": tuple(incomplete),
        # EMPTY since 2026-09-24 — see `close_checklist` above for why the
        # channel is kept and the retired marker is not.
        "unavailable": (),
    }


@require_role(SYSTEM_ADMIN, br_ref="BR-LED-006")
def reopen_period(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    reopened_at: datetime,
    reason: str,
) -> dict[str, Any]:
    """BR-LED-006 / BR-TEN-038 — *"SysAdmin reopens"*, with a reason, audited.

    The one role gate in this module that IS separately ruled rather than read
    across from OQ-175: both rules name the System Admin explicitly, so a
    Billing Clerk who may close a month may not reopen one (US-LED-015 TC-4).

    A reason is REQUIRED. Reopening is the act that lets figures an accountant
    may already have exported move again (BR-LED-017), so the record of why has
    to exist before the door opens, not after.
    """
    if not isinstance(reopened_at, datetime):
        raise CloseError("reopened_at must be a datetime supplied by the caller (BR-TEN-043).")
    cleaned = str(reason or "").strip()
    if not cleaned:
        raise CloseError(
            "reopening a closed period needs a REASON (BR-LED-006, *reason + audit*). A reopened "
            "month can receive entries that change totals an ERP has already been handed "
            "(BR-LED-017), so the only record of why that was allowed is the one written now."
        )
    row = _close_row(period_start, period_end)
    if row is None or row.status != models.PERIOD_CLOSED:
        raise CloseError(
            f"the period {period_start} … {period_end} is not closed, so there is nothing to "
            "reopen."
        )
    with transaction.atomic():
        before = {"status": row.status, "closed_at": row.closed_at.isoformat()}
        row.status = models.PERIOD_OPEN
        row.reopened_at = reopened_at
        row.reopened_by_user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
        row.reopen_reason = cleaned
        row.save(
            update_fields=[
                "status",
                "reopened_at",
                "reopened_by_user_id",
                "reopen_reason",
                "updated_at",
            ]
        )
        core_audit.money_action(
            actor,
            AUDIT_REOPENED,
            "fiscal_period",
            str(row.pk),
            before=before,
            after={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "reopened_at": reopened_at.isoformat(),
                "reason": cleaned,
                "job": None if actor is not None else "ledger.close",
            },
        )
    return {
        "period": [period_start.isoformat(), period_end.isoformat()],
        "status": models.PERIOD_OPEN,
        "reopened_at": reopened_at,
        "reason": cleaned,
    }


def closed_periods() -> tuple[dict[str, Any], ...]:
    """Every period this tenant has ever closed, newest first — the S42 banner
    and the *closed-through* card of BR-LED-006's field-map row."""
    rows = models.FiscalPeriodClose.objects.filter(tenant_id=_tenant_id()).order_by(
        "-period_start"
    )
    return tuple(
        {
            "period": [row.period_start.isoformat(), row.period_end.isoformat()],
            "status": row.status,
            "closed_at": row.closed_at,
            "reason": row.close_reason,
            "incomplete_items": tuple(row.incomplete_items or ()),
            "reopened_at": row.reopened_at,
            "reopen_reason": row.reopen_reason,
        }
        for row in rows
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-015@2e059e0 (sha1[:7] of the authorities this module implements, newline-joined in order this module implements, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-015 §1-§7 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-006/015/018 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-9 · 08-qa/01-e2e/journeys/J19-month-end-close.md steps 1-2 + T5-09 · 12-governance/01-open-questions.md OQ-033 CLOSED → BR-TEN-038)
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(the S42 close endpoints are the API half — not built by this lane) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row owed and G7 glob REPORTED)
# gates: see 06-backend/tests/test_us_led_015_month_close.py — every refusal in
#         this file was proved RED before it was trusted green, including the
#         auto-forward (a Jul 30 entry landed in July before the close row
#         existed) and the WARN+CONFIRM (an incomplete checklist closed silently
#         with the reason check removed)
# exceptions: THREE OF FIVE CHECKLIST ITEMS CANNOT BE COMPUTED and are reported
#         `unknown` with the read they want named — billing and payments publish
#         no run/batch/bank-rec counts and this lane may not edit either module ·
#         ~~the CLOSE role gate is a READING of OQ-175~~ **RULED 2026-09-24 —
#         both gates are now signed law (close = System Admin + Billing Clerk,
#         reopen = System Admin), the marker is RETIRED and no result carries it;
#         the accrual carry is NOT ruled and keeps its own** · `lock_closed_periods` is NOT
#         consulted — a closed period locks unconditionally, which is the
#         fail-closed reading of BR-LED-006 and is flagged in `resolve_entry_date`
#         · BILLING AND PAYMENTS DO NOT CALL `resolve_entry_date` YET, so a
#         late-dated BILL or PAYMENT still lands where it was dated: only the
#         manual JE (US-LED-011) is wired to it today. Hard-won law 2 — stated
#         rather than left to be assumed done · the S42 close/reopen ENDPOINTS
#         are not built by this lane, so IS-6's modal→confirm→toast has no server
#         surface yet; the role gates are enforced at the SERVICE layer, which
#         BR-SHL-025 makes the enforcement either way
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

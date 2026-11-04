# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-006 (Pending-billing queue + catch-up sub-runs — hold ≠
#           forget)   Screens: S30 (KPI chip → queue list) · S31 (sub-run mode)
# Rules:    BR-BIL-015 (held accounts enter the Pending-billing queue with
#           aging and escalation, and are billed via catch-up SUB-RUNS —
#           parent-linked, scope-keyed idempotency, never a colliding re-run) ·
#           BR-BIL-005 (the run key; a sub-run's is parent key + scope) ·
#           BR-BIL-034 (anything excluded from a run drops into a queue a human
#           must clear — the run key has no scope term, so excluded work would
#           otherwise be unbillable forever) · BR-BIL-055 (a partial run ISSUES
#           the clean bills and HOLDS the rest; the queue records WHICH DOOR) ·
#           BR-BIL-053 (a break's two ways out: fix-and-retry, or mark for
#           later) · BR-TEN-043 (event-time law — aging is measured against a
#           date the CALLER names, never a wall clock) · CLAUDE.md rule 1
#           (tenant scoping) · rule 7 (every money action writes audit_log)
# Tests:    06-backend/tests/test_us_bil_006_pending_queue.py
# Journeys: J16 (held-account catch-up) · J24 (the five-phase run) · J2 step 8
# Impacts:  apps/billing/runs.create_run + mark_for_later (the row this reads) ·
#           apps/billing/decisions.apply_decisions (door 1) ·
#           core/idempotency.catch_up_run_key (the scope-keyed string) ·
#           apps/billing/api.py (GET /billing/pending · POST …/catch-up)
# ───────────────────────────────────────────────────────
"""The Pending-billing queue, and the catch-up sub-run that empties it.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module composes a CLAUDE.md rule-6
idempotency key (the scope-keyed sub-run key) and creates the run that will
bill real money to accounts a previous run deliberately did not bill.
AI-authored 2026-08-15 under the PO ruling of 2026-08-09; it needs a row in
12-governance/09-human-review-ledger.md.

⚠ CORRECTED 2026-09-01 (DEF-2791) — THE PARAGRAPH BELOW IS HISTORY, NOT THE
CURRENT STATE. `human_owned.txt` carries `06-backend/apps/billing/pending.py`
today ("Pending-billing queue and catch-up sub-runs — carries the idempotency
scope that stops a held bill being issued twice"), measured 2026-09-01, so **G7
DOES read the markers above**. The list does not date this line, so no ruling is
dated here either — inventing one would be worse than the gap. The ask below was
answered; it is kept because why a money path went unguarded is worth knowing.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so G7
does not read the markers above. Editing that guard list is itself a process
event (its own header says so), so the line is REPORTED for the PO batch rather
than self-granted — the same posture, and the same sentence,
`posting_seam.py` and `delivery_seam.py` both took from this position. A marker
no gate reads is hard-won law 1; saying so here is the point of saying it.

╔══════════════════════════════════════════════════════════════════════════╗
║  HOLD ≠ FORGET.                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

BR-BIL-034 states the failure this module exists to prevent, and it is a silent
one: *"the run key is `(tenant, cycle, period)` with no scope term, so a re-run
is refused as a duplicate and excluded work would otherwise be unbillable
forever — silent lost revenue found only when a customer notices."* An account
held in July cannot be billed by re-running July. The queue is the door back,
and the catch-up sub-run is what walks through it.

────────────────────────────────────────────────────────────────────────────
TWO DOORS INTO ONE QUEUE, AND THE QUEUE RECORDS WHICH
────────────────────────────────────────────────────────────────────────────
US-BIL-006 §1, and both doors write the SAME `bill_run_exclusions` row:

  * **Door 1 — a phase-1 HOLD** (BR-BIL-015). The read is missing and staff
    chose *hold* over *estimate* or *bill-without-service*. **Nothing was ever
    calculated for this account.**
  * **Door 2 — a phase-3 MARK-FOR-LATER** (BR-BIL-055, PO answer 1 to the
    partial-run question). The batch RAN, this account produced no draft, and
    rather than block the run the clerk deferred it. **It was calculated and it
    broke**, at a named stage.

The story says why the difference has to survive into the queue: a clerk must
be able to tell *"we never calculated this"* from *"we calculated it and it
broke"*, because the first is fixed by entering a read and the second is often
fixed by fixing configuration. `origin` below is that fact, derived from the
reason code the door wrote — see `ORIGIN_BY_PREFIX`.

**A partial run is the NORMAL case, not a failure mode.** BR-BIL-055: a run
that issues 1,122 of 1,124 and queues 2 is a run that WORKED, and its status is
completed. Nothing here marks a run failed, and `pending_rows` is deliberately
not called "errors".

────────────────────────────────────────────────────────────────────────────
AGING IS MEASURED AGAINST A DATE THE CALLER NAMES (BR-TEN-043, gate G6)
────────────────────────────────────────────────────────────────────────────
`as_of` is a required argument on every function here that computes an age.
Not a default of `date.today()`, and not a server clock: *today* is the
TENANT's, and a queue re-opened in a different timezone must not silently age
its own rows by a day (BR-BIL-066 records the same trap for past-due). It is
also what makes an escalation assertion reproducible in a test that does not
travel in time.

────────────────────────────────────────────────────────────────────────────
ESCALATION SURFACES. IT NEVER BILLS.
────────────────────────────────────────────────────────────────────────────
US-BIL-006 TC-4 and r1.3: *"ages out to escalation (config days)"* — *"still
requires staff action, never auto-bills"*. So `escalated` is a computed FLAG on
a row and this module contains no path that bills anything without a human
starting a sub-run. An escalation that quietly billed would be exactly the
decision-by-omission the PO's whole five-phase description exists to remove.

**THE ESCALATION THRESHOLD IS A TENANT SETTING AND THIS MODULE DOES NOT OWN
ONE.** BR-BIL-021 makes every mechanic tenant-configured with a seeded default,
and the tenant settings surface for THIS number does not exist (S66's billing
defaults are US-TEN-010's). `DEFAULT_ESCALATION_DAYS` is the story's own fixture
value (14) shipped as the DEFAULT of an argument, so the pre-setting behaviour
is reachable and a caller that knows the tenant's number passes it. Reported
rather than invented as a constant nobody can change: the setting is owed, and
`escalation_days` being an argument is what will make wiring it a one-line
change instead of a search.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import IntegrityError, transaction

from apps.billing import models
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import idempotency
from core import tenancy as core_tenancy

# ── The two doors, as reason-code prefixes ──────────────────────────────────
#: Door 1. `decisions._hold_reason` writes `staff_hold_missing_read`,
#: `staff_exclude_no_usage` and friends — every phase-1 hold begins `staff_`.
PREPARE_PREFIX = "staff_"
#: Door 2. Written by `mark_break_for_later` below, and it carries the STAGE
#: that failed inside the code itself (`break_measure-consumption`) so the queue
#: row can be grouped the same way the phase-3 break list is (BR-BIL-040 — a
#: failure names its stage) without a second column.
BREAK_PREFIX = "break_"

ORIGIN_PREPARE = "prepare"  # phase 1 — never calculated
ORIGIN_BREAKS = "breaks"  # phase 3 — calculated, and it broke
ORIGIN_UNKNOWN = "unknown"  # a row written before the two doors were named

#: Door 3 (DEF-BIL-8410, BR-BIL-1054) — at SEND, an account the run's saved
#: Check left out of the run without any clerk's hold: BLOCKED by a problem,
#: or still WAITING ON A DECISION. Nothing was calculated for it, so its
#: origin is `prepare`, like a hold.
CHECK_PREFIX = "check_"
REASON_CHECK_BLOCKED = f"{CHECK_PREFIX}blocked"
REASON_CHECK_UNDECIDED = f"{CHECK_PREFIX}waiting_on_a_decision"

ORIGIN_BY_PREFIX: tuple[tuple[str, str], ...] = (
    (BREAK_PREFIX, ORIGIN_BREAKS),
    (PREPARE_PREFIX, ORIGIN_PREPARE),
    (CHECK_PREFIX, ORIGIN_PREPARE),
)

#: US-BIL-006 §4's fixture threshold, shipped as an argument default rather than
#: a constant — see the module docstring's last paragraph. The tenant setting it
#: stands in for is OWED, not present.
DEFAULT_ESCALATION_DAYS = 14


def origin_of(reason_code: str) -> str:
    """Which door this row came through, from the reason code it was written
    with.

    Derived rather than stored, and that is a deliberate reading of US-BIL-006
    §5, which maps the origin onto `bill_run_exclusions.reason_code + detail`
    (r10 #13) and mints no column for it. A stored `origin` would be a second
    home for a fact the reason code already carries, and the two would drift the
    first time somebody wrote one without the other.

    `unknown` is returned rather than guessed for a code from neither family —
    a row written before the doors were named, or by a caller passing its own
    string. It is shown as unknown on the screen, because inventing a door for
    it would tell a clerk something nobody recorded.
    """
    for prefix, origin in ORIGIN_BY_PREFIX:
        if (reason_code or "").startswith(prefix):
            return origin
    return ORIGIN_UNKNOWN


@dataclass(frozen=True)
class QueueRow:
    """One account waiting to be billed, and everything the S30 list shows.

    `age_days` and `escalated` are COMPUTED against the caller's `as_of` and
    are display facts, never stored — a stored age is wrong the next morning.

    `stage` is present only for door 2 and is `None` for a phase-1 hold, which
    is honest rather than tidy: nothing was calculated for a held account, so
    there is no stage that failed. A screen that showed a stage for both would
    be inventing one.
    """

    exclusion_id: str
    account_id: str
    account_no: str | None
    bill_run_id: str
    parent_run_id: str | None
    period_start: date
    period_end: date
    reason_code: str
    detail: str | None
    origin: str
    stage: str | None
    held_on: date
    age_days: int
    escalated: bool
    resolved_by_run_id: str | None = None
    resolved_on: date | None = None
    #: BR-BIL-1054 — a clerk chose *Leave for next cycle* (billing/0036).
    next_cycle: bool = False

    @property
    def is_open(self) -> bool:
        return self.resolved_by_run_id is None


def _tenant_id() -> Any:
    """Hard rule 1 — refuse loudly rather than run an unscoped query."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        from core import errors

        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def mark_break_for_later(
    *,
    bill_run: Any,
    account_id: str,
    stage: str,
    reason: str,
    detail: str = "",
    excluded_by: Any = None,
) -> Any:
    """Door 2 — BR-BIL-053's *"mark for later"* on a phase-3 break row.

    `runs.mark_for_later` is the write; this is the wrapper that composes the
    reason code so the queue can tell the two doors apart. It exists as its own
    function rather than as a `reason_code=` argument at each call site for one
    reason: a call site that passed `"gas read missing"` would produce a row
    whose origin is `unknown`, and one clerk somewhere would then be told
    nothing about which half of the run it came from.

    The STAGE travels inside the code (`break_measure-consumption`) so the queue
    groups the way the phase-3 list does — BR-BIL-040, *"a stage failure NAMES
    the stage"* — and the human-readable failure travels in `detail`.

    Idempotent on (run, account) through the table's own unique constraint, so
    a double-click marks once.
    """
    from apps.billing import runs

    if not stage:
        raise BillingRuleError(
            "a phase-3 mark-for-later records the STAGE that broke (BR-BIL-040/053). A "
            "queue row with no stage tells a clerk the account failed and not where, "
            "which is the difference between a minute's work and a hunt.",
            br_ref="BR-BIL-053",
        )
    return runs.mark_for_later(
        bill_run=bill_run,
        account_id=account_id,
        reason_code=f"{BREAK_PREFIX}{stage}",
        detail=detail or reason,
        excluded_by=excluded_by,
    )


def _stage_of(reason_code: str) -> str | None:
    if (reason_code or "").startswith(BREAK_PREFIX):
        return reason_code[len(BREAK_PREFIX) :] or None
    return None


def pending_rows(
    *,
    as_of: date,
    escalation_days: int = DEFAULT_ESCALATION_DAYS,
    bill_run_id: Any = None,
    include_resolved: bool = False,
) -> tuple[QueueRow, ...]:
    """The queue: every account a run did not bill, oldest first.

    OLDEST FIRST is the capability matrix's own default sort (`age desc`), and
    it is the right one for the reason escalation exists — the row that has been
    waiting longest is the one closest to being a customer's phone call.

    `include_resolved` exists for the audit view US-BIL-006 TC-3 asks for
    (*"queue rows closed with resolution + link to the child run"*): the row is
    never deleted, so the history of *enter → age → clear* stays readable.
    Default False, because the QUEUE is the unresolved set — that is what makes
    it a queue rather than a log (the `BillRunExclusion` docstring says the same).
    """
    tenant_id = _tenant_id()
    query = models.BillRunExclusion.objects.filter(tenant_id=tenant_id)
    if not include_resolved:
        query = query.filter(resolved_at__isnull=True)
    if bill_run_id is not None:
        query = query.filter(bill_run_id=bill_run_id)
    rows = query.select_related("bill_run", "account").order_by("created_at", "id")

    out: list[QueueRow] = []
    for row in rows:
        held_on = row.created_at.date()
        age_days = max((as_of - held_on).days, 0)
        out.append(
            QueueRow(
                exclusion_id=str(row.pk),
                account_id=str(row.account_id),
                account_no=getattr(row.account, "account_no", None),
                bill_run_id=str(row.bill_run_id),
                parent_run_id=(
                    str(row.bill_run.parent_run_id) if row.bill_run.parent_run_id else None
                ),
                period_start=row.bill_run.period_start,
                period_end=row.bill_run.period_end,
                reason_code=row.reason_code,
                detail=row.detail,
                origin=origin_of(row.reason_code),
                stage=_stage_of(row.reason_code),
                held_on=held_on,
                age_days=age_days,
                # STRICTLY GREATER. US-BIL-006 TC-4's fixture is 14 days and the
                # account "hits day 15" — so the row escalates the day AFTER the
                # threshold, not on it. `>=` would flag a fourteenth-day row the
                # setting says is still inside its window.
                escalated=age_days > escalation_days,
                resolved_by_run_id=(
                    str(row.resolved_by_run_id) if row.resolved_by_run_id else None
                ),
                resolved_on=(row.resolved_at.date() if row.resolved_at else None),
                next_cycle=row.next_cycle_at is not None,
            )
        )
    return tuple(sorted(out, key=lambda item: (-item.age_days, item.account_no or "")))


def pending_count(*, as_of: date, escalation_days: int = DEFAULT_ESCALATION_DAYS) -> dict[str, int]:
    """The S30 KPI chip, and it TIES TO THE LIST (US-BIL-006 §5).

    Computed from `pending_rows` rather than from its own query, which is the
    whole of why it ties: a chip with its own `COUNT(*)` and a list with its own
    `WHERE` disagree the first time one of the two filters changes, and the chip
    is the number a clerk trusts without opening anything.
    """
    rows = pending_rows(as_of=as_of, escalation_days=escalation_days)
    return {
        "pending": len(rows),
        "escalated": sum(1 for row in rows if row.escalated),
        "prepare": sum(1 for row in rows if row.origin == ORIGIN_PREPARE),
        "breaks": sum(1 for row in rows if row.origin == ORIGIN_BREAKS),
    }


def held_account_ids(parent_run: Any) -> frozenset[str]:
    """The parent run's UNRESOLVED held set — the only lawful sub-run scope."""
    return frozenset(
        str(account_id)
        for account_id in models.BillRunExclusion.objects.filter(
            tenant_id=_tenant_id(), bill_run=parent_run, resolved_at__isnull=True
        ).values_list("account_id", flat=True)
    )


class DuplicateCatchUp(BillingRuleError):
    """This exact scope has already been caught up (BR-BIL-005, TC-5).

    Carries the winning sub-run so the screen can show *who ran it, when, and a
    link* — the same shape `runs.DuplicateRun` gives the parent-level refusal,
    and the same shape US-BIL-006 TC-5 asks for in those words.
    """

    def __init__(self, existing: Any):
        self.existing = existing
        super().__init__(
            f"a catch-up sub-run over exactly this scope already exists "
            f"({getattr(existing, 'pk', existing)}), started by "
            f"{getattr(existing, 'run_by_id', None)} on "
            f"{getattr(existing, 'created_at', None)}. BR-BIL-015 keys a sub-run on its "
            "PARENT's key plus its scope, so re-running the same held accounts is refused "
            "rather than billing them twice. A catch-up over a DIFFERENT held subset is a "
            "different scope and starts normally.",
            br_ref="BR-BIL-005",
        )


@transaction.atomic
def create_catch_up_run(
    *,
    parent_run: Any,
    account_ids: tuple[str, ...] | list[str],
    run_by: Any = None,
    actor: Any = None,
) -> models.BillRun:
    """US-BIL-006's exit: a CHILD run over the parent's period, scoped to holds.

    Four things are true of the row this writes, and each is a rule:

      * **`parent_run_id` is set** (r10 #7). The lineage is a real FK so it is
        queryable rather than reconstructed from a key string.
      * **The period is the PARENT's, copied.** US-BIL-006 TC-2: *"same period;
        invoices carry the original period"*. A catch-up bills July in August;
        it does not bill August.
      * **The idempotency key is parent key + scope** (BR-BIL-005/015,
        `core.idempotency.catch_up_run_key`). Composed by the owner of the key
        shapes and never as an f-string here.
      * **The scope is a SUBSET of the parent's UNRESOLVED held set** — TC-6:
        *"a catch-up including an account never held on that run is rejected"*.
        Billing an account the parent never held would bill it TWICE for one
        period, because the parent already billed it.

    The bill DATE is deliberately not copied and not invented. `bill_runs.
    bill_date` is what a clerk typed on S31 step 1 (BR-BIL-070) and NULL means
    *nobody typed one on this run* — a fact, not a gap — so the sub-run's own
    wizard step supplies one or the cycle's date is used, exactly as for any
    other run. Copying the parent's would silently price a catch-up at a date
    nobody typed for it.
    """
    tenant_id = _tenant_id()
    if getattr(parent_run, "tenant_id", None) is not None and str(parent_run.tenant_id) != str(
        tenant_id
    ):
        # HR-1: another tenant's run is ABSENT, never "forbidden".
        from core import errors

        raise errors.deny_as_not_found("BR-TEN-003")

    requested = [str(account_id) for account_id in account_ids or ()]
    if not requested:
        raise BillingRuleError(
            "a catch-up sub-run names the held accounts it is going to bill "
            "(BR-BIL-015). A sub-run with no scope would occupy the parent's catch-up "
            "key and bill nobody.",
            br_ref="BR-BIL-015",
        )
    held = held_account_ids(parent_run)
    stray = sorted(set(requested) - held)
    if stray:
        raise BillingRuleError(
            f"{len(stray)} account(s) in this catch-up were never held on run "
            f"{parent_run.pk} — {', '.join(stray[:5])}. A sub-run's scope must be a "
            "SUBSET of its parent's unresolved held set (US-BIL-006 TC-6): the parent "
            "already billed every account it did not hold, so catching one of those up "
            "would bill it twice for one period.",
            br_ref="BR-BIL-015",
        )

    key = idempotency.catch_up_run_key(parent_key=parent_run.idempotency_key, account_ids=requested)
    existing = models.BillRun.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
    if existing is not None:
        raise DuplicateCatchUp(existing)

    try:
        child = models.BillRun.objects.create(
            tenant_id=tenant_id,
            cycle_id=parent_run.cycle_id,
            period_start=parent_run.period_start,
            period_end=parent_run.period_end,
            bill_date=None,  # see the docstring — never copied, never invented
            status="draft",
            bill_type=parent_run.bill_type,
            idempotency_key=key,
            parent_run=parent_run,
            scope_services=parent_run.scope_services,
            run_by_id=audit.actor_user_id(run_by),  # DEF-BIL-5090
        )
    except IntegrityError as clash:
        # Lost the race between the check and the insert. The unique index is
        # the real guarantee; re-read and answer with the same refusal.
        winner = models.BillRun.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
        if winner is None:
            raise clash
        raise DuplicateCatchUp(winner) from clash

    audit.money_action(
        actor if actor is not None else run_by,
        "bill_run.catch_up_created",
        "bill_run",
        str(child.pk),
        before=None,
        after={
            "parent_run_id": str(parent_run.pk),
            "period_start": child.period_start.isoformat(),
            "period_end": child.period_end.isoformat(),
            "scope_accounts": sorted(requested),
            "idempotency_key": key,
            "status": child.status,
        },
    )
    return child


def queue_not_in_run(*, bill_run: Any, actor: Any = None) -> int:
    """🔒 DEF-BIL-8410 · BR-BIL-1054 — AT SEND, every account the run's saved
    Check left out enters Pending billing. Returns how many rows it wrote.

    BR-BIL-1054, verbatim from the rule: *"At Send every listed account enters
    Pending billing (BR-BIL-034)"*. A hold and a left-out account already
    arrive here through `decisions.apply_decisions` (door 1). What did not —
    and is why this function exists — is an account the Check BLOCKED, or one
    still WAITING ON A DECISION nobody answered: neither is priced, neither
    wrote a row, and so neither could ever be caught up (`held_account_ids`
    reads only this table). Hold ≠ forget.

    Written ONLY for an account with no bill on this run, and idempotent on
    (run, account) through the table's own unique constraint: a re-sent or
    resumed issue writes nothing twice, and an account already queued by a
    hold keeps the reason it was queued with. A run with no saved Check (one
    prepared before the redesign) writes nothing.
    """
    from apps.billing import check_engine, check_store, decisions

    tenant_id = _tenant_id()
    if getattr(bill_run, "cycle_id", None) is None:
        return 0
    statuses = check_store.account_statuses(bill_run)
    if not statuses:
        return 0
    billed = {
        str(one)
        for one in models.Invoice.objects.filter(tenant_id=tenant_id, bill_run=bill_run)
        .values_list("account_id", flat=True)
    }
    first_block, _count = check_store.first_blocking(bill_run)
    reasons = {
        check_engine.STATUS_BLOCKED: REASON_CHECK_BLOCKED,
        check_engine.STATUS_DECISION: REASON_CHECK_UNDECIDED,
        check_engine.STATUS_LEFT_OUT: decisions.LEFT_OUT_REASON,
    }
    written = 0
    for account_id, status in sorted(statuses.items()):
        reason = reasons.get(status)
        if reason is None or account_id in billed:
            continue
        _row, created = models.BillRunExclusion.objects.get_or_create(
            tenant_id=tenant_id,
            bill_run=bill_run,
            account_id=account_id,
            defaults={
                "reason_code": reason,
                # The FIRST blocking tag, as a stable code — the screen words it.
                "detail": first_block.get(account_id),
                "excluded_by_id": audit.actor_user_id(actor),
            },
        )
        if created:
            written += 1
    if written:
        audit.money_action(
            actor,
            "bill_run.not_in_run_queued",
            "bill_run",
            str(getattr(bill_run, "pk", bill_run)),
            before=None,
            after={"queued": written},
        )
    return written


def leave_for_next_cycle(
    *, bill_run: Any, account_ids: Any, at: Any, actor: Any = None
) -> int:
    """BR-BIL-1054 — *Leave for next cycle* on accounts this run left in
    Pending billing (DEF-BIL-8223). The row stays OPEN (the account is still
    owed) and is marked; the first LATER run that bills the account closes it
    (`resolve_for_run`). Refused for an account this run did not queue, or
    whose row is already closed — nothing is marked that is not owed.
    `at` is the caller's event time (BR-TEN-043)."""
    tenant_id = _tenant_id()
    wanted = sorted({str(one) for one in account_ids or ()})
    if not wanted:
        raise BillingRuleError(
            "Leave for next cycle names the accounts it applies to.",
            message_key="billing.check.noAccounts",
            br_ref="BR-BIL-1054",
        )
    rows = list(
        models.BillRunExclusion.objects.filter(
            tenant_id=tenant_id,
            bill_run=bill_run,
            account_id__in=wanted,
            resolved_at__isnull=True,
        )
    )
    stray = sorted(set(wanted) - {str(r.account_id) for r in rows})
    if stray:
        raise BillingRuleError(
            f"{len(stray)} account(s) are not waiting in Pending billing from run "
            f"{bill_run.pk}: {', '.join(stray[:5])}.",
            message_key="billing.notInRun.notPending",
            br_ref="BR-BIL-1054",
        )
    marked = 0
    for row in rows:
        if row.next_cycle_at is not None:
            continue
        row.next_cycle_at = at
        row.next_cycle_by_id = audit.actor_user_id(actor)
        row.save(update_fields=["next_cycle_at", "next_cycle_by_id"])
        marked += 1
    if marked:
        audit.money_action(
            actor,
            "bill_run.left_for_next_cycle",
            "bill_run",
            str(bill_run.pk),
            before=None,
            after={"accounts": wanted, "marked": marked},
        )
    return marked


def resolve_for_run(*, bill_run: Any, resolved_at: Any, actor: Any = None) -> int:
    """Close the queue rows a run has now billed. Returns how many closed.

    US-BIL-006 TC-3: *"queue rows closed with resolution + link to the child
    run; KPI chip decrements; audit trail complete"*.

    WHAT COUNTS AS BILLED, and it is deliberately narrow: an account has left
    the queue when an INVOICE exists for it on this run. Not when the sub-run
    was created (a created run has billed nobody), and not when a draft exists
    (a draft is discardable, BR-BIL-004) — only when the run holds a row for
    that account. A row closed early is a row nobody chases, which is the exact
    failure BR-BIL-034 names.

    It closes rows on the PARENT chain, not on this run: the exclusion was
    written against the run that held the account, and the child's id goes into
    `resolved_by_run` so the link US-BIL-006 §5 asks for points forward.

    `resolved_at` is the caller's event time (BR-TEN-043) — no clock here.
    """
    tenant_id = _tenant_id()
    # Each billed account's EARLIEST day billed on this run — a bill's own
    # period, which fixed-charge case 3 may have moved back over a held month.
    starts: dict[str, Any] = {}
    for account_id, start in models.Invoice.objects.filter(
        tenant_id=tenant_id, bill_run=bill_run
    ).values_list("account_id", "period_start"):
        key = str(account_id)
        if start is not None and (key not in starts or start < starts[key]):
            starts[key] = start
        starts.setdefault(key, None)
    billed = set(starts)
    if not billed:
        return 0
    open_rows = list(
        models.BillRunExclusion.objects.filter(
            tenant_id=tenant_id, resolved_at__isnull=True, account_id__in=billed
        ).exclude(bill_run=bill_run)
    )
    closed = 0
    for row in open_rows:
        # Only the same PERIOD. An account held for July and billed for August
        # is still owed its July bill, and closing that row on an August run
        # would lose exactly the revenue BR-BIL-034 exists to protect.
        #
        # ONE EXCEPTION, AND A CLERK CHOSE IT (BR-BIL-1054, billing/0036): a
        # row LEFT FOR THE NEXT CYCLE is closed by the first LATER run that
        # bills the account, because that run bills from the last billed read
        # (BR-BIL-1039) and so carries the held usage — the choice the clerk
        # made instead of a catch-up run.
        same_period = (row.bill_run.period_start, row.bill_run.period_end) == (
            bill_run.period_start,
            bill_run.period_end,
        )
        next_cycle = (
            row.next_cycle_at is not None and bill_run.period_start > row.bill_run.period_end
        )
        # 🔒 DEF-BIL-8413 — AND A LATER BILL WHOSE OWN PERIOD COVERS THE HELD ONE
        # closes it. PO 2026-09-30, fixed-charge case 3: a held account's next
        # bill *"starts the day after that account's last bill"* (Sep 1 – Oct 31,
        # one base), so it BILLS the held month. Left open, the row invited a
        # catch-up run over a month already billed — the same usage and the
        # same base twice. Read off the bill's own `period_start`, so an
        # August bill for August (US-BIL-006 TC-3b) still closes nothing.
        billed_from = starts.get(str(row.account_id))
        covered = (
            billed_from is not None
            and bill_run.period_start > row.bill_run.period_end
            and billed_from <= row.bill_run.period_start
        )
        if not (same_period or next_cycle or covered):
            continue
        row.resolved_by_run = bill_run
        row.resolved_at = resolved_at
        row.save(update_fields=["resolved_by_run", "resolved_at"])
        closed += 1
        audit.money_action(
            actor,
            "bill_run.queue_row_resolved",
            "bill_run_exclusions",
            str(row.pk),
            before={"resolved_by_run_id": None},
            after={
                "resolved_by_run_id": str(bill_run.pk),
                "account_id": str(row.account_id),
                "held_by_run_id": str(row.bill_run_id),
                "reason_code": row.reason_code,
            },
        )
    return closed


#: What this module does NOT do, carried so a caller never has to infer an
#: absence and a reviewer never has to take the docstring's word for it
#: (the MOVE_OUT_UNAVAILABLE precedent).
PENDING_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "escalation_days_is_not_a_tenant_setting_yet",
        "br_ref": "BR-BIL-015 · BR-BIL-021",
        "detail": "the escalation threshold is a TENANT setting under BR-BIL-021 and no "
        "settings surface owns it. US-BIL-006 §4's fixture value (14) ships as the DEFAULT "
        "of `escalation_days`, so the pre-setting behaviour is reachable and a caller that "
        "knows the tenant's number passes it. The setting is OWED — reported, never "
        "invented as a constant nobody can change.",
    },
    {
        "code": "catch_up_does_not_run_itself",
        "br_ref": "BR-BIL-051 · BR-BIL-055",
        "detail": "`create_catch_up_run` writes the run ROW and stops, exactly as "
        "`runs.create_run` does for a cycle run. Preparing, calculating, drafting and "
        "issuing it are the same five phases as any other run and are reached through the "
        "same functions — there is no separate catch-up pipeline, which is US-BIL-006's own "
        "*'flowing drafts→issue like any run'*.",
    },
    {
        "code": "no_background_worker",
        "br_ref": "BR-BIL-051",
        "detail": "BR-BIL-051 makes the calculation and the release BACKGROUND batches. "
        "There is no job runner in this project (celery is a declared dependency with no "
        "`tasks.py`), so a catch-up runs inline like every other run. Named rather than "
        "implied — `issue.py` records the same gap for the same reason.",
    },
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-006@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-15 by Eng-Lead (US-BIL-006 lane — the pending queue and the
#         scope-keyed catch-up sub-run)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S30's KPI chip and queue list are not built; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_006_pending_queue.py · run_gates ·
#         four mutations proved RED (the subset guard, the scope-keyed
#         duplicate, the strictly-greater escalation boundary, and the
#         same-period condition on resolution) — quoted in the lane report
# exceptions: (1) [CLOSED 2026-09-01, DEF-2791] "NO GLOB IN human_owned.txt
#         MATCHES THIS FILE, so G7 does not read its markers" was true when
#         written and is false now: the glob is there and G7 checks this file.
#         Kept as history, per the module docstring's dated correction.
#         (2) The escalation threshold is an argument
#         default, not a tenant setting — PENDING_UNAVAILABLE says so.
#         (3) `origin` is DERIVED from the reason code rather than stored:
#         US-BIL-006 §5 maps it onto `reason_code + detail` and mints no column,
#         and a second home for one fact drifts.
#         (4) The S30 KPI chip and queue LIST are backend-only here — the
#         endpoints exist and nothing in 07-frontend calls them yet. Hard-won
#         law 2 applies and the gap is REPORTED rather than described as done.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

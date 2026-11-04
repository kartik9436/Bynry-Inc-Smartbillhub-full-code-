# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md
#           B1 (every Scope refusal and warning in one pass) · B2 (continuity
#           against the cycle's REAL last run) · B4 (run name + template
#           required) · B5 (scope counts + last-run counts) · B6 (cycle details
#           + previous runs) · A1/A2 (the two routes that serve this)
# Rulings:  14-bulk-bill-run-changes.md rows 10–19, 29–35 and ROW 43 (PO
#           2026-09-30 — THE full list of Scope refusals and warnings) · the
#           2026-09-30 rows of 12-governance/02-decision-log.md
# Rules:    BR-BIL-1050 (this list, minted 2026-09-30) · BR-BIL-005 (who/when/link on a duplicate) · BR-BIL-024 (bill date)
#           · BR-BIL-1041 (template chosen at Scope) · BR-TEN-003 / HR-1
#           (unknown, malformed and cross-tenant are ONE answer) · hard rule 1
# Tests:    06-backend/tests/test_bulk_run_scope.py
# Defects:  DEF-BIL-8160 (continuity judged from one page of runs) ·
#           DEF-BIL-5297 (meter counts served null for want of a bulk read)
# ───────────────────────────────────────────────────────
"""The bulk bill run's Scope step, checked on the server — ONE PASS, EVERY PROBLEM.

WHAT THIS IS FOR
----------------
PO 2026-09-30, verbatim: *"what if we have warnings or rufusals on step 1 how you
will show them that is not coming out"*. Until this module the Scope step's
problems arrived ONE AT A TIME: `runs.create_run` raised at the first thing it
disliked, so a clerk with four mistakes fixed one, pressed Start, and met the
second. Row 43 of `14-bulk-bill-run-changes.md` is the PO's full list, and this
module is that list and nothing else — each item with its FIELD (so the screen
can put the sentence under the input) and its OWN catalogue key.

**Scope checks the RUN, never an account** (row 43's last sentence). Every
per-account problem is found at Check. So nothing here prices, gathers a bill,
or reads a meter reading; the most expensive thing it does is COUNT.

TWO KINDS, AND THE DIFFERENCE IS THE START BUTTON
------------------------------------------------
* a **refusal** disables Start and `POST /billing/runs` will not create the run;
* a **warning** is shown and Start stays enabled.

The no-run-number-series case is a WARNING and not a refusal, and that is our
decision recorded in the decision log of 2026-09-30, not an omission: the run is
created unnumbered and `runs._allocate_run_no` says so (the drawing had it as a
refusal and is corrected).

CONTINUITY — `DEF-BIL-8160`
---------------------------
The screen used to judge *continuous / gap / overlap* in the browser from the
page of past runs it happened to have loaded, and counted abandoned runs. Here it
is judged against the cycle's newest real run by a database ordering, so run 51
counts as much as run 1, and a run that issued nothing and was abandoned (or a
legacy `cancelled` one) is ignored — the PO's *"cancelled drafts ignored"*.

⚠ **THE DUPLICATE CHECK DOES NOT IGNORE THEM, AND CANNOT.** An exact repeat of
cycle + period is refused by the UNIQUE index on the run's key whatever the old
run's status is, so a refusal is the truthful answer; saying *"overlap ignored"*
and then failing at insert would be a Start button that lies.

WHY EACH SEAM CALL IS IN ITS OWN SAVEPOINT
------------------------------------------
*"Meter Reads or Customers not answering (names which; the form is kept)"* is a
refusal on the PO's list. Catching a failing seam and carrying on is exactly the
shape hard-won law 14 is about: on PostgreSQL a failed statement aborts the whole
transaction and every later query raises `InFailedSqlTransaction`. So each call
to another module runs inside `transaction.atomic()` — a SAVEPOINT — and a
failure rolls back only that savepoint. **Do not "simplify" it away**: the test
suite runs on SQLite, which has no aborted-transaction state, and the broken
version passes every test there. The PostgreSQL proof is recorded in the test
file's header.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.billing import gather, models
from apps.billing.template_models import BillTemplate
from core import errors
from core import idempotency
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing.run_scope")

# ── Vocabulary ───────────────────────────────────────────────────────────────

REFUSAL = "refusal"
WARNING = "warning"

#: The fields a Scope problem may name — the inputs of *What to bill*. `None`
#: is a problem about the run as a whole (a role, a module, the cycle's units).
FIELD_LABEL = "label"
FIELD_CYCLE = "cycle_id"
FIELD_PERIOD_START = "period_start"
FIELD_PERIOD_END = "period_end"
FIELD_BILL_DATE = "bill_date"
FIELD_DUE_DAYS = "due_days"
FIELD_TEMPLATE = "template_id"

#: Run statuses that never count for continuity: a run that issued nothing and
#: was thrown away. `abandoned` is `runs.RUN_STATUS_ABANDONED`; `cancelled` is
#: the older word `models.RUN_STATUSES` still carries for rows already written.
IGNORED_FOR_CONTINUITY: frozenset[str] = frozenset({"abandoned", "cancelled"})

#: The catalogue namespace. Every clerk-facing sentence here is a key under it
#: (B14 rule 33 caps each sentence at six words; the words live in the eleven
#: catalogues and nowhere in this file).
_KEY = "billing.runScope"

#: code → (severity, catalogue key, catalogue error code for a field error).
#: One row per item on row 43's list, in its order. A code that is not here
#: cannot be raised, so the list and the catalogue cannot drift apart.
PROBLEMS: dict[str, tuple[str, str, str]] = {
    # ── refusals ──
    "not_allowed": (REFUSAL, f"{_KEY}.refusal.notAllowed", errors.AUTH_PERMISSION_DENIED),
    "label_missing": (REFUSAL, f"{_KEY}.refusal.labelMissing", errors.VAL_REQUIRED),
    "cycle_missing": (REFUSAL, f"{_KEY}.refusal.cycleMissing", errors.VAL_REQUIRED),
    "cycle_unknown": (REFUSAL, f"{_KEY}.refusal.cycleUnknown", errors.VAL_UNKNOWN_LOOKUP),
    "period_start_missing": (REFUSAL, f"{_KEY}.refusal.periodStartMissing", errors.VAL_REQUIRED),
    "period_start_invalid": (REFUSAL, f"{_KEY}.refusal.periodStartInvalid", errors.VAL_FORMAT),
    "period_end_missing": (REFUSAL, f"{_KEY}.refusal.periodEndMissing", errors.VAL_REQUIRED),
    "period_end_invalid": (REFUSAL, f"{_KEY}.refusal.periodEndInvalid", errors.VAL_FORMAT),
    "period_order": (REFUSAL, f"{_KEY}.refusal.periodOrder", errors.VAL_RANGE),
    "period_overlap": (REFUSAL, f"{_KEY}.refusal.periodOverlap", errors.BIZ_STATE),
    "duplicate_run": (REFUSAL, f"{_KEY}.refusal.duplicate", errors.BIZ_IDEMPOTENT),
    #: The same refusal when the person who ran it has no name recorded (an
    #: invited user, or a system job) — the sentence cannot say *by whom*.
    "duplicate_run_unnamed": (REFUSAL, f"{_KEY}.refusal.duplicateNoName", errors.BIZ_IDEMPOTENT),
    "bill_date_invalid": (REFUSAL, f"{_KEY}.refusal.billDateInvalid", errors.VAL_FORMAT),
    "bill_date_needed": (REFUSAL, f"{_KEY}.refusal.billDateNeeded", errors.VAL_REQUIRED),
    "bill_date_before_period_end": (
        REFUSAL,
        f"{_KEY}.refusal.billDateBeforePeriodEnd",
        errors.VAL_RANGE,
    ),
    "due_days_invalid": (REFUSAL, f"{_KEY}.refusal.dueDaysInvalid", errors.VAL_RANGE),
    "template_missing": (REFUSAL, f"{_KEY}.refusal.templateMissing", errors.VAL_REQUIRED),
    "template_unknown": (REFUSAL, f"{_KEY}.refusal.templateUnknown", errors.VAL_UNKNOWN_LOOKUP),
    "template_unpublished": (
        REFUSAL,
        f"{_KEY}.refusal.templateUnpublished",
        errors.BIZ_STATE,
    ),
    "cycle_no_units": (REFUSAL, f"{_KEY}.refusal.cycleNoUnits", errors.BIZ_COMPLETENESS),
    "cycle_no_accounts": (REFUSAL, f"{_KEY}.refusal.cycleNoAccounts", errors.BIZ_COMPLETENESS),
    "meter_reads_not_answering": (REFUSAL, f"{_KEY}.refusal.meterReadsDown", errors.SYS_PROVIDER),
    "customers_not_answering": (REFUSAL, f"{_KEY}.refusal.customersDown", errors.SYS_PROVIDER),
    # ── warnings ──
    "period_gap": (WARNING, f"{_KEY}.warning.periodGap", ""),
    "period_length": (WARNING, f"{_KEY}.warning.periodLength", ""),
    "period_after_today": (WARNING, f"{_KEY}.warning.periodAfterToday", ""),
    "bill_day_differs": (WARNING, f"{_KEY}.warning.billDayDiffers", ""),
    "due_days_changed": (WARNING, f"{_KEY}.warning.dueDaysChanged", ""),
    "template_not_usual": (WARNING, f"{_KEY}.warning.templateNotUsual", ""),
    "units_nobody_to_bill": (WARNING, f"{_KEY}.warning.nobodyToBill", ""),
    "services_no_meter": (WARNING, f"{_KEY}.warning.missingMeter", ""),
    "no_run_number_series": (WARNING, f"{_KEY}.warning.noRunNumberSeries", ""),
    "first_run": (WARNING, f"{_KEY}.warning.firstRun", ""),
    # (The TEMPORARY `name_derived` / `template_derived` warnings that let the
    # old `BillRunWizard` start a run with no name and no template field were
    # REMOVED with that screen — plan task F2, 2026-09-30. The one screen left
    # always sends both, so an absent field is refused like an empty one.)
}

#: The summary sentence the envelope carries when the POST is refused.
REFUSED_SUMMARY_KEY = f"{_KEY}.refused"


@dataclass(frozen=True)
class ScopeProblem:
    """One refusal or one warning, on its field, with its own key."""

    code: str
    field: str | None
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        return PROBLEMS[self.code][0]

    @property
    def message_key(self) -> str:
        return PROBLEMS[self.code][1]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message_key": self.message_key,
            "params": dict(self.params),
        }

    def as_field_error(self) -> dict[str, Any]:
        """The envelope's `field_errors[]` item — `{field, code, message_key,
        params}` (core/errors) plus `reason`, the Scope code, so a screen can
        tell two refusals on one field apart."""
        return {
            "field": self.field,
            "code": PROBLEMS[self.code][2],
            "reason": self.code,
            "message_key": self.message_key,
            "params": dict(self.params),
        }


@dataclass
class ScopeCheck:
    """Everything the Scope step shows, from one pass. Writes nothing."""

    refusals: list[ScopeProblem] = field(default_factory=list)
    warnings: list[ScopeProblem] = field(default_factory=list)
    #: The parsed inputs `create_run` is called with when there is no refusal.
    parsed: dict[str, Any] = field(default_factory=dict)
    cycle: dict[str, Any] | None = None
    counts: dict[str, Any] | None = None
    last_run_counts: dict[str, Any] | None = None
    continuity: dict[str, Any] = field(default_factory=lambda: {"state": "unknown"})
    previous_run: dict[str, Any] | None = None

    def add(self, code: str, field_name: str | None, **params: Any) -> None:
        problem = ScopeProblem(code, field_name, params)
        (self.refusals if problem.severity == REFUSAL else self.warnings).append(problem)

    @property
    def ok(self) -> bool:
        return not self.refusals

    def codes(self) -> list[str]:
        return [problem.code for problem in (*self.refusals, *self.warnings)]


# ── Seams: another module's published read, in its own savepoint ────────────


class _NotAnswering(Exception):
    """A module's seam is unpublished or failed. Carries WHICH module."""

    def __init__(self, module: str) -> None:
        super().__init__(module)
        self.module = module


def _published(module: str, attribute: str, kind: str = "selectors") -> Any:
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _ask(module: str, attribute: str, *args: Any, answering_as: str | None = None, **kwargs: Any) -> Any:
    """Call `apps.<module>.selectors.<attribute>` inside a SAVEPOINT.

    Raises `_NotAnswering(answering_as or module)` when the name is unpublished
    or the call fails for any reason other than the owner's own not-found
    (which the caller turns into its own answer). See the module docstring for
    why the savepoint is load-bearing on PostgreSQL (hard-won law 14).
    """
    who = answering_as or module
    target = _published(module, attribute)
    if target is None:
        raise _NotAnswering(who)
    try:
        with transaction.atomic():
            return target(*args, **kwargs)
    except errors.NotFoundError:
        raise
    except Exception:  # noqa: BLE001 — a module not answering, named, never a 500
        logger.exception("run scope: %s.%s did not answer", module, attribute)
        raise _NotAnswering(who) from None


#: The module a clerk knows by name. Assets are Meter Reads' (CLAUDE.md module
#: map: metering, product name Meter Reads, owns assets per B2 r4).
_METER_READS = "metering"
_CUSTOMERS = "customers"
_NOT_ANSWERING_CODE = {
    _METER_READS: "meter_reads_not_answering",
    _CUSTOMERS: "customers_not_answering",
}


# ── Parsing: each input on its own, so every problem is found at once ──────


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(value: Any) -> tuple[date | None, bool]:
    """`(date, present)`. `present` with `None` means *typed and not a date*."""
    if isinstance(value, date):
        return value, True
    text = _text(value)
    if not text:
        return None, False
    try:
        return date.fromisoformat(text), True
    except ValueError:
        return None, True


def _parse_due_days(value: Any) -> tuple[int | None, bool]:
    """`(days, valid)`. Blank is valid and means *use the cycle's*.

    ⚠ `0` is lawful (due on the bill date, BR-MET-009) and `True` is not a
    number of days — `bool` is an `int` in Python, so it is refused by name.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, True
    if isinstance(value, bool):
        return None, False
    if isinstance(value, int):
        return (value, True) if value >= 0 else (None, False)
    text = _text(value)
    if text.lstrip("+").isdigit():
        return int(text), True
    return None, False


def _as_uuid(value: Any) -> str | None:
    try:
        return str(UUID(_text(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _clamped_day(day: int, on: date) -> int:
    """The cycle's bill day in `on`'s month — OQ-339's clamp (31st → 28/29 Feb)."""
    return min(max(int(day), 1), monthrange(on.year, on.month)[1])


def default_bill_date(cycle_bill_day: int | None, period_end: date | None) -> date | None:
    """`runs.default_bill_date`, the ONE rule (OQ-344). Imported at call time
    because `runs` imports half the module and this file is imported by the API."""
    from apps.billing import runs

    return runs.default_bill_date(cycle_bill_day, period_end)


# ── Reads this module owns (billing's own tables) ───────────────────────────


def _cycle_runs(cycle_id: Any) -> Any:
    """The cycle's OWN runs: parent runs of type `cycle`, this tenant only.

    A catch-up (`parent_run`) re-bills its parent's period and is not a
    period of its own; a one-time bill has no cycle.
    """
    return models.BillRun.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        cycle_id=cycle_id,
        parent_run__isnull=True,
        bill_type="cycle",
    )


def _run_ref(run: Any) -> dict[str, Any]:
    return {
        "run_id": str(run.pk),
        "run_no": run.run_no,
        "label": run.label,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
    }


def _ran_by_name(run: Any) -> str | None:
    user = getattr(run, "run_by", None) if run.run_by_id else None
    return (getattr(user, "full_name", None) or None) if user is not None else None


def last_run_counts(run: Any) -> dict[str, Any] | None:
    """Row 30 — the previous run's Accounts to bill · Regular · Master, ONLY
    where its saved bills prove them (PO: *"if you canget that number then only
    show it here"*).

    Distinct accounts on the run's LOCKED bills (what went out), split by the
    account's `kind`. `None` when the run has no locked bill — a run that sent
    nothing proves no count, and a zero would claim it billed nobody.
    """
    if run is None:
        return None
    rows = list(
        models.Invoice.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            bill_run_id=run.pk,
            status__in=models.INVOICE_LOCKED_STATUSES,
        )
        .values_list("account_id", "account__kind")
        .distinct()
    )
    if not rows:
        return None
    kinds = {str(account_id): str(kind or "") for account_id, kind in rows}
    masters = sum(1 for kind in kinds.values() if kind == gather.ACCOUNT_KIND_MASTER)
    return {
        "run_id": str(run.pk),
        "accounts_to_bill": len(kinds),
        "regular_accounts": len(kinds) - masters,
        "master_accounts": masters,
    }


# ── The pass ────────────────────────────────────────────────────────────────


def check_scope(
    *,
    cycle_id: Any,
    period_start: Any,
    period_end: Any,
    bill_date: Any = None,
    due_days: Any = None,
    template_id: Any = None,
    label: Any = None,
    can_run: bool = True,
    with_counts: bool = True,
) -> ScopeCheck:
    """Row 43, in one pass. Every input is checked on its own, so a clerk with
    four mistakes sees four sentences. READ ONLY — writes no row of any table.

    `can_run` is the caller's answer to *may this person start a run* (A4:
    Admin or Clerk). `with_counts=False` skips the cycle-wide counts, for a
    caller that only needs the verdict on the typed fields.
    """
    check = ScopeCheck()
    if not can_run:
        check.add("not_allowed", None)

    # ── What to bill: the typed fields ─────────────────────────────────────
    name = _text(label)
    if not name:
        check.add("label_missing", FIELD_LABEL)

    start, start_present = _parse_date(period_start)
    end, end_present = _parse_date(period_end)
    if start is None:
        check.add("period_start_invalid" if start_present else "period_start_missing", FIELD_PERIOD_START)
    if end is None:
        check.add("period_end_invalid" if end_present else "period_end_missing", FIELD_PERIOD_END)
    period_ok = start is not None and end is not None and end >= start
    if start is not None and end is not None and end < start:
        check.add("period_order", FIELD_PERIOD_END)

    typed_bill, bill_present = _parse_date(bill_date)
    if typed_bill is None and bill_present:
        check.add("bill_date_invalid", FIELD_BILL_DATE)
    elif typed_bill is not None and end is not None and typed_bill < end:
        check.add("bill_date_before_period_end", FIELD_BILL_DATE, periodEnd=end.isoformat())

    days, days_valid = _parse_due_days(due_days)
    if not days_valid:
        check.add("due_days_invalid", FIELD_DUE_DAYS)

    template_pk = _check_template(check, template_id)

    # ── The cycle ──────────────────────────────────────────────────────────
    cycle = _check_cycle(check, cycle_id)
    check.cycle = cycle
    if cycle is not None:
        bill_day = cycle.get("bill_day")
        if not bill_present and bill_day is None:
            check.add("bill_date_needed", FIELD_BILL_DATE)
        if typed_bill is not None and bill_day is not None:
            expected_day = _clamped_day(bill_day, typed_bill)
            if typed_bill.day != expected_day:
                check.add("bill_day_differs", FIELD_BILL_DATE, billDay=int(bill_day))
        cycle_days = cycle.get("due_days")
        if days is not None and cycle_days is not None and days != int(cycle_days):
            check.add("due_days_changed", FIELD_DUE_DAYS, cycleDays=int(cycle_days))

    # ── Continuity, against the cycle's real runs (B2) ─────────────────────
    previous = None
    if cycle is not None and period_ok:
        previous = _check_continuity(check, cycle["id"], start, end)
        _check_period_length(check, cycle, start, end)
    elif cycle is not None:
        # DEF-BIL-8681 — a period the clerk is still typing does not make the
        # cycle's history disappear: Previous runs and the aside's Last run name
        # the cycle's newest live run (D1 05). Continuity is NOT judged here —
        # there is no period to judge it against — and `previous` stays None so
        # nothing below compares a template or counts against a guess.
        latest = (
            _cycle_runs(cycle["id"])
            .exclude(status__in=IGNORED_FOR_CONTINUITY)
            .order_by("-period_end", "-created_at", "-id")
            .first()
        )
        check.previous_run = None if latest is None else _run_ref(latest)
    if previous is not None and template_pk is not None:
        if previous.template_id is not None and str(previous.template_id) != str(template_pk):
            check.add("template_not_usual", FIELD_TEMPLATE)
    if end is not None:
        _check_after_today(check, end)
    _check_numbering(check)

    # ── This run covers (B5) ───────────────────────────────────────────────
    if cycle is not None and with_counts:
        check.counts = _check_counts(check, cycle["id"])
    check.last_run_counts = last_run_counts(previous)

    check.parsed = {
        "cycle_id": None if cycle is None else cycle["id"],
        "period_start": start,
        "period_end": end,
        "bill_date": typed_bill,
        "due_days": days,
        "template_id": template_pk,
        "label": name or None,
    }
    return check


def _check_template(check: ScopeCheck, template_id: Any) -> Any:
    """Missing · not this utility's · not published (BR-BIL-1041, BR-BIL-026).
    Unknown, malformed and another tenant's are ONE answer (HR-1)."""
    if not _text(template_id):
        check.add("template_missing", FIELD_TEMPLATE)
        return None
    pk = _as_uuid(template_id)
    template = (
        None
        if pk is None
        else BillTemplate.objects.filter(tenant_id=core_tenancy.current_tenant_id(), pk=pk).first()
    )
    if template is None:
        check.add("template_unknown", FIELD_TEMPLATE)
        return None
    from apps.billing import templates_service

    if templates_service.published_version(template) is None:
        check.add("template_unpublished", FIELD_TEMPLATE)
        return None
    return template.pk


def _check_cycle(check: ScopeCheck, cycle_id: Any) -> dict[str, Any] | None:
    """The cycle, through metering's own read. HR-1: unknown, malformed and
    another tenant's cycle are one refusal with one body."""
    if not _text(cycle_id):
        check.add("cycle_missing", FIELD_CYCLE)
        return None
    if _as_uuid(cycle_id) is None:
        check.add("cycle_unknown", FIELD_CYCLE)
        return None
    try:
        detail = _ask(_METER_READS, "cycle_detail", _as_uuid(cycle_id))
    except errors.NotFoundError:
        check.add("cycle_unknown", FIELD_CYCLE)
        return None
    except _NotAnswering as down:
        check.add(_NOT_ANSWERING_CODE[down.module], None)
        return None
    return dict(detail)


def _check_continuity(check: ScopeCheck, cycle_id: str, start: date, end: date) -> Any:
    """Duplicate · overlap · gap · first run. Returns the PREVIOUS run (the
    newest real run starting before this period), or None.

    ⚠ ORDERED BY THE DATABASE OVER ALL OF THE CYCLE'S RUNS — never a page of
    them (`DEF-BIL-8160`).
    """
    key = idempotency.bill_run_key(cycle_id=cycle_id, period_start=start, period_end=end)
    duplicate = (
        models.BillRun.objects.filter(tenant_id=core_tenancy.current_tenant_id(), idempotency_key=key)
        .select_related("run_by")
        .first()
    )
    if duplicate is not None:
        check.add(
            "duplicate_run" if _ran_by_name(duplicate) else "duplicate_run_unnamed",
            FIELD_PERIOD_START,
            run_id=str(duplicate.pk),
            runNo=duplicate.run_no,
            label=duplicate.label,
            ran_by=None if duplicate.run_by_id is None else str(duplicate.run_by_id),
            ranBy=_ran_by_name(duplicate),
            ranAt=duplicate.created_at.isoformat(),
        )

    live = _cycle_runs(cycle_id).exclude(status__in=IGNORED_FOR_CONTINUITY)
    overlapping = (
        live.filter(period_start__lte=end, period_end__gte=start)
        .exclude(pk=None if duplicate is None else duplicate.pk)
        .order_by("-period_end", "-created_at", "-id")
        .first()
    )
    if overlapping is not None:
        check.add(
            "period_overlap",
            FIELD_PERIOD_START,
            **{
                **_run_ref(overlapping),
                "from": max(start, overlapping.period_start).isoformat(),
                "to": min(end, overlapping.period_end).isoformat(),
                "runNo": overlapping.run_no,
            },
        )
    previous = (
        live.filter(period_start__lt=start)
        .order_by("-period_end", "-created_at", "-id")
        .first()
    )
    check.previous_run = None if previous is None else _run_ref(previous)
    if overlapping is not None or duplicate is not None:
        check.continuity = {
            "state": "overlap",
            "run": _run_ref(overlapping or duplicate),
        }
        return previous
    if previous is None:
        check.continuity = {"state": "first"}
        check.add("first_run", None)
        return None
    expected = previous.period_end + timedelta(days=1)
    if start > expected:
        gap_to = start - timedelta(days=1)
        check.continuity = {
            "state": "gap",
            "from": expected.isoformat(),
            "to": gap_to.isoformat(),
            "days": (start - expected).days,
            "run": _run_ref(previous),
        }
        check.add(
            "period_gap",
            FIELD_PERIOD_START,
            **{"from": expected.isoformat(), "to": gap_to.isoformat(), "days": (start - expected).days},
        )
    else:
        check.continuity = {"state": "continuous", "run": _run_ref(previous)}
    return previous


def _check_period_length(check: ScopeCheck, cycle: dict[str, Any], start: date, end: date) -> None:
    """Warn when the period is not one period of the cycle's frequency —
    metering's own `cycle_expected_span_days` (BR-MET-121), never a guessed 30."""
    try:
        expected = _ask(_METER_READS, "cycle_expected_span_days", cycle["id"], period_start=start)
    except (errors.NotFoundError, _NotAnswering):
        return
    days = (end - start).days + 1
    if expected is not None and int(expected) != days:
        check.add(
            "period_length",
            FIELD_PERIOD_END,
            days=days,
            expected=int(expected),
            frequency=_frequency_word(cycle.get("frequency")),
        )


def _frequency_word(stored: Any) -> Any:
    """DEF-BIL-8691 — the cycle's frequency as Meter Reads' ONE business word
    (`Monthly`, never a shipped row's `monthly` or `bi_monthly`), so the screen
    can say *"Cycle is monthly."* in each language from one key. Metering's own
    `schedule.business_frequency`, resolved BY NAME (B1, gate G6); unchanged
    when it is not published, and the screen then keeps the day count."""
    normalise = _published(_METER_READS, "business_frequency", kind="schedule")
    if normalise is None or stored is None:
        return stored
    try:
        return normalise(str(stored))
    except Exception:  # noqa: BLE001 — a word nobody can read is left as it was
        return stored


def _check_after_today(check: ScopeCheck, end: date) -> None:
    """Today is the TENANT's (BR-TEN-081), read through tenancy — billing reads
    no clock (BR-TEN-043, gate G6)."""
    try:
        today = _ask("tenancy", "tenant_today")
    except (errors.NotFoundError, _NotAnswering):
        return
    if today is not None and end > today:
        check.add("period_after_today", FIELD_PERIOD_END, today=today.isoformat())


def _check_numbering(check: ScopeCheck) -> None:
    """No `bill_run` series row → the run is created unnumbered (OQ-342) — a
    WARNING, decided 2026-09-30."""
    from core import numbering as core_numbering

    try:
        _ask("tenancy", "number_series_row", core_numbering.BILL_RUN)
    except errors.NotFoundError:
        check.add("no_run_number_series", None)
    except _NotAnswering:
        return


def _check_counts(check: ScopeCheck, cycle_id: str) -> dict[str, Any] | None:
    """Row 15 — the cycle's counts, and the three refusals and two warnings that
    come from them. Every figure is a COUNT; nothing is priced.

    ⚠ A module that does not answer leaves its figures NULL, never zero — a
    zero would claim the cycle has nothing, and the refusal already names who
    did not answer.
    """
    counts: dict[str, Any] = {
        "units_in_cycle": None,
        "accounts_to_bill": None,
        "regular_accounts": None,
        "master_accounts": None,
        "meters": None,
        "sub_meters": None,
        "behind_the_meter": None,
        "missing_meter": None,
        "units_nobody_to_bill": None,
    }
    try:
        units = [str(unit_id) for unit_id in _ask(_METER_READS, "units_in_cycle", cycle_id) or ()]
    except (_NotAnswering, errors.NotFoundError):
        check.add("meter_reads_not_answering", None)
        return counts
    counts["units_in_cycle"] = len(units)
    if not units:
        check.add("cycle_no_units", FIELD_CYCLE)

    # Accounts, and which units they reach (DEF-572 / DEF-2960: a master bills
    # its common areas AND its premises' empty units — the same union
    # `runs._prepare_run` uses, so Scope and Check cannot disagree).
    billed_units: set[str] = set()
    customers_ok = True
    try:
        accounts, billed_units, _by_unit = _population(units)
    except _NotAnswering:
        customers_ok = False
        check.add("customers_not_answering", None)
    except Exception:  # noqa: BLE001 — the queryset failed while being read
        logger.exception("run scope: customers population could not be read")
        customers_ok = False
        check.add("customers_not_answering", None)
    if customers_ok:
        masters = sum(
            1 for account in accounts if str(getattr(account, "kind", "") or "") == gather.ACCOUNT_KIND_MASTER
        )
        counts["accounts_to_bill"] = len(accounts)
        counts["master_accounts"] = masters
        counts["regular_accounts"] = len(accounts) - masters
        nobody = [unit_id for unit_id in units if unit_id not in billed_units]
        counts["units_nobody_to_bill"] = len(nobody)
        if units and not accounts:
            check.add("cycle_no_accounts", FIELD_CYCLE)
        if nobody:
            check.add("units_nobody_to_bill", None, count=len(nobody))

    # Meters, sub-meters, behind the meter, and points with no meter (DEF-BIL-5297).
    try:
        assets_by_unit = _ask("assets", "assets_on_units", units, answering_as=_METER_READS) or {}
        unmetered = _points_with_no_meter(units)
    except (_NotAnswering, errors.NotFoundError):
        if "meter_reads_not_answering" not in check.codes():
            check.add("meter_reads_not_answering", None)
        return counts
    by_tab = {"meters": 0, "sub_meters": 0, "behind_the_meter": 0}
    for rows in assets_by_unit.values():
        for row in rows:
            tab = row.get("tab")
            if tab in by_tab:
                by_tab[tab] += 1
    counts["meters"] = by_tab["meters"]
    counts["sub_meters"] = by_tab["sub_meters"]
    counts["behind_the_meter"] = by_tab["behind_the_meter"]
    missing = len(unmetered)
    counts["missing_meter"] = missing
    if missing:
        check.add("services_no_meter", None, count=missing)
    return counts


def _population(units: list[str]) -> tuple[list[Any], set[str], dict[str, Any]]:
    """The accounts a run over these units bills, the units they reach, and the
    anchor account of each unit — ONE derivation for the counts and the panel.

    DEF-572 / DEF-2960: a master bills its common areas AND its premises' empty
    units — the same union `runs._prepare_run` uses, so Scope and Check cannot
    disagree. Raises `_NotAnswering` when customers does not answer.
    """
    billed_units: set[str] = set()
    by_unit: dict[str, Any] = {}
    population = _ask(_CUSTOMERS, "accounts_for_bill_run", units)
    with transaction.atomic():
        accounts = list(population) if units else []
        for account in accounts:
            if account.unit_id:
                by_unit.setdefault(str(account.unit_id), account)
            try:
                billed_units.update(gather.covered_units(account))
                billed_units.update(
                    str(entry.get("unit_id"))
                    for entry in gather.base_charge_only_units(account)
                    if entry.get("unit_id")
                )
            except gather.GatherProblem:
                # Found again, and named, at Check. Its anchor still counts
                # so a blocked account does not also raise a phantom unit.
                if account.unit_id:
                    billed_units.add(str(account.unit_id))
    return accounts, billed_units, by_unit


def _points_with_no_meter(units: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """`[(unit_id, service point)]` — every connected METERED service with no
    meter in service on it (DEF-BIL-5297). ONE derivation for the count and the
    panel. Raises `_NotAnswering` / `NotFoundError` like `_ask`."""
    points_by_unit = _ask(_METER_READS, "service_points_for_units", units) or {}
    metered = set(_ask("assets", "metered_service_codes", answering_as=_METER_READS) or ())
    metered_points = [
        (unit_id, point)
        for unit_id, points in points_by_unit.items()
        for point in points
        if point.get("service") in metered
    ]
    meters_on = (
        _ask(
            "assets",
            "in_service_meter_counts_for_points",
            [point["id"] for _unit, point in metered_points],
            answering_as=_METER_READS,
        )
        or {}
    )
    return [(unit_id, point) for unit_id, point in metered_points if not meters_on.get(str(point["id"]))]


# ── The two Scope panels' rows (DEF-BIL-8221) ───────────────────────────────

#: `GET /billing/runs/scope-list?list=` — the rows behind two of Scope's counts.
LIST_NOBODY = "nobody"
LIST_MISSING_METER = "missing_meter"
SCOPE_LISTS = (LIST_NOBODY, LIST_MISSING_METER)


def scope_list(cycle_id: Any, which: str, *, page: int, per: int) -> dict[str, Any]:
    """The units behind *Nobody to bill* or the services behind *Missing
    meter*, PAGED (NFR-3), in address order — the same derivations the counts
    use (`_population`, `_points_with_no_meter`), so a panel cannot list a row
    its count did not count, or miss one it did.

    Rows name the address and the unit's label, never an id as the visible
    value (B14 rule 31); `unit_id` rides along for the two new-tab links.
    A *Nobody to bill* row carries the unit's connected services and its last
    finished account (number and move-out day) where there is one; a *Missing
    meter* row carries the service and the unit's account number.

    Raises `_NotAnswering` when a module does not answer — the view turns that
    into the same *module not answering* refusal the preview gives.
    """
    units = [str(unit_id) for unit_id in _ask(_METER_READS, "units_in_cycle", cycle_id) or ()]
    if which == LIST_NOBODY:
        _accounts, billed_units, _by_unit = _population(units)
        items: list[tuple[str, dict[str, Any] | None]] = [
            (unit_id, None) for unit_id in units if unit_id not in billed_units
        ]
    else:
        items = list(_points_with_no_meter(units))
        _accounts, _billed, by_unit = _population(units) if items else ([], set(), {})
    refs = _ask(_METER_READS, "unit_refs", sorted({unit_id for unit_id, _p in items})) or {}

    def order(item: tuple[str, dict[str, Any] | None]) -> tuple[str, str, str]:
        ref = refs.get(item[0]) or {}
        return (
            str(ref.get("premise_address") or ""),
            str(ref.get("label") or ""),
            str((item[1] or {}).get("service") or ""),
        )

    items.sort(key=order)
    total = len(items)
    page = max(1, page)
    window = items[(page - 1) * per : page * per]
    points = (
        _ask(_METER_READS, "service_points_for_units", [unit_id for unit_id, _p in window]) or {}
        if which == LIST_NOBODY
        else {}
    )
    rows: list[dict[str, Any]] = []
    for unit_id, point in window:
        ref = refs.get(unit_id) or {}
        row: dict[str, Any] = {
            "unit_id": unit_id,
            "address": ref.get("premise_address"),
            "unit": ref.get("label"),
        }
        if which == LIST_NOBODY:
            row["services"] = sorted(
                {str(p.get("service")) for p in points.get(unit_id, []) if p.get("service")}
            )
            last = _ask(_CUSTOMERS, "last_closed_account_for_unit", unit_id)
            row["last_account"] = (
                None
                if last is None
                else {
                    "account_no": last.account_no,
                    # Record links (PO 2026-10-19): the number opens the account.
                    "account_id": str(last.pk),
                    "moved_out": last.closed_at.isoformat() if last.closed_at else None,
                }
            )
        else:
            account = by_unit.get(unit_id)
            row["service"] = (point or {}).get("service")
            row["account_no"] = None if account is None else account.account_no
            row["account_id"] = None if account is None else str(account.pk)
        rows.append(row)
    return {"rows": rows, "page": page, "per": per, "total": total, "pages": max(1, -(-total // per))}


def run_templates(*, page: int, per: int) -> dict[str, Any]:
    """The bill templates a run may be started on — this tenant's BILL
    templates that have a PUBLISHED version, each with that version's number,
    by name, PAGED (DEF-BIL-8222, NFR-3). The same test `_check_template`
    applies, so the select cannot offer a template Start would refuse; a
    template with no published version is simply absent here and still refused
    by name if its id is sent (*must be published*)."""
    from apps.billing.template_models import TYPE_BILL, VERSION_PUBLISHED, BillTemplateVersion

    tenant_id = core_tenancy.current_tenant_id()
    versions = (
        BillTemplateVersion.objects.filter(
            tenant_id=tenant_id,
            status=VERSION_PUBLISHED,
            template__template_type=TYPE_BILL,
        )
        .select_related("template")
        .order_by("template__name", "template_id")
    )
    total = versions.count()
    page = max(1, page)
    window = versions[(page - 1) * per : page * per]
    rows = [
        {
            "id": str(version.template_id),
            "name": version.template.name,
            "version_no": version.version_no,
            "category": version.template.category,
        }
        for version in window
    ]
    return {"rows": rows, "page": page, "per": per, "total": total, "pages": max(1, -(-total // per))}


# ── Cycle details and previous runs (B6) ────────────────────────────────────


def cycle_details(check: ScopeCheck) -> dict[str, Any] | None:
    """Row 31 — the chosen cycle's own facts, from metering's read, plus the two
    only billing knows (first run date falls back to the cycle's own; runs so
    far counts the cycle's real runs, abandoned ones excluded)."""
    cycle = check.cycle
    if cycle is None:
        return None
    runs_so_far = _cycle_runs(cycle["id"]).exclude(status__in=IGNORED_FOR_CONTINUITY).count()
    return {
        "id": cycle["id"],
        "code": cycle.get("code"),
        "name": cycle.get("name"),
        "frequency": cycle.get("frequency"),
        "reads_start_day": cycle.get("start_day"),
        "days_to_complete": cycle.get("days_to_complete"),
        "bill_day": cycle.get("bill_day"),
        "due_days": cycle.get("due_days"),
        "routes": len(cycle.get("route_ids") or ()),
        "first_run_date": cycle.get("first_run_date"),
        "runs_so_far": runs_so_far,
        "status": cycle.get("lifecycle_status"),
    }


def preview(check: ScopeCheck) -> dict[str, Any]:
    """`GET /billing/runs/scope-preview`'s body, less the paged previous runs
    (the view pages those through the one run-list read, `bill_runs_page`)."""
    return {
        "refusals": [problem.as_dict() for problem in check.refusals],
        "warnings": [problem.as_dict() for problem in check.warnings],
        "can_start": check.ok,
        "counts": check.counts,
        "last_run_counts": check.last_run_counts,
        "continuity": check.continuity,
        "previous_run": check.previous_run,
        "cycle": cycle_details(check),
    }

# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (Check — saved results; findings by category → tag)
# Ruling:   OQ-843 RE-RULED 2026-09-30, option C (see check_models.py)
# Plan:     15-bulk-bill-run-build-plan.md B9, B15, A4 · DB1
# Tests:    06-backend/tests/test_bbr_check_store.py
# ───────────────────────────────────────────────────────
"""Run the Check and SAVE it; read the saved results back, grouped and paged.

WRITE SIDE — `check_run(run, only_accounts=None, …)` runs the ONE per-account
pass (`selectors.prepared_for` → `runs.prepare_run` → `check_engine`) and saves
each account's result the moment it is checked, inside that account's own
savepoint, so a pass killed at account 9,000 has saved 9,000. A full pass
deletes the rows of accounts it no longer found in scope; a partial pass
(B15, re-check named accounts) touches only the accounts it names.

READ SIDE — every read is a query over the saved rows, PAGINATED (NFR-3), and
never re-runs the pass: that is what option C bought, and the reason is the
measured cost (137 ms an account; ~90 minutes at 40,000). What keeps a saved
row honest is `check_staleness`, which re-checks an account the moment its
plan, reading, meter or payment changes, and `stale` on every row served.

THE FOUR STATUSES (PO 2026-09-30, *"THE FOUR KINDS OF PROBLEM"*) are computed
at READ time from the saved severities and the answers given SINCE the check —
an answer is a decision, not a change to the account, so it must not need a
re-check to show: *"An account is Ready when every problem on it is a warning
or has an accepted decision; one blocked problem sends it to Not in this run."*
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, Max, Min, Q

from apps.billing import check_engine, check_models, check_taxonomy, decisions, runs
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

logger = logging.getLogger("smartbillhub.billing")

#: Where a saved-results store would once have had to plug in — kept as the
#: single write seam so a different store (a partitioned table at T4) is one
#: function, not a hunt.
STORE_SEAM = "apps.billing.check_store.save_account_check"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


# ── locked at Send (PO ruling 2026-09-30, option A) ─────────────────────────
def run_is_sent(run: Any) -> bool:
    """Has this run been SENT — does a release row for it carry `released_at`?

    The moment the run's check record stops changing: decisions and standing
    answers explain the money on bills that went out, the account checks are
    the run's final Check report, and each account's findings are its final
    version. Kept as long as the bills; nothing deletes them (by ruling).
    """
    from apps.billing import models

    return models.BillRunRelease.objects.filter(
        tenant_id=_tenant_id(), bill_run=run, released_at__isnull=False
    ).exists()


def refuse_if_sent(run: Any) -> None:
    """The Python half of `billing/0034`'s trigger: a sentence for the clerk,
    and the same refusal on a database with no triggers. A blocked or held
    account is billed by a CATCH-UP run, which checks afresh in its own
    record — never in its parent's."""
    if run_is_sent(run):
        raise BillingRuleError(
            f"bill run {getattr(run, 'pk', run)} is sent: its check record is locked "
            "(PO ruling 2026-09-30). Accounts it did not bill are checked again by "
            "their catch-up run.",
            message_key="billing.check.runSent",
        )


# ── write ───────────────────────────────────────────────────────────────────
def _saved_status(severities: list[str | None], quiet: bool) -> str:
    """The status `AccountCheck.check_status()` gives, from saved severities."""
    if check_taxonomy.BLOCKS in severities:
        return check_engine.STATUS_BLOCKED
    if quiet:
        return check_engine.STATUS_QUIET
    if check_taxonomy.DECISION in severities:
        return check_engine.STATUS_DECISION
    return check_engine.STATUS_READY


def _finding_rows(run: Any, row: Any, checked: check_engine.AccountCheck) -> list[Any]:
    tenant_id = _tenant_id()
    return [
        check_models.BillRunFinding(
            tenant_id=tenant_id,
            bill_run=run,
            account_check=row,
            account_id=checked.account_id,
            code=f.code,
            category=f.category,
            severity=f.severity,
            service_code=f.service_code,
            detail=f.clerk_detail or f.detail,
            message_key=f.message_key,
            params=dict(f.params or {}),
            support_ref=f.support_ref,
            check_step=f.step,
        )
        for f in checked.findings
    ]


def save_account_check(run: Any, checked: check_engine.AccountCheck, *, job_id: Any = None) -> None:
    """Replace ONE account's saved result with this pass's answer.

    A PARTIAL answer (`checked.rerun`, DEF-BIL-8286) replaces only the saved
    findings of the categories it re-ran, keeps every other category's, and
    re-derives the account's status from the merged set."""
    tenant_id = _tenant_id()
    with transaction.atomic():
        existing = check_models.BillRunAccountCheck.objects.filter(
            tenant_id=tenant_id, bill_run=run, account_id=checked.account_id
        ).first()
        if checked.rerun is not None and existing is not None:
            existing.findings.filter(check_step__in=sorted(checked.rerun)).delete()
            check_models.BillRunFinding.objects.bulk_create(_finding_rows(run, existing, checked))
            severities = list(existing.findings.values_list("severity", flat=True))
            quiet = (
                checked.quiet
                if check_engine.CATEGORY_SERVICES in checked.rerun
                else existing.status == check_engine.STATUS_QUIET
            )
            existing.status = _saved_status(severities, quiet)
            existing.covered_unit_ids = list(checked.covered_unit_ids)
            if check_engine.CATEGORY_SERVICES in checked.rerun:
                existing.plan_id = checked.plan_id
            existing.stale = False
            existing.job_id = job_id
            existing.save()
            _stamp_read_time(existing, checked)
            return
        if existing is not None:
            existing.delete()
        row = check_models.BillRunAccountCheck.objects.create(
            tenant_id=tenant_id,
            bill_run=run,
            account_id=checked.account_id,
            account_no=checked.account_no,
            unit_id=checked.unit_id,
            account_kind=checked.account_kind,
            status=checked.check_status(),
            covered_unit_ids=list(checked.covered_unit_ids),
            plan_id=checked.plan_id,
            stale=False,
            job_id=job_id,
        )
        check_models.BillRunFinding.objects.bulk_create(_finding_rows(run, row, checked))
        _stamp_read_time(row, checked)


def _stamp_read_time(row: Any, checked: check_engine.AccountCheck) -> None:
    """DEF-BIL-8491 — `checked_at` is WHEN THE INPUTS WERE READ, not when the
    row was saved.

    The staleness sweep re-checks an account for a change made AFTER its
    `checked_at`. A batch reads its accounts' payments (and, since B27, their
    readings, meters and prices) once, BEFORE its first account; stamping the
    save time left every change recorded between that read and the save in
    neither the result nor the sweep — reproduced on PostgreSQL by
    `bbr_check_cost.py race`: a $120.00 payment posted mid-batch, the account
    saved without *Paid after cut-off*, and the sweep said *not stale*.

    `auto_now` on the column overwrites any value handed to `save()`, so the
    read time is written by an UPDATE, which it does not intercept. One
    statement per account."""
    stamp = getattr(checked, "inputs_read_at", None)
    if stamp is None:
        return
    check_models.BillRunAccountCheck.objects.filter(pk=row.pk).update(checked_at=stamp)
    row.checked_at = stamp


def check_run(
    run: Any,
    *,
    only_accounts: Any = None,
    on_progress: Any = None,
    job_id: Any = None,
    resume_after: str | None = None,
    categories: Any = None,
) -> dict[str, Any]:
    """Check the run (or NAMED accounts of it) and save every account's result.

    Returns the counts. A `runs.UtilityWideStop` is recorded on the run
    (`findings_summary["stop"]` — what, who, support reference) and re-raised;
    the run itself is never touched otherwise (B21: *"the run is always kept"*).

    `categories` (DEF-BIL-8286) — with `only_accounts`, re-run only those
    categories of the Check and what is downstream of them, merged into each
    account's saved result. An account never saved, or saved before findings
    named their category (`billing/0035`), is checked IN FULL instead.
    """
    from apps.billing import selectors

    refuse_if_sent(run)
    if categories is not None and only_accounts is not None:
        wanted = sorted({str(one) for one in only_accounts})
        saved = dict(
            check_models.BillRunAccountCheck.objects.filter(
                tenant_id=_tenant_id(), bill_run=run, account_id__in=wanted
            ).values_list("account_id", "status")
        )
        saved = {str(k): v for k, v in saved.items()}
        legacy = {
            str(a)
            for a in check_models.BillRunFinding.objects.filter(
                tenant_id=_tenant_id(),
                bill_run=run,
                account_id__in=wanted,
                check_step__isnull=True,
            ).values_list("account_id", flat=True)
        }
        full = [a for a in wanted if a not in saved or a in legacy]
        partial = [a for a in wanted if a not in full]
        if full:
            check_run(run, only_accounts=full, on_progress=on_progress, job_id=job_id)
        if not partial:
            return _record_summary(run, job_id=job_id)
        quiet = [a for a in partial if saved.get(a) == check_engine.STATUS_QUIET]
        done = [0]

        def on_partial(checked: check_engine.AccountCheck) -> None:
            save_account_check(run, checked, job_id=job_id)
            done[0] += 1
            if on_progress is not None:
                on_progress(done[0], checked.account_no)

        try:
            selectors.prepared_for(
                run,
                only_accounts=partial,
                on_account=on_partial,
                check_categories=tuple(categories),
                quiet_account_ids=quiet,
            )
        except runs.UtilityWideStop as stop:
            _record_summary(run, stop=stop.as_dict(), job_id=job_id)
            raise
        return _record_summary(run, job_id=job_id)
    if only_accounts is None and getattr(run, "parent_run_id", None) is not None:
        # PO 2026-09-30: a CATCH-UP run does a FRESH check, of the accounts it
        # exists to bill — its parent's still-held set (US-BIL-006) — in its
        # own record, and never reuses the parent's findings.
        from apps.billing import pending

        only_accounts = sorted(pending.held_account_ids(run.parent_run))
    # B28 (2026-10-01) — ONE CODE PATH FOR EVERY SIZE. The pass is planned in
    # batches of 500 (`check_batches.plan`) and walked one batch after another
    # here, through the same `check_batch` a worker runs; the totals are
    # counted ONCE, after the last batch (`finalize_summary`). A Check job
    # runs the same batches side by side (`check_batches.start`).
    from apps.billing import check_batches

    whole = only_accounts is None
    done = [0]

    def on_account(checked: check_engine.AccountCheck) -> None:
        save_account_check(run, checked, job_id=job_id)
        done[0] += 1
        if on_progress is not None:
            on_progress(done[0], checked.account_no)

    skip = None
    if resume_after:
        # A pass resumed after the last account it SAVED (accounts stream in
        # account_no order, `runs._account_stream`).
        def skip(_account_id: Any, account_no: Any) -> bool:
            return str(account_no) <= resume_after

    unavailable: list[dict[str, Any]] = []
    try:
        planned = check_batches.plan(run, only_accounts)
        for batch in planned["batches"] or [dict(check_batches.EMPTY_BATCH)]:
            prepared = check_batches.check_batch(
                run, batch, on_account=on_account, resume_skip=skip
            )
            unavailable.extend(check_batches.unavailable_of(prepared))
        return check_batches.finalize_summary(
            run, job_id=job_id, whole=whole, unavailable=unavailable
        )
    except runs.UtilityWideStop as stop:
        _record_summary(run, stop=stop.as_dict(), job_id=job_id)
        raise


def _record_summary(
    run: Any, *, stop: dict | None = None, job_id: Any = None, extra: dict | None = None
) -> dict[str, Any]:
    """`bill_runs.findings_summary` — the COUNTS, plus a utility-wide stop."""
    summary = dict(run.findings_summary or {})
    summary.update(counts(run))
    summary["job_id"] = None if job_id is None else str(job_id)
    summary["stop"] = stop
    if extra:
        summary.update(extra)
    run.findings_summary = summary
    run.save(update_fields=["findings_summary", "updated_at"])
    return summary


# ── read ────────────────────────────────────────────────────────────────────
def _inline_fix(code: str, params: dict[str, Any] | None = None) -> str | None:
    """The inline fix the Check can make for this tag or row (`check_fixes`),
    or None — the screen shows the fix control only where one exists
    (DEF-BIL-8218). A row's params decide it where the code is generic."""
    from apps.billing import check_fixes

    return check_fixes.fix_for(code, params)


def _row_choices(code: str, params: dict[str, Any] | None = None) -> list[str]:
    """The answers ONE row may take (DEF-BIL-8472). The tag's own list, except
    where the row's saved facts narrow it: a continuity row answers by its
    state — an overlap offers Investigate only (PO 2026-09-30 case 4), so the
    screen never offers an answer `record_decision` refuses."""
    state = (params or {}).get("state")
    if code == "billing_continuity" and state in decisions.CONTINUITY_CHOICES_BY_STATE:
        return list(decisions.CONTINUITY_CHOICES_BY_STATE[state])
    return list(decisions.CHOICES_BY_CASE.get(code, ()))


def _answered_cases(run: Any, account_ids: list[str] | None = None) -> tuple[dict, dict]:
    """`({account_id: {case: choice}}, {case: choice})` — each account's own
    live answers, and the run's standing answers AS CALCULATE TAKES THEM.

    DEF-BIL-8554: a standing *Estimate* is not an answer for any account — an
    estimate is a quantity with its unit, typed per account (BR-BIL-015,
    CLAUDE.md rule 3), and `decisions.apply_decisions` skips it for exactly that
    reason. Until 2026-09-30 the Check counted it as answered, so the account
    read Ready, *Price N* counted it, and Calculate held it: the account the
    server held itself on the accuracy walk. The tag still shows its *Answer
    for all* (`findings_summary` reads the standing answers directly)."""
    rows = decisions.current_decisions(run)
    own: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        if account_ids is None or str(row.account_id) in account_ids:
            own[str(row.account_id)][row.case] = row.choice
    standing = {
        case: choice
        for case, choice in decisions.standing_answers(run).items()
        if choice != decisions.CHOICE_ESTIMATE
    }
    return own, standing


def _effective_answers(
    findings: list[tuple[str, str | None, dict[str, Any]]],
    own: dict[str, str],
    standing: dict[str, str],
    payment_not_arrived: bool = False,
) -> dict[str, str]:
    """`{case: choice}` — ONE account's answers as `apply_decisions` takes
    them: its own rows, and the tag's standing answer for a decision it raised
    and did not answer itself, except where the row's saved facts refuse that
    answer (an overlap takes Investigate only, DEF-BIL-8473; *Apply to this
    bill* on a payment that has not arrived, DEF-BIL-8651)."""
    out = dict(own)
    if payment_not_arrived and out.get("paid_after_cutoff") == decisions.CHOICE_APPLY_THIS_BILL:
        out.pop("paid_after_cutoff")
    for code, severity, params in findings:
        if severity != check_taxonomy.DECISION:
            continue
        # 🔒 DEF-BIL-10200 — a late fee nobody answered BILLS (decision log
        # 2026-10-17); `decisions.DEFAULT_ANSWERS` is the one statement of it.
        choice = own.get(code) or standing.get(code) or decisions.DEFAULT_ANSWERS.get(code)
        if choice is None:
            continue
        if code == "billing_continuity" and choice not in _row_choices(code, params):
            out.pop(code, None)
            continue
        if (
            payment_not_arrived
            and code == "paid_after_cutoff"
            and choice == decisions.CHOICE_APPLY_THIS_BILL
        ):
            out.pop(code, None)
            continue
        out[code] = choice
    return out


#: The cases Calculate will not price unanswered: the Check's own must-answer
#: cases (`decisions.MUST_ANSWER_CASES`, held by `apply_decisions`) and a
#: missing read, which `runs` refuses at calculate as
#: `missing_read_undecided_at_calculate` (BR-BIL-015: estimate, hold or bill
#: without it — billing the rest would take the third one silently).
CALCULATE_MUST_ANSWER: frozenset[str] = decisions.MUST_ANSWER_CASES | {"missing_read"}

#: What Calculate will do with an account the Check let through — the
#: partition `decisions.apply_decisions` makes, read from the saved Check.
PRICED = "priced"
HELD = "held"
WAIVED = "waived"
UNDECIDED = "undecided"


def _partition_one(
    findings: list[tuple[str, str | None, dict[str, Any]]], answers: dict[str, str]
) -> str:
    """🔒 mirrors `decisions.apply_decisions` (DEF-BIL-8554): a MUST-ANSWER
    case raised and unanswered holds the account out (an overlap's continuity
    is must-answer, DEF-BIL-8473); a waiver bills nothing (PO case 2); any
    holding answer holds; everything else is priced. Change the two together."""
    raised = {code for code, severity, _p in findings if severity == check_taxonomy.DECISION}
    overlap = any(
        code == "billing_continuity" and (params or {}).get("state") == runs.CONTINUITY_OVERLAP
        for code, _s, params in findings
    )
    must = (raised & CALCULATE_MUST_ANSWER) | ({"billing_continuity"} if overlap else set())
    held = any((case, choice) in decisions.HOLDING_CHOICES for case, choice in answers.items())
    if must - set(answers) and not held:
        return UNDECIDED
    if answers.get("base_only_billing") == decisions.CHOICE_WAIVE and not held:
        return WAIVED
    return HELD if held else PRICED


def unbilled(queryset: Any, run: Any) -> Any:
    """`queryset` (a run's saved check rows or findings) without the accounts
    this run holds a bill for — any bill, a void one included, which is exactly
    the set Not in this run skips (`not_in_run.rows_for`). An anti-join in SQL
    (`DEF-BIL-8809`): on a sent 40,008-bill run it leaves a handful of rows
    where the read used to decide 40,015 accounts' statuses in Python only to
    skip 40,008 of them."""
    from apps.billing import models as billing_models

    return queryset.exclude(
        account_id__in=billing_models.Invoice.objects.filter(
            tenant_id=_tenant_id(), bill_run=run
        ).values("account_id")
    )


def _saved_facts(run: Any, *, unbilled_only: bool = False) -> tuple[dict, dict, dict, dict]:
    """`(findings by account, own answers, standing answers, saved status)` —
    the one read the statuses and the pricing partition share. `unbilled_only`
    reads only the accounts the run holds no bill for (`unbilled`)."""
    tenant_id = _tenant_id()
    findings = check_models.BillRunFinding.objects.filter(tenant_id=tenant_id, bill_run=run)
    checks = check_models.BillRunAccountCheck.objects.filter(tenant_id=tenant_id, bill_run=run)
    if unbilled_only:
        findings, checks = unbilled(findings, run), unbilled(checks, run)
    by_account: dict[str, list[tuple[str, str | None, dict[str, Any]]]] = defaultdict(list)
    for account_id, code, severity, params in findings.values_list(
        "account_id", "code", "severity", "params"
    ):
        by_account[str(account_id)].append((code, severity, params or {}))
    own, standing = _answered_cases(run)
    saved = {
        str(account_id): status
        for account_id, status in checks.values_list("account_id", "status")
    }
    return by_account, own, standing, saved


def unbilled_statuses_and_partition(run: Any) -> tuple[dict[str, str], dict[str, str]]:
    """`(account_statuses, pricing_partition)` for ONLY the accounts this run
    holds no bill for, from ONE read of the saved facts (`DEF-BIL-8809`) —
    each value exactly what `account_statuses(run)` and `pricing_partition(run)`
    answer for that account. Not in this run reads nothing else."""
    by_account, own, standing, saved = _saved_facts(run, unbilled_only=True)
    # Asked on the RUN's findings, not only these accounts', exactly as the
    # whole-run read asks it (`_not_arrived`): an account's own *Apply to this
    # bill* is dropped whenever the run raised *Paid after cut-off* anywhere.
    raised_anywhere = check_models.BillRunFinding.objects.filter(
        tenant_id=_tenant_id(), bill_run=run, code="paid_after_cutoff"
    ).exists()
    not_arrived = decisions.accounts_paid_but_not_arrived(run) if raised_anywhere else set()
    statuses: dict[str, str] = {}
    partition: dict[str, str] = {}
    for key, saved_status in saved.items():
        findings = by_account.get(key, [])
        mine = own.get(key, {})
        answers = _effective_answers(findings, mine, standing, key in not_arrived)
        status = _status(
            [(c, s) for c, s, _p in findings], saved_status, set(answers), _is_left_out(mine)
        )
        statuses[key] = status
        if status in (check_engine.STATUS_READY, check_engine.STATUS_DECISION):
            partition[key] = _partition_one(findings, answers)
    return statuses, partition


def pricing_partition(run: Any) -> dict[str, str]:
    """`{account_id: priced | held | waived | undecided}` for every account
    the Check lets through to Calculate (not blocked, not left out, not
    nothing-to-bill) — what *Price N* counts and what Sign off adds up to."""
    by_account, own, standing, saved = _saved_facts(run)
    not_arrived = _not_arrived(by_account, run)
    out: dict[str, str] = {}
    for key, saved_status in saved.items():
        findings = by_account.get(key, [])
        mine = own.get(key, {})
        answers = _effective_answers(findings, mine, standing, key in not_arrived)
        status = _status(
            [(c, s) for c, s, _p in findings], saved_status, set(answers), _is_left_out(mine)
        )
        if status in (check_engine.STATUS_READY, check_engine.STATUS_DECISION):
            out[key] = _partition_one(findings, answers)
    return out


def _status(
    severities: list[tuple[str, str | None]],
    saved: str,
    answered: set[str],
    left_out: bool = False,
) -> str:
    if any(sev == check_taxonomy.BLOCKS for _code, sev in severities):
        return check_engine.STATUS_BLOCKED
    if saved == check_engine.STATUS_QUIET:
        return check_engine.STATUS_QUIET
    # DEF-BIL-10200 — a decision the run answers by itself when nobody does
    # (`decisions.DEFAULT_ANSWERS`: a late fee bills) never holds an account.
    answered = set(answered) | set(decisions.DEFAULT_ANSWERS)
    if any(sev == check_taxonomy.DECISION and code not in answered for code, sev in severities):
        return check_engine.STATUS_DECISION
    # BR-BIL-1054 — only a READY account can be left out, so it is the last
    # word: a left-out account that later needs a decision shows that instead.
    return check_engine.STATUS_LEFT_OUT if left_out else check_engine.STATUS_READY


def _not_arrived(by_account: dict[str, list], run: Any) -> set[str]:
    """DEF-BIL-8651 — asked only when the run raised *Paid after cut-off*."""
    if not any(code == "paid_after_cutoff" for rows in by_account.values() for code, _s, _p in rows):
        return set()
    return decisions.accounts_paid_but_not_arrived(run)


def _is_left_out(own_answers: dict[str, str]) -> bool:
    return own_answers.get(decisions.CASE_LEFT_OUT) == decisions.CHOICE_LEAVE_OUT


def _account_statuses(run: Any) -> dict[str, str]:
    by_account, own, standing, saved = _saved_facts(run)
    not_arrived = _not_arrived(by_account, run)
    out: dict[str, str] = {}
    for key, saved_status in saved.items():
        findings = by_account.get(key, [])
        mine = own.get(key, {})
        answered = set(_effective_answers(findings, mine, standing, key in not_arrived))
        out[key] = _status(
            [(c, s) for c, s, _p in findings], saved_status, answered, _is_left_out(mine)
        )
    return out


def first_blocking(run: Any) -> tuple[dict[str, str], dict[str, int]]:
    """`({account_id: its FIRST blocking code}, {account_id: blocking count})`.

    FIRST in the Check's own order — the registry's category order (account
    before services before …), then the order saved within a category. A
    finding's id is a uuid7 and cannot order two rows saved in one bulk
    insert, so it never decides this on its own."""
    rank = {c.name: i for i, c in enumerate(check_engine.REGISTRY)}
    rows = sorted(
        check_models.BillRunFinding.objects.filter(
            tenant_id=_tenant_id(), bill_run=run, severity=check_taxonomy.BLOCKS
        ).values_list("account_id", "code", "check_step", "checked_at", "id"),
        key=lambda r: (str(r[0]), rank.get(r[2] or "", len(rank)), r[3], str(r[4])),
    )
    first: dict[str, str] = {}
    count: dict[str, int] = {}
    for account_id, code, _step, _at, _id in rows:
        first.setdefault(str(account_id), code)
        count[str(account_id)] = count.get(str(account_id), 0) + 1
    return first, count


def account_statuses(run: Any) -> dict[str, str]:
    """`{account_id: ready | decision | blocked | quiet | left_out}` for every
    saved account of the run, answers included — the one place those five are
    decided, for Sign off, Not in this run and the queue at Send."""
    return _account_statuses(run)


def counts(run: Any) -> dict[str, Any]:
    """The five tiles and the checked-at range, from the saved rows."""
    statuses = _account_statuses(run)
    tally = defaultdict(int)
    for status in statuses.values():
        tally[status] += 1
    agg = check_models.BillRunAccountCheck.objects.filter(
        tenant_id=_tenant_id(), bill_run=run
    ).aggregate(
        first=Min("checked_at"), last=Max("checked_at"), stale=Count("id", filter=Q(stale=True))
    )
    warnings = (
        check_models.BillRunFinding.objects.filter(
            tenant_id=_tenant_id(), bill_run=run, severity=check_taxonomy.WARNING
        )
        .values("account_id")
        .distinct()
        .count()
    )
    problem_types = (
        check_models.BillRunFinding.objects.filter(tenant_id=_tenant_id(), bill_run=run)
        .exclude(severity__isnull=True)
        .values("code")
        .distinct()
        .count()
    )
    # DEF-BIL-8554 — *Price N* is the accounts Calculate will price, never
    # every Ready one: an answer that holds, a waiver and an unanswered
    # must-answer case each keep an account out of the drafts.
    partition = defaultdict(int)
    for outcome in pricing_partition(run).values():
        partition[outcome] += 1
    return {
        "accounts": len(statuses),
        "ready": tally[check_engine.STATUS_READY],
        "to_price": partition[PRICED],
        "held": partition[HELD],
        "waived": partition[WAIVED],
        "undecided": partition[UNDECIDED],
        "decisions": tally[check_engine.STATUS_DECISION],
        "blocked": tally[check_engine.STATUS_BLOCKED],
        "silent": tally[check_engine.STATUS_QUIET],
        "left_out": tally[check_engine.STATUS_LEFT_OUT],
        "warnings": warnings,
        "problem_types": problem_types,
        "stale": agg["stale"] or 0,
        "checked_from": agg["first"].isoformat() if agg["first"] else None,
        "checked_at": agg["last"].isoformat() if agg["last"] else None,
    }


# ── BR-BIL-1040 (amended 2026-09-30) · what *Answer for all N* opens on ─────
def opening_answers(run: Any = None) -> dict[str, str]:
    """`{case: choice}` — the S66 Billing defaults for the tags that have one
    (`settings_seam.RUN_CASE_DEFAULT_KEYS`: no reading, a bill that looks
    unusually large, unusual days). The RUN's own copy first
    (`bill_runs.case_defaults`, resolved from S66 when the run was created —
    BR-BIL-1040: a tenant editing Settings mid-run must not change a run in
    flight), then the tenant's current values. Empty when neither can be read:
    the tags then open on their first choice, as a tag with no S66 setting
    always does — never on a guessed default (DEF-BIL-8418)."""
    from apps.billing import settings_seam

    stored = getattr(run, "case_defaults", None) if run is not None else None
    if isinstance(stored, dict) and stored:
        return {str(k): str(v) for k, v in stored.items() if v}
    try:
        return settings_seam.run_case_defaults()
    except (BillingConfigError, BillingRuleError):
        logger.warning("billing defaults unreadable; Check tags open on their first choice")
        return {}


def default_choice(code: str, opening: dict[str, str] | None = None) -> str | None:
    """The answer ONE tag's *Answer for all N* opens on: its S66 default when
    the tenant has one and the tag offers it, otherwise the tag's first choice
    (BR-BIL-1040: *"a tag with no S66 setting opens on its first choice as
    drawn"*)."""
    offered = decisions.CHOICES_BY_CASE.get(code) or ()
    chosen = (opening or {}).get(code)
    if chosen in offered:
        return chosen
    return offered[0] if offered else None


def store_opening_answers(run: Any) -> list[str]:
    """DEF-BIL-8418 — BR-BIL-1040: the S66 answers are STORED ON THE RUN, now
    written at Check. After a whole pass, each S66-keyed case that has never
    had a standing answer on this run gets the tenant's default, written as a
    system act (`decided_by` empty — the report reads it as the Billing
    defaults). A case a clerk has answered, or changed their mind about, is
    never touched: any row for the case, superseded or live, means the run
    already has its answer.

    ⚠ ONLY THE S66-KEYED CASES. Every other decision tag opens on its first
    choice ON SCREEN and stores nothing until a clerk applies it, because for
    the former automatic cases that first choice is *Accept the suggestion*,
    and storing it here would be the automatic fix the PO ruled out (changes
    row 45: *"the account stays under Need a decision until accepted"*). A
    stored *Estimate* is still no answer for any one account — each No-reading
    row takes its own figure (`_answered_cases`, DEF-BIL-8554). Returns the
    cases written."""
    tenant_id = _tenant_id()
    if getattr(run, "status", None) not in (None, "draft"):
        return []
    answered = set(
        check_models.BillRunStandingAnswer.objects.filter(
            tenant_id=tenant_id, bill_run=run
        ).values_list("case", flat=True)
    )
    written: list[str] = []
    for case, choice in sorted(opening_answers(run).items()):
        if case in answered or choice not in (decisions.CHOICES_BY_CASE.get(case) or ()):
            continue
        if (case, choice) in decisions.REASON_REQUIRED:
            continue
        try:
            decisions.set_standing_answer(bill_run=run, case=case, choice=choice, decided_by=None)
        except BillingRuleError:
            logger.warning("opening answer %s=%s refused for run %s", case, choice, run.pk)
            continue
        written.append(case)
    return written


def findings_summary(run: Any) -> dict[str, Any]:
    """A4's first read: tiles, and categories → tags with ACCOUNT counts."""
    tenant_id = _tenant_id()
    per_tag = dict(
        check_models.BillRunFinding.objects.filter(tenant_id=tenant_id, bill_run=run)
        .values_list("code")
        .annotate(n=Count("account_id", distinct=True))
    )
    standing = decisions.standing_answers(run)
    opening = opening_answers(run)
    categories = []
    for category in check_taxonomy.categories_payload():
        tags = []
        for tag in category["tags"]:
            code = tag["code"]
            tags.append(
                {
                    **tag,
                    "count": int(per_tag.get(code, 0)),
                    "choices": list(decisions.CHOICES_BY_CASE.get(code, ())),
                    "default_choice": default_choice(code, opening),
                    "answer_for_all": standing.get(code),
                    "fix_here": _inline_fix(code),
                }
            )
        categories.append(
            {
                **category,
                "tags": tags,
                "count": sum(t["count"] for t in tags),
            }
        )
    # Codes the engine raised that the map does not know — never dropped.
    unmapped = sorted(code for code in per_tag if code not in check_taxonomy.TAGS)
    summary = dict(run.findings_summary or {})
    return {
        "bill_run_id": str(run.pk),
        "checked": bool(per_tag) or bool(summary.get("accounts")),
        "tiles": counts(run),
        "categories": categories,
        "unmapped": unmapped,
        "stop": summary.get("stop"),
        "unavailable": summary.get("unavailable") or [],
        "units_with_nobody_to_bill": summary.get("units_with_nobody_to_bill"),
    }


def _page(request_params: dict[str, Any]) -> tuple[int, int]:
    per = clamp_page_size(request_params.get("per"))
    try:
        page = max(int(str(request_params.get("page"))), 1)
    except (TypeError, ValueError):
        page = 1
    return page, per


def tag_accounts(run: Any, code: str, params: dict[str, Any]) -> dict[str, Any]:
    """ONE tag's accounts, paginated and searchable (A4), each row carrying
    what was found, the suggestion, its answer and the account's OTHER tags."""
    tenant_id = _tenant_id()
    page, per = _page(params)
    rows = check_models.BillRunFinding.objects.filter(
        tenant_id=tenant_id, bill_run=run, code=code
    ).select_related("account_check")
    q = (params.get("q") or "").strip()
    if q:
        # `DEF-BIL-10709` (tester L3-07) — *Find account* matches the account
        # number OR the customer's name. The name is customers' column, so it
        # is asked through their published search (a lazy subquery, no round
        # trip); where it is unpublished the number alone still filters.
        from apps.billing import customers_seam

        by_name = customers_seam.account_ids_matching_search(q)
        match = Q(account_check__account_no__icontains=q)
        if by_name is not None:
            match |= Q(account_id__in=by_name)
        rows = rows.filter(match)
    rows = rows.order_by("account_check__account_no", "service_code", "id")
    total = rows.count()
    last = max((total + per - 1) // per, 1)
    page = min(page, last)
    chunk = list(rows[(page - 1) * per : page * per])
    ids = sorted({str(r.account_id) for r in chunk})
    others: dict[str, set[str]] = defaultdict(set)
    for account_id, other in (
        check_models.BillRunFinding.objects.filter(
            tenant_id=tenant_id, bill_run=run, account_id__in=ids
        )
        .exclude(code=code)
        .values_list("account_id", "code")
    ):
        others[str(account_id)].add(other)
    own, standing = _answered_cases(run, ids)
    shown = display_for(ids)
    quantities = _estimate_quantities(run, ids, code)
    basis = _basis_reader(run, code)
    meters = _meter_numbers(chunk)
    results = []
    for r in chunk:
        account_id = str(r.account_id)
        answer = own.get(account_id, {}).get(code)
        results.append(
            {
                "account_id": account_id,
                "account_no": r.account_check.account_no,
                **shown.get(account_id, {}),
                "unit_id": str(r.account_check.unit_id) if r.account_check.unit_id else None,
                "service_code": r.service_code,
                # DEF-BIL-8701 — the meter NUMBERS on this row's service, so the
                # cell reads "Water · W-10442" (D1 11-14); [] when none.
                "meters": _meters_on(meters, r),
                "detail": r.detail,
                "message_key": r.message_key,
                "params": r.params,
                "support_ref": r.support_ref,
                "also_has": sorted(others.get(account_id, ())),
                "fix_here": _inline_fix(code, r.params),
                "choices": _row_choices(code, r.params),
                "answer": answer or standing.get(code) or decisions.DEFAULT_ANSWERS.get(code),
                "answer_source": (
                    "account"
                    if answer
                    else "tag"
                    if code in standing
                    # DEF-BIL-10200 — the answer the run takes unasked (a late
                    # fee bills unless waived), named so the screen can say so.
                    else "default"
                    if code in decisions.DEFAULT_ANSWERS
                    else None
                ),
                # DEF-BIL-8551 — an estimate is a quantity with its unit: the
                # one recorded, and the account's own average month to start
                # the box from (metering's figure, DEF-2859; null = no history).
                "answer_quantity": quantities.get(account_id, (None, None))[0],
                "answer_unit": quantities.get(account_id, (None, None))[1],
                "basis": basis(account_id, r.service_code),
                "checked_at": r.account_check.checked_at.isoformat(),
                "stale": r.account_check.stale,
            }
        )
    tag = check_taxonomy.classify(code)
    out = {
        "tag": {
            **tag.as_dict(),
            "choices": list(decisions.CHOICES_BY_CASE.get(code, ())),
            "answer_for_all": standing.get(code),
            "fix_here": _inline_fix(code),
        },
        "results": results,
        "count": total,
        "page": page,
        "per": per,
    }
    if code == "late_fee":
        out["late_fees"] = late_fee_totals(run)
    return out


def late_fee_totals(run: Any) -> dict[str, Any]:
    """🔒 DEF-BIL-10200 — *"12 accounts · late fees $78.40"*: the late fees this
    run will ADD, over the WHOLE tag (never the page on screen — NFR-3), less
    the accounts a clerk waived. `{accounts, total, waived}`; `total` a
    decimal string at 2 places (display), the sum of each account's own
    finalized fee, so it foots to the bills. One read of the tag's figures and
    one of its answers."""
    tenant_id = _tenant_id()
    fees: dict[str, Decimal] = {}
    currencies: set[str] = set()
    for account_id, params in check_models.BillRunFinding.objects.filter(
        tenant_id=tenant_id, bill_run=run, code="late_fee"
    ).values_list("account_id", "params"):
        try:
            fees[str(account_id)] = Decimal(str((params or {}).get("amount")))
            currencies.add(str((params or {}).get("currency") or "USD"))
        except (ArithmeticError, TypeError, ValueError):
            continue
    own, _standing = _answered_cases(run, set(fees))  # type: ignore[arg-type]
    waived = {
        key for key in fees if own.get(key, {}).get("late_fee") == decisions.CHOICE_WAIVE
    }
    applied = [amount for key, amount in fees.items() if key not in waived]
    return {
        "accounts": len(applied),
        "total": str(sum(applied, Decimal("0")).quantize(Decimal("0.01"))),
        "waived": len(waived),
        # CHAR(3) (hard rule 2); None where the tag mixes currencies — a sum
        # across two currencies is not a number to print.
        "currency": currencies.pop() if len(currencies) == 1 else None,
    }


def _meter_numbers(chunk: list[Any]) -> dict[str, dict[str, list[str]]]:
    """DEF-BIL-8701 — the in-service meters' numbers for every unit on ONE
    page, asked of Meter Reads through billing's metering seam: two reads per
    page, never one per row (NFR-3)."""
    from apps.billing import metering_seam

    units = sorted({str(r.account_check.unit_id) for r in chunk if r.account_check.unit_id})
    return metering_seam.meter_numbers_for_units(units) if units else {}


def _meters_on(meters: dict[str, dict[str, list[str]]], row: Any) -> list[str]:
    """The numbers on THIS row's unit and service; [] for a row about the
    account as a whole (no service) or a service with no meter."""
    unit_id = row.account_check.unit_id
    if not unit_id or not row.service_code:
        return []
    return list(meters.get(str(unit_id), {}).get(row.service_code, ()))


def _estimate_quantities(run: Any, ids: list[str], code: str) -> dict[str, tuple]:
    """`{account_id: (quantity, unit)}` of each account's live ESTIMATE on
    this case — served with its unit or not at all (CLAUDE.md rule 3)."""
    out: dict[str, tuple] = {}
    for row in decisions.current_decisions(run):
        if (
            row.case == code
            and row.choice == decisions.CHOICE_ESTIMATE
            and str(row.account_id) in ids
            and row.amount is not None
            and row.unit
        ):
            out[str(row.account_id)] = (str(row.amount.normalize()), row.unit)
    return out


def _basis_reader(run: Any, code: str) -> Any:
    """What the estimate box starts from, for a No-reading row only: the
    account's own average month, asked of metering through the seam the
    exceptions read uses (`selectors._UsageBasisMemo`, one read per account per
    request — never a cache, OQ-843). Every other tag reads None."""
    if code != "missing_read":
        return lambda _account_id, _service_code: None
    from apps.billing import selectors

    memo = selectors._UsageBasisMemo(run.period_end)
    return memo.basis_for


def display_for(account_ids: list[str]) -> dict[str, dict[str, Any]]:
    """The words a row shows for each account — customer name, address and
    unit label — through customers' own BATCHED reads (three queries for a
    page, never one per row; DEF-2723's lesson). B14 rule 31: an id is never
    the visible value, so every list the Check serves carries these."""
    from apps.billing import gather

    ids = sorted({str(one) for one in account_ids if one})
    out: dict[str, dict[str, Any]] = {
        one: {"customer_name": None, "address": None, "unit_label": None} for one in ids
    }
    if not ids:
        return out
    names = gather._resolve("customers", "primary_contact_names_for")
    if names is not None:
        for account_id, name in (names(ids) or {}).items():
            if account_id in out:
                out[account_id]["customer_name"] = name
    queryset = gather._resolve("customers", "account_queryset")
    cells = gather._resolve("customers", "premise_cells_for")
    if queryset is not None and cells is not None:
        accounts = list(queryset().filter(pk__in=ids))
        for account_id, cell in (cells(accounts) or {}).items():
            if account_id in out:
                # DEF-BIL-8700 — the cell is (unit label, "street · unit label");
                # the street alone is the address, so the unit is shown once.
                label, place = cell
                suffix = f" · {label}" if label else ""
                if suffix and place and place.endswith(suffix):
                    place = place[: -len(suffix)]
                out[account_id]["address"], out[account_id]["unit_label"] = place, label
    return out


def _ready_facts(run: Any, rows: list[Any]) -> dict[str, dict[str, Any]]:
    """The Ready list's three drawn columns for one PAGE (DEF-BIL-8414, image
    21): the services the account's bill covers, the plan it priced on, and
    whether every reading was read (`all_read` false when the Check found a
    missing reading on it — the clerk's *Estimate* then priced it). Three
    batched reads for a page, never one per row (DEF-2723)."""
    from apps.billing import gather

    out: dict[str, dict[str, Any]] = {
        str(r.account_id): {"services": [], "plan_name": None, "all_read": True} for r in rows
    }
    if not rows:
        return out
    units_of = {
        str(r.account_id): [str(u) for u in (r.covered_unit_ids or ([r.unit_id] if r.unit_id else []))]
        for r in rows
    }
    points_for = gather._resolve("metering", "service_points_for_units")
    if points_for is not None:
        points = points_for(sorted({u for units in units_of.values() for u in units})) or {}
        for account_id, units in units_of.items():
            out[account_id]["services"] = sorted(
                {str(p.get("service")) for u in units for p in points.get(u, []) if p.get("service")}
            )
    plans = gather._resolve("rating", "plan_queryset")
    plan_ids = sorted({str(r.plan_id) for r in rows if r.plan_id})
    if plans is not None and plan_ids:
        names = dict((str(pk), name) for pk, name in plans().filter(pk__in=plan_ids).values_list("id", "name"))
        for r in rows:
            if r.plan_id:
                out[str(r.account_id)]["plan_name"] = names.get(str(r.plan_id))
    estimated = set(
        str(a)
        for a in check_models.BillRunFinding.objects.filter(
            tenant_id=_tenant_id(),
            bill_run=run,
            account_id__in=[r.account_id for r in rows],
            code="missing_read",
        ).values_list("account_id", flat=True)
    )
    for account_id in estimated:
        if account_id in out:
            out[account_id]["all_read"] = False
    return out


def ready_accounts(run: Any, params: dict[str, Any]) -> dict[str, Any]:
    """*Ready to bill* (changes row 41), paginated, searchable, Regular/Master.

    It carries the accounts a clerk LEFT OUT too (BR-BIL-1054), each with
    `left_out: true`, so *Put back* is on the same list the account left —
    and `left_out` counts them for the *N left out* pill. `kind=regular|master`
    filters on `accounts.kind` as saved at Check; `left_out=only` narrows to
    the left-out rows."""
    statuses = _account_statuses(run)
    wanted = {check_engine.STATUS_READY, check_engine.STATUS_LEFT_OUT}
    ids = [a for a, s in statuses.items() if s in wanted]
    left = {a for a, s in statuses.items() if s == check_engine.STATUS_LEFT_OUT}
    page, per = _page(params)
    rows = check_models.BillRunAccountCheck.objects.filter(tenant_id=_tenant_id(), bill_run=run)
    # `DEF-BIL-8694` — `statuses` names EVERY saved row, so the list is the
    # wanted ids or, the same rows, all but the others: whichever is SHORTER
    # is bound. At 40,008 ready accounts binding the wanted ids twice (count
    # and page) was ~2 s of Python before PostgreSQL saw the statement.
    others = [a for a, s in statuses.items() if s not in wanted]
    rows = (
        rows.filter(account_id__in=ids)
        if len(ids) <= len(others)
        else rows.exclude(account_id__in=others)
    )
    kind = str(params.get("kind") or "").strip()
    if kind in ("regular", "master"):
        rows = rows.filter(account_kind=kind)
    if str(params.get("left_out") or "") == "only":
        rows = rows.filter(account_id__in=sorted(left))
    q = (params.get("q") or "").strip()
    if q:
        rows = rows.filter(account_no__icontains=q)
    rows = rows.order_by("account_no", "id")
    total = rows.count()
    last = max((total + per - 1) // per, 1)
    page = min(page, last)
    chosen = list(rows[(page - 1) * per : page * per])
    shown = display_for([str(r.account_id) for r in chosen])
    facts = _ready_facts(run, chosen)
    return {
        "results": [
            {
                "account_id": str(r.account_id),
                "account_no": r.account_no,
                "account_kind": r.account_kind,
                "unit_id": str(r.unit_id) if r.unit_id else None,
                "plan_id": str(r.plan_id) if r.plan_id else None,
                "left_out": str(r.account_id) in left,
                **shown.get(str(r.account_id), {}),
                **facts.get(str(r.account_id), {}),
                "checked_at": r.checked_at.isoformat(),
                "stale": r.stale,
            }
            for r in chosen
        ],
        "count": total,
        "left_out": len(left),
        "page": page,
        "per": per,
    }


def leave_out(run: Any, account_id: str, *, decided_by: Any = None, reason: str | None = None):
    """BR-BIL-1054 — take a READY account out of this run (a decision row).
    Refused for any other status: a blocked account is already out, and one
    waiting on a decision is answered on its tag, not left out."""
    refuse_if_sent(run)
    from apps.billing import models as billing_models

    if billing_models.Invoice.objects.filter(
        tenant_id=_tenant_id(), bill_run=run, account_id=account_id
    ).exists():
        # Already priced: a draft exists and would be sent. Leaving it out is a
        # Check act, before Calculate — never a quiet way to drop a draft.
        raise BillingRuleError(
            f"account {account_id} already has a draft bill on this run.",
            message_key="billing.check.leaveOut.alreadyPriced",
            br_ref="BR-BIL-1054",
        )
    status = _account_statuses(run).get(str(account_id))
    if status != check_engine.STATUS_READY:
        raise BillingRuleError(
            f"account {account_id} is {status or 'not checked'} on this run; only a ready "
            "account can be left out (BR-BIL-1054).",
            message_key="billing.check.leaveOut.notReady",
            br_ref="BR-BIL-1054",
        )
    return decisions.record_decision(
        bill_run=run,
        account_id=str(account_id),
        case=decisions.CASE_LEFT_OUT,
        choice=decisions.CHOICE_LEAVE_OUT,
        reason=reason,
        decided_by=decided_by,
    )


def put_back(run: Any, account_id: str, *, decided_by: Any = None):
    """BR-BIL-1054 — undo Leave out: a NEW row supersedes it (append-only)."""
    refuse_if_sent(run)
    current = decisions.current_decision(run, str(account_id), decisions.CASE_LEFT_OUT)
    if current is None or current.choice != decisions.CHOICE_LEAVE_OUT:
        raise BillingRuleError(
            f"account {account_id} is not left out of this run.",
            message_key="billing.check.putBack.notLeftOut",
            br_ref="BR-BIL-1054",
        )
    return decisions.record_decision(
        bill_run=run,
        account_id=str(account_id),
        case=decisions.CASE_LEFT_OUT,
        choice=decisions.CHOICE_PUT_BACK,
        decided_by=decided_by,
    )


def account_findings(run: Any, account_id: str) -> dict[str, Any] | None:
    """The *Fix account* panel: EVERY problem on one account, with its answer."""
    row = check_models.BillRunAccountCheck.objects.filter(
        tenant_id=_tenant_id(), bill_run=run, account_id=account_id
    ).first()
    if row is None:
        return None
    own, standing = _answered_cases(run, [str(account_id)])
    mine = own.get(str(account_id), {})
    findings = [
        {
            "code": f.code,
            "category": f.category,
            "severity": f.severity,
            "service_code": f.service_code,
            "detail": f.detail,
            "message_key": f.message_key,
            "params": f.params,
            "support_ref": f.support_ref,
            "tag": check_taxonomy.classify(f.code).as_dict(),
            "choices": _row_choices(f.code, f.params),
            "fix_here": _inline_fix(f.code, f.params),
            "answer": mine.get(f.code) or standing.get(f.code),
        }
        for f in row.findings.order_by("id")
    ]
    answered = set(mine) | set(standing)
    return {
        "account_id": str(row.account_id),
        "account_no": row.account_no,
        "account_kind": row.account_kind,
        **display_for([str(row.account_id)]).get(str(row.account_id), {}),
        "status": _status(
            [(f["code"], f["severity"]) for f in findings], row.status, answered, _is_left_out(mine)
        ),
        "checked_at": row.checked_at.isoformat(),
        "stale": row.stale,
        "findings": findings,
    }


def check_report(run: Any, params: dict[str, Any]) -> dict[str, Any]:
    """The run's read-only CHECK REPORT (PO ruling 2026-09-30): the tiles, the
    categories and tags, and every checked account with its problems, PAGED
    (NFR-3) — exactly as saved. For a SENT run this is the record as at Send,
    because nothing can change it afterwards (`billing/0034`); for an open run
    it is the current saved check, and `sent` says which."""
    tenant_id = _tenant_id()
    page, per = _page(params)
    rows = check_models.BillRunAccountCheck.objects.filter(
        tenant_id=tenant_id, bill_run=run
    ).order_by("account_no", "account_id")
    status = str(params.get("status") or "")
    if status:
        rows = rows.filter(status=status)
    query = str(params.get("q") or "").strip()
    if query:
        rows = rows.filter(account_no__icontains=query)
    total = rows.count()
    chosen = list(rows[(page - 1) * per : page * per])
    by_check: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for f in check_models.BillRunFinding.objects.filter(
        tenant_id=tenant_id, account_check__in=chosen
    ).order_by("id"):
        by_check[f.account_check_id].append(
            {
                "code": f.code,
                "category": f.category,
                "severity": f.severity,
                "service_code": f.service_code,
                "message_key": f.message_key,
                "params": f.params,
                "support_ref": f.support_ref,
            }
        )
    summary = findings_summary(run)
    answered = _report_decisions(run, chosen, by_check)
    return {
        "bill_run_id": str(run.pk),
        "sent": run_is_sent(run),
        "tiles": summary["tiles"],
        "categories": summary["categories"],
        "accounts": {
            "results": [
                {
                    "account_id": str(r.account_id),
                    "account_no": r.account_no,
                    "status": r.status,
                    "checked_at": r.checked_at.isoformat(),
                    "problems": by_check.get(r.pk, []),
                    "decisions": answered.get(str(r.account_id), []),
                }
                for r in chosen
            ],
            "count": total,
            "page": page,
            "per": per,
        },
    }


def _person(user: Any) -> str | None:
    """A user as the words a reader sees, never an id (B14 rule 31)."""
    for attribute in ("full_name", "email", "username"):
        value = getattr(user, attribute, None) if user is not None else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _report_decisions(
    run: Any, chosen: list[Any], by_check: dict[Any, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """DEF-BIL-8555 · clerk check A6 — every answer a clerk gave, per account
    on the page: its own answers (who, when, the reason and an estimate's
    quantity), and the tag's *Answer for all* for each decision the account
    raised and did not answer itself, with the clerk who set it. The LIVE
    answers only — a changed mind is in the audit trail, not here."""
    from django.apps import apps as django_apps

    from apps.billing import models as billing_models

    # The FK's own target, by label — `bill_run_decisions.decided_by` points at
    # `identity.User`, which is not Django's auth user (no AUTH_USER_MODEL).
    user_model = django_apps.get_model("identity", "User")

    tenant_id = _tenant_id()
    ids = {str(r.account_id) for r in chosen}
    codes = {str(sid): code for code, sid in _service_ids().items()}
    out: dict[str, list[dict[str, Any]]] = {one: [] for one in ids}
    own_cases: dict[str, set[str]] = defaultdict(set)
    rows = (
        billing_models.BillRunDecision.objects.filter(
            tenant_id=tenant_id,
            bill_run=run,
            superseded_by__isnull=True,
            account_id__in=list(ids),
        )
        .select_related("decided_by")
        .order_by("account_id", "case", "created_at")
    )
    for row in rows:
        key = str(row.account_id)
        own_cases[key].add(row.case)
        measured = row.amount is not None and bool(row.unit)
        out[key].append(
            {
                "case": row.case,
                "choice": row.choice,
                "scope": "account",
                "reason": row.reason,
                "quantity": str(row.amount.normalize()) if measured else None,
                "unit": row.unit if measured else None,
                "service_code": codes.get(str(row.service_id)) if row.service_id else None,
                "decided_by": _person(row.decided_by),
                "decided_at": row.created_at.isoformat(),
            }
        )
    standing = list(
        check_models.BillRunStandingAnswer.objects.filter(
            tenant_id=tenant_id, bill_run=run, superseded=False
        )
    )
    users = {
        str(u.pk): u
        for u in user_model.objects.filter(
            pk__in=[a.decided_by_id for a in standing if a.decided_by_id]
        )
    }
    for r in chosen:
        key = str(r.account_id)
        raised = {
            f["code"] for f in by_check.get(r.pk, []) if f["severity"] == check_taxonomy.DECISION
        }
        for answer in standing:
            if answer.case in raised and answer.case not in own_cases[key]:
                out[key].append(
                    {
                        "case": answer.case,
                        "choice": answer.choice,
                        "scope": "all",
                        "reason": None,
                        "quantity": None,
                        "unit": None,
                        "service_code": None,
                        "decided_by": _person(users.get(str(answer.decided_by_id))),
                        "decided_at": answer.created_at.isoformat(),
                    }
                )
    return out


def _service_ids() -> dict[str, Any]:
    from apps.billing import gather

    codes = gather._resolve("tenancy", "service_ids_by_code")
    return dict((codes() if codes else {}) or {})


__all__ = [
    "STORE_SEAM",
    "account_findings",
    "check_report",
    "refuse_if_sent",
    "run_is_sent",
    "check_run",
    "counts",
    "findings_summary",
    "ready_accounts",
    "save_account_check",
    "tag_accounts",
]

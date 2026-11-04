# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 `P0.18` · the brief's §7.2.4, RULED — option (b).
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 14 (a failed
#          statement poisons a PostgreSQL transaction and the suite runs on
#          SQLite, which does not) · NFR-3 (no unpaginated read) ·
#          BR-REP-024 (report the owner's figure or name the gap)
# Tests:   06-backend/tests/test_cr142_p0_18_attribute_history.py
# ───────────────────────────────────────────────────────
"""WRITING AND READING an account's as-was class, type and status.

Two functions and no more: one that RECORDS a change and one that ANSWERS as at
a date. Everything else a report needs is a query over the table.

⚠ **`as_was` RETURNS `None` FOR ANY DATE BEFORE THIS TABLE STARTED RECORDING,
AND THAT IS THE HONEST ANSWER RATHER THAN A GAP TO PAPER OVER.** The brief is
explicit about what a report does with it: *"Where history exists it answers
as-was… Where it does not — anything before the table ships — it falls back to
as-is and SAYS SO ON THE FACE OF THE REPORT. One report will state both for the
first year, and that is correct rather than untidy: the alternative is a single
confident basis line that is true of half the rows."*

So `None` here never means *"no change"* and must never be read as the current
value. A caller that substitutes the current row for a missing one has turned a
stated absence into a wrong number, which is BR-REP-024's whole subject.

⚠ **AND THERE IS NOWHERE ELSE TO LOOK.** The old value of a class, type or
status that changed before this table started recording survives only in
`audit_log`, which is **pruned** on a retention schedule with no exemptions (PO
ruling 2026-09-23, verbatim: *"keep the same rule s; when audit log is delete -
it is deleted thats okay"*). Nothing in this module, in any document, or on any
screen may describe that path as keeping an old value for good, because it does
not — CLAUDE.md hard rule 4's closing clause. (`DEF-CUS-9084`: this sentence
used to quote the very phrase `test_p0_18_no_document_or_docstring_claims_the_
audit_log_is_permanent` refuses, so the scan was red from the day both landed.)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction

from core import audit as core_audit

from apps.customers.attribute_history_models import AccountAttributeHistory

#: The three columns of `accounts` this table shadows, in the order a report
#: names them (class · type · status). Named once so a fourth attribute is a
#: deliberate edit in one place rather than four `getattr`s in three files.
TRACKED_FIELDS = ("account_type_id", "account_subtype_id", "status_id")


def _current(account_id: Any) -> AccountAttributeHistory | None:
    """The open row for this account, or None while none has ever been written."""
    return (
        AccountAttributeHistory.objects.select_for_update()
        .filter(account_id=account_id, effective_to__isnull=True)
        .first()
    )


def _triple(row: Any) -> tuple[Any, Any, Any]:
    return tuple(getattr(row, field, None) for field in TRACKED_FIELDS)  # type: ignore[return-value]


def record(account: Any, *, on: date, actor: Any = None) -> AccountAttributeHistory | None:
    """Close the open period and open a new one — IF anything actually moved.

    Returns the new row, or `None` when the account's three values are already
    what the open row says. **An unchanged save must not write a row**: a table
    with one row per PATCH is a list of edits, not a history, and a report
    grouping by period would then split July in two for no reason a reader
    could see.

    ⚠ **THE CLOSE AND THE OPEN ARE ONE SAVEPOINT** — a nested
    `transaction.atomic()`, not a bare `try/except IntegrityError` (hard-won
    law 14). The partial unique index below refuses a second open row, and on
    PostgreSQL that refusal **aborts the whole transaction** unless it is
    caught inside a savepoint: every later statement then raises
    `InFailedSqlTransaction` and the caller's own work is lost at COMMIT. The
    test suite runs on in-memory SQLite, which has no aborted-transaction
    state, so the version without this passes green on every machine and loses
    a customer's edit the first time two writes race in production.
    **Do not "simplify" this away.**

    ⚠ **SAME-DAY CHANGES COLLAPSE, DELIBERATELY.** If the open period already
    begins on `on`, this UPDATES it in place rather than closing a zero-day
    window: `[2026-07-14, 2026-07-14)` is half-open and contains no date at
    all, so a row of that shape could never be read back by the query this
    table exists to serve. The last change on a day wins, which is exactly what
    a day-grained report can state truthfully.
    """
    with transaction.atomic():
        open_row = _current(account.pk)
        wanted = _triple(account)
        if open_row is not None and _triple(open_row) == wanted:
            return None
        if open_row is not None and open_row.effective_from == on:
            open_row.account_type_id = account.account_type_id
            open_row.account_subtype_id = account.account_subtype_id
            open_row.status_id = account.status_id
            open_row.save(
                update_fields=["account_type_id", "account_subtype_id", "status_id"]
            )
            return open_row
        if open_row is not None:
            if open_row.effective_from >= on:
                # A change dated on or before the open period's own start is a
                # BACKDATE, and backdating is not built: it would have to split
                # or reorder periods a report has already been run over. Named
                # rather than silently accepted, because accepting it writes a
                # window that violates `ck_account_attribute_history_window`
                # and fails at the database with nothing naming the cause.
                raise ValueError(
                    "CR-142 P0.18: a change dated on or before the open period's "
                    f"start ({open_row.effective_from}) is a backdate, and "
                    "backdating is not built. Record it on or after that day."
                )
            open_row.effective_to = on
            open_row.save(update_fields=["effective_to"])
        return AccountAttributeHistory.objects.create(
            tenant_id=account.tenant_id,
            account_id=account.pk,
            account_type_id=account.account_type_id,
            account_subtype_id=account.account_subtype_id,
            status_id=account.status_id,
            effective_from=on,
            effective_to=None,
            # `DEF-CUS-9081` — WHO, through the one resolver (`core.audit.
            # actor_user_id`). This read `actor if actor.pk else None`, and every
            # API layer's actor is `SimpleNamespace(id, role)` with no `pk`, so
            # every clerk change made in the app recorded NOBODY (hard rule 7).
            recorded_by_id=core_audit.actor_user_id(actor),
        )


def as_was(account_id: Any, *, on: date) -> AccountAttributeHistory | None:
    """The period in force on `on`, or None if this table was not recording yet.

    `None` is a STATED ABSENCE. It is not the current row and a caller must not
    substitute one — see this module's docstring.
    """
    return (
        AccountAttributeHistory.objects.filter(account_id=account_id, effective_from__lte=on)
        .filter(effective_to__isnull=True)
        .first()
    ) or (
        AccountAttributeHistory.objects.filter(
            account_id=account_id, effective_from__lte=on, effective_to__gt=on
        ).first()
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.18
# screens: none
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case in tests/test_cr142_p0_18_attribute_history.py failed on ImportError before this module existed.
# exceptions: (1) `as_was` is two queries rather than one `Q(...) | Q(...)`, because the open row has `effective_to IS NULL` and no comparison against NULL is ever true — one OR'd filter would silently return nothing for every date inside the CURRENT period, which is most dates anyone asks about · (2) backdating raises rather than accepting — it is not built and saying so by name beats a database error nobody can read
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

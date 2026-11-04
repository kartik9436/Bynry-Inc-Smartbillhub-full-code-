# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 task W2-T1:
#           *"Closing a window writes the W1-T4 record"* (B17 §7).
#           Screens: SET-06D (Audit tab · Read history)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §6, §7
# Rules:    D1 — *"yes"*, read windows are first-class CLOSABLE records
#           (window · read on · collected · expected · skips · result — **the
#           reader was removed by OQ-343 on 2026-08-23**, PO verbatim *"B: no
#           reader anywhere, correct the screenshot and drop the stored name"*,
#           and B17 §3 D14 records the divergence from the screenshot) ·
#           BR-MET-078 (NO money on these surfaces) · BR-MET-048
#           (every route/cycle change is audited) · CLAUDE.md rule 1 (tenant
#           scoping, RLS FORCE) · rule 6 (idempotency posture) · rule 7
# Tests:    06-backend/tests/test_cr029_rcw2_read_windows.py
# ───────────────────────────────────────────────────────
"""Closing a read window — the Read-history row SET-06D draws.

THE ACCEPTANCE SHAPE IS THE PO'S OWN SCREENSHOT, **CORRECTED BY THEIR OWN LATER
RULING**:

    Aug 2026 · Aug 3 · ~~M. Chen~~ · 196 · 196 · Complete
    └ window   └ read on             └ collected └ expected └ result

⚠ **THE READER IS GONE — OQ-343, ruled 2026-08-23.** D6 had ruled *"not
required"* against reader ASSIGNMENT; whether that reached this HISTORICAL fact
(who actually walked a closed window) was genuinely unclear, so RC-W3c built the
column, left the screen column out, and asked. The PO answered: *"B: no reader
anywhere, correct the screenshot and drop the stored name"*. So the screenshot is
corrected rather than followed, the payload keys are gone, and metering 0022
drops the stored FK — the product does not keep data no screen shows.

⚠ **`routes.assigned_to` IS UNTOUCHED.** D6 explicitly preserved the ops tab's
existing read-only reader display and the PO was not asked about it; removing it
would be a defect, not thoroughness.

Six facts, six columns on `read_windows` (metering 0020, minus 0022's drop), and
this module is their only writer.

⚠ **WHY THIS IS NOT IN `services.py`.** `import_runs.py` set the precedent and
states the reason: LAW 0 is a MODULE boundary, so a metering module may hold its
own ORM against metering's OWN tables, and keeping a new writer out of the
3,000-line shared file means a lane editing `services.py` and this lane never
touch one file (hard-won law 11 — in a shared tree a commit is a statement about
FILES). No table outside metering is written here.

⚠ **`result` IS STATED BY THE CLOSER, NEVER INFERRED FROM THE COUNTS.** Nothing
rules how a SKIP counts towards *"Complete"* — 190 collected plus 6 skipped of
196 could read either way — so this module refuses to decide it. Deriving it
would be a rule invented by a call site, which is the failure the prime
directive exists to prevent, and it would be invisible: the row would look
right.

**CLOSING IS IDEMPOTENT, AND A CLOSED WINDOW IS HISTORY.** The unique key
`(tenant, route, period_start)` is what makes a retry find the row rather than
write a second history (W1-T4's own words), and the record's dates are STORED
rather than derived at read time because of the FROM-NEXT rule: changing the
cycle's schedule tomorrow must not restate which days a crew walked last month.
A second close therefore returns the first one, marked `already_closed`, and
changes nothing — correcting a closed window is not built and is not guessed at.

**NOTHING HERE IS MONEY** (BR-MET-078, hardened by this CR): a read window
counts meters; what they bill to is the bill run's business.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.metering import models
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

__all__ = ["close_read_window", "read_window_history", "window_dict", "window_for_read"]


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _route_row(route_id: Any) -> models.Route:
    """This tenant's route, or ABSENT.

    HR-1 / CLAUDE.md rule 1: an unknown id, a malformed id and another tenant's
    id are ONE answer. A foreign key alone would not stop a window being written
    against another tenant's route — PostgreSQL evaluates referential integrity
    outside row-level security — so the row is resolved through a tenant-scoped
    read first, exactly as `runs.create_run` resolves its cycle.
    """
    try:
        return models.Route.objects.get(tenant_id=_tenant_id(), pk=route_id)
    except (models.Route.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        # `objects.get` raises Django's own ValidationError for a malformed
        # UUID; all four cases are the same answer — absent.
        raise errors.NotFoundError(audit_br_ref="BR-MET-073") from None


def window_dict(row: models.ReadWindow) -> dict[str, Any]:
    """One Read-history row, in the SET-06D column order.

    ⚠ **NO READER, BY RULING (OQ-343).** This served `reader_id` and
    `reader_name` — the screenshot shows *"M. Chen"* — and the PO ruled on
    2026-08-23, verbatim: *"B: no reader anywhere, correct the screenshot and
    drop the stored name"*. The columns are **Window · Read on · Collected ·
    Expected · Result**; the stored FK went with the payload keys (metering
    0022), because a product that keeps data no screen shows is keeping it for
    no one.
    """
    return {
        "id": str(row.id),
        "route_id": str(row.route_id),
        "cycle_id": str(row.cycle_id) if row.cycle_id else None,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "read_on": row.read_on.isoformat() if row.read_on else None,
        "collected": row.collected_count,
        "expected": row.expected_count,
        "skips": row.skip_count,
        "result": row.result,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def close_read_window(
    actor: Any,
    *,
    route_id: Any,
    period_start: date,
    period_end: date,
    read_on: date | None,
    collected_count: int | None,
    expected_count: int | None,
    skip_count: int | None = None,
    result: str,
) -> dict[str, Any]:
    """Close one route's window and write its history row. Idempotent.

    The window's PERIOD is passed in rather than re-derived: the caller got it
    from `period_engine` (or from the crew's own dates), and a record that
    recomputed its period at close time would move whenever the cycle's schedule
    moved — the FROM-NEXT rule broken in the one place it matters most.

    The CYCLE is taken from the route, because that is where a route's calendar
    lives (BR-MET-010, one cycle per route at a time). A window whose route
    later moves to another cycle still names the calendar that produced it.

    ⚠ **IT TOOK A `reader_id` UNTIL 2026-08-23 AND NO LONGER DOES (OQ-343).**
    PO verbatim: *"B: no reader anywhere, correct the screenshot and drop the
    stored name"*. The parameter is REMOVED rather than accepted-and-ignored: a
    caller passing a reader now gets a `TypeError` naming the argument, which is
    a better answer than a value silently dropped on the floor. `routes.assigned_to`
    is untouched — D6 preserved it and this ruling did not reach it.

    Returns the row as `window_dict`, plus `already_closed` — `True` when this
    call found a window that was closed before and changed nothing.
    """
    tenant_id = _tenant_id()
    route = _route_row(route_id)

    if period_end < period_start:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="metering.cycle.read_window_order",
            params={"period_start": period_start.isoformat(), "period_end": period_end.isoformat()},
            field_errors=[
                {
                    "field": "period_end",
                    "code": errors.VAL_RANGE,
                    "message_key": "metering.cycle.read_window_order",
                    "params": {},
                }
            ],
        )
    if result not in models.READ_WINDOW_RESULTS:
        # The sentence is the same one a lookup refusal uses ("Pick one of:
        # {{allowed}}.") and it now has a key that names THIS surface, minted by
        # RC-W3c in all eleven catalogues and pointed here by W5-T5. It borrowed
        # `metering.premises.status_unknown` only while that key did not exist —
        # G32 is a zero-baseline ratchet, so an unkeyed refusal could not ship,
        # and the borrow was REPORTED rather than hidden.
        allowed = ", ".join(models.READ_WINDOW_RESULTS)
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.readWindow.result_unknown",
            params={"allowed": allowed},
            field_errors=[
                {
                    "field": "result",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "metering.readWindow.result_unknown",
                    "params": {"allowed": allowed},
                }
            ],
        )

    with transaction.atomic():
        existing = models.ReadWindow.objects.filter(
            tenant_id=tenant_id, route_id=route.id, period_start=period_start
        ).first()
        if existing is not None:
            # A retry, a double-click, or a second crew closing the same walk.
            # The first close is the history; nothing is updated (a closed
            # window is a record of what happened, and restating it silently is
            # how a Read history stops being evidence).
            return {**window_dict(existing), "already_closed": True}
        try:
            row = models.ReadWindow.objects.create(
                tenant_id=tenant_id,
                route_id=route.id,
                cycle_id=route.cycle_id,
                period_start=period_start,
                period_end=period_end,
                read_on=read_on,
                collected_count=collected_count,
                expected_count=expected_count,
                skip_count=skip_count,
                result=result,
                closed_at=timezone.now(),
            )
        except IntegrityError:
            # Lost the race between the read above and this insert. The unique
            # index is the real guarantee; re-read and answer identically.
            winner = models.ReadWindow.objects.filter(
                tenant_id=tenant_id, route_id=route.id, period_start=period_start
            ).first()
            if winner is None:
                raise
            return {**window_dict(winner), "already_closed": True}

        served = window_dict(row)
        # CLAUDE.md rule 7 / BR-MET-048 — who closed it, when, and with what.
        # `before` is None because a window has no row until it is closed: this
        # design keeps no open placeholder to go stale (B17 §7 W2-T1, computed
        # on demand, no cron).
        core_audit.write_row(
            action="read_window.closed",
            entity_type="read_window",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before=None,
            after=served,
        )
    return {**served, "already_closed": False}


#: ⚠ **A PLACEHOLDER ID, NOT A MINTED ONE.** The RC-W6 lane surfaced this
#: question while implementing OQ-341 and reported it for minting rather than
#: numbering it itself — an id invented by a lane is an id nobody can find in
#: `12-governance/01-open-questions.md`. Replace it with the real `OQ-###` in
#: this one constant when the register allocates one.
OQ_WHICH_WINDOW = "OQ-345"


def window_for_read(read_on: date, windows: Sequence[tuple[date, date]]) -> tuple[date, date]:
    """Which window a read collected on `read_on` belongs to — **or a refusal.**

    ⚠ **THIS IS THE COST OQ-341's RULING CREATED, AND IT IS UNPAID.** On
    2026-08-23 the PO ruled that a cycle whose days-to-complete exceeds its own
    repeat is a WARNING and not a refusal — *"you give warning and if user
    override; let them do it"* — so read windows may now legitimately OVERLAP.
    OQ-341's own closing sentence states the consequence: *"a read taken while
    two windows are open must record WHICH window it belongs to"*.

    **Nothing in the schema answers it.** `meter_reads` carries `period_start`
    and `period_end` (nullable, and written by the read path from whatever
    period it was given), a `route` stamp (BR-MET-079, immutable provenance) and
    an `import_batch` — and **no link to `read_windows` at all**. So for a read
    collected on 2 September, with window 1 running 1–3 Sep and window 2 running
    2–4 Sep, there are at least three candidate answers and no rule:

      **(A) THE EARLIEST OPEN WINDOW** — the one that opened first is the one the
          crew is still finishing, so a read on the 2nd closes out window 1.
      **(B) THE LATEST OPEN WINDOW** — a crew that has started the next round is
          working the new one, so the 2nd belongs to window 2.
      **(C) THE CREW SAYS** — the read carries the window it was collected for,
          which needs a column (`meter_reads.read_window_id`) and a reader-side
          field, and is the only reading that survives a crew working both.

    They are not equivalent: the choice decides which window's `collected_count`
    a read lands in, and therefore whether a window closes *196 of 196* or
    *195 of 196* with a straggler in the next one.

    **So this REFUSES rather than picking one** (CLAUDE.md prime directive: an
    unruled question is carried to the PO, never answered by a lane — and least
    of all by a call site, which is how it would be answered if some caller
    quietly took `windows[0]`). **The unambiguous case still works**: exactly one
    window covering `read_on` is not a question, and this returns it. Only the
    genuinely ambiguous overlap raises.

    Nothing calls this yet, and that is deliberate: it is the boundary marker for
    the next lane to build against, so the question is met HERE rather than
    discovered inside a counting query. Its placeholder id is above.
    """
    covering = [window for window in windows if window[0] <= read_on <= window[1]]
    if len(covering) == 1:
        return covering[0]
    if not covering:
        # A plain ValueError, NOT a catalogued refusal: nothing calls this yet,
        # so a new `message_key` would have to be minted in eleven i18n
        # catalogues (G32) for a sentence no screen can reach. The caller that
        # eventually wires this up mints the key with its own refusal copy.
        raise ValueError(
            f"a read collected on {read_on.isoformat()} falls inside none of the "
            f"{len(windows)} windows offered, so it cannot be attributed to one."
        )
    raise NotImplementedError(
        f"{OQ_WHICH_WINDOW}: a read collected on {read_on.isoformat()} falls inside "
        f"{len(covering)} open read windows — "
        + " and ".join(f"{start.isoformat()}..{end.isoformat()}" for start, end in covering)
        + ". Since the Product Owner ruled on 2026-08-23 that a cycle may take longer to "
        "complete than its own repeat (a warning the operator may override), two windows "
        "can be open at once and nothing says which one a read belongs to. The earliest "
        "open window, the latest open window and a window the crew names are three "
        "different answers and they put the read in different counts, so it is NOT "
        "guessed here. `meter_reads` has no link to `read_windows` and adding one is a "
        "schema decision, not a call-site one."
    )


def read_window_history(route_id: Any, *, limit: int = 50) -> list[dict[str, Any]]:
    """SET-06D's Read history for one route — newest walk first.

    Tenant-scoped like every read here (rule 1). ⚠ It carried
    `select_related("reader")` so the Reader column cost no query per row (D7:
    *"the N+1 derivations batched"*); OQ-343 removed the column, so the join
    goes with it rather than being left as a prefetch of nothing.
    """
    rows = models.ReadWindow.objects.filter(tenant_id=_tenant_id(), route_id=route_id).order_by(
        "-period_start", "-created_at"
    )[:limit]
    return [window_dict(row) for row in rows]


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §6/§7 RC-W2-T1 + the CR-029 record in 12-governance/11-change-requests.md (D1)
# screens: SET-06D
# generated: 2026-08-23 by the CR-029 RC-W2 lane
# checklist: A✔ B=deferred(RC-W3-T3 owns SET-06D's Audit tab; this lane serves the row shape it renders) C✔(tests/test_cr029_rcw2_read_windows.py — RED first: ImportError, no such module) D✔ E✔ F✔ G✔ H=deferred(not a 🔒 path — no money, no rate, no RLS policy change, no idempotency KEY: the uniqueness is the schema's, landed in W1-T4)
# gates: ruff✔ black✔
# exceptions: (0) **NO READER ANYWHERE** — OQ-343 (PO 2026-08-23, *"B: no reader anywhere, correct the screenshot and drop the stored name"*): the payload keys, the `close_read_window` parameter, the `select_related` and the stored FK are all gone, and metering 0022 drops the column. `routes.assigned_to` is deliberately NOT touched (D6 preserved it; the PO was not asked) · (1) `result` is STATED by the closer and never inferred from the counts — no rule says how a skip counts towards "Complete", and inventing one would be invisible in the row · (2) a second close returns the first record unchanged; CORRECTING a closed window is not built and not guessed (no ruling exists) · (3) the refusal for an unknown result REUSES `metering.premises.status_unknown` ("Pick one of: {{allowed}}.") rather than minting a key — G32 ratchet + G15's eleven catalogues; the cross-surface reuse is REPORTED · (4) this module holds its own ORM against metering's own tables rather than routing through `services.py` — the `import_runs.py` posture, so two lanes never edit one file (hard-won law 11)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

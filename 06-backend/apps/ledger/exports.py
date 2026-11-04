# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-016 (S42 export: one summary JE per period per GL, idempotent
#           recorded batches, drill-back, dimension CSVs — TC-1..TC-7) ·
#           US-LED-021 (the COST-OF-SERVICE section — both sides leave in ONE
#           idempotent batch: TC-1 the five cost rows summing $51,902.50, TC-2
#           no second July batch, TC-4 drill-back on $28,222.00, TC-5 the
#           missing-ref atomic block, TC-6 the voided purchase out of the hash,
#           TC-7 the register-derived label that keeps it OUT of the
#           trial-balance footer) ·
#           US-LED-006 (the export codes it addresses accounts by — consumed)
#           Screens: S42 · S43
# Rules:    BR-LED-004 (one summary JE per period per GL account to QBO/Xero/
#           CSV/IIF using the mapping-page export codes; batches recorded +
#           IDEMPOTENT; every figure drills back; dimension CSV extracts) ·
#           BR-LED-017 (granularity is FLEXIBLE — summary or weekly, chosen per
#           export, both idempotent per covered window; export REQUIRES the
#           covered period CLOSED) · BR-LED-014 (the export codes live on the GL
#           mapping page, under Settings → Configure) · BR-LED-007 (a drifting
#           tie-out is a release blocker) · BR-LED-015 (every export audits) ·
#           BR-TEN-020 (a recorded batch keeps the refs it shipped with) ·
#           BR-LED-039 (the export carries the payable side out beside the
#           receivable side: one summary row per period per cost GL account, in
#           the SAME idempotent (period, target) batch — never a second one) ·
#           BR-LED-035 (a voided purchase leaves every aggregate) ·
#           CLAUDE.md rule 1 · rule 2 · rule 6 · rule 7
# Golden:   LE-5 — July → QuickBooks, 8 GL rows from LE-1's period deltas, batch
#           EXP-2607-QBO, payload debits = credits = 598.69, re-run BLOCKED ·
#           LE-14 — the SAME batch also carries 5100 $28,222.00 · 5110
#           $3,100.00 · 5140 $6,235.00 · 5200 $1,845.50 · 5300 $12,500.00 =
#           $51,902.50, labelled register-derived and NOT in the 598.69 footer
# Tests:    06-backend/tests/test_us_led_016_export.py ·
#           06-backend/tests/test_us_led_021_cost_export.py
# Impacts:  apps/ledger/close.py (BR-LED-017's closed-period gate reads it) ·
#           apps/ledger/reporting.py (the figures are ITS trial balance — this
#           module recomputes nothing) · apps/ledger/services.py (US-LED-006's
#           export codes)
# ───────────────────────────────────────────────────────
"""Accounting exports: one recorded, idempotent handover per closed window.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides what an accounting
system is told the books hold, and DB-12's idempotency key is a 🔒 path.
AI-authored 2026-08-15 under the PO ruling of 2026-08-09; row owed in
12-governance/09-human-review-ledger.md. Not on the G7 glob list yet — REPORTED
for the daily batch rather than self-added (B12 r2).

════════════════════════════════════════════════════════════════════════════
THIS MODULE COMPUTES NO MONEY
════════════════════════════════════════════════════════════════════════════
Every figure it hands over is `apps.ledger.reporting.trial_balance` for the
window — the same rows S56 renders, the same rows the tie-out panel checks.
A second summation here would be a second answer to *"what did July hold?"*, and
the day the two disagreed the ERP would hold the wrong one. LE-5 is explicit
that the export IS LE-1's table: *"one summary JE — 8 GL rows from LE-1's period
deltas"*, footing **598.69 = 598.69**.

════════════════════════════════════════════════════════════════════════════
FOUR GATES, IN THIS ORDER, AND EACH IS A DEFECT IT PREVENTS
════════════════════════════════════════════════════════════════════════════
1. **THE WINDOW MUST BE A CLOSED PERIOD** (BR-LED-017, the L-3b ruling: *"the
   ERP never receives numbers that can still move"*). T5-08 is the whole test:
   an open month's totals still change — late reads, corrections, reversals — so
   exporting one hands an accountant figures that silently drift from the books.
2. **THE WINDOW MUST NOT ALREADY BE COVERED** (BR-LED-004, DB-12, T5-07). A
   second QuickBooks handover of July is how a tenant's ERP books July's revenue
   twice, and SMARTBillHub would have caused it. The refusal LINKS the existing
   batch, because the user's real need is the FILE, and re-download is the
   ratified door. Idempotency is per covered WINDOW, whichever granularity was
   chosen (T5-07 step 3) — so a weekly export over an already-summarised month is
   refused too, and the overlap check below is what makes that true for windows
   that are not identical.
3. **THE PERIOD MUST FOOT** (BR-LED-007, US-LED-016 TC-6). A trial balance that
   does not balance can only mean a posting-service bypass, and *"no clean-looking
   handover over broken books"*. It is a release blocker with no dismiss path.
4. **EVERY ROW MUST CARRY THE TARGET'S REF** (BR-LED-014 / US-LED-006 TC-5), for
   QBO and Xero. The refusal NAMES the account (*"6900 · Bad debt"*) and is
   ATOMIC — nothing partial hands over. CSV and IIF address accounts by code and
   name (A14 §Accounting exports), so they need no ref and stay available, which
   is US-LED-006 TC-5's own second sentence.

════════════════════════════════════════════════════════════════════════════
WHY THE PAYLOAD IS STORED
════════════════════════════════════════════════════════════════════════════
J19 step 7: *"the export file re-generated from the batch is identical
(hash-stable)"*. Re-deriving it from the books would satisfy that only by luck —
US-LED-006 TC-4 changes `4100`'s QBO ref from 79 to 101 AFTER July's batch, and
*"the recorded batch (content hash) is unchanged; only future exports use the new
ref"*. A batch that regenerated itself would silently start saying 101. So the
rows that went are kept exactly as they went, and `content_hash` is a SHA-256
over their canonical JSON.

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT BUILT HERE, NAMED SO SILENCE IS NOT READ AS "DONE"
════════════════════════════════════════════════════════════════════════════
  * **No file is written and nothing is sent.** BR-LED-020 makes v1 *"FILE/batch
    export"* and DIRECT CONNECT (QBO/Xero OAuth) v2, and the S43 send modal, the
    IS-11 streamed downloads and the bookkeeper email (W6) are all surfaces this
    lane does not own. What exists is the RECORDED BATCH and its payload — which
    is what BR-LED-004 makes the durable artifact, and what a file is rendered
    FROM. Stated rather than implied (hard-won law 2).
  * **The `EXP-` number** is allocated from the tenant's `export_batch` series
    and no tenant has that series row either (`apps.tenancy.services.
    SERIES_DEFAULTS` seeds five and this is not one). The batch records with
    `batch_no = None` and says so by name; a number is never composed here, for
    BR-TEN-035's reason.
  * ⚠ **THIS BULLET SAID THE BY-PREMISES EXTRACT RETURNS NOTHING ATTRIBUTABLE
    UNTIL 2026-09-03, AND IT HAS RETURNED REAL ROWS SINCE 2026-08-16
    (`DEF-2345`).** It read: *"`journal_lines.premises_id` is NULL on every line
    in the product (US-LED-002 unbuilt)"*. That was true when written and stopped
    being true when `posting._stamped` began resolving account → unit → premises
    at posting time. The extract carries LE-6's three rows and foots to
    **553.69**. **What is unchanged is the posture:** the figures are passed
    through from `reporting.by_premises_summary` rather than re-derived here, so
    a real refusal — an undesignated AR account, or money lawfully carrying no
    premises — still reaches the caller as that read model states it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction

from apps.ledger import chart, close, cost_capture, models, reporting
from core import audit as core_audit
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")

AUDIT_BATCH_CREATED = "export.batch_created"
#: `P5.4` — what the accounting package said about a handover. A SEPARATE
#: action from the send, because a finance officer at an audit is asking a
#: different question: not *did we hand July over* but *did they take it*.
AUDIT_BATCH_ACKNOWLEDGED = "export_batch.acknowledged"

#: Which targets address an account by a REF the tenant typed, and which address
#: it by its own code+name. A14 §Accounting exports fixes both halves, and
#: US-LED-006 TC-5 turns on the difference: a missing QBO ref blocks the QBO
#: send while *"CSV/IIF (code-addressed) remain available"*.
REF_FIELD_BY_TARGET: dict[str, str | None] = {
    models.EXPORT_QBO: "qbo_ref",
    models.EXPORT_XERO: "xero_ref",
    models.EXPORT_CSV: None,
    models.EXPORT_IIF: None,
}

EXPORT_SERIES_NOT_SEEDED = {
    "code": "export_batch_number_series_is_not_seeded",
    "br_ref": "BR-LED-004 · BR-TEN-035 · BR-TEN-041",
    "detail": "LE-5 names the July batch **EXP-2607-QBO** and `core/numbering.EXPORT_BATCH` is "
    "the series it comes from, but no tenant has an `export_batch` row in `number_series`: "
    "`apps.tenancy.services.SERIES_DEFAULTS` seeds five series and BR-TEN-041's DEP-/RCT-/EXP- "
    "are deliberately absent, for *their owning lanes* to seed. The batch is RECORDED either "
    "way — its identity is (period, target) in the database, not its printed number — and it "
    "records with `batch_no = None` rather than a composed one, because BR-TEN-035 makes "
    "numbering tenant-visible and format-configurable and a second allocator is how two "
    "batches end up as EXP-7.",
    "wanted_reads": ("apps.tenancy.services.SERIES_DEFAULTS[core.numbering.EXPORT_BATCH]",),
}


class ExportError(RuntimeError):
    """An export the ledger refuses, with the reason a human can act on.

    Same shape and argument as `apps.ledger.posting.PostingError`: no HTTP
    surface here, and the API layer decides what a browser sees. `existing_batch`
    is populated on the idempotency refusal because T5-07's whole recovery path
    is *"route the user to the recorded batch (re-DOWNLOAD, never re-export)"* —
    a refusal that did not carry the link would send them looking for it.
    """

    def __init__(self, message: str, *, existing_batch: dict[str, Any] | None = None):
        super().__init__(message)
        self.existing_batch = existing_batch


@dataclass(frozen=True)
class SummaryRow:
    """One GL line of the handover — BR-LED-004's *"one summary JE per period
    per GL account"*, or one per GL per week under BR-LED-017's other choice."""

    code: str
    name: str
    type: str
    account_id: str
    target_ref: str | None
    debit: Decimal
    credit: Decimal
    window_start: date
    window_end: date


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _weeks(period_start: date, period_end: date) -> tuple[tuple[date, date], ...]:
    """BR-LED-017's weekly slices of a CLOSED period.

    Seven-day windows anchored on the period's own first day, with the last one
    clipped to the period end — so every slice is inside the closed window and
    their union is exactly it. Anchoring on ISO Monday instead would push the
    first slice back into the PREVIOUS month, which is a window this export was
    not authorised to cover.
    """
    slices: list[tuple[date, date]] = []
    cursor = period_start
    while cursor <= period_end:
        stop = min(cursor + timedelta(days=6), period_end)
        slices.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return tuple(slices)


def _rows_for_window(
    window: tuple[date, date], ref_field: str | None
) -> tuple[tuple[SummaryRow, ...], Decimal, Decimal, bool]:
    """The trial balance for one window, as export rows. NO arithmetic here."""
    balance = reporting.trial_balance(start=window[0], end=window[1])
    accounts = {
        str(row.pk): row
        for row in models.LedgerAccount.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True
        )
    }
    rows: list[SummaryRow] = []
    for row in balance["rows"]:
        if row["debit"] == ZERO and row["credit"] == ZERO:
            # A zero-net account inside ONE WEEK of a month is the common case
            # (nothing happened on that account that week). LE-1's own
            # zero-balance 2300 line is kept for the PERIOD view by the trial
            # balance itself; a week with no movement adds nothing an ERP can
            # book, and an all-zero row is noise the accountant has to read past.
            continue
        account = accounts.get(str(row["account_id"]))
        rows.append(
            SummaryRow(
                code=row["code"],
                name=row["name"],
                type=row["type"],
                account_id=str(row["account_id"]),
                target_ref=(getattr(account, ref_field, None) if ref_field and account else None),
                debit=row["debit"],
                credit=row["credit"],
                window_start=window[0],
                window_end=window[1],
            )
        )
    return tuple(rows), balance["total_debit"], balance["total_credit"], balance["balanced"]


def _payload(rows: tuple[SummaryRow, ...]) -> list[dict[str, Any]]:
    """The stored, hashed shape. Money as STRINGS — a float in a payload is the
    same defect CLAUDE.md rule 2 forbids in a column, one layer out."""
    return [
        {
            "code": row.code,
            "name": row.name,
            "type": row.type,
            "account_id": row.account_id,
            "target_ref": row.target_ref,
            "debit": str(row.debit),
            "credit": str(row.credit),
            "window_start": row.window_start.isoformat(),
            "window_end": row.window_end.isoformat(),
        }
        for row in rows
    ]


def _cost_payload(section: dict[str, Any]) -> list[dict[str, Any]]:
    """The cost rows in the STORED, hashed shape (BR-LED-039).

    Money as STRINGS, exactly as `_payload` does it — a float in a payload is
    the same defect CLAUDE.md rule 2 forbids in a column, one layer out.

    **`debit` and `credit` are deliberately ABSENT from these rows**, and since
    2026-08-16 that is the RULING rather than a held-open question. A captured
    purchase has no side because it has no journal entry (OQ-200, PO: *"(b) for
    R2, (a) once supplier payments exist"*); `amount` plus `source` is what the
    register actually knows, and writing `debit` would assert a posting that did
    not happen. The day supplier payments ship, these rows are re-derived from
    `journal_lines` and gain the pair with the label removed.

    ⚠ **`section` is load-bearing beyond labelling.** `stale_batches` recovers
    what a batch CARRIED by summing the rows stamped with it, so renaming this
    marker silently breaks the OQ-203 drift warning. It is a named constant,
    `COST_SECTION_MARKER`, for exactly that reason.
    """
    return [
        {
            "code": row["code"],
            "name": row["name"],
            "type": row["type"],
            "account_id": row["account_id"],
            "target_ref": row["target_ref"],
            "amount": str(row["amount"]),
            "purchase_count": row["purchase_count"],
            "section": COST_SECTION_MARKER,
            "source": row["source"],
            "unsigned": row["unsigned"],
            "window_start": row["window_start"],
            "window_end": row["window_end"],
        }
        for row in section["rows"]
    ]


def content_hash(payload: list[dict[str, Any]]) -> str:
    """SHA-256 over the canonical JSON of the rows that were handed over.

    `sort_keys=True` and a fixed separator, so the same rows hash the same on any
    machine and in any Python version — the property J19 step 7 relies on when it
    re-generates the file from the batch and expects it identical.
    """
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def overlapping_batch(*, period_start: date, period_end: date, target: str):
    """Any recorded batch for this target whose window touches this one.

    The database's `uq_export_batches_period_target` catches the identical
    window; this catches T5-07 step 3 — *"the OTHER granularity over the same
    already-covered window"* — and the wider case of a week inside an
    already-exported month. Two batches whose windows overlap is two handovers of
    the same money, whatever their dates say.
    """
    return (
        models.ExportBatch.objects.filter(
            tenant_id=_tenant_id(),
            target=target,
            period_start__lte=period_end,
            period_end__gte=period_start,
        )
        .order_by("created_at")
        .first()
    )


def batch_dict(batch: models.ExportBatch) -> dict[str, Any]:
    """One S42 export-history row (the epic's capability matrix)."""
    return {
        "batch_id": str(batch.pk),
        "batch_no": batch.batch_no,
        "period": [batch.period_start.isoformat(), batch.period_end.isoformat()],
        "target": batch.target,
        "granularity": batch.granularity,
        "entries": batch.row_count,
        "total_debits": batch.total_debits,
        "total_credits": batch.total_credits,
        "currency": batch.currency,
        "content_hash": batch.content_hash,
        "created_at": batch.created_at,
        "created_by_user_id": str(batch.created_by_user_id) if batch.created_by_user_id else None,
        # ── `P5.4` · the handover's answer ────────────────────────────────
        # ⚠ **`None` HERE MEANS NOBODY HAS SAID, AND THE SCREEN MUST RENDER
        # THAT AS ITSELF.** It is not *pending* and it is not *failed*: there
        # is no callback in a file handover (`BR-LED-020` makes direct connect
        # v2), so an unanswered batch is the ordinary case and always will be
        # until somebody records what the accountant told them. `DEF-127` is
        # what it costs to spell *nobody looked* and *the answer is no* the
        # same way.
        "ack_state": batch.ack_state,
        "ack_at": batch.ack_at,
        "ack_reference": batch.ack_reference,
        "ack_note": batch.ack_note,
        "ack_by_user_id": str(batch.ack_by_user_id) if batch.ack_by_user_id else None,
    }


def export_preview(
    *,
    period_start: date,
    period_end: date,
    target: str,
    granularity: str = models.EXPORT_SUMMARY,
) -> dict[str, Any]:
    """S43's balanced preview — *"entries count, total debits = credits"*.

    Writes NOTHING. It runs the same four gates as `create_export_batch` and
    reports which ones would refuse, so the modal can say *"July is still open"*
    or *"6900 · Bad debt has no QBO ref"* before a clerk clicks send.
    """
    _tenant_id()
    if target not in models.EXPORT_TARGETS:
        raise ExportError(
            f"{target!r} is not one of {models.EXPORT_TARGETS} — BR-LED-004 names four targets: "
            "QuickBooks Online, Xero, generic CSV and QuickBooks Desktop IIF."
        )
    if granularity not in models.EXPORT_GRANULARITIES:
        raise ExportError(
            f"{granularity!r} is not one of {models.EXPORT_GRANULARITIES}. BR-LED-017 (PO L-1, "
            '*"keep it flexible"*) offers ONE summary JE per closed period or WEEKLY JEs over '
            "that period — chosen per export, both idempotent per covered window."
        )
    if period_end < period_start:
        raise ExportError(f"the window {period_start} … {period_end} runs backwards.")

    ref_field = REF_FIELD_BY_TARGET[target]
    windows = (
        _weeks(period_start, period_end)
        if granularity == models.EXPORT_WEEKLY
        else ((period_start, period_end),)
    )
    rows: list[SummaryRow] = []
    debits = ZERO
    credits = ZERO
    for window in windows:
        window_rows, window_debits, window_credits, _balanced = _rows_for_window(window, ref_field)
        rows.extend(window_rows)
        debits += window_debits
        credits += window_credits

    # The FOOTING that gates the handover is the PERIOD's, not the sum of the
    # weekly slices: a week can legitimately not balance on its own (an entry
    # dated Monday against one dated the following Tuesday), while the period
    # always must. BR-LED-007 is a statement about the books, and the books are
    # the period.
    _period_rows, period_debits, period_credits, period_balanced = _rows_for_window(
        (period_start, period_end), ref_field
    )
    # ── BR-LED-039 — the payable side rides the SAME preview and the SAME
    # ── batch. Read over the whole period whatever the granularity: a captured
    # ── purchase carries a PERIOD and not a day, so slicing it into weeks would
    # ── invent a date the register does not hold.
    costs = cost_section(period_start=period_start, period_end=period_end, target=target)

    # US-LED-006 TC-5's ATOMIC block, extended to the cost accounts and merged
    # into ONE list. The gate is not re-implemented: adding the payable side
    # must loosen no existing gate and add no new failure mode, so a missing
    # 5100 QBO ref refuses through exactly the path a missing 6900 one does.
    missing_refs = tuple(
        f"{row.code} · {row.name}" for row in rows if ref_field and not row.target_ref
    ) + tuple(costs["missing_refs"])
    closed = close.window_is_closed(period_start, period_end)
    existing = overlapping_batch(
        period_start=period_start, period_end=period_end, target=target
    )
    return {
        "period": [period_start.isoformat(), period_end.isoformat()],
        "target": target,
        "granularity": granularity,
        "rows": tuple(rows),
        "entries": len(rows),
        "total_debits": debits,
        "total_credits": credits,
        "period_total_debits": period_debits,
        "period_total_credits": period_credits,
        "balanced": period_balanced,
        "period_closed": closed,
        "missing_refs": missing_refs,
        "already_exported": batch_dict(existing) if existing is not None else None,
        "sendable": bool(closed and period_balanced and not missing_refs and existing is None),
        # ⚠ US-LED-021 TC-7 — the cost section is carried SEPARATELY and its
        # total is NOT added to `total_debits` / `total_credits`. Under OQ-200
        # reading (b) it is a register extract and the trial balance does not
        # contain it; an unlabelled mixed total is a figure no reader can
        # reconcile, and that is the failure this separation exists to catch.
        # `balanced` therefore still means what it meant before this section
        # existed: the RECEIVABLE books foot.
        "cost_section": costs,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-004")
def create_export_batch(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    target: str,
    created_at: datetime,
    granularity: str = models.EXPORT_SUMMARY,
) -> dict[str, Any]:
    """LE-5 — July to QuickBooks, recorded once, and never a second time.

    The four gates run in the docstring's order and each refuses ATOMICALLY:
    nothing is written unless every one passes, because a half-recorded batch is
    a window the idempotency key says was handed over and a file that never went.

    `created_at` is an INPUT (BR-TEN-043) — a retried send must stamp one moment.
    """
    tenant_id = _tenant_id()
    if not isinstance(created_at, datetime):
        raise ExportError("created_at must be a datetime supplied by the caller (BR-TEN-043).")
    preview = export_preview(
        period_start=period_start,
        period_end=period_end,
        target=target,
        granularity=granularity,
    )

    # ── gate 1 · BR-LED-017: the covered period must be CLOSED ──────────────
    if not preview["period_closed"]:
        raise ExportError(
            f"the period {period_start} … {period_end} is NOT CLOSED, so it may not be exported "
            "(BR-LED-017, PO L-3b: *the ERP never receives numbers that can still move*). An "
            "open month's totals still change — late reads, corrections, reversals — and an "
            "accountant who has booked them cannot tell that they moved. Close the month first "
            "(the checklist is apps.ledger.close.close_checklist; incomplete items are a WARN "
            "and a reason, never a lockout — BR-LED-018)."
        )

    # ── gate 2 · BR-LED-004 / DB-12: one handover per covered window ────────
    existing = preview["already_exported"]
    if existing is not None:
        raise ExportError(
            f"the window {period_start} … {period_end} is already covered for {target} by batch "
            f"{existing['batch_no'] or existing['batch_id']} "
            f"({existing['period'][0]} … {existing['period'][1]}, sent {existing['created_at']}). "
            "BR-LED-004: batches are recorded and IDEMPOTENT — no double-handover. A second "
            "export is how the tenant's ERP books this money twice. The ratified door is to "
            "RE-DOWNLOAD the recorded batch; a genuine correction posts into the earliest OPEN "
            "period (BR-TEN-038) and rides the NEXT window's export.",
            existing_batch=existing,
        )

    # ── gate 3 · BR-LED-007: no clean handover over broken books ────────────
    if not preview["balanced"]:
        difference = preview["period_total_debits"] - preview["period_total_credits"]
        raise ExportError(
            f"the period does not FOOT — debits {preview['period_total_debits']} <> credits "
            f"{preview['period_total_credits']} (difference {difference}). BR-LED-007 makes "
            "drift a RELEASE BLOCKER with no dismiss path, and US-LED-016 TC-6 refuses the "
            "export over it: a balanced-looking handover of unbalanced books is worse than no "
            "handover. Drift is only possible through a posting-service bypass — find the "
            "entry, do not plug the total."
        )

    # ── gate 4 · BR-LED-014 / US-LED-006 TC-5: every row carries its ref ────
    if preview["missing_refs"]:
        named = ", ".join(preview["missing_refs"])
        ref_field = REF_FIELD_BY_TARGET[target]
        raise ExportError(
            f"these accounts have no {ref_field} and {target} addresses accounts by that ref: "
            f"{named}. BR-LED-014 puts the export codes on the GL mapping page (Settings → "
            "Configure) and US-LED-006 TC-5 makes this an ATOMIC block — nothing partial hands "
            "over, because a payload missing one account is a set of books the ERP cannot "
            "balance. CSV and IIF address accounts by code+name and remain available."
        )

    # ── BR-LED-039 — ONE batch, both sections, ONE content hash ─────────────
    # The cost rows go INTO the stored payload and therefore into the hash, and
    # they carry their own `source` label so a reader of the payload — an
    # accountant, an auditor, a re-generated file — can tell a register extract
    # from a journal summary without going back to the code. TC-6: a voided
    # purchase is already out of `cost_section`'s rows, so it is out of the
    # payload and out of the hash by construction rather than by a filter
    # somebody has to remember here.
    payload = _payload(preview["rows"]) + _cost_payload(preview["cost_section"])
    digest = content_hash(payload)
    try:
        batch_no = core_numbering.next_number(core_numbering.EXPORT_BATCH, period_end)
        series_gap = None
    except core_numbering.NumberingError:
        batch_no = None
        series_gap = EXPORT_SERIES_NOT_SEEDED

    try:
        with transaction.atomic():
            batch = models.ExportBatch.objects.create(
                tenant_id=tenant_id,
                batch_no=batch_no,
                period_start=period_start,
                period_end=period_end,
                target=target,
                granularity=granularity,
                content_hash=digest,
                row_count=len(payload),
                total_debits=preview["total_debits"],
                total_credits=preview["total_credits"],
                currency=_currency(),
                payload=payload,
                created_by_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            )
            core_audit.money_action(
                actor,
                AUDIT_BATCH_CREATED,
                "export_batch",
                str(batch.pk),
                after={
                    "batch_no": batch_no,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "target": target,
                    "granularity": granularity,
                    "content_hash": digest,
                    "rows": len(payload),
                    "total_debits": str(preview["total_debits"]),
                    "total_credits": str(preview["total_credits"]),
                    # BR-LED-039 — the payable side, recorded SEPARATELY in the
                    # trail for the same reason it is separate in the payload:
                    # it is not in the debits/credits above and a reader must
                    # never add it to them (US-LED-021 TC-7).
                    "cost_of_service_total": str(preview["cost_section"]["cost_total"]),
                    "cost_of_service_rows": preview["cost_section"]["entries"],
                    "cost_of_service_source": preview["cost_section"]["source"],
                    "job": None if actor is not None else "ledger.exports",
                },
            )
    except IntegrityError as exc:
        # Two clerks clicking send at once. The unique index is the half that
        # survives the race the SELECT above cannot.
        winner = overlapping_batch(
            period_start=period_start, period_end=period_end, target=target
        )
        if winner is None:
            raise
        raise ExportError(
            f"the window {period_start} … {period_end} was recorded for {target} by another "
            "request while this one was running (BR-LED-004, DB-12's unique key). One handover "
            "exists and this is not it.",
            existing_batch=batch_dict(winner),
        ) from exc

    result = batch_dict(batch)
    result["unavailable"] = (series_gap,) if series_gap else ()
    return result


def _currency() -> str:
    """The tenant's declared book currency, or USD.

    Read through tenancy's published `regional_settings`, never assumed — a CAD
    tenant's export saying USD is a set of books an accountant would post
    verbatim. `apps/ledger/wire.py` takes the same read for the same reason.
    """
    from importlib import import_module

    try:
        selectors = import_module("apps.tenancy.selectors")
    except ImportError:
        return "USD"
    fn = getattr(selectors, "regional_settings", None)
    if not callable(fn):
        return "USD"
    value = (fn() or {}).get("currency")
    return str(value) if value else "USD"


def export_history(*, target: str | None = None) -> tuple[dict[str, Any], ...]:
    """S42's export history — *"Sent · Period · Destination · Entries · By ·
    Status"*, newest first (the epic's capability matrix)."""
    rows = models.ExportBatch.objects.filter(tenant_id=_tenant_id())
    if target:
        rows = rows.filter(target=target)
    return tuple(batch_dict(row) for row in rows.order_by("-created_at"))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-004")
def record_acknowledgement(
    actor: Any,
    *,
    batch_id: Any,
    state: str,
    acknowledged_at: datetime,
    reference: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """`P5.4` — what the accounting package's operator said about a handover.

    ⚠ **THE BLUEPRINT'S OWN SENTENCE IS THE TASK:** *"Nothing reports back
    whether the accounting package accepted it."* A batch recorded who sent what
    and when, in full, and then the handover ended; a finance officer asking
    *"did QuickBooks take July?"* got `finance.export.noAckStatus`, which is a
    stated absence the screen has been rendering since it shipped.

    ⚠ **A RECORDED ANSWER, NOT A LIVE ONE.** `BR-LED-020` makes v1 a FILE/batch
    handover and direct connect v2, so there is nothing to poll and no callback
    to listen for. What closes the loop is a PERSON — the accountant imports the
    file, says whether it took, and a clerk writes that down here. A live status
    would be three green *Connected* chips over nothing (`DEF-007`).

    ⚠ **`acknowledged_at` IS AN INPUT AND NO CLOCK IS READ HERE** (`BR-TEN-043`).
    The import happened when it happened; a clerk may be recording it a day
    later, and stamping `now()` would put our clock on their event.

    ⚠ **THIS IS NOT A WIDENING OF HARD RULE 4.** That rule names issued
    invoices, invoice lines, payments and journal entries. `export_batches` is
    none of them — it is a record of a handover — and **nothing about the books,
    the payload, the totals or the content hash moves here.** What is written is
    what somebody ELSE did with the file afterwards. The batch's own
    idempotency (`BR-LED-004`, one recorded handover per period and target) is
    untouched: this never creates one and never changes which window was sent.

    ⚠ **AN ANSWER MAY BE CORRECTED AND THE AUDIT ROW IS WHY THAT IS SAFE.** An
    accountant who says *accepted* on Tuesday and finds two rejected lines on
    Wednesday must be able to say so, so this is an UPDATE rather than an
    append — and every call writes `audit_log` with the before and the after
    (hard rule 7), so the sequence of what was believed when is recoverable.

    `partial` is a real answer and not a hedge: a package that refuses the two
    lines whose account codes it does not recognise and takes the other thirty
    is neither accepted nor rejected, and that is the case a finance officer
    most needs to see.
    """
    tenant_id = _tenant_id()
    if state not in models.ACK_STATES:
        raise ExportError(
            f"{state!r} is not something an accounting package can tell us. The three "
            f"answers are {', '.join(models.ACK_STATES)} — and a batch nobody has answered "
            "for carries no state at all, which is a different fact and is not one of them."
        )
    if not isinstance(acknowledged_at, datetime):
        raise ExportError(
            "acknowledged_at must be a datetime supplied by the caller (BR-TEN-043 — the "
            "import happened when it happened; nothing here reads a clock)."
        )
    batch = models.ExportBatch.objects.filter(tenant_id=tenant_id, pk=batch_id).first()
    if batch is None:
        raise ExportError(
            f"export batch {batch_id!r} is not one of this tenant's batches (US-LED-016 TC-7)."
        )

    before = {
        "ack_state": batch.ack_state,
        "ack_at": batch.ack_at.isoformat() if batch.ack_at else None,
        "ack_reference": batch.ack_reference,
        "ack_note": batch.ack_note,
    }
    with transaction.atomic():
        batch.ack_state = state
        batch.ack_at = acknowledged_at
        batch.ack_reference = (reference or "").strip() or None
        batch.ack_note = (note or "").strip() or None
        batch.ack_by_user_id = getattr(actor, "id", None)
        batch.save(
            update_fields=[
                "ack_state",
                "ack_at",
                "ack_reference",
                "ack_note",
                "ack_by_user_id",
                "updated_at",
            ]
        )
        # Hard rule 7 — every money action writes `audit_log`. A handover's
        # answer is not money moving, and it IS the record a finance officer
        # relies on at an audit, so it is trailed the same way.
        core_audit.money_action(
            actor,
            AUDIT_BATCH_ACKNOWLEDGED,
            "export_batch",
            str(batch.pk),
            before=before,
            after={
                "ack_state": state,
                "ack_at": acknowledged_at.isoformat(),
                "ack_reference": batch.ack_reference,
                "ack_note": batch.ack_note,
            },
        )
    return batch_dict(batch)


def drill_back(*, batch_id: Any, code: str) -> dict[str, Any]:
    """US-LED-016 TC-3 — *"what is the 506.31?"* answered in dimensioned lines.

    LE-5 verbatim: the auditor points at a figure in the payload and the answer
    is *every journal line behind it*, with its service, account, premises and
    source. The lines are read for the BATCH'S OWN WINDOW, so a batch recorded in
    July still drills to July however many months later it is asked.

    The figure is looked up in the STORED payload rather than recomputed, so a
    drill-back proves what was HANDED OVER rather than what the books say now —
    which is exactly the question an auditor holding the ERP's copy is asking.
    """
    tenant_id = _tenant_id()
    batch = models.ExportBatch.objects.filter(tenant_id=tenant_id, pk=batch_id).first()
    if batch is None:
        raise ExportError(
            f"export batch {batch_id!r} is not one of this tenant's batches (US-LED-016 TC-7)."
        )
    exported = [row for row in (batch.payload or []) if row.get("code") == code]
    if not exported:
        raise ExportError(
            f"batch {batch.batch_no or batch.pk} carries no row for GL account {code!r}, so "
            "there is no exported figure to drill into."
        )
    lines = (
        models.JournalLine.objects.filter(
            tenant_id=tenant_id,
            journal_entry__status=models.JE_POSTED,
            journal_entry__entry_date__gte=batch.period_start,
            journal_entry__entry_date__lte=batch.period_end,
            ledger_account__code=code,
        )
        .select_related("journal_entry", "ledger_account")
        .order_by("journal_entry__entry_date", "created_at")
    )
    return {
        "batch_id": str(batch.pk),
        "code": code,
        "exported": tuple(exported),
        "lines": tuple(
            {
                "entry_id": str(line.journal_entry_id),
                "je_number": line.journal_entry.number,
                "entry_date": line.journal_entry.entry_date,
                "side": line.side,
                "amount": line.amount,
                "service_id": str(line.service_id) if line.service_id else None,
                "account_id": str(line.account_id) if line.account_id else None,
                "premises_id": str(line.premises_id) if line.premises_id else None,
                "source_type": line.source_type,
                "source_id": str(line.source_id) if line.source_id else None,
            }
            for line in lines
        ),
    }


def dimension_extract(*, kind: str, period_start: date, period_end: date) -> dict[str, Any]:
    """BR-LED-004's *"dimension-level CSV extracts"* — by service / premises /
    authority, each summing to the exported figures.

    Every one is `apps.ledger.reporting`'s existing read, passed through. This
    module derives nothing: an extract that summed the lines itself would be a
    third answer to the same question, after the trial balance and the screen.

    ⚠ **THIS SAID by-premises RETURNS `available=False` UNTIL 2026-09-03, AND IT
    HAS RETURNED LE-6's THREE ROWS SINCE 2026-08-16 (`DEF-2345`).** The old
    reason — *"`journal_lines.premises_id` is NULL on every line in the product
    (US-LED-002 unbuilt)"* — expired when `posting._stamped` began resolving the
    chain at posting time. **`available=False` is still reachable and still
    correct**, for a different and much narrower reason: a tenant whose chart
    designates no AR account has no receivable to attribute. That refusal is
    `reporting.by_premises_summary`'s, passed through here rather than re-derived,
    exactly as every other figure in this function is.
    """
    _tenant_id()
    if kind == "service":
        rows = reporting.revenue_by_service(start=period_start, end=period_end)
        return {"kind": kind, "rows": rows, "available": True}
    if kind == "premises":
        return {"kind": kind, **reporting.by_premises_summary(start=period_start, end=period_end)}
    if kind == "authority":
        return {
            "kind": kind,
            **reporting.remittance_by_authority(start=period_start, end=period_end),
        }
    raise ExportError(
        f"{kind!r} is not a dimension extract. BR-LED-004 names three — by service, by premises, "
        "by authority."
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-021 — THE COST-OF-SERVICE SECTION (BR-LED-039)
# ═══════════════════════════════════════════════════════════════════════════
#
# *"Capture, hold, reconcile, EXPORT"* is the whole of what the PO ruled the
# product does with AP (OQ-188), and the real payables live in the tenant's
# QuickBooks or Xero where they always did. So the period's handover carries
# **both sides** — the receivable side it already carried and the captured
# payable side — inside **the SAME recorded, idempotent `export_batches` row**
# keyed on (period, target). **Never a second batch**: two handovers for one
# month is exactly the double-handover BR-LED-004 exists to prevent, and a
# utility reconciling its ERP would find the same July twice.
#
# **Worked (LE-14, July 2026, Brazos Bend):** 5100 $28,222.00 · 5110 $3,100.00 ·
# 5140 $6,235.00 · 5200 $1,845.50 · 5300 $12,500.00 = **$51,902.50**, riding
# beside LE-5's receivable summary of **598.69 = 598.69**.
#
# ⚠⚠ **THE ROW SHAPE IS BLOCKED ON OQ-200, AND THE HONESTY GUARD IS THE POINT.**
# If a capture POSTS (reading (a)) these are ordinary GL summary rows read out of
# the books like every other row on S42, and July's trial balance moves from
# 598.69 to **52,501.19** — a change to golden test GT-51 needing the
# HUMAN-GUIDE §6 re-sign. If it does not (reading (b)) the section is
# REGISTER-DERIVED and must be labelled as such **so a reader never adds it to a
# trial-balance total that does not contain it** (US-LED-021 TC-7).
#
# Nothing here chooses. `cost_section` reads the REGISTER — which is what exists
# — and stamps `source="register"` on the section and on every row, keeps its
# total in `cost_total` and **out of `total_debits` / `total_credits`**, and
# `posting_shape_is_not_ruled` rides the result. The day OQ-200 closes as
# reading (a) the source becomes `journal` and the label goes; nothing about the
# arithmetic, the export codes, the idempotency, the drill-back or the refusals
# changes either way, which is exactly what the story says is settled.

#: The label a register-derived section carries, and the reason it must. Named
#: as a constant so a screen, a CSV header and a test all use one string.
COST_SECTION_SOURCE_REGISTER = "register"
COST_SECTION_SOURCE_JOURNAL = "journal"

#: ⚠ SUPERSEDED 2026-08-16 — OQ-200 is RULED and this code no longer rides any
#: section. Kept as a name so a reader of an older payload or an older test can
#: still find out what it meant, and removed from every result below.
COST_SHAPE_NOT_RULED = "posting_shape_is_not_ruled"

#: The shape is RULED, and it is register-derived. PO 2026-08-16 closing OQ-200,
#: verbatim: *"(b) for R2, (a) once supplier payments exist"*.
COST_SHAPE_RULED_REGISTER = "cost_section_is_register_derived"

COST_SECTION_LABEL = (
    "REGISTER-DERIVED — summed from the captured supplier-invoice register, NOT from the "
    "journal, and that is the RULING rather than a gap. A CAPTURE posts nothing to the books "
    "(OQ-200, PO 2026-08-16: '(b) for R2, (a) once supplier payments exist'), so these rows "
    "are NOT in the trial balance and this total MUST NOT be added to the balanced footer "
    "beside it: the receivable section contains none of this money. The reason posting was "
    "declined is that option (a) would credit an accounts payable this product can never "
    "drain — BR-LED-028 forbids payment runs — leaving $37,200.00 a year standing for "
    "invoices the utility settled by cheque. A purchase the clerk has marked SETTLED is a "
    "different matter and is NOT in these rows: entering a paid-on date posts DR cost / CR "
    "cash (BR-LED-028 as amended 2026-09-02), so that money is already in the books and "
    "reaches this handover through the balanced section above. It is counted out separately "
    "beside this one, because a cost that left by both routes would be paid twice at the "
    "other end."
)

#: The settled block's own label, and the sentence that keeps a reader from
#: reading its absence from the rows above as a figure that went missing.
COST_SECTION_SETTLED_LABEL = (
    "IN THE BOOKS — these purchases carry a paid-on date, so DR cost / CR cash has posted "
    "and they are inside the balanced section of whichever period the payment booked into. "
    "They are listed here so this month's register still adds up to what was bought; they "
    "are NOT in the register rows and must not be added to them."
)


def cost_section(
    *, period_start: date, period_end: date, target: str = models.EXPORT_CSV
) -> dict[str, Any]:
    """BR-LED-039 — one summary row per period per COST GL account.

    **TC-1's five rows, from the nine captured July purchases:** 5100
    $28,222.00 · 5110 $3,100.00 · 5140 $6,235.00 · 5200 $1,845.50 · 5300
    $12,500.00, Σ **$51,902.50**, each with its target ref.

    **TC-6 — a voided purchase is out of the payload and out of the hash.** The
    filter is `status=captured`, so RS-2607-0192's $155.00 leaves the section the
    moment it is voided and the section totals $51,747.50 instead. BR-LED-035:
    a voided row stays visible in the REGISTER and leaves every AGGREGATE.

    **TC-5 — a cost account with no target ref blocks the export ATOMICALLY,
    naming the account** (the US-LED-006 pattern). That gate is not implemented
    a second time here: `missing_refs` comes back on this result and
    `export_preview` merges it into the one list `create_export_batch` refuses
    over, so the payable side loosens no existing gate and adds no new failure
    mode.

    Rows are grouped on the ledger account, not on the service: BR-LED-039 says
    *"one summary row per period per cost GL account"*, and a tenant that points
    two services at one account gets one row, which is what an ERP can book.

    ⚠ **A SETTLED PURCHASE IS NOT IN THESE ROWS — CR-060 T6c, `DEF-3380`.**
    Until 2026-09-02 a capture posted nothing, so this section and the balanced
    section beside it could not overlap and the label above said so. **CR-060 T6
    made that false**: entering a paid-on date posts `DR cost / CR cash` through
    the one posting service, so the money is in the trial balance — and this
    section went on summing it as well. Measured on LE-11 with CI-1 settled: the
    batch carried **1,240.00 of purchased water in the balanced section AND
    3,100.00 in this one**, handing an ERP 4,340.00 against 3,100.00 bought.

    **THE FILTER IS SUBTRACTION, NOT RE-DERIVATION, AND THAT IS THE JUDGMENT.**
    Re-deriving the settled rows out of `journal_lines` and stamping them
    `journal` would put them in the payload twice over, because the balanced
    section already holds them. It would not even be the same payload: a July
    purchase paid on 4 August books into AUGUST, so its register row and its
    journal lines are in two different export windows and no single batch shows
    the duplication at all. So this section carries what is **only** in the
    register, and `settled` states what it left out with its total — a row that
    silently vanishes from a figure a clerk reconciled last month is worse than
    one that leaves loudly.

    **NO GATE IS LOOSENED.** A settled invoice's account still has to carry the
    target's reference, because it now appears in the SUMMARY rows and
    `export_preview` computes `missing_refs` over those by the same rule.
    """
    tenant_id = _tenant_id()
    ref_field = REF_FIELD_BY_TARGET[target]
    captured = cost_capture.models.SupplierInvoice.objects.filter(
        tenant_id=tenant_id,
        status=models.SUPPLIER_INVOICE_CAPTURED,
        period_start__gte=period_start,
        period_end__lte=period_end,
    )
    # `paid_on` is what makes a row postable (CR-060 C1), so it is what divides
    # the two halves here. The SETTLED half is summed and counted, never listed:
    # its rows are in the books and an ERP reads them from the balanced section.
    settled_total = ZERO
    settled_count = 0
    settled_currency: str | None = None
    for amount, currency in captured.filter(paid_on__isnull=False).values_list(
        "amount", "currency"
    ):
        settled_total += amount
        settled_count += 1
        settled_currency = settled_currency or currency
    rows = (
        captured.filter(paid_on__isnull=True)
        .select_related("ledger_account")
        .order_by("ledger_account__code")
    )

    by_account: dict[str, dict[str, Any]] = {}
    total = ZERO
    for row in rows:
        account = row.ledger_account
        bucket = by_account.setdefault(
            account.code,
            {
                "code": account.code,
                "name": account.name,
                "type": account.type,
                "account_id": str(account.pk),
                "target_ref": getattr(account, ref_field, None) if ref_field else None,
                # US-LED-017 TC-5 / field map D-10: the marker travels with the
                # row, because no column carries it and an unsigned code
                # presented as signed is the failure that rule exists to stop.
                # ⚠ False on every row since 2026-08-18, when the PO finance
                # re-signed the eight cost codes and names (no figure attached);
                # a stale warning riding a QuickBooks batch is its own defect.
                # The marker is derived, never listed, so it needs no edit here
                # — and it is held on a synthetic unsigned code in
                # `tests/test_us_led_021_cost_export.py`.
                "unsigned": account.code in chart.PENDING_FINANCE_RE_SIGN_COST,
                "amount": ZERO,
                "purchase_count": 0,
                "currency": row.currency,
                "window_start": period_start.isoformat(),
                "window_end": period_end.isoformat(),
                # ⚠ The row's OWN source label, not only the section's. A row
                # copied out of the payload into a spreadsheet keeps it.
                "source": COST_SECTION_SOURCE_REGISTER,
            },
        )
        bucket["amount"] += row.amount
        bucket["purchase_count"] += 1
        total += row.amount

    section_rows = tuple(by_account[code] for code in sorted(by_account))
    missing_refs = tuple(
        f"{row['code']} · {row['name']}" for row in section_rows if ref_field and not row["target_ref"]
    )
    return {
        "rows": section_rows,
        "entries": len(section_rows),
        "cost_total": total,
        "currency": _currency(),
        "missing_refs": missing_refs,
        # ⚠ TC-7's honesty guard, in three places at once so it cannot be read
        # past: the source, the label and the problem code. The code changed on
        # 2026-08-16 from `posting_shape_is_not_ruled` to
        # `cost_section_is_register_derived` because the shape IS ruled now —
        # a screen still calling a ruled question open is the stale claim
        # hard-won law 1 is about, and it reads to a finance officer as "this
        # number may be about to change", which it is not.
        "source": COST_SECTION_SOURCE_REGISTER,
        "label": COST_SECTION_LABEL,
        "problems": (COST_SHAPE_RULED_REGISTER,),
        "in_trial_balance": False,
        # CR-060 T6c / DEF-3380 — what this section deliberately does NOT carry,
        # stated rather than merely absent. `count` is 0 and `total` is 0.00 on
        # every tenant that has settled nothing, which is a derived answer and
        # not a default: LE-11's nine purchases carry no `paid_on`, so US-LED-021
        # TC-1's five rows and $51,902.50 are untouched by this change.
        "settled": {
            "count": settled_count,
            "total": settled_total,
            "currency": settled_currency or _currency(),
            "source": COST_SECTION_SOURCE_JOURNAL,
            "in_trial_balance": True,
            "label": COST_SECTION_SETTLED_LABEL,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# OQ-203's PRICE, MADE VISIBLE — the batch that no longer matches
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-08-16 closing OQ-203, verbatim: *"Yes it can be corrected"* — a
# captured supplier invoice may be edited or voided after its period closes.
# The consequence the PO accepted, in the registry's own words: *"the accounting
# export is idempotent and a re-run is blocked, so a correction made after an
# export changes a reconciliation the ERP ALREADY HOLDS, with no second handover
# possible. That drift must therefore be a NAMED, VISIBLE problem on the export
# screen — the utility has to be told which exported batch no longer matches, so
# a human can fix it at the ERP end. Building the edit without that warning
# would be worse than freezing it."*
#
# This is that warning. It is computed rather than flagged: a stored "is stale"
# boolean would have to be set by every write path that could ever touch a
# purchase, and the one that forgot would be silent. Comparing what the batch
# CARRIED against what the register says NOW cannot be forgotten by a new
# caller, because there is nothing for a new caller to remember to do.
#
# **What is compared, and why it is the cost total and not the content hash.**
# The hash covers the whole payload including the receivable rows, which can move
# for reasons that are not corrections. The cost total is the figure an
# after-close correction actually moves, it is recoverable exactly from the
# STORED payload — every cost row carries `section: "cost_of_service"` and its
# `amount` — and quoting both numbers, "carried 51,902.50 USD, register now
# 51,747.50 USD", tells the person at the ERP end precisely what to post.

#: The problem code S42 renders, and the one `cost_capture` echoes at the moment
#: of correction. ONE string for one fact (hard-won law 1's shape).
BATCH_NO_LONGER_MATCHES = "exported_batch_no_longer_matches"

#: The marker `_cost_payload` stamps on every stored cost row. Named once so the
#: writer and this reader cannot drift apart.
COST_SECTION_MARKER = "cost_of_service"


def batches_covering(*, period_start: date, period_end: date) -> tuple[dict[str, Any], ...]:
    """Every recorded batch whose window contains this one — newest first.

    Used by `cost_capture` at the moment a clerk corrects a closed period, so the
    refusal-shaped question *"has this month already gone to the accountant?"*
    is answered where the correction is made and not only on the export screen.
    Deliberately window-CONTAINMENT rather than overlap: a batch that covered
    only part of the corrected row's period did not carry that row.
    """
    rows = models.ExportBatch.objects.filter(
        tenant_id=_tenant_id(),
        period_start__lte=period_start,
        period_end__gte=period_end,
    ).order_by("-created_at")
    return tuple(
        {
            "batch_id": str(batch.pk),
            "batch_no": batch.batch_no,
            "target": batch.target,
            "period": [batch.period_start.isoformat(), batch.period_end.isoformat()],
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
        }
        for batch in rows
    )


def stale_batches() -> tuple[dict[str, Any], ...]:
    """S42's named warning: the batches whose cost section no longer matches.

    For each recorded batch, the cost section is recomputed over the window it
    covered and compared against the total it CARRIED. A difference means a
    purchase inside that window was corrected or voided after the handover.

    **Every figure here carries its currency** and both sides are quoted, because
    the person receiving this warning has to go and post the difference by hand
    in QuickBooks or Xero: *"EXP-2607-QBO carried 51,902.50 USD; the register now
    totals 51,747.50 USD — a difference of 155.00 USD."* A bare "this batch is
    stale" would send them to hunt for a number this product already knows.

    A batch recorded before the payable side existed carries **no cost rows at
    all**, and the register for its window is empty too, so it compares equal
    and is silent. A batch that carried cost rows and now finds none reports the
    whole amount as the difference, which is correct: every purchase in it was
    voided.
    """
    out: list[dict[str, Any]] = []
    currency = _currency()
    for batch in models.ExportBatch.objects.filter(tenant_id=_tenant_id()).order_by("-created_at"):
        payload = batch.payload if isinstance(batch.payload, list) else []
        carried = ZERO
        for row in payload:
            if isinstance(row, dict) and row.get("section") == COST_SECTION_MARKER:
                carried += Decimal(str(row.get("amount") or "0"))
        now = cost_section(
            period_start=batch.period_start, period_end=batch.period_end, target=batch.target
        )["cost_total"]
        if now == carried:
            continue
        out.append(
            {
                "problem": BATCH_NO_LONGER_MATCHES,
                "batch_id": str(batch.pk),
                "batch_no": batch.batch_no,
                "target": batch.target,
                "period": [batch.period_start.isoformat(), batch.period_end.isoformat()],
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "carried": carried,
                "register_now": now,
                "difference": now - carried,
                "currency": currency,
                "detail": (
                    "A captured supplier invoice inside this window was corrected or voided "
                    "AFTER this batch was handed over. The export is idempotent and cannot be "
                    "re-run (BR-LED-004) — a utility must never receive one month twice — so "
                    "the difference has to be posted by hand at the accounting system's end. "
                    "PO 2026-08-16 (OQ-203) permitted the after-close correction on exactly "
                    "the condition that this warning names the batch."
                ),
            }
        )
    return tuple(out)


def cost_drill_back(*, code: str, period_start: date, period_end: date) -> dict[str, Any]:
    """TC-4 — *"what is the $28,222.00?"* → the purchases behind it.

    The BR-LED-004 discipline applied to the payable side: every exported figure
    explains itself. For 5100 in July that is **BVPC-070026, Brazos Valley Power
    Cooperative, 412,000 kWh, 2026-07-31**.

    Register-derived like the section itself, and for the same reason: under
    OQ-200 reading (b) there are no journal lines to drill into, and under
    reading (a) these purchases are still what the lines were built from.

    ⚠ **IT DRILLS INTO WHAT THE SECTION CARRIES, WHICH SINCE `DEF-3380` EXCLUDES
    A SETTLED PURCHASE.** A drill-back that answered with five purchases for a
    figure summed from four is not an explanation, it is a second, contradicting
    total — and BR-LED-004's discipline is that every exported figure explains
    ITSELF. The settled ones explain themselves through the journal entry their
    settlement posted, which carries the invoice as its `source_id`.
    """
    rows = (
        cost_capture.models.SupplierInvoice.objects.filter(
            tenant_id=_tenant_id(),
            status=models.SUPPLIER_INVOICE_CAPTURED,
            paid_on__isnull=True,
            ledger_account__code=code,
            period_start__gte=period_start,
            period_end__lte=period_end,
        )
        .select_related("ledger_account")
        .order_by("invoice_date", "created_at")
    )
    purchases = tuple(cost_capture.supplier_invoice_row(row) for row in rows)
    if not purchases:
        raise ExportError(
            f"no captured purchases point at GL account {code!r} for {period_start} … "
            f"{period_end}, so there is no cost figure to drill into. A VOIDED purchase is "
            "excluded here and is still visible in the register (BR-LED-035); a SETTLED one "
            "is excluded because its cost is in the books and drills back through its "
            "journal entry (DEF-3380)."
        )
    return {
        "code": code,
        "period": [period_start.isoformat(), period_end.isoformat()],
        "purchases": purchases,
        "total": sum((row["amount"] for row in purchases), ZERO),
        "source": COST_SECTION_SOURCE_REGISTER,
        # ⚠ `COST_SHAPE_NOT_RULED` was SUPERSEDED on 2026-08-16 when the PO closed
        # OQ-200, and was removed from `cost_section` the same day — it was left
        # riding here, so a drill-back went on telling a finance officer that a
        # ruled question was open. Hard-won law 1, in a payload rather than a
        # comment. It carries the same code the section does.
        "problems": (COST_SHAPE_RULED_REGISTER,),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-016@dbc769d (sha1[:7] of the authorities this module implements, newline-joined in order this module implements, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-016 §1-§8 + US-LED-006 §3 TC-5 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-004/007/014/015/017/020 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-5 + LE-1 · 08-qa/01-e2e/journeys/J19-month-end-close.md steps 3-5 + T5-07 + T5-08 · 04-docs/02-decisions/02-database-design-brief.md Addendum r13 #4 + DB-12)
# generated: 2026-08-15 by the ledger close-the-books lane (replacing the one-line docstring stub) · AMENDED 2026-08-15 by the AP-capture lane (US-LED-021 / BR-LED-039: `cost_section`, `_cost_payload` and `cost_drill_back`; the payable side rides the SAME (period, target) batch and the SAME content hash, its total is carried OUTSIDE total_debits/total_credits and labelled register-derived under OQ-200, and the missing-ref atomic block is EXTENDED to cost accounts rather than re-implemented)
# checklist: A✔ B✔ C✔ D=deferred(the S42/S43 endpoints are the API half — not built by this lane) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row owed and G7 glob REPORTED)
# gates: see 06-backend/tests/test_us_led_016_export.py — the open-period gate,
#         the re-run block, the overlap block, the drift block and the missing-ref
#         block were each proved RED before they were trusted green
# exceptions: NO FILE IS WRITTEN AND NOTHING IS SENT — BR-LED-020 makes v1 a file
#         export and DIRECT CONNECT v2; this lane records the BATCH and its
#         payload, which is what a file renders from, and the S43 modal + IS-11
#         streamed downloads + the W6 bookkeeper email are other lanes' · the
#         `EXP-` number is allocated and no tenant has the `export_batch` series
#         row (tenancy seeds five and BR-TEN-041's three are deliberately absent
#         *for their owning lanes*); the batch records with `batch_no = None` and
#         says so by name — a number is never composed here · WEEKLY GRANULARITY
#         SLICES A CLOSED PERIOD and never spans two: BR-LED-017 offers *weekly
#         JEs over THE CLOSED PERIOD*, and the covered window is still the period,
#         which is what keeps the idempotency key honest under T5-07 step 3 · the
#         FOOTING gate is asserted on the PERIOD, not per weekly slice — a single
#         week can lawfully not balance and the books cannot · ⚠ **THIS CLAUSE
#         SAID THE BY-PREMISES EXTRACT IS `available=False` BECAUSE US-LED-002 IS
#         UNBUILT — CORRECTED 2026-09-03 (`DEF-2345`), THE DIMENSION LANDED
#         2026-08-16** and the extract carries LE-6's three rows footing to
#         **553.69**; `available=False` remains reachable for the narrower
#         reason that a chart designating no AR account has no receivable to
#         attribute, and the figure it cannot attribute is still named by the
#         read model ·
#         **THE COST SECTION'S ROW SHAPE IS BLOCKED ON OQ-200** — it is
#         REGISTER-DERIVED, stamped `source="register"` on the section, on every
#         row and in the stored payload, its total is carried in `cost_total`
#         and deliberately NOT added to `total_debits`/`total_credits`, and
#         `posting_shape_is_not_ruled` rides the result. `balanced` therefore
#         still means "the RECEIVABLE books foot", exactly as before. Under
#         OQ-200 reading (a) the same rows are journal-derived and July's trial
#         balance moves 598.69 → 52,501.19, which is GT-51 and takes the
#         HUMAN-GUIDE §6 re-sign · the cost rows carry `amount` and NOT
#         `debit`/`credit`: a captured purchase has no side until OQ-200 says it
#         posts, and writing one would answer the question inside a payload an
#         ERP reads · the cost section is read over the WHOLE PERIOD whatever
#         the granularity, because a captured purchase carries a period and not
#         a day — slicing it weekly would invent a date the register does not
#         hold. REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — *New World receipt push*: yesterday's online
#           receipts, as ONE New World file, placed in the City's SFTP folder.
# Rules:    PO 2026-10-07 — S2 (*"You already ruled that scheduled jobs run as
#           runbooks - this is correct"*; 2026-09-16 *"we are going to use
#           runbooks to run the scheduled job"*) · the GIS row of the same day
#           (*"we will call APi manually and test it first when everything
#           work then we will do nightly job for specific utility/tenant"*) ·
#           Q2 (the utility's own day) · Q4 (refuse a day already sent) · Q6
#           (*"User will configure this in runbook on thier own"*) · BR-RBS-002
#           · BR-RBS-003 (dry and live walk one path) · BR-RBS-004 (plan first)
#           · BR-RBS-010 · BR-RBS-022 (a write is a named port)
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py ·
#           06-backend/tests/test_cr173_newworld_sftp_pg.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registering line) ·
#           apps/runbooks/engine/acts.py (LIVE_ENABLED_RUNBOOKS) ·
#           apps/runbooks/ports/integrations_ports.py ·
#           apps/runbooks/seams/integrations_seam.py
# ───────────────────────────────────────────────────────
"""*New World receipt push* — build → upload → record, for ONE day.

THE DAY
-------
`day` is the one input. Blank — what a schedule always sends — means
**yesterday on the utility's own clock** (PO Q2). A person running it by hand
may type a day (`2026-10-05`). Today and any later day are refused: a day that
has not ended is a file that would miss the evening's payments, and once sent
it could not be sent again without a person's resend.

THE THREE STEPS
---------------
1. **Build** — the file is built exactly as it would be sent (one
   `<ROOT>` document, `newworld.render` once over every receipt) and
   COUNTED: receipts, not balanced, lines with no City GL number. Reads only.
2. **Upload** — one act through the `send_partner_file` port, whose subject is
   the DAY. The engine's idempotency key is the runbook, the act and the day,
   with no run in it, so a second run for the same day is refused by the
   engine before the port is reached; integrations' own partial unique index
   refuses it again underneath, which is the guard that also holds against a
   person's resend racing a schedule.
3. **Record** — reads back what the act did and reports it. The run history
   row on Settings → Integrations is written by integrations, on every attempt.

DRY AND LIVE — HOW THIS BECOMES LIVE FOR ONE UTILITY
----------------------------------------------------
Recorded in the decision log of 2026-10-07. In short:

* This key is on `engine.acts.LIVE_ENABLED_RUNBOOKS` — the one line in code
  that lets ANY tenant's run of it reach a bound writer. It writes no money:
  it sends a file of payments already posted.
* That alone sends nothing anywhere. A run is LIVE only when it is started
  live — **Run ▶** with *Run for real* chosen by a System Admin, or a schedule whose
  runbook's gate is *approved up front* (`scheduler._mode_for`); every other
  run is dry and builds, counts and reports, uploading nothing.
* And a live run sends nothing for a utility that has not typed a City server
  on its New World connection (PO S1). The utility's own settings ARE the
  per-utility switch; there is no environment variable and no flag.

So *"by hand first, then schedule it for one utility"* (the GIS row) is: a
System Admin at that utility types the folder settings, presses **Test
connection**, runs this by hand dry, then live, then sets the schedule time and
approves it up front. Every other utility is untouched.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_TEXT,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts
from apps.runbooks.seams import integrations_seam, tenancy_seam

KEY = "newworld_receipt_push"
PORT = "send_partner_file"
ACTION_KIND = "send_receipt_file"

STEP_BUILD = "build"
STEP_UPLOAD = "upload"
STEP_RECORD = "record"

#: The record outcomes a clerk reads (B14 rule 33: a fact ≤ 6 words).
OUTCOME_SENT = "Sent to the City folder"
OUTCOME_WOULD_SEND = "Would send — dry run"
OUTCOME_ALREADY = "Already sent for that day"
OUTCOME_NOT_SENT = "Not sent"
OUTCOME_NOT_SET_UP = "No City folder set up"

RULE = "One file per utility per day"
FIX_ROUTE = "Settings → Integrations → New World / Logos"

#: Refusals of the input, ≤ 6 words.
NOT_A_DAY = "That is not a day."
NOT_FINISHED = "Only a finished day is sent."
NO_ZONE = "The utility time zone is unknown."


def _day_from(ctx: Any) -> tuple[date | None, str]:
    raw = str((ctx.params or {}).get("day") or "").strip()
    today = tenancy_seam.today()
    if raw:
        try:
            chosen = date.fromisoformat(raw)
        except ValueError:
            return None, NOT_A_DAY
    else:
        chosen = integrations_seam.receipt_file_default_day()
        if chosen is None:
            return None, NO_ZONE
    if today is not None and chosen >= today:
        return None, NOT_FINISHED
    return chosen, ""


def resolve(ctx: Any) -> list[SubjectRef]:
    """ONE subject — the day — or none, with the reason kept for the report."""
    chosen, why = _day_from(ctx)
    ctx.set_results["day_refused"] = why
    if chosen is None:
        return []
    return [SubjectRef(subject_type="period", subject_id=chosen.isoformat(), label=f"{chosen:%d %b %Y}")]


def step_build(ctx: Any, walked: Any) -> dict[str, Any]:
    """Build and count the file. Nothing is written and nothing is dialled."""
    if not walked:
        return {"built": False, "why": ctx.set_results.get("day_refused") or NOT_A_DAY}
    day = date.fromisoformat(str(walked[0].subject_id))
    found = dict(integrations_seam.receipt_file_preview(day))
    found["built"] = True
    return found


def _trigger(ctx: Any) -> str:
    run = models.RunbookRun.objects.filter(pk=ctx.run_id).only("trigger").first()
    return "scheduled" if run is not None and run.trigger == models.TRIGGER_SCHEDULE else "manual"


def step_upload(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """The one act: place the file. Dry, or not live-enabled → *planned*, nothing sent."""
    built = dict(ctx.set_results.get(STEP_BUILD) or {})
    if not built.get("set_up"):
        return {
            "outcome": OUTCOME_NOT_SET_UP,
            "decided_by_rule": "Set the City folder up first",
            "reason": "No server is saved on the New World connection.",
            "fix_route": FIX_ROUTE,
            "data": {"filename": built.get("filename"), "receipts": built.get("receipt_count", 0)},
        }
    filename = str(built.get("filename") or "")
    result = acts.perform(
        ctx,
        acts.ActRequest(
            port=PORT,
            action_kind=ACTION_KIND,
            subject=subject,
            planned_action=f"Send {filename} to the City folder",
            # Empty: once per day, ever — PO Q4. A resend is a person's act on
            # the Integrations screen and never this runbook's.
            discriminator="",
            decided_by_rule=RULE,
            reason=f"{built.get('receipt_count', 0)} receipts for {subject.label}",
            fix_route=FIX_ROUTE,
            payload={
                "day": subject.subject_id,
                "trigger": _trigger(ctx),
                "started_by_name": (ctx.params or {}).get("started_by_name"),
            },
        ),
    )
    words = {
        acts.OUTCOME_DONE: OUTCOME_SENT,
        acts.OUTCOME_PLANNED: OUTCOME_WOULD_SEND,
        acts.OUTCOME_ALREADY: OUTCOME_ALREADY,
    }
    record = (
        models.RunbookRunRecord.objects.filter(pk=result.record_id).only("data", "reason").first()
        if result.record_id is not None
        else None
    )
    detail = dict((record.data or {}).get("result") or {}) if record is not None else {}
    outcome = words.get(result.outcome, OUTCOME_NOT_SENT)
    if detail.get("code") == "already_sent":
        outcome = OUTCOME_ALREADY
    return {
        "outcome": outcome,
        "decided_by_rule": RULE,
        "reason": (record.reason if record is not None and record.reason else "")
        or str(detail.get("sentence") or ""),
        "fix_route": "" if result.outcome == acts.OUTCOME_DONE else FIX_ROUTE,
        "data": {
            "filename": filename,
            "act": result.outcome,
            "receipts": built.get("receipt_count", 0),
            "trace": detail.get("trace", ""),
        },
    }


def step_record(ctx: Any, walked: Any) -> dict[str, Any]:
    """What happened, for the report. Reads only — integrations wrote the run row."""
    return {"days": len(walked)}


def report(view: Any) -> list[Block]:
    built = dict(view.set_results.get(STEP_BUILD) or {})
    record = view.records[0] if view.records else None
    outcome = record.outcome if record is not None else ""
    if not built.get("built"):
        word, tone, detail = "Nothing to send", "warning", str(built.get("why") or "")
    elif outcome == OUTCOME_SENT:
        word, tone, detail = "Sent", "success", f"{built.get('filename')} is in the City folder."
    elif outcome == OUTCOME_WOULD_SEND:
        word, tone, detail = "Dry run", "warning", "Built and counted. Nothing was sent."
    elif outcome == OUTCOME_ALREADY:
        word, tone, detail = "Already sent", "warning", "That day's file went earlier."
    elif outcome == OUTCOME_NOT_SET_UP:
        word, tone, detail = "Not set up", "warning", "Save the City folder first."
    else:
        word, tone, detail = "Not sent", "danger", (record.reason if record is not None else "")
    receipts = str(built.get("receipt_count", 0))
    return [
        Block(
            block="verdict",
            payload={"word": word, "tone": tone, "count": receipts, "detail": detail},
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {"id": "receipts", "label": "Receipts", "value": {"kind": "text", "text": receipts}},
                    {
                        "id": "unbalanced",
                        "label": "Not balanced",
                        "value": {"kind": "text", "text": str(built.get("unbalanced_count", 0))},
                        "detail": "Sent and flagged",
                    },
                    {
                        "id": "no_gl",
                        "label": "No GL number",
                        "value": {"kind": "text", "text": str(built.get("unresolved_gl_count", 0))},
                        "detail": "Sent and flagged",
                    },
                ]
            },
        ),
        Block(
            block="facts",
            payload={
                "heading": "The file",
                "rows": [
                    {"id": "day", "label": "Day", "value": {"kind": "text", "text": str(built.get("day") or "—")}},
                    {
                        "id": "file",
                        "label": "File name",
                        "value": {"kind": "text", "text": str(built.get("filename") or "—")},
                    },
                    {
                        "id": "folder",
                        "label": "Folder",
                        "value": {"kind": "text", "text": str(built.get("folder") or "—")},
                    },
                    {
                        "id": "server",
                        "label": "Server",
                        "value": {"kind": "text", "text": str(built.get("server") or "—")},
                    },
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "day", "label": "Day"},
                    {"key": "outcome", "label": "Outcome"},
                    {"key": "reason", "label": "Why"},
                ],
                "rows": [
                    {
                        "id": f"{one.subject.subject_id}:{one.step_key}",
                        "cells": {
                            "day": {"kind": "text", "text": str(one.subject.label or one.subject.subject_id)},
                            "outcome": {"kind": "text", "text": one.outcome},
                            "reason": {"kind": "text", "text": one.reason},
                        },
                        "meta": {"decided_by_rule": one.decided_by_rule, "step": one.step_key},
                    }
                    for one in view.records
                ],
                "total": len(view.records),
                "empty": {
                    "title": "No day to send.",
                    "helper": str(built.get("why") or "Pick a finished day."),
                },
            },
        ),
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="New World receipt push",
    kind=models.KIND_ACTION,
    category="data_sync",
    subject_type="period",
    unit_of_work="the day's receipt file",
    resolve=resolve,
    report=report,
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("new world", "receipts", "sftp"),
    parameters=(
        # Blank = yesterday on the utility's clock. A person may type a day.
        Parameter(name="day", type=PARAM_TEXT, label="Day", default=""),
    ),
    steps=(
        Step(key=STEP_BUILD, label="Build", mode=MODE_SET, run=step_build),
        Step(key=STEP_UPLOAD, label="Upload", mode=MODE_PER_RECORD, run=step_upload, writes=True),
        Step(key=STEP_RECORD, label="Record", mode=MODE_SET, run=step_record),
    ),
    ports=(PORT,),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-173-BRC10 (the 2026-10-07 rulings verbatim) + BR-RBS-002/003/004/010/022
# generated: 2026-10-07 by the CR-173-BRC10 lane NW-SFTP
# checklist: A✔ B✔ C✔ D✔(POST /runbooks/{key}/runs) E✔(Run ▶ on the runbook page) F✔ G✔ H=deferred(🔒 idempotency — the engine composes the key; row in 09-human-review-ledger.md)
# gates: pytest tests/test_cr173_newworld_sftp.py · tests/test_cr173_newworld_sftp_pg.py · tests/test_us_rbs_015_conformance.py
# exceptions: none
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────

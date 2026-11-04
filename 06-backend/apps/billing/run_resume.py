# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-004 (phase 2 calculate)   Screens: S31 step 4
# Contract: TD-17 (*"every job idempotent + resumable"* — tasks record a
#           `checkpoint` as they go and a resumed run reads it and skips
#           finished work) · core/jobs.py §RESUMABLE · NFR-4 (progress)
# Rules:    BR-BIL-052 (*"per-account, restartable, resumable — already-drafted
#           accounts are not recomputed and never duplicated"*) · BR-BIL-023 (a
#           re-calculation REPLACES an account's draft) · BR-BIL-053 (the break
#           list) · BR-BIL-055 (a break never blocks the run) · CLAUDE.md hard
#           rule 6 (a bill run is idempotent) · hard rule 4 (nothing here
#           touches an issued document) · BR-TEN-043 / gate G6 (no clock)
# Change:   CR-051 task 11 — *"Write a checkpoint so a killed worker resumes
#           rather than re-walking the cycle."*
# Tests:    06-backend/tests/test_cr051_run_scale.py
# Impacts:  apps/billing/run_jobs.py (writes the checkpoint, reads the plan) ·
#           apps/billing/runs.py (`prepare_run(resume_skip=…)`,
#           `calculate_run(already_done=…)`) ·
#           apps/billing/selectors.py (`prepared_for(resume_skip=…)`)
# ───────────────────────────────────────────────────────
"""CR-051 task 11 — what a killed calculate worker may skip when it comes back.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides which accounts a resumed
bill run does NOT walk, which puts it directly in front of CLAUDE.md hard rule
6 (a bill run is idempotent). AI-authored 2026-08-31 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

⚠ **THIS FILE IS NOT MATCHED BY ANY GLOB IN `10-scripts/gates/human_owned.txt`
AND DELIBERATELY DID NOT ADD ONE.** That file's own header makes changing the
guarded set a PROCESS EVENT — *"the guarded set must not drift with whoever is
coding"* — and it records five occasions on which a money or idempotency file
joined the CODE without joining the LIST. `apps/billing/run_jobs.py`, the file
this one serves, took exactly this posture on 2026-08-30. So the markers and
the ledger row are here and whether the glob should exist is asked in the
ledger row rather than answered by a lane.

────────────────────────────────────────────────────────────────────────────
WHY A CHECKPOINT AT ALL, WHEN THE RUN IS ALREADY RESUMABLE
────────────────────────────────────────────────────────────────────────────
`runs.calculate_run` is resumable BY CONSTRUCTION and says so: each account is
its own transaction, stage 6 REPLACES an account's draft rather than adding a
second (BR-BIL-023), and stages 1-5 are pure — so a killed pass that simply
starts again converges on the same drafts and can never double-bill. That is
correct and this file does not change it.

**What it costs is the whole cycle, and CR-051 task 21 measured the bill.**
On real PostgreSQL 16: **137 ms per account** and **1,383.5 seconds — 23
minutes — for 10,000 accounts**, of which the prepare pass is **84%**. A worker
killed at account 9,000 of 10,000 pays the whole 23 minutes again to redo work
it had finished. That is what "re-walking the cycle" means and it is what this
file exists to stop.

(This paragraph said *"the 8 seams"* and *"88%"* while it was drafted against
the CR's estimate and a partial pass. The seam count is TWENTY, measured —
`DEF-2707` — and the share is 84%. Corrected rather than left standing, which
is hard-won law 1 at its smallest.)

────────────────────────────────────────────────────────────────────────────
THE MARKER IS A CURSOR **AND** THE WRITE — AND IT NEEDS BOTH
────────────────────────────────────────────────────────────────────────────
Neither half is sufficient alone, which is the whole design:

* **The cursor alone is not safe.** The checkpoint records the LAST ACCOUNT
  NUMBER completed, and the run walks accounts in `account_no` order
  (`customers.accounts_for_bill_run` orders by `account_no, id`, `prepare_run`
  appends in that order, and `decisions.apply_decisions` preserves it). But
  BR-MET-082 Amendment 1 says the population is re-derived on every pass —
  *"every run it is not necessry it will ahve same number of accounts"* — so a
  NEW account can appear below the cursor between the kill and the resume.
  Skipping on the cursor alone would leave that customer silently unbilled,
  which is the worst failure this module could have.

* **The write alone is not safe either.** "This account already has a draft
  for this run" cannot tell THIS job's draft from a PREVIOUS job's stale one,
  and `invoices` carries no job stamp (adding one is a migration into a money
  table for a marker that is not needed — see the cursor above). A clerk who
  fixes a plan and presses *Work out the bills* again must be re-priced, not
  handed last week's drafts.

**So an account is skipped only when BOTH are true:** its number is at or
below the cursor THIS job wrote, *and* the run already holds a draft invoice
or a break row for it. Everything below the cursor was walked by this job in
this pass, so a draft found there IS this pass's; an account that appeared
below the cursor since has neither and is walked normally.

⚠ **AND A FRESH JOB SKIPS NOTHING.** `core.jobs.enqueue` mints a record with
`checkpoint: None`, and `plan_for` answers "walk everything" for it. Only a
job whose record already carries a checkpoint — which is to say a job that has
already run once and been re-delivered or restarted (`core.jobs.start`:
*"queued → running, or failed → running … checkpoint SURVIVES"*) — resumes.
Every inline caller, every first delivery and every re-press of the button is
byte-for-byte the pass this product ran yesterday.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY NOT DONE HERE
────────────────────────────────────────────────────────────────────────────
* **No clock** (BR-TEN-043 / gate G6). The cursor is an account NUMBER, not a
  time. A timestamp marker would have been the obvious alternative and it
  needs a clock read in a worker, which this repo forbids for good reason.
* **No decision is re-taken.** `decisions.apply_decisions` runs over whatever
  `prepare_run` returns; a skipped account's decision was applied on the pass
  that drafted it, and the exclusion row it may have written is idempotent.
* **No break is closed and none is re-raised.** A skipped account is not
  walked, so `record_break` and `clear_break` are not reached for it and its
  row stands exactly as the first pass left it. `runs.clear_break` closing a
  break belongs to an account that DRAFTS on a later pass, which is a full
  re-calculation and not a resume.
* **Nothing is deleted, updated or issued.** This module only ever READS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from apps.billing import models
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")

#: The checkpoint shape this module writes and reads. Bumped when the members
#: change, and an unrecognised version is treated as NO checkpoint — a resumed
#: job then re-walks the cycle, which is slow and always correct. A checkpoint
#: read with the wrong shape is the one case where guessing costs money.
CHECKPOINT_VERSION = 1


@dataclass(frozen=True)
class ResumePlan:
    """What a re-delivered calculate job may skip, and what it has already done.

    `resume_after` is an account NUMBER (the cursor) or None for "walk
    everything". `already_done` seeds NFR-4's gauge so a resumed run reads
    *"9,000 of 10,000"* and not *"0 of 1,000"* — a gauge that restarts at zero
    tells an operator the work restarted, which is exactly the thing this
    module exists to stop being true.
    """

    resume_after: str | None = None
    already_done: int = 0

    @property
    def resuming(self) -> bool:
        return self.resume_after is not None


def checkpoint(*, done: int, total: int, account_no: str | None) -> dict[str, Any]:
    """The marker `run_jobs._progress_reporter` hands to `record_progress`.

    Small on purpose: three scalars, whatever the size of the run. The obvious
    alternative — the set of account ids already done — is 360 KB of JSON at
    10,000 accounts, rewritten on every progress tick, which is a write that
    grows with the work it measures.
    """
    return {
        "v": CHECKPOINT_VERSION,
        "done": int(done),
        "total": int(total),
        # The cursor: the last account this pass FINISHED, worked or broken.
        # `run_jobs.PROGRESS_EVERY` throttles the write to one account in 25,
        # so the cursor can lag the truth by up to 24 accounts and a resume
        # re-walks those. That is deliberate and safe — re-walking is what the
        # run did before this file existed — and it is the whole cost of not
        # writing to the jobs table once per draft.
        "cursor": None if account_no is None else str(account_no),
    }


def plan_for(record: dict[str, Any]) -> ResumePlan:
    """The plan this job record implies. A record with no checkpoint walks all.

    Reads only the record — no database, no clock. `run_jobs.run_calculate_job`
    calls it once, before the prepare pass, because the plan decides what that
    pass is allowed not to gather.
    """
    marker = record.get("checkpoint") or {}
    if not isinstance(marker, dict) or marker.get("v") != CHECKPOINT_VERSION:
        if marker:
            logger.warning(
                "job %s carries a checkpoint this build does not recognise (%r) — "
                "the run re-walks the cycle, which is slow and always correct",
                record.get("id"),
                marker.get("v"),
            )
        return ResumePlan()
    cursor = marker.get("cursor")
    if not cursor:
        return ResumePlan()
    return ResumePlan(resume_after=str(cursor), already_done=int(marker.get("done") or 0))


def completed_account_ids(bill_run: Any) -> frozenset[str]:
    """The accounts this run has already FINISHED with — drafted, or broken.

    Two queries for the whole run, never one per account: the ids of the run's
    draft invoices, and the ids on its break rows. Together they are *"the run
    has a result for this account"*, and both come from billing's own tables —
    no join into customers, no cross-module read (B1).

    An ISSUED invoice is deliberately not counted. A run that has issued is
    past phase 2 and `calculate_run` has no business walking it at all; leaving
    it out means this set can never be read as permission to skip an account
    whose bill is already immutable (hard rule 4).
    """
    tenant_id = core_tenancy.current_tenant_id()
    drafted = models.Invoice.objects.filter(
        tenant_id=tenant_id, bill_run=bill_run, status=models.INVOICE_DRAFT
    ).values_list("account_id", flat=True)
    broken = models.BillRunBreak.objects.filter(tenant_id=tenant_id, bill_run=bill_run).values_list(
        "account_id", flat=True
    )
    return frozenset(str(one) for one in drafted) | frozenset(str(one) for one in broken)


def skip_predicate(plan: ResumePlan, bill_run: Any):
    """`(account_id, account_no) -> bool` — may this account be skipped?

    Returns a callable rather than a set so the two halves are read together at
    the one place the decision is made, and so the expensive half (the two
    queries above) is not run at all on a job that is not resuming.

    ⚠ **THE `and` IS THE WHOLE SAFETY ARGUMENT** — see the module docstring.
    Weaken either side and this stops being idempotent: cursor-only can skip an
    account nobody billed, write-only can skip an account somebody asked to be
    re-priced.
    """
    if not plan.resuming:
        return lambda account_id, account_no: False
    completed = completed_account_ids(bill_run)
    cursor = plan.resume_after

    def skip(account_id: Any, account_no: Any) -> bool:
        if account_no is None or str(account_no) > cursor:
            return False
        return str(account_id) in completed

    return skip


__all__ = [
    "CHECKPOINT_VERSION",
    "ResumePlan",
    "checkpoint",
    "completed_account_ids",
    "plan_for",
    "skip_predicate",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051@task11 (12-governance/11-change-requests.md §CR-051 task 11 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-051..055 · core/jobs.py's TD-17 resume contract)
# generated: 2026-08-31 by the CR-051 W2/W5/W6 backend lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — this lane touched no file under 07-frontend; the wizard's readout is CR-051 task 12 and shipped 2026-08-30) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr051_run_scale.py (RED-proved first; verbatim failures in the lane report) · the resume cases re-run against real PostgreSQL under config.settings.local (CLAUDE.md law 14) · golden 33/33 unchanged before and after — no ❄️ B4/B5 figure is reachable from this file
# exceptions: (1) the skip needs BOTH the cursor and the write, and the reason each alone is unsafe is in the module docstring · (2) the cursor lags by up to `run_jobs.PROGRESS_EVERY` accounts, which re-walks at most 24 and is the price of not writing to `jobs` once per draft · (3) this file is NOT in 10-scripts/gates/human_owned.txt: adding a glob there is a process event the PO owns, so the markers and the ledger row are here and the glob is REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

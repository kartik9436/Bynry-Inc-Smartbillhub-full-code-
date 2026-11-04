# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-012 (EP-RBS-04) — CR-075 wave L task L5, the half the
#           Product Owner reshaped on 2026-09-06.
# Rules:    OQ-RBS-1737 CLOSED (the duplicate check moved from the RECORD to
#           the RUN) · supersedes BR-RBS-008, which was PROPOSED and never
#           confirmed · CLAUDE.md hard rule 6 (idempotency) · hard rule 1
#           (tenant scoping)
# Tests:    06-backend/tests/test_us_rbs_012_duplicates.py
# Impacts:  apps/runbooks/engine/acts.py (the per-record belt under this brace)
#           · apps/runbooks/definitions/dunning.py (asks this before step 1)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED · HUMAN-REVIEW-PENDING — has this job already run this morning?

AI-authored 2026-09-06 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`. 🔒 **idempotency keys** — this is the
run-level half of hard rule 6 for this module.

THE RULING THIS FILE IMPLEMENTS, AND WHAT IT REPLACED
------------------------------------------------------
`OQ-RBS-1737` asked *how is a runbook's idempotency key composed*, with two
candidates we had already shown to be wrong in opposite directions. **The
Product Owner did not choose between them. They moved the check from the RECORD
to the RUN**, verbatim (decision log 2026-09-06):

> *"if it runs at 7 am and user approved it then it will create records/data in
> system. when you again run it at 9 am - you will find those record means you
> can see that it is duplicate. second scenario lets say you run at 7 am and no
> one approve it until 9 am ; then again 9 am run at that time you will see same
> job ran at 7 am and not yet approved; you can give warning to user sayng that
> job is pending to be approved; keep 24 hours time limit on the same job or we
> can parameteise the frequency of the runs"*

Three parts, all of them here:

1. **AN APPROVED EARLIER RUN HAS ALREADY WRITTEN ITS ROWS, SO THE DUPLICATE IS
   VISIBLE.** Detection is a READ of what exists, not a fingerprint computed in
   advance. `ALREADY_ACTED` below is that read.
2. **AN UNAPPROVED EARLIER RUN IS A THIRD STATE AND GETS A WARNING, NEVER A
   SILENT SKIP.** *"you can give warning to user sayng that job is pending to be
   approved"*. A run waiting for a person is not a duplicate: the second run
   tells the clerk the first is still sitting there. **Neither candidate key
   could express this at all**, because a key is a yes/no and this is a third
   answer — which is the clearest sign the question was the wrong shape.
3. **A TIME BOUND ON THE SAME JOB.** *"keep 24 hours time limit on the same job
   or we can parameteise the frequency of the runs"*. Offered as an either/or.
   **This lane read it as ONE control — the frequency is a parameter and 24
   hours is its default** — because the two are the same control at different
   settings and shipping only the fixed limit would need removing the moment a
   utility wants a weekly ladder. That reading is recorded as OURS in the
   decision log rather than attributed to the Product Owner; if it is wrong it
   costs one field, not a design.

⚠ WHAT THIS DOES NOT COVER, NAMED SO NOBODY READS IT AS COVERING MORE
-----------------------------------------------------------------------
**A customer past due for thirty days, under a ladder that runs daily.** This
check stops the 09:00 retry; the 24-hour bound stops a second run the same day;
**neither stops account 4021 receiving a letter on each of thirty consecutive
days.** That belongs to the LADDER'S RUNGS — the runbook's own logic — and it
is where `definitions/dunning.py` solves it: the rung is the per-record key's
discriminator, so the 10-day notice is written ONCE however many times the
ladder runs, and the 5-day notice is a different key three days later. Worked:
**a customer 30 days past due under a daily ladder receives 3 letters over 45
days, not 30 over 30.** It is written out in both places so the boundary is met
rather than rediscovered.

⚠ WHAT WOULD MAKE THIS CHECK PASS WRONGLY (hard-won law 7, habit 2)
--------------------------------------------------------------------
* **Looking at every run of the tenant instead of every run of THIS runbook.**
  Two different runbooks running at 07:00 would each report the other as a
  duplicate. → The query is filtered on `runbook_id` and the test asserts a
  sibling runbook's run is invisible to it.
* **Counting the run that is asking.** A run always finds itself and every run
  reports a duplicate. → `exclude(pk=...)`, and the test runs the check from
  inside a live run row.
* **Reading a wall clock.** `BR-TEN-043`: event time is an argument. A clock
  read here makes the check untestable at a boundary and unbacktestable. →
  `now` is a required argument, and `G6` greps for the clock read this does not
  make.
* **Treating `stopped` or `failed` as acted.** A run somebody stopped at record
  120 wrote 120 rows, so it IS partly acted; a run that failed at record 0 is
  not. → Both are reported as `EARLIER_RUN` with their record count, and the
  count is what the caller reads rather than the status word.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from apps.runbooks import models

#: The Product Owner's own figure, as the DEFAULT of a parameter — see part 3
#: of the ruling above. Hours rather than a `timedelta` because it is a runbook
#: parameter a clerk types on a setup screen (`PARAM_INTEGER`).
DEFAULT_FREQUENCY_HOURS = 24

#: The four verdicts. `NONE` is the ordinary answer; the other three each carry
#: a sentence a clerk reads.
VERDICT_NONE = "none"
VERDICT_ALREADY_ACTED = "already_acted"
VERDICT_PENDING_APPROVAL = "pending_approval"
VERDICT_EARLIER_RUN = "earlier_run"

#: A run in one of these statuses has been through a person and has written
#: whatever it was going to write.
ACTED_STATUSES = (
    models.RUN_STATUS_APPROVED,
    models.RUN_STATUS_ACTING,
    models.RUN_STATUS_DONE,
)


@dataclass(frozen=True)
class DuplicateVerdict:
    """What the last run of this job says about this one.

    `warning` is the distinction the ruling turns on: `ALREADY_ACTED` is a
    reason to write nothing, `PENDING_APPROVAL` is a reason to TELL SOMEBODY —
    and a build that collapsed the two into one boolean would silently skip a
    run whose plan is still sitting on a clerk's screen.
    """

    verdict: str
    #: Plain language, no rule id and no run id (B14 rules 31 and 32).
    message: str = ""
    earlier_run_id: Any = None
    earlier_started_at: Any = None
    earlier_status: str = ""
    records_written: int = 0

    @property
    def is_duplicate(self) -> bool:
        """Has this work already been done? A pending run has NOT."""
        return self.verdict == VERDICT_ALREADY_ACTED

    @property
    def warning(self) -> bool:
        """Is there something a person needs to be told about?"""
        return self.verdict in (VERDICT_PENDING_APPROVAL, VERDICT_EARLIER_RUN)


def check(
    *,
    tenant_id: Any,
    runbook_id: Any,
    now: dt.datetime,
    this_run_id: Any = None,
    frequency_hours: int = DEFAULT_FREQUENCY_HOURS,
) -> DuplicateVerdict:
    """Look for an earlier run of THIS job inside the window, and read what it did.

    `now` is an ARGUMENT and never a clock read (`BR-TEN-043`, gate `G6`): a
    ladder re-run for last Tuesday must take last Tuesday's answer, and a check
    that read the wall clock could not be tested at the window's edge at all.

    Worked, on the Product Owner's own two scenarios:

      **07:00 approved, 09:00 asks.** The 07:00 run is `done` with 812 record
      rows. This returns `ALREADY_ACTED` and the 09:00 run writes nothing — and
      it can SAY 812, because it read them.

      **07:00 unapproved, 09:00 asks.** The 07:00 run is `awaiting_approval`
      with 812 planned rows and nobody has pressed anything. This returns
      `PENDING_APPROVAL` with *"a run of this job from earlier today is still
      waiting to be approved"* — a WARNING, and the 09:00 run does not quietly
      vanish.
    """
    if frequency_hours <= 0:
        raise ValueError(
            "the frequency of a job is a positive number of hours; 24 is the default the "
            "Product Owner named on 2026-09-06 and zero would mean *never treat any run as "
            "the same job*, which is the guarantee switched off rather than configured."
        )
    since = now - dt.timedelta(hours=frequency_hours)
    runs = models.RunbookRun.objects.filter(
        tenant_id=tenant_id, runbook_id=runbook_id, started_at__gte=since
    )
    if this_run_id is not None:
        runs = runs.exclude(pk=this_run_id)
    earlier = runs.order_by("-started_at").first()
    if earlier is None:
        return DuplicateVerdict(verdict=VERDICT_NONE)

    written = models.RunbookRunRecord.objects.filter(
        tenant_id=tenant_id, run_id=earlier.pk
    ).count()

    if earlier.status in ACTED_STATUSES:
        return DuplicateVerdict(
            verdict=VERDICT_ALREADY_ACTED,
            message=(
                f"this job already ran in the last {frequency_hours} hours and was approved. "
                f"It left {written} records; those are what you are looking at, and nothing "
                "is being done again."
            ),
            earlier_run_id=earlier.pk,
            earlier_started_at=earlier.started_at,
            earlier_status=earlier.status,
            records_written=written,
        )
    if earlier.status == models.RUN_STATUS_AWAITING_APPROVAL:
        return DuplicateVerdict(
            verdict=VERDICT_PENDING_APPROVAL,
            message=(
                f"a run of this job from earlier is still waiting to be approved. It has "
                f"{written} records ready and nobody has looked at them yet."
            ),
            earlier_run_id=earlier.pk,
            earlier_started_at=earlier.started_at,
            earlier_status=earlier.status,
            records_written=written,
        )
    return DuplicateVerdict(
        verdict=VERDICT_EARLIER_RUN,
        message=(
            f"this job ran in the last {frequency_hours} hours and did not finish. "
            f"It left {written} records behind."
        ),
        earlier_run_id=earlier.pk,
        earlier_started_at=earlier.started_at,
        earlier_status=earlier.status,
        records_written=written,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-012 (EP-RBS-04; CR-075 wave L task L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the run routes are a sibling's api.py) E=n/a(no screen — L7 is another lane's) F✔ G✔ H✔(🔒 idempotency keys — HUMAN-OWNED + HUMAN-REVIEW-PENDING above, row in 12-governance/09-human-review-ledger.md, glob in 10-scripts/gates/human_owned.txt)
# gates: pytest tests/test_us_rbs_012_duplicates.py · G115 · G6 (no clock read) · G7
# exceptions: the thirty-day daily-ladder case is NOT covered here and is named in the docstring — it belongs to the ladder's rungs (definitions/dunning.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

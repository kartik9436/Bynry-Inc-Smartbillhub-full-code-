# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-006 (EP-RBS-03) — CR-075 wave H task H1: the engine upserts a
#           run's findings into `work_items` BY FINGERPRINT at run close.
# Rules:    BR-RBS-017 (a work item is upserted by fingerprint so a repeated
#           finding AGES rather than duplicating) · BR-RBS-022 (work items and
#           audit rows are the ENGINE's to write, never a port) · BR-RBS-011 (a
#           failure names its fix route) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 4 (nothing here touches an invoice, a payment
#           or a journal line) · hard-won law 14 (a savepoint, not a bare
#           except) · B14 rule 31 (no database id is ever the visible value)
# Tests:    06-backend/tests/test_us_rbs_006_work_items.py
# Impacts:  apps/runbooks/services.py (`close_run` calls `upsert`) ·
#           apps/runbooks/contract.py (`Finding`, and the optional `findings`
#           declaration on `RunbookDefinition`)
# ───────────────────────────────────────────────────────
"""The engine act that fills `RBS-007` — **upsert by fingerprint, close by absence.**

⚠ **THIS IS AN ENGINE ACT AND NOT A PORT, WHICH IS THE WHOLE POINT**
(`BR-RBS-022`). `contract.ENGINE_ACTS` names `raise_work_item` and
`interfaces.PORTS` refuses it BY NAME, because a fourteenth port would give
**every Check in the catalogue** the ability to write. A runbook returns
`Finding` objects from its declared `findings()`; this module turns them into
rows. That is what lets a runbook holding no writer at all populate a screen.

═════════════════════════════════════════════════════════════════════════════
THE FINGERPRINT, AND WHY IT IS A READABLE STRING RATHER THAN A DIGEST
═════════════════════════════════════════════════════════════════════════════
`US-RBS-006`: *"The daily pre-bill sweep raises the same missing read for thirty
days. **That must be one item ageing, not thirty items.** The fingerprint is the
runbook, the subject and the finding kind; the row's age is what tells a clerk
this has been ignored for a month."*

    <tenant>|<runbook key>|<subject type>:<subject id>|<finding kind>

⚠ **AND IT NEVER CONTAINS THE RUN ID** (`US-RBS-006` §5, in those words). With
the run in it every run mints a new row, the screen becomes a log, and
`TC-RBS-006.2` — *a resolved item whose finding recurs reopens the SAME row* —
is unreachable. That is this file's `must first fail on`, and `TC-RBS-10` is
first shown red on an INSERT.

**It is a readable string and not a hash, and that is a decision with a reason.**
Nothing renders it (B14 rule 31 — it is never a visible value), so a digest
would buy nothing; and the `<runbook key>|` prefix is what
`close_the_ones_that_stopped_recurring` matches on to find *the items THIS
runbook raised*. A digest would need a second column to answer that, and a
column is a migration — where a prefix is an index scan on the unique index
that already exists.

⚠ **THE TENANT IS IN THE MATERIAL AS WELL AS IN THE CONSTRAINT.**
`UNIQUE (tenant, fingerprint)` already keeps two utilities apart, and
`TC-RBS-7`'s *must first fail on* is *a fingerprint that omits the tenant* — so
it is in both. Belt and braces on a multi-tenant key is the cheap side of that
trade.

═════════════════════════════════════════════════════════════════════════════
CLOSING ITSELF IS THE OTHER HALF, AND IT IS WHAT MAKES THE SCREEN USABLE
═════════════════════════════════════════════════════════════════════════════
`US-RBS-006`: *"Fix the tax region and re-run, and **the item closes itself** —
that is `J-RBS-1`'s assertion and the reason the item is keyed by fingerprint
rather than by a person's tick."*

So a run closes every OPEN item **this runbook raised** whose fingerprint it did
NOT raise this time. Three properties are load-bearing and each is asserted:

* **It is scoped to the runbook.** A grid run must not close the ladder's items.
* **It never closes an item a person owns the state of.** A `human_task` has no
  `source_run` and no runbook prefix, so it is outside the query by
  construction rather than by a flag somebody has to remember.
* **A reopened item keeps `created_at`.** The age a clerk sees is the first
  sighting, never the last — that is the whole value of the ageing column.

⚠ **A RUN THAT RAISED NOTHING STILL CLOSES.** That is the *fixed it* case and
it is the one an `if not findings: return` would break — the most natural line
to write here, and the one that would make `J-RBS-1` fail at its last step with
every other assertion green.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (hard-won law 7's second habit): a
runbook that declares no `findings()` raises nothing AND closes nothing, so a
lane that forgot the declaration would see an empty work list and no error. The
report is the check: `upsert` returns what it raised and what it closed, and
`close_run` puts both numbers on the run's `counts`, so *"raised 0"* is visible
beside *"walked 25"* instead of being an absence nobody can see.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.runbooks import models
from apps.runbooks.contract import Finding, RunbookDefinition

#: What a run puts on the counts so a reader can tell *raised nothing* from
#: *was never asked*. See the docstring's last paragraph.
COUNT_RAISED = "work_items_raised"
COUNT_CLOSED = "work_items_closed"

#: `work_items.status`. Two values and no third: a person may assign, resolve or
#: reopen, and a resolved item that recurs REOPENS rather than being written
#: again (`TC-RBS-006.2`).
STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"


def fingerprint(
    *, tenant_id: Any, runbook_key: str, finding: Finding
) -> str:
    """`<tenant>|<runbook>|<subject>|<kind>` — and **no run id, ever**.

    See the module docstring. The separator is `|` because none of the four
    parts can contain one: a tenant and a subject are uuids, a runbook key is a
    slug, and a finding kind is written by us.
    """
    subject = (
        f"{finding.subject_type}:{finding.subject_id}"
        if finding.subject_id
        else finding.subject_type or "-"
    )
    return f"{tenant_id}|{runbook_key}|{subject}|{finding.kind}"


def prefix_for(*, tenant_id: Any, runbook_key: str) -> str:
    """Everything this runbook has ever fingerprinted, for the closing half."""
    return f"{tenant_id}|{runbook_key}|"


def collect(definition: RunbookDefinition, view: Any) -> list[Finding]:
    """What the runbook says is waiting on a person, or nothing at all.

    ⚠ **A DECLARATION THAT IS ABSENT MEANS *THIS RUNBOOK RAISES NOTHING*, AND
    THAT IS DIFFERENT FROM ONE THAT RETURNED AN EMPTY LIST** — the first cannot
    close anything either, because it never raised anything. Both are lawful and
    the counts tell them apart.
    """
    if definition.findings is None:
        return []
    raised = definition.findings(view)
    return [f for f in raised if isinstance(f, Finding)]


def upsert(
    run: models.RunbookRun,
    definition: RunbookDefinition,
    findings: Sequence[Finding],
) -> dict[str, int]:
    """Write this run's findings, then close the ones that stopped recurring.

    ⚠⚠ **THE SAVEPOINT IS NOT THE TIDY OPTION** (hard-won law 14). One refused
    row must not lose the other twenty-four, and on PostgreSQL a bare
    `except IntegrityError: continue` loses the WHOLE transaction at COMMIT —
    while passing this repository's entire suite green, because
    `config/settings/test.py` is in-memory SQLite and SQLite has no
    aborted-transaction state at all. Two lanes found that independently on
    2026-08-29 in different modules. **Do not simplify the nested
    `transaction.atomic()` away.**

    ⚠ **THE RACE IS REAL AND IT IS WHY THIS IS A GET-THEN-WRITE UNDER A UNIQUE
    INDEX RATHER THAN A `get_or_create` I TRUST.** Two runs of the same runbook
    can close in the same second (a schedule and a person). The unique index on
    `(tenant, fingerprint)` is what actually decides it; the savepoint is what
    lets the loser carry on.
    """
    raised = 0
    seen: set[str] = set()
    now = timezone.now()
    source_kind = (
        models.WORK_ITEM_SOURCE_FINDING
        if definition.is_check
        else models.WORK_ITEM_SOURCE_EXCEPTION
    )

    for finding in findings:
        key = fingerprint(
            tenant_id=run.tenant_id, runbook_key=definition.key, finding=finding
        )
        seen.add(key)
        try:
            with transaction.atomic():
                existing = models.WorkItem.objects.filter(
                    tenant_id=run.tenant_id, fingerprint=key
                ).first()
                if existing is None:
                    models.WorkItem.objects.create(
                        tenant_id=run.tenant_id,
                        source_kind=source_kind,
                        source_run=run,
                        fingerprint=key,
                        title=finding.title,
                        weight=finding.weight,
                        subject_ref=finding.subject_ref,
                        fix_route=finding.fix_route,
                        status=STATUS_OPEN,
                    )
                else:
                    # ⚠ **`created_at` IS NOT IN THIS LIST AND THAT IS THE
                    # FEATURE.** *"The age a clerk sees is `created_at`, never
                    # the last sighting"* — thirty daily sweeps over one missing
                    # read are ONE item, THIRTY DAYS OLD. `auto_now` on
                    # `updated_at` records the last sighting separately.
                    models.WorkItem.objects.filter(pk=existing.pk).update(
                        source_run=run,
                        title=finding.title,
                        weight=finding.weight,
                        subject_ref=finding.subject_ref,
                        fix_route=finding.fix_route,
                        # A resolved item whose finding RECURS reopens, with its
                        # history — `TC-RBS-006.2`, whose *must first fail on* is
                        # a second row.
                        status=STATUS_OPEN,
                        resolved_at=None,
                        updated_at=now,
                    )
                raised += 1
        except DatabaseError:
            # One finding refused does not lose the rest. The savepoint above is
            # what makes that true on PostgreSQL; see the docstring.
            continue

    closed = close_the_ones_that_stopped_recurring(
        run, definition, still_raised=seen, at=now
    )
    return {COUNT_RAISED: raised, COUNT_CLOSED: closed}


def close_the_ones_that_stopped_recurring(
    run: models.RunbookRun,
    definition: RunbookDefinition,
    *,
    still_raised: set[str],
    at: Any,
) -> int:
    """**The item closes itself** — `J-RBS-1`'s last assertion.

    Every OPEN item this runbook raised whose fingerprint this run did not
    raise is resolved. Scoped by the fingerprint's `<tenant>|<runbook>|` prefix,
    so one runbook's run can never close another's item and a human task — which
    carries no runbook prefix at all — is outside the query by construction.

    ⚠ **IT RUNS EVEN WHEN THE RUN RAISED NOTHING.** *Nothing raised* is exactly
    the fixed-everything case, and an early return on an empty list is the most
    natural line to write here and the one that would break the last step of
    `J-RBS-1` with every other assertion still green.
    """
    stale = models.WorkItem.objects.filter(
        tenant_id=run.tenant_id,
        status=STATUS_OPEN,
        fingerprint__startswith=prefix_for(
            tenant_id=run.tenant_id, runbook_key=definition.key
        ),
    ).exclude(fingerprint__in=list(still_raised))
    return stale.update(status=STATUS_RESOLVED, resolved_at=at, updated_at=at)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-006 (EP-RBS-03; CR-075 wave H task H1)
# generated: 2026-09-07 by the CR-075 wave H build lane
# checklist: A✔ B✔ C✔ D=n/a(the routes are H2) E=n/a(the screen is H3) F✔ G✔ H=n/a(no 🔒 path: no idempotency key, no rating math, no ledger line)
# gates: pytest tests/test_us_rbs_006_work_items.py · G115 (the import census)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

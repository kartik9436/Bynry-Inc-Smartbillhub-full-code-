# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2842 (2026-08-31) — "the authorisation record has neither the
#           screen the PO declined nor the export the PO chose". The declined
#           option was honoured and the chosen one was not, and that reads as
#           compliance: `api.py` states in its own comments that a GET would
#           implement the option the PO DECLINED, which is correct and complete
#           about half the ruling, and nothing anywhere stated that the export
#           the PO DID choose was still missing.
# Story:    US-BIL-005 (S31 step 5 — the summary, the gate and the release)
# Rules:    BR-BIL-065 (PO ruling 2026-08-11, OQ-112 option B, verbatim: *"B An
#           export only"* — the release authorisation record is reachable as an
#           EXPORT and gets NO screen) · BR-BIL-056 (the phase-4 panel
#           RECALCULATES; this row does not, which is why it is the only answer
#           to *"what did I approve on 1 July?"*) · BR-BIL-058 (the gate is FIVE
#           separately recorded facts) · BR-SHL-016 (server-side export under
#           the caller's tenant context, 50,000-row cap) · BR-SHL-011 (the
#           export mirrors the list's own q/sort/dir/f.* state) · B14 rule 31
#           (no database id is the visible value of a field) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money carries its CHAR(3) currency)
# Tests:    06-backend/tests/test_def2842_release_export.py
# Impacts:  apps/billing/apps.BillingConfig.ready (registration) · the platform
#           export kernel apps/tenancy/exports.py (POST /exports)
# ───────────────────────────────────────────────────────
"""BR-BIL-065's export — the only readable answer to *"what did I approve?"*.

**THE RULING, AND WHY THIS FILE IS THE WHOLE OF IT.** The Product Owner was
shown two options for the release authorisation record on 2026-08-11 and chose
one in two words: *"B An export only"*. Option A — putting it back on the
phase-4 panel — was DECLINED in the same breath they ruled that the panel
recalculates live (BR-BIL-056), because the approved figures and the current
figures answer different questions and one screen showing both invites a reader
to take the wrong one.

**A RULING THAT SAYS *DO B, NOT A* IS CLOSED BY DOING B.** The repo recorded not
doing A — `api.py` says so in its own comments — and nothing recorded that B was
still missing. That is `DEF-2842`, and it is a shape worth naming: **honouring
the declined half of a ruling reads exactly like compliance.**

WHAT AN AUDITOR ASKS, AND WHAT THIS FILE ANSWERS
------------------------------------------------
*"What did we authorise on 1 July, who authorised it, and did they tick the
compliance box?"* Every column below is one of those questions:

  * **WHICH RUN** — the run's own number and its cycle, never a uuid (B14 rule
    31, and the assets export records the same decision in the same words: the
    number leads, the uuid is not a column).
  * **WHAT WAS SHOWN** — the account count, the bill count and the total with
    its currency, **as they stood at sign-off**. These are the stored columns
    and NOT a recomputation: a bill voided next week leaves the live panel and
    does not leave this file, which is precisely what BR-BIL-056's ruling
    preserved.
  * **THE FIVE FACTS OF THE GATE** — the four confirmations, each its own
    column because *"they confirmed"* must never be one undifferentiated tick,
    plus who and when, which is the fifth.
  * **WHETHER IT ACTUALLY WENT OUT** — `released_at`. Empty means authorised
    and not yet released, which is the state a crash between phase 4 and phase
    5 leaves behind, and an auditor reading a blank there is reading a real
    fact rather than a missing value.

⚠ **THE `summary` PAYLOAD IS DELIBERATELY NOT A COLUMN.** It is a
tenant-shaped JSON blob — their services, their account types — and a CSV cell
holding a JSON document is not a readable answer to anything; it is the file
refusing to choose. The four figures pulled out of it are the four the model
itself pulled out as columns *"because these four are what a person reads first
and what an auditor asks for"*, and that judgment is reused here rather than
re-taken. A per-category breakdown is a second, wider export and belongs to
whoever is asked for one.

⚠ **APPEND-ONLY MEANS A RUN CAN APPEAR TWICE, AND THAT IS NOT A DUPLICATE.** A
catch-up sub-run or a resumed batch writes a second row; both happened and both
were authorised by somebody. The file carries both, newest first, and the
`confirmed_at` column is what tells them apart. Collapsing them would delete the
evidence this record exists to hold.

⚠ **NO MONEY IS WRITTEN BY THIS FILE AND NONE IS RECOMPUTED.** It is a read of
one table under the caller's own tenant context. `BR-SHL-016`'s money-export
audit clause is about exports that move or expose money the caller could not
otherwise see; this exposes a figure the caller approved themselves.
"""

from __future__ import annotations

from typing import Any

from apps.billing import models
from apps.tenancy import exports as export_kernel
from apps.tenancy.exports import ExportColumn, ExportResource
from core import tenancy as core_tenancy
from core.pagination import ListParams

#: The sort vocabulary, and it is short on purpose. An authorisation record is
#: read by DATE almost always ("what went out in July?") and by RUN otherwise.
#: A sort key that names no column is a 500 waiting to happen, so the set the
#: export honours is stated here and nowhere else.
RELEASE_SORTS: tuple[str, ...] = ("confirmed_at", "released_at", "run_no", "total_amount")
RELEASE_DEFAULT_SORT = "confirmed_at"

#: `f.released=yes|no` — the one filter worth having, because *authorised but
#: not yet released* is a state somebody chases rather than browses. Declared
#: here so an undeclared `f.*` is ignored rather than becoming a query column a
#: client picked (`ListParams`' own contract).
RELEASE_FILTERS: tuple[str, ...] = ("released",)


def _select(params: ListParams) -> Any:
    """Every authorisation this tenant has recorded, newest confirmation first.

    ⚠ **`tenant_id` IS FILTERED EXPLICITLY EVEN THOUGH RLS FORCE WOULD REFUSE A
    CROSS-TENANT ROW ANYWAY** (CLAUDE.md rule 1). It is this module's own
    convention on a read that leaves the server as a file — the belt is worth
    the line when the failure mode is one utility's approvals in another
    utility's download.
    """
    rows = models.BillRunRelease.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    ).select_related("bill_run", "bill_run__cycle", "confirmed_by")

    released = (params.filters or {}).get("released", "")
    if released == "yes":
        rows = rows.filter(released_at__isnull=False)
    elif released == "no":
        rows = rows.filter(released_at__isnull=True)

    sort = params.sort if params.sort in RELEASE_SORTS else RELEASE_DEFAULT_SORT
    if sort == "run_no":
        key = "bill_run__run_no"
    else:
        key = sort
    prefix = "" if params.dir == "asc" else "-"
    # `id` breaks a tie, so two approvals recorded in the same second come out
    # in a stable order rather than in whatever order the planner returns —
    # a file that reorders between two downloads cannot be diffed.
    return rows.order_by(f"{prefix}{key}", "-id")


def _serialize(row: Any) -> dict[str, Any]:
    """One authorisation, as the columns below read it.

    Composed here rather than in a selector because there is no LIST endpoint
    for this resource and there is not going to be one — BR-BIL-065 is *"an
    export only"*, and inventing a served list to hang the export off would
    build the screen the Product Owner declined.
    """
    run = row.bill_run
    cycle = getattr(run, "cycle", None)
    confirmed_by = row.confirmed_by
    return {
        # B14 rule 31 — the run's own number leads. `run_no` is nullable on the
        # model, so a run allocated before the series existed exports an empty
        # cell rather than a uuid standing in for a name.
        "run_no": run.run_no or "",
        "cycle": getattr(cycle, "code", "") or "",
        "period_start": run.period_start,
        "period_end": run.period_end,
        "accounts": row.account_count,
        "bills": row.bill_count,
        "total_amount": row.total_amount,
        # CLAUDE.md rule 2 — an amount never travels without its CHAR(3)
        # partner, in a file least of all: a column of numbers with no currency
        # is the one thing a finance reader cannot reconstruct.
        "currency": row.currency,
        "compliance_confirmed": row.compliance_confirmed,
        "email_mandate_confirmed": row.email_mandate_confirmed,
        "sms_mandate_confirmed": row.sms_mandate_confirmed,
        "autopay_mandate_confirmed": row.autopay_mandate_confirmed,
        # WHO, as a name a person can read. `confirmed_by` is nullable, and an
        # empty cell there is a real fact — a release recorded with no user row
        # behind it — not a formatting gap.
        "confirmed_by": _person(confirmed_by),
        "confirmed_at": row.confirmed_at,
        "released_at": row.released_at,
    }


def _person(user: Any) -> str:
    """A user row as the words an auditor reads, never as an id (B14 rule 31).

    Falls back through the fields identity actually populates rather than
    assuming one: a deployment where `full_name` is blank must still say WHO,
    and an empty string is better than a uuid pretending to be a person.
    """
    if user is None:
        return ""
    for attribute in ("full_name", "name", "email", "username"):
        value = getattr(user, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


RELEASES = ExportResource(
    name="bill_run_releases",
    slug="bill-run-releases",
    module="billing",
    select=_select,
    serialize=_serialize,
    columns=(
        ExportColumn("run_no", "run_no"),
        ExportColumn("cycle", "cycle"),
        ExportColumn("period_start", "period_start", export_kernel.DATE),
        ExportColumn("period_end", "period_end", export_kernel.DATE),
        ExportColumn("accounts", "accounts", export_kernel.NUMBER),
        ExportColumn("bills", "bills", export_kernel.NUMBER),
        ExportColumn("total_amount", "total_amount", export_kernel.MONEY),
        ExportColumn("currency", "currency"),
        ExportColumn("compliance_confirmed", "compliance_confirmed", export_kernel.BOOLEAN),
        ExportColumn("email_mandate_confirmed", "email_mandate_confirmed", export_kernel.BOOLEAN),
        ExportColumn("sms_mandate_confirmed", "sms_mandate_confirmed", export_kernel.BOOLEAN),
        ExportColumn(
            "autopay_mandate_confirmed", "autopay_mandate_confirmed", export_kernel.BOOLEAN
        ),
        ExportColumn("confirmed_by", "confirmed_by"),
        ExportColumn("confirmed_at", "confirmed_at", export_kernel.TIMESTAMP),
        ExportColumn("released_at", "released_at", export_kernel.TIMESTAMP),
    ),
    sorts=RELEASE_SORTS,
    default_sort=RELEASE_DEFAULT_SORT,
    default_dir="desc",
    filters=RELEASE_FILTERS,
    # BR-REP-001: a money KPI must label its date basis, and this is not one —
    # it is an append-only log of approvals, so the filename segment says WHAT
    # KIND of file it is, exactly as the kernel's own comment prescribes.
    basis="event-time",
    period="full-list",
)


def register() -> None:
    """Called once from `BillingConfig.ready()`.

    Hard-won law 2 in one line: without this the resource is a dataclass nobody
    can reach, `POST /exports` answers 404 for its name, and the ruling stays
    unbuilt while the file that implements it exists — which is the same shape
    as `DEF-2842` itself, one layer along.
    """
    export_kernel.register_export_resource(RELEASES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2842 + BR-BIL-065 (04-docs/05-modules/07-billing/02-business-rules.md)
#         + apps/tenancy/exports.py (the kernel's own contract)
# generated: 2026-09-01 by the billing defect lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(BR-BIL-065 is "an export only" — the screen was DECLINED by the PO on 2026-08-11 and is not owed) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with `register()` not called from BillingConfig.ready()
#        the resource is absent from `registered_resources()` and the new suite
#        fails by name. Verbatim in the lane report.
# exceptions: (1) NO SCREEN, and that is the ruling rather than a deferral —
#         option A was declined on 2026-08-11 · (2) the `summary` JSON payload is
#         not a column; the four figures the model itself pulled out are · (3) a
#         run appears once per authorisation, so a catch-up sub-run adds a second
#         row rather than replacing the first
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

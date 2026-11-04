# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 tasks A1 (write and read back by reference), A4 (the join)
#           and A5 (the retention sweep) — 12-governance/11-change-requests.md
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — no query here runs without
#           `app.tenant_id`) · BR-AUD-002 (why the DETAIL lives here and not in
#           `audit_log`) · BR-AUD-007 (tenant from context, never a parameter) ·
#           BR-TEN-074 (a job that walks tenants sets context PER TENANT)
# Pattern:  `apps/audit/services.store_row` — the registered sink `core.audit`
#           calls. Same split, same reason: `core` imports no app model.
# Tests:    06-backend/tests/test_cr067_diagnostics.py
# ───────────────────────────────────────────────────────
"""The store behind `core.diagnostics` — write, read back by reference, prune.

THE THREE THINGS THIS FILE IS
------------------------------
1. **The sink.** `core.diagnostics` assembles a row and hands it here, exactly
   as `core.audit` hands one to `services.store_row`. One INSERT, nothing else.
2. **The read.** `by_reference("5F2B-9C1D")` — the join CR-067 §3 describes,
   done on a VALUE because there is no foreign key in either direction.
3. **The sweep.** CR-067 task A5: an expired record is gone, and its audit row
   still reads correctly without it.

⚠ **THE SWEEP'S ACCEPTANCE CRITERION IS ABOUT THE ROW IT DOES *NOT* TOUCH.**
A year later the permanent audit row still reads *"this failed, here is why in
plain words"* — the stable code, the fixed catalogue sentence and the
reference. What it can no longer do is be REBUILT into a test, and that is the
bargain CR-067 struck deliberately: the detail is what carries risk, so the
detail is what expires. A drawer that finds nothing for a reference must say so
as a normal state; `HAS_EXPIRED` below is the sentence for it and it exists so
two surfaces cannot invent two different ways of saying "gone".

TENANT SCOPING, AND WHY THE SWEEP TAKES ITS TENANTS AS AN ARGUMENT
-------------------------------------------------------------------
`error_diagnostics` is under `FORCE ROW LEVEL SECURITY`, so a platform-wide
`DELETE` with no `app.tenant_id` set deletes NOTHING — deny-by-default, working
exactly as designed. A sweep must therefore enter each tenant's context in turn
(BR-TEN-074's shape, the same one `apps/tenancy/reference_sweep.py` uses).

`sweep_expired()` takes the tenant ids **as a parameter** and enumerates
nothing. The platform registry belongs to `apps.tenancy`, and a read of it from
here would put a module boundary inside a retention job; the management command
`manage.py sweep_error_diagnostics` does the enumerating, which is where every
other cross-module sweep in this repo puts it.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from typing import Any

from django.db import transaction

from core import diagnostics as diagnostics_kernel
from core import tenancy as tenancy_kernel

from .diagnostic_models import ErrorDiagnostic

logger = logging.getLogger("smartbillhub.diagnostics")

#: The one sentence for "there is a reference, and no detail behind it". Kept
#: here so the drawer, the API and any future report cannot each invent their
#: own — an expired diagnostic is a NORMAL state and must not read like a fault.
#:
#: ⚠ **THE API DOES NOT SERVE THIS STRING, IT SERVES A `REASON` CODE BELOW, AND
#: THAT IS NOT A SECOND WORDING (CR-067 B2 / DEF-3321).** This product renders in
#: eleven languages; an English sentence out of a payload can only ever be one of
#: them. So the SCREEN owns the words, the SERVER owns the state, and this
#: constant stays what a log line, a shell and a report say. Two surfaces still
#: cannot invent two meanings, which is what this constant was always for.
HAS_EXPIRED = "the technical detail for this reference is no longer held"

#: The record is there and is being served.
REASON_HELD = "held"
#: The audit row named a reference and nothing is behind it — the record expired
#: (task A5), the writer refused a call site that tried to put a VALUE in it, or
#: the store was unavailable when it was written. **All three are NORMAL** and
#: none of them is a fault to report: the permanent audit row still carries the
#: code, the plain-words sentence and the reference, which is the bargain CR-067
#: struck deliberately.
REASON_NOT_HELD = "not_held"
#: The audit row is older than CR-067 task A4 and carries no reference at all,
#: so there is nothing to look up. Told apart from the case above ON PURPOSE:
#: "this failure predates the diagnostic" and "the detail expired" are different
#: facts about the world, and a screen that says the second when the first is
#: true has invented a record that never existed.
REASON_NO_REFERENCE = "no_reference"

#: The columns the sink writes, in the order the model declares them. Named
#: rather than `**row` so a key the kernel adds later cannot silently become a
#: column nobody reviewed.
STORED_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "reference",
    "trace_id",
    "error_code",
    "component",
    "exception_type",
    "exception_module",
    "exception_chain",
    "frames",
    "settings_in_force",
    "request_fields",
    "job_kind",
    "job_id",
    "step",
    "step_total",
    "audit_action",
    "release",
    "created_at",
    "expires_at",
)


class DiagnosticTenantMissing(RuntimeError):
    """A diagnostic was written or read with no tenant in context (hard rule 1)."""


def store_row(row: dict[str, Any]) -> None:
    """Persist one assembled diagnostic — the sink `core.diagnostics` calls.

    Deny-by-default like every other write in this product: a record with no
    tenant would be a row RLS can never show anyone again, which is a leak in
    the storage sense and a lie in the reporting sense. `capture()` catches this
    and logs it rather than breaking the run being described.
    """
    if not row.get("tenant_id"):
        raise DiagnosticTenantMissing(
            "a diagnostic needs tenant context (CLAUDE.md rule 1, BR-AUD-007). "
            "Enter core.tenancy.tenant_context(...) before the work that can fail."
        )
    ErrorDiagnostic.objects.create(**{name: row.get(name) for name in STORED_FIELDS})


def _tenant_or_refuse() -> Any:
    tenant_id = tenancy_kernel.current_tenant_id()
    if tenant_id is None:
        raise DiagnosticTenantMissing(
            "reading a diagnostic needs tenant context (CLAUDE.md rule 1, BR-AUD-007)."
        )
    return tenant_id


def _normalised(reference: str) -> str:
    """`5f2b9c1d`, `5F2B-9C1D`, ` 5f2b-9c1d ` → `5F2B-9C1D`.

    A person reads this reference off a screen and types it back, down a phone,
    into a search box. The dashes and the case are for THEM; matching on them
    would make the reference harder to use than the raw trace id it replaced.
    """
    return diagnostics_kernel.support_ref(reference)


def by_reference(reference: str) -> ErrorDiagnostic | None:
    """The diagnostic for one reference, inside the current tenant, or None.

    **None is a normal answer, not an error.** The record expired (task A5), it
    was refused because a call site tried to put a value in it, or the store was
    unavailable when it was written. In all three the permanent audit row still
    carries the reference and still reads correctly — see `HAS_EXPIRED`.
    """
    tenant_id = _tenant_or_refuse()
    normalised = _normalised(reference)
    if normalised == diagnostics_kernel.SUPPORT_REF_ABSENT:
        return None
    return (
        ErrorDiagnostic.objects.filter(tenant_id=tenant_id, reference=normalised)
        .order_by("-created_at")
        .first()
    )


def payload(record: ErrorDiagnostic) -> dict[str, Any]:
    """One diagnostic as the API serves it — CR-067 §5's six facts, and no more.

    **THE SHAPE IS THE ACCEPTANCE TEST, READ OFF §5 RATHER THAN OFF THE MODEL.**
    CR-067 §5 asks *"could somebody holding ONLY the diagnostic record write a
    failing test?"* and prints six lines to prove it. Each key below is one of
    the six things that answer takes:

        the exception     → `exception_type` · `exception_module` · `chain`
        where in the code → `frames`
        which job step    → `job` (`kind`, `id`, `step`, `of`)
        which build       → `release`
        the settings      → `settings_in_force`
        the request       → `request_fields` — NAMES, never a value

    plus the four that identify it: the reference, the full trace id, the stable
    error code and the component.

    ⚠ **THE ROW'S OWN `id` IS NOT IN HERE, AND ITS ABSENCE IS THE POINT.** B14
    rule 31 — PO 2026-08-31, *"no Databse ID on screen - that is a rule"* — and
    nothing on the drawer needs it: the record is addressed through the audit row
    it belongs to, and the value a person reads and dictates is the eight-
    character reference. A uuid that is never served cannot be rendered by a
    later lane that did not read this comment.

    ⚠ **`expires_at` IS SERVED AND IT IS THE ONLY HONEST ANSWER TO "HOW LONG IS
    THIS KEPT" (`OQ-1390`).** The window is `DIAGNOSTIC_RETENTION_DAYS`, a
    per-deployment setting, and it is STAMPED on the row at write time — so a
    utility that set 30 days is told its own date and never the platform default.
    A screen printing a number instead would state an unratified figure as fact
    twice over, which is why the previous lane took "90 days" back out of eleven
    catalogues.

    Nothing here reads a message: `str(exc)` is stored by no column (task A2),
    so there is nothing to redact on the way out.
    """
    return {
        "reference": record.reference,
        # The full 32 hex, so a server log can be grepped for the whole of it.
        # System-Admin-only, like everything else this function returns.
        "trace_id": record.trace_id,
        "error_code": record.error_code,
        "component": record.component,
        "exception": {
            "type": record.exception_type,
            "module": record.exception_module,
            "chain": record.exception_chain or [],
        },
        "frames": record.frames or [],
        "settings_in_force": record.settings_in_force or {},
        "request_fields": record.request_fields or [],
        "job": {
            "kind": record.job_kind,
            "id": record.job_id,
            "step": record.step,
            "of": record.step_total,
        },
        "audit_action": record.audit_action,
        "release": record.release,
        "captured_at": record.created_at.isoformat(),
        "kept_until": record.expires_at.isoformat(),
    }


def read_for_reference(reference: str | None) -> dict[str, Any]:
    """The whole answer for one reference: is it held, and if so what is in it.

    **THE THREE OUTCOMES ARE A CLOSED SET AND NONE OF THEM IS AN ERROR.** A
    caller gets `held` plus a `reason` from the vocabulary above, and the record
    itself only in the one case where there is a record. See `REASON_NOT_HELD`
    and `REASON_NO_REFERENCE` for why the last two are told apart.

    Tenant scope is `by_reference`'s (CLAUDE.md rule 1) — the id comes from
    context, never from a parameter, and another tenant's record is ABSENT here
    rather than refused.
    """
    if reference is None or not str(reference).strip():
        return {"held": False, "reason": REASON_NO_REFERENCE, "reference": None, "record": None}
    record = by_reference(reference)
    if record is None:
        return {
            "held": False,
            "reason": REASON_NOT_HELD,
            "reference": _normalised(reference),
            "record": None,
        }
    return {
        "held": True,
        "reason": REASON_HELD,
        "reference": record.reference,
        "record": payload(record),
    }


def recent(limit: int = 50) -> list[ErrorDiagnostic]:
    """The current tenant's newest diagnostics — bounded, never unfiltered."""
    tenant_id = _tenant_or_refuse()
    return list(
        ErrorDiagnostic.objects.filter(tenant_id=tenant_id).order_by("-created_at")[
            : max(1, int(limit))
        ]
    )


def sweep_expired(
    tenant_ids: Iterable[Any],
    *,
    now: dt.datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """CR-067 task A5 — delete every diagnostic past its own `expires_at`.

    One tenant at a time, inside that tenant's context, because the table is
    under `FORCE ROW LEVEL SECURITY` and a context-free DELETE would quietly
    delete nothing (BR-TEN-074 · CLAUDE.md rule 1).

    ⚠ **ONE TENANT'S FAILURE MUST NOT STOP THE REST, AND ON POSTGRES THAT TAKES
    A SAVEPOINT** — hard-won law 14, verbatim: *"once any statement errors
    inside a transaction, the transaction is aborted; every later query raises
    `InFailedSqlTransaction` and the work is lost at COMMIT anyway. A SAVEPOINT
    — a nested `transaction.atomic()` — is not the tidy option, it is the ONLY
    option."* The suite runs on in-memory SQLite, which has no aborted-
    transaction state and therefore **cannot show this**, so the nested
    `atomic()` below is load-bearing on the database nobody tests on by default.
    Do not "simplify" it away.

    ⚠ **IT WRITES NO `audit_log` ROW.** Hard rule 7 attaches the trail to a
    MONEY action; pruning a technical record is not one, it touches no customer
    data and no figure, and a row per tenant per nightly run would bury the
    tenant-specific failures the trail exists to surface. The run is recorded in
    the log and in the summary this returns. The judgment is written down in
    12-governance/02-decision-log.md rather than left to be inferred here.
    """
    moment = now or dt.datetime.now(dt.timezone.utc)
    swept: dict[str, int] = {}
    failed: dict[str, str] = {}
    total = 0
    # ⚠ `tenant_context` CLEARS on exit rather than restoring what was there
    # before (core/tenancy.py — a job's normal shape is to have no ambient
    # context, and clearing is the safe default THERE). This loop enters it once
    # per tenant, so without this the sweep would return having silently emptied
    # its CALLER's context and every query after it would be denied with nothing
    # visibly wrong. `apps/audit/services.write_archive_audit` records the same
    # trap and the same fix, found the same way; saved and restored here rather
    # than by changing the 🔒 kernel's contract for one caller.
    previous = tenancy_kernel.current_tenant_id()
    for tenant_id in tenant_ids:
        key = str(tenant_id)
        try:
            with tenancy_kernel.tenant_context(tenant_id):
                # The SAVEPOINT. See the docstring — law 14, and the default
                # suite cannot prove it.
                with transaction.atomic():
                    expired = ErrorDiagnostic.objects.filter(
                        tenant_id=tenant_id, expires_at__lte=moment
                    )
                    count = expired.count() if dry_run else expired.delete()[0]
        except Exception as exc:  # noqa: BLE001 — one tenant must not stop the rest
            logger.exception("diagnostic sweep failed for tenant %s", key)
            failed[key] = type(exc).__name__
            continue
        if count:
            swept[key] = count
            total += count
    if previous is not None:
        tenancy_kernel.set_current_tenant(previous)
    logger.info(
        "diagnostic sweep %s: %s record(s) past their retention across %s tenant(s); "
        "%s tenant(s) failed and were skipped. The audit rows they belonged to are "
        "untouched and still read correctly on their own.",
        "would remove" if dry_run else "removed",
        total,
        len(swept),
        len(failed),
    )
    return {
        "removed": total,
        "by_tenant": swept,
        "failed": failed,
        "dry_run": dry_run,
        "as_of": moment,
        "retention_days": diagnostics_kernel.retention_days(),
    }


def register() -> None:
    """Wire this store in as the kernel's diagnostic sink (apps.audit only)."""
    diagnostics_kernel.set_diagnostic_sink(store_row)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 tasks A1/A4/A5 (12-governance/11-change-requests.md §3 the approved shape, §6 the task table) + BR-AUD-007 + BR-TEN-074 + CLAUDE.md hard rules 1 and 7 and hard-won law 14
# generated: 2026-09-02 by the CR-067 backend lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09) — ⚠ AMENDED 2026-09-02 by the CR-067 B2/B3 lane: `payload()` and `read_for_reference()` below are the read `apps/audit/api.AuditEntryDiagnosticView` serves, and the S61 drawer draws it (hard-won law 1).
# gates: see the lane report
# exceptions: (1) the sweep writes NO audit row — hard rule 7 is about MONEY actions and this touches no customer data or figure; decision recorded in 12-governance/02-decision-log.md. (2) `sweep_expired` ENUMERATES NOTHING — the tenant ids are a parameter, so this module never reads the platform registry another module owns; the management command does that. (3) OQ-1390 (is 90 days right; own regime or audit's) is OPEN and is answered by a SETTING, so nothing here guesses a value.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-008 (EP-CWP-03) — the record, its numbering and its three
#           statuses · US-CWP-007 (what a guest report creates) · US-CWP-009
#           (what the tracked timeline reads)
# Rules:    BR-CWP-027 (free-text location; premises resolved by a clerk, not by
#           the form) · BR-CWP-012 (the record lives here and the portal reads
#           it through a seam) · BR-TEN-035 (a number is allocated INSIDE the
#           issuing transaction and is never reused) · CLAUDE.md hard rule 7
#           (every write lands an audit row) · CLAUDE.md hard rule 1 (tenant
#           scoping; RLS FORCE on the table)
# Tests:    06-backend/tests/test_us_cwp_008_interruption.py
# Impacts:  apps/portal/services.py (the guest report's one write point) ·
#           apps/customers/service_request_api.py (the clerk's status control) ·
#           apps/portal/seams/metering_seam.py (read-only)
# ───────────────────────────────────────────────────────
"""The interruption's own service — open it, move it, and answer who it hits.

⚠ **CREATION IS ROLE-GATED SINCE 2026-09-04, AND IT WAS DELIBERATELY NOT
BEFORE.** This docstring used to say the opposite in bold — *"creation takes no
actor role and that is the point"* — because `create_interruption` was reachable
from the GUEST EDGE, where there is nobody signed in at all. `CR-072` took that
door away: a passer-by's report is a service request now, and **a stranger's
form cannot settle whether something is an outage**. The only caller left is a
clerk who has read the reports and judged them real, so the function carries
`@require_role` like every other write in this file.

**That is a narrowing and not a tidy-up.** While the guest path existed, an
anonymous request from the public internet could insert a row into a `metering`
table; the guard was the narrowness of the arguments rather than a role. It is
now a role, and `PORTAL_REPORTER` — which carries none — raises `AUTH-002`
against it, so the old path cannot be re-opened by accident.

`create_interruption`, `set_status` and `set_affected_area` are all the clerk's
now, and that uniformity IS the security story of this module.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.metering import interruptions as interruption_models
from core import audit as core_audit
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

INTERRUPTION_SERIES = core_numbering.INTERRUPTION_REPORT  # `RP-{YY}-{0000}`

_MAX_TEXT = 2000


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _text(value: Any, limit: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] or None


def _audit(actor: Any, action: str, row_id: Any, **kw: Any) -> None:
    """CLAUDE.md rule 7. A guest write is audited with `actor_user_id = None`,
    which is the truthful answer — *"we do not know who asked, and that is
    expected on this path"* — rather than an invented user id."""
    core_audit.write_row(
        action=action,
        entity_type="interruption",
        entity_id=row_id,
        actor_user_id=_actor_id(actor),
        before=kw.get("before"),
        after=kw.get("after"),
    )


def interruption_row(row_id: Any, *, lock: bool = False) -> interruption_models.Interruption:
    """One interruption, tenant-scoped. Another tenant's row is a 404 and never
    a 403 (HR-1 — the boundary must not confirm the row exists)."""
    qs = interruption_models.Interruption.objects.filter(tenant_id=_tenant_id(), id=row_id)
    if lock:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def allocate_reference(row: interruption_models.Interruption) -> str:
    """`RP-26-0412`, from the tenant's own series, inside the caller's
    transaction (`BR-TEN-035`).

    Raises rather than inventing a number: a report handed to a stranger with a
    reference nothing can look up is worse than a refusal they can act on.
    """
    issue_date = (row.reported_at or timezone.now()).date()
    try:
        return core_numbering.next_number(INTERRUPTION_SERIES, issue_date)
    except core_numbering.NumberingError as exc:
        raise errors.SysError(
            errors.SYS_INTERNAL,
            message_key="metering.interruption.numberingUnavailable",
            params={"series": INTERRUPTION_SERIES},
        ) from exc


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def create_interruption(
    actor: Any,
    *,
    kind: str,
    location_text: str,
    reporter_name: str | None = None,
    reporter_phone: str | None = None,
    affected_area: Any = None,
    service_request_id: Any = None,
) -> interruption_models.Interruption:
    """One interruption, numbered, at `looking_into_it`. **A clerk's act.**

    ⚠ **`service_request_id` IS A ROLLBACK AFFORDANCE AND NOTHING WRITES IT.**
    `CR-072` reversed the link — `service_requests.interruption_id` is the live
    one, and many reports may point at one interruption. The parameter and the
    column survive one release so the previous behaviour is a code revert
    (`CR-072` §7); the wave that drops both is named in
    `apps/metering/interruptions.py`.

    ⚠ **`gas_smell` NEVER REACHES HERE.** It is refused by name rather than
    stored, because a row for it would sit on a queue and `US-CWP-007` TC-3 is
    the opposite of that: the form answers with a phone number and creates
    nothing. The refusal stays even though the guest edge is gone — a clerk
    opening an interruption from a report cannot reach it either, because no
    report row can carry the kind.

    ⚠ **`premises_id` IS NOT AN ARGUMENT.** `BR-CWP-027`: the address is free
    text resolved LATER, by a clerk. A signature that accepted a premises would
    invite a caller to guess one, and a wrong premises on an interruption is
    worse than none — it tells a customer their street is fine when it is not.
    """
    if kind not in interruption_models.STORABLE_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.interruption.kindUnknown",
            params={"value": str(kind)},
        )
    where = _text(location_text)
    if not where:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.interruption.locationRequired",
            params={"field": "location_text"},
        )
    with transaction.atomic():
        row = interruption_models.Interruption.objects.create(
            tenant_id=_tenant_id(),
            kind=kind,
            status=interruption_models.STATUS_LOOKING,
            reported_at=timezone.now(),
            location_text=where,
            reporter_name=_text(reporter_name, 200),
            reporter_phone=_text(reporter_phone, 60),
            affected_area=interruption_models.normalise_area(affected_area),
            service_request_id=service_request_id,
        )
        row.reference = allocate_reference(row)
        row.save(update_fields=["reference", "updated_at"])
        _audit(
            actor,
            "interruption.reported",
            row.id,
            after={
                "reference": row.reference,
                "kind": row.kind,
                "status": row.status,
                "location_text": row.location_text,
            },
        )
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_status(actor: Any, interruption_id: Any, *, status: str) -> interruption_models.Interruption:
    """The clerk's move: `looking into it → crew on site → resolved`.

    ⚠ **`resolved` IS TERMINAL AND A SECOND RESOLUTION IS REFUSED**
    (`US-CWP-008` TC-4) — *"the second resolution is not recorded as a new
    event"*. Refusing rather than folding it into a no-op is deliberate: a
    clerk pressing *Resolve* on a job somebody else closed an hour ago has
    learnt something, and a silent success teaches them nothing.

    ⚠ **THE CLOCK DOES NOT CLOSE A RECORD — A CREW DOES** (`TC-6`). Nothing
    here reads `expected_back_on`; an ETA in the past leaves the row open.
    """
    if status not in interruption_models.STATUSES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.interruption.statusUnknown",
            params={"value": str(status)},
        )
    with transaction.atomic():
        row = interruption_row(interruption_id, lock=True)
        before = row.status
        if status == before:
            # Idempotent on the SAME status — a double-click is one click
            # (CLAUDE.md rule 6). This is not the TC-4 case: that is `resolved`
            # → `resolved` reached from a screen that thought it was open.
            return row
        allowed = interruption_models.ALLOWED_TRANSITIONS[before]
        if status not in allowed:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CWP-027",
                message_key="metering.interruption.statusNotAllowed",
                params={"from": before, "to": status},
            )
        row.status = status
        row.resolved_at = timezone.now() if status == interruption_models.STATUS_RESOLVED else None
        row.save(update_fields=["status", "resolved_at", "updated_at"])
        _audit(
            actor,
            "interruption.status_changed",
            row.id,
            before={"status": before},
            after={"status": status},
        )
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_affected_area(
    actor: Any,
    interruption_id: Any,
    *,
    area: Any,
    expected_back_on: Any = None,
) -> interruption_models.Interruption:
    """*"Elm St, 1400–1500"*, and the time a crew expects supply back.

    An area naming a street with no premises is ACCEPTED (`TC-3`): the record
    is valid before we know who it touches. What is refused is an area with no
    street at all, because that is not an area.
    """
    shaped = interruption_models.normalise_area(area) if area is not None else None
    if area is not None and shaped is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.interruption.areaNeedsStreet",
            params={"field": "street"},
        )
    with transaction.atomic():
        row = interruption_row(interruption_id, lock=True)
        before = {"affected_area": row.affected_area, "expected_back_on": str(row.expected_back_on)}
        row.affected_area = shaped
        if expected_back_on is not None:
            row.expected_back_on = expected_back_on
        row.save(update_fields=["affected_area", "expected_back_on", "updated_at"])
        _audit(
            actor,
            "interruption.area_set",
            row.id,
            before=before,
            after={"affected_area": shaped, "expected_back_on": str(row.expected_back_on)},
        )
    return row


def affected_set(interruption_id: Any) -> dict[str, Any]:
    """Who this interruption touches: the premises, and how many units on them.

    A READ, and the only one this module publishes for the affected-area rule.
    An interruption with no area answers an empty set with a reason rather than
    an empty list on its own — *"an interruption can exist before we know who
    it touches"* is a state, not a blank.
    """
    row = interruption_row(interruption_id)
    rows = interruption_models.resolve_affected_premises(row.tenant_id, row.affected_area)
    return {
        "area": interruption_models.normalise_area(row.affected_area),
        "premises": [
            {"id": str(one.id), "address_line": one.address_line, "postal_code": one.postal_code}
            for one in rows
        ],
        "premises_count": len(rows),
        "unit_count": interruption_models.affected_unit_count(rows),
    }


def open_on_street(tenant_id: Any, location_text: str) -> interruption_models.Interruption | None:
    """An interruption already open on the same street, or None.

    `US-CWP-007` TC-7: a second report from the same street is **accepted**, and
    the screen says the street is already reported. ⚠ *"Two reports of one burst
    is the desired behaviour — we would rather hear twice than not at all."* So
    this answers a SENTENCE on the confirmation, never a refusal.

    The match is the street WORDS of the free-text location, which is as much
    as free text can honestly support: `"1408 Elm St, Austin TX 78702"` and
    `"Water coming up outside 1412 Elm St"` share `Elm St`.
    """
    street = street_words(location_text)
    if street is None:
        return None
    return (
        interruption_models.Interruption.objects.filter(tenant_id=tenant_id, location_text__icontains=street)
        .exclude(status=interruption_models.STATUS_RESOLVED)
        .order_by("-reported_at")
        .first()
    )


#: The suffixes that make a word a street name rather than a town or a state.
STREET_SUFFIXES: tuple[str, ...] = (
    "st",
    "street",
    "rd",
    "road",
    "ave",
    "avenue",
    "dr",
    "drive",
    "ln",
    "lane",
    "ct",
    "court",
    "row",
    "way",
    "blvd",
    "close",
    "cres",
    "terrace",
)


def street_words(location_text: str | None) -> str | None:
    """`"1408 Elm St, Austin TX 78702"` → `"Elm St"`, or None.

    ⚠ **A DELIBERATELY SMALL RULE, AND ITS LIMIT IS NAMED.** It finds the first
    word ending in a street suffix and returns it with the word before it. It
    will miss `"Grand Boulevard North"` and it will not understand `"the corner
    of Elm and Third"`. That is acceptable HERE and nowhere else in this
    module: the only thing it drives is the sentence *"someone has already
    reported this street"*, where a miss costs one missing sentence and a
    false positive costs one wrong sentence — never a refusal, never a row.
    The affected-area rule, which decides who is told their supply is off, does
    NOT use this: a clerk types the street there.
    """
    if not location_text:
        return None
    words = [w.strip(" ,.;:").lower() for w in str(location_text).split()]
    for index, word in enumerate(words):
        if word in STREET_SUFFIXES and index > 0:
            return f"{words[index - 1].title()} {word.title()}"
    return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-008@d6d31c46 (EP-CWP-03 story + BR-CWP-001..096 snapshot)
# generated: 2026-09-04 by the CR-068 wave B build lane
# checklist: A✔ B✔ C✔ D✔(customers/service_request_api.py) E✔(ServiceRequestDetailPage's Interruption section) F✔ G✔ H=deferred(the 🔒 half is migrations/0047_rls_interruptions.py)
# gates: pytest tests/test_us_cwp_008_interruption.py · run_gates · G81 (the portal reaches this only through apps/portal/services.py)
# exceptions: none — `create_interruption` carried NO @require_role until CR-072 (2026-09-04) because the guest edge reached it; that edge is gone and all three writes are now role-gated · `street_words` is a small rule whose only consumer is one sentence, stated with its limits
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

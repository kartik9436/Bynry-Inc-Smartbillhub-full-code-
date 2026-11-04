# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-042 (EP-CWP-08) — *Send your own reading: one validation,
#           two sources*. Screen: CWP-035 (blueprint `P21`)
# Defect:   DEF-CWP-10175 — gap E of the 2026-10-17 meter-reading ruling
#           (decision log *"WHERE A USER ENTERS A METER READING"*, PO verbatim
#           *"we need to clsoe these gaps"*)
# Rules:    BR-CWP-067 (exactly the same validation as a staff-entered read) ·
#           BR-CWP-074 (ACCEPTED first, then validated; a VALIDATION flag only
#           when the check objects; a PROVENANCE flag on EVERY customer reading
#           — a fourth read source `customer`, NOT `manual`; supersedes B2
#           `meter_source`'s three values) · BR-CWP-069 (a later real read must
#           not leave the customer charged twice) · BR-CWP-010 (a customer
#           reaches only their own account's meters) · BR-MET-129 (a warned
#           reading POSTS with its flags; an error refuses) · BR-MET-014 (the
#           source is a tag) · CLAUDE.md hard rules 1, 3, 4, 7
# Tests:    06-backend/tests/test_us_cwp_042_self_read.py
# Impacts:  apps/metering/services.py `_post_row` (reads the batch's
#           `source_kind` into `meter_reads.source`) · apps/portal/services.py
#           `submit_meter_reading` (the `meter_reading` write point) ·
#           apps/portal/seams/metering_seam.py
# ───────────────────────────────────────────────────────
"""A CUSTOMER's own meter reading — the portal's way into Meter Reads.

════════════════════════════════════════════════════════════════════════════
ONE VALIDATION, TWO SOURCES — THIS FILE ADDS A DOOR, NOT A SECOND SET OF RULES
════════════════════════════════════════════════════════════════════════════
`BR-CWP-067`: *"A customer-submitted reading runs through exactly the same
validation as a staff-entered one."* So nothing below judges a figure. The
reading is staged, validated and committed by the SAME three functions every
staff reading goes through — `stage_read_batch` → `validate_read_batch` →
`commit_read_batch` — exactly the path `commit_event_reads` (BR-MET-128) takes
for a move-in's opening read. A customer reading that skipped the thresholds
would be a route into billing nobody checked, which is the one thing the
blueprint's Figure 6 exists to forbid.

⚠ **WHY THE `__wrapped__` CALLS, AND WHY THEY ARE NOT A WAY AROUND A GUARD.**
Those three functions carry `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`, and a
portal customer is NOT a staff user and has no role (`BR-CWP-004`: separate
table, separate session, separate permission catalogue). The guard for THIS
door is the portal's own, and it is stricter than a role: the account comes off
the signed-in session intersected IN THE QUERY (`BR-CWP-010`), the meter must be
one CURRENTLY assigned to that account's unit, and the self-read switch must be
on. `metering.importers` and `payments.reversal` already call `__wrapped__`
for the same reason — the door checked, the body runs.

════════════════════════════════════════════════════════════════════════════
`BR-CWP-074` — ACCEPTED FIRST, THEN VALIDATED, AND TWO FLAGS
════════════════════════════════════════════════════════════════════════════
PO verbatim, 2026-09-04: *"we accept the reading - and then run the validation
and flag it if any issue; you will also ahve to flag that this reading is
reacievd from Cosnumer"*.

  (1) **THE VALIDATION FLAG** is the staff one, unchanged: a WARNED row posts
      with a mechanical `accept_with_flag` disposition and its outcomes travel
      onto the committed read in `rule_outcomes`, with the read's primary
      `status` (`high`, `low`, …) — exactly BR-MET-129's clause (1). A clerk
      sees it where a clerk sees every other flag.
  (2) **THE PROVENANCE FLAG** is `meter_reads.source = 'customer'` on EVERY
      reading this door writes, clean or not. It is NOT `manual`: manual means
      a person the utility SENT, which is precisely the distinction the ruling
      exists to keep. The batch is staged MANUAL-shaped (that is what the
      staging parser accepts) and its `source_kind` is re-stamped
      `CUSTOMER_SOURCE_KIND` while it is still STAGED and mutable
      (BR-MET-012/017) — the move `commit_event_reads` makes for
      `event_context` — so `_post_row` writes the fourth source AT INSERT and
      no committed row is ever updated to add it (hard rule 4).

⚠ **`customer` IS NOT IN `models.SOURCE_KINDS`, ON PURPOSE.** That tuple is
what the STAFF upload endpoint accepts, and a clerk must never be able to post
a file of readings labelled as the customer's own. This file is the only writer
of the value.

⚠ **AN ERROR STILL REFUSES, AND THAT IS NOT `BR-CWP-070` BEING IGNORED.** A
warning — *nineteen times your usual* — is accepted and flagged, which is the
whole of `BR-CWP-070`/`074`. An ERROR in this product's validation is a reading
the pipeline cannot post for ANYBODY without a human disposition: a figure
LOWER than the last one is `negative_usage`, and accepting it would post a
negative consumption. `US-CWP-042` TC-4 asks for exactly this: *"The low
threshold fires with a plain sentence; it is not silently accepted."* The
refusal names the rule; the screen writes the sentence (B14 rule 35).

════════════════════════════════════════════════════════════════════════════
`BR-CWP-069` — NEVER ON A BILL TWICE
════════════════════════════════════════════════════════════════════════════
Nothing new is built for it, and that is the point. A customer reading is an
ordinary committed head; the next real reading's consumption is measured FROM
it (`prior_value` is the previous head), so `153,040 → 153,300 (customer)
→ 153,400 (reader)` bills `260 + 100 = 360` gallons — exactly the dial's
movement. A same-day staff reading is kept beside it and `counted_reading`
(BR-MET-1189) picks the one that counts. The test asserts the sum.

⚠ **NO PHOTO.** `US-CWP-042` TC-11 — consumer upload is a signed deferral
(PO 2026-08-08, DF-4; `DEF-CWP-3611`). A posted file is not read here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from apps.metering import models, seams, selectors, services, validation
from core import audit as core_audit
from core import errors

#: `BR-CWP-074` — the fourth read source. Supersedes B2 `meter_source`'s three
#: (`ami`, `manual`, `import`); `models.READ_SOURCES` carries it.
CUSTOMER_SOURCE = "customer"
#: The batch tag that makes `_post_row` write `CUSTOMER_SOURCE`. Deliberately
#: absent from `models.SOURCE_KINDS` — see the module docstring.
CUSTOMER_SOURCE_KIND = "customer"
#: `BR-MET-142`'s method — WHO read the meter. The portal's *You sent it in*
#: (`portal_reads.HOW_SELF_READ`) keys on it. Stamped only where the tenant's
#: own `read_methods` list still carries it (`BR-AST-043`: the list is data).
SELF_READ_METHOD = "self_read"

#: The refusals this door raises, as message KEYS — eleven catalogues write the
#: sentences (B14 rule 35). Each is a field error on the input it is about, so
#: the screen ties the sentence to that input (accessibility question 3).
REFUSE_UNREADABLE = "portal.selfRead.refuse.unreadable"
REFUSE_FUTURE = "portal.selfRead.refuse.future"
REFUSE_BEFORE_LAST = "portal.selfRead.refuse.beforeLast"
REFUSE_LOWER = "portal.selfRead.refuse.lower"
REFUSE_NOT_POSTED = "portal.selfRead.refuse.notPosted"


def _register_heads(asset_ids: list[Any]) -> dict[tuple[str, str], Any]:
    """The newest committed head per (meter, register) — ONE query.

    `_read_heads()` is the set every consumer sees (BR-MET-016/053 heads,
    BR-MET-1189's counted reading), so the *last reading* a customer is shown
    is the one billing would price from, never a superseded row.
    """
    if not asset_ids:
        return {}
    rows = (
        selectors._read_heads()
        .filter(asset_id__in=asset_ids)
        .order_by("asset_id", "channel", "-read_at", "-id")
        .only(
            "id",
            "asset_id",
            "channel",
            "read_at",
            "current_value",
            "consumption",
            "unit",
            "days_since_prior",
            "multiplier",
        )
    )
    out: dict[tuple[str, str], Any] = {}
    for row in rows:
        out.setdefault((str(row.asset_id), row.channel), row)
    return out


def _expected_now(head: Any, *, today: date) -> str | None:
    """*Expected now — about 153,300* (`13-wireframe-delta.md` 35.9): the last
    dial figure moved on by the last period's own daily rate, or None.

    Arithmetic on two stored facts and nothing else — the head's consumption
    over its own `days_since_prior`, turned back into dial units by the
    multiplier it was taken under. It is a hint for a person about to type,
    NEVER a threshold: the judging is `validation.py`'s, unchanged.
    """
    if head is None or head.current_value is None or head.read_at is None:
        return None
    days = head.days_since_prior or 0
    consumption = head.consumption
    multiplier = head.multiplier or Decimal("1")
    if days <= 0 or consumption is None or consumption <= 0 or multiplier <= 0:
        return None
    elapsed = (today - head.read_at.date()).days
    if elapsed <= 0:
        return None
    per_day = consumption / multiplier / Decimal(days)
    return str((head.current_value + per_day * elapsed).quantize(Decimal("1")))


def meters_for_unit(unit_id: Any, *, today: date) -> list[dict[str, Any]]:
    """The meters a customer at this unit may read, each with its registers and
    the last reading on each — what `CWP-035` draws.

    ⚠ **ONLY METERS, ONLY THIS UNIT'S, ONLY THE CURRENT ONES.** The set is the
    ONE asset registry's current assignments (`seams.equipment_on_unit`,
    BR-AST-028) narrowed to devices somebody READS (`DEF-CUS-9753`'s
    categories) — a cart has no dial. A meter on the flat next door was never
    assigned here, so it is absent by construction (`BR-CWP-010`).

    ⚠ **NO DATABASE ID LEAVES THIS FUNCTION** (B14 rule 31). A meter is named
    by its SERIAL on screen and addressed by its meter number on the way back,
    which is the key every reading in this product is posted under.

    ⚠ **A REGISTER NOBODY HAS READ IS OFFERED AS THE FLAT METER'S `total`.**
    `reads_for_unit`'s own contract: an unread register is ABSENT, not zero —
    so a meter with no history offers one register with no last reading, and
    the screen states *no reading yet* rather than inventing a `0`.
    """
    rows = [
        row
        for row in seams.equipment_on_unit(unit_id, today=today)
        if row.get("category") in selectors.READ_DEVICE_CATEGORIES and row.get("asset_no")
    ]
    heads = _register_heads([row["asset_id"] for row in rows if row.get("asset_id")])
    out: list[dict[str, Any]] = []
    for row in rows:
        asset_id = str(row.get("asset_id"))
        mine = sorted(
            (head for (aid, _channel), head in heads.items() if aid == asset_id),
            key=lambda head: head.channel,
        )
        if not mine:
            asset = seams.meter_by_no(row["asset_no"])
            registers = [
                {
                    "register": models.CHANNEL_TOTAL,
                    "unit": getattr(asset, "unit", None),
                    "last_reading": None,
                    "last_read_on": None,
                    "expected_now": None,
                }
            ]
        else:
            registers = [
                {
                    "register": head.channel,
                    "unit": head.unit,  # hard rule 3 — never separated from the number
                    "last_reading": (
                        str(head.current_value) if head.current_value is not None else None
                    ),
                    "last_read_on": head.read_at.date().isoformat() if head.read_at else None,
                    "expected_now": _expected_now(head, today=today),
                }
                for head in mine
            ]
        out.append(
            {
                "meter": row["asset_no"],
                "serial": row.get("serial_no"),
                "service": row.get("service"),
                "where": row.get("where"),
                "registers": registers,
            }
        )
    return out


def _field(field: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {
        "field": field,
        "code": errors.VAL_FORMAT,
        "message_key": message_key,
        "params": params,
    }


def _refuse(field: str, message_key: str, **params: Any) -> None:
    raise errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=message_key,
        params=params,
        field_errors=[_field(field, message_key, **params)],
    )


def _parse_value(raw: Any) -> Decimal:
    """The dial figure, or a refusal on the `value` input. A reading is a
    non-negative finite number; `1,53,040`-style separators are a typing habit
    and are dropped, never interpreted."""
    text = str(raw if raw is not None else "").strip().replace(",", "").replace(" ", "")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        _refuse("value", REFUSE_UNREADABLE)
    if not value.is_finite() or value < 0:
        _refuse("value", REFUSE_UNREADABLE)
    return value


def _parse_day(raw: Any, *, today: date) -> date:
    text = str(raw or "").strip()
    if not text:
        return today  # the drawing's default — *Date you read it* opens on today
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        _refuse("read_on", REFUSE_UNREADABLE)
    raise AssertionError("unreachable")  # pragma: no cover


def _error_rules(row: Any) -> list[str]:
    return [
        str(outcome.get("rule"))
        for outcome in (row.rule_outcomes or [])
        if outcome.get("severity") == validation.ERROR
    ]


def _warned(row: Any) -> list[dict[str, Any]]:
    return [
        {"rule": outcome.get("rule"), "detail": outcome.get("detail") or {}}
        for outcome in (row.rule_outcomes or [])
        if outcome.get("severity") == validation.WARNING
    ]


def record_customer_read(
    *,
    unit_id: Any,
    meter: Any,
    register: Any,
    value: Any,
    read_on: Any,
    today: date,
    actor: dict[str, Any],
) -> dict[str, Any]:
    """Accept ONE customer reading for one register of a meter on `unit_id`.

    The caller (`apps.portal.services.submit_meter_reading`) has already
    resolved the unit from the signed-in session's own account and checked the
    self-read switch. `actor` is the portal identity for `audit_log` — a
    customer is not a `User`, so `actor_user_id` stays NULL and the payload
    names them (`portal_self_service._portal_actor`'s contract).

    Refusals, each a field error on the input it is about: an unreadable
    figure or date; a date AFTER `today`; a date BEFORE the register's last
    reading; a figure lower than the last one (`negative_usage`, US-CWP-042
    TC-4). A meter not on this unit answers the SAME 404 as a meter that does
    not exist (`BR-CWP-010`) — a customer cannot probe another household's
    meter numbers by watching which refusal comes back.

    Returns `{"received", "flagged", "checks", "used", "unit", "times_usual",
    "read_on", "reading"}` — `flagged` is `BR-CWP-074`'s validation flag, and
    `times_usual` is the HIGH rule's own ratio, rounded, for the sentence
    *about nineteen times your usual*. No id leaves (B14 rule 31).
    """
    offered = {row["meter"]: row for row in meters_for_unit(unit_id, today=today)}
    meter_no = str(meter or "").strip()
    chosen = offered.get(meter_no)
    if chosen is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    channel = str(register or "").strip() or chosen["registers"][0]["register"]
    target = next((reg for reg in chosen["registers"] if reg["register"] == channel), None)
    if target is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")

    figure = _parse_value(value)
    day = _parse_day(read_on, today=today)
    if day > today:
        _refuse("read_on", REFUSE_FUTURE)
    if target["last_read_on"] and day < date.fromisoformat(target["last_read_on"]):
        _refuse("read_on", REFUSE_BEFORE_LAST, last_read_on=target["last_read_on"])

    tags: dict[str, Any] = {
        "source_kind": "manual",
        "period_month": day.isoformat(),
        "rows": [
            {
                "meter_no": meter_no,
                "read_at": day.isoformat(),
                "reading": str(figure),
                "channel": channel,
                "note": "",
            }
        ],
    }
    if SELF_READ_METHOD in set(services.read_method_index().values()):
        tags["read_method"] = SELF_READ_METHOD

    with transaction.atomic():
        staged = services.stage_read_batch.__wrapped__(None, tags)
        batch = services._batch_row(staged["id"])
        # BR-CWP-074 (2) — the provenance flag, on the STAGED batch (mutable,
        # BR-MET-012/017) so `_post_row` writes it AT INSERT. The one writer.
        batch.source_kind = CUSTOMER_SOURCE_KIND
        batch.save(update_fields=["source_kind", "updated_at"])

        services.validate_read_batch.__wrapped__(None, batch.id)
        row = models.ReadImportRow.objects.get(tenant_id=batch.tenant_id, batch=batch, row_no=1)
        already = services._is_already_recorded(row)
        if row.severity == validation.ERROR and not already:
            rules = _error_rules(row)
            if validation.RULE_NEGATIVE_USAGE in rules:
                _refuse("value", REFUSE_LOWER, last_reading=target["last_reading"])
            # Any other error is one this product refuses for a clerk too
            # (BR-MET-129 (2)). The rule names travel; the screen writes one
            # sentence for all of them.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CWP-067",
                message_key=REFUSE_NOT_POSTED,
                params={"rules": rules},
            )
        warned = _warned(row)
        if already:
            # BR-MET-1189 (4) — the very same reading is already on file: it is
            # not refused and not stored twice. The customer is told RECEIVED.
            services.set_row_disposition.__wrapped__(
                None,
                batch.id,
                1,
                {
                    "disposition": "reject",
                    "reason": "BR-MET-1189: the same reading is already in the register",
                },
            )
        elif row.severity == validation.WARNING:
            # BR-CWP-074 (1) — ACCEPTED, then flagged. Mechanical, the ruling's
            # own clause and not a human judgment, exactly BR-MET-129 (1).
            services.set_row_disposition.__wrapped__(
                None,
                batch.id,
                1,
                {
                    "disposition": "accept_with_flag",
                    "reason": (
                        "BR-CWP-074: a customer's reading is accepted first and "
                        "flagged where the check objects; worked post-commit"
                    ),
                },
            )
        services.commit_read_batch.__wrapped__(None, batch.id, {"certified": True}, defer=False)
        posted = (
            models.MeterRead.objects.filter(tenant_id=batch.tenant_id, import_batch=batch)
            .order_by("created_at")
            .first()
        )
        if posted is None and not already:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref="BR-CWP-067", message_key=REFUSE_NOT_POSTED
            )
        core_audit.write_row(
            action="portal.meter_reading.submitted",
            entity_type="meter_read" if posted is not None else "read_import_batch",
            entity_id=posted.id if posted is not None else batch.id,
            actor_user_id=None,  # a portal customer is not a User (BR-CWP-004)
            after={
                "meter_no": meter_no,
                "register": channel,
                "reading": str(figure),
                "read_on": day.isoformat(),
                "source": CUSTOMER_SOURCE,
                "flagged": bool(warned) and not already,
                "checks": [one["rule"] for one in warned],
                "already_recorded": already,
                "actor": actor,
                "br_ref": "BR-CWP-074",
            },
        )

    high = next((one for one in warned if one["rule"] == validation.RULE_HIGH), None)
    times_usual = None
    if high is not None and high["detail"].get("ratio_pct"):
        times_usual = int(
            (Decimal(str(high["detail"]["ratio_pct"])) / Decimal(100)).quantize(Decimal("1"))
        )
    return {
        "received": True,
        "flagged": bool(warned) and not already,
        "checks": [] if already else [one["rule"] for one in warned],
        "used": (
            str(posted.consumption)
            if posted is not None and posted.consumption is not None
            else None
        ),
        "unit": posted.unit if posted is not None else target["unit"],
        "times_usual": times_usual,
        "read_on": day.isoformat(),
        "reading": str(figure),
    }


def is_customer_read(read: Any) -> bool:
    """`BR-CWP-074` (2) asked as a question — for any screen that needs it."""
    return getattr(read, "source", None) == CUSTOMER_SOURCE


__all__ = [
    "CUSTOMER_SOURCE",
    "CUSTOMER_SOURCE_KIND",
    "meters_for_unit",
    "record_customer_read",
    "is_customer_read",
]

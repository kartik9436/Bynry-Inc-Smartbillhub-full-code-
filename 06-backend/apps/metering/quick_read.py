# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · ADDITION 2026-08-26 — **W5 task 6, the quick single-
#           reading entry (S28's counter case).** PO verbatim: *"we will need
#           modpage to load single reading, if it is simple then modal"*.
#           Screens: S25 (the "Add reading" action) · S28 (the path it hands
#           off to when the meter is NOT simple)
# Story:    US-MET-007 (S28 steps 1–2, the manual grid this reuses) ·
#           US-MET-012 (S25, where the action lives)
# Rules:    BR-MET-140 (a counter reading on a meter with NO cycle is ACCEPTED
#           AND WARNED — PO 2026-08-27, quoted verbatim below) · BR-MET-049
#           (the plan-driven expected register set — what makes a meter
#           "simple") · BR-MET-059 (the channel model; flat meter = one `total`
#           channel) · BR-MET-129 (a collected reading is STORED — we may warn,
#           we may not reject) · BR-MET-122 (an OFF-cycle meter warns with a
#           reason; a meter in NO cycle is the neighbouring case) ·
#           BR-MET-131 (no read DRAWER — and why a capture MODAL is not one;
#           see below) · BR-MET-014 (batch tags inherit to every row) ·
#           BR-MET-012 (nothing posts before commit) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 3 (an explicit unit)
# Questions: OQ-422 **CLOSED 2026-08-27** — PO: *"(b) Accept and warn"*. The
#           reading POSTS and the absence is now a WARNING with a reason a
#           clerk can act on. The rule is BR-MET-140.
# Tests:    06-backend/tests/test_cr038_w5_bulk_and_quick.py
# Impacts:  apps/metering/api.py (`GET /reads/quick-context`) ·
#           07-frontend/src/features/metering/QuickReadModal.tsx
# ───────────────────────────────────────────────────────
"""What the quick single-read modal must know BEFORE it draws — and nothing else.

────────────────────────────────────────────────────────────────────────────
A DIFFERENT SURFACE. NOT A DIFFERENT PIPELINE. THIS IS THE WHOLE RULE.
────────────────────────────────────────────────────────────────────────────
A clerk with ONE reading at the counter should not walk a five-stage import
wizard, and the PO sanctioned a modal for it by name. What the modal must NOT
become is a second way for a reading to reach `meter_reads`.

**There is no write path in this file.** The reading the modal captures is
staged, validated and committed by exactly the three routes a 1,247-row CSV
uses, in this order and with no shortcut:

    POST /read-batches                   →  services.stage_read_batch
                                            (with `rows: [ONE ROW ]`, the same
                                             `read_import.parse_manual_rows`
                                             parser the S28 manual grid uses)
    POST /read-batches/{id}/validate     →  services.validate_read_batch
                                            (all sixteen VEE rules, unchanged)
    POST /read-batches/{id}/post         →  services.commit_read_batch
                                            (BR-MET-017's compliance stamp,
                                             BR-MET-018's idempotency key, the
                                             append-only commit)

So the counter read is exactly as validated, as audited, as idempotent and as
correctable as a row that arrived in a file. **A second write path for reads
would be a second place for the rules to be wrong**, and the rules are the
sixteen the whole product bills off.

This module exists for the ONE thing the modal cannot decide for itself: *is
this meter simple?*

────────────────────────────────────────────────────────────────────────────
WHY THIS DOES NOT CONTRADICT BR-MET-131, WRITTEN WHERE A READER WOULD ASK
────────────────────────────────────────────────────────────────────────────
BR-MET-131 (PO 2026-08-26) reads: *"no read drawer required"* — S29 opens as a
full PAGE and the drawer retires. A reader who meets a modal in the reads
surface a day later is entitled to think something slipped through, so:

  * **BR-MET-131 retired a DETAIL VIEW presented as a side panel.** Its subject
    is S29, the screen that DISPLAYS an existing read with its supersession
    chain, its compliance stamp and its corrections. A record with that much
    behind it needs a page, an address and a back button.

  * **This is a CAPTURE control for a record that does not exist yet.** It has
    four fields, no history to show, no URL worth sharing and one outcome. The
    PO asked for it by name — *"if it is simple then modal"* — in the SAME
    session that retired the drawer, which is the strongest evidence available
    that the two are different things to them.

A modal that captures one record and a drawer that displays a record are
different objects. Both statements are live law; neither is an exception to the
other.

────────────────────────────────────────────────────────────────────────────
"IF IT IS SIMPLE" IS MEASURED, NOT ASSUMED — AND IT IS MEASURED PER METER
────────────────────────────────────────────────────────────────────────────
CR-038 task 6: *"A MULTI-REGISTER meter (TOU/demand) is detected on selection
and the modal hands off to the full manual entry path ("this meter has 3
registers") rather than growing rows inside the modal — that is the "if it is
simple" boundary, applied per meter."*

The expected register set is BR-MET-049's, resolved by
`completeness.PlanRegisterResolver` from the meter's PLAN — not from its type
name and not from what it happened to report last month. One expected channel
means the modal is the right surface; two or more means it is not, and the
answer says how many and which, so the hand-off sentence names them.

**An UNRESOLVABLE expected set is not "simple".** A meter whose plan cannot be
read answers `simple: false` with the resolver's own reason, because guessing
`total` for a meter that might be time-of-use would file one register's reading
as the whole month's usage.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from core import errors
from core import tenancy as core_tenancy

from apps.metering import completeness, models, read_import, seams

#: The hand-off target when the meter is not simple — the full S28 manual path.
#: A constant so the frontend route and this sentence cannot drift apart.
FULL_ENTRY_SURFACE = "S28"

# ── BR-MET-140 · a meter on NO cycle: ACCEPTED AND WARNED ──────────────────
# PO verbatim, 2026-08-27, closing OQ-422: *"(b) Accept and warn"*.
#
# The reading POSTS — refusing was never offered, because the reading is real
# and the customer is standing in front of the clerk (BR-MET-129: *"we can give
# the warning, but we cannot reject the reading"*). **What changed on this date
# is only the warning.** The absence was already served and already shown; it is
# now stated as something to ACT ON, with the reason and the fix, so somebody
# puts the meter on a route.

#: The two shapes the absence can take, each with the action that ends it. One
#: declaration: the reason picks the sentence AND the remedy, so a screen can
#: never show a reason with somebody else's fix.
CYCLE_ABSENT_NO_ROUTE = "no_route"
CYCLE_ABSENT_ROUTE_HAS_NO_CYCLE = "route_has_no_cycle"

CYCLE_ABSENT_ACTIONS: dict[str, str] = {
    CYCLE_ABSENT_NO_ROUTE: "add_meter_to_route",
    CYCLE_ABSENT_ROUTE_HAS_NO_CYCLE: "assign_route_to_cycle",
}

#: ⚠ **`warning`, NOT `error`, AND THE TIER IS THE RULING.** Nothing is wrong
#: with the reading; what is wrong is our configuration. A danger tier here
#: would tell a clerk at a counter that the number they just took off a meter
#: is bad, which is the opposite of what the PO ruled.
CYCLE_ABSENT_SEVERITY = "warning"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _resolve_meter(meter_no: str | None, asset_id: str | None) -> Any:
    """The meter, by number or by id, WITHIN this tenant (hard rule 1).

    Both doors exist because both callers do: the modal opened from a meter's
    own page knows the id, and the modal opened from S25 has a clerk typing the
    number off the device in front of them.
    """
    asset = None
    if meter_no:
        asset = seams.meter_by_no(meter_no)
    if asset is None and asset_id:
        asset = seams.meter_by_id(asset_id)
    if asset is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.read.unknown_meter",
            params={"meter_no": meter_no or asset_id},
            field_errors=[
                {
                    "field": "meter_no",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "metering.read.unknown_meter",
                }
            ],
        )
    return asset


def _read_date(raw: str | None) -> date:
    """The read date, or today. Parsed by `read_import._parse_date` — the SAME
    parser the CSV path uses, so the modal cannot accept a date shape the file
    path would reject (and vice versa)."""
    if raw:
        parsed = read_import._parse_date(str(raw))
        if parsed is None:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="metering.cycle.bad_date",
                params={"read_at": raw},
            )
        return parsed.date()
    from django.utils import timezone

    return timezone.now().date()


def _registers(asset: Any, on_day: date) -> dict[str, Any]:
    """BR-MET-049's expected register set for this meter, and the verdict.

    `PlanRegisterResolver` is `completeness.py`'s, unchanged and un-copied —
    the same resolver the chase list and the coverage block use, so *"this
    meter has 3 registers"* in the modal and *"3 expected records"* on the
    chase list can never disagree.
    """
    expected = completeness.PlanRegisterResolver().for_asset(asset, service_date=on_day)
    channels = list(expected.channels) if expected.channels is not None else None
    if channels is None:
        # The resolver could not read this meter's plan. NOT simple — see the
        # docstring: guessing `total` for a possibly-TOU meter would file one
        # register's reading as the whole month.
        return {
            "simple": False,
            "channels": None,
            "channel_count": None,
            "default_channel": None,
            "absent_reason": expected.absent_reason,
            "hand_off_to": FULL_ENTRY_SURFACE,
        }
    return {
        "simple": len(channels) == 1,
        "channels": channels,
        "channel_count": len(channels),
        # The one register the modal writes into when it IS simple. Never a
        # hardcoded "total": a single-register meter whose plan names a
        # different channel gets that one.
        "default_channel": channels[0] if len(channels) == 1 else None,
        "absent_reason": None,
        "hand_off_to": None if len(channels) == 1 else FULL_ENTRY_SURFACE,
    }


def _cycle_and_period(asset: Any, on_day: date) -> dict[str, Any]:
    """The cycle and period this reading will belong to — DERIVED, then SHOWN.

    CR-038's period/cycle sanity statement, clause 4, verbatim: *"the quick
    single-read modal DERIVES cycle + period from the read date and the meter's
    cycle assignment and SHOWS them (the clerk confirms, never types)"*. And
    clause 1: *"The read date is the truth; the batch tag is the intent …
    Period membership is DERIVED from `read_at` against the cycle's calendar —
    never typed, never guessed."*

    The chain is the one BR-MET-079 already stamps at collection:
    asset → its service point's route → that route's cycle. A meter that
    resolves to no route, or a route on no cycle, gets `cycle: null` WITH a
    reason — never a blank the clerk is invited to fill in, and never a default
    cycle picked because one was needed.

    ⚠ **A METER ON NO CYCLE IS ACCEPTED AND WARNED — BR-MET-140, PO 2026-08-27
    (*"(b) Accept and warn"*), closing OQ-422.** The reading posts; this payload
    carries `cycle_absent` with the REASON, the SEVERITY (`warning`, never an
    error — nothing is wrong with the reading) and the ACTION that ends it, so
    the modal states something a clerk can act on instead of a quiet blank and
    **somebody fixes the route**.

    ⚠ **AND THE BATCH STILL CARRIES NO `cycle_id` AT ALL** — not an empty one.
    An empty tag is a claim; an absence is not. The warning is what makes the
    absence visible, which is the half BR-MET-140 added.
    """
    from apps.metering import services as metering_services

    route_id = metering_services.collection_route_id(asset)
    route = (
        models.Route.objects.filter(tenant_id=_tenant_id(), id=route_id)
        .select_related("cycle")
        .first()
        if route_id
        else None
    )
    cycle = route.cycle if route is not None and route.cycle_id else None
    period_month = date(on_day.year, on_day.month, 1)

    if cycle is None:
        reason = CYCLE_ABSENT_NO_ROUTE if route is None else CYCLE_ABSENT_ROUTE_HAS_NO_CYCLE
        return {
            "cycle": None,
            # BR-MET-140. `accepted` is on the wire beside the reason because
            # the FIRST thing a clerk needs to know is that their reading is
            # not being refused — hard-won law 1, the claim travels rather
            # than living in this docstring.
            "cycle_absent": {
                "reason": reason,
                "severity": CYCLE_ABSENT_SEVERITY,
                "accepted": True,
                "action": CYCLE_ABSENT_ACTIONS[reason],
                "rule_ref": "BR-MET-140",
            },
            "route": None if route is None else {"id": str(route.id), "code": route.code},
            "period_month": period_month.isoformat(),
            "read_window": None,
            "in_window": None,
        }

    window = metering_services._cycle_window_for(cycle, on_day)
    return {
        "cycle": {"id": str(cycle.id), "code": cycle.code, "name": cycle.name},
        "cycle_absent": None,
        "route": {"id": str(route.id), "code": route.code},
        "period_month": period_month.isoformat(),
        "read_window": (
            None if window is None else {"from": window[0].isoformat(), "to": window[1].isoformat()}
        ),
        # BR-MET-122: an off-window read is a WARNING with a reason, never a
        # refusal. Shown here so the clerk sees it BEFORE they commit rather
        # than as a flag on the list afterwards — the same information, one
        # step earlier, which is the entire value of the modal.
        "in_window": None if window is None else window[0] <= on_day <= window[1],
    }


def quick_entry_context(
    *, meter_no: str | None = None, asset_id: str | None = None, read_at: str | None = None
) -> dict[str, Any]:
    """Everything the modal draws before the clerk types a value. WRITES NOTHING."""
    _tenant_id()  # hard rule 1: refuse before any lookup runs
    on_day = _read_date(read_at)
    asset = _resolve_meter(meter_no, asset_id)
    registers = _registers(asset, on_day)
    return {
        "meter": {
            "id": str(asset.id),
            "asset_no": asset.asset_no,
            # Hard rule 3: the modal SHOWS this beside the value box. A clerk
            # typing 4,812 into a box with no unit is the shape rule 3 exists
            # to forbid.
            "unit": asset.unit,
            "multiplier": str(asset.multiplier) if asset.multiplier is not None else None,
            "service": getattr(getattr(asset, "service", None), "code", None)
            or getattr(asset, "service_code", None),
        },
        "read_at": on_day.isoformat(),
        "registers": registers,
        "cycle": _cycle_and_period(asset, on_day),
        # ⚠ THE PIPELINE, NAMED ON THE WIRE. The modal does not get to decide
        # where the reading goes, and a reader of the payload can see that it
        # does not: these are the three routes it must call, in order.
        "pipeline": {
            "stage": "POST /read-batches",
            "validate": "POST /read-batches/{id}/validate",
            "commit": "POST /read-batches/{id}/post",
            "note": "same_as_file_import",
        },
        "rule_refs": ["BR-MET-049", "BR-MET-059", "BR-MET-014", "BR-MET-140"],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 ADDITION 2026-08-26 (W5 task 6) + BR-MET-049/059/131 + the S28 pipeline; AMENDED 2026-08-27 for OQ-422 as ruled (BR-MET-140, accept and warn)
# generated: 2026-08-26 by the CR-038 W5 tasks 6/7/8 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint is in apps/metering/api.py) E=deferred(no-frontend-half — QuickReadModal.tsx is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr038_w5_bulk_and_quick.py tests/test_br_met_140_no_cycle_counter_read.py
# exceptions: E3 this module WRITES NOTHING and adds no endpoint that could — the modal stages/validates/commits through the three existing `/read-batches` routes, so there is exactly one write path for a read · E3 a meter whose expected register set is UNRESOLVABLE answers `simple: false` rather than defaulting to `total`: a wrong default would file one register's reading as a whole month's usage · E3 a meter on no route or a route on no cycle answers `cycle: null` with a WARNING carrying the reason and the action that ends it (BR-MET-140, PO 2026-08-27 *"(b) Accept and warn"*) — the reading posts, and the batch still carries no `cycle_id` field at all rather than an empty one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

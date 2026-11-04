# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
#           rule page — CR-009 · the HTTP half)   Screens: S8
# Rules:    BR-NOT-017 (ONE HOME for every notification rule — PO 2026-08-17) ·
#           BR-NOT-018 (an event with no trigger is drawn and refused by name) ·
#           BR-NOT-005 (queue only; NO synchronous send endpoint anywhere) ·
#           BR-NOT-013 (delivery is out of this release on every channel) ·
#           BR-IDN-009 (server-enforced RBAC IS the gating) ·
#           BR-SHL-025 (a forbidden control renders disabled WITH its reason) ·
#           BR-TEN-016 (a settings edit is audited) · CLAUDE.md rule 1 · rule 7
# Change:   CR-048 wave B task B9 — the coverage block on both GET responses:
#           what is built, what the requirement claimed, and how many customer
#           messages have wording and no rule. DERIVED, not typed in ·
#           **task B6, 2026-08-30 — `last_30_days` on every row and on the rule
#           page**: what was queued, what is held, and what this utility's own
#           switch suppressed. `delivered` and `bounced` stay NOT REPORTED.
# Tests:    06-backend/tests/test_cr_009_notification_rules.py ·
#           06-backend/tests/test_cr048_b_engine_on.py (CR-048 B9) ·
#           06-backend/tests/test_cr048_b6_b10.py (CR-048 B6)
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json (BE-11 TC05 diffs the snapshot) ·
#           07-frontend/src/features/notifications/NotificationRules.tsx
# ───────────────────────────────────────────────────────
"""SET-12's matrix and SET-12D's rule page, over HTTP.

THIN by law (B8 / LAW 0): parse → call the service → serialize. No ORM, no
clock, no send.

╔══════════════════════════════════════════════════════════════════════════╗
║  FOUR ROUTES, AND NOT ONE OF THEM TRANSMITS ANYTHING.                    ║
╚══════════════════════════════════════════════════════════════════════════╝
    GET  /notification-rules                 the SET-12 matrix — every event
    GET  /notification-rules/{event}         the SET-12D page for one event
    PUT  /notification-rules/{event}         save it — System Admin, audited
    POST /notification-rules/{event}/queue-test   ENQUEUE a test to yourself

**The fourth is deliberately not called `send` or `test-send`, and that is a
rule rather than a naming preference.** BR-NOT-005 and A11 Addendum r2 §4 make a
synchronous send endpoint a gate failure; the PO's ruling of 2026-08-17 asked
for the *infrastructure* — *"the moment we take the decison on ESP or SMTP … we
just need to plug it; rest of the infra will work"* — and the infrastructure is
a QUEUE ROW. `test_cr_009__no_send_endpoint_is_minted_by_this_surface` asserts
that neither `…/send` nor `…/test-send` resolves here, exactly as CR-007's own
surface does, so the rule stays visible instead of depending on nobody adding
one later.

────────────────────────────────────────────────────────────────────────────
THE PERMISSION RULE, AND WHOSE IT IS
────────────────────────────────────────────────────────────────────────────
PO ruling 2026-08-17, verbatim: *"APply setting permission rule we discussed
before"*. DEF-196 gave that rule a precise shape the same day, from A4's
`settings_lookups` row (`{"system_admin": "Full", "executive": "View"}`):

* **System Admin** edits notification rules.
* **Executive** READS them — every control visible and disabled carrying its
  reason (BR-SHL-025), never hidden.
* **Billing Clerk** has **no access at all**: A4 gives them no cell, and no
  cell is no access rather than read-only access.

So these views wear `SettingsReadAnyWriteSystemAdmin`, the class DEF-196 exists
for, and the SERVICE keeps its own `@require_role(SYSTEM_ADMIN)` underneath — a
write refuses twice, the narrower gate refusing first. Removing either one must
still leave the write refused, and the tests assert both.

⚠ The permission ruling answers who may CHANGE a rule. **Who RECEIVES a staff
notification was OQ-261 and is now RULED (PO 2026-08-17 → BR-NOT-021,
amended here 2026-08-18)**: the user who started the action, plus every active
System Admin for failures. Every staff event carries `staff_recipient_policy`
on the wire, and the service still refuses any attempt to SET one — the policy
is platform law, not a per-rule field.
"""

from __future__ import annotations

from datetime import time as time_cls
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import delivery_counts, models, rule_catalog, rule_service, settings_api
from core import errors
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The B12 §6a actor shape — id and ROLE from the session, never the body.

    `user` travels too because a test send goes to the SIGNED-IN PERSON's own
    address (CR-009: *"sends a test to the signed-in user's email/phone"*) and
    that address lives on the user row.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="notifications.payload_not_object"
        )
    return data


def _refused(detail: str, br_ref: str = "BR-NOT-017") -> errors.BizError:
    """A service refusal as the ONE catalog exception G9 allows.

    `RuleRefused` is deliberately not a catalog exception — the service is
    callable from a shell and from provisioning, and a catalog code carries an
    HTTP status — so the translation belongs here, the only layer that knows
    what HTTP is. The refusal's own sentence travels in `params.detail`.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key="notifications.rules.refused",
        params={"detail": detail},
    )


def _unknown_event(key: str) -> errors.BizError:
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-NOT-017",
        message_key="notifications.rules.unknownEvent",
        params={
            "detail": (
                f"{key!r} is not a notification event. The vocabulary is a CONSTANT "
                f"({', '.join(rule_catalog.EVENT_KEYS)}) — a tenant cannot invent an "
                "event, because only a writer in this codebase can fire one."
            )
        },
    )


def _time_field(raw: Any) -> Any:
    """`HH:MM` → `datetime.time`, or None. Wall-clock TENANT time (BR-NOT-009)."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.rules.timeFormat",
            field_errors=[{"field": "fixed_time", "code": errors.VAL_FORMAT}],
        )
    try:
        parts = [int(piece) for piece in raw.split(":")[:2]]
        return time_cls(parts[0], parts[1])
    except (ValueError, IndexError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.rules.timeFormat",
            field_errors=[{"field": "fixed_time", "code": errors.VAL_FORMAT}],
        ) from bad


#: What the platform will and will not do with these rules in this release,
#: served as DATA beside them. Not decoration: a matrix full of enabled toggles
#: on a deployment with no dispatcher is a true fact about stored flags and a
#: false impression about the product — the same posture the delivery dashboard
#: keeps by refusing to print "0 delivered".
RELEASE_POSTURE = {
    # ⚠ **AMENDED 2026-08-17 (CR-009 in-app lane) — THIS USED TO READ `False`
    # WITH THE REASON "nothing leaves the building", AND BOTH BECAME FALSE THE
    # DAY `in_app` LANDED.** A screen reading this flag decides whether to tell a
    # utility that switching a rule on will do anything, so leaving it at False
    # would have understated the product in exactly the direction that costs
    # trust the second somebody sees a message arrive.
    #
    # It is deliberately NOT flipped to a bare `True` either: three of the four
    # channels still cannot send a thing (BR-NOT-013), so a plain True would
    # overstate it in the other direction. The truthful shape is a LIST.
    "dispatch_runs_in_this_release": True,
    # ⚠ **`dispatchable_channels` IS DERIVED IN `_release_posture()` AND
    # `no_dispatcher_reason` IS GONE (`DEF-NOT-10537`, 2026-10-22).** The list
    # read `[in_app]` and the reason said print, email and text are queued but
    # *"none of them leaves the building"* — false from the day the Custom SMTP
    # adapter went live, and drawn above the matrix. PO 2026-10-22: *"Each
    # channel tells the clerk the truth about itself, in one short line"* —
    # that line is the Channel status card's (`settings_api.channel_lines`), so
    # the matrix carries no release sentence at all (B14 rule 33: rationale is
    # zero words on screen).
    # BR-NOT-013 — both are PROVIDER facts and nothing in this repo can write
    # them, so the "Last 30 days" rail reports SENT and names the other two as
    # unreported rather than drawing two zeros.
    # ⚠ **THIS FLAG IS ABOUT `delivered` AND `bounced` ONLY, AND CR-048 B6 DID
    # NOT FLIP IT.** It stays False because no provider adapter exists on any
    # channel and neither figure can ever be computed here. What B6 added is a
    # DIFFERENT rail: `last_30_days` on every row below counts what this
    # platform itself did — messages written, messages held, and messages this
    # utility's own switch stopped. Those are our own facts and they were being
    # drawn as zeros. A screen reading this flag to decide whether to draw the
    # rail at all would now be wrong; read `queue_counts_available` for that.
    "delivery_counts_available": False,
    # CR-048 B6. TRUE, and deliberately a separate key from the one above: the
    # two answer different questions and one flag for both is how "we cannot
    # know" and "nothing happened" came to render the same.
    "queue_counts_available": True,
    "queue_counts_window_days": delivery_counts.WINDOW_DAYS,
    # Provenance for support: 'delivered' needs a provider confirmation and
    # 'bounced' needs an ESP webhook, and the Custom SMTP adapter reports
    # neither. ⚠ AMENDED 2026-10-22 (`DEF-NOT-10537`): this read *"because
    # sending is not switched on"*, which stopped being true when email began
    # to send. The fact stays; the false reason goes. The screen draws its own
    # catalogue key (`notifications.rules.rail.deliveryUnreported`), in all
    # eleven languages; this stays on the wire for API readers.
    "delivery_counts_reason": "No provider reports these back yet.",
    # CR-009's requirement claims sixteen events and names fifteen — REPORTED
    # rather than resolved by inventing a row. See rule_catalog's docstring.
    # ⚠ Both are ALSO inside `coverage` below (CR-048 B9), which is where a
    # screen should read them: they are two thirds of one three-part fact and
    # splitting them across two places is how one of them gets rendered without
    # the other. These two keys stay for the screens already reading them.
    "requirement_claims_event_count": rule_catalog.REQUIREMENT_CLAIMS_EVENT_COUNT,
    "built_event_count": rule_catalog.BUILT_EVENT_COUNT,
}


def _release_posture() -> dict[str, Any]:
    """`RELEASE_POSTURE` plus CR-048 B9's coverage block.

    ⚠ **A FUNCTION AND NOT A CONSTANT, WHICH IS THE POINT OF B9.** The third
    count is DERIVED from the seeded template catalogue against the event
    catalogue (`rule_catalog.coverage`), so it is right on the day wave B10/B11
    adds an event and takes a class out of the gap — nobody has to remember to
    edit a number. A module-level dict would have frozen it at import, which is
    a different way of writing the note somebody forgets.

    CR-048 B9, verbatim: *"Report what is covered and what is not … as data in
    the response, not a note somebody remembers."*
    """
    return {
        **RELEASE_POSTURE,
        # The dispatcher's own verdict per channel (`DEF-NOT-10537`), so the
        # list is right the day a channel starts or stops sending.
        "dispatchable_channels": rule_service.dispatchable_channels(),
        "coverage": rule_catalog.coverage(),
    }


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def notification_rules(request: Any) -> Response:
    """`GET /notification-rules` — the SET-12 matrix.

    Every event, in the PO's own order, with its audience, its channels, its
    timing and its On state. Rows are created from the catalogue on first read,
    so a tenant that has never opened this screen still has a complete, stated
    configuration rather than an empty table (the same discipline
    `NotificationSettings` records).
    """
    require_tenant(request)
    views = rule_service.rules()
    # CR-048 B6 — the counters on the list, real. FOUR queries for the whole
    # matrix rather than four per row: `for_events` groups by `event_key` and
    # splits in Python, because a settings GET that already reads eighteen rules
    # must not also run seventy-two aggregates.
    #
    # ⚠ **NO `as_of` PARAMETER IS ACCEPTED HERE, and the service's own argument
    # is deliberately not exposed.** The window ends today in the TENANT's
    # timezone and the response STATES the dates it measured, so no reader has
    # to infer them. A `?as_of=` override would need a refusal sentence in all
    # eleven locale catalogues for a malformed value (G32), and no screen asks
    # for one — a parameter nothing passes is hard-won law 2 on an endpoint.
    # `delivery_counts.for_events(as_of)` still takes the date, which is how the
    # tests pin the arithmetic on a named day (BR-TEN-043).
    counts = delivery_counts.for_events()
    return Response(
        {
            "results": [
                {**view.as_wire(), "last_30_days": counts.get(view.event.key)} for view in views
            ],
            "count": len(views),
            "categories": list(rule_catalog.CATEGORIES),
            **_release_posture(),
        }
    )


@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def notification_rule(request: Any, event_key: str) -> Response:
    """`GET|PUT /notification-rules/{event}` — the SET-12D page.

    The PUT carries a PARTIAL change set and the response is always the whole
    page again (BR-TEN-024's atomic per-tab save, the shape every rule page in
    this product already uses). One transaction, one audit row, and the matrix
    the screen returns to is re-read from the server rather than patched
    client-side.
    """
    require_tenant(request)
    try:
        rule_catalog.event(event_key)
    except KeyError:
        raise _unknown_event(event_key) from None

    if request.method == "PUT":
        payload = _payload(request)
        changes: dict[str, Any] = {}
        for field in rule_service.EDITABLE_RULE_FIELDS:
            if field not in payload:
                continue
            changes[field] = (
                _time_field(payload[field]) if field == "fixed_time" else payload[field]
            )
        channels = payload.get("channels")
        if channels is not None and not isinstance(channels, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="notifications.rules.channelsNotObject"
            )
        unknown = sorted(set(payload) - set(rule_service.EDITABLE_RULE_FIELDS) - {"channels"})
        if unknown:
            raise _refused(
                f"{', '.join(unknown)} is not a notification-rule field. The editable set "
                f"is {', '.join(rule_service.EDITABLE_RULE_FIELDS)} plus per-channel "
                "settings under 'channels'. The escalation ladder is edited through "
                "/settings/collections — it has ONE store and this is not it. Who receives "
                f"a staff notification is ruled ({rule_catalog.STAFF_RECIPIENT_BR}) and is "
                "not a rule field."
            )
        try:
            rule_service.update_rule(
                event_key=event_key,
                actor=_actor(request),
                channels=channels,
                **changes,
            )
        except rule_service.RuleRefused as refusal:
            raise _refused(str(refusal)) from refusal

    view = rule_service.rule(event_key)
    return Response(
        {
            **view.as_wire(include_ladder=True),
            # CR-048 B6 — SET-12D's right rail. Served on the SAME key the list
            # uses, so one component reads both screens and a rail cannot be
            # right in one place and stale in the other.
            "last_30_days": delivery_counts.for_event(event_key),
            **_release_posture(),
        }
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def queue_test_message(request: Any, event_key: str) -> Response:
    """`POST /notification-rules/{event}/queue-test` — ENQUEUE a test to yourself.

    ⚠ **THE NAME IS THE CONTRACT.** This route writes a queue row and returns;
    it makes no provider call, and no route in this module may. BR-NOT-005's
    *"queue only, no synchronous send endpoint"* is intact and asserted by name.

    The response carries the provider seam's own verdict unchanged, plus the
    channel's own line from the Channel status card (`channel_line`,
    `DEF-NOT-10537`), so a System Admin who clicks the button is told what
    actually happened: *on its way* where the dispatcher will send it, and
    *queued*, with the channel's reason, where it will not. ⚠ AMENDED
    2026-10-22: this read *"it will not leave the building until an adapter is
    plugged in"* — false once the Custom SMTP adapter went live.
    """
    require_tenant(request)
    payload = _payload(request)
    channel = payload.get("channel")
    if not isinstance(channel, str) or not channel:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.rules.channelRequired",
            field_errors=[{"field": "channel", "code": errors.VAL_REQUIRED}],
        )
    try:
        result = rule_service.queue_test(
            event_key=event_key, channel=channel, actor=_actor(request)
        )
    except KeyError:
        raise _unknown_event(event_key) from None
    except rule_service.RuleRefused as refusal:
        raise _refused(str(refusal), br_ref="BR-NOT-005") from refusal
    return Response({**result.as_wire(), "channel_line": settings_api.channel_line(channel)})


urlpatterns = [
    path("notification-rules", notification_rules),
    path("notification-rules/<str:event_key>", notification_rule),
    path("notification-rules/<str:event_key>/queue-test", queue_test_message),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-017@cr009a17 (12-governance/11-change-requests.md → CR-009 in full including the three PO ruling sets of 2026-08-17 · 04-docs/05-modules/10-notifications/02-business-rules.md · 04-docs/01-spec/11-api-contracts.md Addendum r2 §4 (no synchronous send endpoint) · core/permissions.py SettingsReadAnyWriteSystemAdmin, DEF-196)
# generated: 2026-08-17 by story-coder (CR-009 SET-12/SET-12D lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — all three paths answered django.urls.exceptions.Resolver404 before config/urls.py named this module; the permission split was proved by calling PUT as an Executive (403) and GET as a Billing Clerk (403) before the class was attached; the OQ-261 refusal was proved by POSTing a staff_recipient and reading the NotImplementedError. Transcripts in the lane report.
# exceptions: (0) [CR-048 B9, 2026-08-29] `RELEASE_POSTURE` IS NO LONGER SERVED DIRECTLY — `_release_posture()` wraps it and adds `coverage`. A function and not a constant on purpose: the third count is derived from the seeded template catalogue against the event catalogue, so a module-level dict would have frozen it at import and gone stale the day wave B10/B11 lands. The two older count keys stay at the top level for the screens already reading them, and are also inside `coverage`, where a screen should read them — they are three parts of one fact. (1) NO SEND ROUTE AND NO TEST-SEND ROUTE. The fourth path is `queue-test` because it queues; `test_cr_009__no_send_endpoint_is_minted_by_this_surface` asserts `…/send` and `…/test-send` both answer Resolver404. (2) THE ESCALATION LADDER IS NOT WRITTEN HERE — SET-12D reads it on this page and saves it through tenancy's existing `PUT /settings/collections`, so the five ruled figures keep ONE store. (3) [AMENDED 2026-08-18] NO STAFF RECIPIENT FIELD — the recipient is RULED (BR-NOT-021, OQ-261 closed): still refused at the service boundary, now quoting the ruling, and every staff row carries `staff_recipient_policy`. (4) NO "LAST 30 DAYS" DELIVERED/FAILED COUNTS — BR-NOT-013 makes both provider facts nothing in this repo can write; `delivery_counts_available: false` travels with its reason.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

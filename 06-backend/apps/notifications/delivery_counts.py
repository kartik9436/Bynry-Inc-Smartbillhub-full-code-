# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
#           rule page)   Screens: S8 (Settings → Notifications) · SET-12D's
#           "Last 30 days" right rail
# Rules:    BR-NOT-013 (delivery is out of this release on EVERY channel — so
#           `delivered` and `bounced` are NOT REPORTED, never zero) ·
#           BR-NOT-017 (one home for every notification rule) ·
#           BR-NOT-024 (print is the floor on every customer document — which is
#           what makes a suppression recordable at all) ·
#           BR-PAY-018 (paper suppression on a bad address — what `held` means) ·
#           BR-TEN-043 (the business date is an ARGUMENT, never assumed) ·
#           BR-SHL-025 (an absent figure renders WITH its reason) ·
#           CLAUDE.md rule 1 (tenant scoping; RLS FORCE)
# Change:   CR-048 wave B task B6 — *"per-event delivery counts, last thirty
#           days … real numbers instead of zeroes"*
# Tests:    06-backend/tests/test_cr048_b6_b10.py
# Impacts:  apps/notifications/rules_api.py (both GET responses carry this) ·
#           apps/notifications/models.py (`event_key`, `rule_suppressed_channels`
#           — the two columns this reads) · apps/notifications/services.py
#           (the ONE writer that stamps them) ·
#           07-frontend/src/features/notifications/NotificationRules.tsx
# ───────────────────────────────────────────────────────
"""The "Last 30 days" rail, counted from what this platform actually did.

╔══════════════════════════════════════════════════════════════════════════╗
║  THREE NUMBERS ARE COUNTED AND TWO ARE REFUSED, and the refusal is the   ║
║  more important half.                                                    ║
║                                                                          ║
║  COUNTED  · queued      — messages this platform WROTE for the event     ║
║           · held        — of those, the ones held back and not sent      ║
║           · suppressed  — documents this utility's own rule stopped      ║
║                                                                          ║
║  REFUSED  · delivered   — nobody is telling us; there is no provider     ║
║           · bounced     — same                                           ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
WHY `delivered` IS NOT DERIVED FROM `queued`, WHICH IS THE ONE TEMPTING LIE
────────────────────────────────────────────────────────────────────────────
Every row this counts is a row on a QUEUE. BR-NOT-013 puts delivery out of this
release on every channel, and `delivery_ops.UNPOPULATED_STATUSES` records the
consequence: nothing in this repo ever writes `delivered` or `bounced`, because
both are facts a PROVIDER reports back and no adapter exists on any channel.

So a `delivered` count taken from queued rows would not be an approximation —
it would be a number that says "12 customers received this" about twelve
letters sitting in a table. The rail reports both as UNAVAILABLE with the
reason, which is the discipline the delivery dashboard already keeps
(`RELEASE_POSTURE.delivery_counts_reason`: *"A zero here would look like every
message had failed, which is not what is happening."*). The same argument runs
the other way and is why this file exists at all: **printing zero where a real
number is available is the same failure in the opposite direction**, and until
today the rail printed zeros for all five.

────────────────────────────────────────────────────────────────────────────
WHAT EACH COUNTED NUMBER MEANS, EXACTLY, BECAUSE A RAIL CANNOT CARRY A CAVEAT
────────────────────────────────────────────────────────────────────────────
**`queued`** counts `outbound_messages` rows WRITTEN in the window, whatever
status they now hold. It is per CHANNEL, because the queue is (BR-BIL-016: one
delivery record per document per channel), so a bill on print + email is two.
`documents` is the same set counted by distinct source, for a screen that wants
"how many customers heard from us".

**`held`** is `held = TRUE` (BR-PAY-018) — written, not dispatched, not lost.
It is a SUBSET of `queued` and is deliberately not subtracted from it: a held
letter was still produced, and a rail where the two numbers do not add up is a
rail nobody trusts.

**`suppressed`** counts DOCUMENTS whose `rule_suppressed_channels` names the
channel — this utility's own SET-12 switch removing a channel the writer asked
for. Distinct by (source_type, source_id, copy_no) rather than by row, because
one document's suppression is stamped on every surviving row of that document
and counting rows would multiply it by the channels that survived.

────────────────────────────────────────────────────────────────────────────
⚠ THE ONE THING THIS CANNOT COUNT, STATED RATHER THAN LEFT TO BE DISCOVERED
────────────────────────────────────────────────────────────────────────────
A suppression rides the SURVIVING row of the document it is about. For every
customer document that is always at least one row — BR-NOT-024 makes print the
floor on `invoice`, `payment`, `notice` and `plan`, and a floor channel cannot
be switched off. **But a source kind with NO floor whose rule suppressed every
channel writes no row at all, so there is nothing to stamp and nothing to
count.** That is `bulk_action`, `test` and `move`: the two staff alerts, the
rule test button, and B10's two move messages.

For those events the suppression figure is served as UNAVAILABLE with that
reason rather than as zero — because zero would tell a System Admin who has just
switched *Move-in welcome* off that their switch is doing nothing, which is the
exact opposite of the truth.

────────────────────────────────────────────────────────────────────────────
AND ZERO ITSELF IS AMBIGUOUS, SO THE ROW SAYS WHICH ZERO IT IS
────────────────────────────────────────────────────────────────────────────
`queued: 0` has two completely different meanings — *nothing happened this
month*, and *no writer in this codebase has ever fired this event*. Six events
are in the second state by construction (BR-NOT-018: three field-work on OQ-249,
three staff/system on OQ-262) and would read as a quiet month forever.
`ever_attributed` separates them: false means this platform has never once
written a row for this event, which is a fact about the BUILD and not about the
utility's month.

────────────────────────────────────────────────────────────────────────────
THE WINDOW, AND THE ONE CLOCK READ IN THIS MODULE
────────────────────────────────────────────────────────────────────────────
`as_of` is the business date and is an ARGUMENT (BR-TEN-043). Passed nothing,
this file reads today in the TENANT's own timezone — the single clock read here,
and it is deliberate rather than an oversight:

* BR-TEN-043 governs EVENT time — the date a business fact is recorded must be
  the clerk's, and nothing here records a fact. This is a view, and *"the last
  thirty days"* has no meaning without a today.
* The alternative was refusing to compute unless a caller supplies a date,
  which would leave the rail blank on the screen it was built for.
* The window's start and end travel in the response, so the screen states what
  it measured and two readers cannot disagree about which thirty days.
* The tenant's timezone, not the server's, so a utility's month boundary is
  theirs (`tenancy_seam.tenant_timezone`).

Nothing here writes. Every query is filtered by `app.tenant_id`'s tenant under
RLS FORCE (hard rule 1) — there is no tenant parameter for a caller to widen.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.notifications import models, rule_catalog, tenancy_seam
from core import errors
from core import tenancy as core_tenancy

#: The rail's own name for its window. THIRTY DAYS is CR-009's requirement
#: (*"Last 30 days"*) and it is a constant here so the number the screen prints
#: and the number the query uses cannot drift apart.
WINDOW_DAYS = 30

#: The two provider facts, and the sentence each is served with. Kept beside the
#: counts rather than in the screen, for `RELEASE_POSTURE`'s reason: a reason
#: that lives in a component is a reason nobody can grep when it stops being
#: true.
NOT_REPORTED: dict[str, str] = {
    "delivered": (
        "Nobody is reporting deliveries back to us yet, because sending is not "
        "switched on. Every message below was written and is waiting; a "
        "'delivered' figure would mean a provider had confirmed it, and there "
        "is no provider on any channel."
    ),
    "bounced": (
        "A bounce is reported by an email provider, and there is no email "
        "provider connected. A zero here would read as 'nothing bounced' when "
        "the truth is that nothing has been sent to bounce."
    ),
}

#: ⚠ **THE SENTENCES ABOVE STOPPED BEING TRUE ON 2026-09-04 FOR ANY UTILITY
#: THAT CONNECTED ITS OWN MAIL SERVER, AND NOTHING NOTICED (`CR-069` wave F,
#: `BR-INT-027`).** Both say *there is no provider* — which was simply a fact of
#: the product until wave E shipped the SMTP adapter. From that day a utility
#: could connect a mailbox, press *Save and test*, watch a real message arrive,
#: and then read on this dashboard that *there is no email provider connected*.
#:
#: **The reason is still `not reported` and the figure is still not zero** — a
#: mailbox genuinely cannot tell us what bounced, because SMTP hands a message
#: to a server and a bounce comes back hours later as a new email to a human.
#: What changed is WHY, and a reason that has quietly become false is hard-won
#: law 1, not a wording preference: it reads as a product that has not noticed
#: what the utility just did.
#:
#: ⚠ **AND IT IS FOR EVER, NOT YET.** A mailbox will never gain a feedback path;
#: only a bulk email service declares one (`manifests/sendgrid.py` and
#: `manifests/postmark.py`, each with a `receive_feedback` operation; the file
#: was `email_bulk.py` until `CR-115-BRC05` named both vendors on 2026-09-17).
#: So this sentence must not soften into a zero on the day
#: the connection starts looking healthy — that is the substitution
#: `BR-INT-027` forbids by name.
NOT_REPORTED_MAILBOX: dict[str, str] = {
    "delivered": (
        "Your own mail server accepts each message and does not report back on "
        "what happened next, so there is no 'delivered' figure to show. The "
        "count of messages we handed it is above."
    ),
    "bounced": (
        "Your own mail server cannot tell us what bounced — a bounce comes back "
        "hours later as an email to a person, not as a report to us. A zero "
        "here would read as 'nothing bounced', which we do not know."
    ),
}


def _not_reported_reasons() -> dict[str, str]:
    """Which pair of sentences is true for THIS tenant right now.

    Read through `provider_seam`, which is the one seam (`BR-NOT-005`), and
    fails to the original pair: a seam that cannot answer must not be rendered
    as a fact, and the older sentence is the safer of the two to be wrong with.
    """
    from apps.notifications import provider_seam

    try:
        status = provider_seam.provider_status("email")
    except Exception:  # pragma: no cover — a broken read must not break the rail
        return dict(NOT_REPORTED)
    if not status or not status.get("connected"):
        return dict(NOT_REPORTED)
    if status.get("reports_feedback"):
        # A provider that WILL report and has not yet. Neither sentence fits and
        # inventing a third here would be this lane guessing at wave F's
        # feedback door; the honest one is the original until that door lands.
        return dict(NOT_REPORTED)
    return dict(NOT_REPORTED_MAILBOX)

#: Source kinds with NO print floor (`services.CHANNEL_FLOOR_BY_SOURCE`). An
#: event whose messages ride one of these can be suppressed to NOTHING, and a
#: suppressed-to-nothing document leaves no row to carry the fact.
#:
#: Derived from the floor map rather than typed out, so a source kind that gains
#: a floor tomorrow leaves this set on the same commit and no sentence goes
#: stale (hard-won law 1).
SUPPRESSION_UNRECORDABLE_REASON = (
    "A message this utility switched off entirely leaves no row to record it "
    "on, and this event's messages are not the kind that always print "
    "(BR-NOT-024 makes print the floor on bills, receipts, notices and plan "
    "letters — not on this). So the switch IS working; what cannot be counted "
    "is how many times it fired."
)


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _floorless_source_types() -> frozenset[str]:
    """Source kinds carrying no print floor, read from the floor map itself."""
    from apps.notifications import services

    return frozenset(
        kind for kind in models.SOURCE_TYPES if not services.CHANNEL_FLOOR_BY_SOURCE.get(kind)
    )


def _suppression_recordable(
    event: rule_catalog.EventClass, floorless: frozenset[str], observed: frozenset[str]
) -> bool:
    """Can a full suppression of this event leave a row behind to be counted?

    Two inputs, in this order, and the order is the point:

    1. **What the event DECLARES** (`EventClass.source_type`). Written down by
       the lane that wired the writer, so it answers correctly for an event that
       has never fired — which is exactly when a wrong answer would be believed
       (*"I switched it off and the count still says 0"*).
    2. **What the rows SHOW**, for every event that declares nothing. A measured
       floorless kind is proof; a measured floored kind is proof the other way.

    An event that declares nothing and has written nothing is treated as
    recordable, because every source kind but three carries a print floor and
    the three that do not are all declared above.
    """
    if event.source_type is not None:
        return event.source_type not in floorless
    return not (observed & floorless)


def window(as_of: date | None = None) -> tuple[date, date, datetime, datetime]:
    """`(start_date, end_date, start_at, end_at)` for the last `WINDOW_DAYS`.

    Inclusive of both end days, half-open in datetimes — `[start 00:00, end+1
    00:00)` — so a message written at 23:59 on the last day is inside it and
    none is counted twice. Both boundaries are the TENANT's midnight.
    """
    zone = tenancy_seam.tenant_timezone()
    end_date = as_of or timezone.now().astimezone(zone).date()
    start_date = end_date - timedelta(days=WINDOW_DAYS - 1)
    start_at = datetime.combine(start_date, time.min, tzinfo=zone)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
    return start_date, end_date, start_at, end_at


def _blank_row(event: rule_catalog.EventClass) -> dict[str, Any]:
    return {
        "queued": 0,
        "documents": 0,
        "held": 0,
        "suppressed": 0,
        "by_channel": {
            channel: {"queued": 0, "held": 0, "suppressed": 0} for channel in event.channels
        },
    }


def for_events(as_of: date | None = None) -> dict[str, dict[str, Any]]:
    """Every event's rail, in FOUR queries whatever the event count.

    Per-event queries would be sixty on a fifteen-row matrix, inside a settings
    GET that already reads the rules — so the aggregation groups by `event_key`
    and the split is done in Python over a handful of rows.
    """
    tenant_id = _tenant_id()
    start_date, end_date, start_at, end_at = window(as_of)
    rows = {event.key: _blank_row(event) for event in rule_catalog.EVENTS}

    # 1 · queued + held, per event × channel. One GROUP BY.
    windowed = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id,
        event_key__isnull=False,
        created_at__gte=start_at,
        created_at__lt=end_at,
    )
    for group in windowed.values("event_key", "channel").annotate(
        queued=Count("id"), held=Count("id", filter=Q(held=True))
    ):
        row = rows.get(group["event_key"])
        if row is None:
            # A row stamped with an event this build no longer has. REPORTED as
            # absent rather than crashing a settings screen: the count is not
            # ours to show, and the row is not ours to delete.
            continue
        row["queued"] += group["queued"]
        row["held"] += group["held"]
        channel = row["by_channel"].setdefault(
            group["channel"], {"queued": 0, "held": 0, "suppressed": 0}
        )
        channel["queued"] += group["queued"]
        channel["held"] += group["held"]

    # 2 · documents — the same set counted by distinct source, so a screen can
    #     say "how many customers heard from us" without dividing by channels.
    for group in windowed.values("event_key").annotate(documents=Count("source_id", distinct=True)):
        row = rows.get(group["event_key"])
        if row is not None:
            row["documents"] = group["documents"]

    # 3 · suppression, counted by DOCUMENT. The stamp rides every surviving row
    #     of the document, so counting rows would multiply one suppression by
    #     the number of channels that survived it.
    seen: dict[tuple[str, str, str, int], set[str]] = {}
    for stamped in (
        windowed.filter(rule_suppressed_channels__isnull=False)
        .values("event_key", "source_type", "source_id", "copy_no", "rule_suppressed_channels")
        .distinct()
    ):
        key = (
            stamped["event_key"],
            stamped["source_type"],
            str(stamped["source_id"]),
            stamped["copy_no"],
        )
        seen.setdefault(key, set()).update(
            piece for piece in (stamped["rule_suppressed_channels"] or "").split(",") if piece
        )
    for (event_key, _source_type, _source_id, _copy_no), channels in seen.items():
        row = rows.get(event_key)
        if row is None:
            continue
        row["suppressed"] += 1
        for channel in channels:
            slot = row["by_channel"].setdefault(channel, {"queued": 0, "held": 0, "suppressed": 0})
            slot["suppressed"] += 1

    # 4 · has this platform EVER written a row for this event, and under which
    #     source kind? Unwindowed, so a quiet month and an unwired writer stop
    #     reading the same — `queued: 0` means two entirely different things and
    #     a rail cannot carry a caveat.
    observed: dict[str, set[str]] = {}
    for pair in (
        models.OutboundMessage.objects.filter(tenant_id=tenant_id, event_key__isnull=False)
        .values("event_key", "source_type")
        .distinct()
    ):
        observed.setdefault(pair["event_key"], set()).add(pair["source_type"])

    floorless = _floorless_source_types()
    reasons = _not_reported_reasons()  # one read, not one per event
    for event in rule_catalog.EVENTS:
        row = rows[event.key]
        row["window_days"] = WINDOW_DAYS
        row["since"] = start_date.isoformat()
        row["until"] = end_date.isoformat()
        row["ever_attributed"] = event.key in observed
        row["not_reported"] = dict(reasons)
        if _suppression_recordable(event, floorless, frozenset(observed.get(event.key, ()))):
            row["suppressed_unavailable_reason"] = None
        else:
            # NOT zero. A System Admin who has just switched this event off must
            # not be told their switch did nothing.
            row["suppressed"] = None
            row["suppressed_unavailable_reason"] = SUPPRESSION_UNRECORDABLE_REASON
            for slot in row["by_channel"].values():
                slot["suppressed"] = None
    return rows


def for_event(event_key: str, as_of: date | None = None) -> dict[str, Any]:
    """One event's rail. Raises `KeyError` naming the vocabulary for an unknown
    key — `rule_catalog.event`'s own refusal, not re-worded here."""
    rule_catalog.event(event_key)
    return for_events(as_of)[event_key]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B task B6 (12-governance/11-change-requests.md → CR-048 · apps/notifications/rule_models.py (the ruling that per-event counts are computed from outbound_messages and never stored) · apps/notifications/models.py OutboundMessage (`event_key`, `rule_suppressed_channels`, `held`) · apps/notifications/services.py CHANNEL_FLOOR_BY_SOURCE + queue_document (the one writer of both columns) · apps/notifications/rules_api.py RELEASE_POSTURE · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-013 + BR-NOT-024 + BR-PAY-018)
# generated: 2026-08-30 by story-coder (CR-048 wave B tasks B6 + B10 lane)
# checklist: A✔ B=deferred(no frontend half — SET-12D's rail is NotificationRules.tsx and a sibling lane is building it against this shape) C✔ D✔(served on the two existing GET /notification-rules routes; this file mints no route of its own) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr048_b6_b10.py under PostgreSQL — RED PROVED FIRST: before the two columns existed the rail had nothing to group on and every event counted zero; the suppression count was red-proved by counting ROWS instead of DOCUMENTS and reading a 2-channel document as two suppressions.
# exceptions: (1) NO `delivered` AND NO `bounced`, AND NEITHER IS DERIVED FROM `queued` — BR-NOT-013 makes both provider facts and no adapter exists on any channel; both are served as unavailable WITH the reason. (2) SUPPRESSION IS UNCOUNTABLE FOR FLOORLESS SOURCE KINDS (`bulk_action`, `test`, `move`) because a message suppressed to nothing leaves no row to stamp; served as `null` + a reason, never as zero. (3) ONE CLOCK READ, and it is the window's end when no `as_of` is passed — a VIEW, not an event time; BR-TEN-043 governs the second and the judgment is argued in the module docstring. The tenant's timezone is used, and the measured window travels in the response. (4) `ever_attributed` EXISTS BECAUSE ZERO IS AMBIGUOUS: six events have no writer at all (BR-NOT-018, OQ-249/OQ-262) and would otherwise read as a quiet month forever. (5) NOTHING IS WRITTEN AND NO STATUS MOVES — four SELECTs, all tenant-scoped by the manager under RLS FORCE.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-003 (channel routing + the provider adapter seam — print/PDF
#           live v1 · email dispatch DEFERRED → W6 · SMS dispatch DEFERRED →
#           v1.1)   Screens: S8
# Rules:    BR-NOT-005 (provider adapters — BYO mailbox, transactional ESP,
#           Twilio — behind ONE seam; the dispatcher sends at the provider's
#           pace) · BR-BIL-016 (print/PDF v1; customer email ships W6 — rows are
#           written from day one, only the SEND defers; BYO mailbox for small
#           tenants, transactional ESP for volume) · BR-PAY-017 (email + SMS
#           ride the delivery queue WHEN their channels land) · BR-NOT-010 (v1
#           channels are print/email/SMS — door-hanger is not a channel until
#           v2) · BR-BIL-036 (print is the primary channel and the floor) ·
#           BR-TEN-013 (cross-module work goes through the owner's published
#           callable, never its ORM)
# Tests:    06-backend/tests/test_us_not_003_channel_routing.py
# Impacts:  apps/notifications/dispatcher.py (asks this module whether a channel
#           may be dispatched at all, and hands it the batch when it may)
# ───────────────────────────────────────────────────────
"""notifications → integrations SEAM: the ONE provider adapter, and the routing.

TD-8 and BR-NOT-005 both say ONE seam: *"provider adapters (BYO mailbox,
transactional ESP, Twilio) behind one seam"*. This is it. No provider name
appears in any business-logic file in this module — B7's design rule — and
which provider a tenant actually uses is integrations' own per-tenant config,
resolved inside integrations and never read from here.

╔══════════════════════════════════════════════════════════════════════════╗
║  EMAIL DOES NOT SEND IN THIS RELEASE, AND THIS FILE IS WHERE THAT IS     ║
║  WRITTEN DOWN AS CODE RATHER THAN AS A COMMENT (hard-won law 1).         ║
╚══════════════════════════════════════════════════════════════════════════╝

US-NOT-003's own deferred-wave note: *"queue rows + rendering for ALL channels
are v1; only the SEND adapters defer — email dispatch activates at W6 (OQ-073
closed), SMS dispatch at v1.1 behind the Twilio seam."* The absence is therefore
not a gap to be discovered by reading a docstring — `channel_route()` returns a
`ChannelRoute` whose `dispatchable` is False and whose `problem` names the wave,
the dispatcher records it on every cycle, and a test asserts that zero provider
calls happen for a deferred channel (TC-2, TC-3).

THE THREE STATES A CHANNEL CAN BE IN, AND WHY THEY ARE THREE AND NOT TWO
------------------------------------------------------------------------
1. **DEFERRED** — the tenant has not switched the channel on because the
   platform has not shipped it yet (email → W6, SMS → v1.1). Rows are written
   and rest `queued`. **No provider is contacted and none is looked for.**
2. **NO PROVIDER** — the channel IS active and the tenant has no connection for
   it. US-NOT-003 TC-5, verbatim: *"Rows stay `queued`; config-missing surfaced
   on the dispatch home — no crash, no loss, no fallback shared sender."*
3. **READY** — active, connected; the batch is handed over.

Collapsing 1 and 2 into "not sending" would put a number on the dispatch home
that reads *"email is not configured"* to a utility at W5, when the truth is
that the platform has not built it yet. That is the same distinction
`apps/notifications/services.py` draws between a customer who HAS no email
address and a platform that never LOOKED, and it is drawn for the same reason:
one of them is the tenant's to fix.

WHAT "SENDING" MEANS ON THIS DEPLOYMENT TODAY — THE THREE PROVIDER CHANNELS
----------------------------------------------------------------------------
⚠ **AMENDED 2026-08-17 (CR-009 in-app lane). This section used to be headed
"ALL THREE CHANNELS" and used to say "this deployment dispatches nothing at
all". BOTH became false the day `in_app` landed** — a fourth channel with a
platform adapter, dispatchable, reaching `sent` — and a paragraph describing the
product is a claim about it (hard-won law 1). What follows is still true of the
three channels that need a third party.

`apps/integrations` contains three docstrings and no models, no services and no
selectors. So the integrations adapter resolves to nothing for print, email and
SMS alike: print rows rest `queued` with `provider_not_connected`, exactly as
email and SMS rows rest `queued` with their wave markers. **In-app is the one
channel on this deployment that delivers**, and its adapter is
`apps/notifications/in_app.py` rather than a vendor.

That is stated here, carried on every dispatch result, parked in
`10-scripts/gates/seam_known_gaps.txt` with a live guard, and asserted by a test
— rather than left for a reader to infer from an empty app. US-NOT-003 TC-1
expects a print batch to reach `sent`; it cannot today, and the reason is a
missing print-vendor integration, not a missing dispatcher.

THE ADAPTER CONTRACT, for the lane that publishes it
----------------------------------------------------
    apps.integrations.services.dispatch_outbound_batch(
        channel: str,
        messages: tuple[dict, ...],
    ) -> dict[str, dict]

One call per hand-off, never one call per message: BR-NOT-005 paces at the
PROVIDER's rate and a per-message loop is the burst the rule forbids. Each
`messages` entry carries `{"id", "channel", "address", "snapshot", "artifact"}`
— the queue row's id, the snapshotted recipient (BR-TEN-017: never re-resolved)
and the rendered artifact. Integrations resolves the tenant's own provider from
its per-tenant config (A15 addendum: the utility's OWN address, never a shared
sender) and returns one entry per message id:

    {"status": "sent",   "provider_reference": "...", "response": {...}}
    {"status": "failed", "error": "…", "retryable": True|False, "response": {...}}

A message id the adapter does not answer for is treated by the dispatcher as a
retryable failure — silence is not success. An adapter that RAISES fails the
whole hand-off the same way, which is what a 429 looks like (T5-24 step 3) and
is why the retry is per-batch as well as per-row.

    apps.integrations.services.provider_connection_status(channel) -> dict | None

US-NOT-004 §5's provider-status readout — *"read-model over integrations
connections … read-only here"*. `None` means integrations cannot answer, which
is NOT the same as "not connected" and is never rendered as one.

⚠ **IT IS DECLARED AT `services` AND NOT AT `selectors`, WHICH IS THIS REPO'S
USUAL HOME FOR A READ.** `apps/integrations` holds three files — `models.py`,
`services.py`, `registry.py` — and no `selectors.py`. Declaring a contract
against a module file that does not exist is a TYPO by G20's rule B7 and is
never parkable, correctly: *"a typo'd contract is not a gap."* Creating an
empty `apps/integrations/selectors.py` to hold the address would be this lane
scaffolding another module while it is unbuilt, which is exactly the kind of
cross-lane edit that collides.

There is precedent for the address as well as a reason for it:
`apps/tenancy/seams.py` resolves EVERY neighbour contract from
`apps.<module>.services`, reads included — and DEF-075 is the record of what
happens when a read is published somewhere the seam does not look. When
integrations grows a `selectors.py`, moving this one line is the whole change.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from apps.notifications import models

#: The integrations contracts this module depends on, named once so each is
#: greppable from BOTH sides of the boundary and harvestable by G20.
PROVIDER_MODULE = "integrations"
DISPATCH_ADAPTER = "dispatch_outbound_batch"
CONNECTION_STATUS_READ = "provider_connection_status"

#: ⚠ ONE CHANNEL'S PROVIDER IS THIS PLATFORM (BR-NOT-019, PO 2026-08-17).
#:
#: The seam is still ONE seam. What changed on 2026-08-17 is that `in_app`
#: resolves its adapter INSIDE this application instead of inside
#: `apps.integrations`, because there is no third party to resolve it to: no
#: vendor decision, no per-tenant connection, no credentials, no cost. The
#: adapter it points at implements the SAME contract as the integrations one,
#: verbatim, precisely so that in-app proves the path every other channel will
#: travel rather than a shortcut around it.
#:
#: Written as a map rather than an `if channel == …` so that a second
#: platform-delivered channel (if one is ever ruled) is a row here, and so that
#: a reader can see at a glance which channels this product can deliver on its
#: own — today, two: the staff inbox and the customer portal.
#: ⚠ **TWO CHANNELS' PROVIDER IS THIS PLATFORM SINCE 2026-09-07 (`CR-084`), AND
#: THE COMMENT ABOVE PREDICTED EXACTLY THIS.** It said the map exists *"so that
#: a second platform-delivered channel (if one is ever ruled) is a row here"*,
#: and it now is: the Product Owner ruled the customer portal on, pointing at
#: the greyed-out row on Settings → Notifications (*"can you swithc on this now
#: - Customer portal"*). The sentence one line up — *"today, exactly one"* — was
#: true when it was written and is corrected rather than left standing, which is
#: hard-won law 1.
#:
#: Each channel names its OWN module. It was one constant while there was one
#: adapter; a second channel resolving through `PLATFORM_ADAPTER_MODULE` would
#: have had to live inside `in_app.py`, which is a staff mailbox and has nothing
#: to do with a customer's portal.
PLATFORM_ADAPTER_MODULES: dict[str, str] = {
    models.CHANNEL_IN_APP: "apps.notifications.in_app",
    models.CHANNEL_PORTAL: "apps.notifications.portal_delivery",
}
PLATFORM_ADAPTERS: dict[str, str] = {
    models.CHANNEL_IN_APP: "deliver_batch",
    models.CHANNEL_PORTAL: "deliver_batch",
}

#: WHY a channel is not dispatchable. CODES, never prose: the dispatch home
#: (US-NOT-004) and the per-run dashboard (US-BIL-024) group on them, and a
#: screen cannot group on a sentence.
ROUTE_CHANNEL_DEFERRED = "channel_dispatch_deferred"
ROUTE_PROVIDER_NOT_CONNECTED = "provider_not_connected"
ROUTE_PROVIDER_STATUS_UNKNOWN = "provider_status_unknown"

#: The release each deferred channel activates in, from the CLOSED questions —
#: OQ-073 (email → W6) and BR-PAY-017/NFR-21 (SMS → v1.1, Twilio seam). Stated
#: as data so the dispatch home can badge a channel with its wave instead of
#: with the word "off" (US-NOT-004 TC-2: *"email: 'Ships W6' badge … honest
#: about deferral"*).
#:
#: ⚠ **`sms: "v1.1"` LEFT THIS MAP ON 2026-10-29 — SUPERSEDED (`CR-198-BRC10`).**
#: PO, verbatim: *"1A 2A 4B 5 US 6A(ONly Stop option is required), start"* —
#: SMS is built now, through one shared platform Twilio account. A tenant whose
#: *Turn texts on* switch is off now reads *switched off for this tenant* (the
#: branch below for a channel with no wave), never *deferred to v1.1*; and with
#: the switch on, the PLATFORM's credentials decide (`provider_status_unknown`
#: while they are absent — the platform's gap, not the utility's).
DEFERRED_UNTIL: dict[str, str] = {
    models.CHANNEL_EMAIL: "W6",
}

#: `CR-198-BRC10` — the integrations read that caps ONE hand-off at the
#: provider's per-minute rate (Twilio: 60), named once (G20).
SENDING_CEILING_READ = "sending_ceiling"


def batch_limit(channel: str, default: int) -> int:
    """At most `default`, and at most the provider's per-minute ceiling.

    The dispatcher claims this many rows for one hand-off. Claiming more than
    a provider takes in a minute would hand the excess over anyway, and a text
    Twilio queues for hours is a reminder that arrives after the cut."""
    read = _resolve(PROVIDER_MODULE, SENDING_CEILING_READ)
    if read is None:
        return default
    try:
        ceiling = read(channel)
    except Exception:  # pragma: no cover — a broken read must not stop dispatch
        return default
    return min(default, int(ceiling)) if ceiling else default


@dataclass(frozen=True)
class ChannelRoute:
    """May this channel be dispatched for this tenant right now — and if not, why.

    `dispatchable` is the only thing the dispatcher branches on. `problem` is
    what it records and what a screen shows; it is present exactly when
    `dispatchable` is False, which is the same address-or-reason discipline the
    queue row itself carries.
    """

    channel: str
    dispatchable: bool
    problem: dict[str, Any] | None = None


def _resolve(module: str, attribute: str, kind: str = "services") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `apps/notifications/services.py`,
    `apps/billing/settings_seam.py` and `apps/metering/seams.py` all use. The
    day integrations lands its adapter, dispatch starts flowing through it with
    no edit here (hard-won law 2).
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def adapter(channel: str | None = None) -> Any:
    """The adapter that will deliver this channel, or None if there is none.

    For `in_app` that is the PLATFORM's own adapter, which always exists — this
    application is the provider (BR-NOT-019). For the other three it is the ONE
    integrations seam (TD-8), which resolves to None until integrations
    publishes it, and BR-NOT-013 says it is not coming in this release.

    `channel` defaults to None so the pre-2026-08-17 call shape still means "the
    integrations adapter"; every caller in this module passes it.
    """
    if channel is not None and channel in PLATFORM_ADAPTERS:
        # Imported at CALL time, like every other resolution here: a module-level
        # import of `in_app` would be a cycle (it imports `models`, which is fine,
        # but the dispatcher imports both) and the late binding is what lets a
        # test substitute the adapter without patching this module's globals.
        platform = import_module(PLATFORM_ADAPTER_MODULES[channel])
        found = getattr(platform, PLATFORM_ADAPTERS[channel], None)
        return found if callable(found) else None
    return _resolve(PROVIDER_MODULE, DISPATCH_ADAPTER)


def provider_status(channel: str) -> dict[str, Any] | None:
    """Integrations' connection state for a channel, or None if it cannot answer.

    None is NOT "not connected". US-NOT-004 TC-3 shows a readout with real
    states (*"Connected … Not connected"*), and rendering "cannot answer" as
    "Not connected" would tell a utility its mailbox had dropped when the truth
    is that nothing asked. Same rule `apps/billing/release.py` states about
    mandate coverage: *"'0 of 1,122 hold an address' and 'we could not count'
    must never render the same."*

    Resolved at `services` rather than `selectors` — `apps/integrations` has no
    `selectors.py` at all, and the reasoning is in the module docstring.
    """
    read = _resolve(PROVIDER_MODULE, CONNECTION_STATUS_READ)
    if read is None:
        return None
    answer = read(channel)
    return dict(answer) if answer is not None else None


def _email_sender_source() -> dict[str, Any] | None:
    """C-12's resolution (BR-NOT-023) — WHICH sender email would use, attached
    to the email route's problem so the dispatch home can say not only "email
    cannot send" but "and when it can, it goes THIS way": the tenant's own
    SMTP if configured, else the platform ESP when that lands.

    Imported at CALL time like every resolution here; a failure to answer is
    None rather than an invented mode (DEF-075's rule)."""
    try:
        from apps.notifications import sender_config

        return sender_config.sender_route()
    except Exception:  # pragma: no cover — a broken read must not break routing
        return None


def channel_route(channel: str, *, active: bool) -> ChannelRoute:
    """Routing for ONE channel: dispatch it, or say precisely why not.

    `active` is the tenant's own activation flag from
    `apps/notifications/dispatch_config.py` — print is always active
    (BR-BIL-036's floor), email and SMS ship off. This function does not read
    the config itself, so a caller cannot get one channel's route while another
    channel's settings were in hand.
    """
    if not active:
        wave = DEFERRED_UNTIL.get(channel)
        detail = (
            f"{channel} dispatch is DEFERRED to {wave}. Rows for this channel are written "
            "from day one and rest `queued`; only the SEND defers (US-NOT-003). No "
            "provider is contacted and none is looked for — a queued row on a deferred "
            "channel is the correct finished state, not a failed send."
            if wave
            else f"{channel} dispatch is switched off for this tenant, so its rows rest "
            "`queued`. Nothing is lost and nothing is sent."
        )
        problem = {
            "code": ROUTE_CHANNEL_DEFERRED,
            "br_ref": "BR-BIL-016" if channel == models.CHANNEL_EMAIL else "BR-PAY-017",
            "channel": channel,
            "deferred_until": wave,
            "detail": detail,
        }
        if channel == models.CHANNEL_EMAIL:
            problem["sender_source"] = _email_sender_source()
        return ChannelRoute(channel=channel, dispatchable=False, problem=problem)

    # ⚠ TWO SEPARATE QUESTIONS, AND UNTIL 2026-09-04 ONE CHECK ANSWERED BOTH
    # BY ACCIDENT (CR-069 wave E). *Has the PLATFORM built an adapter?* and
    # *has THIS TENANT connected a provider?* were the same question for as
    # long as `apps.integrations.services.dispatch_outbound_batch` did not
    # exist: no adapter meant nobody could send, ever. Publishing it made the
    # first answer *yes* for every tenant at once, and this branch would have
    # gone on to report `dispatchable=True` for a utility with **no mail
    # connection at all** — the dispatcher would have handed over a batch that
    # every message in it was going to fail.
    #
    # It was caught by `test_c12__a_fully_configured_sender_changes_no_dispatch
    # _verdict`, whose own comment named the assumption out loud: *"Even
    # ACTIVE, there is still no adapter: configured is not connected."* The
    # sentence is still true and the reason for it moved.
    # ⚠ **A CHANNEL THIS PLATFORM DELIVERS ITSELF IS CONNECTED BY DEFINITION,
    # AND SAYING SO IS `DEF-NOT-4532` — A LIVE REGRESSION FOUND ON 2026-09-07.**
    #
    # The `connected` requirement below arrived with `CR-069` wave E on
    # 2026-09-04 (`d471e868`), and that commit does not mention `in_app` once.
    # It did not have to: the rule it added is right for every channel with a
    # third party behind it. But `in_app`'s provider is THIS APPLICATION —
    # `apps/integrations` has no category for it, so `provider_connection_status`
    # correctly answers `None` (*"this module cannot answer"*), and this function
    # then read that as `provider_status_unknown` and reported the channel
    # **not dispatchable**.
    #
    # So from 2026-09-04 the one channel this product could actually deliver on
    # stopped delivering, on every tenant, silently: the rows rest `queued`,
    # which is the same state they rest in when a channel is merely deferred,
    # and nothing anywhere says *the platform's own adapter was skipped because
    # a third party could not be asked about it*. It is `DEF-NOT-4532`, and it
    # was found by `CR-084` asking the same question of the portal channel.
    #
    # The check is placed BEFORE the provider questions rather than folded into
    # them, because there is no third party to ask about and asking is what went
    # wrong: `PLATFORM_ADAPTERS` is the register of channels whose provider is
    # this codebase, and an adapter that imports is the whole of what
    # "connected" can mean for one.
    if channel in PLATFORM_ADAPTERS:
        platform_adapter = adapter(channel)
        if platform_adapter is not None:
            return ChannelRoute(channel=channel, dispatchable=True)
        return ChannelRoute(
            channel=channel,
            dispatchable=False,
            problem={
                "code": ROUTE_PROVIDER_STATUS_UNKNOWN,
                "br_ref": "BR-NOT-019",
                "channel": channel,
                "detail": f"{channel} is delivered by this platform and its own adapter "
                f"({PLATFORM_ADAPTER_MODULES.get(channel)}) could not be resolved, so its "
                "rows rest `queued`. This is a broken deployment of THIS product, not a "
                "missing connection a utility could make — nothing on Settings → "
                "Integrations would help.",
            },
        )

    found = adapter(channel)
    status = provider_status(channel)
    connected = bool(status.get("connected")) if isinstance(status, dict) else False
    # ⚠ `DEF-NOT-8451` (2026-09-30). The generic hand-off seam exists for EVERY
    # channel, so `found` alone cannot say whether this platform can deliver
    # THIS one. Integrations can: `connectable` is False when no provider of
    # the channel's kind has an adapter bound (print and SMS today), and then
    # the gap is the PLATFORM's — reported as `provider_status_unknown`, exactly
    # as before `d471e8680`, and never as a connection the utility should make.
    platform_gap = isinstance(status, dict) and status.get("connectable") is False
    if found is None or not connected:
        if status is None or platform_gap:
            return ChannelRoute(
                channel=channel,
                dispatchable=False,
                problem={
                    "code": ROUTE_PROVIDER_STATUS_UNKNOWN,
                    "br_ref": "BR-NOT-005",
                    "channel": channel,
                    "detail": f"apps.{PROVIDER_MODULE}.services.{DISPATCH_ADAPTER} is not "
                    "published, or integrations cannot report a connection state, "
                    f"or no {channel} provider can be connected on this platform yet, "
                    f"so {channel} rows rest `queued`. This is the PLATFORM having no "
                    "adapter, not the tenant having no provider — the two are counted "
                    "apart so a utility is never told to fix a connection that is not "
                    "theirs to fix. Nothing is sent through a shared sender in the "
                    "meantime (A15 addendum: the utility's OWN address, always).",
                },
            )
        return ChannelRoute(
            channel=channel,
            dispatchable=False,
            problem={
                "code": ROUTE_PROVIDER_NOT_CONNECTED,
                "br_ref": "BR-NOT-005",
                "channel": channel,
                "detail": f"this tenant has no {channel} provider connected, so its rows "
                "rest `queued` and are surfaced on the dispatch home (US-NOT-003 TC-5). "
                "No crash, no loss, and NO fallback shared sender: every customer email "
                "goes from the utility's own address or it does not go (A15 addendum). "
                "Settings → Integrations is where the connection is made.",
                "provider_status": status,
            },
        )

    return ChannelRoute(channel=channel, dispatchable=True)


def dispatch_batch(channel: str, messages: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    """Hand ONE batch to the tenant's provider for this channel. One call.

    One call per hand-off, never one per message: BR-NOT-005 paces at the
    provider's rate, and a per-message loop is the burst T5-24 step 2 forbids
    (*"Max messages per provider hand-off ≤ 500"*).

    Returns the adapter's per-message answer unchanged. Interpreting it —
    which row is `sent`, which retries, which rests `failed` — is the
    dispatcher's, because those are lifecycle rules (BR-NOT-005) and not
    provider facts.

    The caller must have asked `channel_route` first; calling this with no
    adapter published is a programming error rather than a runtime condition,
    so it raises rather than returning an empty answer that would read as
    "the provider sent nothing".
    """
    send = adapter(channel)
    if send is None:
        raise RuntimeError(
            f"apps.{PROVIDER_MODULE}.services.{DISPATCH_ADAPTER} is not published — ask "
            "`channel_route` before handing over a batch. Returning an empty result here "
            "would be indistinguishable from a provider that accepted the batch and sent "
            "nothing, which is the one answer a delivery system must never fabricate."
        )
    return dict(send(channel, messages) or {})


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-003@9b2a71e (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md — US-NOT-003 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-005/010 — · 10-notifications/03-field-map.md §1 · 08-qa/01-e2e/journeys/T5-24-dispatch-burst-pacing.md)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — channel routing + the provider seam)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — a cross-module seam) E=deferred(no-frontend-half; the S8 channel badges are US-NOT-004's UI and live under 07-frontend/src/features/tenancy/, which this lane was told not to touch) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_003_channel_routing.py · G20:
#         BOTH declared contracts are unresolved and are PARKED in
#         10-scripts/gates/seam_known_gaps.txt with `absent=` guards that expire
#         the moment integrations publishes either — the fallback here REPORTS
#         and never substitutes an answer · the deferral was proved RED by
#         switching email on with a stub adapter present and watching the
#         zero-provider-call assertion fail (transcript in the lane report)
# exceptions: (1) NOTHING DISPATCHES ON THIS DEPLOYMENT, INCLUDING PRINT.
#         `apps/integrations` holds three docstrings and no code, so the adapter
#         resolves to None for every channel and every row rests `queued` with a
#         stated reason. US-NOT-003 TC-1 (a print batch reaching `sent`) is
#         therefore NOT satisfiable here, and the blocker is a missing
#         print-vendor integration rather than a missing dispatcher. REPORTED,
#         parked, and asserted by a test rather than left to be inferred.
#         (2) NO PROVIDER IS NAMED IN THIS MODULE. Lob, Twilio, Google/M365 and
#         the ESPs appear in the prose that cites B7 and nowhere in the code —
#         which provider a tenant uses is resolved inside integrations from its
#         per-tenant config (B7 design rule).
#         (3) NO SMS OPT-IN CHECK. A15 requires opt-in before an SMS dispatch;
#         the opt-in lives on a customers-owned preference that is
#         PROPOSED-SCHEMA and unbuilt, and `apps/notifications/services.py`
#         already records an SMS row's absent opt-in as `no_sms_opt_in` at QUEUE
#         time. Re-asking at dispatch would re-resolve a snapshotted fact
#         (BR-TEN-017). Stated so the absence is findable: while SMS dispatch is
#         deferred to v1.1 this cannot bite, and it must be closed before it is
#         switched on.
#         (4) THE ADAPTER IS NEVER CALLED PER MESSAGE. One hand-off per batch is
#         the pacing rule itself (T5-24 step 2), not an optimisation.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

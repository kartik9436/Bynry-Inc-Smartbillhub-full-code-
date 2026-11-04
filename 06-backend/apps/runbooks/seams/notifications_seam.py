# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · BR-RBS-022 (a write is a port) ·
#           CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → notifications — what was queued, and to which channel. READ ONLY.

Read here to answer *has this customer already been told*, which is what keeps
the collections ladder from writing twice and what the delivery-feedback runbook
needs in order to suppress a channel that keeps bouncing.

⚠ **QUEUEING IS A PORT, NOT A READ.** `queue_notice` and `queue_receipt` are two
of the thirteen and are unbound in phase 1. **A notice cannot be unsent**, and
that single fact decides the whole design of this module: the failure that hurts
is not a runbook doing nothing — somebody notices that — it is a misconfigured
runbook queueing three thousand wrong disconnection notices in four minutes. The
cap, the dry run, the batch approval and the stop button are first-release
requirements rather than hardening for later, and phase 4's live half is the one
part of `CR-075` whose rollback is **not symmetric**: the reversible act is
turning the runbook off, never removing the code.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; each later wave brings the reads its own
runbooks actually need. A selector written here now would be a function nothing
calls (hard-won law 2), and naming one in prose that `notifications` does not
expose would fail `G20` — the guard that caught `DEF-075`. What this module will
need and `notifications` does not offer today is inventoried in
`17-runbooks/13-selector-inventory.md`, and **`notifications` adds each of
them** — never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="notifications",
    pair="operations → notifications",
    crosses="what was queued, and to which channel",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────


def published_notice_templates() -> int:
    """How many notice templates this tenant has PUBLISHED.

    ⚠ **THE READ IS `notifications`' OWN `template_service.published_versions`,
    NOT ITS `selectors`, AND THAT IS DELIBERATE RATHER THAN A SHORTCUT.**
    `notifications/selectors.py` publishes fifteen reads and not one of them is
    about templates: the template store's readers all live in
    `template_service`, which is the owning module's own published door. A seam
    resolving a selector that does not exist would answer `None` for ever and
    read as *no findings* — `DEF-035`'s WRONG DOOR shape, which the selector
    inventory calls worse than an absent one precisely because it looks
    answered.

    Counting rather than listing: runbook 1 step 9 asks whether the tenant has
    any published notice template at all, and the *which ones* question belongs
    to a screen rather than to a Check.
    """
    from apps.notifications import template_service

    return len(template_service.published_versions())


# ── CR-075 wave Q′ · the read runbook 22 makes (US-RBS-034) ────────────────


def undeliverable_feedback(*, limit: int = 2000) -> dict[str, object]:
    """What this utility has been told did not arrive, and **what nobody reports**.

    `apps.notifications.selectors.undeliverable_feedback` — the module that owns
    `outbound_messages` composes it from its own `delivery_ops` reads, so the
    delivery dashboard and this runbook cannot disagree about one morning.

    ⚠ **THE `not_reported` HALF IS WHY THIS RETURNS A MAPPING AND NOT A LIST.**
    `delivery_ops.queue_health` records that *"`delivered` and `bounced` are
    PROVIDER facts … no provider adapter exists on any channel, print included …
    Their counts are structurally zero here and must be rendered as NOT
    REPORTED, never as zero"*. An empty list read as *nothing bounced* would
    report a clean morning over channels nobody is listening to — a declared
    blind spot with no number attached, which hard-won law 7 says is
    indistinguishable from an empty one.
    """
    from apps.notifications import selectors as notifications_selectors

    return dict(notifications_selectors.undeliverable_feedback(limit=limit))


# ── CR-075 wave R′ · *have we already told them?* (US-RBS-023) ────────────
#
# Resolves `apps.notifications.selectors.queued_source_ids`, added by the module
# that owns `outbound_messages` in the same commit as this file.


def queued_source_ids(source_type: str, source_ids) -> dict[str, dict[str, object]]:
    """Which of these source ids already have a queue row — ONE query for all.

    `apps.notifications.selectors.queued_source_ids`.

    ⚠ **THIS IS THE ONLY DURABLE RECORD IN THE PRODUCT THAT WE TOLD SOMEBODY
    SOMETHING**, and that is why `RB-111`'s *once per meter every 7 days* guard
    reads it. The obvious home — *"told about a leak on the 4th"* on the meter —
    **does not exist** (`DEF-RBS-4331`, and the `flag_meter` port's own
    docstring), and the obvious substitute is forbidden: `BR-RBS-040` makes a
    NOTE an engine act rather than a fourteenth port, precisely so nobody
    reaches for one here.

    ⚠ **AND IT IS STRUCTURALLY EMPTY ON THIS DEPLOYMENT, WHICH IS REPORTED WITH
    A NUMBER RATHER THAN LEFT TO BE INFERRED** (hard-won law 7). Nothing has
    ever queued a leak alert, because `engine.acts.LIVE_ENABLED_RUNBOOKS` is an
    empty frozenset for the whole catalogue — so *0 told this week* is TRUE and
    means *nobody has been told yet*, not *the guard looked and found nothing*.
    The runbook carries the outbox row count beside the guard count so a reader
    can tell the two apart.

    An id with no row is ABSENT from the mapping rather than present with an
    empty value.
    """
    from apps.notifications import selectors as notifications_selectors

    return dict(notifications_selectors.queued_source_ids(str(source_type), source_ids))

# ── Trace ──────────────────────────────────────────────
# Story:    New Connect step 7 — `Choosing a template`
#           Screens: 05-prototype/02 Accounts Menu Blueprint.pdf p091, read AS
#           AN IMAGE at scale 2 (B14 rule 42)
# Rules:    PO ruling 2026-09-16 (step 7 is three messages) · OQ-MET-12360
#           CLOSED 2026-09-16 · BR-BIL-025 (three axes, two fallbacks) ·
#           BR-BIL-027 (nothing renders from a draft) · BR-NOT-002 (a contract
#           version is effective-dated and cannot be seeded) · B14 rules 31, 42
# Tests:    06-backend/tests/test_new_connect_step7_messages.py
# ───────────────────────────────────────────────────────
"""What notifications publishes to New Connect's step 7.

One door, and it is deliberately thin: the picker's rules are p091's and they
were already built and proved for the service-request picker on 2026-09-15.
A second implementation of *list the draft, refuse the pick* would be a second
opinion about one picture, and the two would drift the first time either was
touched (hard-won law 5's reasoning, applied to behaviour rather than to a
file).

⚠ **THREE CLASSES, AND ONE OF THEM IS OLDER THAN THIS FILE.** The PO closed
`OQ-MET-12360` with *"using existing template and notification"*, and the
contract turned out to need nothing built: `contract_service_agreement` has
been in the `contracts` group since `CR-011`. So this names it beside the two
new classes rather than authoring a fourth.

⚠ **AND THAT IS WHY A CONTRACT ROW CAN BE LISTED WITH NO PUBLISHED VERSION.**
`BR-NOT-002` makes every contract version effective-dated and
`seed_notice_templates` REFUSES to seed one — there is no human in a
provisioning transaction to choose that date. On a utility that has not yet
published its own agreement there is simply no pickable row for message two,
and the picker says so in the same words it uses for a draft. That is the rule
working, not a gap here.
"""

from __future__ import annotations

from typing import Any

from apps.notifications import service_request_events

#: The three classes step 7 chooses between, in the PO's own order — the build
#: exists, the contract, the cost.
CONNECTION_CLASSES: tuple[str, ...] = (
    "new_connect_confirmed",
    "contract_service_agreement",
    "new_connect_quote",
)


def connection_templates(*, search: str | None = None) -> tuple[dict[str, Any], ...]:
    """Every published or draft VARIANT of step 7's three classes.

    The drawn columns are `TEMPLATE · GROUP · CHANNEL · VARIANT · VERSION` with
    a radio per row, so one row is one VARIANT of one class carrying its live
    version number and status.

    ⚠ **A DRAFT IS RETURNED, NOT FILTERED OUT**, and the row travels with
    `pickable: false` and the reason. p091, read as an image: *"The Spanish
    variant is a draft, and drafts are listed but cannot be picked. Hiding it
    would send a clerk looking for something they can see exists; showing it as
    choosable would queue a letter nobody has approved."*

    ⚠ **`search` MATCHES THE NAME A HUMAN GAVE IT** — the box's own helper line
    — and never the class code (B14 rule 31).

    ⚠ **DELEGATED, NOT REIMPLEMENTED.** `applicant_templates` is already the
    generic row-builder: it takes the class codes it should list, and its only
    applicant-specific behaviour is the DEFAULT it falls back to when given
    none. This passes the three codes explicitly, so nothing of that default is
    reached. The name on the other side is the older caller's; the behaviour is
    the drawing's, and the drawing is the same drawing.
    """
    return service_request_events.applicant_templates(codes=CONNECTION_CLASSES, search=search)


def preview_occasion(
    *,
    template_code: str,
    category: str | None,
    language: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    """**What one New Connection letter would say, for THIS build** —
    `CR-163-BRC10` item 26's *Preview*, before anything is queued.

    The version is the one `queue_document` would PIN (`template_service.
    resolve`, `BR-BIL-025`'s order), its body is loaded exactly
    (`load_pinned`), and it is rendered with the build's own facts by the one
    renderer (`rendering.render`). Nothing is written and no number is spent.

    ⚠ **NO PUBLISHED TEMPLATE IS AN ANSWER, NOT AN ERROR** — `available: False`
    with `reason: "no_template"`, which the screen turns into *"No template —
    add one in Settings → Templates"* (item 27). A preview that invented a
    body would be content this platform wrote for a utility.
    """
    from apps.notifications import rendering, template_service

    try:
        resolved = template_service.resolve(
            code=template_code, category=category, language=language
        )
        pinned = template_service.load_pinned(
            template_id=resolved.template_id, version=resolved.version
        )
    except template_service.TemplateRefused:
        return {"available": False, "reason": "no_template", "template_code": template_code}
    try:
        artifact = rendering.render(
            template_code=pinned.code,
            template_version=pinned.version,
            body=pinned.body,
            context=dict(context),
            subject=pinned.subject,
            language=resolved.language,
        )
    except rendering.RenderRefused:
        return {"available": False, "reason": "render_refused", "template_code": template_code}
    return {
        "available": True,
        "reason": None,
        "template_code": template_code,
        "template_version": pinned.version,
        "language": resolved.language,
        "channel": artifact.channel,
        "subject": artifact.subject,
        "body": artifact.body,
        "absences": [dict(entry) for entry in artifact.absences],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: New Connect step 7 (PO ruling 2026-09-16 · OQ-MET-12360 closed · 05-prototype/02 Accounts Menu Blueprint.pdf p091 read as an image at scale 2)
# generated: 2026-09-16 by story-coder (wave 1 lane D)
# checklist: A✔ B=deferred(the step-7 screen is a later wave's) C✔ D=deferred(reached through metering's seam, no HTTP surface of its own) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest under PostgreSQL — RED PROVED FIRST, quoted in the lane report.
# exceptions: (1) A CONTRACT CLASS MAY HAVE NO PICKABLE ROW — BR-NOT-002, a contract version is effective-dated and cannot be seeded, so the utility publishes it under its own date. (2) NOTHING IS SENT — BR-NOT-013.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

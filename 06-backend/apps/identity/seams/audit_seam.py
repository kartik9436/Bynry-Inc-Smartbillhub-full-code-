# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-010 (the Security tab) — the Audit log card of the approved
#           Settings → Security redesign, 2026-09-29
#           (05-prototype/security-redesign-2026-09-29/approved-auditcard-1440.png).
#           Screens: S8 (Settings → Security). `View all →` lands on S61.
# Rules:    BR-AUD-003 (the actor shapes, and what an UNNAMED system job is) ·
#           BR-AUD-006 (PII is masked in the trail; nothing unmasks) ·
#           BR-AUD-007 (every audit read tenant-scoped, RLS FORCE underneath) ·
#           BR-AUD-013 (every audit query starts from a time floor) ·
#           BR-IDN-019 (who may see the Security tab at all) ·
#           CLAUDE.md hard rule 1 · hard-won law 5 (one source, derive views)
# Tests:    06-backend/tests/test_security_redesign_audit_card.py ·
#           06-backend/tests/test_security_redesign_audit_card_pg.py
# Impacts:  apps/identity/selectors.py (the only caller)
# ───────────────────────────────────────────────────────
"""identity → audit: this tab's OWN change history, and nothing else.

WHAT IT SERVES
--------------
`security_policy_changes(limit=…)` — the most recent saves of the tenant's
`security_policies` row, newest first, each one already reduced to the fields
that actually changed, in the wire shape `endpoints.ts` declares as
`SecurityPolicyChange`. **It returns FACTS: a field name and the two stored
values. No words.** `lockout_minutes` is called *Lockout length* and printed
`15 minutes` by `securityValueLabel` in the browser, through the eleven
catalogues — one formatter for the dropdowns and the card alike.

⚠ **IT IS THIS TAB'S LOG, NOT THE PLATFORM'S.** The PO ruled the card stays on
this screen — *"keep it here only in this screen"* — and a platform-wide feed
here would be noise a clerk has to filter. The filter is `action =
settings.security_updated`, which is exactly and only what
`services.save_security_policy` writes, and what `identity/0007` and `0008`
were deliberately built to write too so that a migration's change and a
person's change sit in one history.

⚠ **NO SECOND READER OF `audit_log`.** Every query below is
`apps.audit.selectors.audit_queryset`, the one definition of what an audit
query means (its window floor, its tenant scope, its stable sort). This file
adds a filter and a bound and nothing else.

⚠ **NO DATABASE ID LEAVES THIS FILE (B14 rule 31).** `audit.selectors`
renders a person actor as `{"id": …, "name": …}` because S61's ratified column
contract carries the id. This card has no use for it, so the id is dropped
HERE rather than trusted not to be rendered upstream — an id that never
reaches the payload cannot reach a screen.

⚠ **FEWER THAN `limit` ROWS IS A TRUE ANSWER, NOT A FAULT.** `audit_log` is
pruned on a retention schedule and bounded by a two-year window floor, and
`CLAUDE.md` hard rule 4 is explicit that no surface may describe an audit row
as a permanent record. A utility that has never touched this tab, or whose
history has aged out, gets an empty list and the screen says so.

⚠ **THE SCAN IS BOUNDED AND THE BOUND IS REPORTED.** One save can change six
settings and the card draws one row PER SETTING, so filling five card rows can
take one audit row or five. A save that changed nothing writes a row with an
empty `changed` set, which yields none at all — so the walk is over audit rows
until the card is full, capped at `SCAN_LIMIT`. Law 7's fifth shape: the
caller is told `scanned` and `capped` beside the rows, because a check that
cannot cover its whole subject must print what it skipped beside what it
checked.
"""

from __future__ import annotations

from typing import Any

#: The one action code this card reads. `services.save_security_policy` writes
#: it, and so do `identity/0007` and `0008` — see the module docstring.
SECURITY_POLICY_ACTION = "settings.security_updated"

#: How many audit rows the walk may read to fill one card. Five card rows need
#: at most five audit rows in the ordinary case; the cap exists for the
#: pathological one (a long run of saves that changed nothing) and keeps this
#: read O(1) in the size of the log, which `NFR-3`'s reasoning asks of every
#: read even when the answer is a fixed five.
SCAN_LIMIT = 200


def _audit():
    """Resolve the owning module at CALL time — the seam shape this repo uses,
    so a module move changes this line and nothing that calls it."""
    from apps.audit import selectors as audit_selectors

    return audit_selectors


def security_policy_changes(tenant_id: Any, *, limit: int = 5) -> dict[str, Any]:
    """The last `limit` CHANGES to this tenant's security policy.

    A CHANGE is one setting moving, not one save: the card's columns are
    WHEN · WHO · SETTING · CHANGE and the drawing puts one setting on each
    row, so a save that moved three settings contributes three rows, newest
    first, in the order `save_security_policy` recorded them.

    Returns `{"changes": [...], "scanned": n, "capped": bool}`.

    Each change is the wire row `07-frontend/src/api/endpoints.ts` declares as
    `SecurityPolicyChange`: `{"id", "changed_at", "actor", "field", "before",
    "after"}`, with **RAW stored values on both sides and no words anywhere**.

    ⚠ **THE WORDS ARE THE BROWSER\'S AND THAT IS A REVERSAL, RECORDED
    2026-09-29.** This seam served a rendered pair for one afternoon
    (`480 minutes` as a string, built by an `apps/identity/security_render.py`
    that no longer exists). The Security tab landed the same day with
    `securityValueLabel` — ONE formatter that already labels the dropdowns AND
    the card, through the eleven catalogues. Two formatters for one pair is
    exactly what `DEF-IDN-7501` is about, and of the two the browser\'s is the
    one that can speak eleven languages. So the server sends the fact and the
    browser prints it.
    """
    audit_selectors = _audit()
    queryset = audit_selectors.audit_queryset(tenant_id, filters={"action": SECURITY_POLICY_ACTION})
    # `audit_queryset` already sorts newest-first with a stable tie-break.
    rows = list(queryset[:SCAN_LIMIT])
    names = audit_selectors.actor_names(tenant_id, [row.actor_user_id for row in rows])

    changes: list[dict[str, Any]] = []
    scanned = 0
    for row in rows:
        scanned += 1
        actor = _actor(row, names)
        for field, before, after in _changed_fields(row.before, row.after):
            changes.append(
                {
                    # The audit row\'s id, one per CHANGE rather than per row,
                    # so a save that moved three settings gives three keys a
                    # list can be drawn from. It is a KEY and never a visible
                    # value — B14 rule 31 is about what a clerk reads.
                    "id": f"{row.id}:{field}",
                    "changed_at": row.created_at.isoformat(),  # UTC; IS-8 renders it
                    "actor": actor,
                    "field": field,
                    "before": before,
                    "after": after,
                }
            )
        if len(changes) >= limit:
            break
    return {
        "changes": changes[:limit],
        "scanned": scanned,
        "capped": scanned >= SCAN_LIMIT and len(changes) < limit,
    }


def _changed_fields(before: Any, after: Any) -> list[tuple[str, Any, Any]]:
    """The fields this save actually moved.

    `save_security_policy` already stores only the changed fields, so this is
    normally the whole of `after`. It is recomputed rather than assumed
    because `identity/0007` and `0008` write their own pair, and because a row
    written before a field existed has it on one side only.
    """
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    fields = list(after) + [field for field in before if field not in after]
    return [
        (field, before.get(field), after.get(field))
        for field in fields
        if before.get(field) != after.get(field)
    ]


#: What the redesign calls the product changing a utility's setting for it.
#:
#: ⚠ **THE MIGRATIONS DO NOT WRITE THIS STRING — THEY WRITE NOTHING AT ALL FOR
#: THE ACTOR, AND THAT IS THE POINT.** `identity/0007` and `0008` pass
#: `actor_user_id=None` with no automation actor, which is `BR-AUD-003`'s
#: UNNAMED SYSTEM JOB, and `apps/audit/selectors._actor_payload` renders that
#: as `null`. The Security tab's card would then draw a blank WHO cell, which
#: reads as *we do not know who did this* — and we do know: the product did,
#: during an upgrade. The drawing says `Product upgrade` and this is where
#: that becomes true.
#:
#: ⚠ **IT IS SERVED AS A NAMED AUTOMATION (`BR-AUD-019`), NEVER AS A SENTENCE
#: THIS FILE COMPOSED.** `actorLabel` in the browser reads `kind` to decide the
#: actor is an automation and then prints `name`, so the card needs the SHAPE.
#: `version` is null rather than absent: a version nobody established is a
#: fact nobody established, and `actorLabel` draws the bare name for it.
#:
#: ⚠ **AND IT DIFFERS FROM S61's WORD ON PURPOSE.** The audit screen renders
#: the same underlying row as *System job* (`audit.actor.system`), which is
#: right there, because on the platform-wide log an unnamed job is a nightly
#: run as often as an upgrade. On THIS tab the only unnamed job that has ever
#: written a row is a migration moving a setting, so the narrower, truer word
#: is available. Recorded in `12-governance/02-decision-log.md`, 2026-09-29.
PRODUCT_ACTOR_NAME = "Product upgrade"

#: `BR-AUD-019`'s `kind` vocabulary is `runbook | job | import | integration`
#: and none of them is a migration, so this one names itself. The browser
#: narrows on the PRESENCE of `kind` and never on its value
#: (`isAutomationActor`), so a new word here cannot break a screen.
PRODUCT_ACTOR_KIND = "product_upgrade"


def _actor(row: Any, names: dict[str, str]) -> dict[str, Any] | None:
    """WHO, in the shapes `endpoints.ts` declares as `AuditActor | null`.

    Built on `apps.audit.selectors.audit_row`, so the branch ORDER that
    `US-AUD-010` made load-bearing — a named automation is read as an
    automation BEFORE it is read as a person — is inherited rather than
    re-derived here.

    A PERSON keeps S61's exact `{id, name}` payload, byte for byte. The id
    travels for support and no screen prints it: `actorLabel` reads `name`,
    and `AuditLogPage` puts the id on `title` (B14 rule 31, `DEF-2378`).
    Serving a different person shape on this one card would be a second actor
    contract for one table.

    **The single row this function changes is the unnamed system job**, which
    becomes the named automation above instead of `null`.
    """
    actor = _audit().audit_row(row, names).get("actor")
    if actor is None:
        return {"kind": PRODUCT_ACTOR_KIND, "name": PRODUCT_ACTOR_NAME, "version": None}
    return actor

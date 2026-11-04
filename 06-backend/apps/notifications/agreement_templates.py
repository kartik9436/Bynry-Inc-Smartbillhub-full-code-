# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, *"don't do any
#           hardcoding"* (email subject and body come only from the Settings
#           template; languages from the registry)
# Rules:    BR-NOT-006 · BR-NOT-001 · BR-NOT-002 (NOT touched — the two classes
#           here are EMAIL classes; a contract is still never seeded)
# Tests:    06-backend/tests/test_cr190_agreements.py
# Impacts:  apps/customers/agreements.py (calls `ensure_seeded` at queue time) ·
#           notifications/migrations — none (seeded on first use, see below)
# ───────────────────────────────────────────────────────
"""Plant the two agreement email classes for the tenant in context.

Insert-missing, through `seed_templates._seed_one` — the ONE seeder, so a
utility's own published variant is never overwritten and every plant is audited
exactly as every other seeded class is. The `default` variant is the `en`
wording; then one variant per REGISTRY language (`tenancy_seam.
platform_languages`), each in its own native wording (`agreement_wording`).

⚠ **CALLED AT QUEUE TIME, NOT AT PROVISIONING.** Lane STAFF-INVITE's
`ensure_seeded` takes the same posture for the same reason: a utility
provisioned before `CR-190-BRC10` must never be queued a message pinned to
nothing. A later merge may also plant these at provisioning
(`seed_notice_templates`); both are insert-missing, so doing it twice is
harmless.

⚠ **THAT MERGE HAPPENED (2026-10-22, lane MERGE-EMAILS).** Provisioning plants
both classes now (`seed_templates.SEEDABLE` + `LANGUAGE_WORDING`), so a new
utility sees them on Settings → Templates from day one; this queue-time call
stays for a utility provisioned before `CR-190-BRC10`.
"""

from __future__ import annotations

from typing import Any

from apps.notifications import catalogs

# The source string every planted row carries now lives beside the other
# seeded bodies' (`seed_templates._AGREEMENT_AUTHORED`), word for word.

CODES: tuple[str, ...] = (
    catalogs.AGREEMENT_REQUEST_EMAIL,
    catalogs.AGREEMENT_ACCEPTED_EMAIL,
)


def ensure_seeded(*, actor: Any = None) -> dict[str, Any]:
    """Both classes, `default` and every written registry language.

    Returns `{seeded: [codes·languages planted now], unwritten: [languages]}`;
    a registry language with no wording is served by the `default` variant
    and REPORTED, never invented.

    ⚠ MERGED 2026-10-22 (lane MERGE-EMAILS): this is now a thin door onto the
    ONE seeder. `seed_templates` plants both classes at provisioning
    (`SEEDABLE` + `LANGUAGE_WORDING`) and this still runs at queue time for a
    utility provisioned before `CR-190-BRC10` — insert-missing both ways, the
    same words and the same source string either way.
    """
    from apps.notifications import seed_templates

    planted: list[str] = []
    unwritten: set[str] = set()
    for code in CODES:
        entry = next(e for e in seed_templates.SEEDABLE if e.code == code)
        if seed_templates._seed_one(entry, actor=actor, at=None).get("created"):
            planted.append(f"{code}·default")
        result = seed_templates.seed_language_variants(code, actor=actor)
        planted.extend(f"{code}·variant" for row in result["seeded"] if row.get("created"))
        unwritten.update(result["unwritten"])
    return {"seeded": planted, "unwritten": sorted(unwritten)}


__all__ = ["CODES", "ensure_seeded"]

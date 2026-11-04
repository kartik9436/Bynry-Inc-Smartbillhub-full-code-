# ── Trace ──────────────────────────────────────────────
# Journey:  J73 F2 · J72 E6 — "Meter Reads is down" walked in a browser
# Checks:   04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md F2
# Defect:   DEF-BIL-8510 (no test-only way to take Meter Reads down on a live
#           stack; the harness renamed a table, which broke every route screen)
# Rules:    CLAUDE.md hard-won law 3 (defaults fail closed — the unsafe option
#           is the one you type)
# Tests:    06-backend/tests/test_us_bil_037_clerk_checks.py (TC-15)
# ───────────────────────────────────────────────────────
"""TEST-ONLY outage switches: make ONE module stop answering on a walk stack.

A browser walk has to show a clerk what happens when Meter Reads is down, and
the product must never offer that as a feature. So the switch is a FILE on the
server's own disk, in a directory a walk names at start-up:

    SBH_WALK_SWITCHES_DIR=/tmp/j73-switches  manage.py runserver …
    touch /tmp/j73-switches/meter_reads.down     # Meter Reads stops answering
    rm    /tmp/j73-switches/meter_reads.down     # …and is back

The module's own entry point asks `refuse_if_down("meter_reads")` and raises
exactly as an unreachable store would, so everything downstream — billing's
utility-wide stop, its support reference, the banner — is the real path.

**IT FAILS CLOSED, THREE WAYS.** (1) With no directory named, nothing is read
and nothing can be switched — the default, everywhere. (2) `production.py`
sets `WALK_SWITCHES_FORBIDDEN = True` and empties the directory, so a
production process never looks, whatever its environment says. (3) There is
no HTTP route, no setting a tenant can reach and no management command: the
only way to flip it is to write a file on the server's disk, which an
attacker able to do that does not need.
"""

from __future__ import annotations

from pathlib import Path

#: The modules a walk may take down, and nothing else.
KNOWN = frozenset({"meter_reads", "customers", "payments"})


class WalkSwitchDown(ConnectionError):
    """A module taken down by a walk switch — raised as the outage itself."""


def _directory() -> Path | None:
    from django.conf import settings

    if getattr(settings, "WALK_SWITCHES_FORBIDDEN", False):
        return None
    named = str(getattr(settings, "WALK_SWITCHES_DIR", "") or "").strip()
    return Path(named) if named else None


def is_down(module: str) -> bool:
    """Is `module` switched off for this walk? False unless a walk said so."""
    if module not in KNOWN:
        return False
    directory = _directory()
    return directory is not None and (directory / f"{module}.down").exists()


def refuse_if_down(module: str) -> None:
    """Raise as the outage when `module` is switched off; otherwise nothing."""
    if is_down(module):
        raise WalkSwitchDown(f"{module} is switched off by a walk switch (test only)")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-037@4cb6ab0 (sha1[:7] of 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md + 04-docs/05-modules/07-billing/02-business-rules.md, concatenated in that order)
# generated: 2026-09-30 by the final bulk-run lane (DEF-BIL-8510)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — test-only by design; no route may reach it) E=deferred(no-frontend-half — the banner it causes is the Check's) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ · pytest tests/test_us_bil_037_clerk_checks.py -k tc15✔ (red first; production settings refuse it) · J72 E6 and J73 F2 walked at 1440 and 1280
# exceptions: test-only by design; production.py sets WALK_SWITCHES_FORBIDDEN and an empty directory, and it fails closed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

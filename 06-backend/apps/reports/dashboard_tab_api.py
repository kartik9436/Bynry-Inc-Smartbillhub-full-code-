# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11`/`P4.12`/
#          `P4.13`. The server half of screen `3·1`, the Reports Dashboard tab.
#          Drawing p36–p38, read as IMAGES per B14 rule 42.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping — the tenant comes from the
#          request context, never from a parameter a caller can edit) ·
#          BR-SHL-011 (an unknown or impossible parameter FALLS BACK, never
#          refuses) · BR-REP-024 (an absent figure is a null with a reason)
# Tests:   06-backend/tests/test_rep_p4_dashboard_tab.py
# Impacts: apps/reports/api.py (its `urlpatterns` extends with these) ·
#          07-frontend/src/features/reports/ReportsDashboardPage.tsx
# ───────────────────────────────────────────────────────
"""`GET /reports/dashboard` — the one route screen `3·1` needs.

⚠ **A SEPARATE FILE FROM `api.py`, FOR LAW 11'S REASON RATHER THAN TIDINESS**,
exactly as `schedules_api.py` says of itself: `api.py` is 35 KB and several
lanes are editing it this week, and a pathspec commit takes the WHOLE file, so
the second lane to commit silently reverts the first. This phase touches
`api.py` in ONE line — the splice.

⚠ **`reports/dashboard` IS DECLARED ABOVE `reports/<str:key>` AND THE ORDERING
IS LOAD-BEARING.** `dashboard` sits in the same URL position as a report key and
is one of the four RESERVED segments (`P0.8`/`P5.2`) precisely because a utility
might name a report *Dashboard*. A catch-all declared first would swallow this
and a client asking for the tab would get a 422 about a report named
*dashboard*.

⚠ **ALWAYS 200.** There is no 404 and no 422 on this path: a malformed
`f.period` falls back to the newest period and an unknown `f.compare` falls back
to the default (BR-SHL-011). A screen inside a board pack that 500s on a
hand-edited URL is a locked door, and an absent figure is a `null` with a reason
beside it — a state of this deployment rather than an error the caller caused.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.permissions import AnyTenantRole
from core.tenancy import require_tenant

from . import dashboard_tab, report_seams


def _as_of(raw: Any) -> date | None:
    """One ISO day from the query string, or None. Never raises (BR-SHL-011)."""
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


def _tenant_today() -> date:
    """The tenant's own today, never the server's (BR-TEN-043 · IS-8).

    A utility in Hawaii reading its September dashboard at 21:00 on 30 September
    is not in October, and a bare `date.today()` here would put it there for
    three hours every day.

    ⚠ **RESOLVED THROUGH `report_seams.resolve` RATHER THAN THROUGH A NEW
    NAMED SEAM, AND THE REASON IS HARD-WON LAW 11.** `report_seams.py` is being
    edited by the Phase 6 lane this week; adding a four-line function to it
    would put this phase's work in the path where the second lane to commit
    silently reverts the first. The crossing is still declared — it is in this
    docstring and it names the module, the file and the function, which is what
    `G20` and the next reader are looking for. **It should become a named seam
    the moment `report_seams.py` is quiet**; REPORTED.

    `apps.tenancy.selectors.tenant_today` already answers UTC for a tenant with
    no timezone configured, so the fallback below is only reached when the
    tenancy module cannot be resolved at all.
    """
    found = report_seams.resolve(
        report_seams.TENANCY_MODULE, "tenant_today", kind=report_seams.TENANCY_KIND
    )
    today = found() if found is not None else None
    return today if isinstance(today, date) else date.today()


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def reports_dashboard(request: Any) -> Response:
    """`GET /reports/dashboard` — screen `3·1`.

    Reads nothing from the caller but the two controls the drawing has (p36 ③:
    *"Set the period · set what to compare it against · open a panel. That is
    the whole surface"*), and **writes nothing at all** (p36 ④, p38 ⓸ — *"No
    write of any kind, not even a remembered period"*).
    """
    require_tenant(request)
    return Response(
        dashboard_tab.dashboard(
            # `asOf` picks which period is NEWEST, so a board pack assembled on
            # the 2nd can still be reproduced. An argument, never a clock
            # (BR-TEN-043).
            as_of=_as_of(request.query_params.get("asOf")) or _tenant_today(),
            # BR-SHL-011's grammar spells a filter `f.<name>`; both are passed
            # through RAW and validated by the vocabulary built for THIS tenant,
            # never against a list spelled here — a second vocabulary drifting
            # from the first is BR-REP-006's own lesson.
            period=request.query_params.get("f.period") or None,
            compare=request.query_params.get("f.compare") or None,
        )
    )


#: Extended onto `api.urlpatterns`, ABOVE `reports/<str:key>` — see the module
#: docstring for why that ordering is load-bearing rather than tidy.
DASHBOARD_TAB_URLS = [path("reports/dashboard", reports_dashboard)]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.11 · P4.12 · P4.13 (05-prototype/09 Reports Build Brief.pdf pp36-38, read as IMAGES per B14 rule 42)
# screens: 3·1
# generated: 2026-09-27 by lane REP-P4-DASH
# checklist: A✔ B=n/a(the screen is its own file) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p4_dashboard_tab.py was run before this file existed and reported `django.urls.exceptions.Resolver404` on /api/brazosbend/reports/dashboard.
# exceptions: (1) this file is separate from `api.py` for hard-won law 11's reason, not for tidiness · (2) `asOf` is spelled as the shell dashboard spells it, because it means the same thing on both and a second spelling of one argument is the drift this repo keeps filing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

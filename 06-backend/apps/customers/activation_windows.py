# ── Trace ──────────────────────────────────────────────
# Change:   CR-162-BRC10 — a move-in before a New Connection is approved is
#           ALLOWED, and billing waits until the unit is activated.
# Ruling:   PO 2026-10-02, verbatim: *"B: allow it. The account opens, but
#           billing waits until the unit is activated"*, confirmed *"this is
#           correct"* on the worked comparison (Maria moves in 5 Oct, the unit
#           is activated 8 Oct: nothing for 5–7 Oct, the first bill from 8 Oct).
# Rules:    BR-CUS-103 (dark days stop the base charge — the SAME mechanism) ·
#           B4.3 ❄️ (`service_days / cycle_days`, unchanged) · hard rule 1
# Tests:    06-backend/tests/test_cr162_new_connection_lifecycle.py
# ───────────────────────────────────────────────────────
"""**The days an account held a unit before its service existed.**

HUMAN-OWNED (listed in `10-scripts/gates/human_owned.txt`).
HUMAN-REVIEW-PENDING — a 🔒 money path: what this returns decides how many days
of base charge a customer pays (row in `12-governance/09-human-review-ledger.md`,
`CR-162-BRC10`).

⚠ **NO NEW MONEY MATH, WHICH IS WHY IT COULD BE BUILT AT ALL.** Billing already
subtracts DARK DAYS from `service_days` — the days a service was cut
(`BR-CUS-103`, `disconnects.service_off_windows`) — and B4.3's frozen
`service_days / cycle_days` factor prices the rest. A unit not yet activated is
dark in exactly the same sense: nothing is connected. So these windows join the
cut windows in `selectors.service_off_windows`, in the same shape, and the
billing engine reads them without a line changing.

**What else already keeps a pending unit at $0.00, so this is the last piece:**
its meters and devices are earmarked in stage *Inventory* (`installed=False`) and
are not in `billable_asset_count`'s population until the activation installs
them; and no meter is read before it is fitted. The base charge was the one
figure that would have run from the move-in date.

Each window: `off_from` = the account's `opened_at`; `off_through` = the day
before the unit's service was activated, or `None` while it still waits (an
open end, as a cut that is not yet restored). A service activated on or before
the move-in leaves no window. One window per activation DAY, naming the services
it covers — a unit activated all at once (the ordinary case) is one window over
all of them; a unit activated service by service is several, and a bill that
charges a service still waiting beside one already live is refused as a partial
cut (`GATHER_PARTIAL_CUT`) rather than averaged — billing's own rule for the
same shape.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from apps.customers import seams


def _activation_day(moment: Any) -> date | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        zone = seams.tenant_timezone()
        return moment.astimezone(zone).date() if zone is not None else moment.date()
    return moment if isinstance(moment, date) else None


def awaiting_activation_windows(
    account: Any, build_services: list[dict[str, Any]] | None = None
) -> tuple[dict[str, Any], ...]:
    """The dark windows for one account (see the module docstring). `()` for
    every account on a unit no build touched, and for any account opened on or
    after its unit's activation. `build_services` is the unit's rows when the
    caller already holds them (the bulk Check's one query); otherwise they are
    read here."""
    unit_id = getattr(account, "unit_id", None)
    opened = getattr(account, "opened_at", None)
    if unit_id is None or not isinstance(opened, date):
        return ()
    rows = build_services if build_services is not None else seams.unit_build_services(unit_id)
    if not rows:
        return ()
    by_end: dict[date | None, list[dict[str, Any]]] = {}
    for row in rows:
        live_from = _activation_day(row.get("activated_at"))
        if live_from is not None and live_from <= opened:
            continue
        through = None if live_from is None else live_from - timedelta(days=1)
        by_end.setdefault(through, []).append(row)
    windows = []
    for through, members in by_end.items():
        windows.append(
            {
                "off_from": opened,
                "off_through": through,
                "cut_on": None,
                "restored_on": None if through is None else through + timedelta(days=1),
                "services": sorted({str(member["service"]) for member in members}),
                "reason": "awaiting_activation",
                "connection_no": members[0].get("connection_no"),
            }
        )
    return tuple(sorted(windows, key=lambda w: (w["off_through"] is None, w["off_through"] or opened)))

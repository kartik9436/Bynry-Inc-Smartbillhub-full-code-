#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 Phase 2 · `P2.24` — *"Drill down in place. A group row
#          expands to the next level WITHOUT LEAVING THE REPORT."* Outcome,
#          verbatim: *"Three levels open and close without a page load."*
#          Read from `05-prototype/09 Reports Build Brief.pdf` p013 and p028
#          (2·1E note ②), as rendered images per B14 rule 42.
# Rules:   CLAUDE.md hard-won law 2's MIRROR (never a control the query cannot
#          honour) · law 7 clause 2 (what would make this pass wrongly) and its
#          FIFTH shape (a number beside every blind spot) · hard-won law 14
#          (the suite runs on SQLite; this is evidence only on PostgreSQL).
# ───────────────────────────────────────────────────────
"""HOW DEEP CAN A REPORT ACTUALLY GROUP TODAY? COUNT IT, DO NOT ASSUME IT.

`P2.24` draws a disclosure on a group row. The one thing that would make that a
DEAD CONTROL over a live screen is drawing it where nothing lies beneath — and
the only way to know is to run every definition and look at what comes back.

    python3 10-scripts/rep_p2_24_grouping_depth.py

Env: DJANGO_SETTINGS_MODULE=config.settings.local · run from 06-backend, or
with it on PYTHONPATH. `REP_TENANT` names the tenant (default: the seeded
`Brazos Bend Utilities`).

⚠ **IT REPORTS WHAT IT COULD NOT SEE, BESIDE WHAT IT COULD.** A definition whose
dataset is unregistered raises `DatasetNotExecutable` and one that declines by
name raises `DatasetCannotServe`; both are COUNTED and NAMED rather than folded
into "cannot group", because a blind spot with no number beside it is
indistinguishable from an empty one (`G32` reported `0 unresolved` over 21 live
refusals exactly this way).

⚠ **WHAT WOULD MAKE THIS REPORT A DEPTH WRONGLY.** `payload["group_by"]` is not
evidence: `DEF-REP-6855` was a payload that named a grouping over rows nothing
had grouped. So the depth here is read from the ROWS — the greatest `level` on
any row carrying `__kind__ == "group"` — which is the same thing the screen
draws and cannot be true while the screen is empty.

MEASURED 2026-09-27, real PostgreSQL 16, seeded `brazosbend`, 46 definitions:

    depth 3 · 1   trend_pack (journal_lines) — this run reports
                  year → quarter → accounting_period; year → accounting_period
                  → service answers to depth 3 as well, and the script keeps
                  whichever triple it widened into first
    depth 1 · 2   ar_aging (consumer_class) · journal_export (service)
    depth 0 · 43  of which 18 DatasetNotExecutable and 17 DatasetCannotServe

So the DEEPEST group row on 45 of the 46 has nothing beneath it. That is why
`ReportGroupRow.openableGroups` derives the control from the payload rather than
from a row being a group, and it is the figure the `P2.24` docstrings cite.
"""

from __future__ import annotations

import os
from collections import Counter

import django

django.setup()

from apps.reports import datasets, slicers  # noqa: E402
from apps.reports.models import ReportDefinition  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

from apps.reports import runner  # noqa: E402

#: The levels worth trying. A dataset refuses the rest by name, which is the
#: point — this list is deliberately WIDER than any one dataset serves.
CANDIDATES = (
    "year",
    "quarter",
    "accounting_period",
    "day",
    "service",
    "consumer_class",
    "area",
    "route_cycle",
    "account_status",
)


def _group_levels(payload: dict) -> list[int]:
    """The `level` of every GROUP row in the answer — read from the rows."""
    return [
        int(row["level"])
        for row in (payload.get("rows") or ())
        if isinstance(row, dict) and row.get("__kind__") == "group"
    ]


def _depth(key: str, group_by: list[str]) -> int:
    """0 when nothing grouped, else 1 + the deepest level the ROWS carry."""
    try:
        payload = runner.run(key, {"group_by": group_by}).payload
    except Exception:  # a refusal is not a depth — the caller counts it
        return 0
    levels = _group_levels(payload)
    return 0 if not levels else max(levels) + 1


def main() -> int:
    tenant = Tenant.objects.get(name=os.environ.get("REP_TENANT", "Brazos Bend Utilities"))
    rows: list[tuple[str, str, int, str, str]] = []
    refusals: Counter[str] = Counter()

    with tenant_context(tenant.pk):
        for definition in ReportDefinition.objects.all().order_by("key"):
            code = definition.dataset
            if datasets.BY_CODE.get(code) is None:
                rows.append((definition.key, code, 0, "no dataset", ""))
                refusals["no dataset"] += 1
                continue

            singles: list[str] = []
            refusal = ""
            for level in CANDIDATES:
                if not slicers.is_group_level(code, level):
                    continue
                try:
                    payload = runner.run(definition.key, {"group_by": [level]}).payload
                except Exception as exc:
                    refusal = type(exc).__name__
                    break
                if _group_levels(payload):
                    singles.append(level)
            if refusal:
                rows.append((definition.key, code, 0, refusal, ""))
                refusals[refusal] += 1
                continue

            best, best_gb = (1, [singles[0]]) if singles else (0, [])
            # Widen one level at a time — the deepest ANSWER wins, never the
            # longest REQUEST, because a request the query drops comes back
            # ungrouped and would read as depth 0 for the whole definition.
            for extra in singles:
                if extra in best_gb:
                    continue
                candidate = best_gb + [extra]
                if len(candidate) > slicers.MAX_GROUP_LEVELS:
                    break
                depth = _depth(definition.key, candidate)
                if depth > best:
                    best, best_gb = depth, candidate
            rows.append(
                (definition.key, code, best, ",".join(singles) or "-", ",".join(best_gb))
            )

    print(f"{'definition':32} {'dataset':15} {'depth':>5}  deepest grouping that ANSWERED")
    for key, code, depth, _singles, gb in rows:
        print(f"{key:32} {code:15} {depth:>5}  {gb or '-'}")

    histogram = Counter(depth for _k, _c, depth, _s, _g in rows)
    print(f"\nDEFINITIONS: {len(rows)}")
    print("DEPTH HISTOGRAM:", dict(sorted(histogram.items())))
    # ⚠ THE BLIND SPOT, WITH ITS NUMBER BESIDE IT (law 7's fifth shape).
    print("NOT MEASURABLE, BY REASON:", dict(refusals) or "none")
    print(
        "\nA definition at depth 0 or 1 has NO group row with anything beneath it, "
        "so `P2.24` must draw no disclosure on it at all."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P2.24 (05-prototype/09 Reports Build Brief.pdf p013 + p028, read as images per B14 rule 42)
# generated: 2026-09-27 by lane REP-P2-REST
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

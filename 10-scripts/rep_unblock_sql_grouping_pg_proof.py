#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.17 — grouping made REAL, in SQL.
#           DEF-REP-6855 · DEF-REP-6875 · DEF-REP-6876.
# Rules:    CLAUDE.md hard rule 1 (app.tenant_id before any read) · hard rule 2
#           (money 4 dp, never a float) · hard-won law 14 (the suite is SQLite
#           and a GROUP BY is a claim about PostgreSQL) · law 7 (a check's
#           output must distinguish pass from fail TO A READER)
# ───────────────────────────────────────────────────────
"""THE GROUP SUBTOTALS FOOT TO THE FOOTER, ON A REAL DATABASE.

⚠ **WHY THIS IS A SCRIPT AND NOT A PYTEST CASE.** `config/settings/test.py`
hardcodes in-memory SQLite and ignores `DATABASE_URL` (hard-won law 14). Every
assertion below is about what PostgreSQL's `GROUP BY` returns over a queryset
with `Trunc` expressions in it and over the tenant's own RLS-scoped rows, and
neither is a thing the suite's database can answer. `tests/test_rep_unblock_grouping.py`
proves the WIRING against a stub; this proves the ARITHMETIC against the books.

⚠ **AND IT ASSERTS THE RELATIONSHIP, NOT THE FIGURES.** A proof that each
subtotal equalled a literal would pass just as happily over three numbers that
do not add up to the footer — which is exactly `DEF-REP-6875`. What is checked is
that Σ(subtotals at every level) EQUALS the footer, and that a group's own
filters reopen exactly as many rows as the group says it holds.

Run:
    10-scripts/proof-db.sh clone repunblock --template <a seeded template>
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_repunblock \\
      .venv/bin/python ../10-scripts/rep_unblock_sql_grouping_pg_proof.py

It READS ONLY and writes nothing — hard rule 4, and the reports module writes
nothing on a run in any case (BR-REP-018).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.reports import queries, runner  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

#: The reports the two newly-registered datasets serve, and the levels each can
#: cut in SQL. `trend_pack` is on `journal_lines`; `cash_reconciliation` is on
#: `payments`.
CASES: tuple[tuple[str, str], ...] = (
    ("trend_pack", "accounting_period"),
    ("trend_pack", "service"),
    ("trend_pack", "accounting_period,service"),
    ("trend_pack", "year,quarter,accounting_period"),
    ("cash_reconciliation", "accounting_period"),
    ("cash_reconciliation", "year,accounting_period"),
)

failures: list[str] = []


def check(ok: bool, sentence: str) -> None:
    """One line a reader can act on. `PASS`/`FAIL` in the text and not only in
    the exit code — hard-won law 7's third habit."""
    print(f"  {'PASS' if ok else 'FAIL'}  {sentence}")
    if not ok:
        failures.append(sentence)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--from", dest="start", default="2026-01-01")
    parser.add_argument("--to", dest="end", default="2026-12-31")
    args = parser.parse_args()

    print("registry")
    check("journal_lines" in queries.DATASET_QUERIES, "`journal_lines` is in DATASET_QUERIES")
    check("payments" in queries.DATASET_QUERIES, "`payments` is in DATASET_QUERIES")

    tenant = tenancy_models.Tenant.objects.get(subdomain=args.tenant)
    window = {"from": args.start, "to": args.end}

    with tenant_context(str(tenant.id)):
        for key, levels in CASES:
            print(f"\n{key} · group by {levels}")
            plain = runner.run(key, dict(window))
            params = dict(window)
            params["group_by"] = levels
            grouped = runner.run(key, params)

            rows = grouped.payload["rows"]
            groups = [r for r in rows if isinstance(r, dict) and r.get("__kind__") == "group"]
            footer = grouped.payload["totals"]

            # ⚠ THE FALSE PASS THIS GUARDS: a grouping that returns rows proves
            # nothing if the ungrouped run returns the same rows. That is
            # DEF-REP-6855 measured — 20 of 20 identical.
            check(bool(groups), f"{len(groups)} group rows served")
            check(rows != plain.payload["rows"], "the grouped rows DIFFER from the ungrouped rows")
            check(
                grouped.payload.get("group_by") == levels.split(","),
                "the payload names the grouping it actually applied",
            )

            by_level: dict[int, list[dict]] = {}
            for group in groups:
                by_level.setdefault(group["level"], []).append(group)

            for level, members in sorted(by_level.items()):
                for measure, value in footer.items():
                    if isinstance(value, dict) or value is None:
                        continue  # a refused figure has no Σ to compare
                    if measure not in (members[0].get("subtotals") or {}):
                        continue
                    figures = [m["subtotals"][measure] for m in members]
                    if any(isinstance(f, dict) for f in figures):
                        continue  # refused at the subtotal too — lawful
                    total = sum(Decimal(str(f)) for f in figures)
                    check(
                        total == Decimal(str(value)),
                        f"level {level}: Σ{measure} {total} == footer {value}",
                    )
                check(
                    sum(m["rows"] for m in members) == footer.get("lines", footer.get("payments")),
                    f"level {level}: Σrows {sum(m['rows'] for m in members)} == the footer's count",
                )

            # ── the drill-through door (DEF-REP-6869's EFFECT assertion) ─────
            for group in groups:
                filters = group.get("filters")
                if filters is None:
                    print(
                        f"    n/a   {group['dimension']}={group['value']!r}: no reproducing "
                        "filters, served as a refusable absence"
                    )
                    continue
                back = dict(window)
                back.update(filters)
                back["per"] = "all"
                served = len(runner.run(key, back).rows)
                check(
                    served == group["rows"],
                    f"{group['dimension']}={group['value']!r}: its filters reopen "
                    f"{served} rows and it claims {group['rows']}",
                )

        # ── the named refusals, which are the other half of registration ────
        print("\nnamed refusals (DatasetCannotServe, never a plausible report)")
        for key in sorted(
            set(queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED)
            | set(queries.PAYMENTS_DEFINITIONS_NOT_SERVED)
        ):
            try:
                runner.run(key, dict(window))
            except queries.DatasetCannotServe as exc:
                check(len(exc.reason) > 120, f"{key} refuses with a reason a reader can act on")
            except Exception as exc:  # noqa: BLE001
                check(False, f"{key} raised {type(exc).__name__} rather than DatasetCannotServe")
            else:
                check(False, f"{key} SERVED a report the dataset may not serve")

    print()
    if failures:
        print(f"FAILED — {len(failures)} check(s):")
        for sentence in failures:
            print(f"  · {sentence}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

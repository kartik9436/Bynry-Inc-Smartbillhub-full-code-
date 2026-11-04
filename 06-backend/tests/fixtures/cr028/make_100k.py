# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W0-T2 (B16 §9) — the 100,000-row synthetic meters CSV
#           for AST-W3-T6's async-bar proof (CR-026: cap 100,000 rows,
#           ASYNC_ROW_BAR = 5_000 → 202 + job).
# Rules:    CR-026 (volume + async bar) · BR-AST-045 (blank UNIT_REF is
#           ACCEPTED → inventory) · B16 §4.7b (the meters target's columns)
# Tests:    the W3 lane's target tests consume the OUTPUT of this script; the
#           header row is pinned against assets_meters.csv by
#           tests/test_cr028_seed.py
# Impacts:  tests/fixtures/cr028/assets_meters.csv (same header, one source)
# ───────────────────────────────────────────────────────
"""Generate the 100,000-row meters import CSV — DETERMINISTICALLY.

⚠ DO NOT COMMIT THE GENERATED FILE. It is ~12 MB of derived data; one
generated file committed twice is hard-won law 5's drift waiting to happen.
The default output name carries `.generated.` and `.gitignore` beside this
script excludes it — regenerate on demand:

    .venv-ci/bin/python tests/fixtures/cr028/make_100k.py
    .venv-ci/bin/python tests/fixtures/cr028/make_100k.py --rows 5001 --out /tmp/bar.csv

Determinism is the point (no Date.now, no unseeded random): the async-bar test
must chase the SAME file every run, so the row mix is a fixed-seed
`random.Random(20260822)` and two invocations are byte-identical — the SHA-256
the runner records at stage 1 (CR-025/B16 §4.7a) is stable, which is what lets
a receipt assertion pin it.

The row mix mirrors assets_meters.csv's cases at volume so validation has real
work at 100k, in fixed proportions: ~2% blank UNIT_REF (BR-AST-045 →
inventory), ~1% bad unit refs, ~0.5% non-integer multipliers, one duplicate
meter number pair every 10,000 rows. Everything else is happy rows cycling the
48 seeded Silver Creek units.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from pathlib import Path

#: MUST equal assets_meters.csv's header — one target, one column set
#: (B16 §4.7b). test_cr028_seed.py asserts the two never drift apart.
HEADER = [
    "METER_NO",
    "METER_TYPE",
    "SERVICE",
    "READ_METHOD",
    "MULTIPLIER",
    "UNIT_REF",
    "MFR",
    "MODEL",
    "INSTALL_DT",
    "CERT_DUE",
    "WARRANTY_END",
    "SUPPLIER",
    "COST",
    "LEGACY",
]

SEED = 20260822  # the ruling's date — fixed forever, or the SHA-256 moves
DEFAULT_ROWS = 100_000  # CR-026's cap, exactly

_MAKES = (
    ("Itron Inc", "OpenWay Riva", "ami", "289.0000"),
    ("Badger Meter", "ORION LTE-M", "amr", "244.0000"),
    ("Neptune", "E-Coder R900i", "walk_by", "198.0000"),
)


def generate(out_path: Path, rows: int = DEFAULT_ROWS) -> str:
    """Write `rows` data rows + the header; return the file's SHA-256 hex."""
    rng = random.Random(SEED)
    with out_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for i in range(rows):
            meter_no = f"E-{100000 + i}"
            supplier, model, kind, cost = _MAKES[i % len(_MAKES)]
            roll = rng.random()
            if i % 10_000 == 9_999:
                meter_no = f"E-{100000 + i - 1}"  # the duplicate-number pair
            if roll < 0.02:
                unit_ref = ""  # BR-AST-045: accepted → inventory
            elif roll < 0.03:
                unit_ref = f"SCW-U-{900 + (i % 90):03d}"  # no such unit → reject
            else:
                unit_ref = f"SCW-U-{(i % 48) + 1:03d}"
            multiplier = "1.5" if 0.03 <= roll < 0.035 else "1"
            day = (i % 28) + 1
            month = (i % 12) + 1
            writer.writerow(
                [
                    meter_no,
                    kind,
                    "electric",
                    kind,
                    multiplier,
                    unit_ref,
                    supplier,
                    model,
                    f"2026-{month:02d}-{day:02d}",
                    f"2027-{month:02d}-{day:02d}",
                    f"2031-{month:02d}-{day:02d}",
                    supplier,
                    cost,
                    f"LG-{700000 + i}",
                ]
            )
    return hashlib.sha256(out_path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).with_name("assets_meters_100k.generated.csv"),
        help="output path (default: beside this script, gitignored)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help="data rows to write (default 100,000 — CR-026's cap)",
    )
    args = parser.parse_args()
    digest = generate(args.out, args.rows)
    print(f"{args.out}: {args.rows} rows · sha256 {digest}")


if __name__ == "__main__":
    main()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028 / B16 §9 AST-W0-T2 + CR-026 (100k cap, async bar) + CR-025 (sample CSV/hash)
# generated: 2026-08-22 by story-coder (CR-028 AST-W0 lane)
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run twice, byte-identical output confirmed by SHA-256 (see the lane report)
# exceptions: the generated CSV is NEVER committed (hard-won law 5 — one generated file, derived on demand); .gitignore beside this script enforces it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

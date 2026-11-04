# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6980 (2026-09-27) — `$799.95` was typed into two test files
#          as the seeded catalogue's priced total. It was measured correctly
#          and then `OQ-CUS-12518` (PO 2026-09-21, *"reconnection fee is $75 -
#          fix the code and seed"*) moved `RECON` from $45.00 to $75.00. Both
#          files went red, in a suite nobody runs whole, and the cheapest move
#          for the next reader was to type $829.95 over it — which is how a
#          figure nobody has checked becomes the signed one.
# Rules:   CLAUDE.md hard rule 2 (money stored to 4 decimals) · B12 §No
#          hard-coded values · BR-BIL-007 (a charge code's amount is a SEED the
#          tenant edits, never a constant)
# Tests:   tests/test_def_438_parity.py · tests/test_def_498_def_493_charge_code_recurrence.py
# Impacts: 06-backend/apps/tenancy/fixtures/lookup_defaults.json
# ───────────────────────────────────────────────────────
"""What the provisioning fixture's charge codes add up to, READ not typed.

`apps/tenancy/fixtures/lookup_defaults.json` is what a tenant is PROVISIONED
from, so summing it and comparing against the catalogue the product SERVES
tests the seeding path — fixture → `charges` rows → `charge_code_facts` — which
is exactly what sits between the two. A row dropped, a `percent` read as an
`amount`, a decimal mangled in transit: all still bite.

⚠ **IT DELIBERATELY PINS NO PRICE.** Pinning one figure is the caller's job and
each caller does it by name for the figure a PO ruled on. A helper that froze
all eighteen amounts would go red on a legitimate ruling every time, which is
how a test stops being read.
"""

from __future__ import annotations

import json
import pathlib
from decimal import Decimal

FIXTURE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "apps"
    / "tenancy"
    / "fixtures"
    / "lookup_defaults.json"
)


def seeded_charge_codes() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["charge_codes"]


def seeded_priced_total() -> Decimal:
    """Σ of every seeded charge code that states a flat `amount`.

    `$829.95` on 2026-09-27, over 18 codes. It was `$799.95` until
    `OQ-CUS-12518` took `RECON` from `$45.00` to `$75.00` on 2026-09-21 —
    `$30.00`, the whole of the difference, with the COUNT unchanged.
    """
    priced = [row for row in seeded_charge_codes() if row.get("amount") is not None]
    return sum((Decimal(str(row["amount"])) for row in priced), Decimal("0"))

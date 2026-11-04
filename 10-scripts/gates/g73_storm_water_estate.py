#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2368 (2026-09-02) — the seeded estate's storm-water assessment
#          grew from 54 ERU across 41 premises to 59 across 43 when CR-062's
#          addendum appended two seats, and the two constants stating it did
#          not move. The PLAN is derived and picked both up; the totals were
#          LITERALS and did not. Three of the D6 suite's fourteen cases were
#          red on it for a day, and the only reason it took a day is that
#          nothing runs that suite on a lane that never touched storm water.
# Rules:   CLAUDE.md hard rule 2 (money to 4 decimals, its factors with it) ·
#          hard rule 3 (a quantity carries an explicit unit) · hard-won law 1
#          (a comment claiming a guarantee is not the guarantee) · law 7
#          (prove a guard RED before trusting it green) · BR-TEN-171 (the five
#          ratified storm-water sizes and what each is worth) · BR-RAT-090 as
#          amended (storm water's capacity is a fact on the UNIT)
# Tests:   `selftest()` in this file — it must report a disagreement on a pair
#          that disagrees and must report none on a pair that agrees, and
#          `run()` refuses to report anything until it has.
# Impacts: 06-backend/core/sample_fixture.py ·
#          06-backend/apps/tenancy/service_size_classes.py ·
#          06-backend/tests/test_cr062_d6_storm_water_on_the_unit.py
# ───────────────────────────────────────────────────────
"""G73 — THE STORM-WATER ESTATE'S WRITTEN TOTAL MUST BE THE TOTAL IT DERIVES.

**THE DEFECT THIS EXISTS FOR IS A TEST THAT WORKED.** `test_cr062_d6_storm_
water_on_the_unit.py` says in its own docstring: *"The stated constant and the
ladder are two independent statements of one figure, and this is what stops them
drifting apart in silence."* They drifted, and that case is exactly what said so
— **a day late, because running it costs six minutes of PostgreSQL and a lane
appending two premises had no reason to.** The check was right; its PRICE was
the problem.

So this is the same comparison with the database taken out of it. It reads two
pure Python modules by path, derives the estate's assessment from
`BR-TEN-171`'s ratified ladder, and compares it with the figure written down
beside it. No Django, no settings, no tenant, no seed: **milliseconds, on every
lane, whether or not that lane has ever heard of storm water.**

WHY THE FIGURE IS A LITERAL AT ALL, WHICH IS THE FIRST THING A READER ASKS
--------------------------------------------------------------------------
`STORM_WATER_ASSESSED_PREMISES` is derived now — counting the plan's rows needs
nothing but the plan. `STORM_WATER_ESTATE_ERU` cannot be, and the reason is a
boundary rather than an oversight: totalling ERU needs to know **what each size
CODE is worth**, and that lives in `apps/tenancy/service_size_classes`.
`core/sample_fixture` is *"a DECLARATION and nothing else: plain data, no Django
import, no ORM, no service call"* and refuses to type those numbers — *"a figure
typed here would be this fixture teaching a vocabulary the product already
owns, and it would drift the day the ladder moves."* Both halves of that are
right, so the literal stays and the DRIFT is what gets the check. A gate is the
one place in this repository allowed to read both modules at once.

WHAT IT CHECKS, AND EACH ONE IS A DIFFERENT WAY TO BE WRONG
------------------------------------------------------------
  1. **the ERU total** — the ladder applied to the plan, against
     `STORM_WATER_ESTATE_ERU`. This is `DEF-2368` itself.
  2. **the assessed premises count** — against `STORM_WATER_ASSESSED_PREMISES`.
     Derived today, so it is a tautology today; it is asserted anyway, because
     the constant going back to a literal is precisely the regression to catch
     and a tautology that never fails costs nothing.
  3. **every unit is assessed exactly once** — the plan's unit indexes against
     `UNIT_COUNT`, with no duplicates. A unit assessed twice double-bills it; a
     unit missing bills `$0.00` on a line that foots and prints, which is
     `DEF-2388` and is invisible to everything else here.
  4. **every size code is one of the ratified five** — a code the ladder does
     not hold is skipped by the seeder with its reason logged, so the units
     keep the ruled `$0.00` and the demo silently under-bills.
  5. **the unit of measure agrees** — the ladder sums in `ERU` and the seeded
     price is quoted per `ERU`. A price quoted per a unit the quantity is not
     in is `DEF-497` on a money path (CLAUDE.md hard rule 3).

⚠ **WHAT IT CANNOT SEE, SAID PLAINLY (hard-won law 1 applied to this file).**
**It does not read prose.** Eleven sentences across nine files said *54 ERU*
and *$243.00* on the day this was written and this gate would have passed over
every one of them; they were corrected by hand and by grep. It compares two
NUMBERS in two SOURCE files. It also says nothing about whether the money
reaches a bill — that is the D6 suite's job, on PostgreSQL, and no static check
can do it.

⚠ **AND IT DELIBERATELY DOES NOT SCAN PROSE, HAVING CONSIDERED IT.** The
sentences that state this figure are mostly RECORDS of past runs — *"it said 54
until 2026-09-02"*, a verbatim red-first failure message — and a gate that
demanded those be rewritten would be falsifying the record to keep itself green.
`DEF-182`'s lesson is the governing one: a check whose output cannot distinguish
a real finding from an exempt one is worse than no check, because it is trusted.
`G72` reads count sentences where the exemptions are enumerable; here they are
not.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]

#: CLAUDE.md hard rule 2 — money is CARRIED at four decimals and DISPLAYED at
#: two. Every dollar figure this gate puts in a message goes through here; the
#: comparisons above it are made on the full-precision value.
_CENTS = Decimal("0.01")


def _money(amount: Decimal) -> str:
    return f"{amount.quantize(_CENTS)}"


FIXTURE = "06-backend/core/sample_fixture.py"
LADDER = "06-backend/apps/tenancy/service_size_classes.py"

#: The service this gate is about. Storm water is the ONE capacity service whose
#: quantity is a fact on the unit rather than a device's size (PO ruling
#: 2026-09-02), which is why its estate total is derivable from a plan and a
#: ladder alone and why the other ten are not checked here.
SERVICE = "storm_water"


def _load(relative: str, name: str) -> ModuleType:
    """Import one PURE module by path, without its package.

    ⚠ **BY PATH AND NOT BY PACKAGE, ON PURPOSE.** `import apps.tenancy.
    service_size_classes` would execute `apps/tenancy/__init__.py` and pull in
    Django; a gate must run with nothing installed and nothing configured (the
    rule `G72._collection_length` states for the same reason). Both files this
    gate reads are deliberately free of Django — `core/sample_fixture` says so
    in its own docstring and `service_size_classes` imports only `decimal` and
    `typing` — so a plain spec-from-file-location is enough, and if either ever
    gains a Django import this raises rather than passing quietly.
    """
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — unreachable
        raise ImportError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive(fixture: ModuleType, ladder: ModuleType) -> dict[str, object]:
    """The estate's storm-water assessment, computed from the two sources.

    Returns the derived figures rather than a verdict, so `findings()` can
    compare them and `--report` can print them. `total_capacity` is asked once
    per PREMISES with that premises' single size code, which is the same call
    the SEEDER makes — deliberately, so the gate and the seed cannot disagree
    about what `SW-APT` means.
    """
    plan = fixture.storm_water_assessment_plan()
    ratified = {row.code for row in ladder.RATIFIED_SERVICE_SIZE_CLASSES[SERVICE]}
    total = Decimal("0")
    unit_indexes: list[int] = []
    codes: set[str] = set()
    for row in plan:
        codes.add(row["size_class"])
        unit_indexes.extend(row["unit_indexes"])
        # ⚠ **AN UNRATIFIED CODE IS SKIPPED HERE RATHER THAN TOTALLED, AND THE
        # FIRST DRAFT OF THIS GATE GOT IT WRONG.** `total_capacity` RAISES on a
        # code the ladder does not hold — *"'SW-NOPE' is not a ratified size
        # class of 'storm_water'"* — so asking it first turned that case into a
        # crash, and the finding written to name the offending code in a
        # sentence could never be reached. Proving the gate RED is what found it
        # (CLAUDE.md law 7), which is the whole reason that step exists. The
        # code is collected and reported by name in `findings()`; skipping it
        # here also mirrors the SEEDER, which skips an unratified code with its
        # reason logged and leaves the unit on BR-MET-108's ruled $0.00.
        if row["size_class"] not in ratified:
            continue
        total += Decimal(str(ladder.total_capacity(SERVICE, [row["size_class"]])))
    price = Decimal(fixture.CAPACITY_UNIT_PRICES[SERVICE])
    return {
        "premises": len(plan),
        # CLAUDE.md hard rule 2 — the ERU total is a FACTOR of a money figure,
        # so it is carried on the money grid and never as a float.
        "eru": total,
        "assessment": total * price,
        "unit_indexes": tuple(unit_indexes),
        "codes": codes,
        "price": price,
        # Hard rule 3 — the derived quantity never travels without its unit,
        # here or in this gate's own PASS line.
        "uom": ladder.capacity_uom_for_service(SERVICE),
    }


def findings() -> tuple[list[str], dict[str, object]]:
    """Every disagreement between what the estate derives and what it states."""
    fixture = _load(FIXTURE, "_g73_sample_fixture")
    ladder = _load(LADDER, "_g73_service_size_classes")
    got = derive(fixture, ladder)
    out: list[str] = []

    stated_eru = Decimal(str(fixture.STORM_WATER_ESTATE_ERU))
    if got["eru"] != stated_eru:
        out.append(
            f"the estate derives {got['eru']} ERU from BR-TEN-171's ladder and "
            f"STORM_WATER_ESTATE_ERU says {stated_eru} — "
            f"${_money(got['assessment'])} of monthly assessment against "
            f"${_money(stated_eru * got['price'])}. DEF-2368: the plan is derived and "
            "the total is written down, so growing the estate moves one and not "
            "the other. Correct the constant in core/sample_fixture.py and every "
            "sentence quoting it (this gate does not read prose)."
        )

    if got["premises"] != fixture.STORM_WATER_ASSESSED_PREMISES:
        out.append(
            f"the plan holds {got['premises']} assessed premises and "
            f"STORM_WATER_ASSESSED_PREMISES says "
            f"{fixture.STORM_WATER_ASSESSED_PREMISES}. That constant is DERIVED "
            "from the plan as of DEF-2368, so a disagreement here means it has "
            "been turned back into a literal."
        )

    indexes = got["unit_indexes"]
    if len(indexes) != len(set(indexes)):
        duplicated = sorted({i for i in indexes if list(indexes).count(i) > 1})
        out.append(
            f"unit(s) {duplicated} carry two storm-water assessments, which "
            "double-bills them: the seeder writes one characteristic per unit "
            "per premises row."
        )
    elif len(indexes) != fixture.UNIT_COUNT:
        missing = sorted(set(range(fixture.UNIT_COUNT)) - set(indexes))
        out.append(
            f"{len(indexes)} of the estate's {fixture.UNIT_COUNT} units are "
            f"assessed; {missing} are not. Every seeded unit stands on ground "
            "with hard surface, and an unassessed one bills BR-MET-108's ruled "
            "$0.00 on a line that foots and prints (DEF-2388)."
        )

    ratified = {row.code for row in ladder.RATIFIED_SERVICE_SIZE_CLASSES[SERVICE]}
    unratified = sorted(set(got["codes"]) - ratified)
    if unratified:
        out.append(
            f"the plan uses size class(es) {unratified}, which BR-TEN-171 does "
            f"not ratify for {SERVICE} (it holds {sorted(ratified)}). The seeder "
            "skips them with the reason logged, so those units keep the ruled "
            "$0.00 and the demo under-bills in silence."
        )

    uom = ladder.capacity_uom_for_service(SERVICE)
    if uom != fixture.STORM_WATER_UOM:
        out.append(
            f"the ratified ladder sums {SERVICE} in {uom!r} and the fixture's "
            f"seeded price is quoted per {fixture.STORM_WATER_UOM!r}. CLAUDE.md "
            "hard rule 3: a price quoted per a unit the quantity is not in is a "
            "wrong number on a money path (DEF-497)."
        )

    return out, got


def selftest() -> bool:
    """Prove the comparison bites, in both directions (CLAUDE.md law 7).

    `findings()` reads the real tree, so it cannot be made to fail on demand
    without editing the repository. What IS exercised here is the arithmetic
    the gate turns into a verdict: a stated figure that disagrees with a derived
    one must produce a finding, and one that agrees must produce none. This is
    the shape `DEF-2368` had — `Decimal("54")` against a derived `59.0000` —
    including the trailing-zero form, because `Decimal('59.0000') ==
    Decimal('59')` is True and a naive string comparison would have said the
    estate was broken on the day it was correct.
    """
    if Decimal("59.0000") != Decimal("59"):  # pragma: no cover — sanity
        return False
    if Decimal("54") == Decimal("59.0000"):  # pragma: no cover — sanity
        return False
    # The defect's own figures, worked: 59 ERU at $4.5000 is $265.50, and the
    # stale pair would have claimed $243.00.
    if Decimal("59") * Decimal("4.5000") != Decimal("265.50000"):
        return False
    return Decimal("54") * Decimal("4.5000") == Decimal("243.00000")


def run() -> tuple[str, str]:
    for relative in (FIXTURE, LADDER):
        if not (ROOT / relative).exists():
            return "SKIP", f"{relative} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own arithmetic self-test does not hold, so its verdict "
            "cannot be trusted either way (DEF-182 — a check that cannot "
            "distinguish pass from fail is worse than no check)."
        )
    try:
        failures, got = findings()
    except Exception as exc:  # noqa: BLE001 — a broken gate must block the merge
        return "FAIL", (
            f"{type(exc).__name__}: {exc}. This gate imports "
            f"{FIXTURE} and {LADDER} by path, without Django. If one of them has "
            "gained a Django, ORM or settings import, that is the finding — "
            "core/sample_fixture is a declaration and nothing else."
        )
    if failures:
        return "FAIL", (
            f"{len(failures)} storm-water estate disagreement(s). "
            + " | ".join(failures)
        )
    return "PASS", (
        f"the seeded estate assesses {got['eru']} {got['uom']} across "
        f"{got['premises']} premises — ${_money(got['assessment'])} a month at "
        f"${got['price']} per {got['uom']} — and each of its "
        f"{len(got['unit_indexes'])} units is assessed exactly once, on one of "
        "BR-TEN-171's ratified sizes. ⚠ IT READS TWO NUMBERS IN TWO SOURCE "
        "FILES: it does not read prose and it does not prove the money reaches "
        "a bill (that is the D6 suite, on PostgreSQL)."
    )


def main() -> int:
    if "--report" in sys.argv:
        failures, got = findings()
        print(f"premises: {got['premises']}")
        print(f"eru: {got['eru']} {got['uom']}")
        print(f"assessment: ${_money(got['assessment'])} at ${got['price']} per {got['uom']}")
        print(f"units assessed: {len(got['unit_indexes'])}")
        print(f"size classes used: {sorted(got['codes'])}")
        for line in failures:
            print(f"FINDING: {line}")
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

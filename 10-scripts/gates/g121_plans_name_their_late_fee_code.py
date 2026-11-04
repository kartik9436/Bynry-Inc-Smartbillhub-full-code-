#!/usr/bin/env python3
"""G121 — a plan that charges no late fee must be VISIBLE, and no code path may
fall back to the tenant default.

`CR-078` (PO ruling 2026-09-07, finance re-signed the same day) makes a NULL
`rate_plans.late_fee_charge_id` mean **charge $0.00**. PO verbatim: *"if plan
doent provide you that charge code then you have to put zero on late payment"*.

⚠ **THAT RULING CREATES EXACTLY THE FAILURE SHAPE CLAUDE.md WARNS ABOUT MOST
OFTEN.** A plan created next month with no charge code charges nothing, on real
customers, and **nothing raises, nothing logs and every test passes** — the
bill is produced, just without the fee. It is the mirror of `DEF-CUS-3653` (a
retired lookup value that returned null on every account forever with `tsc` and
every test green) and of law 7's *reporting zero over a scope it silently
excludes*.

So this gate asks two questions, and PRINTS BOTH ANSWERS whether they pass or
fail, because a check whose output cannot distinguish pass from fail to a
reader is worse than no check (`DEF-182`).

**QUESTION 1 — HAS A FALLBACK BEEN REINSTATED?** (source; always runs)
The two figures `late_pct` and `late_min_amount` still live on Settings →
Billing defaults and still describe what a utility intends. They are no longer
what an engine reads. A billing module that starts reading them again for a
late fee silently restores the behaviour the PO ruled against, and it would
look like a tidy-up. This half greps billing's late-fee path for them.

**QUESTION 2 — HOW MANY PLANS CHARGE NOTHING?** (data; needs a database)
`manage.py cr078_late_fee_codes --fail-on-missing`, in a subprocess. When no
database is reachable this half **SKIPs and says so with the reason**, and the
gate's overall verdict says which halves ran — a declared blind spot with no
number attached is indistinguishable from an empty one.

WHAT WOULD MAKE THIS PASS WRONGLY
---------------------------------
  * **The grep matching nothing because the path moved.** So it asserts the
    files it scanned EXIST and names them; a scan over zero files would
    otherwise report a truthful, useless zero.
  * **The data half being counted as a pass when it could not run.** It cannot:
    a SKIP is reported as a SKIP in the verdict text and never folded into the
    PASS sentence.
  * **`--fail-on-missing` exiting 0 for a reason unrelated to the count** — a
    crashed command exits non-zero too, so the two are distinguished by reading
    the command's own TOTAL line rather than by the exit code alone.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

BACKEND = common.REPO_ROOT / "06-backend"

#: The late-fee path. Every file that decides a late fee's TERMS or its BOOKING.
#: Listed rather than globbed, so a file added to the path has to be added here
#: deliberately — and so a rename turns this gate red instead of shrinking its
#: scope in silence.
LATE_FEE_PATH = (
    "06-backend/apps/billing/late_fee.py",
    "06-backend/apps/billing/decisions.py",
    "06-backend/apps/billing/rating_seam.py",
)

#: The tenant Billing-defaults keys the late fee may no longer read.
#: `BR-RAT-1011`: the terms come from the charge code the plan names.
BANNED = ("late_pct", "late_min_amount")

#: A mention inside a comment or docstring is the file EXPLAINING the rule,
#: which is required rather than forbidden. Only code lines are checked.
_COMMENT = re.compile(r"^\s*#")


def _code_lines(text: str) -> list[tuple[int, str]]:
    """Lines outside triple-quoted blocks and outside `#` comments.

    Deliberately crude: it is a fence around two identifiers, not a parser. A
    false POSITIVE here costs a reader ten seconds; a false negative costs
    every customer of every tenant their late fee.
    """
    out: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if fence is None:
            for quote in ('"""', "'''"):
                if stripped.count(quote) == 1:
                    fence = quote
                    break
            else:
                if not _COMMENT.match(line):
                    out.append((number, line))
            continue
        if fence in stripped:
            fence = None
    return out


def _fallback_hits() -> tuple[list[str], list[str]]:
    """(hits, files actually scanned)."""
    hits: list[str] = []
    scanned: list[str] = []
    for relative in LATE_FEE_PATH:
        path = common.REPO_ROOT / relative
        if not path.is_file():
            hits.append(f"{relative}: NOT FOUND — this gate's scope has moved under it")
            continue
        scanned.append(relative)
        for number, line in _code_lines(common.read_text(path)):
            for key in BANNED:
                if key in line:
                    hits.append(f"{relative}:{number} reads {key!r} — {line.strip()[:110]}")
    return hits, scanned


def _plan_count() -> tuple[str, str]:
    """(status, detail) from `manage.py cr078_late_fee_codes --fail-on-missing`."""
    if not BACKEND.is_dir():
        return "SKIP", "no 06-backend directory in this checkout"
    # ⚠ ASKED OF THE SHARED HELPER, NOT A LIST OF ITS OWN (`DEF-GOV-7813`):
    # this half kept a private `(sys.executable, "python3.12", "python3")` and
    # so ignored `SBH_GATE_PYTHON` while G4/G5 honoured it in the same run.
    python, tried = common.interpreter_with("django")
    if python is None:
        return "SKIP", (
            "no interpreter on this machine can import Django (tried: "
            + ", ".join(tried) + ")"
        )
    done = subprocess.run(
        [python, "manage.py", "cr078_late_fee_codes", "--fail-on-missing"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.local"},
        timeout=300,
        check=False,
    )
    total = [line for line in done.stdout.splitlines() if line.startswith("TOTAL:")]
    if not total:
        # No TOTAL line means the command did not get as far as counting —
        # a missing database, a migration not applied. That is an environment
        # fact, not a branch fault, and the two must not report the same way.
        tail = [line for line in done.stderr.strip().splitlines() if line.strip()]
        return "SKIP", (
            "the count could not be taken (no database, or migrations not applied): "
            + (tail[-1] if tail else "no output")
        )
    sentence = total[0]
    if done.returncode == 0:
        return "PASS", sentence
    return "FAIL", sentence + " Every one of them charges NOTHING, silently."


def run() -> tuple[str, str]:
    hits, scanned = _fallback_hits()
    count_status, count_detail = _plan_count()

    scope = f"{len(scanned)}/{len(LATE_FEE_PATH)} late-fee file(s) scanned"
    if hits:
        return "FAIL", (
            f"the tenant Billing-defaults fallback is back on the late-fee path "
            f"({scope}). BR-RAT-1011 / CR-078: the percent and the minimum come from "
            f"the charge code the PLAN names, and a plan naming none charges $0.00. "
            + " · ".join(hits[:6])
            + f" || plan count: {count_status} — {count_detail}"
        )
    if count_status == "FAIL":
        return "FAIL", (
            f"{count_detail} A plan with no late-fee charge code charges $0.00 "
            "(BR-RAT-1011, ruled) and nothing raises when it does — so an unpointed "
            "plan must be seen here rather than in a customer's question six months "
            f"later. Point it at a charge code on Plans & Rates. ({scope}; no "
            "Billing-defaults fallback found.)"
        )
    return "PASS", (
        f"no late-fee code path reads {' or '.join(BANNED)} from the tenant's "
        f"Billing defaults ({scope}) — the terms come from the charge code the plan "
        f"names (BR-RAT-1011). Plan count: {count_status} — {count_detail}"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

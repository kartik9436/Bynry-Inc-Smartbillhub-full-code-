#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2386 (2026-09-02) — a fresh tenant's 28 charge codes point at
#           no GL account, and a fee line then refuses at issue. Its
#           escape_reason is the whole reason this file exists: NOTHING in the
#           repo compared the charge-code fixture against the GL mapping, so a
#           code could be added to `lookup_defaults.json` and be seeded onto
#           every tenant in the world with nowhere to post.
# Change:   CR-066 task D1 — *"A gate that refuses a fixture charge code with
#           no default account — this is the escape route DEF-2386 used"*.
# Rules:    BR-BIL-010 (every line carries a GL account resolved at issue and
#           frozen; *charge codes carry their own GL*) · BR-RAT-117 (a
#           recurring auto-apply code lands on every ordinary bill) ·
#           CLAUDE.md law 7 (prove a guard RED first) · law 1 (a comment
#           claiming a guarantee is not the guarantee)
# ───────────────────────────────────────────────────────
"""G70 — every charge code the platform ships has an account to post to.

WHAT IT COSTS WHEN THIS IS NOT CHECKED, IN THE PRODUCT'S OWN NUMBERS
=====================================================================
`apps/billing/issue.py` resolves a bill line's GL account by KIND. A **usage**
or **base** line resolves from the SERVICE's designation; a **fee** line
resolves `rating.charges.gl_account_id` and **refuses the whole bill** when it
is null. So one charge code with no account is not one missing line — it is
every bill that carries that code, refused at issue, atomically.

On 2026-09-02 a tenant the Product Owner had just redeployed with a deleted
database held **28 charge codes pointing nowhere**, and its sample estate issued
**95 invoices anyway**, because every line the estate writes is usage or base.
**That asymmetry is why nobody saw it for weeks.** Two of the seeded codes
(`PAPER`, `HYDRANT`) are `recurring`, which `BR-RAT-117` puts on the ordinary
bill of every tenant that configures one.

WHAT IT CHECKS, AND WHY THAT IS THE CHEAP HALF
-----------------------------------------------
Two files, read as text, no database and no Django:

  * `06-backend/apps/tenancy/fixtures/lookup_defaults.json` → the charge codes
    the platform ships to every tenant.
  * `06-backend/apps/ledger/chart.py` → `CHARGE_CODE_ACCOUNTS` (the PO's
    approved table), `CHARGE_CODE_ACCOUNTS_NOT_MAPPED` (the ruled exemptions)
    and `SEED_CHART` (the accounts that actually exist).

Three questions, and the third is the one a mapping table alone cannot answer:

  1. **Is every shipped code answered** — by the map, or by a written exemption?
  2. **Does every account the map names EXIST in `SEED_CHART`?** A map pointing
     at `4620` — a number nobody seeds — reads exactly like a correct mapping
     and produces exactly the same NULL column, because the seed resolves the
     account by code and finds nothing.
  3. **Is the account list free of unreachable rows?** Not checked, deliberately
     — a chart is a tenant's to extend and an account nothing points at yet is
     a normal state, not a defect. Said here so nobody adds it later thinking it
     was an oversight.

⚠ **WHAT IT CANNOT SEE, SAID PLAINLY (hard-won law 1).** This is a STATIC check
over two files. It cannot tell you that provisioning actually ran the sweep, and
it cannot tell you that a tenant's rows came out non-NULL — a wiring failure
would leave every source file here perfectly consistent. That is
`tests/test_cr066_gl_defaults_live_pg.py`'s job, on real PostgreSQL, and the
`BASE-*` family is checked only there because those codes are created by the
SAMPLE loader and never appear in this fixture at all.

PROVED RED BEFORE IT WAS TRUSTED GREEN (law 7)
-----------------------------------------------
Three ways, on 2026-09-02, each output quoted rather than described:

  1. GREEN first, so the reds mean something:
     `PASS — 25 platform charge codes: 23 mapped to an account that exists in
     the seed chart, 2 exempt by a written ruling`.
  2. RED on a NEW UNMAPPED CODE. A `{"code": "SBH-REDPROOF", "name": "red
     proof", "charge_type": "one_time", "amount": "1"}` row added to the
     fixture:
     `FAIL: 1 platform charge code(s) ship with no GL account and no written
     exemption: SBH-REDPROOF.`
  3. RED on a MAP POINTING AT AN ACCOUNT NOBODY SEEDS. `"PAPER": "4650"`
     changed to `"PAPER": "4655"`:
     `FAIL: 1 charge code(s) are mapped to a chart code that SEED_CHART does not
     contain: PAPER -> 4655.`

The self-test below re-runs 2 and 3 against synthetic inputs on every run, so
the gate cannot rot into a check that cannot fail (DEF-182).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "06-backend/apps/tenancy/fixtures/lookup_defaults.json"
CHART = ROOT / "06-backend/apps/ledger/chart.py"

#: `SeedAccount("4600", …` — the account CODES the seed chart actually plants.
#: Read with a regex rather than by importing Django, for the reason every gate
#: in this directory is written that way: a gate that needs a settings module
#: and a database is a gate that gets skipped.
SEED_ROW = re.compile(r'SeedAccount\(\s*"([^"]+)"')


def _dict_literal(source: str, name: str) -> dict[str, str]:
    """The `{...}` assigned to `name` in `source`, parsed as a literal.

    `ast.literal_eval` rather than a regex over the keys: the map is authored by
    hand with comments between entries, and a key-scraping regex would silently
    disagree with what Python actually binds — which is the same class of bug as
    a check that cannot fail.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name and node.value is not None:
                return {str(k): str(v) for k, v in ast.literal_eval(node.value).items()}
    return {}


def analyse(fixture_text: str, chart_text: str) -> dict[str, list[str]]:
    """The three findings, as `{kind: [messages]}`. Pure, so the self-test can
    drive it with synthetic inputs and no files on disk."""
    fixture = json.loads(fixture_text)
    codes = [str(row.get("code", "")).strip() for row in fixture.get("charge_codes", [])]
    codes = [code for code in codes if code]

    mapping = _dict_literal(chart_text, "CHARGE_CODE_ACCOUNTS")
    exempt = _dict_literal(chart_text, "CHARGE_CODE_ACCOUNTS_NOT_MAPPED")
    seeded = set(SEED_ROW.findall(chart_text))

    unmapped = [code for code in codes if code not in mapping and code not in exempt]
    dangling = [
        f"{code} -> {mapping[code]}"
        for code in codes
        if code in mapping and mapping[code] not in seeded
    ]
    # An exemption with no words is not a ruling, it is a hole with a name on
    # it. `CHARGE_CODES_NOT_SEEDED` takes the same posture one module over.
    unreasoned = [code for code, why in exempt.items() if len(str(why).strip()) < 40]
    return {"unmapped": unmapped, "dangling": dangling, "unreasoned": unreasoned}


def selftest() -> bool:
    """The gate must BITE on both shapes DEF-2386 could take, and must not bite
    on a healthy pair. Run on every invocation — a guard nobody has seen fail is
    a guard nobody should trust (law 7, DEF-182)."""
    chart = (
        'CHARGE_CODE_ACCOUNTS = {"LATE": "4200"}\n'
        'CHARGE_CODE_ACCOUNTS_NOT_MAPPED = {"DEPO-R": "'
        + "x" * 50
        + '"}\n'
        'X = (SeedAccount("4200", "Late-fee revenue", "revenue"),)\n'
    )
    healthy = json.dumps({"charge_codes": [{"code": "LATE"}, {"code": "DEPO-R"}]})
    if any(analyse(healthy, chart).values()):
        return False  # a healthy pair must be silent, or the gate is noise
    new_code = json.dumps({"charge_codes": [{"code": "LATE"}, {"code": "SBH-REDPROOF"}]})
    if analyse(new_code, chart)["unmapped"] != ["SBH-REDPROOF"]:
        return False
    bad_target = chart.replace('"LATE": "4200"', '"LATE": "4655"')
    if analyse(healthy, bad_target)["dangling"] != ["LATE -> 4655"]:
        return False
    return True


def run() -> tuple[str, str]:
    if not FIXTURE.exists() or not CHART.exists():
        return "SKIP", f"{FIXTURE.name} or {CHART.name} is not present in this tree"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not bite: it must find a NEW unmapped "
            "fixture code and a mapping that points at an account SEED_CHART does not "
            "plant, and must stay silent on a healthy pair. A check that cannot "
            "distinguish pass from fail is worse than no check, because it is trusted "
            "(DEF-182)."
        )
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    chart_text = CHART.read_text(encoding="utf-8")
    found = analyse(fixture_text, chart_text)

    if found["unmapped"]:
        return "FAIL", (
            f"{len(found['unmapped'])} platform charge code(s) ship with no GL account "
            f"and no written exemption: {', '.join(sorted(found['unmapped']))}. Every "
            "tenant this product creates receives these codes, and a bill carrying one "
            "of them REFUSES AT ISSUE — the whole bill, not the line (BR-BIL-010, "
            "DEF-2386). Add the code to `chart.CHARGE_CODE_ACCOUNTS` with the account "
            "the Product Owner approved, or to `CHARGE_CODE_ACCOUNTS_NOT_MAPPED` with "
            "the ruling that says why it has none."
        )
    if found["dangling"]:
        return "FAIL", (
            f"{len(found['dangling'])} charge code(s) are mapped to a chart code that "
            f"SEED_CHART does not contain: {'; '.join(sorted(found['dangling']))}. The "
            "seed resolves an account BY CODE, so a map pointing at a number nobody "
            "plants leaves exactly the NULL column an unmapped code leaves — and reads "
            "like a correct mapping while doing it."
        )
    if found["unreasoned"]:
        return "FAIL", (
            f"{', '.join(sorted(found['unreasoned']))} is exempt from the GL mapping "
            "with no reason written down. An exemption without its ruling is a hole "
            "with a name on it: the next reader cannot tell a decision from an "
            "oversight, which is the distinction this gate exists to keep."
        )

    fixture = json.loads(fixture_text)
    total = len([row for row in fixture.get("charge_codes", []) if row.get("code")])
    mapped = len(_dict_literal(chart_text, "CHARGE_CODE_ACCOUNTS"))
    exempt = len(_dict_literal(chart_text, "CHARGE_CODE_ACCOUNTS_NOT_MAPPED"))
    return "PASS", (
        f"{total} platform charge codes: {mapped} mapped to an account that exists in "
        f"the seed chart, {exempt} exempt by a written ruling. Self-test: a new "
        "unmapped code bites, a mapping at an unseeded account bites, a healthy pair "
        "is silent. ⚠ STATIC — that provisioning actually WRITES the column, and the "
        "`BASE-*` family the sample loader creates, are proved on real PostgreSQL by "
        "tests/test_cr066_gl_defaults_live_pg.py and by nothing here."
    )


def main() -> int:
    if "--report" in sys.argv:
        found = analyse(
            FIXTURE.read_text(encoding="utf-8"), CHART.read_text(encoding="utf-8")
        )
        for kind, rows in found.items():
            print(f"{kind}: {', '.join(sorted(rows)) or '(none)'}")
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   step 3 of `12-governance/19-execution-sequence.md`, PO-approved —
#           the import↔ledger boundary. Nothing in this repo compares what an
#           IMPORT writes against what the LEDGER posts.
# Rules:    BR-LED-007 (CONFIRMED, PO LF-7 2026-08-08 — "deposit-liability GL =
#           Σ deposits held · AR GL = Σ account balances · tax payable =
#           remittance outstanding; ANY drift = red flag + release blocker") ·
#           BR-CUS-048 (❄️ GT-16, the four aged opening buckets) ·
#           CLAUDE.md hard rule 5 (only the ledger posting service writes
#           journal lines) · hard rule 4 (financial immutability)
# Defects:  DEF-1713 (the offender this gate was written for — CLOSED
#           2026-08-28, and this gate is what said so: it went RED as STALE the
#           moment the posting caller appeared) · DEF-1661 (the same column,
#           the other half) · DEF-177 (the same column, the opposite direction,
#           filed 2026-08-16 — CLOSED 2026-08-28)
# ───────────────────────────────────────────────────────
"""G48 — money an import can write must be money the ledger posts.

WHY THIS GATE EXISTS
--------------------
`DEF-1713`, measured on a full plant on 2026-08-27:

    deposit_liability DRIFTING, GL 0.00 against register 750.00, drift -750.00,
    cause deposit_register_is_never_written

**And the books still footed.** All 155 seeded journal entries balanced, so hard
rule 5 held perfectly — the entry was not unbalanced, it was never made. That is
the shape of this whole class: a subledger and its control account are written
by DIFFERENT PATHS, and when one path is missing, nothing about the ledger looks
wrong. The trial balance is right. The tie-out is the only thing that can see it,
and `DEF-1713`'s escape column says why it did not:

    US-LED-004's tie-out — the product's own check for precisely this — had
    never been pointed at the seeded fixture. […] So a control account and its
    subledger could disagree by $750.00 on the estate the Product Owner clicks
    on, and no test, gate or screen ever put the two side by side.

`DEF-1713`'s own prevention text names the asymmetry exactly, and it is the
asymmetry this gate looks for:

    Note the asymmetry INSIDE THE SAME IMPORT: the opening AR position posts a
    balanced opening JE (CR030_OPENING_BATCH_KEY, and GT-16 pins it), and the
    deposit half of the same row posts nothing at all.

One import row, two money columns, one of them booked and one of them not.

WHAT IT CHECKS — AND WHY THIS PARTICULAR COMPARISON
-----------------------------------------------------
Three facts are read out of the tree, each from the file that OWNS it, so the
gate carries no list of its own:

1. **THE SHIPPED IMPORT TEMPLATE.** `apps/metering/import_runs.py` declares
   every column a customer's file may carry, through `_account_column(…)` /
   `_asset_column(…)`. A column with `KIND_DECIMAL` and a money-shaped NAME is
   money the import can write. This is the customer-facing artefact — the
   spreadsheet a utility fills in at cutover — which is what makes it the right
   side of the boundary rather than a model field nobody offers.
2. **THE LEDGER'S POSTING SURFACE.** Every `post_*` function defined under
   `apps/ledger/`. Today that is seven, and it is derived rather than listed so
   a new posting entrypoint counts the day it lands.
3. **THE POSTING CALLERS.** Modules outside `apps/ledger` that CALL one of
   those entrypoints, or name one as a seam string. Today that is exactly TWO —
   `apps/billing/posting_seam.py` and `apps/customers/import_writer.py` — which
   is the whole point: hard rule 5 makes this universe small enough to check.

**THE RULE: a money column a shipped template accepts must be NAMED by a module
that posts.** `ob_current`/`ob_31_60`/`ob_61_90`/`ob_90_plus` are named in
`import_writer.py`, which calls `post_opening_batch` — they are booked, and
GT-16 pins the figure. `deposit_on_file` is named by no posting caller at all.

⚠ **WHY "NAMED BY A POSTING CALLER" AND NOT SOMETHING STRONGER.** The honest
statement of this clause's limit matters more than the clause. A *dataflow*
check — *does this column's VALUE reach a posting request* — is what one would
want, and no source-reading gate can do it; G43 and G44 both stop at the same
line and say so. What is checkable is whether the money column is KNOWN to any
code path that posts. That is a **necessary** condition, not a sufficient one:
a module could name the column and still not carry it into the request. It is
worth having anyway, because it is exactly the condition `deposit_on_file`
fails — nothing that posts has ever heard of it — and because the weaker
readings were tried first and could not distinguish pass from fail:

* *"some module names both the column and a posting entrypoint"* passes on
  `deposit_on_file`, because `customers/services.py` is 4,000 lines and mentions
  both.
* *"the ledger app names the column"* fails on `ob_current`, which correctly
  reaches the ledger as a SUMMED balance and never by name.

A check whose output cannot distinguish pass from fail is worse than no check,
because it is trusted (DEF-182).

**DOCSTRINGS AND COMMENTS ARE STRIPPED, BOTH SIDES.** This is not decoration:
`customers/move_out_settlement.py` names `apps.payments.credit.…` and
`apps.ledger.deposit_legs.post_deposit_applied` in PROSE, twice, and without
stripping it would register as a posting caller that knows about deposits —
the gate would report the defect fixed by its own explanation of it (DEF-741,
and G45 carries the same note).

THE BASELINE IS A NAMED SET, NOT A NUMBER — AND IT IS NOW EMPTY
---------------------------------------------------------------
⚠ **UPDATED 2026-08-28: `KNOWN_UNPOSTED` IS `{}`.** `DEF-1713` is fixed — a
migrated deposit now posts DR opening clearing / CR 2300 deposit liability
through `apps/ledger/opening_balances.post_opening_deposit_batch`, dated at
cutover (BR-CUS-671) — and this gate is what announced it: it turned RED as
STALE the moment `import_writer.py` began naming the column on the way to a
posting entrypoint, and stayed red until the row was removed. The paragraphs
below are the reasoning that banked it in the first place and are kept because
they are the argument for the SHAPE, which is unchanged.

`deposit_on_file` was unposted on this branch **until 2026-08-28**. `DEF-1713` is open, is
filed at HIGH, and its fix is a ledger posting for migrated deposits — 🔒
sensitive-path work under CLAUDE.md's ledger-posting lock, owned by step 4's
module blocks and not by a gate lane. Shipping this gate hard-RED would put the
whole suite on the floor for every lane over a known, already-filed defect that
nobody in flight is fixing, and *"a gate that is red from birth earns a `# noqa`
instead of a fix"* (G44's docstring, in its own words).

So it ships with **exactly one banked offender, named**:

    KNOWN_UNPOSTED = {"deposit_on_file": …DEF-1713…}

**A NAMED SET IS STRICTLY STRONGER THAN A COUNT**, and that is why it is one.
A baseline of `1` would let a SECOND money column go unposted the day the first
was fixed, and the count would still read 1. Naming the column means a different
one fails immediately, at its own name, with `DEF-1713` quoted beside it.

⚠ **AND IT MAY FALL AND NEVER RISE — ENFORCED, NOT ASKED FOR.** When
`DEF-1713` is fixed the gate goes RED as STALE until the row is removed, because
a ratchet that never tightens is a number nobody reads (DEF-490, G44 clause (c)).

NOT POSTED BY RULE — ONE COLUMN, ONE RULING
---------------------------------------------
`purchase_cost` is money on a shipped template and is **correctly** never
posted. CR-028's own migration says so, verbatim
(`assets/migrations/0007_cr028_valuation.py`):

    `book_value_amount` + `book_value_treatment` are a RECORD of a decision made
    at retirement, computed and shown, **never posted**. Only the ledger posting
    service writes journal lines (hard rule 5), and this migration gives it
    nothing to write.

An asset's cost is a valuation the product REPORTS; it is not a transaction.
The exemption is named here, in the check, rather than trusted to that comment —
hard-won law 1, a comment claiming a guarantee is not the guarantee.

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
**Whether the posted AMOUNT is right.** Only `06-backend/tests/
test_us_led_004_tie_out.py` and the golden set can say that, and GT-16 pins the
opening batch to the cent. This gate asks whether a door EXISTS, which is the
question `DEF-1713` answers "no" to.

**Whether the tie-out is run against the seeded estate.** That is `DEF-1713`'s
other half and it needs a database; `G24` already shows what a DB-dependent
clause reports here (*"no database reachable (OperationalError) — clause (b)
NOT EVALUATED"*), and an unevaluated clause proves nothing (G21's words).

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — the verbatim failure is in
the `RED PROOF` block below. It was taken on THIS tree with `KNOWN_UNPOSTED`
emptied, because the defect is live here: no worktree was needed and none was
mutated.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "06-backend"
LEDGER = BACKEND / "apps" / "ledger"
TEMPLATE_MODULE = BACKEND / "apps" / "metering" / "import_runs.py"

#: A money-shaped column NAME. `KIND_DECIMAL` alone is not enough:
#: `export_capacity_kw` is a decimal and a physical capacity, and CR-028's
#: migration says so in as many words ("a physical capacity, not money").
MONEY_NAME = re.compile(r"cost|balance|deposit|amount|charge|fee|total|price|credit|payment|^ob_")

#: `_account_column("name", "Label", KIND_X, …)` / `_asset_column(…)` — the
#: shipped template's own declaration, whatever the wrapper is called.
TEMPLATE_COLUMN = re.compile(
    r"""_\w*column\(\s*["']([a-z_0-9]+)["']\s*,\s*["']([^"']+)["']\s*,\s*(KIND_\w+)""",
    re.S,
)
#: The same call spread over several lines by the formatter (four of them are).
TEMPLATE_COLUMN_WRAPPED = re.compile(
    r"""_\w*column\(\s*\n\s*["']([a-z_0-9]+)["']\s*,\s*\n?\s*["']([^"']+)["']\s*,\s*\n?\s*(KIND_\w+)""",
    re.S,
)

#: BANKED, and it is a SET so a different column cannot hide inside a count.
#: It may SHRINK and may never GROW; a fall that is not banked is a FAIL.
#: ⚠ **EMPTIED 2026-08-28 — `deposit_on_file` WAS THE ONE ROW AND DEF-1713 IS
#: FIXED.** The gate did exactly what its docstring promised: the moment
#: `apps/customers/import_writer.py` started naming the column on the way to
#: `post_opening_deposit_batch`, it went RED as STALE
#: (*"the banked set is STALE: deposit_on_file now reach(es) a posting caller"*)
#: and stayed red until this row was removed. That is the ratchet working, and
#: it is the reason the set is NAMED rather than counted.
#:
#: ⛔ **AN EMPTY SET IS THE STRONGEST STATE THIS GATE CAN BE IN — DO NOT ADD A
#: ROW TO GET A BUILD GREEN.** Every money column a shipped import template
#: accepts now reaches a module that posts. A new row here is a new
#: `DEF-1713`: a figure a customer types into a migration spreadsheet that
#: lands in a register and never in the books, on a trial balance that foots
#: perfectly because the entry was never made rather than made wrong.
KNOWN_UNPOSTED: dict[str, str] = {}

#: NOT POSTED BY A RULING, quoted in the named file. See the docstring.
NOT_POSTED_BY_RULE: dict[str, str] = {
    "purchase_cost": (
        "CR-028 · assets/migrations/0007_cr028_valuation.py, verbatim: valuation columns are "
        "'a RECORD of a decision made at retirement, computed and shown, never posted. Only "
        "the ledger posting service writes journal lines (hard rule 5), and this migration "
        "gives it nothing to write.' An asset's cost is a valuation the product REPORTS, not "
        "a transaction"
    ),
    # ── 2026-10-02 · `DEF-WRK-8545` — CLOSED BY RULING, NOT A DEFECT ──────────
    # Put to the PO in plain words: a clerk imports the parts row "Water meter,
    # $85.00 each, 10" — is $85.00 just the meter's price, or are 10 meters
    # worth $850.00 sitting in a storeroom the books should show? PO verbatim:
    # "A · It's just a price. Nothing goes into the accounts." (decision log
    # 2026-10-02, "THREE MORE ANSWERS"). Exempt BY NAME, exactly as
    # `purchase_cost` is: every OTHER money column on a shipped template that
    # no posting caller names is still red, and the self-test proves it.
    "unit_cost": (
        "PO ruling 2026-10-02, verbatim: 'A · It's just a price. Nothing goes into the "
        "accounts.' A part's imported unit cost is a catalogue price (a valuation of the "
        "item), never stock on hand, and posts nothing to the ledger (DEF-WRK-8545, closed "
        "by ruling)"
    ),
}


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"\S", " ", match.group(0))


def _strip_py(text: str) -> str:
    """Blank docstrings AND `#` comments — prose must not satisfy the rule."""
    text = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""', _blank, text)
    text = re.sub(r"'''(?:[^'\\]|\\.|'(?!''))*'''", _blank, text)
    return re.sub(r"#[^\n]*", lambda m: " " * len(m.group(0)), text)


def posting_entrypoints(ledger_sources: dict[str, str]) -> set[str]:
    """Every `post_*` the ledger app defines — DERIVED, never listed here."""
    found: set[str] = set()
    for text in ledger_sources.values():
        found.update(re.findall(r"^def (post_[a-z_0-9]+)", text, re.M))
    return found


def template_money_columns(template_text: str) -> dict[str, str]:
    """`{column: label}` for every money column the shipped template offers."""
    out: dict[str, str] = {}
    for pattern in (TEMPLATE_COLUMN, TEMPLATE_COLUMN_WRAPPED):
        for name, label, kind in pattern.findall(template_text):
            if kind == "KIND_DECIMAL" and MONEY_NAME.search(name):
                out.setdefault(name, label)
    return out


def posting_callers(sources: dict[str, str], entrypoints: set[str]) -> dict[str, list[str]]:
    """Modules OUTSIDE the ledger that call a posting entrypoint or name one
    as a seam string. `posting_seam._resolve` reaches `deposit_legs` by NAME
    through `import_module`, so a call-syntax-only reader would miss it and
    report a wired posting path as dead (the mirror of hard-won law 2)."""
    out: dict[str, list[str]] = {}
    for rel, text in sources.items():
        if "/apps/ledger/" in rel:
            continue
        called = [
            entry
            for entry in sorted(entrypoints)
            if re.search(rf"\b{entry}\s*\(", text) or re.search(rf"""["']{entry}["']""", text)
        ]
        if called:
            out[rel] = called
    return out


def _sources() -> dict[str, str]:
    """Every non-test backend module, comments and docstrings already blanked."""
    out: dict[str, str] = {}
    for path in sorted(BACKEND.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if "/tests/" in rel or path.name.startswith("test_"):
            continue
        out[rel] = _strip_py(path.read_text("utf-8", errors="replace"))
    return out


def unposted(
    money: dict[str, str], sources: dict[str, str], callers: dict[str, list[str]]
) -> list[str]:
    """Money columns no posting caller has ever heard of."""
    out: list[str] = []
    for column, label in sorted(money.items()):
        if column in NOT_POSTED_BY_RULE:
            continue
        if any(column in sources[rel] for rel in callers):
            continue
        out.append(f"`{column}` ({label})")
    return out


def selftest() -> list[str]:
    """Shown to BITE on planted text before it is trusted on the real tree."""
    problems: list[str] = []

    ledger = {"apps/ledger/x.py": "def post_thing(a):\n    return 1\n"}
    entries = posting_entrypoints(ledger)
    if entries != {"post_thing"}:
        problems.append(f"does not derive posting entrypoints from the ledger app ({entries})")

    tpl = (
        '_account_column("deposit_on_file", "Deposit on file", KIND_DECIMAL, sample="150.00"),\n'
        '_account_column("ob_current", "Opening balance", KIND_DECIMAL),\n'
        '_asset_column("export_capacity_kw", "Export capacity (kW)", KIND_DECIMAL),\n'
        '_account_column("status", "Status", KIND_LOOKUP),\n'
    )
    money = template_money_columns(tpl)
    if set(money) != {"deposit_on_file", "ob_current"}:
        problems.append(f"template money columns misread: {sorted(money)}")
    if "export_capacity_kw" in money:
        problems.append("reads a physical capacity as money — CR-028 says it is not")

    src = {
        "apps/customers/writer.py": "post_thing(batch)\nrow['ob_current']\n",
        "apps/customers/other.py": "row['deposit_on_file']\n",
    }
    callers = posting_callers(src, entries)
    if set(callers) != {"apps/customers/writer.py"}:
        problems.append(f"posting callers misread: {sorted(callers)}")

    missed = unposted(money, src, callers)
    # ⚠ THE DEFECT ITSELF: a money column no posting caller names.
    if not any("deposit_on_file" in m for m in missed):
        problems.append("does not bite a money column no posting caller names (DEF-1713's shape)")
    if any("ob_current" in m for m in missed):
        problems.append("bites a money column a posting caller DOES name — false positive")

    # A seam STRING is a posting path (posting_seam reaches deposit_legs by name).
    seam = {"apps/billing/seam.py": '_resolve(M, "post_thing", K)\nrow["deposit_on_file"]\n'}
    if any("deposit_on_file" in m for m in unposted(money, seam, posting_callers(seam, entries))):
        problems.append("does not count a seam-resolved posting path — it would report it dead")

    # ⚠ PROSE MUST NOT SATISFY THE RULE. move_out_settlement names
    # `post_deposit_applied` and `deposit_on_file` in DOCSTRINGS, twice.
    prose = {
        "apps/customers/prose.py": _strip_py(
            'def f():\n    """calls post_thing for deposit_on_file one day."""\n    return 1\n'
        )
    }
    if not unposted(money, prose, posting_callers(prose, entries)):
        problems.append("a DOCSTRING mention counts as a posting path — the gate explains itself green")

    # An exempted column is exempt, and only by NAME.
    exempt_tpl = '_asset_column("purchase_cost", "Purchase cost", KIND_DECIMAL),\n'
    if unposted(template_money_columns(exempt_tpl), {}, {}):
        problems.append("does not honour NOT_POSTED_BY_RULE")

    # ⚠ AND ONLY BY NAME (2026-10-02, `unit_cost` joined the list): a part's
    # unit cost passes, and another money-bearing import column on the SAME
    # template that nothing posts — a part's stock value — still bites.
    parts_tpl = (
        '_part_column("unit_cost", "Unit cost", KIND_DECIMAL),\n'
        '_part_column("stock_value_amount", "Stock value", KIND_DECIMAL),\n'
    )
    parts_missed = unposted(template_money_columns(parts_tpl), {}, {})
    if any("unit_cost" in m for m in parts_missed):
        problems.append("does not honour the unit_cost ruling (DEF-WRK-8545)")
    if not any("stock_value_amount" in m for m in parts_missed):
        problems.append("an exemption leaked past its NAME — an unposted stock value passed")
    return problems


def run() -> tuple[str, str]:
    """`("PASS"|"FAIL"|"SKIP", detail)` — the runner's contract, not a bool."""
    if not TEMPLATE_MODULE.exists() or not LEDGER.exists():
        return "SKIP", "the import template module or the ledger app does not exist yet"

    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    sources = _sources()
    ledger_sources = {rel: text for rel, text in sources.items() if "/apps/ledger/" in rel}
    entrypoints = posting_entrypoints(ledger_sources)
    if not entrypoints:
        return "FAIL", "no `post_*` entrypoint found under apps/ledger — this gate's authority"

    money = template_money_columns(sources[TEMPLATE_MODULE.relative_to(ROOT).as_posix()])
    if not money:
        return "FAIL", "no money column found in the shipped import template — the reader is blind"

    callers = posting_callers(sources, entrypoints)
    missed = unposted(money, sources, callers)
    banked = {c for c in KNOWN_UNPOSTED if c in money}
    new = [m for m in missed if not any(f"`{c}`" in m for c in banked)]
    healed = sorted(c for c in banked if not any(f"`{c}`" in m for m in missed))

    note = (
        f"BR-LED-007: {len(money)} money column(s) on the shipped import template, "
        f"{len(entrypoints)} ledger posting entrypoint(s), {len(callers)} posting caller(s) "
        f"outside the ledger; {len(missed)} unposted ({len(banked)} banked, "
        f"{len(NOT_POSTED_BY_RULE)} not posted by a ruling); self-test: 10/10 clauses bite"
    )

    # ── RED PROOF ─────────────────────────────────────────────────────────
    # Taken on THIS tree with KNOWN_UNPOSTED emptied — the defect is live
    # here, so no worktree was needed and none was mutated:
    #
    #   FAIL: BR-LED-007: 6 money column(s) on the shipped import template, 7
    #   ledger posting entrypoint(s), 2 posting caller(s) outside the ledger;
    #   1 unposted (0 banked, 1 not posted by a ruling); self-test: 8/8 clauses
    #   bite. 1 money column(s) a shipped import template accepts are named by
    #   NO module that posts to the ledger. A migrated figure written to a
    #   register and never posted is a control account and its subledger
    #   disagreeing, and the books still FOOT — the entry was not unbalanced,
    #   it was never made (DEF-1713: register $750.00 against a 2300 GL of
    #   $0.00). Post it through the ledger posting service, or — if it is a
    #   valuation and not a transaction — name it in NOT_POSTED_BY_RULE with
    #   the ruling. Offender(s): `deposit_on_file` (Deposit on file)
    failures: list[str] = []
    if new:
        failures.append(
            f"{len(new)} money column(s) a shipped import template accepts are named by NO "
            "module that posts to the ledger. A migrated figure written to a register and "
            "never posted is a control account and its subledger disagreeing, and the books "
            "still FOOT — the entry was not unbalanced, it was never made (DEF-1713: register "
            "$750.00 against a 2300 GL of $0.00). Post it through the ledger posting service, "
            "or — if it is a valuation and not a transaction — name it in NOT_POSTED_BY_RULE "
            "with the ruling. Offender(s): " + ", ".join(new)
        )
    if healed:
        failures.append(
            f"the banked set is STALE: {', '.join(healed)} now reach(es) a posting caller. "
            "A ratchet that never tightens is a number nobody reads (DEF-490). Remove the "
            f"row(s) from KNOWN_UNPOSTED in {Path(__file__).name}"
        )
    if failures:
        return "FAIL", f"{note}. " + "\n  ".join(failures)
    return "PASS", note


def main() -> int:
    """Run this gate from the command line.

    ⚠ A `run()` with no main block exits 0 with no output, which is
    indistinguishable from a pass to the eye and to `$?` (DEF-672).
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

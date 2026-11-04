#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.8 — "No change to the allow list. `payments/0014`
#           is the only place it moves, and it moved once, for three columns.
#           Cancel writes a status and a new row; it does not widen
#           immutability." (payments blueprint p19)
# Rules:    CLAUDE.md hard rule 4, as NARROWED by PO ruling 2026-09-02 for
#           exactly three columns and for nothing else · BR-PAY-002 ·
#           hard-won law 1 (a docstring asking the next lane not to widen it is
#           a note, never a guard) · hard-won law 7 (proved RED first, through
#           `run_gates` and not through `python3 <gate>.py`) · law 14 (the
#           default suite is SQLite and cannot see this at all)
# Tests:    selftest() below — the detector on synthetic bodies, run as part 0
#           of every `run()`, so the red proof happens on every invocation
#           rather than once at birth
# Impacts:  10-scripts/gates/run_gates.py · apps/payments/migrations/*
# ───────────────────────────────────────────────────────
"""G131 — hard rule 4's allow list moved ONCE, for three columns, and stays there.

WHY THIS GATE EXISTS
--------------------
CLAUDE.md hard rule 4 says no UPDATE on a payment. The Product Owner narrowed
it on 2026-09-02, in these words — *"(a) Allow those fields to change"* — for
**`confirmation`, `memo` and `method_id`** and for nothing else, and CLAUDE.md
carries the amendment with a sentence that is the whole of this gate's job:

    `payments/0014` is the ONLY place the database's allow list moves; widening
    it anywhere else is a new ruling, not this one.

**Until today that sentence was enforced by nobody.** `payments/0014` asks the
next lane not to move the arrays, in its own docstring; `payments/0033` restates
the function body and says *"The `mutable` and `stamps` arrays are
byte-identical"*, correctly, in a comment. Both are notes. Hard-won law 1 is
exactly this: *a comment claiming a guarantee is not the guarantee.*

⚠ **AND THE REALISTIC WAY IT BREAKS IS NOT MALICE — IT IS CONVENIENCE.** The
trigger compares whole rows minus a short allow list, so **any** new column on
`payments` is frozen the day it is created. A lane that then needs to stamp
that column on a row which is already history has one obvious, quick move:
add the name to `stamps`. It is four characters, it makes their migration work,
every test passes, and hard rule 4 is quietly wider for every payment this
product will ever take. `payments/0002` names that exact temptation about
`deposit_batch_id` and closes the door by hand; this gate is that door for
every column after it.

WHAT IT CHECKS — THREE THINGS, AND THE SECOND IS THE ONE PEOPLE MISS
----------------------------------------------------------------------
**1 · NO NAME BEYOND `payments/0014`'s TWO SETS.** Every `mutable` / `stamps`
array declared inside a `payments_payment_immutable()` body anywhere in
`apps/payments/migrations/` is read, and any name outside `0014`'s sets is a
FAIL. It is a **one-directional** check on purpose: a NARROWER array is lawful
and expected — `0002`, `0005` and `0006` predate the ruling and `0014`'s own
REVERSE body restores `0006`'s narrower pair, because a freeze must unapply to
exactly what came before it.

**2 · THE BRANCH THAT USES THE ALLOW LIST MUST STILL BE THERE.** An allow list
can be left untouched while the code that consults it is removed, and then
checking only the arrays reports a confident PASS over a trigger that freezes
nothing. So every body that redefines the function must also contain the
append-only branch (`OLD.status <> 'processing'`) and the DELETE refusal. That
is this gate's answer to *what would make this check pass wrongly* — the
question law 7 habit 2 says to ask before trusting a green.

**3 · IT MUST HAVE READ SOMETHING.** A wrong root, a renamed directory, a
changed spelling of the arrays, and a sweep of nothing passes cleanly. The gate
FAILS when it finds no function bodies, and prints **how many files it read and
how many arrays it parsed on a PASS as well as on a FAIL** — G32's lesson:
*a declared blind spot with no NUMBER attached is indistinguishable from an
empty one.*

WHAT IT DELIBERATELY DOES NOT CHECK
------------------------------------
**The deployed database.** A gate cannot reach a cluster, and pretending to
would be worse than not trying: it would pass on every machine where no
database is configured. The DEPLOYED arrays are read back out of
`pg_proc.prosrc` by `10-scripts/p3_cancel_state_and_trigger_readback.py` §6,
against a live PostgreSQL 16 clone, and that is the other half of this proof.
This gate watches what is about to be deployed; that script watches what was.

PROVED RED BEFORE IT WAS TRUSTED GREEN, THROUGH `run_gates` (DEF-GOV-3733)
---------------------------------------------------------------------------
`selftest()` is **part 0 of `run()`**, not a separate entry point, so the red
proof is re-taken on every invocation and cannot rot into a green that nobody
has seen fail. It feeds the detector four synthetic bodies — one widened
`mutable`, one widened `stamps`, one with the append-only branch removed, one
with the DELETE refusal removed — and this gate FAILS if any of them is not
reported. A detector that has stopped detecting is caught before it is asked
about the real files.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "06-backend" / "apps" / "payments" / "migrations"

#: The function whose allow list hard rule 4 lives in.
FUNCTION = "payments_payment_immutable"

#: `payments/0014` — the ONE widening, PO ruling 2026-09-02. These two sets are
#: the ceiling: a body may declare LESS (the pre-ruling migrations, and 0014's
#: own reverse) and may never declare MORE.
CEILING = {
    "mutable": {"status", "cleared_at", "updated_at", "confirmation", "memo", "method_id"},
    "stamps": {
        "deposit_batch_id",
        "journal_entry_id",
        "updated_at",
        "confirmation",
        "memo",
        "method_id",
    },
    #: `CR-186-BRC10`, `payments/0051` — the SECOND ruling that moves hard rule
    #: 4 (PO 2026-10-21: a payment is `posted` at entry and becomes `cleared`
    #: when its deposit batch is reconciled; `cancelled` only from `posted`).
    #: A posted row may move its status and gain its clearing date, once.
    #: Consulted only inside an `OLD.status = 'posted'` branch, which part 4
    #: below demands. ⚠ Until 0051 this gate parsed `mutable|stamps` ONLY, so a
    #: third array of any name was a blind spot it reported PASS over — part 5
    #: now fails any allow-list array whose NAME is not one of these three.
    "clearing": {"status", "cleared_at", "updated_at"},
    #: `payments/0052` — the THIRD ruling (PO 2026-10-21, "Allow, back to
    #: Posted"): Unreconcile puts a CLEARED member of its own batch back to
    #: posted, the clearing date removed. Consulted only inside an
    #: `OLD.status = 'cleared'` branch, which part 4 below demands.
    "unclearing": {"status", "cleared_at", "updated_at"},
    #: `payments/0005`'s pre-ruling name for the batch stamp — narrower than
    #: `stamps` and superseded by it in 0006. Listed so part 5 can tell a
    #: historic name from a new door; it may never hold more than this.
    "batch_stamp": {"deposit_batch_id", "updated_at"},
}

#: The guard the `clearing` array must sit behind (part 4).
POSTED_BRANCH = re.compile(r"OLD\.status\s*=\s*'posted'")
#: The guard the `unclearing` array must sit behind (part 4), with the window.
CLEARED_BRANCH = re.compile(
    r"OLD\.status\s*=\s*'cleared'.*?current_setting\('app\.payment_unclearing'", re.S
)
#: Any `<name> text[] := ARRAY[` declaration at all (part 5).
ANY_ARRAY = re.compile(r"\b([a-z_][a-z0-9_]*)\s+text\[\]\s*:=\s*ARRAY\[", re.I)

#: The two clauses that make the allow list mean anything. Without the first,
#: a frozen row never reaches the comparison; without the second, a row can be
#: removed instead of edited.
FROZEN_BRANCH = re.compile(r"OLD\.status\s*<>\s*'processing'")
DELETE_REFUSAL = re.compile(r"TG_OP\s*=\s*'DELETE'")

#: `mutable text[] := ARRAY[ … ];` over as many lines as it takes.
ARRAY = re.compile(r"\b(mutable|stamps|clearing|unclearing|batch_stamp)\s+text\[\]\s*:=\s*ARRAY\[(.*?)\]\s*;", re.S)
#: Every `CREATE OR REPLACE FUNCTION <name>` body, to the `$$ LANGUAGE` that ends it.
BODY = re.compile(
    r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+" + FUNCTION + r"\s*\(.*?\$\$\s*LANGUAGE\s+plpgsql\s*;",
    re.S | re.I,
)


def inspect(text: str, where: str) -> tuple[list[str], int, int]:
    """`(findings, bodies_seen, arrays_seen)` for one file's source."""
    findings: list[str] = []
    bodies = BODY.findall(text)
    arrays_seen = 0
    for index, body in enumerate(bodies, start=1):
        label = f"{where} (body {index} of {len(bodies)})"
        for name, inner in ARRAY.findall(body):
            arrays_seen += 1
            declared = set(re.findall(r"'([^']*)'", inner))
            extra = sorted(declared - CEILING[name])
            if extra:
                findings.append(
                    f"{label}: `{name}` declares {extra} — beyond the "
                    f"{sorted(CEILING[name])} that payments/0014 set under the PO's "
                    f"ruling of 2026-09-02. Widening hard rule 4's allow list is a NEW "
                    f"ruling, not that one"
                )
        names = {one.lower() for one in ANY_ARRAY.findall(body)}
        unknown = sorted(names - set(CEILING))
        if unknown:
            findings.append(
                f"{label}: declares allow-list array(s) {unknown} that this gate has no "
                f"ruling for. A new array is a new door in hard rule 4 under a name the "
                f"ceiling cannot see"
            )
        if "clearing" in names and not POSTED_BRANCH.search(body):
            findings.append(
                f"{label}: declares `clearing` without the `OLD.status = 'posted'` branch "
                f"it is ruled for (CR-186-BRC10) — the clearing door would open on every "
                f"status"
            )
        if "unclearing" in names and not CLEARED_BRANCH.search(body):
            findings.append(
                f"{label}: declares `unclearing` without the `OLD.status = 'cleared'` branch "
                f"and its `app.payment_unclearing` window (CR-186-BRC10 follow-up) — the "
                f"door back to posted would open outside Unreconcile"
            )
        if not FROZEN_BRANCH.search(body):
            findings.append(
                f"{label}: the append-only branch `OLD.status <> 'processing'` is gone. "
                f"The allow list can be untouched and mean nothing if the code that "
                f"consults it is removed"
            )
        if not DELETE_REFUSAL.search(body):
            findings.append(
                f"{label}: the DELETE refusal is gone. Hard rule 4 names payments with "
                f"no status qualifier — money handed over has no delete path"
            )
    return findings, len(bodies), arrays_seen


def selftest() -> list[str]:
    """Part 0 — the detector, proved RED on synthetic bodies, every run."""
    shell = (
        "CREATE OR REPLACE FUNCTION " + FUNCTION + "() RETURNS trigger AS $$\n"
        "DECLARE\n"
        "  mutable  text[] := ARRAY[{mutable}];\n"
        "  stamps   text[] := ARRAY[{stamps}];\n"
        "BEGIN\n"
        "{delete_clause}"
        "{frozen_clause}"
        "  RETURN NEW;\n"
        "END $$ LANGUAGE plpgsql;\n"
    )
    ok_mutable = ", ".join(f"'{one}'" for one in sorted(CEILING["mutable"]))
    ok_stamps = ", ".join(f"'{one}'" for one in sorted(CEILING["stamps"]))
    delete_clause = "  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'no'; END IF;\n"
    frozen_clause = "  IF OLD.status <> 'processing' THEN RETURN NEW; END IF;\n"

    lawful = shell.format(
        mutable=ok_mutable,
        stamps=ok_stamps,
        delete_clause=delete_clause,
        frozen_clause=frozen_clause,
    )
    broken = {
        "a widened `mutable`": shell.format(
            mutable=ok_mutable + ", 'amount'",
            stamps=ok_stamps,
            delete_clause=delete_clause,
            frozen_clause=frozen_clause,
        ),
        "a widened `stamps`": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps + ", 'account_id'",
            delete_clause=delete_clause,
            frozen_clause=frozen_clause,
        ),
        "the append-only branch removed": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps,
            delete_clause=delete_clause,
            frozen_clause="",
        ),
        "a widened `clearing`": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps + "];\n  clearing text[] := ARRAY['status', 'amount'",
            delete_clause=delete_clause,
            frozen_clause=frozen_clause + "  IF OLD.status = 'posted' THEN NULL; END IF;\n",
        ),
        "an allow-list array under an unruled name": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps + "];\n  extra text[] := ARRAY['amount'",
            delete_clause=delete_clause,
            frozen_clause=frozen_clause,
        ),
        "`clearing` outside the posted branch": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps + "];\n  clearing text[] := ARRAY['status'",
            delete_clause=delete_clause,
            frozen_clause=frozen_clause,
        ),
        "`unclearing` outside the cleared branch and its window": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps + "];\n  unclearing text[] := ARRAY['status'",
            delete_clause=delete_clause,
            frozen_clause=frozen_clause + "  IF OLD.status = 'cleared' THEN NULL; END IF;\n",
        ),
        "the DELETE refusal removed": shell.format(
            mutable=ok_mutable,
            stamps=ok_stamps,
            delete_clause="",
            frozen_clause=frozen_clause,
        ),
    }

    complaints: list[str] = []
    findings, bodies, arrays = inspect(lawful, "<selftest lawful>")
    if bodies != 1 or arrays != 2:
        complaints.append(
            f"the parser stopped parsing: {bodies} body/bodies and {arrays} array(s) "
            f"found in a synthetic body that holds exactly 1 and 2. Every verdict "
            f"below would be a truthful zero over nothing"
        )
    if findings:
        complaints.append(f"a LAWFUL synthetic body was reported: {findings[0]}")
    for what, text in broken.items():
        found, _bodies, _arrays = inspect(text, "<selftest>")
        if not found:
            complaints.append(
                f"the detector did NOT report {what} — it has stopped detecting, "
                f"so a green on the real files means nothing"
            )
    return complaints


def check() -> tuple[list[str], int, int, int]:
    """`(findings, files_read, bodies_seen, arrays_seen)` over the real migrations."""
    findings: list[str] = []
    files = sorted(MIGRATIONS.glob("*.py")) if MIGRATIONS.is_dir() else []
    bodies = arrays = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if FUNCTION not in text:
            continue
        try:
            where = path.relative_to(ROOT).as_posix()
        except ValueError:
            # A path outside the repo root — the red-proof harness points this
            # gate at a temp copy of the real migrations. A gate that CRASHES
            # here reports `gate crashed` rather than a verdict, which is
            # DEF-GOV-3733's shape one layer down.
            where = path.as_posix()
        hits, seen, counted = inspect(text, where)
        findings.extend(hits)
        bodies += seen
        arrays += counted
    return findings, len(files), bodies, arrays


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    broken_detector = selftest()
    if broken_detector:
        return "FAIL", (
            f"{len(broken_detector)} problem(s) in this gate's OWN red proof, so nothing "
            f"it says about the real files can be believed: " + "; ".join(broken_detector)
        )

    findings, files, bodies, arrays = check()

    if not MIGRATIONS.is_dir():
        # ⚠ `common.rel()` is NOT used here, and that is a fix rather than an
        # oversight: it raises for a path outside the repo root, so the branch
        # that reports a MISSING scope would itself CRASH — a gate answering
        # `gate crashed` instead of a verdict, which is DEF-GOV-3733's shape
        # inside the very branch meant to catch a wrong scope. Found by this
        # gate's own red-proof harness pointing it at a directory that is not
        # there, which is the case this branch exists for.
        return "FAIL", (
            f"{MIGRATIONS} is not a directory — the scope is wrong. A sweep of "
            f"nothing passes cleanly, so this is a FAIL by construction."
        )
    if bodies == 0 or arrays == 0:
        return "FAIL", (
            f"read {files} migration file(s) and found {bodies} `{FUNCTION}` body/bodies "
            f"and {arrays} allow-list array(s). Zero means the spelling changed under "
            f"this gate, not that hard rule 4 is safe — it would report a truthful PASS "
            f"over a scope it silently excludes."
        )
    if findings:
        return "FAIL", (
            f"{len(findings)} breach(es) of hard rule 4's allow list across {bodies} "
            f"function body/bodies: {findings[0]}"
            + (f" (+{len(findings) - 1} more)" if len(findings) > 1 else "")
        )
    return "PASS", (
        f"hard rule 4's allow list is where the PO left it on 2026-09-02: `mutable` "
        f"{sorted(CEILING['mutable'])}, `stamps` {sorted(CEILING['stamps'])}. "
        f"{files} migration file(s) read, {bodies} `{FUNCTION}` body/bodies, {arrays} "
        f"array(s) parsed; 8 synthetic breaches were detected first. Since payments/0051 "
        f"(CR-186-BRC10, PO 2026-10-21) a posted row may also use `clearing` "
        f"{sorted(CEILING['clearing'])}, and since payments/0052 a cleared row may go "
        f"back to posted through Unreconcile's window using `unclearing` "
        f"{sorted(CEILING['unclearing'])}"
    )


def main() -> int:
    status, detail = run()
    print(f"G131 {status}: {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

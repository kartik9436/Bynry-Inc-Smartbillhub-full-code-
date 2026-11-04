"""G41 — a tenant-isolation policy reads an UNSET tenant as *absent*, never as *broken*.

Added 2026-08-24 from DEF-639, and it exists because the test that proves the
same thing cannot run where it matters.

THE DEFECT, IN ITS OWN NUMBERS
------------------------------
Every RLS policy in this product used to read

    tenant_id = current_setting('app.tenant_id')::uuid

With `app.tenant_id` unset or empty, that CAST FAILS. The denial is correct —
nothing is visible — but it is LOUD, and the same policy is evaluated during
FOREIGN KEY VALIDATION. Three committed migrations create a table, enable FORCE
RLS on it, run a seed that ends `set_config('app.tenant_id','')`, and then exit,
at which point Django creates and validates the FKs it deferred. The validation
scan hit `invalid input syntax for type uuid: ""` and a FRESH DATABASE COULD NOT
BE BUILT: the repo's own sequencer applied 11 of 165 steps and died at step 12.

The PO ruled on 2026-08-24 — *"Change the security rule instead, in a new step"* —
choosing to fix the CLASS rather than the three instances. The predicate is now

    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid

`, true` makes an unset GUC return NULL instead of raising; `NULLIF(…, '')` turns
the empty string into NULL; and `tenant_id = NULL` is NULL, which is not TRUE, so
the row is denied. Deny-by-default (CLAUDE.md hard rule 1) is unchanged. What
changed is that absence of context is now SILENT on reads and still loud on
writes, via WITH CHECK.

WHY A GATE AND NOT ONLY A TEST
------------------------------
`tests/test_def639_unset_tenant_denies.py::tc6` asserts the same property
directly against `pg_policies` — and it can only run on live PostgreSQL, which
CI does not provision for the unit tier. So the one check that would catch a new
policy written in the old form does not run on any machine that would catch it
before merge. This gate needs no database and runs beside the other 22.

WHAT IT CHECKS, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
It is a RATCHET, not a ban, and the reason is that the old string legitimately
survives in three places: two docstrings that narrate what the predicate USED to
be (`core/rls.py`, `core/tenancy.py` — that narration is the point, hard-won law
10), and one `--` comment in `db/001_tenant_context_default.sql`. A blanket ban
would force those to be deleted, which would delete the explanation of why the
current form exists.

So: every scanned file's count of the OLD form may FALL and may never RISE, and a
file not in the baseline may not introduce it at all.

  Scanned:  06-backend/apps/*/migrations/*.py   (inline policy literals)
            06-backend/db/*.sql                 (loaded at migration RUN TIME)
            06-backend/core/*.py                (the partition template)

The 76 occurrences still inline in 24 committed migrations are BASELINED, not
forgiven: `audit.0005_rls_deny_on_unset_tenant` rewrites whatever they created,
so the END STATE of a built database is correct. They stay counted because a
committed migration may not be edited (`migration-guard.yml`), so the number can
only fall when one is superseded.

PROVING IT RED (hard-won law 7 — do this before trusting a green)
------------------------------------------------------------------
Append a policy in the old form to any scanned file and re-run:

    echo "CREATE POLICY x ON y USING (tenant_id = current_setting('app.tenant_id')::uuid);" \
      >> 06-backend/db/rls_audit_w0.sql

It must name the file, the old and new counts, and the correct predicate.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend"
BASELINE = pathlib.Path(__file__).with_name("g41_tenant_guc_baseline.txt")

#: The form that RAISES on an unset GUC. Matched literally — a policy is written
#: as one expression on one line everywhere in this repo, so no multiline dance.
OLD = "current_setting('app.tenant_id')::uuid"
NEW = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

CORRECT = (
    "A tenant policy must read\n"
    f"    tenant_id = {NEW}\n"
    "so that an unset or empty tenant marker DENIES (the comparison is NULL, which is\n"
    "not TRUE) instead of raising `invalid input syntax for type uuid: \"\"`. The bare\n"
    "cast is what made a fresh database un-buildable — DEF-639, PO ruling 2026-08-24."
)


def scanned() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    paths += sorted(BACKEND.glob("apps/*/migrations/*.py"))
    paths += sorted(BACKEND.glob("db/*.sql"))
    paths += sorted(BACKEND.glob("core/*.py"))
    return [p for p in paths if p.is_file()]


def counts() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in scanned():
        text = path.read_text(encoding="utf-8", errors="replace")
        n = text.count(OLD)
        if n:
            found[str(path.relative_to(ROOT))] = n
    return found


def read_baseline() -> dict[str, int]:
    if not BASELINE.exists():
        return {}
    out: dict[str, int] = {}
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rel, _, num = line.rpartition(" ")
        out[rel.strip()] = int(num)
    return out


def run() -> tuple[str, str]:
    """The gate proper, in the shape `run_gates.py` calls.

    ⚠ ADDED 2026-08-25 (DEF-674). This module shipped with `main()` and NO
    `run()`, while `run_gates.py` imports every gate and calls `.run()` on it —
    so the merge stack reported
    `AttributeError("module 'g41_tenant_guc_form' has no attribute 'run'")`
    for this gate on every run since it was added, and the crash was counted as
    a FAIL among other FAILs and never read.

    It is the exact mirror of DEF-672, where sixteen gates had `run()` and no
    `main()` and so exited 0 in silence when run directly. One convention,
    two halves, and a module could satisfy either alone and be dead in the
    other context. `main()` below now delegates here, so the two can no longer
    disagree about what this gate says.
    """
    now, base = counts(), read_baseline()
    problems: list[str] = []
    notes: list[str] = []

    for rel, n in sorted(now.items()):
        allowed = base.get(rel)
        if allowed is None:
            problems.append(
                f"{rel}: introduces the OLD tenant predicate ({n}x) and is not in the baseline."
            )
        elif n > allowed:
            problems.append(
                f"{rel}: the OLD tenant predicate rose from {allowed} to {n}. "
                "This count may fall, never rise."
            )

    fell = {rel: (base[rel], now.get(rel, 0)) for rel in base if now.get(rel, 0) < base[rel]}
    if fell:
        lines = ", ".join(f"{rel} {was}->{is_}" for rel, (was, is_) in sorted(fell.items()))
        notes.append(
            f"the old form FELL in {len(fell)} file(s) — {lines}; lower the numbers in "
            "g41_tenant_guc_baseline.txt so the ratchet holds"
        )

    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems) + f" {CORRECT}"

    total = sum(now.values())
    message = (
        f"{total} baselined occurrence(s) of the old tenant predicate across {len(now)} "
        "file(s), none new. Every policy a fresh database builds ends up in the NULLIF form "
        "(audit.0005 normalises the committed migrations at run time)."
    )
    if notes:
        message += " note: " + "; ".join(notes)
    return "PASS", message


def main() -> int:
    now, base = counts(), read_baseline()
    problems: list[str] = []

    for rel, n in sorted(now.items()):
        allowed = base.get(rel)
        if allowed is None:
            problems.append(
                f"{rel}: introduces the OLD tenant predicate ({n}×) and is not in the baseline.\n"
                f"{CORRECT}"
            )
        elif n > allowed:
            problems.append(
                f"{rel}: the OLD tenant predicate rose from {allowed} to {n}. "
                "This count may fall, never rise.\n"
                f"{CORRECT}"
            )

    fell = {rel: (base[rel], now.get(rel, 0)) for rel in base if now.get(rel, 0) < base[rel]}
    if fell:
        lines = ", ".join(f"{rel} {was}→{is_}" for rel, (was, is_) in sorted(fell.items()))
        print(f"note: the old form FELL in {len(fell)} file(s) — {lines}")
        print("      lower the numbers in g41_tenant_guc_baseline.txt so the ratchet holds.")

    if problems:
        print(f"G41 FAIL — {len(problems)} problem(s):")
        for p in problems:
            print("  " + p.replace("\n", "\n    "))
        return 1

    total = sum(now.values())
    print(
        f"G41 PASS: {total} baselined occurrence(s) of the old tenant predicate across "
        f"{len(now)} file(s), none new. Every policy a fresh database builds ends up in the "
        "NULLIF form (audit.0005 normalises the committed migrations at run time)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

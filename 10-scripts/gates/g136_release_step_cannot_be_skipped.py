#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-INF-7683 (2026-09-28) — nobody could sign in at
#          smartbillhub.bynry.com. Every `POST /api/<slug>/auth/session`
#          answered 500 over `UndefinedColumn: column
#          security_policies.absolute_session_hours does not exist`, while
#          `GET /api/health` answered `200 {"status":"ok"}` throughout, because
#          the rollout ran without the release task that migrates.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee — the entrypoint PREDICTED this outage in prose and
#          shipped no check beside the prediction) · law 2 (built is not
#          wired) · law 7 (prove it RED first, in the harness that runs it;
#          and say what you did NOT check beside what you did) ·
#          CR-144-BRC07 H4 (a web task must never migrate).
# Tests:   selftest() below · 06-backend/tests/test_def_inf_7683_schema_guard.py
# Impacts: 06-backend/docker-entrypoint.sh · 06-backend/docker-release.sh ·
#          06-backend/core/schema_guard.py · Makefile · 09-infra/02-aws-runbook.md
# ───────────────────────────────────────────────────────
"""G136 — the web task never migrates, and never serves a schema it cannot serve.

WHY THIS GATE EXISTS
--------------------
`CR-144-BRC07` task H4 moved `manage.py migrate` out of `docker-entrypoint.sh`
and into `docker-release.sh`, for three reasons that are all correct: two tasks
migrating concurrently with no advisory lock, a slow migration failing the
health check that is waiting on it, and a scale-out running DDL.

**What moved with the migrate, and nobody noticed, is a GUARANTEE.** While
every web task migrated on boot, a task could not physically serve a schema
older than its code. The invariant was held by an implementation detail rather
than by a check, and the day the detail moved, the guarantee went with it and
**nothing anywhere went red.** The product was down within hours.

So the two halves are now held together by something that fails at merge:

* the migrate must stay OUT of the web entrypoint (H4's ruling, kept), and
* the web entrypoint must ASK whether the schema is current (the guarantee,
  restored as a check), and
* `docker-release.sh` must still be the thing that migrates, and
* the runbook must still name the one-line recovery, because at 3am a rule
  nobody can find is a rule nobody follows.

Delete any one of the four and this gate names which one.

⚠ **WHAT WOULD MAKE THIS GATE PASS WRONGLY** — hard-won law 7's second habit,
answered rather than left to be discovered:

1. **The strings are present only in a COMMENT.** Both scripts are mostly
   comment by line count, and the very prose this gate is written about was a
   comment. So every executable-line check below reads the file with `#` lines
   and blank lines REMOVED, and the comment-only case is what `selftest()`
   proves it catches.
2. **The guard is invoked AFTER gunicorn.** `exec gunicorn` never returns, so a
   call below it never runs — the check would be present and dead, which is
   law 2 exactly. The order is asserted, by line number.
3. **The guard is renamed.** Then the substring check fails and this gate goes
   RED, which is the correct outcome: a rename must move this gate too.
4. **It cannot see a deploy.** This gate reads FILES. It cannot tell whether a
   human ran the release task, whether a task definition carries
   `SBH_ALLOW_PENDING_MIGRATIONS=1`, or whether the ECS pipeline that
   `09-infra/02-aws-runbook.md` §H6 describes exists at all — **it does not,
   every workflow in `.github/workflows/` is `.disabled`.** That is the gap the
   BOOT-TIME guard covers and no gate can. Stated in the PASS line, because a
   declared blind spot with no number beside it is indistinguishable from an
   empty one.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ENTRYPOINT = REPO / "06-backend" / "docker-entrypoint.sh"
RELEASE = REPO / "06-backend" / "docker-release.sh"
GUARD = REPO / "06-backend" / "core" / "schema_guard.py"
MAKEFILE = REPO / "Makefile"
RUNBOOK = REPO / "09-infra" / "02-aws-runbook.md"

#: `python manage.py migrate` in any spelling a shell script would use.
MIGRATE_CALL = re.compile(r"manage\.py\s+migrate\b")

#: How the entrypoint reaches the guard.
#: ⚠ **QUALIFIED, AND THE QUALIFIER IS THE WHOLE CHECK.** The first draft looked
#: for the bare string `enforce_at_startup` — and the entrypoint calls
#: `rls_guard.enforce_at_startup` twenty lines earlier, so the gate matched the
#: WRONG GUARD and reported **PASS** over an entrypoint whose schema check had
#: been deleted. It was found by running this gate's own RED proof through
#: `run_gates`, which is exactly why hard-won law 7 asks for that proof and not
#: for a selftest alone: the selftest's mutation commented out EVERY line
#: containing the bare name, so it went red for a reason the real regression
#: does not share. `selftest()` now mutates only the schema line.
GUARD_IMPORT = "from core import schema_guard"
GUARD_CALL = "schema_guard.enforce_at_startup"

#: The one line an operator needs at 3am, and where they will look for it.
RECOVERY_TOKENS = ("make release", "docker-release.sh", "showmigrations --plan")


def executable_lines(text: str) -> list[tuple[int, str]]:
    """`(1-based line number, line)` for every line that is not a comment.

    A shell comment cannot run, and the failure this gate exists for was a
    correct prediction living in a comment. Reading the whole file would let a
    lane satisfy every check below by writing a sentence about it.
    """
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append((number, line))
    return out


def findings(
    entrypoint: str | None = None,
    release: str | None = None,
    makefile: str | None = None,
    runbook: str | None = None,
    guard_exists: bool | None = None,
) -> tuple[list[str], dict]:
    """Return `(problems, what_was_seen)`. Pure, so `selftest()` can mutate input."""
    problems: list[str] = []
    seen: dict[str, object] = {}

    entry_text = ENTRYPOINT.read_text(encoding="utf-8") if entrypoint is None else entrypoint
    rel_text = RELEASE.read_text(encoding="utf-8") if release is None else release
    make_text = MAKEFILE.read_text(encoding="utf-8") if makefile is None else makefile
    book_text = RUNBOOK.read_text(encoding="utf-8") if runbook is None else runbook
    have_guard = GUARD.is_file() if guard_exists is None else guard_exists

    entry_code = executable_lines(entry_text)
    rel_code = executable_lines(rel_text)
    seen["entrypoint_code_lines"] = len(entry_code)
    seen["release_code_lines"] = len(rel_code)

    # ── 1 · The web entrypoint must NOT migrate (CR-144-BRC07 H4) ───────────
    migrating = [n for n, line in entry_code if MIGRATE_CALL.search(line)]
    if migrating:
        problems.append(
            "docker-entrypoint.sh RUNS `manage.py migrate` again, at line(s) "
            f"{', '.join(str(n) for n in migrating)} — CR-144-BRC07 H4 moved it out: "
            "two tasks migrate with no advisory lock, a slow migration fails the "
            "health check waiting on it, and a scale-out runs DDL"
        )

    # ── 2 · …and it must ASK whether the schema is current (DEF-INF-7683) ──
    guard_lines = [n for n, line in entry_code if GUARD_CALL in line or GUARD_IMPORT in line]
    called = [n for n, line in entry_code if GUARD_CALL in line]
    if not called:
        problems.append(
            "docker-entrypoint.sh never CALLS "
            f"`{GUARD_CALL}` on an executable line — without it a web "
            "task serves an older schema, answers 500 to every sign-in and reports "
            "healthy while doing it (DEF-INF-7683)"
        )
    seen["guard_lines"] = guard_lines

    # ── 3 · …and it must ask BEFORE it serves ───────────────────────────────
    gunicorn_lines = [n for n, line in entry_code if "exec gunicorn" in line]
    if called and gunicorn_lines:
        if min(called) > min(gunicorn_lines):
            problems.append(
                f"the schema check is at line {min(called)}, AFTER `exec gunicorn` at "
                f"line {min(gunicorn_lines)} — `exec` never returns, so the check is "
                "present and dead (hard-won law 2)"
            )
    elif not gunicorn_lines:
        problems.append(
            "docker-entrypoint.sh no longer `exec gunicorn`s — this gate can no "
            "longer tell whether the check runs before the process serves"
        )
    seen["gunicorn_line"] = gunicorn_lines[0] if gunicorn_lines else None

    # ── 4 · The guard module must exist and must REFUSE ─────────────────────
    if not have_guard:
        problems.append(
            "06-backend/core/schema_guard.py is missing — the entrypoint's check "
            "has nothing to call"
        )
    elif guard_exists is None:
        guard_text = GUARD.read_text(encoding="utf-8")
        if "raise ImproperlyConfigured" not in guard_text:
            problems.append(
                "core/schema_guard.py no longer RAISES — a guard that only prints "
                "is a warning, and a warning lets the task into the balancer's "
                "rotation, which is the whole of DEF-INF-7683"
            )
        if "UNREACHABLE" not in guard_text:
            problems.append(
                "core/schema_guard.py lost its UNREACHABLE state — "
                "`migrate --check` exits 1 both for pending migrations AND for a "
                "database it cannot reach, so collapsing the two crash-loops the "
                "service through a failover"
            )

    # ── 5 · The release script must still be the thing that migrates ────────
    rel_migrating = [n for n, line in rel_code if MIGRATE_CALL.search(line)]
    if not rel_migrating:
        problems.append(
            "docker-release.sh does not run `manage.py migrate` on any executable "
            "line — migrations now happen nowhere at all"
        )
    seen["release_migrate_line"] = rel_migrating[0] if rel_migrating else None

    # ── 6 · `make up` must run the release step ─────────────────────────────
    up_calls_release = re.search(r"^up:.*(?:\n(?!\S).*)*", make_text, re.MULTILINE)
    if not up_calls_release or "release" not in up_calls_release.group(0):
        problems.append(
            "Makefile's `up` target no longer runs `release`, so `make up` builds a "
            "stack against an unmigrated database"
        )

    # ── 7 · The runbook must name the recovery, where they will look ────────
    missing_tokens = [t for t in RECOVERY_TOKENS if t not in book_text]
    if missing_tokens:
        problems.append(
            "09-infra/02-aws-runbook.md does not name "
            + ", ".join(repr(t) for t in missing_tokens)
            + " — the operator reading it during an outage is the reader this "
            "whole defect was about"
        )

    # ── 8 · Not an empty parse (DEF-057's shape) ────────────────────────────
    if len(entry_code) < 10 or len(rel_code) < 5:
        problems.append(
            f"PARSE LOOKS BROKEN: {len(entry_code)} executable line(s) in the "
            f"entrypoint and {len(rel_code)} in the release script. A parse that "
            "finds nothing would otherwise report a confident PASS"
        )

    return problems, seen


def selftest() -> int:
    """Prove each clause RED on a mutation of the real files (hard-won law 7)."""
    entry = ENTRYPOINT.read_text(encoding="utf-8")
    release = RELEASE.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    problems, seen = findings()
    if problems:
        print("SELFTEST FAIL — the real tree is already red:", problems)
        return 1

    cases = [
        (
            "the schema guard's call is REPLACED BY `pass` and the RLS guard's "
            "identically-named call is left alone (the false pass this gate shipped "
            "with for twenty minutes)",
            dict(
                entrypoint=re.sub(
                    r"^(\s*)schema_guard\.enforce_at_startup\(.*\)$",
                    r"\1pass  # deleted",
                    entry,
                    flags=re.MULTILINE,
                )
            ),
            "never CALLS",
        ),
        (
            "the guard call is COMMENTED OUT",
            dict(
                entrypoint=re.sub(
                    r"^(\s*)(.*schema_guard\.enforce_at_startup.*)$",
                    r"\1# \2",
                    entry,
                    flags=re.MULTILINE,
                )
            ),
            "never CALLS",
        ),
        (
            "`migrate` comes back to the web entrypoint",
            dict(entrypoint=entry.replace("exec gunicorn", "python manage.py migrate --noinput\nexec gunicorn")),
            "RUNS `manage.py migrate` again",
        ),
        (
            "the release script stops migrating",
            dict(release=release.replace("python manage.py migrate --noinput", "true")),
            "migrations now happen nowhere",
        ),
        (
            "`make up` stops running the release step",
            dict(makefile=makefile.replace("\t$(MAKE) release\n", "")),
            "no longer runs `release`",
        ),
        (
            "the runbook loses the recovery command",
            dict(runbook=runbook.replace("make release", "run the thing")),
            "does not name",
        ),
        (
            "the guard module is deleted",
            dict(guard_exists=False),
            "is missing",
        ),
    ]

    for label, mutation, expected in cases:
        got, _ = findings(**mutation)
        if not any(expected in one for one in got):
            print(f"SELFTEST FAIL — {label}: not caught. Got: {got}")
            return 1

    # And the order clause, which needs the call MOVED rather than removed —
    # the "present and dead" shape. Every existing mention is stripped and one
    # is re-added below `exec gunicorn`, which never returns.
    stripped = "\n".join(
        line for line in entry.splitlines() if GUARD_CALL not in line
    )
    moved = (
        stripped
        + "\npython -c 'from core import schema_guard; "
        + f"{GUARD_CALL}()'\n"
    )
    got, _ = findings(entrypoint=moved)
    if not any("AFTER `exec gunicorn`" in one for one in got):
        print("SELFTEST FAIL — a check placed after `exec gunicorn` was not caught:", got)
        return 1

    print(
        "SELFTEST PASS — the real tree passes with the schema check at line "
        f"{min(seen['guard_lines'])} and `exec gunicorn` at line {seen['gunicorn_line']}; "
        "eight mutations each go red, including the one that leaves the RLS guard's "
        "identically-named call in place"
    )
    return 0


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    ⚠ Both entry points on purpose — `DEF-GOV-3733` is two gates announced
    green through `__main__` while the suite reported
    `module has no attribute 'run'`.
    """
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"the web entrypoint does not migrate, asks `{GUARD_CALL}` at "
        f"line {min(seen['guard_lines'])} — before `exec gunicorn` at line "
        f"{seen['gunicorn_line']} — docker-release.sh migrates at line "
        f"{seen['release_migrate_line']}, `make up` runs `release`, and the runbook "
        f"names all {len(RECOVERY_TOKENS)} recovery tokens. It reads FILES: it cannot "
        "tell whether anyone RAN the release task, whether a task definition carries "
        "SBH_ALLOW_PENDING_MIGRATIONS, or whether a deploy pipeline exists — it does "
        "not, every workflow in .github/workflows/ is .disabled. That gap is the "
        "boot-time guard's, not this gate's",
    )


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    status, note = run()
    print(f"G136 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

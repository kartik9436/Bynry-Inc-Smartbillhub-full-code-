#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Task:    one-time bill build plan T2 (04-docs/05-modules/07-billing/
#          12-one-time-bill-build-plan.md) — "PostgreSQL proofs for every path
#          that catches a DB error, and the money paths above (law 14)".
# Rules:   CLAUDE.md hard-won law 14 (a failed statement poisons a PostgreSQL
#          transaction; the default suite is SQLite and cannot see it) · law 7
#          (prove a guard RED before trusting it green, through the harness that
#          runs it) · law 3 (fail closed: this refuses to report on SQLite).
# Tests:   06-backend/tests/test_otb_t2_money_paths_pg.py (written for this) ·
#          tests/test_b11_issue_hardening.py (the `_issue_one` savepoint, B11) ·
#          tests/test_b4_missing_base_bills_zero_with_warning.py (missing base)
# ───────────────────────────────────────────────────────
"""THE ONE-TIME BILL'S MONEY PATHS AND ITS SAVEPOINT, PROVED ON POSTGRESQL.

    DATABASE_URL=postgres://sbh:sbh@127.0.0.1:55611/sbh_otbt2 \\
        python3 10-scripts/otb_t2_pg_proofs.py green      # the proofs, one line each
    …   python3 10-scripts/otb_t2_pg_proofs.py red        # the savepoint REMOVED → RED
    …   python3 10-scripts/otb_t2_pg_proofs.py both

`green` runs the three test files under `--ds=config.settings.pgtest --reuse-db`
and prints one PASS/FAIL line per proof with its figure (the `PROOF …` lines
the cases print, plus pytest's own verdict).

`red` is law 7 for the one guard here that catches a database error and goes
on: the per-bill savepoint in `apps/billing/issue.py::issue_run` around
`_issue_one` (B11). It copies `06-backend` to a SCRATCH directory (the other
top-level folders are symlinked, so nothing in the checkout is touched and
nothing is committed), rewrites exactly one line there —
`with transaction.atomic():` above `_issue_one(` becomes `if True:` — refuses
if that line is not found exactly once, and runs
`test_B11_a_database_error_on_one_bill_does_not_poison_the_rest` from the copy
against the SAME test database. It must FAIL, and the failure must be
PostgreSQL's aborted-transaction state (`InFailedSqlTransaction` or Django's
`TransactionManagementError`); anything else is reported as an inconclusive red.

WHAT IT REFUSES, BECAUSE EACH WAS A REAL WAY TO GET A MEANINGLESS ANSWER:
  * a `DATABASE_URL` that is not PostgreSQL — `pgtest` refuses too, but this
    says so before a six-minute migrate;
  * a server whose encoding is not UTF8. Measured 2026-09-30: a cluster made
    by a bare `initdb` in a `C` locale is `SQL_ASCII`, and tenant provisioning
    then fails at `import_mappings` with `DataError: unsupported Unicode escape
    sequence` — so EVERY `brazos`-fixture case errors at setup, 21 of 22 on the
    first run, and the one that "passed" touched no database. That reads like a
    product defect and is the cluster; `initdb -E UTF8 --locale=C.UTF-8`.

The cluster is the operator's. Earlier lanes' pattern: `initdb` + `pg_ctl` as
the `postgres` user under `/tmp/pg16_<lane>`, a free port, and `pg_ctl stop`
when done.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "06-backend"
FILES = [
    "tests/test_otb_t2_money_paths_pg.py",
    "tests/test_b11_issue_hardening.py",
    "tests/test_b4_missing_base_bills_zero_with_warning.py",
]
SAVEPOINT_CASE = (
    "tests/test_b11_issue_hardening.py::"
    "test_B11_a_database_error_on_one_bill_does_not_poison_the_rest"
)
SAVEPOINT_LINE = re.compile(
    r"^(?P<indent>[ ]+)with transaction\.atomic\(\):\n"
    r"(?P=indent)    billed, per_account, pin_problem = _issue_one\(",
    re.MULTILINE,
)
POISON = ("InFailedSqlTransaction", "TransactionManagementError", "current transaction is aborted")


def _python() -> str:
    return os.environ.get("PYTHON") or sys.executable


def _preflight() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgres://", "postgresql://")):
        raise SystemExit(f"REFUSED: DATABASE_URL must be PostgreSQL (got {url!r}). Law 14.")
    import psycopg  # noqa: PLC0415 — only needed here

    with psycopg.connect(url) as conn:
        version = conn.execute("show server_version").fetchone()[0]
        encoding = conn.execute("show server_encoding").fetchone()[0]
    if encoding.upper() != "UTF8":
        raise SystemExit(
            f"REFUSED: server_encoding is {encoding}, not UTF8 — tenant provisioning "
            "fails at import_mappings and every fixture errors. Re-initdb with "
            "-E UTF8 --locale=C.UTF-8."
        )
    print(f"server: PostgreSQL {version}, encoding {encoding}")
    return version


def _test_db_name() -> str:
    """The test database the GREEN run uses — base.py's per-checkout name —
    so the red run in the scratch copy reuses it instead of migrating again."""
    if os.environ.get("SBH_TEST_DB_NAME"):
        return os.environ["SBH_TEST_DB_NAME"]
    out = subprocess.run(
        [
            _python(),
            "-c",
            "import django,os;os.environ['DJANGO_SETTINGS_MODULE']='config.settings.pgtest';"
            "from django.conf import settings;print(settings.DATABASES['default']['TEST']['NAME'])",
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip().splitlines()[-1]


def _pytest(cwd: Path, targets: list[str], extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "JOBS_EAGER": "false", **extra_env}
    return subprocess.run(
        [
            _python(),
            "-m",
            "pytest",
            *targets,
            "--ds=config.settings.pgtest",
            "--reuse-db",
            "-p",
            "no:cacheprovider",
            "-W",
            "ignore",
            "-q",
            "-s",
            "-rA",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def green(db_name: str) -> int:
    run = _pytest(BACKEND, FILES, {"SBH_TEST_DB_NAME": db_name})
    out = run.stdout + run.stderr
    verdicts = re.findall(r"^(PASSED|FAILED|ERROR) (\S+)", out, re.MULTILINE)
    # NOT anchored at line start: `-s` prints each case's PROOF line straight
    # after pytest's progress dots, so `^PROOF` saw ONE of the seven (measured
    # 2026-09-30) and printed a short list that read like the whole list.
    proofs = re.findall(r"PROOF \S+ vendor=.*$", out, re.MULTILINE)
    expected = len(re.findall(r'print\(\s*f?"PROOF ', (BACKEND / FILES[0]).read_text()))
    print(f"\n== GREEN: {len(verdicts)} cases on test database {db_name}")
    for verdict, node in verdicts:
        print(f"  {'PASS' if verdict == 'PASSED' else 'FAIL'}  {node}")
    print("\n== FIGURES (read back from invoices / invoice_lines by raw SQL)")
    for line in proofs:
        print("  " + line)
    print(f"  ({len(proofs)} figure line(s) found; {expected} printed by the test file)")
    summary = [ln for ln in out.splitlines() if re.search(r"\d+ (passed|failed|error)", ln)]
    print("\n" + (summary[-1] if summary else "(no pytest summary line — read the run)"))
    if not verdicts:
        print(out[-4000:])
        return 2
    return 0 if all(v == "PASSED" for v, _ in verdicts) else 1


def red(db_name: str) -> int:
    source = (BACKEND / "apps/billing/issue.py").read_text()
    hits = SAVEPOINT_LINE.findall(source)
    if len(hits) != 1:
        print(f"REFUSED: expected the savepoint line exactly once in issue.py, found {len(hits)}.")
        return 2
    broken = SAVEPOINT_LINE.sub(
        lambda m: (
            f"{m.group('indent')}if True:  # RED PROOF — savepoint removed in a scratch copy\n"
            f"{m.group('indent')}    billed, per_account, pin_problem = _issue_one("
        ),
        source,
        count=1,
    )
    scratch = Path(tempfile.mkdtemp(prefix="otb_t2_red_"))
    try:
        for entry in REPO.iterdir():
            if entry.name in {"06-backend", ".git"}:
                continue
            (scratch / entry.name).symlink_to(entry)
        shutil.copytree(
            BACKEND,
            scratch / "06-backend",
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "node_modules", ".venv"),
        )
        (scratch / "06-backend/apps/billing/issue.py").write_text(broken)
        run = _pytest(scratch / "06-backend", [SAVEPOINT_CASE], {"SBH_TEST_DB_NAME": db_name})
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    out = run.stdout + run.stderr
    failed = run.returncode != 0 and re.search(r"^FAILED ", out, re.MULTILINE)
    poison = [marker for marker in POISON if marker in out]
    print(f"\n== RED (savepoint removed in a scratch copy): pytest exit {run.returncode}")
    for line in out.splitlines():
        if any(marker in line for marker in POISON) or line.startswith(("FAILED", "E   ")):
            print("  " + line.strip()[:300])
    if failed and poison:
        print(f"RED AS REQUIRED — PostgreSQL's aborted transaction named: {poison}")
        return 0
    if failed:
        print("RED, BUT INCONCLUSIVE — it failed without naming the aborted transaction.")
        return 1
    print("NOT RED — the savepoint's removal went unnoticed; this proof proves nothing.")
    print(out[-3000:])
    return 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    if mode not in {"green", "red", "both"}:
        raise SystemExit(__doc__)
    _preflight()
    db_name = _test_db_name()
    codes = []
    if mode in {"green", "both"}:
        codes.append(green(db_name))
    if mode in {"red", "both"}:
        codes.append(red(db_name))
    return max(codes)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""THE BULK CHECK'S PER-ACCOUNT SAVEPOINT, PROVED ON POSTGRESQL (law 14).

    DATABASE_URL=postgres://sbh:sbh@127.0.0.1:<port>/sbh_bbr \\
        python3 10-scripts/bbr_check_engine_pg_proof.py green   # the proofs
    …   python3 10-scripts/bbr_check_engine_pg_proof.py red     # savepoints REMOVED → RED

`green` runs the Check-engine tests under `--ds=config.settings.pgtest
--reuse-db` (the PostgreSQL-only savepoint case included) and prints pytest's
verdict and the `PROOF` line.

`red` copies `06-backend` to a SCRATCH directory (the other top-level folders
symlinked; nothing in the checkout is touched), rewrites every
`with transaction.atomic():` in `apps/billing/check_engine.py` to `if True:`
— refusing unless it finds the expected number — and runs the savepoint case
from the copy. It must FAIL, and the failure must be PostgreSQL's
aborted-transaction state (`InFailedSqlTransaction` /
`TransactionManagementError`) reaching the NEXT account; anything else is an
inconclusive red.

The cluster is the operator's: `initdb -E UTF8 --locale=C.UTF-8` as the
`postgres` user (a bare `initdb` in a C locale is SQL_ASCII and every
tenant-provisioning fixture fails at setup), `pg_ctl` on a free port, and
`pg_ctl stop` when done — the `otb_t2_pg_proofs.py` pattern.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "06-backend"
FILES = ["tests/test_bbr_check_pg.py", "tests/test_bbr_check_engine.py", "tests/test_bbr_check_store.py"]
CASE = "tests/test_bbr_check_pg.py::test_tc2_pg__a_database_error_on_the_middle_account_blocks_only_it"
TARGET = "apps/billing/check_engine.py"
#: The savepoints in check_engine: `_Guard.run`, `check_account`, the
#: readings probe and `_nothing_to_bill`.
EXPECTED_SAVEPOINTS = 4


def _python() -> str:
    return os.environ.get("SBH_PYTHON") or sys.executable


def _pytest(cwd: Path, targets: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, JOBS_EAGER="false")
    if not env.get("DATABASE_URL", "").startswith("postgres"):
        raise SystemExit("DATABASE_URL must name a PostgreSQL database (law 14)")
    return subprocess.run(
        [_python(), "-m", "pytest", "-q", "-s", "--reuse-db", "--ds=config.settings.pgtest",
         "-p", "no:cacheprovider", *targets],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def green() -> int:
    done = _pytest(BACKEND, FILES)
    tail = done.stdout.strip().splitlines()[-1:] if done.stdout else []
    for line in done.stdout.splitlines():
        if line.startswith("PROOF") or "TC-A1 timing" in line:
            print(line)
    print("GREEN:", *tail)
    return done.returncode


def red() -> int:
    scratch = Path(tempfile.mkdtemp(prefix="bbr_red_"))
    try:
        for entry in REPO.iterdir():
            if entry.name == "06-backend":
                continue
            (scratch / entry.name).symlink_to(entry)
        shutil.copytree(BACKEND, scratch / "06-backend", symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.sqlite3"))
        target = scratch / "06-backend" / TARGET
        text = target.read_text()
        found = text.count("with transaction.atomic():")
        if found != EXPECTED_SAVEPOINTS:
            raise SystemExit(f"expected {EXPECTED_SAVEPOINTS} savepoints in {TARGET}, found {found}")
        target.write_text(text.replace("with transaction.atomic():", "if True:"))
        done = _pytest(scratch / "06-backend", [CASE])
        out = done.stdout + done.stderr
        aborted = "InFailedSqlTransaction" in out or "TransactionManagementError" in out
        for line in out.splitlines():
            if line.startswith(("PROOF", "E  ")) and len(line) < 400:
                print(line)
        verdict = "RED (conclusive)" if done.returncode and aborted else (
            "RED (inconclusive)" if done.returncode else "NOT RED — the proof failed"
        )
        print("RED:", verdict, "|", (done.stdout.strip().splitlines() or [""])[-1])
        return 0 if done.returncode and aborted else 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    code = 0
    if mode in ("green", "both"):
        code |= green()
    if mode in ("red", "both"):
        code |= red()
    raise SystemExit(code)

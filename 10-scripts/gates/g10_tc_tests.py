"""G10 - TC-named tests (B12 r2 / B8): every built story ships its TCs as tests.

Per-territory check, driven by where a story's Trace headers appear:
- Story cited in a 06-backend file -> a pytest function named
  `test_us_<mod>_<nnn>_tc...` (B8 naming) must exist under 06-backend.
- Story cited in a 07-frontend file -> its US-ID must appear inside a
  `*.test.ts`/`*.test.tsx` file under 07-frontend (vitest names embed the
  US-ID + TC per B8 "tests embed TC IDs").
A story cited in both territories needs both.

The coverage-percentage half of G10 (services >= 85%) needs a full pytest-cov
environment and arrives with ci-backend; this gate covers the grep-able half.
"""
import sys
import re

import common


def run() -> tuple[str, str]:
    cited_backend: set[str] = set()
    cited_frontend: set[str] = set()
    for path, text in common.files_with_trace_header():
        header = "\n".join(common.trace_header_lines(text))
        ids = set(common.US_ID_RE.findall(header))
        if common.BACKEND_DIR in path.parents:
            cited_backend |= ids
        if common.FRONTEND_SRC in path.parents:
            cited_frontend |= ids
    if not (cited_backend or cited_frontend):
        return "SKIP", "no US-IDs cited in Trace headers yet — activates with the first story code"

    missing = []

    be_haystack = "\n".join(common.read_text(p) for p in common.BACKEND_DIR.rglob("*.py")).lower()
    for us_id in sorted(cited_backend):
        module, number = re.fullmatch(r"US-([A-Z]{3})-(\d{3,6})", us_id).groups()
        needle = f"def test_us_{module.lower()}_{number}_tc"
        if needle not in be_haystack:
            missing.append(f"{us_id}: no test named test_us_{module.lower()}_{number}_tc* under 06-backend")

    fe_test_files = [p for p in common.FRONTEND_SRC.rglob("*.test.*") if p.suffix in {".ts", ".tsx"}]
    fe_haystack = "\n".join(common.read_text(p) for p in fe_test_files)
    for us_id in sorted(cited_frontend):
        if us_id not in fe_haystack:
            missing.append(f"{us_id}: no *.test.ts(x) under 07-frontend mentions it")

    if missing:
        return "FAIL", common.summarize(missing)
    total = len(cited_backend | cited_frontend)
    return "PASS", f"all {total} Trace-cited story(ies) have TC-named tests in their territory"


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

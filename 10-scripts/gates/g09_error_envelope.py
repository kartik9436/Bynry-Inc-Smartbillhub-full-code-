"""G9 - error-envelope conformance (B12 §3 + Addendum r1 HTTP table), grep level.

Once api.py files contain non-stub code (anything beyond a docstring and
imports), each such file must raise only catalog exceptions — imported from
`core.errors` — never bare ValueError/Exception into a response. This is the
cheap grep tier; full response-shape validation against the OpenAPI contract
(A11) arrives with the generated client tooling.

SKIPs until the first endpoint exists.
"""
import sys
import ast
import re

import common

BARE_RAISE_RE = re.compile(r"\braise (ValueError|Exception)\b")
CATALOG_IMPORT_RE = re.compile(r"from core(\.errors| import errors)\b|from core\.errors import")


def _has_endpoint_code(path) -> bool:
    """True when the module body holds anything beyond a docstring and imports."""
    tree = ast.parse(common.read_text(path))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring
        return True
    return False


def run() -> tuple[str, str]:
    api_files = sorted(common.BACKEND_APPS.glob("*/api.py")) if common.BACKEND_APPS.is_dir() else []
    if not api_files:
        return "SKIP", "no api.py files in 06-backend/apps yet"
    live = [p for p in api_files if _has_endpoint_code(p)]
    if not live:
        return "SKIP", (f"all {len(api_files)} api.py files are docstring-only stubs — "
                        "gate activates with the first endpoint")

    problems = []
    for path in live:
        text = common.read_text(path)
        if not CATALOG_IMPORT_RE.search(text):
            problems.append(f"{common.rel(path)}: endpoint code without importing catalog exceptions (core.errors)")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            match = BARE_RAISE_RE.search(line)
            if match:
                problems.append(f"{common.rel(path)}:{lineno}: raises bare {match.group(1)} — "
                                "use the B12 §3 catalog (core.errors)")
    if problems:
        return "FAIL", common.summarize(problems)
    return "PASS", f"{len(live)} endpoint file(s) raise catalog exceptions only"


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

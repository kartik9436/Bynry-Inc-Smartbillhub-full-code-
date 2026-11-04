#!/usr/bin/env python3
"""G58 — a STREAMED response body must carry its own tenant context.

WHY THIS GATE EXISTS
--------------------
`DEF-2734` (2026-08-31). `StreamingHttpResponse` returns from the view with its
body UNCONSUMED. `core.tenancy.TenantContextMiddleware` clears `app.tenant_id`
in a `finally` the moment the view returns, and WSGI iterates the body
afterwards — so the generator's first query runs with **no tenant marker**, the
RLS policy's `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL,
`tenant_id = NULL` is not TRUE, and the queryset yields **zero rows**.

Nothing raises. The download succeeds with **200**. The file is a header row and
nothing under it — and an empty rejects file reads as *"nothing was rejected"*,
which is the exact `DEF-320` failure `metering.read_rejects._refuse_not_decided`
cites in its own docstring as the reason it refuses rather than serving one.

It hit **both** streamed routes in this codebase, written a day apart by two
different lanes for two different features:

    apps/metering/api.py:1163  read_batch_results_csv   (CR-054 task 16, reads)
    apps/metering/api.py:1774  import_results_csv       (CR-047 task 13, accounts)

⚠ **THIS GATE WAS WRITTEN AS `G56` AND RENUMBERED AT PUSH TIME.** Two siblings
took `G56` (`g56_rls_runtime_guard.py`, DEF-2717) and `G57`
(`g57_tenant_guc_not_faked.py`, DEF-2761) between this lane's base and the
branch tip, and both are about the SAME hour of the same day and the same root
cause — a database role that had been bypassing row-level security. That is
`DEF-1787`'s shape (an allocated id is a blob too), and it was caught by
re-deriving the number from the pinned tip rather than trusting one computed
twenty minutes earlier.

**READ THE THREE TOGETHER, because they are three different layers of one
question — *is the tenant marker really reaching the database?***
  * **`G56`** asks it of the RUNNING APPLICATION: the role it connects as must
    not bypass RLS.
  * **`G57`** asks it of the TEST FIXTURES: nothing may stand in front of the
    kernel that sets `app.tenant_id`.
  * **`G58`** (this one) asks it of the RESPONSE: a body iterated after the
    request has ended must re-enter the context the request was granted.

WHY A GATE AND NOT ONLY THE FIX
-------------------------------
Two lanes wrote the identical trap independently, so the trap is the defect and
the two routes are instances. The fix — `core.tenancy.stream_within_tenant_context`
— is one line per call site, and a rule that costs one line and depends on
someone REMEMBERING it is exactly the rule this repo keeps recording as skipped
(change-process step 7's own argument, and every version bump before G35).

WHY NO TEST CAN STAND IN FOR IT
-------------------------------
`tests/test_def2734_streamed_tenant_context.py` proves the property, and it
**only runs on live PostgreSQL under a role that is subject to RLS**, which CI
does not provision for the unit tier. Three separate things hide this defect
from a normal run:

  1. `config/settings/test.py` hardcodes in-memory SQLite, which has NO
     row-level security at all (CLAUDE.md law 14).
  2. A SUPERUSER or `BYPASSRLS` role bypasses RLS completely, FORCE included,
     while every table still reports `relrowsecurity=t` — the two routes passed
     their checks twice on the very database that then failed, an hour apart,
     because a sibling lane revoked that bit in between (`DEF-2717`).
  3. The two tests that DID cover these routes end to end assert on the CSV
     **header**, which is a Python constant yielded before any query runs, so
     `assert b"account_number" in b"".join(response.streaming_content)` is true
     over an empty file.

So the one check that would catch a NEW streamed route does not run on any
machine that would catch it before merge. This gate needs no database.

WHAT IT CHECKS
--------------
Every `StreamingHttpResponse(...)` constructed under `06-backend/apps/` must
take, as its FIRST positional argument, a call to `stream_within_tenant_context`
(bare or attribute-qualified — `core_tenancy.stream_within_tenant_context(...)`
counts). AST, not a regex, so a mention inside a docstring or a comment is not
mistaken for a call site.

WHAT IT DELIBERATELY DOES NOT CHECK, AND WHY
--------------------------------------------
* **`FileResponse` is out of scope.** `apps/tenancy/api.py::export_file` streams
  an already-open FILE HANDLE and makes its only query (`selectors.job_artifact`)
  inside the view, so it has nothing to re-enter. Requiring the wrapper there
  would mean re-assigning `streaming_content` on a class that overrides
  `_set_streaming_content` for file-specific behaviour — a change with a real
  failure mode to prevent a defect it cannot have.
* **`HttpResponse` is out of scope.** Django's `content` setter joins an
  iterable at construction, inside the view. The nine call sites in this
  codebase are safe by construction and stay unencumbered.
* **It cannot see a queryset that is lazy for some OTHER reason.** This is a
  shape check on one class, not a proof about laziness in general. It is the
  cheapest thing that catches the mechanism that actually bit twice.

PROVING IT RED (hard-won law 7 — do this before trusting a green)
------------------------------------------------------------------
Remove the wrapper from either call site and re-run:

    sed -i 's/stream_within_tenant_context(tenant_id, body)/body/' \
      06-backend/apps/metering/api.py
    python3 10-scripts/gates/g58_streamed_tenant_context.py

It must name the file, the line and the fix. Verified 2026-08-31:

    G58 FAIL — 2 streamed response(s) built without a tenant context:
      06-backend/apps/metering/api.py:1168 StreamingHttpResponse(body, …)
      06-backend/apps/metering/api.py:1783 StreamingHttpResponse(body, …)
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend"
APPS = BACKEND / "apps"

#: The response class whose body is consumed after every middleware has unwound.
STREAMING = "StreamingHttpResponse"

#: The one lawful way to build one in this codebase. `core.tenancy` owns the GUC
#: lifecycle, so the wrapper lives beside `tenant_context` rather than in a
#: helper each module would grow its own copy of.
WRAPPER = "stream_within_tenant_context"

CORRECT = (
    "A StreamingHttpResponse's body is iterated by WSGI AFTER "
    "TenantContextMiddleware has cleared app.tenant_id, so any query it makes runs "
    "with no tenant marker and RLS denies it silently — 200, a header row, and no "
    "rows (DEF-2734). Build it through the wrapper:\n"
    "    from core.tenancy import require_tenant, stream_within_tenant_context\n"
    "    tenant_id = require_tenant(request)\n"
    "    filename, body = <module>.results_csv(...)\n"
    f"    StreamingHttpResponse({WRAPPER}(tenant_id, body), content_type=...)\n"
    "Pass the REQUEST's tenant (require_tenant's return), never a record's "
    "tenant_id — see core/tenancy.py::stream_within_tenant_context for why, and "
    "for why materialising the rows instead was rejected."
)


def _is_wrapper_call(node: ast.expr) -> bool:
    """True when `node` is a call to the wrapper, plain or attribute-qualified.

    `stream_within_tenant_context(...)` and
    `core_tenancy.stream_within_tenant_context(...)` are both lawful; this repo
    imports `core.tenancy` under three different names across modules and a gate
    that insisted on one of them would be a style rule wearing a safety hat.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == WRAPPER
    if isinstance(func, ast.Attribute):
        return func.attr == WRAPPER
    return False


def _calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if called == name:
            out.append(node)
    return out


def findings() -> tuple[list[str], int, int]:
    """(problems, how many streamed responses were seen, how many files)."""
    problems: list[str] = []
    seen = 0
    files = 0
    if not APPS.is_dir():
        return [f"{APPS} is missing — the gate cannot scan what is not there"], 0, 0
    for path in sorted(APPS.rglob("*.py")):
        if "/migrations/" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if STREAMING not in text:
            continue
        files += 1
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:  # pragma: no cover — a broken file is its own alarm
            problems.append(f"{path.relative_to(ROOT)}: cannot parse ({exc})")
            continue
        for call in _calls_named(tree, STREAMING):
            seen += 1
            first = call.args[0] if call.args else None
            if first is None:
                problems.append(
                    f"{path.relative_to(ROOT)}:{call.lineno} {STREAMING}() with no body "
                    "argument — the gate cannot tell what it streams"
                )
            elif not _is_wrapper_call(first):
                shown = ast.unparse(first)[:40]
                problems.append(
                    f"{path.relative_to(ROOT)}:{call.lineno} {STREAMING}({shown}, …) — "
                    f"the body is not wrapped in {WRAPPER}()"
                )
    return problems, seen, files


def run() -> tuple[str, str]:
    """The gate proper, in the shape `run_gates.py` calls.

    ⚠ Both halves are here on purpose. `DEF-672` (sixteen gates with `run()` and
    no `main()`, silently exiting 0 when run directly) and `DEF-674` (`g41` with
    `main()` and no `run()`, crashing inside the suite for weeks) are one
    convention with two halves, and a module can satisfy either alone and be
    dead in the other context. `main()` below delegates to this function so the
    two cannot disagree about what this gate says.
    """
    problems, seen, files = findings()
    if problems:
        return (
            "FAIL",
            f"{len(problems)} streamed response(s) built without a tenant context: "
            + " · ".join(problems)
            + f" {CORRECT}",
        )
    if seen == 0:
        # Not a pass to be proud of, and it says so: a gate that finds nothing to
        # check is indistinguishable from a gate pointed at the wrong tree.
        return (
            "PASS",
            f"no {STREAMING} call sites under 06-backend/apps — nothing to check. If "
            "that is a surprise, this gate is pointed at the wrong tree.",
        )
    return (
        "PASS",
        f"{seen} {STREAMING} call site(s) across {files} file(s), every one built "
        f"through {WRAPPER}() so its late queries still have the request's tenant "
        "(DEF-2734). FileResponse and HttpResponse are out of scope by design — see "
        "the module docstring.",
    )


def main() -> int:
    status, note = run()
    print(f"G58 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

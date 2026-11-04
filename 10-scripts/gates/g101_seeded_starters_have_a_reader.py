#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-WRK-019 TC-6 (EP-WRK-03) — *"Remove the Fire starters from the
#          list endpoint's queryset → the gate FAILS naming the two unread
#          rows — proved RED first, then restored."*
# Rules:   BR-WRK-014 (**every seeded starter row has a reader**) · `CR-070`
#          §12 gate 3 · CLAUDE.md hard-won law 2 (BUILT IS NOT WIRED) · law 7
#          (prove a guard RED before trusting it green, and prove it in the
#          harness that will run it — `DEF-GOV-3733`) · DEF-182 (a check whose
#          output cannot distinguish pass from fail is worse than no check)
# Tests:   `selftest()` below — `run()` refuses to report until it has passed ·
#          06-backend/tests/test_us_wrk_016_019_builder.py
# ───────────────────────────────────────────────────────
"""G101 — EVERY SEEDED STARTER TEMPLATE HAS A READER.

WHY THIS GATE EXISTS, AND IT IS A DEFECT THIS PRODUCT ALREADY PAID FOR
----------------------------------------------------------------------
`apps/metering/sample_data.py` has planted **24 work-order template starters**
in every tenant since 2026-08-25 — the jobs each service needs, gas gated on
the light-up — and for eleven days **nothing in the product read a single one
of them**. The screen at `/work/templates` was four sentences saying *not built
yet*. The rows were correct, the seeder was correct, and a utility's first day
showed it none of them.

That is `G74` one level down. `G74` asks whether a TABLE has a reader; this
asks whether the ROWS A SEEDER PLANTS have one — which `G74` cannot see,
because `work_order_templates` has been read by `create_work_order` since long
before any of those rows existed.

WHAT IT ASSERTS, IN THREE CLAUSES
---------------------------------
  1. **THE SEEDER'S SERVICES ARE SERVED.** Every service code that
     `W6_TEMPLATE_STARTERS` plants a row for must be reachable through the list
     endpoint's queryset. The queryset is `metering_seam.templates_queryset()`
     and it filters by TENANT and nothing else, so a narrowing filter added
     there — `service__code__in=(...)`, `is_sample=False`, `sequence__lte=N` —
     is what this clause catches. **That is TC-6's sabotage exactly**: hiding
     the Fire starters from the list means adding such a filter, and this goes
     red naming the queryset.
  2. **A SCREEN RENDERS THE LIST.** `features/work/TemplatesPage.tsx` must call
     the list wrapper. A served row nobody draws is the same defect one layer
     up, and it is the one the four blank sentences were.
  3. **THE SEEDER WRITES THROUGH THE SERVICE.** `sample_data.py` must not
     write `WorkOrderTemplate.objects.create` / `get_or_create` directly. A row
     planted around the write service is a row that skips `publish`, so it has
     no version and no `ST-` number — and `BR-WRK-016` proposes only PUBLISHED
     templates, which means an unpublished starter is invisible to New Connect
     step 6 however well the list serves it. `US-WRK-015` TC-4 asks for this
     grep by name.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* **It does not run Django and does not count rows.** No gate in this directory
  does; the row-level proof is `test_us_wrk_016_019_builder.py`, which seeds a
  tenant and asserts 24 rows with 8 gates through the real endpoint. This gate
  is the STRUCTURAL half — it catches the filter, the deleted call and the
  by-passed service, which are the three ways the rows go dark between test
  runs.
* **It does not check the 24 rows are the RIGHT 24.** `test_w6_w7_seed.py`
  owns that, including the one row a copying lane gets wrong (gas gates on the
  light-up, not the meter set).

PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (law 7, both halves). Each clause
was sabotaged through `selftest()`, which is the same function `run()` calls and
the same one `run_gates` reaches through `.run`:

    G101 seeded-starters-have-a-reader FAIL  self-test failed, so nothing below
    is trustworthy: a narrowed queryset was NOT reported — clause 1 is blind
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend"
FRONTEND = ROOT / "07-frontend"

SEEDER = BACKEND / "apps/metering/sample_data.py"
SEAM = BACKEND / "apps/work/seams/metering_seam.py"
SCREEN = FRONTEND / "src/features/work/TemplatesPage.tsx"

#: The queryset the list endpoint pages. It must be scoped by TENANT and by
#: nothing else — a second filter is a row a tenant owns and cannot see.
QUERYSET = "templates_queryset"

#: What clause 3 refuses in the seeder. `objects.create` and friends on the
#: template model mean the row skipped `publish`, so it has no version, no
#: number, and `BR-WRK-016` will never propose it.
DIRECT_WRITE = re.compile(
    r"WorkOrderTemplate\.objects\.(create|get_or_create|update_or_create|bulk_create)\b"
)


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _queryset_body(seam_text: str) -> str:
    """The body of `templates_queryset()` — from its `def` to the next one."""
    start = seam_text.find(f"def {QUERYSET}(")
    if start < 0:
        return ""
    rest = seam_text[start:]
    end = rest.find("\ndef ", 1)
    return rest if end < 0 else rest[:end]


def _call_args(text: str, method: str) -> list[str]:
    """Every `.<method>(...)` argument string in `text`, matched by BALANCED
    parentheses.

    ⚠ **A `[^)]*` REGEX IS WRONG HERE AND THE SELFTEST PROVED IT.** The real
    queryset reads `.filter(tenant_id=_tenant_id())`, so a lazy scan stops at
    the `)` that closes `_tenant_id()` — which makes
    `.filter(tenant_id=_tenant_id(), service__code__in=(...))` look like it has
    exactly one argument, and the gate reports nothing about the very narrowing
    it exists to catch. Counting depth is the only form that reads a call whose
    arguments are themselves calls.
    """
    out: list[str] = []
    needle = f".{method}("
    index = text.find(needle)
    while index >= 0:
        depth = 0
        start = index + len(needle)
        cursor = start - 1
        while cursor < len(text):
            char = text[cursor]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[start:cursor])
                    break
            cursor += 1
        index = text.find(needle, cursor + 1)
    return out


def _top_level_split(args: str) -> list[str]:
    """`args` split on commas that are NOT inside a nested call — so
    `tenant_id=_tenant_id(), service__code__in=('electric',)` is two arguments
    and not four."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in args:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current)
    return parts


def _findings(
    seam_text: str, screen_text: str, seeder_text: str
) -> list[str]:
    """The three clauses, over text a caller supplies — so the selftest can
    sabotage each one without writing to the tree."""
    out: list[str] = []

    body = _queryset_body(seam_text)
    if body == "":
        out.append(
            f"clause 1: `{QUERYSET}()` is gone from {SEAM.name} — the list endpoint's "
            "queryset is where every seeded starter reaches a screen"
        )
    else:
        # `.filter(...)` inside the queryset. `tenant_id=` is the ONE lawful
        # key (hard rule 1); anything else narrows what a tenant can see of its
        # own seeded rows, which is this gate's whole subject.
        for call in _call_args(body, "filter"):
            keys = [
                part.split("=")[0].strip()
                for part in _top_level_split(call)
                if "=" in part.split("(")[0]
            ]
            extra = [key for key in keys if key not in ("tenant_id",)]
            if extra:
                out.append(
                    f"clause 1: `{QUERYSET}()` narrows the list by {', '.join(extra)} — a "
                    "seeded starter this tenant owns would be planted and never served "
                    "(BR-WRK-014). The tenant scope is the only lawful filter here"
                )
        # ⚠ **AND `.exclude(...)` IS THE FORM `US-WRK-019` TC-6 ACTUALLY
        # NAMES** — *"remove the Fire starters from the list endpoint's
        # queryset"*. A first draft of this gate read `.filter(` only and was
        # BLIND to exactly the sabotage the story asks it to catch; the
        # selftest below found that, which is what a selftest is for. There is
        # no lawful exclusion here at all: every row of the tenant's own
        # templates belongs on the list.
        for call in _call_args(body, "exclude"):
            out.append(
                f"clause 1: `{QUERYSET}()` EXCLUDES rows ({call.strip()}) — that is the "
                "sabotage `US-WRK-019` TC-6 names, and it plants seeded starters no screen "
                "can ever show (BR-WRK-014)"
            )

    if "listTemplates" not in screen_text:
        out.append(
            f"clause 2: {SCREEN.name} does not call `listTemplates` — the rows are served "
            "and nothing draws them, which is the four-blank-sentences defect this gate "
            "was written for"
        )

    hit = DIRECT_WRITE.search(seeder_text)
    if hit is not None:
        out.append(
            f"clause 3: the seeder writes `{hit.group(0)}` — a starter planted around "
            "`templates_svc` skips `publish`, so it has no version and no ST- number, and "
            "`BR-WRK-016` proposes only PUBLISHED templates (US-WRK-015 TC-4)"
        )
    return out


#: A minimal HEALTHY tree, in text, for the selftest to sabotage.
#:
#: ⚠ **SYNTHETIC, AND THE FIRST DRAFT WAS NOT — WHICH BROKE THE GATE'S OWN
#: MESSAGE.** That draft asserted *"the real tree reports no finding"* as its
#: first selftest clause and then sabotaged the real files. It bit correctly,
#: but a REAL finding then came back as *"self-test failed … the healthy tree
#: reports a finding"* instead of the sentence naming the excluded service —
#: so the gate would have told the next lane its selftest was broken when what
#: was actually broken was the queryset. `DEF-182`'s rule, one turn deeper: a
#: check whose output cannot tell its own failure from the failure it is
#: watching for is worse than no check.
_HEALTHY_SEAM = """
def templates_queryset() -> Any:
    from apps.metering import connections as w6

    return (
        w6.WorkOrderTemplate.objects.filter(tenant_id=_tenant_id())
        .select_related("service", "type", "skill", "safety_kit")
        .order_by("service__code", "sequence", "name", "id")
    )


def next_thing() -> None:
    pass
"""
_HEALTHY_SCREEN = "const rows = await listTemplates(query, client);"
_HEALTHY_SEEDER = "templates_svc.create_draft(actor, payload)"


def selftest() -> tuple[bool, str]:
    """Law 7, both ways, on SYNTHETIC text: every sabotage must be seen and the
    healthy shape must be silent — without reading the real tree, so a genuine
    finding is reported as a finding rather than as a broken selftest."""
    if _findings(_HEALTHY_SEAM, _HEALTHY_SCREEN, _HEALTHY_SEEDER):
        return False, "the healthy shape reports a finding — the check fires on correct work"

    # clause 1a — `US-WRK-019` TC-6's own sabotage: hide the Fire starters.
    excluded = _HEALTHY_SEAM.replace(
        ".select_related(", '.exclude(service__code="fire")\n        .select_related(', 1
    )
    if not _findings(excluded, _HEALTHY_SCREEN, _HEALTHY_SEEDER):
        return False, "an EXCLUDED service was NOT reported — clause 1 is blind to TC-6"

    # clause 1b — the same harm written as a narrowing filter instead. The
    # nested `_tenant_id()` call is why the argument scan counts parentheses.
    narrowed = _HEALTHY_SEAM.replace(
        "filter(tenant_id=_tenant_id())",
        "filter(tenant_id=_tenant_id(), service__code__in=('electric',))",
        1,
    )
    if not _findings(narrowed, _HEALTHY_SCREEN, _HEALTHY_SEEDER):
        return False, "a narrowed queryset was NOT reported — clause 1 is blind"

    # clause 2 — the screen stops reading the list.
    if not _findings(_HEALTHY_SEAM, "const rows = [];", _HEALTHY_SEEDER):
        return False, "a screen that does not read the list was NOT reported — clause 2 is blind"

    # clause 3 — the seeder goes back around the write service.
    if not _findings(
        _HEALTHY_SEAM,
        _HEALTHY_SCREEN,
        "WorkOrderTemplate.objects.get_or_create(tenant_id=tenant_id)",
    ):
        return False, "a direct model write in the seeder was NOT reported — clause 3 is blind"

    return True, "4/4 sabotages bite, and none fires on the healthy shape"


def run() -> tuple[str, str]:
    ok, how = selftest()
    if not ok:
        return "FAIL", f"self-test failed, so nothing below is trustworthy: {how}"
    findings = _findings(_read(SEAM), _read(SCREEN), _read(SEEDER))
    detail = (
        "BR-WRK-014: the 24 seeded starters reach a screen — the list queryset is scoped by "
        "tenant alone, `TemplatesPage.tsx` reads it, and the seeder writes through "
        f"`templates_svc`. self-test: {how}"
    )
    if findings:
        return "FAIL", " | ".join(findings) + f" | {detail}"
    return "PASS", detail


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}  {detail}")
    sys.exit(0 if status == "PASS" else 1)

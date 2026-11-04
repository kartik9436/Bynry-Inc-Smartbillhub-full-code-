#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2377 (2026-09-02) — the Product Owner, reading the deployed audit
#          log: "business rules are displayed in". One summary row read, in full:
#          "the named sample_data_runs rows this run stored (BR-TEN-060)" — our
#          rule id AND a database table name, in a sentence written for a clerk.
#          Forty-eight payload values carried an internal reference. EIGHTEEN
#          across ELEVEN files were rewritten (that sentence among them); the
#          rest are machine fields, and the population of those stands at 51
#          today (33 `job`, 18 `br_ref`) because four keys were RENAMED onto
#          the `br_ref` convention rather than emptied. The S61 presenter
#          drops all 51 instead of showing them to a clerk.
# Rules:   B14 rule 32 — no rule id or internal code in clerk-facing copy,
#          RATIFIED 2026-08-31 ("too much content - desctiption is too much for
#          clark to read") · DEF-332 (our internal ids do not belong on a user's
#          screen) · BR-AUD-003 (the payload standard) · BR-AUD-009 (the S61
#          Summary column) · CLAUDE.md hard-won law 7 (prove a guard RED first)
# Impacts: G28 (the same rule over catalogue values, five named served-prose
#          modules and the raise sites) · 07-frontend/src/features/audit/
#          auditEvents.tsx (the presenter that RENDERS these values)
# ───────────────────────────────────────────────────────
"""G71 — AN AUDIT PAYLOAD IS CLERK-FACING COPY, SO NO INTERNAL REFERENCE GOES IN IT.

WHY THIS EXISTS AND WHY G28 CANNOT SEE IT
-----------------------------------------
G28 asks the same question this does — "is this value something a utility should
be reading?" — over three corpora, and an audit payload is in none of them:

* **Part 1** reads the eleven i18n catalogues. A payload value is written by the
  server at run time and is in no catalogue.
* **Part 2** reads an EXPLICIT list of five backend modules whose strings are
  rendered verbatim (`notifications/catalogs.py`, `seed_templates.py`,
  `settings_api.py`, `rules_api.py`, `billing/templates_service.py`). Its own
  docstring records why the list is explicit and what that costs: *"an explicit
  list only checks what somebody remembered to name"*. **No audit writer is on
  it**, and the module that wrote the row the PO photographed —
  `tenancy/sample_data.py` — is not on it either.
* **Part 3** reads `raise` sites, and since DEF-2468 it EXCLUDES `sample_data.py`
  by name, along with `management/commands/` and `migrations/`. That exclusion is
  right for refusal prose, which since 2026-08-19 reaches the audit row and the
  log and no screen — and it is exactly wrong here, because **the audit row IS
  the screen** on S61.

And the frontend cannot close it either, deliberately. `auditEvents.tsx` drops a
value that IS a whole rule id (`isInternalReference`), and its own comment says
why it will not drop a SENTENCE that merely mentions one: *"a sentence that
happens to mention one is a message whose meaning would be destroyed by dropping
it. Hiding real recorded data is its own defect on an audit trail."* That
reasoning is sound and it is why the fix has to be at the WRITER.

WHAT IS CHECKED
---------------
Every `before=` / `after=` payload handed to the two audit writers
(`core.audit.write_row` and `core.audit.money_action`), read with `ast`, one
dict entry at a time. A value fails when the string it is built from carries:

1. **a register id** — `BR-TEN-060`, `OQ-133`, `DEF-210`, `US-BIL-002` …
2. **a declared database table name**, read from the repo's own
   `db_table = "…"` declarations in `apps/*/models.py` (114 of the 142 today,
   after the underscore filter below) —
   `sample_data_runs`, `bill_run_decisions`, `outbound_messages` …
3. **a dotted lower_snake path** — `invoices.corrects_invoice_id`,
   `apps/notifications/bulk_summary` — a column or a module, either way ours.

⚠ **CLAUSE 2 ONLY LOOKS AT TABLE NAMES THAT CONTAIN AN UNDERSCORE, AND THAT IS
DELIBERATE.** `accounts`, `addresses`, `areas`, `adjustments` and `units` are all
declared tables AND ordinary English words a clerk-facing sentence is entitled to
use. A gate that flagged "the arrears this plan spreads across three accounts"
would be switched off within the day — the exact false-positive failure G26's and
G27's own docstrings record. A single-word table name therefore passes here, and
saying so is the point (hard-won law 1).

WHY IT IS A CEILING OF ZERO
---------------------------
All 18 were rewritten in the commit that added this gate, so the honest count is
**0**. `MACHINE_KEYS` below is the only exemption; it holds two
names and each is backed by a frontend test rather than by this comment.

⚠ **WHAT IT CANNOT SEE, SAID PLAINLY.** It reads SOURCE, so a sentence composed
at run time from a variable passes. It reads the writers by NAME, so a module that
names its wrapper something else, or that builds the payload dict away from the
call, passes. It reads the `after=` / `before=` KEYWORDS, so a wrapper taking
`**after: Any` and called with loose keywords passes too. And it says nothing about `entity_type`, `action` or the masked values
BR-AUD-006 stores verbatim. It closes one mechanical shape that produced 18 live
values, one of which a Product Owner read on a screen.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "06-backend" / "apps"

#: The audit writers. `money_action` delegates to `write_row`, so a payload
#: reaching either one reaches the store and therefore S61.
#:
#: ⚠ `_audit` IS IN THE LIST, AND IT WAS ADDED BECAUSE THE FIRST DRAFT MISSED A
#: LIVE BREACH. Eighteen modules wrap the two writers in a local `_audit(actor,
#: action, entity, *, after=…)` helper, and reading only the two real writers by
#: name walked straight past `apps/tenancy/services.py`, whose payload carried
#: *"PO 2026-08-27 (OQ-490) — Undeposited funds is the answer for every tender"*
#: into a value S61 renders. A gate that names its own blind spot in a docstring
#: and then leaves a live instance inside it is hard-won law 1.
AUDIT_WRITERS = ("write_row", "money_action", "_audit")

#: The payload keywords BR-AUD-003 defines. Nothing else is read.
PAYLOAD_KWARGS = ("before", "after")

#: ⚠ ONE EXEMPTION, AND IT IS THE G28 PRECEDENT RATHER THAN A CONVENIENCE.
#: `br_ref` is a MACHINE field that is SUPPOSED to hold a rule id — G28's own
#: docstring rules exactly this for `billing/templates_service.py`: *"A gate that
#: demanded `br_ref` contain no rule id would be asking the field to stop being
#: itself."* The remedy there was to stop RENDERING it (it travels on
#: `data-br-ref` since DEF-322), and the same remedy is applied here: the S61
#: presenter now drops `br_ref` with the other identifier fields, asserted by
#: `auditEvents.test.tsx` ("a br_ref never reaches a rendered field"). The
#: exemption is therefore backed by a test, not by this comment.
#: `job` is the second, and it is BR-AUD-003 doing what it was told: `write_row`'s
#: own docstring says *"None = system job; name the job in the payload"*, so
#: `"job": "payments.refund"` is the rule being obeyed. Thirty of the forty-two
#: findings on the day this gate was written were that one key. The same remedy
#: applies — the S61 presenter drops it, the actor column already says "System
#: job" in words, and the exact job name stays in the row for support.
MACHINE_KEYS: dict[str, str] = {
    "br_ref": "machine field, dropped by the S61 presenter (auditEvents.isIdentifierField)",
    "job": "BR-AUD-003 requires the job be named; dropped by the S61 presenter",
}

# ── The patterns ───────────────────────────────────────────────────────────
#: The module-scoped and flat register grammars. Five digits since the PO's
#: 2026-08-31 ruling, and the `(?!\d)` lookahead is load-bearing (DEF-2804):
#: without it `OQ-123456` reads as `OQ-12345`.
REGISTER_ID = re.compile(
    r"\b(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,5}(?!\d)\b" r"|\b(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,5}(?!\d)\b"
)
#: `invoices.corrects_invoice_id`, `sample_data_runs.blocks`,
#: `apps/notifications/bulk_summary`. Both halves lower_snake so an ordinary
#: sentence ending in a full stop cannot match.
DOTTED_INTERNAL = re.compile(r"\b[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\b|\bapps/[a-z_]+/")


def declared_tables() -> set[str]:
    """Every `db_table = "…"` in `apps/*/models.py` that contains an underscore.

    Read from the repo rather than listed here, so a table added tomorrow is
    covered without anybody remembering to come back. The underscore filter is
    the false-positive concession explained in the module docstring.
    """
    found: set[str] = set()
    pattern = re.compile(r'db_table\s*=\s*["\']([a-z][a-z0-9_]*)["\']')
    for path in sorted(BACKEND.glob("*/models.py")):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            if "_" in name:
                found.add(name)
    return found


def _reasons(text: str, tables: set[str]) -> list[str]:
    out: list[str] = []
    if REGISTER_ID.search(text):
        out.append("register id")
    hit = sorted(name for name in tables if re.search(rf"\b{re.escape(name)}\b", text))
    if hit:
        out.append(f"database table ({hit[0]})")
    if DOTTED_INTERNAL.search(text):
        out.append("dotted column or module path")
    return out


def _strings(node: ast.AST) -> list[str]:
    """Every string constant under `node`, EACH ON ITS OWN and also joined.

    ⚠ JOINED, because implicit concatenation splits a sentence across literals
    and an id can straddle two of them — the same trap G28 records for its own
    part 2.

    ⚠ **AND EACH ONE SEPARATELY, BECAUSE JOINING ALONE LET A LIVE BREACH
    THROUGH.** `"br": "BR-MET-133" if read.lifecycle == "billed" else None` puts
    two constants under one value node, and `"".join` makes them
    `BR-MET-133billed` — where the pattern's closing `\b` no longer matches,
    because `3` is followed by a word character. The gate reported that site as
    clean while it was writing a rule id into a rendered payload; the frontend
    test caught it instead, which is a check finding what a gate was pointed at
    and missed (DEF-182's shape). Concatenating unrelated fragments is how a
    joined-only sweep manufactures false NEGATIVES, so both forms are tested.
    """
    parts = [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    return parts + ["".join(parts)] if len(parts) > 1 else parts


def _is_audit_writer(call: ast.Call) -> bool:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return name in AUDIT_WRITERS


def findings() -> list[tuple[str, int, str, str, str]]:
    """(path, line, key, reasons, value) for every offending payload entry."""
    tables = declared_tables()
    out: list[tuple[str, int, str, str, str]] = []
    for path in sorted(BACKEND.rglob("*.py")):
        parts = path.parts
        if "migrations" in parts or "tests" in parts or path.name.startswith("test_"):
            continue
        if path.name == "tests.py":
            continue
        rel = str(path.relative_to(REPO_ROOT))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            out.append((rel, 0, "-", "unparseable", "this file could not be read"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_audit_writer(node):
                continue
            for keyword in node.keywords:
                if keyword.arg not in PAYLOAD_KWARGS:
                    continue
                for entry in ast.walk(keyword.value):
                    if not isinstance(entry, ast.Dict):
                        continue
                    for key, value in zip(entry.keys, entry.values):
                        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                            continue
                        if key.value in MACHINE_KEYS:
                            continue
                        for text in _strings(value):
                            if not text:
                                continue
                            reasons = _reasons(text, tables)
                            if reasons:
                                out.append(
                                    (rel, key.lineno, key.value, "/".join(reasons), text[:120])
                                )
                                break
    return out


def selftest() -> bool:
    """The gate must BITE on DEF-2377's own shapes and must NOT bite on the
    ordinary sentences an audit payload is supposed to carry.

    Both halves are asserted because both have already been wrong somewhere in
    this directory: a gate that cannot fail is worse than none (DEF-182), and a
    gate that fires on correct work gets switched off within the day.
    """
    tables = {"sample_data_runs", "bill_run_decisions", "outbound_messages"}
    breaches = (
        "the named sample_data_runs rows this run stored (BR-TEN-060)",
        "invoices.corrects_invoice_id (PO 2026-08-12, OQ-120)",
        "no money moved (BR-PAY-1073)",
        "the class gained a catalog on 2026-08-17 (DEF-210)",
        "apps/notifications/bulk_summary is the one message a bulk action sends",
    )
    innocent = (
        "the arrears this plan spreads, while it stays current",
        "the posting date, never the clearing date",
        "customer e-signature alone",
        # A single-word table name is an ordinary English word and passes — the
        # concession the docstring names, asserted so it cannot drift silently.
        "the earliest unmet instalment across all accounts",
        # A date is not a register id (the DEF-2804 lookahead, from the far side).
        "recorded on 2026-09-02",
    )
    for text in breaches:
        if not _reasons(text, tables):
            return False
    # ⚠ THE MISSED SHAPE, KEPT AS A CASE. A ternary puts two constants under one
    # value node; joining them makes `BR-MET-133billed`, where the pattern's
    # closing word boundary fails. Testing each part separately is what finds it.
    ternary = ["BR-MET-133", "billed", "BR-MET-133billed"]
    if not any(_reasons(part, tables) for part in ternary):
        return False
    if _reasons("BR-MET-133billed", tables):
        return False  # the joined form alone must NOT be what saves this check
    for text in innocent:
        if _reasons(text, tables):
            return False
    return True


def run() -> tuple[str, str]:
    if not BACKEND.is_dir():
        return "SKIP", f"{BACKEND} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not bite: it must find DEF-2377's five shapes "
            "and must NOT find them in the five ordinary sentences beside them. A check "
            "that cannot distinguish pass from fail is worse than no check, because it is "
            "trusted (DEF-182)."
        )
    tables = declared_tables()
    hits = findings()
    if hits:
        shown = "; ".join(f"{rel}:{line} {key} — {why}" for rel, line, key, why, _ in hits[:5])
        return "FAIL", (
            f"{len(hits)} audit payload value(s) carry an internal reference into a sentence "
            f"a clerk reads on the audit log. B14 rule 32 forbids a rule id or internal code "
            f"in clerk-facing copy, and an audit payload IS clerk-facing: S61 renders it as "
            f"words. Keep the honesty and drop the provenance — say what happened in plain "
            f"English and put the rule id in the code comment beside the string, which is "
            f"where support and engineers can still reach it (G28's own remedy). {shown}"
        )
    return "PASS", (
        f"0 audit payload value(s) carry an internal reference (ceiling 0 — DEF-2377's "
        f"18 values across 11 files all rewritten); {len(tables)} declared table name(s) "
        f"read from apps/*/models.py; 2 machine key(s) exempt (br_ref and job, both "
        f"dropped by the S61 presenter). "
        f"Self-test: five breach shapes bite and five ordinary sentences do not. "
        f"⚠ SOURCE ONLY — a sentence composed at run time, or a payload built away from "
        f"the writer call, still passes here."
    )


def main() -> int:
    if "--report" in sys.argv:
        for rel, line, key, why, value in findings():
            print(f"{rel}:{line}  {key}  [{why}]  {value}")
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

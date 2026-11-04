#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) TC-3 — the connection table holds no secret
#           column. CR-069 §13 gate 2, the SCHEMA half ("a credential never
#           reaches a log, an audit row or an error body" — it cannot reach any
#           of them from a table that cannot hold one).
# Rules:    BR-INT-003 (credentials never rendered back, never logged, never in
#           audit payloads — masked refs only) · BR-INT-014 (audit is a consumer
#           of the CONNECTION table, never of the credential table) · CLAUDE.md
#           hard-won law 7 (proven RED first — see the docstring)
# Tests:    selftest() below · 06-backend/tests/test_us_int_014_tables.py TC-3
#           (the same rule, read off the ORM's model instead of the source)
# Impacts:  06-backend/apps/integrations/models.py (IntegrationConnection)
# ───────────────────────────────────────────────────────
"""G75 — `integration_connection` may never grow a column that could hold a secret.

WHY THIS GATE EXISTS
--------------------
The integrations substrate keeps two tables where one would have been the
instinct: `integration_connection` (rarely changes, read everywhere) and
`integration_credential` (the password or key, encrypted, versioned). The
design's own words for why: *"Audit is a consumer of the connection table,
never of the credential table."* Every connection lifecycle event writes an
audit row with the connection's non-secret columns in its payload (BR-INT-014);
the grid read serves the row to a screen; a support engineer `SELECT *`s it on
a box. **All three are safe ONLY as long as no column of that table can hold a
secret** — and nothing structural stops the next lane from adding
`api_key_enc = EncryptedTextField(...)` to the connection model "because the
modal has one field". The migration would apply, every test would pass, and
the next audit row would carry a ciphertext that decrypts under the app key.

So this gate reads the model source and refuses two things on
`IntegrationConnection`:

  1. **any `EncryptedTextField`** — encryption on that table is the tell that a
     secret is being stored where the audit trail reads;
  2. **any field whose NAME matches `secret|token|password|payload`** — the four
     words the story names (US-INT-014 TC-3); a plain `TextField` called
     `api_token` is the same leak without the encryption.

It reads SOURCE rather than importing Django (the gate suite is stdlib-only),
walking the class body of `IntegrationConnection` with `ast`, so a renamed
import or an aliased field type cannot slip past a regex.

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With `api_key_enc = EncryptedTextField(crypto_context="x")` added to the
connection model the gate reported
    FAIL: 06-backend/apps/integrations/models.py: IntegrationConnection.api_key_enc
    is an EncryptedTextField — a secret on the table the audit trail reads
and with the line removed it went green. `selftest()` replays both halves on
an in-memory model body, and `run()` refuses to report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
MODELS = REPO / "06-backend" / "apps" / "integrations" / "models.py"
GUARDED_CLASS = "IntegrationConnection"
#: US-INT-014 TC-3 — the four words, matched anywhere in a field name.
SECRET_NAME = re.compile(r"secret|token|password|payload", re.IGNORECASE)
ENCRYPTED_FIELD = "EncryptedTextField"


def _field_type_name(value: ast.AST) -> str | None:
    """`EncryptedTextField(...)` or `models.TextField(...)` → the callee's last name."""
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def findings_in(source: str, *, where: str = "models.py") -> list[str]:
    """Every column of the guarded class that could hold a secret, as sentences."""
    tree = ast.parse(source)
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != GUARDED_CLASS:
            continue
        for statement in node.body:
            targets: list[str] = []
            value: ast.AST | None = None
            if isinstance(statement, ast.Assign):
                targets = [t.id for t in statement.targets if isinstance(t, ast.Name)]
                value = statement.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                targets = [statement.target.id]
                value = statement.value
            for name in targets:
                type_name = _field_type_name(value) if value is not None else None
                if type_name == ENCRYPTED_FIELD:
                    problems.append(
                        f"{where}: {GUARDED_CLASS}.{name} is an {ENCRYPTED_FIELD} — a secret on "
                        "the table the audit trail reads (BR-INT-014, US-INT-014 TC-3)"
                    )
                if SECRET_NAME.search(name) and type_name is not None:
                    problems.append(
                        f"{where}: {GUARDED_CLASS}.{name} — a column named like a secret on the "
                        "connection table; it belongs in integration_credential (BR-INT-003)"
                    )
        return problems
    return [f"{where}: no class {GUARDED_CLASS} found — the gate has nothing to guard"]


CLEAN_BODY = """
class IntegrationConnection(models.Model):
    id = dbfields.uuid7_pk()
    provider_key = models.TextField()
    config = models.JSONField(default=dict)
    masked_note = "not a field"
"""
RED_ENCRYPTED = CLEAN_BODY + "    api_key_enc = EncryptedTextField(crypto_context='x')\n"
RED_NAMED = CLEAN_BODY + "    api_token = models.TextField()\n"


def selftest() -> bool:
    """Law 7: the clean body passes, and each of the two defect shapes is named."""
    if findings_in(CLEAN_BODY, where="selftest"):
        return False
    encrypted = findings_in(RED_ENCRYPTED, where="selftest")
    named = findings_in(RED_NAMED, where="selftest")
    return (
        len(encrypted) >= 1
        and "api_key_enc" in encrypted[0]
        and len(named) == 1
        and "api_token" in named[0]
    )


def run() -> tuple[str, str]:
    if not MODELS.is_file():
        return "SKIP", f"{MODELS.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a clean connection "
            "table from one carrying a secret, so its verdict is worthless (DEF-182)"
        )
    try:
        problems = findings_in(MODELS.read_text(encoding="utf-8"), where=str(MODELS.relative_to(REPO)))
    except SyntaxError as exc:  # a broken gate must block the merge
        return "FAIL", f"{MODELS.relative_to(REPO)} does not parse: {exc}"
    if problems:
        return "FAIL", " | ".join(problems)
    return "PASS", (
        f"{GUARDED_CLASS} declares no {ENCRYPTED_FIELD} and no column named secret/token/"
        "password/payload — the table the audit trail and the grid read is safe to SELECT *; "
        "self-test: both sabotages bite (an encrypted column, and one named api_token)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

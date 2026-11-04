#!/usr/bin/env python3
"""G32 — every `message_key` the backend RAISES resolves to a customer sentence.

WHY THIS GATE EXISTS (2026-08-19, DEF-322 · PO ruling `bec921e`)
----------------------------------------------------------------
The PO ruled that server `detail` text never reaches a customer screen: a
refusal's words come from the catalogue entry for its `message_key` and from
nothing else. Measured on the day of the ruling, that would have been a
DISASTER shipped as a fix:

    319  distinct message_keys the backend raised
    271  resolved to a customer sentence in en.json
     48  resolved to NOTHING AT ALL

For those 48, `params.detail` was the only text carrying any meaning. Suppress
it without writing the sentence and the refusal goes from ugly to SILENT — the
user clicks, nothing happens, and no explanation appears anywhere. The ruling
names the shape: *"that is worse than the defect being fixed, and it is the
exact shape of DEF-320: a path that looks handled and communicates nothing."*

So the ruling asked for this gate in as many words: **no `message_key` may be
raised that does not resolve, ratcheted so the number can only fall.**

WHY IT IS NOT G18 AND NOT G27
-----------------------------
* **G27** reads the FRONTEND — literal `t("…")` in `*.tsx`. A key the backend
  raises appears in no `t()` call anywhere, so G27 cannot see one.
* **G18** reads both directions and is the broader gate, but it carries an
  83-line parked register of real, unfixed findings (`i18n_known_gaps.txt`), by
  design: it is a defect backlog with a DEF row per line. A backlog cannot also
  be a ratchet — a new unresolved key is licensed the moment someone adds a
  line. This gate has NO register. The number is the number.

WHAT IT MEASURES
----------------
Every `message_key` in `06-backend/apps/**/*.py`, read with `ast` rather than
grep, because the grep form MISSES REAL FAILURES: three keys
(`errors.identity.password_too_short` and its two siblings) live inside
`field_errors` dict literals and were absent from every catalogue on the day
this gate was written. A regex over `message_key="…"` finds them; a regex over
`message_key=` does not. Both forms are read here:

  1. the keyword argument — `errors.BizError(..., message_key="a.b")`
  2. the dict-literal form — `{"field": ..., "message_key": "a.b"}`, which is
     how every inline field error is written, and which the screen renders
     under the input through `envelopeErrors`.

⚠ i18next PLURALS ARE HONOURED, and that is not a nicety — it is DEF-323. G18
matched the catalogue EXACTLY, so `dashboard.period.age`, answered at runtime by
`dashboard.period.age_one`/`_other`, was reported as "renders raw to a user":
a false statement inside a headline count a reader trusts. A key is present when
it is there, or when ANY i18next plural suffix of it is.

THE RATCHET
-----------
`UNRESOLVED_BASELINE` is what remained when the gate landed. It may only fall.
It is 0 today, because the 48 were written first — which was the whole order of
the work, and is why a ratchet rather than a register is honest here.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_APPS = REPO_ROOT / "06-backend" / "apps"
EN = REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales" / "en.json"

# i18next resolves a `count` call through these suffixes (DEF-323).
PLURAL_SUFFIXES = ("_zero", "_one", "_two", "_few", "_many", "_other")

# What remained unresolved when this gate landed. LOWER IT when it falls; the
# gate FAILS if it rises, and REPORTS when it has fallen without being lowered.
UNRESOLVED_BASELINE = 0


def _positional_helpers(tree: ast.Module) -> dict[str, int]:
    """{helper name: which POSITIONAL argument is its message_key}, per file.

    ⚠ THE THIRD FORM, ADDED 2026-08-24 (DEF-643), AND IT WAS THE COMMON ONE.
    A module almost always wraps `errors.BizError` in a local helper —
    `def _refuse(code, message_key, **params)`, `def _cap(message_key,
    **params)`, `def _field_error(field, code, message_key, **params)` — and
    then calls it POSITIONALLY: `_refuse(errors.BIZ_STATE, "customers.x.y")`.
    Neither form above sees that. There is no `message_key=` keyword and no
    dict literal; there is a bare string in argument slot 1.

    MEASURED THE DAY THIS WAS FIXED: **341** keys reach a user this way — the
    majority of every key the backend raises — and **60 of them resolved to
    NOTHING**, across assets, customers, metering, rating and settings. Every
    one renders as its own raw dotted key on a utility's screen, which is the
    single failure this gate exists to prevent. It reported PASS over all of
    them for as long as it has existed.

    SCOPED PER FILE, DELIBERATELY. Resolving imported helpers would need a
    module graph; keying by bare name across the tree does NOT work and the
    first attempt proved it — two unrelated `_cap` functions merged and the
    scan returned English sentences as if they were keys. A helper defined in
    the file that calls it is the overwhelming majority and is exactly
    checkable. A helper imported from a sibling module is still invisible;
    that is a KNOWN and stated limit, not a silent one.
    """
    helpers: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names = [a.arg for a in node.args.args]
            if "message_key" in names:
                helpers[node.name] = names.index("message_key")
        elif isinstance(node, ast.ClassDef):
            # A dataclass declares its positional order as annotated fields —
            # `Condition(key, state, blocking, message_key)` is called that way.
            fields = [
                n.target.id
                for n in node.body
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
            ]
            if "message_key" in fields:
                helpers[node.name] = fields.index("message_key")
    return helpers


def _looks_like_a_key(text: str) -> bool:
    """A message key is a dotted path. A sentence is not.

    This is the guard that makes the positional read safe: a helper's slot may
    legitimately hold prose (a caption, a reason), and mistaking one for a key
    would have this gate demand catalogue entries for whole sentences.
    """
    return "." in text and " " not in text and not text.endswith(".")


def raised_keys() -> dict[str, str]:
    """{message_key: first file that raises it}, in path order."""
    found: dict[str, str] = {}
    if not BACKEND_APPS.is_dir():
        return found
    for path in sorted(BACKEND_APPS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # a half-written file belongs to another gate
            continue
        rel = str(path.relative_to(REPO_ROOT))
        helpers = _positional_helpers(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "message_key" and _is_str(keyword.value):
                        found.setdefault(keyword.value.value, rel)
                # Form 3 — the positional helper call. See _positional_helpers.
                name = node.func.id if isinstance(node.func, ast.Name) else None
                index = helpers.get(name) if name else None
                if (
                    index is not None
                    and len(node.args) > index
                    and _is_str(node.args[index])
                    and _looks_like_a_key(node.args[index].value)
                ):
                    found.setdefault(node.args[index].value, rel)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if _is_str(key) and key.value == "message_key" and _is_str(value):
                        found.setdefault(value.value, rel)
    return found


def _is_str(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def check() -> tuple[list[str], list[str]]:
    if not EN.is_file():
        return [f"{EN} is missing — the catalogue must exist"], []
    catalogue = set(json.loads(EN.read_text(encoding="utf-8")))

    def resolves(key: str) -> bool:
        return key in catalogue or any(key + suffix in catalogue for suffix in PLURAL_SUFFIXES)

    keys = raised_keys()
    unresolved = sorted((key, where) for key, where in keys.items() if not resolves(key))
    notes = [f"{len(keys)} message_key(s) raised across 06-backend/apps"]
    violations = [f"{key} (raised in {where}) resolves to nothing" for key, where in unresolved]
    return violations, notes


def main() -> int:
    violations, notes = check()
    for note in notes:
        print(f"note: {note}")
    for violation in violations[:12]:
        print(f"FAIL: {violation}")
    if len(violations) > UNRESOLVED_BASELINE:
        print(
            f"\n{len(violations)} unresolved key(s), {UNRESOLVED_BASELINE} baselined. "
            "A raised key with no catalogue entry renders as SILENCE now that "
            "params.detail is suppressed (PO ruling 2026-08-19) — write the "
            "sentence in all eleven catalogues."
        )
        return 1
    print(f"every raised message_key resolves ({len(violations)} unresolved, baseline {UNRESOLVED_BASELINE})")
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    violations, notes = check()
    if len(violations) > UNRESOLVED_BASELINE:
        return "FAIL", (
            f"{len(violations)} raised message_key(s) resolve to nothing, "
            f"{UNRESOLVED_BASELINE} baselined: {violations[0][:80]}"
        )
    if len(violations) < UNRESOLVED_BASELINE:
        return "PASS", (
            f"{len(violations)} unresolved, DOWN from {UNRESOLVED_BASELINE} — "
            f"lower UNRESOLVED_BASELINE to {len(violations)} to hold the gain"
        )
    return "PASS", f"{notes[0]}; {len(violations)} unresolved, at the baseline"


if __name__ == "__main__":
    raise SystemExit(main())

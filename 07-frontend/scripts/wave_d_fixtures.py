"""Point the six hand-built `TaxRow` fixtures at the one shared default.

CR-013 P4 (2026-08-21): `TaxRow` gained twenty fields and six test files each
held a complete literal of the contract, so all six went red for a reason that
had nothing to do with what they test. Each gains ONE line — `...taxRowDefaults(),`
as the first property — and keeps every value it already declared, because a
later key wins over a spread. Nothing any of these tests asserts changes.

Idempotent: a file that already spreads the defaults is left alone.
"""

from __future__ import annotations

import pathlib
import re

FILES = [
    "src/features/rating/ChargesTaxes.test.tsx",
    "src/features/rating/DefinitionDetail.test.tsx",
    "src/features/rating/PlanWizard.test.tsx",
    "src/features/tenancy/SettingsAccountingTab.test.tsx",
]

IMPORT_LINE = 'import { taxRowDefaults } from "@/features/rating/taxRowFixture";\n'
LOCAL_IMPORT = 'import { taxRowDefaults } from "./taxRowFixture";\n'
SPREAD = "  ...taxRowDefaults(),\n"

LITERAL = re.compile(r"(:\s*TaxRow\s*=\s*\{\n)")


def main() -> None:
    for name in FILES:
        path = pathlib.Path(name)
        text = path.read_text(encoding="utf-8")
        if "taxRowDefaults" in text:
            print(f"{name}: already wired")
            continue
        # Indent the spread to match the literal it opens (top-level fixtures are
        # at 0, the one inside a test body is at 4).
        def insert(match: re.Match[str]) -> str:
            start = match.end()
            following = text[start : start + 40]
            indent = re.match(r"[ ]*", following).group(0) or "  "
            return match.group(1) + f"{indent}...taxRowDefaults(),\n"

        updated, count = LITERAL.subn(insert, text)
        if count == 0:
            print(f"{name}: no TaxRow literal found — skipped")
            continue
        # The import goes after the last existing import line, so the file's own
        # ordering is untouched.
        lines = updated.splitlines(keepends=True)
        last_import = max(i for i, line in enumerate(lines) if line.startswith("import "))
        which = LOCAL_IMPORT if "/features/rating/" in name else IMPORT_LINE
        lines.insert(last_import + 1, which)
        path.write_text("".join(lines), encoding="utf-8")
        print(f"{name}: {count} literal(s) wired")


if __name__ == "__main__":
    main()

"""G2 - code-trace lint (B12 r2 / B8 traceability standard).

Every US-ID cited in a code file's `── Trace ──` header must exist as a story
(frontmatter `id: US-...` in 04-docs/05-modules/*/06-epics/*.md); every cited
BR-ID must exist in 04-docs/05-modules/*/02-business-rules.md. A dangling ID
means the code claims a requirement the docs do not define — FAIL.

Docs-side integrity (duplicate IDs, docs referencing docs) stays with
10-scripts/02-trace_lint.py, which CI runs alongside this suite.
"""
import sys
import common


def run() -> tuple[str, str]:
    traced = common.files_with_trace_header()
    if not traced:
        return "SKIP", "no Trace-headed code files yet — nothing cites US/BR IDs"

    stories = common.defined_story_ids()
    rules = common.defined_br_ids()
    problems = []
    for path, text in traced:
        header = "\n".join(common.trace_header_lines(text))
        for us_id in sorted(set(common.US_ID_RE.findall(header))):
            if us_id not in stories:
                problems.append(f"{common.rel(path)}: cites {us_id} — no such story in 06-epics frontmatter")
        for br_id in sorted(set(common.BR_ID_RE.findall(header))):
            if br_id not in rules:
                problems.append(f"{common.rel(path)}: cites {br_id} — not in any 02-business-rules.md")
    if problems:
        return "FAIL", common.summarize(problems)
    return "PASS", (f"{len(traced)} Trace header(s); all cited IDs resolve "
                    f"({len(stories)} stories, {len(rules)} BRs defined)")


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

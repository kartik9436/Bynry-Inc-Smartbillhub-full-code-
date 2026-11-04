"""G13 — unwired props. Added 2026-08-10 by Eng-Lead from the defect log's own
numbers: `unwired-prop` was the largest single category (4 of 21, DEF-007..010)
— a component built, styled and fully tested, then never given its data. All of
G1–G12 passed on every one of them, because each asks about law, traceability or
output shape and none asks whether a component was wired.

RATIFIED 2026-08-11 by the PO (option A, "keep all four blocking"): G1-G16 are
the confirmed merge-blocking set. G13-G16 were Eng-Lead additions made from
defects that reached the running product; they are now confirmed law, so a
loosening here - an allowlist entry, a skipped check, a widened pattern - is a
change to a ratified decision and belongs in the daily PO batch.

WIDENED 2026-08-15 (DEF-041), and REPORTED for the daily PO batch under exactly
that rule. G13 knew ONE optionality idiom and React has four; measured on
AppShell, SEVEN of its ten optional props had zero non-test callers while this
gate reported "every guarded prop has a caller". The rule is STRICTER now, not
looser - it sees three shapes it could not see - but the change also adds 18
allow entries for the props that widening surfaced, and an allow entry IS a
loosening, so both halves are on the batch. Every one of the 18 carries a reason
and a revisit condition, and the check FAILS ITSELF if any entry lacks the
revisit condition. The idioms, the triage and the 34-finding measurement of the
idiom deliberately NOT enabled are all in check_unwired_props.py's docstring.
"""

import sys
import contextlib
import io

import check_unwired_props


#: How many findings the one-line summary names before it starts counting. The
#: runner prints this beside 100-odd other gates, so it has to stay one line —
#: but one line naming three files is worth more than one line naming none.
SUMMARY_FINDINGS = 3


def run():
    """The runner's contract is ("PASS"|"FAIL"|"SKIP", detail) — not a bool.

    ⚠ **THIS RETURNED `lines[0]` UNTIL 2026-09-05, AND `lines[0]` IS THE
    HEADER (`DEF-GOV-4038`).** `check_unwired_props` prints
    *"FAIL unwired props — a feature is guarded by a prop nothing supplies:"*
    first and then one indented `· <path>: <prop>` line per finding, so the
    gate reported WHICH KIND of failure it had found and never WHICH FILE.

    **It reads as a working gate, which is why it lasted.** The verdict is
    right, the sentence is a real sentence, and the only way to learn the file
    name was to re-run the checker by hand — so a lane meeting this at merge
    time is told a prop somewhere is unsupplied and sent to find it unaided.
    That is a lot of the value of hard-won law 2's gate thrown away in a
    subscript.

    The summary now carries the header AND the findings themselves, first
    `SUMMARY_FINDINGS` of them by name with a count of the rest, which is the
    shape `G78` and `G106` already use.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = check_unwired_props.main()
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return ("PASS" if code == 0 else "FAIL"), "no output"
    header = lines[0]
    # The findings are the indented bullets; the trailing "Either pass the prop
    # …" advice line is not one, and neither is the blank line before it.
    findings = [line.strip().lstrip("·").strip() for line in lines[1:] if line.startswith("  ")]
    if not findings:
        return ("PASS" if code == 0 else "FAIL"), header
    shown = " | ".join(findings[:SUMMARY_FINDINGS])
    more = len(findings) - SUMMARY_FINDINGS
    detail = f"{header} {shown}" + (f" (+{more} more)" if more > 0 else "")
    return ("PASS" if code == 0 else "FAIL"), detail


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

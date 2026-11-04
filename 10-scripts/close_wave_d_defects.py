"""Close the Wave D tax-model defect rows — ONE FIELD ON SEVEN LINES.

⚠ `file_defect.py` deliberately refuses to do this and says why: *"Closing a
defect changes one field on one line and is a different, riskier operation"*,
because a `csv.writer` round-trip RE-SERIALISES EVERY ROW — a whole-file write
wearing the costume of an edit, which on 2026-08-19 swept four lanes' rows into
one commit and silently reverted a fifth.

So this does what that warning prescribes instead:

1. reads the file as BYTES and splits on the CRLF terminator the register uses,
   so no line it does not touch is re-encoded (a `text=True` read converts CRLF
   to LF and rewrites all 400+ lines for a one-field edit);
2. rewrites ONLY the lines whose id is in `CLOSURES`, and only the two fields
   `status` and `fixed_commit`, by re-quoting that row alone;
3. REFUSES if the row's current status is not `open`, if the id is missing, or
   if the field count changes — a register edit that silently did nothing is
   worse than one that stops.

`fixed_commit` carries the SHA and **VERSION PENDING**, not a version number:
the lane brief for this work says *do not bump the version*, and DEF-442 set the
precedent for saying so out loud rather than guessing a number a concurrent lane
may already hold.
"""

from __future__ import annotations

import csv
import io
import pathlib
import sys

REGISTER = pathlib.Path("12-governance/10-defect-log.csv")
SHA = "39e889a"
PENDING = f"{SHA} (VERSION PENDING: integrator to assign — this lane was told not to bump it)"

CLOSURES: dict[str, str] = {
    "DEF-380": f"matched premise count served from the engine's own premises_in_scope (BR-RAT-107), {PENDING}",
    "DEF-382": f"taxes.discount_treatment + the taxable_subtotal_for reader (BR-RAT-106), {PENDING}",
    "DEF-383": f"tax_exemption_categories + tax_exemption_certificates, wired into the bill run (BR-RAT-105), {PENDING}",
    "DEF-384": f"the correction row over the same window + the SERVER-side in-force edit refusal (BR-RAT-104), {PENDING}",
    "DEF-385": f"thirteen columns on taxes, collected by TAX-02 and read back (rounding stored-not-honoured, OQ-309), {PENDING}",
    "DEF-387": f"four statuses derived + taxes.is_draft, the one fact no date carries (BR-RAT-103), {PENDING}",
    "DEF-467": f"plan_tax_rules reads the effective window it had stored since r6.5 (BR-RAT-103), {PENDING}",
}

STATUS = 11
FIXED_COMMIT = 12
WIDTH = 14


def main() -> int:
    raw = REGISTER.read_bytes()
    terminator = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(terminator)
    seen: set[str] = set()

    for index, line in enumerate(lines):
        if not line.strip():
            continue
        text = line.decode("utf-8")
        row = next(csv.reader([text]))
        if len(row) != WIDTH or row[0] not in CLOSURES:
            continue
        if row[STATUS] != "open":
            print(f"REFUSED: {row[0]} is '{row[STATUS]}', not 'open' — left alone", file=sys.stderr)
            return 1
        row[STATUS] = "fixed"
        row[FIXED_COMMIT] = CLOSURES[row[0]]
        buffer = io.StringIO()
        csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="").writerow(row)
        rewritten = buffer.getvalue()
        if len(next(csv.reader([rewritten]))) != WIDTH:
            print(f"REFUSED: {row[0]} would not round-trip at {WIDTH} fields", file=sys.stderr)
            return 1
        lines[index] = rewritten.encode("utf-8")
        seen.add(row[0])
        print(f"closed {row[0]}")

    missing = sorted(set(CLOSURES) - seen)
    if missing:
        print(f"REFUSED: not found in the register: {', '.join(missing)}", file=sys.stderr)
        return 1

    REGISTER.write_bytes(terminator.join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

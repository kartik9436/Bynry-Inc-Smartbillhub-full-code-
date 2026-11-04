#!/usr/bin/env python3
"""Append the CR-067 frontend lane's two defect rows, with the ids it reserved.

`DEF-3321` and `DEF-3322` come out of `CR-067`'s own reserved block
(`DEF-3320-3339`, `12-governance/14-id-reservations.md`), which is why they are
written here rather than taken from `file_defect.py`'s global `max + 1` — that
allocator would hand out a number from somebody else's range.

⚠ IT REFUSES IF EITHER ID IS ALREADY IN THE REGISTER, which is law 11's id
clause done by the machine: a sibling working in its own worktree has rows in
nothing this checkout can see until it pushes, so the check belongs at write
time AND again at push time.
"""

import csv
import pathlib
import sys

REGISTER = pathlib.Path(__file__).resolve().parents[2] / "12-governance" / "10-defect-log.csv"

ROWS = [
    {
        "id": "DEF-3321",
        "reported_on": "2026-09-02",
        "reported_by": "CR-067 frontend lane, looking for the endpoint its drawer section was told to build against",
        "title": (
            "error_diagnostics is written and expires and NOTHING READS IT BACK: no route in "
            "06-backend serves the record, so CR-067 task B2's System-Admin technical panel has "
            "no data to draw and no boundary to gate on"
        ),
        "surface": (
            "S61 audit log > the row detail drawer (07-frontend/src/features/audit/AuditLogPage.tsx) "
            "· 06-backend/apps/audit/api.py · 06-backend/apps/audit/selectors.py::audit_detail"
        ),
        "module": "audit",
        "severity": "high",
        "found_in": "06-backend/apps/audit/api.py",
        "introduced_in": (
            "CR-067's own task table: A1 creates the table, A2 the redaction, A3 the capture, A4 the "
            "reference and A5 the sweep, and no A-row covers reading a record back onto a screen. "
            "apps/audit/diagnostic_models.py's Lifecycle trailer says so in as many words - "
            "'D=deferred(no endpoint of its own)'"
        ),
        "category": "written-but-never-read",
        "escape_reason": (
            "Every gate that could have asked reads one side only. G52 asks whether a ROLE-GATED "
            "backend action reaches a route and this record has no such action to gate. G13 asks "
            "whether a frontend PROP is passed and there is no prop, because there is no endpoint to "
            "build one from. G27 counts served endpoints and cannot ask which stored table has none. "
            "The backend half's own tests all pass, correctly: they write a record and read it back "
            "in-process through by_reference(). This is hard-won law 2 one layer lower than usual - "
            "not a component nothing passes a prop to, but a TABLE nothing serves - and the same "
            "shape as US-MET-020's archive_job_runs, which had a migration, a command and a kernel "
            "and no api.py anywhere for weeks."
        ),
        "status": "open",
        "fixed_commit": "",
        "prevention": (
            "The endpoint is small and its shape is already decided by CR-067 section 3: a "
            "System-Admin-only read of one diagnostic by the reference the audit row already "
            "carries, answering 'no longer held' for a swept record rather than 404 with no "
            "explanation. Two things it must do that a naive version would not: gate with "
            "@require_role(SYSTEM_ADMIN) so the technical half is a BOUNDARY and not a CSS choice "
            "(a frontend role check is BR-SHL-025 convenience, and both halves are drawn from one "
            "payload today), and run inside the tenant context because error_diagnostics is under "
            "FORCE RLS. Longer term: a gate clause asking of every tenant table whether any route "
            "reads it, ratcheted the way G52 baselines its no-door set."
        ),
    },
    {
        "id": "DEF-3322",
        "reported_on": "2026-09-02",
        "reported_by": "CR-067 frontend lane, sizing the 'Errors only' toolbar control the PO said was required",
        "title": (
            "The audit list cannot be asked for failures: AUDIT_FILTERS has no outcome filter and "
            "'action' matches ONE code exactly, so no toolbar control the frontend can draw reaches "
            "the failure behind 809 rows of successful seeding"
        ),
        "surface": "S61 audit log > the filter toolbar · 06-backend/apps/audit/selectors.py",
        "module": "audit",
        "severity": "medium",
        "found_in": "06-backend/apps/audit/selectors.py",
        "introduced_in": (
            "BR-AUD-009's filter vocabulary, which names actor, action, entity type/id, from and to "
            "and never named an outcome - the audit log had no failure rows to find until CR-039 "
            "wave B added sample.block_failed"
        ),
        "category": "the-control-the-requester-asked-for-has-nothing-to-drive",
        "escape_reason": (
            "Nothing compares a CR task against the API it would need. G62 reads a CR row that "
            "CLAIMS a block and checks the id is live; it cannot ask whether an unblocked row is "
            "buildable. G45 checks that a screen declaring filters renders a filter bar, which is "
            "the opposite direction. And the failure mode if a lane had shipped it anyway is silent: "
            "parse_list_params DROPS an undeclared f.<name> rather than refusing it (BR-SHL-011 - "
            "list params never 4xx), so an 'Errors only' toggle sending f.outcome=error would come "
            "back with the whole unfiltered list and look like a product with no errors in it."
        ),
        "status": "open",
        "fixed_commit": "",
        "prevention": (
            "One filter, server-side, over a NAMED set of failure actions rather than a guessed "
            "prefix: sample.block_failed, sample.seed_incomplete, security.attempt_refused, "
            "auth.sign_in_failed, auth.lockout, tenant.provision_failed, customer.not_created and "
            "reference.sweep_failed are what the writers actually emit today. It has to be the "
            "server's list because the count and the pagination are the server's; a client-side "
            "narrowing of one 25-row page would report 'no errors' on page 1 of 33. The frontend "
            "half is one toggle in the S61 toolbar writing f.outcome=error into the URL, and it is "
            "deliberately NOT shipped ahead of the filter - a control that appears to narrow and "
            "does not is worse than no control."
        ),
    },
]


def main() -> int:
    with REGISTER.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        existing = {row["id"] for row in reader}
    for row in ROWS:
        if row["id"] in existing:
            print(f"REFUSED: {row['id']} is already in the register — renumber before writing")
            return 1
        if set(row) != set(fields):
            print(f"REFUSED: {row['id']} does not match the register's columns")
            return 1
    original = REGISTER.read_text(encoding="utf-8")
    if not original.endswith("\n"):
        print("REFUSED: the register does not end in a newline — a lane is mid-write")
        return 1
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\n")
    for row in ROWS:
        writer.writerow(row)
    appended = buffer.getvalue()
    assert appended.strip(), "nothing to append"
    with REGISTER.open("a", encoding="utf-8", newline="") as handle:
        handle.write(appended)
    print(f"appended {len(ROWS)} row(s): {', '.join(row['id'] for row in ROWS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

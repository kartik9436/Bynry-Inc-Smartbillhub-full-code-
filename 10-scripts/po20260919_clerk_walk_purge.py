#!/usr/bin/env python3
"""Remove everything the clerk walk created, BY ITS TAG AND NOTHING ELSE.

The journey's own instruction: *"Leave the beta as it was found: count the
service requests before and after, and purge by a tag."*

⚠ **IT DELETES BY `applicant_name LIKE '<tag>%'` AND REFUSES ANY OTHER
PREDICATE.** A purge that takes a date range, or "the newest N rows", or
`is_sample = false`, is one mistake away from deleting a tester's work — and
this database is the beta, with real people looking at it. The tag is written
by the walk into the one required free-text field on the row, so every row it
made carries it and no row it did not make can.

⚠ **`--dry-run` IS THE DEFAULT.** Pass `--commit` to actually delete.

⚠ **THE STORED FILE ITSELF CANNOT BE PURGED, AND THAT IS THE PRODUCT WORKING.**
`stored_documents` is write-once under a seven-year object lock (`BR-SHL-031`,
`NFR-35`), so the attachment ROW goes and one small orphan object stays, named
by nothing and reachable from nothing. It is ~50 bytes per walk. Stated here
rather than hidden, because a purge that claimed to remove it would be lying.

    python3 10-scripts/po20260919_clerk_walk_purge.py --tag CLERKWALK-475842
    python3 10-scripts/po20260919_clerk_walk_purge.py --tag CLERKWALK-475842 --commit
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

DSN = os.environ.get("CW_DSN", "postgres://sbh:u3mCzzMxzQmNBvS-nfPoDV4q@127.0.0.1:5432/sbh")
TENANT = os.environ.get("CW_TENANT_ID", "01a0afe1-1f82-780e-bb2f-502863531c71")

# Children first. `service_requests` last, so a failure part-way leaves a
# readable parent rather than orphaned children nothing can find.
CHILDREN = [
    ("service_request_documents", "request_id"),
    ("service_request_fees", "request_id"),
    ("service_request_events", "request_id"),
    ("service_request_messages", "request_id"),
    ("service_request_extra_messages", "request_id"),  # DEF-CUS-10042
    ("service_request_services", "request_id"),
    # ⚠ **APPROVING RAISES A JOB, AND THE JOB FKs BACK TO THE REQUEST.** The
    # first run of this purge failed on
    # `move_in_jobs_request_id_fk_service_requests_id` — which is the product
    # working: `approve_and_raise` creates the build and names the request on
    # it. A purge that did not know this would leave the request behind with a
    # misleading "deleted" on screen. Only rows pointing at OUR requests go.
    ("move_in_jobs", "request_id"),
    # `service_request_document_requirements` is deliberately NOT here: it is a
    # TENANT-level settings table (which document types this utility asks for),
    # keyed by tenant and not by request. Deleting from it would remove the
    # utility's own configuration, which is the opposite of leaving the beta as
    # it was found.
    ("outbound_messages", "source_id"),
]


def psql(*statements: str) -> str:
    # `-q` matters: without it psql prints the `SET` command tag on stdout and
    # it is indistinguishable from a result row, which put the literal string
    # "SET" into an id list the first time this was run.
    args = ["psql", DSN, "-X", "-At", "-q", "-v", "ON_ERROR_STOP=1",
            "-c", f"SET app.tenant_id = '{TENANT}';"]
    for s in statements:
        args += ["-c", s]
    out = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        raise SystemExit(f"psql failed: {out.stderr.strip()[:600]}")
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    # The tag is interpolated into SQL, so it is constrained to the shape the
    # walk generates and nothing else. A purge script that accepts arbitrary
    # text is a purge script that accepts `%`.
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", args.tag):
        raise SystemExit(f"refusing tag {args.tag!r}: expected [A-Za-z0-9_-]{{4,64}}")

    rows = [r for r in psql(
        f"SELECT id, request_no, state, applicant_name FROM service_requests "
        f"WHERE applicant_name LIKE '{args.tag}%' ORDER BY created_at"
    ).split("\n") if r]
    if not rows:
        print(f"nothing tagged {args.tag}")
        return 0

    ids = [r.split("|")[0] for r in rows]
    print(f"{len(ids)} request(s) tagged {args.tag}:")
    for r in rows:
        print("  " + r)

    id_list = ", ".join(f"'{i}'" for i in ids)
    if not args.commit:
        for table, col in CHILDREN:
            n = psql(f"SELECT count(*) FROM {table} WHERE {col} IN ({id_list})")
            if n != "0":
                print(f"  would delete {n} row(s) from {table}")
        print("\nDRY RUN — pass --commit to delete.")
        return 0

    # ⚠ **`outbound_messages.source_id` IS NOT ALWAYS THE REQUEST.** The
    # acknowledgement queued on submit carries the REQUEST's id, so the
    # `CHILDREN` sweep below catches it — but a decision message (refused,
    # more info, approved) carries the id of its `service_request_messages`
    # ROW instead. The first run of this purge left eight of those behind and
    # the count of outbound_messages did not come back to its baseline, which
    # is the only reason it was noticed. So resolve the message ids FIRST,
    # while the rows still exist, and delete what points at them.
    msg_ids = [r for r in psql(
        f"SELECT id FROM service_request_messages WHERE request_id IN ({id_list})"
    ).split("\n") if r]
    stmts = []
    if msg_ids:
        msg_list = ", ".join(f"'{m}'" for m in msg_ids)
        stmts.append(f"DELETE FROM outbound_messages WHERE source_id IN ({msg_list});")
    stmts += [f"DELETE FROM {t} WHERE {c} IN ({id_list});" for t, c in CHILDREN]
    stmts.append(f"DELETE FROM service_requests WHERE id IN ({id_list});")
    psql(*stmts)
    left = psql(f"SELECT count(*) FROM service_requests WHERE applicant_name LIKE '{args.tag}%'")
    print(f"\ndeleted. rows still tagged {args.tag}: {left}")
    print("note: stored_documents objects are write-once (BR-SHL-031) and remain, orphaned.")
    return 0 if left == "0" else 1


if __name__ == "__main__":
    sys.exit(main())

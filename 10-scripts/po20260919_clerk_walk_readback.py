#!/usr/bin/env python3
"""Read every verdict of the clerk walk back out of PostgreSQL.

`08-qa/01-e2e/journeys/J-REQ-CLERK-WALK-the-request-end-to-end.md` says it in
as many words:

    ⚠ **EACH ONE VERIFIED IN THE DATABASE AFTERWARDS, NOT ON THE SCREEN.** A
    screen that says *Approved* over a row that did not move is exactly the
    class of defect that only surfaces in front of a customer.

So `po20260919_clerk_walk_end_to_end.mjs` drives the browser and writes a
manifest of the ids it made; this reads those ids out of the database and
decides. The two halves are deliberately separate processes: a browser that
asks the API whether the API did its job is one witness, not two.

⚠ **IT READS WITH `app.tenant_id` SET, BECAUSE THE ALTERNATIVE LIES BY
OMISSION.** `service_requests` is under RLS FORCE. A psql session with no
`app.tenant_id` returns ZERO ROWS for every query here — not an error, a clean
empty result — so a readback written without the SET would report "no account
was created" and "no journal line was posted" with total confidence, over a
database it cannot see. That is hard-won law 7's *reporting zero over a scope it
silently excludes*, and it would make every NOT-check in this file pass for the
wrong reason. The count of visible rows is printed for exactly that reason.

⚠ **THE `must NOT` CHECKS ARE THE POINT AND THEY ARE ALL SCOPED IN TIME.**
"Approve did not open an account" is unprovable in the abstract — the beta has
accounts. What IS provable is that no account, job, payment or journal line
appeared in this tenant AFTER the walk started. Every negative check therefore
compares against a baseline captured before the walk, passed in as
`--since <ISO timestamp>`.

    python3 10-scripts/po20260919_clerk_walk_readback.py \
        --manifest /tmp/clerk-walk-manifest.json --since '2026-09-19T16:00:00Z'
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

DSN = os.environ.get(
    "CW_DSN", "postgres://sbh:u3mCzzMxzQmNBvS-nfPoDV4q@127.0.0.1:5432/sbh"
)
TENANT = os.environ.get("CW_TENANT_ID", "01a0afe1-1f82-780e-bb2f-502863531c71")

RESULTS: list[tuple[bool, str, str]] = []


def ok(name: str, cond: bool, detail: str = "") -> bool:
    RESULTS.append((bool(cond), name, detail))
    return bool(cond)


def q(sql: str) -> list[list[str]]:
    """One scoped query. The SET and the SELECT share a session -- separate
    `-c` arguments run in ONE connection, which is what makes the RLS scope
    apply to the statement that follows it."""
    out = subprocess.run(
        [
            # `-q` or psql prints the SET command tag as if it were a row.
            "psql", DSN, "-X", "-At", "-q", "-F", "\x1f",
            "-c", f"SET app.tenant_id = '{TENANT}';",
            "-c", sql,
        ],
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip()[:400]}")
    return [line.split("\x1f") for line in out.stdout.strip().split("\n") if line]


def one(sql: str, default=None):
    rows = q(sql)
    return rows[0][0] if rows and rows[0] and rows[0][0] != "" else default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="/tmp/clerk-walk-manifest.json")
    ap.add_argument("--since", required=True, help="ISO timestamp taken BEFORE the walk")
    args = ap.parse_args()

    man = json.load(open(args.manifest))
    since = args.since
    tag = man["tag"]

    # ── the scope proof, first, because every NOT-check below depends on it ──
    visible = int(one("SELECT count(*) FROM service_requests", "0"))
    ok(
        "scope · the readback can see this tenant's rows at all",
        visible > 0,
        f"{visible} service_requests visible under app.tenant_id — if this were 0, "
        f"every 'nothing happened' check below would pass for the wrong reason",
    )
    if visible == 0:
        print("REFUSED: RLS scope not established; every negative check would be a false pass.")
        return 2

    walked = q(
        "SELECT id, request_no, state, applicant_name, applicant_email, applicant_phone, "
        "  coalesce(date_of_birth::text,''), coalesce(drivers_licence,''), coalesce(ssn,''), "
        "  coalesce(co_applicant_name,''), coalesce(co_applicant_email,''), coalesce(co_applicant_phone,''), "
        "  coalesce(requested_start::text,''), coalesce(units_on_property::text,''), "
        "  coalesce(billing_address_as_given,''), coalesce(waiting_on,''), "
        "  coalesce(submitted_at::text,''), coalesce(decision_reason,''), coalesce(reason_code,''), "
        "  coalesce(outcome,''), coalesce(outcome_kind,''), coalesce(park_note,''), "
        "  coalesce(parked_at::text,''), coalesce(fee_quoted::text,''), coalesce(fee_collected::text,''), "
        "  coalesce(address_as_given,''), coalesce(address_unit_as_given,'')"
        f" FROM service_requests WHERE applicant_name LIKE '{tag}%' ORDER BY created_at"
    )
    by_id = {r[0]: r for r in walked}
    ok("the walk's requests are in the database", len(walked) > 0, f"{len(walked)} row(s) tagged {tag}")

    C = dict(
        id=0, no=1, state=2, name=3, email=4, phone=5, dob=6, licence=7, ssn=8,
        co_name=9, co_email=10, co_phone=11, start=12, units=13, billing=14,
        waiting=15, submitted_at=16, reason=17, reason_code=18, outcome=19,
        outcome_kind=20, park_note=21, parked_at=22, fee_quoted=23,
        fee_collected=24, address=25, unit=26,
    )

    # ══ CASE 1 · THE DRAFT ═══════════════════════════════════════════════
    d = man["cases"].get("draft", {})
    drow = by_id.get(d.get("id"))
    if drow:
        ok("1.2 · the draft's state is Draft in the database", drow[C["state"]] == "draft", drow[C["state"]])
        ok("1.1 · the draft carries its number", drow[C["no"]] not in ("", None), drow[C["no"]])

        # every field the clerk typed, read out of its own column
        v = d.get("values", {})
        pairs = [
            ("applicant_email", v.get("applicant_email"), drow[C["email"]]),
            ("applicant_phone", v.get("applicant_phone"), drow[C["phone"]]),
            ("date_of_birth", v.get("date_of_birth"), drow[C["dob"]]),
            ("ssn", v.get("ssn"), drow[C["ssn"]]),
            ("co_applicant_name", v.get("co_applicant_name"), drow[C["co_name"]]),
            ("co_applicant_email", v.get("co_applicant_email"), drow[C["co_email"]]),
            ("co_applicant_phone", v.get("co_applicant_phone"), drow[C["co_phone"]]),
            ("requested_start", v.get("requested_start"), drow[C["start"]]),
            ("units_on_property", v.get("units_on_property"), drow[C["units"]]),
            ("billing_address_as_given", v.get("billing_address_as_given"), drow[C["billing"]]),
        ]
        lost = [f"{n}: typed {w!r}, column holds {g!r}"
                for n, w, g in pairs if w and (g or "").strip() == ""]
        ok("1.3db · every field typed on the draft reached its column", not lost,
           f"{len(lost)} never stored → " + " ; ".join(lost) if lost else "all stored")
        # the licence is encrypted at rest, so its column is checked for PRESENCE
        ok("1.3db-licence · the driver's licence was stored (encrypted at rest)",
           (drow[C["licence"]] or "").strip() != "", "present" if drow[C["licence"]] else "EMPTY")

        # the attached document and its bytes
        docs = q(
            "SELECT id, coalesce(name,''), coalesce(size::text,''), coalesce(storage_ref,''), "
            "coalesce(verification_state,'') FROM service_request_documents "
            f"WHERE request_id = '{d['id']}'"
        )
        ok("1.5 · the draft's document row is in the database", len(docs) > 0, f"{len(docs)} row(s)")
        if docs:
            ok("1.5b · it points at a stored object", docs[0][3] != "", docs[0][3][:70])
            ok("1.5c · its recorded size equals the bytes handed in",
               docs[0][2] == str(d.get("document", {}).get("bytes")),
               f"{docs[0][2]} vs {d.get('document', {}).get('bytes')}")
            ok("1.5d · it did NOT land pre-verified", docs[0][4] != "verified", docs[0][4])

        # ── 1.6 · NOTHING LEFT THE BUILDING ──
        did = d["id"]
        msgs = int(one(f"SELECT count(*) FROM outbound_messages WHERE source_id = '{did}'", "0"))
        ok("1.6a · the draft sent no message to anybody", msgs == 0, f"{msgs} outbound_messages")
        fired = int(one(
            f"SELECT count(*) FROM service_request_messages WHERE request_id = '{did}' AND fired_at IS NOT NULL", "0"))
        ok("1.6b · no applicant message was fired for the draft", fired == 0, f"{fired} fired")
        fees = int(one(f"SELECT count(*) FROM service_request_fees WHERE request_id = '{did}'", "0"))
        ok("1.6c · no fee was raised on the draft", fees == 0, f"{fees} fee line(s)")
        ok("1.6d · no money was recorded as collected on the draft",
           (drow[C["fee_collected"]] or "") in ("", "0", "0.0000"), drow[C["fee_collected"]])

    # ── side effects across the whole tenant since the walk began ──
    # These are the `must NOT` checks for the draft AND the guard for Approve.
    new_accounts = int(one(f"SELECT count(*) FROM accounts WHERE created_at >= '{since}'", "0"))
    new_payments = int(one(f"SELECT count(*) FROM payments WHERE created_at >= '{since}'", "0"))
    new_journal = int(one(f"SELECT count(*) FROM journal_entries WHERE created_at >= '{since}'", "0"))
    ok("1.6e · no account was opened anywhere during the walk", new_accounts == 0, f"{new_accounts} new account(s)")
    ok("1.6f · no payment was taken during the walk", new_payments == 0, f"{new_payments} new payment(s)")
    ok("1.6g · no journal entry was posted during the walk", new_journal == 0, f"{new_journal} new entry/entries")

    # ══ CASE 2 · THE SUBMITTED REQUEST ═══════════════════════════════════
    s = man["cases"].get("submitted", {})
    srow = by_id.get(s.get("id"))
    if srow:
        ok("2.1 · the submitted request's state is Submitted", srow[C["state"]] == "submitted", srow[C["state"]])
        ok("2.1b · it carries a submitted_at", srow[C["submitted_at"]] != "", srow[C["submitted_at"]])
        ok("2.2 · it carries a waiting-on", srow[C["waiting"]] != "", srow[C["waiting"]] or "EMPTY")
        sid = s["id"]
        told = int(one(f"SELECT count(*) FROM outbound_messages WHERE source_id = '{sid}'", "0"))
        fired = q("SELECT occasion, coalesce(fired_at::text,''), coalesce(fired_state,''), coalesce(fired_reason,'') "
                  f"FROM service_request_messages WHERE request_id = '{sid}'")
        ok("2.3 · the applicant was told the request was received",
           told > 0 or any(r[1] for r in fired),
           f"outbound_messages={told}; service_request_messages={[ (r[0], r[2] or 'not fired', r[3]) for r in fired ]}")
        docs2 = int(one(f"SELECT count(*) FROM service_request_documents WHERE request_id = '{sid}'", "0"))
        ok("2.4 · its document is stored", docs2 > 0, f"{docs2} row(s)")
        fee_lines = q("SELECT charge_code, amount::text, coalesce(settled_at::text,'') "
                      f"FROM service_request_fees WHERE request_id = '{sid}'")
        ok("2.5 · a fee was raised on submit", len(fee_lines) > 0,
           f"{len(fee_lines)} fee line(s) {fee_lines if fee_lines else ''}")
        ok("2.5b · and it reached payments", new_payments > 0, f"{new_payments} payment(s) since the walk began")
        ok("2.5c · and it reached the books", new_journal > 0, f"{new_journal} journal entry/entries since the walk began")

    # ══ THE FOUR ACTIONS ═════════════════════════════════════════════════
    EXPECT = {
        "PARK":    ("under_review", "Park · Submitted becomes Under review"),
        "ASK":     ("more_info",    "Ask for more · the state becomes More info"),
        "REFUSE":  ("refused",      "Refuse · the state becomes Refused"),
        "APPROVE": ("approved",     "Approve · the state becomes Approved"),
    }
    for key, (want, label) in EXPECT.items():
        a = man.get("actions", {}).get(key)
        if not a or not a.get("id"):
            ok(f"4.{key.lower()} · the walk created a request to {key.lower()}", False, "no id in manifest")
            continue
        row = by_id.get(a["id"])
        if not row:
            ok(f"4.{key.lower()} · its row is readable", False, a["id"])
            continue
        got = row[C["state"]]
        screen = a.get("screenState")
        ok(f"4.{key.lower()} · {label}", got == want, f"database says {got!r} (screen said {screen!r})")
        if screen and got != want:
            ok(f"4.{key.lower()} · the screen and the database agree", False,
               f"screen {screen!r} vs database {got!r}")

        aid = a["id"]
        msgs = int(one(f"SELECT count(*) FROM outbound_messages WHERE source_id = '{aid}'", "0"))
        if key == "PARK":
            ok("4.park · waiting-on is set", row[C["waiting"]] != "", row[C["waiting"]] or "EMPTY")
            ok("4.park · a park note is recorded", row[C["park_note"]] != "", row[C["park_note"]][:60] or "EMPTY")
            ok("4.park · nothing was decided", row[C["outcome"]] == "" and row[C["reason"]] == "",
               f"outcome={row[C['outcome']]!r} reason={row[C['reason']]!r}")
        if key == "ASK":
            ok("4.ask · waiting-on moved to the applicant",
               "applicant" in (row[C["waiting"]] or "").lower(), row[C["waiting"]] or "EMPTY")
            ok("4.ask · a message was sent to the applicant", msgs > 0, f"{msgs} outbound_messages")
            ok("4.ask · it does NOT look refused", row[C["state"]] != "refused", row[C["state"]])
        if key == "REFUSE":
            ok("4.refuse · a reason is recorded",
               row[C["reason"]] != "" or row[C["reason_code"]] != "",
               f"reason={row[C['reason']][:50]!r} code={row[C['reason_code']]!r}")
            ok("4.refuse · the applicant was told", msgs > 0, f"{msgs} outbound_messages")
            # PO 2026-09-15 — *"if it is refuse then it is application fees
            # non refundable - it stya in books"*. A refund would show as a
            # NEGATIVE payment or a reversing journal entry against this row.
            refunds = int(one(
                f"SELECT count(*) FROM payments WHERE created_at >= '{since}' AND amount < 0", "0"))
            ok("4.refuse · the money was NOT given back", refunds == 0, f"{refunds} negative payment(s)")
        if key == "APPROVE":
            ok("4.approve · an outcome travels with the approval",
               row[C["outcome"]] != "" or row[C["outcome_kind"]] != "",
               f"outcome={row[C['outcome']]!r} kind={row[C['outcome_kind']]!r}")
            ok("4.approve · it did NOT open an account", new_accounts == 0, f"{new_accounts} new account(s)")

    # ══ REPORT ═══════════════════════════════════════════════════════════
    print("\n════════ DATABASE READBACK ════════")
    for good, name, detail in RESULTS:
        print(f"{'PASS' if good else 'FAIL'} · {name}" + (f" · {detail}" if detail else ""))
    npass = sum(1 for g, _, _ in RESULTS if g)
    print(f"\n{npass} PASS · {len(RESULTS) - npass} FAIL")
    return 1 if npass != len(RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())

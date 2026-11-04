"""CR-094-BRC01 step 1 lane 1 — MEASURE what the Accounts register and its
seven sibling tabs actually open on, against a running stack.

⚠ WHY THIS EXISTS. `05-prototype/02 Accounts Menu Blueprint.pdf` audits screen
01 with the entry "Walked: **Not walked.** The app could not be booted here (no
docker daemon, no systemd, no PostgreSQL, no node_modules). Every statement in
this entry is read from source." Every as-built claim about this screen is
therefore a READING, and `CR-092` cost this project two passes learning that a
description is not a measurement. This script is the measurement.

WHAT IT ANSWERS, one row per tab: what ordering does the server apply when a
clerk opens the tab with NOTHING chosen, and where does the most recently
created record land in it? That is the question `BR-CUS-1046` (PO 2026-09-10,
"It should always sort it by the creation order. The new newly created entries
should always show on the top") asks of all eight lists, because the ruling says
*any entry* rather than naming the accounts list.

IT WRITES NOTHING. No seeding, no fixtures, no product code — it reads eight
endpoints and prints what came back. Run it before and after the step-2 fix.

USAGE
    # a backend on 8570 with the seeded demo database behind it
    python3 10-scripts/cr094_lane1_register_measure.py [--base URL] [--tenant SLUG]
"""
import argparse
import json
import subprocess
import sys
import tempfile

TABS = [
    # (tab id as it appears in ?tab=, endpoint, key holding the rows, the id field)
    ("accounts", "/accounts", "results", "account_no"),
    ("requests", "/service-requests", "results", "request_no"),
    ("new-connects", "/connections", "results", "connection_no"),
    ("move-ins", "/move-ins", "rows", "move_no"),
    ("move-outs", "/move-outs", "rows", "move_no"),
    ("transfers", "/transfers", "rows", "reference"),
    ("disconnects", "/disconnects", "rows", "case_no"),
    ("imports", "/imports", "rows", "run_no"),
]


def curl(jar, url):
    out = subprocess.run(
        ["curl", "-s", "-b", jar, "-H", "Accept: application/json", url],
        capture_output=True, text=True,
    ).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"__not_json__": out[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8570")
    ap.add_argument("--tenant", default="brazosbend")
    ap.add_argument("--email", default="dana@brazosbendutilities.com")
    ap.add_argument("--password", default="S3cure!passw0rd")
    args = ap.parse_args()
    root = f"{args.base}/api/{args.tenant}"

    jar = tempfile.NamedTemporaryFile(suffix=".cookies", delete=False).name
    login = subprocess.run(
        ["curl", "-s", "-c", jar, "-X", "POST", f"{root}/auth/session",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"email": args.email, "password": args.password})],
        capture_output=True, text=True,
    ).stdout
    if "user" not in login:
        sys.exit(f"could not sign in: {login[:200]}")

    print(f"# measured against {root}\n")
    for tab, path, rows_key, id_field in TABS:
        body = curl(jar, f"{root}{path}")
        if "__not_json__" in body:
            print(f"{tab:<14} ENDPOINT DID NOT ANSWER JSON: {body['__not_json__']!r}")
            continue
        rows = body.get(rows_key) or []
        total = body.get("count", body.get("total", len(rows)))
        envelope = "DRF count/next/previous/results" if "results" in body else (
            "page/per/total/pages" if "total" in body else "rows ONLY — no count, no page"
        )
        head = [str(r.get(id_field) or "?") for r in rows[:3]]
        print(f"{tab:<14} rows={len(rows):<4} total={total:<5} envelope={envelope}")
        print(f"{'':<14} first three: {' · '.join(head) if head else '(empty list)'}")
    print("\n# the ordering each list APPLIES is in the server, not in this output:")
    print("#   accounts      selectors.account_list — rows.sort() in PYTHON, default ACCOUNT_DEFAULT_SORT")
    print("#   requests      service_request_reads   — .order_by('received_at', 'id')")
    print("#   new-connects  connection_reads        — .order_by(target_activation asc nulls_last, 'id')")
    print("#   move-ins      move_reads              — .order_by('opened_at', 'account_no')")
    print("#   move-outs     move_reads              — .order_by('closed_at', 'account_no')")
    print("#   transfers     transfer_reads          — .order_by('-created_at', '-id')")
    print("#   disconnects   disconnect_reads        — .order_by('account_no', 'id')")
    print("#   imports       import_runs.run_list    — .order_by('-created_at')[:200]")


if __name__ == "__main__":
    main()

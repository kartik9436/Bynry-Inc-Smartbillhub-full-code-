"""CR-168-BRC10 lane FLOW-FIX — raise, complete in the field, accept, over HTTP.

The PO's question, verbatim: *"when work orders are completed is clerk able to
see the status update in those requests"*. For each flow this drives the REAL
doors of a running build (`2.508.x`) on PostgreSQL:

  1. RAISE as Dana through the flow's own HTTP door — move-out
     (`POST /accounts/{id}/move-out`), move-in on the unit it vacated
     (`POST /accounts/{from}/move-in`), a sale (`POST /transfers/commit`), a
     cut and then the reconnect page's own row raise
     (`POST /disconnects/{ref}/reconnect/work-orders {service}`), and for New
     Connect the jobs a seeded build already carries;
  2. ASSIGN to R. Patel (`POST /work-orders/{id}/assignments`), then, signed in
     AS R. Patel on the mobile surface, close through the field sync API the
     phone uses (`POST /work/mobile/jobs/{id}/sync`) — the office never
     completes (ruling 18);
  3. ACCEPT as Dana (`POST /work-orders/{id}/accept`);
  4. print each originating record's read, and write a TARGETS file for
     `cr168_flows_walk.mjs` to photograph.

⚠ WHAT WOULD MAKE THIS PASS WRONGLY (law 7, habit 2): a step answering 4xx
that the script carried past. So every call raises on a non-2xx and prints the
body; and the final reads are printed from the SERVER, never from what this
script believes it did.

    BASE=http://127.0.0.1:5195 /tmp/venv_a5c/bin/python 10-scripts/cr168_flowfix_walk.py \
      > /tmp/flowfix-walk.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests

BASE = os.environ.get("BASE", "http://127.0.0.1:5195")
TENANT = os.environ.get("TENANT", "brazosbend")
API = f"{BASE}/api/{TENANT}"
PASSWORD = os.environ.get("PASSWORD", "S3cure!passw0rd")
DANA = os.environ.get("DANA", "dana@brazosbendutilities.com")
PATEL = os.environ.get("PATEL", "r.patel@sample.test")
TODAY = os.environ.get("TODAY", date.today().isoformat())
#: BR-CUS-056 — a move-in starts the day AFTER the move-out it follows.
TOMORROW = os.environ.get("TOMORROW", (date.today() + timedelta(days=1)).isoformat())
MOVE_OUT_ACCOUNT = os.environ.get("MOVE_OUT_ACCOUNT", "A-10432")
TRANSFER_ACCOUNT = os.environ.get("TRANSFER_ACCOUNT", "A-11109")
DISCONNECT_CASE = os.environ.get("DISCONNECT_CASE", "DSC-26-0001")
BUILDS = os.environ.get("BUILDS", "CON-26-0126,CON-26-0124").split(",")


#: A 1×1 PNG — the walk proves the photo is linked to its row, not what it shows.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def log(*parts: object) -> None:
    print(*parts, file=sys.stderr, flush=True)


def session(email: str, surface: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/session", json={"email": email, "password": PASSWORD, "surface": surface})
    if r.status_code >= 300:
        raise SystemExit(f"sign-in {email}: {r.status_code} {r.text[:300]}")
    return s


def call(s: requests.Session, method: str, path: str, **kw) -> dict:
    r = s.request(method, f"{API}{path}", **kw)
    if r.status_code >= 300:
        raise SystemExit(f"{method} {path}: {r.status_code} {r.text[:600]}")
    return r.json() if r.content else {}


def account_id(dana: requests.Session, account_no: str) -> str:
    rows = call(dana, "GET", "/accounts", params={"q": account_no})
    for row in rows.get("results") or rows.get("rows") or []:
        if row.get("account_no") == account_no:
            return row["id"]
    raise SystemExit(f"no account {account_no}")


def template_for(dana: requests.Session, kind: str, flow_id: str, name: str) -> str:
    offer = call(dana, "GET", f"/work/flows/{kind}/{flow_id}/proposed")
    names = [row["name"] for row in offer.get("proposed") or []]
    log(f"  {kind} is offered: {names}")
    for row in offer.get("proposed") or []:
        if row["name"] == name:
            return row["template_id"]
    raise SystemExit(f"{kind}: '{name}' not offered ({names})")


def by_number(dana: requests.Session, order_no: str) -> dict:
    row = call(dana, "GET", f"/work-orders/by-number/{order_no}")
    return {"id": row["id"], "order_no": row["order_no"]}


def field_close_and_accept(dana, patel, technician_id: str, order: dict, outcome: str = "passed") -> dict:
    oid = order["id"]
    call(dana, "POST", f"/work-orders/{oid}/assignments", json={"act": "assign", "technician_id": technician_id, "reason": "R. Patel takes it"})
    pack = call(patel, "GET", f"/work/mobile/jobs/{oid}")
    items, n = [], 0

    def add(kind, payload):
        nonlocal n
        n += 1
        # Captured in the PAST, minutes ago, in order: a close stamped in the
        # future is refused (`metering.work_order_completed_at_future`).
        at = datetime.now(timezone.utc) - timedelta(minutes=30 - n)
        items.append({"key": f"flowfix-{order['order_no']}-{n:03d}", "kind": kind, "seq": n,
                      "captured_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "payload": payload})

    for row in pack.get("safety") or []:
        add("safety_tick", {"safety_id": row["id"]})
    for row in pack.get("tasks") or []:
        add("task_tick", {"task_id": row["id"]})
    for row in pack.get("readings") or []:
        value = row.get("min_value") or "1204"
        add("reading", {"reading_id": row["id"], "value": str(value), "unit": row.get("unit_of_measure")})
    # The photographs a template REQUIRES, each taken FOR its row through the
    # field app's own upload (#77) — without them the close lands WITH a
    # recorded gap (`BR-WRK-040` superseded 2026-10-21, PO "warn"; until then
    # it was refused, `DEF-WRK-9625`), and this walk wants a clean close.
    for collection, field in (("tasks", "task_id"), ("readings", "reading_id")):
        for row in pack.get(collection) or []:
            if row.get("photo_required") and not row.get("photo_attachment_id"):
                r = patel.post(f"{API}/work-orders/{oid}/attachments",
                               data={"idempotency_key": f"flowfix-photo-{row['id']}", field: row["id"]},
                               files={"file": ("site.png", TINY_PNG, "image/png")})
                if r.status_code >= 300:
                    raise SystemExit(f"photo for {order['order_no']}: {r.status_code} {r.text[:300]}")
    add("close", {"outcome": outcome} if outcome == "passed" else {"outcome": outcome, "notes": "No access to the meter pit"})
    answer = call(patel, "POST", f"/work/mobile/jobs/{oid}/sync", json={"items": items})
    refused = [row for row in answer.get("items") or [] if row.get("result") == "refused"]
    if refused:
        raise SystemExit(f"sync {order['order_no']} refused: {refused}")
    accepted = call(dana, "POST", f"/work-orders/{oid}/accept")
    log(f"  {order['order_no']}: assigned to R. Patel, closed in the field ({outcome}), accepted by Dana")
    return accepted


def main() -> None:
    dana = session(DANA, "web")
    patel = session(PATEL, "mobile")
    tech = call(dana, "GET", "/work/technicians/r-patel")
    technician_id = tech.get("id") or tech.get("technician", {}).get("id")
    targets: list[dict] = []
    done: dict[str, list[str]] = {}

    # ── move-out, then move-in on the unit it vacated ──────────────────────
    out_id = account_id(dana, MOVE_OUT_ACCOUNT)
    if os.environ.get("MOVE_OUT_NO"):
        # Resume: the move-out was committed by an earlier run (a move-out can
        # only happen once); its job is read back from the record itself.
        visit = call(dana, "GET", f"/moves/{os.environ['MOVE_OUT_NO']}")["still_owed"]["visit"]["value"]
        moved = {"move_no": os.environ["MOVE_OUT_NO"],
                 "work_orders": [by_number(dana, o["order_no"]) for o in visit["orders"]]}
    else:
        final = template_for(dana, "move_out", out_id, "Final read")
        moved = call(dana, "POST", f"/accounts/{out_id}/move-out",
                     json={"moved_out_on": TODAY, "field_visit": {"template_ids": [final]}})
    log(f"move-out {moved.get('move_no')}: raised {[o.get('order_no') for o in moved.get('work_orders') or []]}")
    if os.environ.get("MOVE_IN_NO"):
        visit = call(dana, "GET", f"/moves/{os.environ['MOVE_IN_NO']}")["still_owed"]["visit"]["value"]
        moved_in = {"move_no": os.environ["MOVE_IN_NO"],
                    "work_orders": [by_number(dana, o["order_no"]) for o in visit["orders"]]}
    else:
        # ⚠ Asked about the account the move-out just CLOSED, `move_in`'s offer is
        # empty (its services ended with it) — `DEF-WRK-9645`, filed, not fixed here. The template
        # is the same row the move-out was offered, so it is taken from there.
        opening = template_for(dana, "move_out", account_id(dana, TRANSFER_ACCOUNT), "Opening read")
        moved_in = call(dana, "POST", f"/accounts/{out_id}/move-in", json={
            "account_type": "residential", "opened_at": TOMORROW,
            "contact": {"full_name": "Priya Raman", "email": "priya.raman@example.com", "phone": "+1 (281) 555-0177"},
            "customer": {"display_name": "Priya Raman", "kind": "person", "identity": {"phone": "+1 (281) 555-0177"}},
            "field_visit": {"template_ids": [opening]},
        })
    log(f"move-in {moved_in.get('move_no')}: raised {[o.get('order_no') for o in moved_in.get('work_orders') or []]}")

    # ── transfer ───────────────────────────────────────────────────────────
    trf_from = account_id(dana, TRANSFER_ACCOUNT)
    if os.environ.get("TRANSFER_NO"):
        sold = {"transfer_no": os.environ["TRANSFER_NO"],
                "work_orders": [by_number(dana, n) for n in os.environ["TRANSFER_ORDERS"].split(",")]}
    else:
        changeover = template_for(dana, "transfer", trf_from, "Changeover read")
        sold = call(dana, "POST", "/transfers/commit", json={
        "from_account_id": trf_from, "sold_on": TODAY,
        "customer": {"display_name": "Luis Ortega", "kind": "person", "identity": {"phone": "+1 (281) 555-0190"}},
        "field_visit": {"template_ids": [changeover]},
    })
    log(f"transfer {sold.get('transfer_no')}: raised {[o.get('order_no') for o in sold.get('work_orders') or []]}")

    # ── reconnect: cut the case, then the PAGE's own row raise ─────────────
    detail = call(dana, "GET", f"/disconnects/{DISCONNECT_CASE}/reconnect")
    cut_account = account_id(dana, detail["account"]["account_no"])
    if not (detail.get("services") or {}).get("rows"):
        # The demo's cases are all BEFORE the cut (scheduled / notice sent) with
        # no service chosen, so a reconnect page has no row to raise from. The
        # clerk's own two acts: choose what is cut (DSC-02.1), then record it.
        call(dana, "POST", "/disconnects/schedule", json={
            "account_id": cut_account, "cut_on": TODAY,
            "services": {"water": "full_disconnection"}})
        call(dana, "POST", f"/accounts/{cut_account}/disconnect-case/cut", json={"cut_on": TODAY})
        detail = call(dana, "GET", f"/disconnects/{DISCONNECT_CASE}/reconnect")
    rows = (detail.get("services") or {}).get("rows") or []
    log(f"reconnect {DISCONNECT_CASE}: {len(rows)} row(s) {[r.get('service') for r in rows]}")
    if rows[0].get("work_order"):
        # Resume: the row already carries its job — read back, not raised twice.
        raised_rc = {"work_orders": [by_number(dana, rows[0]["work_order"]["reference"])]}
    else:
        raised_rc = call(dana, "POST", f"/disconnects/{DISCONNECT_CASE}/reconnect/work-orders",
                         json={"service": rows[0]["service"]})
    log(f"reconnect raised {[o.get('order_no') for o in raised_rc.get('work_orders') or []]} warnings {raised_rc.get('warnings')}")

    # ── complete and accept every job these raised ─────────────────────────
    flow_orders = [
        *(moved.get("work_orders") or []), *(moved_in.get("work_orders") or []),
        *(sold.get("work_orders") or []), *(raised_rc.get("work_orders") or []),
    ]
    for order in flow_orders:
        if order["order_no"] in os.environ.get("ALREADY_ACCEPTED", "").split(","):
            continue
        field_close_and_accept(dana, patel, technician_id, order)

    # ── New Connect: every open job on the named builds ───────────────────
    for number in BUILDS:
        page = call(dana, "GET", "/work-orders", params={"q": number, "per": 50})
        open_rows = [r for r in page.get("results") or [] if (r.get("connection") or {}).get("connection_no") == number]
        log(f"build {number}: {len(open_rows)} open job(s) {[r['order_no'] for r in open_rows]}")
        for row in open_rows:
            field_close_and_accept(dana, patel, technician_id, row)
        done[number] = [r["order_no"] for r in open_rows]

    # ── two more sources: a meter-read visit, and a FAILED job's follow-up ──
    extras: dict[str, str] = {}
    if os.environ.get("METER_NO"):
        meter = call(dana, "GET", "/assets", params={"q": os.environ["METER_NO"]})
        meter_id = next(r["id"] for r in meter.get("results") or [] if r.get("asset_no") == os.environ["METER_NO"])
        offer = call(dana, "GET", f"/work/flows/meter_read/{meter_id}/proposed")
        reread = next(r["template_id"] for r in offer["proposed"] if r["name"] == "Re-read")
        raised_mr = call(dana, "POST", "/work/flows/meter-read/raise", json={"meters": [meter_id], "template_ids": [reread]})
        mr = (raised_mr.get("raised") or [])[0]
        mr_order = by_number(dana, mr.get("order_no"))
        field_close_and_accept(dana, patel, technician_id, mr_order)
        extras["meter_read"] = mr_order["order_no"]
        failed = by_number(dana, call(dana, "POST", "/work-orders", json={
            "type": "Leak investigation", "service": "water", "premises_id": os.environ["FAILED_PREMISES_ID"],
            "source": "dispatcher"})["order_no"])
        answer = field_close_and_accept(dana, patel, technician_id, failed, outcome="failed")
        extras["failed"] = failed["order_no"]
        extras["follow_up"] = ((answer.get("failed_outcome") or {}).get("follow_up") or {}).get("order_no")
        log(f"meter read {extras['meter_read']}; failed {extras['failed']} -> follow-up {extras['follow_up']}")

    # ── read every originating record back FROM THE SERVER ─────────────────
    out = {
        "move_out": call(dana, "GET", f"/moves/{moved['move_no']}")["still_owed"]["visit"],
        "move_in": call(dana, "GET", f"/moves/{moved_in['move_no']}")["still_owed"]["visit"],
        "move_in_money": call(dana, "GET", f"/moves/{moved_in['move_no']}")["money_taken"],
        "transfer": sold.get("transfer_no"),
        "reconnect_rows": [
            {"service": r["service"], "work_order": r["work_order"]}
            for r in call(dana, "GET", f"/disconnects/{DISCONNECT_CASE}/reconnect")["services"]["rows"]
        ],
        "builds": done,
        "orders": [o.get("order_no") for o in flow_orders],
        "extras": extras,
    }
    targets += [
        {"name": "fx01-move-out-record", "path": f"/moves/{moved['move_no']}", "caption": "move-out record after accept",
         "find": ["1 raised · 1 done · 1 accepted", "Not raised"]},
        {"name": "fx02-move-in-record", "path": f"/moves/{moved_in['move_no']}", "caption": "move-in record after accept",
         "find": ["1 raised · 1 done · 1 accepted", "Not raised", "0.0000"]},
        {"name": "fx03-transfer-record", "path": f"/transfers/{sold.get('transfer_no')}", "caption": "transfer record after accept",
         "find": ["1 raised · 1 done", "0 raised"]},
        {"name": "fx04-reconnect-page", "path": f"/disconnects/{DISCONNECT_CASE}/reconnect", "caption": "reconnect page after accept",
         "find": ["1 raised", "Accepted", "0 raised"]},
    ]
    print(json.dumps({"result": out, "targets": targets}, indent=1, default=str))


if __name__ == "__main__":
    main()

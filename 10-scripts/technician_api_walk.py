#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 §F, lane FIELD-FIX — PO 2026-10-04: "you should create
#          apis for techncian app and use those apis wth payload to complete
#          the jobs". Until the phone app exists, technician work is completed
#          by THIS script calling the technician API as the technician, and the
#          office accepts through its own route (ruling 18: the office never
#          completes a job).
# Contract: 04-docs/03-contracts/technician-api.md
# ───────────────────────────────────────────────────────
"""Complete field jobs purely through the technician API, then accept them as
the office. Prints every request and its status; ends with each job's state.

    python3 10-scripts/technician_api_walk.py --base http://127.0.0.1:8063 \\
        --tenant brazosbend --tech-password '…' --office-password '…' --all-mine
    … --order WO-0043 --order WO-0044          # named jobs only
    … --scenario shared --order WO-0047        # X offline, signs out; Y signs in
    … --fix-accuracy 300 --order WO-0045       # a close with a wide fix → flagged
    … --replay --order WO-0042                 # every page sent twice → nothing added
    … --capture out.json                       # every request/response, for the contract doc
    … --no-accept --order WO-0041              # stop at the close; the office accepts in a browser
    … --outcome failed --order WO-0050         # close the job Failed (a follow-up is raised on Accept)

PER JOB, IN THIS ORDER (each a real HTTP call with a JSON payload):
  POST /auth/session (surface=mobile) → POST /work/mobile/capture-token →
  GET /work/mobile/changes (paged) → GET /work/mobile/jobs/{id} →
  GET …/jobs/{id}/readings (paged) → POST …/accept → POST …/acts depart →
  POST …/acts arrive → POST …/sync (data page: safety, tasks, readings,
  materials and one `photo` declaration per photo-required row — the server
  answers each photo's LINK) → PUT /work/mobile/photos/{photo_id} (the
  compressed bytes, to that link) → POST /work-orders/{id}/signature →
  POST …/sync (the close, with its location fix) → [office]
  POST /auth/session → GET /work-orders/{id} → POST /work-orders/{id}/accept.

Photographs are compressed EXACTLY as the phone does (long edge 1,600 px, JPEG
quality stepped to land in 70–100 KB) and never uploaded raw.

What would make it pass wrongly: a refused item still counted as sent — so
the script counts the server's per-item ACK list, not its own sends, and exits
1 when any item was not acknowledged or any job did not end accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import requests

PAGE = 200  # sync.MAX_ITEMS
LOG: list[dict] = []


#: The handset's clock for this run. `--closed-at` moves it into the past —
#: the close's capture time is the date a final read lands on (`BR-WRK-003`),
#: and a read on a day the meter already has one is refused at Accept.
CLOCK: dict = {"at": None}
#: The value every numeric reading is given; `--reading-value` sets it (the
#: same-day proof reads 3,412 kWh over the office's 3,400).
READING: dict = {"value": "48221"}


def now() -> str:
    at = CLOCK["at"] or datetime.now(timezone.utc)
    return at.isoformat()


class Api:
    def __init__(self, base: str, tenant: str, who: str) -> None:
        self.base, self.tenant, self.who = base.rstrip("/"), tenant, who
        self.s = requests.Session()

    def call(self, method: str, path: str, *, quiet: bool = False, **kw):
        url = f"{self.base}/api/{self.tenant}{path}"
        started = time.monotonic()
        r = self.s.request(method, url, timeout=60, **kw)
        ms = int((time.monotonic() - started) * 1000)
        try:
            body = r.json()
        except ValueError:
            body = None
        if not quiet:
            print(f"  [{self.who}] {method:6} {path} -> {r.status_code} ({ms} ms)")
        LOG.append({
            "who": self.who, "method": method, "path": path, "status": r.status_code,
            "request": kw.get("json") if "json" in kw else (
                {k: v for k, v in kw["data"].items()} if isinstance(kw.get("data"), dict)
                else (f"<{len(kw['data']):,} bytes>" if kw.get("data") else None)),
            "response": body,
        })
        return r.status_code, body

    def sign_in(self, email: str, password: str, surface: str) -> None:
        code, body = self.call("POST", "/auth/session",
                               json={"email": email, "password": password, "surface": surface})
        if code != 201:
            raise SystemExit(f"sign-in failed for {email}: {code} {body}")

    def sign_out(self) -> None:
        self.call("DELETE", "/auth/session")


# ── the phone's compressor, in Python ──────────────────────────────────────
def camera_photo(seed: int) -> bytes:
    """A 3,000 x 2,250 'camera' JPEG: a gradient with noise, seeded, so every
    photograph has its own bytes and hash."""
    from PIL import Image, ImageDraw

    rnd = random.Random(seed)
    img = Image.new("RGB", (3000, 2250))
    draw = ImageDraw.Draw(img)
    for y in range(0, 2250, 6):
        shade = (40 + y % 120, 60 + (y * 3) % 140, 90 + rnd.randint(0, 60))
        draw.rectangle([0, y, 3000, y + 6], fill=shade)
    for _ in range(600):
        x, y = rnd.randint(0, 2990), rnd.randint(0, 2240)
        draw.rectangle([x, y, x + 8, y + 8], fill=(rnd.randint(0, 255),) * 3)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    return out.getvalue()


def compress_like_the_phone(raw: bytes, *, ceiling: int = 100 * 1024, floor: int = 70 * 1024) -> bytes:
    """Long edge 1,600 px, then quality from 92 down until <= 100 KB. Never
    refuses: the smallest result is kept (PO: a photo is never rejected)."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    scale = min(1.0, 1600 / max(img.size))
    if scale < 1.0:
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)))
    best = None
    for quality in range(92, 20, -4):
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        data = out.getvalue()
        best = data
        if len(data) <= ceiling:
            return data
    return best  # the smallest it could make — sent anyway; the server shrinks it


# ── one job ────────────────────────────────────────────────────────────────
FIX = {"lat": "29.560100", "lng": "-95.807200"}


def location(accuracy: float) -> dict:
    return {**FIX, "accuracy_m": str(accuracy), "fix_at": now()}


def build_items(bundle: dict, readings: list[dict], token: str, accuracy: float, prefix: str,
                photos: dict, outcome: str = "passed") -> tuple[list[dict], list[dict]]:
    """(data page items, the close) — every item carries the captor's token,
    its capture time and a location fix."""
    items: list[dict] = []
    n = 0

    def add(kind: str, payload: dict) -> None:
        nonlocal n
        n += 1
        items.append({"key": f"{prefix}-{n:04d}", "kind": kind, "seq": n, "captured_at": now(),
                      "capture_token": token, "location": location(accuracy), "payload": payload})

    for row in bundle.get("safety") or []:
        if not row.get("ticked_at"):
            add("safety_tick", {"safety_id": row["id"]})
    for row in bundle.get("tasks") or []:
        if not row.get("ticked_at"):
            add("task_tick", {"task_id": row["id"]})
    for row in readings:
        if row.get("kind") == "text":
            add("reading", {"reading_id": row["id"], "value_text": "W-5000-N"})
        elif row.get("value") is None:
            add("reading", {"reading_id": row["id"], "value": READING["value"], "unit": row["unit_of_measure"]})
    for row in bundle.get("materials") or []:
        add("material", {"material_id": row["id"], "used_qty": row["planned_qty"]})
    owners = [("task_id", r) for r in bundle.get("tasks") or [] if r.get("photo_required")]
    owners += [("reading_id", r) for r in readings if r.get("photo_required")]
    for field, row in owners:
        data = compress_like_the_phone(camera_photo(hash(row["id"]) & 0xFFFF))
        pid = str(uuid.uuid4())
        photos[pid] = data
        add("photo", {"photo_id": pid, "sha256": hashlib.sha256(data).hexdigest(), field: row["id"]})
    close = {"key": f"{prefix}-close", "kind": "close", "seq": n + 1, "captured_at": now(),
             "capture_token": token, "location": location(accuracy),
             "payload": {"outcome": outcome}}
    return items, [close]


def send_pages(api: Api, order_id: str, items: list[dict], *, replay: bool = False) -> dict:
    """Pages of <= 200; each page saved on arrival. Returns photo_id -> link."""
    links: dict[str, str] = {}
    for start in range(0, len(items), PAGE):
        page = items[start:start + PAGE]
        for attempt in (1, 2) if replay else (1,):
            code, body = api.call("POST", f"/work/mobile/jobs/{order_id}/sync", json={"items": page})
            if code != 200:
                raise SystemExit(f"sync failed: {code} {body}")
            acked = set(body.get("acknowledged") or [])
            missing = [i["key"] for i in page if i["key"] not in acked]
            counts = {k: body.get(k) for k in ("accepted", "duplicate", "held_for_review", "refused")}
            print(f"      page {start // PAGE + 1}{' (replay)' if attempt == 2 else ''}: {counts}"
                  f" · acknowledged {len(acked)}/{len(page)}")
            if missing:
                print(f"      NOT ACKNOWLEDGED: {missing}")
                for r in body["items"]:
                    if r["key"] in missing:
                        print("        ", r)
                raise SystemExit(1)
            for r in body["items"]:
                if r["kind"] == "photo" and r.get("detail") and r["detail"].get("upload_url"):
                    links[r["detail"]["photo_id"]] = r["detail"]["upload_url"]
    return links


def upload_photos(api: Api, photos: dict, links: dict) -> None:
    for pid, data in photos.items():
        code, body = api.call("PUT", f"/work/mobile/photos/{pid}", data=data,
                              headers={"Content-Type": "image/jpeg"}, quiet=True)
        state = (body or {}).get("state")
        print(f"  [{api.who}] PUT    /work/mobile/photos/{pid} -> {code} · {len(data):,} bytes · {state}")
        if code != 200:
            raise SystemExit(f"upload failed: {body}")


def complete_job(tech: Api, token: str, order_id: str, order_no: str, *, accuracy: float,
                 replay: bool, courier: Api | None = None, offline_hold: list | None = None,
                 outcome: str = "passed") -> None:
    print(f"\n── {order_no} ─────────────────────────────────────────")
    _, bundle = tech.call("GET", f"/work/mobile/jobs/{order_id}")
    readings: list[dict] = []
    page = 1
    while True:
        _, rp = tech.call("GET", f"/work/mobile/jobs/{order_id}/readings?page={page}&page_size=50")
        readings += rp["results"]
        if not rp.get("next"):
            break
        page = rp["next"]
    tech.call("POST", f"/work/mobile/jobs/{order_id}/accept", json={})
    tech.call("POST", f"/work/mobile/jobs/{order_id}/acts", json={"act": "depart"})
    tech.call("POST", f"/work/mobile/jobs/{order_id}/acts", json={"act": "arrive"})
    photos: dict[str, bytes] = {}
    items, close = build_items(bundle, readings, token, accuracy, f"{order_no}-{int(time.time())}", photos,
                               outcome)
    sig = io.BytesIO()
    from PIL import Image

    Image.new("RGB", (240, 80), (255, 255, 255)).save(sig, format="PNG")
    code, body = tech.call("POST", f"/work-orders/{order_id}/signature",
                           data={"printed_name": "S. Miller", "capture_token": token,
                                 "signed_at": now()},
                           files={"file": ("signature.png", sig.getvalue(), "image/png")})
    if code != 200:
        print(f"      signature: {code} {(body or {}).get('message_key')} (one per job — a re-run meets the first)")
    if offline_hold is not None:
        # OFFLINE: nothing is sent; the items wait on the device under X's token.
        offline_hold.append((order_id, order_no, items, close, photos))
        print(f"      captured offline: {len(items) + 1} items, {len(photos)} photos — held on the device")
        return
    sender = courier or tech
    links = send_pages(sender, order_id, items, replay=replay)
    upload_photos(sender, photos, links)
    send_pages(sender, order_id, close, replay=replay)


def office_accept(office: Api, order_id: str, order_no: str) -> str:
    _, row = office.call("GET", f"/work-orders/{order_id}")
    loc = ((row or {}).get("closed") or {}).get("location")
    print(f"      office sees: state={row.get('state')} photos_uploading={row.get('photos_uploading')}"
          f" location={loc}")
    code, body = office.call("POST", f"/work-orders/{order_id}/accept", json={})
    _, after = office.call("GET", f"/work-orders/{order_id}", quiet=True)
    accepted = bool((after or {}).get("accepted"))
    print(f"   {order_no}: accept -> {code}; final state={after.get('state')} accepted={accepted}"
          + ("" if code == 200 else f" · {body}"))
    return "accepted" if accepted else f"NOT accepted ({code})"


def my_jobs(api: Api) -> list[dict]:
    jobs, cursor = {}, None
    while True:
        q = f"/work/mobile/changes?page_size=50" + (f"&cursor={cursor}" if cursor else "")
        _, feed = api.call("GET", q)
        for c in feed["changes"]:
            if c["change"] == "upsert":
                jobs[c["order_id"]] = c["job"]
            else:
                jobs.pop(c["order_id"], None)
        cursor = feed["next_cursor"]
        if not feed["has_more"]:
            return list(jobs.values())


def refusals(a, tech: Api, token: str, jobs: list[dict]) -> int:
    """`--refusals`: every refusal the contract documents, captured live on two
    of the technician's open jobs (the first is declined; the second is used
    for the photo and accept refusals and then completed normally)."""
    print("\n── refusals, captured for the contract ─────────────────────")
    first, second = jobs[0], jobs[1]
    tech.call("POST", f"/work/mobile/jobs/{first['id']}/decline", json={})
    tech.call("POST", f"/work/mobile/jobs/{first['id']}/decline", json={"reason": "Van in the shop"})
    tech.call("POST", f"/work/mobile/jobs/{first['id']}/accept", json={})
    tech.call("POST", f"/work/mobile/jobs/{second['id']}/acts", json={"act": "assign"})
    tech.call("POST", "/work/mobile/devices", json={"token": "fcm-demo-token-0001", "platform": "web"})
    tech.call("DELETE", "/work/mobile/devices", json={"token": "fcm-demo-token-0001"})
    tech.call("GET", "/work/mobile/changes?cursor=not-a-cursor")
    # A held-for-review item: a tick on the DECLINED job.
    _, bundle = tech.call("GET", f"/work/mobile/jobs/{first['id']}")
    task = (bundle.get("tasks") or [{}])[0]
    tech.call("POST", f"/work/mobile/jobs/{first['id']}/sync", json={"items": [{
        "key": f"refusal-{int(time.time())}", "kind": "task_tick", "seq": 1, "captured_at": now(),
        "capture_token": token, "location": location(9), "payload": {"task_id": task.get("id")}}]})
    # The photo refusals and the accept hold, on the second job.
    tech.call("POST", f"/work/mobile/jobs/{second['id']}/accept", json={})
    _, b2 = tech.call("GET", f"/work/mobile/jobs/{second['id']}")
    readings = b2.get("readings") or []
    photos: dict[str, bytes] = {}
    items, close = build_items(b2, readings, token, 9, f"refusal2-{int(time.time())}", photos)
    send_pages(tech, second["id"], items)
    send_pages(tech, second["id"], close)
    pid, data = next(iter(photos.items()))
    tech.call("PUT", f"/work/mobile/photos/{pid}", data=data[:-500], headers={"Content-Type": "image/jpeg"})
    tech.call("PUT", f"/work/mobile/photos/{pid}", data=b"not an image at all",
              headers={"Content-Type": "image/jpeg"})
    office = Api(a.base, a.tenant, "Dana")
    office.sign_in(a.office_email, a.office_password, "web")
    office.call("GET", f"/work-orders/{second['id']}")
    office.call("POST", f"/work-orders/{second['id']}/accept", json={})
    office.call("GET", "/work/photo-links/stale")
    upload_photos(tech, photos, {})
    office.call("POST", f"/work-orders/{second['id']}/accept", json={})
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="http://127.0.0.1:8063")
    p.add_argument("--tenant", default="brazosbend")
    p.add_argument("--tech-email", default="r.patel@sample.test")
    p.add_argument("--tech-password", required=True)
    p.add_argument("--second-tech-email", default="m.chen@sample.test")
    p.add_argument("--office-email", default="dana@brazosbendutilities.com")
    p.add_argument("--office-password", required=True)
    p.add_argument("--order", action="append", default=[])
    p.add_argument("--all-mine", action="store_true")
    p.add_argument("--scenario", choices=["normal", "shared"], default="normal")
    p.add_argument("--fix-accuracy", type=float, default=8.0)
    p.add_argument("--replay", action="store_true")
    p.add_argument("--capture")
    p.add_argument("--refusals", action="store_true",
                   help="capture every documented refusal on the first two chosen jobs")
    p.add_argument("--closed-at", help="the handset's time for every item, ISO-8601, in the past")
    p.add_argument("--reading-value", default="48221",
                   help="the value given to every numeric reading (the same-day proof)")
    p.add_argument("--no-accept", action="store_true",
                   help="stop after the technician's close; the office accepts in its own browser")
    p.add_argument("--outcome", default="passed",
                   choices=["passed", "partly_done", "failed", "waiting_on_someone_else"])
    a = p.parse_args()
    READING["value"] = a.reading_value
    if a.closed_at:
        CLOCK["at"] = datetime.fromisoformat(a.closed_at.replace("Z", "+00:00"))

    tech = Api(a.base, a.tenant, "R. Patel" if "patel" in a.tech_email else a.tech_email)
    tech.sign_in(a.tech_email, a.tech_password, "mobile")
    _, tok = tech.call("POST", "/work/mobile/capture-token", json={"device_label": "Tablet 3"})
    token = tok["capture_token"]
    jobs = my_jobs(tech)
    open_jobs = [j for j in jobs if j["state"] != "completed"]
    chosen = [j for j in open_jobs if a.all_mine or j["order_no"] in a.order]
    print(f"\n{tech.who}: {len(jobs)} job(s) in the feed, {len(open_jobs)} open, {len(chosen)} chosen:"
          f" {[j['order_no'] for j in chosen]}")
    if not chosen:
        return 1

    if a.refusals:
        code = refusals(a, tech, token, chosen)
        if a.capture:
            with open(a.capture, "w") as fh:
                json.dump(LOG, fh, indent=1, default=str)
        return code

    held: list | None = [] if a.scenario == "shared" else None
    for job in chosen:
        complete_job(tech, token, job["id"], job["order_no"], accuracy=a.fix_accuracy,
                     replay=a.replay, offline_hold=held, outcome=a.outcome)

    if held is not None:
        print("\n── shared tablet: X signs out OFFLINE, Y signs in ──────────────")
        tech.sign_out()
        y = Api(a.base, a.tenant, "M. Chen")
        y.sign_in(a.second_tech_email, a.tech_password, "mobile")
        y_jobs = my_jobs(y)
        leaked = {j["order_no"] for j in y_jobs} & {h[1] for h in held}
        print(f"      Y's feed: {[j['order_no'] for j in y_jobs]} · X's jobs visible to Y: {sorted(leaked) or 'none'}")
        for order_id, order_no, _items, _close, _ph in held:
            code, _ = y.call("GET", f"/work/mobile/jobs/{order_id}")
            print(f"      Y opens X's {order_no}: {code} (404 = not visible)")
        print("      signal returns: the device sends X's held work under Y's session, with X's token")
        for order_id, order_no, items, close, photos in held:
            links = send_pages(y, order_id, items)
            upload_photos(y, photos, links)
            send_pages(y, order_id, close)
        y.sign_out()
        tech = Api(a.base, a.tenant, "R. Patel")
        tech.sign_in(a.tech_email, a.tech_password, "mobile")
        _, rec = tech.call("GET", "/work/mobile/reconciliation")
        print(f"      X's reconciliation (server side): {rec}")

    if a.no_accept:
        print("\nFINAL (closed by the technician; the office accepts in its browser):")
        for j in chosen:
            print(f"   {j['order_no']}: closed")
        if a.capture:
            with open(a.capture, "w") as fh:
                json.dump(LOG, fh, indent=1, default=str)
        return 0
    office = Api(a.base, a.tenant, "Dana")
    office.sign_in(a.office_email, a.office_password, "web")
    print("\n── the office accepts ──────────────────────────────────────")
    outcomes = {j["order_no"]: office_accept(office, j["id"], j["order_no"]) for j in chosen}
    print("\nFINAL:")
    for order_no, outcome in outcomes.items():
        print(f"   {order_no}: {outcome}")
    if a.capture:
        with open(a.capture, "w") as fh:
            json.dump(LOG, fh, indent=1, default=str)
    return 0 if all(v == "accepted" for v in outcomes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

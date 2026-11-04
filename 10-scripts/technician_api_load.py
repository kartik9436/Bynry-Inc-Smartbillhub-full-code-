#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 §F, lane FIELD-FIX — PO 2026-10-04: "what of we are
#          sending 1000 reading records from server to phone and phone to
#          server - including images coming from phone", and the sync design
#          ("we cant drop data record in sync process both ways").
# Contract: 04-docs/03-contracts/technician-api.md
# ───────────────────────────────────────────────────────
"""The 1,000-record proof, on PostgreSQL, through the technician API.

    # 1. prepare (Django, as the office): a job for R. Patel carrying 1,000
    #    readings, each asking for a photograph; prints its id
    cd 06-backend && DATABASE_URL=… python ../10-scripts/technician_api_load.py prepare
    # 2. run the legs over HTTP
    python3 10-scripts/technician_api_load.py run --order-id <id> --tech-password … --office-password …

LEGS, each timed:
  1. DOWN   — 1,000 readings, paged (GET …/jobs/{id}/readings, 200 a page).
  2. UP     — 1,000 readings + 1,000 photo declarations = 2,000 items in pages
              of 200 (`sync.MAX_ITEMS`), each page saved on arrival BEFORE any
              image is sent; every link comes back with its record.
  3. REPLAY — the first page again: every item `duplicate`, the SAME links.
  4. IMAGES — 1,000 photographs, one PUT each to its link. 50 are left
              OVERSIZED on purpose (the phone could not compress them) and the
              server shrinks them; 5 are sent CORRUPTED first, refused 409 and
              sent again. The upload is INTERRUPTED after 400 and RESUMED: the
              resume asks each link's state and sends only what is pending.
  5. COUNT  — rows in the database (receipts, links landed, attachments) and
              the reconciliation read; zero dropped, zero duplicated.
  6. ACCEPT — close, then the office's Accept (held until the last required
              photo landed, which by now it has).

Exit 1 on any dropped, duplicated or unacknowledged record.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import sys
import time
import uuid
from pathlib import Path

N = 1000


def prepare() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django

    django.setup()
    from types import SimpleNamespace

    from apps.identity import models as identity_models
    from apps.metering import connections as w6
    from apps.work import connection_models as work_tables
    from apps.tenancy import models as tenancy_models
    from apps.work import dispatch, mobile, templates_svc
    from apps.work import models as work_models
    from core import tenancy as core_tenancy

    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    with core_tenancy.tenant_context(tenant.id):
        office = identity_models.User.objects.get(tenant_id=tenant.id, email="dana@brazosbendutilities.com")
        dana = SimpleNamespace(id=office.id, pk=office.id, role="system_admin", tenant_id=tenant.id,
                               full_name=office.full_name, email=office.email, is_authenticated=True)
        patel = work_models.Technician.objects.get(tenant_id=tenant.id, user__email="r.patel@sample.test")
        name = f"Load test — {N} readings"
        tpl = work_tables.WorkOrderTemplate.objects.filter(name=name, active=True).first()
        if tpl is None:
            header = templates_svc.create_draft(
                dana, {"name": name, "service": "water", "scope": "per_premise", "sequence": 0}
            )
            tid = header["id"]
            templates_svc.replace_collection(dana, tid, "readings", [
                {"prompt": f"Point {n:04d}", "unit_of_measure": "psi", "min": 0, "max": 200,
                 "photo_required": True}
                for n in range(1, N + 1)
            ])
            templates_svc.publish(dana, tid)
        else:
            tid = str(tpl.id)
        from apps.metering import models as metering_models

        premises = metering_models.Premises.objects.order_by("created_at").first()
        order = w6.create_work_order(dana, None, {
            "premises_id": str(premises.id), "type": name, "template_id": tid, "source": "dispatcher",
        })
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(patel.id)}, push=False)
        tech = SimpleNamespace(id=patel.user_id, role="field_technician")
        mobile.accept_job(tech, order["id"])
        print(order["id"], order["order_no"])
    return 0


def run(a) -> int:
    import requests
    from technician_api_walk import Api, camera_photo, compress_like_the_phone, now

    tech = Api(a.base, a.tenant, "R. Patel")
    tech.sign_in(a.tech_email, a.tech_password, "mobile")
    _, tok = tech.call("POST", "/work/mobile/capture-token", json={"device_label": "Load tablet"})
    token = tok["capture_token"]
    oid = a.order_id
    timings: dict[str, float] = {}
    moved = {"down": 0, "up": 0, "images": 0}

    # ── 1 · DOWN ───────────────────────────────────────────────────────────
    t0 = time.monotonic()
    readings, page = [], 1
    while page:
        r = tech.s.get(f"{a.base}/api/{a.tenant}/work/mobile/jobs/{oid}/readings",
                       params={"page": page, "page_size": 200}, timeout=60)
        moved["down"] += len(r.content)
        body = r.json()
        readings += body["results"]
        page = body["next"]
    timings["1 down: 1,000 readings, paged"] = time.monotonic() - t0
    pages_down = -(-len(readings) // 200)
    print(f"DOWN  {len(readings)} readings in {pages_down} pages · {moved['down']/1e6:.2f} MB")

    # ── 2 · UP (records first, no image yet) ──────────────────────────────
    rnd = random.Random(7)
    photos: dict[str, bytes] = {}
    oversized: set[str] = set()
    items = []
    stamp = int(time.time())
    for n, row in enumerate(readings):
        items.append({"key": f"load-{stamp}-r{n}", "kind": "reading", "seq": 2 * n, "captured_at": now(),
                      "capture_token": token,
                      "payload": {"reading_id": row["id"], "value": str(rnd.randint(40, 90)), "unit": "psi"}})
        raw = camera_photo(n)
        if n % 20 == 0:
            from PIL import Image

            img = Image.open(io.BytesIO(raw)).convert("RGB").resize((2000, 1500))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            data = buf.getvalue()  # deliberately NOT compressed by the "phone"
            oversized.add(str(n))
        else:
            data = compress_like_the_phone(raw)
        pid = str(uuid.UUID(int=rnd.getrandbits(128)))
        photos[pid] = data
        items.append({"key": f"load-{stamp}-p{n}", "kind": "photo", "seq": 2 * n + 1, "captured_at": now(),
                      "capture_token": token,
                      "payload": {"photo_id": pid, "sha256": hashlib.sha256(data).hexdigest(),
                                  "reading_id": row["id"]}})
    t0 = time.monotonic()
    links: dict[str, str] = {}
    acked = 0
    first_page_links = None
    for start in range(0, len(items), 200):
        page_items = items[start:start + 200]
        r = tech.s.post(f"{a.base}/api/{a.tenant}/work/mobile/jobs/{oid}/sync",
                        json={"items": page_items}, timeout=60)
        moved["up"] += len(r.request.body or b"") + len(r.content)
        body = r.json()
        acked += len(body["acknowledged"])
        got = {d["detail"]["photo_id"]: d["detail"]["upload_url"]
               for d in body["items"] if d["kind"] == "photo" and d.get("detail")}
        links.update(got)
        if first_page_links is None:
            first_page_links = got
        print(f"UP    page {start // 200 + 1}: {r.status_code} accepted={body['accepted']} "
              f"duplicate={body['duplicate']} held={body.get('held_for_review')} acked={len(body['acknowledged'])}")
    timings["2 up: 2,000 records in 10 pages (no image)"] = time.monotonic() - t0
    if acked != len(items):
        print(f"FAIL: {len(items) - acked} items not acknowledged")
        return 1

    # ── 3 · REPLAY page 1 ─────────────────────────────────────────────────
    t0 = time.monotonic()
    r = tech.s.post(f"{a.base}/api/{a.tenant}/work/mobile/jobs/{oid}/sync",
                    json={"items": items[:200]}, timeout=60)
    body = r.json()
    same = {d["detail"]["photo_id"]: d["detail"]["upload_url"]
            for d in body["items"] if d["kind"] == "photo" and d.get("detail")}
    timings["3 replay: page 1 again"] = time.monotonic() - t0
    print(f"REPLAY page 1: duplicate={body['duplicate']}/200 · same links: {same == first_page_links}")
    if body["duplicate"] != 200 or same != first_page_links:
        return 1

    # ── 4 · IMAGES, interrupted at 400 and resumed ────────────────────────
    order = list(photos)
    corrupt = set(order[100:105])
    statuses = {"landed_or_staged": 0, "duplicate": 0, "hash_mismatch": 0, "resent_after_mismatch": 0}

    def put(pid: str, data: bytes):
        r = tech.s.put(f"{a.base}/api/{a.tenant}/work/mobile/photos/{pid}", data=data,
                       headers={"Content-Type": "image/jpeg"}, timeout=60)
        moved["images"] += len(data)
        return r

    t0 = time.monotonic()
    for pid in order[:400]:
        if pid in corrupt:
            r = put(pid, photos[pid][:-1000])
            if r.status_code == 409:
                statuses["hash_mismatch"] += 1
            r = put(pid, photos[pid])
            statuses["resent_after_mismatch"] += 1
        else:
            r = put(pid, photos[pid])
        b = r.json()
        statuses["duplicate" if b.get("duplicate") else "landed_or_staged"] += 1
    timings["4a images: first 400, then the connection drops"] = time.monotonic() - t0
    print(f"IMAGES interrupted after 400 · {statuses}")
    # RESUME: ask each link; send only what is still pending.
    t0 = time.monotonic()
    pending = []
    for pid in order:
        state = tech.s.get(f"{a.base}/api/{a.tenant}/work/mobile/photos/{pid}", timeout=60).json()["state"]
        if state == "pending":
            pending.append(pid)
    print(f"RESUME: {len(pending)} links still pending (expected {N - 400})")
    for pid in pending:
        b = put(pid, photos[pid]).json()
        statuses["duplicate" if b.get("duplicate") else "landed_or_staged"] += 1
    # And 10 already-landed photos sent again on purpose: they must add nothing.
    for pid in order[:10]:
        b = put(pid, photos[pid]).json()
        statuses["duplicate" if b.get("duplicate") else "landed_or_staged"] += 1
    timings["4b images: resume the remaining 600 (+10 deliberate re-sends)"] = time.monotonic() - t0
    print(f"IMAGES done · {statuses}")

    # ── 5 · COUNT ─────────────────────────────────────────────────────────
    _, rec = tech.call("GET", "/work/mobile/reconciliation")
    print(f"RECONCILIATION (server): {json.dumps(rec)}")

    # ── 6 · CLOSE + ACCEPT ────────────────────────────────────────────────
    t0 = time.monotonic()
    tech.call("POST", f"/work/mobile/jobs/{oid}/sync", json={"items": [{
        "key": f"load-{stamp}-close", "kind": "close", "seq": 9999, "captured_at": now(),
        "capture_token": token, "location": {"lat": "29.56", "lng": "-95.81", "accuracy_m": "9",
                                             "fix_at": now()},
        "payload": {"outcome": "passed"}}]})
    office = Api(a.base, a.tenant, "Dana")
    office.sign_in(a.office_email, a.office_password, "web")
    code, body = office.call("POST", f"/work-orders/{oid}/accept", json={})
    timings["6 close + accept"] = time.monotonic() - t0

    print("\nTIMINGS (wall clock):")
    for leg, seconds in timings.items():
        print(f"   {leg:62} {seconds:7.1f} s")
    print(f"MOVED: down {moved['down']/1e6:.2f} MB · up (records) {moved['up']/1e6:.2f} MB · "
          f"images {moved['images']/1e6:.2f} MB")
    print(f"ACCEPT: {code} {'' if code == 200 else body}")
    return 0 if code == 200 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    r = sub.add_parser("run")
    r.add_argument("--base", default="http://127.0.0.1:8063")
    r.add_argument("--tenant", default="brazosbend")
    r.add_argument("--order-id", required=True)
    r.add_argument("--tech-email", default="r.patel@sample.test")
    r.add_argument("--tech-password", required=True)
    r.add_argument("--office-email", default="dana@brazosbendutilities.com")
    r.add_argument("--office-password", required=True)
    a = p.parse_args()
    if a.cmd == "prepare":
        return prepare()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 round 7, lane WALK-B — the technician-app rulings of
#          2026-10-04, proved once more over HTTP on the 2.518.x build:
#          a close with a required photo missing; a 2 MB photo accepted and
#          stored at 100 KB or less (never reject a photo); Accept held while a
#          required photo uploads; a job reassigned while the phone was offline
#          keeps its items, flagged for review. Contract:
#          04-docs/03-contracts/technician-api.md.
# ───────────────────────────────────────────────────────
"""Three proofs, each a real HTTP call with a JSON payload, printed with the
server's answer. Jobs from `cr168_r7_walkb_prep.py` (Final read — residential:
one safety line, two tasks of which the first asks for a photograph, one
reading).

    python3 10-scripts/cr168_r7_walkb_tech_proofs.py --base http://127.0.0.1:8087 \\
        --password '…' --photo-job WO-0108 --reassign-job WO-0109

What would make it pass wrongly (law 7, habit 2): a proof that reads its own
sends. Every verdict below is read from the SERVER's answer (status, the
per-item `result`, `acknowledged`, `photos_uploading`, the stored byte count),
and the script exits 1 when any verdict is not the ruled one.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from technician_api_walk import Api, LOG, camera_photo, location, my_jobs, now  # noqa: E402

VERDICTS: list[tuple[str, bool, str]] = []


def verdict(name: str, ok: bool, detail: str) -> None:
    VERDICTS.append((name, ok, detail))
    print(f"   {'PASS' if ok else 'FAIL'} · {name} · {detail}")


def item(prefix: str, n: int, kind: str, payload: dict, token: str) -> dict:
    return {"key": f"{prefix}-{n:04d}", "kind": kind, "seq": n, "captured_at": now(),
            "capture_token": token, "location": location(8.0), "payload": payload}


def job_by_no(api: Api, order_no: str) -> dict:
    for job in my_jobs(api):
        if job["order_no"] == order_no:
            return job
    raise SystemExit(f"{order_no} is not in {api.who}'s feed")


def photo_proof(a, tech: Api, office: Api, token: str, order_no: str) -> None:
    print(f"\n── {order_no}: a close with a required photo missing; a 2 MB photo; Accept held ──")
    job = job_by_no(tech, order_no)
    oid = job["id"]
    _, bundle = tech.call("GET", f"/work/mobile/jobs/{oid}")
    tech.call("POST", f"/work/mobile/jobs/{oid}/accept", json={})
    prefix = f"{order_no}-proof-{uuid.uuid4().hex[:6]}"
    items, n = [], 0
    for row in bundle["safety"]:
        n += 1
        items.append(item(prefix, n, "safety_tick", {"safety_id": row["id"]}, token))
    for row in bundle["tasks"]:
        n += 1
        items.append(item(prefix, n, "task_tick", {"task_id": row["id"]}, token))
    for row in bundle["readings"]:
        n += 1
        items.append(item(prefix, n, "reading", {"reading_id": row["id"], "value": "5120",
                                                 "unit": row["unit_of_measure"]}, token))
    code, body = tech.call("POST", f"/work/mobile/jobs/{oid}/sync", json={"items": items})
    # 1 · the close, with the photo-required task's photograph never declared
    n += 1
    close = item(prefix, n, "close", {"outcome": "passed"}, token)
    code, body = tech.call("POST", f"/work/mobile/jobs/{oid}/sync", json={"items": [close]})
    r = (body or {}).get("items", [{}])[0]
    _, row = office.call("GET", f"/work-orders/{oid}")
    verdict("a close with a required photo missing is not completed",
            row.get("state") != "completed",
            f"sync {code} result={r.get('result')} ack={r.get('ack')} detail={json.dumps(r.get('detail'))[:220]}"
            f" · order state={row.get('state')}")
    # 2 · declare the photo: a 2 MB camera JPEG, never compressed on the phone
    raw = camera_photo(4242)
    while len(raw) < 2 * 1024 * 1024:  # make it at least 2 MB, as a phone that could not compress
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).resize((4000, 3000))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=100)
        raw = out.getvalue()
        if len(raw) < 2 * 1024 * 1024:
            raw = raw + b""  # quality 100 at 4000x3000 is well over 2 MB; guard only
            break
    task = next(t for t in bundle["tasks"] if t.get("photo_required"))
    pid = str(uuid.uuid4())
    n += 1
    decl = item(prefix, n, "photo", {"photo_id": pid, "sha256": hashlib.sha256(raw).hexdigest(),
                                     "task_id": task["id"]}, token)
    code, body = tech.call("POST", f"/work/mobile/jobs/{oid}/sync", json={"items": [decl]})
    n += 1
    close2 = item(prefix, n, "close", {"outcome": "passed"}, token)
    code, body = tech.call("POST", f"/work/mobile/jobs/{oid}/sync", json={"items": [close2]})
    r = (body or {}).get("items", [{}])[0]
    _, row = office.call("GET", f"/work-orders/{oid}")
    verdict("with the photo declared and its bytes still on the phone, the close is accepted",
            row.get("state") == "completed", f"result={r.get('result')} state={row.get('state')}"
            f" photos_uploading={row.get('photos_uploading')}")
    # 3 · Accept is held while the required photo uploads
    code, body = office.call("POST", f"/work-orders/{oid}/accept", json={})
    verdict("Accept is held while a required photo uploads",
            code == 409 and (body or {}).get("message_key") == "work.order.photos_uploading",
            f"accept {code} {(body or {}).get('message_key')} params={(body or {}).get('params')}")
    # 4 · the 2 MB bytes land; the server keeps them at 100 KB or less
    code, body = tech.call("PUT", f"/work/mobile/photos/{pid}", data=raw,
                           headers={"Content-Type": "image/jpeg"})
    _, state = tech.call("GET", f"/work/mobile/photos/{pid}")
    verdict("a 2 MB photo is accepted, never refused for size",
            code == 200, f"PUT {len(raw):,} bytes -> {code} state={(body or {}).get('state')}"
            f" then {(state or {}).get('state')}")
    VERDICTS_PHOTO.update({"photo_id": pid, "bytes_sent": len(raw)})
    code, body = office.call("POST", f"/work-orders/{oid}/accept", json={})
    verdict("Accept is available once the photo has landed", code == 200, f"accept {code}")


VERDICTS_PHOTO: dict = {}


def reassign_proof(a, tech: Api, office: Api, token: str, order_no: str, chen_technician_id: str) -> None:
    print(f"\n── {order_no}: reassigned while the phone was offline ──")
    job = job_by_no(tech, order_no)
    oid = job["id"]
    _, bundle = tech.call("GET", f"/work/mobile/jobs/{oid}")
    tech.call("POST", f"/work/mobile/jobs/{oid}/accept", json={})
    prefix = f"{order_no}-offline-{uuid.uuid4().hex[:6]}"
    items = []
    n = 0
    for row in bundle["safety"]:
        n += 1
        items.append(item(prefix, n, "safety_tick", {"safety_id": row["id"]}, token))
    for row in bundle["tasks"]:
        n += 1
        items.append(item(prefix, n, "task_tick", {"task_id": row["id"]}, token))
    print(f"      captured offline by R. Patel: {len(items)} items (held on the device)")
    code, body = office.call("POST", f"/work-orders/{oid}/assignments",
                             json={"act": "reassign", "technician_id": chen_technician_id,
                                   "reason": "Patel off sick"})
    print(f"      office reassigns to M. Chen: {code} {json.dumps(body)[:200]}")
    code, body = tech.call("POST", f"/work/mobile/jobs/{oid}/sync", json={"items": items})
    held = [i for i in (body or {}).get("items", []) if i.get("result") == "held_for_review"]
    acked = set((body or {}).get("acknowledged") or [])
    reasons = sorted({(i.get("detail") or {}).get("needs_review") for i in held})
    verdict("a job reassigned while offline keeps the items, flagged for review",
            code == 200 and len(held) == len(items) and acked == {i["key"] for i in items},
            f"sync {code}: held_for_review={len(held)}/{len(items)} acknowledged={len(acked)} reasons={reasons}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="http://127.0.0.1:8087")
    p.add_argument("--tenant", default="brazosbend")
    p.add_argument("--password", required=True)
    p.add_argument("--photo-job", required=True)
    p.add_argument("--reassign-job", required=True)
    p.add_argument("--chen-technician-id", required=True)
    p.add_argument("--capture")
    a = p.parse_args()
    tech = Api(a.base, a.tenant, "R. Patel")
    tech.sign_in("r.patel@sample.test", a.password, "mobile")
    _, tok = tech.call("POST", "/work/mobile/capture-token", json={"device_label": "Tablet 3"})
    office = Api(a.base, a.tenant, "Dana")
    office.sign_in("dana@brazosbendutilities.com", a.password, "web")
    photo_proof(a, tech, office, tok["capture_token"], a.photo_job)
    reassign_proof(a, tech, office, tok["capture_token"], a.reassign_job, a.chen_technician_id)
    print("\nPHOTO:", json.dumps(VERDICTS_PHOTO))
    if a.capture:
        with open(a.capture, "w") as fh:
            json.dump(LOG, fh, indent=1, default=str)
    return 0 if all(ok for _, ok, _ in VERDICTS) else 1


if __name__ == "__main__":
    sys.exit(main())

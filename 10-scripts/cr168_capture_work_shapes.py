#!/usr/bin/env python3
"""CR-168-BRC10 lane SHAPE-SWEEP — record what the REAL Work server sends.

⚠ **WHY THIS EXISTS (`DEF-WRK-9600`, `DEF-WRK-9601`).** On 2026-10-04 the
rebuilt order page crashed on every job with a unit, and *Put on hold* offered
no reason, and **both passed every test**: the server lane typed its test
fixture to agree with the server and the screen lane typed its fixture to agree
with the screen. Nothing ever put the server's reply in front of the screen.
So the screens' fixtures for Work are not WRITTEN — they are RECORDED, by this
script, from `manage.py runserver` on PostgreSQL, and `tsc` checks every one of
them against the TypeScript type the screen reads through
(`07-frontend/src/features/work/recordedServerShapes.typecheck.ts`), and the
screens render them (`recordedServerShapes.dom.test.tsx`). **Never hand-edit a
file this script writes; re-run it** (CR-168 §7, *"Fixtures come from the
server"*).

How to record (a SCRATCH database, never a real tenant):

    cd 06-backend
    export DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
           DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    python manage.py migrate && python manage.py seed_demo \\
      && python manage.py load_sample_data --tenant brazosbend
    python manage.py shell < ../10-scripts/cr168_order_page_seed.py
    python manage.py shell < ../10-scripts/cr168_orders_list_walk_prep.py
    python manage.py runserver 127.0.0.1:8461 --noreload &
    cd .. && /tmp/venv_a5c/bin/python 10-scripts/cr168_capture_work_shapes.py --prepare

`--only <prefix>[,<prefix>…]` (lane CREWS, CR-168 round 4) still performs every read, so
the ids later reads need are found the same way, but WRITES only the
recordings whose name starts with the prefix and MERGES them into the existing
`manifest.json` — so one lane can record the reads it needs without rewriting
another lane's 49 recordings from a different database (whose ids and dates
would differ and turn their value assertions red).

`--prepare` makes the ONE write this script ever makes, and only when no job
is held: it puts the first scheduled job on hold through the real
`POST /work-orders/{id}/hold` with the tenant's first hold reason, so the
recording carries a held row (the shape *Put on hold* and the list's hold
line read). Without the flag the script only reads.

It signs in as the sample System Admin, reads every Work endpoint the back
office's screens read, finds the ids it needs from the lists it has already
read (by the numbers a person reads, never a literal uuid), and writes one
`<name>.json` per read plus `manifest.json` (path, status, row count) into
`07-frontend/src/features/work/__fixtures__/server/`. It exits 1 if any read
answers other than 200, or if an order with a unit, a completed order with a
signature, or a held order cannot be found — **a recording that silently
lacks the case that crashed is the fixture problem again**.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

BASE = os.environ.get("BASE", "http://127.0.0.1:8461").rstrip("/")
TENANT = os.environ.get("TENANT", "brazosbend")
EMAIL = os.environ.get("EMAIL", "dana@brazosbendutilities.com")
PASSWORD = os.environ.get("PASSWORD", "S3cure!passw0rd")
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("OUT", ROOT / "07-frontend/src/features/work/__fixtures__/server"))

session = requests.Session()
manifest: list[dict] = []
problems: list[str] = []


def api(path: str) -> str:
    return f"{BASE}/api/{TENANT}/{path.lstrip('/')}"


def sign_in() -> None:
    r = session.post(api("auth/session"), json={"email": EMAIL, "password": PASSWORD})
    if r.status_code >= 300:
        sys.exit(f"sign-in refused: {r.status_code} {r.text[:200]}")
    token = session.cookies.get("csrftoken")
    if token:
        session.headers["X-CSRFToken"] = token


def rows_of(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "rows", "candidates", "pins"):
            if isinstance(data.get(key), list):
                return data[key]
    return None


ONLY = (
    sys.argv[sys.argv.index("--only") + 1]
    if "--only" in sys.argv[1:] and sys.argv.index("--only") + 1 < len(sys.argv)
    else None
)


def wanted(name: str) -> bool:
    """`--only a.,b` — comma-separated name prefixes."""
    return ONLY is None or any(name.startswith(one) for one in ONLY.split(",") if one)


def record(name: str, path: str):
    r = session.get(api(path))
    entry = {"name": name, "path": path, "status": r.status_code}
    if r.status_code not in (200, 204):
        problems.append(f"{name}: GET {path} answered {r.status_code} {r.text[:160]}")
        manifest.append(entry)
        return None
    # An empty 200/204 is recorded as `null` — the client reads it as "no body"
    # (`/signature` on a job nobody signed answers exactly that).
    data = r.json() if r.content.strip() else None
    entry["empty_body"] = data is None
    rows = rows_of(data)
    entry["rows"] = None if rows is None else len(rows)
    manifest.append(entry)
    if not wanted(name):
        return data
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data


def first(rows, predicate, why: str):
    for row in rows or []:
        if predicate(row):
            return row
    problems.append(f"no row found: {why}")
    return None


def prepare() -> None:
    """Hold one job, through the real endpoint, if none is held yet."""
    page = session.get(api("work-orders?page=1&per=100")).json()
    rows = rows_of(page) or []
    if any(r.get("dispatch_state") == "on_hold" for r in rows):
        return
    target = next((r for r in rows if r.get("dispatch_state") == "scheduled"), None)
    reasons = rows_of(session.get(api("work/hold-reasons")).json()) or []
    if target is None or not reasons:
        problems.append("--prepare: no scheduled job or no hold reason to hold it with")
        return
    r = session.post(api(f"work-orders/{target['id']}/hold"),
                     json={"reason_code": reasons[0]["code"], "note": "recorded by the shape sweep"})
    print(f"--prepare: held {target.get('order_no')} -> {r.status_code}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sign_in()
    if "--prepare" in sys.argv[1:]:
        prepare()

    # ── Orders (1·1), Approvals (2·1), Map (3·1) ───────────────────────────
    orders = record("work-orders.list", "work-orders?page=1&per=100")
    # The list's default is the open work; the completed jobs are their own
    # filter (`status=complete`, J3), and a completed job is where the
    # signature and `closed` shapes live.
    done = record("work-orders.list.complete", "work-orders?page=1&per=100&status=complete")
    record("work-orders.awaiting-approval", "work-orders/awaiting-approval?page=1&per=50")
    record("work-orders.map", "work-orders/map")
    record("work.hold-reasons", "work/hold-reasons")
    record("work.raise-options", "work/raise-options")
    record("work.kpis", "work/kpis")
    record("work.areas", "work/areas")
    # The order page also draws the utility's own work-order fields (CR-161).
    record("custom-fields.work-orders", "custom-fields?entity=work_orders&screen=WORK_DETAIL&mode=view")

    rows = (rows_of(orders) or []) + (rows_of(done) or [])
    # The three cases that have broken a screen: a job with a unit, a completed
    # job with a signature, a held job. Each is found by reading details.
    details = {}
    for row in rows:
        d = session.get(api(f"work-orders/{row['id']}")).json()
        loc = d.get("location") or {}
        if d.get("state") != "completed" and loc.get("unit"):
            # Prefer the richest open job: a unit AND an asset (WO-0041's
            # meter W-5000 from cr168_order_page_seed.py), else any unit.
            if "open" not in details or (loc.get("asset") and not details["open"][1]):
                details["open"] = (row["id"], bool(loc.get("asset")))
        if "completed" not in details and d.get("signature"):
            details["completed"] = (row["id"], True)
        if "accepted" not in details and d.get("accepted"):
            details["accepted"] = (row["id"], True)
        if "held" not in details and row.get("dispatch_state") == "on_hold":
            details["held"] = (row["id"], True)
    details = {case: oid for case, (oid, _rich) in details.items()}
    for case, why in (("open", "an open order with a unit"),
                      ("completed", "a completed order with a signature"),
                      ("held", "a held order (run with --prepare)"),
                      ("accepted", "a completed order the office accepted")):
        if case not in details:
            problems.append(f"no row found: {why}")
    for case, oid in details.items():
        record(f"work-order.{case}", f"work-orders/{oid}")
        record(f"work-order.{case}.audit", f"work-orders/{oid}/audit")
        record(f"work-order.{case}.checklist", f"work-orders/{oid}/checklist")
        record(f"work-order.{case}.attachments", f"work-orders/{oid}/attachments")
        record(f"work-order.{case}.close-readiness", f"work-orders/{oid}/close-readiness")
    for case in ("completed", "accepted"):
        if case in details:
            record(f"work-order.{case}.signature", f"work-orders/{details[case]}/signature")
    if "open" in details:
        oid = details["open"]
        record("work-order.open.edit", f"work-orders/{oid}/edit")
        record("work-order.open.candidates", f"work-orders/{oid}/candidates?page=1&per=50")

    # ── Crews (4·1), one technician (4·2) ─────────────────────────────────
    techs = record("work.crews.technicians", "work/crews?view=technicians&page=1&per=50")
    record("work.crews.crews", "work/crews?view=crews&page=1&per=50")
    record("work.crews.contractors", "work/crews?view=contractors&page=1&per=50")
    record("work.crew-directory", "work/crew-directory")
    record("work.certification-watch", "work/certification-watch")
    tech = first(rows_of(techs), lambda r: r.get("slug"), "a technician with a slug")
    if tech:
        detail = record("work.technician", f"work/technicians/{tech['slug']}")
        # SRV-3 (P3.45, P3.46) — image 32's Jobs tab and image 34's figures.
        record("work.technician.jobs", f"work/technicians/{tech['slug']}/jobs?page=1&per=50")
        record("work.technician.performance", f"work/technicians/{tech['slug']}/performance")
        # Lane CREWS (round 4): the Jobs tab's Open and Done, Performance for
        # the month the detail names, the add-crew-member picker (image 26),
        # and the two catalogues the add forms and Certifications choose from.
        slug = tech["slug"]
        record("work.technician.jobs.open", f"work/technicians/{slug}/jobs?f.state=open&page=1&per=50")
        record("work.technician.jobs.done", f"work/technicians/{slug}/jobs?f.state=done&page=1&per=50")
        month = ((detail or {}).get("this_month") or {}).get("month") or ""
        record("work.technician.performance.month", f"work/technicians/{slug}/performance?period={month}&page=1&per=50")
    record("work.technicians", "work/technicians")
    record("work.lookups.work_skills", "lookups/work_skills?page=1&per=200")
    record("work.lookups.certification_types", "lookups/certification_types?page=1&per=200")

    # ── Parts (5·1) ────────────────────────────────────────────────────────
    record("work.parts", "work/parts?page=1&per=50")
    record("work.parts.issues", "work/parts/issues?page=1&per=50")

    # ── Templates (6·1–6·3) ────────────────────────────────────────────────
    templates = record("work.templates", "work/templates?page=1&per=50")
    record("work.template-packs", "work/template-packs")
    tpl = first(rows_of(templates), lambda r: r.get("status") == "published", "a published template")
    if tpl:
        record("work.template", f"work/templates/{tpl['id']}")
        record("work.template.versions", f"work/templates/{tpl['id']}/versions")
        record("work.template.usage", f"work/templates/{tpl['id']}/usage")
        # SRV-3 (P3.28) — image 47's Audit tab, in words, paged.
        record("work.template.audit", f"work/templates/{tpl['id']}/audit?page=1&per=50")

    # ── Rules (7·1), Labour rates, Performance (8·1) ───────────────────────
    rules_list = record("work.rules", "work/rules?page=1&per=50")
    record("work.labour-rates", "work/labour-rates?page=1&per=50")
    record("work.performance", "work/performance")
    # Lane SRV-4 (round 5) — the reads lanes RULES and PERFORMANCE build on:
    # the twelve processes and the Notify step's vocabularies (P3.30), one
    # rule with `tonight` (detail only), its jobs and its audit (P3.61), the
    # Performance table paged in SQL (P5.6), the at-risk board (P5.3) and the
    # SLA settings with the warning window.
    record("work.rules.processes", "work/rules/processes")
    # A rule that has raised something, so its jobs page carries a row.
    rule = next((r for r in rows_of(rules_list) or [] if r.get("jobs_raised")), None) or first(
        rows_of(rules_list), lambda r: r.get("id"), "a rule"
    )
    if rule:
        record("work.rule", f"work/rules/{rule['id']}")
        record("work.rule.jobs", f"work/rules/{rule['id']}/jobs?page=1&per=50")
        record("work.rule.audit", f"work/rules/{rule['id']}/audit?page=1&per=50")
    # Lane RULES (CR-168 round 5) — the three non-Work reads the rule form
    # offers from: the notification catalogue (the *Message* pickers and the
    # *How* column), the utility's services (a continuous-flow trigger's
    # service and unit) and the roles (an escalation's *Also tell*).
    record("work.rules.lookup.notification-rules", "notification-rules")
    record("work.rules.lookup.services", "settings/services")
    record("work.rules.lookup.roles", "roles")
    record("work.performance.paged", "work/performance?page=1&per=50")
    record("work.at-risk", "work/at-risk?page=1&per=50")
    record("work.settings.sla", "work/settings/sla")

    reads = [line for line in manifest if wanted(line["name"])]
    if ONLY is not None and (OUT / "manifest.json").exists():
        kept = json.loads((OUT / "manifest.json").read_text()).get("reads", [])
        fresh = {line["name"] for line in reads}
        reads = [line for line in kept if line["name"] not in fresh] + reads
    (OUT / "manifest.json").write_text(json.dumps(
        {"recorded_from": f"{BASE}/api/{TENANT}/", "signed_in_as": EMAIL,
         "regenerate": "10-scripts/cr168_capture_work_shapes.py", "reads": reads},
        indent=2) + "\n")
    for line in manifest:
        print(f"{line['status']}  {line['name']:<40} rows={line.get('rows')}  {line['path']}")
    if problems:
        print("\nPROBLEMS:", *problems, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

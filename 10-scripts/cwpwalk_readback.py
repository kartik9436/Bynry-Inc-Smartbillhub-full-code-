#!/usr/bin/env python3
"""The 21-walk's database read-back (PO request 2026-10-01): SAVED, UPDATED, VIEWED.

`cwpwalk_portal_walk21.mjs` drives the browser and records, per walk, what the
SCREENS said. This reads the same walks back out of PostgreSQL, so every row of
`RESULTS.md` rests on a stored fact rather than on a screen's word for it:

  * SAVED   — the request, its services, its documents (bytes stored), the
              customer and the account the clerk carried it to, the account's
              class, kind and status, its open service agreements, the unit and
              premises it sits on, the sized equipment, the portal login;
  * UPDATED — the field the clerk corrected, read off the request AND off the
              `audit_log` row that recorded before → after;
  * VIEWED  — each document the clerk opened, read off the `audit_log`.

It then writes `RESULTS.md` beside the screenshots: one row per walk.

Read-only. It connects as the database owner (which RLS does not bind) because
it reads two utilities' rows side by side; it writes nothing to the database.

usage: cwpwalk_readback.py [--db cwpwalk_db] [--port 55433]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "08-qa" / "screens" / "portal-walk21-2026-10-02"
MANIFEST = OUT / "walk-manifest.json"


def sql(args: argparse.Namespace, query: str) -> list[list[str]]:
    raw = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-p", str(args.port), "-U", "postgres", "-d", args.db,
         "-AtF", "\x1f", "-c", query],
        check=True, capture_output=True, text=True,
    ).stdout
    return [line.split("\x1f") for line in raw.splitlines() if line]


def one(args, query: str) -> list[str]:
    rows = sql(args, query)
    return rows[0] if rows else []


def q(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


PREMISES = {"A": "on file, one unit", "B": "on file, with units", "C": "not in the system"}


def readback(args, wid: str, r: dict) -> dict:
    w = r.get("walk") or {}
    out: dict = {"id": wid, "walk": w}
    rid = r.get("request_id")
    if not rid:
        return out
    req = one(args, f"""
        select sr.request_no, sr.state, sr.applicant_name, sr.requested_start, sr.outcome,
               coalesce(at.code,''), coalesce(c.customer_no,''), sr.outcome_ref, sr.applicant_kind
        from service_requests sr
        left join account_types at on at.id = sr.account_type_id
        left join customers c on c.id = sr.matched_customer_id
        where sr.id = {q(rid)}""")
    out["request"] = dict(zip(
        ["no", "state", "name", "start", "outcome", "class", "linked", "outcome_ref", "kind"], req))
    out["services"] = [x[0] for x in sql(args, f"""
        select s.code from service_request_services rs join services s on s.id = rs.service_id
        where rs.request_id = {q(rid)} order by s.sort""")]
    out["documents"] = sql(args, f"""
        select d.name, coalesce(sd.byte_length::text, '')
        from service_request_documents d
        left join stored_documents sd on sd.id::text = d.storage_ref
        where d.request_id = {q(rid)} order by d.name""")
    out["viewed"] = sql(args, f"""
        select action, after->>'name'
        from audit_log where action = 'customers.service_request_document.viewed'
          and after->>'request_id' = {q(rid)}
        order by created_at""")
    out["audit_actions"] = [x[0] for x in sql(args, f"""
        select distinct action from audit_log where entity_id = {q(rid)} order by 1""")]
    fix = r.get("corrected") or {}
    if fix:
        field = fix.get("field")
        out["corrected"] = fix
        out["correction_audit"] = sql(args, f"""
            select action, coalesce(before->>{q(field)}, ''), coalesce(after->>{q(field)}, '')
            from audit_log where entity_id = {q(rid)} and after ? {q(field)}
              and coalesce(before->>{q(field)}, '') <> coalesce(after->>{q(field)}, '')
              and action = 'service_request.updated'
            order by created_at""")
        out["correction_now"] = one(args, f"select {field}::text from service_requests where id = {q(rid)}")
    acct_no = r.get("account_no")
    if acct_no:
        acct = one(args, f"""
            select a.account_no, a.kind, at.code, st.code, st.behavior_class, coalesce(u.label,''),
                   coalesce(p.address_line,''), c.customer_no, c.display_name, c.kind, c.id,
                   (c.created_at > (select submitted_at from service_requests where id = {q(rid)}))::text,
                   coalesce(ca.match_tier,''), a.id
            from accounts a
            join account_types at on at.id = a.account_type_id
            join account_statuses st on st.id = a.status_id
            left join units u on u.id = a.unit_id
            left join premises p on p.id = coalesce(u.premises_id, a.premises_id)
            join customer_accounts ca on ca.account_id = a.id and ca.ended_at is null
            join customers c on c.id = ca.customer_id
            where a.account_no = {q(acct_no)}""")
        keys = ["no", "kind", "class", "status", "behavior", "unit", "address", "customer_no",
                "customer_name", "customer_kind", "customer_id", "customer_new", "match_tier", "id"]
        out["account"] = dict(zip(keys, acct))
        if acct:
            out["agreements"] = [x[0] for x in sql(args, f"""
                select s.code from service_agreements sa
                join service_points sp on sp.id = sa.service_point_id
                join services s on s.id = sp.service_id
                where sa.account_id = {q(acct[13])} and sa.ended_on is null order by s.sort""")]
            out["equipment"] = sql(args, f"""
                select s.code, coalesce(a2.size_class, '—'), (a2.install_date is not null)::text
                from service_agreements sa
                join service_points sp on sp.id = sa.service_point_id
                join services s on s.id = sp.service_id
                join assets a2 on a2.service_point_id = sp.id
                where sa.account_id = {q(acct[13])} and sa.ended_on is null order by s.sort""")
            out["portal_login"] = one(args, f"""
                select email, status from portal_credential where customer_id = {q(acct[10])}""")
            out["customers_for_applicant"] = [x[0] for x in sql(args, f"""
                select distinct c.customer_no from customers c
                where c.display_name = {q(acct[8])} order by 1""")]
    owner_no = r.get("build_owner_account")
    if owner_no:
        out["build_owner"] = one(args, f"""
            select a.account_no, a.kind, c.customer_no from accounts a
            join customer_accounts ca on ca.account_id = a.id and ca.ended_at is null
            join customers c on c.id = ca.customer_id where a.account_no = {q(owner_no)}""")
    return out


def tick(ok) -> str:
    return "yes" if ok is True else ("NO" if ok is False else "—")


def step_ok(r: dict, needle: str):
    hits = [s for s in r.get("steps", []) if needle in s["name"]]
    if not hits:
        return None
    return all(s["ok"] is True for s in hits)


def main_rows(args, manifest: dict) -> list[str]:
    head = ("| Walk | Premises | Applicant | Services | New / linked | Regular / master | Class "
            "| Submitted | Docs saved | Docs viewed | Correction updated | Approved as | ACTIVE "
            "| Portal sees it | Saved / updated / viewed (database) | Notes |")
    rows = [head, "|" + "---|" * 16]
    detail: dict = {}
    for i in range(1, 13):
        wid = f"W{i}"
        r = manifest.get(wid)
        if not r:
            rows.append(f"| {wid} | not run |" + " |" * 14)
            continue
        b = readback(args, wid, r)
        detail[wid] = b
        w = b["walk"]
        req = b.get("request", {})
        acct = b.get("account", {})
        docs = b.get("documents", [])
        stored = [d for d in docs if d[1]]
        viewed_ui = step_ok(r, "clerk opens")
        corr = b.get("correction_audit") or []
        fix = b.get("corrected") or {}
        corrected_ok = bool(corr) and bool(b.get("correction_now")) and str(fix.get("to")) in b["correction_now"][0]
        active = acct.get("status") == "active" and acct.get("behavior") == "billable"
        portal = step_ok(r, "portal")
        services = ", ".join(b.get("services", []))
        new_linked = ("linked " if w.get("link") else "new ") + (acct.get("customer_no") or "?")
        if w.get("link") and acct.get("customer_new") == "true":
            new_linked += " (NEW number minted)"
        regmaster = acct.get("kind") or ("master" if w.get("master") else "regular")
        saved_bits = [
            f"request {req.get('no','?')} {req.get('state','?')}",
            f"{len(stored)}/{len(docs)} files stored",
            f"agreements {','.join(b.get('agreements', [])) or '—'}",
        ]
        if b.get("equipment"):
            saved_bits.append("equipment " + ", ".join(f"{e[0]}:{e[1]}" for e in b["equipment"]))
        if corr:
            saved_bits.append(f"audit {corr[-1][0]}: {corr[-1][1]} → {corr[-1][2]}")
        if b.get("viewed"):
            saved_bits.append(f"{len(b['viewed'])} open(s) audited")
        owner = b.get("build_owner")
        if owner:
            saved_bits.append(f"build owner {owner[0]} ({owner[1]}) on {owner[2]}")
        cust_count = len(b.get("customers_for_applicant", []))
        notes = []
        fails = [s["name"] for s in r.get("steps", []) if s["ok"] is False]
        if fails:
            notes.append("failed: " + "; ".join(fails))
        if cust_count > 1:
            notes.append(f"{cust_count} customer numbers carry this name")
        if b.get("portal_login"):
            notes.append(f"portal login {b['portal_login'][0]} ({b['portal_login'][1]})")
        rows.append("| " + " | ".join([
            wid,
            f"{PREMISES.get(w.get('prem'), '?')}: {w.get('addr','')}{(' ' + w['unit']) if w.get('unit') else ''}",
            f"{w.get('who', {}).get('kind','?')} — {req.get('name') or w.get('who', {}).get('name','')}",
            services or "—",
            new_linked,
            regmaster,
            acct.get("class") or req.get("class") or "—",
            tick(bool(req.get("no"))),
            f"{len(stored)} of {len(docs)}",
            tick(viewed_ui),
            tick(corrected_ok) + (f" ({fix.get('field')})" if fix else ""),
            req.get("outcome") or "—",
            tick(active) + (f" {acct.get('no')}" if acct.get("no") else ""),
            tick(portal),
            "; ".join(saved_bits),
            "; ".join(notes) or "—",
        ]).replace("\n", " ") + " |")
    (OUT / "readback.json").write_text(json.dumps(detail, indent=2, default=str))
    return rows


def extra_rows(manifest: dict) -> list[str]:
    rows = ["| Walk | What was tried | Result | Detail |", "|---|---|---|---|"]
    for i in range(13, 22):
        wid = f"W{i}"
        r = manifest.get(wid)
        if not r:
            rows.append(f"| {wid} | not run | — | — |")
            continue
        for s in r.get("steps", []):
            if wid in ("W13", "W14") and s["name"].startswith(("address step", "services the", "two files", "check-and-send", "request detail", "on the clerk")):
                continue
            detail = s["detail"].replace("|", "/").replace("\n", " ")[:160]
            rows.append(f"| {wid} | {s['name']} | {'pass' if s['ok'] else 'FAIL'} | {detail} |")
    return rows


FINDINGS = """## What the walk found

**Fixed during the walk** (each filed first, red test first, re-walked green):
`DEF-CUS-9041` the clerk could not pick the property on a portal request ·
`DEF-CWP-4930` an address we do not hold could not be applied for ·
`DEF-CUS-9042` the request page dropped the unit · `DEF-CUS-9043` no way to link
a customer on file from Approve · `DEF-CUS-9044` the move-in started blank ·
`DEF-CWP-9045` a business's Tax ID never reached its new customer ·
`DEF-CWP-9046` the date of birth typed online was dropped ·
`DEF-CUS-9047` New Connect's owner class ignored the clerk's pick ·
`DEF-CWP-9051` a save's answer wiped an attached file off the screen ·
`DEF-CUS-9052` the move-in held a linked or Tax-ID business on step 1 ·
`DEF-CUS-9053` a master account opened with no contact, so its portal login could
not be set up · `DEF-CUS-9074` New Connect asked again for what the request
holds · `DEF-CUS-9078` one applicant got two customer numbers ·
`DEF-CWP-9049` after *Ask for more* the customer could not send a second
document — Track now offers *Add a document* (W14) · `DEF-CWP-9079` the
paperless box arrived ticked — it now arrives unticked (W1–W14) ·
`DEF-CUS-9048` (fixed by the coordinator on the PO's ruling of 2026-10-02, not by
this lane) the billing clerk could not read New Connect's size and equipment
lists — W9–W12 re-walked and now offered them.

**Still failing, filed, not fixed:**
* `DEF-CUS-9050` — New Connect's occupancy choice *Open an account* does nothing
  (the walk opens the occupant's account through Move-in instead). Left
  unbuilt: nothing says WHO the per-unit account is for — the wizard names no
  occupant — and `BR-MET-116` (PO 2026-08-25) says every unit is vacant at
  confirm. `DEF-CUS-9082`: the other two non-default choices are read by
  nothing either.

**Open, with the coordinator for the PO:** `OQ-1361` — sizing a fire line from
New Connect (on the re-walk W10 and W12 store sized trash, solar and battery
equipment, but fire gets no fire line and the water meter no size class) · W11: the owner's master account on a new single-unit build opens
ACTIVE with no service on it, because the battery sits on Unit 1, which has no
occupant account.

**Walk artefact, not a defect:** every walk comes from one address, and the
guest door allows sixty requests a minute per address (BR-CWP-022); W17 waits a
minute so it measures the draft and not the throttle.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="cwpwalk_db")
    ap.add_argument("--port", default=55433, type=int)
    args = ap.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    body = [
        "# Portal request to active account — the 21-walk (2026-10-02)",
        "",
        "Driven by `10-scripts/cwpwalk_portal_walk21.mjs` in a real browser against a real",
        "PostgreSQL 16; read back by `10-scripts/cwpwalk_readback.py`. Screenshots are",
        "beside this file, named `<walk>-<step>.png`. `readback.json` holds every stored",
        "fact the table below was built from.",
        "",
        "## W1–W12 — apply online, clerk processes, account goes ACTIVE",
        "",
        *main_rows(args, manifest),
        "",
        "## W13–W21 — the refusals and the edges",
        "",
        *extra_rows(manifest),
        "",
        FINDINGS,
    ]
    (OUT / "RESULTS.md").write_text("\n".join(body))
    print(f"wrote {OUT / 'RESULTS.md'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-8696 (Sign off's summary read, three questions per account)
#           DEF-BIL-8697 (`GET …/summary`, Python over every draft)
#           DEF-BIL-8720 (Sign off's Amount due ignored a plan's not-yet-due part)
# Journey:  08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md S2
# Doc:      04-docs/05-modules/07-billing/19-check-cost-measured.md §11
# ───────────────────────────────────────────────────────
"""Sign off's figures BEFORE and AFTER the batching — the same world, the same views.

TEST HARNESS ONLY. Writes only through the product's own views; refuses SQLite
(hard-won law 14) and a role that bypasses row-level security (DEF-2717).

    prepare [--answer case=choice ...]
        The J72 world at Sign off: `POST …/check` inline, each --answer as the
        tag's standing answer (`POST …/check/decide`, scope all), then
        `POST …/calculate` inline, through the real views (J72 E1.2's September
        run, created the way Scope creates it when the world has none yet).

    dump --out FILE [--run ID]
        `GET …/sign-off-summary` and `GET …/summary` through the real views, as a
        Billing Clerk, written to FILE as JSON with each read's wall time. Run it
        on the OLD code first (a worktree at the commit before the change) and on
        the NEW code second, against the same database.

    send-compare SIGNED_OFF_DUMP [--run ID]     (a COPY of a world — it sends the run)
        Sign off and Send inline through the real views, then each issued bill's
        stamped balance forward added up and set beside the dump's Sign off
        figures: previous balance, payments and credits, a plan's part not yet
        due, and the amount due, each compared to the cent.

    diff OLD NEW [--allow KEY ...]
        Every figure of OLD and NEW compared key by key. Exit 1 on any difference
        not named with --allow (a dotted path, e.g.
        `sign_off.payments_and_balances.amount_due` — DEF-BIL-8720 moves that one
        on purpose, and only on an account with a payment plan).

USAGE (from 06-backend):
    DATABASE_URL=postgres://sbh_b27:sbh_b27@127.0.0.1:55433/<db> \\
      DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python ../10-scripts/d8696_signoff_parity.py dump --out /tmp/old.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")
os.environ.setdefault("BILLING_MAX_ACCOUNTS_PER_RUN", "0")


def _setup():
    import django

    django.setup()
    from django.conf import settings

    settings.DEBUG = False
    import j73_scale_proof as proof

    proof._refuse()
    return proof


def _context(proof, run_id: str | None):
    from apps.billing import models as bm
    from core import tenancy as core_tenancy

    tenant, actor = proof._world()
    with core_tenancy.tenant_context(tenant.id):
        if run_id:
            run = bm.BillRun.objects.get(pk=run_id)
        else:
            try:
                run = proof._run_a(tenant, actor)
            except bm.BillRun.DoesNotExist:
                run = _create_september(tenant, actor)
    return tenant, actor, run, proof._Api(tenant, getattr(actor, "user", actor))


def _create_september(tenant, actor):
    """J72 E1.2's run — *September 2026 · Riverside*, Sep 1 – Sep 30, bill date
    Oct 1, 21 days — made the way the Scope step makes it (`runs.create_run`)."""
    from datetime import date

    from apps.billing import runs
    from apps.tenancy.management.commands import seed_j72_bulk_run as seeder

    template_id, _version = seeder._template()
    return runs.create_run(
        cycle_id=seeder.ensure_cycle(tenant).id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        bill_date=date(2026, 10, 1),
        due_days=seeder.DUE_DAYS,
        label="September 2026 · Riverside",
        template_id=template_id,
        run_by=getattr(actor, "user", None),
    )


def prepare(run_id: str | None, answers: list[str]) -> dict:
    proof = _setup()
    from apps.billing import api as billing_api
    from apps.billing import check_api

    tenant, _actor, run, api = _context(proof, run_id)
    root = f"/api/{tenant.subdomain}/billing/runs/{run.pk}"
    out = {"run": str(run.pk)}
    code, body, _ = api.call(check_api.run_check, "POST", root + "/check", {}, run_id=str(run.pk))
    out["check"] = code
    # Each `case=choice` answered for the whole tag (`scope: all`, the standing
    # answer), as the clerk's tag panel does, so more of the world is billed.
    for answer in answers:
        case, choice = answer.split("=", 1)
        code, body, _ = api.call(
            check_api.run_check_decide, "POST", root + "/check/decide",
            {"case": case, "choice": choice, "scope": "all"}, run_id=str(run.pk),
        )
        out[f"answer {answer}"] = code if code < 400 else body
    code, body, _ = api.call(
        billing_api.run_calculate, "POST", root + "/calculate", {}, run_id=str(run.pk)
    )
    out["calculate"] = code
    out["calculate_body"] = body if code >= 400 else None
    return out


def dump(out_path: str, run_id: str | None) -> dict:
    proof = _setup()
    from apps.billing import api as billing_api
    from apps.billing import check_api

    tenant, _actor, run, api = _context(proof, run_id)
    root = f"/api/{tenant.subdomain}/billing/runs/{run.pk}"
    result: dict = {"run": str(run.pk), "load_start": proof._load()}
    for key, view, suffix in (
        ("sign_off", check_api.run_sign_off_summary, "/sign-off-summary"),
        ("summary", billing_api.run_summary, "/summary"),
    ):
        t0 = time.perf_counter()
        code, body, _ = api.call(view, "GET", root + suffix, {}, run_id=str(run.pk))
        result[f"{key}_seconds"] = round(time.perf_counter() - t0, 3)
        result[f"{key}_status"] = code
        result[key] = body
    result["load_end"] = proof._load()
    Path(out_path).write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    return {k: v for k, v in result.items() if k not in ("sign_off", "summary")}


def send_compare(signed_off_path: str, run_id: str | None) -> dict:
    """Sign off's figures (a `dump` taken before Send) against the BILLS: Sign
    off, then Send inline through the real views, then each issued bill's own
    stamped balance forward added up. *"The figures on Sign off must equal the
    sum of the bills to the cent."* Only on a COPY of a world: it sends the run."""
    from datetime import datetime, timezone
    from decimal import Decimal

    proof = _setup()
    from apps.billing import api as billing_api
    from apps.billing import models as bm
    from core import tenancy as core_tenancy

    signed = json.loads(Path(signed_off_path).read_text())["sign_off"]["payments_and_balances"]
    tenant, _actor, run, api = _context(proof, run_id)
    root = f"/api/{tenant.subdomain}/billing/runs/{run.pk}"
    now = datetime.now(timezone.utc).isoformat()
    confirm = ("compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final")
    code, body, _ = api.call(
        billing_api.run_release, "POST", root + "/release",
        {"confirmations": {k: True for k in confirm}, "confirmed_at": now}, run_id=str(run.pk),
    )
    out: dict = {"release": code}
    code, body, _ = api.call(
        billing_api.run_issue, "POST", root + "/issue", {"issued_at": now}, run_id=str(run.pk)
    )
    out["issue"] = code if code < 400 else body
    sums = {key: Decimal("0") for key in ("previous_balance", "payments_credits", "total_due",
                                          "plan_not_yet_due")}
    with core_tenancy.tenant_context(tenant.id):
        bills = list(bm.Invoice.objects.filter(bill_run=run).exclude(status="void")
                     .values_list("bill_payload", flat=True))
    for payload in bills:
        block = (payload or {}).get("balance_forward") or {}
        for key in sums:
            if block.get(key) is not None:
                sums[key] += Decimal(str(block[key]))
    pairs = {
        "previous_balance": ("previous_balance", signed.get("previous_balance")),
        "payments_credits": ("payments_and_credits_applied",
                             signed.get("payments_and_credits_applied")),
        "plan_not_yet_due": ("plan_not_yet_due", signed.get("plan_not_yet_due")),
        "total_due": ("amount_due", signed.get("amount_due")),
    }
    out["bills"] = len(bills)
    out["compared"] = {
        bill_key: {
            "bills_sum": str(sums[bill_key]),
            f"sign_off_{off_key}": value,
            "equal_to_the_cent": value is not None
            and Decimal(value).quantize(Decimal("0.01")) == sums[bill_key].quantize(Decimal("0.01")),
        }
        for bill_key, (off_key, value) in pairs.items()
    }
    return out


def _walk(old, new, path, out):
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            _walk(old.get(key, "<absent>"), new.get(key, "<absent>"), f"{path}.{key}", out)
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for i, (a, b) in enumerate(zip(old, new)):
            _walk(a, b, f"{path}[{i}]", out)
    elif old != new and not _same_money(old, new):
        out.append((path.lstrip("."), old, new))


def _same_money(old, new) -> bool:
    """Two money texts that are the SAME NUMBER at a different printed scale
    (`"242.00"` and `"242.000000"`) are the same figure; anything else is not."""
    from decimal import Decimal, InvalidOperation

    if not (isinstance(old, str) and isinstance(new, str)):
        return False
    try:
        return Decimal(old) == Decimal(new)
    except InvalidOperation:
        return False


def diff(old_path: str, new_path: str, allow: list[str]) -> int:
    old = json.loads(Path(old_path).read_text())
    new = json.loads(Path(new_path).read_text())
    found: list = []
    for key in ("sign_off", "summary", "sign_off_status", "summary_status"):
        _walk(old.get(key), new.get(key), key, found)
    unexpected = [row for row in found if not any(row[0].startswith(a) for a in allow)]
    for path, a, b in found:
        flag = "ALLOWED " if (path, a, b) not in unexpected else "DIFFERS "
        print(f"{flag}{path}: {json.dumps(a)[:120]} -> {json.dumps(b)[:120]}")
    leaves = sum(1 for _ in _leaves(old.get("sign_off"))) + sum(1 for _ in _leaves(old.get("summary")))
    print(
        f"compared {leaves} figures: {len(found)} differ, {len(unexpected)} not allowed · "
        f"old {old.get('sign_off_seconds')} s + {old.get('summary_seconds')} s, "
        f"new {new.get('sign_off_seconds')} s + {new.get('summary_seconds')} s"
    )
    return 1 if unexpected else 0


def _leaves(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _leaves(value)
    elif isinstance(node, list):
        for value in node:
            yield from _leaves(value)
    else:
        yield node


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--run")
    p.add_argument("--answer", action="append", default=[], help="case=choice, standing")
    d = sub.add_parser("dump")
    d.add_argument("--out", required=True)
    d.add_argument("--run")
    c = sub.add_parser("send-compare")
    c.add_argument("signed_off")
    c.add_argument("--run")
    f = sub.add_parser("diff")
    f.add_argument("old")
    f.add_argument("new")
    f.add_argument("--allow", action="append", default=[])
    args = parser.parse_args()
    if args.cmd == "prepare":
        print(json.dumps(prepare(args.run, args.answer), indent=1, default=str))
    elif args.cmd == "send-compare":
        print(json.dumps(send_compare(args.signed_off, args.run), indent=1, default=str))
    elif args.cmd == "dump":
        print(json.dumps(dump(args.out, args.run), indent=1, default=str))
    else:
        sys.exit(diff(args.old, args.new, args.allow))


if __name__ == "__main__":
    main()

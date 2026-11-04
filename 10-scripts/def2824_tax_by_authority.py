#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2824 — `resolution_catalogue.tax_facts` called
#          `rating.selectors.plan_tax_rules` with NO customer class, NO premises
#          and NO service list. All three restrictions FAIL CLOSED, so every
#          class-scoped, premises-scoped or service-scoped tax was dropped from
#          the ruled R1–R7 chain on every account of every tenant.
# Rules:   BR-BIL-069 / OQ-116 (each authority has its own account and its own
#          tagging, so a tax must be reported PER AUTHORITY and never as a
#          total) · DEF-273 (a failed applicability condition means NO LINE) ·
#          BR-BIL-039 (the preview and the real run are the same code, so this
#          reads `prepare_run`'s own output) · BR-RAT-087 (the server formats
#          money) · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:   06-backend/tests/test_def2824_tax_narrowing_facts.py
# Impacts: nothing. It writes no row — `prepare_run` writes nothing by its own
#          contract, no draft is assembled, and the pass is rolled back.
# ───────────────────────────────────────────────────────
"""WHICH AUTHORITIES ATTACH, AND WHAT EACH ONE IS OWED — live path vs ruled chain.

`10-scripts/cr052_r1r7_shadow_measure.py` answers the applicability question:
which authorities attach on each side. It stops there on purpose — R7 decides
applicability and never an amount.

**This file answers the money half, per authority, because a total cannot.** The
PO ratified the tax-per-authority work on 2026-08-31 and a bill now shows each
authority's subtotal, so a change to WHICH taxes attach moves those subtotals.
A single tax figure per account would let a 6.25% state tax appearing and a
2.00% county tax disappearing cancel to something that looks like no change at
all — which is exactly the shape of error `resolution_shadow.compare()`'s own
docstring refuses ("comparing totals would hide two errors that cancel").

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://…/<db>?sslmode=disable \
    JOBS_EAGER=false \
    python3 10-scripts/def2824_tax_by_authority.py [--only-differing]

── HOW THE "RULED" COLUMN IS PRODUCED, AND WHAT IT IS NOT ───────────────────

The ruled chain prices nothing: `resolution_switch.SERVED_BY_CHAIN_DEFAULT` is
empty and R7 has no arithmetic of its own. So the ruled column is produced by
running the LIVE engine twice over the SAME account with everything identical
except the tax rule set — once with the rules the live path attached, once with
the live rules filtered to the authorities the CHAIN attached. Nothing else is
substituted, no rate is re-derived and no rounding rule is re-applied.

That makes it an honest answer to one question — *"if R7's attachment decision
were the one used, what would each authority be owed?"* — and NOT a claim that
the chain computed it. It cannot compute it; that is what BR-RAT-036's
arithmetic in `apps/rating/pricing/stages/compute_tax.py` is for.

⚠ **THE POSTURE IS PART OF THE FIGURE.** Run it as a role RLS applies to
(`rolsuper = false`, `rolbypassrls = false`); it prints what it is connected as
so a figure can never be quoted without it.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

settings.DEBUG = False

from apps.billing import rating_seam, runs  # noqa: E402
from apps.billing import resolution_shadow as shadow  # noqa: E402
from apps.billing.stages.measure_consumption import measure_consumption  # noqa: E402
from apps.billing.stages.resolve_subscription import resolve_subscription  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
SERVICE_DATE = date(2026, 7, 1)


def _money(amount: Decimal) -> str:
    """CLAUDE.md hard rule 2 — money DISPLAYS at 2 decimals, and nothing here
    re-rounds one: every figure is an amount the engine already finalized."""
    value = Decimal(str(amount))
    two = value.quantize(Decimal("0.01"))
    return f"${two}" if two == value else f"${value} (NOT exact at 2dp — unrounded)"


def _posture() -> list[str]:
    """`rolsuper` / `rolbypassrls`, read back at runtime rather than assumed."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT current_database(), current_user, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"
        )
        row = cur.fetchone()
    if row is None:  # pragma: no cover - defensive
        return ["  posture could not be read from pg_roles"]
    database, user, is_super, bypasses = row
    return [
        f"  database              {database}",
        f"  connected as          {user}",
        f"  rolsuper              {is_super}   "
        f"(RLS is {'BYPASSED' if is_super else 'NOT bypassed'})",
        f"  rolbypassrls          {bypasses}   "
        f"(RLS is {'BYPASSED' if bypasses else 'NOT bypassed'})",
    ]


def _tax_by_authority(priced) -> dict[str, Decimal]:
    """Each authority's own subtotal off the engine's finalized tax lines.

    Keyed on the line's DESCRIPTION, which is the authority the rule named
    (BR-BIL-069: the identity and the rate name the same row). Summed rather
    than assumed-one-per-authority: BR-RAT-036 gives an authority a percent, a
    flat and a per-unit form and a bill may carry more than one of them.
    """
    out: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for line in priced.lines_of("tax"):
        out[str(line.description)] += Decimal(str(line.amount))
    return dict(out)


def _price(subscription, usage, taxes):
    """The live engine over one account, with the tax rule set substituted.

    Every other argument is `runs.calculate_account`'s, verbatim — the same
    services, the same base-only services, the same period, the same account
    context, the same fees and the same discounts. Only `taxes` moves, which is
    the only thing R7 decides.
    """
    return rating_seam.price_bill(
        services=tuple((service.tariff, service.consumption) for service in usage.measured),
        base_only_services=tuple(service.tariff for service in usage.unmeasured),
        period=subscription.period,
        account=rating_seam.AccountContext(
            currency=subscription.currency, tax_exempt=subscription.tax_exempt
        ),
        taxes=taxes,
        fees=subscription.fees,
        discounts=getattr(subscription, "discounts", ()),
    )


def _ruled_codes(data, account) -> tuple[tuple[str, ...], str | None]:
    """The authorities the RULED chain attaches, or the reason it could not say.

    ⚠ **THE `TypeError` BRANCH IS DELIBERATE AND IS NOT A FALLBACK.** Before
    `DEF-2824` was fixed, `build_catalogue` took no account facts at all, and
    this script has to run on THAT tree to produce the "before" column the
    defect is proved with. The two branches are two different programs and are
    named as such rather than merged behind a `getattr`.
    """
    inputs = shadow.adapt(data, account=account)
    if inputs.blocked_reason is not None:
        return (), inputs.blocked_reason

    resolution, catalogue_module = shadow._rating()
    base = shadow._refusal_base() or ()
    try:
        catalogue = catalogue_module.build_catalogue(
            plan_id=inputs.plan_id,
            service_date=SERVICE_DATE,
            unmetered_services=inputs.unmetered_services,
            account=inputs.account,
            premises=inputs.premises,
        )
    except TypeError:
        catalogue = catalogue_module.build_catalogue(
            plan_id=inputs.plan_id,
            service_date=SERVICE_DATE,
            unmetered_services=inputs.unmetered_services,
        )
    try:
        resolved = resolution.resolve(
            catalogue=catalogue,
            account=inputs.account,
            premises=inputs.premises,
            meters=inputs.meters,
            quantities=inputs.quantities,
            asset_counts=inputs.asset_counts,
            service_date=SERVICE_DATE,
        )
    except base as refusal:  # type: ignore[misc]
        return (), f"{type(refusal).__name__}: {refusal}"
    return tuple(sorted(str(rule.code) for rule in resolved.taxes)), None


def _one(data, account) -> dict | None:
    """One account, both sides.

    Returns None when the LIVE path cannot price it — an account the live engine
    refuses has no live figure to compare against, which is a different fact
    from a disagreement and is not reported as one.
    """
    try:
        subscription = resolve_subscription(data)
        usage = measure_consumption(subscription, data)
        live_priced = _price(subscription, usage, subscription.taxes)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        print(f"{data.account_no}: the LIVE path could not price this account — {exc}")
        return None

    live_codes = tuple(sorted(str(rule.code) for rule in data.taxes))
    ruled_codes, blocked = _ruled_codes(data, account)

    ruled_rules = tuple(rule for rule in subscription.taxes if str(rule.code) in set(ruled_codes))
    ruled_priced = _price(subscription, usage, ruled_rules) if blocked is None else None

    return {
        "account_no": data.account_no,
        "customer_class": getattr(getattr(account, "account_type", None), "code", None),
        "blocked": blocked,
        "live_codes": live_codes,
        "ruled_codes": ruled_codes,
        "live_tax": _tax_by_authority(live_priced),
        "ruled_tax": _tax_by_authority(ruled_priced) if ruled_priced is not None else {},
        "live_total": Decimal(str(live_priced.tax_total)),
        "ruled_total": (
            Decimal(str(ruled_priced.tax_total)) if ruled_priced is not None else Decimal("0")
        ),
    }


class _Done(Exception):
    def __init__(self, rows):
        super().__init__("done")
        self.rows = rows


def _collect() -> list[dict]:
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        raise SystemExit("no tenant on this database")
    try:
        with transaction.atomic():
            rows: list[dict] = []
            with core_tenancy.tenant_context(tenant.id):
                accounts = {
                    str(account.id): account for account in customer_models.Account.objects.all()
                }
                for cycle in metering_models.Cycle.objects.order_by("code"):
                    prepared = runs.prepare_run(
                        cycle_id=cycle.id,
                        period_start=PERIOD_START,
                        period_end=PERIOD_END,
                        service_date=SERVICE_DATE,
                    )
                    for data in sorted(prepared.ready, key=lambda d: d.account_no):
                        account = accounts.get(str(data.account_id))
                        if account is None:
                            continue
                        row = _one(data, account)
                        if row is not None:
                            rows.append(row)
            raise _Done(rows)
    except _Done as done:
        return done.rows


def main() -> int:
    only_differing = "--only-differing" in sys.argv
    rows = _collect()

    print("═" * 78)
    print("DEF-2824 · TAX BY AUTHORITY — live path vs the ruled R1–R7 chain")
    print("═" * 78)
    print()
    print("THE ROLE'S POSTURE, because a figure without it is not a figure:")
    for line in _posture():
        print(line)
    print()

    differing = [row for row in rows if row["live_codes"] != row["ruled_codes"]]
    shown = differing if only_differing else rows
    for row in sorted(shown, key=lambda r: r["account_no"]):
        flag = "  ← DIFFERS" if row["live_codes"] != row["ruled_codes"] else ""
        print(f"{row['account_no']}  ({row['customer_class'] or 'NO CLASS'}){flag}")
        if row["blocked"]:
            print(f"    ruled path could not run: {row['blocked']}")
        print(f"    live  attaches  {row['live_codes']}")
        print(f"    ruled attaches  {row['ruled_codes']}")
        authorities = sorted(set(row["live_tax"]) | set(row["ruled_tax"]))
        if not authorities:
            print("    no tax line on either side")
        for authority in authorities:
            live = row["live_tax"].get(authority)
            ruled = row["ruled_tax"].get(authority)
            mark = "" if live == ruled else "   ← MOVED"
            live_text = _money(live) if live is not None else "—"
            ruled_text = _money(ruled) if ruled is not None else "—"
            print(f"      {authority:<28} live {live_text:>12}   ruled {ruled_text:>12}{mark}")
        print(
            f"      {'TOTAL TAX':<28} live {_money(row['live_total']):>12}"
            f"   ruled {_money(row['ruled_total']):>12}"
        )
        print()

    print("─" * 78)
    print(
        f"{len(rows)} account(s) priced · "
        f"{len(differing)} where the attached authority set DIFFERS"
    )
    per_authority_live: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    per_authority_ruled: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        for authority, amount in row["live_tax"].items():
            per_authority_live[authority] += amount
        for authority, amount in row["ruled_tax"].items():
            per_authority_ruled[authority] += amount
    print("ACROSS THE WHOLE RUN, PER AUTHORITY — never as one tax total")
    for authority in sorted(set(per_authority_live) | set(per_authority_ruled)):
        live = per_authority_live.get(authority, Decimal("0"))
        ruled = per_authority_ruled.get(authority, Decimal("0"))
        mark = "" if live == ruled else "   ← MOVED"
        print(f"  {authority:<28} live {_money(live):>12}   ruled {_money(ruled):>12}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2824 · CR-052 task 20
# generated: 2026-08-31 by the DEF-2824 lane (claude)
# gates: reads only; `prepare_run` writes nothing, no draft is assembled and the
#        pass is rolled back.
# ──────────────────────────────────────────────────────────

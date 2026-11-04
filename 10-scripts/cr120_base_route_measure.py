#!/usr/bin/env python3
"""WHICH BASE CHARGE EVERY READY ACCOUNT RESOLVES, PRINTED ONE LINE AT A TIME.

`CR-120-BRC06` · `BR-RAT-1025`. PO ruling 2026-09-19: the rate schedule NAMES
its base charge code, where until today it was inferred.

⚠ **THIS EXISTS TO PROVE A NEGATIVE, AND A NEGATIVE IS EXACTLY WHERE A CHECK
PASSES WRONGLY (hard-won law 7 habit 2).** The ruling rests on one claim:
*"no existing schedule changes behaviour and no bill moves on day one."*
A test that asserted that by running the NEW code twice would pass whatever the
new code did — it would be law 7's *incapable of failing* shape wearing the name
of the proof.

**So this script is deliberately not a test. It PRINTS, and the proof is the
DIFF of two runs:**

    # on a worktree pinned at the tip this lane started from
    python3 10-scripts/cr120_base_route_measure.py > /tmp/before.txt
    # on this tree
    python3 10-scripts/cr120_base_route_measure.py > /tmp/after.txt
    diff /tmp/before.txt /tmp/after.txt        # must be EMPTY

An empty diff is the 47-of-47 figure in the review-ledger row. A non-empty one
names the account, the service and the two figures.

⚠ **IT RUNS THE LIVE PATH, WHICH IS THE ONE THAT ACTUALLY BILLS.**
`resolution_switch.SERVED_BY_CHAIN_DEFAULT` is empty on this deployment, so the
R1–R7 chain prices nothing in production; measuring only the chain would prove
the safety of a path no customer is billed from. `selectors
.base_charge_from_charge_code` is what `billing.gather._base_charge_code_for`
calls, through the seam, for every line of every bill.

⚠ **`app.tenant_id` IS WHY THIS IS A SCRIPT AND NOT A `psql` ONE-LINER.** RLS
FORCE is on: without the setting every query returns ZERO ROWS, which reads
exactly like *"no account resolves a base"* — the loudest possible false
negative for this particular measurement.

⚠ **AND THE OUTPUT IS SORTED AND CARRIES NO TIMESTAMP, ID OR COUNT-ONLY LINE**,
so the diff cannot be defeated by row order and cannot be satisfied by a run
that read nothing. The LAST line is the count, printed after the rows rather
than instead of them: `0 accounts · 0 resolved` and a healthy estate must not
look alike (law 7's *reporting zero over a scope it silently excludes*).

    TENANT=brazosbend python3 10-scripts/cr120_base_route_measure.py
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.customers import models as customer_models  # noqa: E402
from apps.rating import models as rating_models, selectors  # noqa: E402
from apps.tenancy.models import Tenant, TenantService  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TENANT = os.environ.get("TENANT", "brazosbend")


def _account_class(account) -> str | None:
    """The account's customer class as a CODE, which is what R4 narrows by."""
    account_type = getattr(account, "account_type", None)
    return str(getattr(account_type, "code", "")) or None


def main() -> int:
    # `Tenant` is keyed by SUBDOMAIN, not by a `code` column — and getting that
    # wrong answers `FieldError` rather than an empty result, which is the safe
    # direction and is why it is not defended against here.
    tenant = Tenant.objects.get(subdomain=TENANT)
    rows: list[str] = []
    accounts = 0
    resolved = 0
    bound_versions = 0
    with core_tenancy.tenant_context(str(tenant.id)):
        # ── HOW MANY VERSIONS NAME A CODE ───────────────────────────────────
        # Printed first because it is the fact that makes the rest meaningful:
        # if this is not ZERO on a tree that has never had the column, the
        # comparison is between two different worlds and the diff proves
        # nothing. On the tip it is absent entirely and reads `n/a`.
        try:
            bound_versions = (
                rating_models.TariffVersion.objects.filter(tenant_id=tenant.id)
                .exclude(base_charge_code_id=None)
                .count()
            )
            bound = str(bound_versions)
        except Exception:  # the column does not exist on the control tree
            bound = "n/a (column absent)"

        services = sorted(_enabled_services(tenant))
        for account in (
            customer_models.Account.objects.filter(tenant_id=tenant.id)
            .select_related("account_type")
            .order_by("account_no")
        ):
            accounts += 1
            customer_class = _account_class(account)
            for service in services:
                answer = selectors.base_charge_from_charge_code(
                    service, customer_class=customer_class, size_class=None
                )
                amount = answer.get("amount")
                code = answer.get("code")
                refusal = "REFUSED" if answer.get("refusal") else "ok"
                if amount is not None:
                    resolved += 1
                rows.append(
                    f"{account.account_no}\t{service}\t{customer_class or '-'}\t"
                    f"{code or '-'}\t{amount if amount is not None else '-'}\t{refusal}"
                )

    for line in sorted(rows):
        print(line)
    # The counts go LAST and they go beside each other, so an empty estate and a
    # healthy one cannot print the same shape.
    print(f"# accounts={accounts} lines={len(rows)} resolved={resolved} bound_versions={bound}")
    return 0


def _enabled_services(tenant) -> set[str]:
    """Every service this utility sells, as service CODES.

    ⚠ **EVERY ACCOUNT IS MEASURED AGAINST EVERY SERVICE, ON PURPOSE, AND IT
    OVER-MEASURES.** The alternative — reading each account's own connections —
    would be closer to a real bill and WORSE as a comparison, because an account
    that fell out of one tree's query would silently shrink that side's output
    and the diff would read as a difference in the BASE. A fixed cross-product
    cannot do that: both sides emit exactly `accounts x services` lines, so a
    missing line is as loud as a changed one.

    The cell where the account does not take the service is still meaningful —
    it is what that account WOULD resolve if it did — and it is the same
    question on both trees, which is all a diff needs.
    """
    return {
        str(row.service.code)
        for row in TenantService.objects.filter(tenant_id=tenant.id, enabled=True)
        .select_related("service")
        if row.service_id
    }


if __name__ == "__main__":
    raise SystemExit(main())

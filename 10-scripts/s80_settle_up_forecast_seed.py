#!/usr/bin/env python3
"""Seed the demo utility with budget accounts so §05 entry 25.2 has rows to draw.

Hard-won law 6: no gate in this repo reads rendered output, and the PO's own
definition of done is *"ensure you do web walkthorugh before you sign off the
user story or build"*. A forecast screen with no enrolled account proves
nothing, so this puts real accounts on a level and records real bills against
them through `budget_service` — the SAME write path the cycle run uses. Nothing
here inserts a row by hand.

⚠ **`core.tenancy.set_current_tenant(pk)` IS A PYTHON CONTEXTVAR, and it is what
the selectors read.** Setting the Postgres GUC alone leaves every selector
returning 0 rows against a database that plainly has the data — a near-miss that
almost produced a false defect on this branch.

⚠ **AND THERE ARE TWO MODELS CALLED `User`.** The actor foreign key on
`account_budget_events` points at `identity.User` (table `users`), NOT at
Django's `auth.User` that `get_user_model()` returns. Seeding with the wrong one
gets all the way to COMMIT before Postgres refuses the key, so the traceback
names a constraint rather than the mistake.

⚠ **WHAT THIS SCRIPT DOES NOT DO, AND WHAT IS STILL OWED.** It seeds the DATA a
browser walkthrough of §05 entry 25.2 needs; it does not boot the stack or drive
the screen. The lane that wrote it got as far as reading the endpoint directly
and was stopped by authentication: the demo database has no `identity.User` and
no `tenant_memberships` row, so `AnyTenantRole` answers `AUTH-003` / `BR-TEN-003`
to any request that has not been through the sign-in flow. **A walkthrough of
this screen therefore needs a member created first**, which is the next piece of
work and is recorded here rather than left to be rediscovered.

Run:
    cd 06-backend && DATABASE_URL=... DJANGO_SETTINGS_MODULE=config.settings.local \
        python3.12 ../10-scripts/s80_settle_up_forecast_seed.py

It is IDEMPOTENT: it exits without writing when the tenant already has budget
status rows.
"""
from __future__ import annotations

import datetime as dt
import sys
from decimal import Decimal
from types import SimpleNamespace

import django

django.setup()

from apps.billing import budget_service, models as bm  # noqa: E402
from apps.customers.models import Account  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import set_current_tenant  # noqa: E402

# ❄️ WE-8 / GT-24's own figures, so what the screen prints can be checked against
# a number that is already signed. The level computes to $242 from $2,904.
TRAILING = Decimal("2904")
CHAIN = [Decimal("292.87"), Decimal("231.40"), Decimal("198.75")]

tenant = Tenant.objects.get(subdomain="brazosbend")
set_current_tenant(tenant.pk)

# ⚠ THE ACTOR FK POINTS AT `identity.User` (table `users`), NOT at Django's
# `auth.User`. `get_user_model()` returns the latter, and seeding with it gets
# as far as COMMIT before Postgres refuses the foreign key — which is a failure
# worth naming because the two models are both called `User`.
from apps.identity.models import User  # noqa: E402

user = User.objects.filter(tenant=tenant).first()
if user is None:
    user = User.objects.create(
        tenant=tenant,
        email="s80-seed@example.invalid",
        full_name="Settle-up forecast seed",
        password_hash="!",            # unusable; this actor never signs in
    )
    print("created the seed actor (the demo database had no identity users)")
actor = SimpleNamespace(id=user.pk, pk=user.pk, role="system_admin", user=user)

already = bm.AccountBudgetStatus.objects.filter(tenant=tenant).count()
if already:
    print(f"already seeded: {already} budget status row(s); nothing to do")
    sys.exit(0)

accounts = list(Account.objects.filter(tenant=tenant).order_by("account_no")[:9])
if len(accounts) < 9:
    sys.exit(f"REFUSED: only {len(accounts)} accounts in the demo tenant; need 9")

# Nine accounts across FOUR settle-up months, so the screen's own sentence —
# "accounts settle in different months" — is true of the data and not just of
# the copy. Some settle this month, some later.
today = dt.date.today()
months = [today.month, today.month, today.month, today.month,
          (today.month % 12) + 1, (today.month % 12) + 1,
          ((today.month + 3) % 12) + 1, ((today.month + 5) % 12) + 1,
          ((today.month + 7) % 12) + 1]

made = 0
for account, month in zip(accounts, months):
    status = budget_service.enroll(
        actor=actor,
        account_id=account.id,
        trailing_actuals=(TRAILING,),
        months_of_history=12,
        plan_offers_budget=True,
        currency="USD",
        on_date=today - dt.timedelta(days=120),
    )
    status.settle_up_month = month
    status.save(update_fields=["settle_up_month"])
    # Real bills through the real write path. The spread makes some accounts
    # owe and some be owed, so the screen shows both directions.
    for n, actual in enumerate(CHAIN[: 1 + (made % 3)], start=1):
        budget_service.record_bill(
            account_id=account.id,
            actual=actual,
            on_date=today - dt.timedelta(days=90 - 30 * n),
            actor=actor,
        )
    made += 1

print(f"enrolled {made} account(s); "
      f"{bm.AccountBudgetEvent.objects.filter(tenant=tenant).count()} budget event(s)")
for row in bm.AccountBudgetStatus.objects.filter(tenant=tenant).select_related("account"):
    print(f"  {row.account.account_no}  month={row.settle_up_month}  "
          f"balance={row.variance_balance}")

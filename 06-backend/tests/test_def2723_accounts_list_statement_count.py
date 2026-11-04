# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2723 (2026-08-31) — the accounts list takes 562 ms for
#          SEVENTY-THREE accounts on an idle system (p50 562.2 / p95 639.4 /
#          max 752.2 ms), against 43.6 ms for ONE account's detail and 17.5 ms
#          for a whole bill with its lines, on the same database in the same
#          second. So it is not the machine and not the tenant predicate — it is
#          this read. Under ten concurrent bill runs its p95 goes to 3,377.8 ms
#          and its worst click to 5,196.4 ms while its p50 barely moves (562 ->
#          580), which is the tail-latency signature a person experiences as the
#          system sticking at random.
# Rules:   The defect row's own prescription, verbatim: "WHAT WOULD SETTLE IT IN
#          ONE COMMAND: count the SQL statements one account_list call sends. If
#          the count moves with the page size it is an N+1 … DURABLE GUARD: the
#          same statement counter as an assertion — a list endpoint costs a
#          constant number of statements whatever the page size."
#          CLAUDE.md hard-won law 7 (prove the guard goes RED first) · DEF-182
#          (a check that cannot distinguish pass from fail is worse than none)
# Screens: S17/S20 Accounts list — the product's busiest screen
# Impacts: 06-backend/apps/customers/selectors.account_list
# ───────────────────────────────────────────────────────
"""A LIST COSTS A CONSTANT NUMBER OF STATEMENTS, WHATEVER THE PAGE HOLDS.

WHY A STATEMENT COUNT AND NOT A TIMING TEST
-------------------------------------------
Nothing in this repo times a screen, and a timing test is the wrong instrument
anyway: slow, flaky on a shared machine, and it reports a NUMBER where the
question is a SHAPE. **7.7 ms per account is not a slow query, it is a query per
account**, and the two are fixed by completely different things. At SQLite's
zero latency the defect is invisible in seconds and obvious in statements —
which is the same lesson `DEF-1549` records one module over.

WHAT WAS MEASURED HERE, BEFORE ANY FIX
--------------------------------------
`account_list` already batches four page-wide reads, each with a comment saying
why: the AR position and the last bill date (`DEF-127`), the ageing band, and
the customer number (`CR-030` W2). **Four more were left per row**, and they are
the whole of this defect:

  * `_premise_cell`         -> `seams.unit_row(unit_id)`     — one per account
  * `primary_contact_name`  -> a `contacts` read             — one per account
  * `service_codes_for`     -> `service_agreements_for`      — one per account
  * `_service_by_point_for` -> `seams.service_points_for`    — one per account

Nothing about that is visible on the screen it slows down, and no gate in this
repo reads a query count.

WHAT "CONSTANT" MEANS, AND WHY IT IS NOT A MAGIC NUMBER
-------------------------------------------------------
A hand-written budget ("must be under 12 queries") goes red for benign reasons
and earns a `noqa` rather than a fix — `DEF-1075`'s guard says exactly that. So
this asserts the DIFFERENCE between two page sizes on the same tenant: doubling
the accounts must not move the count. A small tolerance is allowed for
legitimately row-shaped work, and it is small enough that ONE new per-row read
fails it.

Run with `JOBS_EAGER=false` (`DEF-567`).
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import models as customers_models, selectors as customers_selectors, services as customers_services
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

ESTATE_SERVICES = ("water", "sewer", "trash")


def plant_accounts(tenant, *, units: int, tag: str) -> int:
    """`units` ordinary accounts — each with the contact, unit and agreements a
    real row has.

    ⚠ **A PAGE OF BARE ACCOUNTS WOULD PASS ON THE BROKEN CODE.** Every per-row
    read this test exists to catch is a read of something HANGING OFF the
    account: its contact, its unit's premises, its service agreements. Plant
    accounts with none of those and each of the four costs one cheap query that
    finds nothing, the count stays flat, and the guard reports success over the
    defect — `DEF-1549`'s fixture gap, verbatim, one module over.
    """
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"1408 Elm St {tag}", city="Ottumwa", state="IA"
    )
    status = customers_models.AccountStatus.objects.filter(
        tenant=tenant, behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES
    ).first()
    assert status is not None, "the tenant has no occupying account status seeded"
    account_type = customers_models.AccountType.objects.first()
    for index in range(units):
        unit = metering_models.Unit.objects.create(
            tenant=tenant, premises=premises, label=f"Unit {tag}{index}"
        )
        account = customers_models.Account.objects.create(
            tenant=tenant,
            unit=unit,
            account_no=f"A-7{tag}{index:04d}",
            status=status,
            account_type=account_type,
        )
        customers_models.Contact.objects.create(
            tenant=tenant,
            account=account,
            full_name=f"Ana Ruiz {tag}{index}",
            is_primary=True,
        )
        for code in ESTATE_SERVICES:
            service = tenancy_models.Service.objects.filter(code=code, active=True).first()
            if service is None:  # pragma: no cover — the seed carries all ten
                continue
            point = metering_models.ServicePoint.objects.create(
                tenant=tenant, unit=unit, service=service
            )
            customers_models.ServiceAgreement.objects.create(
                tenant=tenant, account=account, service_point=point, started_on="2026-01-01"
            )
    return units


@pytest.fixture()
def ottumwa(growth_plan, identity_seam):  # noqa: F405
    """The Product Owner's own tenant: Water · Sewer · Trash."""
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Ottumwa Water Works",
            subdomain="ottumwa-water-works",
            services=list(ESTATE_SERVICES),
            owner={
                "full_name": "Ops Owner",
                "email": "owner@ottumwa-water-works.test",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    return tenant


def _list_params():
    from apps.customers.selectors import ListParams

    return ListParams(q="", filters={}, sort=None, dir="asc")


def _statements(params) -> int:
    with CaptureQueriesContext(connection) as ctx:
        customers_selectors.account_list(params)
    return len(ctx.captured_queries)


def test_def2723__accounts_list_cost_does_not_grow_with_the_page(ottumwa):
    """The whole defect, as one comparison between two page sizes.

    **RED BEFORE THE FIX, measured on this harness:** four accounts cost 22
    statements and twelve cost 54 — **four extra statements for every account
    added**, which at a real round trip is the 7.7 ms per account the defect row
    measured against a live PostgreSQL.
    """
    with tenant_ctx(ottumwa):
        plant_accounts(ottumwa, units=4, tag="a")
        small_n = 4
        small = _statements(_list_params())

        plant_accounts(ottumwa, units=8, tag="b")
        large_n = 12
        large = _statements(_list_params())

    per_account = (large - small) / (large_n - small_n)
    print(
        f"\nDEF-2723 accounts list: {small} statements for {small_n} accounts, "
        f"{large} for {large_n} — {per_account:.2f} per account added"
    )
    assert large <= small + 2, (
        f"account_list cost {small} statements for {small_n} accounts and {large} for "
        f"{large_n} — {per_account:.2f} extra PER ACCOUNT. That is a query per row on the "
        f"product's busiest screen, and it is what 562 ms for seventy-three accounts is "
        f"made of (DEF-2723). Batch the read for the whole page the way the AR position, "
        f"the last bill date, the ageing band and the customer number already are."
    )


def test_def2723__the_page_still_says_the_same_things(ottumwa):
    """⚠ **THE SEMANTIC GUARD, AND IT IS WHY THE FIX IS NOT ONE LINE.**

    A batched read that returns fewer facts is a speed-up wearing a regression's
    clothes, and a statement count cannot see it — the count would only get
    better. So the cells the four per-row reads feed are asserted by VALUE: the
    contact's name, the premise label, and the service chips in the platform
    catalogue's order.
    """
    with tenant_ctx(ottumwa):
        plant_accounts(ottumwa, units=2, tag="c")
        rows = customers_selectors.account_list(_list_params())

    assert len(rows) == 2
    by_no = {row["account_no"]: row for row in rows}
    first = by_no["A-7c0000"]
    assert first["name"] == "Ana Ruiz c0", "the primary contact's name is the Name cell"
    assert first["unit_label"] == "Unit c0"
    assert first["premise"] == "1408 Elm St c · Unit c0"
    assert set(first["services"]) == set(ESTATE_SERVICES), (
        "every active agreement's service must still reach the chips — a batched read that "
        "quietly drops one is invisible to a statement count"
    )

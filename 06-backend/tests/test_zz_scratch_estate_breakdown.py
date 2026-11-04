"""SCRATCH — count exactly what a seeded tenant receives, broken down, so the
PO's table is measured rather than summed from constants. Deleted after.
"""
from __future__ import annotations

from collections import Counter

import pytest

from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models

from tests.test_us_ten_helpers import *  # noqa: F401,F403
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _dump(tenant, title):
    with tenant_ctx(tenant):
        prem = list(metering_models.Premises.objects.filter(tenant_id=tenant.id))
        units = list(metering_models.Unit.objects.filter(tenant_id=tenant.id))
        accts = list(customers_models.Account.objects.filter(tenant_id=tenant.id))
        sps = metering_models.ServicePoint.objects.filter(tenant_id=tenant.id)
        svc = {s.id: s.code for s in tenancy_models.Service.objects.all()}
        print(f"\n=== {title} ===")
        print(f"  premises {len(prem)}  units {len(units)}  accounts {len(accts)}")
        print(f"  premises by type: {dict(Counter(p.premises_type for p in prem))}")
        print(f"  units by type:    {dict(Counter(u.unit_type for u in units))}")
        for field in ("account_type", "status"):
            if hasattr(customers_models.Account, field):
                print(f"  accounts by {field}: "
                      f"{dict(Counter(getattr(a, field, None) for a in accts))}")
        for flag in ("is_master", "master", "parent_account_id", "customer_id"):
            if hasattr(customers_models.Account, flag):
                vals = [getattr(a, flag, None) for a in accts]
                if flag in ("customer_id", "parent_account_id"):
                    print(f"  distinct {flag}: {len({v for v in vals if v})} "
                          f"(null {sum(1 for v in vals if not v)})")
                else:
                    print(f"  accounts by {flag}: {dict(Counter(vals))}")
        cust = getattr(customers_models, "Customer", None)
        if cust is not None:
            print(f"  customers: {cust.objects.filter(tenant_id=tenant.id).count()}")
        tally = Counter()
        for point in sps.values_list("service_id", flat=True):
            tally[svc.get(point, str(point))] += 1
        print(f"  service points by service: {dict(tally)}")


@pytest.mark.parametrize(
    "label,services",
    [
        ("water+sewer+trash (municipal)", ["water", "sewer", "trash"]),
        ("electric only", ["electric"]),
    ],
)
def test_breakdown(growth_plan, audit_rows, settings, label, services):
    settings.JOBS_EAGER = True
    slug = "brk-" + "-".join(services)[:30]
    tenant, result = provisioned_tenant(
        brazosbend_payload(
            subdomain=slug,
            name=f"Breakdown {label}",
            services=list(services),
            owner={
                "full_name": "Dana Whitfield",
                "email": f"dana@{slug}.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    assert result["created"] is True
    _dump(tenant, label)

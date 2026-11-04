#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 3 task 6 — the data the discount DETAILS walk
#          photographs (images 19–26), written through the product's OWN
#          services on a scratch database, never by hand-made rows (DEF-658).
# ───────────────────────────────────────────────────────
"""Put a sample utility into the eight drawn states of the details page.

Run AFTER `migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`, with
`DJANGO_SETTINGS_MODULE` and `DATABASE_URL` pointing at the SCRATCH database:

    python 10-scripts/cr166_discount_detail_walk_prep.py

What it does, each through `apps.rating.discount_services`:

* AUTOPAY (live, Automatic, carried by *Sample — Residential*) — the automatic
  enrolment job runs once, so the Accounts tab lists the accounts with autopay
  on (ruling 3); a NEW VALUE from 01/01 next year is saved, so the header reads
  *Next:* and the versions table holds a *Scheduled* row (images 19–23).
* MILITARY (the sample's draft) — left a draft: images 24 and 25.
* LIFELINE — a new fixed-amount discount, submitted: *Waiting approval*,
  image 26.

Idempotent enough to re-run: a second new value or a second LIFELINE is
refused by the service, and the refusal is printed rather than raised.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.identity import models as identity_models  # noqa: E402
from apps.rating import discount_enrolment_job, discount_services, seams  # noqa: E402
from apps.rating import discounts as dm  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TENANT = os.environ.get("TENANT", "brazosbend")


def first_of_next_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def main() -> int:
    tenant_id = core_tenancy.tenant_id_for_slug(TENANT)
    if tenant_id is None:
        print(f"no utility {TENANT!r}")
        return 1
    with core_tenancy.tenant_context(tenant_id):
        user = identity_models.User.objects.filter(email__istartswith="dana@").first()
        actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)
        today = seams.tenant_today()
        print("utility today:", today)

        autopay = dm.Discount.objects.get(code="AUTOPAY")
        print("sync AUTOPAY:", discount_enrolment_job.sync_discount(autopay, actor=actor))
        try:
            discount_services.new_discount_value(
                actor,
                autopay.id,
                {
                    "value": "0.75",
                    "effective_from": date(today.year + 1, 1, 1).isoformat(),
                    "change_reason": "Board raised the autopay credit for next year.",
                },
            )
            print("AUTOPAY: new value saved from", date(today.year + 1, 1, 1))
        except Exception as exc:  # noqa: BLE001 — a re-run; print and go on
            print("AUTOPAY new value refused:", exc)

        if not dm.Discount.objects.filter(code="LIFELINE").exists():
            row = discount_services.create_discount(
                actor,
                {
                    "code": "LIFELINE",
                    "name": "Lifeline water credit",
                    "program_owner": "billing",
                    "funding_source": "Rate-payer funded",
                    "discount_type": dm.DISCOUNT_FIXED_AMOUNT,
                    "value": "10",
                    "applies_to": dm.SCOPE_WHOLE_BILL,
                    "effective_from": first_of_next_month(today).isoformat(),
                    "enrolment_mode": dm.ENROLMENT_APPLY_AND_APPROVE,
                    "verification_method": dm.VERIFY_ANNUAL_RECERT,
                    "recertification_months": 12,
                    "eligibility": "household_income_limit",
                },
            )
            discount_services.submit_discount(actor, row["id"])
            print("LIFELINE created and submitted")
        else:
            print("LIFELINE already there")
        for code in ("AUTOPAY", "MILITARY", "LIFELINE"):
            discount = dm.Discount.objects.get(code=code)
            print(code, discount.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

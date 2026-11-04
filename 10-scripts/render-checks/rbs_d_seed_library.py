#!/usr/bin/env python3
"""Make `RBS-002`/`RBS-003` walkable in a browser — CR-075 wave D, `D3`/`D4`.

Two jobs, and both are FIXTURE work on a throwaway database rather than anything
the product does.

1. **GIVE THE FINANCE USER A PASSWORD.** The walkthrough's second half signs in
   as the executive — this product's Finance role
   (`models.ROLE_VISIBILITY_BY_CATEGORY`) — to prove `BR-RBS-024` clause 2 on a
   real screen: *a Finance user's Templates page shows Finance, Payments and
   Collections runbooks and not Platform.*

   ⚠ **THAT USER HAS NO USABLE CREDENTIAL AND THAT IS DELIBERATE PRODUCT
   BEHAVIOUR, NOT A GAP.** `apps/identity/sample_data.py` creates the two sample
   staff through `services.add_user` and then **discards the temp password
   unread**, with its reason written out: *"the OWNER stays the only credentialed
   login, which is the PO's stated posture."* So there is no password to look up
   anywhere, and a browser check that wants a second role has to mint one. This
   script does that ON A DISPOSABLE DATABASE and nowhere else.

2. **ADD ONE RUNBOOK**, so `RBS-003` draws its TABLE as well as its empty state.
   Through `services.add_template`, which is the same call `POST /runbooks`
   makes — never a hand-built row, because a fixture that writes a shape the
   product cannot produce proves a screen against a world that does not exist.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/sbh_rbsd34" \\
      python3.12 10-scripts/render-checks/rbs_d_seed_library.py --tenant brazosbend
      [--add configuration_check]

⚠ `python3` on this box is 3.11 and cannot import Django; `python3.12` can
(`DEF-GOV-4299`).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.contrib.auth.hashers import make_password  # noqa: E402

from apps.identity import models as identity_models  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument(
        "--finance-email",
        default="avery.cole@sample.test",
        help="the executive (Finance) sample user to give a password to",
    )
    parser.add_argument("--password", default="S3cure!passw0rd")
    parser.add_argument(
        "--add",
        default="",
        help="a template key to add to My runbooks, so RBS-003 draws a table",
    )
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.get(subdomain=args.tenant)
    print(f"tenant {tenant.subdomain} {tenant.id}")

    with core_tenancy.tenant_context(tenant.id):
        user = identity_models.User.objects.filter(email=args.finance_email).first()
        if user is None:
            print(f"⛔ no user {args.finance_email} — is this the seeded demo tenant?")
            return 2
        user.password_hash = make_password(args.password)
        # ⚠ **THE COLUMN IS `password_hash`, NOT `password`.** `apps/identity`
        # does not extend Django's `AbstractBaseUser`; it declares its own
        # `password_hash` (BR-IDN-002, never raw), and `save(update_fields=
        # ["password"])` raises `ValueError: The following fields do not exist
        # in this model` — which is the model refusing a wrong name loudly, and
        # is how this script's first draft was caught.
        #
        # ⚠ **AND CLEAR `must_change_password`.** Without this the sign-in
        # succeeds and the app parks the person on the change-password screen,
        # which is CORRECT product behaviour and is not the screen this check is
        # about — it would read as *the library never loaded*.
        user.must_change_password = False
        user.save(update_fields=["password_hash", "must_change_password"])
        role = (
            identity_models.TenantMembership.objects.filter(tenant_id=tenant.id, user_id=user.id)
            .select_related("role")
            .first()
        )
        print(f"credentialed {user.email} — role {role.role.code if role else 'UNKNOWN'}")

        if args.add:
            existing = runbook_models.Runbook.objects.filter(
                tenant_id=tenant.id, template_key=args.add
            ).first()
            if existing is not None:
                print(f"already added: {existing.key}")
            else:
                added = services.add_template(tenant.id, args.add, actor_id=None)
                print(f"added {added.key} ({added.kind} · {added.category})")

        total = runbook_models.Runbook.objects.filter(tenant_id=tenant.id).count()
        print(f"My runbooks now holds {total} runbook(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-018 · US-RBS-003 (CR-075 wave D tasks D3/D4) · BR-RBS-024 · RB-050
# generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: run against a throwaway database only; it mints a credential and must never touch a shared one
# exceptions: it sets a password the product deliberately discards — the reason is in the module docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

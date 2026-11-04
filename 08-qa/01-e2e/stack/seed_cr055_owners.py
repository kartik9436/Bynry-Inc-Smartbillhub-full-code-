#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-055 — a premises upload never rejects a row because of the
#          owner's name. This seeds the ONE precondition the browser journey
#          cannot create for itself.
# Rules:   BR-MET-402 clause 5 (**THE IMPORT NEVER CREATES A PARTY**) ·
#          BR-MET-151 clause 3 (a category is never read off a name) ·
#          CLAUDE.md rule 1 (every write inside `tenant_context`)
# Tests:   07-frontend/e2e/CR-055-owner-never-rejects.spec.ts
# ───────────────────────────────────────────────────────
"""Two owner records whose names collapse onto ONE search key.

WHY THIS IS FIXTURE AND NOT PRODUCT. The `near` answer needs two EXISTING owner
records that a third spelling resembles, and the import is forbidden from
creating a party (`BR-MET-402` clause 5) — so a browser journey cannot reach the
state CR-055 is about by clicking through the import alone. `seed_demo` seeds no
typed owners at all, which is correct for a first upload and useless here.

⚠ **THE NAMES ARE THE PRODUCT'S OWN EXAMPLE, NOT AN INVENTION.**
`_normalise_owner_name` strips LEGAL FORMS only — `llc`, `inc`, `l.l.c.` — and
never trade words, exactly so that *Ridge Property LLC* and *Ridge Holdings LLC*
stay two parties. These two share the key `ridge property`; the CSV the journey
uploads carries a third spelling, *Ridge Property Inc*, which matches NEITHER
exactly and BOTH loosely. That is the ambiguity, built from the rule rather than
from a coincidence.

⚠ **THE CATEGORY IS STATED HERE, NEVER DERIVED.** `BR-MET-151` clause 3 forbids
reading a category off a name — *Ridge Property LLC* is not evidence of a
landlord — so this file picks one out loud, which is what a person does on the
matching screen.

    DJANGO_SETTINGS_MODULE=config.settings.local \\
        DATABASE_URL=... python 08-qa/01-e2e/stack/seed_cr055_owners.py

Idempotent: it goes through `resolve_owner_name`, so a second run reuses the
parties rather than refusing on `uq_premises_owners_tenant_name_ci`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import premises_owners  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

NAMES = ("Ridge Property LLC", "Ridge Property, L.L.C.")
SUBDOMAIN = os.environ.get("E2E_TENANT", "brazosbend")


def main() -> int:
    tenant = tenancy_models.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if tenant is None:
        print(f"seed_cr055_owners: no tenant '{SUBDOMAIN}' — run seed_demo first", file=sys.stderr)
        return 1
    with tenant_context(tenant.id):
        # ⚠ **TWO THINGS THIS NEEDS AND NEITHER IS OBVIOUS.**
        # `users` has no `is_active` — a live user is one that has not been
        # soft-deleted — and the identity row carries **no `role` column**: the
        # auth layer attaches the role to the request user, and
        # `@require_role` reads `actor.role`. A bare `User` therefore fails
        # `AUTH-002` on `create_premises_owner`, which is the guard working
        # (BR-SHL-025: the service refuses no matter which caller forgot).
        # So the actor is a real user row wearing the role this fixture is
        # entitled to act with — the same shape `tests/test_us_met_helpers.
        # staff_actor` builds, for the same reason.
        from types import SimpleNamespace

        user = (
            identity_models.User.objects.filter(tenant_id=tenant.id, deleted_at__isnull=True)
            .order_by("created_at")
            .first()
        )
        if user is None:
            print("seed_cr055_owners: the tenant has no live user to act as", file=sys.stderr)
            return 1
        actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)
        for name in NAMES:
            found = premises_owners.resolve_owner_name(name)
            if found["match"] == "exact":
                print(f"  {name}: already on file")
                continue
            premises_owners.create_premises_owner(
                actor, {"name": name, "category": "landlord"}
            )
            print(f"  {name}: created")
        # Say out loud what was built, so a journey that skips can be told why.
        probe = premises_owners.resolve_owner_name("Ridge Property Inc")
        print(
            f"seed_cr055_owners: 'Ridge Property Inc' resolves to {probe['match']!r} "
            f"against {[c['name'] for c in probe['candidates']]}"
        )
        if probe["match"] != "near" or len(probe["candidates"]) < 2:
            print(
                "seed_cr055_owners: the ambiguity was NOT produced — the journey would "
                "pass over a world where its case cannot arise",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

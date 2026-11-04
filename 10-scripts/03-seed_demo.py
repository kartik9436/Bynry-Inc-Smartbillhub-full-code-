# DEPRECATED (2026-08-09, DevOps-prep lane): superseded by the Django management command
# `python manage.py seed_demo` in 06-backend/apps/tenancy/management/commands/seed_demo.py.
"""Demo-tenant seeder — a first-class artifact (04-docs/06-roles/forward-deployed-engineer.md).
Target state: one tenant resembling the prototype's fixtures — ~1,100 accounts, mixed
services, reads with every validation flag, open balances across all aging buckets,
and the 7 billing exception cases present. Grows module-by-module with the models.
Run: python 10-scripts/03-seed_demo.py (requires backend models — currently a stub)."""

if __name__ == "__main__":
    raise SystemExit("Seeder activates when tenancy/metering/customers models exist.")

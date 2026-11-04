# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INT-10020 — US Payments moves to /api/partner/v1/, where the
#           utility comes ONLY from `integration_key_directory`. PO 2026-10-07:
#           *"confirm issued US Payments keys exist in integration_key_directory
#           and document how to populate any missing"*.
# Rules:    the 2026-09-16 partner-URL rule (DEF-INT-5546) · BR-TEN-003 ·
#           CLAUDE.md hard rule 1 (each utility's credentials are read under its
#           own context) · hard-won law 3 (the write is the option you type)
# Tests:    06-backend/tests/test_def_int_10020_uspayments_partner_addresses.py
# ───────────────────────────────────────────────────────
"""`manage.py check_key_directory` — every live key WE issued that the partner
addresses cannot resolve, because it has no row in `integration_key_directory`.

WHY IT MATTERS
--------------
Every `/api/partner/v1/…` address carries no utility. The utility is found by
looking the presented key up in `integration_key_directory` BEFORE the view
runs (`key_directory.open_utility_for`). A live key with no row there opens no
utility, so every call it makes is refused with the ordinary one sentence —
exactly what a WRONG key looks like. Nothing on any screen can tell the two
apart; this command can.

How a key can lack its row: `services.record_credential` writes it for every
key issued since `integrations/0011` (2026-09-16), and that migration back-filled
the keys that existed then. So a missing row means a row deleted by hand, or a
credential written by some path other than `record_credential`.

WHAT IT DOES
------------
Read-only by default. For each utility, under that utility's own context (the
credential table is RLS `FORCE`), it lists every ACTIVE credential that carries
a key fingerprint (`blind_index` — only keys we issued do) and has no directory
row, and prints one line per key — utility, connector, the key's masked hint and
version — then `N missing`. Never the key: we do not hold it.

THE REPAIR, IN ORDER OF PREFERENCE
----------------------------------
1. **Issue a new key on the connector's card** (Settings → Integrations →
   <connector> → the key) and hand it to the partner. `record_credential` writes
   the directory row as part of the issue, and the old key stops working.
2. **`--fix`**, when re-issuing would interrupt a partner that is live: it
   writes the missing row through `key_directory.record` — the same function
   `record_credential` calls, from the same credential row, so the row holds
   nothing that was not already ours (the fingerprint and three ids). It is
   safe because the directory decides only WHICH utility to open; whether the
   key is live, in scope and from an allowed address is still decided under
   that utility by `serve.resolve_caller`.

Python 3.12. `--tenant <subdomain>` narrows it to one utility.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.integrations import key_directory, models
from core.tenancy import tenant_context


class Command(BaseCommand):
    help = (
        "List live issued partner keys with no integration_key_directory row "
        "(read-only); --fix writes the missing rows."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", help="One utility's subdomain.")
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Write each missing row through key_directory.record (the issue path's own write).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.tenancy.models import Tenant

        tenants = Tenant.objects.all().order_by("subdomain")
        if options.get("tenant"):
            tenants = tenants.filter(subdomain=options["tenant"])
        listed = set(models.IntegrationKeyDirectory.objects.values_list("blind_index", flat=True))
        missing = fixed = checked = 0
        for tenant in tenants:
            with tenant_context(tenant.id):
                credentials = (
                    models.IntegrationCredential.objects.filter(is_active=True)
                    .exclude(blind_index__isnull=True)
                    .exclude(blind_index="")
                    .select_related("connection")
                    .order_by("connection__provider_key", "version")
                )
                for credential in credentials:
                    checked += 1
                    if credential.blind_index in listed:
                        continue
                    missing += 1
                    self.stdout.write(
                        f"{tenant.subdomain} · {credential.connection.provider_key} · "
                        f"key {credential.masked_hint} v{credential.version} · no directory row"
                    )
                    if options.get("fix"):
                        key_directory.record(credential)
                        fixed += 1
        self.stdout.write(f"{checked} live issued keys checked · {missing} missing" + (f" · {fixed} written" if options.get("fix") else ""))


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-INT-10020 (maintenance)
# generated: 2026-10-07 by the US Payments partner-URL lane
# checklist: A✔ B=n/a(no screen) C✔ D=n/a E=n/a F✔ G✔ H=n/a(read-only by default; --fix calls the existing write)
# gates: pytest tests/test_def_int_10020_uspayments_partner_addresses.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

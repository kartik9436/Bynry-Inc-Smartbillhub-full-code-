# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 §4 — *The partner's morning*: 2026-09-02's 1,236
#           payments over three pages of 500, the allowlist
#           `198.51.100.0/24, 203.0.113.7`, the rate limit, and the unusual
#           read. The fixture the wave S walkthrough clicks.
# Rules:    10-execution-plan.md wave S tasks S3 · S4 · CLAUDE.md hard rule 1
#           (tenant context is a PostgreSQL GUC) · BR-INT-053 (the key is
#           issued once; here it is a KNOWN demo string on purpose)
# Tests:    10-scripts/render-checks/cr069-s-partner-morning.mjs (the consumer)
# Impacts:  apps/integrations/runners/serve.py (the blind-index context)
# ───────────────────────────────────────────────────────
"""seed_partner_morning — Aclarian, its key, and the morning it collected.

    DATABASE_URL=… python manage.py seed_partner_morning [--tenant brazosbend]

⚠ **THE KEYS THIS WRITES ARE PUBLIC DEMO STRINGS AND THE COMMAND SAYS SO ON
EVERY RUN.** A real key is minted by wave R, shown once and never again
(`BR-INT-053`). A walkthrough cannot use a key it can never read back, so this
seeds two KNOWN ones — a live one and a revoked one — and refuses to run
against anything but a database whose name marks it as a proof clone. The
alternative, printing a real issued key to a terminal, is the habit this
product exists to prevent.

⚠ **TWO CONNECTIONS, AND THE SECOND ONE IS HOW THE ALLOWLIST IS PROVED.** Every
request a walkthrough makes leaves from 127.0.0.1, so the only honest way to
demonstrate a refusal from an address that is not on the list is to make
127.0.0.1 the address that is not on it. The PRODUCTION connection's allowlist
is the story's own `198.51.100.0/24, 203.0.113.7` — which loopback is not in —
and the SANDBOX one leaves the allowlist empty so the collectable pages can be
served. Both are real rows; neither is a special case in the door.

PostgreSQL only, like every other seed here: tenant context is a GUC and these
tables are RLS-forced.
"""

import os
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection as db_connection

from apps.integrations import models, services
from apps.integrations.runners import serve
from core import crypto
from core.tenancy import tenant_context, tenant_id_for_slug

#: ⚠ `gl_partner` until `CR-110-BRC04`, when one generic finance card became
#: five named ERPs (blueprint p162). The seed picks ONE of the five; the
#: partner surface serves all five identically, so which one is arbitrary and
#: the walkthrough reads the same either way.
PROVIDER = "erp_workday"
#: ⚠ THE KEY CARRIES THE UTILITY'S NAME, AND THAT IS FOR THE PROOF RATHER THAN
#: FOR THE PRODUCT. A real key is opaque and says nothing about who it belongs
#: to. These are demo strings, and seeding two utilities with the SAME string
#: would quietly make the isolation demonstration meaningless — the same key
#: would work at both addresses and prove nothing about scoping. So each
#: utility gets its own, derived from its own slug.
def live_key(subdomain: str) -> str:
    return f"sbh_live_7Q2F_{subdomain}_demo"


def revoked_key(subdomain: str) -> str:
    return f"sbh_live_9X1B_{subdomain}_revoked"


def gated_key(subdomain: str) -> str:
    return f"sbh_live_3M5T_{subdomain}_gated"


LIVE_HINT = "••••7Q2F"
REVOKED_HINT = "••••9X1B"
GATED_HINT = "••••3M5T"
ALLOWLIST = "198.51.100.0/24, 203.0.113.7"
TOTAL_PAYMENTS = 1236
UNUSUAL_ROWS = 48_000


class Command(BaseCommand):
    help = "Seed Aclarian, its key and the morning it collected (US-INT-041 §4)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", default="brazosbend")
        parser.add_argument(
            "--i-know-this-writes-a-known-key",
            action="store_true",
            help="required: this seeds PUBLIC demo keys and must never touch a real database",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if db_connection.vendor != "postgresql":
            raise CommandError(
                "seed_partner_morning needs PostgreSQL — tenant context is a GUC and "
                "these tables are RLS-forced; nothing was written."
            )
        if not options["i_know_this_writes_a_known_key"]:
            raise CommandError(
                "refused: this command writes two PUBLICLY KNOWN partner keys, which is "
                "safe only on a proof clone. Re-run with --i-know-this-writes-a-known-key."
            )
        # ⚠ THE PREFIX IS `sbh_clone_`, AND THE FIRST DRAFT GUESSED `sbh_proof_`
        # AND REFUSED THE VERY CLONE IT WAS WRITTEN FOR. `proof-db.sh` spells it
        # `CLONE_PREFIX="sbh_clone_"`; the guard is READ from there in spirit and
        # the mistake is left recorded rather than tidied away, because a guard
        # that refuses everything is the mirror of one that refuses nothing and
        # both look like working code (CLAUDE.md law 7).
        name = (os.environ.get("DATABASE_URL") or "").rsplit("/", 1)[-1].split("?")[0]
        if name and not name.startswith("sbh_clone_"):
            raise CommandError(
                f"refused: {name!r} is not a proof clone (`sbh_clone_…`). "
                "Run `10-scripts/proof-db.sh clone int_s --export` first; nothing was written."
            )

        subdomain = options["tenant"]
        tenant_id = tenant_id_for_slug(subdomain)
        if tenant_id is None:
            raise CommandError(f"no tenant with subdomain {subdomain!r} — run seed_demo first.")

        with tenant_context(tenant_id):
            live = self._connection(tenant_id, models.ENVIRONMENT_SANDBOX, allowlist="")
            gated = self._connection(tenant_id, models.ENVIRONMENT_PRODUCTION, allowlist=ALLOWLIST)
            # ⚠ THE THREE REFUSALS MUST BE THREE DISTINCT CAUSES, AND THE
            # FIRST DRAFT COLLAPSED TWO OF THEM. It put the revoked key on the
            # allowlist-gated connection, so "off the allowlist" and "revoked"
            # were the SAME request failing for two reasons at once — which
            # demonstrates nothing about whether the two are distinguishable.
            # Found by reading the seed against the walkthrough it feeds.
            #
            # So: the OPEN connection carries both a revoked key and a live one
            # (the database allows one ACTIVE credential per connection, and
            # `record_credential` deactivates the previous version, so writing
            # the revoked one FIRST is what makes it the revoked one), and the
            # GATED connection carries a perfectly good key whose only problem
            # is where the call comes from.
            self._key(live, revoked_key(subdomain), REVOKED_HINT)   # becomes v1
            self._key(live, live_key(subdomain), LIVE_HINT)         # v2, deactivates v1
            self._key(gated, gated_key(subdomain), GATED_HINT)      # active, address-gated
            written = self._payments(tenant_id)
            self._history(live)

        self.stdout.write(
            self.style.SUCCESS(
                f"seeded {subdomain}: {written} payments · "
                f"{LIVE_HINT} live and servable · "
                f"{REVOKED_HINT} revoked on the same connection · "
                f"{GATED_HINT} live but gated by the allowlist {ALLOWLIST}"
            )
        )
        self.stdout.write(
            "⚠ these keys are printed in this file and in the walkthrough — a proof clone only."
        )

    # ── the pieces ───────────────────────────────────────────────────────

    def _connection(self, tenant_id: Any, environment: str, *, allowlist: str):
        row, _ = models.IntegrationConnection.objects.get_or_create(
            tenant_id=tenant_id,
            provider_key=PROVIDER,
            environment=environment,
            defaults={
                "label": "Aclarian",
                "status": models.STATUS_WORKING,
                "enabled": True,
                "cadence": models.CADENCE_MANUAL,
            },
        )
        config = dict(row.config or {})
        config.update(
            {
                # ⚠ `client_id` and `scopes` are NOT written here any more —
                # both fields were retired from the five ERP manifests on
                # 2026-09-16 (`DEF-INT-5534`, PO ruling). A seed that keeps
                # writing a field no manifest declares is a record that lies:
                # `settings_for` drops an unknown key on the way out, so it
                # would never appear on a screen and would sit in `config`
                # looking authoritative to the next reader.
                serve.ALLOWLIST_CONFIG_KEY: allowlist,
                serve.RATE_LIMIT_CONFIG_KEY: serve.DEFAULT_RATE_LIMIT_PER_MINUTE,
            }
        )
        # The audited grant OQ-INT-1481 (a) requires, so the register row the
        # walkthrough reads has a name and a date on it rather than the honest
        # "authorisation not recorded" a seeded connection would otherwise get.
        config.setdefault(
            serve.GRANT_CONFIG_KEY,
            {"granted_by_name": "Dana Whitfield", "granted_at": "2026-09-03T09:00:00+00:00"},
        )
        row.config = config
        row.status = models.STATUS_WORKING
        row.enabled = True
        row.save(update_fields=["config", "status", "enabled", "updated_at"])
        return row

    def _key(self, connection, key: str, hint: str) -> None:
        index = crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT)
        if models.IntegrationCredential.objects.filter(
            connection=connection, blind_index=index
        ).exists():
            return
        # ⚠ A SEED IS A SYSTEM JOB AND STILL NEEDS AN ACTOR WITH A ROLE.
        # `record_credential` is `@require_role`-guarded, and `actor=None` was
        # refused with AUTH-002 — correctly: a credential written by nobody is
        # a credential nobody can be asked about. `actor_user_id=None` is what
        # `core.audit.write_row` already means by *a system job*, so the row is
        # honest about who wrote it: the seeder, not a person.
        row = services.record_credential(
            actor=SimpleNamespace(id=None, role="system_admin"),
            connection=connection,
            payload=key,
            masked_hint=hint,
            blind_index=index,
        )
        del row  # the caller decides which version is current by the ORDER it writes

    def _payments(self, tenant_id: Any) -> int:
        from apps.customers import models as customer_models
        from apps.payments import models as payment_models

        existing = payment_models.Payment.objects.filter(
            payment_no__startswith="PMT-DEMO-"
        ).count()
        if existing >= TOTAL_PAYMENTS:
            return existing
        account = customer_models.Account.objects.order_by("account_no").first()
        if account is None:
            raise CommandError("no account to hang payments on — run load_sample_data first.")
        day = datetime(2026, 9, 2, 14, 0, tzinfo=dt_timezone.utc)
        payment_models.Payment.objects.bulk_create(
            [
                payment_models.Payment(
                    tenant_id=tenant_id,
                    account=account,
                    payment_no=f"PMT-DEMO-{index:06d}",
                    amount=Decimal("142.1800"),
                    currency="USD",
                    status="posted",
                    posted_at=day,
                )
                for index in range(existing + 1, TOTAL_PAYMENTS + 1)
            ],
            batch_size=500,
        )
        return TOTAL_PAYMENTS

    def _history(self, connection) -> None:
        """Frame 46.2's fourth row — the unusual read, so the screen has one to
        draw differently before the walkthrough makes any of its own."""
        if models.IntegrationRun.objects.filter(
            connection=connection, direction=models.RUN_DIRECTION_INBOUND_READ
        ).exists():
            return
        caller = serve.PartnerCaller(
            connection=connection,
            credential_id=None,
            hint=LIVE_HINT,
            tenant_id=connection.tenant_id,
            scopes=("payments",),
        )
        serve.record_read(
            caller=caller,
            operation="serve_payment",
            rows=UNUSUAL_ROWS,
            window="Payments, 2 years",
            page=1,
            total_pages=96,
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11) §4 Test Data
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
# checklist: A✔ B✔ C✔ D=n/a(a command, not a route) E=n/a F✔ G✔ H=n/a
# gates: 10-scripts/render-checks/cr069-s-partner-morning.mjs (the consumer)
# exceptions: it writes two PUBLICLY KNOWN keys and refuses any database not named `sbh_proof_…` — a walkthrough cannot use a key that is shown once and never again
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

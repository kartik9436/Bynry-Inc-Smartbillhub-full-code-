# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S8 (the
#           Sample data panel this is the command-line twin of, BR-TEN-069)
# Rules:    BR-TEN-056 as AMENDED 2026-08-16 · BR-TEN-060 (an unloaded block is
#           a NAMED line) · BR-TEN-063 (atomic per module, idempotent, audited)
#           · BR-TEN-064 (runs in production; a human asks — this command IS
#           the human asking) · BR-TEN-066 (removal is partial-and-named) ·
#           CLAUDE.md rule 1 (tenant context)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py
# Impacts:  every module's `seed_sample_records` seam, through the tenancy
#           orchestrator — this command adds no seeding logic of its own.
# ───────────────────────────────────────────────────────
"""`load_sample_data --tenant <subdomain>` — THE REPAIR PATH.

WHY THIS COMMAND HAS TO EXIST
------------------------------
Hard-won law 4: *"A template change never reaches a host that already has a
`.env`. Editing `.env.example` fixes nothing already deployed. Say so, every
time."* The same law with different nouns is what makes provisioning-time
seeding insufficient: **a seeder that runs when a tenant is created reaches that
tenant at that moment and never afterwards.**

`silver-creek-water` exists on the live deployment today with no sample data,
and it was created before any of this was written. Without a command that loads
an EXISTING tenant, every tenant created before 2026-08-16 is permanently
un-demoable — and "create a new tenant instead" is not an answer for a utility
that has already started entering its own data into the old one.

WHAT IT IS NOT
---------------
It is not a second seeder. Every row it writes is written by
`apps.tenancy.sample_data`, which is the same code the Sample data panel on
Settings → Company profile calls (BR-TEN-069). If the two ever disagreed, one of
them would be seeding a tenant differently from the other and nobody would know
which. This command resolves a tenant, opens its context, and calls that.

IT RUNS IN PRODUCTION, AND THAT IS BR-TEN-064
-----------------------------------------------
*"The sample-data job runs under production settings — BR-TEN-056's beneficiary
is a real new operator on the live system, so a production refusal would mean
the ruling never executes where it was written for."* It creates no tenant, no
user, no credential and no subscription. `seed_demo` KEEPS its production
refusal because it publishes an owner password; this one publishes nothing.

REMOVAL IS PARTIAL AND IT SAYS SO
-----------------------------------
`--remove` deletes every sample row nothing real references and NAMES the rest
(BR-TEN-066). Issued bills, their lines and their payments are append-only
(CLAUDE.md hard rule 4) and can never be removed — the command prints that
rather than reporting a clean sweep it did not perform.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from apps.tenancy import models, sample_data
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN


class _SampleDataActor:
    """The human who asked, as the services need to see them.

    Every service the seeders drive writes an `audit_log` row naming an actor
    (CLAUDE.md rule 7), and a command-line run still has to say WHO. The
    tenant's provisioning owner is that person: they are the account the load
    is being performed on behalf of, and they exist for every tenant
    (BR-TEN-001 refuses an owner-less tenant).
    """

    def __init__(self, user_id: Any) -> None:
        self.id = user_id
        self.pk = user_id
        self.role = SYSTEM_ADMIN
        self.roles = (SYSTEM_ADMIN,)
        self.is_authenticated = True


class Command(BaseCommand):
    help = (
        "Load (or remove) the demo sample data for an EXISTING tenant. "
        "The Settings > Company profile panel does the same thing; this is the "
        "path for a tenant that was created before the sample data existed."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--tenant",
            required=True,
            help="the tenant's subdomain, e.g. silver-creek-water",
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            help=(
                "remove the sample data instead of loading it. Partial by law "
                "(BR-TEN-066): issued bills and payments can never be deleted "
                "and are reported by name."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            # Tenant context is a Postgres GUC (core/tenancy.py). Refusing here
            # is the same guard `seed_demo` makes, and for the same reason: on
            # sqlite the load would silently run with no tenant scoping at all.
            raise CommandError(
                "sample data needs PostgreSQL — tenant context is set with "
                "set_config('app.tenant_id', …) and sqlite cannot run it "
                "(CLAUDE.md rule 1). Nothing was written."
            )
        subdomain = str(options["tenant"]).strip()
        try:
            tenant = models.Tenant.objects.filter(subdomain=subdomain).first()
        except DatabaseError as exc:  # pragma: no cover - surfaced, never swallowed
            raise CommandError(f"could not read tenants: {exc}") from exc
        if tenant is None:
            raise CommandError(
                f"no tenant with subdomain {subdomain!r}. Nothing was written. "
                "This command loads an EXISTING tenant; it never creates one."
            )

        actor = _SampleDataActor(self._owner_user_id(tenant))
        with core_tenancy.tenant_context(str(tenant.id)):
            if options["remove"]:
                self._report_removal(sample_data.remove_sample_data(actor))
                return
            self._report_load(sample_data.seed_sample_data(actor))

    @staticmethod
    def _owner_user_id(tenant: Any) -> Any:
        """The tenant's own owner, through identity's published seam (B1)."""
        from apps.tenancy import seams

        with core_tenancy.tenant_context(str(tenant.id)):
            resolver = seams.resolve("identity", "owner_user_id_for")
            if resolver is not None:
                return resolver(tenant.id)
            users = seams.resolve("identity", "first_user_id")
            if users is not None:
                return users()
        # No published read for it: the load still runs and the audit rows carry
        # no actor id, which is honest — better than inventing a user id that
        # would attribute a demo load to somebody who did not ask for it.
        return None

    def _report_load(self, summary: dict[str, Any]) -> None:
        self.stdout.write("")
        for row in summary["modules"]:
            mark = "OK  " if row["outcome"] == "seeded" else "NOT "
            style = self.style.SUCCESS if row["outcome"] == "seeded" else self.style.WARNING
            # CR-039 wave B: the stable code rides on the LINE, beside the
            # label, because this command is the other surface an operator
            # reads and a code in a screen only is a code half the users of
            # this feature never see. The sentence still follows underneath.
            code = f"  [{row['error_code']}]" if row.get("error_code") else ""
            self.stdout.write(style(f"  {mark} {row['label']:<48} {row['count']:>6} row(s){code}"))
            if row["outcome"] != "seeded" and row.get("detail"):
                # BR-TEN-060: a block that did not load is a NAMED line with a
                # sentence an operator can act on — never a count and never a
                # silent skip (DEF-016's prevention).
                self.stdout.write(f"        {row['detail']}")
            if row.get("failure_class") == "consequence":
                # CR-039 wave B task 7 — five reds, one cause. Without this the
                # command prints a wall of equally-red lines and the operator
                # has no way to tell which one to fix first (DEF-660's shape).
                self.stdout.write(
                    self.style.WARNING(
                        f"        ↳ waiting on {row.get('root_block')} — fix that "
                        "block first; this one will fail the same way"
                    )
                )
        self.stdout.write("")
        self.stdout.write(f"  {summary['seeded_total']} row(s) written in total")
        if summary["succeeded"]:
            self.stdout.write(self.style.SUCCESS("  every block loaded"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  {len(summary['not_loaded'])} block(s) did NOT load — named above"
                )
            )

    def _report_removal(self, plan: dict[str, Any]) -> None:
        self.stdout.write("")
        self.stdout.write(f"  {plan['removed']} row(s) removed")
        for row in plan.get("retained") or []:
            # BR-TEN-066 — *"remove what is free, report the rest BY NAME"*.
            self.stdout.write(self.style.WARNING(f"  KEPT  {row.get('label')}"))
            self.stdout.write(f"        {row.get('reason')}")
        for row in plan.get("blocked") or []:
            self.stdout.write(self.style.WARNING(f"  BLOCKED  {row.get('label')}"))
            self.stdout.write(f"        {row.get('detail')}")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — this IS the command-line half; the endpoint half is tenancy's Sample data panel, already served) E=deferred(no-frontend-half — same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: this command contains NO seeding logic of its own — it resolves a tenant, opens its context and calls the same `apps.tenancy.sample_data` the S8 panel calls, so the two can never disagree about what a seeded tenant looks like · it RUNS in production (BR-TEN-064) because that is where the tenants created before 2026-08-16 live; `seed_demo` keeps its production refusal because it publishes an owner password and this one publishes nothing · the actor is the tenant's own owner where identity publishes a read for it, and NULL where it does not — an invented user id would attribute a demo load to somebody who did not ask for it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

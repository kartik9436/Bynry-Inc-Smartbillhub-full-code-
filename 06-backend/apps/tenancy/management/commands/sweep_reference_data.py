# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-020 (EP-TEN-03 — the fixture-version sweep over existing
#           tenants: `manage.py sweep_reference_data`)   Screens: none
# Rules:    BR-TEN-070 · BR-TEN-071 · BR-TEN-073 · BR-TEN-074 · BR-TEN-075 ·
#           BR-TEN-076 (the mandatory dry-run) · BR-TEN-077 (version-bump guard) ·
#           BR-TEN-079 (the "which tenants are behind" read) · BR-TEN-003 ·
#           BR-TEN-010 · BR-TEN-012 · BR-TEN-016 · BR-TEN-064 (the per-path
#           production split this command inherits from `seed_demo`)
# Tests:    06-backend/tests/test_us_ten_020_sweep.py
# Impacts:  06-backend/docker-entrypoint.sh (OQ-087 — automatic post-migrate) ·
#           09-infra/01 §5 step 4 (whose "NEVER prod" text that ruling amends) ·
#           S8 → Reference data, where the swept rows appear
# ───────────────────────────────────────────────────────
"""`manage.py sweep_reference_data` — deliver new platform reference data to
tenants that already exist.

WHY A NEW COMMAND RATHER THAN A FLAG ON `seed_demo` (BR-TEN-064's precedent)
---------------------------------------------------------------------------
`seed_demo` refuses under production settings on its demo-fixture path because
that path mints a tenant with a PUBLISHED owner password. This command mints no
tenant, no user, no credential and no subscription — it copies platform
reference vocabulary into tenants somebody else provisioned — and production is
the only host where those tenants exist. So it RUNS in production, exactly as
BR-TEN-064 ruled for the sample-data job, and `seed_demo` keeps its refusal.

EXIT CODES, SAID OUT LOUD BECAUSE THIS IS WHERE THEY SILENTLY DEGRADE
---------------------------------------------------------------------
Django's `CommandError` exits 1 by default, so 2 and 3 are passed explicitly as
`returncode=` — otherwise "a tenant failed" and "a list is unexplained-empty"
would both read as "refused before starting", which is the one thing they are
not.

  0  every targeted tenant swept (or nothing to do) and no UNEXPLAINED empty list
  1  REFUSED BEFORE ANY TENANT WAS TOUCHED — non-Postgres vendor, no BE-03 audit
     sink, missing/corrupt fixture, a fixture edited without a version bump
     (BR-TEN-077), or an unknown `--tenant`
  2  the sweep RAN and ≥1 tenant FAILED. The failed subdomains are named; the
     tenants that succeeded keep their writes (BR-TEN-074)
  3  the sweep completed but ≥1 declared list is EMPTY with no recorded reason —
     DEF-016's signal — unless `--allow-empty-reference-lists` was typed

`--dry-run` and `--report` always exit 0: they are reports, exactly like
`seed_demo --check`, and refusing to REPORT was never the point.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.tenancy import models, reference_sweep, services
from core import audit as core_audit


class Command(BaseCommand):
    help = (
        "Deliver new platform reference data to tenants that ALREADY EXIST "
        "(BR-TEN-070: the reference_seed_runs ledger IS the update mechanism). "
        "Per-tenant context, per-tenant transaction, failures isolated and named. "
        "Insert-if-absent only — a sweep never UPDATEs or DELETEs a tenant's row "
        "(BR-TEN-071). Run --dry-run first: it writes nothing (BR-TEN-076)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute and print the exact per-tenant, per-list plan and write "
            "NOTHING — no reference rows, no reference_seed_runs rows, no audit rows. "
            "Required before the first run of any new fixture version (BR-TEN-076). "
            "Always exits 0.",
        )
        parser.add_argument(
            "--report",
            action="store_true",
            help="The 'which tenants are behind' read only (BR-TEN-079): per tenant, "
            "per list, current / behind (X < Y) / never seeded. Read-only, exits 0.",
        )
        parser.add_argument(
            "--tenant",
            metavar="SUBDOMAIN",
            action="append",
            default=None,
            help="Restrict to the named tenant (repeatable). Default: every tenant.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            metavar="N",
            help="Stop after N tenants. Blast-radius control for a first live run — "
            "same motive as --dry-run.",
        )
        parser.add_argument(
            "--allow-empty-reference-lists",
            action="store_true",
            help="Do not exit 3 when a declared reference list is EMPTY with no recorded "
            "reason. Escape hatch for a deliberately partial environment — naming it on "
            "the command line is the point (DEF-016: the unsafe option is the one you type).",
        )

    # ── pre-flight: everything that refuses BEFORE a tenant is touched ──────
    def _refuse_up_front(self) -> str:
        """Returns the fixture version. Raises CommandError (exit 1) otherwise.

        Order is deliberate — cheapest and most fundamental first, so an operator
        on sqlite is told about sqlite rather than about a digest.
        """
        if connection.vendor != "postgresql":
            raise CommandError(
                f"database vendor is '{connection.vendor}' — tenant context is a Postgres "
                "GUC (core/tenancy.py set_config), so the sweep cannot enter any tenant's "
                "context. Nothing was read and nothing was written. Point DATABASE_URL at "
                "the compose postgres:16 service."
            )
        if getattr(core_audit, "_sink", None) is None:
            raise CommandError(
                "no BE-03 audit sink registered (core/audit.py) — a charge-code or tax "
                "write that cannot be audited must not happen (CLAUDE.md rule 7, "
                "BR-TEN-075). Refused before any tenant was touched, exactly as "
                "`seed_demo._blockers` refuses."
            )
        try:
            return reference_sweep.assert_fixture_version_matches_content()
        except reference_sweep.FixtureVersionError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:  # missing/corrupt fixture surfaces the same way
            raise CommandError(
                f"the platform reference fixture could not be read: {type(exc).__name__}. "
                "Nothing was touched."
            ) from exc

    def _targets(self, subdomains: list[str] | None, limit: int | None) -> list[models.Tenant]:
        """`tenants` is the PLATFORM registry and RLS-exempt (B2 §3), so this is
        the one query in the whole story that is not inside a tenant context."""
        qs = models.Tenant.objects.all().order_by("subdomain")
        if subdomains:
            wanted = [s.strip().lower() for s in subdomains]
            qs = qs.filter(subdomain__in=wanted)
            found = set(qs.values_list("subdomain", flat=True))
            missing = [s for s in wanted if s not in found]
            if missing:
                known = sorted(models.Tenant.objects.values_list("subdomain", flat=True))
                raise CommandError(
                    f"unknown --tenant: {', '.join(missing)} (present: "
                    f"{', '.join(known) or 'none'}). Nothing was swept."
                )
        tenants = list(qs)
        if limit is not None and limit >= 0:
            tenants = tenants[:limit]
        return tenants

    # ── output helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _dots(label: str, width: int = 20) -> str:
        return f"{label} {'.' * max(1, width - len(label))}"

    def _print_plan(self, result: dict[str, Any]) -> None:
        head = f"{result['from_version'] or 'never seeded'} → {result['to_version']}"
        would = {
            row["list"]: row["would_seed"]
            for row in result["lists"]
            if row["action"] == reference_sweep.ACTION_SEED
        }
        self.stdout.write(
            f"{self._dots(result['subdomain'])} {head} · would seed "
            + self._fmt_counts(would)
            + (f" · DEFERRED {sorted(result['deferred'])}" if result["deferred"] else "")
        )

    @staticmethod
    def _fmt_counts(counts: dict[str, Any]) -> str:
        if not counts:
            return "{}"
        body = ", ".join(
            f"{name}: {'?' if value is None else value}" for name, value in sorted(counts.items())
        )
        return "{" + body + "}"

    def _print_result(self, result: dict[str, Any]) -> None:
        head = f"{result['from_version'] or 'never seeded'} → {result['to_version']}"
        if result["outcome"] == reference_sweep.OUTCOME_FAILED:
            self.stdout.write(
                self.style.ERROR(
                    f"{self._dots(result['subdomain'])} FAILED ({result['error']}) — rolled "
                    "back whole; the sweep continues (BR-TEN-074)"
                )
            )
            return
        line = f"{self._dots(result['subdomain'])} {head} · seeded " + self._fmt_counts(
            result["seeded"]
        )
        if result["skipped"]:
            line += " · skipped " + self._fmt_counts(
                {code: "unwired" for code in result["skipped"]}
            )
        if result["deferred"]:
            line += f" · DEFERRED {sorted(result['deferred'])}"
        # DEF-253 — the holiday renewal is printed only when it did something.
        # A silent renewal would be a renewal nobody could confirm ran, which
        # is the shape of the defect it closes; a line on every tenant every
        # sweep would be noise that hides the one tenant that needed it.
        if result.get("holidays_added"):
            line += f" · holidays +{result['holidays_added']}"
        self.stdout.write(line)

    def _print_divergences(self, results: list[dict[str, Any]]) -> None:
        """OQ-086: name every divergence; apply none (BR-TEN-071)."""
        rows = [(r["subdomain"], d) for r in results for d in r["divergences"]]
        unverifiable = sorted({code for r in results for code in r["unverifiable"]})
        if not rows and not unverifiable:
            return
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("── corrections NOT applied (OQ-086) ──"))
        for subdomain, d in rows:
            self.stdout.write(
                f"  · {subdomain} {d['list']}/{d['code']}.{d['field']}: fixture "
                f"{d['fixture']!r}, tenant holds {d['tenant_holds']!r} — NOT applied "
                "(BR-TEN-071: a sweep never UPDATEs). OQ-086 rules the fix is an "
                "audited, opt-in apply-correction action; it is not built."
            )
        if unverifiable:
            self.stdout.write(
                "  · not checkable at all: "
                + ", ".join(unverifiable)
                + " — no registered lookup handler, or its serialize() shares no field "
                "with the fixture entry (rating's charge-code handler omits amount / "
                "percent / min_amount by design, and no handler exposes a tax rate). A "
                "corrected AMOUNT or RATE is therefore invisible here and is reported as "
                "unknown rather than as absent."
            )

    # ── handle ──────────────────────────────────────────────────────────────
    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = bool(options["dry_run"])
        report_only = bool(options["report"])
        if dry_run and report_only:
            raise CommandError(
                "--dry-run and --report are two different reports; name one. "
                "--report reads the ledger; --dry-run computes the seeding plan."
            )
        version = self._refuse_up_front()
        tenants = self._targets(options["tenant"], options["limit"])

        self.stdout.write(f"fixture version .... {version}")
        self.stdout.write(f"tenants targeted ... {len(tenants)}")
        if not tenants:
            self.stdout.write("nothing to do — no tenant matched")
            return

        if report_only:
            self._handle_report(tenants)
            return

        run = reference_sweep.sweep(tenants, dry_run=dry_run)
        self.stdout.write("")
        for result in run["tenants"]:
            if dry_run:
                self._print_plan(result)
            else:
                self._print_result(result)
        self._print_divergences(run["tenants"])

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    "--dry-run: NOTHING was written — no reference row, no "
                    "reference_seed_runs row, no audit row (BR-TEN-076)."
                )
            )
            return  # a report always exits 0

        unexplained = self._unexplained_lists(tenants)
        if run["failed"]:
            raise CommandError(
                "sweep completed with failures: "
                + ", ".join(run["failed"])
                + ". Each failed tenant was rolled back WHOLE and carries a "
                "`reference.sweep_failed` audit row; every other tenant keeps its "
                "writes (BR-TEN-074). Re-run after fixing — the sweep is idempotent.",
                returncode=2,
            )
        if unexplained:
            if options["allow_empty_reference_lists"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"{len(unexplained)} UNEXPLAINED empty reference list(s) tolerated "
                        "because --allow-empty-reference-lists was named on the command line: "
                        + ", ".join(unexplained)
                    )
                )
                return
            raise CommandError(
                "UNEXPLAINED empty reference list(s) after the sweep: "
                + ", ".join(unexplained)
                + ". Either wire the owning module's seed_reference_list seam "
                "(BR-TEN-013) or record the reason in "
                "apps.tenancy.services.UNSEEDABLE_REFERENCE_LISTS. This is DEF-016: a "
                "reference list may be legitimately unseedable, but it may never be "
                "quietly empty.",
                returncode=3,
            )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("sweep complete — every targeted tenant is current"))

    def _handle_report(self, tenants: list[models.Tenant]) -> None:
        """BR-TEN-079. Per-tenant loop under each tenant's own context — never
        one cross-tenant SELECT, because `reference_seed_runs` is RLS FORCE."""
        from core import tenancy as core_tenancy

        self.stdout.write("")
        for tenant in tenants:
            with core_tenancy.tenant_context(tenant.id):
                report = reference_sweep.behind_report_for_tenant(tenant)
            behind = report["behind"]
            never = report["never_seeded"]
            if not behind and not never:
                self.stdout.write(f"{self._dots(tenant.subdomain)} current")
                continue
            self.stdout.write(self.style.WARNING(f"{self._dots(tenant.subdomain)} NOT current"))
            for row in report["lists"]:
                if row["state"] == reference_sweep.STATE_BEHIND:
                    self.stdout.write(
                        f"    {row['list']}: behind ({row['at_version']} < "
                        f"{report['fixture_version']})"
                    )
                elif row["state"] == reference_sweep.STATE_NEVER:
                    self.stdout.write(f"    {row['list']}: never seeded")

    def _unexplained_lists(self, tenants: list[models.Tenant]) -> list[str]:
        """DEF-016's machine-checkable signal, gathered per tenant under that
        tenant's own context. `<subdomain>/<list>` so the operator knows WHERE."""
        from core import tenancy as core_tenancy

        found: list[str] = []
        for tenant in tenants:
            with core_tenancy.tenant_context(tenant.id):
                report = services.reference_data_report()
            found.extend(f"{tenant.subdomain}/{code}" for code in report["unexplained"])
        return found


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-020@e7c1a94 (EP-TEN-03 — the sweep command; co-packet US-TEN-002@178c282)
# generated: 2026-08-15 by story-coder (tenancy/identity lane) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-253: the sweep prints `holidays +N` when it renewed a calendar)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — BR-TEN-079 gives this read no A1 screen; A4 records that no UI exposes cross-tenant data and the admin console is v2) E=deferred(no-frontend-half, same reason) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check .✔ (no finding in this lane's files) · black✔ · pytest tests/test_us_ten_020_sweep.py sqlite 25 passed/1 vendor-skipped · live PostgreSQL 16 26 passed · full backend suite `pytest tests` 2581 passed / 160 skipped / 1 xfailed, with 1 PRE-EXISTING FAIL (tests/test_be11_openapi.py snapshot) that was PROVED pre-existing on the untouched baseline BEFORE this lane wrote a line (2400 passed / 144 skipped / 1 xfailed + the same openapi failure) · run_gates: 19 PASS / 2 FAIL / 0 SKIP — and BOTH FAILS ARE OTHER LANES' (G6 names apps/ledger/billing_seam.py:41; G7 names 6 files under apps/ledger, apps/notifications and apps/billing with no review-ledger row). Enumerated mechanically, not assumed: no file of this lane appears in either. The baseline when this lane started was 20 PASS / 0 FAIL (G21 arrived from a concurrent lane mid-session) · LIVE against a real seeded tenant: --report printed `brazosbend …… current` before the bump and 12 per-list `behind (2026.08 < 2026.09)` lines after it; --dry-run wrote zero rows on all three tables; the real run exited 0 and the replay created nothing · RED-PROVED: with one asset type added to the fixture and no version bump, `manage.py sweep_reference_data` exits **1** naming both digests (BR-TEN-077) — measured, not reasoned
# exceptions: exit codes 2 and 3 are passed as CommandError(returncode=…) because Django's default is 1 and the three cases must not read alike — said out loud in the module docstring for the same reason · `--report` and `--dry-run` are mutually exclusive and both always exit 0 · the production guard is NOT inherited from seed_demo: this command runs in production BY DESIGN (BR-TEN-064's per-path precedent), because production is where the tenants are and it mints no tenant, user, credential or subscription · OQ-087's "automatic post-migrate" half is WIRING and lives in 06-backend/docker-entrypoint.sh — a command nobody runs delivers nothing (hard-won law 2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

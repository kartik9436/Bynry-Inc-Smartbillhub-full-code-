#!/usr/bin/env python3
"""`P2.20`'s OWN OUTCOME, PROVED ON REAL PostgreSQL WITH TWO TENANTS.

Brief §7.8, p88, read as an image (B14 rule 42): *"Power BI reads a report over
the same API a screen uses; **RLS applies unchanged**."* That is a statement
about the DATABASE, and CLAUDE.md hard-won law 14 is why it cannot be checked in
the default suite: `config/settings/test.py` hardcodes in-memory SQLite, **which
has no row-level security of any kind**, so every assertion about a policy
passes there by vacuum.

    ./10-scripts/proof-db.sh clone p220
    DATABASE_URL=... PYTHONPATH=06-backend \\
      06-backend/.venv/bin/python 10-scripts/rep_p2_20_service_account_rls_proof.py

⚠ **IT REFUSES TO RUN AS A ROLE RLS DOES NOT APPLY TO, AND THAT REFUSAL IS THE
MOST IMPORTANT LINE IN THE FILE.** PostgreSQL exempts a superuser from every
policy unconditionally, `FORCE` included (`DEF-2717`), and a role with
`BYPASSRLS` likewise. A proof run as either prints the same word as a real one
and means nothing — CLAUDE.md hard-won law 7's *structurally incapable of
failing*. So the role is read out of `pg_roles` first and the run STOPS if it is
exempt, rather than reporting a pass.

⚠ **IT ALSO REFUSES A SINGLE-TENANT DATABASE.** An isolation proof with one
tenant in it has nothing to isolate FROM: every count would be right, every
assertion would hold, and the policy could be absent. The second tenant is
created here if the database has only one, and the run says which it did.
"""

from __future__ import annotations

import os
import sys

import django


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    django.setup()

    from django.db import connection

    from apps.reports import service_accounts as svc
    from apps.reports.models import ReportServiceAccount
    from apps.tenancy.models import Tenant
    from core.tenancy import tenant_context

    failures = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'}  {label}{'' if detail == '' else f' — {detail}'}")
        if not ok:
            failures += 1

    # ── 0 · the role must be one RLS actually applies to ────────────────────
    with connection.cursor() as cur:
        cur.execute(
            "select current_user, rolsuper, rolbypassrls from pg_roles "
            "where rolname = current_user"
        )
        role, is_super, bypasses = cur.fetchone()
    if is_super or bypasses:
        print(
            f"REFUSED: running as {role!r}, which is "
            f"{'a SUPERUSER' if is_super else 'BYPASSRLS'}. PostgreSQL exempts it "
            "from every policy, FORCE included, so this proof would pass over an "
            "absent one. Re-run as a NOSUPERUSER NOBYPASSRLS role."
        )
        return 2
    print(f"role {role!r}: NOSUPERUSER, NOBYPASSRLS — RLS applies\n")

    # ── 1 · two tenants ──────────────────────────────────────────────────────
    tenants = list(Tenant.objects.order_by("created_at")[:2])
    if len(tenants) < 2:
        # ⚠ **CREATED RATHER THAN SKIPPED, AND SAID OUT LOUD.** A seeded clone
        # holds ONE utility, and an isolation proof with nothing to isolate from
        # is not a proof — every count would be right and the policy could be
        # absent. A second tenant ROW is all this needs: no accounts, no bills,
        # nothing but an id for the policy to tell apart from the first.
        second = Tenant.objects.create(
            name="RLS proof neighbour",
            subdomain="rls-proof-neighbour",
            currency="USD",
        )
        print("this database held ONE tenant; a second was created for the proof")
        tenants = [tenants[0], second]
    alpha, beta = tenants[0], tenants[1]
    print(f"tenant A = {alpha.subdomain} · tenant B = {beta.subdomain}\n")

    # ── 2 · one service account per tenant, written in its own context ──────
    tokens: dict[str, str] = {}
    for tenant, granted in ((alpha, ["ar_aging"]), (beta, ["billing_register"])):
        with tenant_context(tenant.id):
            ReportServiceAccount.objects.filter(name="rls proof").delete()
            token, token_hash, prefix = svc.mint_token()
            ReportServiceAccount.objects.create(
                tenant_id=tenant.id,
                name="rls proof",
                token_hash=token_hash,
                token_prefix=prefix,
                report_keys=granted,
            )
            tokens[str(tenant.subdomain)] = token

    # ── 3 · RLS: each tenant sees ITS OWN accounts and no other ─────────────
    for tenant, other in ((alpha, beta), (beta, alpha)):
        with tenant_context(tenant.id):
            mine = list(ReportServiceAccount.objects.all())
            foreign = [
                row for row in mine if str(row.tenant_id) != str(tenant.id)
            ]
            check(
                f"3 · {tenant.subdomain} sees only its own service accounts",
                mine and not foreign,
                f"{len(mine)} visible, {len(foreign)} belonging to another tenant",
            )
            # And the OTHER tenant's row is not merely filtered out by Django —
            # it is not there at all, which is the policy and not the ORM.
            with connection.cursor() as cur:
                cur.execute(
                    "select count(*) from report_service_accounts where tenant_id = %s",
                    [str(other.id)],
                )
                leaked = cur.fetchone()[0]
            check(
                f"3 · raw SQL under {tenant.subdomain} cannot reach {other.subdomain}'s row",
                leaked == 0,
                f"{leaked} row(s) reachable",
            )

    # ── 4 · WITH CHECK: a tenant cannot write another tenant's row ──────────
    with tenant_context(alpha.id):
        refused = False
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "insert into report_service_accounts "
                    "(id, tenant_id, name, token_hash, token_prefix, report_keys, "
                    " created_at, updated_at) "
                    "values (gen_random_uuid(), %s, 'smuggled', 'x', 'x', '[]'::jsonb, "
                    " now(), now())",
                    [str(beta.id)],
                )
        except Exception as exc:  # noqa: BLE001 - the refusal IS the assertion
            refused = "policy" in str(exc).lower() or "row-level" in str(exc).lower()
        check(
            "4 · WITH CHECK refuses a row written for another tenant",
            refused,
            "the insert was accepted" if not refused else "refused by policy",
        )

    # ── 5 · a token is visible ONLY inside its own tenant's context ────────
    # ⚠ **THIS IS THE CASE THAT REDESIGNED THE AUTHENTICATION CLASS.** It first
    # read the credential with NO tenant context, resolving the tenant FROM the
    # token, and failed here with *"resolved to nothing"* — because RLS denies a
    # read whose `app.tenant_id` is unset. The class now looks the token up
    # inside the context `TenantContextMiddleware` sets from the PATH, so the
    # cross-tenant refusal is the policy's rather than a comparison somebody has
    # to remember to write. See `apps/reports/service_account_auth.py`.
    for tenant, other in ((alpha, beta), (beta, alpha)):
        token = tokens[str(tenant.subdomain)]
        with tenant_context(tenant.id):
            found = ReportServiceAccount.objects.filter(
                token_hash=svc.hash_token(token)
            ).first()
        check(
            f"5 · {tenant.subdomain}'s token is found on {tenant.subdomain}'s path",
            found is not None and str(found.tenant_id) == str(tenant.id),
            "resolved" if found else "not found",
        )
        with tenant_context(other.id):
            foreign = ReportServiceAccount.objects.filter(
                token_hash=svc.hash_token(token)
            ).first()
        check(
            f"5 · the SAME token is INVISIBLE on {other.subdomain}'s path",
            foreign is None,
            "RLS hides it; the 404 is the policy's, not a slug comparison's",
        )
    # And with no context at all — the shape the first design depended on.
    orphan = ReportServiceAccount.objects.filter(
        token_hash=svc.hash_token(tokens[str(alpha.subdomain)])
    ).first()
    check(
        "5 · a token is invisible with NO tenant context — deny by default",
        orphan is None,
        "an unset app.tenant_id shows zero rows, which is why the token cannot "
        "be what chooses the tenant",
    )

    # ── 6 · the named list denies what it did not grant ─────────────────────
    with tenant_context(alpha.id):
        account = ReportServiceAccount.objects.get(name="rls proof")
        check(
            "6 · the granted report is allowed",
            svc.may_read(account, "ar_aging"),
            "ar_aging",
        )
        check(
            "6 · an ungranted report is denied",
            not svc.may_read(account, "billing_register"),
            "billing_register — granted to tenant B and not to this one",
        )
        account.report_keys = []
        check(
            "6 · an EMPTY grant denies everything, never everything-by-default",
            not svc.may_read(account, "ar_aging"),
            "empty report_keys",
        )

    # ── 7 · a revoked credential is dead ────────────────────────────────────
    with tenant_context(alpha.id):
        account = ReportServiceAccount.objects.get(name="rls proof")
        check("7 · a live credential is live", svc.is_live(account))
        account.revoked_at = svc.now()
        check("7 · a revoked credential is dead", not svc.is_live(account))

    # ── tidy: the proof's own rows ──────────────────────────────────────────
    for tenant in (alpha, beta):
        with tenant_context(tenant.id):
            ReportServiceAccount.objects.filter(name="rls proof").delete()

    print("\n" + ("ALL PASS" if failures == 0 else f"{failures} FAILURE(S)"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

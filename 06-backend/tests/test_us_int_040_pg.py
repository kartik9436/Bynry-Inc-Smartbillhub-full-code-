# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-040 (EP-INT-11) TC-5 — *"the key presented against Lone Star
#         Ridge's route → unknown caller, identical body to a wrong key"*.
# Rules:  CLAUDE.md hard rule 1 (RLS FORCE; no cross-tenant queryset) ·
#         BR-INT-053 (a machine credential is scoped to ONE tenant) ·
#         BR-INT-044 (the refusal reveals nothing) · BR-TEN-003 (the tenant is
#         the path) · CLAUDE.md law 7 (a check that cannot fail, and a check
#         that reports zero over a scope it silently excludes)
# ───────────────────────────────────────────────────────
"""US-INT-040 TC-5 on PostgreSQL — and an honest account of what this harness can and cannot show.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/postgres \\
        pytest tests/test_us_int_040_pg.py --create-db

⚠ **`--create-db`, NOT `--reuse-db`, AND THE REASON IS WORTH ONE LINE.** The
case below is `django_db(transaction=True)`, and a transactional test TRUNCATES
the tables between tests — including reference data seeded by a MIGRATION
rather than by a fixture, which `subscription_plans` is. Reuse the database
afterwards and the next run fails in `growth_plan` with
`SubscriptionPlan.DoesNotExist` before a line of this file runs: a setup error
that names a fixture in `tenancy` and says nothing about this wave. It is the
harness, not the product, and a fresh database is the whole cure.

⚠ **READ THIS BEFORE ADDING A CASE HERE, BECAUSE TC-5 HAS NOW BEEN WRITTEN
WRONG TWICE AND BOTH DRAFTS LOOKED RIGHT.**

TC-5 says: Brazos Bend's key presented at Lone Star Ridge's address must answer
exactly as a key that never existed does. The obvious test is to call the
partner route under the other tenant's context and assert `404`. **That test
returns `200`, on SQLite AND on PostgreSQL, and neither result means what it
appears to.**

  * **On SQLite** there is no row-level security at all, so
    `serve._connection_for()` — which takes no `tenant_id` argument ON PURPOSE,
    because *"the tenant is already on the database session"* — is simply
    unscoped. Law 7's third shape: a case incapable of passing.
  * **On PostgreSQL** the policies are there and are `FORCE`, but the role the
    Django test connection runs as **bypasses row security**. `SET ROLE
    sbh_rls_probe` is what makes an assertion about RLS a real one, and a
    Django VIEW cannot be called inside it — the view uses the ordinary
    connection. So the second draft ran green-looking machinery over a role for
    which the guarantee is switched off, which is law 7's *looking at the wrong
    thing*: worse than the first draft, because it had `requires_postgres` on it
    and therefore read as rigorous.

**SO THE CLAIM IS PROVED WHERE IT LIVES, WHICH IS THE DATABASE.** What the door
actually leans on is that `integration_connection` and `integration_credential`
are invisible across tenants; `assert_rls_scoped` proves exactly that under the
non-bypassing probe role, and `rls.assert_is_a_real_proof()` fails rather than
skips if the role it was handed can see through the policies. Wave A proves the
same thing for all five tables in `test_us_int_014_pg.py`; it is asserted AGAIN
here because it is this wave's whole tenant story, and a guarantee that lives
only in a neighbour's file is one nobody re-reads when this one changes.

⚠ **WHAT IS THEREFORE NOT PROVED ANYWHERE, STATED WITH ITS NUMBER RATHER THAN
LEFT AS AN ABSENCE:** exactly ONE assertion of TC-5 has no test in this
repository — that the partner ROUTE, called end to end under another tenant's
path, answers 404. Everything it depends on is proved (the tables are scoped
below; the refusal is byte- and time-identical in
`test_us_int_040_issued_key.py`), and the composition of the two is not. It
would need a request issued over a real connection as a non-superuser, which no
harness here has. `DEF-INT-4217` carries it.
"""

from __future__ import annotations

import pytest

from apps.integrations import models
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_int_040_issued_key import (  # the wave's own helpers, unchanged
    PARTNER,
    connect_partner,
    issue,
)
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin


@requires_postgres
@pytest.mark.django_db(transaction=True)
def test_tc5_an_issued_key_is_invisible_from_another_utilitys_context(
    brazos, lonestar, dana, rls
):
    """The guarantee TC-5 rests on, proved under the role that cannot bypass it.

    A key we issue is a row in `integration_credential`. If that row is
    invisible under another utility's `app.tenant_id`, then the door's lookup
    finds nothing there — and *finds nothing* is the same code path, the same
    body and the same time as a key that never existed. That is the whole of
    TC-5, minus the round trip this harness cannot make.

    `rls.assert_is_a_real_proof()` has already run by the time this body starts:
    the fixture refuses a role that can see through the policies, so a green
    here cannot be the vacuous kind.
    """
    connect_partner(brazos, dana)
    minted = issue(brazos, dana).data["key"]
    assert minted.startswith("sbh_live_")

    with live_tenant_context(brazos.id):
        assert models.IntegrationCredential.objects.count() == 1

    for table in ("integration_connection", "integration_credential"):
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)

    # …and nothing of Brazos Bend's is reachable from Lone Star Ridge on ANY of
    # this module's tables, which is the stronger statement and the one that
    # would catch a table added later without a policy.
    assert_no_foreign_rows_anywhere(rls, lonestar, models.TENANT_TABLES)

    # ── AND THE LIMITATION, ASSERTED RATHER THAN WRITTEN IN A COMMENT ───────
    #
    # ⚠ This is the reason the END-TO-END form of TC-5 is absent, pinned so it
    # cannot be mistaken for coverage. Under the ORDINARY Django connection —
    # the one every view in this suite uses — Brazos Bend's credential IS
    # visible from Lone Star Ridge's context, because that role bypasses row
    # security. The policies above are real; the request path cannot be made to
    # run under a role that respects them.
    #
    # **If this line ever goes RED, that is good news:** the harness has gained
    # a non-bypassing request path, the real TC-5 becomes writable, and
    # `DEF-INT-4217` should be closed by writing it. A comment claiming a
    # limitation is not a limitation (hard-won law 1), so it is an assertion.
    with live_tenant_context(lonestar.id):
        bypassed = models.IntegrationCredential.objects.count()
    assert bypassed == 1, (
        "the Django test connection no longer bypasses RLS — the end-to-end TC-5 "
        "is now writable, so write it and close DEF-INT-4217"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-040@wave-R (EP-INT-11) TC-5
# generated: 2026-09-06 by the CR-069 wave R build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=… pytest tests/test_us_int_040_pg.py
# exceptions: skips on the default SQLite suite by design — the guarantee under test does not exist there and a green would be vacuous (hard-won law 14). The END-TO-END form of TC-5 is absent and DEF-INT-4217 carries it; the second test here pins the reason so the absence cannot be mistaken for coverage
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

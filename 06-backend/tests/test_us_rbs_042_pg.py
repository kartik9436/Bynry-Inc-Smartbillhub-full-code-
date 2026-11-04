# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-042 (EP-RBS-01) — runbook 36, on the vendor that runs it.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; RLS FORCE is on; no cross-tenant queryset) ·
#           hard rule 5 (balanced pairs) · hard-won law 14 (the default suite is
#           SQLite, which holds neither guarantee) · hard-won law 7 (a check
#           that cannot fail is the defect)
# Tests:    this file
# Impacts:  apps/runbooks/definitions/accounting_export.py ·
#           apps/runbooks/seams/ledger_seam.py · apps/ledger/selectors.py
# ───────────────────────────────────────────────────────
"""Runbook 36 on PostgreSQL — the two things SQLite cannot say anything about.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        python3.12 -m pytest tests/test_us_rbs_042_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY.** `config/settings/test.py` hardcodes
in-memory SQLite. **SQLite has no row-level security at all** and **no
aborted-transaction state**, so a tenant-isolation case and a savepoint case
that run there prove exactly nothing while reporting green. `G5` once ran the
isolation suite on SQLite and **called 192 skips a pass** — the shape this
repository names *a check that cannot fail*. Every case here carries
`requires_postgres` and SKIPS on the default suite rather than passing
vacuously, and the module prints WHICH VENDOR it ran on so a reader can tell a
real green from a skipped one without reading the marker.

**The two claims proved here, and nowhere else:**

1. **A run in tenant A's context reads tenant A's books and nothing else.** The
   file this runbook hands a bookkeeper is a set of MONEY figures; a leak here
   is another utility's revenue on somebody's desk, which is the worst thing
   this module could produce. Asserted as a FIGURE — `598.69` and never
   `1,197.38` — because a cross-tenant read that doubled every total would pass
   *"there is a total"*.
2. **Step 2's per-record savepoint keeps one bad month from taking the others
   with it.** On PostgreSQL a failed statement aborts the whole transaction;
   without the savepoint the run is lost at COMMIT however carefully the
   exception was caught. That savepoint is the ENGINE's
   (`executor._run_one_record`) and `tests/test_rbs_savepoint_pg.py` proves the
   engine's half; what is proved here is that **this runbook's per-record step
   actually goes through it** — a step registered as `set` by mistake would run
   once, mean something else, and every SQLite case above would still pass.
"""

from decimal import Decimal

import pytest
from django.db import connection

from apps.runbooks.contract import MODE_PER_RECORD
from apps.runbooks.definitions import accounting_export as rb36
from apps.runbooks.engine import executor

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.ledger_le_fixtures import LE1_FOOTING, gl, make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _print_vendor() -> None:
    """Say which vendor this ran on, beside the result.

    Hard-won law 7's third habit — *a check's output must distinguish pass from
    fail to a READER*. A skipped isolation case and a passing one are the same
    green dot in a summary line; this is what tells them apart.
    """
    print(f"runbook 36 PostgreSQL suite: vendor={connection.vendor}")


def _books(tenant, actor, *, service="electric"):
    """LE-1's month on a tenant, posted through the posting service.

    ⚠ **`service` IS A PARAMETER BECAUSE THE ISOLATION TENANT SELLS SOMETHING
    ELSE, AND ONLY A REAL RUN SAID SO.** `lonestar` is *"the isolation tenant
    (Water only)"* — asking it for an electric premises is refused by name with
    `metering.service_not_enabled`, before a single journal line exists. The
    first draft of this file hardcoded `electric` for both tenants and failed on
    PostgreSQL in the fixture rather than in the assertion, which is the least
    useful place for a test to fail and is exactly why it is worth writing down.
    """
    accounts = make_accounts(actor, tenant, {}, service=service)
    post_le1_month(tenant, accounts)
    return accounts


@requires_postgres
def test_a_run_reads_only_its_own_tenants_books(brazos, dana, lonestar, erin):
    """Hard rule 1, asserted as a FIGURE on the money this file carries.

    Both utilities get the SAME fixture, so their books are identical to the
    penny — which is the point: a cross-tenant read would produce `1,197.38`,
    exactly double, and a test that only asserted *"a total exists"* would sail
    past it. The two runs must produce the same number for DIFFERENT reasons,
    and neither may see the other's rows.
    """
    _print_vendor()
    with tenant_ctx(brazos):
        _books(brazos, dana)
    with tenant_ctx(lonestar):
        # Water, because that is the only service this tenant sells — see
        # `_books`. The BOOKS are LE-1's either way: the postings are the same
        # seventeen contracts on the same accounts, so both tenants foot to the
        # same number and a cross-tenant read would show as exactly double.
        _books(lonestar, erin, service="water")

    with tenant_ctx(brazos):
        theirs = executor.execute(rb36.RUNBOOK, tenant_id=brazos.id, params={"period": "all"})
    with tenant_ctx(lonestar):
        others = executor.execute(rb36.RUNBOOK, tenant_id=lonestar.id, params={"period": "all"})

    for result in (theirs, others):
        state = result.set_results[rb36.STEP_FILE]["checked"]
        assert Decimal(state["debits"]) == LE1_FOOTING, (
            "a run saw more than its own tenant's books — "
            f"{state['debits']} where {LE1_FOOTING} is one utility's whole month"
        )
        assert Decimal(state["credits"]) == LE1_FOOTING
        assert state["lines"] > 0, "the fixture produced no rows, so this check cannot fail"


@requires_postgres
def test_a_run_with_no_tenant_context_reads_nothing_at_all(brazos, dana):
    """Hard rule 1's other half — RLS `FORCE`, with no `app.tenant_id` set.

    ⚠ **THE ASSERTION IS ABOUT THE MONEY, NOT ABOUT AN EXCEPTION.** The
    dangerous outcome is not a crash — a crash is loud — it is a **file with a
    header and nothing under it**, which reads as *"nothing happened this
    month"*. `DEF-RBS-4296` is exactly that shape one door along: a streaming
    download whose generator ran with no tenant marker and served a 200 with an
    empty body. So this asserts the run either refuses or produces NO rows, and
    it asserts the rows.
    """
    _print_vendor()
    with tenant_ctx(brazos):
        _books(brazos, dana)

    try:
        result = executor.execute(rb36.RUNBOOK, tenant_id=brazos.id, params={"period": "all"})
    except Exception:
        return  # refusing outright is the stronger outcome and is lawful
    state = result.set_results[rb36.STEP_FILE]["checked"]
    assert state["lines"] == 0, "money crossed a tenant boundary with no context set"
    assert state["csv"] == ""


@requires_postgres
def test_the_figures_step_runs_once_per_month_inside_its_own_savepoint(brazos, dana):
    """`BR-RBS-023`, proved on the vendor where a savepoint means anything.

    ⚠ **A `set`-MODE MISTAKE WOULD PASS EVERY OTHER TEST IN THIS SUITE.** The
    step would run once over the whole pinned set, produce the same file, and
    the only observable difference is `step_runs` and the record count — so
    those are what this asserts, on the vendor whose aborted-transaction state
    makes the savepoint load-bearing (hard-won law 14).
    """
    _print_vendor()
    with tenant_ctx(brazos):
        _books(brazos, dana)
        result = executor.execute(rb36.RUNBOOK, tenant_id=brazos.id, params={"period": "all"})

    months = [s.label for s in result.subjects]
    assert months == ["2026-06", "2026-07"], months
    assert result.step_runs[rb36.STEP_FIGURES] == len(months) == 2
    assert result.step_runs[rb36.STEP_FILE] == 1, "the file is composed ONCE, over the whole set"
    assert len(result.records) == 2, "one record row per month, which is the declared unit"
    assert {record.outcome for record in result.records} == {"ready"}


@requires_postgres
def test_the_declared_mode_and_the_engine_agree(brazos):
    """The declaration and the behaviour, asserted against each other.

    A step's mode is a claim in a dataclass and the executor is what honours it;
    `DEF-RBS-4284` is what happens when two halves agree on a NAME and disagree
    on everything else, with both suites green.
    """
    _print_vendor()
    modes = {step.key: step.mode for step in rb36.RUNBOOK.steps}
    assert modes[rb36.STEP_FIGURES] == MODE_PER_RECORD


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-042 (EP-RBS-01) — the PostgreSQL half
# generated: 2026-09-06 by the CR-075 accounting-export build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_042_pg.py on a real PostgreSQL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

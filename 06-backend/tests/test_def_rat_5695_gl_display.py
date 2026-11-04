# ── Trace ──────────────────────────────────────────────
# Change:  CR/PO ruling 2026-09-17 — the plan wizard's Charges, Taxes and
#          Discounts steps show a GL CODE and NAME where they showed a uuid.
#          PO verbatim: "dont show uuiD- shoe actual 3 of gL code 4000 , 4010
#          something liek this and its name - you might have to pull it from GL
#          code mapping we have it - if GL code is not map then dont show it".
# Rules:   B14 rule 31 (no database id is ever the visible value of a field) ·
#          B1 / BR-TEN-013 (a neighbouring module is reached through its
#          SERVICE layer, never its ORM) · hard rule 1 (tenant scoping).
# ───────────────────────────────────────────────────────
"""The GL display seam: what it answers, and the four ways it answers nothing.

⚠ **THE LOAD-BEARING CASE IS `test_an_unwired_ledger_answers_none_and_does_not
_raise`.** Its neighbour `ledger_account_is_live` RAISES when the ledger
publishes nothing, and is right to — it guards a mapping that freezes onto a
bill. This one renders a table cell, and raising would turn an unwired ledger
into a 500 on the whole Charges step. The two live twenty lines apart in the
same file and a lane "fixing" one into consistency with the other is the
foreseeable mistake; this test is what stops it.
"""

from types import SimpleNamespace

import pytest

from apps.ledger import models as ledger_models
from apps.rating import seams
from core.permissions import SYSTEM_ADMIN
from core.tenancy import tenant_context

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures (env, other_env)

pytestmark = pytest.mark.django_db


def _an_account(env):
    """One live chart row belonging to THIS env's tenant.

    ⚠ **THE `tenant_id=` FILTER IS THE WHOLE POINT AND THE FIRST DRAFT LACKED
    IT.** Without it this returned whatever row the table happened to hold
    first — which under `other_env` was **env's own account** — and the
    cross-tenant case below then failed, apparently proving a leak in
    `ledger_account_display` that does not exist. A fixture that cannot tell one
    tenant's row from another's cannot test tenant scoping, and it fails in the
    direction that looks like a serious finding. `tenant_context` sets the RLS
    GUC; on the sqlite suite there is no RLS to enforce it, so the ORM filter is
    what makes this fixture mean anything at all (hard-won law 14's shape: the
    test database is not the production one).
    """
    return (
        ledger_models.LedgerAccount.objects.filter(
            tenant_id=env.tenant.id, deleted_at__isnull=True
        )
        .order_by("code")
        .first()
    )


def test_a_live_account_answers_its_code_and_name(env):
    account = _an_account(env)
    assert account is not None, "the seeded chart has no live account to read"
    with tenant_context(env.tenant.id):
        shown = seams.ledger_account_display(str(account.id))
    assert shown == {"code": account.code, "name": account.name}
    # The PO asked for "4000, 4010 something like this" — a short numeric code,
    # not a uuid. Pinned so a chart that started serving ids here goes red.
    assert "-" not in shown["code"]
    assert len(shown["code"]) <= 10


def test_a_null_id_answers_none(env):
    with tenant_context(env.tenant.id):
        assert seams.ledger_account_display(None) is None
        assert seams.ledger_account_display("") is None


def test_a_malformed_id_answers_none_rather_than_raising(env):
    with tenant_context(env.tenant.id):
        assert seams.ledger_account_display("not-a-uuid") is None


def test_a_deactivated_account_answers_none(env):
    account = _an_account(env)
    with tenant_context(env.tenant.id):
        assert seams.ledger_account_display(str(account.id)) is not None
        ledger_models.LedgerAccount.objects.filter(pk=account.pk).update(
            deleted_at="2026-09-17T00:00:00Z"
        )
        # IS-1: an account the tenant has retired is not shown as a live mapping.
        assert seams.ledger_account_display(str(account.id)) is None


def test_another_tenants_account_answers_none(env, other_env):
    foreign = _an_account(other_env)
    assert foreign is not None
    # The fixture's own control: prove the row really is the OTHER tenant's
    # before asserting that this tenant cannot see it.
    assert foreign.tenant_id == other_env.tenant.id
    assert foreign.tenant_id != env.tenant.id
    with tenant_context(env.tenant.id):
        # Hard rule 1. Telling this tenant the code would leak another's chart.
        assert seams.ledger_account_display(str(foreign.id)) is None


def test_an_unwired_ledger_answers_none_and_does_not_raise(env, monkeypatch):
    """⚠ THE ONE THAT MATTERS — see this module's docstring.

    `ledger_account_is_live` raises `LedgerSeamNotWired` in this situation and
    must go on doing so. A DISPLAY read may not take a screen down.
    """
    import apps.rating.seams as rating_seams

    monkeypatch.setattr(
        rating_seams, "import_module", lambda name: SimpleNamespace(), raising=True
    )
    with tenant_context(env.tenant.id):
        assert rating_seams.ledger_account_display("anything") is None


def test_a_ledger_that_throws_answers_none(env, monkeypatch):
    """A published read that blows up is still not a reason to 500 a table."""
    import apps.rating.seams as rating_seams

    def _boom(_id):
        raise RuntimeError("the chart is on fire")

    monkeypatch.setattr(
        rating_seams,
        "import_module",
        lambda name: SimpleNamespace(account_display=_boom),
        raising=True,
    )
    with tenant_context(env.tenant.id):
        assert rating_seams.ledger_account_display("anything") is None


def test_the_actor_shape_is_irrelevant_because_this_read_takes_none(env):
    """It is a READ with no actor — recorded so nobody adds a role gate to a
    cell that every role on this screen can already see the rest of."""
    assert SYSTEM_ADMIN  # the constant exists; this read does not consult it
    with tenant_context(env.tenant.id):
        assert seams.ledger_account_display(None) is None

# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-9521 — a vacant unit with no meter fitted could not open an
#          account on a plan whose deposit is priced by meter size.
# Ruling:  PO 2026-10-04 (decision log "THREE PO ANSWERS" item 3), verbatim:
#          *"(c) Let the clerk pick the size on the Deposit step."*
# Rules:   BR-RAT-020 (SUPERSEDED in part 2026-10-03 — by class or size) ·
#          BR-RAT-023 as amended · BR-BIL-012 (the first bill's deposit line)
# Tests:   the RATING half — what the plan asks when no size is recorded, and
#          at a size the clerk picked. The customers half (stored, audited,
#          taken) is `test_def_cus_9521_deposit_size_pick_account.py`.
# ───────────────────────────────────────────────────────
"""A size-priced deposit where no meter is fitted: the clerk picks the size.

THE WORKED FIGURE THE PO WAS SHOWN: Rosa opens an account at 1408 Elm St ·
Unit A before her meter is installed; the plan asks **$150.00** (5/8") or
**$600.00** (2"). With no size recorded the plan's priced sizes are OFFERED;
the clerk picks 2" and the deposit is **$600.00**. Where a meter size IS
recorded the amount follows it exactly as before, whatever was picked.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.rating import seams, selectors

from tests.test_oq_rat_12786_deposit_by_class_or_size import _plan, _world
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 4)
UNIT = str(uuid4())
ACCOUNT = str(uuid4())


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


def _ask(env, monkeypatch, *, recorded, **kwargs):
    plan = _plan(env, _world(env))
    monkeypatch.setattr(seams, "connection_size_for", lambda unit_id, service_code: recorded)
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
        return selectors.deposit_rule_for(plan["id"], residential, **kwargs)


def test_no_size_recorded_offers_the_plans_priced_sizes(env, monkeypatch):
    """Red before the fix: the refusal carried no `sizes` to pick from."""
    answer = _ask(env, monkeypatch, recorded=None, unit_id=UNIT)
    assert answer["amount"] is None
    assert answer["refusal"] == "size_not_recorded"
    offered = {row["size_class"]: (row["label"], row["amount"]) for row in answer["sizes"]}
    assert offered == {
        "W-58": ('Water 5/8"', Decimal("150.00")),
        "W-2": ('Water 2"', Decimal("600.00")),
    }


def test_the_clerk_picks_2_inch_and_the_deposit_is_600(env, monkeypatch):
    """The ruling's figure: no meter, 2" picked → **$600.00**."""
    answer = _ask(env, monkeypatch, recorded=None, unit_id=UNIT, size_class="W-2")
    assert answer["amount"] == Decimal("600.00")
    assert answer["size_class"] == "W-2"
    assert answer["size_label"] == 'Water 2"'
    assert answer["size_picked"] is True
    assert "refusal" not in answer


def test_a_recorded_size_wins_over_a_pick(env, monkeypatch):
    """A 5/8" meter is fitted: **$150.00**, and nothing reads as picked."""
    answer = _ask(env, monkeypatch, recorded="W-58", unit_id=UNIT, size_class="W-2")
    assert answer["amount"] == Decimal("150.00")
    assert not answer.get("size_picked")


def test_a_recorded_size_offers_no_picker(env, monkeypatch):
    answer = _ask(env, monkeypatch, recorded="W-58", unit_id=UNIT)
    assert answer["amount"] == Decimal("150.00")
    assert "sizes" not in answer


def test_a_picked_size_the_plan_does_not_price_is_refused_by_name(env, monkeypatch):
    answer = _ask(env, monkeypatch, recorded=None, unit_id=UNIT, size_class="W-1")
    assert answer["amount"] is None
    assert answer["refusal"] == "size_not_priced"


def test_the_first_bill_honours_the_size_picked_at_the_counter(env, monkeypatch):
    """`deposit_rule_for(account_id=…)` — billing's call — reads the size the
    clerk picked off the account. Red before the fix: `size_not_recorded`, so
    the first bill of an account opened at the counter would be refused."""
    monkeypatch.setattr(seams, "account_unit_id", lambda account_id: UNIT)
    monkeypatch.setattr(seams, "account_deposit_size_class", lambda account_id: "W-2", raising=False)
    answer = _ask(env, monkeypatch, recorded=None, account_id=ACCOUNT)
    assert answer["amount"] == Decimal("600.00")

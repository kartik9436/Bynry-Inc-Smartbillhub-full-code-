# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-1082 (a master account with OPEN SUB-ACCOUNTS is WARNED
#           when it is moved out — never refused, at the commit or on step 1)
# Ruling:   **PO 2026-09-20, closing `OQ-CUS-12515` on option (b), verbatim:
#           *"option B - give a warning and allow it; if owner has sold the
#           property to new owner then we are transfering all libalities and
#           ownership to new owner"*.** This file asserted the REFUSAL until
#           that ruling and is rewritten, not deleted: the contract it guards
#           — *a clerk is TOLD* — is still real, and a case that vanishes
#           takes its coverage with it.
# Rules:    BR-CUS-171 (WHO an open child is — the LINK only, and the whole of
#           what that row signs) · BR-CUS-055 (occupancy keys off the behaviour
#           CLASS, never the label) · BR-SHL-019 (one commit, all or nothing) ·
#           B14 rule 33 (a fact ≤ 6 words; RATIONALE is zero words on screen)
# OQs:      OQ-CUS-12515 (CLOSED 2026-09-20, option (b) — the ratification,
#           answered *no*) · OQ-531 (CLOSED 2026-08-27, reading (A) BY
#           PREMISES, which is where the child list comes from)
# Defects:  DEF-CUS-5930 (the move committed with nothing said) ·
#           DEF-CUS-5950 (the rule it was filed against is not the rule that
#           says this)
# Impacts:  apps/customers/services.py (`move_out`) ·
#           07-frontend/src/features/customers/MoveOutWizard.tsx (step 1) ·
#           06-backend/tests/test_move_out_scenarios.py scenario `E1`
# ───────────────────────────────────────────────────────
"""BR-CUS-1082 — and the half that matters is that it warns the RIGHT account.

**THIS RULE REVERSED ON 2026-09-20 AND THE TEST THAT PROVED IT HAD TO REVERSE
WITH IT.** `DEF-CUS-5930` was a master account that closed over two live
tenants **with nothing said** — status terminal, `closed_at` written, every
agreement ended and `MVO-26-0001` allocated. The fix refused it outright. The PO
ruled that refusal out on option (b) and gave a reason the lane did not have: a
landlord leaving is not a landlord abandoning their tenants, because where the
property has been SOLD the act is a **TRANSFER**, which carries the account, its
liabilities and its ownership to the new owner with the tenants untouched
beneath it. The case the refusal protected against already has its own flow, and
blocking the move-out blocked only the legitimate remainder.

**SO THE DEFECT WAS NEVER THAT THE MOVE COMMITTED — IT IS THAT IT COMMITTED IN
SILENCE**, and that is what these four cases now pin. `tc1` asserts the move
COMMITS, closes properly, leaves the tenants open, **and says so on the
response**.

⚠ **THE FALSE PASS THIS FILE IS WRITTEN AGAINST, AND IT HAS TWO DIRECTIONS
RATHER THAN ONE.** A warning that never appears passes a test that only checks
the commit succeeded — every move-out commits now. A warning that appears on
EVERY account passes `tc1` exactly as a correct one does. So the four cases are
built as two pairs: `tc1` and `tc4` fail if the warning is missing or miscounts,
`tc2` and `tc3` fail if it fires where no child is open. A file holding only
`tc1` could not tell any of the four apart.

⚠ **ONE DEFINITION OF AN OPEN CHILD, WHICH SURVIVED THE REVERSAL UNCHANGED.**
`tc4` asserts the number the warning carries is the same number
`move_out_settlement.settlement_for` serves as `open_sub_accounts`, because two
definitions of one word is the defect class this module paid for twice on
2026-09-19 (`DEF-CUS-5901`) — and it would be that whether the answer refuses or
warns.

**PROVED RED FIRST (hard-won law 7), in the harness that runs it:** scenario
`E1` of `tests/test_move_out_scenarios.py`, through
`./10-scripts/move_out_scenarios.sh E1` on `config.settings.pgtest`, plus four
mutations of this file's own subject — the warning deleted, the warning widened
to every account, the count hard-coded, and the `if` inverted. Each was run,
seen red in the pair that owns it and green in the other, and reverted.
"""

from datetime import date

import pytest

from apps.customers import models as customer_models
from apps.customers import move_out_settlement
from apps.customers import moves
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services

from tests.test_br_cus_171_master_children import (  # the ONE estate builder
    OPENED,
    _common_area,
    _declare_owner,
    _master,
    _occupying_account,
    _ordinary_unit,
    _plan,
    _premises,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

MOVED_OUT_ON = date(2026, 8, 20)

#: The one code `services.move_out` appends for this rule. Named here once so a
#: rename breaks every case at the same moment rather than silently passing the
#: three that only count warnings.
WARNING_CODE = "master_closed_over_open_sub_accounts"


def _estate(tenant, actor, *, children=2):
    """A declared-owner building: one common area, `children` occupied flats.

    The same shape `E1` provisions in the scenario suite, built through the
    product's own doors rather than through fixtures that write rows — so the
    child list is DERIVED exactly as it is in production (BR-CUS-171).
    """
    plan = _plan(tenant)  # ⚠ the PLAN hangs off the tenant, the estate off the actor
    premises = _premises(actor)
    _common_area(actor, premises, plan, label="Hallway & exterior lighting")
    master = customer_models.Account.objects.get(pk=_master(actor, premises)["id"])
    _declare_owner(actor, premises, master)
    tenants = [
        _occupying_account(
            actor,
            _ordinary_unit(actor, premises, plan, label=f"Unit {letter}"),
            name=name,
        )
        for letter, name in list(zip("ABCDE", ("Elena Rivera", "Marcus Webb", "Ada Fenn",
                                               "Ruth Oyelaran", "Tom Beck")))[:children]
    ]
    return master, tenants


def _move_records_for(account):
    """Every `move_records` row for this account — read from the table, never
    inferred from the response. `DEF-CUS-5930`'s damage WAS the row, and this
    ruling makes the row lawful, so it is now read to prove it IS there."""
    return list(moves.MoveRecord.objects.filter(account_id=account.pk))


def _move_out(actor, account):
    return customer_services.move_out(
        actor, account.id, {"moved_out_on": MOVED_OUT_ON.isoformat()}
    )


def _sub_account_warnings(answer):
    """**THIS RULE'S warning rows, never *a* warning.**

    Every move-out comes back carrying several — `MOVE_OUT_UNAVAILABLE` alone
    contributes five — so a case that asserted `answer["warnings"]` were
    non-empty would pass on a response that never mentioned sub-accounts at
    all, and would go on passing after this rule was deleted. The same reason
    `check_refusal_name` names its key instead of asserting *something was
    refused*.
    """
    return [w for w in (answer.get("warnings") or []) if w.get("code") == WARNING_CODE]


# ══════════════════════════════════════════════════════════════════════════
# THE PIN — the move that must COMMIT, and must not do it in silence
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1082_tc1__a_master_with_open_children_commits_and_the_clerk_is_told(
    brazos, dana
):
    """PO 2026-09-20, option (b). The move goes through, and it SAYS so.

    ⚠ **BOTH HALVES OR NEITHER.** Asserting only that the commit succeeded
    would pass with the rule deleted entirely — every move-out commits now —
    and asserting only the warning would pass over an account that never
    closed. `DEF-CUS-5930` was a close that happened in silence; this ruling
    keeps the close and removes the silence, so the case has to read both.
    """
    with tenant_ctx(brazos):
        master, tenants = _estate(brazos, dana, children=2)
        assert len(customer_selectors.sub_accounts_for_master(master)) == 2

        answer = _move_out(dana, master)

        # ── half one · THE CLERK IS TOLD, by name and with the count ───────
        warned = _sub_account_warnings(answer)
        assert len(warned) == 1, f"wanted one sub-account warning; got {answer.get('warnings')}"
        row = warned[0]
        assert row["br_ref"] == "BR-CUS-1082"
        # The SAME catalogue key step 1 draws, so the strip before the commit
        # and the row after it are one pair of words in all eleven catalogues.
        assert row["message_key"] == "customers.account.has_open_sub_accounts"
        assert row["open_sub_accounts"] == 2
        assert row["count"] == 2          # i18next's own plural selector
        assert row["account_no"] == master.account_no

        # ── half two · AND THE ACCOUNT REALLY CLOSED ──────────────────────
        # Read back from PostgreSQL rather than trusted from the response: the
        # defect this file was born for was about what the tables held.
        master.refresh_from_db()
        assert master.closed_at == MOVED_OUT_ON
        assert master.status.behavior_class == "terminal"
        assert answer["move_no"], "a move-out that commits writes its numbered record"
        assert len(_move_records_for(master)) == 1

        # ── and the tenants are UNTOUCHED, which is the PO's own reason ────
        # *"we are transfering all libalities and ownership to new owner"* —
        # the children go on being supplied; closing the landlord is not a
        # cascade and never was.
        for tenant in tenants:
            tenant.refresh_from_db()
            assert tenant.closed_at is None
            assert tenant.status.behavior_class != "terminal"


# ══════════════════════════════════════════════════════════════════════════
# THE TWO THAT KILL THE FALSE PASS — a warning on every account
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1082_tc2__the_same_master_is_not_warned_once_its_children_close(brazos, dana):
    """**The rule is *open* children, not *any* children.**

    Close the two tenants and the landlord's own close says nothing about
    sub-accounts, because there are none. A warning keyed on `kind == 'master'`
    would fire here and pass `tc1`.
    """
    with tenant_ctx(brazos):
        master, tenants = _estate(brazos, dana, children=2)
        for tenant in tenants:
            _move_out(dana, tenant)

        # BR-CUS-055 — a closed tenant drops out of the count on the day they
        # close, with nobody maintaining anything. That is BR-CUS-171's own
        # claim and this is the case that spends it.
        assert customer_selectors.sub_accounts_for_master(master) == []

        answer = _move_out(dana, master)
        assert _sub_account_warnings(answer) == []
        master.refresh_from_db()
        assert master.closed_at == MOVED_OUT_ON
        assert master.status.behavior_class == "terminal"


def test_br_cus_1082_tc3__an_ordinary_tenant_is_not_touched_by_this_rule(brazos, dana):
    """The common path in the product, and the one a broad warning would spam.

    An ordinary account is not a master, so `sub_accounts_for_master` returns
    `[]` before issuing a single query and the move-out — including the
    warnings it comes back with — is byte-for-byte what it was before
    `BR-CUS-1082` existed at all.
    """
    with tenant_ctx(brazos):
        _master_account, tenants = _estate(brazos, dana, children=1)
        tenant = tenants[0]

        answer = _move_out(dana, tenant)
        assert _sub_account_warnings(answer) == []
        tenant.refresh_from_db()
        assert tenant.closed_at == MOVED_OUT_ON
        assert tenant.status.behavior_class == "terminal"
        assert answer["move_no"]


def test_br_cus_1082_tc4__the_warning_counts_what_the_settlement_serves(brazos, dana):
    """**One number, two readers** — `DEF-CUS-5901`'s defect class refused.

    `settlement_for` has served `open_sub_accounts` since `CR-056` W6 and the
    screen has rendered it since 2026-08-24. If the commit counted children its
    own way the strip could say `3` while the receipt said `2`, and a clerk
    would have no way to tell which number was the real one. The reversal from
    refusal to warning did not touch this: it is the same selector, read in the
    same place.
    """
    with tenant_ctx(brazos):
        master, _tenants = _estate(brazos, dana, children=3)

        served = move_out_settlement.settlement_for(dana, master.id)["open_sub_accounts"]
        answer = _move_out(dana, master)

        assert served == 3
        warned = _sub_account_warnings(answer)
        assert len(warned) == 1
        assert warned[0]["open_sub_accounts"] == served
        assert warned[0]["count"] == served

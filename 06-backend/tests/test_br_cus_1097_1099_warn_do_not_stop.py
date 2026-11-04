# ── Trace ──────────────────────────────────────────────
# Rules:   BR-CUS-1097 (PO 2026-09-25 — *"Show what's still owed and let the
#          clerk proceed"*) · BR-CUS-1099 (PO 2026-09-25 — *"So we warn user ,
#          but we dont stop user"*) · BR-CUS-1096 (their pair and the principle)
#          · BR-CUS-039 · BR-CUS-100 (the rule BR-CUS-1099 reverses half of) ·
#          BR-CUS-104 (AMENDED — the fee's TIMING survives, the GATE does not) ·
#          CLAUDE.md hard rule 7 (every money action writes `audit_log`)
# Defects: DEF-CUS-6735 · DEF-CUS-6736 · DEF-CUS-6755
# Tests:   this file — the ones both rules' register rows say are OWED
# ───────────────────────────────────────────────────────
"""**THE PRODUCT TELLS THE CLERK WHAT IS TRUE AND DOES NOT STOP THEM ACTING.**

Five rulings on 2026-09-25 were one principle. Two of them reversed behaviour
this module had shipped, and **both register rows said the same thing in the
same column: `⛔ NONE — and the code does the opposite.`** A rule with no failing
test is green for ever, which is why these exist.

════════════════════════════════════════════════════════════════════════════
EACH RULING HAS TWO HALVES AND BOTH ARE ASSERTED
════════════════════════════════════════════════════════════════════════════
Both register rows demand it in as many words — *"it must assert BOTH halves"*.
The half everybody remembers is that the act now succeeds. The half that is
easy to lose is the RECORD, and it is the half that matters more: **with nothing
blocking, the record is the only protection there is.** So every case below
asserts the act AND asserts what the act wrote down.

════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THESE PASS WRONGLY — asked before they were written (law 7)
════════════════════════════════════════════════════════════════════════════
  * **A test that only asserts no exception.** `mark_reconnecting` on a
    ZERO-balance account has never raised, so a case that forgot to give the
    account a debt would pass against the old code. Every case below asserts the
    balance it is acting over is **NON-ZERO**, and names the figure.
  * **A test that asserts the warning EXISTS.** A warning list that always
    contains every code would pass too, so the settled cases assert the list is
    EMPTY where nothing is owed and no proof is missing.
  * **A test that reads `ready` alone.** `ready` is a boolean a refactor could
    hard-code, so the blocker CODES are asserted by name in both directions.

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE GREEN, AND AGAINST WHAT
════════════════════════════════════════════════════════════════════════════
Run against the tip these were written from (`202f3a9ca`), where
`reconnect_blockers` still returned `not_settled` and `assert_service_proved`
still raised `cut_on_unrecorded_service`, every case in this file fails — the
two reversal cases on the refusal itself, the record cases on the missing keys,
and the hold case on `displayed_state` not existing at all. The run is quoted in
the decision-log row for 2026-09-25, lane CUTPATH.
"""

from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_record, disconnects

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _reconnect_charge, _scheduled
from tests.test_w7_disconnects import _account, _at_tier, _owes, _prove_tier_3_service

pytestmark = pytest.mark.django_db

#: **BRETT CALLOWAY, and it is the case that was put to the Product Owner.**
#: He owes $1,204.50 plus the reconnection fee, pays $400.00, agrees a plan for
#: the rest, and the clerk restores water the same day. The figure is written out
#: rather than derived so a reader can check it against `BR-CUS-1097`'s own text.
BRETT_ARREARS = D("1204.50")


def _cut(actor, tenant, monkeypatch, *, owed, **kwargs):
    """A case standing at `cut`, over a REAL balance, through the real verbs."""
    account = _scheduled(actor, tenant, monkeypatch, owed=owed, **kwargs)
    disconnects.commit_cut(actor, account["id"], cut_on=CUT_ON, as_of=TODAY)
    # The cut raised and ISSUED the reconnection fee, so what the account owes
    # afterwards is the arrears plus that fee. The seam is re-pointed at the
    # combined figure rather than left at the pre-cut one, because
    # `DEF-CUS-6050` is exactly the defect of those two numbers disagreeing.
    _owes(monkeypatch, owed)
    return account


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-1097 — THE BALANCE NEED NOT BE CLEAR TO RECONNECT
# ═══════════════════════════════════════════════════════════════════════════
def test_br_cus_1097__brett_calloway_is_reconnected_owing_money(
    brazos, marcus, monkeypatch, audit_rows
):
    """The worked case from the ruling, run end to end.

    ⛔ **THIS RAISED `not_settled` UNTIL 2026-09-25.** `reconnect_blockers`
    returned it whenever `balance > 0`, `reconnection_readiness` reported
    `ready: False`, and `mark_reconnecting` refused. PO ruling of that day,
    verbatim, choosing option (a) of two: *"Show what's still owed and let the
    clerk proceed"*.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch, owed=BRETT_ARREARS)

        readiness = disconnects.reconnection_readiness(account["id"])
        # ⚠ **THE PRECONDITION IS ASSERTED, NOT ASSUMED.** A zero balance would
        # make this whole test pass against the OLD code.
        assert readiness["balance"]["stored"] == "1204.5000"
        assert readiness["ready"] is True
        assert [b["code"] for b in readiness["blockers"]] == []

        payload = disconnects.mark_reconnecting(
            marcus, account["id"], on_date=CUT_ON + timedelta(days=7)
        )
        assert payload["state"] == disconnects.STATE_RECONNECTING


def test_br_cus_1097__what_was_owed_is_on_the_record_and_what_was_paid_is_not_invented(
    brazos, marcus, monkeypatch, audit_rows
):
    """The SECOND half of the ruling, which is the half that protects anybody.

    *"At reconnect the product captures, itself, without asking the clerk for
    anything: what was still owed at the moment service was restored · what had
    been paid · who restored it · when."*

    Three of the four are readable and are asserted. **The fourth is a stated
    ABSENCE and that is deliberate** — nothing on the disconnect path reads what
    has been PAID against arrears (`DEF-PAY-6074`), and a figure invented here
    would be a second, wrong answer to a question `BR-BIL-160` answers exactly.
    A test that let an invented number through would be worse than this one.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch, owed=BRETT_ARREARS)
        on_date = CUT_ON + timedelta(days=7)

        payload = disconnects.mark_reconnecting(marcus, account["id"], on_date=on_date)

        # WHAT WAS STILL OWED — the same read the warning quotes, so the number
        # a clerk was shown and the number recorded cannot differ.
        assert payload["owed_at_reconnection"]["stored"] == "1204.5000"
        assert payload["owed_at_reconnection"]["display"] == "1204.50"
        # WHEN.
        assert payload["on_date"] == str(on_date)
        # WHAT THE CLERK WAS TOLD, recorded beside the act rather than only
        # rendered and forgotten.
        assert [w["code"] for w in payload["warnings"]] == ["money_still_owed"]
        assert "1204.50" in payload["warnings"][0]["detail"]
        # WHAT HAD BEEN PAID — named as unread, never guessed.
        assert payload["paid_absence"]["code"] == "paid_against_arrears_not_read"
        # WHO — `audit_log`, CLAUDE.md hard rule 7. The capture sink is a list in
        # this suite, so the trail is read from there and asserted NON-EMPTY
        # first: a census over a number that cannot move proves nothing.
        mine = [r for r in audit_rows if r.get("action") == disconnects.AUDIT_RECONNECTING]
        assert len(mine) == 1
        assert mine[0]["actor_user_id"] is not None
        assert mine[0]["after"]["owed_at_reconnection"]["stored"] == "1204.5000"


def test_br_cus_1097__a_settled_account_carries_no_warning_at_all(
    brazos, marcus, monkeypatch, audit_rows
):
    """The other direction, and it is what stops the warning becoming noise.

    A warning list that always answered would pass every case above.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch, owed=BRETT_ARREARS)
        _owes(monkeypatch, D("0"))

        readiness = disconnects.reconnection_readiness(account["id"])
        assert readiness["balance"]["stored"] == "0.0000"
        assert readiness["ready"] is True
        assert list(readiness["warnings"]) == []


def test_br_cus_1097__an_unreadable_balance_still_refuses(
    brazos, marcus, monkeypatch, audit_rows
):
    """⛔ **THE RULING DOES NOT REACH THIS ONE AND IT MUST NOT BE SWEPT UP.**

    `BR-CUS-1097` is about a balance that is KNOWN and not clear. A balance the
    ledger could not answer is a different fact: §5.8.1's caption for this state
    is *"paid, awaiting a visit"*, and moving a case there on a reading that
    FAILED would put that sentence on screen with nothing behind it. The account
    is not stuck — the reading is, and it is reported.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch, owed=BRETT_ARREARS)
        _owes(monkeypatch, None, available=False)

        readiness = disconnects.reconnection_readiness(account["id"])
        assert readiness["ready"] is False
        assert readiness["refusal"]["code"] == disconnects.HALT_BALANCE_UNREADABLE

        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnects.mark_reconnecting(marcus, account["id"], on_date=CUT_ON)
        assert refused.value.code == disconnects.HALT_BALANCE_UNREADABLE


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-1099 — NO RECORDED PROOF OF CERTIFIED SERVICE WARNS; IT DOES NOT REFUSE
# ═══════════════════════════════════════════════════════════════════════════
def test_br_cus_1099__a_cut_is_scheduled_with_no_proof_and_the_absence_is_recorded(
    brazos, marcus, monkeypatch, audit_rows
):
    """⛔ **THIS RAISED `cut_on_unrecorded_service` UNTIL 2026-09-25.**

    PO ruling, verbatim: *"So we warn user , but we dont stop user - We can't
    send a certified notice — a final-tier cut isn't lawful without one"*.

    ⚠ **THE RECORD HALF IS THE POINT HERE MORE THAN ANYWHERE.** This is the one
    ruling of the five where **the record protects the UTILITY**: a final-tier
    cut without proved certified service is a cut it may not lawfully have made,
    so its absence is the utility's own exposure. The rule says what must be
    captured — *that no proof was recorded, who scheduled it, when* — and all
    three are asserted below.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("640.00"))
        _reconnect_charge(brazos)
        account = _account(marcus, brazos, label="Unit P", name="Proofless Ltd.")
        _at_tier(marcus, account["id"], disconnects.TIER_3)
        # ⚠ **NO `_prove_tier_3_service` CALL, AND THAT IS THE WHOLE FIXTURE.**
        assert (
            disconnects.service_proof_for(
                disconnects.open_case_for(account["id"]), tier=disconnects.TIER_3
            )["recorded"]
            is False
        )

        payload = disconnects.schedule_cut(
            marcus,
            account["id"],
            cut_on=CUT_ON,
            as_of=TODAY,
            services={"electric": disconnects.TREATMENT_FULL},
        )

        assert payload["state"] == disconnects.STATE_SCHEDULED
        # THAT NO PROOF WAS RECORDED — on the payload, so on the audited row.
        assert [w["code"] for w in payload["warnings"]] == ["cut_on_unrecorded_service"]
        assert payload["warnings"][0]["br_ref"] == "BR-CUS-1099"
        # WHO, and WHEN — `audit_log`, hard rule 7.
        mine = [r for r in audit_rows if r.get("action") == disconnects.AUDIT_CUT_SCHEDULED]
        assert len(mine) == 1
        assert mine[0]["actor_user_id"] is not None
        assert mine[0]["after"]["warnings"][0]["code"] == "cut_on_unrecorded_service"


def test_br_cus_1099__the_non_certified_channel_refusal_is_NOT_removed_with_it(
    brazos, marcus, monkeypatch, audit_rows
):
    """⛔ **THE RULING'S OWN BOUNDARY, ASSERTED SO A LATER LANE CANNOT DRIFT PAST IT.**

    The PO's words are about the ABSENCE of proof and say nothing about a notice
    recorded as served by ANOTHER channel. `BR-CUS-1099`'s register row says so
    in its own statement column, and `assert_service_proved`'s docstring warns
    *"do not remove it with the first"*. **Reading a ruling wider than it was
    given is how a refusal on a household's water supply disappears by
    accident**, so this case exists to go red if it does.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("640.00"))
        _reconnect_charge(brazos)
        account = _account(marcus, brazos, label="Unit Q", name="Wrong Channel Co.")
        _at_tier(marcus, account["id"], disconnects.TIER_3)
        case = disconnects.open_case_for(account["id"])
        notice = disconnects.latest_notice_at_tier(case, disconnects.TIER_3)
        disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_POSTED,
            reference="POSTED-0001",
            served_on=CUT_ON - timedelta(days=3),
        )

        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnects.schedule_cut(
                marcus,
                account["id"],
                cut_on=CUT_ON,
                as_of=TODAY,
                services={"electric": disconnects.TREATMENT_FULL},
            )
        assert refused.value.code == "tier_3_proof_not_certified"


def test_br_cus_1099__a_proved_cut_carries_no_warning(
    brazos, marcus, monkeypatch, audit_rows
):
    """The mirror, so the warning cannot become a constant nobody reads."""
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        assert disconnects.service_proof_warnings(case) == ()


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-6755 — A HELD CASE READ `At notice` AND `On hold` AT ONCE
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_6744__a_protected_case_reads_on_hold_on_the_record(
    brazos, marcus, monkeypatch, audit_rows
):
    """Blueprint p144's third drawn promise: *"the case moves to the On hold segment"*.

    ⚠ **DERIVED, NOT STORED, AND THE TEST SAYS SO BY CHECKING BOTH.** The stored
    state must STILL read `notice_sent` — `_ladder_restarts` rejects a stored
    `on_hold` by name, and a payment plan's protection has no expiry to un-write
    one by — while what the clerk reads says `on_hold`. A test that asserted
    only the displayed value would pass over a lane that wrote the column.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("640.00"))
        account = _account(marcus, brazos, label="Unit H", name="Held Bakery")
        _at_tier(marcus, account["id"], disconnects.TIER_3)

        before = disconnect_record.record_detail(
            disconnects.open_case_for(account["id"]).case_no
        )
        assert before["state"]["value"] == disconnects.STATE_NOTICE_SENT

        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=TODAY - timedelta(days=1),
            expires_on=TODAY + timedelta(days=60),
        )

        after = disconnect_record.record_detail(
            disconnects.open_case_for(account["id"]).case_no
        )
        assert after["state"]["value"] == disconnects.STATE_ON_HOLD
        # ⚠ **THE COLUMN DID NOT MOVE**, and that is as much the design as the
        # line above it.
        assert after["state_stored"]["value"] == disconnects.STATE_NOTICE_SENT
        assert disconnects.open_case_for(account["id"]).state == disconnects.STATE_NOTICE_SENT


def test_def_cus_6744__a_cut_case_is_never_relabelled_on_hold(
    brazos, marcus, monkeypatch, audit_rows
):
    """The boundary. A protection filed AFTER the supply went off does not make
    the case `On hold` — the supply is already off, and saying *On hold* over it
    would be a worse sentence than the one it replaced. `HOLDABLE_CASE_STATES`
    is what keeps the derivation away from every state in which something has
    already happened.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch, owed=BRETT_ARREARS)
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=TODAY - timedelta(days=1),
            expires_on=TODAY + timedelta(days=60),
        )
        case = disconnects.open_case_for(account["id"])
        assert disconnects.displayed_state(case, as_of=TODAY) == disconnects.STATE_CUT

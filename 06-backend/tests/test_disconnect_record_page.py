# ── Trace ──────────────────────────────────────────────
# Change:   CR-125-BRC07 — the DISCONNECT CASE RECORD, `GET /disconnects/{ref}`,
#           blueprint `02 Accounts Menu Blueprint.pdf` p143 (the record), p144
#           (hold) and p145 (mark as cut). PO ruling, verbatim: *"okay build it
#           as per specification and as per what you ahve mentioned -
#           Disconnect details view — every section - i will consolidate
#           actions - too many actions - keep critical ones"*.
# Rules:    BR-CUS-039 · BR-CUS-100 · BR-CUS-103/104/107 · BR-BIL-007 ·
#           BR-MET-1161 / hard rule 8 · B14 rule 31 · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""What this file holds the disconnect record to — the seven things that could
go wrong here and be INVISIBLE to every other check in this repository.

**1 · A CELL CARRYING NEITHER A VALUE NOR A REASON.** The whole record is
label→value rows and `_fact` promises *"never both, and never neither"*. A cell
with neither renders an empty row that reads as a rendering bug; a cell with
both lets the screen draw whichever it reaches for first. Asserted as an
INVARIANT over the WHOLE payload, recursively, rather than cell by cell —
because a cell-by-cell test covers the cells whoever wrote it remembered, and
the next section added to this screen would be untested by construction.

**2 · THE TWO ABSENT FACTS QUIETLY ACQUIRING A VALUE.** `Oldest debt` and the
name half of `Raised by` have no source anywhere (the module's §2). The
dangerous repair is not leaving them blank — it is a later lane deriving the
age from `opened_on`, or the name from `audit_log`, because both look
available. This asserts the CODE of each absence, so a substitution goes red
and names itself.

**3 · A DELIVERY CLAIM APPEARING IN THE NOTICES TABLE.** `delivery_state` is
NULL by a deliberate rule and the drawn `STATE` column cannot be filled. A lane
"finishing" the table by mapping a raised notice to `Queued` and an attested one
to `Sent` would be making a delivery claim this product cannot make — which is
`DEF-692`'s shape. The table's rows are asserted to carry no delivery field at
all.

**4 · A PRICE APPEARING WHERE THE CHARGE CODE DOES NOT RESOLVE.** Three sources
disagree about the reconnection fee — the drawing and the signed worked figure
say `$75.00`, the seeded catalogue spells the code differently and prices it
`$45.00`, and `commit_cut` looks up a third spelling. **That is a money figure
and a fact only the PO holds.** This asserts that when the code does not
resolve the payload carries NO number anywhere — not in the fee, not in the
total — and carries the server's own refusal instead.

**5 · `Mark as cut` BECOMING PRESSABLE WHEN THE SERVER WOULD REFUSE.** The
button is drawn GREYED and the grey is `cut_readiness`. A preview that says
*ready* over a case `commit_cut` would refuse is the exact defect a greyed
button exists to prevent — the clerk presses it, the supply does not go off,
and nobody learns why. This drives a case that is genuinely refused and asserts
both the refusal CODE and that `ready` is false.

**6 · THE ACTION SET GROWING.** Fifteen disconnect routes exist on the server
and the PO has ruled *"too many actions - keep critical ones"*. `ACTIONS` is
asserted to be exactly the drawn three. A fourth is a ruling, not a commit.

**7 · A DATABASE ID AS A FIELD'S VISIBLE VALUE.** B14 rule 31. The payload
carries `account_id` so the two write actions have an address to post to, so a
test that merely greps the payload for a uuid would fail on correct code. This
asserts the narrower true thing: no `value` a label points at is a uuid.

⚠ **RED PROVED FIRST for every assertion in this file** (hard-won law 7), in
this lane's own `git worktree` and through `pytest`, which is the harness that
will run them — never a direct module invocation, which is the half `DEF-GOV-3733`
added to that law.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_record as dr
from apps.customers import disconnects
from apps.rating import models as rating_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_w7_disconnects import _account, _at_tier, _owes

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)
OWED = D("2410.00")

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


# ═══════════════════════════════════════════════════════════════════════════
# helpers — every one drives the REAL service, never a hand-written row
# ═══════════════════════════════════════════════════════════════════════════
def _case_with_number(actor, tenant, monkeypatch, *, tier=disconnects.TIER_2, name="Bramble Bakery"):
    """A case that ARRIVED at `tier` through the real `advance()`, with a number.

    ⚠ **THE NUMBER IS SET AFTER THE FACT AND THAT IS A FIXTURE CONCERN, NOT A
    BEHAVIOUR ONE.** `_allocate_case_no` reads the tenant's `disconnect_case`
    numbering series, which a test tenant provisioned by these fixtures does not
    carry — so a case opened here is born with `case_no = NULL`, exactly as the
    model's own comment says of a host provisioned before `OQ-427` closed. The
    record is addressed BY that number (B14 rule 31), so a test of the record
    needs one; writing it here keeps the ladder walk real and changes nothing
    the record reads.
    """
    _owes(monkeypatch, OWED)
    account = _account(actor, tenant, name=name)
    _at_tier(actor, account["id"], tier)
    case = disconnects.open_case_for(account["id"])
    case.case_no = "DSC-26-0003"
    case.save(update_fields=["case_no"])
    return account, case


def _walk_facts(node, path="") -> list[tuple[str, dict]]:
    """Every `_fact`-shaped cell in the payload, wherever it is nested.

    ⚠ **THE RECURSION IS THE POINT** — `test_move_record_page._walk_facts`'
    reasoning, and it applies harder here because this payload is five sections
    deep and a section is added to it every time the drawing gains a row.
    """
    found: list[tuple[str, dict]] = []
    if isinstance(node, dict):
        if set(node) == {"value", "unavailable"}:
            found.append((path, node))
            return found
        for key, value in node.items():
            found += _walk_facts(value, f"{path}.{key}" if path else key)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            found += _walk_facts(value, f"{path}[{index}]")
    return found


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE INVARIANT — never both, and never neither
# ═══════════════════════════════════════════════════════════════════════════
def test_every_cell_carries_a_value_or_a_reason_and_never_both(brazos, marcus, monkeypatch):
    """§1. Asserted over the WHOLE payload, recursively."""
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)

        cells = _walk_facts(payload)
        # A guard that found no cells would pass in silence — hard-won law 7's
        # *incapable of failing* shape. The record draws more than a dozen.
        assert len(cells) >= 10, cells

        for path, cell in cells:
            both = cell["value"] is not None and cell["unavailable"] is not None
            neither = cell["value"] is None and cell["unavailable"] is None
            assert not both, f"{path} carries a value AND a reason"
            assert not neither, f"{path} carries neither a value nor a reason"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE TWO FACTS p143 DRAWS THAT NOTHING IN THIS REPOSITORY HOLDS
# ═══════════════════════════════════════════════════════════════════════════
def test_the_two_drawn_facts_with_no_source_are_absences_and_not_derivations(
    brazos, marcus, monkeypatch
):
    """§2. **The dangerous repair is a derivation, not a blank.**

    `opened_on` is right beside `oldest_debt` and subtracting it from today
    would produce a plausible age for a figure that has no source; `audit_log`
    holds a `disconnect.case.opened` actor and reading it would produce a name
    that disappears when the log is pruned. Both look available. Neither is the
    fact the drawing names.
    """
    with tenant_ctx(brazos):
        _account_, case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)
        the_case = payload["the_case"]

        assert the_case["oldest_debt"]["value"] is None
        assert the_case["oldest_debt"]["unavailable"]["code"] == "oldest_debt_age_has_no_source"

        assert the_case["raised_by"]["value"] is None
        assert the_case["raised_by"]["unavailable"]["code"] == "case_opener_not_recorded"

        # ⚠ **THE DATE HALF IS REAL AND IS SERVED.** `Raised by S. Ortiz ·
        # 04/14/2026` is two facts and only one of them is missing; an absence
        # covering both would hide a date the table actually holds.
        assert the_case["opened_on"]["value"] == case.opened_on.isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE NOTICES TABLE MAKES NO DELIVERY CLAIM
# ═══════════════════════════════════════════════════════════════════════════
def test_the_notices_table_is_two_columns_and_claims_no_delivery(brazos, marcus, monkeypatch):
    """§3 · `DEF-692`'s shape. The drawing draws four columns and two of them
    cannot be filled — `delivery_state` is NULL by rule and `service_channel` is
    the PROOF channel, null until a person attests."""
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)
        notices = payload["notices"]

        # Two notices climbing to tier 2, newest first.
        assert len(notices["rows"]) == 2
        assert [row["tier"] for row in notices["rows"]] == [
            disconnects.TIER_2,
            disconnects.TIER_1,
        ]

        for row in notices["rows"]:
            # ⚠ **NOT `row["delivery_state"] is None` — the field must not EXIST.**
            # A null field is one `or "Queued"` away from a delivery claim; an
            # absent one cannot be defaulted by a screen that never saw it.
            assert "delivery_state" not in row
            assert row["channel"] is None
            assert row["proved"] is False

        assert (
            notices["state_column_unavailable"]["code"]
            == "notice_delivery_state_is_null_by_rule"
        )
        assert notices["channel_column_empty"]["code"] == "service_channel_is_the_proof_channel"
        assert notices["delivery"] == disconnects.DELIVERY_UNAVAILABLE


# ═══════════════════════════════════════════════════════════════════════════
# 4 · NO PRICE WHERE THE CHARGE CODE DOES NOT RESOLVE
# ═══════════════════════════════════════════════════════════════════════════
def test_no_reconnection_figure_is_invented_when_the_charge_code_is_missing(
    brazos, marcus, monkeypatch
):
    """§4. **`$75.00` and `$45.00` are both wrong answers here**, and so is a
    total computed over a missing addend.

    ⚠ **THIS WAS THE TREE'S DEFAULT STATE UNTIL 2026-09-20 AND IS NOW A
    DELIBERATE ONE.** `CR-125-BRC07` §4 had the price as the one number the PO
    must settle — the drawing and the signed worked figure said `$75.00`, the
    seeded catalogue spelled the code `RECON` at `$45.00`, and `commit_cut`
    looked up `CC-RECON` — and **no seed created a reconnection code at all**,
    so every tenant including this fixture's was already in the state under
    test. **The PO ruled it** (*"reconnection fee is $75 - fix the code and
    seed"*, `OQ-CUS-12518`): `a3a572501` pointed the constant at `RECON` and
    seeded it at `$75.00`, so a provisioned tenant now HAS one and this case
    stopped arriving for free. It went RED that day, on nobody's change.

    **The case is not weaker for being set up rather than stumbled into** — a
    utility that never configures its reconnection code, or retires it, is a
    real state, and a record that invented a price for an act the product cannot
    charge is worse than one that says it cannot price it. So the row is REMOVED
    rather than the assertions relaxed, which is the posture
    `test_w7_cut_reconnect._scheduled(charge=False)` took the same day and for
    the same reason: weakening a case to match a fixture is how a guard quietly
    stops guarding (`DEF-705`).
    """
    with tenant_ctx(brazos):
        rating_models.Charge.objects.filter(
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        ).delete()
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)
        cut = payload["what_a_cut_would_do"]

        fee = cut["reconnection_fee"]
        assert fee["charge_code_configured"] is False
        assert fee["stored"] is None and fee["display"] is None
        assert fee["unavailable"] is not None

        # ⚠ **THE TOTAL GOES TOO.** `To clear before reconnection` is the
        # arrear PLUS the fee (BR-CUS-104), so a total served over an absent
        # fee would be the arrear wearing the total's label — a wrong number in
        # a right number's clothes, on the panel that previews taking a
        # household's supply away.
        assert cut["to_clear_before_reconnection"]["stored"] is None
        assert cut["to_clear_before_reconnection"]["unavailable"] is not None

        # ⚠ **ASKED OF THE MONEY CELLS AND NEVER OF THE WHOLE PAYLOAD, AND THE
        # FIRST DRAFT ASKED THE WHOLE PAYLOAD AND FAILED ON CORRECT CODE.**
        # `BR-CUS-104`'s own ruling text quotes `$8,315.00`, and `DSC-02.4`'s
        # quotes the signed worked figure — those are RULINGS travelling with
        # their reasoning, which is exactly what a stated absence is for. What
        # must carry no number is the cell a clerk reads a price off.
        for cell in (fee, cut["to_clear_before_reconnection"]):
            assert cell["stored"] is None
            assert cell["display"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 5 · `Mark as cut` IS GREYED, WITH THE SERVER'S OWN REASON
# ═══════════════════════════════════════════════════════════════════════════
def test_mark_as_cut_is_refused_and_carries_the_servers_own_first_reason(
    brazos, marcus, monkeypatch
):
    """§5. A tier-2 case is not scheduled, so the FIRST thing a clerk must be
    told is that nothing is cut until a date is set — not the fourth thing."""
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)
        readiness = payload["actions"]["mark_as_cut"]

        assert readiness["ready"] is False
        assert readiness["refusal"]["code"] == "cut_not_scheduled"

        # ⚠ **ALL OF THEM, NOT THE FIRST.** `commit_cut` stops at the first
        # refusal because it is performing an act; a clerk asking *what would I
        # have to do* and told one thing at a time makes four trips.
        codes = {row["code"] for row in readiness["blockers"]}
        assert "cut_not_scheduled" in codes
        assert "no_services_chosen" in codes
        # ⛔ **`cut_on_unrecorded_service` LEFT THIS LIST ON 2026-09-25** —
        # `BR-CUS-1099` (PO: *"So we warn user , but we dont stop user"*),
        # `DEF-CUS-6736`. It is not gone from the screen: it is a WARNING now,
        # asserted below and rendered under the action row rather than as the
        # reason a button is grey. Re-pointed rather than deleted, because a
        # green test pinning a reversed rule is worse than no test (DEF-705).
        assert "cut_on_unrecorded_service" not in codes
        assert [row["code"] for row in readiness["warnings"]] == [
            "cut_on_unrecorded_service"
        ]

        # Every blocker carries a sentence a clerk can read. An empty detail is
        # a greyed button with nothing beside it, which is the defect.
        assert all(row["detail"].strip() for row in readiness["blockers"])


def test_the_preview_and_the_act_refuse_for_the_same_reason(brazos, marcus, monkeypatch):
    """§5's real guarantee: the preview is not a SECOND opinion.

    ⚠ **THIS IS THE ASSERTION THAT MATTERS AND IT IS THE ONE EASIEST TO WRITE
    WRONGLY.** Testing that the preview refuses proves nothing on its own — a
    preview that refuses EVERYTHING would pass it. What has to be true is that
    the preview and `commit_cut` refuse the SAME case for the SAME named
    reason, so a clerk reading the grey is reading the act.
    """
    with tenant_ctx(brazos):
        account, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=TODAY, as_of=TODAY)

        assert payload["actions"]["mark_as_cut"]["refusal"]["code"] == refusal.value.code


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THREE CONTROLS ON SCREEN, AND THE COMMIT IS THE ONE THE STATE ADMITS
# ═══════════════════════════════════════════════════════════════════════════
def test_the_record_carries_exactly_three_actions(brazos, marcus, monkeypatch):
    """§6. PO ruling: *"i will consolidate actions - too many actions - keep
    critical ones"*. A fourth CONTROL is a ruling, not a commit.

    ⚠ **AMENDED 2026-09-20 AND THE COUNT DID NOT MOVE.** This case asserted the
    flat three for every case in every state. The PO has since ruled the way
    back into the product — *"The other half of the job. Today a utility can cut
    supply and cannot restore it from the product."* — so the COMMIT is now the
    one this case's state admits, and `mark_as_cut` is still it on a case at
    notice, which is what this case builds. `DRAWN_ACTIONS` keeps the drawn set
    under a name of its own; `available` is what the screen offers.

    ⚠ **THE COUNT IS STILL THREE BECAUSE THE COMMITS ARE STATE-EXCLUSIVE** — a
    case is `scheduled` or `cut` or `reconnecting`, never two — which is the
    reason this does not reopen *"too many actions"*. The other states are
    asserted in `test_br_cus_1083_visit_outcomes.py`.
    """
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)

        assert payload["actions"]["available"] == ["hold", "open_account", "mark_as_cut"]
        assert dr.DRAWN_ACTIONS == ("hold", "open_account", "mark_as_cut")
        assert len(payload["actions"]["available"]) == 3


def test_the_hold_dialog_promises_only_what_recording_a_protection_does(
    brazos, marcus, monkeypatch
):
    """**THE RULING THIS LANE TOOK, PINNED SO IT CANNOT DRIFT BACK.**

    p144 promises three immediate effects: the cut date is cleared, the ladder
    stops, and the case moves to `On hold`. Measured against
    `disconnects.record_protection`, which writes a protection row and touches
    the case NOT AT ALL, only the middle one is true — the ladder stops because
    `halt_reason` is COMPUTED, which is the module's own design.

    So the dialog states the one that is true and states the cut date STAYING
    as its own consequence, which is the fact a clerk actually needs before
    pressing it. **A lane that makes the other two true must do it in
    `disconnects.py` and move these rows in the same commit** — a dialog that
    says three things happen when one does is the outcome this test exists to
    prevent.
    """
    with tenant_ctx(brazos):
        account, case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)
        hold = payload["actions"]["hold"]

        # ⚠ **`case_moves_to_on_hold` JOINED THIS LIST ON 2026-09-25**
        # (`DEF-CUS-6755`). p144 draws THREE immediate effects and this product
        # kept ONE; `disconnects.displayed_state` now DERIVES `on_hold` from the
        # protections in force, so the second is kept too. The cut date STILL
        # stays and is still stated as its own consequence.
        assert [row["code"] for row in hold["effects"]] == [
            "ladder_stops",
            "case_moves_to_on_hold",
            "cut_date_stays",
            "debt_stays_and_ages",
        ]
        assert hold["promises_not_kept"]["code"] == (
            "hold_clears_no_date_and_moves_no_state"
        )

        # ── AND THE MEASUREMENT BEHIND IT, RE-RUN RATHER THAN QUOTED ────────
        # A comment claiming a guarantee is not the guarantee (hard-won law 1).
        # This drives the real write and reads the real row back.
        before = case.cut_scheduled_for
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=TODAY,
            expires_on=date(2026, 10, 25),
        )
        case.refresh_from_db()
        assert case.cut_scheduled_for == before, "the hold cleared a cut date after all"
        # ⚠ **THE COLUMN STILL DOES NOT MOVE, AND THAT IS STILL THE DESIGN**
        # (`_ladder_restarts` rejects a stored `on_hold` by name). What changed
        # on 2026-09-25 is that the record DERIVES it — asserted on the next
        # line, so this file proves both halves of `DEF-CUS-6755` rather than
        # only the one that was already true.
        assert case.state != disconnects.STATE_ON_HOLD, "the hold moved the state after all"
        assert (
            disconnects.displayed_state(case, as_of=TODAY) == disconnects.STATE_ON_HOLD
        ), "the record still reads the ladder state beside a live protection"
        # …and the one promise that IS kept.
        assert (
            disconnects.halt_reason(account["id"], as_of=TODAY, case=case)["code"]
            == disconnects.HALT_PROTECTED
        )


def test_the_fourth_hold_reason_is_drawn_and_refused_rather_than_offered(
    brazos, marcus, monkeypatch
):
    """p144 draws FOUR reasons and `record_protection` names THREE.

    *A bill is disputed* cannot be recorded: nothing in this repository stores a
    disputed AMOUNT, which is why `protection_check` already serves that row as
    `unavailable` and never as `pass`. The dialog draws it and refuses it with
    the server's sentence — a control that is always pressed and always refused
    is the shape hard-won law 2's mirror names.
    """
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)
        hold = payload["actions"]["hold"]

        # ⚠ **THE SET, NOT THE ORDER — THE ORDER IS THE DRAWING'S** and has its
        # own case below. This one asks the question it was written for: are
        # the offered reasons exactly the three `record_protection` accepts?
        assert set(hold["kinds"]) == set(disconnects.PROTECTIONS)
        assert len(hold["kinds"]) == len(disconnects.PROTECTIONS)
        assert dr.HOLD_KIND_DISPUTE not in hold["kinds"]
        assert hold["dispute_unrecordable"]["code"] == "dispute_is_not_a_protection"

        # And the drawn `Review on` field follows `record_protection`'s own
        # rules rather than a second set: required for a certificate and a
        # moratorium, REFUSED for a plan (BR-CUS-043 holds that one while the
        # plan is active and current, so a stored date would be a second and
        # slower answer).
        assert hold["review_date"][disconnects.PROTECTION_MEDICAL] == "required"
        assert hold["review_date"][disconnects.PROTECTION_MORATORIUM] == "required"
        assert hold["review_date"][disconnects.PROTECTION_PLAN] == "refused"


# ═══════════════════════════════════════════════════════════════════════════
# 7 · NO DATABASE ID IS A FIELD'S VISIBLE VALUE (B14 rule 31)
# ═══════════════════════════════════════════════════════════════════════════
def test_no_visible_value_is_a_database_id(brazos, marcus, monkeypatch):
    """§7. `account_id` rides on `actions` so the two writes have an address to
    post to — rule 31 forbids an id as the VISIBLE VALUE of a field, never in
    the response (`DEF-2716`'s proved fix keeps one on a `title=`). So the
    assertion is the narrower true thing."""
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)

        for path, cell in _walk_facts(payload):
            value = cell["value"]
            assert not (isinstance(value, str) and _UUID.match(value)), f"{path} is a uuid"

        # The record is ADDRESSED by the number, which is the other half.
        assert payload["case_no"]["value"] == "DSC-26-0003"


# ═══════════════════════════════════════════════════════════════════════════
# THE ADDRESS — hard rule 8, and the reference is the KEY
# ═══════════════════════════════════════════════════════════════════════════
def test_the_address_is_walked_to_the_premises_and_the_record_declares_none(
    brazos, marcus, monkeypatch
):
    """**CLAUDE.md hard rule 8 / BR-MET-1161.** An address is stored on
    `premises` and NOWHERE else; every other entity derives it by walking
    there. A disconnect case declares no address column and this record copies
    none onto itself — the line under the title is the premises' own."""
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)

        assert payload["address"]["value"], payload["address"]
        # The case model holds nothing address-shaped for anyone to read.
        columns = {field.name for field in disconnects.DisconnectCase._meta.get_fields()}
        # ⚠ **`state` IS NOT ON THIS LIST AND THE FIRST DRAFT PUT IT THERE.**
        # `disconnect_cases.state` is the CASE's state — `notice_sent`,
        # `scheduled`, `cut` — and has nothing to do with a postal one, so the
        # guard failed on correct code. Law 7's *looking at the wrong thing*,
        # caught by the assertion rather than by what it was pointed at.
        for forbidden in (
            "address",
            "address_line",
            "city",
            "postal_code",
            "postcode",
            "lat",
            "lng",
        ):
            assert forbidden not in columns


def test_the_reference_is_the_case_number_and_matching_is_case_insensitive(
    brazos, marcus, monkeypatch
):
    """B14 rule 31 — the record is addressed by `DSC-26-0003` and never by a
    uuid, and the blueprint's own URL is lower (`/disconnects/dsc-26-0003`)
    while the number a clerk quotes is upper."""
    with tenant_ctx(brazos):
        _account_, case = _case_with_number(marcus, brazos, monkeypatch)

        assert dr.record_detail("dsc-26-0003", as_of=TODAY)["case_no"]["value"] == "DSC-26-0003"

        # A uuid is NOT an address for this record.
        with pytest.raises(errors.NotFoundError):
            dr.record_detail(str(case.pk), as_of=TODAY)


def test_an_unknown_reference_is_a_404_and_never_a_403(brazos, marcus, monkeypatch):
    """HR-1 — the boundary must not confirm that a row exists somewhere else."""
    with tenant_ctx(brazos):
        _case_with_number(marcus, brazos, monkeypatch)
        with pytest.raises(errors.NotFoundError):
            dr.record_detail("DSC-26-9999", as_of=TODAY)


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUTE — resolved through `config/urls.py`, and in the right ORDER
# ═══════════════════════════════════════════════════════════════════════════
def test_both_disconnect_paths_resolve_and_schedule_wins_the_static_segment():
    """⚠ **THE INCLUDE ORDER IS LOAD-BEARING AND NOTHING ELSE CHECKS IT.**

    `transfer_disconnect_api` mounts `disconnects/schedule` and this module
    mounts `disconnects/<str:ref>`. Django resolves the FIRST match and stops,
    so an include placed above that one would swallow the schedule POST and
    read the word *"schedule"* as a case number — `accounts/master`'s trap and
    `DEF-520`'s. Both are resolved HERE, through `config/urls.py`, so a future
    lane cannot reorder or lose either include silently.
    """
    from django.urls import resolve

    # ⚠ **IDENTITY, NOT `__name__`, AND THE FIRST DRAFT USED `__name__` AND
    # PASSED FOR THE WRONG REASON.** DRF's `@api_view` returns a wrapper called
    # `view`, so BOTH routes answer `"view"` — the assertion could not tell the
    # two apart at all and would have gone green over the include being in the
    # wrong order. Law 7's *check that cannot fail*, found by running it.
    from apps.customers import transfer_disconnect_api

    assert resolve("/api/brazosbend/disconnects/schedule").func is (
        transfer_disconnect_api.schedule_cut
    )
    assert resolve("/api/brazosbend/disconnects/dsc-26-0003").func is dr.disconnect_record


# ═══════════════════════════════════════════════════════════════════════════
# THE DRAWN ORDER — p143 and p144 read differently from `disconnects.PROTECTIONS`
# ═══════════════════════════════════════════════════════════════════════════
def test_the_four_protections_come_back_in_the_order_the_drawing_reads(
    brazos, marcus, monkeypatch
):
    """**FOUND BY LOOKING AT THE RUNNING SCREEN, NOT BY A TEST** (hard-won law 6).

    `disconnects.PROTECTIONS` is `(medical, payment_plan, weather_moratorium)`
    and both p143 and p144 read `Medical certificate · Weather · A payment
    plan`. B14 rule 41 says the product matches the blueprint, and an ORDER is
    exactly the kind of thing a drawing owns — so the record re-orders what the
    writer publishes rather than the writer changing for one screen.
    """
    with tenant_ctx(brazos):
        _account_, _case = _case_with_number(marcus, brazos, monkeypatch)
        payload = dr.record_detail("DSC-26-0003", as_of=TODAY)

        assert [row["check"] for row in payload["protections"]["checks"]] == [
            disconnects.PROTECTION_MEDICAL,
            disconnects.PROTECTION_MORATORIUM,
            disconnects.PROTECTION_PLAN,
            dr.HOLD_KIND_DISPUTE,
        ]
        assert payload["actions"]["hold"]["kinds"] == [
            disconnects.PROTECTION_MEDICAL,
            disconnects.PROTECTION_MORATORIUM,
            disconnects.PROTECTION_PLAN,
        ]


def test_a_protection_the_drawing_does_not_know_about_still_reaches_the_screen():
    """⚠ **THE HALF THAT MATTERS, AND IT IS THE SILENT ONE.**

    A sort key written as a LIST would mean a fourth protection added to
    `disconnects.PROTECTIONS` never reaching either surface — and that failure
    is invisible: the row exists, the API serves it, `tsc` and every test pass,
    and the screen simply never offers it. That is the eleventh-service lesson
    (`CLAUDE.md` hard-won law 2) applied before it can bite, so `_as_drawn`
    keeps anything it does not name, AFTER the ones it does.

    This case needs no database — it is arithmetic over a list — which is why
    it takes no fixture and runs in milliseconds.
    """
    ordered = dr._as_drawn(
        [
            disconnects.PROTECTION_PLAN,
            "a_fifth_protection_nobody_has_drawn",
            disconnects.PROTECTION_MEDICAL,
        ]
    )
    assert ordered == [
        disconnects.PROTECTION_MEDICAL,
        disconnects.PROTECTION_PLAN,
        "a_fifth_protection_nobody_has_drawn",
    ]

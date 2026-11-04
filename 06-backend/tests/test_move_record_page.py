# ── Trace ──────────────────────────────────────────────
# Change:   The MOVE RECORD screen, `GET /moves/{ref}` — blueprint
#           `02 Accounts Menu Blueprint.pdf` p074, approved by the PO
#           2026-09-19 (*"we have to buid … we have it in drawing that is our
#           next work"*). The action bar was ruled the same day: TWO doors,
#           `Open the account` and `Open the customer`, and no action.
# Rules:    BR-CUS-150/151 (a record of the JOB) · BR-CUS-056 (earliest legal
#           start) · BR-MET-1161 / hard rule 8 (the address is WALKED from the
#           premises) · B1 (no cross-module join) · B14 rule 31 (no database id
#           is a visible value) · CLAUDE.md rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""What this file holds the move-record page to — the five things that could go
wrong here and be INVISIBLE to every other check in the repo.

**1 · A CELL CARRYING NEITHER A VALUE NOR A REASON.** The whole screen is
label→value rows, and the module's own `_fact` promises *"never both, and never
neither"*. A cell with both lets a screen render whichever it reaches for first;
a cell with neither renders an empty row that reads as a rendering bug. Neither
is visible to `tsc`, to a snapshot, or to any gate — so it is asserted here as
an INVARIANT over the whole payload rather than cell by cell, because a
cell-by-cell test only covers the cells somebody remembered.

**2 · AN IN-FLIGHT MOVE 404-ing.** Half of what blueprint p073 draws is a move
still in progress, and the list gives every row an `↗ Open`. A page that
resolved only `move_records` would 404 on all of them — and would do it
*correctly*, because there genuinely is no record row yet. The draft is reached
through `wizard_parks.reference`, and this asserts the URL is the SAME string
before and after the commit, which is the property that makes the link durable.

**3 · AN ABSENCE COLLAPSING INTO A DASH.** DEF-075 / DEF-127's shape. *"This
has not happened yet"*, *"the seam cannot answer"* and *"this unit holds no
meter"* are three different facts, and a screen that prints one dash for all
three tells a clerk to go and look for something that does not exist. Tested by
asserting the CODE, never merely that something was absent.

**4 · THE PAGE GROWING AN ACTION.** The blueprint's ruling is that this record
has no actions, which is unusual enough that somebody will "improve" it. There
is no write endpoint to test, so this asserts the shape the screen reads: the
`doors` map, and nothing beside it.

**5 · A DATABASE ID RENDERED AS A FIELD'S VALUE.** B14 rule 31. The payload
carries ids for ROUTES, so a test that merely greps the payload for a uuid would
fail on correct code. This asserts the narrower true thing: no *visible* value —
no `value` a label points at — is a uuid.

⚠ **RED PROVED FIRST for every assertion in this file** (hard-won law 7), in
this lane's own `git worktree` and never in the shared tree: each guard was
broken, run, and its failure quoted in the lane report.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from apps.customers import models as customers_models
from apps.customers import move_record_reads as mrr
from core import errors

from tests import identity_fixtures
from tests.test_cr039_wd_move_records import _moved_out
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


# ═══════════════════════════════════════════════════════════════════════════
# helpers — every one drives the REAL service, never a hand-written row
# ═══════════════════════════════════════════════════════════════════════════
def _walk_facts(node, path="") -> list[tuple[str, dict]]:
    """Every `_fact`-shaped cell in the payload, wherever it is nested.

    ⚠ **THE RECURSION IS THE POINT.** A test that listed the cells by hand
    would cover the cells whoever wrote it remembered, and the next section
    added to this screen would be untested by construction — which is how a
    check comes to report zero over a scope it silently excludes (hard-won law
    7's fifth shape).
    """
    found: list[tuple[str, dict]] = []
    if isinstance(node, dict):
        if set(node) >= {"value", "unavailable"}:
            found.append((path, node))
            return found
        for key, value in node.items():
            found += _walk_facts(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found += _walk_facts(item, f"{path}[{i}]")
    return found


def _move_in(actor, tenant, *, label="1408 Elm Street"):
    """One completed move-in **through the real flow**, and the record it left.

    ⚠ **NEVER `MoveRecord.objects.create(...)`, AND NEVER JUST AN OCCUPANT.**
    The first draft of this helper called `_mover`, which creates an occupying
    account and performs no move at all — so every assertion below ran against
    `None` and failed for a reason that had nothing to do with the screen. The
    thing under test is what the PAGE makes of what the FLOW leaves, so the flow
    is what runs: an outgoing account is moved out, and the next occupant moves
    in after it.
    """
    from apps.customers import models as cmodels, moves, services

    account, _unit, _out = _moved_out(actor, tenant, label=label)
    # ⚠ **REFRESHED, BECAUSE THE FIXTURE'S INSTANCE IS STALE.**
    # `services.move_out` writes `closed_at` on its OWN copy of the row, so the
    # object the helper hands back still reads `closed_at = None`. Computing the
    # incoming start from it raises `NoneType + timedelta` — which is what the
    # first draft of this file did, and the failure named the arithmetic rather
    # than the cause.
    account.refresh_from_db()
    result = services.move_in(
        actor,
        str(account.id),
        {
            "account_type": "residential",
            # BR-CUS-056 — the incoming account starts the day AFTER the
            # outgoing one's last day, and an earlier date is refused.
            "opened_at": (account.closed_at + timedelta(days=1)).isoformat(),
            "contact": {"full_name": "Miller, Sarah"},
            "customer": identity_fixtures.customer_block(
                "Miller, Sarah", account_type="residential"
            ),
        },
    )
    row = moves.MoveRecord.objects.get(id=result["move_record_id"])
    incoming = cmodels.Account.objects.get(id=result["id"])
    return incoming, row


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE INVARIANT — never both, never neither
# ═══════════════════════════════════════════════════════════════════════════
def test_every_cell_states_a_value_or_a_reason_and_never_both(brazos, marcus):
    """The screen's contract, asserted over the WHOLE payload (§1).

    ⚠ Broken first by making `_fact` return `{"value": None, "unavailable":
    None}` for an empty string, which is the natural-looking bug: it fails here
    naming the exact path, and passes every other check in the repo.
    """
    with tenant_ctx(brazos):
        account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)

    cells = _walk_facts(payload)
    assert cells, "no label→value cells found — the walker is looking at the wrong shape"
    for path, cell in cells:
        has_value = cell["value"] is not None and cell["value"] != ""
        has_reason = cell["unavailable"] is not None
        assert has_value != has_reason, (
            f"{path} states "
            f"{'both a value and a reason' if has_value else 'neither a value nor a reason'}"
        )


def test_every_stated_absence_names_a_code_and_a_rule(brazos, marcus):
    """An absence with no code is a dash wearing a longer coat (§3)."""
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)

    for path, cell in _walk_facts(payload):
        if cell["unavailable"] is None:
            continue
        assert cell["unavailable"].get("code"), f"{path}: absence with no code"
        assert cell["unavailable"].get("br_ref"), f"{path}: absence with no rule"
        assert cell["unavailable"].get("detail"), f"{path}: absence with no sentence"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE IN-FLIGHT MOVE, AND THE URL THAT SURVIVES THE COMMIT
# ═══════════════════════════════════════════════════════════════════════════
def test_a_parked_draft_is_reachable_at_the_reference_it_will_be_filed_under(
    brazos, marcus
):
    """§2 — the property that makes `↗ Open` work on an `In progress` row.

    ⚠ **THIS IS THE ASSERTION THE PAGE WAS MISSING A REASON TO HAVE.** Without
    it, resolving only `move_records` is correct-looking code that 404s on every
    unfinished move, and no other test in the repo would notice.
    """
    from apps.customers import seams

    with tenant_ctx(brazos):
        park = seams.park_wizard_draft(
            marcus,
            {
                "flow": "move_in",
                "step": 2,
                "subject_label": "1408 Elm Street · Unit A",
                "values": {"unit_no": "SCW-U-207"},
                "waiting_on": "documents",
            },
        )
        reference = getattr(park, "reference", None) or park["reference"]
        assert reference, "a move-in draft must carry the number it will be filed under"

        payload = mrr.record_detail(reference)

    assert payload["state"] == mrr.STATE_IN_FLIGHT
    assert payload["move_no"] == reference
    # every fact the commit has not produced states the LIFECYCLE reason, and
    # never a seam reason or a dash
    for key in ("account_opened", "earliest_legal_start", "committed_by"):
        cell = payload["what_happened"][key]
        assert cell["value"] is None
        assert cell["unavailable"]["code"] in {
            mrr.NO_ACCOUNT_UNTIL_IT_COMPLETES["code"],
            mrr.NOT_COMMITTED_YET["code"],
        }, f"{key} states the wrong kind of absence: {cell['unavailable']['code']}"


def test_an_in_flight_record_carries_the_handle_its_resume_door_needs(brazos, marcus):
    """The record is addressed by REFERENCE; the wizard is resumed by ID.

    ⚠ **WITHOUT THIS FIELD THE PO's ACTION CANNOT BE BUILT AT ALL** (ruling
    2026-09-19, *"We will need this action on details page - 4 · Close or
    complete it"*). `resumePath()` builds `/move-ins/new?parked=<id>` and the
    wizard reads that id back; the page had `MVI-26-0114` and nothing else, so
    it could NAME the draft and could not open it.

    ⚠ **ASSERTED AGAINST THE PARK'S OWN ID, NOT MERELY `is not None`.** A
    payload carrying SOME uuid would satisfy a presence check and send the
    clerk to a draft that is not the one they are looking at — and the wizard
    would hydrate it without complaining, because any real id reads fine.
    """
    from apps.customers import seams

    with tenant_ctx(brazos):
        park = seams.park_wizard_draft(
            marcus,
            {
                "flow": "move_out",
                "step": 2,
                "subject_label": "1408 Elm Street · Unit E",
                "values": {"unit_no": "SCW-U-207"},
                "waiting_on": "documents",
            },
        )
        reference = getattr(park, "reference", None) or park["reference"]
        park_id = str(getattr(park, "id", None) or park["id"])
        payload = mrr.record_detail(reference)

    assert payload["state"] == mrr.STATE_IN_FLIGHT
    # the SAME id `wizard_parks.row_dict` hands the parked-drafts panel, so the
    # two doors onto one act cannot disagree about the handle
    assert payload["park_id"] == park_id
    # and the flow the wizard is chosen by travels with it, or the handle names
    # a draft the page cannot decide which wizard to open
    assert payload["kind"] == "move_out"


def test_a_completed_record_carries_no_resume_handle(brazos, marcus):
    """The action exists for `in_flight` ONLY, and the absence is the guard.

    A completed move has no draft to go back into. If this field ever appeared
    here, the record page would grow a Resume door on a finished move — the
    exact control the blueprint's *"this record has no actions"* ruling
    refuses, and the one thing this wave must not change.
    """
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)

    assert payload["state"] == mrr.STATE_COMPLETED
    assert "park_id" not in payload


def test_the_reference_resolves_in_either_case(brazos, marcus):
    """The blueprint's own URL is lowercase (`/moves/mvi-26-0114`) while the
    number a clerk quotes is upper. Both must land."""
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        upper = mrr.record_detail(row.move_no.upper())
        lower = mrr.record_detail(row.move_no.lower())
    assert upper["move_no"] == lower["move_no"] == row.move_no


def test_an_unknown_reference_is_not_found_and_never_forbidden(brazos, marcus):
    """HR-1 — the boundary must not confirm that a row exists elsewhere."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            mrr.record_detail("MVI-26-9999")
        with pytest.raises(errors.NotFoundError):
            mrr.record_detail("")


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE ABSENCES ARE DISTINCT
# ═══════════════════════════════════════════════════════════════════════════
def test_no_meter_and_no_seam_are_different_absences(brazos, marcus):
    """§3 — DEF-127's shape. Three facts, three codes, never one dash.

    ⚠ Asserted on the CONSTANTS being DISTINCT *and* on the branch choosing
    between them, because DEF-182's lesson is that reading the constants alone
    proves nothing about which arm runs.
    """
    codes = {
        mrr.UNIT_HAS_NO_METERS["code"],
        mrr.READS_NOT_READABLE_HERE["code"],
        mrr.NO_ACCOUNT_UNTIL_IT_COMPLETES["code"],
    }
    assert len(codes) == 3, "two of the three read-absences collapsed onto one code"

    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)
    reads = payload["opening_reads"]
    if reads["unavailable"] is not None:
        assert reads["unavailable"]["code"] in codes


def test_a_deposit_standard_of_none_is_not_printed_as_zero(brazos, marcus):
    """BR-CUS-023 — *"a plan that asks nothing"* and *"nobody wrote a rule"* are
    different facts that a `$0.00` would render identically."""
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        money = mrr.record_detail(row.move_no)["money_taken"]
    required = money["required"]
    if required["value"] is None:
        assert required["unavailable"]["code"] == mrr.NO_PLAN_DEPOSIT_STANDARD["code"]
        # and the arithmetic that depends on it is absent too, never a total
        assert money["still_to_collect"]["value"] is None


def test_the_tender_is_stated_rather_than_invented(brazos, marcus):
    """§3 of the module docstring — B1 forbids the join and payments publishes
    no read, so the cheque number is an absence that NAMES the seam."""
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        tender = mrr.record_detail(row.move_no)["money_taken"]["tender"]
    assert tender["value"] is None
    assert tender["unavailable"]["code"] == mrr.TENDER_NOT_READABLE_FROM_CUSTOMERS["code"]
    assert tender["unavailable"]["wanted_reads"], "an absence must name what would close it"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · NO ACTIONS — the blueprint's ruling, asserted as a shape
# ═══════════════════════════════════════════════════════════════════════════
def test_the_record_offers_two_doors_and_no_action(brazos, marcus):
    """The blueprint: *"This record has no actions … the only controls are doors
    to the account and the customer."* PO 2026-09-19 ruled the pair and removed
    `Raise a visit` and `Record the reading` by name.

    ⚠ **ASSERTED AS AN EXACT KEY SET, NOT A SUBSET.** A subset assertion passes
    while somebody adds a third control, which is precisely the drift this is
    here to catch.
    """
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)
    assert set(payload["doors"]) == {"account", "customer"}


def test_a_move_without_a_linked_customer_states_it_and_offers_no_linking(
    brazos, marcus
):
    """PO 2026-09-19: *"Open the account, Open the customer - if requried
    otherwise we will ahev to link to exisitng one"*.

    ⚠ **MEASURED, NOT ASSUMED: this is the ORDINARY case on a move-in.** On the
    sample estate, the seeded move-in's account carries ZERO `customer_accounts`
    rows and the seeded move-out's carries one. So the absence branch is the one
    a clerk meets first, and it must say so plainly — and must NOT grow a
    linking control, which is its own piece of work.
    """
    with tenant_ctx(brazos):
        account, row = _move_in(marcus, brazos)
        customers_models.CustomerAccount.objects.filter(account_id=account.id).delete()
        door = mrr.record_detail(row.move_no)["doors"]["customer"]
    assert door["value"] is None
    assert door["unavailable"]["code"] == mrr.NO_CUSTOMER_LINKED["code"]
    assert "link" not in str(door.get("value") or "").lower()


# ═══════════════════════════════════════════════════════════════════════════
# 5 · B14 RULE 31 — no database id is a field's VISIBLE value
# ═══════════════════════════════════════════════════════════════════════════
def test_no_visible_value_is_a_database_id(brazos, marcus):
    """B14 rule 31, asserted narrowly enough to be true.

    ⚠ **THE PAYLOAD DOES CARRY IDS, DELIBERATELY** — a door needs one to build
    a route. So a test that greps the whole payload for a uuid would fail on
    correct code and would be deleted by the next lane. What rule 31 forbids is
    an id being *what a person reads*, so this walks the label→value cells and
    asserts no `value` is a uuid, while the route ids ride in their own keys.
    """
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)

    for path, cell in _walk_facts(payload):
        value = cell["value"]
        if isinstance(value, str):
            assert not _UUID.match(value), f"{path} renders a database id: {value}"
        elif isinstance(value, dict):
            for key, inner in value.items():
                if key.endswith("_id"):
                    continue  # carried for the ROUTE, never rendered
                if isinstance(inner, str):
                    assert not _UUID.match(inner), f"{path}.{key} renders a database id"


def test_the_title_is_a_name_and_never_the_address_line(brazos, marcus):
    """B14 rule 40 · p074 — the 32px head title is the CUSTOMER'S NAME."""
    with tenant_ctx(brazos):
        _account, row = _move_in(marcus, brazos)
        payload = mrr.record_detail(row.move_no)
    assert payload["title"], "the page head has no title at all"
    assert payload["title"] != payload["address_line"], (
        "the title is repeating the address line, which reads as a rendering bug"
    )


def test_the_title_falls_back_to_the_contact_when_no_customer_is_linked(
    brazos, marcus
):
    """⚠ **THIS ASSERTION EXISTS BECAUSE THE OBVIOUS ONE DOES NOT WORK, AND THE
    DIFFERENCE IS THE WHOLE LESSON.**

    The first draft of the page read `getattr(account, "contact", None)`.
    `Contact` is a REVERSE fk, so that expression returns None on every account
    without raising, and the 32px title rendered EMPTY over a contact row that
    said `Kwan, Michael`. Nothing else in the repo would have seen it.

    The first draft of the TEST could not see it either: every account this
    fixture builds has a LINKED CUSTOMER, so `_title_name` returns the
    customer's name and never reaches the contact fallback at all. Breaking the
    code and re-running — hard-won law 7 — is what showed that the guard passed
    with the bug reintroduced, which is law 7's fourth shape exactly: a test
    named after an assertion it does not make.

    So this test **removes the customer link first**, which is the state the
    contact fallback exists for and, measured on the sample estate, the ORDINARY
    state of a move-in: the one seeded move-in's account carries zero
    `customer_accounts` rows.
    """
    with tenant_ctx(brazos):
        account, row = _move_in(marcus, brazos)
        customers_models.CustomerAccount.objects.filter(account_id=account.id).delete()
        contact = customers_models.Contact.objects.filter(
            account_id=account.id, deleted_at__isnull=True
        ).first()
        assert contact is not None and contact.full_name, (
            "fixture drift: this account has no contact row, so the branch under "
            "test is unreachable and a pass here would mean nothing"
        )
        payload = mrr.record_detail(row.move_no)

    assert payload["title"] == contact.full_name, (
        f"the head title fell back to {payload['title']!r} instead of the "
        f"contact's name {contact.full_name!r}"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: the MOVE RECORD (blueprint p074) + the PO's approval and action-bar
#         ruling of 2026-09-19 + the conformance file's "The Move-ins LIST and
#         the MOVE RECORD — blueprint pages 073–074"
# generated: 2026-09-19, the move-record lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

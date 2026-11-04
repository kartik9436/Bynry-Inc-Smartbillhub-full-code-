# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-6746` — `f.state=on_hold` was offered over two rows whose
#           State cell reads `Held` and could never match one, because
#           `STATE_ON_HOLD` is assigned nowhere in this repository ·
#           `DEF-CUS-6749` — the list read NO visit at all, so a case a crew
#           attended and could not cut rendered identically to one nobody had
#           been to.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — every read here runs inside
#           `tenant_ctx`) · hard-won law 7 (a guard is proved RED first, through
#           the harness that will run it) · BR-CUS-1083 (the four outcomes) ·
#           BR-SHL-011 (declared filters, AND-combined server-side) · NFR-3
# Tests:    this file
# Impacts:  apps/customers/disconnect_reads.py
# ───────────────────────────────────────────────────────
#
# ══════════════════════════════════════════════════════════════════════════
# WHY THESE TWO SIT IN ONE FILE
# ══════════════════════════════════════════════════════════════════════════
# They are the same failure wearing two costumes, and naming it once is worth
# more than either case: **a fact that exists in the database and reaches no
# screen.** One is a filter that asks a column a question the column can never
# answer; the other is a whole table the read model had never heard of. Neither
# produced a null, an error or a gap — both produced a plausible, correct-
# looking answer — and nothing in this repository could see either.
#
# ⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY** (law 7, habit 2), because a
# check whose false pass you cannot describe is one you do not understand:
#   * `test_on_hold_now_matches…` would pass on a list that IGNORED `f.state`
#     entirely and returned everything. So it also asserts that the filter
#     EXCLUDES — the bakery, which is at a tier and holds no protection, must
#     not be in the answer.
#   * `test_the_last_visit_reaches_the_row` would pass on a row that carried a
#     hard-coded visit. So the sibling case asserts `None` on an unvisited row,
#     and both run against the same payload.
#
# ⚠ **RUN THESE ON POSTGRES TOO.** The default suite is in-memory SQLite
# (`config/settings/test.py` hardcodes it — hard-won law 14), and the `on_hold`
# branch resolves a Python-computed id list into a `WHERE id IN (…)`. That
# shape is where SQLite and PostgreSQL have already disagreed on this project.
from __future__ import annotations

from datetime import date

from apps.customers import disconnect_reads, disconnect_visits, disconnects

# ⚠ **THE STAR IMPORT IS NOT LAZINESS — IT IS HOW THIS SUITE'S FIXTURES CHAIN.**
# `brazos` depends on `growth_plan` and `identity_seam`, which live in
# `test_us_met_helpers` and are pulled in by `test_w7_worklists` the same way.
# Naming `brazos` alone imports the fixture and NOT what it asks for, and pytest
# then reports `fixture 'growth_plan' not found` — a failure that reads like a
# missing fixture and is really a missing transitive one.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — the W1 shared fixtures
from tests.test_w7_worklists import (  # noqa: F401  (helpers + the two fixtures)
    BAKERY_OWED,
    TODAY,
    _account,
    _at_tier,
    _owes,
    _row_for,
    brazos,
    marcus,
    tenant_ctx,
)


def _held_and_laddered(marcus, brazos, monkeypatch):
    """One account on the list for a PROTECTION, one on it for the LADDER.

    The two halves of §4's union, which is exactly what `f.state=on_hold` has
    to tell apart: the protected half is DERIVED and the laddered half is a
    stored `disconnect_cases.state`.
    """
    _owes(monkeypatch, BAKERY_OWED)
    bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
    _at_tier(marcus, bakery["id"], disconnects.TIER_2)

    okafor = _account(marcus, brazos, label="77 Okafor Way", name="Okafor, Emmanuel")
    disconnects.record_protection(
        marcus,
        okafor["id"],
        kind=disconnects.PROTECTION_MEDICAL,
        effective_from=date(2026, 8, 1),
        expires_on=date(2026, 12, 31),
    )
    return bakery, okafor


def test_on_hold_now_matches_the_rows_whose_state_cell_says_held(brazos, marcus, monkeypatch):
    """`DEF-CUS-6746` — the filter answers the question the column asks.

    ⛔ **BEFORE THE FIX THIS RETURNED ZERO, FOREVER, BY CONSTRUCTION.**
    `DISCONNECT_FILTER_STATES` derives its options by SUBTRACTION from
    `disconnects.CASE_STATES` — a good rule, so that a new state cannot be left
    behind — and `CASE_STATES` contains `on_hold`, which nothing ever assigns.
    The branch then ran `cases.filter(state="on_hold")`. Hard-won law 7's
    INCAPABLE OF PASSING shape, wearing a filter control: offered, correct,
    and answering nothing while two rows on the same screen read `Held`.

    Measured on PostgreSQL 16 before and after, on the demo tenant:
    `GET /disconnects?f.state=on_hold` → **total 0**, then **total 2**, over a
    list whose State column says `Held` on exactly those two rows.
    """
    with tenant_ctx(brazos):
        bakery, okafor = _held_and_laddered(marcus, brazos, monkeypatch)

        payload = disconnect_reads.list_disconnects(
            as_of=TODAY, filters={"state": disconnects.STATE_ON_HOLD}
        )

        numbers = {row["account_no"] for row in payload["rows"]}
        # It MATCHES the protected row…
        assert okafor["account_no"] in numbers
        # …and it EXCLUDES the laddered one, which is what stops this case
        # passing on a filter that was ignored altogether.
        assert bakery["account_no"] not in numbers
        assert payload["total"] == 1

        # The row it returns is the one whose State cell says so — one
        # definition of *on hold* on this screen, not two.
        held = _row_for(payload, okafor["account_no"])
        assert held["state"]["held_by"] == [disconnects.PROTECTION_MEDICAL]


def test_every_offered_state_carries_its_count(brazos, marcus, monkeypatch):
    """`DEF-CUS-6746`'s screen half — an empty view says so before it is opened.

    Six of the eight offered values answered zero and the screen offered all
    eight identically, so a clerk could not tell a BROKEN control from an EMPTY
    one. One was broken and is fixed above; the rest are true zeroes. The
    remedy for those is a number beside the option, never withdrawing it.
    """
    with tenant_ctx(brazos):
        bakery, okafor = _held_and_laddered(marcus, brazos, monkeypatch)

        payload = disconnect_reads.list_disconnects(as_of=TODAY)
        counts = {entry["code"]: entry["count"] for entry in payload["states"]}

        # Every offered option carries one — including the ones that are zero,
        # which is the entire point.
        assert set(counts) == {entry["code"] for entry in payload["states"]}
        assert counts[disconnects.STATE_NOTICE_SENT] == 1
        assert counts[disconnects.STATE_ON_HOLD] == 1
        # A state no case has reached is a TRUE zero and is still offered.
        assert counts[disconnects.STATE_CUT] == 0
        assert counts[disconnects.STATE_RECONNECTING] == 0

        # ⚠ The count and the filter must AGREE, or the number is decoration.
        # This is the assertion that would catch a count computed one way and a
        # filter resolved another — which is precisely how `on_hold` broke.
        for code, expected in counts.items():
            served = disconnect_reads.list_disconnects(as_of=TODAY, filters={"state": code})
            assert served["total"] == expected, f"{code}: count {expected}, filter {served['total']}"


def test_the_last_visit_reaches_the_row(brazos, marcus, monkeypatch):
    """`DEF-CUS-6749` — a case a crew attended stops reading like an untouched one.

    ⛔ **`disconnect_reads.py` HELD ZERO REFERENCES TO `DisconnectVisit`.** The
    model, its CHECK constraint, its four outcomes and its own test file all
    existed; the one screen a dispatcher looks at did not know the table was
    there. Three of the four outcomes CLEAR the cut date and return the case to
    `notice_sent` — a real, correct state — so the visited case and the
    unvisited one were the same word and the same empty date.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, BAKERY_OWED)
        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_3)
        # ⚠ **`BR-CUS-100` — A TIER-3 CUT CANNOT BE SCHEDULED ON AN UNRECORDED
        # SERVICE**, and the refusal is by design: the in-app notice is a SEND,
        # and proof of service is a person attesting to the posted item. So the
        # case walks the real door rather than being planted, which is also the
        # only way a visit can exist at all — `record_outcome` refuses a case
        # that is not `scheduled`.
        case = disconnects.open_case_for(bakery["id"])
        notice = disconnects.DisconnectNotice.objects.filter(
            tenant_id=case.tenant_id, case_id=case.pk, tier=disconnects.TIER_3
        ).latest("created_at")
        disconnects.record_proof_of_service(
            marcus,
            notice.pk,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference="RA 4821 9930 US",
            served_on=date(2026, 8, 24),
            signed_for_on=date(2026, 8, 24),
        )
        disconnects.schedule_cut(
            marcus,
            bakery["id"],
            cut_on=date(2026, 8, 27),
            as_of=TODAY,
        )

        disconnect_visits.record_outcome(
            marcus,
            bakery["id"],
            on_date=date(2026, 8, 27),
            outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
            note="Gate padlocked.",
        )

        row = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), bakery["account_no"])

        # The trap, asserted so it cannot be mistaken for the bug: the STATE is
        # back to `notice_sent` and the cut date is gone, both CORRECTLY.
        assert row["state"]["stored"] == disconnects.STATE_NOTICE_SENT
        assert row["cut_date"] is None
        # …and the row now carries what tells it apart from one nobody visited.
        assert row["visit"] is not None
        assert row["visit"]["outcome"] == disconnect_visits.OUTCOME_LOCKED_GATE
        assert row["visit"]["visited_on"] == "2026-08-27"
        assert row["visit"]["clears_the_cut_date"] is True


def test_a_row_with_no_visit_claims_nothing_about_one(brazos, marcus, monkeypatch):
    """The mirror, and the half that makes the case above mean anything.

    `None` means *no attendance is recorded*, which is NOT the claim *nobody
    went*. A screen that printed one from the absence of a row would be making
    a statement about the world out of a gap in a table.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, BAKERY_OWED)
        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_2)

        row = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), bakery["account_no"])
        assert row["visit"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-6746 · DEF-CUS-6749 · BR-CUS-1083 · BR-SHL-011 · NFR-3 ·
#         hard rule 1 · hard-won laws 7 and 14
# generated: 2026-09-25 by lane LIST
# checklist: A✔ B=n/a(backend half) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 the count/filter agreement loop is the case that would catch a
#         number computed one way and a filter resolved another — the shape
#         `on_hold` failed in
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

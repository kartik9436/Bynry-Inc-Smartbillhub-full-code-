# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.14 (the Subject parameter — one
#           parameter on two definitions, four grains).  Screens: 2·1 head.
# Rules:    CLAUDE.md hard rule 8 (an address lives on `premises` and a UNIT
#           REFINES IT BY LABEL, declaring no address column) · BR-CUS-068
#           (`kind='master'` is a column on an ordinary accounts row) ·
#           B14 rule 31 (no database id is ever the visible value of a field)
# Tests:    this file
# Impacts:  apps/reports/subject.py · apps/reports/runner.py
# ───────────────────────────────────────────────────────
"""P2.14 — FOUR SUBJECTS, AND MASTER IS NOT A FIFTH.

p12, read as an image: *"One parameter on two definitions — Account · Customer
· Premises · Unit. Selects on `accounts.id`, `customer_id`, `premises_id`,
`unit_id`. ⚠ **Master is not a fifth value**: 'a master account is an ordinary
row', `kind='master'`, same lookup."*

⚠ **WHAT WAS ALREADY THERE, MEASURED RATHER THAN ASSUMED.** `reports/0003`
already seeds `filters["subject"]` and `filters["subjects"]` onto the two keys
`statement` and `account_ledger`, and `runner._DEFINITION_BOOKKEEPING` already
lets both through `validate` untouched. So the PARAMETER exists as stored data.
What did not exist is anything that reads it: no vocabulary, no validation, no
selector, and nothing that refuses a fifth value. A stored string nothing
honours is hard-won law 1 in a migration.
"""

import pytest

from apps.reports import subject as subj


def test_p2_14__there_are_exactly_four_subjects_in_the_drawn_order():
    assert subj.SUBJECTS == ("account", "customer", "premises", "unit")


@pytest.mark.parametrize(
    "name,selector",
    [
        ("account", "accounts.id"),
        ("customer", "customer_id"),
        ("premises", "premises_id"),
        ("unit", "unit_id"),
    ],
)
def test_p2_14__each_subject_selects_on_the_column_the_brief_names(name, selector):
    assert subj.resolve(name).selects_on == selector


def test_p2_14__master_is_refused_by_name_and_the_refusal_says_why():
    """⚠ The whole point of the task's warning. *"A master account is an
    ordinary row"* — `kind='master'`, same lookup — so offering it as a fifth
    subject would build a second lookup for a row the first one already
    returns, and the two would drift."""
    with pytest.raises(subj.UnknownSubject) as raised:
        subj.resolve("master")
    message = str(raised.value)
    assert "master" in message
    assert "account" in message, "the refusal must name the subject that DOES serve it"


def test_p2_14__a_master_account_is_reachable_through_the_account_subject():
    """The other direction: refusing `master` must not make a master account
    unreportable. It is an `account`, selected on `accounts.id` like any
    other, and the premises subject MARKS it rather than merging it."""
    assert subj.resolve("account").selects_on == "accounts.id"
    assert subj.resolve("premises").marks_master is True
    assert subj.resolve("account").marks_master is False


def test_p2_14__an_unknown_subject_is_refused_and_never_silently_defaulted():
    """A subject that falls back to `account` is a report about the wrong
    thing with a confident head — worse than a refusal."""
    for bad in ("", "  ", "Account ledger", "premise", None, 4):
        with pytest.raises(subj.UnknownSubject):
            subj.resolve(bad)


def test_p2_14__every_subject_states_what_one_row_is():
    """`P2.23` — every report says what one row is, and a report whose subject
    changes its grain must change the line under its title with it."""
    for name in subj.SUBJECTS:
        assert subj.resolve(name).grain, f"{name} states no grain"


def test_p2_14__the_unit_subject_carries_no_address_of_its_own():
    """CLAUDE.md hard rule 8: a unit refines a premises BY LABEL and declares
    no address column. The head reads `premises address + unit label`, which is
    a WALK and not a second address."""
    unit = subj.resolve("unit")
    assert unit.head_from == ("premises_address", "unit_label")
    assert "address" not in unit.selects_on
    # And the premises subject is where the address itself comes from.
    assert subj.resolve("premises").head_from == ("premises_address",)


def test_p2_14__no_subject_puts_a_database_id_on_screen():
    """B14 rule 31 — *"no Databse ID on screen - that is a rule"*. The selector
    is a QUERY column; what the head shows is a number or a label."""
    for name in subj.SUBJECTS:
        one = subj.resolve(name)
        assert not any(part.endswith("_id") or part == "id" for part in one.head_from), (
            f"{name} would put {one.head_from} on screen"
        )


def test_p2_14__the_payload_offers_the_four_and_nothing_else():
    """What the screen reads. A fifth entry here is a control that opens onto
    a lookup nobody wrote."""
    payload = subj.payload()
    assert [entry["name"] for entry in payload["subjects"]] == list(subj.SUBJECTS)
    assert payload["count"] == 4
    assert all("selects_on" not in entry for entry in payload["subjects"]), (
        "the wire must not carry the selector — it is a column name, not a control"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.14 (05-prototype/09 Reports Build Brief.pdf p12 read as an image per B14 rule 42)
# generated: 2026-09-27 by lane REP-P2-MODEL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

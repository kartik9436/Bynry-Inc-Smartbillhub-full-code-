# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave C task 10 — *"a way to SET jurisdiction"*. The
#          provisioning trace (2026-08-26) finding 3: *"Jurisdiction
#          (inside/outside city) can be written by NOTHING. It decides an
#          outside-city surcharge on every bill at an address; the bill run
#          treats it unstated as an exception. Read side built, write side
#          absent."*
# Defect:  DEF-517 (the column has no writer at any layer, filed 2026-08-21) ·
#          DEF-507 (the READ half, 2026-08-26)
# Story:   US-MET-001 (premises write) · US-MET-003 (S16 guided add)
# Rules:   BR-RAT-101 (the flag lives on the premises; `None` is a THIRD state
#          and must stay one) · BR-RAT-102 (the plan states the factor, the
#          premises states the side)
# Question: OQ-423 (does a corrected flag reach bills already issued?)
# ───────────────────────────────────────────────────────
"""The WRITE half of BR-RAT-101, and the four things a money-bearing flag owes.

⚠ **PROVED RED FIRST (2d), against `apps/metering/services.py` exactly as it
stood at `0899de8`.** The whole file was run with the pre-change validator in
place: **12 failed, 1 passed** — the one that passed is
`an_omitted_field_stays_the_third_state`, which is the behaviour that was
already correct and must not move. The failure, quoted verbatim from that run:

    apps/metering/services.py:626: in create_premises
        cleaned = _validate_premises(data, partial=False)
    apps/metering/services.py:575: in _validate_premises
        _refuse_fields(fe)

    field_errors = [{'field': 'inside_city_limits', 'code': 'VAL-002',
                     'message_key': 'metering.unknown_field', 'params': {}}]

    E   core.errors.ValidationError: VAL-002 (metering.unknown_field)

`metering.unknown_field` renders to a clerk as *"This app sent a field this
record doesn't have. Nothing was saved."* — which is DEF-517 in one sentence:
the column exists, the bill run reads it, and the product's own answer to
somebody trying to set it was that it does not exist.

⚠ **NOTHING HERE READS SEEDED DATA**, for the reason CR-036 (h)'s twin test
gives: every premises below is created through the real service inside the test
and the assertions are about what the WRITE did. Task 11's seeding is proved
separately, on the seeded estate, by
`tests/test_cr039_c11_seeded_surcharge.py`.
"""

import pytest

from apps.metering import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


# ── The three states, written ───────────────────────────────────────────────


def test_cr039_c10__create_records_inside_the_city(brazos, dana):
    """S16's single step, with the clerk answering *inside*."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana, {"owner_id": owner_for(dana), "address_line": "21 Quarry Hill Rd", "inside_city_limits": True}
        )
        row = models.Premises.objects.get(pk=created["id"])
    assert row.inside_city_limits is True
    # The selector serves it back, so the detail screen re-opens on the answer
    # rather than on a guess (DEF-507).
    assert created["inside_city_limits"] is True


def test_cr039_c10__create_records_outside_the_city(brazos, dana):
    """The answer that COSTS the customer money — BR-RAT-102 surcharges it."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana, {"owner_id": owner_for(dana), "address_line": "23 Quarry Hill Rd", "inside_city_limits": False}
        )
        row = models.Premises.objects.get(pk=created["id"])
    assert row.inside_city_limits is False


def test_cr039_c10__an_omitted_field_stays_the_third_state(brazos, dana):
    """⚠ THE ONE THAT MUST NEVER REGRESS. `None` is *nobody recorded it*, and a
    create that defaulted it would answer a pricing question for every address
    ever added (BR-RAT-101)."""
    with tenant_ctx(brazos):
        created = services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "25 Quarry Hill Rd"})
        row = models.Premises.objects.get(pk=created["id"])
    assert row.inside_city_limits is None


def test_cr039_c10__update_records_outside_the_city_and_audits_the_change(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — a money action writes `audit_log`. Nothing extra was
    written for it: `premises_detail_dict` already carries the field, so the
    before/after on `premises.updated` shows the flag move."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="27 Quarry Hill Rd")
        audit_rows.clear()
        services.update_premises(dana, premise["id"], {"inside_city_limits": False})
        row = models.Premises.objects.get(pk=premise["id"])
    assert row.inside_city_limits is False
    updates = [r for r in audit_rows if r["action"] == "premises.updated"]
    assert len(updates) == 1
    assert updates[0]["before"]["inside_city_limits"] is None
    assert updates[0]["after"]["inside_city_limits"] is False


def test_cr039_c10__an_omitted_field_on_a_patch_leaves_the_answer_alone(brazos, dana):
    """A clerk correcting a street name must not un-answer the pricing
    question — the posture `services_available` takes (DEF-762)."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="29 Quarry Hill Rd")
        services.update_premises(dana, premise["id"], {"inside_city_limits": True})
        services.update_premises(dana, premise["id"], {"city": "Katy"})
        row = models.Premises.objects.get(pk=premise["id"])
    assert row.inside_city_limits is True
    assert row.city == "Katy"


def test_cr039_c10__an_explicit_null_clears_the_answer_back_to_unrecorded(brazos, dana):
    """*"We recorded it and we were wrong"* is a real correction, and it fails
    SAFE: an unrecorded premises on a surcharging plan REFUSES its bill by name
    (BR-RAT-102's fourth case) rather than being priced on a value nobody
    stands behind."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="31 Quarry Hill Rd")
        services.update_premises(dana, premise["id"], {"inside_city_limits": False})
        services.update_premises(dana, premise["id"], {"inside_city_limits": None})
        row = models.Premises.objects.get(pk=premise["id"])
    assert row.inside_city_limits is None


# ── What is refused, and why each refusal is not pedantry ───────────────────


@pytest.mark.parametrize(
    "value",
    [
        1,  # `1 == True` in Python: a `bool(value)` writes INSIDE silently
        0,  # …and `bool(0)` writes OUTSIDE, which ADDS a surcharge
        "outside",  # a word that reads right and is truthy either way
        "maybe",  # the importer's own example (PRM.VALUES_PARSE)
        [],
    ],
)
def test_cr039_c10__a_value_that_is_not_one_of_the_three_is_refused(brazos, dana, value):
    """⚠ **THE TYPE IS CHECKED, NEVER COERCED.** `1` and `0` are the dangerous
    pair: Python makes them equal to the booleans, so every lenient shape of
    this parser — `bool(value)`, `value in (True, False)`, a truthiness test —
    accepts them, and a spreadsheet's `0` becomes *outside the city* on a
    column that surcharges every future bill at the address.

    The refusal is the importer's posture in the importer's own words
    (`PRM.VALUES_PARSE`): *"a cell with words in it nobody can read IS an
    error, because guessing which way it meant is a silent pricing
    decision"*.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_premises(
                dana,
                {"owner_id": owner_for(dana), "address_line": f"33 Quarry Hill Rd {value!r}", "inside_city_limits": value},
            )
    field_errors = caught.value.field_errors
    assert [fe["field"] for fe in field_errors] == ["inside_city_limits"]
    assert field_errors[0]["message_key"] == "metering.premises.jurisdiction_unreadable"
    # The value is NAMED, so a clerk can see what the product could not read.
    assert field_errors[0]["params"]["value"] == str(value)


def test_cr039_c10__an_empty_string_is_the_form_clearing_it__not_an_error(brazos, dana):
    """A `<select>` yields `""` for its empty option, and *not recorded* is a
    real answer to give. It is the ONLY string this parser accepts."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="35 Quarry Hill Rd")
        services.update_premises(dana, premise["id"], {"inside_city_limits": True})
        services.update_premises(dana, premise["id"], {"inside_city_limits": ""})
        row = models.Premises.objects.get(pk=premise["id"])
    assert row.inside_city_limits is None


# ── OQ-423 — the question this lane asked rather than answered ──────────────


def test_cr039_c10__oq423_changing_the_flag_touches_no_issued_invoice(brazos, dana):
    """⚠ **STATED ASSUMPTION, NOT A RULING (`OQ-423`).**

    Correcting a premises from *inside* to *outside* changes what BR-RAT-102
    charges at that address. No signed document says whether that reaches
    anything ALREADY BILLED, and CLAUDE.md hard rule 4 says an issued invoice
    is immutable — so this product applies the change FORWARD ONLY.

    This test pins that behaviour so the assumption cannot drift into an
    accident: `update_premises` writes one column and reaches no other table.
    If the PO rules that a correction owes an adjustment, this test is what
    goes red and names the place to build it.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="37 Quarry Hill Rd")
        before = billing_models.Invoice.objects.count()
        services.update_premises(dana, premise["id"], {"inside_city_limits": False})
        after = billing_models.Invoice.objects.count()
    assert before == after

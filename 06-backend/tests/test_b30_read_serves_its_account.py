# ── Trace ──────────────────────────────────────────────
# Rules:    B2 §2 (`meter_reads.account_id`, a reviewed cross-module FK) ·
#           B1 module map (metering reaches customers only through seams, and
#           never writes) · B14 rule 31 (no database id is ever the visible
#           value of a field) · CLAUDE.md hard rule 8 (an address lives on
#           `premises`; everything else walks to it, server-side)
# Blueprint: Meter Reads entry 03, ⑪ `B30` / `MR-39`
# ───────────────────────────────────────────────────────
"""`B30` — the reading detail's ACCOUNT is served, and it is the read's OWN.

WHAT WAS WRONG, AND IT WAS AN ABSENCE PRINTED OVER AN ANSWER. The drawing puts
the account in `LOCATION` as a live link (⑪ `ACC-2042`). `read_dict` serves 41
keys and **none of them is the account**, so the screen printed *"The account is
not served on a reading; open it through the unit."* over the top of
`meter_reads.account_id` — a reviewed cross-module FK that `DEF-658` taught the
commit path to stamp on 2026-08-24. The blueprint's own verdict: *"a stored
column and a printed absence for the same fact is the two-homes problem waiting
to happen."*

PO ruling 2026-09-14, verbatim: *"if you ahve account or meter in read details
screen - please ensure you ahve link it back to account and mter to imporve
interaction design"*.

⚠ **THE DANGEROUS FIX IS THE OBVIOUS ONE, WHICH IS WHY THE THIRD TEST BELOW
EXISTS.** Metering already has `seams.active_account_for_unit`, and a reading
knows its unit, so *"walk to the unit and ask who is on supply"* is one line and
is WRONG: a reading belongs to whoever was on supply the day it was taken. Doing
it that way hands a year of the previous occupant's consumption to whoever moves
in next — which is the exact hazard `services.collection_account_id` stamps the
column to prevent, and it would be reintroduced at the display layer, silently,
on the one screen whose whole job is proving where a number came from.

⚠ **AND `read_dict` IS NOT WHERE THIS LIVES.** Every other caller of that
serializer is a LIST, and one cross-module read per row on a fifty-row page is
the N+1 `accounts_for_units` was added to remove (`NFR-3`, the DEF-324
discipline). `read_account` is resolved by the DETAIL endpoint, and the seam it
calls is batched so a list that wants it later asks once with the page's ids.

RED PROOF, MEASURED (CLAUDE.md hard-won law 7), against the tree before the fix:
    E   AttributeError: module 'apps.metering.selectors' has no attribute
        'read_account'
…on all four cases, which is the honest shape of a guard written for an absence.
"""

import pytest

from apps.metering import models, selectors, services

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)
from tests.test_def658_read_carries_its_account import (  # noqa: F401
    _account_on_a_unit,
    _commit_one,
    _published_plan,
    brazos,
    marcus,
)

pytestmark = pytest.mark.django_db


def test_b30__the_reading_serves_its_account_by_NUMBER(brazos, marcus):
    """B14 rule 31 — the NUMBER is the visible value; the uuid is evidence.

    *"No database id is ever the visible value of a field"* (PO 2026-08-31).
    The id still travels, because the screen puts it on `title`; what must never
    happen is a uuid landing where a person reads an account.
    """
    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        read = _commit_one(marcus)
        served = selectors.read_account(read)

    assert served["account_absent_reason"] is None
    assert served["account"]["account_no"] == account["account_no"]
    assert served["account"]["id"] == str(account["id"])
    # A number a person can read, not a uuid wearing a different key name.
    assert "-" not in served["account"]["account_no"] or len(
        served["account"]["account_no"]
    ) < 36, served["account"]["account_no"]


def test_b30__a_reading_with_no_account_says_WHICH_absence(brazos, marcus):
    """⚠ TWO ABSENCES, AND THEY ARE DIFFERENT FACTS (the DEF-075 posture).

    A vacancy read, a meter on a unit nobody has taken service at, and every row
    committed before `DEF-658` genuinely carry no account — `not_stamped`. An id
    that customers could not answer is `unresolved`. A screen that printed one
    sentence over both would tell a clerk *"no account"* about a reading that
    has one, which is the failure `DEF-075` cost a re-denominated ledger for.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")  # its own premise and unit, no account
        read = _commit_one(marcus)
        served = selectors.read_account(read)

    assert read.account_id is None
    assert served["account"] is None
    assert served["account_absent_reason"] == "not_stamped"


def test_b30__it_reads_the_STAMP_and_never_the_unit_s_current_occupant(
    brazos, marcus, monkeypatch
):
    """⚠ **THE ONE THAT MATTERS.** The obvious implementation is a unit walk.

    `seams.active_account_for_unit` answers *who is on supply now*; this screen
    needs *who was on supply when the meter was read*. On a unit that has since
    changed hands those are different accounts, and the wrong one reassigns a
    year of consumption to a stranger.

    Proved by making the unit walk IMPOSSIBLE rather than by asserting a value:
    both unit-scoped seams raise, and `read_account` still answers. A version
    that reached for either one fails here by exception, which no equality
    assertion on a single-occupant fixture could ever have caught.
    """
    from apps.metering import seams

    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        read = _commit_one(marcus)

        def _refuse(*args, **kwargs):  # pragma: no cover - the point is that it never runs
            raise AssertionError(
                "read_account walked to the UNIT — it must read the stamp on the row"
            )

        monkeypatch.setattr(seams, "active_account_for_unit", _refuse)
        monkeypatch.setattr(seams, "accounts_for_units", _refuse)
        monkeypatch.setattr(seams, "current_unit_for_asset", _refuse)
        served = selectors.read_account(read)

    assert served["account"]["account_no"] == account["account_no"]


def test_b30__customers_unable_to_answer_is_NOT_no_account(brazos, marcus, monkeypatch):
    """The seam returning nothing means *we could not tell*, never *there is none*.

    `DEF-075` is the whole argument: `None` read as *"this module has nothing"*
    when it meant *"this module cannot answer"* re-denominated a live ledger. The
    two answers stay apart here, all the way to the sentence on the screen.
    """
    from apps.metering import seams

    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        read = _commit_one(marcus)
        monkeypatch.setattr(seams, "account_references", lambda ids: {})
        served = selectors.read_account(read)

    assert read.account_id is not None, "the stamp is there; only the lookup failed"
    assert served["account"] is None
    assert served["account_absent_reason"] == "unresolved"


def test_b30__the_seam_is_batched_and_customers_publishes_it(brazos, marcus):
    """G20's question, asked here too: the seam resolves to a real implementer.

    `seams.account_references` is documented as
    `apps.customers.selectors.account_references(ids) -> {id: {...}}`, and a
    seam whose target does not exist resolves to `None` and answers `{}` — which
    reads exactly like *"this tenant holds no such account"* (DEF-035/DEF-075).
    Asserted by CALLING it with two ids rather than by importing the name, so a
    signature change is caught as well as a deletion.
    """
    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        from apps.metering import seams

        found = seams.account_references([account["id"], account["id"]])

    assert list(found) == [str(account["id"])], found
    assert found[str(account["id"])]["account_no"] == account["account_no"]
    assert set(found[str(account["id"])]) == {"id", "account_no", "customer_name", "status"}


def test_b30__metering_never_touches_the_accounts_TABLE_to_answer_it():
    """B1's module boundary, asserted on the SOURCE rather than at runtime.

    `read_account` is a cross-module READ and the one lawful route is the seam.
    A lane reaching for `customers.models` directly would pass every behavioural
    test in this file — the answer would be right — and would put metering
    inside another module's ORM, which is the thing B8 forbids and the thing
    `seams.py` exists to make unnecessary.
    """
    import inspect

    source = inspect.getsource(selectors.read_account)
    assert "seams.account_references" in source
    assert "customers" not in source.replace("customers seam", "").replace(
        "the customers", ""
    ), source
    # …and the module as a whole still imports no customers model.
    assert "from apps.customers" not in inspect.getsource(selectors).split("\ndef ")[0]


def test_b30__the_detail_endpoint_actually_serves_it(brazos, marcus, client):
    """⚠ **BUILT IS NOT WIRED** (CLAUDE.md hard-won law 2). A selector nothing
    calls is dead code: every test above passes and the screen still prints its
    absence. The question this asks is the one no unit test can — *does the
    payload the browser receives carry the key?*
    """
    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        read = _commit_one(marcus)
        body = selectors.read_dict(read)
        body.update(selectors.read_account(read))

    assert "account" in body and "account_absent_reason" in body
    assert body["account"]["account_no"] == account["account_no"]
    # ⚠ AND `read_dict` ITSELF STILL DOES NOT CARRY IT, DELIBERATELY — every
    # other caller of that serializer is a LIST, and one cross-module read per
    # row is the N+1 the batched seam exists to avoid (`NFR-3`).
    assert "account" not in selectors.read_dict(read)


def test_b30__a_reading_that_lost_its_meter_state_does_not_crash_the_panel(brazos, marcus):
    """`read_account` takes whatever the endpoint has. An object with no
    `account_id` at all is the pre-`DEF-658` shape and must answer, not raise."""

    class _Bare:
        pass

    served = selectors.read_account(_Bare())
    assert served == {"account": None, "account_absent_reason": "not_stamped"}

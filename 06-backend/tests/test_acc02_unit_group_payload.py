# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-5163` — the account Overview's UNIT group ("what this
#           account is attached to") is drawn in the blueprint's R5 frame with
#           five rows and was rendered by nothing. Two of the five facts were
#           not on the payload at all.
# Rules:    CLAUDE.md hard rule 8 / `BR-MET-1161` (an address is stored on
#           `premises` and NOWHERE else; a unit refines a premises BY LABEL, and
#           every other entity derives it by walking to the premises) ·
#           `BR-CUS-1010` (a master account may name no unit and still has an
#           address) · B2 §2 (metering owns units — customers READS through the
#           seam and imports no metering model).
# ───────────────────────────────────────────────────────
"""`unit_type` and `premise_address` on `GET /accounts/{id}`.

**WHY THIS IS A TEST AND NOT A GLANCE AT THE DICT.** The failure this guards is
the one hard rule 8's own lesson names — `DEF-CUS-3653`, where the account
header composed its locality from a retired address kind and *"would have
returned null on every account forever with `tsc` and every test green"*. An
absent value is invisible to every check this repository has: the row renders,
the label is right, and the screen simply draws a dash forever.

So each case reads the VALUE back and compares it against the unit and the
premises the fixture built, never merely asserting the key is present.

**PROVED RED FIRST (hard-won law 7), in the harness that runs them** —
`JOBS_EAGER=false python3 -m pytest tests/test_acc02_unit_group_payload.py
--reuse-db -q`, with `**_unit_facts(account)` taken back out of
`account_detail_dict`. All three fail, quoted verbatim:

    E       KeyError: 'unit_type'
    E       KeyError: 'premise_address'
    E       KeyError: 'unit_type'
    3 failed

**THE MASTER CASE IS THE ONE THAT COSTS SOMETHING.** `BR-CUS-1010` lets an
owner's account name no unit, and hard rule 8 still says it has an address —
the building's, reached through `accounts.premises_id`. The temptation is to
answer `None` for the whole group when there is no unit, which would blank the
`Premises` and `Service address` rows on every master account in the product.
"""

import pytest

from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors

from tests.br_cus_1114_fixtures import top_up_homes
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

pytestmark = pytest.mark.django_db


def test_unit_group_tc1__unit_type_and_premise_address_are_served_and_are_the_unit_s_own(
    brazos, marcus
):
    """The two facts the drawn group needed that the payload did not carry.

    Compared against what metering itself holds, so this cannot pass by the
    payload inventing a plausible string."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        created = customers_services.create_account(marcus, _create_payload(unit["id"]))
        detail = customers_selectors.account_detail_dict(
            customers_selectors.account_or_404(created["id"])
        )
        # The SAME seam the screen's value came through — not a second read.
        served = metering_selectors.unit_detail_dict(metering_selectors.unit_row(unit["id"]))

    assert detail["unit_type"] == served["unit_type"]
    assert detail["premise_address"] == served["premise_address"]
    # And the building's line is the BUILDING's — never the composed
    # "<address> · <label>" cell the LIST draws, which is a different string for
    # a different column and would put the unit label into the Premises row.
    assert detail["premise_address"] != detail["premise"]


def test_unit_group_tc2__the_address_is_the_premises_and_not_a_second_copy(brazos, marcus):
    """Hard rule 8, proved rather than asserted: the value the account serves is
    byte-for-byte the `premises` row's own `address_line`, so a map, an envelope
    and this group cannot disagree."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        created = customers_services.create_account(marcus, _create_payload(unit["id"]))
        detail = customers_selectors.account_detail_dict(
            customers_selectors.account_or_404(created["id"])
        )
        # ⚠ **THE `premises` ROW ITSELF, NOT A SECOND SELECTOR.** Comparing two
        # selectors would prove only that they agree with each other; the claim
        # hard rule 8 makes is about the stored COLUMN.
        premises = metering_selectors.premises_row(detail["premises_id"])

    assert detail["premise_address"] == premises.address_line


def test_unit_group_tc3__an_account_with_no_unit_still_has_the_building(brazos, marcus):
    """`BR-CUS-1010` + hard rule 8. The UNIT half is genuinely absent and stays
    `None`; the ADDRESS half walks to the premises, exactly as `_premise_cell`
    already does — so the Premises and Service address rows are still drawn on a
    master account and only the two unit facts show a dash.

    ⚠ Without this the obvious implementation — *no unit, no answer* — blanks
    two rows on every master account in the product, and nothing would go red.
    """
    with tenant_ctx(brazos):
        premises = make_premises(marcus)
        # The payload `test_br_cus_068_master_accounts` already uses, mounted
        # rather than re-derived — a master account needs its owner customer and
        # a tax id, and inventing a second shape here is how the two drift.
        # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
        top_up_homes(marcus, premises["id"])
        master = customers_services.create_master_account(
            marcus,
            {
                "premises_id": premises["id"],
                "account_type": "commercial",
                "opened_at": "2026-08-01",
                "customer": {
                    "display_name": "Ridge Property LLC",
                    "kind": "company",
                    "identity": {"tax_id": "74-2910046"},
                },
            },
        )
        detail = customers_selectors.account_detail_dict(
            customers_selectors.account_or_404(master["id"])
        )

    assert detail["unit_id"] is None
    assert detail["unit_type"] is None, "a master names no unit, so it has no unit TYPE"
    assert detail["premise_address"] not in (None, ""), (
        "hard rule 8: the account walks to its premises for the address — "
        "a master account must not lose the building it owns"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-5163 · hard rule 8 / BR-MET-1161 · BR-CUS-1010 · B2 §2
# generated: 2026-09-13 — with the UNIT group's first render
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

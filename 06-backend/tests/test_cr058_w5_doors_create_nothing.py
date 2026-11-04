# ── Trace ──────────────────────────────────────────────
# Change:  CR-058 task 19 — the two doors the PO confirmed UNCHANGED get a test
#          each, so a later lane cannot quietly widen them.
# Ruling:  PO 2026-09-01. On the units import: *"this is correct no changes
#          here"*. On the new service request: *"this si also correct no
#          chnges"*.
# Rules:   BR-MET-1031 (the units import creates units and nothing else) ·
#          BR-CUS-1032 (a service request is a numbered ask and nothing else) ·
#          BR-MET-096 · BR-MET-100 · BR-CUS-093
# ───────────────────────────────────────────────────────
"""CR-058 task 19 — two doors that create nothing, pinned.

WHY A TEST FOR BEHAVIOUR NOBODY IS CHANGING
--------------------------------------------
On 2026-09-01 the PO went through the product door by door and changed three of
them. **The premises import gained a conditional master account and Customer #**
(`BR-MET-1030`); the two doors below were confirmed as they stand.

A confirmation is invisible in code. *"This one creates an account now"* leaves a
diff; *"and the one next to it does not"* leaves nothing at all — so the next
lane reading `import_runs._load_locked` sees the premises branch creating an
owner account, reads the pattern, and adds the same thing to units because it
looks like an omission. **That is what these two cases exist to stop**, and it
is why they assert an ABSENCE rather than a behaviour.

Both are deliberately blunt: run the door, then count the rows in the three
tables the ruling is about. A subtle test here would be worse than none, because
the thing being defended is *"nothing happened"*.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import service_request_service
from apps.metering import import_runs
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

UNIT_HEADERS = ["PREMISE_ID", "UNIT_LABEL", "UNIT_TYPE", "PLAN"]
UNIT_MAPPING = {
    "PREMISE_ID": "premises",
    "UNIT_LABEL": "label",
    "UNIT_TYPE": import_runs.IGNORE,
    "PLAN": import_runs.IGNORE,
}


def _csv(rows, headers):
    lines = [",".join(headers)]
    lines += [",".join(str(row.get(column, "")) for column in headers) for row in rows]
    return "\n".join(lines) + "\n"


def test_cr058_w5__the_units_import_creates_units_and_nothing_else(brazos, marcus):
    """`BR-MET-1031` — PO verbatim: *"this is correct no changes here"*.

    A units upload writes `units` rows. **No account, no customer, no
    `customer_accounts` link** — and the counts are taken before and after so
    the assertion is about this run rather than about an empty database.
    """
    with tenant_ctx(brazos):
        premises = make_premises(marcus)
        accounts_before = customers_models.Account.objects.count()
        customers_before = customers_models.Customer.objects.count()
        links_before = customers_models.CustomerAccount.objects.count()
        units_before = metering_models.Unit.objects.count()

        run = import_runs.extract(
            marcus,
            {
                "target": "units",
                "source_kind": "file",
                "file_name": "cr058_units_create_nothing.csv",
                "content": _csv(
                    [{"PREMISE_ID": premises["premise_no"], "UNIT_LABEL": "Apt 101"}],
                    UNIT_HEADERS,
                ),
            },
        )
        import_runs.transform(marcus, run["id"], {"mapping": UNIT_MAPPING})
        import_runs.validate(marcus, run["id"])
        import_runs.load(marcus, run["id"], {"write_mode": "insert"})

        assert metering_models.Unit.objects.count() == units_before + 1, (
            "the units import still creates units — this case pins what it does "
            "NOT do, and a version that created nothing at all would satisfy "
            "every assertion below while being broken"
        )
        assert customers_models.Account.objects.count() == accounts_before, (
            "BR-MET-1031: the units import creates NO account. The premises "
            "import gained one on 2026-09-01 and this one was confirmed "
            "unchanged in the same exchange."
        )
        assert customers_models.Customer.objects.count() == customers_before, (
            "BR-MET-1031: no Customer # either. A unit has no owner and no "
            "party of its own."
        )
        assert customers_models.CustomerAccount.objects.count() == links_before


def test_cr058_w5__the_units_target_offers_no_owner_identity_column(brazos, marcus):
    """The second half of the same defence, and it is the one that would catch a
    widening EARLY.

    A lane adding an owner account to the units import would first have to offer
    the columns to carry the identity — `VIRTUAL_COLUMNS_BY_TARGET` is keyed by
    target for exactly this reason.
    """
    with tenant_ctx(brazos):
        offered = {entry["target"] for entry in import_runs.target_columns("units")}
        assert not (offered & set(import_runs.PREMISES_OWNER_COLUMN_NAMES))
        assert import_runs.VIRTUAL_COLUMNS_BY_TARGET.get("units") in (None, ())


def test_cr058_w5__a_new_service_request_creates_a_numbered_request_and_nothing_else(
    brazos, marcus
):
    """`BR-CUS-1032` — PO verbatim: *"this si also correct no chnges"*.

    A service request is an ASK, not a party and not an account. It is numbered
    at creation (`BR-CUS-093`, PO 2026-08-24) and that is the whole of what it
    creates.

    ⚠ **A REQUEST MAY LINK TO A CUSTOMER LATER** — `service_request_service.
    link_customer` is the clerk's own act on `REQ-03`. What it may not do is
    MINT one at creation, and that is what this pins.
    """
    with tenant_ctx(brazos):
        accounts_before = customers_models.Account.objects.count()
        customers_before = customers_models.Customer.objects.count()
        links_before = customers_models.CustomerAccount.objects.count()

        request = service_request_service.create_request(
            marcus,
            {
                "address_as_given": "1408 Elm Street, Katy TX",
                "applicant_name": "Okafor, Chidi",
            },
        )

        assert request.request_no, (
            "BR-CUS-093: every draft is numbered at creation. A request with no "
            "number would satisfy the absence assertions below and be broken."
        )
        assert customers_models.Account.objects.count() == accounts_before, (
            "BR-CUS-1032: the new-request door creates NO account. Two of the "
            "doors beside it started resolving a customer on 2026-09-01; this "
            "one was confirmed unchanged in the same exchange."
        )
        assert customers_models.Customer.objects.count() == customers_before, (
            "BR-CUS-1032: and no Customer #. An applicant's name on a request "
            "is not a party on file — the request records who ASKED."
        )
        assert customers_models.CustomerAccount.objects.count() == links_before

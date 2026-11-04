# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6917 (PO, live beta v2.352.0) — the Accounts register drew
#           TWO service chips on `AC-2026-00057` while its premises carried
#           four services, and NO SURFACE IN THE PRODUCT could say whether the
#           account took two or whether this read lost two.
# Law:      CLAUDE.md hard-won law 7, fifth shape, verbatim — *a declared blind
#           spot with no number beside it is indistinguishable from an empty
#           one*. `service_codes_for_accounts` skipped every agreement it could
#           not resolve (`if code:`) and counted nothing, so a short row and a
#           complete row were the same picture.
# Rules:    BR-CUS-015 (one chip per ACTIVE service agreement) · BR-CUS-672 (an
#           account's services come from its unit) · BR-CUS-1093 (a MASTER's
#           come from its premises) · BR-CUS-045 (a log line holds no PII) ·
#           hard rule 1 (a point another tenant owns is invisible, by design)
# Impacts:  apps/customers/selectors.py · 07-frontend accountsListCells.tsx
# ───────────────────────────────────────────────────────
"""DEF-CUS-6917 — the dropped chip is COUNTED, on the row and in the log.

**WHAT WAS WRONG, AND IT WAS NOT THE CHIPS.** The chips are what the account
agreed to take (`BR-CUS-015`/`BR-CUS-672`), which is deliberate and is not
changed by one line of this fix. What was wrong is that the read had a hole in
it with no number beside it: an open agreement whose service point would not
resolve was dropped silently, and the row rendered as a correct row.

**MEASURED FIRST, ON REAL POSTGRESQL, BEFORE ANY CODE MOVED (2026-09-27).**
Across the two tenants in the development database — Brazos Bend Utilities and
BILLNARROW Six-Service Utility — there are **479 open service agreements and
479 of them resolve to a service code; zero drop.** That number is the reason
this file exists rather than a fix to the resolution: **today the hole is
empty, and before this change nothing in the product could have told anybody
that.**

**A NULL SERVICE COLUMN IS NOT ONE OF THE WAYS IT HAPPENS.** Checked against
`information_schema` the same day: `service_points.service_id` is `NOT NULL`
with a `PROTECT` FK, `services.code` is `NOT NULL`, and
`service_agreements.service_point_id` carries a real FK — so a service point
with no service cannot be stored and a dangling agreement cannot be stored
either. The reachable causes are the two below.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A selector that reported a drop for
every account would satisfy tc1 and be wrong on the 100% of rows that are
healthy, so tc2 asserts a healthy account reports exactly `0` — and asserts the
KEY is present with that value, because an absent key is the original defect in
a nicer coat. A selector that counted ENDED agreements would inflate tc1, so
tc3 closes one and requires the count not to move. And a fix that touched only
the batched plural would leave the account detail screen silent, so tc4 asserts
the singular counts the same number for the same account.
"""

import logging
from datetime import date

import pytest

from apps.customers import models as customer_models
from apps.customers import seams as customer_seams
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import services as metering_services

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OPENED = date(2026, 8, 1)


def _account_on_two_services(actor, tenant, address):
    """An ordinary account with TWO open agreements, through the real doors.

    Two services and not one because the defect is about ARITHMETIC: a count of
    one cannot tell "all of them" from "half of them".
    """
    plan = make_plan(tenant, name=f"Plan {address}", services=["water", "electric"])
    premises = make_premises(
        actor, address_line=address, services_available=["water", "electric"]
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["water", "electric"])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": "Elena Rivera"},
            "customer": identity_fixtures.customer_block(
                "Elena Rivera", account_type="residential"
            ),
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


def _blind_metering(monkeypatch):
    """Metering answers NOTHING about service points — the page-wide cause.

    This is not an invented state. `customers.seams.service_points_for_units`
    and `service_codes_for_points` BOTH return `{}` when
    `seams.resolve("metering", …)` finds no module, and each says so in its own
    docstring. When that happens every code on every row resolves to `None` and
    **the whole register loses its chips at once** — which before this change
    was indistinguishable from a tenant that had configured no services.

    ⚠ **FOUR FUNCTIONS AND NOT TWO, AND THE FIRST DRAFT OF THIS FIXTURE BLINDED
    ONLY THREE.** The batched read reaches metering through
    `service_points_for_units` + `service_codes_for_points`; the SINGULAR reaches
    it through `service_points_for` + `service_point_ref`. **They are different
    doors**, so a metering outage that closes one can leave the other open — and
    on the first run of this file tc4 duly reported the plural losing two chips
    and the singular losing none, which read exactly like the fix having a hole
    in it. It did not; the fixture did. Recorded rather than quietly patched,
    because the same asymmetry is a real latent divergence between the register
    and the account detail screen.
    """
    monkeypatch.setattr(customer_seams, "service_points_for_units", lambda _ids: {})
    monkeypatch.setattr(customer_seams, "service_codes_for_points", lambda _ids: {})
    monkeypatch.setattr(customer_seams, "service_points_for", lambda _id: [])
    monkeypatch.setattr(customer_seams, "service_point_ref", lambda _id: None)


# ══════════════════════════════════════════════════════════════════════════
# THE PIN
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_6917_tc1__a_read_that_loses_a_chip_says_how_many(brazos, dana, monkeypatch):
    """**THE PRODUCT OWNER'S PICTURE, REPRODUCED.** Two open agreements, no
    resolvable code for either — and before this change the row served
    `services: []` and nothing else, which the register draws as *No services*.

    Now the codes are still `[]` — the chips must not invent what they could
    not read — and the row carries `services_unresolved: 2`.
    """
    with tenant_ctx(brazos):
        account = _account_on_two_services(dana, brazos, "101 Cedar Row")
        assert len(customer_selectors.service_agreements_for(account)) == 2

        _blind_metering(monkeypatch)
        codes, drops = customer_selectors.service_codes_and_drops_for_accounts([account])

        assert codes[str(account.id)] == [], "nothing may be invented to fill the cell"
        assert drops[str(account.id)] == 2, "and the hole is a NUMBER, not a silence"

        row = customer_selectors.account_row(
            account, service_codes=codes, service_drops=drops
        )
        assert row["services"] == []
        assert row["services_unresolved"] == 2


def test_def_cus_6917_tc2__a_healthy_account_states_zero_rather_than_omitting_it(
    brazos, dana
):
    """**THE CASE THAT IS 100% OF TODAY'S DATA** (479 of 479 agreements resolve).

    The key is SERVED, with the value `0`. A key that appeared only when
    something went wrong would be a blind spot with no number beside it wearing
    a slightly better disguise — an absent field and a zero field look the same
    to a reader and mean opposite things.
    """
    with tenant_ctx(brazos):
        account = _account_on_two_services(dana, brazos, "103 Cedar Row")
        codes, drops = customer_selectors.service_codes_and_drops_for_accounts([account])

        assert codes[str(account.id)] == ["electric", "water"]
        assert drops[str(account.id)] == 0

        row = customer_selectors.account_row(
            account, service_codes=codes, service_drops=drops
        )
        assert "services_unresolved" in row, "an absent key IS the defect"
        assert row["services_unresolved"] == 0


def test_def_cus_6917_tc3__an_ENDED_agreement_is_not_a_drop(brazos, dana, monkeypatch):
    """A closed agreement was never going to be a chip (`BR-CUS-015` — one chip
    per ACTIVE agreement), so it cannot be counted as one that was lost.

    Without this case a counter placed one line higher in the loop would pass
    tc1 and inflate every account that has ever moved out of a service.
    """
    with tenant_ctx(brazos):
        account = _account_on_two_services(dana, brazos, "105 Cedar Row")
        agreements = customer_selectors.service_agreements_for(account)
        closed = agreements[0]
        customer_models.ServiceAgreement.objects.filter(pk=closed.pk).update(
            ended_on=date(2026, 8, 20)
        )

        _blind_metering(monkeypatch)
        _codes, drops = customer_selectors.service_codes_and_drops_for_accounts([account])
        assert drops[str(account.id)] == 1, "one live agreement lost, not two"


def test_def_cus_6917_tc4__the_singular_counts_what_the_plural_counts(
    brazos, dana, monkeypatch
):
    """One answer, two query plans — the same pin `BR-CUS-1093`'s tc6 puts on
    the codes, now on the count.

    `service_codes_and_drops_for` serves the account DETAIL header and every
    caller that builds one row; the batched plural serves the register. A fix
    applied to one of them would make the drop visible on the list and
    invisible on the screen a clerk opens to investigate it.
    """
    with tenant_ctx(brazos):
        account = _account_on_two_services(dana, brazos, "107 Cedar Row")
        _blind_metering(monkeypatch)

        _codes, drops = customer_selectors.service_codes_and_drops_for_accounts([account])
        singular_codes, singular_drops = customer_selectors.service_codes_and_drops_for(
            account
        )

        assert singular_drops == drops[str(account.id)] == 2
        assert singular_codes == []


def test_def_cus_6917_tc5__the_number_reaches_an_operator_who_never_opened_the_screen(
    brazos, dana, monkeypatch, caplog
):
    """**THE OTHER HALF OF THE FIX, AND THE SCREEN CANNOT DO IT.**

    A chip in the cell tells the clerk standing in front of that row. It cannot
    tell anybody that this happened on a page nobody opened, and *how often does
    this happen* is the question the PO's report could not be answered in.

    ⚠ **AND THE LINE CARRIES NO PII** (`BR-CUS-045`): a tenant id, an account id
    and a count. No name, no address, no account number. B14 rule 31 bans a
    database id from a SCREEN; a log line is not a screen and an id is exactly
    what an operator pastes into a query.
    """
    with tenant_ctx(brazos):
        account = _account_on_two_services(dana, brazos, "109 Cedar Row")
        _blind_metering(monkeypatch)

        with caplog.at_level(logging.WARNING, logger="smartbillhub.customers"):
            customer_selectors.service_codes_and_drops_for_accounts([account])

        lines = [r.getMessage() for r in caplog.records if "DEF-CUS-6917" in r.getMessage()]
        assert len(lines) == 1, "one line per affected account, not one per agreement"
        assert str(account.id) in lines[0]
        assert "unresolved=2" in lines[0]
        assert "Elena Rivera" not in lines[0], "BR-CUS-045 — a log holds no PII"


def test_def_cus_6917_tc6__a_healthy_page_writes_no_line_at_all(brazos, dana, caplog):
    """A log line that is always there means nothing. Silence is what makes the
    line in tc5 worth reading."""
    with tenant_ctx(brazos):
        account = _account_on_two_services(dana, brazos, "111 Cedar Row")
        with caplog.at_level(logging.WARNING, logger="smartbillhub.customers"):
            customer_selectors.service_codes_and_drops_for_accounts([account])
        assert not [r for r in caplog.records if "DEF-CUS-6917" in r.getMessage()]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-6917 · maintenance process 12-governance/22 (reproduce → locate → blast radius → minimal fix)
# generated: 2026-09-27 by lane CUS-CHIPS
# proved-red: every case above was run against the pre-fix selector and failed on `AttributeError: module 'apps.customers.selectors' has no attribute 'service_codes_and_drops_for_accounts'`; the frontend half was proved red by suppressing the chip and watching 3 of 5 cases fail on the missing `?N`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

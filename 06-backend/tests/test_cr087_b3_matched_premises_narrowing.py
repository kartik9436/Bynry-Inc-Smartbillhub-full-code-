# ── Trace ──────────────────────────────────────────────
# Change:  CR-087 task B3 (`PRB-05`) — *"`GET /taxes/matched-premises` narrows on
#          class and service"*, blueprint screen 07: *"the count on this step now
#          narrows on the customer classes and the services as well … Until it
#          is, the number on screen is the BOUNDARY's count and not the tax's
#          reach, which is the one way this safeguard can mislead rather than
#          fail."*
# Rules:   BR-RAT-107 (the count runs the ENGINE'S OWN PREDICATE, never a WHERE
#          clause that agrees with it) · DEF-273 (a restriction the caller cannot
#          evaluate CLOSES the gate — under-charging is recoverable, over-charging
#          is a refund) · NFR-3 (a count is a count; this read grows no list)
# ───────────────────────────────────────────────────────
"""The premises count answers the TAX'S reach, not the boundary's.

── WHY THIS IS A SAFEGUARD AND NOT A STATISTIC ──────────────────────────────
A boundary that matches nobody is the commonest and most expensive mistake on
the tax wizard: the tax is set up, it looks correct, and it reaches no one. The
count exists to put that in front of a clerk *before they leave the step*. Until
this change it counted the boundary alone, so a tax restricted to Commercial
customers on Water reported every premises in the utility — a number that is
larger than the truth, on the safeguard whose whole job is to be smaller than
the total when something is wrong.

── PROVED RED FIRST (hard-won law 7) ────────────────────────────────────────
At HEAD, `selectors.matched_premises` takes two positional arguments and no
keywords, so every case below printed:

    TypeError: matched_premises() got an unexpected keyword argument
    'customer_classes'

and the API case answered `count: 4` — the boundary's count — where the tax
reaches one premises.

── THE ARITHMETIC, ON A FOUR-PREMISES UTILITY ───────────────────────────────
Brazos Bend sells Electric and Water. Four premises, one account and one metered
service each:

    P-000  residential  electric
    P-001  residential  water
    P-002  commercial   electric
    P-003  commercial   water

  * no narrowing at all                    → 4   (today's behaviour, unmoved)
  * Commercial only                        → 2   (P-002, P-003)
  * Water only                             → 2   (P-001, P-003)
  * Commercial AND Water                   → 1   (P-003)

The fourth line is the one that matters: the two gates are independent and BOTH
must open, which is exactly how `tax_applies_to` reads them on a real bill.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — the shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


#: The cast, in the order `premise_no` sorts them — so a sample line is
#: predictable and a failure names the premises rather than an index.
CAST: tuple[tuple[str, str, str], ...] = (
    ("500 Main St", "residential", "electric"),
    ("501 Main St", "residential", "water"),
    ("502 Main St", "commercial", "electric"),
    ("503 Main St", "commercial", "water"),
)


def _account_type(code: str):
    """The PLATFORM `account_types` row for a class code.

    Read through the row and never guessed from a NAME — `gather._customer_class`
    states the same rule: a tenant may rename the label on their own screen while
    the platform CODE is the one the rule is written against.
    """
    return customer_models.AccountType.objects.get(code=code)


def _build_estate(tenant, actor) -> None:
    """Four premises, each with a unit, one account of a stated class, and one
    metered service point. Built through the real services where they exist."""
    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    service_rows = {
        code: metering_models.ServicePoint._meta.get_field("service").related_model.objects.get(
            code=code
        )
        for code in {service for _address, _klass, service in CAST}
    }
    for index, (address, klass, service) in enumerate(CAST):
        premises = make_premises(
            actor, address_line=address, city="Katy", services_available=[service]
        )
        unit = make_unit(actor, premises["id"], label=f"U{index}", services=[service])
        customer_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            account_no=f"ACC-{index:04d}",
            status=status,
            account_type=_account_type(klass),
        )
        metering_models.ServicePoint.objects.create(
            tenant=tenant, unit_id=unit["id"], service=service_rows[service]
        )


def test_prb05_the_count_narrows_on_customer_class_and_service(brazos, dana):  # noqa: F811
    """CR-087 B3 — *"ticking Commercial only moves the count before the clerk
    leaves the step"*.

    ⚠ EACH GATE IS THE ENGINE'S OWN (`selectors.tax_applies_to`), not a second
    query that agrees with it — BR-RAT-107. A count computed from a WHERE clause
    would be a second implementation of one rule, and the two would disagree the
    first time either changed.
    """
    with tenant_ctx(brazos):
        _build_estate(brazos, dana)

        everywhere = selectors.matched_premises(None, None)
        commercial = selectors.matched_premises(None, None, customer_classes=("commercial",))
        water = selectors.matched_premises(None, None, services=("water",))
        both = selectors.matched_premises(
            None, None, customer_classes=("commercial",), services=("water",)
        )

    # ⚠ THE UNNARROWED CASE MUST NOT MOVE. This change is additive: a tax that
    # states no class and no service restriction resolves exactly as it always
    # has, which is why no existing figure in the repo moves with it.
    assert everywhere["count"] == 4
    assert everywhere["total"] == 4
    assert everywhere["everywhere"] is True

    assert commercial["count"] == 2, "Commercial only reaches P-002 and P-003"
    assert commercial["total"] == 4, "the denominator is every premises, always"

    assert water["count"] == 2, "Water only reaches P-001 and P-003"

    # The two gates are INDEPENDENT and both must open — `tax_applies_to`'s own
    # reading, on a real bill.
    assert both["count"] == 1, "Commercial AND Water reaches P-003 alone"
    assert [line["address_line"] for line in both["sample"]] == ["503 Main St"]


def test_prb05_a_narrowing_the_estate_cannot_answer_reaches_nobody(brazos, dana):  # noqa: F811
    """DEF-273's fail-safe, carried into the count.

    A premises with no account has no customer class, so a CLASS-RESTRICTED tax
    does not reach it — the same direction `tax_applies_to` fails on a real bill,
    and the same reason: under-charging is recoverable in the next cycle,
    over-charging a customer who is exempt is a refund and a support cycle.

    ⚠ AND THE COUNT MUST STILL SAY 4 WHEN NOTHING IS RESTRICTED, because a
    premises with no account is a real premises and an unrestricted tax reaches
    it. A safeguard that under-counted the unrestricted case would send a clerk
    hunting a boundary fault that does not exist.
    """
    with tenant_ctx(brazos):
        for index in range(4):
            make_premises(dana, address_line=f"{600 + index} Vacant Row", city="Katy")

        unrestricted = selectors.matched_premises(None, None)
        restricted = selectors.matched_premises(None, None, customer_classes=("commercial",))
        unknown_class = selectors.matched_premises(None, None, customer_classes=("agricultural",))

    assert unrestricted["count"] == 4
    assert restricted["count"] == 0, "no account, so no class to satisfy the restriction"
    assert unknown_class["count"] == 0, "a class nobody at this utility holds reaches nobody"


def test_prb05_the_endpoint_passes_both_narrowings_through(brazos, dana):  # noqa: F811
    """The wiring, end to end — the half that actually reaches the screen.

    ⚠ THE SELECTOR BEING RIGHT IS NOT THE FEATURE. Hard-won law 2: a capability
    the endpoint does not pass through is dead code, every test on the selector
    passes, and the count on screen is still the boundary's.

    ⚠ NFR-3 — this read returns a COUNT and a three-line sample and it grows no
    list. Nothing here may become an unpaginated enumeration of premises.
    """
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.rating import api as rating_api

    # Law 2 in its URL form: an endpoint no router mounts is a feature that does
    # not exist, and every test that called the SELECTOR would still pass.
    assert resolve("/api/v1/taxes/matched-premises").func is rating_api.tax_matched_premises

    request = APIRequestFactory().get(
        "/api/v1/taxes/matched-premises",
        {"customer_classes": "commercial", "services": "water"},
    )
    # ⚠ `request.user = …` ON THE RAW REQUEST IS NOT ENOUGH AND SILENTLY 401s.
    # DRF's own `Request.user` runs the authenticators and overwrites whatever
    # the underlying Django request carried, so the first draft of this test
    # measured `assert 401 == 200` against a correct permission check. The two
    # server-attached facts `core.permissions._role_of` reads are the SESSION
    # user (through DRF's own force hook) and `tenant_role` (a plain attribute,
    # which DRF proxies through).
    force_authenticate(request, user=dana.user)
    request.tenant_role = "system_admin"
    request.tenant_id = brazos.id

    with tenant_ctx(brazos):
        _build_estate(brazos, dana)
        response = rating_api.tax_matched_premises(request)

    assert response.status_code == 200, response.data
    assert response.data["count"] == 1, "the endpoint narrows, it does not merely accept the params"
    assert response.data["total"] == 4
    assert len(response.data["sample"]) <= 3, "NFR-3 — a sample, never every premises"


def test_prb05_the_query_parameters_are_read_as_repeatable_and_as_csv(brazos, dana):  # noqa: F811
    """Two spellings of a list in a query string, and both have to work.

    A tick-list on a screen sends `?customer_classes=a&customer_classes=b`; a
    hand-typed URL and every worked example in the blueprint send
    `?customer_classes=a,b`. Reading only one of them would make the safeguard
    silently unnarrowed for whichever caller used the other — the exact failure
    mode this task exists to close, one layer down.
    """
    assert rating_api_filter_list(["commercial", "residential"]) == ("commercial", "residential")
    assert rating_api_filter_list(["commercial,residential"]) == ("commercial", "residential")
    assert rating_api_filter_list([" commercial , , residential "]) == (
        "commercial",
        "residential",
    )
    # An absent parameter is NOT an empty restriction — it is no restriction at
    # all, and the two must not be confused: an empty tuple means "every class".
    assert rating_api_filter_list([]) == ()
    assert rating_api_filter_list([""]) == ()


def rating_api_filter_list(values):
    from apps.rating.api import matched_premises_filter_list

    return matched_premises_filter_list(values)

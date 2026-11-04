"""BR-CUS-1070 — each service on a request carries its own requested start.

⚠ **WHAT THIS FILE EXISTS TO STOP COMING BACK, AND IT IS NOT A MISSING COLUMN.**
`service_request_services.requested_start` has been in the schema since
`customers/0017` and `set_services` has always WRITTEN it — as
`requested_start=request.requested_start`, a copy of the job-level
`Connection date`. So a clerk could never give two services different dates: the
column existed, was written, and was not theirs to set. That is hard-won law 2
one layer below the screen — every check passed over it because the column was
never empty.

**The drawing settles the fallback and it is worth restating here, because a
later lane reading only this code would reasonably "simplify" the copy back in.**
Blueprint entry 06 `p080`, the step-6 review block, draws two adjacent rows of
ONE request: `Requested start → 05/12/2026, all three` and
`Connection date → — not given`. **No fallback can produce that state.** If a
service's date came from the job's, three given dates could not sit over a blank
job date; if the job's were derived from the services', it could not read *not
given*. Hence NULL means *the clerk gave none*, in both directions, and the copy
is gone.

**Proved RED before the code moved — 14 failed, 1 passed** against the
pre-change tree, and the two reds worth quoting are these, because between them
they are the whole defect:

    test_a_bare_code_still_means_no_date_given
        assert [row["requested_start"] for row in _served(request)["services"]] == [None, None]
    E   AssertionError: assert ['2026-11-02', '2026-11-02'] == [None, None]

    test_no_services_at_all_is_a_count_of_zero
    E   KeyError: 'requested_start_agreement'

The first is the copy: a clerk picks electric and water and gives neither a
date, and both come back stamped with the job's `Connection date`. The one test
that PASSED before the change was the unknown-service refusal — a guard that
already existed and had to survive the widening.
"""

from __future__ import annotations

from datetime import date

import pytest

from core import errors

from apps.customers import models as customers_models
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "address_as_given": "212 Balcones Drive",
}

#: The drawn dates, and they are ILLUSTRATIONS under B14 rule 37 — what is
#: asserted is that THREE INDEPENDENT VALUES survive the round trip, never that
#: any particular date does.
ELECTRIC_ON = date(2026, 12, 5)
SEWER_A_FORTNIGHT_LATER = date(2026, 12, 19)


def _new(actor, **overrides):
    return sr.create_request(actor, {**CAPTURE, **overrides})


def _served(request):
    return reads.location_tab(request, sr.evidence_for(request))


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE WRITE — three services, three dates, one request
# ═══════════════════════════════════════════════════════════════════════════
def test_a_clerk_sets_three_different_starts_on_one_request(brazos, dana):
    """The blueprint's own argument, executed: *"A block that needs electric on
    the 12th and sewer a fortnight later is one request and not two."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(
            dana,
            request.id,
            [
                {"code": "electric", "requested_start": ELECTRIC_ON},
                {"code": "sewer", "requested_start": SEWER_A_FORTNIGHT_LATER},
                {"code": "water", "requested_start": ELECTRIC_ON},
            ],
        )
        served = _served(request)["services"]
        assert {row["code"]: row["requested_start"] for row in served} == {
            "electric": "2026-12-05",
            "sewer": "2026-12-19",
            "water": "2026-12-05",
        }
        # `available` is a different fact and is untouched — REQ-03.3's CHECK
        # callout: NULL is *not yet asked* and is never spelled the same as *no*.
        assert all(row["available"] is None for row in served)


def test_an_iso_string_is_accepted_as_well_as_a_date(brazos, dana):
    """The API hands this function whatever came off the wire, which is a
    string. A test that only ever passes `date` objects would leave the one
    shape the product actually uses unproved."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(dana, request.id, [{"code": "gas", "requested_start": "2026-12-05"}])
        assert _served(request)["services"][0]["requested_start"] == "2026-12-05"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE FALLBACK THAT IS NOT THERE — in both directions
# ═══════════════════════════════════════════════════════════════════════════
def test_an_unset_service_start_stays_null_and_does_not_borrow_the_job_date(brazos, dana):
    """**This is the assertion the old copy failed.** `Connection date` is given
    and no per-service date is; every service must still read *not given*."""
    with tenant_ctx(brazos):
        request = _new(dana, requested_start=date(2026, 11, 2))
        sr.set_services(dana, request.id, [{"code": "electric"}, {"code": "water"}])
        served = _served(request)
        assert [row["requested_start"] for row in served["services"]] == [None, None]
        # …and the job's own date is untouched by any of it.
        assert reads.detail(request.id)["header"]["requested_start"] == "2026-11-02"


def test_a_bare_code_still_means_no_date_given(brazos, dana):
    """The shape every caller sent until 2026-09-15 is still accepted, and it
    means *this service, no date given* rather than *copy the job's*."""
    with tenant_ctx(brazos):
        request = _new(dana, requested_start=date(2026, 11, 2))
        codes = sr.set_services(dana, request.id, ["electric", "water"])
        assert codes == ["electric", "water"]
        assert [row["requested_start"] for row in _served(request)["services"]] == [None, None]


def test_the_job_date_is_not_derived_from_the_services(brazos, dana):
    """The other direction of the same rule. Three services carry a date and the
    request's own `Connection date` still reads *not given* — which is exactly
    the pair `p080` draws."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(
            dana,
            request.id,
            [{"code": c, "requested_start": ELECTRIC_ON} for c in ("electric", "water", "sewer")],
        )
        assert reads.detail(request.id)["header"]["requested_start"] is None
        assert _served(request)["requested_start_agreement"]["agreed"] == "2026-12-05"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE READ — enough to say *all three*, and enough to list them when not
# ═══════════════════════════════════════════════════════════════════════════
def test_the_agreement_block_says_all_three_agree(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(
            dana,
            request.id,
            [{"code": c, "requested_start": ELECTRIC_ON} for c in ("electric", "water", "sewer")],
        )
        assert _served(request)["requested_start_agreement"] == {
            "count": 3,
            "agreed": "2026-12-05",
            "unset": 0,
        }


def test_one_service_a_fortnight_later_is_not_an_agreement(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(
            dana,
            request.id,
            [
                {"code": "electric", "requested_start": ELECTRIC_ON},
                {"code": "water", "requested_start": ELECTRIC_ON},
                {"code": "sewer", "requested_start": SEWER_A_FORTNIGHT_LATER},
            ],
        )
        assert _served(request)["requested_start_agreement"] == {
            "count": 3,
            "agreed": None,
            "unset": 0,
        }


def test_all_unset_is_not_an_agreement_either(brazos, dana):
    """Three services all saying *not given* must NOT read as three services
    agreeing on a date — `agreed` is a date or it is nothing, and `unset` is how
    a screen tells this case from the one above it."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(dana, request.id, ["electric", "water", "sewer"])
        assert _served(request)["requested_start_agreement"] == {
            "count": 3,
            "agreed": None,
            "unset": 3,
        }


def test_one_service_with_a_date_agrees_with_itself(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(dana, request.id, [{"code": "water", "requested_start": ELECTRIC_ON}])
        assert _served(request)["requested_start_agreement"] == {
            "count": 1,
            "agreed": "2026-12-05",
            "unset": 0,
        }


def test_no_services_at_all_is_a_count_of_zero(brazos, dana):
    """A request that has not reached step 2 — the shape the demo tenant's eight
    rows are all in today. Nothing may divide by that zero."""
    with tenant_ctx(brazos):
        request = _new(dana)
        assert _served(request)["requested_start_agreement"] == {
            "count": 0,
            "agreed": None,
            "unset": 0,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE REFUSALS — by name, never a 500
# ═══════════════════════════════════════════════════════════════════════════
def test_a_repeated_service_is_refused_by_name_rather_than_by_the_database(brazos, dana):
    """`ux_sr_services_request_service` is UNIQUE on (request, service), so a
    repeat used to reach the database and come back as an `IntegrityError` — a
    500 with no sentence in it. A list of objects makes a repeat much easier to
    send than a list of bare codes did, so it is refused in the service."""
    with tenant_ctx(brazos):
        request = _new(dana)
        with pytest.raises(errors.ValidationError) as caught:
            sr.set_services(
                dana,
                request.id,
                [
                    {"code": "electric", "requested_start": ELECTRIC_ON},
                    {"code": "electric", "requested_start": SEWER_A_FORTNIGHT_LATER},
                ],
            )
        assert caught.value.message_key == "customers.serviceRequest.serviceRepeated"


def test_something_that_is_not_a_date_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana)
        with pytest.raises(errors.ValidationError) as caught:
            sr.set_services(dana, request.id, [{"code": "electric", "requested_start": "next tue"}])
        assert caught.value.message_key == "customers.serviceRequest.requestedStartNotADate"


def test_an_unknown_service_is_still_refused_in_the_object_shape(brazos, dana):
    """The refusal `set_services` already made must survive the widening — a new
    payload shape that quietly skips an existing guard is the widening doing
    damage."""
    with tenant_ctx(brazos):
        request = _new(dana)
        with pytest.raises(errors.ValidationError) as caught:
            sr.set_services(
                dana, request.id, [{"code": "unobtanium", "requested_start": ELECTRIC_ON}]
            )
        assert caught.value.message_key == "customers.serviceRequest.serviceUnknown"


def test_a_replacement_set_replaces_the_dates_too(brazos, dana):
    """`set_services` REPLACES the set. A clerk who goes back to step 2 and
    changes a date must not find the old row still there beside the new one."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(dana, request.id, [{"code": "electric", "requested_start": ELECTRIC_ON}])
        sr.set_services(
            dana, request.id, [{"code": "electric", "requested_start": SEWER_A_FORTNIGHT_LATER}]
        )
        served = _served(request)["services"]
        assert [(r["code"], r["requested_start"]) for r in served] == [("electric", "2026-12-19")]
        assert (
            customers_models.ServiceRequestService.objects.filter(request_id=request.id).count() == 1
        )


def test_the_whole_detail_can_be_read_with_services_on_the_request(brazos, dana):
    """`DEF-CUS-5412` — and it is here because writing a service row is what
    made it visible.

    `request_jobs._service_codes` read `row.service_code`, which is not a field
    on `ServiceRequestService` (`service` is a FK; the code is
    `row.service.code`). It raised `AttributeError` inside `reads.detail()`, so
    `GET /service-requests/{id}` was a **500 for any request that had
    services** — and nothing could see it, because the comprehension evaluates
    the attribute only when the queryset yields a row and
    `service_request_services` held ZERO rows in the demo tenant and in every
    suite. ⚠ **The demo half of that stopped being true on 2026-09-16
    (`DEF-CUS-5423`): the seeder now records services at capture step 2, so a
    freshly seeded tenant carries twelve of them.** The whole detail is read
    here rather than one tab, so the next lane that walks a child table from
    this payload is covered too.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(
            dana,
            request.id,
            [
                {"code": "electric", "requested_start": ELECTRIC_ON},
                {"code": "sewer", "requested_start": SEWER_A_FORTNIGHT_LATER},
            ],
        )
        detail = reads.detail(request.id)
        assert [row["code"] for row in detail["location_and_services"]["services"]] == [
            "electric",
            "sewer",
        ]


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE TENANT — hard rule 1
# ═══════════════════════════════════════════════════════════════════════════
def test_a_service_row_is_written_under_the_requests_own_tenant(brazos, dana):
    """Every row this function creates takes its tenant from the REQUEST, never
    from the caller's ambient context.

    ⚠ **THIS TEST DELIBERATELY DOES NOT CLAIM TO PROVE ISOLATION, AND THE FIRST
    DRAFT OF IT DID.** That draft opened a second tenant's context and asserted
    the rows had vanished — which is hard-won law 7's *incapable of proving what
    it claims*: the suite runs on in-memory sqlite, which has no row-level
    security at all, and even on PostgreSQL a plain ORM query runs as a role
    that BYPASSES RLS in dev. The assertion would have gone green over a
    guarantee that was never consulted. It went RED instead (`assert 1 == 0`),
    which is the only reason it was caught.

    **The real proof already exists and is not duplicated here:**
    `test_cr031_service_request.py::test_a_service_request_is_rls_scoped` runs
    under `SET ROLE sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS) and its
    `SR_TABLES` names `service_request_services`. What is left here is the
    app-layer half, which this file CAN prove: the tenant on the row is the
    request's.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(
            dana,
            request.id,
            [
                {"code": "electric", "requested_start": ELECTRIC_ON},
                {"code": "water", "requested_start": SEWER_A_FORTNIGHT_LATER},
            ],
        )
        rows = customers_models.ServiceRequestService.objects.filter(request_id=request.id)
        assert {row.tenant_id for row in rows} == {request.tenant_id}
        assert len(rows) == 2

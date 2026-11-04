# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-REP-6898 — every named report refusal reached the clerk as HTTP
#          500 "Something went wrong on our side. Nothing was saved."
# Covers:  apps/reports/api.report — the except tuple · screen S46
# Rules:   BR-REP-024 (*a stated absence, never a silent one*) · B14 rule 33
#          (RATIONALE is zero words on screen) · hard-won law 2 (built is not
#          wired) · hard-won law 7 (*ask what would make this check pass
#          wrongly*)
# ───────────────────────────────────────────────────────
"""**A REPORT THAT CANNOT BE PRODUCED SAYS SO, WITH A STATUS THAT IS NOT 500.**

⚠ **THIS FILE ASSERTS THE HTTP ANSWER AND NEVER THE EXCEPTION, WHICH IS THE
WHOLE POINT.** Eight suites already assert `pytest.raises(DatasetCannotServe)`
and every one of them was green on 2026-09-27 while **27 of the 46 reports**
answered `500 SYS-INTERNAL` in a browser and drew *"The finance figures could
not be loaded / Something went wrong on our side. Nothing was saved."* over a
meter-reads report. A test that asserts an exception passes on a 500 forever:
the exception IS raised, correctly, and then falls through DRF's catch-all
because `api.report`'s `except` tuple named its two SIBLING classes
(`DefinitionNotFound`, `DatasetNotExecutable`) and not it.

⚠ **AND `assert response.status_code != 200` WOULD PASS ON THE BUG.** So does
`assert it raises`. Both were available and neither was written. Every case
below asserts the exact status, the exact `message_key` and — where it matters
— that the sentence a clerk reads is the SAME sentence the catalogue card
two clicks earlier already renders.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from apps.reports import api as reports_api
from apps.reports import catalogue_read, queries

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db

#: The one sentence a clerk reads, keyed the way the CARD keys it. There is no
#: second string: `reports.library.unavailableGeneric` is already authored in
#: all eleven catalogues, so this refusal adds no key and cannot become the
#: twelfth instance of `DEF-REP-6900` (a key used and never added).
CANNOT_BE_PRODUCED_KEY = "reports.library.unavailableGeneric"


def _seeded_catalogue():
    """`(key, dataset)` for all 46, read from the migration that seeds them —
    the same source `test_rep_wire_catalogue_reachable` reads, for the same
    reason: a table read answers over whatever this run happened to seed."""
    path = pathlib.Path(__file__).resolve().parents[1] / (
        "apps/reports/migrations/0003_seed_catalogue.py"
    )
    spec = importlib.util.spec_from_file_location("rep_seed_catalogue_refusal", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return tuple((row[1], row[5]) for row in module.DEFINITIONS)


CATALOGUE = _seeded_catalogue()


def _viewer(tenant, key, **query):
    """`GET /reports/{key}` exactly as the S46 parameter bar submits it."""
    return api_call(
        reports_api.report,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        query=query or None,
        key=key,
    )


def test_a_refused_report_answers_422_and_not_500(brazos):
    """⚠ **THE RED ONE.** R28 Read Completeness is a METER READS report whose
    grain is a ROUTE; the `meter_reads` dataset publishes one row per READ and
    declines it by name. Before the fix this call answered **500 SYS-INTERNAL**.
    """
    with tenant_ctx(brazos):
        response = _viewer(brazos, "read_completeness")
    assert response.status_code == 422, (
        f"a report that cannot be produced answered {response.status_code}; "
        "500 tells a clerk the product broke"
    )
    assert response.data["code"] == "BIZ-COMPLETENESS"
    assert response.data["message_key"] == CANNOT_BE_PRODUCED_KEY
    assert response.data["br_ref"] == "BR-REP-024"
    assert response.data["params"]["key"] == "read_completeness"
    # The machine reason code the CARD carries, so the screen can render the
    # more specific sentence where one is authored.
    assert response.data["params"]["reason_code"] == catalogue_read.REASON_GRAIN_NOT_SERVED


def test_the_viewer_and_the_catalogue_card_say_the_same_thing(brazos):
    """`DEF-REP-6898`'s second half: the two surfaces DISAGREED. The grid said
    *"This report cannot be produced yet."* and the viewer said the server
    broke. Both now resolve one key from one function."""
    with tenant_ctx(brazos):
        card_reason = queries.definition_refusal("read_completeness", "meter_reads")
        response = _viewer(brazos, "read_completeness")
    assert card_reason, "the card has no reason, so this case proves nothing"
    assert response.data["params"]["reason_code"] == catalogue_read.REASON_GRAIN_NOT_SERVED
    # ⚠ The engineering prose NEVER travels to the screen (B14 rule 33 —
    # rationale is zero words on screen) but it does travel to the log.
    assert response.data["params"]["detail"] == card_reason


def test_a_producible_report_is_untouched(brazos):
    """The mirror, and it is the half that would be missed: do not make a
    producible report look refused. AR Ageing serves rows today."""
    with tenant_ctx(brazos):
        response = _viewer(brazos, "ar_aging")
    assert response.status_code == 200, response.data
    assert "rows" in response.data


def test_an_unknown_key_is_still_the_unknown_key_refusal(brazos):
    """A typo must not acquire the *"cannot be produced"* sentence — that would
    tell a clerk a report they invented exists but is unbuilt."""
    with tenant_ctx(brazos):
        response = _viewer(brazos, "revenue_by_srevice")
    assert response.status_code == 422
    assert response.data["code"] == "VAL-005"
    assert response.data["message_key"] == "reports.viewer.unknown_key"


def test_every_report_in_the_catalogue_answers_200_or_422_and_never_500(brazos, capsys):
    """**THE DELIVERABLE, AND IT COUNTS EVERY SIDE AND SUMS THEM.**

    A run reporting only *"18 served"* reads identically whether the other
    twenty-eight refused with a sentence or fell through every branch
    (`G32` reported `0 unresolved` that way over 21 live refusals). So: a
    verdict per report, every total printed, the sum asserted against the
    catalogue's own size, and **the failure names every report**.

    ⚠ **THERE ARE THREE GOOD ANSWERS AND NOT TWO, AND THE THIRD WAS FOUND BY
    RUNNING THIS.** `account_ledger` answers **422 VAL-001
    `reports.account_ledger.account_required`** — *"Choose an account. This
    report runs for one account at a time."* That is not a fault and not an
    unbuildable report: it is the screen asking for a parameter, and folding it
    into either of the other two buckets would be a wrong count in a file whose
    whole job is counting. It is not pinned to a LITERAL SET of keys, which
    would be the count that rots; what is asserted of it is a PROPERTY — it
    names the field it wants, so a genuine fault cannot hide in this bucket.
    """
    served: list[str] = []
    refused: list[str] = []
    asks: list[str] = []
    broken: list[str] = []
    disagree: list[str] = []

    with tenant_ctx(brazos):
        for key, dataset in CATALOGUE:
            response = _viewer(brazos, key)
            body = response.data if isinstance(response.data, dict) else {}
            if response.status_code == 200:
                served.append(key)
            elif response.status_code == 422 and body.get("message_key") == CANNOT_BE_PRODUCED_KEY:
                refused.append(key)
                # ⚠ **THE AGREEMENT IS ASSERTED OVER ALL OF THEM, NOT OVER ONE.**
                # The defect was two surfaces saying different things about one
                # report, so a single worked example proves a single worked
                # example. This compares the viewer's refusal against the
                # CARD's, report by report, over the whole catalogue.
                card = queries.definition_refusal(key, dataset)
                served_detail = body.get("params", {}).get("detail")
                if served_detail != card:
                    disagree.append(
                        f"{key}: the card says {card!r} and the viewer says {served_detail!r}"
                    )
            elif response.status_code == 422 and body.get("field_errors"):
                asks.append(f"{key} -> {body.get('message_key')}")
            else:
                broken.append(
                    f"{key} (on {dataset}) -> {response.status_code} "
                    f"{body.get('code')} {body.get('message_key')}"
                )

    with capsys.disabled():
        print(
            f"\n  SERVED {len(served)}  REFUSED {len(refused)}  "
            f"ASKS {len(asks)}  BROKEN {len(broken)}"
            f"  = {len(served) + len(refused) + len(asks) + len(broken)} of {len(CATALOGUE)}"
        )
        for row in asks:
            print(f"    ASKS  {row}")
    assert not disagree, (
        "the catalogue card and the viewer give different reasons for the same "
        "report:\n  " + "\n  ".join(disagree)
    )
    assert not broken, (
        "these reports answer a clerk with neither a payload, nor the refusal "
        "sentence the catalogue already holds, nor a named parameter:\n  " + "\n  ".join(broken)
    )
    assert len(served) + len(refused) + len(asks) == len(CATALOGUE)
    # ⚠ **THE FLOOR THAT STOPS THIS PASSING ON A DEAD PRODUCT.** Zero served
    # and forty-six refused would satisfy every assertion above, and would be a
    # catalogue of reports none of which works.
    assert len(served) >= 18, f"only {len(served)} reports still serve rows: {served}"
    assert len(refused) >= 27, f"only {len(refused)} reports name their reason"

# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2381 — a bill run says NOTHING when an account's customer type is
#          covered by no base charge. DEF-3282 fixed the classes the SEEDED
#          codes name; this is the other half the PO asked for: *"A utility that
#          adds their own customer type — agricultural, a housing association,
#          anything — hits the same wall on their own data, and the product
#          still won't say a word. It should be a named finding on step 2."*
# Rules:   BR-RAT-108 (`charges.applies_to_customer_classes` is an INCLUSION
#          list; NULL or `[]` means EVERY class) · BR-RAT-088 (the CHARGE CODE
#          owns the base amount) · BR-BIL-015 (a missing input is an EXCEPTION,
#          never a silent skip) · BR-BIL-040 (a finding surfaces on the tab that
#          owns its stage's inputs) · BR-BIL-055 (a refusal stops ONE account
#          and lets the run continue) · BR-BIL-1024/1025 (no lines, no document
#          — and `silent` means the correct state, `blocked` means a human must
#          act) · B14 rule 32 (no rule id, no internal code in clerk copy)
# Tests:   this file
# Impacts: apps/rating/selectors.py :: base_charge_from_charge_code ·
#          apps/billing/gather.py :: _base_charge_code_for ·
#          apps/billing/runs.py :: STAGE_BY_REASON, NOT_RETRYABLE_HERE ·
#          07-frontend/src/i18n/locales/*.json
# ───────────────────────────────────────────────────────
"""**A CUSTOMER TYPE NO BASE CHARGE COVERS IS A NAMED FINDING, NOT A SILENCE.**

The boundary this file exists to hold, and getting it wrong turns a working
configuration into a refusal:

    the service has NO base charge code at all   -> UNCHANGED. That tenant has
                                                    not adopted BR-RAT-088 and
                                                    still bills from the plan.
    base charges EXIST and none names this
    account's customer type                      -> THE NEW FINDING.
    a base charge naming NO classes at all       -> UNCHANGED. NULL/`[]` is
                                                    every class (BR-RAT-108).

⚠ **RED PROVED FIRST (hard-won law 7).** Every case below was run against the
branch tip before a line of the fix was written. On the tip
`test_the_uncovered_type_is_a_named_finding` failed with

    Failed: DID NOT RAISE <class 'apps.billing.gather.GatherProblem'>

and `test_the_run_puts_the_uncovered_account_in_blocked` failed with

    AssertionError: the run reported NOTHING for an account no base charge
    covers — blocked=(), silent=()

which is the defect in one line: the account gathers, the run reports nothing,
and a clerk finds out when the bill does not arrive.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from apps.billing import gather, runs
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.test_def_438_parity import (  # the fixture set this extends
    CYCLE_DAYS,
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    _account_on,
    _price_live,
    _water_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

LOCALES = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"

#: A category the platform ratifies (BR-CUS-094) and no seeded base charge code
#: has ever named — the PO's own example of a utility's own customer type.
UNCOVERED = "agricultural"
COVERED = "residential"

#: ⚠ **THE CODE'S FIGURE AGREES WITH THE PLAN'S ON PURPOSE.** `_water_plan`
#: states `fixture.WATER_BASE` on `plan_services.base_charge` AND on the rate
#: schedule version, and `_base_charge_for` REFUSES a charge code that states a
#: different one — BR-RAT-088's migration-artefact tripwire. A fixture that
#: disagreed would refuse every case in this file for a reason that has nothing
#: to do with customer types, which is what the first draft did:
#: `GatherProblem: the base charge is stated in more than one place and they
#: disagree`. Equal figures pass through as a duplicate, which is what all 47
#: seeded accounts are.
CODE_BASE = Decimal(fixture.WATER_BASE)


def _base_code(tenant, classes, *, code="BASE-W", amount=CODE_BASE):
    """One `is_base` water charge code, scoped to `classes`.

    `classes=[]` is BR-RAT-108's *every class*, written as the empty list the
    column really stores rather than as `None`, because that is the value a
    tenant's own S12 card produces.

    ⚠ **NAMED ON THE SCHEDULE FROM 2026-10-06 (`DEF-RAT-9832`, PO ruling)** — an
    unnamed schedule bills `$0.00` for every class, so the class scoping this
    file is about is only reached through a NAMED code.
    """
    from tests.base_code_naming import name_base_code

    return name_base_code(
        tenant,
        rating_models.Charge.objects.create(
            tenant=tenant,
            code=code,
            name="Water base service",
            charge_type="recurring",
            amount_rule="flat",
            amount=amount,
            service=tenancy_models.Service.objects.get(code="water"),
            is_base=True,
            applies_to_customer_classes=classes,
        ),
    )


def _typed(account, code):
    """Point the account at ONE platform consumer category, by CODE.

    Never `AccountType.objects.first()`: the whole subject of this file is
    WHICH type the account carries, so a fixture that takes whichever row the
    database returned first would be testing nothing.
    """
    account.account_type = customer_models.AccountType.objects.get(code=code)
    account.save(update_fields=["account_type"])
    return account


def _cycle_over(tenant, unit_id, code):
    """A cycle holding this unit's service points, so `prepare_run` has scope."""
    cycle = metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        name=code,
        frequency="monthly",
        start_day=PERIOD_START.day,
        days_to_complete=CYCLE_DAYS,
    )
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(
        cycle=cycle
    )
    return cycle


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE FINDING
# ══════════════════════════════════════════════════════════════════════════


def test_the_uncovered_type_bills_zero_and_is_WARNED_not_silent(brazos, dana):
    """**THE DEFECT, REPRODUCED — AND ITS ANSWER AS OF 2026-09-30.**

    A water base charge exists and names `residential`; the account is
    `agricultural`. Before `DEF-2381` nothing happened at all — no refusal, no
    finding, and a bill that quietly lost its standing charge.

    ⚠ **SUPERSEDED 2026-09-30.** PO ruling of that day: *"if user did not
    define and bind base charges in rate schedule - then as a default you take 0
    and complete the bill instead of refusing - if you want to show the warning
    you can display it dueing the process"*. The decision log's reading names
    this exact case — *(c) no base code for this customer type*. So the account
    is no longer a named finding that stops the bill: it BILLS a `$0.00` base
    and carries `billing.oneTime.warn.baseNotSet`, which is how the process
    now says what `DEF-2381` made it say. The silence `DEF-2381` was filed for
    does not come back — the warning is the sentence.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, UNCOVERED)
        _base_code(brazos, [COVERED])

        data = _price_live(account)

    water = [c for c in data.tariffs if c.service == "water"][0]
    assert water.base_charge == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): the fixture account also
    # carries `noAgreements` — no service agreements on file, billed and WARNED
    # since `31358c239` (PO 2026-09-30 option C) — which names no service. It
    # is asserted beside the base warning, never instead of it.
    assert [(w["key"], w["params"].get("service_code")) for w in data.warnings] == [
        ("billing.oneTime.warn.noAgreements", None),
        ("billing.oneTime.warn.baseNotSet", "water"),
    ]


def test_the_sentence_names_the_type_and_the_service_the_way_the_PO_wrote_it(brazos, dana):
    """The PO's own words: *"this account's customer type is not covered by any
    charge for water"*. The two facts a clerk needs are the TYPE and the
    SERVICE, and both are in the sentence.

    ⚠ **AMENDED 2026-09-30 — THE SENTENCE IS NOW RATING'S, READ WHERE IT IS
    STILL SHOWN.** Billing no longer refuses on it (see the case above), but
    rating keeps it — flagged `not_set` — for its own configuration screens,
    which is where the repair is made. So it is asserted at its source.

    B14 rule 32 is asserted here too — no rule id and no internal code reaches
    this copy.
    """
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        _base_code(brazos, [COVERED])
        answer = rating_selectors.base_charge_from_charge_code(
            "water", customer_class=UNCOVERED, named_code="BASE-W"  # DEF-RAT-9832
        )

    assert answer["not_set"] is True
    assert answer["refusal_reason"] == "customer_class"
    sentence = answer["refusal"]
    assert UNCOVERED in sentence
    assert "water" in sentence
    # ⚠ The list of types that ARE covered left this sentence on 2026-09-24
    # (`DEF-CUS-6550`); asserted in the NEGATIVE so a lane putting it back goes
    # red and reads this note.
    assert COVERED not in sentence
    assert "Charge codes" in sentence
    for internal in ("BR-", "DEF-", "OQ-", "CR-", "GT-", "S9", "S11"):
        assert internal not in sentence, f"{internal} is an internal code (B14 rule 32)"


def test_the_run_bills_the_uncovered_account_and_carries_the_warning(brazos, dana):
    """**WHERE THE PO ASKED FOR IT — step 2** — and, from 2026-09-30, as a
    WARNING on a READY account rather than a blocked one.

    ⚠ **SUPERSEDED 2026-09-30.** PO ruling of that day: *"if user did not
    define and bind base charges in rate schedule - then as a default you take 0
    and complete the bill instead of refusing - if you want to show the warning
    you can display it dueing the process"*. The decision log's reading names
    this exact case — *(c) no base code for this customer type*. So the account
    is no longer a named finding that stops the bill: it BILLS a `$0.00` base
    and carries `billing.oneTime.warn.baseNotSet`, which is how the process
    now says what `DEF-2381` made it say. The silence `DEF-2381` was filed for
    does not come back — the warning is the sentence.

    ⚠ **THE SHIPPED DEFAULT IS LEFT ALONE HERE, DELIBERATELY.** `R3,R4` are
    served on every deployment since v2.115.0, so this is the run a utility
    actually gets — and the chain must agree on `$0.00` rather than reach for
    the retired schedule column.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, UNCOVERED)
        _base_code(brazos, [COVERED])
        cycle = _cycle_over(brazos, unit["id"], "DEF2381-BLOCKED")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert prepared.blocked == ()
    assert prepared.silent == (), "a misconfiguration is not a quiet correct state"
    assert [data.account_no for data in prepared.ready] == [account.account_no]
    # AMENDED 2026-10-01 (billing red triage): the fixture account also
    # carries `noAgreements` — no service agreements on file, billed and WARNED
    # since `31358c239` (PO 2026-09-30 option C) — which names no service. It
    # is asserted beside the base warning, never instead of it.
    assert [
        (w["key"], w["params"].get("service_code")) for w in prepared.ready[0].warnings
    ] == [
        ("billing.oneTime.warn.noAgreements", None),
        ("billing.oneTime.warn.baseNotSet", "water"),
    ]


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE BOUNDARY — the three configurations that must NOT move
# ══════════════════════════════════════════════════════════════════════════


def test_a_service_with_NO_base_charge_code_at_all_bills_zero_and_warns_too(
    brazos, dana, settings
):
    """⚠ **SUPERSEDED TWICE — 2026-09-28 (`DEF-BIL-7170`) and 2026-09-30.**

    This case was `…_still_bills` (the plan's own figure), then
    `…_REFUSES_SEPARATELY` (*"we will never take default value from plan $8.0 -
    that is retired"*). On 2026-09-30 the PO ruled a base nobody defined and
    bound bills `$0.00` and warns — case (a) of that day's reading. The 09-28
    half still holds: the figure is `$0.00`, never the plan's `$8.00`.

    **What is lost, and it is recorded rather than hidden:** `DEF-2381` kept
    this configuration and the uncovered-customer-type one on DIFFERENT
    reasons because they are repaired in different places. Both now reach the
    clerk as the same `baseNotSet` warning; rating's configuration screens
    still tell them apart by sentence.

    The chain is stated OFF here so that the LIVE path is what is proved; the
    case above proves the served chain agrees.
    """
    settings.BILLING_RESOLUTION_STEPS = ""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, UNCOVERED)
        # No charge code at all.
        data = _price_live(account)

    water = [c for c in data.tariffs if c.service == "water"][0]
    assert water.base_charge == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): the fixture account also
    # carries `noAgreements` — no service agreements on file, billed and WARNED
    # since `31358c239` (PO 2026-09-30 option C) — which names no service. It
    # is asserted beside the base warning, never instead of it.
    assert [(w["key"], w["params"].get("service_code")) for w in data.warnings] == [
        ("billing.oneTime.warn.noAgreements", None),
        ("billing.oneTime.warn.baseNotSet", "water"),
    ]


def test_a_covered_customer_type_still_bills_from_the_charge_code(brazos, dana):
    """The account's type IS on the list, so nothing changes and the code's own
    figure prices the bill — the source, not just the number."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, COVERED)
        _base_code(brazos, [COVERED])
        data = _price_live(account)

    water = [config for config in data.tariffs if config.service == "water"][0]
    assert water.base_charge == CODE_BASE


def test_a_charge_that_names_NO_classes_covers_every_type(brazos, dana):
    """BR-RAT-108: NULL or `[]` means EVERY class. The same `agricultural`
    account that is refused above bills here, from the same code, because the
    code claims nobody in particular."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, UNCOVERED)
        _base_code(brazos, [])
        data = _price_live(account)

    water = [config for config in data.tariffs if config.service == "water"][0]
    assert water.base_charge == CODE_BASE


def test_a_null_class_list_covers_every_type(brazos, dana):
    """The other spelling of the same fact — a row whose column is NULL rather
    than `[]`. Both reach `row.applies_to_customer_classes or []` and both must
    mean every class; asserting only one of them would leave half the rule
    untested."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, UNCOVERED)
        charge = _base_code(brazos, [])
        rating_models.Charge.objects.filter(pk=charge.id).update(
            applies_to_customer_classes=None
        )
        data = _price_live(account)

    water = [config for config in data.tariffs if config.service == "water"][0]
    assert water.base_charge == CODE_BASE


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE WIRING — the map, the retry button and the clerk's copy
# ══════════════════════════════════════════════════════════════════════════


def test_the_reason_is_mapped_to_the_tab_that_owns_the_repair():
    """BR-BIL-040. The repair is the charge code's customer-type list in Plans &
    Rates, which is stage 1's input — so the finding belongs on the Plans tab
    and never on Reads."""
    assert (
        runs.STAGE_BY_REASON[gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE]
        == "resolve-subscription"
    )


def test_retry_now_is_not_offered_for_a_repair_made_somewhere_else():
    """Nothing on the phase-3 screen edits a charge code, so "retry now" would
    be a button that always fails."""
    assert gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE in runs.NOT_RETRYABLE_HERE


def test_the_reason_has_copy_in_all_eleven_catalogues():
    """`BillRunWizard` renders `billing.run.reason.<code>`; a missing key puts a
    snake_case identifier in front of a clerk (DEF-518, and B14 rule 32)."""
    key = f"billing.run.reason.{gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE}"
    files = sorted(LOCALES.glob("*.json"))
    assert len(files) == 11, f"expected eleven catalogues, found {len(files)}"
    missing = [path.name for path in files if key not in json.loads(path.read_text("utf-8"))]
    assert not missing, f"{key} is missing from {missing}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@def2381 (sources: PO ruling 2026-09-02, the DEF-3282 review
#         — *"It should be a named finding on step 2: 'this account's customer type
#         is not covered by any charge for water'"* · 12-governance/10-defect-log.csv
#         DEF-2381 · 04-docs/05-modules/06-rating/02-business-rules.md BR-RAT-108 +
#         BR-RAT-088 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-015
#         + BR-BIL-040 + BR-BIL-055 + BR-BIL-1024/1025 ·
#         04-docs/02-decisions/14-ui-conventions.md rule 32)
# generated: 2026-09-02 by the DEF-2381 lane (claude)
# gates: every case below the boundary heading was run RED first, on real
#        PostgreSQL 16 (law 14) — the finding pair as
#        `Failed: DID NOT RAISE GatherProblem` and a run whose `blocked` and
#        `silent` were both empty while the account sat in `ready`.
# ──────────────────────────────────────────────────────────

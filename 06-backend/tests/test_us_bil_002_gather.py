# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 — the run assembles every input per account and
#           shows it BEFORE anything commits)   Screens: S31.2 · S31.3
# Rules:    BR-BIL-015 (a missing input is an EXCEPTION, never a silent skip) ·
#           BR-MET-040 (a plan is REQUIRED) · BR-RAT-030 (published plans only)
#           · BR-RAT-007/017 (price on the SERVICE DATE — 7-year
#           reproducibility) · BR-CUS-014 (the account derives its plan from
#           the unit) · B4.3 (calendar-day proration) · CLAUDE.md rule 2
# ───────────────────────────────────────────────────────
"""Gather: every way an account can fail to be billable, named rather than defaulted.

Almost every test here is a REFUSAL, and that is the shape of the thing. The
gather step's job is not to produce data — that part is easy — it is to refuse
to produce plausible data when the truth is missing. Each refusal carries a
reason code the exception screen groups on, because BR-BIL-015 makes every one
of these a decision a human takes.

The failure this file exists to prevent: an account with no plan, or a plan
with no tariffs, quietly producing a bill of $0.00 that issues, tells the
customer they owe nothing, and is never noticed.

`tc4` is the one to read: the SERVICE DATE picks the tariff version, and there
is no fallback to today's prices. A fallback would make every individual bill
look plausible and the set of them impossible to defend in an audit.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import gather
from apps.billing.contracts import ServiceReading

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)


def an_account(**overrides):
    """Customers' row shape, structurally — gather reads it by attribute and
    never imports the model (B1: cross-module reads go through seams)."""
    values = dict(
        id="acct-1",
        account_no="A-10432",
        unit_id="unit-1",
        status=SimpleNamespace(behavior_class="billable"),
        tax_exempt=False,
        opened_at=None,
        closed_at=None,
        # AMENDED 2026-10-01 (billing red triage): the row's KIND. Gather asks
        # customers which units a bill covers before anything else
        # (`covered_units`, BR-CUS-068), and that read branches on
        # `account.kind`. Every real account has one; a REGULAR account covers
        # its own unit only, which is what each case here always meant.
        kind="regular",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def _gather_without_a_database(monkeypatch, settings):
    """AMENDED 2026-10-01 (billing red triage) — this file has NO database by
    design (every seam is a stub), and two later reads reach for one.

    1. Since `18e1069f2` (2026-09-30, PO: a base nobody bound bills `$0.00`
       *"with a named warning"*) gather names the service in that warning
       through `tenancy_seam.service_names_by_code`. The catalogue answering
       nothing is the seam's OWN degraded answer — the warning then carries
       the service CODE — so nothing asserted here can move.
    2. Since R3 + R4 went live (`e998f92b1`, 2026-09-01) the happy path ends in
       `resolution_switch.apply`, the ruled R1–R7 chain, which reads metering
       and premises from the database. `SBH_BILLING_RESOLUTION_STEPS` is
       EMPTIED here — a STATED limit, on `test_br_bil_1048`'s precedent: what
       these cases assert (the readings carried, the service days owned, a
       re-rate swapping readings) is shaped by gather BEFORE the switch is
       called, and the switch substitutes prices, never readings or days. The
       chain itself is proved on real rows by `test_br_bil_870` and the
       `def_438` parity suite.
    """
    from apps.billing import tenancy_seam

    monkeypatch.setattr(tenancy_seam, "service_names_by_code", lambda *a, **k: {})
    settings.BILLING_RESOLUTION_STEPS = ""


def test_us_bil_002_tc1__an_account_with_no_unit_is_named_not_skipped():
    """BR-CUS-017 — an account is bound to exactly one unit.

    With no unit there is no plan and no service point, so there is nothing to
    bill. Skipping it silently loses a paying customer from the run.
    """
    with pytest.raises(gather.GatherProblem) as raised:
        gather.gather_account(
            account=an_account(unit_id=None),
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
        )
    assert raised.value.reason == gather.GATHER_NO_UNIT


def test_us_bil_002_tc2__a_planless_unit_is_an_exception_not_a_zero_bill(monkeypatch):
    """BR-MET-040 — a unit without a plan BLOCKS.

    THE FAILURE THIS PREVENTS: no plan means no tariffs, so a careless pipeline
    prices nothing, produces $0.00, issues it, and tells the customer they owe
    nothing. The utility finds out at the next audit.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver({"metering.unit_row": lambda _id: SimpleNamespace(rate_plan_id=None)}),
    )
    with pytest.raises(gather.GatherProblem) as raised:
        gather.gather_account(
            account=an_account(),
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
        )
    assert raised.value.reason == gather.GATHER_NO_PLAN


def test_us_bil_002_tc3__an_unpublished_plan_cannot_bill(monkeypatch):
    """BR-RAT-030 — a draft plan has no prices a bill could be produced from.

    `plan_ref` filters to published, so a draft resolves to None. Treating that
    as "no plan" rather than distinguishing it is deliberate: both are "you
    cannot bill this", and separating them would leak which plan ids exist.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(
            {
                "metering.unit_row": lambda _id: SimpleNamespace(
                    id="unit-1", rate_plan_id="plan-1"
                ),
                "rating.plan_ref": lambda _id: None,  # draft or archived
            }
        ),
    )
    with pytest.raises(gather.GatherProblem) as raised:
        gather.gather_account(
            account=an_account(),
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
        )
    assert raised.value.reason == gather.GATHER_PLAN_UNPUBLISHED


def test_us_bil_002_tc4__no_version_in_force_at_the_service_date_refuses(monkeypatch):
    """BR-RAT-007/017 — THE SEVEN-YEAR REPRODUCIBILITY PROMISE, as a refusal.

    A June bill prices on the version in force in JUNE, whether the run happens
    in July or in 2031. There is deliberately no fallback to today's prices,
    because a fallback re-prices history silently: every individual bill still
    looks plausible, and the set of them cannot be defended.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(
            {
                "metering.unit_row": lambda _id: SimpleNamespace(
                    id="unit-1", rate_plan_id="plan-1"
                ),
                "rating.plan_ref": lambda _id: {
                    "id": "plan-1",
                    "name": "Residential",
                    "version": 3,
                },
                "rating.plan_rate_schedules": lambda _id: [
                    {"service_code": "electric", "tariff": SimpleNamespace(id="t-1")}
                ],
                # Rating's own answer for "no version was in force then".
                "rating.pricing_inputs": lambda _t, _d: None,
            }
        ),
    )
    with pytest.raises(gather.GatherProblem) as raised:
        gather.gather_account(
            account=an_account(),
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
        )
    assert raised.value.reason == gather.GATHER_NO_VERSION
    assert raised.value.service_code == "electric"  # WHICH service, for the screen


def test_us_bil_002_tc5__a_plan_resolving_to_no_service_refuses(monkeypatch):
    """A bill with no services is not a $0.00 bill — it is a misconfiguration.

    The distinction matters because $0.00 issues silently and a refusal does
    not.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(
            {
                "metering.unit_row": lambda _id: SimpleNamespace(
                    id="unit-1", rate_plan_id="plan-1"
                ),
                "rating.plan_ref": lambda _id: {
                    "id": "plan-1",
                    "name": "Residential",
                    "version": 3,
                },
                "rating.plan_rate_schedules": lambda _id: [],
            }
        ),
    )
    with pytest.raises(gather.GatherProblem) as raised:
        gather.gather_account(
            account=an_account(),
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=30,
        )
    assert raised.value.reason == gather.GATHER_NO_TARIFF


def test_us_bil_002_tc6__the_happy_path_carries_everything_the_pipeline_needs(monkeypatch):
    """What a gathered account looks like when nothing is missing."""
    monkeypatch.setattr(gather, "_resolve", _resolver(_full_world()))

    data = gather.gather_account(
        account=an_account(),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=__import__("apps.billing.rating_seam", fromlist=["Quantity"]).Quantity(
                    amount=Decimal("684"), unit="kWh"
                ),
            ),
        ),
    )

    assert data.account_no == "A-10432"
    assert data.currency == "USD"  # rule 2 — the TENANT's, resolved not defaulted
    assert data.rate_plan_version == 3  # snapshot for the bill (BR-CUS-013)
    assert len(data.tariffs) == 1 and data.tariffs[0].service == "electric"
    assert data.tariffs[0].billed_unit == "kWh"  # rule 3 travels from the tariff
    assert data.cycle_days == 30 and data.service_days == 30
    # The document's frozen identity is captured HERE, at gather — not at issue,
    # where it would re-join a name that may have changed since (BR-BIL-030).
    assert data.snapshot["plan"]["version"] == 3
    assert data.snapshot["account_no"] == "A-10432"


def test_us_bil_002_tc7__a_mid_period_move_in_owns_fewer_service_days(monkeypatch):
    """B4.3 — moved in on the 12th: 19 of 30 days.

    Both numbers travel so the proration factor is derived ONCE downstream.
    Computing it here as well would give it two places to be wrong differently.
    """
    monkeypatch.setattr(gather, "_resolve", _resolver(_full_world()))

    data = gather.gather_account(
        account=an_account(opened_at=date(2026, 6, 12)),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
    )
    assert (data.cycle_days, data.service_days) == (30, 19)


def test_us_bil_002_tc8__a_re_rate_swaps_readings_and_keeps_everything_else(monkeypatch):
    """How the exception step's estimate reaches the pipeline.

    Re-GATHERING would re-read the customer record and could pick up a name
    changed since the clerk approved the run — so the readings are swapped on
    the data already held, and stages 2–6 replay over it. What the bill prints
    stays exactly as it was seen.
    """
    monkeypatch.setattr(gather, "_resolve", _resolver(_full_world()))
    quantity = __import__("apps.billing.rating_seam", fromlist=["Quantity"]).Quantity

    original = gather.gather_account(
        account=an_account(),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        readings=(ServiceReading(service_code="electric", absent_reason="no_read"),),
    )
    estimated = gather.with_readings(
        original,
        (
            ServiceReading(
                service_code="electric",
                consumption=quantity(amount=Decimal("618"), unit="kWh"),
                estimated=True,
            ),
        ),
    )

    assert original.readings[0].consumption is None  # untouched
    assert estimated.readings[0].estimated is True
    assert estimated.snapshot == original.snapshot  # the document did not move
    assert estimated.rate_plan_version == original.rate_plan_version


# ── test plumbing ───────────────────────────────────────────────────────────


def _resolver(published: dict):
    """Stand in for the seam resolver, publishing only what a test names.

    Anything NOT named resolves to None — which is exactly what a module that
    has not landed yet does, so a test cannot accidentally rely on a real
    module being importable.
    """

    def resolve(module, attribute, kind="selectors"):
        return published.get(f"{module}.{attribute}")

    return resolve


def _full_world():
    return {
        "metering.unit_row": lambda _id: SimpleNamespace(
            id="unit-1", label="Unit A", rate_plan_id="plan-1"
        ),
        "rating.plan_ref": lambda _id: {"id": "plan-1", "name": "Residential", "version": 3},
        "rating.plan_rate_schedules": lambda _id: [
            {"service_code": "electric", "tariff": SimpleNamespace(id="t-1")}
        ],
        # `pricing_inputs` — rating's ENGINE shape, not its storage shape. The
        # earlier fake published `version_structure`, which is the S9 card's
        # display preview and could never have priced a bill; the fake agreed
        # with the code and both were wrong. The real-selector proof is
        # tests/test_us_rat_002_plan_seams.py::tc10, which drives this same
        # path against real rows and fails if either half drifts.
        "rating.pricing_inputs": lambda _t, _d: {
            "version_id": "v-1",
            "model": "flat",
            "billed_unit": "kWh",
            "base_charge": "18.50",
            "minimum_bill": None,
            "currency": "USD",
            "unit_price": "0.12",
            "tiers": [],
        },
        "rating.plan_tax_rules": lambda _p, _d, **_ctx: [{"code": "STATE+LOCAL", "rate": "0.0825"}],
        "tenancy.regional_settings": lambda: {"currency": "USD"},
        "customers.primary_contact_name": lambda _a: "Sarah Chen",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · NO django_db marker — the gather step reads through
#         SEAMS, so its tests publish a fake resolver and touch no database.
#         The real-selector half is tests/test_us_rat_002_plan_seams.py::tc10
#         (added 2026-08-11), which drives this same path against real rows;
#         red-proved by blanking `billed_unit` in rating's pricing_inputs
# exceptions: the seam resolver is STUBBED here, so what is proved is the
#         gather's LOGIC and its refusals. A FAKE AGREEING WITH THE CODE PROVES
#         NOTHING: the first cut of this file published `version_structure`,
#         which is rating's display preview, and the gather read it — fake and
#         code matched and no bill could ever have priced. That is why tc10
#         exists and why this file must never be the only proof of a seam
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── DEF-465 · a service-scoped tax must narrow its BASE, not just attach ────


def test_def_465__applies_to_services_crosses_the_seam_into_the_engine(monkeypatch):
    """The one hop that was missing, asserted where it was missing.

    `rating_seam.TaxRule.applies_to_services` has existed since the seam was
    written and `compute_tax._base_for` has always read it. `_taxes_for` built
    the rule from four fields and never carried the fifth, so the engine read
    the default `()` as **no restriction** and charged a service-scoped percent
    tax on the whole bill.

    ⚠ **THIS IS WHY THE §A4 SCENARIO TESTS DID NOT CATCH IT.** They construct
    `TaxRule`s by hand and drive `rating_seam.price_bill`, so they exercise the
    engine's side of the seam and never the adapter's — and they assert `$1.82`,
    the correct figure, while production computed `$2.83`. A test on the far
    side of a broken hop passes forever.

    Silver Creek's City Franchise Fee is **1.50% of [electric, gas]**.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(
            {
                "rating.plan_tax_rules": lambda *_a, **_k: [
                    {
                        "code": "City Franchise",
                        "rate": "0.015",
                        "flat_amount": None,
                        "jurisdiction_id": "j-city",
                        "tax_id": "TAX-CITY",
                        "applies_to_services": ["electric", "gas"],
                    }
                ]
            }
        ),
    )
    rules = gather._taxes_for("plan-1", SERVICE_DATE)
    assert len(rules) == 1
    assert rules[0].applies_to_services == ("electric", "gas")


def test_def_465__an_unscoped_tax_still_means_EVERY_service(monkeypatch):
    """The stored convention, and what makes this fix safe for every tenant.

    `applies_to_services` NULL or `[]` means NO RESTRICTION — so a tax that
    names nothing keeps taxing the whole bill exactly as it did before. Only a
    tax that NAMES services moves, and it moves to the design's own figure.
    Without this, the fix would silently un-tax every existing bill.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver(
            {
                "rating.plan_tax_rules": lambda *_a, **_k: [
                    {"code": "State", "rate": "0.0625", "tax_id": "TAX-TX"},
                    {"code": "County", "rate": "0.02", "applies_to_services": []},
                ]
            }
        ),
    )
    rules = gather._taxes_for("plan-1", SERVICE_DATE)
    # An ABSENT key and an EMPTY list both mean every service — the first is a
    # rating lane that has not landed, the second is a tax with no restriction,
    # and the engine treats both the same way on purpose.
    assert [r.applies_to_services for r in rules] == [(), ()]


def test_def_465__a_row_shape_without_the_field_degrades_rather_than_raising(monkeypatch):
    """`.get` with a `()` fallback, like every field beside it.

    Rating's row shape is another module's contract. A deployment where that
    lane has not landed must degrade to TODAY's behaviour — the whole bill —
    rather than raise a KeyError in the middle of a 500-account run.
    """
    monkeypatch.setattr(
        gather,
        "_resolve",
        _resolver({"rating.plan_tax_rules": lambda *_a, **_k: [{"code": "Old", "rate": "0.01"}]}),
    )
    assert gather._taxes_for("plan-1", SERVICE_DATE)[0].applies_to_services == ()


# ── BR-RAT-101 · the premises jurisdiction flag reaches the bill run ───────


def _a_premises(**overrides):
    values = dict(city="San Antonio", state="TX", postal_code="78205")
    values.update(overrides)
    return SimpleNamespace(**values)


def test_br_rat_101__the_inside_city_flag_travels_from_the_premises():
    """PO ruling 2026-08-21: *"On premises we will add this flag and during
    billing we will consider Account -> Unit -> Premises to consider it."*

    The path already existed — `gather` reaches the premises through the unit
    for tax scoping — so the ruling only had to put a column at the end of it.
    """
    unit = SimpleNamespace(premises=_a_premises(inside_city_limits=True))
    assert gather._premises_geography(unit)["inside_city_limits"] is True
    outside = SimpleNamespace(premises=_a_premises(inside_city_limits=False))
    assert gather._premises_geography(outside)["inside_city_limits"] is False


def test_br_rat_101__an_UNRECORDED_flag_travels_as_ABSENT_never_as_false():
    """⚠ THE ONE THAT MATTERS. `None` means NOBODY RECORDED IT — a third state,
    not `False`.

    A premises whose flag nobody set must travel WITHOUT the key, so the tax
    does not apply: DEF-273's ruled direction is never to charge an
    inside-city-only fee on a guess. `bool(flag)` without the `is not None`
    test would turn every unrecorded premises into an OUTSIDE-city one and
    start charging on data nobody entered.
    """
    unit = SimpleNamespace(premises=_a_premises(inside_city_limits=None))
    facts = gather._premises_geography(unit)
    assert "inside_city_limits" not in facts
    # The geography it DOES carry still travels — this is a missing flag, not a
    # missing premises.
    assert facts["city"] == "San Antonio"


def test_br_rat_101__a_deployment_without_the_migration_degrades_rather_than_raising():
    """`getattr` stays. `unit.premises` is reached across a module boundary, and
    a deployment where metering's migration has not run must fall back to the
    recorded city name rather than raise inside a 500-account run."""
    legacy = SimpleNamespace(premises=SimpleNamespace(city="Austin", state="TX", postal_code="78701"))
    facts = gather._premises_geography(legacy)
    assert "inside_city_limits" not in facts
    assert facts["city"] == "Austin"


def test_br_rat_101__no_premises_at_all_still_yields_nothing():
    """Unchanged, and asserted so the new key cannot resurrect a fact from an
    account that has no premises to have one."""
    assert gather._premises_geography(SimpleNamespace(premises=None)) == {}

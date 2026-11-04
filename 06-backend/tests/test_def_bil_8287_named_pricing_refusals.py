"""DEF-BIL-8287 / DEF-BIL-8288 / DEF-BIL-8329 — a one-time bill's refusal names its cause.

PO report on deployed 2.412.3 (Ottumwa Water Works, AC-2026-00057): an INTERIM
bill for Aug 1–31 was refused at step 1 with *"Water can't be priced. Check its
rates."* — `billing.oneTime.err.notPriced`, the generic per-service fallback
`one_time_answer.pricing_refusal` used whenever the engine's gap carried no
`message_key`. The engine's real reason travelled only in `params.detail`, which
is never rendered (BR-SHL-020 r2). DEF-BIL-8288 is the same fault one branch
over: a FIRST bill refused with the no-service fallback `billing.oneTime.refused`
(*"This one-time bill can't be created as asked …"*).

PO ruling 2026-09-30: *"we have to show the warning or error to user -
specific"*. So:

  * every reason the pricing path can refuse with has its OWN key, carrying the
    fact it is about (the service, the date, the size) as `message_params`;
  * where no key can name it, the ENGINE's own sentence is shown, cleaned of ids
    and rule codes — never either generic line;
  * a first bill whose To is not after its move-in date is refused ON THE FIELD
    at step 1, before any pricing;
  * the account card serves the cycle's NAME (DEF-BIL-8329 — the Cycle cell
    printed the cycle's days to pay).

Written RED FIRST (hard-won law 7); the failures are quoted in the lane report.

⚠ PostgreSQL: none of these paths catches a database error and continues, so
law 14 does not bind them; they are proved on the default sqlite harness.
"""

from __future__ import annotations

import re
import ast
import json
import pathlib
from datetime import date

import pytest

from apps.billing import api as billing_api
from apps.billing import one_time_answer
from apps.billing.exceptions import BillingRuleError
from apps.rating import models as rating_models
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _interim_body, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

GENERIC = {"billing.oneTime.err.notPriced", "billing.oneTime.refused", "billing.run.refused"}

BILLING = pathlib.Path(__file__).resolve().parents[1] / "apps" / "billing"
LOCALES = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
LANGS = ("en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR")


# ══════════════════════════════════════════════════════════════════════════
# THE GUARD — every reason that can reach `pricing_refusal` has its own key
# ══════════════════════════════════════════════════════════════════════════



@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch, request):
    """`BR-BIL-1066` (PO 2026-10-01) — an interim bill for an account on no
    billing cycle is now REFUSED (*"No billing cycle. Assign one on the
    account."*). This file's interim cases are about something else, so their
    unit is put on a cycle through the same metering seam the card and the
    refusal read. Only the cycle's NAME is given, not its calendar, so the
    denominator falls back to the window's own length and no figure here moves.
    """
    if "8329" in request.node.name:
        return  # that case is ABOUT a unit on no cycle
    from apps.metering import selectors as _metering_selectors

    monkeypatch.setattr(
        _metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


def _gather_problem_reasons() -> dict[str, list[str]]:
    """Every reason a `GatherProblem` is raised with anywhere in billing, as its
    string VALUE, with the sites that raise it. Read from the source, so a new
    raise site is counted the day it is written."""
    import importlib

    found: dict[str, list[str]] = {}
    unresolved: list[str] = []
    ruled_path_sites: list[str] = []
    for path in sorted(BILLING.rglob("*.py")):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module_name = "apps.billing." + ".".join(path.relative_to(BILLING).with_suffix("").parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "GatherProblem":
                continue
            arg = node.args[0]
            site = f"{path.name}:{node.lineno}"
            # ── `DEF-BIL-8807` · `getattr(refusal, "reason", None) or <CONSTANT>`
            # `gather`'s ruled-path refusal takes its reason at RUNTIME since
            # changes row 44 (bd94c047e, 2026-10-01): the refusal's own reason
            # when it carries one, else the named constant. The constant is the
            # FALLBACK and is counted like any other; the runtime half is every
            # `RuledPathRefused(..., reason=...)` in `resolution_switch`, which
            # `_ruled_path_runtime_reasons` counts and pins below. Any other
            # shape of `or` stays unresolved, and the assertion still fires.
            if (
                isinstance(arg, ast.BoolOp)
                and isinstance(arg.op, ast.Or)
                and len(arg.values) == 2
                and isinstance(arg.values[0], ast.Call)
                and getattr(arg.values[0].func, "id", None) == "getattr"
                and len(arg.values[0].args) >= 2
                and isinstance(arg.values[0].args[1], ast.Constant)
                and arg.values[0].args[1].value == "reason"
                and isinstance(arg.values[1], ast.Name)
            ):
                value = getattr(importlib.import_module(module_name), arg.values[1].id, None)
                if isinstance(value, str):
                    found.setdefault(value, []).append(site)
                    ruled_path_sites.append(site)
                    continue
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.setdefault(arg.value, []).append(site)
                continue
            if isinstance(arg, ast.Name):
                owner, attr = importlib.import_module(module_name), arg.id
            elif isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                owner, attr = importlib.import_module(f"apps.billing.{arg.value.id}"), arg.attr
            else:
                unresolved.append(site)
                continue
            value = getattr(owner, attr, None)
            if isinstance(value, str):
                found.setdefault(value, []).append(site)
            else:
                unresolved.append(f"{site} ({attr})")
    # `gather._base_charge_for` raises with a LOCAL `reason` that is one of three
    # constants — all three are counted explicitly, and nothing else may be local.
    # Matched by FILE and variable, never by line number: the line moved once
    # already (479 -> 480 when B27's batch reads landed, 6d6d58fab), and a
    # pinned line turns an unrelated edit to gather.py into a red here.
    assert len(unresolved) == 1 and re.fullmatch(r"gather\.py:\d+ \(reason\)", unresolved[0]), unresolved
    from apps.billing import gather

    # `DEF-BIL-9024` — and since 2.436.11 the unsized-meter stop as well.
    for value in (
        gather.GATHER_NO_TARIFF,
        gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE,
        gather.GATHER_SIZE_UNRESOLVED,
    ):
        found.setdefault(value, []).append(unresolved[0].split(" ")[0])
    # The one runtime-reason site, and what its runtime half can carry.
    assert len(ruled_path_sites) == 1 and ruled_path_sites[0].startswith("gather.py:"), (
        ruled_path_sites
    )
    check_only, any_caller = _ruled_path_runtime_reasons()
    assert check_only == RULED_PATH_CHECK_PASS_ONLY, (
        "a RuledPathRefused carries a reason this census has not classified: a "
        "reason a one-time bill can receive needs a PRICING_REFUSAL_KEYS entry"
    )
    # `DEF-BIL-8851` — a reason the ruled path raises OUTSIDE a Check pass can
    # reach a one-time bill, so it is counted like every other reason and the
    # guard below demands its key (today: the asset count nobody could read).
    for value, sites in any_caller.items():
        found.setdefault(value, []).extend(sites)
    return found


#: `DEF-BIL-8807` — the reasons a `RuledPathRefused` may carry, and why none of
#: them needs a one-time key: each is raised only inside a bulk run's Check pass
#: (`runs.in_check_pass()`), which `check_engine` alone opens. `runs.py`, of
#: that context: *"every other caller (single, first, one-time, back-bill)
#: keeps the adapter's refusal"* — i.e. `GATHER_RULED_PATH_REFUSED`, which is
#: counted above and has its key. A NEW reason here goes red until it is
#: either classified as check-pass-only or given a one-time key.
RULED_PATH_CHECK_PASS_ONLY = frozenset({"meter_has_no_multiplier"})


def _ruled_path_runtime_reasons() -> tuple[frozenset[str], dict[str, list[str]]]:
    """Every `reason=` handed to `RuledPathRefused` in `resolution_switch`, as
    its string value, split by whether it sits under an `in_check` condition:
    `(check_only, {reason: [sites]} for every other caller)`."""
    import importlib

    path = BILLING / "resolution_switch.py"
    module = importlib.import_module("apps.billing.resolution_switch")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    reasons: set[str] = set()
    any_caller: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "RuledPathRefused"):
            continue
        for kw in node.keywords:
            if kw.arg != "reason" or (isinstance(kw.value, ast.Constant) and kw.value.value is None):
                continue
            if isinstance(kw.value, ast.Attribute) and isinstance(kw.value.value, ast.Name):
                # `runs` is imported INSIDE the raising function, so it is not a
                # module attribute; resolve it as the billing module it names.
                owner = getattr(module, kw.value.value.id, None) or importlib.import_module(
                    f"apps.billing.{kw.value.value.id}"
                )
                value = getattr(owner, kw.value.attr)
            else:
                value = f"<unresolved {ast.unparse(kw.value)}>"
            ancestor, guarded = parents.get(node), False
            while ancestor is not None and not guarded:
                guarded = isinstance(ancestor, ast.If) and "in_check" in ast.unparse(ancestor.test)
                ancestor = parents.get(ancestor)
            if guarded:
                reasons.add(value)
            else:
                any_caller.setdefault(value, []).append(f"resolution_switch.py:{node.lineno}")
    return frozenset(reasons), any_caller


def test_def_bil_8287__every_pricing_refusal_reason_has_its_own_key():
    """THE GUARD. A reason with no entry reaches the clerk as a generic line —
    which is the defect. The scan found 40 reasons on 2026-09-30; the number is
    printed so a scan that silently finds fewer is visible (law 7)."""
    reasons = _gather_problem_reasons()
    reasons.update(
        {
            reason: ["one_time._clerk_gap fallback"]
            for reason in one_time_answer.ENGINE_SENTENCE_REASONS
        }
    )
    missing = {
        reason: sites
        for reason, sites in reasons.items()
        if reason not in one_time_answer.PRICING_REFUSAL_KEYS
        and reason not in one_time_answer.ENGINE_SENTENCE_REASONS
    }
    assert len(reasons) >= 40, f"the scan found only {len(reasons)} reasons"
    assert missing == {}, f"{len(missing)} of {len(reasons)} reasons have no clerk key: {missing}"


@pytest.mark.django_db
def test_def_bil_8287__no_reason_falls_back_to_a_generic_line():
    reasons = set(_gather_problem_reasons()) | set(one_time_answer.ENGINE_SENTENCE_REASONS)
    for reason in sorted(reasons):
        for service_code in ("water", None):
            refusal = one_time_answer.pricing_refusal(
                {
                    "reason": reason,
                    "service_code": service_code,
                    "detail": "service water: something the engine said on 2026-08-31.",
                }
            )
            assert refusal.message_key not in GENERIC, (reason, service_code)
            assert refusal.message_key.startswith("billing.oneTime.err."), refusal.message_key


def test_def_bil_8287__every_new_key_is_in_all_eleven_catalogues():
    keys = set(one_time_answer.PRICING_REFUSAL_KEYS.values()) | set(one_time_answer.CLASSIFIED_KEYS)
    keys |= {one_time_answer.ENGINE_SENTENCE_KEY, "billing.oneTime.err.toNotAfterMoveIn"}
    for lang in LANGS:
        catalogue = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
        absent = sorted(key for key in keys if key not in catalogue)
        assert absent == [], f"{lang}: {absent}"


def test_def_bil_8287__the_engine_sentence_is_cleaned_of_ids_and_rule_codes():
    raw = (
        "rating refused to price this bill (water): tiered tariff for service 'water' "
        "has no tiers (BR-RAT-032). Nothing is guessed."
    )
    assert one_time_answer.engine_sentence(raw) == "Tiered tariff for service 'water' has no tiers."
    uuid_raw = "plan 01a0f3a3-97e7-7cb3-a883-2fccb31d0446 resolves to no tariff. BR-RAT-007: no."
    cleaned = one_time_answer.engine_sentence(uuid_raw)
    assert "01a0" not in cleaned and "BR-" not in cleaned, cleaned


def test_def_bil_8831__a_second_sentence_opening_with_a_rule_code_is_not_glued_on():
    """`DEF-BIL-8831` (CR-157-BRC10 wave C walk): the engine's time-of-use and
    demand refusals start their SECOND sentence with a rule code. Stripping the
    code before choosing the first sentence glued the rest on — *"arrived.'s
    measurement is a MAX-DEMAND REGISTER READ"*. These are the two refusals as
    the walk received them on a plain kWh meter."""
    tou = (
        "rating refused to price this bill (electric, trash, water, water, sewer): service "
        "'electric' prices on time of use (Off-peak, On-peak) and NO per-window quantity "
        "arrived. BR-RAT-021: reads arrive pre-split per window. Nothing here divides a total "
        "across windows."
    )
    demand = (
        "rating refused to price this bill (electric): service 'electric' bills a demand charge "
        "at 11.000000 per kW and no peak-demand read arrived. BR-RAT-014's measurement is a "
        "MAX-DEMAND REGISTER READ; an absent register is unread, not a month without a peak."
    )
    assert one_time_answer.engine_sentence(tou) == (
        "Service 'electric' prices on time of use (Off-peak, On-peak) and NO per-window "
        "quantity arrived."
    )
    assert one_time_answer.engine_sentence(demand) == (
        "Service 'electric' bills a demand charge at 11.000000 per kW and no peak-demand "
        "read arrived."
    )


def test_def_bil_8288__a_bare_rule_refusal_shows_the_engines_sentence_not_the_generic_one():
    refusal = billing_api._one_time_refusal(
        BillingRuleError(
            "account AC-1 names no consumer category, so the deposit rule for its first "
            "bill cannot be resolved (BR-RAT-020/023).",
            br_ref="BR-BIL-012",
        )
    )
    assert refusal.message_key == one_time_answer.ENGINE_SENTENCE_KEY
    assert refusal.params["sentence"].startswith("Account AC-1 names no consumer category")
    assert "BR-" not in refusal.params["sentence"]


# ══════════════════════════════════════════════════════════════════════════
# REPRODUCED — each realistic cause, on real rows, through the route
# ══════════════════════════════════════════════════════════════════════════


def _refused(brazos, dana, mutate, **account_kw):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan, **account_kw)
        mutate(brazos, plan, asset)
    response = _post(billing_api.one_time_preview, brazos, user, _interim_body(account))
    assert response.status_code == 422, response.data
    return response.data["message_key"], response.data.get("params") or {}


@pytest.mark.django_db
def test_def_bil_8287__no_rate_in_force_on_the_period_end_names_the_service_and_the_date(
    brazos, dana
):
    """THE PO'S CASE. The water schedule's only version starts AFTER the period
    ends — the refusal that produced exactly *"Water can't be priced"*."""

    def later(tenant, _plan, _asset):
        rating_models.TariffVersion.objects.filter(tenant=tenant).update(
            effective_from=date(2026, 9, 1)
        )

    key, params = _refused(brazos, dana, later)
    assert key == "billing.oneTime.err.noRateOnDate"
    assert params["service"] == "Water"
    assert params["date"] == "Jul 31, 2026"


@pytest.mark.django_db
def test_def_bil_8287__a_rate_that_ended_before_the_period_end_is_the_same_refusal(brazos, dana):
    def ended(tenant, _plan, _asset):
        rating_models.TariffVersion.objects.filter(tenant=tenant).update(
            effective_to=date(2026, 6, 30)
        )

    key, params = _refused(brazos, dana, ended)
    assert key == "billing.oneTime.err.noRateOnDate"
    assert params["date"] == "Jul 31, 2026"


@pytest.mark.django_db
def test_def_bil_8287__a_size_the_schedule_does_not_price_is_named(brazos, dana):
    def unpriced(tenant, _plan, _asset):
        rating_models.RateSizeRow.objects.filter(tenant=tenant, size_class="W-8").delete()

    key, params = _refused(brazos, dana, unpriced, size_class="W-8")
    assert key == "billing.oneTime.err.sizeNotPriced"
    assert params["size"] == "W-8" and params["service"] == "Water"


def _base_priced_by_size(tenant, _plan, _asset):
    """`DEF-BIL-9023` — give the water base code a SECOND price that depends on
    the size, so its base is no longer one price for every size. Since
    `DEF-RAT-8822` (PO 2026-10-01, option A: *"Hold back only where the price
    depends on the size"*) that is the only base an unsized meter is held on."""
    from decimal import Decimal

    from apps.rating import charge_prices
    from apps.rating.constants import PRICE_HISTORY_EPOCH
    from apps.tenancy import service_size_classes

    charge = rating_models.Charge.objects.get(tenant=tenant, is_base=True, service__code="water")
    # ONE basis per code (CR-013 part 2): the all-sizes price is REPLACED by a
    # per-size table, never stated beside it - 5/8" at the same $8.00, the
    # largest size at $34.00.
    sizes = [code for code, _name in service_size_classes.size_classes_for_service("water")]
    target = {(sizes[0], None): Decimal("8.00"), (sizes[-1], None): Decimal("34.00")}
    charge_prices.save_prices(charge, target, effective_from=PRICE_HISTORY_EPOCH, effective_to=None)


@pytest.mark.django_db
def test_def_bil_8287__a_meter_with_no_size_is_named(brazos, dana):
    # ⚠ `DEF-BIL-9023` — the base must DIFFER by size for the refusal to be
    # owed; on the fixture's one-price base the bill now goes out (next case).
    key, params = _refused(brazos, dana, _base_priced_by_size, size_class=None)
    assert key == "billing.oneTime.err.noSize"
    assert params["service"] == "Water"


@pytest.mark.django_db
def test_def_bil_8287__an_unsized_meter_on_a_one_price_base_is_not_refused_for_its_size(
    brazos, dana
):
    """`DEF-RAT-8822`'s other half, so the case above cannot pass by refusing
    everything: on a base that is one price for every size the preview is not
    refused, and never for a missing size."""
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan, size_class=None)
    response = _post(billing_api.one_time_preview, brazos, user, _interim_body(account))
    assert response.status_code == 200, response.data


@pytest.mark.django_db
def test_def_bil_8287__a_reading_unit_the_rate_does_not_bill_in_is_named(brazos, dana):
    def kwh(tenant, _plan, _asset):
        rating_models.TariffVersion.objects.filter(tenant=tenant).update(uom="kWh")

    key, params = _refused(brazos, dana, kwh)
    assert key == "billing.oneTime.err.unitMismatch"
    assert params["read_unit"] == "kgal" and params["rate_unit"] == "kWh"


@pytest.mark.django_db
def test_def_bil_8287__a_plan_with_no_schedule_for_water_is_named(brazos, dana):
    def unbound(_tenant, plan, _asset):
        rating_models.PlanRateSchedule.objects.filter(rate_plan_id=plan.id).delete()

    key, _params = _refused(brazos, dana, unbound)
    assert key == "billing.oneTime.err.nothingPriced"


@pytest.mark.django_db
def test_def_bil_8287__a_draft_plan_is_named(brazos, dana):
    def draft(_tenant, plan, _asset):
        rating_models.RatePlan.objects.filter(pk=plan.id).update(status="draft")

    key, _params = _refused(brazos, dana, draft)
    assert key == "billing.oneTime.err.planDraft"


@pytest.mark.django_db
def test_def_bil_8287__a_tiered_rate_with_no_tiers_is_named(brazos, dana):
    def bare(tenant, _plan, _asset):
        rating_models.RateTier.objects.filter(tenant=tenant).delete()

    key, params = _refused(brazos, dana, bare)
    assert key == "billing.oneTime.err.noTiers"
    assert params["service"] == "Water"


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8288 — To after move-in, on its field · DEF-BIL-8329 — the cycle
# ══════════════════════════════════════════════════════════════════════════


def test_def_bil_8288__a_first_bill_whose_to_is_not_after_move_in_is_refused_on_its_field():
    base = {
        "account_id": "x",
        "kind": "first",
        "bill_date": "2026-09-30",
        "due_days": 21,
    }
    same = one_time_answer.problems_in(
        {**base, "period_start": "2026-07-01", "period_end": "2026-07-01"}
    )
    assert [(p["field"], p["message_key"]) for p in same] == [
        ("period_end", "billing.oneTime.err.toNotAfterMoveIn")
    ]
    later = one_time_answer.problems_in(
        {**base, "period_start": "2026-07-01", "period_end": "2026-07-02"}
    )
    assert later == []
    # An interim bill of one day is lawful and unchanged.
    interim = one_time_answer.problems_in(
        {**base, "kind": "interim", "period_start": "2026-07-01", "period_end": "2026-07-01"}
    )
    assert interim == []


@pytest.mark.django_db
def test_def_bil_8329__the_account_card_serves_the_cycles_name_or_none(brazos, dana):
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        card = one_time_answer.account_facts(str(account.id))
    assert "cycle_name" in card
    assert card["cycle_name"] is None, "this fixture's unit is on no cycle"

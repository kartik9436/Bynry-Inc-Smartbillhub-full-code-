# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-RAT-9797 (#27 a rate schedule names exactly one base code) ·
#           DEF-RAT-9798 (#28 an every-class and a one-class base code coexist) ·
#           DEF-RAT-9799 (#29 the clash is asked before the save) ·
#           DEF-RAT-9800 (#30 "One per service." → one per class)
# Rulings:  PO 2026-10-06, decision log "PO RULINGS — BASE CHARGES…" (A (a), B (a))
# Rules:    BR-RAT-088 / BR-RAT-1025 as amended 2026-10-06
# ───────────────────────────────────────────────────────
"""The figures put to the PO, asserted so drift goes RED.

* Water has W-ALL $8.00 (every class) and W-COM $15.00 (Commercial): both save.
  A second Commercial water base code is refused; a second every-class one too.
* The Commercial schedule names W-COM, so a commercial account pays $15.00; the
  residential schedule names W-ALL, so a residential account pays $8.00.
* Ann Arbor's case: a Residential solar base at $10.00 saves beside every-class
  BASE-SOL.
* A schedule that activates with no base code named, while its service has
  one, is refused ("Choose a base charge code."); a live schedule that already
  names none keeps billing and is listed for a System Admin.
* B (a): a base-code change is a new schedule version from a date, and a bill
  straddling the date splits by days — WP-1 up to it, WP-2 after.
"""


from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from core import errors
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures (env)
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _class_codes():
    from apps.customers import models as customer_models

    codes = {row.code for row in customer_models.AccountType.objects.all()}
    assert {"residential", "commercial"} <= codes, codes
    return "residential", "commercial"


def _base(env, code, amount, *, service="water", classes=None):
    with tenant_ctx(env.tenant):
        return services.create_charge(
            env.admin,
            {
                "code": code,
                "name": f"{code} base",
                "service": service,
                "charge_type": "recurring",
                "amount_rule": "flat",
                "amount": amount,
                "is_base": True,
                "effective_from": "2000-01-01",
                **({"applies_to_customer_classes": classes} if classes else {}),
            },
        )


# ── #28 · A (a) — an every-class and a one-class base code coexist ─────────
def test_w_all_and_w_com_both_save_and_so_does_a_second_commercial(env):
    """⚠ AMENDED 2026-10-09 (`DEF-RAT-10026`, PO ruling *"yes please do it"*): a
    service may now hold two or more base codes for the same customer class, so
    the refusals this asserted are gone; the rate schedule names which one bills.
    Until then a second Commercial code and a second every-class code were
    refused naming W-COM and W-ALL."""
    residential, commercial = _class_codes()
    env.enable("water")
    _base(env, "W-ALL", "8.00")
    _base(env, "W-COM", "15.00", classes=[commercial])  # saves beside W-ALL
    assert _base(env, "W-COM2", "16.00", classes=[commercial])["code"] == "W-COM2"
    assert _base(env, "W-ALL2", "9.00")["code"] == "W-ALL2"


def test_ann_arbor_residential_solar_at_10_saves_beside_every_class_base_sol(env):
    residential, _ = _class_codes()
    env.enable("solar")
    _base(env, "BASE-SOL", "5.00", service="solar")
    row = _base(env, "BASE-SOL-RES", "10.00", service="solar", classes=[residential])
    assert row["code"] == "BASE-SOL-RES"


# ── #29 — the step-1 probe (`GET /charges/base-clash`) was RETIRED 2026-10-09
# with the refusal it mirrored (`DEF-RAT-10026`); its absence is asserted in
# `test_def_rat_10026_two_base_codes_one_class.py`.


def _request(env, path, **params):
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get(path, params)
    force_authenticate(request, user=env.owner)
    request.tenant_role = "system_admin"
    request.tenant_id = env.tenant.id
    return request


def test_the_list_is_served(env):
    from apps.rating import api as rating_api

    residential, commercial = _class_codes()
    env.enable("water")
    _base(env, "W-ALL", "8.00")
    _base(env, "W-COM", "15.00", classes=[commercial])
    _activate(env, "Legacy water", seeded=True)
    with tenant_ctx(env.tenant):
        listed = rating_api.rate_schedules_base_to_choose(
            _request(env, "/api/t/rate-schedules/base-to-choose")
        ).data
    assert listed["count"] == 1
    assert [row["name"] for row in listed["results"]] == ["Legacy water"]


# ── #27 — a rate schedule names exactly one base code ──────────────────────
def _activate(env, name, *, base_code=None, seeded=False):
    payload = {
        "name": name,
        "service": "water",
        "model": "flat",
        "uom": "kgal",
        "effective_from": "2026-08-01",
        "structure": {"unit_price": "2.90"},
    }
    if base_code is not None:
        payload["base_charge_code"] = str(base_code)
    with tenant_ctx(env.tenant):
        if seeded:
            with services.seeding_schedules_without_a_named_base():
                return services.create_rate_schedule(env.admin, payload)
        return services.create_rate_schedule(env.admin, payload)


def test_activating_a_schedule_naming_no_base_code_is_refused_when_two_could_serve(env):
    """W-ALL $8.00 and W-COM $15.00 both reach an every-class water schedule:
    which one the bill reads is a person's choice, so the save refuses."""
    _, commercial = _class_codes()
    env.enable("water")
    _base(env, "W-ALL", "8.00")
    _base(env, "W-COM", "15.00", classes=[commercial])
    with pytest.raises(errors.ValidationError) as refused:
        _activate(env, "Res water")
    assert refused.value.message_key == "rating.schedules.base_charge_code_required"
    assert [fe["field"] for fe in refused.value.field_errors] == ["base_charge_code"]
    with tenant_ctx(env.tenant):
        assert not models.Tariff.objects.filter(tenant=env.tenant, name="Res water").exists()


def test_the_only_code_that_could_serve_is_named_on_the_version(env):
    """Water with only W-ALL: nothing to choose, so the version NAMES W-ALL and
    the schedule leaves the pooled fallback for good. Same $8.00 either way."""
    env.enable("water")
    w_all = _base(env, "W-ALL", "8.00")
    created = _activate(env, "Only water")
    with tenant_ctx(env.tenant):
        version = selectors.latest_version(models.Tariff.objects.get(pk=created["id"]))
    assert str(version.base_charge_code_id) == w_all["id"]


def test_a_draft_is_not_refused(env):
    env.enable("water")
    _base(env, "W-ALL", "8.00")
    with tenant_ctx(env.tenant):
        services.create_rate_schedule(
            env.admin, {"name": "Draft water", "service": "water", "model": "flat", "uom": "kgal"}
        )


def test_a_live_schedule_naming_none_is_listed_and_one_naming_a_code_is_not(env):
    _, commercial = _class_codes()
    env.enable("water")
    w_all = _base(env, "W-ALL", "8.00")
    _base(env, "W-COM", "15.00", classes=[commercial])
    legacy = _activate(env, "Legacy water", seeded=True)
    named = _activate(env, "Named water", base_code=w_all["id"])
    with tenant_ctx(env.tenant):
        listed = [row.name for row in selectors.schedules_needing_a_named_base()]
        assert listed == ["Legacy water"]
        cards = {
            card["name"]: card
            for card in selectors.schedule_list(selectors.ListParams(per=100))
        }
    assert cards["Legacy water"]["base_code_to_choose"] is True
    assert cards["Named water"]["base_code_to_choose"] is False
    assert legacy["id"] != named["id"]


# ── the bill follows the schedule's named code ─────────────────────────────
def test_commercial_pays_w_com_15_and_residential_pays_w_all_8(env):
    residential, commercial = _class_codes()
    env.enable("water")
    _base(env, "W-ALL", "8.00")
    _base(env, "W-COM", "15.00", classes=[commercial])
    with tenant_ctx(env.tenant):
        com = selectors.base_charge_from_charge_code(
            "water", customer_class=commercial, named_code="W-COM"
        )
        res = selectors.base_charge_from_charge_code(
            "water", customer_class=residential, named_code="W-ALL"
        )
    assert (com["code"], com["amount"]) == ("W-COM", Decimal("15.000000"))
    assert (res["code"], res["amount"]) == ("W-ALL", Decimal("8.000000"))


# ── SIGNED 2026-10-06 — the statements the PO approved, figure for figure ──
def _named_base(env, created):
    with tenant_ctx(env.tenant):
        version = selectors.latest_version(models.Tariff.objects.get(pk=created["id"]))
        code = version.base_charge_code
        return None if code is None else code.code


def test_s6_the_statement_the_po_signed_on_2026_10_06(env):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S6, shown as:
    *"Water has W-ALL $8.00 (every class) and W-COM $15.00 (Commercial). The
    Commercial schedule names W-COM, so a commercial account pays $15.00; the
    residential schedule names W-ALL, so a residential account pays $8.00. A
    second Commercial water base code is refused, and so is a second
    every-class one."*"""
    residential, commercial = _class_codes()
    env.enable("water")
    w_all = _base(env, "W-ALL", "8.00")
    w_com = _base(env, "W-COM", "15.00", classes=[commercial])
    commercial_schedule = _activate(env, "Commercial water", base_code=w_com["id"])
    residential_schedule = _activate(env, "Residential water", base_code=w_all["id"])
    com_named = _named_base(env, commercial_schedule)
    res_named = _named_base(env, residential_schedule)
    assert (com_named, res_named) == ("W-COM", "W-ALL")
    with tenant_ctx(env.tenant):
        com = selectors.base_charge_from_charge_code("water", customer_class=commercial, named_code=com_named)
        res = selectors.base_charge_from_charge_code("water", customer_class=residential, named_code=res_named)
    assert (com["code"], com["amount"]) == ("W-COM", Decimal("15.000000"))
    assert (res["code"], res["amount"]) == ("W-ALL", Decimal("8.000000"))
    # ⚠ SUPERSEDED 2026-10-09 AT ITS LAST SENTENCE ONLY (`DEF-RAT-10026`, PO
    # ruling *"yes please do it"*, decision log *"PO RULING — A SERVICE MAY
    # HOLD TWO OR MORE BASE CODES FOR THE SAME CUSTOMER CLASS…"*). S6's *"A
    # second Commercial water base code is refused, and so is a second
    # every-class one"* asserted two refusals here; both codes now SAVE, and
    # every other figure of S6 above is still asserted as signed.
    assert _base(env, "W-COM2", "16.00", classes=[commercial])["code"] == "W-COM2"
    assert _base(env, "W-ALL2", "9.00")["code"] == "W-ALL2"


def test_s7_the_statement_the_po_signed_on_2026_10_06(env):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S7, shown as:
    *"When only one base code could serve a schedule, that one is written on
    it; when two could, you are asked to choose. Schedules already live that
    name none keep billing as today and are listed as 'Choose a base code'.
    Nothing is chosen for you."*

    ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9832`), NOT DELETED.** The clause *"keep
    billing as today"* is SUPERSEDED by the PO's ruling of the same day,
    verbatim: *"You will take the code from plan -> rate schedule -> base
    charges - in that case if it is provided then you will take it if it is not
    provided then you will take it zeo ; but you cannot take W-COM because it is
    availabel in charge coede - I have provided this before also- you have
    asked again"*. Every other sentence of S7 is still asserted as signed. The
    last block now asserts the ruling: a live schedule naming none bills a
    `$0.00` base (with the warning) for residential AND commercial — it used to
    assert W-ALL `$8.00` from the pool for residential, and commercial refused
    (`DEF-RAT-9829`, closed by this)."""
    residential, commercial = _class_codes()
    env.enable("water")
    _base(env, "W-ALL", "8.00")
    # Only one could serve → that one is written on it.
    only = _activate(env, "Only one could serve")
    assert _named_base(env, only) == "W-ALL"

    _base(env, "W-COM", "15.00", classes=[commercial])
    # Two could → you are asked to choose, and nothing is saved.
    with pytest.raises(errors.ValidationError) as asked:
        _activate(env, "Two could serve")
    assert asked.value.message_key == "rating.schedules.base_charge_code_required"
    assert [fe["field"] for fe in asked.value.field_errors] == ["base_charge_code"]

    # Already live and naming none → listed as "Choose a base code", nothing
    # chosen for it — and (PO 2026-10-06, superseding "bills as today") its
    # base is $0.00 with the warning for EVERY class: no code from the pool.
    legacy = _activate(env, "Live naming none", seeded=True)
    assert _named_base(env, legacy) is None
    with tenant_ctx(env.tenant):
        assert [row.name for row in selectors.schedules_needing_a_named_base()] == ["Live naming none"]
        cards = {card["name"]: card for card in selectors.schedule_list(selectors.ListParams(per=100))}
        res = selectors.base_charge_from_charge_code("water", customer_class=residential, named_code=None)
        com = selectors.base_charge_from_charge_code("water", customer_class=commercial, named_code=None)
    assert cards["Live naming none"]["base_code_to_choose"] is True
    assert cards["Only one could serve"]["base_code_to_choose"] is False
    assert _named_base(env, legacy) is None
    for answer in (res, com):
        # `not_set` → billing bills $0.00 and warns (`billing.oneTime.warn.baseNotSet`).
        assert (answer["code"], answer["amount"], answer["not_set"]) == (None, None, True)
        assert answer["refusal_reason"] == selectors.BASE_NOT_NAMED


# ── #30 — the help line ────────────────────────────────────────────────────
def test_the_help_line_says_the_schedule_picks_one_in_every_catalogue():
    """⚠ AMENDED 2026-10-09 (`DEF-RAT-10026`): *"One per customer class."* became
    false when the PO allowed two base codes for one class, so the line now says
    what is true — *"Each rate schedule picks one."* It still never says one per
    SERVICE (`DEF-RAT-9800`)."""
    import json
    from pathlib import Path

    locales = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    texts = {
        path.name: json.loads(path.read_text(encoding="utf-8"))["rating.chargeCode.kindHelp.base"]
        for path in sorted(locales.glob("*.json"))
    }
    assert len(texts) == 11
    assert texts["en.json"] == "Each rate schedule picks one."
    assert not any("service" in text.lower() for text in texts.values()), texts

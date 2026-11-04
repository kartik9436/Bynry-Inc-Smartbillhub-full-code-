"""DEF-BIL-8330 — a FIRST bill for an account with no billing cycle is refused.

PO ruling 2026-09-30, option A, verbatim: *"you have to show the message
/warning to user - A · Refuse until the account has a cycle"* (decision log;
BR-BIL-012 stamped the same day).

The fault it closes: BR-BIL-012 prorates a first bill from the move-in day over
the CYCLE's length (B4.3), and an account on no cycle has no length to divide by.
`one_time` then defaulted the denominator to the window's own length, a factor
of 1, so on 2.412.x a 1-day first bill for John Mauli (AC-2026-00054) priced the
same $418.00 as a whole month.

So, and every case below was written RED FIRST (hard-won law 7):

  * the preview and the draft both refuse it BEFORE anything is priced, on the
    ACCOUNT field, with their own key — `billing.oneTime.err.noBillingCycle`,
    *"No billing cycle. Assign one on the account."* — never a generic line;
  * the engine refuses it too (`one_time.preview` / `one_time.create`), so no
    caller that skips the API's step-1 check can price it;
  * nothing is drafted;
  * the same account's INTERIM bill is untouched (the ruling is about a first
    bill), and a first bill for an account WITH a cycle is not refused;
  * the key is in all eleven catalogues, and each is not the English sentence.

⚠ PostgreSQL (law 14): the new check reads and refuses; it catches no database
error and continues. It is ALSO run on PostgreSQL by the lane (see the report).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import one_time, one_time_answer
from apps.billing.exceptions import BillingRuleError
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

KEY = "billing.oneTime.err.noBillingCycle"
LOCALES = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
LANGS = ("en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR")


def _first_body(account, **overrides):
    """The PO's case: a ONE-DAY first bill (move-in Jul 1, To Jul 2)."""
    body = {
        "account_id": str(account.id),
        "kind": "first",
        "period_start": "2026-07-01",
        "period_end": "2026-07-02",
        "bill_date": "2026-07-02",
        "due_days": 21,
    }
    body.update(overrides)
    return body


def _keys(response):
    return [(row["field"], row["message_key"]) for row in response.data.get("field_errors") or ()]


@pytest.fixture
def cycle_less(brazos, dana):
    """`_account_on`'s unit is on no cycle — the account card says *None*."""
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        assert one_time_answer.account_facts(str(account.id))["cycle_name"] is None
    return account


@pytest.fixture
def on_a_cycle(monkeypatch):
    """Puts every unit on ONE cycle, through the same metering seam the card
    and the refusal both read — so the two can never disagree."""
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


# ── the API: step 1's refusal, on the account field, before any pricing ────


@pytest.mark.parametrize("view", ["one_time_preview", "one_time_create"])
def test_def_bil_8330__a_first_bill_with_no_cycle_is_refused_on_the_account(
    brazos, dana, cycle_less, view
):
    response = _post(getattr(billing_api, view), brazos, _clerk(brazos), _first_body(cycle_less))
    assert response.status_code == 422, response.data
    assert ("account_id", KEY) in _keys(response), response.data
    assert response.data.get("message_key") == KEY, response.data


def test_def_bil_8330__nothing_is_drafted(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        before = billing_models.Invoice.objects.count()
    _post(billing_api.one_time_create, brazos, _clerk(brazos), _first_body(cycle_less))
    with tenant_ctx(brazos):
        assert billing_models.Invoice.objects.count() == before


def test_def_bil_8330__the_same_accounts_fee_bill_is_not_refused_for_its_cycle(
    brazos, dana, cycle_less
):
    """⚠ This case used an INTERIM bill until 2026-10-01, when the PO ruled the
    interim base is cut down over the account's cycle (`BR-BIL-1066`) and an
    interim bill with no cycle is refused too. A fee bill has no base and is
    still not refused for a missing cycle."""
    response = _post(
        billing_api.one_time_preview,
        brazos,
        _clerk(brazos),
        _first_body(cycle_less, kind="fee", period_start="2026-07-31", period_end="2026-07-31",
                    bill_date="2026-07-31", charge_code="RECON"),
    )
    assert ("account_id", KEY) not in _keys(response), response.data
    assert response.data.get("message_key") != KEY, response.data


def test_def_bil_8330__a_first_bill_for_an_account_on_a_cycle_is_not_refused_for_it(
    brazos, dana, cycle_less, on_a_cycle
):
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), _first_body(cycle_less))
    assert ("account_id", KEY) not in _keys(response), response.data
    assert response.data.get("message_key") != KEY, response.data


def test_def_bil_8330__account_problems_is_silent_for_an_unknown_account_and_other_kinds(
    brazos, dana
):
    with tenant_ctx(brazos):
        # An id nobody holds is the account field's OWN question (a 404 through
        # customers), never *"no billing cycle"* about an account that is not there.
        assert one_time_answer.account_problems(
            {"kind": "first", "account_id": "018f0000-0000-7000-8000-000000000001"}
        ) == []
        assert one_time_answer.account_problems({"kind": "first", "account_id": ""}) == []
        assert one_time_answer.account_problems({"kind": "first", "account_id": "x"}) == []


def test_def_bil_8332__a_cycle_with_no_name_is_still_a_cycle(brazos, dana, cycle_less, monkeypatch):
    """`cycles.name` is optional; a unit on such a cycle is ON a cycle. The card
    prints its code, and its first bill is not refused for a missing cycle."""
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "J70-MONTHLY", "name": None, "due_days": 21},
    )
    with tenant_ctx(brazos):
        card = one_time_answer.account_facts(str(cycle_less.id))
    assert card["cycle_name"] == "J70-MONTHLY"
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), _first_body(cycle_less))
    assert ("account_id", KEY) not in _keys(response), response.data


# ── the engine: never priced, whichever door ─────────────────────────────


def test_def_bil_8330__the_engine_refuses_the_preview_by_its_key(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        request = one_time_answer.request_from(_first_body(cycle_less))
        with pytest.raises(BillingRuleError) as refused:
            one_time.preview(request)
    assert refused.value.message_key == KEY
    assert refused.value.br_ref == "BR-BIL-012"


def test_def_bil_8330__the_engine_refuses_the_draft_by_its_key(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        before = billing_models.Invoice.objects.count()
        request = one_time_answer.request_from(_first_body(cycle_less))
        with pytest.raises(BillingRuleError) as refused:
            one_time.create(request, run_by=None, actor=None)
        assert billing_models.Invoice.objects.count() == before
    assert refused.value.message_key == KEY


def test_def_bil_8330__the_api_carries_the_engines_key_not_a_generic_line():
    refusal = billing_api._one_time_refusal(
        BillingRuleError("no cycle", br_ref="BR-BIL-012", message_key=KEY)
    )
    assert refusal.message_key == KEY


# ── the words, in all eleven ─────────────────────────────────────────────


def test_def_bil_8330__the_sentence_is_in_all_eleven_catalogues_and_written_natively():
    english = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    assert english.get(KEY) == "No billing cycle. Assign one on the account."
    for lang in LANGS:
        catalogue = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
        assert catalogue.get(KEY), f"{lang}: {KEY} absent"
        if lang != "en":
            assert catalogue[KEY] != english[KEY], f"{lang}: English copied, not written"

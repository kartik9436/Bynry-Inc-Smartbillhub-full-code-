# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (one-time bill) · Screen S30, step 2 → step 3 → draft
# Defects:  DEF-BIL-10067 (after-walk of 2026-10-12, `05-prototype/
#           otb-after-2026-10-12/README.md`: "Rates follow the typed reading —
#           FAIL", "Water billed on 1.7 kgal (step 3) — FAIL")
# Ruling:   decision log 2026-10-12 (row 5) — *"the draft is priced on the
#           reading entered"*; Readings shows the full usage (1.7 kgal) and the
#           Rates table follows it.
# ───────────────────────────────────────────────────────
"""On the ONE-TIME BILL, the reading the clerk types on step 2 prices the bill.

The walk: AC-2026-00012, water meter W-9011, previous 2.9 on 31 Aug, a
committed 8.0 already on file for 29 Sep, the clerk types 4.6. Usage showed
1.7 kgal while the preview's Rates, step 3 and the saved draft all priced
5.1 kgal, because metering's overlay keeps a committed read in the period over
a typed one — the right answer for the move-out wizard (`DEF-CUS-5931`) and the
wrong one for this bill.

This fixture is the same shape at this harness's numbers: 1,200 on 28 Jul, a
committed 1,300 on 29 Aug, the clerk types 1,260 — 60 kgal, not 100.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import midperiod, models as billing_models, rating_seam, runs
from apps.billing.contracts import ServiceReading
from apps.metering import selectors as metering_selectors
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db

AUG_1 = date(2026, 8, 1)
AUG_14 = date(2026, 8, 14)
AUG_15 = date(2026, 8, 15)
AUG_31 = date(2026, 8, 31)


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` — an interim bill needs a cycle; named only, so the
    denominator is the window's own length (the 8300 file's fixture)."""
    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


def _august(account, **overrides):
    body = {
        "account_id": str(account.id),
        "kind": "interim",
        "period_start": AUG_1.isoformat(),
        "period_end": AUG_31.isoformat(),
        "bill_date": AUG_31.isoformat(),
        "due_days": 21,
    }
    body.update(overrides)
    return body


def _typed(asset, value):
    return [
        {
            "asset_id": str(asset["id"]),
            "read_at": "2026-08-29",
            "value": value,
            "role": "current",
        }
    ]


def _read(dana, asset, value):
    """A committed read on 29 Aug counting up from 1,200 (28 Jul)."""
    return commit_read(
        dana,
        asset["id"],
        day="2026-08-29",
        value=value,
        prior_value="1200",
        consumption=Decimal(value) - Decimal("1200"),
        unit="kgal",
    )


def _usage(body):
    lines = [line for group in body["bill"]["groups"] for line in group["lines"]]
    return sum(Decimal(line["quantity"]) for line in lines if line["charge"] == "usage")


@pytest.fixture
def walk(brazos, dana):
    """The walk's shape: a committed in-period read (1,300) the clerk's typed
    reading (1,260) must beat."""
    with tenant_ctx(brazos):
        account, unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        committed = _read(dana, asset, "1300")
    return account, unit, asset, committed


# ── the preview ──────────────────────────────────────────────────────────────
def test_the_preview_prices_the_typed_reading_over_a_committed_one(brazos, walk):
    account, _unit, asset, _committed = walk
    user = _clerk(brazos)
    plain = _post(billing_api.one_time_preview, brazos, user, _august(account))
    assert plain.status_code == 200, plain.data
    assert _usage(plain.data) == Decimal("100"), "nothing typed: the committed 1,300 prices it"

    typed = _post(
        billing_api.one_time_preview, brazos, user, _august(account, readings=_typed(asset, "1260"))
    )
    assert typed.status_code == 200, typed.data
    assert _usage(typed.data) == Decimal("60"), "1,260 − 1,200 — the reading the clerk typed"
    assert Decimal(typed.data["bill"]["total"]) < Decimal(plain.data["bill"]["total"])
    # The Readings table says the same thing the Rates table prices.
    row = typed.data["readings"]["rows"][0]
    assert row["current"]["value"] == "1260"
    assert Decimal(row["usage"]) == Decimal("60")


# ── the draft ────────────────────────────────────────────────────────────────
def test_the_draft_is_priced_on_the_reading_continue_saved_and_matches_the_preview(
    brazos, dana, walk
):
    """Step 2's Continue posts 1,260 to Meter Reads (same day as the 1,300);
    the draft is priced on THAT saved reading, and its total is the preview's."""
    account, _unit, asset, committed = walk
    with tenant_ctx(brazos):
        saved = _read(dana, asset, "1260")
    user = _clerk(brazos)
    body = _august(account, readings=_typed(asset, "1260"))
    preview = _post(billing_api.one_time_preview, brazos, user, body)
    assert preview.status_code == 200, preview.data
    assert _usage(preview.data) == Decimal("60")

    made = _post(billing_api.one_time_create, brazos, user, body)
    assert made.status_code in (200, 201), made.data
    assert Decimal(made.data["total"]) == Decimal(preview.data["bill"]["total"])
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.get(pk=made.data["invoice_id"])
        usage = sum(
            line.quantity
            for line in billing_models.InvoiceLine.objects.filter(invoice=invoice)
            if line.quantity is not None and line.kind == "usage"
        )
        from apps.billing import metering_seam

        read_ids = metering_seam.read_ids_on(invoice)
    assert usage == Decimal("60")
    # Issue locks the reading the bill was priced on — the one Continue saved —
    # and not the 1,300 the clerk's reading replaced.
    assert str(saved.id) in read_ids
    assert str(committed.id) not in read_ids


def test_a_typed_reading_never_saved_does_not_price_the_draft(brazos, walk):
    """A draft is priced only on a reading Meter Reads holds (`DEF-BIL-8300`'s
    rule, kept). Typed and not saved, with a different committed read on file,
    the draft refuses rather than pricing the 1,300 the screen did not show."""
    account, _unit, asset, _committed = walk
    user = _clerk(brazos)
    made = _post(
        billing_api.one_time_create, brazos, user, _august(account, readings=_typed(asset, "1260"))
    )
    assert made.status_code == 422, made.data


# ── the overlay's default is the move-out wizard's, untouched ───────────────
def test_the_overlay_default_still_keeps_a_committed_read(brazos, walk):
    _account, unit, asset, _committed = walk
    with tenant_ctx(brazos):
        rows = metering_selectors.provisional_reads_for_unit(
            unit["id"],
            period_start=AUG_1,
            period_end=AUG_31,
            keyed_reads=({"asset_id": str(asset["id"]), "value": "1260"},),
        )
        wins = metering_selectors.provisional_reads_for_unit(
            unit["id"],
            period_start=AUG_1,
            period_end=AUG_31,
            keyed_reads=(
                {
                    "asset_id": str(asset["id"]),
                    "value": "1260",
                    metering_selectors.KEYED_WINS_OVER_COMMITTED: True,
                },
            ),
        )
    assert Decimal(rows[0]["consumption"]) == Decimal("100"), "move-out: committed wins"
    assert Decimal(wins[0]["consumption"]) == Decimal("60"), "one-time: typed wins"
    assert wins[0]["read_id"] is None, "a value nobody saved names no read"


# ── split or not: a typed reading over a cut service ────────────────────────
def _water_account(start, end, reading):
    from apps.billing.contracts import AccountBillingData

    return AccountBillingData(
        account_id="acct",
        account_no="AC-1",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=start,
        period_end=end,
        cycle_days=31,
        service_days=(end - start).days + 1,
        tariffs=(),
        readings=(reading,),
    )


def test_a_typed_reading_over_a_split_service_is_shared_by_days_not_beside_a_committed_part(
    monkeypatch,
):
    """Water cut on 15 Aug; a committed 1,300 sits in the second part (100 kgal)
    and the clerk typed 1,260 (60 kgal for the month). Every part is a day share
    of the 60 — 14/31 and 17/31 — never 60 + 100 or the committed part kept."""
    whole = ServiceReading(
        service_code="water",
        consumption=rating_seam.Quantity(Decimal("60"), "kgal"),
        provisional=True,
        read_id="read-1260",
        chain_read_ids=("read-1260",),
    )
    monkeypatch.setattr(runs, "_readings_for", lambda unit_id, **kw: ((whole,), ()))
    gathered = [
        (
            AUG_1,
            AUG_14,
            None,
            {},
            _water_account(
                AUG_1,
                AUG_14,
                ServiceReading(
                    service_code="water",
                    consumption=rating_seam.Quantity(Decimal("60"), "kgal"),
                    provisional=True,
                ),
            ),
        ),
        (
            AUG_15,
            AUG_31,
            None,
            {},
            _water_account(
                AUG_15,
                AUG_31,
                ServiceReading(
                    service_code="water",
                    consumption=rating_seam.Quantity(Decimal("100"), "kgal"),
                    read_id="read-1300",
                    chain_read_ids=("read-1300",),
                ),
            ),
        ),
    ]
    out, _est = midperiod._apportion_evenly_by_day(
        "unit",
        gathered,
        period_start=AUG_1,
        period_end=AUG_31,
        scope_services=None,
        keyed_reads=(
            {
                "asset_id": "m",
                "value": "1260",
                runs.KEYED_WINS_OVER_COMMITTED: True,
            },
        ),
    )
    amounts = [data.readings[0].consumption.amount for *_x, data in out]
    assert amounts == [Decimal("27.096774"), Decimal("32.903226")]
    assert sum(amounts) == Decimal("60")
    assert all(data.readings[0].read_id in (None, "read-1260") for *_x, data in out)
    assert "read-1300" not in {
        rid for *_x, data in out for rid in data.readings[0].chain_read_ids
    }


def test_billing_spells_the_overlay_options_as_metering_does():
    assert runs.KEYED_WINS_OVER_COMMITTED == metering_selectors.KEYED_WINS_OVER_COMMITTED
    assert runs.KEYED_SAVED_ONLY == metering_selectors.KEYED_SAVED_ONLY

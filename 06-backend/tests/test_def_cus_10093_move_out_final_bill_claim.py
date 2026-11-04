"""DEF-CUS-10093 — a move-out told the clerk *"Billing raises it on its run"*.

It does not and cannot: no cycle run bills a closed account, and
Billing → One-time → Final refuses one by name
(`final_bill.FINAL_ACCOUNT_ALREADY_CLOSED`). Reproduced 2026-10-12 on the
brazosbend demo (AC-2026-00001, move-out 10/12/2026: step 3 drew a $186.36
draft, Complete raised no invoice, and the One-time final bill then answered
422 `account_already_closed_for_billing`).

How the final bill SHOULD be raised is an open PO question on the defect; these
tests only pin that the product stops promising a bill that cannot come.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.billing import final_bill
from apps.customers.services import MOVE_OUT_UNAVAILABLE

LOCALES = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
KEY = "customers.account.warning.final_bill_not_issued"


def _detail() -> str:
    (entry,) = [e for e in MOVE_OUT_UNAVAILABLE if e["code"] == "final_bill_not_issued"]
    return entry["detail"]


def test_the_server_no_longer_says_billing_raises_it_on_a_run():
    detail = _detail()
    assert "own run" not in detail, detail
    # It names the refusal a clerk would actually meet, by its code.
    assert final_bill.FINAL_ACCOUNT_ALREADY_CLOSED in detail, detail


def test_the_screen_sentence_promises_nothing_in_any_catalogue():
    for path in sorted(LOCALES.glob("*.json")):
        text = json.loads(path.read_text(encoding="utf-8"))[KEY]
        # One sentence: the second one was the false promise in every language.
        assert text.count(".") + text.count("。") + text.count("।") <= 1, (path.name, text)
    assert json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))[KEY] == (
        "No final bill was raised."
    )

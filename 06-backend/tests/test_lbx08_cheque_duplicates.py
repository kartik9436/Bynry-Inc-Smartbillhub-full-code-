# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10697 (lockbox audit LBX-08)
# Ruling:   decision log 2026-10-30 — *"LBX-08 (in-file duplicate cheque flagged
#           and held; de-duplicate on account + cheque, never cheque alone;
#           finish removing the old pipeline per OQ-PAY-12579)"*
# ───────────────────────────────────────────────────────
"""A cheque is ACCOUNT · AMOUNT · REFERENCE — never the cheque number alone.

Pure: no database. The already-recorded rule's payments read is handed in as a
callable, so the rule's own logic is proved here and the read is proved on a
database in `test_lbx_lockbox_import_fixes.py`.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from apps.metering import import_rules, import_runs

from tests.test_pay_import_target import INDEX, _world

A = "AC-2026-00042"
A_ID = INDEX["ac-2026-00042"]["id"]
B_INDEX = {
    **INDEX,
    "ac-2026-00077": {"id": "22222222-2222-2222-2222-222222222222", "account_no": "AC-2026-00077"},
}


def _rule(code):
    return next(one for one in import_rules.PAYMENTS_RULES if one.code == code)


def _row(no, account, amount, reference):
    return {
        "row_no": no,
        "mapped": {"account_ref": account, "amount": amount, "reference": reference},
    }


def _run(code, rows, **world):
    rule = _rule(code)
    return import_rules.EVALUATORS[rule.rule_kind](rows, _world(**world), rule)


# ── (a) the same cheque twice in one file is HELD ─────────────────────────────


def test_the_two_new_rules_hold_the_row_rather_than_warn():
    for code in ("PAY.CHEQUE_ONCE_IN_FILE", "PAY.CHEQUE_NOT_ALREADY_RECORDED"):
        rule = _rule(code)
        assert rule.severity == import_rules.ERROR, code
        assert rule.action == import_rules.REJECT_ROW, code
        assert rule.rule_kind in import_rules.EVALUATORS, code


def test_the_same_cheque_twice_in_one_file_holds_the_second_row():
    rows = [
        _row(1, A, "76.40", "CHK-1042"),
        _row(2, A, "76.4000", " chk-1042 "),
        _row(3, A, "154.00", "CHK-1043"),
    ]
    hits = _run("PAY.CHEQUE_ONCE_IN_FILE", rows, payments_account_index=INDEX)
    assert [hit.row_no for hit in hits] == [2]
    assert "Row 1" in hits[0].fix_hint


def test_two_customers_with_the_same_cheque_number_are_two_cheques():
    rows = [_row(1, A, "76.40", "1042"), _row(2, "AC-2026-00077", "76.40", "1042")]
    assert _run("PAY.CHEQUE_ONCE_IN_FILE", rows, payments_account_index=B_INDEX) == []


def test_a_row_with_no_cheque_number_is_never_called_a_duplicate():
    rows = [_row(1, A, "76.40", ""), _row(2, A, "76.40", "")]
    assert _run("PAY.CHEQUE_ONCE_IN_FILE", rows, payments_account_index=INDEX) == []


def test_the_same_cheque_with_a_different_amount_is_not_held():
    rows = [_row(1, A, "76.40", "1042"), _row(2, A, "67.40", "1042")]
    assert _run("PAY.CHEQUE_ONCE_IN_FILE", rows, payments_account_index=INDEX) == []


# ── (a) a cheque payments already has is HELD ─────────────────────────────────


def test_a_cheque_already_recorded_is_held_naming_the_payment():
    asked = []

    def lookup(keys):
        asked.append(list(keys))
        return {(str(A_ID), "76.4000", "chk-1042"): "PMT-000123"}

    rows = [_row(1, A, "76.40", "CHK-1042"), _row(2, A, "154.00", "CHK-1043")]
    hits = _run(
        "PAY.CHEQUE_NOT_ALREADY_RECORDED",
        rows,
        payments_account_index=INDEX,
        payments_posted_cheques=lookup,
    )
    assert [hit.row_no for hit in hits] == [1]
    assert "PMT-000123" in hits[0].problem
    assert len(asked) == 1, "payments is asked ONCE per file, never once per row"


def test_the_already_recorded_rule_says_nothing_when_payments_cannot_answer():
    rows = [_row(1, A, "76.40", "CHK-1042")]
    assert _run("PAY.CHEQUE_NOT_ALREADY_RECORDED", rows, payments_account_index=INDEX) == []
    assert (
        _run(
            "PAY.CHEQUE_NOT_ALREADY_RECORDED",
            rows,
            payments_account_index=None,
            payments_posted_cheques=lambda keys: {},
        )
        == []
    )


def test_the_run_wires_the_payments_read_into_stage_3():
    source = inspect.getsource(import_runs)
    assert "payments_posted_cheques=seams.payments_posted_cheques" in source


# ── (b) keep-latest keys on account + reference, never reference alone ───────


def test_keep_latest_keys_a_cheque_on_its_account_and_never_the_number_alone():
    target = import_runs.TARGET_PAYMENTS
    one = import_runs._dedupe_key_of(target, {"account_ref": A, "reference": "1042"})
    other = import_runs._dedupe_key_of(
        target, {"account_ref": "AC-2026-00077", "reference": "1042"}
    )
    again = import_runs._dedupe_key_of(
        target, {"account_ref": " ac-2026-00042", "reference": "1042"}
    )
    assert one != other, "a different customer's cheque 1042 is not a duplicate"
    assert one == again
    assert import_runs._dedupe_key_of(target, {"account_ref": A, "reference": ""}) is None


def test_the_other_targets_keep_their_single_field_key():
    key = import_runs._dedupe_key_of(import_runs.TARGET_PARTS, {"part_no": "P-1"})
    assert key == "P-1"


def test_stage_two_uses_the_scoped_key():
    source = inspect.getsource(import_runs)
    block = source.split('if handling["keep_latest_on_key"]:')[1].split("forward = ")[0]
    assert "_dedupe_key_of(run.target" in block
    assert ".get(key_field)\n            if key" not in block


# ── (c) the retiring pipeline's doors are gone ───────────────────────────────


def test_the_retiring_pipeline_routes_are_gone():
    from django.urls import Resolver404, resolve

    backend = Path(__file__).resolve().parents[1]
    assert not (backend / "apps" / "payments" / "payment_import_api.py").exists()
    api = (backend / "apps" / "payments" / "api.py").read_text()
    assert 'include("apps.payments.payment_import_api")' not in api
    for path in (
        "/api/brazosbend/payment-imports",
        "/api/brazosbend/payment-imports/x/commit",
    ):
        try:
            match = resolve(path)
        except Resolver404:
            continue
        assert "payment_import" not in (match.func.__module__ or ""), path

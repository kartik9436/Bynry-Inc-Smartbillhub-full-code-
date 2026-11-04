# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-PAY-10756 (L2-08 — import results do not add up) ·
#           DEF-PAY-10757 (L2-09 — risky rows: closed, disconnect, future) ·
#           DEF-PAY-10758 (L3-03 — messages: amount sentence, file loaded twice) ·
#           DEF-PAY-10760 (L2-02 — a store receipt repeated in a file)
# Ruling:   decision log 2026-10-30 "Payments audit by level (L1/L2/L3, 31
#           issues)" — "Rest we will fix": L2-02 (file and cross-file duplicate
#           reference held), L2-08, L2-09 (closed account held, disconnect
#           warned, future-dated payment row refused), L3-03.
# ───────────────────────────────────────────────────────
"""A payments file, through the REAL five stages, adds up.

The tester's complaint (L2-08): ten rows in, *"4 loaded and 3 rejected, and 3
rows were not explained"*, a dry run that said 5 where 4 loaded, and a
loaded-payments download with nothing in it. The figure every test below holds
is the partition: **loaded + rejected = rows in**, and the dry run's *will
create* is what loaded.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest

from apps.customers import models as customer_models
from apps.metering import import_rules, import_runs
from apps.payments import models as payment_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_pay_import_target import INDEX, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of

ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}
MAPPING = {
    "ACCOUNT": "account_ref",
    "AMOUNT": "amount",
    "DATE": "paid_on",
    "REF": "reference",
    "PAYER": "payer_name",
}
PAST = "2026-01-15"
FUTURE = "2099-11-15"


def _rule(code):
    return next(one for one in import_rules.PAYMENTS_RULES if one.code == code)


def _hits(code, rows, **world):
    rule = _rule(code)
    return import_rules.EVALUATORS[rule.rule_kind](rows, _world(**world), rule)


def _csv(lines):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["ACCOUNT", "AMOUNT", "DATE", "REF", "PAYER"])
    for line in lines:
        writer.writerow(line)
    return out.getvalue()


def _run(actor, content, *, name=None):
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_PAYMENTS,
            "source_kind": "file",
            "file_name": name or f"store-{uuid.uuid4().hex[:6]}.csv",
            "content": content,
            "session_ref": "sess_paye",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": MAPPING, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"])
    return run["id"]


def _status(tenant, code):
    return customer_models.AccountStatus.objects.get(tenant=tenant, code=code)


# ══ pure: the rules ═════════════════════════════════════════════════════════

CLEAN = {
    "ac-2026-00042": {
        **INDEX["ac-2026-00042"],
        "behavior_class": "billable",
        "status_code": "active",
    }
}


def test_l2_08_a_name_only_row_is_held_at_stage_3_as_the_writer_refuses_it():
    rule = _rule("PAY.NAME_ONLY_MATCH")
    assert rule.severity == import_rules.ERROR
    assert rule.action == import_rules.REJECT_ROW


def test_l2_09_a_closed_account_is_held():
    index = {
        k: {**v, "behavior_class": "terminal", "status_code": "closed"} for k, v in INDEX.items()
    }
    rows = [{"row_no": 1, "mapped": {"account_ref": "AC-2026-00042", "amount": "66.00"}}]
    hits = _hits("PAY.ACCOUNT_NOT_CLOSED", rows, payments_account_index=index)
    assert [hit.row_no for hit in hits] == [1]
    assert "closed" in hits[0].problem
    assert _rule("PAY.ACCOUNT_NOT_CLOSED").severity == import_rules.ERROR
    assert _hits("PAY.ACCOUNT_NOT_CLOSED", rows, payments_account_index=CLEAN) == []


def test_l2_09_an_account_in_a_disconnect_is_warned_and_still_loads():
    for code in ("marked_disconnect", "disconnected"):
        index = {
            k: {**v, "behavior_class": "billable", "status_code": code} for k, v in INDEX.items()
        }
        rows = [{"row_no": 4, "mapped": {"account_ref": "AC-2026-00042", "amount": "942.34"}}]
        hits = _hits("PAY.ACCOUNT_IN_DISCONNECT", rows, payments_account_index=index)
        assert [hit.row_no for hit in hits] == [4], code
    rule = _rule("PAY.ACCOUNT_IN_DISCONNECT")
    assert rule.severity == import_rules.WARNING
    assert rule.action == import_rules.FLAG_ONLY


def test_l2_09_a_future_dated_payment_is_refused_and_today_is_not():
    rows = [
        {"row_no": 1, "mapped": {"account_ref": "A", "amount": "1", "paid_on": "2026-11-15"}},
        {"row_no": 2, "mapped": {"account_ref": "A", "amount": "1", "paid_on": "2026-10-30"}},
        {"row_no": 3, "mapped": {"account_ref": "A", "amount": "1"}},
    ]
    from datetime import date

    hits = _hits("PAY.DATE_NOT_FUTURE", rows, today=date(2026, 10, 30))
    assert [hit.row_no for hit in hits] == [1]
    assert _rule("PAY.DATE_NOT_FUTURE").severity == import_rules.ERROR


def test_l2_02_a_repeated_store_receipt_is_held_and_named_a_reference_not_a_cheque():
    rows = [
        {
            "row_no": 1,
            "mapped": {
                "account_ref": "AC-2026-00042",
                "amount": "253.00",
                "reference": "HV-1029-0006",
            },
        },
        {
            "row_no": 2,
            "mapped": {
                "account_ref": "AC-2026-00042",
                "amount": "253.00",
                "reference": "HV-1029-0006",
            },
        },
    ]
    hits = _hits("PAY.CHEQUE_ONCE_IN_FILE", rows, payments_account_index=INDEX)
    assert [hit.row_no for hit in hits] == [2]
    assert "Cheque" not in hits[0].problem
    assert "HV-1029-0006" in hits[0].problem


def test_l3_03_a_missing_amount_says_nothing_about_premises():
    rows = [{"row_no": 1, "mapped": {"account_ref": "A", "amount": None}}]
    hits = _hits("PAY.AMOUNT_REQUIRED", rows)
    assert hits and "premises" not in hits[0].fix_hint


def test_l2_08_a_refused_row_is_labelled_by_its_row_number_not_a_cell():
    refusal = errors.BizError(
        errors.BIZ_STATE, br_ref="BR-PAY-026", message_key="payments.import.lockbox_method_off"
    )
    problem, _fix = import_runs._payment_write_refusal_sentences(
        refusal, {"reference": "30505", "account_ref": "A-1"}, row_no=7
    )
    assert "30505" not in problem.split(".")[0] or "Row 7" in problem
    assert "Row 7" in problem


def test_l2_08_the_loaded_payments_download_has_a_payments_layout():
    headers = import_runs.success_headers(import_runs.TARGET_PAYMENTS)
    assert headers == ["Payment #", "Account #", "Amount", "Reference", "Date paid"]


# ══ on the database: the tester's ten rows ═════════════════════════════════


@pytest.mark.django_db
def test_l2_08_ten_rows_in_loaded_plus_rejected_is_ten_and_dry_run_equals_loaded(brazos, dana):
    with tenant_ctx(brazos):
        a1, a2, a3, a4 = (an_account_of(dana, brazos) for _ in range(4))
        closed = an_account_of(dana, brazos)
        closed.status = _status(brazos, "closed")
        closed.save(update_fields=["status"])
        shut = an_account_of(dana, brazos)
        shut.status = _status(brazos, "marked_disconnect")
        shut.save(update_fields=["status"])
        named = an_account_of(dana, brazos)
        named.external_ref = "NOOR LARKIN"
        named.save(update_fields=["external_ref"])
        content = _csv(
            [
                [a1.account_no, "100.00", PAST, "R1", ""],
                [a2.account_no, "50.00", PAST, "R2", ""],
                [a3.account_no, "25.00", PAST, "R3", ""],
                [a1.account_no, "100.00", PAST, "R1", ""],  # same payment twice → held
                [a4.account_no, "30.00", FUTURE, "R5", ""],  # 15 Nov 2099 → refused
                [closed.account_no, "66.00", PAST, "R6", ""],  # closed → held
                [shut.account_no, "942.34", PAST, "R7", ""],  # disconnect → loads, flagged
                ["ZZ-NOT-OURS", "10.00", PAST, "R8", ""],  # not on file → rejected
                ["", "20.00", PAST, "R9", "Noor Larkin"],  # a name only → held
                [a2.account_no, "", PAST, "R10", ""],  # no amount → rejected
            ]
        )
        run_id = _run(dana, content)
        dry = import_runs.dry_run(dana, run_id, "insert")
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        figures = receipt["receipt"]
        assert figures["loaded"] == 4, figures
        assert figures["rejected"] == 6, figures
        assert figures["loaded"] + figures["rejected"] == 10
        assert figures["flagged"] == 1, "the disconnect row loads and is flagged"
        assert dry["will_create"] == figures["loaded"], (dry["will_create"], figures["loaded"])
        assert not payment_models.Payment.objects.filter(account_id=closed.pk).exists()
        assert not payment_models.Payment.objects.filter(account_id=a4.pk).exists()
        assert payment_models.Payment.objects.filter(account_id=shut.pk).count() == 1

        _name, body = import_runs.results_csv(run_id, "successes")
        lines = list(csv.reader(io.StringIO("".join(body))))
        assert lines[0] == ["Payment #", "Account #", "Amount", "Reference", "Date paid"]
        assert len(lines) == 1 + 4, lines
        refs = sorted(line[3] for line in lines[1:])
        assert refs == ["R1", "R2", "R3", "R7"]
        for line in lines[1:]:
            assert line[0], "every loaded row names its payment number"


@pytest.mark.django_db
def test_l2_08_a_row_the_writer_refuses_counts_in_the_rejected_tile(brazos, dana):
    with tenant_ctx(brazos):
        a1, a2 = an_account_of(dana, brazos), an_account_of(dana, brazos)
        run_id = _run(
            dana,
            _csv(
                [[a1.account_no, "10.00", PAST, "X1", ""], [a2.account_no, "11.00", PAST, "X2", ""]]
            ),
        )
        tenancy_models.PaymentMethod.objects.filter(tenant_id=brazos.id, code="lockbox").update(
            active=False
        )
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        figures = receipt["receipt"]
        assert figures["loaded"] == 0
        assert figures["rejected"] == 2, figures
        rows = list(
            import_runs.models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no")
        )
        assert rows[0].problem.startswith("Row 1"), rows[0].problem
        assert rows[1].problem.startswith("Row 2"), rows[1].problem


@pytest.mark.django_db
def test_l2_02_noor_larkin_hv_1029_0006_twice_pays_once(brazos, dana):
    with tenant_ctx(brazos):
        noor = an_account_of(dana, brazos)
        content = _csv(
            [
                [noor.account_no, "253.00", PAST, "HV-1029-0006", ""],
                [noor.account_no, "253.00", PAST, "HV-1029-0006", ""],
            ]
        )
        run_id = _run(dana, content)
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["receipt"]["loaded"] == 1
        assert receipt["receipt"]["rejected"] == 1
        paid = payment_models.Payment.objects.filter(account_id=noor.pk)
        assert paid.count() == 1
        assert str(paid.get().amount.quantize(__import__("decimal").Decimal("0.01"))) == "253.00"

        # The same receipt in TOMORROW's file is held too (cross-file).
        again = _run(dana, _csv([[noor.account_no, "253.00", PAST, "HV-1029-0006", "x"]]))
        receipt = import_runs.load(dana, again, {"write_mode": "insert", "approved": True})
        assert receipt["receipt"]["loaded"] == 0
        assert payment_models.Payment.objects.filter(account_id=noor.pk).count() == 1


@pytest.mark.django_db
def test_l3_03_a_payments_file_loaded_once_is_refused_at_upload(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account_of(dana, brazos)
        content = _csv([[account.account_no, "12.00", PAST, "F1", ""]])
        first = _run(dana, content, name="store-a.csv")
        receipt = import_runs.load(dana, first, {"write_mode": "insert", "approved": True})
        with pytest.raises(errors.ApiError) as refused:
            import_runs.extract(
                dana,
                {
                    "target": import_runs.TARGET_PAYMENTS,
                    "source_kind": "file",
                    "file_name": "store-a-again.csv",
                    "content": content,
                },
            )
        assert refused.value.message_key == "metering.import.file_already_loaded"
        assert refused.value.params.get("run_no") == receipt["receipt"]["run_no"]

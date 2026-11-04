# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10759 (L1-02 (a)+(b) — every imported payment banked under
#           one 'lockbox' deposit channel; nothing said which store network)
# Ruling:   decision log 2026-10-30 "Eight open payment questions answered
#           (PO)" — Q6: the store payment network's name comes from a COLUMN IN
#           THE CSV / EXCEL FILE, never a field on screen; payments carrying a
#           network name bank in that network's own daily deposit batch and read
#           "Store · <network>"; a file without the column keeps today's
#           behaviour (Lockbox / File).
# ───────────────────────────────────────────────────────
"""Q6 — a payments file's **Network** column, end to end.

The worked day (29 Oct): a file with two lockbox rows (no network) and two
Hy-Vee rows (Network = Hy-Vee) banks in **two** deposit batches — the lockbox
channel's and Hy-Vee's — and the Hy-Vee payments say *Store · Hy-Vee*. The same
file without the column banks all four under the lockbox, exactly as before.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest

from apps.metering import import_runs
from apps.payments import bankrec_models as bankrec
from apps.payments import payment_detail, reconciliation, selectors
from apps.payments import models as payment_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of

ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}
DAY = "2026-10-29"


# ══ pure ════════════════════════════════════════════════════════════════════


def test_a_store_network_banks_in_its_own_channel_and_no_network_stays_lockbox():
    assert reconciliation.channel_for(origin="import") == "lockbox"
    assert reconciliation.channel_for(origin="import", network="Hy-Vee") == "store:hy-vee"
    assert reconciliation.channel_for(origin="import", network="  Hy-Vee ") == "store:hy-vee"
    assert reconciliation.channel_for(origin="import", network="") == "lockbox"
    assert reconciliation.channel_for(origin="import", network="CheckFreePay") == (
        "store:checkfreepay"
    )
    # An explicit channel still wins, as it always has.
    assert reconciliation.channel_for(origin="import", network="Hy-Vee", explicit="office") == (
        "office"
    )


def test_the_payments_file_has_a_network_column():
    columns = {column["target"]: column for column in import_runs.PAYMENTS_COLUMNS}
    assert columns["network"]["label"] == "Network"
    assert not columns["network"]["required"]


@pytest.mark.django_db
def test_the_mapping_step_knows_it_and_the_template_carries_it(brazos):
    with tenant_ctx(brazos):
        for header in ("Network", "Payment network", "store network"):
            mapped = import_runs._auto_map([header], import_runs.TARGET_PAYMENTS)
            assert mapped == {header: "network"}, (header, mapped)
        _name, body = import_runs.sample_csv(import_runs.TARGET_PAYMENTS)
        header_row = next(csv.reader(io.StringIO(body)))
        assert "Network" in header_row


def test_the_row_payload_carries_the_network_to_the_writer():
    run = import_runs.models.ImportRun(file_name="hv.csv")
    run.id = uuid.uuid4()
    payload = import_runs._payment_payload_from(
        {"account_ref": "A", "amount": "1", "network": "Hy-Vee"}, run=run, row_no=2, recorded_at=None
    )
    assert payload["network"] == "Hy-Vee"


# ══ on the database ═════════════════════════════════════════════════════════


def _csv(header, lines):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for line in lines:
        writer.writerow(line)
    return out.getvalue()


def _load(actor, content, mapping):
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_PAYMENTS,
            "source_kind": "file",
            "file_name": f"day-{uuid.uuid4().hex[:6]}.csv",
            "content": content,
            "session_ref": "sess_imp2",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"])
    receipt = import_runs.load(actor, run["id"], {"write_mode": "insert", "approved": True})
    return receipt["receipt"]


def _batch_channel(payment):
    batch = bankrec.DepositBatch.objects.select_related("session").get(pk=payment.deposit_batch_id)
    return batch.session.channel


@pytest.mark.django_db
def test_lockbox_and_hy_vee_rows_on_29_oct_bank_in_two_batches(brazos, dana):
    with tenant_ctx(brazos):
        a1, a2, a3, a4 = (an_account_of(dana, brazos) for _ in range(4))
        content = _csv(
            ["ACCOUNT", "AMOUNT", "DATE", "REF", "Network"],
            [
                [a1.account_no, "100.00", DAY, "CHK-1", ""],
                [a2.account_no, "50.00", DAY, "CHK-2", ""],
                [a3.account_no, "253.00", DAY, "HV-1029-0006", "Hy-Vee"],
                [a4.account_no, "60.00", DAY, "HV-1029-0007", "Hy-Vee"],
            ],
        )
        figures = _load(
            dana,
            content,
            {
                "ACCOUNT": "account_ref",
                "AMOUNT": "amount",
                "DATE": "paid_on",
                "REF": "reference",
                "Network": "network",
            },
        )
        assert figures["loaded"] == 4, figures

        by_account = {
            p.account_id: p
            for p in payment_models.Payment.objects.filter(
                account_id__in=[a1.pk, a2.pk, a3.pk, a4.pk]
            )
        }
        lockbox = [by_account[a1.pk], by_account[a2.pk]]
        store = [by_account[a3.pk], by_account[a4.pk]]
        assert [p.store_network for p in lockbox] == [None, None]
        assert [p.store_network for p in store] == ["Hy-Vee", "Hy-Vee"]

        assert {_batch_channel(p) for p in lockbox} == {"lockbox"}
        assert {_batch_channel(p) for p in store} == {"store:hy-vee"}
        batches = {p.deposit_batch_id for p in lockbox + store}
        assert len(batches) == 2, "one batch per channel per day"
        for payment in lockbox + store:
            assert reconciliation.channel_of_payment(payment) == _batch_channel(payment)

        # The label: the list row and the payment page both carry the name.
        assert selectors.payment_row(store[0])["store_network"] == "Hy-Vee"
        assert selectors.payment_row(lockbox[0])["store_network"] is None
        assert payment_detail._source(store[0])["store_network"] == "Hy-Vee"
        assert payment_detail._source(lockbox[0])["store_network"] is None


@pytest.mark.django_db
def test_a_file_without_the_network_column_keeps_the_lockbox(brazos, dana):
    with tenant_ctx(brazos):
        a1, a2 = an_account_of(dana, brazos), an_account_of(dana, brazos)
        content = _csv(
            ["ACCOUNT", "AMOUNT", "DATE", "REF"],
            [[a1.account_no, "10.00", DAY, "C-1"], [a2.account_no, "11.00", DAY, "C-2"]],
        )
        figures = _load(
            dana,
            content,
            {"ACCOUNT": "account_ref", "AMOUNT": "amount", "DATE": "paid_on", "REF": "reference"},
        )
        assert figures["loaded"] == 2, figures
        payments = list(payment_models.Payment.objects.filter(account_id__in=[a1.pk, a2.pk]))
        assert [p.store_network for p in payments] == [None, None]
        assert {_batch_channel(p) for p in payments} == {"lockbox"}
        assert len({p.deposit_batch_id for p in payments}) == 1

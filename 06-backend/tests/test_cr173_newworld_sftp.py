"""CR-173-BRC10 — the New World receipt file, pushed to a City SFTP folder by a runbook.

Every case dials the in-process fake in `tests/fake_sftp_server.py` on
127.0.0.1 — **never the City's server** — with the obviously fake password
`test-password-not-real`.

**What would make these pass wrongly** (hard-won law 7, habit 2), answered:

  * *one document* would pass wrongly if it counted `<ROOT` in a file built
    from ONE batch. The batch size is forced below the receipt count, and the
    1,500 case crosses the real 1,000 boundary, so a builder that glued the
    per-batch bodies fails on the second `<?xml`.
  * *the local day* would pass wrongly with a tenant on UTC, where the local
    and the server day are the same. The tenant is on America/Detroit and the
    payment sits at 21:00 local — 01:00 UTC the next day.
  * *refused when already sent* would pass wrongly if the second call simply
    failed for another reason. It asserts the code, that the far end holds ONE
    file, and that no second claim row was written.
  * *the password never leaves* sweeps run rows, delivery rows, audit rows,
    the section's own JSON and every log line — the places a value leaks to.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.integrations import (
    file_drop,
    models,
    newworld,
    receipt_push,
    services,
    sftp,
)
from apps.integrations.adapters.erp_newworld import ErpNewWorldAdapter
from apps.integrations.manifests import erp_newworld as nw_manifest
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from apps.integrations.seams import notifications as notifications_seam
from core import crypto
from tests.fake_sftp_server import FakeSftpServer
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

PASSWORD = "test-password-not-real"
USER = "Bynry-test"
NEWWORLD = "erp_newworld"
KEY = "sbh_live_7Q2Z_brazosbend_newworld_test_only"
DETROIT = ZoneInfo("America/Detroit")
CARD_FIELDS = (
    "ReceiptPaymentCreditCardNumber",
    "ReceiptPaymentCreditCardType",
    "ReceiptPaymentCreditCardExpirationDate",
    "ReceiptPaymentCreditCardValidationNumber",
)


# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def server(tmp_path):
    with FakeSftpServer(tmp_path / "city", user=USER, password=PASSWORD) as running:
        yield running


@pytest.fixture()
def alerts(monkeypatch):
    """Every staff alert raised, recorded — and still passed on to notifications."""
    seen: list[dict] = []
    real = notifications_seam.queue_staff_alert

    def record(**alert):
        seen.append(alert)
        return real(**alert)

    monkeypatch.setattr(notifications_seam, "queue_staff_alert", record)
    return seen


def _on_detroit(tenant):
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantSettings.objects.update_or_create(
        tenant=tenant, defaults={"timezone": "America/Detroit"}
    )


def _connect(tenant, actor):
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=NEWWORLD,
        label="New World / Logos",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload="{}",
        masked_hint="••••7Q2Z",
        blind_index=crypto.blind_index(KEY, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=[one.name for one in REGISTRY.require(NEWWORLD).operations if one.they_call_us],
    )
    return connection


def _set_up(tenant, actor, server, *, password=PASSWORD, folder="/", host_key=None):
    values = {
        nw_manifest.SFTP_HOST: "127.0.0.1",
        nw_manifest.SFTP_PORT: str(server.port),
        nw_manifest.SFTP_USERNAME: USER,
        nw_manifest.SFTP_PASSWORD: password,
        nw_manifest.SFTP_PATH: folder,
        nw_manifest.SFTP_HOST_KEY: host_key if host_key is not None else server.fingerprint,
    }
    return file_drop.save(
        actor=actor,
        tenant_id=tenant.id,
        provider_key=NEWWORLD,
        group=nw_manifest.SEND_FILE_GROUP,
        values=values,
    )


def _account(tenant, actor, *, account_no="A-88120"):
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    premises = make_premises(actor, address_line=f"{account_no} Main St", services_available=["water"])
    unit = make_unit(actor, premises["id"], label="1", services=["water"])
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=status,
        account_type=customer_models.AccountType.objects.first(),
    )
    customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name="Delgado, Rosa", is_primary=True
    )
    return account


def _online_payment(actor, account, *, at, amount="42.18", ref):
    from apps.payments import idempotency
    from apps.payments import services as payment_services

    return payment_services.record_payment(
        actor,
        account_id=account.id,
        amount=Decimal(amount),
        posted_at=at,
        cleared_at=at,
        method_code="check",
        idempotency_source=idempotency.SOURCE_WEBHOOK,
        idempotency_reference=ref,
    )


def _past_day(days: int = 3) -> date:
    return datetime.now(DETROIT).date() - timedelta(days=days)


def _local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=DETROIT)


# ── the client and the server key ──────────────────────────────────────────


def test_an_unknown_server_key_is_refused_before_a_socket_opens(server):
    """Law 3: the unattended path never accepts whatever key it is shown."""
    client = sftp.ParamikoFolderWriter()
    with pytest.raises(sftp.HostKeyUnknown):
        client.write(host="127.0.0.1", port=server.port, username=USER, password=PASSWORD,
                     path="/", filename="x.xml", payload=b"x")
    assert server.connections == 0, "refused BEFORE dialling — nothing reached the server"


def test_a_different_server_key_is_refused_before_the_password_is_sent(server):
    client = sftp.ParamikoFolderWriter()
    with pytest.raises(sftp.HostKeyMismatch) as refused:
        client.write(host="127.0.0.1", port=server.port, username=USER, password=PASSWORD,
                     path="/", filename="x.xml", payload=b"x",
                     host_key="SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    assert refused.value.sentence == "Server key does not match."
    assert server.files() == {}


def test_a_wrong_password_is_one_sentence_and_carries_no_password(server):
    client = sftp.ParamikoFolderWriter()
    with pytest.raises(sftp.LoginRefused) as refused:
        client.write(host="127.0.0.1", port=server.port, username=USER, password="wrong-also-fake",
                     path="/", filename="x.xml", payload=b"x", host_key=server.fingerprint)
    assert str(refused.value) == "User name or password refused."
    assert len(str(refused.value).split()) <= 6
    assert "wrong-also-fake" not in repr(refused.value.__dict__)


def test_every_refusal_sentence_is_six_words_or_fewer():
    """B14 rule 33 — a fact on screen is ≤ 6 words."""
    for one in (sftp.UNREACHABLE_SENTENCE, sftp.LOGIN_SENTENCE, sftp.KEY_UNKNOWN_SENTENCE,
                sftp.KEY_MISMATCH_SENTENCE, sftp.WRITE_SENTENCE, receipt_push.NOT_SET_UP_SENTENCE,
                receipt_push.ALREADY_SENT_SENTENCE, receipt_push.BUILD_FAILED_SENTENCE,
                receipt_push.SENT_SENTENCE):
        assert len(one.split()) <= 6, one


def test_a_whole_ssh_keygen_line_is_read_down_to_the_fingerprint():
    assert sftp.normalise_fingerprint("256 SHA256:abcDEF123+/x host (ED25519)") == "SHA256:abcDEF123+/x"
    assert sftp.normalise_fingerprint("MD5:12:34") == ""


# ── the manifest ───────────────────────────────────────────────────────────


def test_the_two_partner_operations_are_unchanged_and_one_outbound_is_added():
    manifest = REGISTRY.require(NEWWORLD)
    by_name = {one.name: one for one in manifest.operations}
    assert list(by_name) == ["serve_receipt", "serve_ledger", "send_receipt_file"]
    assert by_name["serve_receipt"].served_path == "/partner/v1/receipts"
    assert by_name["serve_receipt"].initiative == "them" and by_name["serve_receipt"].codec == "xml"
    assert by_name["serve_ledger"].served_path == "/partner/v1/ledger"
    send = by_name["send_receipt_file"]
    assert (send.direction, send.initiative, send.transport, send.trigger) == ("out", "us", "sftp", "scheduled")
    assert send.idempotency.mode == "refuse"
    group = [one for one in manifest.fields if one.group == nw_manifest.SEND_FILE_GROUP]
    assert [one.name for one in group] == [
        "sftp_host", "sftp_port", "sftp_username", "sftp_password", "sftp_path", "sftp_host_key",
    ]
    assert all(not one.required for one in group)
    assert {one.name: one.default for one in group}["sftp_port"] == "22"
    assert {one.name: one.default for one in group}["sftp_path"] == "/"


def test_no_card_field_exists_on_the_manifest_or_in_a_pushed_file(brazos, dana, server):
    for one in REGISTRY.require(NEWWORLD).fields:
        assert "card" not in one.name.lower()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        day = _past_day()
        _online_payment(dana, _account(brazos, dana), at=_local(day, 12), ref="nw-card-0")
        result = receipt_push.send(day, trigger="manual")
    assert result.done
    body = server.files()[result.filename]
    # ⚠ AMENDED 2026-10-21 (DEF-INT-10304). Until then this asserted the four
    # names never appear. PO, option A: *"Always write all four as `""`"* —
    # so the pushed file carries all four on every payment node, EMPTY, and
    # the file passes the template check it was refused on before upload.
    from xml.etree import ElementTree as ET

    nodes = ET.fromstring(body).findall("ReceiptHeaderLevel/ReceiptPaymentLevel")
    assert nodes, "the pushed file carries a payment node to check"
    for node in nodes:
        for name in CARD_FIELDS:
            assert node.get(name) == "", f"{name} must be present and empty"
    assert newworld.validate(body) == []


def test_a_file_that_fails_the_template_check_is_never_written_to_the_city_folder(
    brazos, dana, server, alerts, monkeypatch
):
    """PO 2026-10-21: *validate before writing to the outbox*. A file that
    fails is not uploaded, no delivery claim is written (so the day stays
    sendable once fixed), the run is recorded failed WITH the problems, and
    the System Admins are alerted — the existing failure path.

    ⚠ **What would make this pass wrongly:** the upload failing for some
    other reason. The fake server would then hold no file either, so the case
    also asserts that the server was NEVER DIALLED and that the run row names
    the template problem.
    """
    real_render = newworld.render

    def wrong_shape(receipts):
        # The shape this file had until 2026-10-21: VoidedFlag true/false.
        return real_render(receipts).replace(b'VoidedFlag="0"', b'VoidedFlag="false"')

    monkeypatch.setattr(receipt_push.newworld, "render", wrong_shape)
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        _online_payment(dana, _account(brazos, dana), at=_local(day, 12), ref="nw-bad-0")
        result = receipt_push.send(day, trigger="scheduled")
        claims = models.IntegrationFileDelivery.objects.filter(connection=conn, data_day=day).count()
        run = models.IntegrationRun.objects.filter(connection=conn).order_by("-started_at").first()
        dry = receipt_push.preview(day)
    assert result.code == receipt_push.CODE_FAILED and not result.done
    assert result.sentence == receipt_push.INVALID_SENTENCE
    assert server.files() == {}, "nothing reached the City's folder"
    assert server.connections == 0, "the server was never dialled"
    assert claims == 0
    assert run.outcome == "failed"
    assert "VoidedFlag is 'false', not 0 or 1" in run.summary
    assert len(alerts) == 1 and receipt_push.INVALID_SENTENCE in alerts[0]["operation"]
    assert any("VoidedFlag" in one for one in result.flags)
    # the dry run says it would be refused, and why
    assert dry["valid"] is False and any("VoidedFlag" in one for one in dry["problems"])


def test_a_valid_day_previews_as_valid(brazos, dana):
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _online_payment(dana, _account(brazos, dana), at=_local(day, 12), ref="nw-ok-0")
        dry = receipt_push.preview(day)
        built = receipt_push.build_file(day)
    assert dry["valid"] is True and dry["problems"] == []
    assert newworld.validate(built.payload) == []
    assert b"<ROOT>" in built.payload


def test_the_adapter_passes_the_conformance_kit(server):
    from apps.integrations.conformance import Fixture, failures, run_kit

    config = {
        # `localhost`, not the dotted address: the kit reads any three-digit
        # run in describe() as a status code, and `127` is one.
        nw_manifest.SFTP_HOST: "localhost",
        nw_manifest.SFTP_PORT: str(server.port),
        nw_manifest.SFTP_USERNAME: USER,
        nw_manifest.SFTP_PATH: "/",
        nw_manifest.SFTP_HOST_KEY: server.fingerprint,
        "allowed_addresses": "",
    }
    fixture = Fixture(
        config=config,
        good_secrets={nw_manifest.SFTP_PASSWORD: PASSWORD},
        bad_secrets={nw_manifest.SFTP_PASSWORD: "wrong-but-also-fake"},
        work=[{"filename": "Receipt_20261005.xml", "payload": b"<ROOT />"}],
    )
    found = run_kit(ErpNewWorldAdapter, REGISTRY.require(NEWWORLD), fixture)
    assert failures(found) == [], failures(found)


# ── the settings section ───────────────────────────────────────────────────


def test_the_partner_rows_keep_their_own_address_after_the_folder_is_saved(brazos, dana, server):
    """DEF-INT-10000 — the City's SFTP server is the address of *Send receipt
    file* only; the two doors the City dials stay `/partner/v1/…`."""
    from apps.integrations import selectors

    with tenant_ctx(brazos):
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        card = selectors.provider_card(brazos.id, NEWWORLD)
    endpoints = {one["name"]: one["endpoint"] for one in card["operations"]}
    assert endpoints["serve_receipt"] == "/api/partner/v1/receipts"  # DEF-INT-10020: with /api
    assert endpoints["serve_ledger"] == "/api/partner/v1/ledger"
    assert endpoints["send_receipt_file"] == "127.0.0.1"


def test_saving_the_password_keeps_the_partner_key_active(brazos, dana, server):
    """The credential SLOT: one active per (connection, slot), so storing the
    City's password does not revoke the key the City uses to read from us."""
    with tenant_ctx(brazos):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        active = list(models.IntegrationCredential.objects.filter(connection=conn, is_active=True)
                      .values_list("slot", "blind_index"))
    assert sorted(slot for slot, _ in active) == ["primary", "send_file"]
    assert any(index for slot, index in active if slot == "primary")
    with tenant_ctx(brazos):
        assert services.credential_secrets(conn) == {}  # the primary is the key's marker
        assert services.credential_secrets(conn, slot="send_file") == {"sftp_password": PASSWORD}


def test_the_section_never_returns_the_password_and_masks_it(brazos, dana, server):
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        shown = _set_up(brazos, dana, server)
        again = file_drop.view(brazos.id, NEWWORLD, "send_file")
    for answer in (shown, again):
        text = json.dumps(answer, default=str)
        assert PASSWORD not in text
        assert answer["password_hint"] == "••••" + PASSWORD[-4:]
        assert "sftp_password" not in answer["settings"]


def test_a_half_typed_section_is_refused_by_field(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        _connect(brazos, dana)
        with pytest.raises(errors.ValidationError) as refused:
            file_drop.save(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD,
                           group="send_file", values={"sftp_host": "sftp.example.test"})
    named = {one["field"] for one in refused.value.field_errors}
    assert named == {"sftp_username", "sftp_password"}


def test_a_server_key_that_is_not_sha256_is_refused(brazos, dana, server):
    from core import errors

    with tenant_ctx(brazos):
        _connect(brazos, dana)
        with pytest.raises(errors.ValidationError) as refused:
            _set_up(brazos, dana, server, host_key="ab:cd:ef")
    assert {one["field"] for one in refused.value.field_errors} == {"sftp_host_key"}


def test_a_new_server_forgets_the_old_servers_key(brazos, dana, server):
    with tenant_ctx(brazos):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        file_drop.save(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD, group="send_file",
                       values={"sftp_host": "sftp.other.test"})
        conn.refresh_from_db()
    assert "sftp_host_key" not in conn.config


def test_test_connection_writes_a_file_captures_the_key_and_shows_it(brazos, dana, server):
    with tenant_ctx(brazos):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server, host_key="")
        answer = file_drop.test(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD,
                                group="send_file", started_by_name="Dana Whitfield")
        conn.refresh_from_db()
        run = models.IntegrationRun.objects.filter(connection=conn).order_by("-started_at").first()
    assert answer["ok"] is True
    assert answer["sentence"] == "Signed in and wrote a file."
    assert answer["server_key"] == server.fingerprint and answer["server_key_captured"]
    assert conn.config["sftp_host_key"] == server.fingerprint
    assert answer["test_file"].startswith("/SMART360-connection-test-")
    assert server.files() == {}, "the test file was deleted after writing"
    assert run.outcome == "succeeded" and run.started_by_name == "Dana Whitfield"


def test_test_connection_with_a_wrong_password_says_so_and_stores_no_key(brazos, dana, server):
    with tenant_ctx(brazos):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server, password="wrong-but-also-fake", host_key="")
        answer = file_drop.test(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD,
                                group="send_file")
        conn.refresh_from_db()
    assert answer["ok"] is False
    assert answer["sentence"] == "User name or password refused."
    assert "sftp_host_key" not in conn.config


# ── the file ───────────────────────────────────────────────────────────────


def test_the_day_is_the_utilitys_own_day(brazos, dana, server):
    """21:00 in Michigan on D is 01:00 UTC on D+1 — and belongs to D (PO Q2)."""
    day = _past_day()
    late = _local(day, 21)
    assert late.astimezone(dt_timezone.utc).date() == day + timedelta(days=1)
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        account = _account(brazos, dana)
        _online_payment(dana, account, at=late, ref="nw-late")
        _online_payment(dana, account, at=_local(day + timedelta(days=1), 0, 30), ref="nw-next")
        ours = receipt_push.build_file(day)
        next_day = receipt_push.build_file(day + timedelta(days=1))
    assert ours.filename == f"Receipt_{day:%Y%m%d}.xml"
    assert ours.receipt_count == 1
    assert next_day.receipt_count == 1


def test_one_document_however_many_batches(brazos, dana, monkeypatch):
    """Five receipts, batches of two → ONE declaration, ONE root, five receipts,
    each byte-identical to the API's own rendering of it."""
    monkeypatch.setattr(receipt_push, "BATCH", 2)
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        account = _account(brazos, dana)
        for index in range(5):
            _online_payment(dana, account, at=_local(day, 9, index), ref=f"nw-b-{index}")
        built = receipt_push.build_file(day)
        from apps.integrations.seams import payments as payments_seam

        start, end = receipt_push.day_window(day, DETROIT)
        rows = list(payments_seam.page_queryset(origin=payments_seam.ORIGIN_ONLINE,
                                                posted_from=start, posted_before=end))
        api_page = newworld.emit(rows)
    text = built.payload.decode()
    assert text.count("<?xml") == 1
    assert text.count("<ROOT>") == 1 and text.count("</ROOT>") == 1  # <Receipts> until 2026-10-21 (DEF-INT-10304)
    assert built.receipt_count == 5
    assert built.payload == api_page.body, "the file IS what the API serves for that day, in one page"


def test_fifteen_hundred_receipts_across_two_api_pages_are_one_document(monkeypatch):
    """The PO's worked figure: 1,500 at 1,000 a page. Built WITHOUT a database
    by standing in for the two reads, so the boundary at 1,000 is real."""
    from tests.test_cr132_newworld_receipts import _receipt

    made = [
        _receipt(number=f"P-{index:05d}", amount="10.00",
                 distributions=[(None if index % 500 == 0 else "1100", "10.00")])
        for index in range(1500)
    ]
    calls: list[int] = []

    class _Rows:
        def prefetch_related(self, *_a):
            return self

        def iterator(self, chunk_size):
            assert chunk_size == 1000
            return iter(range(1500))

    def fake_emit(batch):
        calls.append(len(batch))
        picked = tuple(made[i] for i in batch)
        return newworld.Emission(body=newworld.render(picked), receipts=picked)

    monkeypatch.setattr(receipt_push.payments_seam, "page_queryset", lambda **_kw: _Rows())
    monkeypatch.setattr(receipt_push.newworld, "emit", fake_emit)
    built = receipt_push.build_file(date(2026, 10, 5), zone=DETROIT)
    text = built.payload.decode()
    assert calls == [1000, 500], "two API pages' worth of rows"
    assert text.count("<?xml") == 1 and text.count("<ROOT>") == 1
    assert text.count("<ReceiptHeaderLevel ") == 1500
    assert built.filename == "Receipt_20261005.xml"
    # GL: three receipts carry no City GL number — sent and COUNTED, never guessed (PO Q7).
    assert built.unresolved_gl_count == 3
    assert "3 lines with no City GL number" in built.flags()


# ── sending ────────────────────────────────────────────────────────────────


def test_a_day_is_sent_once_and_the_second_is_refused(brazos, dana, server, alerts):
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server, folder="/")
        _online_payment(dana, _account(brazos, dana), at=_local(day, 10), ref="nw-once")
        first = receipt_push.send(day, trigger="scheduled")
        second = receipt_push.send(day, trigger="scheduled")
        claims = models.IntegrationFileDelivery.objects.filter(connection=conn, data_day=day).count()
        runs = list(models.IntegrationRun.objects.filter(connection=conn, operation="send_receipt_file")
                    .order_by("started_at").values_list("outcome", "summary"))
    assert first.done and first.receipt_count == 1
    assert second.code == receipt_push.CODE_ALREADY and not second.done
    assert list(server.files()) == [f"Receipt_{day:%Y%m%d}.xml"]
    assert claims == 1
    assert [outcome for outcome, _ in runs] == ["succeeded", "skipped"]
    assert f"Receipt_{day:%Y%m%d}.xml · 1 receipts · to /" in runs[0][1]
    assert alerts == []


def test_a_person_may_resend_with_a_reason(brazos, dana, server):
    from core import errors

    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        assert receipt_push.send(day, trigger="scheduled").done
        with pytest.raises(errors.ValidationError):
            file_drop.resend(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD,
                             group="send_file", day=day, reason="  ")
        again = file_drop.resend(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD,
                                 group="send_file", day=day, reason="City lost the file",
                                 started_by_name="Dana Whitfield")
        rows = list(models.IntegrationFileDelivery.objects.filter(connection=conn, data_day=day)
                    .values_list("status", "is_resend", "reason"))
    assert again["done"] is True
    assert sorted(rows) == [("sent", False, None), ("sent", True, "City lost the file")]


def test_an_empty_day_sends_an_empty_file_and_alerts(brazos, dana, server, alerts):
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        result = receipt_push.send(day, trigger="scheduled")
    assert result.done and result.receipt_count == 0
    body = server.files()[result.filename].decode()
    assert "<ROOT />" in body  # <Receipts /> until 2026-10-21 (DEF-INT-10304)
    assert newworld.validate(body.encode()) == [], "an empty day is a valid file (PO Q3)"
    assert len(alerts) == 1 and "no online receipts" in alerts[0]["operation"]


def test_a_refused_login_is_recorded_alerted_and_not_marked_sent(brazos, dana, server, alerts):
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server, password="wrong-but-also-fake")
        result = receipt_push.send(day, trigger="scheduled")
        claim = models.IntegrationFileDelivery.objects.get(connection=conn, data_day=day)
        run = models.IntegrationRun.objects.filter(connection=conn).order_by("-started_at").first()
        retried = receipt_push.send(day, trigger="scheduled")
    assert result.code == receipt_push.CODE_FAILED
    assert result.sentence == "User name or password refused."
    assert claim.status == "failed" and claim.failure == result.sentence
    assert run.outcome == "failed"
    assert len(alerts) == 2 and "refused" in alerts[0]["operation"]
    assert retried.code == receipt_push.CODE_FAILED, "a failed day is retried, not locked"


def test_a_utility_without_a_city_folder_sends_nothing(brazos, dana, server):
    day = _past_day()
    with tenant_ctx(brazos):
        conn = _connect(brazos, dana)
        result = receipt_push.send(day, trigger="scheduled")
        runs = models.IntegrationRun.objects.filter(connection=conn).count()
    assert result.code == receipt_push.CODE_NOT_SET_UP
    assert runs == 0 and server.connections == 0


def test_the_password_is_in_no_row_no_audit_and_no_log(brazos, dana, server, caplog, audit_rows):
    caplog.set_level(logging.DEBUG)
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server, host_key="")
        file_drop.test(actor=dana, tenant_id=brazos.id, provider_key=NEWWORLD, group="send_file")
        receipt_push.send(day, trigger="scheduled")
        runs = list(models.IntegrationRun.objects.filter(connection=conn).values())
        deliveries = list(models.IntegrationFileDelivery.objects.filter(connection=conn).values())
        audits = list(audit_rows)
        conn.refresh_from_db()
    blob = json.dumps([runs, deliveries, audits, conn.config], default=str)
    assert PASSWORD not in blob
    assert all(PASSWORD not in record.getMessage() for record in caplog.records)
    actions = {one["action"] for one in audits}
    assert {"integration.file_drop.saved", "integration.file_drop.tested"} <= actions


def test_another_utility_sees_none_of_it(brazos, lonestar, dana, erin, server):
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        _online_payment(dana, _account(brazos, dana), at=_local(day, 11), ref="nw-iso")
        assert receipt_push.send(day, trigger="scheduled").done
    with tenant_ctx(lonestar):
        assert models.IntegrationFileDelivery.objects.filter(tenant_id=lonestar.id).count() == 0
        assert receipt_push.connection() is None
        view = file_drop.view(lonestar.id, NEWWORLD, "send_file")
    assert view["deliveries"] == [] and view["password_hint"] is None and not view["connected"]


# ── the runbook ────────────────────────────────────────────────────────────


def _runbook(tenant):
    from apps.runbooks import services as runbook_services
    from apps.runbooks.registry import registry

    row = runbook_services.add_template(tenant.id, "newworld_receipt_push")
    return row, registry.get("newworld_receipt_push")


def test_a_dry_run_builds_and_counts_and_sends_nothing(brazos, dana, server):
    from apps.runbooks import services as runbook_services

    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        _online_payment(dana, _account(brazos, dana), at=_local(day, 8), ref="nw-dry")
        runbook, definition = _runbook(brazos)
        run, result = runbook_services.run_to_completion(
            runbook, definition, mode="dry", trigger="manual", params={"day": day.isoformat()}
        )
        deliveries = models.IntegrationFileDelivery.objects.count()
    assert server.files() == {} and deliveries == 0
    verdict = result.report[0]
    assert verdict["payload"]["word"] == "Dry run"
    assert verdict["payload"]["count"] == "1"
    assert result.records[0].outcome == "Would send — dry run"


def test_a_live_run_sends_yesterday_and_a_second_live_run_is_refused(brazos, dana, server):
    from apps.runbooks import services as runbook_services

    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        runbook, definition = _runbook(brazos)
        _, first = runbook_services.run_to_completion(runbook, definition, mode="live",
                                                      trigger="schedule")
        _, second = runbook_services.run_to_completion(runbook, definition, mode="live",
                                                       trigger="schedule")
    yesterday = datetime.now(DETROIT).date() - timedelta(days=1)
    assert list(server.files()) == [f"Receipt_{yesterday:%Y%m%d}.xml"]
    assert first.records[0].outcome == "Sent to the City folder"
    assert second.records[0].outcome == "Already sent for that day"


def test_today_is_refused_as_a_day_to_send(brazos, dana, server):
    from apps.runbooks import services as runbook_services

    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        runbook, definition = _runbook(brazos)
        today = datetime.now(DETROIT).date()
        _, result = runbook_services.run_to_completion(
            runbook, definition, mode="live", trigger="manual", params={"day": today.isoformat()}
        )
    assert result.records == () and server.files() == {}
    assert result.report[0]["payload"]["detail"] == "Only a finished day is sent."


def test_the_run_route_queues_a_live_run_by_hand(brazos, dana, server, settings):
    from django.urls import resolve

    from apps.runbooks import api as runbook_api
    from core import permissions
    from tests.test_us_ten_helpers import api_call

    assert resolve("/api/brazosbend/runbooks/newworld_receipt_push/runs").func is runbook_api.runbook_runs
    settings.JOBS_EAGER = True
    day = _past_day()
    with tenant_ctx(brazos):
        _on_detroit(brazos)
        _connect(brazos, dana)
        _set_up(brazos, dana, server)
        _runbook(brazos)
    answer = api_call(
        runbook_api.runbook_runs, "post",
        f"/api/{brazos.subdomain}/runbooks/newworld_receipt_push/runs",
        user=dana.user, role=permissions.SYSTEM_ADMIN, tenant=brazos,
        data={"mode": "live", "parameters": {"day": day.isoformat()}},
        key="newworld_receipt_push",
    )
    assert answer.status_code == 202, getattr(answer, "data", None)
    assert list(server.files()) == [f"Receipt_{day:%Y%m%d}.xml"]
    with tenant_ctx(brazos):
        run = models.IntegrationRun.objects.filter(operation="send_receipt_file").first()
    assert run.trigger == "manual" and run.started_by_name


def test_a_live_run_by_hand_is_refused_for_a_runbook_not_turned_on(brazos, dana):
    from apps.runbooks import services as runbook_services
    from core import errors

    with tenant_ctx(brazos):
        row = runbook_services.add_template(brazos.id, "test_bill")
        with pytest.raises(errors.BizError):
            runbook_services.request_run(row, mode="live", parameters={})


def test_a_billing_clerk_cannot_save_the_section_or_run_it(brazos, dana, marcus):
    from core import errors

    with tenant_ctx(brazos):
        _connect(brazos, dana)
        with pytest.raises(errors.AuthError):
            file_drop.save(actor=marcus, tenant_id=brazos.id, provider_key=NEWWORLD,
                           group="send_file", values={"sftp_host": "x.test"})

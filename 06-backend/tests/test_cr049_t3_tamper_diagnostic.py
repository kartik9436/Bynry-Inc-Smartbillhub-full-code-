# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 3 — the tamper refusal, pinned DETERMINISTICALLY after
#           `test_cr049_t3__corrupting_the_stored_bytes_makes_the_route_REFUSE`
#           was reported RED on the branch tip and passed locally. A check that
#           passes on one machine and fails on another is worse than a failing
#           one, because it is trusted.
# Rules:    BR-NOT-027 · CR-049 step 5d(e) decision 7 (*"The content hash is
#           stored as the object's checksum as well as in the row, and verified
#           on read"*) · hard-won law 1 (a check that cannot distinguish pass
#           from fail is worse than no check)
# ───────────────────────────────────────────────────────
"""WHICH FILE DID THE TAMPER TEST ACTUALLY CORRUPT?

**THE DIAGNOSIS, and it is a test defect and not a code defect.** The filesystem
backend writes **TWO files per document** — the payload at `<key>` and a sidecar
at `<key>.meta` carrying the content type and the hex digest
(`document_storage.py`, the line that says a filesystem has no object metadata).
The original case reached for `next(p for p in docs_dir.rglob("*") if
p.is_file())`, which yields **whichever of the two the filesystem happens to
return first**. On a directory order that yields the `.meta` first, the payload
is left intact, the read correctly succeeds, and the assertion fails while the
product is behaving exactly as `BR-NOT-027` requires.

So the same commit passed here and failed on the coordinator's stack, and
**neither run was evidence about the hash check.** That is the shape hard-won
law 1 warns about: a check whose output cannot distinguish pass from fail.

This file pins the behaviour by naming the file it corrupts, and asserts BOTH
directions — because "it refused" is only meaningful beside "it did not refuse
when nothing was wrong".
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

import pytest

from apps.notifications import models, reprint_api
from apps.tenancy import document_storage, document_store

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

SERVED_AT = datetime(2026, 8, 30, 15, 0, tzinfo=dt_timezone.utc)


class StubPrintVendor:
    def __init__(self):
        self.calls = []

    def __call__(self, channel, messages):
        self.calls.append((channel, messages))
        return {
            m["id"]: {"provider_reference": f"prt-{m['id'][:8]}", "status": "sent"}
            for m in messages
        }


@pytest.fixture()
def print_vendor(monkeypatch):
    from apps.integrations import services as integrations_services

    vendor = StubPrintVendor()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", vendor, raising=False)
    return vendor


@pytest.fixture()
def docs_dir(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def _serve(actor, tenant, account_no):
    from decimal import Decimal

    from apps.customers import models as customer_models
    from apps.notifications import dispatcher, notices

    premises = make_premises(actor, address_line=f"{account_no} Ridge Rd")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )
    notices.generate_disconnect_notice(
        account_id=account.pk,
        tier=notices.TIER_FINAL_48_HOUR,
        balance=Decimal("1842.100000"),
        cut_date=date(2026, 9, 3),
        reconnect_fee=Decimal("45.000000"),
        state_puc_ref="TX PUC Substantive Rule 25.29",
        on_date=date(2026, 8, 30),
        actor=actor,
    )
    row = models.OutboundMessage.objects.get(
        source_type="notice", source_id=account.pk, channel=models.CHANNEL_PRINT
    )
    models.OutboundMessage.objects.filter(pk=row.pk).update(
        recipient_address=f"{account_no} Ridge Rd, Katy TX 77494",
        recipient_snapshot={"account_no": account_no},
        unavailable_reason=None,
    )
    row.refresh_from_db()
    dispatcher.dispatch_cycle(
        now=SERVED_AT, channels=(models.CHANNEL_PRINT,), actor=actor, job="test"
    )
    row.refresh_from_db()
    lookup = document_store.for_source(
        source_type="outbound_message", source_id=row.pk, channel=row.channel
    )
    assert lookup.found
    return row, lookup.document


def _payload_and_sidecar(docs_dir):
    """The TWO files this backend writes, told apart by name and not by luck."""
    files = sorted(p for p in docs_dir.rglob("*") if p.is_file())
    sidecars = [p for p in files if p.suffix == ".meta"]
    payloads = [p for p in files if p.suffix != ".meta"]
    assert len(payloads) == 1, f"expected one payload, found {payloads}"
    assert len(sidecars) == 1, f"expected one sidecar, found {sidecars}"
    return payloads[0], sidecars[0]


def _get(view, actor, tenant, **kwargs):
    return api_call(view, "get", user=actor.user, role="system_admin", tenant=tenant, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# THE DIAGNOSIS — two files, and only one of them is the document
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__the_backend_writes_a_payload_AND_a_sidecar(brazos, dana, print_vendor, docs_dir):
    """The fact the flaky test tripped over, asserted so nobody rediscovers it.

    `rglob("*")` over this directory yields TWO files, in filesystem order. A
    tamper case that takes the first one is testing whichever the operating
    system felt like returning.
    """
    with tenant_ctx(brazos):
        _serve(dana, brazos, "A-49401")
        payload, sidecar = _payload_and_sidecar(docs_dir)
    assert sidecar.name == f"{payload.name}.meta"
    # The sidecar carries the checksum as well as the row does — CR-049 step
    # 5d(e) decision 7's *"stored as the object's checksum AS WELL AS in the
    # row"*, which on a filesystem is the only place object metadata can live.
    assert len(sidecar.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_cr049_t3__corrupting_THE_PAYLOAD_makes_the_route_refuse(
    brazos, dana, print_vendor, docs_dir
):
    """⚠ **THE ASSERTION THAT MATTERS, now naming the file it corrupts.**

    Reported RED on the branch tip and green here from the same commit, because
    the original picked a file by directory order. This one picks the payload by
    name, so it means the same thing on every machine.
    """
    with tenant_ctx(brazos):
        row, reference = _serve(dana, brazos, "A-49402")

        good = _get(reprint_api.stored_document, dana, brazos, document_id=str(reference.id))
        assert good.status_code == 200, good.data

        payload, _sidecar = _payload_and_sidecar(docs_dir)
        payload.write_bytes(b"this is not the letter that was sent")

        tampered = _get(reprint_api.stored_document, dana, brazos, document_id=str(reference.id))
        by_message = _get(
            reprint_api.outbound_document, dana, brazos, message_id=str(row.pk)
        )

    assert tampered.status_code >= 400, (
        "the route served bytes whose hash does not match the record — a silent byte "
        "change is the one thing BR-NOT-027's store exists to catch"
    )
    assert tampered.data["message_key"] == "notifications.frozenDocument.hashMismatch"
    assert "this is not the letter" not in str(tampered.data)

    # ⚠ AND IT REFUSES ON THE REPRINT ROUTE TOO, rather than degrading into the
    # honest state. "We never kept it" and "what we kept is not what we stored"
    # are different facts with different remedies.
    assert by_message.status_code >= 400
    assert by_message.data["message_key"] == "notifications.frozenDocument.hashMismatch"
    assert by_message.data.get("provenance") is None


def test_cr049_t3__corrupting_ONLY_THE_SIDECAR_still_serves_the_document(
    brazos, dana, print_vendor, docs_dir
):
    """⚠ **THE OTHER HALF, and it is why the flaky run looked like a code defect.**

    The sidecar is this backend's stand-in for object metadata; the DOCUMENT is
    the payload. Corrupting the sidecar leaves the letter untouched, so the read
    correctly SUCCEEDS — the hash the route verifies is recomputed from the
    payload and compared against the DATABASE ROW, which is the comparison
    decision 7 actually specifies.

    A run that corrupted this file and expected a refusal was asserting that the
    product should refuse to serve an intact document. **That is the assertion
    that was wrong, not the code.**
    """
    with tenant_ctx(brazos):
        _row, reference = _serve(dana, brazos, "A-49403")
        _payload, sidecar = _payload_and_sidecar(docs_dir)
        sidecar.write_text("text/plain\ndeadbeef\n", encoding="utf-8")

        response = _get(reprint_api.stored_document, dana, brazos, document_id=str(reference.id))

    assert response.status_code == 200, response.data
    assert response.data["content_hash"] == reference.content_hash


# ══════════════════════════════════════════════════════════════════════════
# THE PRE-SIGNED URL — the coordinator's second question
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__no_download_url_is_issued_for_a_tampered_document(
    brazos, dana, print_vendor, docs_dir
):
    """⚠ **THE HASH CHECK HAPPENS BEFORE THE LINK IS MINTED, AND THIS PINS THE
    ORDER.**

    A pre-signed URL is a direct client-to-cloud read: our code is not in that
    path, so nothing hashes anything once the link is out. If a link were issued
    beside a failed verification — or worse, instead of one — the check would be
    decorative. `_read_or_refuse` fetches first and raises, so the response that
    would have carried the URL is never built.

    Asserted as an OBSERVABLE PROPERTY of the response rather than by reading the
    order of two statements, because the order of two statements is one refactor
    from changing.
    """
    with tenant_ctx(brazos):
        _row, reference = _serve(dana, brazos, "A-49404")
        payload, _sidecar = _payload_and_sidecar(docs_dir)
        payload.write_bytes(b"swapped years later")

        response = _get(reprint_api.stored_document, dana, brazos, document_id=str(reference.id))

    assert response.status_code >= 400
    body = str(response.data)
    assert "download_url" not in body
    assert "http" not in body, "a link to the tampered object reached the caller"


def test_cr049_t3__the_intact_document_does_get_a_link(brazos, dana, print_vendor, docs_dir):
    """The control for the case above — otherwise "no link" would pass on a route
    that never issues one at all."""
    with tenant_ctx(brazos):
        _row, reference = _serve(dana, brazos, "A-49405")
        response = _get(reprint_api.stored_document, dana, brazos, document_id=str(reference.id))

    assert response.status_code == 200
    assert response.data["download_url"]
    assert response.data["url_expires_in_seconds"] == document_storage.url_ttl_seconds()

# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-039 (EP-INT-10) — format is a parameter: projection × codec
#           × packaging. Screens: S141 (the picker) · S142 (the codec on a run)
# Rules:    BR-INT-033 (a registered codec, separate from the projection;
#           unregistered refused BY NAME with the list; a picker only where
#           more than one is registered; no fixture = not supported) ·
#           BR-INT-038 (a rename touches the projection, never a model) ·
#           BR-NOT-1030 (the print half of the same rule; its tests are
#           unchanged and green against the lifted registry)
# Tests:    this file — TC-1 (one projection, two codecs, identical field
#           sets, byte-equal to the recorded fixtures) · TC-2 (`yaml` refused
#           at load with the list) · TC-3 (four codecs on the accounting card,
#           none on the mailbox card — the served payload) · TC-4 (a codec with
#           code and no fixture fails the kit) · TC-5 (`paymentDate` →
#           `postedDate` is one projection edit) · TC-6 (the print registry
#           IS `apps.integrations.codecs`'s — one mechanism, not two)
# Impacts:  apps/integrations/codecs.py · apps/integrations/registry.py ·
#           apps/billing/print_formats.py · apps/integrations/fixtures/
# ───────────────────────────────────────────────────────
"""US-INT-039 — the same payment as JSON to one partner and XML to another.

Everything here runs on the default SQLite suite; nothing in the codec
registry touches a database. TC-3 reads the grid through `selectors.grid()`
because the picker draws what the SERVER serves, not what a component thinks.
"""

from __future__ import annotations

import dataclasses
import subprocess
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.billing import print_formats
from apps.integrations import codecs, manifests, registry, selectors
from apps.integrations.registry import Auth, Idempotency, ManifestError, Operation, Registry
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

REPO = Path(__file__).resolve().parents[2]
BILLING = REPO / "06-backend" / "apps" / "billing"

#: US-INT-039 §4 — the worked payment. The recorded fixtures were emitted
#: from EXACTLY this object on 2026-09-03; the byte-equality below is what
#: makes them "recorded" rather than typed.
PAYMENT = SimpleNamespace(
    payment_no="PAY-2609-0311",
    posted_at=date(2026, 9, 1),
    amount=Decimal("142.1800"),  # stored at four; DISPLAYED at two (hard rule 2)
    currency="USD",
    method=SimpleNamespace(name="Bank transfer"),
    account_code="4100",
    partner_account="001.100.44100",  # Aclarian's string for 4100 (US-INT-037 §4)
    account_no="ACC-1048",
)
NOTICE = SimpleNamespace(
    to="s.kelly@example.com",
    sender="bills@brazosbend.example",
    subject="Your September bill is ready",
    reference="AC-2026-00214",
    body="Your bill for September is $142.18, due 1 October.\nThank you.",
)


def _fixture(codec: str, filename: str) -> bytes:
    return (codecs.FIXTURES_ROOT / codec / filename).read_bytes()


# ── TC-1 — one projection, two codecs, one fact ─────────────────────────────


def test_us_int_039_tc1_the_same_payment_leaves_as_json_and_as_xml_and_parses_back_identically():
    as_json = codecs.emit("gl_payment_v1", "json", [PAYMENT])
    as_xml = codecs.emit("gl_payment_v1", "xml", [PAYMENT])
    assert as_json.filename == "gl_payment_v1.json" and as_json.media_type == "application/json"
    assert as_xml.filename == "gl_payment_v1.xml" and as_xml.media_type == "application/xml"

    back_from_json = codecs.parse("json", as_json.payload)
    back_from_xml = codecs.parse("xml", as_xml.payload)
    assert back_from_json == back_from_xml, "two codecs, one projection, one set of fields"
    assert set(back_from_json[0]) == set(codecs.GL_PAYMENT_V1.header)
    assert back_from_json[0]["amount"] == "142.18", "stored at four decimals, displayed at two"
    assert back_from_json[0]["paymentNumber"] == "PAY-2609-0311"
    assert back_from_json[0]["partnerAccount"] == "001.100.44100"


def test_us_int_039_tc1_the_recorded_fixtures_are_this_emitter_on_this_payment_byte_for_byte():
    """The fixture is what makes a codec SUPPORTED, and it is honest only if it
    is what the code produces. Re-record it on purpose, never by hand."""
    assert codecs.emit("gl_payment_v1", "json", [PAYMENT]).payload == _fixture(
        "json", "gl_payment_v1.json"
    )
    assert codecs.emit("gl_payment_v1", "xml", [PAYMENT]).payload == _fixture(
        "xml", "gl_payment_v1.xml"
    )
    assert codecs.emit("gl_payment_v1", "csv", [PAYMENT]).payload == _fixture(
        "csv", "gl_payment_v1.csv"
    )
    assert codecs.emit("bill_message_v1", "mime", [NOTICE]).payload == _fixture(
        "mime", "bill_message_v1.eml"
    )


def test_us_int_039_csv_and_mime_round_trip_too():
    rows = codecs.parse("csv", codecs.emit("gl_payment_v1", "csv", [PAYMENT]).payload)
    assert rows == codecs.parse("json", codecs.emit("gl_payment_v1", "json", [PAYMENT]).payload)
    message = codecs.parse("mime", codecs.emit("bill_message_v1", "mime", [NOTICE]).payload)
    assert message == [codecs.BILL_MESSAGE_V1.project(NOTICE)]
    with pytest.raises(ValueError, match="exactly one message"):
        codecs.emit("bill_message_v1", "mime", [NOTICE, NOTICE])


def test_us_int_039_packaging_is_a_third_parameter_and_zip_wraps_the_same_bytes():
    plain = codecs.emit("gl_payment_v1", "csv", [PAYMENT])
    zipped = codecs.emit("gl_payment_v1", "csv", [PAYMENT], packaging_name="zip")
    assert zipped.filename == "gl_payment_v1.csv.zip"
    assert zipped.media_type == "application/zip"
    import io

    with zipfile.ZipFile(io.BytesIO(zipped.payload)) as archive:
        assert archive.namelist() == ["gl_payment_v1.csv"]
        assert archive.read("gl_payment_v1.csv") == plain.payload


# ── TC-2 — an unregistered name is refused AT LOAD, by name, with the list ──


def _op(**overrides):
    base = dict(
        name="send_message",
        label="Send messages",
        direction="out",
        initiative="us",
        transport="https",
        trigger="dispatcher",
        idempotency=Idempotency(mode="refuse", source="queue_row_id"),
        completion="immediate",
        # CR-110-BRC04 — every operation names its ceiling or the registry refuses it.
        rate_limit_per_minute=60,
    )
    base.update(overrides)
    return Operation(**base)


def _manifest(**overrides):
    base = dict(
        key="example_provider",
        category="email",
        display_name="Example",
        summary="One sentence.",
        auth=Auth(mode="we_hold_theirs", placement="header"),
        operations=(_op(),),
    )
    base.update(overrides)
    # `DEF-INT-5488` / `CR-110-BRC04` — an operation we dial names a host field
    # the manifest declares. Appended rather than put in `base` so a case that
    # overrides `fields` (the picker cases below) still gets one.
    from apps.integrations.registry import Field as _Field

    host = _Field(name="base_url", label="Service address", kind="host")
    base["fields"] = (host, *base.get("fields", ()))
    return registry.Manifest(**base)


def test_us_int_039_tc2_a_manifest_naming_yaml_is_refused_at_load_with_the_registered_list():
    fresh = Registry()
    with pytest.raises(ManifestError) as refused:
        fresh.register(_manifest(operations=(_op(codec="yaml"),)))
    text = str(refused.value)
    assert "example_provider · send_message" in text
    assert "'yaml'" in text
    for registered in ("json", "xml", "csv", "mime", "bai2", "camt053"):
        assert registered in text, f"the refusal must list {registered}"
    assert "BR-INT-033" in text
    assert len(fresh) == 0, "nothing half-registered"

    with pytest.raises(ManifestError) as refused_list:
        fresh.register(_manifest(codecs=("yaml",)))
    assert "'yaml'" in str(refused_list.value) and "json" in str(refused_list.value)


def test_us_int_039_tc2_emit_refuses_an_unregistered_codec_projection_or_packaging_by_name():
    with pytest.raises(codecs.UnregisteredName) as refused:
        codecs.emit("gl_payment_v1", "yaml", [PAYMENT])
    said = str(refused.value)
    assert "'yaml'" in said and "json" in said and "xml" in said
    assert refused.value.asked == "yaml" and "json" in refused.value.available

    with pytest.raises(codecs.UnregisteredName) as no_projection:
        codecs.emit("payment_v9", "json", [PAYMENT])
    assert "'payment_v9'" in str(no_projection.value)
    assert "gl_payment_v1" in str(no_projection.value)

    with pytest.raises(codecs.UnregisteredName) as no_packaging:
        codecs.emit("gl_payment_v1", "json", [PAYMENT], packaging_name="tar")
    assert "'tar'" in str(no_packaging.value) and "zip" in str(no_packaging.value)


def test_us_int_039_a_name_only_codec_refuses_to_write_or_read_naming_the_ones_that_can():
    """`bai2` is REGISTERED so the bank card may list it; nothing may be asked
    to write or read one until wave I builds and records it."""
    assert codecs.CODECS.require("bai2").name_only
    with pytest.raises(codecs.UnregisteredName) as cannot_write:
        codecs.emit("gl_payment_v1", "bai2", [PAYMENT])
    assert "'bai2'" in str(cannot_write.value)
    assert "json" in cannot_write.value.available and "bai2" not in cannot_write.value.available
    #: ⚠ THE READ EXAMPLE MOVED FROM `camt053` TO `ofx` ON 2026-09-06, AND THE
    #: MOVE IS THE POINT RATHER THAN A REPAIR. `CR-069` wave J gave `camt053` a
    #: decoder, so it can be read — while STILL not being a *supported* format,
    #: because no real bank statement has been recorded for it (`BR-INT-033`
    #: makes the fixture, not the code, decide that). This case is about a codec
    #: with NO CODE AT ALL, and `ofx` is one; pointing it at `camt053` after
    #: wave J would have been a test named after an assertion it no longer
    #: makes (hard-won law 7's *looking at the wrong thing*).
    with pytest.raises(codecs.UnregisteredName) as cannot_read:
        codecs.parse("ofx", b"<OFX/>")
    assert "csv" in cannot_read.value.available
    assert "camt053" in cannot_read.value.available, "it CAN be read; it is not SUPPORTED"
    with pytest.raises(codecs.UnregisteredName):
        codecs.emit("gl_payment_v1", "json", [PAYMENT], packaging_name="pgp")


def test_us_int_039_the_refusal_is_clerk_copy():
    with pytest.raises(codecs.UnregisteredName) as refused:
        codecs.CODECS.require("fixed-width")
    said = str(refused.value)
    for forbidden in ("BR-", "OQ-", "DEF-", "CR-", "NamedRegistry", "codecs."):
        assert forbidden not in said, f"{forbidden!r} is not something a clerk should read"


def test_us_int_039_two_different_codecs_may_not_share_one_name():
    other = dataclasses.replace(codecs.CODECS.require("json"), summary="a different json")
    with pytest.raises(codecs.AlreadyRegistered):
        codecs.register_codec(other)
    codecs.register_codec(codecs.CODECS.require("json"))  # the same object twice is fine


# ── TC-3 — the picker draws what the server serves ──────────────────────────


@pytest.mark.django_db
def test_us_int_039_tc3_the_accounting_card_serves_four_codecs_and_the_mailbox_serves_none(
    brazos, dana
):
    with tenant_ctx(brazos):
        served = selectors.grid(brazos.id)
    by_key = {one["key"]: one for one in served["providers"]}
    assert by_key["accounting_file"]["codecs"] == ["qbo", "xero", "csv", "iif"]
    # CSV only — PO Q2 = A, 2026-10-30 (`DEF-INT-10702`, lockbox audit LBX-07):
    # `apps/payments/lockbox.py` reads CSV and nothing else, so nothing else is offered.
    assert by_key["bank_lockbox_file"]["codecs"] == ["csv"]
    # One codec on its operation (mime), NONE to choose between — so no picker.
    assert by_key["email_smtp"]["codecs"] == []
    smtp = registry.REGISTRY.require("email_smtp")
    assert [op.codec for op in smtp.operations] == ["mime"]


def test_us_int_039_every_codec_the_seventeen_manifests_name_is_registered():
    """The load-time refusal, run over the shipped set: if this passes, no
    shipped manifest names a codec nobody registered."""
    fresh = manifests.register_all(Registry())
    named = {codec for one in fresh.all() for codec in one.codecs}
    named |= {op.codec for one in fresh.all() for op in one.operations if op.codec}
    assert named <= set(codecs.names())
    assert "camt.053" not in named and "xero_csv" not in named, "the old spellings are gone"


def test_us_int_039_describe_codecs_keeps_the_manifests_order_and_carries_no_internal_id():
    described = codecs.describe_codecs(["qbo", "xero", "csv", "iif"])
    assert [one["name"] for one in described] == ["qbo", "xero", "csv", "iif"]
    assert described[2]["supported"] is True and described[0]["supported"] is False
    for one in described:
        for forbidden in ("BR-", "OQ-", "DEF-"):
            assert forbidden not in one["summary"]


# ── TC-4 — a codec with code and no fixture is not a supported format ───────


def test_us_int_039_tc4_camt053_with_a_decoder_and_no_fixture_fails_the_kit(tmp_path):
    """The kit reads a REGISTRY and a ROOT so the red case can be proved
    without deleting a shipped folder."""
    own = codecs.NamedRegistry("file format")
    own.register(
        "camt053",
        dataclasses.replace(codecs.CODECS.require("camt053"), decode=lambda data: [], arrives=None),
    )
    (tmp_path / "camt053").mkdir()
    (tmp_path / "camt053" / "PROVENANCE").write_text("nothing recorded yet\n")

    findings = codecs.check_fixtures(tmp_path, registry=own)
    assert [one.codec for one in findings] == ["camt053"]
    assert findings[0].status == "not_supported"
    assert "not a supported format" in findings[0].reason
    assert "fixtures/camt053/" in findings[0].reason
    assert codecs.is_supported("camt053", tmp_path, registry=own) is False

    # …and the same codec WITH a recorded file is supported. PROVENANCE never counts.
    (tmp_path / "camt053" / "statement.xml").write_bytes(b"<Document/>")
    assert codecs.fixture_paths("camt053", tmp_path) == [tmp_path / "camt053" / "statement.xml"]
    assert codecs.check_fixtures(tmp_path, registry=own)[0].status == "supported"
    assert codecs.is_supported("camt053", tmp_path, registry=own) is True


def test_us_int_039_tc4_the_shipped_kit_report_is_the_honest_one():
    """The record of what this repository can actually do with a file.

    ⚠ **IT MOVED ON 2026-09-06 AND IT MOVED DELIBERATELY (`CR-069` wave J).**
    This case is a RECORD, so when the world grows the record is edited on
    purpose and never loosened — the same discipline `G64` applies to the
    golden count. Wave J added `iif` to the supported five and put `camt053`
    into a state this test previously had no row for.

    **THREE STATES, AND THE MIDDLE ONE IS THE ONE WAVE J MADE NECESSARY:**

      * **supported** — code AND a recorded fixture. Five now, and for every
        one of them WE are the emitter, so the fixture is our own output.
      * **code, no recorded file** — `camt053` decodes and is STILL not
        supported, because `BR-INT-033` makes the FIXTURE decide. `US-INT-038`
        TC-6 is exactly this: a codec with no fixture fails the kit.
      * **name only** — no encoder and no decoder; `arrives` says what brings
        it. ⚠ For `xero` that is now a MODULE and not a wave: its column layout
        is a projection, and projections are Runbooks' (`BR-INT-054`).

    A shipped folder never holds a typed sample, in any of the three.
    """
    report = {one.codec: one for one in codecs.check_fixtures()}
    assert codecs.supported_names() == ("csv", "iif", "json", "mime", "xml")

    #: the middle state — it reads, and it is not supported
    assert codecs.CODECS.require("camt053").decode is not None
    assert report["camt053"].status == "not_supported"
    assert "no recorded fixture" in report["camt053"].reason
    assert "by name only" not in report["camt053"].reason, (
        "it HAS code; saying 'by name only' about it would be the kit lying "
        "about which half is missing"
    )

    for name in ("xero", "qbo", "ofx", "qfx", "bai2", "pdf"):
        assert report[name].status == "not_supported"
        assert "by name only" in report[name].reason
    for name in ("xero", "qbo", "ofx", "qfx", "bai2", "camt053", "pdf"):
        assert codecs.fixture_paths(name) == [], f"{name} must not carry a typed sample"
        assert codecs.provenance(name) is not None, f"{name} must say why it holds nothing"
        assert "NOT A SUPPORTED FORMAT" in codecs.provenance(name)
    for name in ("json", "xml", "csv", "mime", "iif"):
        assert "WE are the emitter" in codecs.provenance(name)


# ── TC-5 — their rename is one edit in the projection ───────────────────────


def test_us_int_039_tc5_renaming_payment_date_to_posted_date_touches_the_projection_only():
    renamed = dataclasses.replace(
        codecs.GL_PAYMENT_V1,
        name="gl_payment_v1_renamed_for_this_test",
        fields=tuple(
            (
                dataclasses.replace(one, external_name="postedDate")
                if one.external_name == "paymentDate"
                else one
            )
            for one in codecs.GL_PAYMENT_V1.fields
        ),
    )
    codecs.register_projection(renamed)
    try:
        as_json = codecs.emit(renamed.name, "json", [PAYMENT]).payload.decode()
        as_xml = codecs.emit(renamed.name, "xml", [PAYMENT]).payload.decode()
    finally:
        del codecs.PROJECTIONS[renamed.name]
    for text in (as_json, as_xml):
        assert "postedDate" in text and "paymentDate" not in text
    # Neither codec changed: the same objects, the same code, before and after.
    assert codecs.CODECS.require("json").encode is codecs._encode_json
    assert codecs.CODECS.require("xml").encode is codecs._encode_xml
    # And the model it reads did not: the source attribute is still `posted_at`.
    assert [one.source for one in renamed.fields] == [
        one.source for one in codecs.GL_PAYMENT_V1.fields
    ]


def test_us_int_039_a_projection_refuses_a_name_a_codec_would_have_to_escape():
    with pytest.raises(ValueError, match="not a plain identifier"):
        codecs.Projection(
            name="bad", summary="", fields=(codecs.ProjectedField("posted date", "posted_at"),)
        )
    with pytest.raises(ValueError, match="declared twice"):
        codecs.Projection(
            name="bad",
            summary="",
            fields=(
                codecs.ProjectedField("amount", "amount"),
                codecs.ProjectedField("amount", "total"),
            ),
        )


# ── TC-6 — one registry, not two ────────────────────────────────────────────


def test_us_int_039_tc6_the_print_vendor_registry_is_an_instance_of_the_integrations_one():
    assert isinstance(print_formats.NAMED_FORMATS, codecs.NamedRegistry)
    assert print_formats._registry is print_formats.NAMED_FORMATS
    assert "manifest-csv" in print_formats.NAMED_FORMATS.names()
    source = (BILLING / "print_formats.py").read_text(encoding="utf-8")
    assert "from apps.integrations import codecs" in source
    assert "_registry: dict" not in source, "a private dict would be a second registry"

    found = subprocess.run(
        ["grep", "-rln", "--include=*.py", "NAMED_FORMATS", str(BILLING)],
        capture_output=True,
        text=True,
    )
    assert found.stdout.split() == [str(BILLING / "print_formats.py")]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-039@87b94265 (EP-INT-10 story + BR-INT-033 · BR-INT-038 verbatim)
# generated: 2026-09-03 by the CR-069 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔(TC-3 reads the served grid, which is what the picker draws) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_039_codecs.py · tests/test_cr053_task14_print_formats.py · tests/test_us_int_013_registry.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── TC-3's other half — the picker is data, and the registry holds the rule ──


def test_us_int_039_tc3_a_manifest_with_several_codecs_must_carry_the_picker_field_and_one_with_one_must_not():
    """The format picker on S141 is the manifest's own `select` of its codecs,
    drawn by the field slot; it exists exactly where more than one codec is
    registered, and the registry refuses a manifest that says otherwise."""
    from apps.integrations.registry import Field

    fresh = Registry()
    with pytest.raises(ManifestError) as no_picker:
        fresh.register(_manifest(codecs=("csv", "json")))
    assert "carries no select field" in str(no_picker.value)
    assert "BR-INT-033" in str(no_picker.value)

    with pytest.raises(ManifestError) as stray_picker:
        fresh.register(
            _manifest(
                codecs=("mime",),
                fields=(
                    Field(name="file_format", label="Format", kind="select", options=("mime",)),
                ),
            )
        )
    assert "a picker appears only where more than one is registered" in str(stray_picker.value)

    fresh.register(
        _manifest(
            codecs=("csv", "json"),
            fields=(
                Field(name="file_format", label="Format", kind="select", options=("csv", "json")),
            ),
        )
    )
    assert len(fresh) == 1
    # the shipped seventeen obey it: four on the accounting card, none elsewhere —
    # the bank card has ONE codec (CSV) since 2026-10-30, so it draws no picker
    shipped = manifests.register_all(Registry())
    pickers = {
        one.key: [
            f.options
            for f in one.fields
            if f.kind == "select" and f.options and set(f.options) <= set(codecs.names())
        ]
        for one in shipped.all()
    }
    assert pickers["accounting_file"] == [("qbo", "xero", "csv", "iif")]
    assert pickers["bank_lockbox_file"] == []
    assert pickers["email_smtp"] == []

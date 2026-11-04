# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INT-10702 (lockbox audit LBX-07 — the Bank & lockbox connection
#           offered six file formats while only CSV is ever read)
# Ruling:   decision log 2026-10-30, Q2 = A: *"lockbox files are CSV only for
#           now; the connection offers CSV alone"*
# ───────────────────────────────────────────────────────
"""What the connection OFFERS must be what the reader can READ."""

from __future__ import annotations

import pytest

from apps.integrations import codecs, manifests
from apps.integrations.adapters.base import validate_fields
from apps.integrations.adapters.bank_lockbox_file import BankLockboxFileAdapter
from apps.integrations.registry import Registry
from apps.payments import lockbox


def _bank():
    return manifests.register_all(Registry()).require("bank_lockbox_file")


def test_the_bank_connection_offers_csv_and_nothing_else():
    bank = _bank()
    assert bank.codecs == ("csv",)
    assert bank.codecs == (lockbox.FORMAT_CSV,), "offered == the one format lockbox.py reads"


def test_there_is_no_format_picker_because_there_is_one_format():
    """BR-INT-033: a picker appears only where more than one codec is registered."""
    bank = _bank()
    pickers = [
        one.name
        for one in bank.fields
        if one.kind == "select" and one.options and set(one.options) <= set(codecs.names())
    ]
    assert pickers == []
    assert "file_format" not in {one.name for one in bank.fields}


def test_a_bai2_connection_is_refused_by_name_and_csv_is_not():
    bank = _bank()
    shape = validate_fields(bank, {"label": "Chase", "source": "upload", "file_format": "bai2"}, {})
    assert "file_format" in {one.field for one in shape}
    own = BankLockboxFileAdapter().validate({"source": "upload", "file_format": "bai2"})
    assert [one.message_key for one in own if one.field == "file_format"] == [
        "integrations.field.bank_format"
    ]
    assert not [
        one
        for one in BankLockboxFileAdapter().validate({"source": "upload", "file_format": "csv"})
        if one.field == "file_format"
    ]


@pytest.mark.parametrize("fmt", ["ofx", "qbo", "qfx", "bai2", "camt053"])
def test_a_non_csv_lockbox_file_keeps_its_named_refusal(fmt):
    with pytest.raises(lockbox.BankFileError):
        lockbox.parse_remittance_file(b"anything", file_format=fmt)

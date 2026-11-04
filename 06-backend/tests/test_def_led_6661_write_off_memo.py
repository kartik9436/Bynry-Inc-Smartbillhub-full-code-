# ── Trace ──────────────────────────────────────────────
# Defect: DEF-LED-6661 — Finance > General ledger printed a write-off's database
#         UUID in the Journal memo: "Write-off 01a0d522-edd3-710f-84f7-16035e9aec91".
# Rules:  B14 rule 31 (no database id is ever the visible value of a field).
# Tests:  this file
# ───────────────────────────────────────────────────────
"""THE MEMO A CLERK READS NAMES AN ACCOUNT, NEVER A PRIMARY KEY.

⚠ **WHY A UNIT TEST ON THE COMPOSER AND NOT A WALK.** The memo is composed in
`apps.payments.ledger_seam` and stored on the journal entry; by the time the
Journal screen renders it, it is an opaque string that every assertion in the
suite reads as a perfectly good one. That is the defect's own escape reason.
Pinning the COMPOSER is the only place the uuid can be refused before it is
written, because once the entry is posted hard rule 4 makes it permanent.

**This test was proved RED before it was trusted green.** Against the code as
it shipped — `memo=f"Write-off {write_off.pk}"` — `test_the_memo_never_carries_a_uuid`
fails with:

    AssertionError: a uuid reached a clerk's memo: 'Write-off
    01a0d522-edd3-710f-84f7-16035e9aec91'
"""

import re

from apps.payments.ledger_seam import _write_off_memo, _write_off_memo_subject

#: Any uuid shape, so a change of primary-key flavour cannot slip past it.
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

PK = "01a0d522-edd3-710f-84f7-16035e9aec91"


class _Account:
    def __init__(self, account_no):
        self.account_no = account_no


class _WriteOff:
    def __init__(self, account_no):
        self.pk = PK
        self.id = PK
        self.account = _Account(account_no)


def test_the_memo_names_the_account_a_clerk_says_out_loud():
    assert _write_off_memo(_WriteOff("A-10432"), prefix="Write-off") == (
        "Write-off — account A-10432"
    )
    assert _write_off_memo(_WriteOff("A-10432"), prefix="Reversal of write-off") == (
        "Reversal of write-off — account A-10432"
    )


def test_the_memo_never_carries_a_uuid():
    for account_no in ("A-10432", "", None, "   "):
        for prefix in ("Write-off", "Reversal of write-off"):
            memo = _write_off_memo(_WriteOff(account_no), prefix=prefix)
            assert not UUID.search(memo), f"a uuid reached a clerk's memo: {memo!r}"


def test_an_unnamed_account_gives_a_bare_memo_rather_than_the_key():
    # `account_no` is blank on an account migrated under the 2026-08-27 ruling.
    # A blank must not reopen the defect by the back door, so the memo simply
    # has no subject — the entry's own `source_id` dimension still carries the
    # provenance.
    assert _write_off_memo(_WriteOff(""), prefix="Write-off") == "Write-off"
    assert _write_off_memo(_WriteOff(None), prefix="Write-off") == "Write-off"
    assert _write_off_memo_subject(_WriteOff("  A-9 ")) == "A-9"


def test_a_write_off_with_no_account_at_all_still_composes():
    class _Bare:
        pk = PK

    assert _write_off_memo(_Bare(), prefix="Write-off") == "Write-off"

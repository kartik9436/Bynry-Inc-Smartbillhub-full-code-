"""`DEF-CUS-10045` (PO 2026-10-11, SR-26-0027) — a build raised against a
MATCHED premises serves the register's town, state and ZIP on its `premises`
block, so New Connect step 2's read-only City / State / ZIP boxes are filled
instead of blank.

THE WORKED CASE: a request resolved to `P-00074 · 14 Willow Bend, Austin, TX
78704`. `GET /connections/{id}` served `id · premise_no · name · address`
and nothing else, so the wizard (which keeps those three boxes read-only over
a property on file, hard rule 8) drew them empty. It now serves `Austin`,
`TX` and `78704` from the premises row itself — the one home of an address.

A pure test of the one function both readers (list and detail) go through:
no database, because the block reads three plain columns of a row the caller
already loaded.
"""

from __future__ import annotations

from types import SimpleNamespace

from apps.metering import connection_reads


def _premises(**over: object) -> SimpleNamespace:
    row = {
        "id": "01a0c888-9999-7aaa-8bbb-ccccddddeeee",
        "premise_no": "P-00074",
        "name": "Willow Bend House",
        "address_line": "14 Willow Bend",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78704",
    }
    row.update(over)
    return SimpleNamespace(**row)


def test_matched_premises_serves_its_town_state_and_zip() -> None:
    block = connection_reads._premises_block(_premises())
    assert block == {
        "id": "01a0c888-9999-7aaa-8bbb-ccccddddeeee",
        "premise_no": "P-00074",
        "name": "Willow Bend House",
        "address": "14 Willow Bend",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78704",
    }


def test_a_part_the_register_does_not_hold_is_null_never_a_guess() -> None:
    block = connection_reads._premises_block(_premises(city="", state=None, postal_code=""))
    assert block is not None
    assert (block["city"], block["state"], block["postal_code"]) == (None, None, None)


def test_no_premises_is_still_the_whole_block_withheld() -> None:
    assert connection_reads._premises_block(None) is None

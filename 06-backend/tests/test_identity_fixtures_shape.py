# ── Trace ──────────────────────────────────────────────
# Defects: DEF-2585 · DEF-2398 · DEF-2392 · DEF-3343 · DEF-2343 · DEF-3157 ·
#          DEF-3220 — the seven rows one fixture defect was filed under.
# Rules:   BR-CUS-1024 (no identifier, no account) · BR-CUS-1023 (the creation
#          minimum) · BR-CUS-1022 (identity is per kind) · BR-CUS-089 (the
#          MONEY test — this file asserts it is NOT widened)
# ───────────────────────────────────────────────────────
"""The shared fixture shape is CHECKED, not claimed (hard-won law 1).

`tests/identity_fixtures.py` makes three promises in prose. Each one is asserted
here, so a later edit that quietly breaks one goes RED instead of silently
turning twenty-nine suites into a different test than they were:

  1. what it produces is **enough to open an account** — `BR-CUS-1023`'s
     creation minimum returns "nothing missing", for both kinds;
  2. a person's default identifier is a **phone**, which is NOT one of
     `BR-CUS-1024`'s reuse identifiers and NOT enough for `BR-CUS-089`'s
     `strong` tier — so no repaired fixture can reuse another's customer number
     and **$0.00** of anybody's deposit can follow one;
  3. it never invents an identity for a payload that presents no party, and
     never completes one a fixture stated on purpose — the refusal has to stay
     testable.

No database: every function under test is pure, and so is `creation_minimum`.
"""

from __future__ import annotations

import dataclasses

from apps.customers import identity_match
from apps.customers import sample_data as customers_sample
from tests import identity_fixtures


def _evidence(block):
    """Exactly what `services.refuse_account_without_identity` builds at the door.

    ⚠ **THE NAME IS PUT ON SEPARATELY AND THAT IS NOT A DETAIL.**
    `identity_match.from_payload` reads the `identity` sub-dict ONLY — it never
    sees `display_name` — so a mirror that forgets the `replace` reports
    `customer_name_missing` for a block that opens an account perfectly well. It
    did, on the first run of this file: two green-looking helpers and a test that
    was measuring its own mistake.
    """
    evidence = identity_match.from_payload(
        block.get("identity"), kind=identity_match.normalise_kind(block.get("kind"))
    )
    return dataclasses.replace(evidence, name=block.get("display_name"))


def test_a_person_block_is_enough_to_open_an_account():
    block = identity_fixtures.person_customer("Sarah Miller")
    assert identity_match.creation_minimum(_evidence(block)) is None, (
        "the shared person fixture no longer meets BR-CUS-1023's creation minimum, so every "
        "suite that opens an account through it is about to fail in SETUP again"
    )


def test_a_company_block_is_enough_to_open_an_account():
    block = identity_fixtures.company_customer("Ridge Coffee Co.")
    assert identity_match.creation_minimum(_evidence(block)) is None


def test_the_person_default_is_a_phone_and_a_phone_reuses_nobody_and_moves_no_money():
    """The whole reason the default is a phone rather than a Social Security number.

    `BR-CUS-1024` reuses a number on the name plus a GOVERNMENT identifier;
    `BR-CUS-089` needs a name, a date of birth and a government ID to move money.
    A phone is neither, so twenty-nine suites can share one constant without any
    of them touching another's customer row or another's deposit.
    """
    block = identity_fixtures.person_customer("Sarah Miller")
    assert set(block["identity"]) == {"phone"}
    assert "phone" not in identity_match.REUSE_ID_FIELDS[identity_match.KIND_PERSON], (
        "a phone has become a reuse identifier — the shared fixture constant would now let "
        "one suite's account take over another suite's customer number"
    )
    agreed = [identity_match.FACT_NAME, identity_match.FACT_PHONE]
    assert identity_match.tier_for(agreed, identity_match.KIND_PERSON) == "weak", (
        "a name and a phone now earn a strong tier — BR-CUS-089 is the signed MONEY test and "
        "this fixture must never widen it"
    )


def test_the_company_tax_id_is_the_one_the_demo_seed_already_writes():
    """One rule applied twice, not two lanes each deciding for themselves."""
    assert identity_fixtures.SAMPLE_COMPANY_TAX_ID == customers_sample.SAMPLE_COMPANY_TAX_ID


def test_the_person_phone_is_in_the_range_reserved_for_fiction():
    assert "555-" in identity_fixtures.SAMPLE_PERSON_PHONE


def test_with_identity_reads_the_name_off_the_contact_and_the_kind_off_the_type():
    payload = {
        "unit_id": "u",
        "account_type": "residential",
        "contact": {"full_name": "Alvarez, Rosa"},
    }
    out = identity_fixtures.with_identity(payload)
    assert out["customer"]["display_name"] == "Alvarez, Rosa"
    assert out["customer"]["kind"] == "person"
    assert "customer" not in payload, "with_identity mutated its caller's dict"

    company = identity_fixtures.with_identity(
        {"account_type": "commercial", "contact": {"full_name": "Ridge Coffee Co."}}
    )
    assert company["customer"]["kind"] == "company"
    assert set(company["customer"]["identity"]) == {"tax_id"}


def test_a_government_account_is_an_organisation_and_not_a_person():
    """`!= "residential"`, which is `sample_data`'s own reading (CR-062 J3/J4):
    asking a public works department for a driving licence is the bug."""
    assert identity_fixtures.customer_kind_for("government") == "company"
    assert identity_fixtures.customer_kind_for("industrial") == "company"
    assert identity_fixtures.customer_kind_for("residential") == "person"


def test_it_never_completes_a_block_a_fixture_stated_on_purpose():
    """The refusal must stay testable — `test_cr058_w1_one_customer_every_door.py`
    is full of payloads that are SUPPOSED to be refused."""
    stated = {
        "account_type": "residential",
        "contact": {"full_name": "Nameless Ned"},
        "customer": {"display_name": "Nameless Ned", "kind": "person"},
    }
    assert identity_fixtures.with_identity(stated) is stated


def test_it_invents_no_party_where_a_payload_presents_none():
    """`BR-CUS-1024`'s third row: no name presented, nothing failed to identify
    itself, and this helper does not decide who an account belongs to."""
    payload = {"unit_id": "u", "account_type": "residential", "opened_at": "2026-08-15"}
    assert "customer" not in identity_fixtures.with_identity(payload)

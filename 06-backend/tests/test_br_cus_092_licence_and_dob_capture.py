# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-092(a) FINISHED — PO ruling 2026-09-15, verbatim: *"ensure
#           user is able to inputs both these on step 1 - Date of birth and
#           driver's licence on step 1 ... rewrite this rules if required"*.
#           ⚠ The permission to rewrite is recorded and DECLINED as unnecessary,
#           for the SECOND time on this rule (the first was 2026-08-24). Clause
#           (a) has read "both identifiers are captured on the service request"
#           since 2026-08-24; this is the half the 2026-08-31 amendment said was
#           outstanding. NOTHING IS SUPERSEDED.
# Rules:    BR-CUS-092 (a) captured · (b) app-layer encrypted · (c) LAST FOUR
#           ONLY on every read path, never in a list response, an export, a log
#           line or an audit `details` blob · (d) the "stored encrypted" claim is
#           earned · BR-CUS-089 (name + date of birth + one government ID) ·
#           BR-CUS-1020 (the date of birth is a PLAIN date and why) ·
#           BR-CUS-1022 (a company is never asked for a licence and has no date
#           of birth) · OQ-016 CLOSED (PO R6) · B2 §6 · hard rule 1 (RLS FORCE) ·
#           hard rule 7 · hard-won law 1 · hard-won law 2 (the hold's own test)
# Impacts:  apps/customers/{models,service_request_service,service_request_reads,
#           service_request_api,identity_match}.py · migration customers 0047
# ───────────────────────────────────────────────────────
"""🔒 **The second identifier, proved the way the first one was.**

The path under test is a SENSITIVE one (CLAUDE.md) — app-layer encryption of
customer PII. `HUMAN-REVIEW-PENDING`; the row naming what was shown to the PO in
plain English with a worked figure is in `12-governance/09-human-review-ledger.md`.

`tests/test_br_cus_092_ssn_capture.py` is this file's model and its four proofs
are deliberately repeated rather than referenced: the promise BR-CUS-092 makes
about the driving licence is the SAME promise it makes about the Social Security
number, and a second column that is only *assumed* to inherit it is how the
first one was skipped for three months.

  1 · **THE COLUMN IS READ BACK RAW** through a second cursor — not `.values()`,
      which applies `from_db_value` and would decrypt.
  2 · **ONLY THE LAST FOUR EVER LEAVE THE SERVER** — asserted as ABSENCE from
      the list row, the detail payload and the serialisation/export path.
  3 · **THE NUMBER NEVER REACHES A LOG, AN AUDIT ROW OR A REFUSAL MESSAGE.**
  4 · **A WRONG KEY FAILS CLOSED** — raises, never returns empty or cleartext.

AND FOUR MORE THAT THE SSN FILE HAS NO REASON TO CARRY:

  5 · **THE BLIND INDEX IS WRITTEN WITH THE VALUE AND MOVES WITH IT.** A
      ciphertext with no token is an applicant the matcher cannot see —
      unfindable, and every other test in this file still green.
  6 · **THE DATE OF BIRTH IS A PLAIN, COMPARABLE DATE** and is NOT masked.
  7 · **BR-CUS-1022 IS ENFORCED BY NAME** — a business is refused a licence and
      a date of birth rather than having them silently dropped.
  8 · **THE EVIDENCE SEAM ACTUALLY READS THEM** (hard-won law 2: built is not
      wired). `BR-CUS-089`'s criteria were signed and inert on this surface for
      three weeks because the form never asked; a column nothing reads would
      leave them exactly as inert with three more tests passing.

THE WORKED FIGURES, used throughout so a reader can follow one case:
**an applicant gives the licence `TX-1234882` and the date of birth 1988-03-14;
staff see `•••• 4882` and `03/14/1988`; the database row contains no `1234882`.**
"""

from __future__ import annotations

import datetime as dt
import json
import logging

import pytest
from django.db import connection
from django.test import override_settings

from core import crypto, errors

from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import service_request_api as sr_api
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The worked example from the review-ledger row. One licence, followed end to end.
LICENCE = "TX-1234882"
LAST_FOUR = "4882"
DOB = "1988-03-14"

#: Every spelling of the same secret that must NOT appear in stored bytes, a
#: payload, a log line or an audit blob. `4882` alone is deliberately NOT here —
#: the last four is exactly what we are allowed to disclose.
FORBIDDEN = ("TX-1234882", "TX1234882", "1234882", "TX-1234", "123488", "12348")

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "address_as_given": "14 Willow Bend, Springfield",
}


def _raw_column(request_id, column: str = "drivers_licence") -> str | None:
    """The bytes actually in the column, with NO field accessor.

    ⚠ **`ServiceRequest.objects.values(...)` WOULD NOT DO.** Django runs
    `from_db_value` for `values()` as well as for attribute access, so a
    `.values()` assertion decrypts and then proves the decrypted value contains
    the characters — which is true, and is the opposite of the guarantee.

    ⚠ `id` is stored un-hyphenated, so a `str(uuid)` bind matches NOTHING and
    this probe would report *"no row"* for a row that is right there — a false
    green. Measured in the SSN file, not assumed here.
    """
    key = getattr(request_id, "hex", None) or str(request_id).replace("-", "")
    with connection.cursor() as cur:
        # `CAST(... AS TEXT)`, not `::text` — this suite runs on SQLite as well
        # as PostgreSQL, and the Postgres-only cast made the probe RAISE rather
        # than answer, which reads exactly like a probe that found nothing.
        cur.execute(
            f"SELECT {column} FROM service_requests "  # noqa: S608 — a literal, not input
            "WHERE replace(CAST(id AS TEXT), '-', '') = %s",
            [key],
        )
        row = cur.fetchone()
    return row[0] if row else None


def _assert_no_secret_in(blob: object, where: str) -> None:
    text = json.dumps(blob, default=str)
    for spelling in FORBIDDEN:
        assert spelling not in text, f"{where} leaked {spelling!r}: {text[:400]}"


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 1 · THE STORED BYTES DO NOT CONTAIN THE NUMBER
# ═══════════════════════════════════════════════════════════════════════════
def test_proof1_the_raw_database_column_holds_no_part_of_the_licence(brazos, dana):
    """Read the column back RAW and assert the characters are not in it.

    The envelope is inspected as well as the absence, because *"the characters
    are missing"* is also true of an empty column and of a column that silently
    dropped the write — which is the state `DEF-632` was filed about.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        stored = _raw_column(request.id)

    assert stored, "nothing was stored: the write was dropped, not encrypted"
    for spelling in FORBIDDEN:
        assert spelling not in stored, f"raw column contains {spelling!r}"

    scheme, kid, nonce, sealed = stored.split(":", 3)
    assert scheme == crypto.SCHEME
    assert kid == crypto.active_kid()
    assert nonce and sealed
    assert crypto.decrypt(stored, context="service_requests.drivers_licence") == LICENCE

    # ⚠ RANDOMISED, not deterministic. The capture form is public-facing, so a
    # deterministic scheme would be a chosen-plaintext oracle over the value.
    with tenant_ctx(brazos):
        second = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        assert _raw_column(second.id) != _raw_column(request.id)


def test_proof1b_the_aad_binds_the_ciphertext_to_THIS_column(brazos, dana):
    """A value lifted out of `service_requests.drivers_licence` decrypts nowhere else.

    ⚠ **THE INTERESTING NEIGHBOUR IS `customers.driving_licence`**, which holds
    the same fact about the same person under a different column and a DIFFERENT
    SPELLING. Copy-paste between the two is the realistic mistake, and the AAD
    turns it into a loud failure instead of a quiet disclosure.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        stored = _raw_column(request.id)
    for foreign in ("customers.driving_licence", "service_requests.ssn", "tenants.ein"):
        with pytest.raises(crypto.FieldDecryptionError):
            crypto.decrypt(stored, context=foreign)


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 2 · ONLY THE LAST FOUR EVER LEAVE THE SERVER
# ═══════════════════════════════════════════════════════════════════════════
def test_proof2_no_read_path_serves_more_than_the_last_four(brazos, dana):
    """List row, detail payload and the serialisation/export path.

    **Asserted as ABSENCE FROM THE PAYLOAD, never as "masked in the UI".** A
    value that reaches the browser is in devtools, in a proxy log and in the HAR
    file a support engineer attaches to a ticket, whatever the screen draws.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(
            dana, {**CAPTURE, "drivers_licence": LICENCE, "date_of_birth": DOB}
        )

        row = reads.list_row(request)
        _assert_no_secret_in(row, "list_row")
        assert "drivers_licence" not in json.dumps(row)

        detail = reads.detail(request.id)
        _assert_no_secret_in(detail, "detail")
        identifier = detail["applicant"]["identifier"]
        assert identifier["drivers_licence_last4"] == LAST_FOUR
        assert identifier["drivers_licence_present"] is True
        # BR-CUS-092(d) — a FACT ABOUT THIS ROW, never a constant.
        assert identifier["drivers_licence_stored_encrypted"] is True

        # ⚠ **THE TWO STATED ABSENCES ARE GONE, IN THE SAME PAYLOAD.** Landing a
        # column and retiring the sentence that said it did not exist are two
        # acts and only the first feels like the work (hard-won law 2's mirror).
        assert "drivers_licence_absence" not in detail["applicant"]
        assert "date_of_birth_absence" not in detail["applicant"]
        # And the one that is STILL true is still there.
        assert detail["applicant"]["acting_for_absence"] == {"tracks": "DEF-638"}

        from django.core import serializers

        dumped = serializers.serialize("json", [request])
        for spelling in FORBIDDEN:
            assert spelling not in dumped, f"dumpdata leaked {spelling!r}"

        assert LAST_FOUR in json.dumps(detail), "the last four must be servable"


def test_proof2b_an_empty_licence_never_claims_to_be_encrypted(brazos, dana):
    """BR-CUS-092(d) in the negative: no value, no claim."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        identifier = reads.detail(request.id)["applicant"]["identifier"]
        assert identifier["drivers_licence_last4"] is None
        assert identifier["drivers_licence_present"] is False
        assert identifier["drivers_licence_stored_encrypted"] is False


def test_proof2c_the_hold_on_the_stored_encrypted_sentence_is_LIFTED(brazos, dana):
    """BR-CUS-092(d): the screen may say *"stored encrypted"* only once the
    column is live. It is live, so the server no longer declares the licence
    unavailable — and `serviceRequestShared.UNAVAILABLE.driversLicence` and the
    capture screen's fallback sentence go with the capture lane's own commit.
    """
    codes = {entry["code"] for entry in sr_api.SERVICE_REQUEST_UNAVAILABLE}
    assert "applicant_drivers_licence_not_captured" not in codes


def test_proof2d_there_is_still_no_general_purpose_encrypt_oracle():
    """⚠ **THE CARVE-OUT `crypto.py` DEMANDS, RE-ASSERTED FOR A SECOND COLUMN.**

    Its docstring: *"an oracle that will encrypt anything a stranger types is a
    chosen-plaintext oracle"*, and **the service-request form is public-facing**.
    So the capture module may encrypt THESE FIELDS ON THIS WRITE and offer
    nothing general — no `encrypt_field(name, value)`, no caller-chosen crypto
    context. The blind index is derived in `identity_match`, which owns both
    context tables, and the capture module names no context literal at all.
    """
    import inspect

    for module in (sr, reads, sr_api):
        source = inspect.getsource(module)
        assert "crypto.encrypt(" not in source, f"{module.__name__} calls encrypt() directly"
        assert "crypto.blind_index(" not in source, f"{module.__name__} builds index tokens"
    assert "crypto.last_four(" in inspect.getsource(reads)


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 3 · NOT IN A LOG, NOT IN AN AUDIT ROW, NOT IN A REFUSAL MESSAGE
# ═══════════════════════════════════════════════════════════════════════════
def test_proof3_the_audit_trail_carries_the_mask_and_never_the_licence(
    brazos, dana, audit_rows  # noqa: F811
):
    """**The sharpest of the four, because it fails silently.**

    `update_request` builds `before` from `getattr(request, "drivers_licence")`
    — the DECRYPTED attribute, because that is what an `EncryptedTextField`
    returns. Both blobs were cleartext, the row would write, nothing would
    raise, and the number would sit in `audit_log` forever.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        sr.update_request(dana, request.id, {"drivers_licence": "TX-9876543"})

    rows = [row for row in audit_rows if row["entity_type"] == "service_request"]
    assert rows, "hard rule 7 — the write must be audited at all"
    for row in rows:
        _assert_no_secret_in(row, f"audit_log[{row['action']}]")
        for spelling in ("TX-9876543", "TX9876543", "9876543"):
            assert spelling not in json.dumps(row, default=str)

    blob = json.dumps(rows, default=str)
    assert LAST_FOUR in blob and "6543" in blob
    # `TX-1234882` normalises to nine characters, so five are hidden and four
    # are shown — enough for a reviewer to tell one licence from another, never
    # enough to be the licence.
    assert crypto.mask(LICENCE) == "•••••4882"

    # ⚠ **AND THE BLIND-INDEX TOKEN IS NOT IN THE TRAIL EITHER.** It is not the
    # value, but it is an equality handle over it and nothing in `audit_log`
    # needs one.
    assert "bix1:" not in blob


def test_proof3b_the_audit_mask_covers_EVERY_encrypted_column_on_this_model():
    """**The forgetting test, and it is the reason this file exists twice.**

    Adding an encrypted identifier and adding it to `AUDIT_MASKED_FIELDS` are two
    acts, and only the first one feels like the work. An identifier left off the
    set writes to `audit_log` IN FULL, nothing raises, and nothing goes red —
    the exact shape of the defect `BR-CUS-092` was filed about.

    So this asserts the SET against the MODEL rather than against a list a lane
    has to remember to extend.
    """
    encrypted = {
        field.name
        for field in customers_models.ServiceRequest._meta.get_fields()
        if isinstance(field, crypto.EncryptedTextField)
    }
    assert encrypted, "the probe found no encrypted column at all — it is looking wrongly"
    missing = encrypted - set(sr.AUDIT_MASKED_FIELDS)
    assert not missing, (
        f"{sorted(missing)} is app-layer encrypted and is NOT masked into audit_log. "
        "BR-CUS-092(c): the full value is never in an audit `details` blob."
    )


def test_proof3c_nothing_logs_the_licence(brazos, dana, caplog):
    """Every log record emitted across a capture, an update and a read."""
    with caplog.at_level(logging.DEBUG):
        with tenant_ctx(brazos):
            request = sr.create_request(
                dana, {**CAPTURE, "drivers_licence": LICENCE, "date_of_birth": DOB}
            )
            sr.update_request(dana, request.id, {"applicant_phone": "555-0142"})
            reads.detail(request.id)
    captured = "\n".join(record.getMessage() for record in caplog.records)
    for spelling in FORBIDDEN:
        assert spelling not in captured, f"a log record leaked {spelling!r}"


def test_proof3d_a_refusal_message_carries_no_part_of_the_licence(brazos, dana):
    """**A validation error is rendered, logged, and pasted into tickets.**

    Every neighbouring validator in `_clean_capture` answers
    `params={"value": str(...)}`. This one may not, and the assertion is here so
    that copying the neighbour breaks the build rather than the promise.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            sr.create_request(dana, {**CAPTURE, "drivers_licence": "TX1"})
        rendered = json.dumps(
            {
                "key": caught.value.message_key,
                "params": getattr(caught.value, "params", None),
                "str": str(caught.value),
            },
            default=str,
        )
        assert caught.value.message_key == "customers.serviceRequest.driversLicenceTooShort"
        assert "TX1" not in rendered


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 4 · A WRONG KEY FAILS CLOSED
# ═══════════════════════════════════════════════════════════════════════════
def test_proof4_a_row_encrypted_under_one_key_raises_under_another(brazos, dana):
    """**Never empty, never the envelope, never cleartext — an exception.**

    Hard-won law 3, *defaults fail closed*. A field that swallowed a decryption
    failure and returned `None` would render as *"no licence on file"* and read
    as ordinary missing data; nobody would ever look.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        request_id = request.id

    other_key = "insecure-other:" + crypto._b64e(b"\x11" * crypto.KEY_BYTES)
    with override_settings(
        FIELD_ENCRYPTION_KEYS=other_key,
        FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=True,
    ):
        with tenant_ctx(brazos):
            with pytest.raises(crypto.FieldDecryptionError) as caught:
                customers_models.ServiceRequest.objects.get(id=request_id).drivers_licence
    assert "insecure-dev" in str(caught.value)

    with override_settings(FIELD_ENCRYPTION_KEYS="", FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False):
        with tenant_ctx(brazos):
            with pytest.raises(crypto.FieldEncryptionUnavailable):
                customers_models.ServiceRequest.objects.get(id=request_id).drivers_licence


def test_proof4b_a_randomised_column_refuses_equality_lookups(brazos, dana):
    """`filter(drivers_licence="TX-1234882")` can never match and must not answer
    quietly. An empty queryset here looks exactly like *"no such applicant"*,
    which on an identity match is the failure BR-CUS-089 can least afford."""
    from django.core.exceptions import FieldError

    with tenant_ctx(brazos):
        sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        with pytest.raises(FieldError, match="blind_index_candidates"):
            list(customers_models.ServiceRequest.objects.filter(drivers_licence=LICENCE))


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 5 · THE BLIND INDEX IS WRITTEN WITH THE VALUE AND MOVES WITH IT
# ═══════════════════════════════════════════════════════════════════════════
def test_proof5_the_index_token_is_written_and_finds_the_row(brazos, dana):
    """**This is why the column is worth capturing at all.**

    The ciphertext is randomised and unsearchable. Without the token the
    applicant is stored, invisible and permanently unmatchable — and every other
    test in this file would still pass.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        token = _raw_column(request.id, "drivers_licence_bidx")

    assert token and token.startswith(f"{crypto.INDEX_SCHEME}:{crypto.active_kid()}:")
    for spelling in FORBIDDEN:
        assert spelling not in token, "a blind index must leak equality and nothing else"

    candidates = crypto.blind_index_candidates(LICENCE, context="service_requests.drivers_licence")
    assert token in candidates

    # Punctuation and case are normalised for the INDEX and not for the stored
    # value, so an applicant who types the hyphen on Tuesday still matches.
    assert token in crypto.blind_index_candidates(
        "tx1234882", context="service_requests.drivers_licence"
    )
    with tenant_ctx(brazos):
        found = customers_models.ServiceRequest.objects.filter(
            tenant_id=request.tenant_id, drivers_licence_bidx__in=candidates
        )
        assert [row.id for row in found] == [request.id]


def test_proof5b_clearing_the_licence_clears_its_token(brazos, dana):
    """A stale token goes on matching a value the row no longer holds."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        assert _raw_column(request.id, "drivers_licence_bidx")
        sr.update_request(dana, request.id, {"drivers_licence": None})
        assert _raw_column(request.id, "drivers_licence_bidx") is None
        assert _raw_column(request.id) is None


def test_proof5c_updating_the_licence_moves_its_token(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        first = _raw_column(request.id, "drivers_licence_bidx")
        sr.update_request(dana, request.id, {"drivers_licence": "TX-9876543"})
        second = _raw_column(request.id, "drivers_licence_bidx")
    assert first != second
    assert second in crypto.blind_index_candidates(
        "TX-9876543", context="service_requests.drivers_licence"
    )


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 6 · THE DATE OF BIRTH IS A PLAIN, COMPARABLE DATE
# ═══════════════════════════════════════════════════════════════════════════
def test_proof6_the_date_of_birth_is_stored_as_a_date_and_served_in_full(brazos, dana):
    """`BR-CUS-1020`, verbatim: *"it must be COMPARABLE, `contacts.dob` is a
    plain date too, and `BR-CUS-092` names two identifiers of which it is not
    one."* So: a `date` on the attribute, the ISO string on the payload, and no
    mask anywhere — masking the one fact `BR-CUS-089` compares would make the
    rule unassessable again."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "date_of_birth": DOB})
        assert request.date_of_birth == dt.date(1988, 3, 14)
        detail = reads.detail(request.id)
        assert detail["applicant"]["date_of_birth"] == DOB
        # It is NOT under `identifier` — it is not one of BR-CUS-092's two.
        assert "date_of_birth" not in detail["applicant"]["identifier"]

    # And the column compares, which is the only thing it exists to do.
    with tenant_ctx(brazos):
        assert customers_models.ServiceRequest.objects.filter(
            id=request.id, date_of_birth__lt=dt.date(1990, 1, 1)
        ).exists()


def test_proof6b_a_date_that_is_not_a_date_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            sr.create_request(dana, {**CAPTURE, "date_of_birth": "last March"})
    assert caught.value.message_key == "customers.serviceRequest.dateOfBirthInvalid"


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 7 · REFUSED BY NAME — THE ALIASES, AND BR-CUS-1022's KINDS
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("dob", "date_of_birth"),
        ("driving_licence", "drivers_licence"),
        ("drivers_license", "drivers_licence"),
        ("dl", "drivers_licence"),
    ],
)
def test_proof7_an_alias_is_refused_WITH_THE_NAME_THAT_WORKS(brazos, dana, alias, canonical):
    """⚠ **`dob` USED TO ANSWER *"that identifier cannot be stored here"*, WHICH
    WAS TRUE AND STOPPED BEING TRUE ON 2026-09-15.** A refusal that has expired
    is worse than no refusal, because somebody believes it and goes away.

    ⚠ **AND `driving_licence` IS THE CUSTOMER TABLE'S OWN SPELLING.** Two
    spellings of one fact is a hazard this product has and is not fixing today —
    renaming either column moves every citation at once — so the refusal names
    the spelling THIS table uses instead of answering *"unknown field"*.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            sr.create_request(dana, {**CAPTURE, alias: "whatever"})
    assert caught.value.message_key == "customers.serviceRequest.useCanonicalFieldName"
    assert caught.value.params["canonical"] == canonical


@pytest.mark.parametrize("field", ["date_of_birth", "drivers_licence"])
def test_proof7b_a_business_is_refused_both_BY_NAME(brazos, dana, field):
    """`BR-CUS-1022` (PO 2026-09-01), verbatim: *"a company is never asked for a
    driving licence and a person is never asked for a Tax ID, refused BY NAME
    rather than dropped, because asking for both and leaving one blank turns a
    rule into a habit and the blank field eventually gets filled with
    something."* A company has no date of birth at all — that is the collision
    the rule resolves against `BR-CUS-089`.
    """
    value = DOB if field == "date_of_birth" else LICENCE
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            sr.create_request(dana, {**CAPTURE, "applicant_kind": "business", field: value})
    assert caught.value.message_key == "customers.serviceRequest.notAskedOfThisApplicant"
    assert caught.value.params["field"] == field


def test_proof7c_the_kind_on_the_ROW_decides_on_a_partial_update(brazos, dana):
    """A PATCH that sets only a licence says nothing about who the applicant is,
    so the row's own kind is what the gate reads — `customer_edit._validate`'s
    posture, and the same reasoning."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "applicant_kind": "business"})
        with pytest.raises(errors.BizError) as caught:
            sr.update_request(dana, request.id, {"drivers_licence": LICENCE})
    assert caught.value.message_key == "customers.serviceRequest.notAskedOfThisApplicant"


def test_proof7d_flipping_a_person_to_a_business_over_stored_identity_is_refused(brazos, dana):
    """The value would be stored, invisible and permanently unmatchable — the
    matcher for the new kind never reads that column. `identity_match.
    set_identifier` refuses the same move one field at a time on a customer."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "drivers_licence": LICENCE})
        with pytest.raises(errors.BizError) as caught:
            sr.update_request(dana, request.id, {"applicant_kind": "business"})
    assert caught.value.message_key == "customers.serviceRequest.notAskedOfThisApplicant"


def test_proof7e_a_person_is_still_asked_for_both(brazos, dana):
    """The gate narrows one kind and must not narrow the other. An unstated kind
    is `person`, which is the column's own default — and the capture screen has
    sent no kind since `CR-033`, so this is the case that actually runs."""
    with tenant_ctx(brazos):
        request = sr.create_request(
            dana,
            {
                "channel": "physical_form",
                "applicant_name": "Okonkwo, David",
                "address_as_given": "14 Willow Bend, Springfield",
                "drivers_licence": LICENCE,
                "date_of_birth": DOB,
            },
        )
        assert request.applicant_kind == "person"
        assert request.drivers_licence == LICENCE
        assert request.date_of_birth == dt.date(1988, 3, 14)


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 8 · BUILT IS NOT WIRED — THE EVIDENCE SEAM ACTUALLY READS THEM
# ═══════════════════════════════════════════════════════════════════════════
def test_proof8_the_identity_seam_lifts_all_three_facts(brazos, dana):
    """**Hard-won law 2.** `BR-CUS-089`'s criteria — *name + date of birth + one
    government ID* — were signed and INERT on this surface for three weeks
    because the form never asked, and `BR-CUS-1020` recorded the cost in as many
    words: *"until the request form captures a DOB, no match can be assessed
    against them."*

    A column nothing reads leaves them exactly as inert, with three more tests
    passing. So this asserts the SEAM, not the column.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(
            dana,
            {
                **CAPTURE,
                "applicant_phone": "555-0142",
                "ssn": "123-45-6789",
                "drivers_licence": LICENCE,
                "date_of_birth": DOB,
            },
        )
        evidence = identity_match.evidence_from_service_request(request)

    assert evidence.name == "Okonkwo, David"
    assert evidence.date_of_birth == DOB or evidence.dob == dt.date(1988, 3, 14)
    assert evidence.driving_licence == LICENCE
    assert evidence.ssn == "123-45-6789"
    # `BR-CUS-089` needs the licence OR the SSN; both are present and both are
    # government IDs for a PERSON (`identity_match.GOVERNMENT_ID_FIELDS`).
    assert set(evidence.identifiers()) >= {"ssn", "driving_licence"}


# ═══════════════════════════════════════════════════════════════════════════
# TENANT SCOPING — hard rule 1, because the columns are new
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_the_new_columns_sit_on_a_force_rls_table():
    """Hard rule 1, for three columns that did not exist yesterday.

    ⚠ **THIS DELIBERATELY DOES NOT RE-ASSERT ROW ISOLATION WITH AN ORM QUERY.**
    `tests/isolation_helpers.py` records why (DEF-101): a plain ORM query inside
    `tenant_ctx` runs as the app's SUPERUSER role and **bypasses RLS
    unconditionally**, so `filter(...).exists()` under another tenant proves
    nothing at all. Row isolation for `service_requests` is asserted under the
    non-superuser probe role in `tests/test_cr031_service_request.py`.

    What IS new and checkable here is the claim migration 0047 makes in its own
    docstring: **it adds no policy of its own** and the columns rely on the
    table's existing `FORCE` policy from migration 0018. A second policy on the
    same table is how a permissive OR-ed rule silently widens access, so the
    absence is the guarantee (hard-won law 1 — the comment is not the proof).
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = 'service_requests'"
        )
        rowsecurity, forced = cur.fetchone()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'service_requests' AND column_name IN "
            "('date_of_birth', 'drivers_licence', 'drivers_licence_bidx')"
        )
        columns = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT count(*) FROM pg_policies WHERE tablename = 'service_requests'")
        (policies,) = cur.fetchone()

    assert columns == {"date_of_birth", "drivers_licence", "drivers_licence_bidx"}, columns
    assert rowsecurity, "service_requests lost row-level security"
    assert forced, "RLS is not FORCEd — the table owner would bypass it"
    assert policies == 1, f"{policies} policies on service_requests — a second one OR-s in"

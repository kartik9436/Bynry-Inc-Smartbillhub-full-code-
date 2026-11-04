# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-632 (critical) — "We tell customers their Social Security number
#           is stored encrypted". PO ruling 2026-08-27, verbatim: *"We need to
#           capture SSN and encript it; we have to ensure it is working"*
# Rules:    BR-CUS-092 (a) captured · (b) written through the app-layer
#           encryptor · (c) LAST FOUR ONLY on every read path, and never in a
#           list response, an export, a log line or an audit `details` blob ·
#           (d) the "stored encrypted" claim is earned, not assumed ·
#           OQ-016 CLOSED (PO R6) · B2 §6 · hard-won law 1 · hard rule 7
# Impacts:  apps/customers/{models,service_request_service,service_request_reads,
#           service_request_api}.py · migration customers 0031
# ───────────────────────────────────────────────────────
"""**"Ensure it is working" is the requirement, and a passing test is not it.**

🔒 The path under test is a SENSITIVE one (CLAUDE.md) — app-layer encryption of
customer PII. `HUMAN-REVIEW-PENDING`; the row naming what was shown to the PO in
plain English with a worked figure is in `12-governance/09-human-review-ledger.md`.

Hard-won law 1: *a comment claiming a guarantee is not the guarantee.* The
product previously carried a screen that said *"Stored encrypted and shown to
staff as the last four digits only"* over a field that **went nowhere** — the
capture path refused fourteen identifier names outright. So this file does not
assert that encryption was *called*; it asserts the four things a customer is
actually being promised, and each is written so that it can only pass for the
right reason:

  1 · **THE COLUMN IS READ BACK RAW.** Not `.values()` — Django applies
      `from_db_value` to `values()` too, so that would decrypt and prove only
      that the accessor works. A **second, direct cursor** reads the `text`
      column and the submitted digits are asserted absent from what is stored,
      in every spelling a caller might have sent.
  2 · **ONLY THE LAST FOUR EVER LEAVE THE SERVER.** Asserted on the list row,
      the detail payload and the serialisation/export path — as ABSENCE from the
      payload, not as "masked in the UI". A number that reaches the browser is
      in devtools, in a proxy log and in the HAR file attached to a ticket,
      whatever the screen chooses to draw.
  3 · **THE NUMBER NEVER REACHES A LOG, AN AUDIT ROW OR A REFUSAL MESSAGE.**
      The audit blob is the sharp one: `update_request` builds `before` from
      `getattr(request, "ssn")`, which is the DECRYPTED attribute.
  4 · **A WRONG KEY FAILS CLOSED.** A row written under one key must RAISE under
      another — never return empty, never return the envelope, never fall
      through to cleartext.

THE WORKED FIGURE, used throughout so a reader can follow one number:
**an applicant types `123-45-6789`; staff see `••• ••• • 6789`; the database row
contains no `123`, no `456789` and no `123456789`.**
"""

from __future__ import annotations

import json
import logging

import pytest
from django.db import connection
from django.test import override_settings

from core import crypto, errors

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

#: The worked example from the review-ledger row. One number, followed end to end.
SSN = "123-45-6789"
DIGITS = "123456789"
LAST_FOUR = "6789"

#: Every spelling of the same secret that must NOT appear in stored bytes, a
#: payload, a log line or an audit blob. `123-45-6789` and `123456789` are the
#: obvious two; `12345` and `456789` catch a partial write, and `6789` alone is
#: deliberately NOT here — the last four is what we are allowed to disclose.
FORBIDDEN = (SSN, DIGITS, "123 45 6789", "12345", "456789", "123-45", "45-6789")

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "address_as_given": "14 Willow Bend, Springfield",
}


def _raw_column(request_id) -> str | None:
    """The bytes actually in `service_requests.ssn`, with NO field accessor.

    ⚠ **`ServiceRequest.objects.values("ssn")` WOULD NOT DO.** Django runs
    `from_db_value` for `values()` as well as for attribute access, so a
    `.values()` assertion decrypts and then proves that the decrypted value
    contains the digits — which is true, and is the opposite of the guarantee.
    A raw cursor is the only read in this codebase that sees the column.
    """
    # ⚠ `id` is stored un-hyphenated (`uuid7_pk` over a 32-char column), so a
    # `str(uuid)` bind matches NOTHING and this probe would report "no row"
    # for a row that is right there — a false GREEN on the tenant-scoping test
    # and a false RED here. Measured, not assumed.
    key = getattr(request_id, "hex", None) or str(request_id).replace("-", "")
    with connection.cursor() as cur:
        # `CAST(... AS TEXT)`, not `::text` — this suite runs on SQLite as well
        # as on Postgres, and the Postgres-only cast made the probe raise rather
        # than answer. A probe that errors reads exactly like a probe that found
        # nothing, which is how it first looked like a dropped write.
        cur.execute(
            "SELECT ssn FROM service_requests WHERE replace(CAST(id AS TEXT), '-', '') = %s",
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
def test_proof1_the_raw_database_column_holds_no_part_of_the_number(brazos, dana):
    """**Read the column back RAW and assert the digits are not in it.**

    This is the assertion the PO's *"ensure it is working"* is asking for, and
    it is the one that cannot be satisfied by a comment. The envelope is
    inspected as well as the absence, because "the digits are missing" is also
    true of an empty column and of a column that silently dropped the write —
    the state DEF-632 was filed about.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "ssn": SSN})

        stored = _raw_column(request.id)

    # It is THERE — a silently dropped SSN is DEF-632 wearing a different hat.
    assert stored, "nothing was stored: the write was dropped, not encrypted"

    # And it is NOT the number, in any spelling.
    for spelling in FORBIDDEN:
        assert spelling not in stored, f"raw column contains {spelling!r}"

    # And it is a real AES-GCM envelope bound to THIS column, not merely
    # something that happens to be unreadable: `sbh1:<kid>:<nonce>:<ct||tag>`.
    scheme, kid, nonce, sealed = stored.split(":", 3)
    assert scheme == crypto.SCHEME
    assert kid == crypto.active_kid()
    assert nonce and sealed
    assert crypto.decrypt(stored, context="service_requests.ssn") == SSN

    # ⚠ RANDOMISED, not deterministic — the same SSN twice must not produce the
    # same ciphertext. A deterministic scheme over a nine-digit domain fed by a
    # PUBLIC form is the chosen-plaintext oracle `crypto.py` warns about.
    with tenant_ctx(brazos):
        second = sr.create_request(dana, {**CAPTURE, "ssn": SSN})
        assert _raw_column(second.id) != _raw_column(request.id)


def test_proof1b_the_aad_binds_the_ciphertext_to_this_column(brazos, dana):
    """A value lifted out of `service_requests.ssn` does not decrypt elsewhere.

    That is what the additional authenticated data is for, and it turns a whole
    class of copy-paste into a loud failure instead of a quiet disclosure.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "ssn": SSN})
        stored = _raw_column(request.id)
    with pytest.raises(crypto.FieldDecryptionError):
        crypto.decrypt(stored, context="tenants.ein")


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 2 · ONLY THE LAST FOUR EVER LEAVE THE SERVER
# ═══════════════════════════════════════════════════════════════════════════
def test_proof2_no_read_path_serves_more_than_the_last_four(brazos, dana):
    """List row, detail payload and the serialisation/export path.

    **Asserted as ABSENCE FROM THE PAYLOAD, never as "masked in the UI".** The
    screen is the last place the value could be hidden and the first place it
    would already have been copied from.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "ssn": SSN})

        # (a) the LIST row — it must not carry the identifier at all.
        row = reads.list_row(request)
        _assert_no_secret_in(row, "list_row")
        assert "ssn" not in json.dumps(row)

        # (b) the DETAIL payload — last four, and that is the whole disclosure.
        detail = reads.detail(request.id)
        _assert_no_secret_in(detail, "detail")
        identifier = detail["applicant"]["identifier"]
        assert identifier["ssn_last4"] == LAST_FOUR
        assert identifier["ssn_present"] is True
        # BR-CUS-092(d) — the claim is a FACT ABOUT THIS ROW, so a screen can
        # never print "stored encrypted" over a blank.
        assert identifier["stored_encrypted"] is True

        # (c) the EXPORT / serialisation path. There is no service-request CSV
        # endpoint today (CR-045 wave E is where the missing exports land), so
        # the export surface that DOES exist is Django serialisation — a
        # fixture is an export, and `Field.value_to_string` normally reaches
        # through `value_from_object`, which returns the DECRYPTED attribute.
        from django.core import serializers

        dumped = serializers.serialize("json", [request])
        for spelling in FORBIDDEN:
            assert spelling not in dumped, f"dumpdata leaked {spelling!r}"

        # (d) belt and braces — EVERY string on the whole detail payload.
        assert LAST_FOUR in json.dumps(detail), "the last four must be servable"


def test_proof2b_an_empty_identifier_never_claims_to_be_encrypted(brazos, dana):
    """BR-CUS-092(d) in the negative: no value, no claim.

    A screen that draws *"stored encrypted"* from a constant would print it over
    a blank column, which is the exact false promise the rule was written about.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        identifier = reads.detail(request.id)["applicant"]["identifier"]
        assert identifier["ssn_last4"] is None
        assert identifier["ssn_present"] is False
        assert identifier["stored_encrypted"] is False


def test_proof2c_the_driving_licence_hold_has_EXPIRED_and_the_sentence_is_gone():
    """⚠ **THIS ASSERTION WAS INVERTED ON 2026-09-15, AND THAT IS ITS JOB.**

    It read *"the driving licence is still declared unavailable"* and was right
    until the PO ruled: *"ensure user is able to inputs both these on step 1 -
    Date of birth and driver's licence on step 1"*. **This is the hold-expiry
    test firing** — the thing CLAUDE.md's hard-won law 2 asks for in as many
    words: *"when you write a hold, write the test that fires when the hold
    expires, in the same commit"*.

    A stated absence is retired in the commit that makes it false. One commit
    later it is a screen telling a clerk a field does not exist over a field
    that works, and nothing in this repo can see that (`DEF-CWP-3925`).
    """
    codes = {entry["code"] for entry in sr_api.SERVICE_REQUEST_UNAVAILABLE}
    assert "applicant_drivers_licence_not_captured" not in codes
    assert "applicant_identifier_needs_an_encryptor" not in codes
    # ⚠ **AND THE ONES THAT ARE STILL TRUE ARE STILL THERE.** Retiring an
    # absence that has arrived and deleting one that has not are opposite acts,
    # and this list is where the difference shows.
    assert "no_customer_matcher" in codes


@pytest.mark.parametrize(
    "field",
    [
        "social_security_number",
        "gov_id",
        "gov_id_number",
        "id_number",
        "national_id",
        "ein",
        "tin",
        "gov_id_last4",
        "ssn_last4",
        "drivers_licence_last4",
        "acting_for",
    ],
)
def test_proof2d_every_other_identifier_name_is_still_refused(brazos, dana, field):
    """**Eleven names still answer `BIZ_STATE`, one by one.**

    ⚠ **`date_of_birth` AND `dob` LEFT THIS LIST ON 2026-09-15** on the PO's
    ruling of that date. `date_of_birth` is a `CAPTURE_FIELDS` member now;
    `dob` is refused as an ALIAS, with the canonical name in the message, which
    is a different refusal and is asserted in
    `tests/test_br_cus_092_licence_and_dob_capture.py`. Leaving them here would
    have been a test asserting a sentence the product had stopped saying.

    ⚠ `ssn_last4` and `drivers_licence_last4` are in this list DELIBERATELY.
    There is no `_last4` column of either kind — the last four is a read
    projection — and accepting a caller-supplied one would put four characters
    of the identifier in the clear beside the ciphertext while every other test
    in this file still passed.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            sr.create_request(dana, {**CAPTURE, field: "whatever"})
        assert caught.value.message_key == "customers.serviceRequest.identifierNotStorable"


def test_proof2e_there_is_no_general_purpose_encrypt_oracle():
    """⚠ **THE CARVE-OUT `crypto.py` DEMANDS, ASSERTED RATHER THAN PROMISED.**

    Its docstring: *"an oracle that will encrypt anything a stranger types is a
    chosen-plaintext oracle"*, and **the service-request form is public-facing**.
    So this module may encrypt THIS FIELD ON THIS WRITE and offer nothing
    general — no `encrypt_field(name, value)`, no caller-chosen crypto context.
    The only name `apps.customers` may hand to `crypto` is the literal on the
    model field.
    """
    import inspect

    for module in (sr, reads, sr_api):
        source = inspect.getsource(module)
        assert "crypto.encrypt(" not in source, f"{module.__name__} calls encrypt() directly"
        assert "crypto.blind_index(" not in source, f"{module.__name__} builds index tokens"
    # The read side may project, and that is all it may do.
    assert "crypto.last_four(" in inspect.getsource(reads)


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 3 · NOT IN A LOG, NOT IN AN AUDIT ROW, NOT IN A REFUSAL MESSAGE
# ═══════════════════════════════════════════════════════════════════════════
def test_proof3_the_audit_trail_carries_the_mask_and_never_the_number(
    brazos, dana, audit_rows  # noqa: F811
):
    """**The sharpest of the four, because it fails silently.**

    `update_request` builds `before` from `getattr(request, "ssn")` — the
    DECRYPTED attribute, because that is what an `EncryptedTextField` returns —
    and `after` from the cleaned payload. Both were cleartext, the row would
    write, nothing would raise, and the number would sit in `audit_log` forever.
    Masking happens at the `_audit` boundary so a new writer in this module
    cannot forget it.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "ssn": SSN})
        sr.update_request(dana, request.id, {"ssn": "987-65-4321"})

    # ⚠ **ASSERTED AT THE SINK, WHICH IS THE ONE PLACE A ROW CAN BE WRITTEN
    # FROM.** `core.audit.write_row` builds the dict, runs `jsonable()` over it
    # and hands it to `_sink` — a single INSERT and nothing else (BR-AUD-008).
    # So the dicts captured here are byte-for-byte what would reach `audit_log`,
    # and intercepting them is stricter than querying the table afterwards: it
    # sees every row, including ones a later assertion's filter would miss.
    rows = [row for row in audit_rows if row["entity_type"] == "service_request"]

    assert rows, "hard rule 7 — the write must be audited at all"
    for row in rows:
        _assert_no_secret_in(row, f"audit_log[{row['action']}]")
        for spelling in ("987-65-4321", "987654321"):
            assert spelling not in json.dumps(row, default=str)

    # And the mask IS there — a reviewer can still tell one identifier from
    # another, which is the whole reason it is masked rather than dropped.
    blob = json.dumps(rows, default=str)
    assert "6789" in blob and "4321" in blob
    assert crypto.mask(DIGITS) == "•••••6789"


def test_proof3b_nothing_logs_the_number(brazos, dana, caplog):
    """Every log record emitted across a capture and an update."""
    with caplog.at_level(logging.DEBUG):
        with tenant_ctx(brazos):
            request = sr.create_request(dana, {**CAPTURE, "ssn": SSN})
            sr.update_request(dana, request.id, {"applicant_phone": "555-0142"})
            reads.detail(request.id)
    captured = "\n".join(record.getMessage() for record in caplog.records)
    for spelling in FORBIDDEN:
        assert spelling not in captured, f"a log record leaked {spelling!r}"


def test_proof3c_a_refusal_message_carries_no_part_of_the_number(brazos, dana):
    """**A validation error is rendered, logged, and pasted into tickets.**

    Every neighbouring validator in `_clean_capture` answers
    `params={"value": str(...)}`. This one may not, and the assertion is here so
    that copying the neighbour breaks the build rather than the promise.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            sr.create_request(dana, {**CAPTURE, "ssn": "12"})
        rendered = json.dumps(
            {
                "key": caught.value.message_key,
                "params": getattr(caught.value, "params", None),
                "str": str(caught.value),
            },
            default=str,
        )
        assert caught.value.message_key == "customers.serviceRequest.ssnTooShort"
        assert "12" not in rendered.replace("092", "").replace("2026", "")


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 4 · A WRONG KEY FAILS CLOSED
# ═══════════════════════════════════════════════════════════════════════════
def test_proof4_a_row_encrypted_under_one_key_raises_under_another(brazos, dana):
    """**Never empty, never the envelope, never cleartext — an exception.**

    Hard-won law 3, *defaults fail closed*. A field that swallowed a decryption
    failure and returned `None` would render as *"no SSN on file"* and read as
    ordinary missing data; nobody would ever look. `sslmode=disable` and
    `ALLOWED_HOSTS=localhost` each reached production in this product because
    the safe option was the default.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "ssn": SSN})
        request_id = request.id

    other_key = "insecure-other:" + crypto._b64e(b"\x11" * crypto.KEY_BYTES)

    with override_settings(
        FIELD_ENCRYPTION_KEYS=other_key,
        FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=True,
    ):
        with tenant_ctx(brazos):
            with pytest.raises(crypto.FieldDecryptionError) as caught:
                customers_models.ServiceRequest.objects.get(id=request_id).ssn
    # It names the key it could not find rather than shrugging.
    assert "insecure-dev" in str(caught.value)

    with override_settings(FIELD_ENCRYPTION_KEYS="", FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False):
        with tenant_ctx(brazos):
            with pytest.raises(crypto.FieldEncryptionUnavailable):
                customers_models.ServiceRequest.objects.get(id=request_id).ssn


def test_proof4b_a_randomised_column_refuses_equality_lookups(brazos, dana):
    """`filter(ssn="123-45-6789")` can never match and must not answer quietly.

    An empty queryset here looks exactly like *"no such applicant"*, which on an
    identity match is the failure BR-CUS-089 can least afford.
    """
    from django.core.exceptions import FieldError

    with tenant_ctx(brazos):
        sr.create_request(dana, {**CAPTURE, "ssn": SSN})
        with pytest.raises(FieldError, match="blind_index_candidates"):
            list(customers_models.ServiceRequest.objects.filter(ssn=SSN))


# ═══════════════════════════════════════════════════════════════════════════
# TENANT SCOPING — hard rule 1, because the column is new
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_the_new_column_sits_on_a_force_rls_table(brazos, dana):
    """Hard rule 1, for a column that did not exist yesterday.

    ⚠ **THIS DELIBERATELY DOES NOT RE-ASSERT ROW ISOLATION WITH AN ORM QUERY.**
    `tests/isolation_helpers.py` records why (DEF-101): a plain ORM query inside
    `tenant_ctx` runs as the app's SUPERUSER role and **bypasses RLS
    unconditionally**, so `filter(...).exists()` under another tenant proves
    nothing at all. Row isolation for `service_requests` is asserted under the
    non-superuser probe role in `tests/test_cr031_service_request.py`, and
    duplicating it badly here would be a vacuous green.

    What IS new and is checkable here is the claim migration 0031 makes in its
    own docstring: **it adds no policy of its own** and the column relies on the
    table's existing `FORCE` policy from migration 0018. A second policy on the
    same table is how a permissive OR-ed rule silently widens access, so the
    absence is the guarantee.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = 'service_requests'"
        )
        rowsecurity, forced = cur.fetchone()
        cur.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'service_requests' AND column_name = 'ssn'"
        )
        (has_column,) = cur.fetchone()

    assert has_column == 1, "migration 0031 did not add the column"
    assert rowsecurity, "service_requests lost row-level security"
    assert forced, "RLS is not FORCEd — the table owner would bypass it"

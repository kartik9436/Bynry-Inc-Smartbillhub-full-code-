# ── Trace ──────────────────────────────────────────────
# Component: BE-12 — app-layer field encryption (core/crypto.py)
# Story:    BR-CUS-092 (PO 2026-08-24, settling DEF-632) · OQ-016 CLOSED (PO R6)
# Rules:    BR-CUS-092(b) app-layer encryptor · (c) last four only on every read
#           path · BR-CUS-089 (the match tiers a randomised column has to keep
#           serving) · CLAUDE.md hard-won law 3 (defaults fail closed) ·
#           hard-won law 7 (a guard is proved RED before it is trusted green)
# Impacts:  apps/tenancy/models.Tenant.ein · every future high-sensitivity column
# ───────────────────────────────────────────────────────
"""The encryptor's own contract, with no database in it.

These are the four decisions the human-review ledger row puts to the Product
Owner, one test group each, so a change to any of them goes RED rather than
quiet: WHERE THE KEY COMES FROM · WHAT HAPPENS WHEN IT IS ABSENT · ROTATION ·
RANDOMISED-NOT-DETERMINISTIC (and therefore the blind index).
"""

import pytest
from django.test import override_settings

from core import crypto

#: Two real 32-byte keys and one development key, written out rather than
#: generated, so a failure is reproducible and the rotation test can name the
#: kid it expects.
K1 = "k1:2B92tb4pfmdFrNtaRsR6oHt1e-ebXzMSle9MK4crk7I"
K2 = "k2:vCyCJbO7WsHjBZif9EKr06BSoLNwSS7Z3XEXQ4YQpMo"
DEV = "insecure-dev:REglBOqa8pf2qDnwnG7zH9Yajye7-QKSQ6mSaeZqqMM"

CTX = "tenants.ein"
SSN = "123-45-6789"

live = override_settings(FIELD_ENCRYPTION_KEYS=K1, FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False)
rotated = override_settings(
    FIELD_ENCRYPTION_KEYS=f"{K2},{K1}", FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False
)


# ── round trip ───────────────────────────────────────────────────────────────
@live
def test_round_trip_returns_exactly_what_went_in():
    token = crypto.encrypt(SSN, context=CTX)
    assert token != SSN
    assert crypto.decrypt(token, context=CTX) == SSN


@live
@pytest.mark.parametrize("value", [None, ""])
def test_absent_values_pass_through_unchanged(value):
    """`None` and `''` are not secrets. Encrypting them would break every
    `if not tenant.ein` in the product and protect nothing."""
    assert crypto.encrypt(value, context=CTX) == value
    assert crypto.decrypt(value, context=CTX) == value
    assert crypto.blind_index(value, context=CTX) == value
    assert crypto.blind_index_candidates(value, context=CTX) == []


@live
def test_the_envelope_names_its_scheme_and_its_key():
    scheme, kid, nonce, sealed = crypto.encrypt(SSN, context=CTX).split(":", 3)
    assert scheme == crypto.SCHEME
    assert kid == "k1" == crypto.active_kid()
    assert nonce and sealed


@live
def test_the_envelope_contains_no_fragment_of_the_cleartext():
    token = crypto.encrypt(SSN, context=CTX)
    for fragment in ("123456789", "123-45-6789", "6789", "123"):
        assert fragment not in token


# ── randomised, not deterministic — and how matching survives it ─────────────
@live
def test_the_same_value_encrypts_differently_every_time():
    """The property that makes the column unsearchable, asserted deliberately so
    nobody 'fixes' it into a deterministic scheme to make a query work."""
    tokens = {crypto.encrypt(SSN, context=CTX) for _ in range(20)}
    assert len(tokens) == 20
    assert {crypto.decrypt(t, context=CTX) for t in tokens} == {SSN}


@live
def test_blind_index_is_deterministic_so_matching_still_works():
    """BR-CUS-089: an applicant is matched against accounts they held before, ON
    THE IDENTIFIER. This is how — the ciphertext is never compared."""
    assert crypto.blind_index(SSN, context=CTX) == crypto.blind_index(SSN, context=CTX)
    assert crypto.blind_index("123-45-6780", context=CTX) != crypto.blind_index(SSN, context=CTX)


@live
def test_blind_index_ignores_the_punctuation_a_human_types():
    """Tuesday's `123-45-6789` and Thursday's `123456789` are one identifier."""
    typed = ["123-45-6789", "123456789", "123 45 6789", "123.45.6789"]
    assert len({crypto.blind_index(v, context=CTX) for v in typed}) == 1


@live
def test_blind_index_is_scoped_to_its_column():
    """The same SSN under two columns indexes differently, so a token lifted
    from one table cannot be used to probe another."""
    assert crypto.blind_index(SSN, context="a.b") != crypto.blind_index(SSN, context="c.d")


@live
def test_blind_index_leaks_nothing_but_equality():
    token = crypto.blind_index(SSN, context=CTX)
    assert token.startswith(f"{crypto.INDEX_SCHEME}:k1:")
    for fragment in ("123456789", "123-45-6789", "6789"):
        assert fragment not in token


@rotated
def test_blind_index_candidates_cover_every_key_so_old_rows_stay_findable():
    """A lookup after a rotation asks about BOTH keys — rows written under the
    retired key are still matched, without being rewritten."""
    candidates = crypto.blind_index_candidates(SSN, context=CTX)
    assert [c.split(":")[1] for c in candidates] == ["k2", "k1"]
    assert crypto.blind_index(SSN, context=CTX) == candidates[0]  # new writes use the active key


@rotated
def test_a_token_written_before_the_rotation_is_one_of_the_candidates():
    with override_settings(FIELD_ENCRYPTION_KEYS=K1):
        written_earlier = crypto.blind_index(SSN, context=CTX)
    assert written_earlier in crypto.blind_index_candidates(SSN, context=CTX)


# ── rotation of the ciphertext itself ────────────────────────────────────────
@live
def test_rotation_keeps_old_ciphertext_readable_and_writes_under_the_new_key():
    old = crypto.encrypt(SSN, context=CTX)
    assert old.split(":")[1] == "k1"
    with override_settings(FIELD_ENCRYPTION_KEYS=f"{K2},{K1}"):
        assert crypto.active_kid() == "k2"
        assert crypto.decrypt(old, context=CTX) == SSN  # still readable
        assert crypto.encrypt(SSN, context=CTX).split(":")[1] == "k2"  # new writes rotate


@live
def test_dropping_a_key_that_still_has_rows_fails_loudly_and_names_it():
    """Retiring a key too early is a data-loss event; it must announce itself."""
    old = crypto.encrypt(SSN, context=CTX)
    with override_settings(FIELD_ENCRYPTION_KEYS=K2):
        with pytest.raises(crypto.FieldDecryptionError) as exc:
            crypto.decrypt(old, context=CTX)
    assert "'k1'" in str(exc.value)


# ── fails closed ─────────────────────────────────────────────────────────────
@override_settings(FIELD_ENCRYPTION_KEYS="", FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False)
def test_no_key_configured_refuses_everything_and_stores_no_plaintext():
    """hard-won law 3. The unsafe option is not merely non-default; it does not
    exist. Every entry point raises, and none returns the value it was given."""
    for call in (
        lambda: crypto.encrypt(SSN, context=CTX),
        lambda: crypto.decrypt("sbh1:k1:aa:bb", context=CTX),
        lambda: crypto.blind_index(SSN, context=CTX),
        lambda: crypto.blind_index_candidates(SSN, context=CTX),
        crypto.active_kid,
    ):
        with pytest.raises(crypto.FieldEncryptionUnavailable) as exc:
            call()
        assert "SBH_FIELD_ENCRYPTION_KEYS" in str(exc.value)


@override_settings(FIELD_ENCRYPTION_KEYS=DEV, FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False)
def test_the_committed_development_key_cannot_be_used_outside_dev_settings():
    """`local.py` and `test.py` carry this key in the repo. The guard is that
    `base.py` leaves FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS False, so 'deploy with
    the dev key' is not a state this code can reach."""
    with pytest.raises(crypto.FieldEncryptionKeyError) as exc:
        crypto.encrypt(SSN, context=CTX)
    assert "development key" in str(exc.value)


@override_settings(FIELD_ENCRYPTION_KEYS=DEV, FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=True)
def test_the_development_key_works_when_a_dev_settings_module_allows_it():
    assert crypto.decrypt(crypto.encrypt(SSN, context=CTX), context=CTX) == SSN


@live
def test_a_wrong_key_raises_and_never_returns_a_value():
    token = crypto.encrypt(SSN, context=CTX)
    forged = "k1:" + K2.split(":", 1)[1]  # same kid, different key material
    with override_settings(FIELD_ENCRYPTION_KEYS=forged):
        with pytest.raises(crypto.FieldDecryptionError) as exc:
            crypto.decrypt(token, context=CTX)
    assert "failed authentication" in str(exc.value)


@live
def test_a_ciphertext_from_another_column_does_not_decrypt_here():
    """AAD binds a value to its column: moving it is a loud failure, not a read."""
    token = crypto.encrypt(SSN, context="customers.ssn")
    with pytest.raises(crypto.FieldDecryptionError):
        crypto.decrypt(token, context="tenants.ein")


@live
def test_a_tampered_envelope_is_refused():
    scheme, kid, nonce, sealed = crypto.encrypt(SSN, context=CTX).split(":", 3)
    flipped = ("B" if sealed[0] != "B" else "C") + sealed[1:]
    with pytest.raises(crypto.FieldDecryptionError):
        crypto.decrypt(f"{scheme}:{kid}:{nonce}:{flipped}", context=CTX)


@live
def test_a_plaintext_value_found_in_an_encrypted_column_is_refused_not_returned():
    """The single most important refusal in the module. A column the rules call
    high-sensitivity that holds a plain value is a DEFECT; returning it would
    make the product work perfectly while the encryption did nothing."""
    with pytest.raises(crypto.FieldDecryptionError) as exc:
        crypto.decrypt("123456789", context=CTX)
    assert "not returned as cleartext" in str(exc.value).replace("It is NOT", "not")


@live
@pytest.mark.parametrize(
    "bad",
    ["nokidhere", "k1:not-base64!!:x", "K1:aaaa", "k1:" + "a" * 8, "k1"],
)
def test_a_malformed_key_setting_is_refused_rather_than_partially_used(bad):
    with override_settings(FIELD_ENCRYPTION_KEYS=bad):
        with pytest.raises(crypto.FieldEncryptionError):
            crypto.encrypt(SSN, context=CTX)


@live
def test_a_duplicate_kid_is_refused():
    with override_settings(FIELD_ENCRYPTION_KEYS=f"{K1},{K1}"):
        with pytest.raises(crypto.FieldEncryptionKeyError):
            crypto.encrypt(SSN, context=CTX)


@live
def test_a_context_is_required_and_may_not_contain_the_envelope_separator():
    for bad in ("", "tenants:ein"):
        with pytest.raises(crypto.FieldEncryptionError):
            crypto.encrypt(SSN, context=bad)


# ── BR-CUS-092(c): last four only ────────────────────────────────────────────
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123-45-6789", "6789"),
        ("123456789", "6789"),
        ("••• ••• • 4471", "4471"),
        ("D1234567", "4567"),
        ("789", "789"),
        ("", ""),
        (None, None),
    ],
)
def test_last_four_never_returns_a_fifth_character(value, expected):
    """BR-CUS-092(c) verbatim: *'every read path renders last four only'*.
    The screen that raised DEF-632 promises `••• ••• • 4471`; this is the four."""
    assert crypto.last_four(value) == expected


def test_last_four_of_a_real_ssn_carries_no_other_digit_of_it():
    assert crypto.last_four(SSN) == "6789"
    assert "12345" not in crypto.last_four(SSN)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("123456789", "•••••6789"), ("123-45-6789", "•••••6789"), ("89", "••"), ("", "")],
)
def test_mask_shows_four_and_hides_the_rest(value, expected):
    assert crypto.mask(value) == expected


# ── the Django field, exercised without a database ──────────────────────────
@live
def test_the_field_encrypts_on_the_way_in_and_decrypts_on_the_way_out():
    field = crypto.EncryptedTextField(crypto_context=CTX)
    stored = field.get_prep_value("123456789")
    assert stored.startswith(f"{crypto.SCHEME}:k1:")
    assert field.from_db_value(stored, None, None) == "123456789"


@live
def test_the_field_is_idempotent_so_the_backfill_can_be_run_twice():
    field = crypto.EncryptedTextField(crypto_context=CTX)
    once = field.get_prep_value("123456789")
    assert field.get_prep_value(once) == once


@live
def test_the_field_refuses_to_store_a_foreign_envelope_it_cannot_verify():
    """Structure alone is not proof. A `sbh1:…` string that does not decrypt for
    THIS column is rejected rather than stored as it stands."""
    field = crypto.EncryptedTextField(crypto_context="tenants.ein")
    foreign = crypto.encrypt("123456789", context="customers.ssn")
    with pytest.raises(crypto.FieldDecryptionError):
        field.get_prep_value(foreign)


def test_the_field_will_not_be_declared_without_naming_its_column():
    """`crypto_context` is required so a table rename can never silently change
    the AAD and make every existing row undecryptable."""
    with pytest.raises(ValueError):
        crypto.EncryptedTextField()


@live
def test_the_field_deconstructs_with_its_context_so_migrations_keep_it():
    _, path, _, kwargs = crypto.EncryptedTextField(crypto_context=CTX).deconstruct()
    assert path.endswith("core.crypto.EncryptedTextField")
    assert kwargs["crypto_context"] == CTX


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-092@2026-08-24 (PO ruling settling DEF-632 · OQ-016 CLOSED, B2 §6)
# generated: 2026-08-24 by the BR-CUS-092 field-encryption lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒)
# gates: ruff✔ black✔ pytest✔
# exceptions: no database in this file by design — the at-rest, audit, log and export leak guards live in tests/test_br_cus_092_ein_encryption.py where a real row exists
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

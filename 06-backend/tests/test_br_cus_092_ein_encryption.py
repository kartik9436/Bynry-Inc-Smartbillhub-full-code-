# ── Trace ──────────────────────────────────────────────
# Story:    BR-CUS-092(b) — "`tenancy.ein` migrates onto it as the SECOND
#           CALLER, because a helper with one caller is exactly how the first
#           one was skipped" · DEF-632
# Rules:    OQ-016 CLOSED (PO R6, B2 §6) · BR-CUS-092(b)(c) · BR-TEN-018 (the
#           EIN's own display rule — the reason this column is display-exempt
#           where an SSN is not) · BR-AUD-006 (identifiers enter the trail
#           masked) · CLAUDE.md hard rule 7 (the audit row is a read path)
# Tests:    this file is the guard. Every assertion here was shown RED against
#           the plain-text column before the encryptor existed — see the
#           lane report; the at-rest test failed with the literal
#           `assert '743182640' not in '743182640'`.
# ───────────────────────────────────────────────────────
"""The EIN is app-layer encrypted at rest, and its cleartext reaches no output.

WHAT THIS FILE IS ACTUALLY GUARDING, IN ONE SENTENCE: the nine digits a utility
types into Settings → Company must exist as those digits in exactly two places —
the screen (BR-TEN-018 says so) and process memory — and nowhere else that can
be read later.

⚠ WHY THE API-RESPONSE CHECK LOOKS INCONSISTENT WITH BR-CUS-092(c), AND IS NOT.
BR-CUS-092(c) requires LAST FOUR ONLY on every read path, and that clause is
about the SSN and the driver's licence. The EIN is a different column under a
different signed rule: BR-TEN-018 displays it `NN-NNNNNNN`, in full, on the S8
company tab, and `tests/test_us_ten_005_006_settings.py` has asserted that since
W0. Encrypting a column AT REST and masking its DISPLAY are two separate laws;
BR-CUS-092(b) applies the first to this column and says nothing about the
second. So the API assertion below pins what BR-TEN-018 requires and pins that
the CIPHERTEXT never leaks into the response either — and the last-four
projection BR-CUS-092(c) needs for the SSN is guarded in
tests/test_be12_field_encryption.py, over SSN-shaped values, because the SSN
COLUMN DOES NOT EXIST YET (apps/customers/ is another lane, and its capture path
still refuses every identifier field by name).
"""

import json
import logging

import pytest
from django.core import serializers
from django.core.exceptions import FieldError
from django.db import connection

from apps.tenancy import models, selectors, services
from core import crypto

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The exact figure carried into the human-review ledger row, so the number the
#: PO is shown and the number the guard asserts are the same number (CLAUDE.md
#: 🔒: "a test asserts the ratified figure so drift goes RED").
EIN_TYPED = "74-3182640"
EIN_CLEARTEXT = "743182640"
EIN_DISPLAYED = "74-3182640"  # BR-TEN-018
EIN_IN_AUDIT = "**-***2640"  # BR-AUD-006


def _raw_ein_column() -> list[str]:
    """What is ACTUALLY on disk — read past the ORM, which would decrypt it."""
    with connection.cursor() as cur:
        cur.execute("SELECT ein FROM tenants WHERE ein IS NOT NULL")
        return [row[0] for row in cur.fetchall()]


def _plant_plaintext_ein(value: str = EIN_CLEARTEXT) -> None:
    """Write nine plain digits the way every pre-migration row on a live host
    looks — past the field, which would encrypt them.

    The id is read BACK from the database rather than taken from `tenant.pk`:
    sqlite stores a UUID as 32 dash-less hex characters, so a `str(uuid)` bind
    parameter matches no row and the plant silently does nothing. That is how
    this helper was first written, and both backfill tests passed their planting
    step against an empty table before failing on the real assertion.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT id FROM tenants")
        ids = [row[0] for row in cur.fetchall()]
        assert ids, "no tenant row to plant an EIN on"
        for stored_id in ids:
            cur.execute("UPDATE tenants SET ein = %s WHERE id = %s", [value, stored_id])


def _save_ein(tenant):
    with tenant_ctx(tenant):
        return services.save_company_profile(
            admin_actor(),
            {"legal_name": "Brazos Bend Utility District No. 1", "ein": EIN_TYPED},
        )


# ── (b) the column is encrypted at rest ──────────────────────────────────────
def test_br_cus_092_b__ein_is_ciphertext_on_disk(growth_plan, identity_seam, audit_rows):
    """RED before the encryptor: the column held `743182640` verbatim."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)

    stored = _raw_ein_column()
    assert stored, "the save wrote no EIN at all — the test is not testing anything"
    for raw in stored:
        assert EIN_CLEARTEXT not in raw
        assert EIN_TYPED not in raw
        assert raw.startswith(f"{crypto.SCHEME}:"), raw[:16]


def test_br_cus_092_b__ciphertext_names_the_key_that_made_it(
    growth_plan, identity_seam, audit_rows
):
    """Rotation lives in the value: every envelope carries scheme + kid."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    scheme, kid, nonce, sealed = _raw_ein_column()[0].split(":", 3)
    assert scheme == crypto.SCHEME
    assert kid == crypto.active_kid()
    assert nonce and sealed


def test_br_cus_092_b__round_trip_through_the_orm_is_unchanged(
    growth_plan, identity_seam, audit_rows
):
    """The whole product keeps reading `tenant.ein` and getting nine digits.

    This is the compatibility claim the migration rests on: adopting the field
    changed no caller, so `test_us_ten_005_006_settings.py` still passes exactly
    as written.
    """
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    assert models.Tenant.objects.get(pk=tenant.pk).ein == EIN_CLEARTEXT


def test_br_cus_092_b__two_saves_of_the_same_ein_store_two_ciphertexts(
    growth_plan, identity_seam, audit_rows
):
    """Randomised, not deterministic — the property the blind index exists for."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    first = _raw_ein_column()[0]

    # NOT a second `save_company_profile`: BR-TEN-043 config writes are
    # forward-only and skip a field whose value has not changed, so the column
    # was never rewritten and this test passed vacuously on one ciphertext.
    # Writing the model directly is what actually re-encrypts.
    row = models.Tenant.objects.get(pk=tenant.pk)
    row.ein = EIN_CLEARTEXT
    row.save(update_fields=["ein"])
    second = _raw_ein_column()[0]
    assert first != second
    assert models.Tenant.objects.get(pk=tenant.pk).ein == EIN_CLEARTEXT


def test_br_cus_092_b__equality_lookup_is_refused_not_silently_empty(
    growth_plan, identity_seam, audit_rows
):
    """A randomised column that answers `filter(ein=…)` with `[]` is the worst
    possible failure: it reads as "no such tenant". It must raise instead."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    with pytest.raises(FieldError) as exc:
        list(models.Tenant.objects.filter(ein=EIN_CLEARTEXT))
    assert "blind_index_candidates" in str(exc.value)


# ── (c) the cleartext reaches no output ──────────────────────────────────────
def test_br_cus_092_c__cleartext_never_appears_in_a_log_line(
    growth_plan, identity_seam, audit_rows, caplog
):
    """Grep the whole captured log stream — messages, args and formatted text."""
    tenant, _ = provisioned_tenant()
    with caplog.at_level(logging.DEBUG):
        _save_ein(tenant)
        with tenant_ctx(tenant):
            selectors.company_profile()
        models.Tenant.objects.get(pk=tenant.pk).ein

    stream = "\n".join(
        [r.getMessage() for r in caplog.records]
        + [str(r.args) for r in caplog.records]
        + [caplog.text]
    )
    assert EIN_CLEARTEXT not in stream
    assert EIN_TYPED not in stream


def test_br_cus_092_c__cleartext_never_appears_in_the_audit_details_blob(
    growth_plan, identity_seam, audit_rows
):
    """CLAUDE.md hard rule 7 writes an audit row for every money action, so the
    `details` blob is a read path and BR-AUD-006 is what keeps it clean. Pinned
    here as well as in the US-TEN-005 suite, because it is now a SECURITY
    guarantee and not only a formatting rule."""
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    _save_ein(tenant)

    rows = [r for r in audit_rows if r["action"] == "settings.company_profile.updated"]
    assert rows
    blob = json.dumps(rows, default=str)
    assert EIN_CLEARTEXT not in blob
    assert EIN_TYPED not in blob
    assert EIN_IN_AUDIT in blob


def test_br_cus_092_c__cleartext_never_appears_in_a_serialised_export(
    growth_plan, identity_seam, audit_rows
):
    """A fixture dump IS an export, and it is the one that bites: Django's
    default `value_to_string` reaches through the model attribute, which is
    decrypted. RED before the field override: `dumpdata` wrote the nine digits
    straight into JSON."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)

    payload = serializers.serialize("json", [models.Tenant.objects.get(pk=tenant.pk)])
    assert EIN_CLEARTEXT not in payload
    assert EIN_TYPED not in payload
    assert f"{crypto.SCHEME}:" in payload


def test_br_cus_092_c__cleartext_never_appears_in_a_list_export_row(
    growth_plan, identity_seam, audit_rows
):
    """The other export shape: whatever a list/report writer serialises out of a
    tenant row. `values()` goes through `from_db_value`, so it decrypts — which
    is why the assertion is that no export writer NAMES this column, and the
    guard is that adding one makes this test fail."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    row = models.Tenant.objects.filter(pk=tenant.pk).values("id", "legal_name").first()
    assert EIN_CLEARTEXT not in json.dumps(row, default=str)


def test_br_cus_092_c__api_response_carries_the_br_ten_018_display_and_no_ciphertext(
    growth_plan, identity_seam, audit_rows
):
    """The rendered read path. BR-TEN-018 puts the EIN on screen in full and
    that is untouched (see this module's docstring); what must NOT be there is
    the envelope, which would leak the key id and be meaningless to a human."""
    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    with tenant_ctx(tenant):
        profile = selectors.company_profile()
    rendered = json.dumps(profile, default=str)
    assert profile["ein"] == EIN_DISPLAYED
    assert f"{crypto.SCHEME}:" not in rendered
    assert crypto.active_kid() not in rendered


# ── the backfill ─────────────────────────────────────────────────────────────
def test_br_cus_092_b__backfill_converts_a_row_written_as_plain_digits(
    growth_plan, identity_seam, audit_rows
):
    """The data migration's own logic, exercised against a row planted the way
    every pre-migration row on a live host looks: nine plain digits."""
    from apps.tenancy.migrations import (  # noqa: PLC0415 — the migration is the unit under test
        _0018_helpers as backfill,
    )

    tenant, _ = provisioned_tenant()
    _plant_plaintext_ein()
    assert _raw_ein_column() == [EIN_CLEARTEXT]  # planted, unencrypted
    converted = backfill.encrypt_plaintext_eins(connection)
    assert converted == 1
    assert _raw_ein_column()[0].startswith(f"{crypto.SCHEME}:")
    assert models.Tenant.objects.get(pk=tenant.pk).ein == EIN_CLEARTEXT

    # Idempotent — running it twice must convert nothing and break nothing.
    assert backfill.encrypt_plaintext_eins(connection) == 0
    assert models.Tenant.objects.get(pk=tenant.pk).ein == EIN_CLEARTEXT


def test_br_cus_092_b__backfill_reverse_returns_plain_digits(
    growth_plan, identity_seam, audit_rows
):
    """Reversible, and honestly so: `migrate tenancy 0017` puts the digits back
    rather than leaving unreadable ciphertext behind a rolled-back field."""
    from apps.tenancy.migrations import _0018_helpers as backfill  # noqa: PLC0415

    tenant, _ = provisioned_tenant()
    _save_ein(tenant)
    assert backfill.decrypt_eins_to_plaintext(connection) == 1
    assert _raw_ein_column() == [EIN_CLEARTEXT]


def test_br_cus_092_b__backfill_refuses_loudly_with_no_key(
    growth_plan, identity_seam, audit_rows, settings
):
    """hard-won law 3. With no key the backfill must STOP the deploy, not skip
    the rows and leave a column the product now believes is encrypted."""
    tenant, _ = provisioned_tenant()
    _plant_plaintext_ein()

    from apps.tenancy.migrations import _0018_helpers as backfill  # noqa: PLC0415

    settings.FIELD_ENCRYPTION_KEYS = ""
    with pytest.raises(crypto.FieldEncryptionUnavailable):
        backfill.encrypt_plaintext_eins(connection)
    assert _raw_ein_column() == [EIN_CLEARTEXT]  # untouched, not half-converted


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-092@2026-08-24 (PO ruling settling DEF-632 · OQ-016 CLOSED, B2 §6)
# generated: 2026-08-24 by the BR-CUS-092 field-encryption lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒)
# gates: ruff✔ black✔ pytest✔
# exceptions: the EIN keeps BR-TEN-018's full display — see this module's docstring; the SSN/driver's-licence read paths BR-CUS-092(c) governs do not exist yet (apps/customers/, another lane)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

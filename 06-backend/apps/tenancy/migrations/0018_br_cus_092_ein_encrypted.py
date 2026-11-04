# ── Trace ──────────────────────────────────────────────
# Story:    BR-CUS-092(b) (PO 2026-08-24, settling DEF-632) · OQ-016 CLOSED
#           (PO R6, B2 §6)   Screens: S8 Settings → Company (BR-TEN-018)
# Rules:    BR-CUS-092(b) — the app-layer encryptor, with `tenancy.ein` as its
#           SECOND caller · BR-TEN-018 (EIN display, UNCHANGED) · BR-AUD-006
#           (masked into the audit trail, UNCHANGED) · CLAUDE.md hard rule 1 ·
#           hard-won law 3 · DEF-639
# Tests:    06-backend/tests/test_br_cus_092_ein_encryption.py
# ───────────────────────────────────────────────────────
"""tenancy 0018 — `tenants.ein` stops being nine plain digits.

HUMAN-OWNED (🔒 migration ordering + sensitive-path data conversion).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09.
Row in 12-governance/09-human-review-ledger.md.

`OQ-016` has been CLOSED since B2 §6 — *"app-layer encryption for
high-sensitivity columns, disk for rest (PO R6)"* — and this column shipped
plain anyway, with a comment in `apps/tenancy/services.py` saying *"ein stored
as plain 9 digits for now"*. "For now" had no expiry, no owner and no test.
BR-CUS-092(b) closes it: the EIN becomes the SECOND caller of the encryptor,
*"because a helper with one caller is exactly how the first one was skipped"*.

NO DDL. `EncryptedTextField` IS a `TextField` — same `text` column, same
nullability. The `AlterField` exists so Django's field state matches the model
and `makemigrations --check` stays clean; it moves no bytes. What moves bytes is
the `RunPython` below.

NOT A DISPLAY CHANGE. BR-TEN-018 still puts the EIN on the S8 company tab as
`NN-NNNNNNN`, in full, and BR-AUD-006 still masks it into the audit trail.
Encrypting a column at rest and masking its display are two separate laws;
BR-CUS-092(b) applies the first to this column and says nothing about the second.

REVERSIBLE, and the reverse really restores plain digits — see
`_0018_helpers.decrypt_eins_to_plaintext`. Rolling back to 0017 re-creates the
DEF-632 exposure; that is what makes it a decision rather than a convenience.

⚠ THIS MIGRATION REFUSES WITHOUT `SBH_FIELD_ENCRYPTION_KEYS` (hard-won law 3),
and editing `.env.example` does not reach a host that already has a `.env`
(law 4). On every existing deployment the key must be added by hand BEFORE this
runs, or `migrate` stops here. That is deliberate: skipping the rows would leave
a column the product now believes is encrypted holding cleartext.
"""

from django.db import migrations

import core.crypto
from apps.tenancy.migrations import _0018_helpers as backfill


def forwards(apps, schema_editor):
    backfill.encrypt_plaintext_eins(schema_editor.connection)


def backwards(apps, schema_editor):
    backfill.decrypt_eins_to_plaintext(schema_editor.connection)


class Migration(migrations.Migration):

    dependencies = [("tenancy", "0017_br_ast_048_mapping_templates")]

    operations = [
        migrations.AlterField(
            model_name="tenant",
            name="ein",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="tenants.ein", null=True
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]

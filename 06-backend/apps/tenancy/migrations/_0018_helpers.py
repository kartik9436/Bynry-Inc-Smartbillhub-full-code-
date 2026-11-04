# ── Trace ──────────────────────────────────────────────
# Story:    BR-CUS-092(b) — "`tenancy.ein` migrates onto it as the second
#           caller, because a helper with one caller is how the first one was
#           skipped" · DEF-632 · OQ-016 CLOSED (PO R6, B2 §6)
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 4 (immutability —
#           `tenants` is not a financial document; this is a representation
#           change, not a correction) · hard-won law 3 (defaults fail closed) ·
#           DEF-639 (a data migration must not leave `app.tenant_id` blank)
# Tests:    06-backend/tests/test_br_cus_092_ein_encryption.py — the three
#           backfill tests call these two functions directly
# ───────────────────────────────────────────────────────
"""The EIN backfill, as importable functions rather than migration-local closures.

HUMAN-OWNED (🔒 migration ordering + a sensitive-path data conversion).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). Row in
12-governance/09-human-review-ledger.md.

WHY THIS IS A MODULE AND NOT A `RunPython` BODY
------------------------------------------------
`.github/workflows/migration-guard.yml` blocks modifying a committed migration,
and DEF-639 is on the record as a three-line fix that could not be applied
because it lived inside one. A conversion that can be IMPORTED can also be
TESTED before it is committed, and re-run by hand on a host where it half-ran.
0018 is a four-line file that calls these; the logic is here, under test.

WHY RAW SQL AND NOT THE HISTORICAL MODEL
-----------------------------------------
By 0018 the field IS `EncryptedTextField`, so reading `Tenant.objects` through
migration state would try to DECRYPT nine plain digits and raise on every row —
the conversion cannot use the ORM to read the values it exists to convert. Raw
SQL reads the column as it actually is.

⚠ TENANT CONTEXT — WHY NOTHING HERE SETS `app.tenant_id`, AND WHY THAT IS THE
SAFE ANSWER (CLAUDE.md hard rule 1, DEF-639)
-------------------------------------------------------------------------------
`tenants` is RLS-EXEMT by signed law: `06-backend/db/rls_tenancy_w0.sql` says so
in its own header — *"RLS-exempt here (platform tables per B2 §3): tenants
(membership-filtered at the app layer) · subscription_plans · services"* — and it
carries no ENABLE/FORCE statement and no policy. It is the tenant REGISTRY, not
a tenant-scoped table, so there is no per-tenant context to set and no policy to
satisfy: one UPDATE per row, scoped by primary key.

That is also why this file CANNOT reproduce DEF-639. The bug there is a data
step that ENDS by setting `app.tenant_id` to `''`, after which the deferred FK
validation casts `''::uuid` and a fresh database becomes un-buildable. Nothing
here sets the GUC at all, so whatever the session arrived holding — the nil-uuid
sentinel from `db/001_tenant_context_default.sql` on a provisioned database — it
still holds on the way out. The sentinel is left valid because it is never
touched. Verified below by assertion rather than by intention: `assert_tenant_
context_intact` reads the GUC before and after and refuses if the conversion
moved it.

⚠ AND IT REFUSES WITHOUT A KEY (hard-won law 3). A backfill that skipped the
rows it could not encrypt would leave a column the product now believes is
encrypted holding plain digits, and every later read would raise on data that
was silently left behind. So with no key configured this raises before it writes
anything: `migrate` stops, the deploy stops, and the message names the variable.
"""

from __future__ import annotations

from typing import Any

from core import crypto

#: The AAD the column's field declares. Must match `Tenant.ein`'s
#: `crypto_context` exactly or nothing written here will ever decrypt.
CONTEXT = "tenants.ein"


def _tenant_guc(connection: Any) -> str | None:
    """Whatever `app.tenant_id` currently is, or None where the GUC does not
    exist (sqlite, and a Postgres that has never been provisioned)."""
    if connection.vendor != "postgresql":
        return None
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.tenant_id', true)")
        row = cur.fetchone()
    return row[0] if row else None


def _assert_tenant_context_intact(connection: Any, before: str | None) -> None:
    """DEF-639, asserted rather than asserted-in-prose.

    A data migration that leaves `app.tenant_id` blank makes the next deferred
    FK validation cast `''::uuid` and a fresh database un-buildable. This
    conversion never sets the GUC, so the check is that it still holds what it
    held — and that it is not the empty string either way.
    """
    after = _tenant_guc(connection)
    if after != before:
        raise RuntimeError(
            f"the EIN backfill moved app.tenant_id from {before!r} to {after!r}. "
            "It must not: a blank tenant context makes the next foreign-key "
            "validation fail on ''::uuid and a fresh database un-buildable (DEF-639)."
        )
    if after == "":
        raise RuntimeError(
            "app.tenant_id is the empty string at the end of the EIN backfill. "
            "Leave the nil-uuid sentinel instead (db/001_tenant_context_default.sql, "
            "DEF-639)."
        )


def encrypt_plaintext_eins(connection: Any) -> int:
    """Rewrite every plain `tenants.ein` as an app-layer ciphertext. Returns the
    number of rows converted.

    IDEMPOTENT: a value that is already a valid envelope under a configured key
    is left exactly as it is, so re-running after a half-finished deploy converts
    only what is still plain. That is what makes this safe to run by hand.
    """
    before = _tenant_guc(connection)
    with connection.cursor() as cur:
        cur.execute("SELECT id, ein FROM tenants WHERE ein IS NOT NULL AND ein <> ''")
        rows = list(cur.fetchall())

    pending = [(pk, value) for pk, value in rows if not crypto.is_ciphertext(value)]
    if not pending:
        _assert_tenant_context_intact(connection, before)
        return 0

    # Raises FieldEncryptionUnavailable here, BEFORE the first UPDATE, so a
    # keyless deploy stops with nothing half-converted (hard-won law 3).
    crypto.active_kid()

    converted = 0
    with connection.cursor() as cur:
        for pk, value in pending:
            sealed = crypto.encrypt(value, context=CONTEXT)
            cur.execute("UPDATE tenants SET ein = %s WHERE id = %s", [sealed, str(pk)])
            converted += 1
    _assert_tenant_context_intact(connection, before)
    return converted


def decrypt_eins_to_plaintext(connection: Any) -> int:
    """The REVERSE. Returns the number of rows put back to plain digits.

    Reversible on purpose and honestly so: rolling back to 0017 restores a plain
    `TextField`, and leaving ciphertext behind a field that cannot decrypt it
    would turn a rollback into data loss. Rolling this back re-creates the
    DEF-632 exposure, which is the point of a rollback being a decision.
    """
    before = _tenant_guc(connection)
    with connection.cursor() as cur:
        cur.execute("SELECT id, ein FROM tenants WHERE ein IS NOT NULL AND ein <> ''")
        rows = list(cur.fetchall())

    pending = [(pk, value) for pk, value in rows if crypto.is_ciphertext(value)]
    restored = 0
    with connection.cursor() as cur:
        for pk, value in pending:
            plain = crypto.decrypt(value, context=CONTEXT)
            cur.execute("UPDATE tenants SET ein = %s WHERE id = %s", [plain, str(pk)])
            restored += 1
    _assert_tenant_context_intact(connection, before)
    return restored


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-092@2026-08-24 (PO ruling settling DEF-632 · OQ-016 CLOSED, B2 §6)
# generated: 2026-08-24 by the BR-CUS-092 field-encryption lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒)
# gates: ruff✔ black✔ pytest tests/test_br_cus_092_ein_encryption.py✔
# exceptions: `tenants` is RLS-exempt (db/rls_tenancy_w0.sql header, B2 §3), so no per-tenant app.tenant_id is set and none is cleared — DEF-639's mechanism is absent rather than avoided, and _assert_tenant_context_intact proves it per run
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

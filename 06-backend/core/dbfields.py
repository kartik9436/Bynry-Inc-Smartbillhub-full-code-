# ── Trace ──────────────────────────────────────────────
# Component: W0 model field kit (shared by apps.tenancy / apps.identity / apps.audit models)
# Contract:  B2 conventions header (uuidv7-style PKs named `id` · citext emails) ·
#            B2 r16 #5 (O-1 uuidv7 mechanics = Eng residue — app-side shim here) ·
#            DB-2 (uuidv7 PKs) · DB-15 (citext emails)
# Rules:     none enforced here — storage plumbing only; uniqueness/scoping laws live
#            on the models and their migrations
# Tests:     06-backend/tests/test_w0_models.py (uuid7 ordering + citext fallback)
# Impacts:   every W0 model PK · users.email / tenants.support_email columns
# ───────────────────────────────────────────────────────
"""Shared model-field plumbing for the W0 tables: the uuidv7 default and citext.

uuid7() — B2 mandates uuidv7-style PKs (DB-2). O-1 (pg_uuidv7 extension vs
shim on the target) remains an Eng residue per B2 r16 #5, so the PK default is
generated APP-SIDE with this RFC 9562 v7 shim: 48-bit unix-ms timestamp +
version/variant bits + random tail. Time-ordered like the DB function would
be, works identically on Postgres and the sqlite test database, and leaves the
DB-side `DEFAULT uuidv7()` a pure deploy-time addition when O-1 lands
(06-backend/db/000_extensions.sql carries that note).

CITextField — B2 types emails `citext` (DB-15). On Postgres the column is
created as citext (extension in 000_extensions.sql / tenancy 0001); on sqlite
it degrades to TEXT, which is why every case-insensitive uniqueness law is
ALSO expressed as a Lower() unique constraint on the model — the constraint,
not the column type, is what the tests and the law lean on (BR-IDN-029).
"""

import os
import time
import uuid

from django.db import models


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7: 48-bit unix-ms + ver 7 + 12 random + var + 62 random."""
    unix_ms = time.time_ns() // 1_000_000
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFF_FFFF_FFFF_FFFF
    value = (
        ((unix_ms & 0xFFFF_FFFF_FFFF) << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    )
    return uuid.UUID(int=value)


def uuid7_pk() -> models.UUIDField:
    """The one PK shape every B2 table uses: `id uuid PRIMARY KEY` (DB-2)."""
    return models.UUIDField(primary_key=True, default=uuid7, editable=False)


class CITextField(models.TextField):
    """citext on Postgres (B2/DB-15), plain TEXT elsewhere (sqlite tests)."""

    def db_type(self, connection) -> str:  # type: ignore[no-untyped-def]
        if connection.vendor == "postgresql":
            return "citext"
        return super().db_type(connection)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — W0 migrations lane)
# generated: 2026-08-09 by story-coder v1 (R1 critical path, W0 migrations)
# checklist: A✔ B=deferred(plumbing — story TCs live with the models/tests) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ py_compile✔ pytest tests/test_w0_models.py✔ · suite 180/180✔ (147 baseline + 33 W0) · run_gates✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: O-1 residue handled as app-side v7 shim (DB-side default = deploy-time, 000_extensions.sql note); citext degrades to TEXT on sqlite — case-insensitivity carried by Lower() constraints
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

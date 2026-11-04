# ── Trace ──────────────────────────────────────────────
# Change:   FB-022 on real PostgreSQL — the PROTECT foreign keys
#           `field_reads.photo_for_id` / `position_for_id` are enforced by the
#           database here, not only by Django's collector (hard-won law 14)
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""The same cases as `test_fb022_refused_reading_with_photo.py`, on PostgreSQL.

Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
        JOBS_EAGER=false pytest tests/test_fb022_refused_reading_with_photo_pg.py --ds=config.settings.pgtest
"""

from __future__ import annotations

import pytest

from tests.isolation_helpers import requires_postgres
from tests.test_fb022_refused_reading_with_photo import *  # noqa: F401,F403 — the cases and fixtures

pytestmark = [pytest.mark.django_db, requires_postgres]

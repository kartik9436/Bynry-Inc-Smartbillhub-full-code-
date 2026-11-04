# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10352 — the native sign-out releases the push token, on
#           PostgreSQL 16 (RLS FORCE on `technician_devices`; the release runs
#           in the sign-out's own transaction)
# ───────────────────────────────────────────────────────
"""Every case of `test_def_wrk_10352_sign_out_push.py` again, on PostgreSQL.

    DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
    DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh JOBS_EAGER=false \\
    pytest tests/test_def_wrk_10352_sign_out_push_pg.py --ds=config.settings.pgtest
"""

from __future__ import annotations

import pytest

from tests.isolation_helpers import requires_postgres
from tests.test_cr187_native_auth import field  # noqa: F401
from tests.test_def_wrk_10352_sign_out_push import *  # noqa: F401,F403 — every case, re-run here
from tests.test_def_wrk_10352_sign_out_push import two  # noqa: F401
from tests.test_us_idn_helpers import idn  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]

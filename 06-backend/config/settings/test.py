# ── THE FIXTURE'S CALENDAR IS PINNED FOR TESTS — DEF-LED-6640 (2026-09-25) ──
# `core/sample_fixture.py` used to hold its calendar as `date()` constants and
# now SHIFTS it by whole months so that today always falls inside the open,
# unbilled period (the defect: every period-scoped Finance screen read $0.00
# from 1 September on a full database). That makes the fixture depend on the
# wall clock, and a test suite that depends on the wall clock is a suite that
# fails on a date rather than on a change.
#
# So the suite pins the fixture to its ANCHOR DAY, which is the day the
# canonical calendar was drawn around. **At that day the offset is zero and the
# fixture reproduces the 2026 constants byte for byte** — June 1–30 billed,
# July 1–31 billed, August 1–14 read-and-unbilled, busy day 8 August — so every
# test written against those dates is unaffected and none was rewritten.
#
# ⚠ **THIS PIN MEANS THE SUITE PROVES NOTHING ABOUT THE TRAVELLING, AND THAT
# IS SAID OUT LOUD BECAUSE IT IS EXACTLY THE "check that cannot fail" SHAPE.**
# The travelling is proved instead by
# `tests/test_def_led_6640_the_calendar_travels.py`, which states the day it
# means for each case and never reads a clock. That test is the only place the
# shift is exercised; delete it and nothing else goes red.
#
# ⚠ **`setdefault`, NOT `=`** — a lane that exports `SBH_FIXTURE_TODAY` to look
# at another month keeps it, which is the whole point of the override.
import os as _os_fixture_pin

_os_fixture_pin.environ.setdefault("SBH_FIXTURE_TODAY", "2026-08-14")

from .base import *  # noqa

# Tests default to sqlite only until models exist; golden/isolation suites will
# force postgres (RLS is untestable on sqlite — see tests/test_tenant_isolation.py).
#
# ⚠ THIS LINE REPLACES `DATABASES` WHOLESALE, SO IT IGNORES `DATABASE_URL` —
# that is CLAUDE.md hard-won law 14, and it is why a `try/except IntegrityError`
# that is broken on PostgreSQL passes the entire suite here. It also means the
# per-checkout TEST database name base.py derives (DEF-054, see the block beside
# `DATABASES` there) does NOT apply under these settings and does not need to:
# in-memory SQLite is private to the process, so two concurrent runs cannot
# collide. The name matters only when a lane runs against real PostgreSQL, which
# is `DJANGO_SETTINGS_MODULE=config.settings.local`.
#
# ⚠ **AND `--reuse-db` WAS A NO-OP FOR THE WHOLE PROJECT UNTIL 2026-09-04
# (`DEF-GOV-3778`), WHICH COST EVERY LANE 2¼ MINUTES ON EVERY SINGLE RUN.**
# Django's SQLite backend builds its TEST database **in memory unless
# `TEST["NAME"]` is set** — a file in `NAME` is not enough, and `NAME` above is
# `:memory:` anyway. So there was never a database on disk to reuse: every
# `pytest --reuse-db` re-applied every migration from scratch. Measured on
# `tests/test_us_cwp_032_bills.py`: **133s before, 8.9s after** — 137 of those
# seconds were the first test's `setup`, which is where pytest attributes
# session database creation.
#
# `TEST["NAME"]` below fixes it, and the name carries a **digest of every
# migration file**, so the reuse is automatic and cannot go stale: add or edit
# a migration and the digest changes, the old file is not found, and the schema
# is rebuilt once. Nobody has to remember `--create-db`.
#
# ⚠ **THIS CHANGES WHERE THE TEST DATABASE LIVES AND NOTHING ELSE.** Same
# engine, same SQLite, so **hard-won law 14 is exactly as true as it was**:
# there is still no row-level security here, a `try/except IntegrityError` that
# is broken on PostgreSQL still passes this suite, and transaction-sensitive
# code still has to be proved under `config.settings.local`. Two concurrent
# runs no longer share a private in-memory database, so the digest is joined by
# the checkout path — two worktrees get two files.
import hashlib as _hashlib
import os as _os
import tempfile as _tempfile
from pathlib import Path as _Path

_MIGRATIONS = sorted(_Path(BASE_DIR).glob("apps/*/migrations/*.py"))  # noqa: F405
_STAMP = _hashlib.sha256(
    b"".join(p.read_bytes() for p in _MIGRATIONS) + str(BASE_DIR).encode()  # noqa: F405
).hexdigest()[:16]
#: ⚠ **ONE FILE PER CONCURRENT RUN, NOT ONE FILE FULL STOP — AND THE FIRST
#: VERSION OF THIS GOT IT WRONG (2026-09-05).** The in-memory database this
#: replaced was private to each process, so two `pytest` runs in one checkout
#: never met. A single shared file made them meet, and the second run failed 8
#: tests with `sqlite3.OperationalError: database is locked`. A 60-second busy
#: timeout did NOT fix it and was the obvious wrong answer: the contention is
#: not a brief write, it is each run FLUSHING the schema between tests, which
#: holds an exclusive lock the other cannot wait out.
#:
#: **So the runs take different SLOTS.** Each slot is a file plus a lock held
#: for the life of the process; a run takes the lowest free one. Sequential
#: runs all take slot 0 and reuse its schema — which is the whole point of the
#: speed-up — while a second concurrent run takes slot 1, builds once, and is
#: fast for every run after that. A lane in its own `git worktree` is unaffected
#: either way, because `BASE_DIR` is already in the digest.
_SLOTS = 8
_lock_handle = None  # held for the process's life; never closed


def _claim_slot() -> str:
    """The lowest test-database slot no other running process holds."""
    import fcntl

    global _lock_handle
    base = _os.path.join(_tempfile.gettempdir(), f"sbh-test-{_STAMP}")
    for slot in range(_SLOTS):
        handle = open(f"{base}-{slot}.lock", "a+b")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            continue
        _lock_handle = handle
        return f"{base}-{slot}.sqlite3"
    #: More than `_SLOTS` concurrent runs in one checkout: fall back to a
    #: private file rather than failing. It is slow (every migration re-applied)
    #: and correct, which is the right way round.
    return f"{base}-p{_os.getpid()}.sqlite3"


_TEST_DB = _claim_slot()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        #: The file `--reuse-db` reuses. Delete it, or add a migration, to
        #: rebuild — both happen by themselves.
        #:
        #: ⚠ **ONE FILE MEANS TWO `pytest` RUNS IN THE SAME CHECKOUT NOW SHARE
        #: A DATABASE, AND THAT IS A REAL COST OF THE SPEED-UP** (found within
        #: the hour, 2026-09-05): the in-memory database it replaced was
        #: private to each process, so overlapping runs never met. They meet
        #: now, and the second one saw `sqlite3.OperationalError: database is
        #: locked` on 34 tests.
        #:
        #: ⚠ **`timeout` WAS TRIED AS THE FIX FOR THAT AND IT DID NOT WORK** —
        #: measured, not assumed: the second run still failed 8 tests. It is
        #: kept because a busy timeout is right for an incidental write, but
        #: what actually solves it is `_claim_slot` above. Recording the failed
        #: attempt because the next person to meet a lock will reach for this
        #: number first, as I did.
        "TEST": {"NAME": _TEST_DB},
        "OPTIONS": {"timeout": 60},
    }
}

# A refusal raised with a `message_key` no catalogue defines reaches a clerk as
# SILENCE, not as an ugly key — the PO suppressed `params.detail` on 2026-08-19.
# ON HERE, and this is the setting that makes the check worth having: a lane
# writing a new refusal meets it in its OWN test run, seconds after typing the
# raise, instead of a gate meeting it after the branch has it. Off in base.py,
# for the reason recorded beside it there.
REFUSAL_KEYS_MUST_RESOLVE = True

# BE-07: the suite enqueues and runs as two deliberate steps — several ratified
# TCs (US-RAT-011 TC-1/TC-6) call the runner by hand after the accept, and
# eager dispatch would run those bodies twice. Tests that exercise the eager
# path turn it on for themselves with @override_settings(JOBS_EAGER=True).
JOBS_EAGER = False

# DEF-2487: the suite IS the worker. It enqueues and then runs the body by hand,
# so asking Celery whether a worker is alive would ask a broker that is
# deliberately not running and refuse every deferral case in this suite. OFF
# here and nowhere else — base.py leaves it True precisely so that a deployment
# cannot lose the check by getting one line wrong (hard-won law 3). The cases
# that PROVE the refusal turn it back on for themselves
# (tests/test_def2487_accounts_async_bar.py).
JOBS_REQUIRE_LIVE_WORKER = False

# App-layer field encryption (BR-CUS-092 / OQ-016). The suite needs a key or
# every tenant with an EIN refuses to save — correctly, per hard-won law 3. The
# same committed development key as config/settings/local.py, under the reserved
# `insecure-` prefix that base.py's FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS=False
# rejects everywhere else. Tests that exercise rotation, a wrong key or a missing
# key override this for themselves (tests/test_be12_field_encryption.py).
FIELD_ENCRYPTION_KEYS = "insecure-dev:REglBOqa8pf2qDnwnG7zH9Yajye7-QKSQ6mSaeZqqMM"  # noqa: F405
FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS = True

# CR-049 — the document store. The suite must not need a network or a bucket,
# so it writes to a temp directory. BOTH settings are needed to get here:
# base.py leaves DOCUMENT_STORAGE_ALLOW_FILESYSTEM False precisely so that a
# production deployment cannot reach local disk by getting one line wrong.
# Tests that exercise the AWS adapter inject a client
# (document_storage.set_s3_client_factory); tests that exercise the refusals
# override these for themselves.
DOCUMENT_STORAGE_BACKEND = "filesystem"
DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
DOCUMENT_STORAGE_DIR = str(BASE_DIR / "var" / "test-documents")  # noqa: F405

# EXPORT FILES — PO 2026-10-02: S3 in every environment, no filesystem stand-in.
# The suite reaches an S3 EMULATOR (`moto`) through the real boto3 client, wired
# in tests/conftest.py (`_export_store_on_s3_emulator`); this is the bucket that
# emulator creates. DOCUMENTS above stay on the filesystem backend — that is the
# document store's own, separate test arrangement, unchanged here.
DOCUMENT_STORAGE_BUCKET = "sbh-test-bucket"
DOCUMENT_STORAGE_REGION = "us-east-1"

# CR-110-BRC04 — the partner call limit's counter.
#
# base.py requires a SHARED counter (Redis), because a per-process count is
# what the PO's ruling was about: three gunicorn workers turned a ceiling of
# 100 a minute into 300. The suite has no Redis, so the default cache here is
# `LocMemCache` — shared by nothing.
#
# ⚠ OFF HERE AND NOWHERE ELSE, and that is deliberate rather than convenient:
# the tests that PROVE the refusal turn it back on for themselves
# (`tests/test_cr110_rate_limit_store.py`), and the four-process proof
# (`tests/test_cr110_shared_counter_pg.py`) points `CACHES` at the database
# cache so the counter is genuinely shared across real processes. A suite that
# simply left this True would refuse every partner request and prove nothing
# about the limit at all — law 7's *incapable of passing*.
INTEGRATION_SHARED_COUNTER_REQUIRED = False

# DEF-SHL-10621 — the application rate limits A1–A4 are OFF for the suite, for
# the reason the partner counter is: a suite that left them on would be
# throttled by its own fixtures (ten imports in a minute is an ordinary test
# file). `tests/test_def_shl_vapt_rate_limits.py` turns them back on and proves
# each refusal. An explicit `APP_RATE_LIMITS_ENABLED=true` in the environment
# still wins, so a whole-suite run WITH them is one variable away.
APP_RATE_LIMITS_ENABLED = _os.environ.get("APP_RATE_LIMITS_ENABLED", "false").lower() in ("1", "true", "yes")

# CR-144-BRC07 (X3) — the suite's `Client` speaks plain HTTP, so a `Secure`
# cookie would be set and never sent back, and every signed-in case in the
# product would fail with a refusal that names authentication rather than
# transport. OFF here; base.py leaves it True so a deployment cannot lose it by
# getting one line wrong.
#
# ⚠ The cases that PROVE the flag turn it back on for themselves
# (tests/test_cr144_cors_and_origin.py), which is the same posture as
# JOBS_REQUIRE_LIVE_WORKER and INTEGRATION_SHARED_COUNTER_REQUIRED above — a
# suite that simply left it True would prove nothing about it at all.
AUTH_COOKIE_SECURE = False

# CR-144-BRC07 (X1/X2) — the deployed shape, so the CORS and Origin-guard cases
# assert against a real pair of hosts rather than against emptiness. Every other
# test is unaffected: a same-origin call from `testserver` is always permitted,
# and a request with no `Origin` header — which is every `Client` call in this
# suite — is never examined (core/origin_guard.py says why).
CORS_ALLOWED_ORIGINS = ["https://app.bynry.com"]
ORIGIN_GUARD_ALLOWED_ORIGINS = ["https://app.bynry.com"]

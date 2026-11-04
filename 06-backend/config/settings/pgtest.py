"""RUN THE TEST SUITE AGAINST REAL POSTGRESQL. The one thing `test.py` cannot do.

⚠ **THIS EXISTS BECAUSE CLAUDE.md HARD-WON LAW 14 NAMES A CLASS OF BUG THE
DEFAULT SUITE CANNOT SEE, AND THEN GAVE NOBODY A WAY TO LOOK.** The law, in its
own words: *"any code that catches a database error and continues MUST be proved
on PostgreSQL, not on the default suite."* `config/settings/test.py` replaces
`DATABASES` wholesale with SQLite and says so at its own line 6. SQLite has no
aborted-transaction state, so

    try:
        ...
    except IntegrityError:
        continue

passes the ENTIRE suite green on every machine and loses the work at COMMIT the
first time a real row is refused in production. Two lanes found that
independently on 2026-08-29, in different modules, weeks apart, neither aware of
the other — which is what made it a law rather than a note.

**Until this module, obeying that law meant hand-rolling a settings file**, and
the one written on 2026-09-18 hardcoded a single shared test-database name —
which would have walked straight back into `DEF-054`: two lanes on one database,
one of them dropping it under the other, fifty minutes lost and an assertion
(`assert not self._finalizers`) that reads like a defect in whatever file happens
to be executing. A workaround everyone reinvents is a gap in the repo.

**WHAT IT CHANGES: the database, and nothing else.** Everything else — fixtures,
eager jobs, every other setting — comes from `test.py`
unchanged, so a suite run here differs from the ordinary one in exactly one
variable. That is the whole point: a difference in outcome is then attributable.

**THE TEST DATABASE NAME IS BASE.py's, NOT OURS**, and that is deliberate.
`base.py` derives `test_sbh_<checkout>_<hash>` per checkout precisely so a
`git worktree` — which isolates FILES and shares the DATABASE, one level worse
than sharing refs — cannot collide with the main tree. Re-deriving a name here
would silently opt out of a mitigation this repo already paid for once.

USE
    cd 06-backend
    set -a; . ./.env; set +a          # DATABASE_URL must be set; there is no default
    .venv/bin/pytest <paths> --ds=config.settings.pgtest --reuse-db

`--reuse-db` matters more here than on SQLite: the first run applies every
migration against a real server. Expect minutes, once.

WHAT IT IS NOT FOR. Not the default, and not a replacement for `test.py`: the
ordinary suite is faster and catches everything that is not transaction-shaped.
Reach for this when the code under test CATCHES a database error and carries on,
when it depends on a SAVEPOINT, when it asserts a constraint fires, or when a
row-level-security policy is the subject — RLS is untestable on SQLite, which
`test.py` line 3 already records.
"""

from .test import *  # noqa: F401,F403

# ── THE ONE OVERRIDE ────────────────────────────────────────────────────────
# Taken from `base.py` AFTER `test.py` has replaced it, so this is the real
# `DATABASE_URL` parsed by the repo's own `env.db()` and carrying base.py's
# per-checkout `TEST["NAME"]`. Imported inside the module body rather than at
# the top because `from .test import *` would otherwise overwrite it.
from .base import DATABASES  # noqa: E402,F401

if DATABASES["default"].get("ENGINE") != "django.db.backends.postgresql":
    # ⚠ FAIL CLOSED (hard-won law 3: the unsafe option must be the one you type).
    # A misread `DATABASE_URL` that quietly left SQLite in place would make this
    # module report a green run that proves NOTHING it exists to prove — law 7's
    # "incapable of failing" shape, wearing the name of the fix.
    raise RuntimeError(
        "config.settings.pgtest requires a PostgreSQL DATABASE_URL and got "
        f"{DATABASES['default'].get('ENGINE')!r}. This module exists to prove "
        "transaction behaviour that SQLite cannot express (CLAUDE.md law 14); "
        "running it on SQLite would be a green run proving nothing. Set "
        "DATABASE_URL (06-backend/.env) and try again."
    )

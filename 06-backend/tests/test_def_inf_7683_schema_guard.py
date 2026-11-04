# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INF-7683 (2026-09-28) — nobody could sign in at
#           smartbillhub.bynry.com. `POST /api/<slug>/auth/session` answered
#           500 over `UndefinedColumn: column
#           security_policies.absolute_session_hours does not exist`, while
#           `GET /api/health` answered `200 {"status":"ok"}` throughout, because
#           the rollout ran without the release task that migrates.
# Rules:    CLAUDE.md hard-won law 3 (defaults fail closed) · law 7 (prove a
#           guard RED first, and name what would make it pass wrongly).
# Component: core/schema_guard.py, called from 06-backend/docker-entrypoint.sh.
# Gate:     10-scripts/gates/g136_release_step_cannot_be_skipped.py
# ───────────────────────────────────────────────────────
"""Three states, and the one that refuses.

⚠ **THE POINT OF THIS FILE IS THE THIRD STATE.** `manage.py migrate --check`
exits 1 both when migrations are pending and when the database cannot be
reached — measured on PostgreSQL 16 on 2026-09-28, four ways:

    schema at tip                     → exit 0
    identity rolled back to 0005      → exit 1
    DATABASE_URL on a closed port     → exit 1
    DATABASE_URL naming a missing db  → exit 1

A boot guard written as `migrate --check || exit 1` therefore crash-loops the
whole service through a thirty-second failover. `test_unreachable_*` is what
stops a later "simplification" back to the one-liner.

⚠ **NO `django_db` MARKER ON THE PENDING AND UNREACHABLE CASES.** They drive
the verdict through a fake plan, because the test database is by definition
fully migrated and there is no way to make it stale from inside pytest without
mutating the shared database a sibling lane is using. The CURRENT case is the
one that talks to a real database, and it is the one that would notice if
`MigrationExecutor` moved under us.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError

from core import schema_guard
from core.schema_guard import SchemaStatus, SchemaVerdict


class _FakeMigration:
    def __init__(self, app_label: str, name: str) -> None:
        self.app_label = app_label
        self.name = name


#: The three that were actually unapplied during the outage, in order.
OUTAGE_PLAN = [
    (_FakeMigration("identity", "0006_cr145_session_settings"), False),
    (_FakeMigration("identity", "0007_cr145_withdraw_long_timeouts"), False),
    (_FakeMigration("identity", "0008_cr145_withdraw_long_timeouts_per_tenant"), False),
]

OUTAGE_NAMES = (
    "identity.0006_cr145_session_settings",
    "identity.0007_cr145_withdraw_long_timeouts",
    "identity.0008_cr145_withdraw_long_timeouts_per_tenant",
)


class _FakeExecutor:
    """Stands in for `MigrationExecutor` so a plan can be dictated."""

    def __init__(self, plan, raises=None):
        self._plan = plan
        self._raises = raises
        if raises is not None:
            raise raises

    class _Loader:
        class _Graph:
            @staticmethod
            def leaf_nodes():
                return [("identity", "0008_cr145_withdraw_long_timeouts_per_tenant")]

        graph = _Graph()

    loader = _Loader()

    def migration_plan(self, targets):
        return self._plan


def _patch_executor(monkeypatch, *, plan=None, raises=None):
    def factory(connection):
        return _FakeExecutor(plan or [], raises=raises)

    monkeypatch.setattr(
        "django.db.migrations.executor.MigrationExecutor", factory, raising=True
    )


class _Sink:
    """Collects the lines a caller prints, so they can be asserted on."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text):  # pragma: no cover - print() calls write twice
        if text.strip():
            self.lines.append(text.rstrip("\n"))

    def flush(self):  # pragma: no cover
        pass

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


# ── CURRENT ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_current_on_a_fully_migrated_database():
    """The real question against the real test database: nothing pending.

    This is the only case here that exercises `MigrationExecutor` itself, so it
    is what goes red if Django moves the API the guard is built on.
    """
    verdict = schema_guard.read_verdict()
    assert verdict.status is SchemaStatus.CURRENT
    assert verdict.pending == ()
    assert "0 unapplied migrations" in verdict.one_line()


@pytest.mark.django_db
def test_current_boots_and_still_says_something():
    """A guard that prints nothing when all is well cannot prove it ran."""
    sink = _Sink()
    verdict = schema_guard.enforce_at_startup(stream=sink)
    assert verdict.status is SchemaStatus.CURRENT
    assert "schema-guard:" in sink.text


# ── PENDING — the outage ────────────────────────────────────────────────────


def test_pending_names_every_unapplied_migration(monkeypatch):
    _patch_executor(monkeypatch, plan=OUTAGE_PLAN)
    verdict = schema_guard.read_verdict()
    assert verdict.status is SchemaStatus.PENDING
    assert verdict.pending == OUTAGE_NAMES
    assert verdict.is_stale


def test_pending_refuses_to_boot(monkeypatch):
    """THE ASSERTION THIS FILE EXISTS FOR.

    On 2026-09-28 this state booted, answered `200` to the balancer and `500`
    to every customer. It must now be a refusal.
    """
    monkeypatch.delenv(schema_guard.ALLOW_PENDING_ENV, raising=False)
    _patch_executor(monkeypatch, plan=OUTAGE_PLAN)

    with pytest.raises(ImproperlyConfigured) as raised:
        schema_guard.enforce_at_startup(stream=_Sink())

    message = str(raised.value)
    # It must name WHAT is wrong …
    for name in OUTAGE_NAMES:
        assert name in message
    # … and the command that fixes it, because at 3am that is the whole cost.
    assert "make release" in message
    assert "docker-release.sh" in message
    assert "showmigrations --plan" in message
    # … and it must not invite the one repair that is forbidden (CR-144 H4).
    assert "Do NOT make this container migrate" in message


def test_pending_boots_when_the_override_is_typed(monkeypatch):
    """Hard-won law 3 — the unsafe option is the one you type."""
    monkeypatch.setenv(schema_guard.ALLOW_PENDING_ENV, "1")
    _patch_executor(monkeypatch, plan=OUTAGE_PLAN)

    sink = _Sink()
    verdict = schema_guard.enforce_at_startup(stream=sink)

    assert verdict.status is SchemaStatus.PENDING
    assert "TOLERATED" in sink.text
    assert schema_guard.ALLOW_PENDING_ENV in sink.text
    # The tolerated state must list what is being assumed, on every boot, so it
    # cannot be left in a task definition quietly.
    for name in OUTAGE_NAMES:
        assert name in sink.text


def test_the_override_must_actually_say_yes(monkeypatch):
    """An empty or `0` value is not a grant — fail closed."""
    _patch_executor(monkeypatch, plan=OUTAGE_PLAN)
    for value in ("", "0", "false", "no", " "):
        monkeypatch.setenv(schema_guard.ALLOW_PENDING_ENV, value)
        granted, _who = schema_guard.allow_pending_is_typed()
        assert granted is False, f"{value!r} must not grant the override"


# ── UNREACHABLE — the state `migrate --check` cannot express ────────────────


def test_unreachable_is_neither_pass_nor_fail(monkeypatch):
    _patch_executor(
        monkeypatch,
        raises=OperationalError(
            'connection failed: connection to server at "127.0.0.1", port 5499 '
            "failed: Connection refused\n\tIs the server running on that host?"
        ),
    )
    verdict = schema_guard.read_verdict()
    assert verdict.status is SchemaStatus.UNREACHABLE
    assert verdict.pending == ()
    assert "NOT a pass and NOT a failure" in verdict.one_line()
    # One line in a boot log, not a psycopg paragraph.
    assert "\n" not in verdict.detail


def test_unreachable_warns_and_boots(monkeypatch):
    """A refusal here would turn a thirty-second failover into a crash loop.

    ⚠ This is the guard's declared blind spot, asserted so that it is a
    DECISION and not an accident: a stale schema behind an unreachable
    database boots exactly like a healthy one.
    """
    monkeypatch.delenv(schema_guard.ALLOW_PENDING_ENV, raising=False)
    _patch_executor(monkeypatch, raises=OperationalError("could not connect"))

    sink = _Sink()
    verdict = schema_guard.enforce_at_startup(stream=sink)  # must NOT raise

    assert verdict.status is SchemaStatus.UNREACHABLE
    assert "Booting anyway" in sink.text


def test_unreachable_does_not_swallow_a_programming_error(monkeypatch):
    """Only a CONNECTION failure is "we could not ask".

    A `ProgrammingError` means we reached the database and it refused the
    statement — that is a real fault and must not be laundered into the
    forgiving state. A bare `except Exception` here would do exactly that.
    """
    from django.db.utils import ProgrammingError

    _patch_executor(monkeypatch, raises=ProgrammingError("syntax error"))
    with pytest.raises(ProgrammingError):
        schema_guard.read_verdict()


# ── The verdict object itself ───────────────────────────────────────────────


def test_every_status_has_a_line_that_says_what_it_measured():
    """Hard-won law 7's third habit: output must distinguish pass from fail."""
    lines = {
        SchemaStatus.CURRENT: SchemaVerdict(SchemaStatus.CURRENT).one_line(),
        SchemaStatus.PENDING: SchemaVerdict(
            SchemaStatus.PENDING, pending=OUTAGE_NAMES
        ).one_line(),
        SchemaStatus.UNREACHABLE: SchemaVerdict(
            SchemaStatus.UNREACHABLE, detail="connection refused"
        ).one_line(),
    }
    assert len(set(lines.values())) == 3, "two states must never read alike"
    assert "3 unapplied" in lines[SchemaStatus.PENDING]
    assert "DEF-INF-7683" in lines[SchemaStatus.PENDING]

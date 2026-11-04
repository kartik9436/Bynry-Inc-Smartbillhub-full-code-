# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-027 (EP-INT-07) TC-1..6 — Silver Creek's `email_microsoft`,
#         `expires_at = 2026-09-12` seen on `2026-09-01`; the day-10 warning
#         not repeated; TC-3 history unbroken across v2; TC-4 the lapse.
#         CR-069 wave H task H4. Screens: S142 (frame 54.1) · S7
# Rules:  BR-INT-042 (a dated warning days ahead; a renewal path that keeps
#         the connection's WHOLE run history) · BR-INT-054 as amended
#         2026-09-06 (the sweep is a callable; scheduling is Runbooks') ·
#         BR-INT-003 (no secret anywhere) · BR-TEN-081 (the utility's clock)
# ───────────────────────────────────────────────────────
"""The last eleven days of a mailbox, and the day after.

⚠ THE DATES HERE ARE THE STORY'S OWN AND ARE LOAD-BEARING. `US-INT-027` states
the case as *`expires_at = 2026-09-12` on `2026-09-01`*, which is **eleven
days** — the figure frame 54.1 puts on the screen (*ELEVEN DAYS OF NOTICE*) and
the one the demo script reads aloud. Microsoft's manifest window is fourteen
days, so eleven is inside it and the warning is due. Changing either date
changes what the screen says, so they are named constants rather than inline
literals.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest

from apps.integrations import expiry, models, services
from tests.test_us_int_helpers_b import *  # noqa: F401,F403 — fixtures + request helpers
from tests.test_us_int_helpers_b import card, post_connect
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The story's own figures.
LAPSES_AT = datetime(2026, 9, 12, 17, 0, tzinfo=dt_timezone.utc)
ELEVEN_DAYS_BEFORE = datetime(2026, 9, 1, 17, 0, tzinfo=dt_timezone.utc)
THAT_DAY = date(2026, 9, 1)

MAILBOX = "email_microsoft"
MAILBOX_FIELDS = {"send_from": "billing@brazosbend.example"}


#: The recorded consent this suite stores. Named so `test_no_secret_reaches…`
#: can grep for the exact string rather than a lookalike.
CONSENT_V1 = "1.RECORDED-CONSENT-A17C"
CONSENT_V2 = "1.RECORDED-CONSENT-B28D"


def _connect_mailbox(tenant, actor):
    """A connected Microsoft mailbox with a consent that lapses on the 12th.

    ⚠ **CALL THIS OUTSIDE `tenant_ctx`, NEVER INSIDE ONE (DEF-2761).**
    `post_connect` is an API call and `core.tenancy.tenant_context` CLEARS on
    exit — correct for a request, which owns its connection for its whole life.
    So a `post_connect` nested inside a test's own context silently drops it,
    and everything after is refused by RLS with `no tenant context set`. The
    helper therefore opens its OWN short context for the direct service write
    and leaves the caller to open theirs afterwards.
    """
    answer = post_connect(tenant, actor, MAILBOX, MAILBOX_FIELDS)
    assert answer.status_code in (200, 201, 202), answer.data
    with tenant_ctx(tenant):
        connection = services.connection_for(tenant.id, MAILBOX)
        services.record_credential(
            actor=actor,
            connection=connection,
            payload=json.dumps({"refresh_token": CONSENT_V1}),
            masked_hint="••••A17C",
            expires_at=LAPSES_AT,
        )
    return connection


# ── TC-1 · the warning is due, and it carries the DATE ──────────────────────


def test_tc1_eleven_days_out_the_state_is_warning_and_carries_the_lapse_date(
    brazos, dana, microsoft_adapter
):
    """Eleven days before the 12th, the connection says *warning* and hands the
    screen the date — not a rendered sentence, the DATE."""
    connection = _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        view = expiry.view_for(connection, now=ELEVEN_DAYS_BEFORE)

    assert view.state == expiry.STATE_WARNING
    assert view.days_left == 11, "the story's own figure, and what frame 54.1 prints"
    assert view.expires_at == LAPSES_AT
    assert view.window_days == 14, "Microsoft's manifest window"
    # ⚠ The SERVER does not format the date. B14/BR-SHL-023 keep one formatting
    # path and it is the screen's, so a tenant on DD/MM/YYYY and one on
    # MM/DD/YYYY read the same row differently without a second code path.
    assert isinstance(view.as_dict()["expires_at"], str)
    assert "September" not in view.as_dict()["expires_at"]


def test_tc1b_the_card_the_screen_reads_carries_the_expiry_block(brazos, dana, microsoft_adapter):
    """S142 and the S7 strip both read `connection.expiry` — so the boundary
    between *warning* and *lapsed* is decided once, on the server."""
    _connect_mailbox(brazos, dana)
    payload = card(brazos, dana, MAILBOX)
    block = payload["connection"]["expiry"]
    assert set(block) == {"state", "expires_at", "days_left", "window_days", "version"}
    assert block["version"] == 1


# ── TC-2 · once a day, never twice ──────────────────────────────────────────


def test_tc2_the_second_sweep_on_one_day_writes_nothing_new(brazos, dana, microsoft_adapter):
    """The whole of *"once per day, never twice for the same day"*."""
    _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        first = expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)
        second = expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)

    assert first.warned == 1
    assert first.already_warned_today == 0
    assert second.warned == 0, "the same day must not warn twice"
    assert second.already_warned_today == 1, "and it says so rather than reporting nothing"


def test_tc2b_the_next_day_warns_again(brazos, dana, microsoft_adapter):
    """Once a day is once A DAY — tomorrow is a new day, and still inside the
    window, so the utility hears about it again."""
    _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)
        tomorrow = expiry.sweep_expiry(
            actor=dana,
            now=ELEVEN_DAYS_BEFORE + timedelta(days=1),
            today=THAT_DAY + timedelta(days=1),
        )
    assert tomorrow.warned == 1


# ── TC-3 · re-authorising keeps the WHOLE run history (the exit test) ───────


def test_tc3_v2_lands_on_the_same_connection_and_every_earlier_run_is_still_there(
    brazos, dana, microsoft_adapter
):
    """`BR-INT-042`'s second half, and `CR-069` §12's phase-3 exit test.

    Twenty runs before re-authorising, twenty runs after — on the SAME
    connection row, with v1 retained rather than overwritten.
    """
    connection = _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        for _ in range(20):
            run = services.start_run(
                connection=connection,
                operation="send_message",
                direction="outbound",
                trigger="dispatcher",
            )
            services.finish_run(
                run, attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True
            )
        before_id = connection.id
        before_runs = models.IntegrationRun.objects.filter(connection=connection).count()

        # Re-authorising: exactly what the OAuth return trip does.
        services.record_credential(
            actor=dana,
            connection=connection,
            payload=json.dumps({"refresh_token": CONSENT_V2}),
            masked_hint="••••B28D",
            expires_at=LAPSES_AT + timedelta(days=90),
        )

        after = services.connection_for(brazos.id, MAILBOX)
        rows = list(
            models.IntegrationCredential.objects.filter(connection=after).order_by("version")
        )
        after_runs = models.IntegrationRun.objects.filter(connection=after).count()

    assert after.id == before_id, "v2 lands on the SAME connection, never a second one"
    assert [one.version for one in rows] == [1, 2]
    assert [one.is_active for one in rows] == [False, True], "v1 retained, not overwritten"
    assert before_runs == 20
    assert after_runs == 20, "every earlier run is still listed on S142"


def test_tc3b_the_new_version_arrives_unwarned_so_the_box_clears_itself(
    brazos, dana, microsoft_adapter
):
    """The design point of putting `expiry_warned_on` on the CREDENTIAL.

    Nothing resets a flag on re-authorisation, because v2 has never been warned
    about and carries its own later date. A lane cannot forget a step that does
    not exist.
    """
    connection = _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)
        v1 = models.IntegrationCredential.objects.get(connection=connection, version=1)
        assert v1.expiry_warned_on == THAT_DAY

        services.record_credential(
            actor=dana,
            connection=connection,
            payload=json.dumps({"refresh_token": CONSENT_V2}),
            masked_hint="••••B28D",
            expires_at=LAPSES_AT + timedelta(days=90),
        )
        v2 = models.IntegrationCredential.objects.get(connection=connection, version=2)
        after = expiry.view_for(connection, now=ELEVEN_DAYS_BEFORE)

    assert v2.expiry_warned_on is None, "nothing had to remember to clear it"
    assert after.state == expiry.STATE_OK, "the warning is gone"
    assert after.version == 2


# ── TC-4 · the lapse ────────────────────────────────────────────────────────


def test_tc4_a_lapsed_consent_turns_the_connection_not_working(brazos, dana, microsoft_adapter):
    """Past the date, the card stops claiming to work — and `enabled` is
    untouched, so nothing queued is cancelled and the queue drains itself the
    moment somebody re-authorises."""
    after_lapse = LAPSES_AT + timedelta(hours=4)
    connection = _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        view = expiry.view_for(connection, now=after_lapse)
        outcome = expiry.sweep_expiry(actor=dana, now=after_lapse, today=date(2026, 9, 12))
        connection.refresh_from_db()

    assert view.state == expiry.STATE_LAPSED
    assert view.days_left == -1, "four hours past is one day past, not zero"
    assert outcome.lapsed == 1
    assert connection.status == models.STATUS_NOT_WORKING
    assert connection.enabled is True, "nothing is cancelled — BR-INT-016's discipline"


def test_tc4b_a_second_sweep_does_not_report_the_lapse_twice(brazos, dana, microsoft_adapter):
    """One event, one audit row — the reason `_mark_lapsed` returns a count."""
    after_lapse = LAPSES_AT + timedelta(hours=4)
    _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        expiry.sweep_expiry(actor=dana, now=after_lapse, today=date(2026, 9, 12))
        again = expiry.sweep_expiry(actor=dana, now=after_lapse, today=date(2026, 9, 13))
    assert again.lapsed == 0


# ── TC-5 · a password that does not expire is never warned about ────────────


def test_tc5_an_smtp_password_with_no_expiry_is_ok_for_ever(brazos, dana, smtp_adapter):
    """`expires_at IS NULL` is `ok` for ever, not `ok` for now. Warning about
    it would teach a clerk the box lies, and the next one they ignore would be
    the real one."""
    from tests.test_us_int_helpers_b import GOOD_PASSWORD, SMTP_FIELDS

    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    with tenant_ctx(brazos):
        connection = services.connection_for(brazos.id, "email_smtp")
        services.record_credential(
            actor=dana,
            connection=connection,
            payload=json.dumps({"password": GOOD_PASSWORD}),
            masked_hint="••••kbox",
            expires_at=None,
        )
        view = expiry.view_for(connection, now=ELEVEN_DAYS_BEFORE)
        # A century later it is still fine, because it does not expire.
        far = expiry.view_for(connection, now=ELEVEN_DAYS_BEFORE + timedelta(days=36500))
        outcome = expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)

    assert view.state == expiry.STATE_OK
    assert far.state == expiry.STATE_OK
    assert view.days_left is None
    assert outcome.looked_at == 0, "it is filtered out before the loop, not inside it"


# ── TC-6 · the calendar, and the refusal to guess one ───────────────────────


def test_tc6_a_sweep_with_no_readable_calendar_declines_rather_than_guessing(
    brazos, dana, microsoft_adapter, monkeypatch
):
    """A warning dated against the wrong calendar tells a utility its mailbox
    lapses on a day it does not. Declining is the honest answer."""
    from apps.integrations.seams import tenancy as tenancy_seam

    _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        monkeypatch.setattr(tenancy_seam, "today", lambda: None)
        outcome = expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE)
        credential = models.IntegrationCredential.objects.get(version=1)

    assert outcome.warned == 0
    assert outcome.declined is not None, "and it SAYS why rather than reporting a silent zero"
    assert credential.expiry_warned_on is None, "nothing was stamped against a guessed day"


# ── the rule that is not about dates at all ─────────────────────────────────


def test_the_sweep_writes_no_run_row(brazos, dana, microsoft_adapter):
    """`BR-INT-054`(3) — `IntegrationRun` records a CONNECTION's own activity
    with a far end. A sweep that read a column never dialled anybody, and rows
    saying so would make S142's runs table unreadable."""
    connection = _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)
        runs = models.IntegrationRun.objects.filter(connection=connection).count()
    assert runs == 0


def test_no_secret_reaches_the_card_or_the_audit_row(brazos, dana, microsoft_adapter, audit_rows):
    """`BR-INT-003`, asserted rather than asserted-about: the token string does
    not appear anywhere a screen or an auditor can read."""
    token = CONSENT_V1
    _connect_mailbox(brazos, dana)
    with tenant_ctx(brazos):
        expiry.sweep_expiry(actor=dana, now=ELEVEN_DAYS_BEFORE, today=THAT_DAY)
    payload = json.dumps(card(brazos, dana, MAILBOX), default=str)
    assert token not in payload
    assert "refresh_token" not in payload
    # `audit_rows` is the captured LIST itself, not a callable — it is an
    # autouse sink fixture. Every row is checked whole rather than only its
    # `after`: a secret that leaked into `before`, or into the entity id,
    # would be just as leaked and a narrower assertion would miss it.
    trail = json.dumps([str(one) for one in audit_rows], default=str)
    assert token not in trail
    assert "RECORDED-CONSENT" not in trail, "nor any consent string, however it was written"


def test_the_sweep_is_a_callable_and_not_a_schedule():
    """`BR-INT-054` as amended 2026-09-06 — scheduling is Runbooks'.

    ⚠ This asserts a BOUNDARY rather than a behaviour, which is unusual and is
    deliberate: the failure it guards against is a future lane quietly adding a
    schedule to this module, and no behavioural test would notice that.

    ⚠ **IT READS THE PARSED CODE, NOT THE TEXT, AND THE FIRST DRAFT DID NOT.**
    Written as a substring scan over `inspect.getsource`, it failed immediately
    — on `expiry.py`'s own docstring, which uses the words *"computes no
    `next_run_at`"* to EXPLAIN the boundary. A guard that cannot tell a
    prohibition from its own explanation would have had to be weakened or
    deleted by the next lane that touched the prose, and law 7's second habit
    is to ask what would make a check pass or fail wrongly. So it walks the AST
    and looks at identifiers a lane could actually execute.
    """
    import ast
    import inspect

    parameters = inspect.signature(expiry.sweep_expiry).parameters
    assert "now" in parameters, "the moment is the CALLER's (BR-TEN-043)"

    tree = ast.parse(inspect.getsource(expiry))
    reachable: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            reachable.add(node.id)
        elif isinstance(node, ast.Attribute):
            reachable.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            reachable.add(node.arg)

    for scheduling_name in ("next_run_at", "crontab", "cron_expression", "schedule", "beat"):
        assert scheduling_name not in reachable, (
            f"{scheduling_name!r} is executable in apps/integrations/expiry.py — "
            "deciding WHEN to sweep is scheduling and belongs to Runbooks (BR-INT-054 "
            "as amended 2026-09-06)"
        )

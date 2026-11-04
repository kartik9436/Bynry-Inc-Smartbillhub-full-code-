# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-024 (EP-INT-07) TC-1..7 — *"the wrong key pasted at 5 pm on a
#         Friday is a one-row undo"*. Screens: S141 · S142 (frame 54.2)
# Rules:  BR-INT-025 (versioned, never updated; ONE active, enforced by the
#         DATABASE; roll-back is one row) · BR-INT-003 (never rendered back,
#         logged or audited — masked hints only) · BR-INT-014 (rotation is a
#         lifecycle event → audit_log with masked refs) · B14 rule 33
# Tests:  TC-3 (the database refuses a second active row) is PostgreSQL's and
#         lives in tests/test_us_int_014_pg.py — the EXCLUDE is asserted there
#         against a real server and is never faked on SQLite.
# ───────────────────────────────────────────────────────
"""Rotation, roll-back, and the three exits a credential may not take.

⚠ THE HINTS IN THIS FILE ARE `••••kbox` AND `••••iday`, NOT THE STORY'S
`••••3F9A` / `••••A17C`, AND THE CODE IS RIGHT. A hint is DERIVED — the mask
plus the last four characters of the secret (`services._hint`, and `_masked`
refuses anything longer so the payload cannot ride the hint through the one
column a screen reads). The story's §4 pairs a password with an API key's
last four from a different figure in the design; the two cannot both be true.
The plaintexts `Ew3!kQ9-lockbox` and `wrong-key-friday` are load-bearing —
TC-6 greps for them — so the hints follow from them. Recorded in the decision
log for 2026-09-04 and stamped in the story.
"""

from __future__ import annotations

import json

import pytest

from apps.integrations import models, services
from core import errors
from tests.test_us_int_helpers_b import *  # noqa: F401,F403 — fixtures + request helpers
from tests.test_us_int_helpers_b import (
    GOOD_PASSWORD,
    SMTP_FIELDS,
    card,
    post_connect,
    post_credential,
    run_job,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FRIDAY_PASSWORD = "wrong-key-friday"
HINT_V1 = "••••kbox"  # Ew3!kQ9-lock*kbox*
HINT_V2 = "••••iday"  # wrong-key-fr*iday*


def _rows(connection):
    return list(
        models.IntegrationCredential.objects.filter(connection=connection).order_by("version")
    )


def test_tc1_replacing_the_password_writes_v2_deactivates_v1_and_audits_the_arrow(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows
):
    """v2 active, v1 retained inactive, `test()` re-run, and the audit row
    reads `••••kbox → ••••iday` and nothing else."""
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    answer = post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})
    assert answer.status_code in (200, 202)

    connection = services.connection_for(brazos.id, "email_smtp")
    rows = _rows(connection)
    assert [one.version for one in rows] == [1, 2]
    assert [one.is_active for one in rows] == [False, True]
    assert [one.masked_hint for one in rows] == [HINT_V1, HINT_V2]
    assert rows[0].rotated_at is not None and rows[1].rotated_at is None

    rotated = [one for one in audit_rows if one["action"] == services.AUDIT_CREDENTIAL_ROTATED]
    assert len(rotated) == 1
    assert rotated[0]["after"]["hints"] == f"{HINT_V1} → {HINT_V2}"
    assert rotated[0]["before"] == {"version": 1, "masked_hint": HINT_V1}
    # And nothing else: no payload, no plaintext, under any key.
    assert GOOD_PASSWORD not in json.dumps(rotated, default=str)
    assert FRIDAY_PASSWORD not in json.dumps(rotated, default=str)


def test_tc2_roll_back_reactivates_the_previous_version_in_one_row_and_nobody_reauthorises(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows
):
    """The 5 pm Friday undo. v1 active again, v2 retained, the connection back
    to *Not tested yet* — because the last test was taken against v2."""
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})

    with tenant_ctx(brazos):  # BE-01 — the API enters this; a direct call must too
        restored = services.rollback_credential(
            actor=dana, tenant_id=brazos.id, provider_key="email_smtp"
        )
    assert restored.version == 1

    connection = services.connection_for(brazos.id, "email_smtp")
    rows = _rows(connection)
    assert [one.version for one in rows] == [1, 2]
    assert [one.is_active for one in rows] == [True, False]  # v1 active again
    assert len(rows) == 2, "roll-back writes no third row — it re-activates one"
    assert connection.status == models.STATUS_UNTESTED
    assert connection.last_test_ok is None

    rolled = [one for one in audit_rows if one["action"] == services.AUDIT_CREDENTIAL_ROLLED_BACK]
    assert len(rolled) == 1
    assert rolled[0]["after"]["hints"] == f"{HINT_V2} → {HINT_V1}"


def test_tc4_roll_back_with_one_version_is_refused_in_five_words(brazos, dana, smtp_adapter):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        services.rollback_credential(actor=dana, tenant_id=brazos.id, provider_key="email_smtp")
    assert refusal.value.message_key == services.REFUSAL_NOTHING_TO_ROLL_BACK
    # The connection is untouched — a refusal writes nothing.
    connection = services.connection_for(brazos.id, "email_smtp")
    assert [one.is_active for one in _rows(connection)] == [True]


def test_tc5_roll_back_to_an_expired_version_is_refused_and_names_the_only_way_out(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """An expired previous credential would put the card back to *Working*
    against a secret the provider has already retired."""
    from datetime import timedelta

    from django.utils import timezone

    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    connection = services.connection_for(brazos.id, "email_smtp")
    models.IntegrationCredential.objects.filter(connection=connection, version=1).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})

    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        services.rollback_credential(actor=dana, tenant_id=brazos.id, provider_key="email_smtp")
    assert refusal.value.message_key == services.REFUSAL_PREVIOUS_EXPIRED
    assert [one.is_active for one in _rows(connection)] == [False, True], "nothing moved"


def test_tc6_the_three_exits_after_a_rotation_hold_for_both_plaintexts(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows, caplog
):
    """CR-069 §12's phase-2 exit test, second half — the credential is provably
    absent from THE DATABASE, THE LOGS and THE AUDIT TRAIL. Three assertions,
    not one (Figure 14), and both passwords in all three."""
    import logging

    caplog.set_level(logging.DEBUG)
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_test(brazos, dana, "email_smtp").data)  # noqa: F405
    post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})

    # 1 · THE DATABASE — a SECOND raw cursor, so `from_db_value` cannot decrypt
    #     on the way out and hand us plaintext to compare against itself.
    from django.db import connection as db

    with db.cursor() as cursor:
        cursor.execute("SELECT payload_enc, masked_hint FROM integration_credential")
        stored = cursor.fetchall()
    # ⚠ `ensure_ascii=False`: `json.dumps` escapes `•` to `\u2022` by default, so the
    # hint assertions below would fail on a dump that is perfectly correct.
    dump = json.dumps(stored, default=str, ensure_ascii=False)
    assert len(stored) == 2
    assert all(one[0].startswith("sbh1:") for one in stored), "a row is not ciphertext"

    # 2 · THE LOGS — everything captured across connect, test and rotate.
    logs = caplog.text

    # 3 · THE AUDIT TRAIL — every row, whole.
    trail = json.dumps(audit_rows, default=str, ensure_ascii=False)

    for plaintext in (GOOD_PASSWORD, FRIDAY_PASSWORD, "lockbox", "wrong-key"):
        assert plaintext not in dump, f"{plaintext!r} is in the database"
        assert plaintext not in logs, f"{plaintext!r} is in the logs"
        assert plaintext not in trail, f"{plaintext!r} is in the audit trail"
    # The hints ARE there, in all the places the plaintext is not.
    assert HINT_V1 in dump and HINT_V2 in dump
    assert HINT_V1 in trail and HINT_V2 in trail


def test_tc7_another_tenant_posting_a_rotation_gets_a_refusal_and_writes_nothing(
    brazos, dana, lonestar, erin, smtp_adapter, recording_dispatcher
):
    """Lone Star Ridge cannot rotate Brazos Bend's credential — and the shape
    of the refusal is *not connected*, identical to a key that never existed."""
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    before = models.IntegrationCredential.objects.count()

    with tenant_ctx(lonestar), pytest.raises(errors.BizError) as refusal:
        services.rollback_credential(actor=erin, tenant_id=lonestar.id, provider_key="email_smtp")
    assert refusal.value.message_key == services.REFUSAL_NOT_CONNECTED
    assert models.IntegrationCredential.objects.count() == before

    brazos_connection = services.connection_for(brazos.id, "email_smtp")
    assert [one.is_active for one in _rows(brazos_connection)] == [True]


def test_replacing_a_password_puts_the_connection_back_to_untested(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """DEF-INT-3762, found by clicking the screen and fixed here.

    This provider's `test()` sends a REAL message, so its operation declares
    `test_needs_recipient` and a rotation queues NOTHING — deliberately,
    because nothing should be sent blind. The trap is what was left behind:
    `status`, `last_test_ok` and `last_test_text` were all taken against the
    password that has just been REPLACED, so the connection went on saying
    *Working* about a credential nobody had tried. Hard-won law 1 exactly.
    """
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_test(brazos, dana, "email_smtp").data)  # noqa: F405
    connection = services.connection_for(brazos.id, "email_smtp")
    assert connection.status == models.STATUS_WORKING
    assert connection.last_test_ok is True

    post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})

    connection.refresh_from_db()
    assert connection.status == models.STATUS_UNTESTED
    assert connection.last_test_ok is None
    assert connection.last_test_text is None
    # …and the credential itself rotated, which is the half that always worked.
    assert [one.masked_hint for one in _rows(connection)] == [HINT_V1, HINT_V2]


def test_the_history_a_screen_reads_carries_hints_and_dates_and_no_column_for_a_secret(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """Frame 54.2's keys table. `credential_versions` does not select
    `payload_enc` and the dicts it returns have no key one could travel in."""
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})
    connection = services.connection_for(brazos.id, "email_smtp")
    history = services.credential_versions(connection)
    assert [one["version"] for one in history] == [2, 1]  # newest first
    assert [one["hint"] for one in history] == [HINT_V2, HINT_V1]
    assert [one["is_active"] for one in history] == [True, False]
    for one in history:
        assert set(one) == {"version", "is_active", "hint", "expires_at", "rotated_at", "created_at"}
    assert GOOD_PASSWORD not in json.dumps(history, default=str)


def test_the_card_serves_the_history_and_the_disconnect_figures(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """Wave E's two additions to the read model, on the shape a screen reads."""
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    post_credential(brazos, dana, "email_smtp", {"password": FRIDAY_PASSWORD})
    the_card = card(brazos, dana, "email_smtp")  # noqa: F405
    assert [one["hint"] for one in the_card["credentials"]] == [HINT_V2, HINT_V1]
    assert the_card["disconnect"]["versions"] == 2
    assert the_card["disconnect"]["category"] == "email"
    assert the_card["disconnect"]["channel"] == "email"
    assert GOOD_PASSWORD not in json.dumps(the_card, default=str)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-024@5bfc2492 (EP-INT-07 story + BR-INT-018..053 snapshot)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D✔(POST /integrations/{key}/credential and /credential/rollback) E✔(S142's Replace password · Roll back) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_024_credentials.py · TC-3 is tests/test_us_int_014_pg.py's EXCLUDE, on real PostgreSQL · G94
# exceptions: the hints are `••••kbox`/`••••iday` and not the story's `••••3F9A`/`••••A17C` — see the module docstring; the code derives a hint and the story paired a password with another figure's key
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-9666 — Messages needing attention printed
#           `notifications.queue.source.appointment` and
#           `notifications.queue.channel.in_app` as raw keys, and an in-app
#           row's recipient as a staff member's database id (B14 rule 31).
#           Found by lane SRV-5's walk (CR-168-BRC10 round 6, srv5-02).
# ───────────────────────────────────────────────────────
"""Every queue kind and channel has a word, and a staff recipient a name."""

from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

import pytest

from apps.notifications import models, selectors

EN = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales" / "en.json"


def test_every_source_kind_and_channel_has_its_queue_word():
    catalogue = json.loads(EN.read_text(encoding="utf-8"))
    missing = [f"notifications.queue.source.{k}" for k in models.SOURCE_TYPES
               if f"notifications.queue.source.{k}" not in catalogue]
    missing += [f"notifications.queue.channel.{c}" for c in models.CHANNELS
                if f"notifications.queue.channel.{c}" not in catalogue]
    assert missing == []


@pytest.mark.parametrize(
    "channel, snapshot, expected",
    [
        ("in_app", {"user_id": "01a1", "display_name": "Dana Whitfield"}, "Dana Whitfield"),
        ("in_app", {"user_id": "01a1"}, None),
        ("email", {"display_name": "Elena Rivera"}, None),
    ],
)
def test_an_in_app_row_names_its_staff_recipient_and_never_a_customer(channel, snapshot, expected):
    row = SimpleNamespace(channel=channel, recipient_snapshot=snapshot)
    assert selectors.queue_recipient_name(row) == expected

"""CR-168-BRC10 round 5, lane RULES — `GET /work/rules/processes` names the
message each escalation kind sends, so the rule form SHOWS it on a *When it
stalls* row instead of offering a picker the sender would ignore.

⚠ **WHY THE SCREEN NEEDS THIS AND NOT A PICKER.** Image 59 draws a *Message*
dropdown on each escalation row. The sender (`notifications.work_escalations.
queue_work_escalation`) sends `EVENT_BY_KIND[kind]` and reads no stored
`event_key` — so a picker there would be a live control that changes nothing
(hard-won law 2's mirror). The form shows the kind's own message, read from
here, and types no second copy of the mapping.

Red first on `3cd891cfb` (the tip before lane RULES): `KeyError: 'escalation_events'`.
"""
from __future__ import annotations

import pytest

from apps.notifications import work_escalations
from apps.work import rules

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx


@pytest.mark.django_db
def test_processes_serve_each_escalation_kinds_own_message(dana, brazos):
    with tenant_ctx(brazos):
        listed = rules.processes()
    events = listed["escalation_events"]
    # Every one of the seven kinds the form offers has its message …
    assert set(events) == set(listed["escalation_kinds"])
    # … and it is the sender's own mapping, not a copy that can drift.
    assert events == work_escalations.EVENT_BY_KIND
    # *Past due* IS the platform's long-drawn `sla_breach` (lane SRV-4).
    assert events["overdue"] == "sla_breach"
    # Every message is a catalogue row a supervisor can find in Notifications.
    from apps.notifications.rule_catalog import EVENT_KEYS

    assert set(events.values()) <= set(EVENT_KEYS)

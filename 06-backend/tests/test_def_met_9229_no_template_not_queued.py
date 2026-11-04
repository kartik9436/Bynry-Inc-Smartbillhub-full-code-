"""DEF-MET-9229 — a New Connection letter with no template is not queued, and does not claim it will be.

Found by the New Connection end-to-end web walk (2026-10-02): a utility signed up with
two of the three templates (*New connect — confirmed*, *Connection quote*). Step 5 said
*The contract · Not sent · No template — add in Settings*; the request's Messages tab
said *Sent on approval*; and at approval the contract was QUEUED as a print row naming
`contract_service_agreement`, a class nobody had published — a row nothing can render.
"""

from __future__ import annotations

from types import SimpleNamespace

from apps.metering import connection_messages as step7

PUBLISHED = (
    {"code": "new_connect_confirmed", "pickable": True},
    {"code": "new_connect_quote", "pickable": True},
)


def test_approval_does_not_queue_a_letter_that_has_no_template(monkeypatch):
    monkeypatch.setattr(step7.seams, "connection_templates", lambda search=None: PUBLISHED)
    sent = []
    monkeypatch.setattr(step7, "send_now", lambda *a, **k: sent.append(k) or {"state": "queued"})
    contract = step7.occasion("contract")
    out = step7._fire_one(
        None,
        SimpleNamespace(id="00000000-0000-0000-0000-000000000001"),
        contract,
        account_id="acct",
        language=None,
        override_template=None,
        asked=True,
    )
    assert out["state"] == step7.STATE_NOT_SENT
    assert out["reason"] == step7.REASON_NO_TEMPLATE
    assert sent == []


def test_a_published_letter_still_goes(monkeypatch):
    monkeypatch.setattr(step7.seams, "connection_templates", lambda search=None: PUBLISHED)
    monkeypatch.setattr(step7.seams, "deliveries_for_source", lambda *a, **k: [])
    monkeypatch.setattr(step7, "send_now", lambda *a, **k: {"state": step7.STATE_QUEUED})
    out = step7._fire_one(
        None,
        SimpleNamespace(id="00000000-0000-0000-0000-000000000001"),
        step7.occasion("build_created"),
        account_id="acct",
        language=None,
        override_template=None,
        asked=True,
    )
    assert out["state"] == step7.STATE_QUEUED


def test_unknown_template_state_does_not_block(monkeypatch):
    """Notifications could not be asked (`None`): the old path stands, no guess."""
    assert step7.template_published.__doc__  # the helper exists
    monkeypatch.setattr(step7.seams, "connection_templates", lambda search=None: None)
    assert step7.template_published("contract_service_agreement") is None

# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-026 (EP-INT-07) — the mail password typed into the product.
#         US-INT-015 TC-1 · TC-2 · TC-4 · TC-7 against the REAL adapter.
#         Screens: S141 (Save and test) · S142 (the sentence, their words)
# Rules:  BR-INT-019 (`test()` is the smallest REAL instance) · BR-INT-003
#         (the three exits) · BR-INT-040 (per-item results, never a batch
#         boolean) · B14 rule 33 (six words) · hard-won law 3 (the unsafe
#         option is the one you type) · law 2 (a stub that always says yes
#         proves nothing about a real conversation)
# ───────────────────────────────────────────────────────
"""The adapter, against a real mail server standing on a real socket.

Every case here opens a TCP connection, speaks SMTP and reads what the server
actually received. Nothing is mocked; the double is the SERVER, which is the
half we do not own.
"""

from __future__ import annotations

import logging

import pytest

from apps.integrations.adapters import email_smtp
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.conformance import Fixture, failures, run_kit
from apps.integrations.registry import REGISTRY
from tests.smtp_server_helper import SmtpTestServer

GOOD = "Ew3!kQ9-lockbox"
BAD = "hunter2 "  # the trailing space — the day-one failure (US-INT-015 §4)
FROM = "billing@brazosbend.example"
RECIPIENT = "alex@brazosbend.example"


def view(port: int) -> ConnectionView:
    return ConnectionView(
        provider_key="email_smtp",
        environment="production",
        config={"host": "127.0.0.1", "port": str(port), "username": FROM, "send_from": FROM},
        label="Brazos mailbox",
    )


def test_us_int_015_tc1_a_good_password_sends_one_real_message_and_says_so():
    """52.1 — *Sent one test message to alex@brazosbend.example.* and the
    server is holding the message that proves it."""
    with SmtpTestServer(password=GOOD) as mail:
        result = email_smtp.EmailSmtpAdapter().test(
            view(mail.port), {"password": GOOD}, recipient=RECIPIENT
        )
        assert result.ok is True
        assert result.sentence == f"Sent one test message to {RECIPIENT}."
        assert result.provider_text is None
        # The message REACHED the far end — one delivery, to the typed address,
        # from the configured sender, carrying the subject a person will see.
        assert len(mail.delivered) == 1
        assert mail.delivered[0].recipients == [f"<{RECIPIENT}>"]
        assert mail.delivered[0].sender == f"<{FROM}>"
        assert "Test message from your billing system" in mail.delivered[0].data
        assert mail.seen_username == FROM


def test_us_int_015_tc2_a_wrong_password_is_the_mail_servers_own_sentence_underneath_ours():
    """52.2 and CR-069 §12's phase-2 exit test, first half."""
    with SmtpTestServer(password=GOOD) as mail:
        result = email_smtp.EmailSmtpAdapter().test(
            view(mail.port), {"password": BAD}, recipient=RECIPIENT
        )
    assert result.ok is False
    assert result.sentence == "The mail server rejected the password."
    assert len(result.sentence.split()) == 6  # B14 rule 33
    assert "535" in (result.provider_text or "")
    assert "AUTHENTICATION FAILED" in (result.provider_text or "")
    # OUR sentence carries no status code and no rule id (rules 32 · 33).
    assert "535" not in result.sentence
    assert "BR-" not in result.sentence


def test_us_int_024_tc6_the_password_is_in_no_sentence_and_no_log_line():
    """Two of the three exits, at the point the plaintext exists. The third —
    `audit_log` — is asserted in `test_us_int_024_credentials.py`, because the
    adapter writes no audit row at all."""
    stream: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            stream.append(self.format(record))

    handler = Capture()
    handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    previous = root.level
    root.setLevel(logging.DEBUG)
    try:
        with SmtpTestServer(password=GOOD) as mail:
            adapter = email_smtp.EmailSmtpAdapter()
            good = adapter.test(view(mail.port), {"password": GOOD}, recipient=RECIPIENT)
            bad = adapter.test(view(mail.port), {"password": BAD}, recipient=RECIPIENT)
            run = adapter.execute(
                view(mail.port),
                {"password": GOOD},
                [{"ref": "A-10432", "address": RECIPIENT, "subject": "Your bill", "body": "bill"}],
            )
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)

    everywhere = "\n".join(
        [good.sentence, bad.sentence, bad.provider_text or "", *stream]
        + [one.provider_text or "" for one in run.items]
        + [adapter.describe(view(1))]
    )
    for plaintext in (GOOD, BAD.strip(), "lockbox", "hunter2"):
        assert plaintext not in everywhere, f"{plaintext!r} escaped through a sentence or a log line"


def test_us_int_015_tc3_execute_answers_per_item_and_seven_bad_addresses_are_seven_items():
    """BR-INT-040 — never a batch boolean. Two go, one is refused by name, and
    the run still reports the two that went.

    ⚠ The items carry a SUBJECT from 2026-10-22 (`DEF-NOT-10420`): before then
    they had none and the adapter quietly titled each real message *Test message
    from your billing system*, which this case relied on without saying so. A
    real message with no subject is now refused, as it should always have been.
    """
    with SmtpTestServer(password=GOOD, refuse_recipients=("j.doe@",)) as mail:
        result = email_smtp.EmailSmtpAdapter().execute(
            view(mail.port),
            {"password": GOOD},
            [
                {"ref": "A-10432", "address": "c.ortiz@example.invalid", "subject": "Your bill", "body": "bill"},
                {"ref": "A-10433", "address": "j.doe@example.invalid", "subject": "Your bill", "body": "bill"},
                {"ref": "A-10434", "address": "s.abbott@example.invalid", "subject": "Your bill", "body": "bill"},
            ],
        )
        assert len(mail.delivered) == 2  # the two that were accepted really went
    assert result.confirmed is True
    assert result.counts == {"attempted": 3, "succeeded": 2, "failed": 1, "skipped": 0}
    refused = [one for one in result.items if one.outcome == "failed"]
    assert len(refused) == 1
    assert refused[0].ref == "A-10433"
    assert refused[0].detail == "j.doe@example.invalid"
    assert "No such mailbox" in (refused[0].provider_text or "")


def test_us_int_015_the_connection_ending_fails_every_item_it_still_owed():
    """A wrong password ends the session before item one, so all three fail —
    each with the server's own words, because that is the truth about each."""
    with SmtpTestServer(password=GOOD) as mail:
        result = email_smtp.EmailSmtpAdapter().execute(
            view(mail.port),
            {"password": BAD},
            [{"ref": f"A-1043{n}", "address": f"a{n}@example.invalid"} for n in range(3)],
        )
    assert result.counts["failed"] == 3
    assert all("AUTHENTICATION FAILED" in (one.provider_text or "") for one in result.items)


def test_us_int_015_a_server_that_is_not_there_is_an_outcome_and_never_an_exception():
    """BR-INT-019 — `test()` never raises for anything the far end does. Port
    1 has nothing listening; the sentence is ours and it is six words."""
    result = email_smtp.EmailSmtpAdapter().test(
        ConnectionView(
            provider_key="email_smtp",
            environment="production",
            config={"host": "127.0.0.1", "port": "1", "username": FROM, "send_from": FROM},
        ),
        {"password": GOOD},
        recipient=RECIPIENT,
    )
    assert result.ok is False
    assert result.sentence == "The mail server did not answer."
    assert len(result.sentence.split()) == 6


def test_us_int_015_tc7_plaintext_smtp_is_allowed_to_localhost_and_to_nothing_else():
    """Hard-won law 3, made checkable. The harness needs no certificate; a
    server on a real network that offers no STARTTLS is refused BY US."""
    assert email_smtp._plaintext_allowed("localhost") is True
    assert email_smtp._plaintext_allowed("127.0.0.1") is True
    assert email_smtp._plaintext_allowed("smtp.office365.com") is False
    assert email_smtp._plaintext_allowed("mail.brazosbend.example") is False


def test_us_int_015_tc6_the_conformance_kit_runs_over_the_real_adapter_unchanged():
    """*"If a new connector requires the suite to change, that is the signal."*
    Thirty-seven cases, no edit to the kit, no provider named inside it."""
    # 2525 rather than an ephemeral port: `validate()` refuses a port no mail
    # server listens on, and the kit checks the fixture-valid config against
    # it — so an ephemeral port would fail the kit for the adapter being
    # right. If something else on the machine holds 2525 there is nothing
    # honest to assert, so the case says so rather than passing on a
    # substitute.
    try:
        mail_server = SmtpTestServer(password=GOOD, port=2525)
    except OSError as busy:  # pragma: no cover — environment, not logic
        pytest.skip(f"port 2525 is in use, so the kit has no mail server to run against: {busy}")
    with mail_server:
        fixture = Fixture(
            config={"host": "127.0.0.1", "port": "2525", "username": FROM, "send_from": FROM},
            good_secrets={"password": GOOD},
            bad_secrets={"password": BAD},
            work=({"ref": "A-10432", "address": RECIPIENT},),
            recipient=RECIPIENT,
        )
        findings = run_kit(
            email_smtp.EmailSmtpAdapter, REGISTRY.require("email_smtp"), fixture
        )
    assert failures(findings) == []


def test_us_int_015_describe_is_the_address_a_customer_will_see_and_nothing_else():
    line = email_smtp.EmailSmtpAdapter().describe(view(2525))
    assert line == f"{FROM} · Custom SMTP"
    assert "127.0.0.1" not in line and "2525" not in line


@pytest.mark.parametrize("port", ["25", "465", "587", "2525"])
def test_us_int_015_validate_accepts_the_ports_a_mail_server_listens_on(port):
    assert email_smtp.EmailSmtpAdapter().validate({"port": port}) == []


def test_us_int_015_validate_refuses_a_port_no_mail_server_uses():
    problems = email_smtp.EmailSmtpAdapter().validate({"port": "8080"})
    assert [one.field for one in problems] == ["port"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-026@5bfc2492 (EP-INT-07 story + BR-INT-018..053 snapshot; co-packet US-INT-015@5bfc2492)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a(the 🔒 half is the adapter, ledgered there)
# gates: pytest tests/test_us_int_026_smtp_adapter.py (SQLite — none of these cases touches the database) · the conformance kit, unchanged
# exceptions: the SMTP server is real and the credential is a fixture — `core/crypto.py`'s sign-off gates a REAL customer credential, not a test one (execution plan E1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) TC-6 — the conformance kit: one suite that
#           EVERY adapter runs unchanged, driven off the manifest. TC-3 (an
#           `execute()` that returns a bare True is refused). Screens: —
# Rules:    BR-INT-038 (translation only) · BR-INT-019 (`test()` is a real
#           instance, answered in a sentence) · BR-INT-003 (no secret in a
#           sentence, a describe line or a log line — the three exits) ·
#           BR-INT-043 (the shape check is the manifest's) · B14 rules 32
#           and 33 (no rule id, no status code in a clerk sentence)
# Tests:    06-backend/tests/test_us_int_015_adapters.py (runs this kit over
#           the fixture adapters; asserts the count and that adding an
#           adapter needs no edit here)
# Impacts:  every file under apps/integrations/adapters/ · wave E's E7 gate
#           (the three-exits assertion runs INSIDE this kit)
# ───────────────────────────────────────────────────────
"""The conformance kit — THIRTY-SEVEN cases every adapter passes, or it is not one.

WHY A KIT AND NOT A TEST PER ADAPTER
------------------------------------
The design's sentence: *"If a new connector requires the suite to change, that
is the signal — a design review, not a merge."* So the cases below read only
the MANIFEST and the four methods; nothing in them names a provider. A case
that needs to know it is talking to SMTP does not belong here.

WHAT IS ASSERTED, in five groups
--------------------------------
  surface   — exactly four public methods, the key matches the manifest,
              the manifest is LIVE (a coming-soon provider has no adapter)
  validate  — a list of FieldErrors back for garbage · every required field
              named when absent · the fixture-valid config accepted by the
              manifest AND by the adapter · a bad port, a bad email, a bad
              host, a select outside its options, an unknown field each
              named · NO network · NO secret value in an error
  test      — a `TestResult` · a sentence · the sentence has no rule id, no
              status code, none of the credential · a wrong credential is
              `ok=False` with their words underneath, and never raises · NO
              credential in any log line captured during the call
  execute   — a `RunResult`, never a bool · every item a real outcome · empty
              work is an empty result · a failing item does not raise · NO
              credential in any log line
  describe  — a string · non-empty · no secret · no rule id

⚠ THE THREE EXITS (BR-INT-003) ARE THE *no log line* CASES, THE *carries no
credential* CASES AND THE DESCRIBE CASE — the credential
must not leave through a sentence, a log line or a describe line. Wave E's E7
gate runs the same assertion permanently; it starts here.

THE FIXTURE ADAPTERS, AND WHY THEY ARE IN THIS FILE
---------------------------------------------------
The kit needs adapters to run against before a real one exists, and three of
them are named by the execution plan (B1): *returns-True* (TC-3 — the kit
must FAIL it), *slow 90 s — sleeps, never raises* (wave F's breaker), and
*no-count 200* (wave C's `unconfirmed`). A fourth, `RecordedSmtpAdapter`,
replays the recorded SMTP conversation of US-INT-015 §4 — host
`smtp.brazosbend.example`, good password `Ew3!kQ9-lockbox`, bad password
`hunter2 ` with the trailing space — so TC-1, TC-2 and TC-4 run with no
network. **None of them is ever registered at `ready()`**: a test binds one,
runs the path, and unbinds it. They are here rather than under `adapters/`
so the real-adapter folder holds real adapters and nothing that could be
mistaken for one.
"""

from __future__ import annotations

import logging
import socket
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_OUTCOMES,
    ITEM_SUCCEEDED,
    PROTOCOL_METHODS,
    Adapter,
    ConnectionView,
    FieldError,
    ItemResult,
    RunResult,
    TestResult,
    validate_fields,
)
from apps.integrations.adapters.oauth_mailbox import OAuthMailboxAdapter, _ConsentLapsed
from apps.integrations.registry import Manifest

#: What a clerk sentence may never carry (B14 rules 31–33).
_RULE_ID = ("BR-", "OQ-", "DEF-", "US-INT")
_STATUS_CODE = __import__("re").compile(r"\b[1-5]\d\d\b")


@dataclass(frozen=True)
class Fixture:
    """What the kit needs from a test to exercise one adapter: a valid config,
    the secrets that WORK, the secrets that are WRONG, and one item of work."""

    config: Mapping[str, Any]
    good_secrets: Mapping[str, str]
    bad_secrets: Mapping[str, str]
    work: Sequence[Mapping[str, Any]]
    recipient: str | None = None


@dataclass(frozen=True)
class Finding:
    case: int
    name: str
    ok: bool
    detail: str = ""


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def _capture_logs(call: Callable[[], Any]) -> tuple[Any, list[str]]:
    handler = _LogCapture()
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        return call(), handler.lines
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def _no_network(call: Callable[[], Any]) -> tuple[Any, bool]:
    """Run `call` with the socket module refusing to connect. True = it tried."""
    tried = {"yes": False}
    original = socket.socket.connect

    def refuse(self: Any, *args: Any, **kwargs: Any) -> None:
        tried["yes"] = True
        raise OSError("the conformance kit forbids network in validate()")

    socket.socket.connect = refuse  # type: ignore[method-assign]
    try:
        return call(), tried["yes"]
    finally:
        socket.socket.connect = original  # type: ignore[method-assign]


def _carries(text: str | None, secrets: Mapping[str, str]) -> bool:
    if not text:
        return False
    return any(value and value in text for value in secrets.values())


def _clean_sentence(text: str) -> str | None:
    if not text or not text.strip():
        return "empty"
    if any(mark in text for mark in _RULE_ID):
        return "carries a rule id"
    if _STATUS_CODE.search(text):
        return "carries a status code"
    return None


def run_kit(adapter_cls: type[Adapter], manifest: Manifest, fixture: Fixture) -> list[Finding]:
    """Every case, every time. Read the findings; `passed()` folds them."""
    out: list[Finding] = []
    n = [0]

    def case(name: str, ok: bool, detail: str = "") -> None:
        n[0] += 1
        out.append(Finding(n[0], name, bool(ok), detail))

    adapter = adapter_cls()
    view = ConnectionView(
        provider_key=manifest.key,
        environment="sandbox",
        config=fixture.config,
        label="conformance",
    )
    secret_names = {one.name for one in manifest.fields if one.is_secret}
    typed = [one for one in manifest.fields if one.kind in ("text", "email", "host", "port", "select")]

    # ── surface ────────────────────────────────────────────────────────────
    public = {
        name
        for name in dir(adapter_cls)
        if not name.startswith("_") and callable(getattr(adapter_cls, name)) and name != "key"
    }
    case("four public methods and only four", public == PROTOCOL_METHODS, f"found {sorted(public)}")
    case("the adapter's key is the manifest's", getattr(adapter_cls, "key", None) == manifest.key)
    case("the manifest is LIVE — a coming-soon provider has no adapter", not manifest.disposition.coming_soon)

    # ── validate ───────────────────────────────────────────────────────────
    garbage = adapter.validate({"": object(), "port": ["x"], "host": 12})
    case(
        "validate() returns a list of FieldErrors for garbage",
        isinstance(garbage, list) and all(isinstance(one, FieldError) for one in garbage),
    )
    required = [one.name for one in manifest.fields if one.required and one.kind in ("text", "email", "host", "port", "select")]
    missing = {one.field for one in validate_fields(manifest, {}, {})}
    case("every required typed field is named when absent", set(required) <= missing, f"missing={sorted(missing)}")
    shape = validate_fields(manifest, fixture.config, fixture.good_secrets)
    own = adapter.validate(fixture.config)
    case("the fixture-valid config passes the manifest's shape check", shape == [], str(shape))
    case("the fixture-valid config passes the adapter's own validate()", own == [], str(own))
    ports = [one for one in typed if one.kind == "port"]
    bad_port = {**fixture.config, **{one.name: "abc" for one in ports}}
    case(
        "a port that is not a number is named",
        not ports or {one.name for one in ports} <= {one.field for one in validate_fields(manifest, bad_port, fixture.good_secrets)},
    )
    emails = [one for one in typed if one.kind == "email"]
    bad_email = {**fixture.config, **{one.name: "not-an-address" for one in emails}}
    case(
        "an email with no @ is named",
        not emails or {one.name for one in emails} <= {one.field for one in validate_fields(manifest, bad_email, fixture.good_secrets)},
    )
    hosts = [one for one in typed if one.kind == "host"]
    bad_host = {**fixture.config, **{one.name: "https://mail.example/x" for one in hosts}}
    case(
        "a host carrying a scheme is named",
        not hosts or {one.name for one in hosts} <= {one.field for one in validate_fields(manifest, bad_host, fixture.good_secrets)},
    )
    selects = [one for one in typed if one.kind == "select"]
    bad_select = {**fixture.config, **{one.name: "not-an-option" for one in selects}}
    case(
        "a select outside its options is named",
        not selects or {one.name for one in selects} <= {one.field for one in validate_fields(manifest, bad_select, fixture.good_secrets)},
    )
    unknown = validate_fields(manifest, {**fixture.config, "no_such_field": 1}, fixture.good_secrets)
    case("an unknown field is named", "no_such_field" in {one.field for one in unknown})
    _, tried = _no_network(lambda: adapter.validate(fixture.config))
    case("validate() opens no socket", not tried)
    leaked_in_errors = any(
        _carries(f"{one.field} {one.message_key} {dict(one.params)}", fixture.good_secrets)
        for one in adapter.validate({**fixture.config, **fixture.good_secrets})
    )
    case("validate() never echoes a secret value in an error", not leaked_in_errors)

    # ── test ───────────────────────────────────────────────────────────────
    good, good_logs = _capture_logs(lambda: adapter.test(view, fixture.good_secrets, recipient=fixture.recipient))
    case("test() returns a TestResult", isinstance(good, TestResult))
    case("test() with the working credential is ok", isinstance(good, TestResult) and good.ok, getattr(good, "sentence", ""))
    reason = _clean_sentence(getattr(good, "sentence", ""))
    case("the ok sentence is clean — no rule id, no status code", reason is None, reason or "")
    case("the ok sentence carries no credential", not _carries(getattr(good, "sentence", ""), fixture.good_secrets))
    case("no log line during test() carries the credential", not any(_carries(line, fixture.good_secrets) for line in good_logs))
    try:
        bad, bad_logs = _capture_logs(lambda: adapter.test(view, fixture.bad_secrets, recipient=fixture.recipient))
        raised = None
    except Exception as exc:  # noqa: BLE001 — the case records it
        bad, bad_logs, raised = None, [], exc
    case("test() with a wrong credential does not raise", raised is None, repr(raised))
    #: ⚠ **A PROVIDER THAT HOLDS NO CREDENTIAL CANNOT HAVE A WRONG ONE**, and
    #: until 2026-09-05 this kit assumed every adapter did. `payments_sandbox`
    #: declares `auth.mode="none"` and has no secret field at all, so
    #: `fixture.bad_secrets` is `{}` — indistinguishable from the good one —
    #: and three cases below failed it for answering correctly.
    #:
    #: **THE CASES ARE NOT SKIPPED.** A skipped case that reads as a pass is
    #: exactly the shape this repo has filed twice (a check that cannot fail).
    #: Each is REPLACED by the question that IS meaningful for such a provider:
    #: does it genuinely declare no secret? The count is unchanged, every case
    #: still asserts something true, and a provider that declares a secret is
    #: held to the original three exactly as before.
    credential_free = manifest.auth.mode == "none" and not any(
        one.is_secret for one in manifest.fields
    )
    if credential_free:
        case(
            "no credential to get wrong — the manifest declares none",
            not any(one.is_secret for one in manifest.fields),
            f"auth.mode={manifest.auth.mode}",
        )
    else:
        case("a wrong credential is ok=False", isinstance(bad, TestResult) and not bad.ok)
    case("a wrong credential has our sentence", isinstance(bad, TestResult) and _clean_sentence(bad.sentence) is None, getattr(bad, "sentence", ""))
    if credential_free:
        case(
            "a credential-free provider still answers with a sentence",
            isinstance(bad, TestResult) and bool(bad.sentence),
            getattr(bad, "sentence", ""),
        )
    else:
        case("a wrong credential has their words underneath", isinstance(bad, TestResult) and bool(bad.provider_text))
    case("the failure sentence carries no credential", not _carries(getattr(bad, "sentence", ""), fixture.bad_secrets))
    case("their words carry no credential", not _carries(getattr(bad, "provider_text", ""), fixture.bad_secrets))
    case("no log line during a failed test() carries the credential", not any(_carries(line, fixture.bad_secrets) for line in bad_logs))

    # ── execute ────────────────────────────────────────────────────────────
    result, run_logs = _capture_logs(lambda: adapter.execute(view, fixture.good_secrets, fixture.work))
    case("execute() returns a RunResult, never a boolean", isinstance(result, RunResult), type(result).__name__)
    items = getattr(result, "items", ()) if isinstance(result, RunResult) else ()
    case("every item is an ItemResult", all(isinstance(one, ItemResult) for one in items))
    case("every item carries a real outcome", all(one.outcome in ITEM_OUTCOMES for one in items))
    case("one item of work is one item of result", isinstance(result, RunResult) and len(items) == len(fixture.work))
    empty = adapter.execute(view, fixture.good_secrets, [])
    # Zero items back for zero items of work; whether an EMPTY batch counts as
    # confirmed is the provider's own truth (a no-count provider says no).
    case("empty work is an empty result, never a raise", isinstance(empty, RunResult) and empty.items == ())
    try:
        failing = adapter.execute(view, fixture.bad_secrets, fixture.work)
        raised = None
    except Exception as exc:  # noqa: BLE001
        failing, raised = None, exc
    case("a refused batch does not raise", raised is None, repr(raised))
    if credential_free:
        #: Same reasoning as the two above: with no credential to get wrong, the
        #: batch that would have been refused is the batch that succeeds. What is
        #: still worth asserting is that it answered PER ITEM rather than with a
        #: boolean, which is BR-INT-040 and is the point of the original case.
        case(
            "a credential-free batch still reports per item, not a bool",
            isinstance(failing, RunResult) and len(failing.items) == len(fixture.work),
        )
    else:
        case("a refused batch reports failed items, not a bool", isinstance(failing, RunResult) and all(one.outcome == ITEM_FAILED for one in failing.items))
    case("no log line during execute() carries the credential", not any(_carries(line, fixture.good_secrets) for line in run_logs))

    # ── describe ───────────────────────────────────────────────────────────
    line = adapter.describe(view)
    case("describe() returns a non-empty string", isinstance(line, str) and bool(line.strip()))
    case("describe() carries no secret", not _carries(line if isinstance(line, str) else "", fixture.good_secrets))
    case("describe() carries no rule id", isinstance(line, str) and _clean_sentence(line) is None, line)
    return out


#: The number the design signed for the kit. `test_us_int_015_adapters.py`
#: asserts the kit produces exactly this many findings, so a case added or
#: removed is a visible change to a signed number and not a quiet drift.
CASE_COUNT = 37


def passed(findings: list[Finding]) -> bool:
    return all(one.ok for one in findings)


def failures(findings: list[Finding]) -> list[str]:
    return [f"{one.case:02d} {one.name}: {one.detail}".rstrip(": ") for one in findings if not one.ok]


# ── the fixture adapters — bound only inside a test, never at ready() ───────

_SMTP_HOST = "smtp.brazosbend.example"
_SMTP_GOOD = "Ew3!kQ9-lockbox"
_SMTP_BAD = "hunter2 "  # the trailing space — the day-one failure (US-INT-015 §4)


class RecordedSmtpAdapter(Adapter):
    """Replays the recorded SMTP conversation of US-INT-015 §4. No network.

    The real adapter is wave E's `adapters/email_smtp.py`; this one exists so
    the runtime, the modal and the kit can be proved before it lands, and so
    the sentences a clerk reads are pinned now: *Sent one test message to
    alex@brazosbend.example* and *the mail server rejected the password*.
    """

    key = "email_smtp"

    def validate(self, config: Mapping[str, Any]) -> list[FieldError]:
        problems: list[FieldError] = []
        port = str(config.get("port", "")).strip()
        if port and port not in ("25", "465", "587", "2525"):
            problems.append(FieldError("port", message_key="integrations.field.smtp_port"))
        return problems

    def test(self, conn: ConnectionView, secrets: Mapping[str, str], *, recipient: str | None = None) -> TestResult:
        if secrets.get("password") == _SMTP_GOOD and conn.config.get("host") == _SMTP_HOST:
            return TestResult(ok=True, sentence=f"Sent one test message to {recipient or conn.config.get('send_from')}.")
        return TestResult(
            ok=False,
            sentence="The mail server rejected the password.",
            provider_text="535 5.7.8 AUTHENTICATION FAILED",
        )

    def execute(self, conn: ConnectionView, secrets: Mapping[str, str], work: Sequence[Mapping[str, Any]]) -> RunResult:
        accepted = secrets.get("password") == _SMTP_GOOD
        items = tuple(
            ItemResult(
                ref=str(one.get("ref", index)),
                outcome=ITEM_SUCCEEDED if accepted else ITEM_FAILED,
                provider_text=None if accepted else "535 5.7.8 AUTHENTICATION FAILED",
            )
            for index, one in enumerate(work)
        )
        return RunResult(items=items, confirmed=True)

    def describe(self, conn: ConnectionView) -> str:
        return f"{conn.config.get('send_from') or conn.config.get('username')} · Custom SMTP"


RECORDED_SMTP_FIXTURE = Fixture(
    config={"host": _SMTP_HOST, "port": "587", "username": "billing@brazosbend.example", "send_from": "billing@brazosbend.example"},
    good_secrets={"password": _SMTP_GOOD},
    bad_secrets={"password": _SMTP_BAD},
    work=({"ref": "A-10432"}, {"ref": "A-10433"}),
    recipient="alex@brazosbend.example",
)


class RecordedOAuthMailboxAdapter(OAuthMailboxAdapter):
    """Wave H — a signed-in mailbox with the socket taken out.

    ⚠ **IT OVERRIDES EXACTLY THE TWO METHODS THAT TOUCH THE NETWORK AND NOTHING
    ELSE.** Everything the tests actually care about — that a lapsed consent
    becomes a SENTENCE rather than a traceback, that a missing consent is
    refused before a token is minted, that one token serves a whole batch, that
    `describe()` reads *billing@… · Microsoft 365* — runs through the real
    `oauth_mailbox.OAuthMailboxAdapter` code. A fixture that reimplemented
    `test()` would assert its own behaviour and prove nothing about the adapter
    a customer's bills actually go through.

    `consent` decides what the recorded provider says: `"live"` mints a token,
    `"lapsed"` raises the provider's own `invalid_grant`.
    """

    key = "email_microsoft"
    provider_label = "Microsoft 365"
    send_url = "https://graph.microsoft.example/recorded/sendMail"
    consent = "live"
    #: What was asked to be sent, so a test can assert the message shape with
    #: no socket. Class-level on purpose: the runtime builds a new adapter per
    #: call, so an instance attribute would be unreadable afterwards.
    sent: list = []

    def _access_token(self, conn: ConnectionView, refresh: str) -> str:
        if self.consent == "lapsed":
            raise _ConsentLapsed("AADSTS700082: invalid_grant — the refresh token has expired")
        return "RECORDED-ACCESS-TOKEN"

    def _send_one(
        self,
        token: str,
        *,
        sender: str,
        to: str,
        subject: str,
        body: str,
        attachments=(),
        language: str | None = None,
        html: str | None = None,
    ) -> None:
        # The REAL `_message` builds the payload, so Graph's shape is exercised.
        type(self).sent.append(
            {
                "to": to,
                "token": token,
                "message": self._message(
                    sender=sender,
                    to=to,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                    language=language,
                    html=html,
                ),
            }
        )

    def _message(
        self,
        *,
        sender: str,
        to: str,
        subject: str,
        body: str,
        attachments=(),
        language: str | None = None,
        html: str | None = None,
    ):
        from apps.integrations.adapters.email_microsoft import EmailMicrosoftAdapter

        return EmailMicrosoftAdapter._message(
            self,
            sender=sender,
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            language=language,
            html=html,
        )


class LapsedMailboxAdapter(RecordedOAuthMailboxAdapter):
    """The mailbox whose consent ran out — `BR-INT-042`'s three-in-the-morning
    case, made into a fixture so the sentence a clerk reads is pinned."""

    consent = "lapsed"


class ReturnsTrueAdapter(RecordedSmtpAdapter):
    """TC-3 — an `execute()` that answers a bare True. The kit must FAIL it and
    the runtime must record `unconfirmed`, never success."""

    def execute(self, conn: ConnectionView, secrets: Mapping[str, str], work: Sequence[Mapping[str, Any]]) -> Any:  # type: ignore[override]
        return True


class NoCountAdapter(RecordedSmtpAdapter):
    """Wave C's fixture — the provider answered 200 and would not say how many
    it accepted. `confirmed=False`, and the outcome word is `unconfirmed`. A
    wrong credential is still refused item by item: the fixture models a
    provider that will not COUNT, not one that will not authenticate."""

    def execute(self, conn: ConnectionView, secrets: Mapping[str, str], work: Sequence[Mapping[str, Any]]) -> RunResult:
        accepted = secrets.get("password") == _SMTP_GOOD
        items = tuple(
            ItemResult(
                ref=str(one.get("ref", i)),
                outcome=ITEM_SUCCEEDED if accepted else ITEM_FAILED,
                provider_text=None if accepted else "535 5.7.8 AUTHENTICATION FAILED",
            )
            for i, one in enumerate(work)
        )
        return RunResult(items=items, confirmed=False, provider_text="200 OK")


class SlowAdapter(RecordedSmtpAdapter):
    """Wave F's fixture — HANGS, it does not error (BR-INT-022's TC-INT-17).
    `SLOW_SECONDS` is a class attribute so a test can shorten it; the product
    figure is ninety seconds."""

    SLOW_SECONDS: float = 90.0

    def test(self, conn: ConnectionView, secrets: Mapping[str, str], *, recipient: str | None = None) -> TestResult:
        time.sleep(self.SLOW_SECONDS)
        return super().test(conn, secrets, recipient=recipient)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-015@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot)
# generated: 2026-09-03 by the CR-069 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(a kit, not a route) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_015_adapters.py (the kit over the recorded fixture passes; over ReturnsTrueAdapter it FAILS by name; CASE_COUNT holds)
# exceptions: the fixture adapters are production code by location and test doubles by nature — they are bound to the registry only inside a test and `adapters/__init__.py` lists none of them
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

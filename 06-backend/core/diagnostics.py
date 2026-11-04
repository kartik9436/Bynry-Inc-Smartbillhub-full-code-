# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 tasks A1/A2/A4 — "a runtime error becomes reproducible"
#           (12-governance/11-change-requests.md). PO 2026-09-02, verbatim:
#           *"many times errors will happen run time and it is very difficult to
#           reproduce those error … we should able to locate and understand what
#           was the error"*
# Rules:    BR-AUD-002 (the audit log has NO write verbs — nothing edits or
#           removes a row, which is exactly why raw error text may not go into
#           it) · BR-AUD-006 (PII enters masked only) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 7 (every money action writes audit_log —
#           this file writes NO audit row and says so below)
# Pattern:  `core/audit.py` — the registered-sink split that keeps `core` free of
#           app-model imports. Same shape on purpose.
#           `apps/tenancy/sample_errors.audit_safe_sentence(code)` — the
#           signature-is-the-guarantee rule this file generalises.
# Tests:    06-backend/tests/test_cr067_diagnostics.py
# ───────────────────────────────────────────────────────
"""**THE TECHNICAL DETAIL OF ONE FAILURE, WRITTEN WHERE IT CAN EXPIRE.**

WHAT THIS IS FOR
----------------
`audit_log` records that something was attempted, by whom, when, and — since
CR-039 — a stable error code and a fixed catalogue sentence. It is permanent.
It cannot say *why* a thing broke in enough detail to reproduce it, and CR-067
§2 is explicit that it must never try: a runtime message routinely carries an
account number, a balance or a meter reading, and **the audit log has no
delete**.

So the detail lives HERE, in a separate, tenant-scoped, EXPIRING record, joined
to the permanent row by a short reference a person can read down a phone.

⚠ **THE SPLIT IS NOT A DESIGN PREFERENCE. IT IS THE ONLY SHAPE THAT SATISFIES
BOTH THE REQUEST AND `BR-AUD-002`** (CR-067 §2, verbatim: *"any implementation
that writes an exception message into `audit_log` has broken a signed rule
rather than delivered this CR"*).

THE REDACTION RULE, AND WHY IT IS A SIGNATURE AND NOT A CONVENTION
-------------------------------------------------------------------
`apps/tenancy/sample_errors.audit_safe_sentence(code)` states the principle
better than a paragraph can:

    ⚠ It takes ONLY the code. That is not a stylistic choice: a function that
    accepted the seeder's own message could be handed one containing an account
    number, a balance or a read value, and `audit_log` has no delete. **The
    signature is the guarantee.**

`capture()` below is that principle applied to a record that holds far more.
**There is no parameter anywhere in it that accepts a field VALUE.** Not one.

  * the caller names the REQUEST FIELDS involved — `["account_no", "amount"]` —
    and each name must match an identifier pattern, so `"account_no=12345"`,
    `"12345"` and `"balance is 181.94"` are all REFUSED;
  * the caller names the SETTINGS that shape the failure — and **this module
    reads their values itself**, from `django.conf.settings`, through a secret
    filter. A caller physically cannot pass a settings value because there is
    no parameter that takes one;
  * the caller passes the EXCEPTION OBJECT, and this module takes its TYPE, its
    module, and its traceback FRAMES. **`str(exc)` is never read, anywhere in
    this file.** Grep it: the message does not appear in an assembled record,
    and the only defence that survives a future lane is that nothing here ever
    holds it.

Everything else — `error_code`, `component`, `audit_action` — is validated
against a strict pattern before it is stored, because a "code" parameter is
exactly where a hurried call site would interpolate a value.

⚠ **A REFUSED INPUT LOSES THE WHOLE RECORD, DELIBERATELY.** The alternative —
dropping the offending name and keeping the rest — produces a diagnostic that
is quietly missing the thing somebody will look for, and no reader can tell
which. Refusing outright leaves a loud log line naming the PARAMETER (never its
value) and a one-line fix at the call site. `capture()` still never raises: it
must not break the run it is describing (the same posture, for the same reason,
as `_audit_failed_block` in `apps/tenancy/sample_data.py`).

WHAT THIS FILE DOES NOT DO
--------------------------
It writes **no `audit_log` row**. Hard rule 7 attaches the trail to a MONEY
ACTION; recording why something broke is not one, and the permanent row for the
failure is written by the call site that already writes it (CR-067 task A4 adds
the reference to that row). Two records, one reference, no duplication.

It also holds **no foreign key into `audit_log`, and `audit_log` holds none
into it.** They have deliberately different lifetimes — one permanent, one
pruned — and a foreign key would make one hostage to the other's retention.
**They join on the reference, which is a value and not a constraint** (CR-067
§3 / task A1).
"""

from __future__ import annotations

import datetime as dt
import functools
import logging
import pathlib
import re
import traceback
import uuid
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from django.conf import settings

from core.tenancy import current_tenant_id

logger = logging.getLogger("smartbillhub.diagnostics")


# ── The short reference ─────────────────────────────────────────────────────
# ⚠ THE FRONT END HAS AN IDENTICAL FORMATTER AND THE TWO ARE A PAIR:
# `07-frontend/src/api/client.ts` → `supportRef()` / `SUPPORT_REF_HEX` /
# `SUPPORT_REF_ABSENT`, added under the PO ruling of 2026-08-19 (DEF-328). It
# shortens a trace id the SERVER minted; this shortens the same trace id on the
# server so the permanent audit row and the diagnostic can carry the identical
# string. **Change one and you must change the other**, or a person reads a
# reference off one screen that the other cannot find.
#
# The shape is also the SEARCHABLE shape: `apps/audit/selectors.audit_queryset`
# matches by PREFIX with dashes and case ignored, so `5F2B-9C1D` finds the row
# carrying the full trace id.

#: How many hex characters of the trace id a person is asked to read aloud.
SUPPORT_REF_HEX = 8

#: What the reference renders as when there was no trace id at all.
SUPPORT_REF_ABSENT = "—"


def support_ref(trace_id: str | None) -> str:
    """`5f2b9c1d3e…` → `5F2B-9C1D`. Uppercase and grouped, because it is dictated.

    Character-for-character the same rule as `supportRef()` in
    `07-frontend/src/api/client.ts`; see the note above on why they are a pair.
    """
    hex_only = re.sub(r"[^0-9a-fA-F]", "", trace_id or "")[:SUPPORT_REF_HEX]
    if len(hex_only) < SUPPORT_REF_HEX:
        return SUPPORT_REF_ABSENT
    return f"{hex_only[:4]}-{hex_only[4:]}".upper()


def new_trace_id() -> str:
    """A fresh 32-hex trace id — the same form `core.errors` mints per refusal."""
    return uuid.uuid4().hex


# ── What a caller may name, and nothing else ────────────────────────────────
#: A request field NAME. An identifier and nothing else, which is what refuses
#: `account_no=12345`, `12345`, `balance is 181.94` and every other shape a
#: value arrives in.
FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

#: A Django settings name. UPPER_SNAKE, which is what Django itself enforces.
SETTING_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")

#: A stable error code — `SD-PRECONDITION`, `BIZ-CAP`, `storage_not_configured`.
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

#: Where in the product this happened, as a NAME: `tenancy:sample_data`,
#: `billing:seed_sample_records`. Never a sentence, never a value.
COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")

#: The dotted `entity.action` grammar `audit_log.action` already uses.
ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

#: A job kind — `audit_export`, `tenancy.sample_data_plant`. Dotted because
#: `PLANT_JOB_KIND` is, and a pattern that refused a kind this product already
#: registers would refuse the exact capture site CR-067 task A3 names first.
JOB_KIND_RE = re.compile(r"^[a-z][a-z0-9_.]{0,63}$")

#: Settings whose NAME says the value is a secret. Matched as substrings, so
#: the list is short and errs wide: a setting wrongly treated as secret loses
#: one line of context, a secret wrongly recorded is a credential in a database
#: somebody exports. Not symmetric, so not a close call.
SECRET_NAME_MARKERS: tuple[str, ...] = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "KEY",
    "CREDENTIAL",
    "PRIVATE",
    "SALT",
    "SIGNATURE",
    "DSN",
    "AUTH",
    "COOKIE",
)

#: How much of a long settings value is kept. A path or a host is short; a
#: template directory list is not, and a diagnostic is read by a person.
SETTING_VALUE_CHARS = 200

#: How many traceback frames are kept. Deep enough for a recursive seeder,
#: bounded so one runaway stack cannot fill the table.
MAX_FRAMES = 40

#: How many links of the `__cause__` / `__context__` chain are followed. Law 14
#: is the reason this exists at all: *"`exc.__cause__` on a caught Django
#: `IntegrityError` is ANOTHER Django `IntegrityError`; the driver's exception
#: with the real SQLSTATE is two or three hops down."* A record that stopped at
#: the outermost type would be the same "looks handled" failure that law names.
MAX_CAUSE_LINKS = 6


class DiagnosticInputRefused(ValueError):
    """A caller tried to put something in a diagnostic that is not a NAME.

    Raised by `assemble()`, which is pure and testable. `capture()` catches it,
    logs the offending PARAMETER (never its value) and writes nothing.
    """


# ── The sink (the `core.audit` split, for the same reason) ──────────────────
DiagnosticSink = Callable[[dict[str, Any]], None]
_sink: DiagnosticSink | None = None


def set_diagnostic_sink(sink: DiagnosticSink | None) -> None:
    """Register (or clear, with None) the persistence sink. apps.audit only."""
    global _sink
    _sink = sink


def diagnostic_sink() -> DiagnosticSink | None:
    """The registered sink, for a caller that wants to know whether one exists."""
    return _sink


# ── Which settings explain which failure ────────────────────────────────────
# A capture site knows what it was doing; it does not know which SETTINGS make
# a `StorageNotConfigured` reproducible, and it should not have to. The module
# that owns the exception registers that from its own AppConfig.ready(), the
# way apps.audit registers the audit sink.
#
# This is what makes CR-067 §5's acceptance test writable from the record of a
# failure the seeding plant knew nothing about:
#
#     settings.DOCUMENT_STORAGE_BACKEND          = "aws_s3"
#     settings.DOCUMENT_STORAGE_BUCKET           = ""
#     settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
#     with pytest.raises(StorageNotConfigured):
#         document_storage.backend()
_settings_for_exception: dict[type[BaseException], tuple[str, ...]] = {}


def register_settings_for(exc_type: type[BaseException], names: Sequence[str]) -> None:
    """Declare the settings that explain `exc_type`, so a record of it is complete.

    Registered by the module that OWNS the exception, from its AppConfig, and
    honoured for every subclass through the MRO walk in `settings_for()`. Names
    are validated here rather than at capture time, so a typo fails at boot
    instead of producing a quietly incomplete record months later.
    """
    for name in names:
        if not SETTING_NAME_RE.match(name):
            raise DiagnosticInputRefused(
                f"register_settings_for({exc_type.__name__}): {name!r} is not a "
                "settings NAME (UPPER_SNAKE). A diagnostic records names, never values."
            )
    _settings_for_exception[exc_type] = tuple(names)


def clear_registered_settings() -> None:
    """Drop every registration — for tests that assert the registry's own shape."""
    _settings_for_exception.clear()


def settings_for(exc: BaseException) -> tuple[str, ...]:
    """Every registered settings name that applies to `exc`, nearest type first."""
    names: list[str] = []
    for klass in type(exc).__mro__:
        for name in _settings_for_exception.get(klass, ()):
            if name not in names:
                names.append(name)
    return tuple(names)


# ── Reading a settings VALUE, which the caller never supplies ───────────────
_ABSENT = object()


def _is_secret_name(name: str) -> bool:
    return any(marker in name for marker in SECRET_NAME_MARKERS)


def settings_snapshot(names: Iterable[str]) -> dict[str, Any]:
    """`{NAME: value}` for settings this module reads ITSELF.

    ⚠ THE CALLER NAMES; THIS READS. That is the whole guarantee — there is no
    path by which a caller-supplied value reaches a stored record.

    Three rules on the value, each one stated because a reader of the record
    needs to know what a given string means:

    * a name that LOOKS like a secret records `"<set>"` or `"<unset>"` and never
      its value. Whether a credential is configured is the diagnostic fact; the
      credential is not;
    * a setting the module does not define at all records `"<not defined>"`,
      which is a different fact from an empty string and is exactly the
      difference that mattered on 2026-09-02;
    * anything that is not a scalar records `"<TypeName>"`. A record is read by
      a person, and a serialised `DATABASES` dict is both unreadable and full of
      passwords.
    """
    snapshot: dict[str, Any] = {}
    for name in names:
        if not SETTING_NAME_RE.match(name):
            raise DiagnosticInputRefused(
                f"settings_named: {name!r} is not a settings NAME (UPPER_SNAKE)."
            )
        raw = getattr(settings, name, _ABSENT)
        if _is_secret_name(name):
            snapshot[name] = "<not defined>" if raw is _ABSENT else ("<set>" if raw else "<unset>")
            continue
        if raw is _ABSENT:
            snapshot[name] = "<not defined>"
        elif raw is None or isinstance(raw, (bool, int, float)):
            # bool before int is deliberate — `bool` IS an `int` in Python and
            # the tuple catches both, so neither is coerced (core.audit.jsonable
            # makes the same point for the same reason).
            snapshot[name] = raw
        elif isinstance(raw, str):
            snapshot[name] = (
                raw
                if len(raw) <= SETTING_VALUE_CHARS
                else raw[:SETTING_VALUE_CHARS] + f"… (+{len(raw) - SETTING_VALUE_CHARS} chars)"
            )
        else:
            snapshot[name] = f"<{type(raw).__name__}>"
    return snapshot


# ── Reading an EXCEPTION, without ever reading its message ──────────────────
def _repo_relative(path: str) -> str:
    """`/srv/app/06-backend/apps/tenancy/x.py` → `06-backend/apps/tenancy/x.py`.

    A deployment's absolute paths say where a container mounted the code and
    nothing a reader needs; the repo-relative path is the thing somebody opens.
    """
    marker = "/06-backend/"
    index = path.rfind(marker)
    return f"06-backend/{path[index + len(marker):]}" if index >= 0 else path


def exception_frames(exc: BaseException) -> list[dict[str, Any]]:
    """The traceback as `{file, function, line}`, outermost first.

    ⚠ **NO SOURCE TEXT AND NO MESSAGE.** `traceback.format_exc()` ends with the
    exception's own message, which is the one string this whole module exists
    to keep out of storage, and its source lines are read off disk at format
    time — so a record written by one release and read after another would show
    lines that were never executed. File, function and line number locate the
    code exactly when read beside the `release` the record already carries, and
    they cannot carry a customer's data.
    """
    frames = traceback.extract_tb(exc.__traceback__)[-MAX_FRAMES:]
    return [
        {"file": _repo_relative(frame.filename), "function": frame.name, "line": frame.lineno}
        for frame in frames
    ]


def exception_chain(exc: BaseException) -> list[dict[str, str]]:
    """`__cause__` / `__context__` as TYPES, innermost last.

    Hard-won law 14: *"`exc.__cause__` on a caught Django `IntegrityError` is
    ANOTHER Django `IntegrityError`; the driver's exception with the real
    SQLSTATE is two or three hops down. A first draft that read one hop returned
    the generic sentence for every row and LOOKED HANDLED."* A diagnostic that
    recorded only the outermost type would reproduce that failure exactly.
    """
    chain: list[dict[str, str]] = []
    seen: set[int] = set()
    current: BaseException | None = exc.__cause__ or exc.__context__
    while current is not None and len(chain) < MAX_CAUSE_LINKS and id(current) not in seen:
        seen.add(id(current))
        chain.append({"type": type(current).__name__, "module": type(current).__module__})
        current = current.__cause__ or current.__context__
    return chain


# ── Assembling a record — pure, strict, and the thing tests point at ────────
def validated_field_names(names: Sequence[str]) -> list[str]:
    """The request's field NAMES, refusing anything that is not one.

    This is the function a test points at to prove a value cannot be smuggled
    in. It is deliberately separate from `capture()` so the refusal can be
    asserted directly rather than inferred from an absent row.
    """
    validated: list[str] = []
    for name in names:
        if not isinstance(name, str) or not FIELD_NAME_RE.match(name):
            raise DiagnosticInputRefused(
                "request_fields takes field NAMES, never values, and "
                f"{type(name).__name__} {name!r} is not a name. A diagnostic records "
                "which fields were involved; the audit log has no delete and neither "
                "record may carry an account number, a balance or a reading."
            )
        if name not in validated:
            validated.append(name)
    return validated


def _validated(pattern: re.Pattern[str], value: str, parameter: str) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise DiagnosticInputRefused(
            f"{parameter} must match {pattern.pattern} — it is a NAME, not a value or "
            "a sentence. (A diagnostic that accepted free text would be the exact hole "
            "CR-067 §2 exists to close.)"
        )
    return value


@functools.lru_cache(maxsize=1)
def _pyproject_version() -> str:
    """The version literal `06-backend/pyproject.toml` already carries.

    ⚠ DERIVED, NEVER COPIED (hard-won law 5 — *"one generated file, committed
    once… one source; derive views on demand"*). `12-governance/13-change-process.md`
    step 7 rule 1 says the same thing about the version specifically, and G35
    already holds `pyproject.toml` and `package.json` in lockstep. Adding a
    Python constant here would create a FIFTH literal for a human to keep in
    step, which is the exact failure step 7 exists to stop.
    """
    try:
        import tomllib

        text = (pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text("utf-8")
        return str(tomllib.loads(text)["project"]["version"])
    except Exception:  # noqa: BLE001 — a diagnostic must survive an unreadable build file
        return "unknown"


def release() -> str:
    """The build this happened on. A deployment may stamp `PRODUCT_VERSION`."""
    return str(getattr(settings, "PRODUCT_VERSION", "") or _pyproject_version())


def retention_days() -> int:
    """How long a diagnostic is kept — CR-067 task A5, default 90, configurable.

    ⚠ `OQ-1390` IS OPEN: is 90 right, and does a diagnostic fall under the same
    retention regime as `audit_log` or its own? It is proposed as its own,
    because a diagnostic holds no customer data and therefore has no legal
    floor. **Nothing here guesses at the answer**: the ruling moves a number in
    `config/settings/base.py` and touches no code, which is why this is a
    setting rather than a constant and why no stub is owed at this boundary.
    """
    days = int(getattr(settings, "DIAGNOSTIC_RETENTION_DAYS", 90))
    return days if days > 0 else 90


def assemble(
    *,
    error_code: str,
    exception: BaseException,
    component: str,
    settings_named: Sequence[str] = (),
    request_fields: Sequence[str] = (),
    job_kind: str | None = None,
    job_id: Any = None,
    step: int | None = None,
    step_total: int | None = None,
    audit_action: str | None = None,
    trace_id: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """One diagnostic record, as a dict — pure, and it RAISES on a bad input.

    Every parameter above is a name, a number or the exception object itself.
    **There is no parameter that accepts a value**, and that absence is the
    guarantee: it survives a lane that never reads this docstring.
    """
    if not isinstance(exception, BaseException):
        raise DiagnosticInputRefused(
            "exception must be the exception OBJECT — this module takes its type, "
            "its module and its frames, and never its message."
        )
    moment = now or dt.datetime.now(dt.timezone.utc)
    resolved_trace = (trace_id or new_trace_id()).strip()
    reference = support_ref(resolved_trace)
    if reference == SUPPORT_REF_ABSENT:
        raise DiagnosticInputRefused(
            f"trace_id {resolved_trace!r} is shorter than {SUPPORT_REF_HEX} hex "
            "characters, so it cannot form a reference a person could quote."
        )
    names = list(settings_for(exception))
    for name in settings_named:
        if name not in names:
            names.append(name)
    return {
        "tenant_id": current_tenant_id(),
        "reference": reference,
        "trace_id": resolved_trace,
        "error_code": _validated(CODE_RE, error_code, "error_code"),
        "component": _validated(COMPONENT_RE, component, "component"),
        "exception_type": type(exception).__name__,
        "exception_module": type(exception).__module__,
        "exception_chain": exception_chain(exception),
        "frames": exception_frames(exception),
        "settings_in_force": settings_snapshot(names),
        "request_fields": validated_field_names(request_fields),
        "job_kind": None if job_kind is None else _validated(JOB_KIND_RE, job_kind, "job_kind"),
        "job_id": None if job_id is None else str(job_id),
        "step": None if step is None else int(step),
        "step_total": None if step_total is None else int(step_total),
        "audit_action": (
            None if audit_action is None else _validated(ACTION_RE, audit_action, "audit_action")
        ),
        "release": release(),
        "created_at": moment,
        "expires_at": moment + dt.timedelta(days=retention_days()),
    }


def capture(
    *,
    error_code: str,
    exception: BaseException,
    component: str,
    settings_named: Sequence[str] = (),
    request_fields: Sequence[str] = (),
    job_kind: str | None = None,
    job_id: Any = None,
    step: int | None = None,
    step_total: int | None = None,
    audit_action: str | None = None,
    trace_id: str | None = None,
) -> str:
    """Store one diagnostic and return the REFERENCE to quote beside it.

    **It always returns a reference and it never raises.** The reference is
    minted before anything can fail, so the permanent audit row can carry it
    whatever happens here — and when the detail was refused, never stored, or
    has since expired, the drawer says so honestly rather than showing a
    reference that leads nowhere by accident.

    It never raises for the reason `_audit_failed_block` never raises: an extra
    record must not break the run it is describing (BR-TEN-063 —*"one module
    must not stop the rest"*).
    """
    resolved_trace = trace_id or new_trace_id()
    reference = support_ref(resolved_trace)
    try:
        row = assemble(
            error_code=error_code,
            exception=exception,
            component=component,
            settings_named=settings_named,
            request_fields=request_fields,
            job_kind=job_kind,
            job_id=job_id,
            step=step,
            step_total=step_total,
            audit_action=audit_action,
            trace_id=resolved_trace,
        )
    except DiagnosticInputRefused as refusal:
        # The PARAMETER and the reason, never the offending value: a server log
        # is not append-only, but writing the value here would put back exactly
        # what the signature refused a line earlier.
        logger.error(
            "diagnostic %s REFUSED at %s: %s. Nothing was stored; fix the call site.",
            reference,
            component if COMPONENT_RE.match(str(component)) else "<component refused>",
            refusal,
        )
        return reference
    if _sink is None:
        logger.warning(
            "diagnostic %s could not be stored: no sink is registered "
            "(apps.audit registers it from AppConfig.ready).",
            reference,
        )
        return reference
    try:
        _sink(row)
    except Exception:  # noqa: BLE001 — a diagnostic must not break the run it describes
        logger.exception(
            "diagnostic %s could not be stored; the permanent audit row still "
            "carries the reference and reads correctly without it.",
            reference,
        )
    return reference


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 §3 (the approved shape) + §5 (the acceptance test) + tasks A1/A2/A4 — 12-governance/11-change-requests.md; shared law: BR-AUD-002, BR-AUD-006, CLAUDE.md hard rules 1 and 7, hard-won law 14
# generated: 2026-09-02 by the CR-067 backend lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09) — ⚠ AMENDED 2026-09-02 by the CR-067 B2/B3 lane: the record IS served beside the audit row it references now, by `GET /audit-log/{id}/diagnostic`, and every field this module assembles is drawn on the S61 drawer for a System Admin (hard-won law 1).
# gates: see the lane report
# exceptions: (1) NO `audit_log` ROW is written here — hard rule 7 attaches the trail to a MONEY action, and the permanent row for the failure is written by the call site that already writes one (task A4 adds the reference to it). (2) NO FK to `audit_log` in either direction, by CR-067 §3: the two have different lifetimes and a foreign key would make one hostage to the other's retention. (3) The settings VALUES are recorded while field values are refused — a deployment's configuration is operator data with no legal floor, it is what CR-067 §5's own worked example prints, and it is filtered by the secret-name list above; the judgment is in 12-governance/02-decision-log.md.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

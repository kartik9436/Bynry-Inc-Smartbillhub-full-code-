#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-024 (EP-INT-07) TC-6 — the three exits: after a rotation, the
#         database dump, the captured logs and `audit_log` are searched for
#         both plaintexts and there are ZERO hits in all three. CR-069 §13's
#         second gate: *"a credential never reaches a log, an audit row or an
#         error body — phase 2's exit test as a PERMANENT CHECK rather than a
#         one-off demonstration"*.
# Rules:  BR-INT-003 (a credential is never rendered back, logged or put in an
#         audit payload — masked hints only) · BR-INT-038 (an adapter
#         translates; it decides nothing) · CLAUDE.md hard rule 7 (every money
#         action writes audit_log — so an audit payload is a read path this
#         has to answer for) · hard-won law 1 (a comment claiming a guarantee
#         is not the guarantee) · law 7 (prove a guard RED before trusting it
#         green, and prove it THROUGH THE HARNESS THAT WILL RUN IT)
# Impacts: apps/integrations/adapters/*.py · apps/integrations/services.py ·
#         apps/integrations/seams/*.py · apps/integrations/jobs.py ·
#         apps/integrations/runners/*.py · apps/integrations/conformance.py
# ───────────────────────────────────────────────────────
"""G94 — THE PLAINTEXT CREDENTIAL HAS EXACTLY ONE READER AND THREE EXITS IT MAY NOT TAKE.

WHY THIS EXISTS AND WHY THE CONFORMANCE KIT IS NOT ENOUGH
----------------------------------------------------------
`apps/integrations/conformance.py` already runs a *no credential in any log
line* case over every adapter, and it is the better check because it RUNS the
code. But it can only see the adapters somebody has bound to it, and it cannot
see `services.py`, `jobs.py`, the runners or the seams — which are the files
that HOLD the plaintext on its way to the adapter and hand the outcome back.

So this gate reads source, and it is honest about that being the weaker half:
a `_SANCTIONED` pattern list cannot prove a secret never leaks, only that
nobody wrote the four shapes that leaked one before. **It is a REDUCTION, not
a promise** — the same posture `scrubbing.py` takes and for the same reason.

THE FOUR THINGS IT REFUSES, each a real way the password gets out
------------------------------------------------------------------
1. **A LOGGER IN THE CREDENTIAL PATH.** No file under `apps/integrations/` may
   call `logging.getLogger`, `logger.<level>`, `print(` or `warnings.warn` —
   because the plaintext is a local variable in three of these files and a
   logger is what a lane reaches for at two in the morning. There is one
   sanctioned logger and it is not here.
2. **THE SECRET IN AN AUDIT PAYLOAD.** A `core_audit.money_action(...)` call
   whose `before=`/`after=` mentions `payload`, `password`, `secret`, `token`
   or `credential_secrets` — as opposed to `masked_hint`, `hint` or `hints`,
   which are the mask and are the whole point.
3. **A SECOND READER OF `payload_enc`.** `services.credential_secrets` is the
   ONE reader (BR-INT-003, and its own docstring says *a grep for this name is
   the audit*). Any other file naming `payload_enc` outside the model, the
   migrations and this gate's allow-list is a finding.
4. **THE SECRET IN AN f-STRING.** `f"…{password}…"`, `f"…{secret}…"`,
   `f"…{payload}…"` — the shape a sentence, a URL or an exception message
   takes on its way to a screen. `TestResult.sentence` is written from module
   constants precisely so this pattern has nowhere to live.

⚠ **SELF-TEST FIRST, AND THROUGH `run()` (DEF-GOV-3733).** `selftest()` runs
the four checks over four synthetic sabotages and four clean strings, and
`run()` refuses to report PASS if any sabotage fails to bite. A gate that
cannot fail is worse than no gate because it is trusted — DEF-182's lesson —
and a gate proved only through `__main__` is proved through a path the suite
never uses.

PROVEN RED FIRST (law 7, 2026-09-04) by adding, one at a time, to
`apps/integrations/adapters/email_smtp.py`:

    logger.info("connecting as %s", password)
        → FAIL  adapters/email_smtp.py:213 logs from the credential path
    core_audit.money_action(actor, "x", "y", 1, after={"password": password})
        → FAIL  adapters/email_smtp.py:220 puts a credential in an audit payload
    row = models.IntegrationCredential.objects.only("payload_enc").first()
        → FAIL  adapters/email_smtp.py:214 reads payload_enc — services.credential_secrets is the one reader
    raise ValueError(f"could not log in as {username}:{password}")
        → FAIL  adapters/email_smtp.py:216 interpolates a credential into a string
"""

import re
import sys
from pathlib import Path

import common

BACKEND = common.REPO_ROOT / "06-backend"
MODULE = Path("apps") / "integrations"

#: ⚠ `conformance.py` MAY TOUCH `logging`, AND IT IS THE ONE EXCEPTION. It
#: does not WRITE a log line — it INSTALLS A HANDLER AND READS THEM BACK, so
#: that the kit's *no credential in any log line* case has something to assert
#: over. Refusing it would be this gate forbidding the test that proves the
#: rule it is guarding.
#: The one reader, by name. Everything else naming the column is a finding.
ONE_READER = "credential_secrets"

#: Files allowed to name `payload_enc` at all: the model that declares the
#: column, the migration that writes it once, and the service that reads it.
_MAY_NAME_PAYLOAD_ENC = (
    "models.py",
    "services.py",
    "migrations/",
)

_LOGGING = re.compile(
    r"\b(?:logging\.getLogger|logger\s*\.\s*(?:debug|info|warning|warn|error|exception|critical)"
    r"|warnings\.warn|print)\s*\("
)
#: ⚠ TWO WORD SETS, AND THE DIFFERENCE COST A FALSE POSITIVE THE FIRST TIME
#: THIS GATE WAS RUN. Bare `payload` is a credential in `record_credential(
#: payload=...)` and it is a JOB payload in `core_jobs.enqueue(payload=...)`
#: eight lines away. So the audit check names `payload_enc` — the column —
#: and the f-string check keeps bare `payload`, because a local called
#: `payload` interpolated into a sentence is a leak whatever else the word
#: means elsewhere.
_AUDIT_SECRETISH = r"(?:password|passwd|secret|payload_enc|token|credential_secrets)"
_FSTRING_SECRETISH = r"(?:password|passwd|secret|payload|token|credential_secrets)"
_AUDIT = re.compile(r"money_action\s*\(", re.I)
#: ⚠ A KEY OR AN IDENTIFIER, NEVER A WORD INSIDE A SENTENCE — and this cost a
#: second false positive on the first run. `disconnect()`'s audit payload
#: carries the honest clerk sentence *"no password was stored"*, which
#: contains the word and no password. So the two shapes that ARE findings are
#: named exactly: `"password":` (a dict key) and `: password` / `=password`
#: (a bare identifier handed in as a value). A gate that cannot tell a
#: variable from an English word will be switched off by the third lane that
#: meets it.
_AUDIT_KEY = re.compile(rf"['\"]{_AUDIT_SECRETISH}\w*['\"]\s*:", re.I)
_AUDIT_VALUE = re.compile(rf"[:=]\s*\w*{_AUDIT_SECRETISH}\w*\s*[,}}\)]", re.I)
_FSTRING_SECRET = re.compile(rf"f['\"][^'\"]*\{{\s*\w*{_FSTRING_SECRETISH}\w*\s*[}}:!]", re.I)
_PAYLOAD_ENC = re.compile(r"\bpayload_enc\b")

#: ⚠ **AN `Authorization` HEADER IS NOT ONE OF THE FOUR EXITS, AND THIS IS THE
#: ONLY THING EXEMPTED.** Rule 4 above is about the shape a secret takes *"on
#: its way to a screen"* — a sentence, a URL, an exception message, a log line.
#: A bearer token in an Authorization header is on its way to the PROVIDER, on
#: the wire, and there is no way to authenticate an HTTPS request without
#: putting the token into a string exactly once.
#:
#: Added 2026-09-06 for `adapters/oauth_mailbox.py`, which dials Microsoft Graph
#: and the Gmail API. **The alternative was worse in a way worth naming:** the
#: obvious way to "fix" the finding is `"Bearer " + token`, which is the same
#: secret in the same string with the pattern filed off — a gate defeated
#: rather than satisfied, and the next reader would have no idea it happened.
#:
#: ⚠ **THE CARVE-OUT IS THE WHOLE LINE, NOT THE WORD.** It matches only a line
#: whose f-string is the VALUE of an `Authorization` key: `"Authorization":
#: f"Bearer {token}"`. `f"...?access_token={token}"` is still a finding, and so
#: is `"X-Debug": f"{token}"` — both are asserted in `selftest()` below,
#: because a carve-out with no near-miss test is a hole with a comment on it.
_AUTHORIZATION_HEADER = re.compile(
    r"""['"]Authorization['"]\s*:\s*f['"][^'"]*['"]""", re.I
)

#: A mask is not a secret, and these three words are how the product says so.
_MASKS = ("masked_hint", '"hint"', '"hints"', "hint=", "hints=")


def _strip_comments_and_docstrings(source: str) -> str:
    """Findings are about CODE. A docstring that names `payload_enc` while
    explaining the rule — as three files in this module do, correctly — is not
    a leak, and a gate that could not tell the difference would push the
    explanations out of the files that most need them."""
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith(('"""', "'''"), i):
            quote = source[i : i + 3]
            end = source.find(quote, i + 3)
            stop = n if end == -1 else end + 3
            # ⚠ ONE NEWLINE PER NEWLINE REMOVED, NEVER ONE PER DOCSTRING. The
            # first draft of this collapsed every docstring to a single "\n"
            # and every line number after the module docstring was wrong — it
            # reported `conformance.py:80` for a call on line 122. A finding
            # that names the wrong line is a finding nobody can act on.
            out.append("\n" * source.count("\n", i, stop))
            i = stop
            continue
        if ch in "\"'":
            # A short string may hold an f-string finding, so keep it.
            j = i + 1
            while j < n and source[j] != ch:
                if source[j] == "\\":
                    j += 1
                j += 1
            out.append(source[i : j + 1])
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _call_text(code: str, open_paren: int) -> str:
    """The source of ONE call, from its opening bracket to the matching close.

    Naive on purpose — it counts brackets and does not parse — but it stops at
    the right place, which a fixed-width window does not."""
    depth = 0
    for i in range(open_paren, len(code)):
        if code[i] == "(":
            depth += 1
        elif code[i] == ")":
            depth -= 1
            if depth == 0:
                return code[open_paren : i + 1]
    return code[open_paren:]


def findings(source: str, *, where: str) -> list[str]:
    """The four checks, over one file's code. Pure, so `selftest` can drive it."""
    code = _strip_comments_and_docstrings(source)
    out: list[str] = []
    may_touch_logging = where.endswith("conformance.py")
    for number, line in enumerate(code.splitlines(), start=1):
        if _LOGGING.search(line) and not may_touch_logging:
            out.append(f"{where}:{number} logs from the credential path — this module has no logger on purpose")
        if _FSTRING_SECRET.search(line) and not _AUTHORIZATION_HEADER.search(line):
            out.append(f"{where}:{number} interpolates a credential into a string")
    # An audit payload is read across the call, not line by line: the dict is
    # usually several lines below `money_action(`.
    for match in _AUDIT.finditer(code):
        # ⚠ THE WINDOW IS THE CALL, NOT A FIXED NUMBER OF CHARACTERS. A 900-
        # character window ran off the end of `money_action(...)` in
        # `services.py` and into an unrelated `core_jobs.enqueue(payload=...)`
        # eight lines below, and reported the job payload as a credential.
        window = _call_text(code, match.end() - 1)
        hit = _AUDIT_KEY.search(window) or _AUDIT_VALUE.search(window)
        if hit is not None and not any(mask in hit.group(0) for mask in _MASKS):
            number = code[: match.start()].count("\n") + 1
            out.append(
                f"{where}:{number} puts a credential in an audit payload ({hit.group(0).strip()})"
            )
    if not where.endswith(_MAY_NAME_PAYLOAD_ENC) and "migrations/" not in where:
        for number, line in enumerate(code.splitlines(), start=1):
            if _PAYLOAD_ENC.search(line):
                out.append(
                    f"{where}:{number} reads payload_enc — services.{ONE_READER} is the one reader"
                )
    return out


_RED_LOG = 'def test(self):\n    logger.info("connecting as %s", password)\n'
_RED_AUDIT = 'money_action(actor, "x", "y", one.id, after={"password": password})\n'
_RED_PAYLOAD = 'row = Credential.objects.only("payload_enc").first()\n'
_RED_FSTRING = 'raise ValueError(f"could not log in as {username}:{password}")\n'
_RED_AUDIT_VALUE = 'money_action(actor, "x", "y", one.id, after={"a": password})\n'
#: ⚠ THE TWO NEAR MISSES FOR THE `Authorization` CARVE-OUT. Both put the same
#: token in the same kind of string and BOTH MUST STILL BITE, or the carve-out
#: is a hole rather than a distinction: a token in a QUERY STRING is a secret in
#: a URL (which is logged by every proxy it passes), and a token under any other
#: header name is not authentication, it is a leak wearing a header's clothes.
_RED_TOKEN_IN_URL = 'url = f"https://graph.example/v1/me?access_token={token}"\n'
_RED_TOKEN_OTHER_HEADER = 'headers = {"X-Debug-Token": f"Bearer {token}"}\n'
#: Four clean shapes, and the fourth is the one that caught this gate out:
#: the WORD in a sentence a clerk reads, which is not a credential.
_CLEAN = (
    'money_action(actor, "x", "y", one.id, after={"masked_hint": hint, "hints": arrow})\n'
    'secrets = services.credential_secrets(connection)\n'
    'return TestResult(ok=False, sentence=REJECTED_PASSWORD)\n'
    'raise ValueError(f"unknown provider {key}")\n'
    'money_action(actor, "x", "y", one.id, after={"summary": "no password was stored"})\n'
    'core_jobs.enqueue(KIND, scope_key=key, payload={"connection_id": str(one.id)})\n'
    # The Authorization header — on the wire to the provider, not to a screen.
    'headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}\n'
)


def selftest() -> list[str]:
    """Every sabotage must bite and the clean sample must not. Returned as a
    list of what went wrong so `run()` can say WHICH half is broken."""
    broken: list[str] = []
    for name, sample, expect in (
        ("logging", _RED_LOG, "logs from the credential path"),
        ("audit key", _RED_AUDIT, "puts a credential in an audit payload"),
        ("audit value", _RED_AUDIT_VALUE, "puts a credential in an audit payload"),
        ("payload_enc", _RED_PAYLOAD, "reads payload_enc"),
        ("f-string", _RED_FSTRING, "interpolates a credential"),
        ("token in a URL", _RED_TOKEN_IN_URL, "interpolates a credential"),
        ("token under another header", _RED_TOKEN_OTHER_HEADER, "interpolates a credential"),
    ):
        hits = findings(sample, where="selftest.py")
        if not any(expect in one for one in hits):
            broken.append(f"the {name} sabotage does not bite")
    if findings(_CLEAN, where="selftest.py"):
        broken.append("the clean sample is reported as a finding")
    return broken


def _module_files() -> list[Path]:
    root = BACKEND / MODULE
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test does not hold — " + "; ".join(broken)
    files = _module_files()
    if not files:
        return "FAIL", f"{MODULE} holds no Python files — the module this gate guards does not exist"
    problems: list[str] = []
    adapters = 0
    for path in files:
        relative = str(path.relative_to(BACKEND / "apps" / "integrations"))
        if relative.startswith("adapters/") and relative != "adapters/__init__.py":
            adapters += 1
        problems.extend(findings(path.read_text(encoding="utf-8"), where=relative))
    if problems:
        return "FAIL", common.summarize(problems, limit=6)
    return "PASS", (
        f"{len(files)} file(s) under apps/integrations, {adapters} real adapter(s): no logger in the "
        f"credential path, no credential in an audit payload, no second reader of payload_enc, no "
        f"secret in an f-string; self-test: all four sabotages bite. A REDUCTION, not a promise — "
        f"the conformance kit runs the same assertion against code that executes"
    )


def main() -> int:
    status, note = run()
    print(f"{status}: {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

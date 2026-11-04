# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 2 task `P2.20`
#          (*"BI tier 1 — service accounts"*, p12 and §7.8 p88–p89, read as
#          images per B14 rule 42).
# Rules:   CLAUDE.md hard rule 1 (tenant scoping — RLS FORCE, `app.tenant_id`,
#          no cross-tenant queryset; this principal takes it UNCHANGED) ·
#          hard rule 7 (every money action writes `audit_log`) · hard-won
#          law 1 (a comment claiming a guarantee is not the guarantee) ·
#          BR-AUD-019 (an automation actor names itself)
# Tests:   06-backend/tests/test_rep_p2_20_service_accounts.py
#          10-scripts/rep_p2_20_service_account_rls_proof.py (two tenants, real
#          PostgreSQL, a NOBYPASSRLS role)
# Impacts: apps/reports/api.py (the three endpoints and the authentication) ·
#          apps/reports/migrations/0006_p2_20_service_accounts.py
# ───────────────────────────────────────────────────────
"""A MACHINE PRINCIPAL FOR THE REPORT API — ISSUE, AUTHENTICATE, REVOKE.

THE RULING, AND THE ONE WORD IT TURNS ON
────────────────────────────────────────
Brief §7.8, p89: *"What a service account is not: a person's password in a BI
config file. That is how a clerk who leaves takes the reporting with them, how
an audit log stops meaning anything, and how a revoked account silently breaks
a board pack."*

And on who may hold one, the PO: *"a · Administrators only … M. Okonkwo creates
it and hands Dana the token + clerk"*. Dana is a billing clerk, so the brief
reads that as **an administrator ISSUES one and any staff member may HOLD and
USE it** — two acts, two people. Whether a clerk may also CREATE one *"is one
line"* and is deliberately NOT assumed: this is a credential, and the narrower
reading ships.

WHY THERE IS NO SECOND SET OF RULES HERE
────────────────────────────────────────
§7.8: *"a BI tool cannot see anything a signed-in person could not, and RLS is
doing the work rather than a second set of rules nobody maintains."* So this
module does exactly two things a browser session does not: it resolves a TOKEN
to a tenant, and it refuses a report key that is not on this principal's named
list. Everything after that — the tenant GUC, every policy, the runner, the
dataset declarations — is the same code path a screen takes. There is no
"service account query", and that absence is the design.

⚠ **THE ALLOW LIST FAILS CLOSED AND THAT DIRECTION IS ITS WHOLE VALUE.** An
empty `report_keys` grants NOTHING. §7.8: *"a connection granted Revenue
Analysis and Trial Balance can read those two and nothing else; AR Ageing later
means somebody grants it."* An empty list that meant *all* would turn a
half-finished create into a key to the building, and it would do so silently.

⚠ **THE TOKEN IS HASHED AND SHOWN ONCE.** A credential a support engineer can
read out of a table is a credential the audit log cannot speak for — the same
failure as the password in the config file, one table over. The comparison is
constant-time, and the LOOKUP is by hash rather than by a scan, so the cost of
an invalid token does not depend on how many accounts a tenant holds.

⚠ **REVOCATION IS A TIMESTAMP, NEVER A DELETE.** *"A revoked account silently
breaks a board pack"* is a thing somebody has to be able to look up afterwards,
and a deleted row takes its own history with it.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Any

from core import audit as core_audit
from core import errors

#: The prefix every token carries, so one found in a log or a config file is
#: recognisable as OURS and as a service-account token rather than a session id.
TOKEN_PREFIX = "sbh_rpt_"

#: 32 bytes of `secrets.token_urlsafe` — 256 bits. Not a uuid: a uuid7 carries
#: its own timestamp and a credential should carry nothing at all.
TOKEN_BYTES = 32

#: How many characters of the token are kept in the clear, to tell two apart on
#: screen without holding either. Short enough to be useless on its own.
PREFIX_KEEP = len(TOKEN_PREFIX) + 6

#: `P2.20`: *"rate-limited"*. Requests per minute per service account.
#: ⚠ **THIS IS A THROTTLE ON ONE CREDENTIAL AND IT IS NOT AN `NFR-5` CAP.**
#: `NFR-5` forbids a per-tenant ceiling on accounts, rows or list length —
#: something that would have to be REMOVED when T4 arrives. A per-credential
#: request rate is a property of the credential, and a bigger utility gets a
#: bigger number or a second account without a migration.
RATE_PER_MINUTE = 60

#: How this principal appears in `Started by` on History — BR-AUD-019's
#: automation actor, `integration` being *"a partner system acting through a
#: connector"*, which is exactly what a BI tool is. The NAME is the account's
#: own, so a board pack that breaks names the credential that broke.
ACTOR_KIND = core_audit.ACTOR_KIND_INTEGRATION


def mint_token() -> tuple[str, str, str]:
    """A new token: `(plaintext, hash, prefix)`. The plaintext is never stored."""
    plaintext = f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_BYTES)}"
    return plaintext, hash_token(plaintext), plaintext[:PREFIX_KEEP]


def hash_token(plaintext: str) -> str:
    """SHA-256 of the token, hex.

    ⚠ **NOT A PASSWORD HASH, AND THE DIFFERENCE IS DELIBERATE RATHER THAN
    LAZY.** A slow KDF exists to make a LOW-ENTROPY secret expensive to guess.
    This secret is 256 bits from `secrets`, so there is nothing to guess and a
    per-request KDF would only make every BI call slower. What a plain digest
    must not be used for is a human-chosen password, and nothing here accepts
    one — `mint_token` is the only way a row is written.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def token_matches(plaintext: str, stored_hash: str) -> bool:
    """Constant-time compare, so a wrong token costs the same as a right one."""
    return hmac.compare_digest(hash_token(plaintext), stored_hash)


def is_live(account: Any, *, now: datetime | None = None) -> bool:
    """Whether this credential may be used at all. Revoked is dead, forever."""
    del now
    return getattr(account, "revoked_at", None) is None


def may_read(account: Any, report_key: str) -> bool:
    """Whether this principal is granted THIS report.

    ⚠ **EMPTY DENIES EVERYTHING** — see the module docstring. Written as an
    explicit membership test rather than `not keys or key in keys`, because the
    second form is one keystroke from meaning the opposite and reads as though
    it were being helpful.
    """
    keys = getattr(account, "report_keys", None) or []
    return str(report_key) in {str(key) for key in keys}


def refuse_report(report_key: str, granted: Any) -> errors.ValidationError:
    """The refusal a BI tool gets for a report it was not granted.

    ⚠ **IT NAMES WHAT IS GRANTED AND NEVER WHAT EXISTS.** A refusal that
    enumerated the whole catalogue would tell an integration — and anybody
    holding a leaked token — the shape of a utility's reporting. The clerk-facing
    route already answers an unknown key with `VAL-005` and the served
    vocabulary; this is a different question asked by a different principal, and
    it gets a different answer on purpose.
    """
    return errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="reports.service_account.not_granted",
        params={"key": report_key, "granted": sorted(str(k) for k in (granted or []))},
        field_errors=[{"field": "key", "code": errors.VAL_UNKNOWN_LOOKUP}],
    )


def audit_issued(account: Any, *, actor_user_id: Any) -> None:
    """One `audit_log` row when a credential is ISSUED, naming the administrator.

    ⚠ **THE ACTOR IS THE PERSON, NOT THE ACCOUNT.** Issuing is an act by an
    administrator; USING is an act by the machine. Writing the machine as the
    actor of its own creation would lose the one fact this row exists to hold —
    *"how an audit log stops meaning anything"*, §7.8.

    ⚠ **NO TOKEN, NO HASH, NO PREFIX IN THE ROW.** An audit trail that carries a
    credential is a second copy of the credential.
    """
    core_audit.write_row(
        action="report_service_account.issued",
        entity_type="report_service_account",
        entity_id=getattr(account, "id", None),
        actor_user_id=actor_user_id,
        after={
            "name": getattr(account, "name", None),
            "report_keys": list(getattr(account, "report_keys", None) or []),
        },
    )


def audit_revoked(account: Any, *, actor_user_id: Any) -> None:
    """One `audit_log` row when a credential is REVOKED. Before-only (BR-AUD-003)."""
    core_audit.write_row(
        action="report_service_account.revoked",
        entity_type="report_service_account",
        entity_id=getattr(account, "id", None),
        actor_user_id=actor_user_id,
        before={
            "name": getattr(account, "name", None),
            "report_keys": list(getattr(account, "report_keys", None) or []),
        },
    )


def actor_for(account: Any) -> core_audit.AutomationActor:
    """How this principal names itself in `Started by` — `P2.20`'s own outcome.

    §7.8: *"it appears in Started by on History like anyone else."* `integration`
    is BR-AUD-019's kind for *"a partner system acting through a connector"*,
    which is what a BI tool is; the LABEL is the account's own name, so a board
    pack that breaks names the credential that broke rather than a person who
    may have left.
    """
    return core_audit.AutomationActor(
        kind=ACTOR_KIND, name=str(getattr(account, "name", "") or "service account")
    )


def wire(account: Any, *, token: str | None = None) -> dict[str, Any]:
    """One service account, as a screen or an administrator sees it.

    ⚠ **`token` IS PASSED ONLY AT CREATE AND IS THE ONLY TIME IT EXISTS.** There
    is no read that can return it again, by construction rather than by policy.

    ⚠ **B14 RULE 31 — NO DATABASE ID IS EVER THE VISIBLE VALUE OF A FIELD.** The
    `id` is here because a client needs something to address the revoke endpoint
    with; the screen draws `name`, and `token_prefix` is what tells two apart.
    """
    out: dict[str, Any] = {
        "id": str(getattr(account, "id", "")),
        "name": getattr(account, "name", None),
        "token_prefix": getattr(account, "token_prefix", None),
        "report_keys": list(getattr(account, "report_keys", None) or []),
        "revoked_at": getattr(account, "revoked_at", None),
        "last_used_at": getattr(account, "last_used_at", None),
        "created_at": getattr(account, "created_at", None),
    }
    if token is not None:
        out["token"] = token
        #: Keyed `reports.service_account.shown_once` in all eleven catalogues.
        out["token_shown_once"] = True
    return out


def now() -> datetime:
    """UTC, through one function, so a test can pin it in one place."""
    return datetime.now(UTC)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P2.20 (05-prototype/09 Reports Build Brief.pdf p12, p88, p89, read as images per B14 rule 42)
# screens: none yet — tier 1 is an API. The administrator's screen is not in this task.
# generated: 2026-09-27 by lane REP-P2-TAIL
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p2_20_service_accounts.py was run before this module existed and failed on ModuleNotFoundError
# exceptions: (1) the CREATE permission is SystemAdminOnly, which is the narrower of the two readings of the PO's *"Administrators only … hands Dana the token + clerk"* — widening it to a clerk is one line and a ruling, and is NOT assumed · (2) no administrator SCREEN is built; §7.8 tier 1 is *"the report API itself"* and a screen is not in the task
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (🔒 RLS + a credential path)
# ──────────────────────────────────────────────────────────

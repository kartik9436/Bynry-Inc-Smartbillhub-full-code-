# ── Trace ──────────────────────────────────────────────
# Component: BE-03 audit writer (B13 §3, W0 kernel lane — component packet)
# Contract:  EP-AUD-01 write contract (US-AUD-001/002/003 §1 flows) · CLAUDE.md hard rule 7
# Rules:     BR-AUD-001 (every money action writes a row) · BR-AUD-002 (append-only) ·
#            BR-AUD-003 (payload standard who/when/tenant/entity/before→after) ·
#            BR-AUD-008 (sole write path, single INSERT, no fan-out) ·
#            BR-AUD-018 (refusal attempt rows) · BR-AUD-007 (tenant-scoped via app.tenant_id) ·
#            BR-AUD-019 (US-AUD-010 — an actor that is NOT a person is named and
#            versioned, and carries no user id) · BR-RBS-015
# Tests:     06-backend/tests/test_be03_audit.py · 06-backend/tests/test_us_aud_010_audit_actor.py
#            (US-AUD-010 + TC-RBS-12) · US-AUD-003 TCs land with apps.audit (W0 story)
# Impacts:   every module's money/settings/refusal writes · BE-02 handler (attempt rows) · S61
# ───────────────────────────────────────────────────────
"""BE-03 — the ONE audit_log write contract every module calls.

Hard rule 7: every money action writes audit_log (who, what, entity,
before/after, when). This module is the write CONTRACT; the audit_log table
and its model belong to apps.audit (US-AUD-001, B1 boundary: no other module
writes audit's tables — writers CALL this service).

Narrow interface (documented, per the W0 kernel plan): persistence is a
registered sink callable. apps.audit registers its single-INSERT model write
in AppConfig.ready():

    core.audit.set_audit_sink(apps.audit.services.insert_audit_row)

The sink receives one assembled row dict and performs ONE lightweight INSERT —
no fan-out, no notifications, no provider calls (BR-AUD-008; NFR-4 async-safe).
`created_at` (the "when") is stamped at INSERT by the store, so the trail
records when the row landed, not when a caller built a dict.

Write guarantee: fire-and-forget-with-loss is NOT an option under rule 7.
write_row()/money_action() therefore FAIL LOUDLY when no sink is registered or
the sink raises — the calling transaction aborts, so no money action can stand
without its row (the same-txn vs guaranteed-outbox mechanics beyond that are
the Eng-Lead 🔒 disposition inside apps.audit, per US-AUD-003).

refusal_attempt() (BR-AUD-018) is the one deliberate exception: it is invoked
while ANSWERING a refusal (BE-02 handler), where raising would turn a lawful
403/409 into a 500 — so it logs loudly and returns None instead of raising
when the trail is unavailable. The refused action itself wrote nothing either
way.

Append-only: this module exposes INSERT-shaped functions only. There is no
update/amend/delete API and never will be (BR-AUD-002; corrections = new rows).
"""

import datetime as dt
import decimal
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.tenancy import current_tenant_id

logger = logging.getLogger("smartbillhub.audit")

# ── The actor that is not a person (US-AUD-010 / BR-AUD-019) ────────────────
#
# ⚠ WHAT WAS MISSING AND WHAT IT COST. Until this story the only actor this
# writer could record was a USER ID, and `NULL` meant "a system job"
# (BR-AUD-003). One value, every automation in the product: a bill run, an
# import, a retention sweep and a runbook all wrote the same blank. So the
# returned-payments runbook applying a $25 fee to 43 accounts overnight —
# $1,075 charged while nobody is at the office — left a clerk two readings six
# weeks later when a customer disputed one, and BOTH are wrong. A blank actor,
# which she cannot tell from a bug. Or a colleague's name, because the
# automation borrowed the login of whoever set it up: a real person recorded as
# having personally applied 43 fees they never applied and never saw.
#
# `BR-RBS-015` already ruled what it must read — *the runbook is the audit
# actor, named and versioned; it never borrows a user identity* — so this is a
# missing PLATFORM CAPABILITY, not an open question. What it must produce on
# screen is "Returned payments, version 4".
#
# ⚠ NAME AND VERSION ARE TWO FIELDS AND ARE NEVER STORED AS ONE SENTENCE. A
# stored "Returned payments, version 4" is English in a database column: it
# cannot be translated (B14 rule 35 — a catalogue is written in its own
# language), and G15 has already caught a value that was never actually
# translated once. The screen composes the sentence in the reader's language
# from the two facts.
#
#: The kinds of non-person actor this platform can name. A CODE-DEFINED closed
#: set, deliberately — the same posture BR-AUD-005 takes for event codes, which
#: are seeded-only and not tenant-extensible. A kind outside it is refused at
#: construction rather than stored, because an unrecognised kind is a word no
#: screen can render and would arrive back as a blank in a different costume.
ACTOR_KIND_RUNBOOK = "runbook"
ACTOR_KIND_JOB = "job"  # a scheduled platform job: a bill run, a retention sweep
ACTOR_KIND_IMPORT = "import"  # a batch loaded from a file
ACTOR_KIND_INTEGRATION = "integration"  # a partner system acting through a connector
AUTOMATION_ACTOR_KINDS = (
    ACTOR_KIND_RUNBOOK,
    ACTOR_KIND_JOB,
    ACTOR_KIND_IMPORT,
    ACTOR_KIND_INTEGRATION,
)


@dataclass(frozen=True)
class AutomationActor:
    """An actor that is not a person: what it is, what it is called, which version.

    `version` is TEXT and optional. Text because a runbook numbers itself `4`
    while a platform job would name a build like `2.209.0`, and an integer
    column would refuse the second; optional because not every automation has a
    version and inventing `1` for one that does not would be a fact nobody
    established. `None` renders as the bare name.

    Refuses at CONSTRUCTION rather than at the writer, so no call site can hold
    a half-formed one: a kind with no name is the blank actor wearing a label,
    and an unknown kind is a word no screen can draw.
    """

    kind: str
    name: str
    version: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in AUTOMATION_ACTOR_KINDS:
            raise ValueError(
                f"unknown automation actor kind {self.kind!r} — "
                f"one of {AUTOMATION_ACTOR_KINDS} (BR-AUD-019)"
            )
        if not str(self.name).strip():
            raise ValueError("an automation actor must be NAMED (BR-AUD-019 / BR-RBS-015)")

    def as_row_fields(self) -> dict[str, Any]:
        """The three stored columns. `actor_user_id` is NOT among them, by law."""
        version = None if self.version is None else str(self.version).strip() or None
        return {
            "actor_kind": self.kind,
            "actor_label": str(self.name).strip(),
            "actor_version": version,
        }


# Event code used for BR-AUD-018 attempt rows. The SC-3 security-event catalog
# that will own the ratified code is still pending (audit BR file, "Pending
# items") — this kernel constant follows the dotted entity.action grammar and
# is flagged to the PO alongside the catalog gap; it lives HERE so the code is
# one grep away from replacement when SC-3 closes.
REFUSAL_ATTEMPT_ACTION = "security.attempt_refused"

# The sink: one callable, one row dict, one INSERT (BR-AUD-008).
AuditSink = Callable[[dict[str, Any]], None]
_sink: AuditSink | None = None


class AuditWriteError(RuntimeError):
    """The trail could not be written. Callers must NOT catch-and-continue on a
    money action — rule 7 says the action may not stand without its row."""


def set_audit_sink(sink: AuditSink | None) -> None:
    """Register (or clear, with None) the persistence sink. apps.audit only."""
    global _sink
    _sink = sink


def jsonable(value: Any) -> Any:
    """Make an audit blob storable, without changing what it says.

    ⚠ ADDED 2026-08-24 (DEF-657), AND IT BELONGS HERE RATHER THAN AT A CALL
    SITE. `write_row` stored `before`/`after` VERBATIM, so any caller that put a
    `UUID` in a blob killed its own transaction at INSERT with
    `TypeError: Object of type UUID is not JSON serializable`. That is not one
    module's bug: it was a trap laid for every module in the product with an
    audit blob, and `write_row` is the single place all of them pass through.

    What it looked like in the field — the reason it was found by a browser
    walkthrough and by nothing else (hard-won law 6): `POST
    /service-requests/{id}/category` answered **200 the first time and 500 on
    every call after it**, because a fresh request's `account_type_id` is `None`
    (which is JSON) and only becomes a `UUID` once a category has been set. So a
    clerk changing their mind met a server error, every unit test was green, and
    the same function's `after` block was already writing `str(subtype.id)` — the
    two halves of one row disagreed about their own types.

    THE RULE, and both halves matter:

    * anything `json` ALREADY holds keeps its own type — a bool stays a bool, an
      int stays an int, `None` stays `None`. An audit trail that recorded
      `False` as `"False"` would be a different kind of wrong from the one this
      fixes, and a reader could not tell them apart afterwards;
    * everything else becomes a string, chosen so the string is the value a
      human wants to read back: `UUID` → its canonical form, dates → ISO-8601,
      and **`Decimal` → its own digits, NEVER a float** (CLAUDE.md hard rule 2 —
      an audit row is exactly where a money figure is read back in a dispute, so
      `181.9400` must not become `181.94000000000001`).

    Sets become SORTED lists, because a blob's job is to be diffed against
    another one and an unordered set makes two identical rows look different.

    ⚠ COERCION MUST NOT BECOME A SILENT SWALLOW. Rule 7 says the row is not
    optional, so an object with no representation here is stringified WITH its
    type named rather than dropped — enough for a human reading the trail to see
    that something unusual was written and go and look. A missing key would hide
    the write; a named string does not.

    ⚠ AND THIS DOES NOT LICENCE PUTTING RICH OBJECTS IN BLOBS. Callers should
    still pass the scoped, already-stringified dicts BR-AUD-003 asks for, and
    PII still enters MASKED only (BR-AUD-006) — masking happens BEFORE this, and
    nothing here would mask anything. This is a floor, not a feature.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        # bool before int is deliberate: bool IS an int in Python, and the
        # isinstance tuple above catches both, so neither is ever coerced.
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        # Sorted on the COERCED values, so ordering is stable across types.
        return sorted(jsonable(v) for v in value)
    if isinstance(value, decimal.Decimal):
        return str(value)  # hard rule 2 — digits, never a float
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        # Never guess an encoding into an audit row; say what it was.
        return f"<{type(value).__name__} len={len(bytes(value))}>"
    return f"<{type(value).__name__} {value!r}>"


def write_row(
    *,
    action: str,
    entity_type: str,
    entity_id: Any,
    actor_user_id: Any = None,
    automation: AutomationActor | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one BR-AUD-003 standard row and hand it to the sink.

    who   = actor_user_id (None and no `automation` = an UNNAMED system job,
            exactly as BR-AUD-003 has always meant it) — or `automation`, an
            AutomationActor naming itself and its version (BR-AUD-019)
    when  = created_at, stamped by the store at INSERT
    tenant= app.tenant_id context (BR-AUD-007 — never a parameter, so a caller
            cannot write another tenant's trail; RLS WITH CHECK backs this up)
    entity= entity_type + entity_id
    action= dotted entity.action catalog code (validated against the seeded
            catalog inside apps.audit once US-AUD-002 lands)
    before/after = changed-fields diff on update; snapshot on create;
            before-only on terminal actions (BR-AUD-003) — callers supply the
            correctly-scoped dicts; PII enters MASKED only (BR-AUD-006).
    """
    if not action or not entity_type:
        raise AuditWriteError("audit row needs an action code and an entity_type (BR-AUD-003)")
    if automation is not None and actor_user_id is not None:
        # BR-RBS-015: the runbook "never borrows a user identity". Refused
        # LOUDLY rather than resolved by preferring one of the two — a rule that
        # silently drops half its input is a rule nobody can rely on, and the
        # half that would be dropped is the one a disputing customer asks about.
        raise AuditWriteError(
            f"an automation actor may not also carry a user id for {action!r} "
            "— it never borrows a user identity (BR-RBS-015 / BR-AUD-019)"
        )
    if automation is not None and not isinstance(automation, AutomationActor):
        raise AuditWriteError(
            f"`automation` must be an AutomationActor, not {type(automation).__name__} "
            "(BR-AUD-019)"
        )
    tenant_id = current_tenant_id()
    if tenant_id is None:
        # A tenant-scoped trail row without tenant context would be a forged or
        # orphaned write — refuse loudly (BR-AUD-007).
        raise AuditWriteError(f"no tenant context set for audit row {action!r} (BR-AUD-007)")
    if _sink is None:
        # Rule 7: losing the row silently is not an option — fail the action.
        raise AuditWriteError(f"no audit sink registered — cannot record {action!r} (rule 7)")
    row = {
        "tenant_id": tenant_id,
        "actor_user_id": actor_user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        # DEF-657 — coerced here, at the ONE writer, not at each call site.
        "before": jsonable(before),
        "after": jsonable(after),
        # BR-AUD-019: all three NULL on a person's row and on an unnamed system
        # job, so every row written before US-AUD-010 reads identically after
        # it. Nothing is backfilled — BR-AUD-002 forbids an UPDATE here.
        "actor_kind": None,
        "actor_label": None,
        "actor_version": None,
    }
    if automation is not None:
        row.update(automation.as_row_fields())
    _sink(row)  # single lightweight INSERT — nothing else happens here (BR-AUD-008)
    return row


def actor_user_id(actor: Any) -> Any:
    """WHICH USER acted — the one place that question is answered (DEF-BIL-5090).

    Five shapes arrive at services in this product and every one of them is
    legitimate: the **B12 §6a actor** every API layer builds
    (`SimpleNamespace(id=…, role=…)`), a **`users` row** handed to a service
    directly, an **id already in hand** (`apps/billing/api._actor_id` never
    builds an object at all), a runbook's **`AutomationActor`**, and **`None`**
    for an unnamed system job. This is needed wherever an actor is written to a
    COLUMN rather than to an audit row.

    ⚠ **`getattr(actor, "pk", actor)` IS WHY THIS FUNCTION EXISTS, AND IT MUST
    NOT COME BACK.** It reads as defensive — *a row or an id, both accepted* —
    and for a MODEL it is: `invoice.pk` always resolves. For an ACTOR it is not.
    The B12 namespace has `id` and no `pk`, so the fallback returned **the
    namespace itself** and Django refused the whole request:

        ValidationError: "namespace(id=UUID('01a09616-…'), role='system_admin')"
        is not a valid UUID

    `POST /accounts/{id}/disconnect-case/cut` could not commit a cut at all,
    while **every cut test passed**: the fixture actor
    (`tests/test_us_met_helpers.staff_actor`) carries a `pk` that no API layer
    builds, so the resolution resolved in the suite and nowhere else. That is
    hard-won law 7's *structurally incapable of failing*, living in a fixture
    instead of in a gate.

    ⚠ **THE `AutomationActor` BRANCH IS LOAD-BEARING, exactly as it is in
    `money_action` below.** An automation has neither `id` nor `pk`, so the old
    expression wrote the DATACLASS into a UUID column — the runbook `apply_fee`
    port could never have raised a fee. **NULL is the right answer here**: no
    person acted, and the automation's name travels on the audit row instead
    (BR-AUD-019 / BR-RBS-015, and `apps/billing/runbook_ports.py` says so in
    terms).

    **An unresolvable object answers `None`, never itself.** That is
    `money_action`'s existing behaviour preserved deliberately rather than a new
    judgment: the actor columns that consume this are nullable, and a NULL that
    reads *nobody* is recoverable where a dataclass in a UUID column takes the
    whole money action down with it.
    """
    if actor is None or isinstance(actor, AutomationActor):
        return None
    resolved = getattr(actor, "id", None) or getattr(actor, "pk", None)
    if resolved is not None:
        return resolved
    # An id already in hand — the shape an API layer passes when it never built
    # an actor object at all. A UUID has neither attribute and IS the answer.
    if isinstance(actor, (uuid.UUID, str, int)):
        return actor
    return None


def money_action(
    actor: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hard rule 7 helper — the B12 §6a shape: audit.money_action(actor, "invoice.issue", ...).

    `actor` is one of three things, and the third is US-AUD-010's whole point:

    * the acting **user** object — its id becomes who;
    * an **AutomationActor** — the row is written NAMED and VERSIONED, and with
      no user id at all (BR-AUD-019 / BR-RBS-015);
    * **None** — an unnamed system job, exactly as BR-AUD-003 has always meant
      it. Name the job in `after`.

    ⚠ THE `isinstance` BRANCH IS LOAD-BEARING AND MUST NOT BE "SIMPLIFIED" INTO
    THE `getattr` BELOW. An AutomationActor has no `.id` and no `.pk`, so the
    getattr line resolves it to `None` and writes a BLANK row — the automation
    silently loses its name on the way to the trail, every test still passes,
    and the failure is invisible until a customer disputes a fee six weeks
    later. That is the exact defect this story closes, arriving through its own
    fix. Branch first, and never make the wrong call quiet.
    """
    if isinstance(actor, AutomationActor):
        return write_row(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            automation=actor,
            before=before,
            after=after,
        )
    # One resolver, five shapes — `actor_user_id` above. The AutomationActor
    # branch is handled before this line, and re-reading it there costs nothing
    # while a SECOND copy of the resolution is what DEF-BIL-5090 was made of.
    who = actor_user_id(actor)
    return write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=who,
        before=before,
        after=after,
    )


def refusal_attempt(
    *,
    actor_user_id: Any,
    code: str,
    br_ref: str | None,
    method: str | None,
    path: str | None,
    trace_id: str | None = None,
) -> dict[str, Any] | None:
    """BR-AUD-018: a refused attempt is audited as a security event —
    who / what (method+path+catalog code) / when / rule (br_ref).

    Called by the BE-02 exception handler for permission denials and BIZ
    refusals (including cross-tenant denials rendered as 404). Returns the row,
    or None when it could not be recorded (no tenant context on the platform
    surface, or no sink yet) — logged loudly, never raised, because raising
    here would mask the lawful refusal response the user is owed.
    """
    if current_tenant_id() is None:
        # Platform-surface refusals have no tenant trail to land in
        # (audit_log.tenant_id is NOT NULL); the structured log is the record.
        logger.warning(
            "refused attempt outside tenant context: %s %s code=%s rule=%s trace_id=%s",
            method,
            path,
            code,
            br_ref,
            trace_id,
        )
        return None
    if _sink is None:
        logger.warning(
            "refused attempt not persisted (no audit sink yet): %s %s code=%s rule=%s trace_id=%s",
            method,
            path,
            code,
            br_ref,
            trace_id,
        )
        return None
    return write_row(
        action=REFUSAL_ATTEMPT_ACTION,
        entity_type="request",
        entity_id=trace_id or uuid.uuid4().hex,
        actor_user_id=actor_user_id,
        # Attempt rows are terminal events with no prior state: before stays
        # None; the "what/rule" halves of BR-AUD-018 land in `after`.
        after={"code": code, "br_ref": br_ref, "method": method, "path": path, "refused": True},
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-03@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be03_audit.py 10/10✔ (live-table TCs land with US-AUD-001..003) · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

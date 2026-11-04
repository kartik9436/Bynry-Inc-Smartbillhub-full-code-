# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-02 (chart of accounts & GL mapping) — CR-060 **C10**, task
#           **T11**
#           Screens: S8 (Settings → Accounting → Where money lands)
# Rules:    BR-LED-014 (where GL mappings live — AMENDED by CR-060 C10: and WHO
#           MAY WRITE THEM through one screen) · BR-TEN-013 / B1 (a module
#           never touches another module's ORM) · BR-BIL-010 (a bill line's GL
#           freezes at issue) · CLAUDE.md rule 7 (every money action is audited)
#           · hard-won law 14 (a failed statement poisons the whole PostgreSQL
#           transaction, and the default suite runs on SQLite, which does not)
# Tests:    06-backend/tests/test_cr060_c10_gl_mapping_save.py
# ───────────────────────────────────────────────────────
"""**ONE SCREEN, ONE SAVE, SEVERAL OWNERS UNDERNEATH — and no cross-module write.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this decides which GL account a service's
money lands in and which account carries a designation, so a wrong answer here
is a misposting that freezes onto every bill line issued afterwards
(BR-BIL-010). AI-authored 2026-09-02 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.

══════════════════════════════════════════════════════════════════════════════
WHAT C10 ASKED FOR, AND WHY THE PAGE WAS READ-ONLY
══════════════════════════════════════════════════════════════════════════════
Verbatim: *"Eleven GL columns are set across six screens; the one page that
shows them all is READ-ONLY because half belongs to another module."* And the
fix, also verbatim: *"An orchestrating service in the tenancy module that the
mapping screen calls — one screen, one save, several owners underneath — NOT a
cross-module write."*

The two halves and their owners, which is the whole reason this file exists:

  * **ROLES** — *"which account means receivables"* — are
    `ledger_accounts.designation`, a **LEDGER** column, written by
    `services.update_account`. A fixed set of **thirteen** (`chart.GL_DESIGNATIONS`),
    set once at setup and rarely touched.
  * **SERVICES** — *"which account does this service's revenue credit"* — are
    `tenant_services.revenue_account_id`, a **TENANCY** column, written by
    `tenancy.services.set_service_gl_accounts` and reached here through the
    published seam. The ledger does not touch that table and does not start to.

══════════════════════════════════════════════════════════════════════════════
⚠ WHERE THE ORCHESTRATOR LIVES, AND WHY IT IS NOT THE MODULE C10 NAMED
══════════════════════════════════════════════════════════════════════════════
C10 says *"in the tenancy module"* in one sentence and *"in the OWNING module"*
in another, and those point at different files because the save has **two**
owners. It is here, in the ledger, and the reasoning is recorded rather than
left to be re-derived:

  1. **The endpoint C10 names is `PUT /ledger/gl-mappings`** — 11b §2.10's own
     path, and its sibling `GET /ledger/gl-mappings` has been served from
     `apps/ledger/chart_api.py` since 2026-08-16. A read and a write of one
     resource served from two modules is the drift `apps/ledger/wire.py`'s own
     docstring warns about.
  2. **The role half is the ledger's own**, and it is the half that is a 🔒
     sensitive path. Putting the orchestration in tenancy would mean tenancy
     calling back into the ledger to write designations — a round trip through
     two seams to change a column the caller already owns.
  3. **The constraint C10 actually cares about is honoured either way**: the
     tenancy column is written by tenancy, asked for through a published
     callable. That is the sentence *"NOT a cross-module write"*, and it is
     true of this file line by line.

══════════════════════════════════════════════════════════════════════════════
⚠ ALL OF IT OR NONE OF IT — AND WHAT WAS ACTUALLY MEASURED, NOT ASSUMED
══════════════════════════════════════════════════════════════════════════════
C10's proof is *"a partial failure writes NOTHING"*, and **ONE
`transaction.atomic()` wraps both halves**. Remove it and the guarantee is gone:
the role half commits, the service half refuses, and the tenant's map is left
half written while the screen says it saved.

⚠ **AN EARLIER DRAFT OF THIS PARAGRAPH CLAIMED SOMETHING THAT IS NOT TRUE, AND
IT IS CORRECTED HERE RATHER THAN QUIETLY DROPPED (hard-won law 1).** It said a
nested `atomic()` around each half *"is a SAVEPOINT and a SAVEPOINT can commit
while the block around it rolls back"*. **It cannot.** Django's nested
`atomic()` opens a savepoint that is rolled back with its parent, and that was
MEASURED rather than reasoned about: the nested version was built deliberately
and the partial-failure case **passed on PostgreSQL 16 and on SQLite**, so the
sabotage proved nothing and the claim it was written to justify was wrong.

**What DOES break the guarantee, and what the test therefore catches, is the
absence of the transaction itself.** With the single `atomic()` replaced by a
no-op the case fails on both databases, verbatim:

    AssertionError: a refused service write left the ROLE half committed —
    the save is not all-or-nothing
    assert '01a06404-eaf5-7491-8948-0663f5def046' == None

**So the honest reason not to nest is narrower than the one first written:** a
nested block that also CATCHES is how a refusal gets swallowed and half a save
survives, and neither half here catches anything. A bare nested `atomic()` is
harmless. Both halves are still documented as taking the caller's transaction,
because one place opening it is easier to reason about than three.

**LAW 14's TRAP DOES NOT APPLY TO THIS FILE, AND SAYING SO IS THE POINT.** That
law is about `except IntegrityError: continue` — code that catches a database
error and carries on, which works on SQLite and loses data on PostgreSQL.
**Nothing here catches a database error at all**, so there is no place for an
aborted transaction to be swallowed, and the PostgreSQL run below is worth
having for a different and smaller reason: it is the database this product
actually uses, and C10 asked for it by name. Claiming more than that would be a
comment describing a guarantee it does not provide.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.ledger import chart, selectors, services, tenancy_seam
from core import errors


def _clean_role_changes(raw: Any) -> list[dict[str, Any]]:
    """The role half of the payload, validated before ANY write is attempted.

    ⚠ **EVERY REFUSAL IN THIS FUNCTION HAPPENS BEFORE THE TRANSACTION OPENS,
    AND THAT IS DELIBERATE.** The atomic block below guarantees that a failure
    writes nothing; it does not make failing cheap. A payload naming a
    designation that does not exist is a screen bug, and finding it after two
    round trips to the database — on PostgreSQL, with the transaction already
    poisoned — turns a clear 422 into a confusing one.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="ledger.glMapping.rolesNotList"
        )
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="ledger.glMapping.roleNotObject"
            )
        designation = str(entry.get("designation") or "").strip()
        if designation not in chart.GL_DESIGNATIONS:
            # BY NAME rather than "invalid": the thirteen are a closed set and a
            # typo in one is the difference between receivables and cash.
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="ledger.glMapping.unknownRole",
                field_errors=[
                    {"field": "designation", "code": errors.VAL_UNKNOWN_LOOKUP}
                ],
            )
        if designation in seen:
            # Two rows for one role is a payload that cannot be honoured in a
            # defined order, and picking the last one silently is how a screen
            # bug becomes a misposting nobody can explain.
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="ledger.glMapping.duplicateRole",
                field_errors=[{"field": "designation", "code": errors.VAL_FORMAT}],
            )
        seen.add(designation)
        account_id = entry.get("account_id")
        cleaned.append(
            {
                "designation": designation,
                "account_id": None if account_id in (None, "") else str(account_id),
            }
        )
    return cleaned


def _clean_service_changes(raw: Any) -> list[dict[str, Any]]:
    """The service half, validated the same way and for the same reason."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="ledger.glMapping.servicesNotList"
        )
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="ledger.glMapping.serviceNotObject"
            )
        code = str(entry.get("service_code") or "").strip()
        if code == "":
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.glMapping.serviceCodeRequired",
                field_errors=[{"field": "service_code", "code": errors.VAL_REQUIRED}],
            )
        if code in seen:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="ledger.glMapping.duplicateService",
                field_errors=[{"field": "service_code", "code": errors.VAL_FORMAT}],
            )
        seen.add(code)
        changes: dict[str, Any] = {}
        for field in ("revenue_account_id", "base_revenue_account_id"):
            if field in entry:
                changes[field] = entry[field]
        cleaned.append({"service_code": code, "changes": changes})
    return cleaned


def save_gl_mappings(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """**THE ONE SAVE BEHIND `PUT /ledger/gl-mappings`.**

    Takes `{"roles": [{designation, account_id}], "services": [{service_code,
    revenue_account_id, base_revenue_account_id}]}` and applies both halves in a
    single transaction, each through the module that owns the column.

    Returns what actually CHANGED, per half — not what it was sent. A screen
    that reported "13 roles saved" over a payload where twelve were already
    correct is telling a clerk something happened that did not, and the audit
    rows underneath would disagree with it.

    ⚠ **AN EMPTY PAYLOAD IS A NO-OP AND NOT A REFUSAL.** A clerk who opens the
    page, changes nothing and presses Save has done nothing wrong.
    """
    roles = _clean_role_changes(payload.get("roles"))
    service_rows = _clean_service_changes(payload.get("services"))

    # ⚠ **ONE TRANSACTION FOR BOTH HALVES — this line IS the guarantee.**
    # Replace it with a no-op and the partial-failure case goes RED on both
    # PostgreSQL and SQLite, which is how it was proved rather than assumed.
    # `services.update_account` and the tenancy seam both run inside it and
    # neither opens one of its own: a nested block that also CAUGHT something
    # is how a refusal gets swallowed, and one opener is easier to reason about
    # than three. (A bare nested `atomic()` would be harmless — see the
    # docstring, which corrects an earlier claim to the contrary.)
    with transaction.atomic():
        # ⚠ **WHAT CHANGED IS READ, NOT ASSUMED.** `update_account` answers with
        # the chart ROW and no change list, so the honest answer comes from the
        # map before and after — the same reason the service half returns one.
        # Reporting `["designation"]` for every id sent would tell a clerk that
        # thirteen roles moved when none did, and the audit rows underneath
        # would disagree with the screen.
        before_map = selectors.designation_map()
        role_results = []
        for entry in roles:
            if entry["account_id"] is None:
                continue
            services.update_account(
                actor,
                account_id=entry["account_id"],
                designation=entry["designation"],
            )
            moved = str(before_map.get(entry["designation"]) or "") != str(entry["account_id"])
            role_results.append({"changed": ["designation"] if moved else []})
        # ⚠ **CLEARING A ROLE IS A DIFFERENT ACT AND IT IS NOT SERVED HERE.**
        # `account_id: null` against a role would mean "no account carries
        # receivables", which stops every posting that resolves through it. It
        # is reachable, deliberately, only through `PATCH /ledger/accounts/{id}`
        # one account at a time with its own audit row — a bulk page must not be
        # able to unmap the books in one press.
        cleared = [entry["designation"] for entry in roles if entry["account_id"] is None]
        if cleared:
            # ⚠ The copy read *"Clear roles one account at a time"* — seven words,
            # one over B14 rule 33's cap — until 2026-09-03. It now says where to
            # go rather than how the other door is shaped: *"A role can't be
            # cleared here. Clear it on the account."* **The reason is the comment
            # block above and must not be folded back into the sentence:** one
            # press on a bulk page could otherwise unmap the books, so clearing is
            # reachable only through `PATCH /ledger/accounts/{id}`, one account at
            # a time, each with its own audit row.
            raise errors.BizError(
                errors.BIZ_STATE,
                message_key="ledger.glMapping.roleCannotBeCleared",
            )
        service_results = [
            tenancy_seam.set_service_gl_accounts(actor, row["service_code"], row["changes"])
            for row in service_rows
        ]

    return {
        "roles": [
            {"designation": entry["designation"], "changed": result["changed"]}
            for entry, result in zip(
                [entry for entry in roles if entry["account_id"] is not None], role_results
            )
        ],
        "services": [
            {"service_code": result["service_code"], "changed": result["changed"]}
            for result in service_results
        ],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C10 + task T11 (12-governance/11-change-requests.md §CR-060) + 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-014 + 04-docs/01-spec/11b-api-audit.md §2.10
#         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — CR-060 allocates no story ids, and minting one to satisfy G01's regex would put a citation in the tree that resolves to nothing. Same posture as apps/customers/close_out.py.
# generated: 2026-09-02 by the CR-060 finance-screens lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST (law 7) and PROVED ON POSTGRESQL 16 (law 14 / C10's own "Prove the partial-failure case on PostgreSQL") — see tests/test_cr060_c10_gl_mapping_save.py, which quotes both
# exceptions: (1) CLEARING a role is REFUSED here and stays available one account at a time through `PATCH /ledger/accounts/{id}` — a bulk page that could unmap receivables in one press is a different risk from one that can re-point it · (2) the orchestrator lives in the LEDGER and not in tenancy, which is the module C10 names in one sentence; the reasoning is in the docstring and in the decision log, and the constraint C10 actually states — never a cross-module write — holds line by line · (3) it opens the ONLY transaction on this path deliberately: both halves are documented as taking the caller's, because a nested atomic() is a SAVEPOINT that can outlive the rollback around it
# status: HUMAN-REVIEW-PENDING · VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:   CR-115-BRC05 §7 — *"CUSTOM URLs ON A CONNECTOR"*, ruled by the
#          Product Owner on 2026-09-17. R32 (*"here Customer is giving custom
#          URLs … hence we need a form to add them"*), R33 (the standard list
#          we ship), R34 (*"any every custom APis … we wil ahve to write a code
#          … using runbook"*), R35 (*"DOnt add field Mapping here - remove
#          it"*), R36 (the Edit button, and standard APIs enable/disable only).
# Rules:   BR-INT-037 (data, never a branch on a provider key; `G77`) ·
#          BR-INT-078 (the five rules of §7.5, minted here) · CLAUDE.md hard
#          rule 1 (tenant scoping; RLS FORCE) · hard-won law 2's mirror (a
#          switch that changes nothing looks identical to one that works) ·
#          law 3 (the permissive answer is the one you type) · B14 rule 33
#          (a refusal is a sentence a clerk reads, capped by what it is for).
# Tests:   06-backend/tests/test_cr115_custom_apis.py ·
#          10-scripts/cr115_custom_apis_walkthrough.mjs (the browser walk)
# Impacts: models.IntegrationApi + migration 0014 · addressing.resolve_address
#          (the `row` rung) · selectors._operation_row · gis.search (the merge)
#          · gis_parcels (the nightly sync asks this module first) · api.py
#          · 07-frontend ConnectionDetailPage.tsx
# ───────────────────────────────────────────────────────
"""THE APIs ON ONE CONNECTION — OURS AND THEIRS, IN ONE LIST.

THE LINE THE WHOLE DESIGN RESTS ON
----------------------------------
`CR-115-BRC05` §7.2, and it is quoted here rather than paraphrased because
every function below is a consequence of it:

    **THE KIND IS OURS. THE NAME IS THEIRS.**

A clerk picks what SORT of call this is from a closed list we ship, and gives
it their own name and their own URL. **Nothing addable can lack code behind
it**, and a genuinely new KIND of call is a Runbook, not a form field — a URL
alone cannot express what to do with the answer (R34).

⚠ **THAT CORRECTS AN EARLIER, BROADER RULE AND THE CORRECTION IS THE POINT.**
The Integration Blueprint ruled on 14 September (p15 `CR-3`, p164): *"Can a
clerk rename an API we declared? **No.** 'no clark will not do it — we will do
it during initial configuration'. The set-up form lists APIs and does not edit
them. The disabled + Add an API control is removed."* The PO ruled that too
broad on 17 September. The distinction is the CONNECTOR, not the customer: a
**protocol reader** — our Esri connector knows how to query an ArcGIS layer and
does not care WHICH layer — needs no new code for a customer's extra URL, while
a connector whose every API is bespoke still falls under the old rule.
⚠ The blueprint also observed that a clerk-owned name *"would need a
per-connection field that does not exist"* and counted the old ruling's saving
as *"no schema change"*. **That schema change is now required and is migration
0014** — the blueprint's own reasoning names the cost, so it is paid knowingly.

HOW THE CLOSED LIST STAYS CLOSED — MECHANICALLY, NOT BY DISCIPLINE
------------------------------------------------------------------
⚠ **A KIND IS OFFERED ONLY WHERE THIS CONNECTOR ALREADY DECLARES THE OPERATION
THAT RUNS IT.** That is what makes *"nothing addable can lack code behind it"*
a fact about the code rather than a promise in a docstring (hard-won law 1). A
custom row does not carry behaviour of its own: it names one of OUR operations,
and the SAME adapter, the SAME codec and the SAME runner do the work at the
clerk's address instead of the connector's. So a Kind with no operation behind
it cannot be offered, cannot be posted, and needs no separate guard to refuse.

`KIND_OF_OPERATION` is the map, and it is DATA keyed by provider — the
declarative form `G77` allows and `gis.RUN_NOW_OPERATIONS` already sets the
precedent for. ⚠ **IT IS NOT INFERRED FROM THE MANIFEST'S SHAPE**, and that was
considered: `trigger == "scheduled"` → a sync, `executor == "browser"` → tiles,
`result_disposition == "offer"` → a lookup. Inference reads plausibly and fails
OPEN — every future connector declaring a scheduled inbound fetch would silently
acquire a *Scheduled sync* a clerk could point anywhere, on the day its manifest
landed and with every test green. A map fails CLOSED: a connector nobody has
thought about offers nothing (law 3 — the permissive answer is the one you type).

THE FIVE RULES OF §7.5, AND WHERE EACH ONE LIVES
------------------------------------------------
Each REASON is written beside its rule on purpose. §7.5: *"Each reason belongs
IN THE CODE, or the rule reads as arbitrary and the next lane simplifies it
away."*

1. **ONE Scheduled sync per connector** — `refuse_second_sync` below, called
   from `add` AND served to the form as `addable`. ⚠ **A FORM-ONLY RULE IS A
   RULE UNTIL SOMEONE CALLS THE API DIRECTLY**, so the server refuses it too and
   the test proves the server half with no screen in the room.
2. **Address lookup MERGES** — `lookup_addresses` below returns every enabled
   lookup address; `gis.search` calls each and ranks the candidates together
   through `gis_search.rank_key`, which already existed.
3. **A disabled API is NOT scheduled and NOT called** — `is_enabled` below, and
   its callers in `gis.search`, `gis.reconcile` and `selectors`.
4. ***Working N of M*** and the **State** word count **ONLY ENABLED** APIs —
   `enabled` travels on the operation row and the screen filters on it.
5. **`DEF-INT-5597` is not undone** — nothing here touches `display_state`. The
   State column means the CONNECTOR, never one of its APIs.

WHAT THIS MODULE DELIBERATELY DOES NOT HAVE
--------------------------------------------
⚠ **NO FIELD MAPPING.** `CR-115-BRC05` §7.3, PO verbatim: *"DOnt add field
Mapping here - remove it"* — **removed BY NAME, not forgotten.** Not
reintroduced, not in a smaller form, not as a link. The product has a mappings
screen (`MAP-01`, per connector) and whether a per-API mapping should exist is a
separate decision that is not this module's to take.

⚠ **NO PER-API KEY, AND IT IS A DEFERRAL RATHER THAN AN OVERSIGHT**
(`DEF-INT-5680`). §7.6: *"A key is a CREDENTIAL, not config … If per-API keys
need that changed, ship Name / Kind / URL / Enabled WITHOUT them and say so."*
A connection holds ONE credential today, encrypted, versioned, one active row
enforced by the database, shown once. Several per connection touches that
store, the *Keys in use* tile, rotation and expiry. The blueprint's own
`VIEW-25` frame says the same thing under the table in as many words — **"One
key. All 3 APIs use it."** — so a per-API key would also contradict the
drawing. A custom row therefore sends the CONNECTION's key, exactly as the
standard rows do, and Ann Arbor needs no key at all.

WHERE THE ROWS LIVE, AND WHY NOT IN `connection.config`
--------------------------------------------------------
⚠ **`services.update_connection` PRUNES `config` TO WHAT THE MANIFEST STILL
DECLARES** (`DEF-INT-5582`), so rows kept there would be **silently deleted by
the next Edit save** — every test green, nothing raised, the clerk's layers
gone. They are their own table instead, FK'd to the connection, which is
already tenant-scoped: *"The rows are PER UTILITY … Two utilities on the same
connector configure it independently"* (§7.6). RLS FORCE lands in the same
migration that creates the table — a tenant table that exists for even one
migration without a policy is a hard-rule-1 breach with a window in it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from apps.integrations import models
from apps.integrations.registry import REGISTRY, Manifest, Operation, Registry
from core import audit as core_audit
from core import errors
from core.permissions import SYSTEM_ADMIN, require_role

# ═══════════════════════════════════════════════════════════════════════════
# The closed list — OURS
# ═══════════════════════════════════════════════════════════════════════════

#: `CR-115-BRC05` §7.3 — *"Kind: **closed list, ours**: Address lookup (while
#: you wait) · Scheduled sync (nightly) · Map tiles"*. Three, and a fourth is a
#: PO ruling rather than a constant somebody adds.
KIND_ADDRESS_LOOKUP = "address_lookup"
KIND_SCHEDULED_SYNC = "scheduled_sync"
KIND_MAP_TILES = "map_tiles"

#: The order the form offers them in, which is the order §7.3 lists them.
KINDS: tuple[str, ...] = (KIND_ADDRESS_LOOKUP, KIND_SCHEDULED_SYNC, KIND_MAP_TILES)

#: ── WHICH OF OUR OPERATIONS RUNS EACH KIND, PER CONNECTOR ──────────────────
#: Data keyed by provider, never a branch (`BR-INT-037`; `G77`'s own docstring
#: allows exactly this shape, and `gis.RUN_NOW_OPERATIONS` is the precedent).
#:
#: ⚠ **THIS MAP IS THE CLOSED LIST.** A connector absent from it offers no
#: Kinds and its form does not appear at all — which is the honest answer for
#: the twenty-seven connectors whose every API is bespoke, and is the half of
#: §7.2 that the earlier, broader ruling got right.
#:
#: ⚠ **AND THE OPERATION NAMED HERE MUST EXIST ON THE MANIFEST.**
#: `kinds_for` checks it against the registry rather than trusting this
#: literal, so a renamed operation empties the list instead of offering a Kind
#: whose code has moved — `DEF-INT-5488` is the record of what a declared name
#: pointing at nothing costs when nobody checks.
KIND_OF_OPERATION: dict[tuple[str, str], str] = {
    ("gis_esri", "address_search"): KIND_ADDRESS_LOOKUP,
    ("gis_esri", "reconcile_parcels"): KIND_SCHEDULED_SYNC,
    ("gis_esri", "map_tiles"): KIND_MAP_TILES,
}

#: ⚠ **A SYNC WRITES, AND THAT IS THE WHOLE REASON FOR RULE 1.** §7.5: *"a sync
#: **writes**. Two pointed at two layers both update the same premises and **the
#: last to run wins silently**"* — silently is the word that matters, because
#: nothing downstream can tell a premises updated twice from one updated once.
#: A lookup and a tile fetch only READ, so neither is capped.
WRITING_KINDS: frozenset[str] = frozenset({KIND_SCHEDULED_SYNC})

# ── the refusals, as catalogue keys ─────────────────────────────────────────
# ⚠ **A KEY, NEVER A SENTENCE BUILT IN PYTHON.** `core.errors` asserts at the
# raise that the key resolves, and the eleven catalogues are what make it reach
# a clerk in their own language (B14 rule 35; `G32`). A sentence built here
# reaches them in English, or — when `params.detail` is suppressed — as silence.
REFUSAL_UNKNOWN_KIND = "integrations.customApi.unknownKind"
REFUSAL_SECOND_SYNC = "integrations.customApi.secondSync"
REFUSAL_ALREADY_CONFIGURED = "integrations.customApi.alreadyConfigured"
REFUSAL_NAME_REQUIRED = "integrations.customApi.nameRequired"
REFUSAL_URL_REQUIRED = "integrations.customApi.urlRequired"
REFUSAL_URL_SHAPE = "integrations.customApi.urlShape"
REFUSAL_NOT_OURS = "integrations.customApi.notOurs"
REFUSAL_STANDARD_LOCKED = "integrations.customApi.standardLocked"
REFUSAL_NO_SUCH_API = "integrations.customApi.noSuchApi"

#: Audit actions. Every one of these changes what the product DIALS, so each is
#: recorded (CLAUDE.md hard rule 7's shape, applied to configuration).
AUDIT_ADDED = "integration_api_added"
AUDIT_EDITED = "integration_api_edited"
AUDIT_REMOVED = "integration_api_removed"
AUDIT_SWITCHED = "integration_api_switched"

#: A URL a clerk typed must be one we could actually dial. Deliberately thin —
#: the manifest's `url` field kind already refuses shape errors on the
#: connector's own address and this is the same question, not a stricter one.
#: ⚠ **`https` IS NOT REQUIRED HERE AND THAT IS NOT AN OVERSIGHT**: a city
#: publishing over plain http is a fact about the city, and refusing it would
#: send a clerk to a Runbook for a layer we can read perfectly well.
_URL_SCHEMES = ("http://", "https://")


# ═══════════════════════════════════════════════════════════════════════════
# Reading — what a screen and a runner both ask
# ═══════════════════════════════════════════════════════════════════════════


def kind_of(provider_key: str, operation_name: str) -> str | None:
    """Which Kind this operation IS, or `None` when it is not one of the three.

    Membership, never a branch — the same shape as `gis.can_run_now`.
    """
    return KIND_OF_OPERATION.get((str(provider_key), str(operation_name)))


def operation_of_kind(provider_key: str, kind: str) -> str | None:
    """Which of OUR operations runs this Kind on this connector.

    The inverse of `kind_of`, and the reason a custom row stores an OPERATION
    rather than a Kind: the operation is what the runner, the adapter and the
    address ladder all key off, so storing the Kind as well would be one fact
    in two columns and the copy nobody reads is the one that drifts.
    """
    for (key, operation), named in KIND_OF_OPERATION.items():
        if key == str(provider_key) and named == str(kind):
            return operation
    return None


def kinds_for(manifest: Manifest) -> list[str]:
    """Every Kind this connector could ever offer, in `KINDS` order.

    ⚠ **CHECKED AGAINST THE MANIFEST, NOT READ OUT OF THE MAP.** A Kind is
    offered only where the operation that runs it is really declared, so a
    renamed or retired operation empties the list rather than offering a Kind
    whose code has moved (`DEF-INT-5488` — fifteen of eighteen manifests named
    a field they never declared, and nothing noticed for weeks).
    """
    declared = {one.name for one in manifest.operations}
    found = []
    for kind in KINDS:
        operation = operation_of_kind(manifest.key, kind)
        if operation is not None and operation in declared:
            found.append(kind)
    return found


def rows_for(connection: Any) -> list[models.IntegrationApi]:
    """Every stored per-API row on this connection, oldest first.

    Under the request's tenant context RLS FORCE already hides every other
    tenant's rows; the `connection` filter is the second guard and the
    connection itself is tenant-scoped (CLAUDE.md hard rule 1).
    """
    if connection is None:
        return []
    return list(
        models.IntegrationApi.objects.filter(connection=connection).order_by("created_at", "id")
    )


def custom_rows(connection: Any) -> list[models.IntegrationApi]:
    """Only the ones a clerk added."""
    return [one for one in rows_for(connection) if not one.is_standard]


def is_enabled(connection: Any, operation_name: str, *, rows: Sequence[Any] | None = None) -> bool:
    """Is the STANDARD API for this operation switched on?

    ⚠ **ABSENCE MEANS ON, AND THAT IS THE ONLY SAFE DEFAULT HERE.** A standard
    row is written the first time somebody touches the switch, so every
    connection that existed before this feature — and every one nobody has
    touched since — must go on behaving exactly as it did. A default of OFF
    would silently stop every scheduled sync in the product on the day this
    migration ran, with no screen saying so.
    """
    found = rows if rows is not None else rows_for(connection)
    for row in found:
        if row.is_standard and row.operation == str(operation_name):
            return bool(row.enabled)
    return True


def enabled_operations(connection: Any, manifest: Manifest) -> set[str]:
    """The operation names that are NOT switched off — rule 4's input.

    *Working N of M* and the connector's State word count these and no others:
    *"a switched-off API must not drag the count, and a connector is not Not
    working because of one you turned off"* (§7.5 rule 4).
    """
    rows = rows_for(connection)
    return {one.name for one in manifest.operations if is_enabled(connection, one.name, rows=rows)}


def _sync_operations(manifest: Manifest) -> set[str]:
    """Our operations on this connector whose Kind WRITES."""
    return {
        one.name
        for one in manifest.operations
        if kind_of(manifest.key, one.name) in WRITING_KINDS
    }


def active_sync_count(connection: Any, manifest: Manifest) -> int:
    """How many ENABLED scheduled syncs this connection has — ours plus theirs.

    ⚠ **BOTH HALVES COUNT, AND THAT IS RULE 1 RATHER THAN A DETAIL.** The
    connector ships a nightly sync of its own; a custom one pointed at a second
    layer is the SECOND, and *"two pointed at two layers both update the same
    premises and the last to run wins silently"*. Counting only the custom ones
    would let exactly the harm the rule exists to prevent through the front
    door, while reading as a correctly implemented rule.
    """
    rows = rows_for(connection)
    ours = _sync_operations(manifest)
    count = sum(1 for name in ours if is_enabled(connection, name, rows=rows))
    count += sum(
        1 for row in rows if not row.is_standard and row.enabled and row.operation in ours
    )
    return count


def addable_kinds(connection: Any, manifest: Manifest) -> list[dict[str, Any]]:
    """What the form may offer, and for each one whether it is refused and why.

    Three states, and the screen draws each differently:

    * **offered** — pick it and Add works.
    * **gone** — a CUSTOM row of this Kind already exists, so *"an API already
      configured drops out of the dropdown — one configuration per API, never
      two"* (§7.4). Absent from this list entirely.
    * **refused** — offered, because it CAN succeed, but not right now: a second
      scheduled sync while the first is on. ⚠ **It is offered rather than
      hidden because the clerk has a real way through it** — switch the other
      one off — and a Kind that simply vanished would leave them with no
      sentence to read and nothing to do.
    """
    taken = {one.operation for one in custom_rows(connection)}
    offered: list[dict[str, Any]] = []
    for kind in kinds_for(manifest):
        operation = operation_of_kind(manifest.key, kind)
        if operation in taken:
            continue
        refusal = None
        if kind in WRITING_KINDS and active_sync_count(connection, manifest) >= 1:
            refusal = REFUSAL_SECOND_SYNC
        offered.append({"kind": kind, "refusal": refusal})
    return offered


def lookup_addresses(
    connection: Any,
    manifest: Manifest,
    operation: Operation,
    *,
    settings: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Every address an ENABLED Address lookup should be searched at — rule 2.

    The connector's own first, then each enabled custom row in the order a
    clerk added them. Each entry carries the resolved address AND how it was
    decided, straight off `addressing.resolve_address`, so the caller never has
    to ask a second time (§7.7 — *"a screen that re-derives it is a second
    source by another name"*).

    ⚠ **THE STANDARD ONE IS DROPPED WHEN IT IS SWITCHED OFF, AND THAT IS RULE
    3.** A clerk whose city has replaced its qualified-address layer wants the
    old one to stop being searched, and a switch that left it in the list would
    be decoration — hard-won law 2's mirror, where a control that renders and
    changes nothing looks identical to a working one.

    ⚠ **AN ADDRESS THAT RESOLVES TO NOTHING IS NOT IN THE LIST.** `None` is a
    real absence and dialling it would be a call to the string *"None"*.
    """
    from apps.integrations import addressing

    found: list[dict[str, Any]] = []
    rows = rows_for(connection)
    if is_enabled(connection, operation.name, rows=rows):
        address = addressing.resolve_address(
            manifest, operation, connection, settings=settings
        )
        if address.found:
            found.append(
                {
                    "url": address.value,
                    "source": address.source,
                    "field": address.field,
                    "name": None,
                    "row_id": None,
                }
            )
    for row in rows:
        if row.is_standard or not row.enabled or row.operation != operation.name:
            continue
        address = addressing.resolve_address(
            manifest, operation, connection, settings=settings, row=row
        )
        if address.found:
            found.append(
                {
                    "url": address.value,
                    "source": address.source,
                    "field": address.field,
                    "name": row.name,
                    "row_id": str(row.id),
                }
            )
    return found


# ═══════════════════════════════════════════════════════════════════════════
# Writing
# ═══════════════════════════════════════════════════════════════════════════


def _manifest_or_refuse(provider_key: str, registry: Registry) -> Manifest:
    manifest = registry.get(str(provider_key))
    if manifest is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=REFUSAL_NOT_OURS,
            params={"provider": str(provider_key)},
        )
    return manifest


def _clean_url(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key=REFUSAL_URL_REQUIRED)
    if not value.lower().startswith(_URL_SCHEMES):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key=REFUSAL_URL_SHAPE)
    return value


def _clean_name(raw: Any) -> str:
    value = " ".join(str(raw or "").split())
    if not value:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key=REFUSAL_NAME_REQUIRED)
    return value[:120]


def refuse_second_sync(connection: Any, manifest: Manifest, kind: str) -> None:
    """Rule 1, on the SERVER, where it is actually a rule.

    ⚠ **§7.5: *"A form-only rule is a rule until someone calls the API
    directly."*** The form checks this too, so a clerk is told before they
    type; this is the half that is still true when nobody is looking at a
    screen, and the test that proves it never opens one.
    """
    if kind not in WRITING_KINDS:
        return
    if active_sync_count(connection, manifest) >= 1:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-078",
            message_key=REFUSAL_SECOND_SYNC,
        )


@require_role(SYSTEM_ADMIN)
def add(
    *,
    actor: Any,
    connection: Any,
    kind: str,
    name: Any,
    url: Any,
    registry: Registry = REGISTRY,
) -> models.IntegrationApi:
    """One custom API — *"the KIND is ours, the NAME is theirs"* (§7.2).

    ⚠ **NO `field_mapping` ARGUMENT, AND NO SMALLER VERSION OF ONE.** PO, R35:
    *"DOnt add field Mapping here - remove it"*. If a Scheduled sync proves
    unusable without one, §7.3 says to SAY SO AND STOP — the product has a
    mappings screen and that is a separate decision.
    """
    manifest = _manifest_or_refuse(connection.provider_key, registry)
    if kind not in kinds_for(manifest):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=REFUSAL_UNKNOWN_KIND,
            params={"kind": str(kind)},
        )
    operation = operation_of_kind(manifest.key, kind)
    if any(one.operation == operation for one in custom_rows(connection)):
        # §7.4 — *"one configuration per API, never two"*. The form drops it
        # out of the dropdown; this is what answers a caller that did not read
        # the form, and the two must agree or the dropdown is the only rule.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-078",
            message_key=REFUSAL_ALREADY_CONFIGURED,
        )
    refuse_second_sync(connection, manifest, kind)
    row = models.IntegrationApi.objects.create(
        tenant_id=connection.tenant_id,
        connection=connection,
        operation=operation,
        is_standard=False,
        name=_clean_name(name),
        url=_clean_url(url),
        enabled=True,
    )
    core_audit.money_action(
        actor,
        AUDIT_ADDED,
        "integration_api",
        row.id,
        before=None,
        after={"operation": row.operation, "name": row.name, "url": row.url, "enabled": True},
    )
    return row


def _row_or_refuse(connection: Any, row_id: Any) -> models.IntegrationApi:
    row = models.IntegrationApi.objects.filter(connection=connection, pk=row_id).first()
    if row is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, message_key=REFUSAL_NO_SUCH_API
        )
    return row


@require_role(SYSTEM_ADMIN)
def edit(
    *, actor: Any, connection: Any, row_id: Any, name: Any = None, url: Any = None
) -> models.IntegrationApi:
    """Rename or re-point a CUSTOM row. A standard row is refused BY NAME.

    R36, PO verbatim: *"in table also give edit button + remember if we have
    existing Apis , standard APis those will be availabel for enable diable but
    those will not be editable"*. The name of a standard API is the manifest's
    and its address is the connector's — both are OURS, and the blueprint's own
    14-September ruling on that half still stands (§7.2 narrows the ADD rule, not
    this one).
    """
    row = _row_or_refuse(connection, row_id)
    if row.is_standard:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-078", message_key=REFUSAL_STANDARD_LOCKED
        )
    before = {"name": row.name, "url": row.url}
    if name is not None:
        row.name = _clean_name(name)
    if url is not None:
        row.url = _clean_url(url)
    row.save(update_fields=["name", "url", "updated_at"])
    core_audit.money_action(
        actor,
        AUDIT_EDITED,
        "integration_api",
        row.id,
        before=before,
        after={"name": row.name, "url": row.url},
    )
    return row


@require_role(SYSTEM_ADMIN)
def remove(*, actor: Any, connection: Any, row_id: Any) -> None:
    """Delete a CUSTOM row. A standard row is refused — it ships with the
    connector and there is nothing of the clerk's to delete (§7.4)."""
    row = _row_or_refuse(connection, row_id)
    if row.is_standard:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-078", message_key=REFUSAL_STANDARD_LOCKED
        )
    before = {"operation": row.operation, "name": row.name, "url": row.url}
    row_id_kept = row.id
    row.delete()
    core_audit.money_action(
        actor, AUDIT_REMOVED, "integration_api", row_id_kept, before=before, after=None
    )


@require_role(SYSTEM_ADMIN)
def switch(
    *,
    actor: Any,
    connection: Any,
    operation_name: str | None = None,
    row_id: Any = None,
    enabled: bool,
    registry: Registry = REGISTRY,
) -> models.IntegrationApi:
    """Turn ONE API on or off — ours or theirs. §7.4: both may be switched.

    A STANDARD row is created on first use, because absence means ON
    (`is_enabled`) and there is nothing to write until somebody disagrees with
    that default.

    ⚠ **SWITCHING A SYNC ON ASKS RULE 1 AGAIN.** Turning the standard sync back
    on while a custom one is running would produce the two writers rule 1
    exists to prevent, by a different door — and a rule enforced only where it
    was first written is a rule with a hole in it.
    """
    manifest = _manifest_or_refuse(connection.provider_key, registry)
    if row_id is not None:
        row = _row_or_refuse(connection, row_id)
    else:
        declared = {one.name for one in manifest.operations}
        if str(operation_name) not in declared:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key=REFUSAL_NO_SUCH_API
            )
        row, _made = models.IntegrationApi.objects.get_or_create(
            connection=connection,
            operation=str(operation_name),
            is_standard=True,
            defaults={"tenant_id": connection.tenant_id, "enabled": True},
        )
    if bool(enabled) and not row.enabled:
        kind = kind_of(manifest.key, row.operation)
        if kind in WRITING_KINDS and active_sync_count(connection, manifest) >= 1:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref="BR-INT-078", message_key=REFUSAL_SECOND_SYNC
            )
    before = {"enabled": row.enabled}
    row.enabled = bool(enabled)
    row.save(update_fields=["enabled", "updated_at"])
    core_audit.money_action(
        actor,
        AUDIT_SWITCHED,
        "integration_api",
        row.id,
        before=before,
        after={"enabled": row.enabled, "operation": row.operation},
    )
    return row


__all__ = [
    "AUDIT_ADDED",
    "AUDIT_EDITED",
    "AUDIT_REMOVED",
    "AUDIT_SWITCHED",
    "KINDS",
    "KIND_ADDRESS_LOOKUP",
    "KIND_MAP_TILES",
    "KIND_OF_OPERATION",
    "KIND_SCHEDULED_SYNC",
    "REFUSAL_ALREADY_CONFIGURED",
    "REFUSAL_SECOND_SYNC",
    "REFUSAL_STANDARD_LOCKED",
    "WRITING_KINDS",
    "active_sync_count",
    "add",
    "addable_kinds",
    "custom_rows",
    "edit",
    "enabled_operations",
    "is_enabled",
    "kind_of",
    "kinds_for",
    "lookup_addresses",
    "operation_of_kind",
    "refuse_second_sync",
    "remove",
    "rows_for",
    "switch",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (the 2026-09-17 rulings verbatim) + §1.6 + B14 33/31/21/35
# generated: 2026-09-17 by the CR-115-BRC05 per-API lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_custom_apis.py · G128 (no second resolver) · G77
# exceptions: per-API KEYS are deferred — DEF-INT-5680, §7.6's own instruction
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

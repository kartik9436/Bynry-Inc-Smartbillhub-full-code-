# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-013 (EP-SHL-05 — "preference storage"; the read-on-mount /
#           write-on-change half that was deferred when the table landed)
#           Screens: every list screen's column chooser (S14, S15, S17, S25,
#           S26, S27, S30, S33, S34, S37, S45, S49, S108, …) + S8's shell
# Defect:   DEF-647 (2026-08-24, PO on the deployed build: *"when I make changes
#           to colume selector and save it; it save temaprarily - it does not
#           save it for that user - i ahve to make the changes every time I
#           again clikc on that menu - it reset to deault"*). There was no
#           persistence AT ALL: the model, the migration, the RLS policy, the
#           `screenId` field and the pure transitions all existed and NOTHING
#           read or wrote a row.
# Rules:    BR-SHL-024 (verbatim below — the whole contract this module
#           implements) · BR-SHL-027 (server-side ALWAYS, never localStorage) ·
#           BR-SHL-013 (`table.‹screen›.columns` is the key)
# Tests:    06-backend/tests/test_us_shl_013_user_preferences.py (per-TC)
# Impacts:  apps/tenancy/preferences_api.py (its only caller) ·
#           07-frontend/src/components/DataTable.tsx (the consumer)
# ───────────────────────────────────────────────────────
"""US-SHL-013 preference storage — the read and the write, over the EXISTING
`user_preferences` table (tenancy migration 0002, RLS in 0003).

LAW 0 (B8): the API layer is thin, this module is the sole writer and the read
path for these rows, and no ORM statement for `user_preferences` lives anywhere
else.

BR-SHL-024, quoted verbatim because every constant below is one clause of it:

    `user_preferences` stores **UI preferences only** — never business data,
    never money, never anything another user needs. One row per (user, tenant,
    key); dotted-namespace keys ≤128 chars (`shell.*`, `table.*`); jsonb value
    ≤32 KB; last-write-wins on concurrent writes; unknown keys read as absent
    (callers fall back to defaults); rows are removed when the tenant membership
    is removed; tenant-scoped under RLS like every tenant table.

Clause by clause, and where each one is:

  * "one row per (user, tenant, key)"  → the `uq_user_prefs` UNIQUE constraint
    (migration 0002) plus `update_or_create` below.
  * "dotted-namespace keys ≤128 chars (`shell.*`, `table.*`)" → `validate_key`.
    The two namespaces are enforced as an ALLOW-LIST rather than as prose: an
    unrecognised namespace is refused (VAL-002), because the alternative is a
    typo'd key that writes a row nothing will ever read — the silent shape
    BR-SHL-024's own "unknown keys read as absent" clause then hides forever.
    A new preference FAMILY therefore adds a line here and a line to the rule,
    together, which is the point.
  * "jsonb value ≤32 KB" → `validate_value` (BIZ-CAP → 422; US-SHL-013 TC-4
    says "Rejected (413/422) with a clear error; existing stored value
    untouched", and the refusal is raised BEFORE any write).
  * "last-write-wins on concurrent writes" → `update_or_create`, no version
    column, no optimistic-concurrency header. Two tabs of the same user racing
    is a UI preference resolving to whichever landed second; that is the signed
    behaviour, not an oversight.
  * "unknown keys read as absent (callers fall back to defaults)" →
    `read_preference` returns `ABSENT`, and the endpoint renders it as
    `{"value": null}` with **200**. Not 404: US-SHL-013 TC-6 says a read of
    `table.S99.columns` "Returns absent (no error)", and a 404 in this client's
    error path is an error.
  * "rows are removed when the tenant membership is removed" → the model's
    `on_delete=CASCADE` on `user`, which predates this module.
  * "tenant-scoped under RLS like every tenant table" → the policy in
    `db/rls_tenancy_w0.sql`, plus the explicit `tenant_id=` filter on every
    queryset here so the same law holds on the sqlite test tier where there is
    no RLS (CLAUDE.md hard rule 1: no cross-tenant queryset).

WHAT IS SCOPED BY WHAT, BECAUSE THE TWO HALVES ARE DIFFERENT MECHANISMS
-----------------------------------------------------------------------
TENANT scoping is the database's (RLS FORCE) *and* the queryset's. USER scoping
is the QUERYSET'S ALONE — there is no per-user RLS policy and there should not
be, because `user_preferences` is not the only table a user touches and the
tenant policy is the one B2 §3 signs. So `user_id=` is never optional here and
never comes from client input: it is `request.user.id`, server-attached by the
identity layer. A user asking for another user's key gets ABSENT, exactly like
a key nobody has ever written — the same non-leaking answer HR-1 requires of
the cross-tenant case.

NOT AUDITED, DELIBERATELY. CLAUDE.md rule 7 audits every MONEY action; a column
order is not one, and BR-SHL-024 explicitly scopes this table to "UI preferences
only — never business data, never money". Writing an audit row per column toggle
would bury the money trail this product's auditors actually read.
"""

import json
import re
from typing import Any

from apps.tenancy.models import UserPreference
from core import errors

#: BR-SHL-024: "dotted-namespace keys ≤128 chars".
KEY_MAX_CHARS = 128

#: BR-SHL-024: "jsonb value ≤32 KB". Measured on the UTF-8 JSON encoding, which
#: is what Postgres stores and what a client sends — not on `len(str(value))`.
VALUE_MAX_BYTES = 32 * 1024

#: BR-SHL-024's two named namespaces, and nothing else (see the module
#: docstring for why this is an allow-list rather than a comment).
#:   shell.*  — US-SHL-001's sidebar state and its neighbours
#:   table.*  — BR-SHL-013's `table.‹screen›.columns`
KEY_NAMESPACES = ("shell", "table")

#: A dotted key: a namespace, then one or more further segments. Segments are
#: alphanumeric with `_` and `-`; screen ids (`S17`, `SET-06.3`) and column-set
#: names both fit, and `..`, a trailing dot and whitespace do not.
_KEY_SEGMENT = r"[A-Za-z0-9_-]+"
KEY_PATTERN = re.compile(rf"^(?:{'|'.join(KEY_NAMESPACES)})(?:\.{_KEY_SEGMENT})+$")


class _Absent:
    """The "no row" answer, distinct from a row whose stored value IS null.

    A sentinel rather than `None` because `None` is a lawful jsonb value: a
    caller that stored `null` deliberately and a caller who never stored
    anything must be distinguishable, or "unknown keys read as absent" quietly
    becomes "unknown keys read as null" and a screen cannot tell a cleared
    preference from a missing one.
    """

    def __repr__(self) -> str:  # pragma: no cover — debugging aid only
        return "ABSENT"

    def __bool__(self) -> bool:
        return False


ABSENT = _Absent()


# ── validation (BR-SHL-024's clauses, one function each) ────────────────────


def validate_key(key: str) -> str:
    """BR-SHL-024's key law. Refuses rather than truncates or normalises.

    ⚠ The three branches share ONE `message_key` and differ by CODE and PARAMS.
    G32 requires every raised key to resolve to a customer sentence, and a
    person cannot type a preference key — empty, over-length and mis-shaped are
    the same fact to them ("that preference name is not one we store") and three
    different facts to a log, which is what the code and the params carry.
    """
    if not key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="settings.preferences.key_invalid",
            br_ref="BR-SHL-024",
        )
    if len(key) > KEY_MAX_CHARS:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="settings.preferences.key_invalid",
            params={"max": KEY_MAX_CHARS, "length": len(key)},
            br_ref="BR-SHL-024",
        )
    if KEY_PATTERN.match(key) is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="settings.preferences.key_invalid",
            params={"namespaces": list(KEY_NAMESPACES)},
            br_ref="BR-SHL-024",
        )
    return key


def value_size_bytes(value: Any) -> int:
    """The stored size of `value`, as Postgres would hold it.

    `json.dumps` with the compact separators the ORM's JSONField uses, encoded
    UTF-8. A dict/list that cannot be JSON-encoded at all raises here rather
    than at INSERT time, so the refusal is the ratified envelope and not a 500.
    """
    try:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="settings.preferences.value_not_json",
            br_ref="BR-SHL-024",
        ) from exc
    return len(encoded.encode("utf-8"))


def validate_value(value: Any) -> Any:
    """BR-SHL-024's 32 KB cap. Raised BEFORE the write, so TC-4's "existing
    stored value untouched" is true by construction rather than by rollback."""
    size = value_size_bytes(value)
    if size > VALUE_MAX_BYTES:
        raise errors.BizError(
            errors.BIZ_CAP,
            br_ref="BR-SHL-024",
            message_key="settings.preferences.value_too_large",
            params={"max_bytes": VALUE_MAX_BYTES, "bytes": size},
        )
    return value


# ── read path (selector) ────────────────────────────────────────────────────


def read_preference(tenant_id: Any, user_id: Any, key: str) -> Any:
    """This user's value for `key` in this tenant, or `ABSENT`.

    Scoped by BOTH tenant and user in the queryset itself — see the module
    docstring on why the two halves are different mechanisms.

    ⚠ The ROW is fetched, not `values_list("value")`: a row whose stored value
    is jsonb `null` and no row at all would otherwise both come back as `None`,
    and those are different facts (see `_Absent`).
    """
    row = UserPreference.objects.filter(tenant_id=tenant_id, user_id=user_id, key=key).first()
    if row is None:
        return ABSENT
    return row.value


# ── write path (service — sole writer) ──────────────────────────────────────


def set_preference(tenant_id: Any, user_id: Any, key: str, value: Any) -> Any:
    """Store `value` under `key` for THIS user in THIS tenant; return the value.

    Last-write-wins (BR-SHL-024): `update_or_create` against the
    (tenant, user, key) unique constraint. Validation runs first, so a refused
    write leaves the previous row exactly as it was.
    """
    validate_key(key)
    validate_value(value)
    UserPreference.objects.update_or_create(
        tenant_id=tenant_id,
        user_id=user_id,
        key=key,
        defaults={"value": value},
    )
    return value


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-013@EP-SHL-05 (story §1 "preference writes happen via a service") + DEF-647
# generated: 2026-08-24 by story-coder (DEF-647 column-preference lane)
# checklist: A✔ B✔ C✔ D✔ E✔(the frontend half lands in the same lane — DataTable.tsx) F✔ G✔ H=deferred(PO)
# gates: see the API module's trailer (one lane, one gate run)
# exceptions: US-SHL-013 §1 and 11b §2.x name the path `PUT /me/preferences/{key}`; this lane serves `/user-preferences/{key}` per DEF-647's stated fix, because `/me/*` is identity's registered route family and this table is hosted by tenancy — REPORTED for the A11/11b addendum, not resolved here · the collection read `GET /me/preferences` (11b) is NOT built: no consumer needs it yet and an unread route is the hard-won-law-2 shape this defect IS
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

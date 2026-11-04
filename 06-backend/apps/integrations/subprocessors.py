# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) TC-8 — the subprocessor register gains the
#           relationship POINTING INWARD, derived from the live connection
#           (`C33`). CR-069 wave S, task S1's last clause.
# Rules:    BR-INT-035 (*"the subprocessor register records the relationship in
#           the inbound direction, derived from live connections"*) ·
#           OQ-INT-1481 CLOSED 2026-09-04 option (a) — a System Admin's audited
#           grant PLUS a register row pointing inward, *"the shape the register
#           did not have"* · BR-INT-054 (c: the lifecycle of a connection) ·
#           CLAUDE.md hard rule 1 (rows come from the tenant on the session)
# Tests:    06-backend/tests/test_us_int_041_partner_surface.py (TC-8, and the
#           two-tenant case that proves a row cannot cross)
# Impacts:  apps/integrations/partner_api.py (GET …/subprocessors) ·
#           07-frontend/src/features/integrations/AccessLogPanel.tsx
# ───────────────────────────────────────────────────────
"""The subprocessor register — who else touches our customers' data, in both directions.

WHO READS THIS, AND WHAT THEY ARE ASKING
-----------------------------------------
Not us. A utility's manager, an auditor, or a customer's lawyer, asking one
question: **"who else has our customers' data, and who let them have it?"**
That question has to be answerable by reading, without knowing what a manifest
is, what `gl_partner` means, or that this product has a concept called a
connection. So every row is a sentence:

    Aclarian — reads payments and bills — authorised by Alex Reed on 3 Sep 2026
    Twilio — receives a phone number and a message — connected by Alex Reed on 12 Aug 2026

`sentence()` is the field a screen and an export both print. The structured
fields beside it exist so the screen can sort and filter; they are not the
answer, and a register that printed only them would not be one.

DERIVED, NEVER TYPED
---------------------
`C33` and `BR-INT-035` both say the register is derived from LIVE connections.
The reason is the failure a hand-kept register has: somebody adds a partner and
forgets to add the row, and the document goes on saying five names while six
systems read the data. Here there is no second place to forget — a connection
that can be read from IS a row, and disconnecting it removes the row on the
next read. Nothing in this module writes a register table, because there is not
one.

THE INWARD DIRECTION IS THE NEW SHAPE
--------------------------------------
Every other connector is the utility reaching OUT: we hand Twilio a phone
number, so Twilio processes data on our behalf — the ordinary subprocessor
shape, and the one the register already had. A partner reading from us points
the other way: **they** collect from **us**, on their own schedule, and the
authorisation is the utility's rather than the vendor's. `OQ-INT-1481` was
ruled on that specifically (option (a), 2026-09-04): a System Admin authorises
it, as an audited grant on the connection **plus** a register row pointing
inward.

So each row carries `direction`, and the two read differently on purpose:
*receives* for outward, *reads* for inward. A register that flattened them
would answer the question wrongly — "Aclarian receives payments" suggests we
send it, and what actually happens is that Aclarian comes and takes it at 02:41.

⚠ **THE GRANT IS PART OF THE ANSWER, NOT A FOOTNOTE.** An inward row with no
`authorised by` is the register saying *somebody outside is reading this and we
cannot tell you who allowed it*, which is exactly the finding an auditor is
looking for. It renders as **"authorisation not recorded"** in the sentence
rather than being quietly omitted, because an absence that prints as nothing is
indistinguishable from an absence that never existed (CLAUDE.md hard rule 8's
lesson, one module along).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.integrations import models
from apps.integrations.registry import REGISTRY, Manifest, Registry
from apps.integrations.runners import serve
from core.tenancy import current_tenant_id

#: The register only ever describes a relationship that is REAL. A connection
#: that was never set up, or that has been switched off, is not a subprocessor
#: of anything — `not_set_up` and `off` are absent for that reason, and
#: `not_working` is PRESENT for the opposite one: a partner whose last call
#: failed still holds everything it collected up to then.
LIVE_STATUSES = (
    models.STATUS_UNTESTED,
    models.STATUS_WORKING,
    models.STATUS_NOT_WORKING,
)

DIRECTION_INWARD = "inward"
DIRECTION_OUTWARD = "outward"


def _day(value: Any) -> str | None:
    """The date part, whichever of the two shapes the value arrives in.

    ⚠ AN AUTHORISATION DATE ARRIVES TWO WAYS AND BOTH ARE REAL: a `datetime`
    off `connection.connected_at`, and a STRING off `config["authority_grant"]`,
    because a JSON column cannot hold a datetime. The first draft called
    `.date()` on both and the grant path raised `AttributeError` — on the one
    branch that only runs after somebody has actually granted authority, which
    is the branch a quick test never reaches.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value[:10] or None
    return value.date().isoformat()


@dataclass(frozen=True)
class RegisterRow:
    """One relationship, in a form a person can read.

    ⚠ NO DATABASE ID IS A FIELD HERE (B14 rule 31). `connection_id` is absent
    on purpose — a register row is a statement about a company, and the screen
    that lists them has no need to show a key.
    """

    party: str
    direction: str
    what: str
    authorised_by: str | None
    authorised_on: Any | None
    environment: str

    def sentence(self) -> str:
        """The whole row, as one line somebody can read aloud."""
        verb = "reads" if self.direction == DIRECTION_INWARD else "receives"
        who = self.authorised_by or None
        when = _day(self.authorised_on)
        if who and when:
            tail = f"authorised by {who} on {when}"
        elif who:
            tail = f"authorised by {who}"
        else:
            # See the docstring: an unrecorded authorisation is the finding, so
            # it is printed rather than dropped.
            tail = "authorisation not recorded"
        return f"{self.party} — {verb} {self.what} — {tail}"


def _party(manifest: Manifest, connection: models.IntegrationConnection) -> str:
    """The company's own name where the utility typed one, the catalogue's
    otherwise. A register that said *Third-party GL* where the utility knows
    the firm as *Aclarian* answers the question with our vocabulary instead of
    theirs."""
    label = (connection.label or "").strip()
    return label or manifest.display_name


def _inward_operations(manifest: Manifest) -> tuple[str, ...]:
    """The operations THEY start against US — `direction = out`, `initiative =
    them`, the SERVE quadrant. This is the same pair `runners.runner_for()`
    reads, so the register and the runtime cannot disagree about which
    connections point inward."""
    return tuple(
        one.label.lower()
        for one in manifest.operations
        if one.direction == "out" and one.initiative == "them"
    )


def _outward_operations(manifest: Manifest) -> tuple[str, ...]:
    return tuple(
        one.label.lower()
        for one in manifest.operations
        if not (one.direction == "out" and one.initiative == "them")
    )


#: The four runner verbs an operation LABEL may open with. A label is drawn
#: verb-first and three words or fewer (the naming format, blueprint p156–p158),
#: so *Read payments* · *Collect readings* · *Send messages* are all correct ON
#: A SCREEN and all wrong inside the sentence this register builds.
_LABEL_VERBS = ("read ", "collect ", "send ", "take ")


def _noun(label: str) -> str:
    """*read payments* → *payments*. The THING, not the act.

    ⚠ **THIS EXISTS BECAUSE `CR-110-BRC04` RENAMED THREE LABELS AND THE REGISTER
    STARTED READING BADLY** — *"Aclarian read payments, read bills and read
    customers"*. The labels themselves are right: the blueprint draws them
    verb-first on the API table and the naming format the PO ruled says a clerk
    label is a verb and three words or fewer.

    **The fault was here rather than there.** This register answers one
    question — *what does this firm take?* — and its own header says it must be
    answerable *"without knowing what a manifest is"*. That question wants a
    NOUN, and the sentence around it (`… takes …`) already supplies the verb, so
    stacking a second one on every item was always going to read wrong; the
    rename only made it visible. One test caught it, and the sentence is the
    thing it asserts on purpose.
    """
    lowered = label.lower()
    for verb in _LABEL_VERBS:
        if lowered.startswith(verb):
            return lowered[len(verb) :]
    return lowered


def _phrase(labels: tuple[str, ...]) -> str:
    """`payments and bills` — the plan's own words for what Aclarian takes."""
    unique: list[str] = []
    for one in (_noun(label) for label in labels):
        if one not in unique:
            unique.append(one)
    if not unique:
        return "nothing recorded"
    if len(unique) == 1:
        return unique[0]
    return f"{', '.join(unique[:-1])} and {unique[-1]}"


def _grant(connection: models.IntegrationConnection) -> tuple[str | None, Any | None]:
    """The audited grant `OQ-INT-1481` option (a) requires, off the
    connection's non-secret config; falls back to who CONNECTED it, which is
    the honest answer for an outward relationship nobody had to grant."""
    grant = (connection.config or {}).get(serve.GRANT_CONFIG_KEY) or {}
    if isinstance(grant, dict) and grant.get("granted_by_name"):
        return str(grant["granted_by_name"]), grant.get("granted_at")
    connected_by = getattr(connection, "connected_by", None)
    name = getattr(connected_by, "display_name", None) or getattr(connected_by, "full_name", None)
    return (str(name) if name else None), connection.connected_at


def register_rows(*, registry: Registry = REGISTRY) -> list[RegisterRow]:
    """Every subprocessor relationship this utility currently has.

    Reads under whatever `app.tenant_id` the request set — no tenant ARGUMENT,
    so it cannot be pointed at another utility's connections (hard rule 1).

    ⚠ **THE `tenant_id` FILTER IS BELT AND BRACES, AND WITHOUT IT THIS FUNCTION
    LISTED ANOTHER UTILITY'S PARTNERS ON SQLITE.** RLS `FORCE` scopes it on
    PostgreSQL; the suite runs on SQLite, which has no RLS, and the first draft
    relied on RLS alone. `test_tc8d…` caught it — but only because it exists.
    A compliance register that answered *who else touches our customers' data*
    with somebody else's answer is a worse defect than the one this file was
    written for, so the tenant is stated twice: once by the database, once
    here. Same argument, and the same paragraph, as `runners/serve.py`.
    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return []
    rows: list[RegisterRow] = []
    connections = models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, status__in=LIVE_STATUSES
    ).order_by("provider_key", "created_at")
    for connection in connections:
        manifest = registry.get(connection.provider_key)
        if manifest is None:
            # A connection whose manifest has been retired is still a real
            # relationship; naming the key is better than dropping the row.
            continue
        granted_by, granted_at = _grant(connection)
        inward = _inward_operations(manifest)
        outward = _outward_operations(manifest)
        if inward:
            rows.append(
                RegisterRow(
                    party=_party(manifest, connection),
                    direction=DIRECTION_INWARD,
                    what=_phrase(inward),
                    authorised_by=granted_by,
                    authorised_on=granted_at,
                    environment=connection.environment,
                )
            )
        if outward:
            rows.append(
                RegisterRow(
                    party=_party(manifest, connection),
                    direction=DIRECTION_OUTWARD,
                    what=_phrase(outward),
                    authorised_by=granted_by,
                    authorised_on=granted_at,
                    environment=connection.environment,
                )
            )
    return rows


def as_payload(*, registry: Registry = REGISTRY) -> list[dict[str, Any]]:
    """The register as a screen and an export both read it."""
    return [
        {
            "party": row.party,
            "direction": row.direction,
            "what": row.what,
            "authorised_by": row.authorised_by,
            "authorised_on": row.authorised_on,
            "environment": row.environment,
            "sentence": row.sentence(),
        }
        for row in register_rows(registry=registry)
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11) TC-8; OQ-INT-1481 CLOSED option (a)
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no secret and no money is read here)
# gates: pytest tests/test_us_int_041_partner_surface.py::test_tc8_register_row_points_inward
# exceptions: none — the register is derived on every read and this module writes no table
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    `CR-115-BRC05` §7 — domain verification. Screens: S142's sending-
#           domain panel (ANOTHER LANE'S; this file serves it and draws none
#           of it). Endpoint: `GET|POST /integrations/{key}/sending-domain`.
# Rules:    BR-INT-003 (no secret in anything served) · BR-INT-022 / BR-INT-041
#           (every provider dial through the guard) · BR-INT-038 (the adapter
#           translates; this decides) · CLAUDE.md hard rule 1 (every read names
#           the tenant) · B14 rule 31 (no database id is a visible value)
# Tests:    06-backend/tests/test_cr115_esp_adapters.py
# Impacts:  apps/integrations/api.py (the two routes) ·
#           apps/integrations/adapters/esp_email.py (the answer it reads)
# ───────────────────────────────────────────────────────
"""The DNS records a utility's IT team must publish, and who is waiting on whom.

⚠ **THE PRODUCT OWNER CALLS THIS THE LONG POLE AND THE ARITHMETIC IS WHY.** Our
part is days; theirs is **one to three weeks**; Production is gated behind
theirs. PO, 2026-09-17, re-asked in plain words and answered in plain words:

    *"Even using our own SendGrid account, the emails will say they come FROM
    THE UTILITY — `billing@ottumwawater.gov`. For Gmail and Outlook to believe
    that and not file it as spam, whoever runs that utility's website must add
    three short records to their domain settings. It is a ten-minute job for
    them; getting it asked for, approved and done usually takes one to three
    weeks. ⚠ That wait is theirs and we cannot shorten it, and everything we
    build is finished long before those records are — which is why it is worth
    starting on day one rather than at the end."*

**So this file is built around one instruction: GET THE RECORDS OUT EARLY.**
Three consequences, and each is a design decision rather than a convenience:

1. **`GET` NEVER DIALS.** It answers from what we last stored, instantly, so a
   panel opens whether or not the provider is reachable and whether or not
   anybody has pressed anything. `POST` is the press that asks the provider.
   A `GET` with a side effect would also mean a screen refresh spending a
   utility's rate limit, which `BR-INT-041` is about.

2. **THE DMARC RECORD IS SERVED BEFORE ANY CHECK HAS EVER RUN.** It is the one
   line on the list that no ESP issues — the domain's owner makes that statement
   about their own mail — so it needs no provider, no credential and no network.
   A utility on Postmark, whose other two records are blocked behind
   `DEF-INT-5650`, can still start their IT ticket on day one with a third of the
   work. **Waiting until we could serve all three would have held the whole
   clock for a value we already had.**

3. **AN ABSENCE IS SERVED WITH ITS REASON, NEVER AS AN EMPTY LIST.**
   `available: false` plus a machine word the panel translates. An empty panel
   reads as a bug and generates a support call; *we cannot ask Postmark this
   with the token we hold* is a fact somebody can act on.

⚠ **NOTHING HERE COMPOSES A DNS VALUE.** Every provider-issued record comes out
of the provider's own answer and carries `source: "provider"`; the single line we
write ourselves carries `source: "ours"`. SendGrid's `em1234` prefix and its DKIM
selectors differ per ACCOUNT and cannot be derived — a plausible-looking record
publishes cleanly, verifies never, and costs the utility's one-to-three-week
cycle a second time. `DnsRecord.source` exists for exactly this and the field is
on the wire so a reader can see which is which.

⚠ **AND THE WHOLE OF IT IS UNPROVEN AGAINST A REAL PROVIDER.** Neither SendGrid
nor Postmark is reachable from this build environment; every test runs against
`esp_fixtures.py`, which is hand-shaped and says so first in its own docstring.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations import models, services
from apps.integrations.adapters import esp_email
from apps.integrations.registry import REGISTRY, Manifest
from apps.integrations.runners.deliver import view_of
from apps.integrations.scrubbing import scrub
from core import errors

#: The operation a manifest declares when it can be asked about a domain. A
#: manifest that does not declare it CANNOT be asked, and that is how Postmark's
#: blocker is expressed — as an absence with a reason, not as a branch on a
#: provider key (`G77`).
OPERATION = esp_email.OP_CHECK_DOMAIN

#: Why we cannot ask, as machine words the panel turns into its own sentences.
#: ⚠ B14 rule 33: the RATIONALE is zero words on screen and lives here and in
#: the register. These are keys, not copy.
REASON_NOT_CONNECTED = "not_connected"
REASON_NO_DOMAIN = "no_sending_domain"
REASON_PROVIDER_CANNOT_BE_ASKED = "provider_cannot_be_asked"
REASON_NOT_AN_EMAIL_CONNECTOR = "not_an_email_connector"


def described(tenant_id: Any, provider_key: str, *, attempt: dict | None = None) -> dict[str, Any]:
    """`GET` — what we hold, plus the DMARC line, and **no network at all**.

    ⚠ **IT ANSWERS FOR A CONNECTOR THAT HAS NEVER BEEN CHECKED**, because that
    is the state every utility is in on the day the clock starts and it is the
    state the panel most needs to draw. `checked_at` is `null`, the state is
    `unverified`, and the DMARC record is already there to be handed over.

    `attempt` is `check_now`'s and is `None` on a real `GET` — see
    `last_attempt` in `_envelope`.
    """
    manifest = REGISTRY.get(provider_key)
    if manifest is None:
        raise errors.NotFoundError()
    connection = services.connection_for(tenant_id, provider_key)
    if connection is None:
        return _envelope(provider_key, connected=False, reason=REASON_NOT_CONNECTED, attempt=attempt)
    domain = _domain_of(connection)
    if not domain:
        return _envelope(
            provider_key, connected=True, reason=REASON_NO_DOMAIN, domain=None, attempt=attempt
        )
    # Hard rule 1: the tenant is named as well as narrowed by a row already
    # fetched under one — this module's own belt-and-braces house style, and
    # what `G126` checks (the suite runs on SQLite, where RLS does not exist).
    row = (
        models.IntegrationSendingDomain.objects.filter(
            tenant_id=tenant_id, connection=connection, domain=domain
        )
        .order_by("-checked_at")
        .first()
    )
    return _envelope(
        provider_key,
        connected=True,
        domain=domain,
        stored=row,
        reason=_why_not_askable(manifest),
        attempt=attempt,
    )


@transaction.atomic
def check_now(*, actor: Any, tenant_id: Any, provider_key: str) -> dict[str, Any]:
    """`POST` — ask the provider, store what they said, answer the same shape.

    ⚠ **THE DIAL GOES THROUGH `guarded_adapter_call` AND THERE IS NO SECOND
    PATH.** One utility's unreachable ESP must stay one utility's problem
    (`BR-INT-041`), and `G108` exists because a 427-line timeout-and-breaker
    module once landed with nothing importing it.

    ⚠ **A BREAKER-SKIPPED OR TIMED-OUT CHECK CHANGES NOTHING WE HOLD.** The
    stored answer is the last thing the provider actually said; overwriting it
    with *we could not ask* would delete a utility's own DNS records from the
    one screen their IT team is working from, over a thirty-second outage.
    """
    manifest = services._live_manifest(actor, provider_key, route="run", registry=REGISTRY)
    connection = services._connected_or_refuse(tenant_id, provider_key)
    domain = _domain_of(connection)
    if not domain:
        return _envelope(provider_key, connected=True, reason=REASON_NO_DOMAIN, domain=None)
    refusal = _why_not_askable(manifest)
    if refusal is not None:
        return described(tenant_id, provider_key)
    adapter_cls = services._adapter_or_refuse(
        actor, manifest, route="run", registry=REGISTRY
    )
    operation = next(one for one in manifest.operations if one.name == OPERATION)
    secrets = services.credential_secrets(connection)  # the ONE read (BR-INT-003)
    try:
        outcome = services.guarded_adapter_call(
            connection=connection,
            operation=operation,
            call=lambda _secrets=secrets: adapter_cls().execute(
                view_of(connection),
                _secrets,
                [{"ref": domain, "operation": OPERATION, "domain": domain}],
            ),
        )
    finally:
        del secrets
    if outcome.skipped or outcome.timed_out:
        return described(tenant_id, provider_key, attempt=_attempt(False, outcome.sentence))
    answer = _answer_from(outcome.value)
    if answer is None:
        return described(tenant_id, provider_key, attempt=_attempt(False, _refusal_of(outcome.value)))
    _store(tenant_id=tenant_id, connection=connection, answer=answer)
    return described(tenant_id, provider_key, attempt=_attempt(True, None))


# ── the envelope ────────────────────────────────────────────────────────────


def _envelope(
    provider_key: str,
    *,
    connected: bool,
    domain: str | None = None,
    stored: Any = None,
    reason: str | None = None,
    attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The ONE shape both routes answer, so the panel has one thing to read.

    ⚠ **NO DATABASE ID IS ON IT** (B14 rule 31). The row's identity to a person
    is the DOMAIN, which is also what they would search for.
    """
    records: list[dict[str, Any]] = []
    if stored is not None and isinstance(stored.records, list):
        records = [dict(one) for one in stored.records if isinstance(one, dict)]
    elif domain:
        # ⚠ **THE DAY-ONE ANSWER.** Nothing has been checked and one third of
        # the work can still be handed over, because DMARC is ours to give.
        records = [esp_email.dmarc_record(domain).as_dict()]
    return {
        "provider_key": provider_key,
        "connected": connected,
        #: Can the provider be asked AT ALL with the credential we hold? Where
        #: this is `false`, `reason` says why and the panel is expected to show
        #: the records it does have rather than an empty box.
        "available": reason is None and connected and bool(domain),
        "reason": reason,
        "domain": domain,
        "state": (stored.state if stored is not None else esp_email.DOMAIN_UNVERIFIED),
        "checked_at": _stamp(stored, "checked_at"),
        #: ⚠ **STAMPED ONCE, NEVER CLEARED.** *When did they finish* has a real
        #: answer that a later unverified state must not erase.
        "verified_at": _stamp(stored, "verified_at"),
        "records": records,
        "provider_text": (stored.provider_text if stored is not None else None),
        #: ⚠ **WHAT THE PRESS JUST DID, AND IT EXISTS BECAUSE WITHOUT IT THE
        #: BUTTON WAS A CONTROL THAT CHANGED NOTHING** (hard-won law 2's
        #: mirror). A provider that refuses — `403` because the key lacks
        #: `whitelabel.read` (`DEF-INT-5649`), a breaker that is open, a socket
        #: that never answers — leaves the STORED answer exactly as it was,
        #: deliberately: overwriting a utility's own DNS records with *we could
        #: not ask* would delete the one screen their IT team works from over a
        #: thirty-second outage. But then the whole reply is byte-identical to
        #: the one before the press, so a clerk pressing *Check* saw nothing
        #: happen and had no way to tell a refusal from *nothing has changed*.
        #:
        #: `null` on a `GET`, which never dials. On a `POST`:
        #: `{"ok": true|false, "provider_text": <their words, or ours for a
        #: breaker> }` — and `ok: false` beside an unchanged `checked_at` is
        #: exactly *we asked and could not find out*.
        "last_attempt": attempt,
    }


def _attempt(ok: bool, text: str | None) -> dict[str, Any]:
    """One press, as the panel reads it. THEIR words when they answered, OURS
    when nothing came back to quote (a breaker, a dead socket) — the same
    distinction `runtime.ProviderTimeout` exists for."""
    return {"ok": ok, "provider_text": (text or None)}


def _refusal_of(result: Any) -> str | None:
    """What the provider said on a check that did not succeed.

    ⚠ It reads the ADAPTER's item rather than re-deriving anything from a
    payload: the adapter is the anti-corruption layer and a second reader here
    would be a second place that understands SendGrid.
    """
    for one in getattr(result, "items", ()) or ():
        if one.outcome != "succeeded":
            return one.provider_text or one.detail
    return None


def _stamp(stored: Any, name: str) -> str | None:
    if stored is None:
        return None
    value = getattr(stored, name, None)
    return value.isoformat() if value is not None else None


# ── the pieces ──────────────────────────────────────────────────────────────


def _domain_of(connection: Any) -> str:
    return str((connection.config or {}).get("sending_domain") or "").strip().lower().strip(".")


def _why_not_askable(manifest: Manifest) -> str | None:
    """`None` when the provider can be asked, else the machine word for why not.

    ⚠ **IT READS THE MANIFEST AND NEVER THE PROVIDER KEY** (`G77`, `BR-INT-004`).
    Postmark's blocker is expressed as an operation it does not declare, so this
    function has no branch naming a vendor and a third ESP needs no edit here.
    """
    if manifest.category != "email":
        return REASON_NOT_AN_EMAIL_CONNECTOR
    if not any(one.name == OPERATION for one in manifest.operations):
        return REASON_PROVIDER_CANNOT_BE_ASKED
    return None


def _answer_from(result: Any) -> dict[str, Any] | None:
    """The adapter's one item, as the dictionary it serialised.

    The adapter is the anti-corruption layer and puts its answer on the item;
    this reads it back rather than re-deriving anything from a provider payload,
    which would be a second place that understands SendGrid.
    """
    import json

    items = getattr(result, "items", ()) or ()
    for one in items:
        if one.outcome != "succeeded" or not one.detail:
            continue
        try:
            found = json.loads(one.detail)
        except (TypeError, ValueError):
            continue
        if isinstance(found, dict) and "records" in found:
            found["provider_text"] = one.provider_text
            return found
    return None


def _store(*, tenant_id: Any, connection: Any, answer: dict[str, Any]) -> None:
    """One row per `(tenant, connection, domain)`, updated in place.

    ⚠ **NOT A HARD-RULE-4 TABLE.** Hard rule 4 names issued invoices, invoice
    lines, payments and journal entries; no balance moves here and nothing is
    owed to anybody, so *the latest thing the provider said* may be an update.
    What is NOT overwritten is `verified_at`.
    """
    now = timezone.now()
    domain = str(answer.get("domain") or "").strip().lower().strip(".")
    state = str(answer.get("state") or esp_email.DOMAIN_UNVERIFIED)
    if state not in models.SENDING_DOMAIN_STATES:
        state = esp_email.DOMAIN_UNVERIFIED
    text = answer.get("provider_text")
    row = (
        models.IntegrationSendingDomain.objects.filter(
            tenant_id=tenant_id, connection=connection, domain=domain
        )
        .order_by("-checked_at")
        .first()
    )
    if row is None:
        row = models.IntegrationSendingDomain(
            tenant_id=tenant_id, connection=connection, domain=domain
        )
    row.state = state
    row.records = list(answer.get("records") or [])
    row.checked_at = now
    if state == esp_email.DOMAIN_VERIFIED_STATE and row.verified_at is None:
        row.verified_at = now
    # THEIRS, scrubbed ONCE at the write — the same posture `services.finish_run`
    # takes, and `G84` fails a second writer.
    row.provider_text = scrub(text) if text else None
    row.save()


__all__ = [
    "OPERATION",
    "REASON_NOT_AN_EMAIL_CONNECTOR",
    "REASON_NOT_CONNECTED",
    "REASON_NO_DOMAIN",
    "REASON_PROVIDER_CANNOT_BE_ASKED",
    "check_now",
    "described",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 · the decision log of 2026-09-17 (PO question 5, re-asked in plain words and answered) · US-INT-015 · BR-INT-041
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a(the S142 panel is another lane's; this serves it) C✔ D✔(GET|POST /integrations/{key}/sending-domain) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_esp_adapters.py · G108 (the dial is inside a `call=`) · G126 (every read names the tenant) · G77 (no branch on a provider key — the blocker is read off the manifest)
# exceptions: (1) `GET` never dials, on purpose — see the docstring. (2) A skipped or timed-out check leaves the stored answer alone rather than overwriting a utility's records with *we could not ask*. (3) The DMARC record is the ONE value not read out of a provider answer and is marked `source: "ours"` on the wire.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

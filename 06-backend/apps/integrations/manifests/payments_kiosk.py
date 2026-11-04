"""Payment kiosk network — take payments at a machine, and hear when one bounces (Payments · LIVE, phase 5).

C1, the correction that did not survive contact: a provider is a SET OF
OPERATIONS. The kiosk card lists three things it does — *Account lookup ·
Payments · Returns* — each with its own state and its own last-run time; not
three cards, and not one word averaging them (BR-INT-028, US-INT-018).

All three are THEIR call to US. The lookup replies straight after
`authenticate`; a payment replies after `dedupe`, so a replayed notification
is answered **409 before anything is posted** (BR-INT-030, C6) — the number is
declared here, and the adapter contains none (BR-INT-045). A return carries the
same provider id as the payment it reverses, so its key is COMPOSITE with the
reversal marker (BR-INT-020 D) — otherwise every return would be refused as a
duplicate of its own payment. The credential is one we ISSUE them (field kind
`issued_secret`: shown once, copyable, never re-displayed) and the connection
carries a source allowlist (BR-INT-044). ⚠ What happens to a payment the
network flags as risky is `OQ-INT-1486` and is not decided here.

TWO VALUES WAVE N ADDED, AND WHY THEY ARE HERE RATHER THAN IN THE DOOR
-----------------------------------------------------------------------
`auth.header` names the credential header (`X-Kiosk-Key`) and
`idempotency.key_field` names the body field the provider’s own event id
arrives in (`eventId`). `inbound.py` reads both, so neither is a branch on a
provider key (G77) and a nineteenth connector adds no line of code
(`BR-INT-037`).

⚠ **`key_field` IS A SEEDED DEFAULT, NOT A SIGNED FACT.** The kiosk
network’s specification section that names its JSON fields could not be read
here (`EP-INT-13` records the same about its risk-flag section), and
`US-INT-044` §4 gives the payload as words — *`K-88231 · $42.10 · CASH`* —
rather than as keys. `eventId` is this lane’s reading, matching the redacted
capture in `fixtures/payments_kiosk/`; it is DATA, so the day the real
specification is read it is one line here and no code anywhere. Recorded in
`12-governance/02-decision-log.md`, 2026-09-06.

⚠ **THE DOOR STOPS AFTER `dedupe` (`BR-INT-058`, `OQ-INT-1729` (a)).** These
three operations declare where the reply sits and what the numbers are;
applying a payment, writing the reversal row, mapping `DRIVEUP` to *Other* and
showing the risk flag to a clerk are all **Runbooks’** and are NOT built. The
`tender` vocabulary above is read by S143, which shipped in wave D.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.payments_kiosk.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
    Vocabulary,
)

#: US-INT-037 §4 — the fourteen tender words the kiosk network sends, verbatim.
#: Each is a ROW on S143 for the clerk to point at one of the utility's own
#: payment methods (BR-INT-032); two of theirs may share one of ours. A
#: fifteenth arriving on the wire adds a red row and stops nothing (BR-INT-031).
KIOSK_TENDER_WORDS = (
    "CASH",
    "CHECK",
    "CREDIT",
    "DEBIT",
    "ACHCHECK",
    "ACHSAVINGS",
    "MONEYORDER",
    "CASHIERCHECK",
    "PAYPAL",
    "VENMO",
    "ZELLE",
    "GIFTCARD",
    "CRYPTO",
    "OTHER",
)

MANIFEST = Manifest(
    key="payments_kiosk",
    category="payments",
    display_name="Payment kiosk network",
    summary="Take payments at a machine, and hear when one bounces.",
    disposition=Disposition(kind="live", phase=5),
    # ⚠ `header="X-Kiosk-Key"` IS THE WHOLE OF WHAT THE DOOR KNOWS ABOUT THIS
    # PROVIDER'S CREDENTIAL, AND IT IS DATA (wave N, `BR-INT-037`, G77). The
    # placement says WHERE — a header — and this says WHICH ONE. `gl_partner`
    # declares none because `bearer` is `Authorization` by definition.
    auth=Auth(mode="they_hold_ours", placement="header", header="X-Kiosk-Key"),
    network_allowlist=True,
    vocabularies=(
        Vocabulary(
            entity_type="tender",
            label="How they pay",
            summary="Which of your payment methods each of their words means.",
            values=KIOSK_TENDER_WORDS,
        ),
    ),
    fields=(
        Field(name="issued_key", label="The key for them to use", kind="issued_secret"),
        Field(name="allowed_addresses", label="Allowed addresses", kind="text", required=False),
    ),
    operations=(
        Operation(
            name="payments",
            # INWARD — *what we allow them*, the half `serve.check_rate_limit`
            # enforces and the half the PO's *"if somone hack we will not have
            # a control"* is about. Sixty a minute is 3,600 an hour, far above
            # any real load at the top of the ICP (40,000 accounts), and a
            # stolen key gets sixty tries a minute rather than three hundred.
            rate_limit_per_minute=60,
            label="Payments",
            description="They send us each payment a customer made at a machine.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", key_field="eventId"
            ),
            completion="immediate",
            codec="json",
            respond_after="dedupe",
            envelope_status={"ok": 200, "duplicate": 409, "refused": 401},
        ),
        Operation(
            name="account_lookup",
            # Double the payment door: a machine looks an account up before
            # every payment and again when a customer mistypes, so the read
            # ceiling has to sit above the write one or normal use hits it.
            rate_limit_per_minute=120,
            label="Account lookup",
            description="They ask what is owed on an account before taking money.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="authenticate",
            # ⚠ `not_found` IS **200**, NOT 404 — `DEF-INT-4257`, corrected
            # 2026-09-06. This read `404` from wave A until the wave-N lane put
            # it beside `US-INT-044` TC-7, which says in as many words: *"for an
            # unknown account, the declared answer (`200` with `status:
            # not_found` — the kiosk's contract), **not** a 404"*. The kiosk
            # network reads the OUTCOME WORD out of the body and treats a 404 as
            # *the endpoint is gone*, which is a different failure and a
            # different retry. 404 is the obvious answer, which is exactly why
            # the story warns against it and why nothing mechanical could catch
            # it: the registry checks that a status IS an HTTP status and can
            # never know which one is right.
            envelope_status={"ok": 200, "refused": 401, "not_found": 200},
        ),
        Operation(
            name="returns",
            # Sixty, matching the payments door it reverses. ⚠ Its composite
            # duplicate key STAYS: *have I already been handed this exact
            # event* is a fact about the door, not the money-duplicate
            # judgment the PO moved to Runbooks on 2026-09-16.
            rate_limit_per_minute=60,
            label="Returns",
            description="They send us a return when a payment bounces.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(
                mode="refuse",
                source="provider_event_id",
                natural_key="event_id+reversal",
                key_field="eventId",
            ),
            completion="immediate",
            codec="json",
            respond_after="dedupe",
            envelope_status={"ok": 200, "duplicate": 409, "refused": 401},
        ),
    ),
)

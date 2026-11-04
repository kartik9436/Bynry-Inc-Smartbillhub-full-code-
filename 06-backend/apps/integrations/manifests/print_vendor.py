"""Print vendor — hand the printed batch to a mailing house (Print · LIVE per BR-INT-017).

PO IN-1, 2026-08-08: the print-vendor connection is v1-REAL and completes the
print/PDF delivery channel. The vendor's own format is still theirs to state,
so the hand-over is declared `submit_poll_collect` (BR-INT-046) with a PDF
codec and NO safe test: a mailing house has no zero-page job to accept, so the
card reads *cannot be tested until first use* (BR-INT-019).

⚠ **THE POLL SCHEDULE AND `result_delivery` BELOW ARE STATED-PROVISIONAL, AND
THEY WERE MISSING ALTOGETHER UNTIL 2026-09-06 (`DEF-INT-4244`).** This operation
has said *they build it while we wait* since `2.131.0` and said nothing about
how often to ask or what the answer would be — so the run would have submitted
and then waited forever. Nothing could see it, because no runner implemented
`submit_poll_collect` until wave K; wave K's new load-time refusal
(`US-INT-031` TC-5) found it the first time all eighteen manifests were
validated together.

**Sixty seconds, up to sixty times — one hour — and a `handle`.** These are OUR
numbers, not the mailing house's, and they sit under exactly the sentence above
that already says the vendor's own format is theirs to state: when their
document is read, the schedule is read off it and changed HERE, as data, with
no code touched. One hour is the honest shape of a print run (a batch of bills
is minutes to tens of minutes to compose, never seconds), and a print job's
receipt is a job reference rather than a URL, which is what `handle` means.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.print_vendor.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
    Poll,
)

MANIFEST = Manifest(
    key="print_vendor",
    category="print",
    display_name="Print vendor",
    summary="Hand the printed batch to a mailing house.",
    #: ⚠ COMING SOON, AND THE MAILING HOUSE IS DELIBERATELY UNNAMED. PO ruling
    #: 2026-09-16, verbatim: *"keep it as it is right now - we will replace
    #: them - theya re dummay right now we will replace them later"*. The card
    #: was LIVE with no adapter bound and `test_action=None`, so it was a card
    #: a utility could press that could not work — the blueprint files exactly
    #: that as a defect on p146, and it is hard-won law 2's mirror: a live
    #: screen behind a dead control. Now the CARD says so and the server
    #: refuses the connect (`BR-INT-001`).
    #: ⚠ THE HOLD CARRIES A TEST THAT FIRES WHEN IT EXPIRES:
    #: `test_cr110_connectors.py` asserts this is coming-soon FOR AS LONG AS
    #: its display name is the category placeholder, so the day a mailing
    #: house is named the suite goes red and names this file.
    disposition=Disposition(kind="coming_soon", wave="v1.1", phase=4),
    auth=Auth(mode="we_hold_theirs", placement="header"),
    fields=(
        #: The PO's phase-1 dummy API — a placeholder address seeded as data
        #: so the hand-over has a host that resolves today (`DEF-INT-5488`).
        #: `required=False` while the vendor is unnamed: there is no real
        #: address for a clerk to be asked for yet.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://api.print-vendor.example",
        ),
        Field(name="api_key", label="API key", kind="secret"),
        Field(name="account_reference", label="Your account with them", kind="text"),
    ),
    operations=(
        Operation(
            name="hand_over_batch",
            # 120 a minute. A print hand-over is one call per batch and the
            # batch is the whole cycle, so this is a retry ceiling rather than
            # a pace. ⚠ The Poll schedule below is a DIFFERENT concept and is
            # untouched: it is how often we re-ask about a job we already
            # submitted, not when to start one, so the PO's scheduling ruling
            # of 2026-09-16 does not reach it.
            rate_limit_per_minute=120,
            label="Print hand-over",
            description="We hand them the finished print set and wait for the receipt.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="dispatcher",
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="submit_poll_collect",
            # DEF-INT-4244 — declared with the completion mode or the registry
            # refuses the manifest at load. Provisional; see the docstring.
            poll=Poll(every_seconds=60, max_attempts=60),
            result_delivery="handle",
            codec="pdf",
            test_action=None,
        ),
    ),
)

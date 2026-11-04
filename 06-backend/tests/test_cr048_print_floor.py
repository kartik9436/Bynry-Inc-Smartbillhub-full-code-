# ── Trace ──────────────────────────────────────────────
# Story:    CR-048 wave A · BR-NOT-024
# Rules:    BR-NOT-024 (print is the floor on every customer document and cannot
#           be switched off) · BR-BIL-036 (the original bills-only floor, now the
#           narrowest case) · BR-NOT-010 (the three v1 channels)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""BR-NOT-024 — a utility can silence every channel it was offered, and the
paper copy still goes.

⚠ **THE CASE THAT MATTERS IS `notice`, AND IT WAS LIVE.**
`CHANNEL_FLOOR_BY_SOURCE` carried one entry — `invoice` — on reasoning that was
correct about the signed documents and wrong about the product: it left a utility
able to switch off the `notice` kind, **which carries the disconnection letter**.
A setting about reminders could suppress a document the law makes a precondition
of cutting somebody's water off, and nothing on screen would have said so.

PO ruling 2026-08-29, verbatim: *"this is correct - don't switch of print for any
document it is awayls on"*.

**Every test here switches things off and asserts paper survives**, because that
is the only shape that can prove a floor. A test that switches a channel ON and
sees print proves nothing at all.
"""

from __future__ import annotations

import pytest

from apps.notifications import models, services

pytestmark = pytest.mark.django_db

#: The four kinds a customer receives. Named here rather than imported from the
#: table under test — a test that reads its own answer out of the code it is
#: checking asserts that the code equals itself.
CUSTOMER_DOCUMENT_KINDS = ("invoice", "payment", "notice", "plan", "account", "move")
#: ⚠ **WIDENED FROM FOUR TO SIX ON 2026-08-30, AND THE FOUR LASTED ONE DAY.**
#: The merge lane put it back to the PO that the four-kind rule was NARROWER
#: THAN WHAT THEY HAD SAID — *"don't switch of print for any document it is
#: awayls on"* — and the PO confirmed: *"Im okay with your suggestions, you are
#: correct"*. `account` was the case that decided it: a DEPOSIT-RECEIVED
#: confirmation acknowledges money received, which is what a receipt is, and no
#: reading of the ruling made that not a document. `move` follows under the same
#: principle rather than being left on the superseded reasoning — the kind holds
#: a letter announcing a customer's FINAL BILL.

#: The four with no envelope to go in. NOT "print switched off" — no postal
#: surface exists for a bell notification or a send-test rehearsal.
#: `staff_access` joined 2026-10-22 (`CR-188-BRC10`): a sign-in link to a
#: member of staff — this product holds no postal address for staff.
NO_POSTAL_SURFACE_KINDS = ("report", "ledger", "test", "bulk_action", "staff_access")

#: ⚠ **THIS BUCKET IS NOW EMPTY, AND EMPTYING IT IS THE POINT OF HAVING HAD IT.**
#: It held `move` and then `account` — the kinds whose "no floor" was a JUDGMENT
#: rather than a physical fact, parked here precisely so the only classification
#: anyone could reasonably argue with stayed VISIBLE instead of disappearing into
#: a list. Somebody did argue with it, the PO ruled on 2026-08-30, and both moved
#: to `CUSTOMER_DOCUMENT_KINDS`.
#:
#: **It is kept rather than deleted because the next arguable kind needs
#: somewhere to sit.** A source kind whose floor is a judgment goes HERE, with
#: its reasoning written out, and stays here until somebody rules — which is
#: what happened to both of these, in a day.
#:
#: ⚠ **AND IT DID NOT STAY EMPTY. IT REFILLED TWICE AND THE FIRST ONE SAT HERE
#: UNNOTICED FOR A DAY WITH THIS TEST RED (`DEF-NOT-4032`).** `portal` was added
#: to `SOURCE_TYPES` on 2026-09-04 by `CR-068` wave E and classified nowhere, so
#: the guard directly below — whose entire job is to fail when exactly that
#: happens — **has been failing since**, naming `portal`, and the wave that
#: added it did not run it. The test worked perfectly; nobody read it.
#:
#:   * **`portal`** — a one-time enrolment code or a password-reset link. Its
#:     own comment in `models.SOURCE_TYPES` already argues the classification
#:     and is worth quoting because it is the sharpest version of it: *"a code
#:     is not a document, there is no envelope for it, and it is worthless
#:     within ten minutes."* Posting a six-digit login code arrives four days
#:     after it expired.
#:   * **`appointment`** (2026-09-05, `CR-070` wave I, `OQ-WRK-1495`) — *your
#:     visit has moved to 12:00–17:00*. Same shape, different clock: a POSTED
#:     appointment change arrives after the visit it was warning about, so a
#:     print floor here would spend a stamp to be wrong. It is nonetheless a
#:     JUDGMENT and not a physical fact — a utility could reasonably want the
#:     letter — which is precisely why it sits in this bucket rather than in
#:     `NO_POSTAL_SURFACE_KINDS`, where it would look settled.
#:
#: Neither is in `CHANNEL_FLOOR_BY_SOURCE`. If a utility asks for a floor on
#: either, that is a rule question for the PO and an amendment to `BR-NOT-024`
#: — never an edit to this tuple. The `move` precedent is the whole procedure:
#: a lane refused to widen a signed rule by editing a dictionary, put it to the
#: PO, and was told *"Im okay with your suggestions, you are correct"*.
#: ⚠ `message` joined 2026-09-12 (`CR-094-BRC01` wave K). A clerk's own
#: courtesy note to a customer is not a document: it freezes no copy, and
#: filing it under `account` — the nearest existing kind — would have put every
#: quick email in an envelope as well, because `account` carries the floor.
#: ⚠ `service_request` joined 2026-09-15 (`CR-094-BRC01`, `DEF-CUS-5389`) and
#: it is the one kind here whose "no floor" rests on a PHYSICAL fact first: this
#: product captures no mailing address for an APPLICANT. A request holds the
#: address of the property that wants service, never an address for the person
#: asking — and the commonest drawn refusal reason is *Not our service area*, so
#: a print floor would post a refusal to a street the utility has just said it
#: does not serve. It sits in THIS bucket and not in `NO_POSTAL_SURFACE_KINDS`
#: because the physical fact could change: give an applicant a mailing address
#: and a posted refusal becomes reasonable, which is a `BR-NOT-024` amendment
#: for the PO rather than an edit to a tuple.
#: ⚠ `transfer` joined 2026-09-20 (`DEF-CUS-5949`). A change-of-ownership note
#: is a courtesy about a job, not a document: nothing is frozen, no copy is
#: kept, and the FACT it announces — who holds the account from today — is
#: already on the account and on the transfer record. `BR-NOT-024` names SIX
#: kinds and a transfer is none of them, so no floor is invented here. It sits
#: in THIS bucket rather than in `NO_POSTAL_SURFACE_KINDS` because the postal
#: surface plainly exists — `premises` holds the address the sale is ABOUT —
#: so a utility could reasonably ask for a posted letter. **That would be a
#: `BR-NOT-024` amendment for the PO and never an edit to this tuple**, which
#: is the `move` procedure written two paragraphs up.
#: ⚠ `connection` joined 2026-10-02 (`CR-163-BRC10`, the ruled `OQ-NOT-12521`
#: kind). Its three occasions already carry their own channels — the contract
#: goes on PAPER and the quote by email AND paper, as p091 draws them — so the
#: clerk's choice per send decides, and a floor on the whole KIND would post a
#: *build confirmed* courtesy email too. That is a `BR-NOT-024` amendment for
#: the PO, never an edit to this tuple — the `move` procedure.
NOT_A_DOCUMENT_KINDS: tuple[str, ...] = (
    "portal",
    "appointment",
    "message",
    "service_request",
    "transfer",
    "connection",
    # CR-168-BRC10 §F (FIELD-2): the office told about a field close, photos
    # complete or Needs review — in-app to staff, never a document.
    "field_work",
    # CR-182-BRC10 (PO A4): a reading flagged high — an email about a meter
    # reading, not a document; a posted copy would arrive after the bill.
    "usage_alert",
    # CR-190-BRC10 (PO 2026-10-22, answer 1): an agreement goes by EMAIL with
    # the PDF attached, "plus a letter if the customer wants paper" — the
    # customer's `paperless` choice decides the letter, so a floor would post
    # one to a customer who said no. The `connection` reasoning above.
    "agreement",
    # DEF-NOT-10649 (PO 2026-10-29, "1 A, 2 A, 3 A, 4 A"): the post-cut and
    # restored messages go by email and SMS (2A) and a utility may switch them
    # off (3A) — a print floor would break both.
    "service_state",
    # DEF-PAY-10651 (PO 2026-10-29, "1A 2A"): the friendly past-due reminder.
    # The rule's on/off decides it (1A) and paper goes ONLY to a customer no
    # email or consented text can reach (2A) — `past_due_reminder` adds the
    # letter itself. A floor would post every reminder and survive "off".
    # The disconnection notices stay on `notice`, floored.
    "reminder",
)


@pytest.mark.parametrize("source_type", CUSTOMER_DOCUMENT_KINDS)
def test_br_not_024__print_survives_a_caller_asking_for_no_channel_at_all(source_type):
    """The floor is a floor: ask for nothing, get paper.

    This is the master-switch case in its simplest form — a rule that switched
    every channel off leaves the caller asking for none.
    """
    assert models.CHANNEL_PRINT in services.channels_for(source_type, ())


@pytest.mark.parametrize("source_type", CUSTOMER_DOCUMENT_KINDS)
def test_br_not_024__print_survives_a_caller_asking_for_email_only(source_type):
    """A caller naming only electronic channels does not remove paper."""
    channels = services.channels_for(source_type, ("email",))
    assert models.CHANNEL_PRINT in channels
    assert "email" in channels, "the floor ADDS paper, it does not replace the ask"


def test_br_not_024__the_disconnection_letter_is_the_case_this_rule_exists_for():
    """⛔ Named on its own, because a parametrised pass is easy to skim past.

    `notice` carries the disconnection letter. Before BR-NOT-024 this kind had no
    floor, so a utility switching the event off stopped a legally required
    document. This is the regression that must never come back.
    """
    assert models.CHANNEL_PRINT in services.channels_for("notice", ()), (
        "a utility silencing the disconnection notice must still post the letter "
        "— it is the legal instrument, not a courtesy (BR-NOT-024)"
    )


def test_br_not_024__every_customer_document_kind_has_a_floor_and_none_is_missed():
    """The set, not the members — so a NINTH source kind added tomorrow fails
    here rather than shipping without a floor nobody noticed was missing.

    ⚠ This is the check the original table did not have. Its floor was correct
    for the one kind it named and silent about the seven it did not.
    """
    floored = {kind for kind, ch in services.CHANNEL_FLOOR_BY_SOURCE.items() if ch}
    assert floored == set(CUSTOMER_DOCUMENT_KINDS), (
        "a customer document kind with no print floor can be switched off "
        "entirely (BR-NOT-024); a new SOURCE_TYPE must be classified deliberately"
    )


def test_br_not_024__the_staff_and_internal_kinds_have_no_postal_surface():
    """NOT the same statement as "print is off" for them, and the distinction is
    the reason this test exists rather than being folded into the one above.

    A bell notification for the clerk who ran a bill run has no envelope. A
    send-test row is a rehearsal addressed to the signed-in user; posting it
    would spend a stamp to prove nothing.
    """
    for kind in NO_POSTAL_SURFACE_KINDS:
        assert models.CHANNEL_PRINT not in services.channels_for(kind, ()), (
            f"{kind} has no postal surface — giving it a floor would post a "
            "staff alert"
        )
    for kind in NOT_A_DOCUMENT_KINDS:
        assert models.CHANNEL_PRINT not in services.channels_for(kind, ()), (
            f"{kind} is not a document (see NOT_A_DOCUMENT_KINDS above) — its "
            "floor is a rule question, and until BR-NOT-024 names it there is none"
        )


def test_br_not_024__every_source_type_is_classified_one_way_or_the_other():
    """No kind may be forgotten. `SOURCE_TYPES` is the vocabulary; this asserts
    the two lists above partition it exactly.

    ⚠ **THE POINT IS THE FAILURE MESSAGE.** A ninth source kind added without a
    decision fails here naming itself, so the choice is made deliberately rather
    than defaulting to "no floor" — which is how `notice` came to be unprotected.
    """
    classified = (
        set(CUSTOMER_DOCUMENT_KINDS) | set(NO_POSTAL_SURFACE_KINDS) | set(NOT_A_DOCUMENT_KINDS)
    )
    unclassified = set(models.SOURCE_TYPES) - classified
    assert not unclassified, (
        f"{sorted(unclassified)} is neither a customer document, nor a kind with "
        "no postal surface, nor a non-document. Decide which, in "
        "CHANNEL_FLOOR_BY_SOURCE and here — "
        "defaulting to no floor is exactly how the disconnection letter came to "
        "be switch-off-able (BR-NOT-024)"
    )
    buckets = (CUSTOMER_DOCUMENT_KINDS, NO_POSTAL_SURFACE_KINDS, NOT_A_DOCUMENT_KINDS)
    named = [kind for bucket in buckets for kind in bucket]
    assert len(named) == len(set(named)), "a source kind is in exactly one bucket"

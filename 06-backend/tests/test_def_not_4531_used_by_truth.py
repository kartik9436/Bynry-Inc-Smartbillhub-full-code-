# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-4531 — the template catalogue's `used_by` column said
#           "Not in use yet — no wording has been written for it." about
#           `email_bill_ready`, on a screen that was displaying the wording
#           underneath it and beside a live notification rule with that class
#           selected and switched ON. Product Owner, verbatim, 2026-09-07:
#           *"in templates why are you saying this tempalte not in use -
#           Email · Not in use yet — no wording has been written for it. ·
#           last edited 2026-09-03 · author not recorded"*.
# Rules:    B14 rule 32 (a screen has a description budget) · B14 rule 33 (a
#           refusal caps at five or six words) · hard-won law 2's mirror
#           (*"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD
#           EXPIRES"*) · hard-won law 1 (a comment claiming a guarantee is not
#           the guarantee — and neither is a sentence claiming an absence)
# Tests:    this file IS the guard.
# Impacts:  apps/notifications/catalogs.py (`has_wording`, `firing_events`,
#           `used_by_state` — the two facts, derived) · templates_api.py (serves
#           `used_by_state`) · 07-frontend/.../TemplateCatalog.tsx (reads it
#           instead of regexing the prose)
# ───────────────────────────────────────────────────────
"""THE `used_by` SENTENCE MAY NOT CONTRADICT THE CATALOGUE IT LIVES IN.

╔══════════════════════════════════════════════════════════════════════════╗
║  23 OF 38 SENTENCES WERE FALSE, AND EVERY ONE WAS TRUE WHEN TYPED.       ║
╚══════════════════════════════════════════════════════════════════════════╝

`used_by` is customer-facing copy (CR-016) rendered VERBATIM in the *Used by*
column of Settings → Configure → Templates and on the template's own page. It
is hand-written, and two of the things it says are facts this codebase already
knows exactly:

  * *"no wording has been written for it"* — `seed_templates` knows.
  * *"Not in use yet"* — `rule_catalog.EVENTS` knows, and an event's
    `trigger_blocked_by` says whether the writer exists today.

Fifteen rows claimed the first while carrying wording; eight more claimed the
second while a live writer fires them. **Nothing could catch it**: the sentence
is a string literal, `tsc` and every test passed over it, the API served it
faithfully and the screen printed it exactly as written.

DERIVE THE STATE; KEEP THE SPECIFICITY — AND THAT IS A PO RULING, NOT A CHOICE
-----------------------------------------------------------------------------
PO, 2026-09-07: *"it should be dynamic and based on actual usage by
notifications - can you fix it"*. The lane was given two options — derive the
sentence, or leave the literal and add a drift test — and **the Product Owner
chose derive; a drift test is no longer acceptable as the substitute.** Their
reasoning is the stronger one: a check tells the next engineer the string is
wrong, while derivation means the string cannot be wrong.

So the STATE is derived (`catalogs.used_by_state`, served on the wire and drawn
as the status beside each row) and the SENTENCE is kept, because the ruling is
equally explicit that the honest-absence half must not be flattened into a
boolean: *"closing an account does not send this"* names WHAT does not happen,
which is worth more than *unused*. This file is what keeps the kept half honest
— it is the belt beside the braces, not the fix.

"ACTUAL USAGE" IS FOUR FACTS, AND ONE OF THEM IS A TRAP
------------------------------------------------------
(1) does a rule reference this template · (2) is that rule's channel switched on
· (3) has wording been authored · (4) has anything ever been sent. **Fact 4 is
never asked**, and `test_never_sent_is_not_read_as_not_in_use` is what stops a
later lane adding it: nothing reports sends back on this deployment, so silence
would render as absence and ship the same lie in a new coat.

⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN, AND THROUGH pytest — THE HARNESS
THAT WILL ACTUALLY RUN IT** (hard-won law 7, and its 2026-09-04 clause: a guard
shown red only through `python3 <file>` has been announced green while the real
runner crashed on it). The four proofs are in this file's own trailer.
"""

from __future__ import annotations

import re

from apps.notifications import catalogs

#: The two claims a `used_by` sentence is allowed to make about machine-knowable
#: facts, as the patterns the seeder actually writes. Matched on the SENTENCE
#: because that is what a person reads — a status word derived beside it would
#: be checking the derivation against itself.
CLAIMS_NO_WORDING = re.compile(r"no wording has been written", re.IGNORECASE)
CLAIMS_NOT_IN_USE = re.compile(r"^\s*not in use yet\b", re.IGNORECASE)


def test_no_sentence_claims_missing_wording_over_wording_that_exists() -> None:
    """The PO's own row: a class with a body may not say it has none.

    This is the assertion `email_bill_ready` needed and nobody had written. It
    fires the moment a wave authors a body and leaves the sentence behind.
    """
    liars = [
        code
        for code, listing in catalogs.LISTINGS.items()
        if CLAIMS_NO_WORDING.search(listing.used_by) and catalogs.has_wording(code)
    ]
    assert liars == [], (
        "these template classes say no wording has been written for them and a body "
        f"exists for every one: {', '.join(sorted(liars))}. Either the sentence is "
        "stale (author it in `catalogs.LISTINGS`) or the body should not be there."
    )


def test_no_sentence_says_not_in_use_while_a_live_writer_fires_it() -> None:
    """The other half of the PO's row: the rule beside it was switched ON."""
    liars = {
        code: catalogs.firing_events(code)
        for code, listing in catalogs.LISTINGS.items()
        if CLAIMS_NOT_IN_USE.match(listing.used_by) and catalogs.firing_events(code)
    }
    assert liars == {}, (
        "these template classes say they are not in use yet and a live writer sends "
        f"each of them: {liars}. The sentence is what must change — an event with a "
        "trigger is a writer that exists today."
    )


def test_a_class_with_a_live_writer_is_reported_in_use() -> None:
    """The derivation and the sentence agree in the other direction too.

    Without this the pair above could be satisfied by a sentence that says
    nothing at all, which is the shape a check passes wrongly on (law 7's second
    habit — *ask what would make this check pass wrongly*).
    """
    for code in catalogs.LISTINGS:
        if catalogs.firing_events(code) and catalogs.has_wording(code):
            assert catalogs.used_by_state(code) in (
                catalogs.USED_BY_IN_USE,
                catalogs.USED_BY_PLACEHOLDER,
            ), f"{code} has wording and a live writer and is not reported in use"


def test_the_derivation_covers_every_listing_and_names_its_state() -> None:
    """A declared blind spot with no NUMBER attached looks like an empty one.

    Law 7's *reporting zero over a scope it silently excludes*: the two guards
    above are only worth their green if they ran over the whole catalogue, so
    the size of the subject is asserted rather than assumed.
    """
    states = {code: catalogs.used_by_state(code) for code in catalogs.LISTINGS}
    assert len(states) == len(catalogs.LISTINGS)
    assert set(states.values()) <= set(catalogs.USED_BY_STATES)
    # Every listable class is covered by the state derivation, and the catalogue
    # is not empty — a guard over nothing passes for the wrong reason.
    assert len(catalogs.LISTINGS) >= 30


def test_the_two_facts_are_read_from_the_catalogues_and_not_from_the_prose() -> None:
    """`has_wording` and `firing_events` must not consult `used_by` at all.

    If they did, this whole file would be the sentence checking itself — which
    is the *test asserting the test* shape `NotificationRules.tsx` records from
    the `pdf_print` spelling bug.
    """
    # A class whose sentence says nothing about wording still reports wording.
    assert catalogs.has_wording("receipt") is True
    assert "wording" not in catalogs.LISTINGS["receipt"].used_by.lower()
    # And a class the seeder deliberately leaves blank reports none, although
    # its sentence never uses the words this file greps for.
    assert catalogs.has_wording("payment_failed_letter") is False
    assert not CLAIMS_NO_WORDING.search(catalogs.LISTINGS["payment_failed_letter"].used_by)


def test_no_sentence_carries_a_rule_id_or_an_internal_code() -> None:
    """B14 rule 32 — no rule id or internal code in clerk-facing copy.

    G28 already guards this field; asserted here as well because the 23 rewrites
    of DEF-NOT-4531 are new copy and a gate that runs elsewhere is not a reason
    to ship copy nobody checked.
    """
    banned = re.compile(r"\b(?:BR|OQ|DEF|CR|US|GT|EP)-[A-Z]{0,3}-?\d+\b|apps\.[a-z_]+")
    offenders = {
        code: listing.used_by
        for code, listing in catalogs.LISTINGS.items()
        if banned.search(listing.used_by)
    }
    assert offenders == {}, offenders


# ══════════════════════════════════════════════════════════════════════════
# THE PO's RULING OF 2026-09-07 — DERIVE THE STATE, KEEP THE SPECIFICITY
# ══════════════════════════════════════════════════════════════════════════
# *"it should be dynamic and based on actual usage by notifications - can you
# fix it"*. The decision row of that day names four facts, and these are the
# three of them a test can pin without a database.


def test_the_state_follows_this_tenants_own_switch_and_not_only_the_catalogue() -> None:
    """Fact 2 — *is that rule's CHANNEL switched on* — and it WINS where it has
    an answer, because it is the only one of the four that is a property of the
    utility rather than of the platform."""
    live = "email_bill_ready"
    assert catalogs.used_by_state(live) == catalogs.USED_BY_IN_USE
    assert catalogs.used_by_state(live, rule_usage={live: False}) == catalogs.USED_BY_NOT_IN_USE
    assert catalogs.used_by_state(live, rule_usage={live: True}) == catalogs.USED_BY_IN_USE
    # A code the tenant's map does not mention falls back to the PLATFORM
    # answer — which is what a utility who has never opened the screen must
    # see, since they have no rule rows at all.
    assert catalogs.used_by_state(live, rule_usage={}) == catalogs.USED_BY_IN_USE


def test_a_class_with_no_wording_stays_no_wording_whatever_the_tenant_switched() -> None:
    """The order is the rule: a person opening the row has to write the wording
    before anything else about it matters."""
    blank = "payment_failed_letter"
    assert catalogs.has_wording(blank) is False
    for usage in ({}, {blank: True}, {blank: False}):
        assert catalogs.used_by_state(blank, rule_usage=usage) == catalogs.USED_BY_NO_WORDING


def test_the_derivation_prints_what_it_skipped_beside_what_it_checked() -> None:
    """*"A declared blind spot with no number attached is indistinguishable from
    an empty one"* — the PO's ruling, quoting this repository's own `G32`, which
    reported 0 unresolved over 21 refusals it could not see.

    Two paths are not looked at and both are real; this asserts they are STATED,
    in a clerk's words, and that neither carries a rule id (B14 rule 32).
    """
    assert len(catalogs.USED_BY_UNCHECKED) == 2
    banned = re.compile(r"\b(?:BR|OQ|DEF|CR|US|GT|EP)-[A-Z]{0,3}-?\d+\b|apps\.[a-z_]+")
    for sentence in catalogs.USED_BY_UNCHECKED:
        assert sentence.strip() != ""
        assert banned.search(sentence) is None, sentence
    # Fact 4 — *has anything ever been SENT* — is the trap the ruling names, so
    # the blind spot must SAY it rather than leave a reader to notice.
    assert any("sent" in sentence.lower() for sentence in catalogs.USED_BY_UNCHECKED)


def test_never_sent_is_not_read_as_not_in_use() -> None:
    """The ruling's sharpest clause, asserted as code.

    Nothing on this deployment reports a send back, so a derivation that asked
    *"has this ever gone out"* would report every template as unused. This pins
    that the derivation does not consult delivery at all: a class with wording
    and a live writer is IN USE with zero sent rows in the database, which is
    exactly the state every tenant is in today.
    """
    import inspect

    source = inspect.getsource(catalogs.used_by_state) + inspect.getsource(catalogs.firing_events)
    for forbidden in ("OutboundMessage", "STATUS_SENT", "sent_at", "delivered"):
        assert forbidden not in source, (
            f"the derivation consults {forbidden!r}. Nothing reports sends back on this "
            "product, so silence would render as absence — the same lie in a new coat."
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-4531 (12-governance/10-defect-log.csv · CR-084 §2 · apps/notifications/catalogs.py's `used_by` block comment · apps/notifications/seed_templates.py SEEDABLE/CONTRACT_DEFAULTS · apps/notifications/rule_catalog.py EVENTS)
# generated: 2026-09-07 by story-coder (notifications used-by truth lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest 06-backend/tests/test_def_not_4531_used_by_truth.py
#   RED PROVED FIRST, through pytest and not through `python3 <file>`:
#     1 · at HEAD before the 23 rewrites, `test_no_sentence_claims_missing_wording_over_wording_that_exists`
#         failed naming all fifteen classes, `email_bill_ready` among them — the PO's own row.
#     2 · at the same commit, `test_no_sentence_says_not_in_use_while_a_live_writer_fires_it`
#         failed naming twenty-two (event, channel) pairs.
#     3 · with `has_wording` stubbed to `False`, `test_a_class_with_a_live_writer_is_reported_in_use` failed.
#     4 · with a `BR-NOT-010` spliced into one sentence, the copy guard failed.
# exceptions: (1) THE SENTENCE IS STILL HAND-WRITTEN. Deriving it whole would delete the clerk-facing half (*"Sent when a payment comes back"*), which is the only part of the column a person acts on; what is derived is the two CLAIMS, and this file is what keeps them honest. (2) `CLAIMS_NOT_IN_USE` anchors at the start of the string, because a sentence may legitimately mention that something else is not in use — `sms_disconnect`'s does. (3) NO ASSERTION ON THE EXACT WORDS of any rewritten sentence: copy is the Product Owner's to change and a test pinning it would make every future edit a test edit.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the palette these bodies are validated against) ·
#           US-NOT-006 (the version rows they are published into)
#           Screens: SET-09 · SET-10 · S8
# Rules:    BR-NOT-001 (the `default` variant these bodies fill) ·
#           BR-NOT-006 (type × category × language) · BR-NOT-014 (the three
#           disconnect slots that stay EMPTY) · BR-NOT-015 (the rights footer
#           is a platform default whose SENTENCES must not be invented) ·
#           BR-PAY-016 (the plan-void notice has nothing left to announce) ·
#           CLAUDE.md rule 3 (a consumption figure never renders without its
#           unit) · rule 7 (audited)
# Tests:    this file — DEF-210's durable guard
# Impacts:  apps/notifications/seed_templates.py (the bodies) ·
#           apps/notifications/catalogs.py (the palettes) ·
#           apps/notifications/rendering.py (`{utility_website}`)
# ───────────────────────────────────────────────────────
"""DEF-210 — **the twenty-six authored bodies, and the eight that are not.**

**THE DEFECT, VERBATIM:** *"34 of 36 template classes have no variant, no body
and no merge-field list, so the email subject line and the SMS character counter
never render at all."* The PO's answer, verbatim: **"please define it for this
product"** (2026-08-17, CR-007).

╔══════════════════════════════════════════════════════════════════════════╗
║  EVERY ASSERTION HERE IS TABLE-DRIVEN OVER THE CATALOGUE.                ║
║  ADD A CLASS OR A BODY AND IT IS COVERED WITHOUT EDITING THIS FILE.      ║
╚══════════════════════════════════════════════════════════════════════════╝

That is deliberate and it is DEF-210's own recommendation — *"DURABLE GUARD: a
test asserting every channel in the catalog has at least one renderable class —
the count is fixed platform vocabulary, so the assertion cannot drift."* A guard
written as a list of twenty-six literal codes would pass forever on the day a
twenty-seventh was added and never checked.

**FIVE THINGS ARE PROVED, and each one is a constraint the PO stated:**

1. every authored body — and every authored SUBJECT — passes
   `rendering.validate_body` for its own class, which is the same gate a human's
   save goes through;
2. **no body anywhere names `{utility_logo}`** (DEF-195: the render context
   supplies no value, so it prints `——` on a customer's letter);
3. **every SMS body is under 160 characters**, MEASURED — the counter CR-007
   asks for exists to be obeyed;
4. **no body states a figure, fee, deadline or regulator reference that is not
   ruled** — the eight sample values prototype r10 draws are named and asserted
   absent, one by one;
5. **every channel has at least one renderable class**, which is the assertion
   DEF-210 asked for: without it the email subject line and the SMS counter can
   silently go back to never rendering for anyone.

WHAT THIS FILE CANNOT PROVE, SAID PLAINLY RATHER THAN IMPLIED
-------------------------------------------------------------
⚠ **It cannot prove the subject FIELD and the character COUNTER appear on the
screen**, because no gate in this repo reads rendered output (B14's own status
table says so). What it proves is the SERVER-SIDE PRECONDITION both of those
surfaces are gated on: a published variant whose `channel` is `email` (with a
non-null `subject`) and one whose `channel` is `sms`. Before this work there was
neither, on any tenant, which is exactly why neither surface had ever rendered.
The remaining step is a browser check, and it is named in the lane report as
NOT DONE rather than dressed up as proof.
"""

from __future__ import annotations

import pytest

from apps.notifications import catalogs, rendering
from apps.notifications import seed_templates as seed
from apps.notifications import template_models as tm

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_def_163_notice_templates_seeded import provisioned_tenant

pytestmark = pytest.mark.django_db

#: Every seeded class, as `(code, SeedBody)` — the table the whole file drives
#: off. `pytest.param` ids make a failure name the CLASS, so a red run says
#: *"email_deposit"* rather than *"case 14"*.
SEEDED = [pytest.param(entry, id=entry.code) for entry in seed.SEEDABLE]


# ══════════════════════════════════════════════════════════════════════════
# 1 · EVERY BODY PASSES THE GATE A HUMAN'S SAVE WOULD
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("entry", SEEDED)
def test_def_210__every_seeded_body_passes_its_own_class_palette(entry):
    """US-NOT-005 TC-5's gate, applied to the platform's own words.

    A seeded body that could not be re-saved through the ordinary designer door
    would be a special case living inside a customer-facing document — so the
    same `validate_body` runs here, over the body AND the subject. An email
    subject is merged text on the same palette, and `{meter_no}` in a subject
    line reaches the customer's inbox exactly as surely as one in a body reaches
    the page.
    """
    rendering.validate_body(entry.code, entry.body, subject=entry.subject)


@pytest.mark.parametrize("entry", SEEDED)
def test_def_210__every_seeded_class_has_a_catalogue_and_a_listing(entry):
    """A body with no palette is a body nothing checks; a body with no SET-09
    listing is a document a utility cannot find to edit."""
    klass = catalogs.catalog_for(entry.code)
    assert klass is not None, f"{entry.code} is seeded with no merge-variable catalogue"
    assert entry.code not in catalogs.CLASSES_WITHOUT_CATALOG, (
        f"{entry.code} is BOTH catalogued and registered as uncatalogued. "
        "`templates_api` reads that dictionary to print a refusal on SET-10, so a stale "
        "entry shows a utility 'no merge-variable catalogue exists' beside a palette they "
        "can click."
    )
    listing = catalogs.listing_for(entry.code)
    assert listing is not None, f"{entry.code} is seeded and SET-09 does not list it"
    # One class, one name. The seeder's label and the catalog's must agree or a
    # utility sees the template called two things in two places.
    assert entry.name == listing.name or entry.code in ("dunning", "receipt"), entry.code


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE LOGO TRAP — DEF-195
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("entry", SEEDED)
def test_def_210__no_seeded_body_uses_the_utility_logo_token(entry):
    """⚠ DEF-195, made structural.

    `{utility_logo}` is offered by every A19 printable palette and
    `rendering.render` supplies NO value for it, so a body using it prints the
    named absence `——` in the logo's position on a customer's letter. The PO's
    authoring constraint is explicit: *"no authored body may reference it"*.

    Two assertions, because they fail for different reasons and a reader needs
    to know which: the TEXT never mentions it, and no authored class even OFFERS
    it in its palette (a token a designer can click is a trap whether or not the
    default body uses it).
    """
    text = entry.body + (entry.subject or "")
    assert "utility_logo" not in text, (
        f"{entry.code} references {{utility_logo}}. The render context supplies no value, "
        "so this prints '——' where the logo belongs on a real customer's letter (DEF-195)."
    )
    if entry.code in catalogs.AUTHORED_CATALOGS:
        assert "utility_logo" not in catalogs.AUTHORED_CATALOGS[entry.code].tokens


def test_def_210__no_authored_palette_offers_the_logo_token_at_all():
    """The palette is what a designer clicks. Offering a field the renderer
    cannot fill is worse than omitting it — CR-007's own words."""
    offenders = sorted(
        code for code, klass in catalogs.AUTHORED_CATALOGS.items() if "utility_logo" in klass.tokens
    )
    assert offenders == []


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE 160-CHARACTER SMS LIMIT — MEASURED, NOT ESTIMATED
# ══════════════════════════════════════════════════════════════════════════
SMS_LIMIT = 160


@pytest.mark.parametrize("entry", SEEDED)
def test_def_210__every_sms_body_is_under_160_characters(entry):
    """CR-007's counter exists to be obeyed, not just displayed.

    ⚠ WHAT IS MEASURED IS THE TEMPLATE TEXT, and that is stated rather than
    left to be assumed: the counter on the designer counts what the author
    typed, which is what this asserts. A RENDERED message can be longer or
    shorter — `{utility_name}` is four tokens' worth of characters and one
    tenant's name — and no rule in this repo states a rendered-length limit, so
    none is invented here. The headroom is the reason the authored bodies sit
    around 100–130 characters rather than at 159.
    """
    klass = catalogs.catalog_for(entry.code)
    if klass.channel != "sms":
        pytest.skip(f"{entry.code} is {klass.channel}, not SMS")
    assert len(entry.body) < SMS_LIMIT, (
        f"{entry.code} is {len(entry.body)} characters of template text and the limit is "
        f"{SMS_LIMIT}."
    )
    assert entry.subject is None, "an SMS has no subject line"


# ══════════════════════════════════════════════════════════════════════════
# 4 · NOTHING STATES A FIGURE, A FEE, A DEADLINE OR A REGULATOR RULE
# ══════════════════════════════════════════════════════════════════════════
#: The sample values prototype r10 draws for its fictional utility, each with
#: the reason it may not be copied. r10 is the design handover and its STRUCTURE
#: and TONE were followed; these are its DATA.
#:
#: ⚠ THE POINT OF THIS TABLE IS THAT IT IS SPECIFIC. A generic "no digits in a
#: body" rule would fail on `{installment_no} of {installments_total}` and pass
#: on "a $25 fee applies", which is precisely backwards.
UNRULED_PHRASES: dict[str, str] = {
    "$25": "r10's NSF fee. An NSF fee is a tenant CHARGE CODE and no rule sets a figure.",
    "$60": "r10's reconnect fee. BR-CUS-039: it renders a tenant charge code, never a constant.",
    "$50": "r10's deposit amount — sample data for a fictional customer.",
    "5 days": "r10's payment-retry window. No rule states one.",
    "12 months": "r10's deposit-refund period. No rule states one.",
    "14 days": "r10's move-out refund window. No rule states one.",
    "3-5 business days": "r10's refund settlement time. It is the card issuer's, not ours.",
    "3–5 business days": "r10's refund settlement time, with an en dash.",
    "60 days": "r10's rate-change notice period. No rule states one.",
    "25.29": "r10's PUC rule reference. `{state_puc_ref}` is a per-tenant VALUE.",
    "TCEQ": "r10's regulator. Regulator-mandated wording this platform does not hold.",
    "PUC rule": "a named regulator rule. Only `{state_puc_ref}` may point at one.",
    "collection agency": "r10's write-off line. A legal consequence nobody has ruled.",
    "plan cancels": "r10's payment-plan clause, SUPERSEDED by the PO 2026-08-11 (*'nodrop'*).",
    "Silver Creek": "r10's fictional utility name.",
    "Jordan": "r10's fictional customer name.",
}


@pytest.mark.parametrize("entry", SEEDED)
def test_def_210__no_seeded_body_states_an_unruled_figure_or_rule(entry):
    """*"A body that invents a notice period is a compliance defect wearing a
    copy deck"* — the PO's constraint, made checkable.

    Every phrase below is one this lane could plausibly have copied out of the
    prototype while writing warm, helpful prose, and every one of them would
    have put a number in a utility's mouth that nobody has agreed to.
    """
    text = (entry.body + " " + (entry.subject or "")).lower()
    found = sorted(phrase for phrase in UNRULED_PHRASES if phrase.lower() in text)
    assert (
        found == []
    ), f"{entry.code} states {found}, which is not ruled anywhere in this repo. " + " ".join(
        UNRULED_PHRASES[phrase] for phrase in found
    )


# ══════════════════════════════════════════════════════════════════════════
# 5 · DEF-210'S OWN DURABLE GUARD — EVERY CHANNEL HAS A RENDERABLE CLASS
# ══════════════════════════════════════════════════════════════════════════
def test_def_210__every_channel_has_at_least_one_seeded_class():
    """**THE ASSERTION DEF-210 ASKED FOR, IN ITS OWN WORDS:** *"a test asserting
    every channel in the catalog has at least one renderable class — the count
    is fixed platform vocabulary, so the assertion cannot drift."*

    This is the one that would have caught the defect. Before today the seeder
    planted two PRINT classes and nothing else, every gate was green, and the
    email subject line and the SMS counter had never rendered for any user on
    any tenant — because both are gated on `channel`, which stays null until a
    variant is published.

    ⚠ **AMENDED 2026-08-17 (CR-009 in-app lane): `in_app` JOINS THE SET, and it
    joins it on the RIGHT side of the assertion.** A fourth channel arrived with
    the PO's ruling that in-app is how the notification pipeline is proved to
    work (BR-NOT-019), and it arrived seeded — `staff_bulk_summary` — so this
    test's whole point holds: there is no channel in the catalog whose designer
    surfaces have never rendered for anybody.
    """
    channels = {catalogs.catalog_for(entry.code).channel for entry in seed.SEEDABLE}
    assert channels == {"pdf_print", "email", "sms", "in_app"}, (
        "a channel with no seeded class is a channel whose designer surfaces have never "
        f"rendered for anyone. Seeded channels: {sorted(channels)}."
    )


def test_def_210__every_email_class_carries_a_subject_and_no_other_class_does():
    """A19 r8's email table gives every email class a subject; printable and SMS
    classes carry NULL, which is *"this class has no subject"* rather than
    *"somebody saved an empty one"* (`template_models`).

    Asserted in BOTH directions on purpose. A one-way check passes on the day
    somebody gives a door hanger a subject line.
    """
    for entry in seed.SEEDABLE:
        channel = catalogs.catalog_for(entry.code).channel
        if entry.code in catalogs.PRINTED_INSIDE:
            # DEF-BIL-4454 (2026-10-22) — a *What changed* sentence is printed
            # INSIDE the corrected-bill email and never sent alone, so it has
            # no subject of its own: its host's subject is the one that goes.
            assert entry.subject is None, f"{entry.code} is printed inside another email"
            continue
        if channel == "email":
            assert entry.subject, f"{entry.code} is an email class with no subject line"
        else:
            assert entry.subject is None, f"{entry.code} is {channel} and carries a subject"


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE FIVE THAT ARE STILL EMPTY, AND WHY EACH ONE IS
# ══════════════════════════════════════════════════════════════════════════
#: code → the ID or rule a reader must be sent to. **These are the classes a
#: PRODUCT ruling could not reach**, and the test exists so that "we authored
#: the templates" can never quietly come to mean "all of them".
#:
#: ⚠ **THIS GUARD FIRED ON 2026-08-17 AND IS AMENDED RATHER THAN DELETED — THAT
#: IS THE OUTCOME IT WAS BUILT FOR.** It held EIGHT codes, three of them the
#: disconnect tiers marked `OQ-253`, and its own docstring set the condition for
#: removing one: *"If a later lane authors one of these, this test goes red and
#: the lane has to say which ruling let them — which is the only protection a
#: product ruling gives against being read as a legal one."*
#:
#: **The ruling, quoted, is the price of the three removals.** PO, 2026-08-17,
#: recorded in 12-governance/11-change-requests.md §"CR-007 · The disconnect
#: notices — the platform writes the defaults":
#:
#:   > *"we will take this option; we provide default option for all 5 you ahve
#:   > mentioned; if Utility wants to over ride it let them do it; I can also
#:   > give tick boxes if required to add 5"*
#:   > *"you build default langauge and let Utility user change it as they
#:   > want"*
#:
#: That is a ruling on OWNERSHIP of the five rights sentences, which is exactly
#: what BR-NOT-015 left unassigned when it said they *"must not be invented"* —
#: so the tiers are authored to an instruction rather than invented by a lane.
#: **It is still not a legal sign-off and nothing in the product claims to be
#: one:** every clause is marked as a platform default on screen, is overridable
#: and switchable per clause by a System Admin, and
#: `rights_footer.PLATFORM_DEFAULT_NOTICE` tells the person editing it to review
#: the wording against their own commission before a notice goes out.
#:
#: **[AMENDED 2026-08-18] The FOUR CONTRACTS are untouched and this guard still
#: stands over them.** `plan_notice_void` LEFT this set under its own ruling —
#: CR-009 C-14, PO verbatim: *"you give default language for the plan-void
#: notice only - we wil allow utility to make the changes"* — which is this
#: speed bump working a second time: the lane that seeded it came here and
#: named the ruling that let them. (The event it announces still has no writer;
#: the 'nodrop' ruling stands and the body states no miss threshold.)
#: ⚠ **[AMENDED 2026-08-18 — CR-011 item 9. THE GUARD FIRED A THIRD TIME AND
#: THIS TIME IT WAS THE LAST FOUR.]** The PO ruled on all four contracts in one
#: sentence, verbatim:
#:
#:   > *"the 4 template classes needing legal wording - already answer - provide
#:   > default and allow user to change"*
#:
#: and, on the two this session flagged back:
#:
#:   > *"Do it; put the details, I will handle it with user"* (the ACH
#:   > authorization — a labelled placeholder, plus the details written down)
#:   > *"create this dont leave it open ; once sample and defaults are available
#:   > we can make changes later; but without default sample functionalities ill
#:   > not work"* (the payment-plan agreement — OVERRULING this session)
#:
#: **So WHAT THIS SET MEANS HAS CHANGED, and the name is now the only stale
#: thing about it.** These four still have no PUBLISHED body at provisioning and
#: this guard still holds them there — but not for want of wording any more.
#: They have wording, in `seed_templates.CONTRACT_DEFAULTS`, offered on the
#: designer. What keeps them unpublished is **BR-NOT-002**: a contract version is
#: effective-dated, `save_draft` refuses a contract draft with no
#: `effective_from`, and the CR keeps that standing over its own ruling — *"a
#: draft still needs an `effective_from` a human chooses; provisioning-day is not
#: that date."*
#:
#: The marker each one carries is the ID a reader must be sent to, unchanged in
#: form: OQ-244 is now *how does the renderer print a repeating block* (not
#: *should this class exist*), and OQ-206's authoring half is closed by the
#: ruling while its row records what it was.
#:
#: ⚠ **AMENDED 2026-08-30 — THE MARKER IS NO LONGER INSIDE THE SENTENCE, AND
#: BOTH MARKERS THEMSELVES MOVED (`DEF-630`, 2026-08-24).**
#: This dict mapped each class to an ID and asserted `marker in reason`. That
#: assertion could only ever pass while the SERVED prose carried an internal
#: reference, which is exactly what `DEF-630` removed and what G28 forbids: an
#: operator reading *"no body: OQ-244"* learns nothing. The citation now travels
#: as DATA beside the English — `seed_templates.absent_refs(code)`, the same
#: shape `br_ref=` already travels on a `core.errors` refusal — so this file
#: asserts BOTH halves and neither inside the other: the clerk's sentence says
#: something a clerk can act on, and the citation is reachable by support.
#:
#: The IDs also changed, and the change is the point rather than a rename. The
#: four contracts are no longer held by *"nobody has written this"* — CR-011
#: item 9 gave all four platform wording (PO 2026-08-18: *"the 4 template
#: classes needing legal wording - already answer - provide default and allow
#: user to change"*). What holds them unpublished is **BR-NOT-002**: a contract
#: version is effective-dated and provisioning has no human to choose that date.
#: So `BR-NOT-002` is the citation every one of them now carries, plus the one
#: extra fact that is genuinely still unbuilt for two of them — `OQ-244`'s
#: instalment SCHEDULE block, and `BR-NOT-004`'s NACHA wording for the ACH
#: authorization, which is a deliberate placeholder the renderer refuses.
#: ⚠ **A FIFTH ENTRY ARRIVED 2026-08-30 (`DEF-2473`), AND IT IS THE FIRST ONE
#: HELD BY NEITHER A DATE NOR A SIGNATURE — IT IS HELD BY NOT HAVING BEEN
#: WRITTEN.** The four contracts above all HAVE platform wording and are unheld
#: only because a human must date them. `payment_failed_letter` has none, and
#: that is a different fact with a different fix: somebody has to write it.
#:
#: **Why the class exists at all.** BR-NOT-024's print floor (PO 2026-08-29,
#: *"don't switch of print for any document it is awayls on"*) puts a paper copy
#: of the returned-payment letter on the queue whatever a utility switches off,
#: and the only class that letter had was `email_payment_failed` — an EMAIL
#: class. So the printed row was pinned to an email body. The floor is right and
#: the missing print class was the gap.
#:
#: **Why it is blank.** It tells somebody that money they believed had reached us
#: came back. BR-NOT-015 is the rule that a class with no authored body REFUSES
#: rather than printing something we invented, and a lane drafting that letter to
#: close a defect would be inventing exactly the wording that rule exists to
#: forbid. So it ships listed, openable, and empty, with a sentence saying why.
STILL_EMPTY: dict[str, tuple[str, ...]] = {
    "contract_payment_plan": ("BR-NOT-002", "OQ-244"),
    "contract_service_agreement": ("BR-NOT-002",),
    "contract_deposit": ("BR-NOT-002",),
    "contract_autopay_authorization": ("BR-NOT-002", "BR-NOT-004"),
    # ⚠ `payment_failed_letter` LEFT THIS SET 2026-10-30 (`DEF-PAY-10744`), the
    # way the disconnect tiers and the plan-void notice did: the PO ruled the
    # payments audit's L2-04 fixed (*"Rest we will fix"* — a proper NSF email
    # and letter), so it is SEEDED from `payment_returned_wording` as a default
    # the utility edits. That is the ruling this guard asks a lane to name.
}


@pytest.mark.parametrize("code,markers", sorted(STILL_EMPTY.items()))
def test_def_210__the_eight_unauthored_classes_stay_empty_and_say_why(code, markers):
    """⚠ **THIS TEST ASSERTS AN ABSENCE, AND THAT IS THE POINT.**

    The 2026-08-17 ruling said *"define it for this product"*. Every class
    still here is a document somebody SIGNS.

    If a later lane authors one of these, this test goes red and the lane has to
    say which ruling let them — which is the only protection a product ruling
    gives against being read as a legal one. **That has now happened twice**:
    the three disconnect tiers on 2026-08-17, and `plan_notice_void` on
    2026-08-18 (C-14) — each ruling quoted above `STILL_EMPTY`, each class
    leaving this set in the same commit that seeded it.
    """
    assert code not in {entry.code for entry in seed.SEEDABLE}, (
        f"{code} has been PUBLISHED at provisioning. A contract version is "
        f"effective-dated (BR-NOT-002) and provisioning cannot choose that date — see "
        f"{', '.join(markers)}."
    )
    reason = seed.absent_reason(code)
    assert reason is not None, f"{code} has no published body and no stated reason"
    # ⚠ **TWO ASSERTIONS WHERE THERE WAS ONE (2026-08-30, see `STILL_EMPTY`).**
    # The sentence is a CLERK's and carries no reference (G28 / `DEF-630`); the
    # references travel beside it. Asserting both is what keeps `DEF-630`'s fix
    # from becoming `DEF-630`'s regression — the citation was rewritten out of
    # the prose once and survived only in a comment, which is hard-won law 1.
    assert not any(marker in reason for marker in markers), (
        f"{code}'s served reason names an internal reference — G28: a sentence a "
        f"utility reads carries no rule id. Put it on `ABSENT_REFS` instead. "
        f"Got: {reason!r}"
    )
    refs = seed.absent_refs(code)
    assert tuple(refs) == markers, (
        f"{code}'s absence is traced to {sorted(refs)} and this file expects "
        f"{sorted(markers)}. A class whose absence nobody can trace is what "
        f"`absent_refs` returns EMPTY for rather than guessing."
    )
    # ⚠ ADDED 2026-08-18 (CR-011 item 9), AND IT IS THE HALF THE OLD ASSERTIONS
    # COULD NOT SEE. "Not seeded" used to mean "nobody has written it". It now
    # means "written, offered, waiting for a human's date" — and a lane that
    # deleted the wording would still pass every line above.
    #
    # ⚠ **SCOPED TO THE CONTRACTS ON 2026-08-30 (`DEF-2473`), AND THE SCOPE IS
    # THE POINT RATHER THAN AN EXEMPTION.** This ran over every `STILL_EMPTY`
    # class and demanded an offered default, because on the day it was written
    # every member of that set was a CONTRACT and the PO's ruling
    # (*"provide default and allow user to change"*) had reached all four. It is
    # a check on the four contracts wearing a general shape.
    #
    # `payment_failed_letter` is unpublished for the OPPOSITE reason: not "we
    # wrote it, a human must date it", but "nobody has written it, and this lane
    # will not invent a letter about somebody's returned money" (BR-NOT-015).
    # Applying the contract rule to it would demand exactly the wording that rule
    # forbids — the check would be requiring the defect.
    #
    # So the two halves are asserted separately, and NEITHER is weakened: a
    # contract must still carry an offered default, and a class held by unwritten
    # wording must still be genuinely empty, so a lane that quietly drafts one
    # goes red here and has to say which ruling let them.
    offered = seed.default_body_for(code)
    if code in set(seed.CONTRACT_DEFAULTS):
        assert offered is not None, (
            f"{code} is unpublished AND has no offered platform default. The PO ruled on "
            "2026-08-18 that all four contracts get one: *'provide default and allow user "
            "to change'*."
        )
        assert offered.body.strip(), f"{code}'s offered default is empty"
    else:
        assert offered is None, (
            f"{code} has been given platform wording. It is on `STILL_EMPTY` because "
            "nobody had written it — if somebody now has, say which ruling let them and "
            "move it out of this set, the way the disconnect tiers and the plan-void "
            "notice both left it."
        )


def test_def_210__the_library_covers_thirty_one_of_the_thirty_six_listed_classes():
    """The arithmetic, held in one place so a report can never round it up.

    37 classes on SET-09 · 32 with a platform body · 5 with a stated reason.

    ⚠ **WAS 28 AND 8 UNTIL 2026-08-17.** CR-007's disconnect ruling added
    BR-NOT-014's three tiers. The numbers are written out rather than derived so
    that seeding a class silently is impossible: a lane that adds one has to come
    here and change a figure, which is the moment they have to say why.

    ⚠ **AND 36/31 BECAME 37/32 LATER THE SAME DAY, WHICH IS THIS SPEED BUMP
    WORKING EXACTLY AS DESIGNED.** CR-009's fourth PO ruling made in-app a real
    channel, and BR-NOT-020 — *"for bulk action also send 1 message only saying
    nulk action is completed"* — needs a class for that one message to render
    from. `staff_bulk_summary` is it: the first class in `GROUP_IN_APP`, seeded
    with a four-line body, and the only class in the library whose
    `mandatory_content` is a FAILURE COUNT. The lane that added it came here and
    said why, which is the whole reason these two figures are literals.

    ⚠ **AND 37/33 GAINED A THIRD FIGURE THE SAME DAY (CR-011 item 9): 37
    listed · 33 published · 4 OFFERED · 0 with no wording.** The PO ruled all
    four contracts get a default — *"already answer - provide default and allow
    user to change"* — and none of them is seeded, because BR-NOT-002 makes a
    contract version effective-dated and that date is a human's choice. So the
    seeded figure is unchanged ON PURPOSE and the number that moved is the last
    one: four classes with no wording became zero.

    ⚠ **37/32 BECAME 37/33 ON 2026-08-18 — the bump's third catch.** CR-009
    C-14, PO verbatim: *"you give default language for the plan-void notice
    only - we wil allow utility to make the changes"* — `plan_notice_void` is
    seeded, the four contracts are the whole remainder, and the event the new
    body announces still has no writer ('nodrop' stands).

    ⚠ **37/33/4/0 BECAME 38/33/4/1 ON 2026-08-30 (`DEF-2473`), AND THE FIGURE
    THAT MOVED IS THE LAST ONE — BACK OFF ZERO.** In plain English: the template
    list grows by one document, from 37 to 38; the number published at
    provisioning does not move; and the number with no wording at all goes from
    none to one.

    The new document is the PRINTED returned-payment letter. It exists because a
    paper copy of that letter is queued on every bounce whatever a utility
    switches off (the print floor, PO 2026-08-29) and the only class it could be
    pinned to was the EMAIL one — so the printed row carried an email body. It is
    BLANK because nobody has written the wording for it and this is a letter
    about somebody's returned money; `STILL_EMPTY` above carries that argument in
    full, and the parametrized test below is what holds it blank.

    **So the fourth figure is no longer an invariant, and pretending otherwise
    was the risk.** The old assertion `seeded | offered == listed` said *every
    listed class carries platform wording*. That was true when it was written and
    it is a claim about wording, not a rule about it — a class whose absence is
    STATED is the posture `seed_templates.absent_reason` was built to serve. The
    assertion is therefore replaced rather than deleted: every listed class must
    now either carry wording OR have a reason a clerk can read, which is strictly
    what the old one asserted plus one honest exception.
    """
    listed = set(catalogs.LISTINGS)
    seeded = {entry.code for entry in seed.SEEDABLE}
    offered = set(seed.CONTRACT_DEFAULTS)
    # ⚠ **38/33 BECAME 39/34 ON 2026-09-12 (`CR-094-BRC01` wave K, `ACC-S16`),
    # AND BOTH FIGURES MOVED TOGETHER, WHICH IS THE HEALTHY SHAPE.** The new
    # class is `account_message` — what a clerk types to a customer from the
    # account screen — and it is seeded at provisioning like the other 33,
    # because a utility cannot be asked to author the wrapper around their own
    # clerk's words before the clerk can send any. Nothing here joins
    # `STILL_EMPTY`: the class HAS a body, and its body is one token.
    # ⚠ **39/34 BECAME 43/38 ON 2026-09-15 (`CR-094-BRC01`, `DEF-CUS-5389`),
    # AND BOTH FIGURES MOVED TOGETHER AGAIN.** In plain English: the template
    # list grows by four documents, from 39 to 43, and all four are published at
    # provisioning, so the seeded figure moves by the same four. Nothing joins
    # `STILL_EMPTY`.
    #
    # The four are the only classes in the library addressed to somebody who is
    # NOT a customer. They go to an APPLICANT — a person who has asked for
    # service and holds no account — and before them, nothing this product did
    # with a service request ever reached the person who raised it.
    #
    # ⚠ **THE ACKNOWLEDGEMENT IS TWO OF THE FOUR, AND THAT IS THE INTERESTING
    # ONE.** `BR-CUS-090` clause (3) forbids the sentence *nothing is charged*
    # on an acknowledgement for a request where money WAS taken at the counter,
    # and requires the amount, the method and the receipt number instead. A
    # template body has no conditional in it, so one class could only ever carry
    # one of those two sentences and the other would be a rule somebody had to
    # remember. Two classes, pinned by whether a receipt exists, makes the wrong
    # sentence unreachable. That is why the figure moved by four rather than by
    # three — and it is worth the extra row.
    # ⚠ **44 SINCE 2026-09-15** (`CR-094-BRC01` lane J): `service_request_approved`,
    # the letter an applicant gets when their request is APPROVED. It is a class
    # of its own and not a branch inside the refusal for the same reason the two
    # sentences above are two classes — a body has no conditional in it, and
    # *"we are going ahead"* and *"we are not able to go ahead"* are two letters.
    # ⚠ **44/39 BECAME 47/42 ON 2026-09-20 (`DEF-CUS-5949`), AND BOTH FIGURES
    # MOVED TOGETHER, WHICH IS THE HEALTHY SHAPE.** In plain English: the
    # template list grows by three, from 44 to 47, and all three are published
    # at provisioning, so the seeded figure moves by the same three. Nothing
    # joins `STILL_EMPTY`.
    #
    # The three are what a PROPERTY SALE says on commit, and before them a
    # committed sale told nobody it had happened — neither the person who
    # bought the house nor the person who sold it. Two letters and one text:
    # the buyer is told the account is theirs, the seller is told it is not,
    # and the buyer gets a text saying a meter reading is being arranged.
    #
    # ⚠ **THE TWO LETTERS ARE TWO CLASSES FOR THE REASON THE ACKNOWLEDGEMENT
    # ABOVE IS TWO:** a template body has no conditional in it, and *"the
    # account is yours from today"* and *"the account is no longer yours"* are
    # two letters to two different people.
    #
    # ⚠ **AND THEIR WORDING IS THE ONE THING HERE NOBODY HAS RATIFIED.** They
    # carry `_LANE_AUTHORED` as their source rather than the PO's 2026-08-17
    # ruling, precisely so a reviewer can see which three those are without
    # diffing; `OQ-CUS-12524` is where the PO settles the words. They are
    # SEEDED anyway, because a utility cannot be asked to author the wording
    # for a letter their clerks can already trigger — which is the argument the
    # four applicant classes above already won.
    # ⚠ **AND THE ARITHMETIC ABOVE IS NOT THE WHOLE MOVE: IT IS 44 → 49 AND
    # 39 → 44, BECAUSE TWO CLASSES ARRIVED BEFORE MINE WITHOUT COMING HERE.**
    # `new_connect_confirmed` and `new_connect_quote` — step 7's two messages
    # to an owner whose build was confirmed and quoted — landed in `d54a7f7d7`
    # (*"A landlord with open tenants is warned, not refused"*, 2026-09-20) and
    # this figure was not moved with them, so **both of these assertions were
    # ALREADY RED when the transfer lane started**. Dated rather than asserted:
    # `git log -S '"new_connect_confirmed": TemplateListing' -- catalogs.py`
    # names that commit and not this one.
    #
    # It is the speed bump doing its job and being READ late, which is the
    # failure hard-won law 7 puts above every other: a guard nobody reads is
    # not a guard. Recorded here rather than silently absorbed into the
    # transfer lane's own +3, so the next reader can see that two lanes moved
    # this number and only one of them said so.
    # ⚠ **49/44 BECAME 50/45 ON 2026-09-27 (`CR-142-BRC07` `P4.10`, lane
    # REP-P4-REST), AND BOTH FIGURES MOVED TOGETHER, WHICH IS THE HEALTHY
    # SHAPE.** In plain English: the template list grows by one document, from
    # 49 to 50, and it is published at provisioning, so the seeded figure moves
    # by the same one. Nothing joins `STILL_EMPTY`.
    #
    # The new class is `email_scheduled_report` — *your report ran, here is the
    # link* — and it is **the only body in the library addressed to a member of
    # STAFF by email**; `staff_bulk_summary`, the only other staff class, is
    # in-app. So it carries no masthead and no support line: the product is
    # writing to the utility's own clerk, and a named absence where the company
    # name should be would reach that clerk on any tenant that has not filled
    # in Settings → Company. `staff_bulk_summary`'s own class records the same
    # reasoning for the same reason.
    #
    # ⚠ **ITS WORDING IS LANE-AUTHORED AND NOBODY HAS RATIFIED IT.** It carries
    # `_REPORTS_LANE_AUTHORED` as its source — its own string, not the transfer
    # lane's — precisely so a reviewer can see which body belongs to which lane
    # and which question settles it. `OQ-REP-12757` is where the PO settles the
    # words. It is SEEDED anyway, because a utility cannot be asked to author
    # the wording for a message their own schedules already trigger, which is
    # the argument the applicant classes above already won.
    # ⚠ **51 SINCE 2026-10-04 (`CR-168-BRC10` §F, lane FIELD-2)** — one more
    # in-app class, `staff_field_work` (the office told about a field close,
    # its photos, or Needs review). LISTED and SEEDED together, so the seeded
    # figure below moves by the same one.
    # ⚠ **55 SINCE 2026-10-04 (`2.517.0`, `CR-168-BRC10` P6.1, lane SRV-5)** —
    # four customer classes for a visit: `service_visit_moved` (email) and the
    # texts `sms_visit_booked`, `sms_visit_moved`, `sms_technician_on_the_way`.
    # LISTED and SEEDED together, so the seeded figure below moves by four too.
    # ⚠ **56 SINCE 2026-10-14 (`CR-182-BRC10`, lane HIGHUSE)** — the email a
    # customer gets when a reading is flagged high, `email_high_usage_alert`.
    # LISTED and SEEDED together, so the seeded figure below moves by one too.
    # ⚠ **58 SINCE 2026-10-22 (`CR-188-BRC10`)** — the two Account access
    # emails, `staff_user_invite` and `staff_password_reset_link`. LISTED and
    # SEEDED together (the `default` variant, plus one per registry language),
    # so the seeded figure below moves by two too.
    # ⚠ **59 SINCE THE SAME DAY'S MERGE** — `portal_password_reset`
    # (`DEF-CWP-10381`, lane PORTAL-RESET), listed and seeded the same way.
    # ⚠ **62 AT THE SAME MERGE** — `CR-189-BRC10` (lane PORTAL-EMAIL): the
    # portal's one-time code, which had a queue row and no class
    # (`DEF-CWP-10402`), the code to a NEW address and the notice to the OLD
    # one. Listed and seeded together, so the seeded figure moves by three too.
    # ⚠ **64 AT THE FOUR-BRANCH MERGE (2026-10-22, lane MERGE-EMAILS)** —
    # `CR-190-BRC10`'s `email_agreement_request` and `email_agreement_accepted`.
    # Their lane planted them at first use only; the merge put them in the ONE
    # seeder (`seed_templates.LANGUAGE_WORDING`), so they are listed AND seeded
    # and the seeded figure moves by two too.
    # ⚠ **81 SINCE 2026-10-22 (`DEF-BIL-4454`, lane CORRECTED-BILL)** — the
    # seventeen *What changed* sentences, `correction_reason_<code>`, one per
    # seeded correction reason. LISTED and SEEDED together.
    # ⚠ **87 SINCE 2026-10-29 (`DEF-NOT-10649`)** — the four service-state
    # classes (`service_disconnected_guide`, `sms_service_disconnected`,
    # `service_restored`, `sms_service_restored`), LISTED and SEEDED together.
    # ⚠ **AND TWO MORE THE SAME DAY THAT DID NOT COME HERE:** `DEF-WRK-10652`
    # (d8c381b30) listed and seeded `service_work_order_logged` and
    # `sms_work_order_logged` without moving these figures, so the tip this lane
    # rebased onto read 83 / 78 against 81 / 76 — red before this lane's four.
    assert len(listed) == 87
    assert seeded <= listed
    # ⚠ **39 SINCE 2026-09-15** — the same one class as the line above
    # (`service_request_approved`, `CR-094-BRC01` lane J): it is both LISTED and
    # SEEDED, so both counts move together and a single one moving is the
    # signal that a class was added to one file and forgotten in the other.
    # 45 + `staff_field_work` + SRV-5's four (2026-10-04) + `email_high_usage_alert` (CR-182)
    # + CR-188-BRC10's two Account access emails (2026-10-22)
    # + `portal_password_reset` (DEF-CWP-10381, 2026-10-22)
    # + CR-189-BRC10's three Account access classes (2026-10-22)
    # + CR-190-BRC10's two agreement emails (merge, 2026-10-22)
    # + DEF-BIL-4454's seventeen *What changed* sentences (2026-10-22)
    # + DEF-NOT-10649's four service-state classes and DEF-WRK-10652's two
    #   work-order-logged classes (both 2026-10-29; see above)
    # + `payment_failed_letter` (DEF-PAY-10744, 2026-10-30 — left `STILL_EMPTY`)
    assert len(seeded) == 83
    assert listed - seeded == set(STILL_EMPTY)

    # ⚠ **THE THIRD FIGURE, ADDED 2026-08-18 (CR-011 item 9).** 33 did NOT
    # become 37 and that is the interesting part: the four contracts gained
    # wording and did not gain a published row, because BR-NOT-002 makes that
    # date a human's. The arithmetic a report can now quote without rounding
    # anything up is **37 listed · 33 published at provisioning · 4 offered as
    # effective-dated defaults · 0 with no wording at all**, where "0" is the
    # figure the PO's ruling actually moved (it was 4).
    # ⚠ **AMENDED 2026-08-30 (`DEF-2473`) — `offered` IS NOW A SUBSET OF
    # `STILL_EMPTY`, NOT EQUAL TO IT**, because the two sets stopped meaning the
    # same thing. Both used to be "the four contracts": listed, unpublished,
    # holding platform wording nobody had dated. The printed returned-payment
    # letter is listed and unpublished and holds NO wording, so it joins the one
    # set and not the other. Four offered, five unpublished, and the difference
    # between those two numbers is the count this file's headline figure tracks.
    assert len(offered) == 4
    # 2026-10-30 (`DEF-PAY-10744`): the letter was the one member of
    # `STILL_EMPTY` with no offered default; it is seeded now, so the two sets
    # are the four contracts again.
    assert offered == set(STILL_EMPTY)

    # ⚠ **THE REPLACED ASSERTION, KEPT AS PROSE SO THE CHANGE IS VISIBLE (hard-won
    # law 1).** It read:
    #
    #     assert seeded | offered == listed, "every listed class must now carry
    #     platform wording"
    #
    # That claim was true the day it was written and it is a statement about how
    # many classes had been AUTHORED, never a rule that they all must be. What
    # replaces it is the rule the old one was standing in for, and it is strictly
    # stronger on the 37 classes it already covered: a listed class either has a
    # body, or it has a sentence telling a utility why it has not — never neither,
    # which is the silent state this assertion exists to catch.
    for code in listed:
        assert code in seeded or seed.absent_reason(code) is not None, (
            f"{code} is listed on the template catalog with no platform wording and no "
            "stated reason. A class a utility can open and cannot use, with nothing "
            "saying why, is the silent absence `absent_reason` exists to prevent."
        )
    assert seeded | offered | set(STILL_EMPTY) == listed


# ══════════════════════════════════════════════════════════════════════════
# 7 · AND IT REACHES A REAL TENANT — THE ACCEPTANCE PRECONDITION
# ══════════════════════════════════════════════════════════════════════════
def test_def_210__provisioning_publishes_an_email_variant_with_a_subject(
    growth_plan, identity_seam
):
    """**THE SERVER HALF OF CR-007's FIRST ACCEPTANCE ITEM — the email subject
    line.**

    The subject field on SET-10 is gated on `channel == "email"`, and `channel`
    is null until a variant is PUBLISHED. This asserts the state that gate needs:
    a real tenant, provisioned through the real service, ends up with published
    email variants whose stored `subject` is non-null.

    It does not assert that the field appears on screen — nothing in this repo
    reads rendered output. It asserts that the reason it could not appear is
    gone.
    """
    tenant, _ = provisioned_tenant()
    #: Read off SEEDABLE rather than written as `19`, so adding an email class
    #: raises the bar automatically instead of passing under a stale literal.
    #: DEF-BIL-4454 — the *What changed* sentences are email-channel classes
    #: printed inside another email, with no subject: counted apart.
    expected = sum(
        1
        for e in seed.SEEDABLE
        if catalogs.catalog_for(e.code).channel == "email" and e.code not in catalogs.PRINTED_INSIDE
    )
    # ⚠ 19 → 20 on 2026-08-18: `plan_notice_void` joined under CR-009 C-14
    # (*"you give default language for the plan-void notice only"*) — the bar
    # working as designed, raised with the ruling named.
    # ⚠ **20 BECAME 21 ON 2026-09-12** — `account_message`, the wrapper around
    # what a clerk types (`CR-094-BRC01` wave K). It is an email class like the
    # other twenty and it is seeded at provisioning like them.
    # ⚠ **21 BECAME 25 ON 2026-09-15** — the four an APPLICANT receives
    # (`CR-094-BRC01` lane C, `DEF-CUS-5389`): a request acknowledged with no
    # fee taken, the same acknowledgement where a fee WAS taken, a refusal
    # letter and an ask for more. All four are email classes and all four are
    # seeded at provisioning, because a utility cannot be asked to author the
    # wording for a letter their clerks can already trigger.
    # ⚠ **26 SINCE 2026-09-15** — `service_request_approved` (`CR-094-BRC01`
    # lane J). The assertion is kept as a NUMBER on purpose: it is the line that
    # tells the next lane the report's own figures have gone stale.
    # ⚠ **26 BECAME 30 ON 2026-09-20, AND TWO LANES MOVED IT.** Two are
    # `transfer_to_buyer` and `transfer_to_seller`, the letters a property sale
    # queues on commit (`DEF-CUS-5949`) — the sale's THIRD message is a TEXT and
    # is counted by the SMS case below, which is why the sale moves this figure
    # by two and that one by one. **The other two arrived first and did not
    # come here:** `new_connect_confirmed` and `new_connect_quote` landed in
    # `d54a7f7d7` the same day, so this assertion was ALREADY RED before the
    # transfer lane started — dated with `git log -S`, not asserted.
    # ⚠ **30 BECAME 31 ON 2026-09-27** — `email_scheduled_report`
    # (`CR-142-BRC07` `P4.10`), the message a schedule sends when its report has
    # run. It is an email class like the other thirty and it is seeded at
    # provisioning like them, for the same reason: a utility cannot be asked to
    # author the wording for a message their own schedules already trigger.
    # ⚠ **IT IS THE ONLY ONE OF THE THIRTY-ONE ADDRESSED TO A MEMBER OF STAFF**,
    # which is why it carries no masthead and no support line — see its class in
    # `catalogs.py`. The number is kept as a LITERAL on purpose: it is the line
    # that tells the next lane the report's own figures have gone stale.
    # ⚠ **31 BECAME 32 ON 2026-10-04 (`2.517.0`)** — `service_visit_moved`, the
    # customer told their visit has a new time (`CR-168-BRC10` P6.1, lane SRV-5).
    # ⚠ **32 BECAME 33 ON 2026-10-14** — `email_high_usage_alert`, the customer
    # told a reading was flagged high (`CR-182-BRC10`, PO A4/A5, lane HIGHUSE).
    # ⚠ **33 BECAME 39 ON 2026-10-22** — `staff_user_invite` and
    # `staff_password_reset_link` (`CR-188-BRC10`), a member of staff's own
    # sign-in link, addressed to staff like `email_scheduled_report`;
    # `portal_password_reset` (`DEF-CWP-10381`), the customer portal's reset
    # link; and `CR-189-BRC10`'s three (the portal one-time code, the code to a
    # new address, the notice to the old one).
    # ⚠ **39 BECAME 41 AT THE MERGE** — the two agreement emails (`CR-190-BRC10`).
    # ⚠ **41 BECAME 44 ON 2026-10-29** — `service_disconnected_guide` and
    # `service_restored` (`DEF-NOT-10649`, PO *"1 A, 2 A, 3 A, 4 A"*), and
    # `service_work_order_logged`, which `DEF-WRK-10652` (d8c381b30) seeded the
    # same day without moving this figure — so this line was ALREADY RED when
    # the DEF-NOT-10649 lane reached it, dated with `git log -S`.
    assert expected == 44, "the seeded email count moved — check the report's figures too"
    with tenant_ctx(tenant):
        # ⚠ The `default` variant of each class. Since `CR-188`/`CR-189-BRC10`
        # (2026-10-22) the Account access classes also plant one variant per
        # registry language, which is more ROWS for the same CLASSES; every
        # variant is still checked for a published subject below.
        rows = tm.NotificationTemplate.objects.filter(channel="email").exclude(
            code__in=list(catalogs.PRINTED_INSIDE)
        )
        assert rows.filter(language=tm.VARIANT_DEFAULT).count() == expected
        for template in rows:
            live = tm.NotificationTemplateVersion.objects.filter(
                template=template, status=tm.VERSION_PUBLISHED
            ).first()
            assert live is not None, f"{template.code} is registered and not published"
            assert live.subject, f"{template.code} published with no subject line"
            assert "{" in live.subject, (
                f"{template.code}'s subject is a constant string. Every authored subject "
                "carries at least the utility's own name, or one tenant's email looks "
                "identical to another's."
            )


def test_def_210__provisioning_publishes_an_sms_variant_under_the_counter(
    growth_plan, identity_seam
):
    """**THE SERVER HALF OF CR-007's SECOND ACCEPTANCE ITEM — the 160-char
    counter.**

    Same shape as the subject test and the same honesty about its limit: the
    counter is gated on `channel == "sms"` and there was no SMS variant on any
    tenant until today. This asserts four published SMS variants exist and that
    every stored body is inside the limit the counter enforces.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = tm.NotificationTemplate.objects.filter(channel="sms")
        # ⚠ **FOUR BECAME FIVE ON 2026-09-20** (`DEF-CUS-5949`):
        # `transfer_field_visit_sms`, the text a property sale queues to the
        # BUYER saying a meter reading is being arranged. It is the first SMS
        # class in this library written by a lane rather than under the PO's
        # 2026-08-17 ruling, and `OQ-CUS-12524` is where its wording is
        # settled. The 160-character assertion below is what held it to the
        # budget while it was being written.
        # ⚠ **FIVE BECAME EIGHT ON 2026-10-04 (`2.517.0`)** — ruling 3's three
        # texts to a customer about a visit: booked, moved, on the way
        # (`CR-168-BRC10` P6.1, lane SRV-5); each under the counter below.
        # ⚠ **EIGHT BECAME ELEVEN ON 2026-10-29, AND THE COUNT IS NOW OF
        # `default` VARIANTS.** `sms_service_disconnected` and
        # `sms_service_restored` (`DEF-NOT-10649`) are the first SMS classes
        # planted once per registry language as well (`LANGUAGE_WORDING`), so a
        # count of ROWS would move with the language registry; the third is
        # `sms_work_order_logged` (`DEF-WRK-10652`, the same day, unrecorded
        # here). The loop below still holds EVERY variant under the counter.
        assert rows.filter(language=tm.VARIANT_DEFAULT).count() == 11
        for template in rows:
            live = tm.NotificationTemplateVersion.objects.filter(
                template=template, status=tm.VERSION_PUBLISHED
            ).first()
            assert live is not None, f"{template.code} is registered and not published"
            assert live.subject is None
            assert len(live.body) < SMS_LIMIT, f"{template.code}: {len(live.body)} chars"


def test_def_210__a_seeded_email_renders_end_to_end_with_its_subject(growth_plan, identity_seam):
    """One body, all the way through the real renderer, subject included.

    Proves the three things a screen would show: the subject merges, the body
    merges, and a token the caller has no value for becomes the NAMED ABSENCE
    `——` rather than a leaked `{token}` (OQ-117's closure).

    ⚠ AND IT SHOWS THE HONEST STATE OF THE MERGE CONTEXT. Most of these classes
    have no consumer yet — the PO's own ruling is *"connecting it with actual
    workflow ... we will take acare later"* — so a preview today fills the
    utility's own identity and marks the account figures absent. That is the
    ratified posture, not a new defect, and the test asserts it rather than
    letting a reader assume the bodies render complete.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        template = tm.NotificationTemplate.objects.get(code="email_welcome")
        live = tm.NotificationTemplateVersion.objects.get(
            template=template, status=tm.VERSION_PUBLISHED
        )
        artifact = rendering.render(
            template_code="email_welcome",
            template_version=live.version,
            body=live.body,
            subject=live.subject,
            context={"first_name": "Jordan", "account_no": "ACCT-10021"},
        )

    assert artifact.channel == "email"
    assert artifact.subject and "{" not in artifact.subject
    assert "Welcome, Jordan." in artifact.body
    assert "ACCT-10021" in artifact.body
    assert "{" not in artifact.body  # nothing leaks a template artifact
    # The figures no caller supplied are NAMED, and named where somebody can act.
    absent = {absence["token"] for absence in artifact.absences}
    assert "service_start_date" in absent
    # ⊕ CR-190-BRC10 (PO 2026-10-22, *"give the activation date , first bill
    # date and no due date required"*) — `{first_bill_date}` is OPTIONAL on this
    # class: with no value its paragraph is left out, so it is neither printed
    # as `——` nor counted as an absence.
    assert "first_bill_date" not in absent
    assert "first bill on" not in artifact.body


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-210@2026-08-17 (12-governance/11-change-requests.md §"CR-007 — PO RULINGS 2026-08-17" · 12-governance/10-defect-log.csv DEF-210 · apps/notifications/catalogs.py · 05-prototype/r10-2026-08-16/SMARTBillHub.dc.html §TPL)
# generated: 2026-08-17 by story-coder (CR-007 template-authoring lane)
# checklist: A✔ B✔ C✔ D=deferred(no API surface — the catalog and seed endpoints exist and are covered by test_cr_007_template_catalog.py) E=deferred(no-frontend-half — SET-09/SET-10 are another lane's this session; the subject field and the SMS counter are proved to their SERVER precondition only and the browser check is REPORTED NOT DONE) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest 368 passed / 45 skipped across the notifications
#         and template suites · EVERY GUARD HERE WAS PROVED RED BEFORE BEING
#         TRUSTED GREEN (hard-won law 7). The sabotage was done in a THROWAWAY
#         `git worktree` off this commit rather than in the shared tree, because
#         six lanes read that tree and a body with `{utility_logo}` in it for
#         ninety seconds is CLAUDE.md law 11's mechanism two waiting to happen.
#         The six measured failures, quoted:
#         · the logo guard — `{utility_logo}` prepended to EMAIL_WELCOME_BODY ⇒
#           `AssertionError: email_welcome references {utility_logo}. The render
#           context supplies no value, so this prints '——' where the logo belongs
#           on a real customer's letter (DEF-195).`
#         · the palette guard — the SAME sabotage, caught one test earlier ⇒
#           `RenderRefused: {utility_logo} is not in the 'email_welcome' catalog.
#           Its palette is: account_no, customer_name, first_bill_date,
#           first_name, service_address, service_start_date, support_email,
#           support_phone, utility_name, utility_website`. ⚠ Worth stating
#           because it CORRECTS this trailer's first draft, which claimed a
#           `{meter_no}`-in-a-receipt proof it had not run: the palette refusal
#           and the logo assertion fire on one edit, and the palette fires first.
#         · the 160-char guard — SMS_PAST_DUE_BODY lengthened ⇒ `AssertionError:
#           sms_past_due is 178 characters of template text and the limit is
#           160.` (178, not the 168 first guessed — measured, as the rule says.)
#         · the unruled-figure guard — ". A $25 fee applies." appended to
#           EMAIL_PAYMENT_FAILED_BODY ⇒ `AssertionError: email_payment_failed
#           states ['$25'], which is not ruled anywhere in this repo. r10's NSF
#           fee. An NSF fee is a tenant CHARGE CODE and no rule sets a figure.`
#         · the every-channel guard — ⚠ removing ONE SMS entry did NOT go red,
#           which is correct and is the more useful half of the proof; all FOUR
#           removed ⇒ `AssertionError: a channel with no seeded class is a
#           channel whose designer surfaces have never rendered for anyone.
#           Seeded channels: ['email', 'pdf_print'].`
#         · the still-empty guard — a `disconnect_notice_10_day` body added to
#           SEEDABLE ⇒ `AssertionError: disconnect_notice_10_day has been given a
#           platform body. That needs a ruling this repo does not record — see
#           OQ-253.` This is the one that protects a legal absence, so it was
#           proved on the class it exists for.
# exceptions: (1) THE BROWSER HALF IS NOT PROVED HERE AND IS NOT CLAIMED. No
#         gate in this repo reads rendered output (B14's own status table). What
#         is proved is the server-side precondition both CR-007 acceptance items
#         are gated on.
#         (2) THE SMS MEASUREMENT IS OF TEMPLATE TEXT, not of a rendered
#         message. No rule states a rendered-length limit and none is invented;
#         the authored bodies carry 30–60 characters of headroom for that reason.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

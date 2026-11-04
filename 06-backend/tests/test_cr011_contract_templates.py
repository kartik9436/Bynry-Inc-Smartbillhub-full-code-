# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the template library — CR-011 item 9: the four contract
#           classes that shipped EMPTY)   Screens: S8 (templates card) · SET-10
#           · S67 (contract types)
# Rules:    CR-011 item 9 (PO 2026-08-18, verbatim: "the 4 template classes
#           needing legal wording - already answer - provide default and allow
#           user to change") · the ACH half ("Do it; put the details, I will
#           handle it with user") · the payment-plan half, OVERRULING this
#           session ("create this dont leave it open ; once sample and defaults
#           are available we can make changes later; but without default sample
#           functionalities ill not work") · BR-NOT-002 (contract versions are
#           EFFECTIVE-DATED — the constraint the CR leaves standing) ·
#           BR-NOT-016 (the instalment schedule prints INSIDE the agreement) ·
#           BR-NOT-004 (the four contract types) · BR-NOT-013 (nothing sends) ·
#           BR-PAY-016 as superseded by 'nodrop' (2026-08-11)
# ───────────────────────────────────────────────────────
"""The four contracts have wording, none of them is published, and one refuses.

Three facts this file exists to keep true, because each is a different failure:

1. **The wording EXISTS.** Four classes refused every save yesterday; a utility
   opening any of them found nothing to demonstrate and nothing to edit, which
   is what *"without default sample functionalities ill not work"* was about.
2. **Nothing is PUBLISHED at provisioning, and that is BR-NOT-002 rather than a
   refusal.** A contract version is effective-dated and only a human can choose
   that date — the CR says so over its own ruling. Seeding one undated would be
   worse than not seeding it at all: an undated published version wins over
   every dated one in `template_service._published_version`, so ours would
   shadow the utility's forever.
3. **One of the four REFUSES TO RENDER and the refusal is the feature.** The
   ACH authorization's wording is NACHA's, a scheme this repo does not hold.

The assertions that matter most here are absences and refusals, so each one is
paired with the positive that proves it is not vacuous.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from apps.notifications import catalogs, rendering, seed_templates, templates_api
from apps.notifications import template_models as tm
from apps.notifications import template_service
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import provisioned_tenant

pytestmark = pytest.mark.django_db

ON_DATE = date(2026, 8, 18)

#: The four, in BR-NOT-004's own order.
CONTRACTS = (
    "contract_payment_plan",
    "contract_service_agreement",
    "contract_deposit",
    "contract_autopay_authorization",
)

PLACEHOLDER = "contract_autopay_authorization"

APP = Path(__file__).resolve().parents[1] / "apps" / "notifications"


def flat(text: str) -> str:
    """One long line, so an assertion about WORDING never fails on a line break.

    Every body here is a laid-out document and every quoted argument is a
    wrapped comment; a substring check against either is really a check about
    the sentence, not about where the author pressed return.
    """
    return re.sub(r"\s+", " ", text.replace("#:", " ").replace(">", " "))


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE WORDING EXISTS — the half the ruling changed
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("code", CONTRACTS)
def test_cr011__every_contract_class_has_a_palette_and_offered_wording(code):
    """Yesterday all four refused at `_class_or_refuse`; three had no palette at
    all and the fourth had a palette and no body.

    PO, 2026-08-18: *"the 4 template classes needing legal wording - already
    answer - provide default and allow user to change"*.
    """
    assert catalogs.catalog_for(code) is not None, f"{code} still has no palette"
    assert code not in catalogs.CLASSES_WITHOUT_CATALOG
    assert catalogs.not_authored_reason(code) is None

    offered = seed_templates.default_body_for(code)
    assert offered is not None, f"{code} has no offered platform default"
    assert offered.body.strip()
    assert offered.name == catalogs.LISTINGS[code].name


@pytest.mark.parametrize("code", CONTRACTS)
def test_cr011__each_offered_body_would_pass_the_utilitys_own_save(code):
    """The one check that is never skipped for a seeded body, applied to an
    offered one: a default the ordinary designer door would refuse is a special
    case living inside a customer-facing document.
    """
    offered = seed_templates.default_body_for(code)
    rendering.validate_body(code, offered.body, subject=offered.subject)


@pytest.mark.parametrize("code", CONTRACTS)
def test_cr011__no_offered_body_uses_the_logo_token(code):
    """DEF-195. The render context supplies no value for `{utility_logo}`, so a
    body using it prints `——` on a document somebody signs."""
    assert "{utility_logo}" not in seed_templates.default_body_for(code).body


#: Prototype r10's sample prose for a fictional utility, plus the figures the
#: 2026-08-17 authoring already banned. None is ruled anywhere in this repo.
FORBIDDEN_PHRASES = (
    "$25",
    "$60",
    "NSF fee",
    "retry within",
    "12 months",
    "14 days",
    "3–5 business days",
    "60 days",
    "PUC rule",
    "collection agency",
)


@pytest.mark.parametrize("code", CONTRACTS)
def test_cr011__no_contract_states_a_figure_fee_or_period_no_rule_sets(code):
    """The rule every authored body in this product runs under, and the one that
    made three of these four refusable in the first place: *"it would have to
    state when a deposit is returned and on what condition, and no rule states
    either."* The answer is to state neither and point at the utility's own
    published policy — not to state a plausible one.
    """
    body = seed_templates.default_body_for(code).body
    lowered = body.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in lowered, f"{code} states {phrase!r}, which no rule sets"
    # A money amount that is not a token, and a period in days/months that is
    # not a token, are the two shapes the ban is really about.
    assert not re.search(r"\$\s?\d", body), f"{code} carries a hardcoded money figure"
    assert not re.search(r"\b\d+\s*(day|days|month|months|year|years)\b", lowered), (
        f"{code} carries a hardcoded period"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE PAYMENT PLAN — the overruled objection, carried inside the document
# ══════════════════════════════════════════════════════════════════════════
def test_cr011__the_schedule_token_is_ruled_and_cannot_be_edited_out():
    """BR-NOT-016 CONFIRMED (PO 2026-08-16, *"Print the schedule inside the
    agreement"*): the contract body carries a merge token for the table itself,
    *"never as an attachment"*.

    So the token is not this lane's invention, and it is MANDATORY class content
    — the `staff_bulk_summary` failure-count precedent. A utility may rewrite
    every word around it and cannot produce the document the original refusal
    was written about: a total with no due dates.
    """
    klass = catalogs.catalog_for("contract_payment_plan")
    assert "schedule_table" in klass.tokens
    assert klass.mandatory_content == ("{schedule_table}",)
    assert "BR-NOT-016" in klass.mandatory_content_reason

    body = seed_templates.default_body_for("contract_payment_plan").body
    assert "{schedule_table}" in body

    # RED-PROOF, inline: the same body without the token is REFUSED, and the
    # refusal quotes this class's own rule rather than the statement class's.
    with pytest.raises(rendering.RenderRefused) as refusal:
        rendering.validate_body("contract_payment_plan", body.replace("{schedule_table}", ""))
    assert "BR-NOT-016" in str(refusal.value)
    assert "nothing is due" not in str(refusal.value), (
        "the refusal is explaining A19 rule 1 — a true sentence about a different document"
    )


def test_cr011__the_schedule_renders_as_a_named_absence_and_the_document_says_so(brazos):
    """**THE HONEST HALF OF AN OVERRULED OBJECTION.**

    Nothing in this repo builds the repeating block — that is all OQ-244 still
    holds — so `{schedule_table}` renders `——`, the same named absence every
    unsupplied catalogued token renders (OQ-117: *"issue and report it"*).

    That alone would be the failure the PO named. What makes it not that is the
    sentence beside it: the agreement tells its reader, on its own face, not to
    sign a blank schedule. The absence is reported in `absences` too, so a
    caller can refuse to issue rather than discovering it on paper.
    """
    body = seed_templates.default_body_for("contract_payment_plan").body
    with tenant_ctx(brazos):
        artifact = rendering.render(
            template_code="contract_payment_plan",
            template_version=1,
            body=body,
            context={"customer_name": "R. Alvarez", "account_no": "ACC-1001"},
        )
    assert rendering.ABSENT_MARK in artifact.body
    assert "{schedule_table}" not in artifact.body
    assert "schedule_table" in [absence["token"] for absence in artifact.absences]
    assert "Do not sign this agreement if the schedule above is blank" in flat(artifact.body)


def test_cr011__the_payment_plan_body_states_the_nodrop_ruling_not_the_superseded_clause():
    """PO 2026-08-11, verbatim: *"nodrop we chase for payments until write
    off"*. A19 §3.3's default clause (*"plan voids on {missed_count} missed →
    full balance due"*) and r10's *"Miss an installment and the plan cancels"*
    both describe the product that ruling abolished."""
    body = seed_templates.default_body_for("contract_payment_plan").body
    assert "does not by itself cancel this plan" in flat(body)
    for gone in ("plan cancels", "voids", "full balance becomes due", "{missed_count}"):
        assert gone not in body, f"the payment-plan agreement states {gone!r}"


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE ACH AUTHORIZATION — the refusal IS the feature
# ══════════════════════════════════════════════════════════════════════════
def test_cr011__the_placeholder_is_labelled_and_refuses_to_render(brazos):
    """PO, 2026-08-18: *"Do it; put the details, I will handle it with user"*.

    Three properties, and dropping any one of them turns a safety feature into a
    bad default: it is VISIBLY a placeholder, it REFUSES to render, and it says
    WHY on its own face.
    """
    offered = seed_templates.default_body_for(PLACEHOLDER)
    assert seed_templates.is_placeholder(PLACEHOLDER) is True
    assert rendering.PLACEHOLDER_MARK in offered.body
    assert "NACHA" in offered.body
    assert "DO NOT SEND THIS TO A CUSTOMER" in flat(offered.body)

    with tenant_ctx(brazos):
        with pytest.raises(rendering.RenderRefused) as refusal:
            rendering.render(
                template_code=PLACEHOLDER,
                template_version=1,
                body=offered.body,
                context={"customer_name": "R. Alvarez"},
            )
    assert "NACHA" in str(refusal.value)

    # …and it is the MARKER that refuses, not the class: the utility clears it
    # by deleting one visible line, which is the act they can see themselves do.
    with tenant_ctx(brazos):
        cleared = rendering.render(
            template_code=PLACEHOLDER,
            template_version=1,
            body="You authorize {utility_name} to debit {payment_method}. {customer_signature}",
            context={"customer_name": "R. Alvarez"},
        )
    assert cleared.body


def test_cr011__the_placeholder_can_still_be_SAVED_which_is_how_a_utility_edits_it():
    """Refusing to RENDER is not refusing to hold. A utility keeps the text in
    front of themselves while their bank answers, so `validate_body` — the
    designer's save gate — accepts it."""
    offered = seed_templates.default_body_for(PLACEHOLDER)
    rendering.validate_body(PLACEHOLDER, offered.body)


def test_cr011__what_the_utility_must_supply_is_enumerated_in_plain_english():
    """**THE SECOND HALF OF THE RULING IS A DELIVERABLE, NOT A COURTESY.** The
    PO is taking this to a real customer, so *"paste your own wording"* is not
    an answer.

    Eight items, in one place, reaching three consumers: the document's own
    face, the renderer's refusal, and the screen.
    """
    items = catalogs.required_from_utility(PLACEHOLDER)
    assert len(items) == 8
    assert all(item.endswith(".") and len(item) > 40 for item in items)
    # No ID, no rule reference, no jargon a person would have to look up — this
    # is the standing PO instruction about how anything is put to them.
    for item in items:
        assert not re.search(r"\b(OQ|BR|US|DEF|CR)-\d", item), item

    body = seed_templates.default_body_for(PLACEHOLDER).body
    for item in items:
        assert item in body, "the placeholder must print the list on its own face"

    with pytest.raises(rendering.RenderRefused) as refusal:
        rendering.refuse_if_placeholder(PLACEHOLDER, body)
    for item in items:
        assert item in str(refusal.value)

    # And no bank number is ever a merge token — the customer writes those in.
    palette = catalogs.catalog_for(PLACEHOLDER).tokens
    assert not {token for token in palette if "routing" in token or "bank" in token}


def test_cr011__only_one_class_in_the_product_ships_a_placeholder():
    """A placeholder is a liability admission, not a shortcut. If a second class
    ever ships one, this goes RED and the lane has to say which ruling let
    them."""
    placeholders = {code for code in CONTRACTS if seed_templates.is_placeholder(code)}
    assert placeholders == {PLACEHOLDER}
    for entry in seed_templates.SEEDABLE:
        assert rendering.PLACEHOLDER_MARK not in entry.body, entry.code


# ══════════════════════════════════════════════════════════════════════════
# 4 · BR-NOT-002 — WHY NOTHING IS PUBLISHED, PROVED ON A REAL TENANT
# ══════════════════════════════════════════════════════════════════════════
def test_cr011__provisioning_publishes_no_contract_and_reports_all_four_as_offered(
    growth_plan, identity_seam
):
    """The CR, over its own ruling: *"Both are BR-NOT-002 effective-dated
    contracts, so a draft still needs an `effective_from` a human chooses;
    provisioning-day is not that date."*

    So a freshly provisioned tenant has thirty-three published notice templates
    and NOT ONE contract version — and the seeder reports the four as OFFERED,
    which is a different sentence from "absent" and points at a different job.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        answer = seed_templates.seed_notice_templates(None, on_date=ON_DATE)
        offered = {row["code"]: row for row in answer["offered"]}
        assert set(offered) == set(CONTRACTS)
        assert offered[PLACEHOLDER]["is_placeholder"] is True
        assert all("BR-NOT-002" in row["reason"] for row in answer["offered"])

        assert not tm.NotificationTemplateVersion.objects.filter(
            template__code__in=CONTRACTS
        ).exists(), "a contract version was published at provisioning — BR-NOT-002"

        # The absence sentence a screen shows now says there IS wording, which
        # is the difference between "go and write a contract" and "click twice".
        #
        # ⚠ **AMENDED 2026-08-30 — `"BR-NOT-002" in reason` MOVED OFF THE
        # SENTENCE AND ONTO ITS OWN FIELD (`DEF-630`, 2026-08-24).** These
        # reasons named their rule INSIDE the English and were rewritten into a
        # clerk's words, correctly — an operator reading *"no body: OQ-244"*
        # learns nothing, and an internal reference in served prose is the class
        # G28 exists to stop. The citation now travels as DATA:
        # `seed_templates.absent_refs(code)`, the same shape `br_ref=` travels
        # on a `core.errors` refusal. The `offered` row above keeps the rule in
        # its own `reason` because that string is an OPERATOR REPORT from the
        # seeder, not a sentence rendered in a table cell — which is why the
        # assertion on line 329 is untouched and only this one moved.
        for code in CONTRACTS:
            reason = seed_templates.absent_reason(code)
            assert "BR-NOT-002" in seed_templates.absent_refs(code)
            assert "BR-NOT-002" not in reason, (
                f"G28: {code}'s served sentence carries a rule id — it belongs "
                f"on `absent_refs`. Got: {reason!r}"
            )
            # The MEANING the CR asked for, asserted in the words DEF-630
            # rewrote it into: there IS wording, and the operator's next act is
            # to pick the date and publish — never "go and write a contract".
            lowered = reason.lower()
            assert "wording" in lowered
            assert "publish" in lowered, reason


def test_cr011__the_utility_adopts_the_default_with_their_own_date(brazos, marcus, dana):
    """**"…AND ALLOW USER TO CHANGE" — end to end, through the ordinary door.**

    Register, save the offered wording as a draft with the date THEY choose,
    publish it as the System Admin, and resolve it on a generation date. Nothing
    here is a special path: it is `save_draft` → `publish` → `resolve`, the same
    four calls every other class uses, with BR-NOT-002's date supplied by a
    person.
    """
    offered = seed_templates.default_body_for("contract_service_agreement")
    with tenant_ctx(brazos):
        template, _ = template_service.register(
            code="contract_service_agreement",
            name=offered.name,
            actor=marcus,
            category=tm.VARIANT_DEFAULT,
            language=tm.VARIANT_DEFAULT,
        )
        # The utility CHANGES it — the whole point of the ruling.
        edited = offered.body.replace(
            "By signing, you agree to the terms above.",
            "By signing, you agree to the terms above and to our tariff.",
        )
        draft = template_service.save_draft(
            template=template,
            body=edited,
            actor=marcus,
            effective_from=date(2026, 10, 1),
        )
        template_service.publish(version_row=draft, actor=dana)

        # BEFORE the date they chose there is NO version in force, and the
        # refusal is the ratified hold rather than "the closest body" — which is
        # the whole reason a contract is effective-dated (US-NOT-006 TC-3).
        with pytest.raises(template_service.TemplateRefused):
            template_service.resolve(
                code="contract_service_agreement", on_date=date(2026, 9, 30)
            )
        after = template_service.resolve(
            code="contract_service_agreement", on_date=date(2026, 10, 2)
        )
        pinned = template_service.load_pinned(
            template_id=after.template_id, version=after.version
        )
    assert after.version == draft.version
    assert "and to our tariff" in pinned.body
    assert pinned.effective_from == date(2026, 10, 1)


def test_cr011__the_seeder_itself_refuses_a_contract_structurally(brazos, dana):
    """**A CONVENTION IS NOT A GUARD (hard-won law 1).** "The four contracts are
    not in `SEEDABLE`" is a fact about a tuple, and a lane adding one there
    would break nothing: the palette exists, `validate_body` passes, and a
    published undated contract version appears on every tenant — after which
    `_published_version` returns OURS in front of every version the utility ever
    dates.

    So `_seed_one` refuses the whole CONTRACT group by name. Proved by calling
    it directly rather than by trusting the tuple.
    """
    entry = seed_templates.default_body_for("contract_deposit")
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as refusal:
            seed_templates._seed_one(entry, actor=dana, at=None)
    assert refusal.value.br_ref == "BR-NOT-002"
    assert "cannot be seeded" in refusal.value.params["detail"]


def test_cr011__a_contract_draft_without_a_date_is_still_refused(brazos, marcus):
    """The constraint that survives the ruling untouched, asserted so that a
    later lane cannot make seeding "work" by relaxing it."""
    with tenant_ctx(brazos):
        template, _ = template_service.register(
            code="contract_deposit",
            name="Deposit agreement",
            actor=marcus,
            category=tm.VARIANT_DEFAULT,
            language=tm.VARIANT_DEFAULT,
        )
        with pytest.raises(template_service.TemplateRefused, match="effective_from"):
            template_service.save_draft(
                template=template,
                body=seed_templates.default_body_for("contract_deposit").body,
                actor=marcus,
            )


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE RECORD — the arguments left quoted, and nothing started sending
# ══════════════════════════════════════════════════════════════════════════
def test_cr011__the_four_departing_arguments_are_quoted_not_deleted():
    """The discipline `plan_notice_void` and the three disconnect tiers already
    model in this file: an entry that argued at length, and correctly, does not
    vanish when a ruling overtakes it — a reader who remembers the argument must
    see what changed.

    Two of the four arguments are STILL TRUE as engineering facts (the repeating
    block; the NACHA scheme), which is exactly why deleting them would be the
    expensive kind of tidy.
    """
    assert catalogs.NOT_AUTHORED_BY_PO_RULING == {}
    source = flat((APP / "catalogs.py").read_text())
    assert "already answer - provide default and allow user to change" in source
    assert "Do it; put the details, I will handle it with user" in source
    assert "create this dont leave it open" in source
    for quoted in (
        "A CONTRACT SOMEBODY SIGNS, not a notice they read",
        "The terms a customer agrees to when they take service",
        "It would have to state when a deposit is returned",
        "A COMPLIANCE DOCUMENT",
    ):
        assert quoted in source, f"a departing argument was deleted rather than quoted: {quoted!r}"


def test_cr011__nothing_here_added_a_dispatch_path():
    """BR-NOT-013 stands: this slice authors WORDING. PO 2026-08-16, *"I already
    confirm it before it Queue them"*.

    Asserted structurally rather than by intent: the offered defaults are
    referenced only by the module that holds them and the read API that serves
    them. A queue writer, a sender or the dispatcher reaching for them would be
    a contract about to go out with nobody having pressed anything.
    """
    referencing = {
        path.name
        for path in APP.glob("*.py")
        if "CONTRACT_DEFAULTS" in path.read_text() or "default_body_for" in path.read_text()
    }
    assert referencing == {
        # where the wording lives …
        "seed_templates.py",
        # … the read API that serves it to the designer …
        "templates_api.py",
        # … and the catalog, which only NAMES them in the note explaining why
        # the four contracts are offered rather than published.
        "catalogs.py",
    }, referencing
    for module in ("dispatcher.py", "senders.py", "notices.py", "services.py"):
        assert "contract_" not in (APP / module).read_text().replace("contract_code", ""), module


def test_cr011__the_designer_is_served_the_offer_the_notice_and_the_requirements():
    """Hard-won law 2 — *built is not wired*. A default that reaches a Python
    file and no screen is a feature that does not exist. `GET
    /template-catalog/{code}` carries the body to pre-fill, the standing notice
    that it is a starting point, and — for the placeholder — the eight items.
    """
    for code in CONTRACTS:
        payload = templates_api._platform_default(code)
        assert payload is not None, code
        assert payload["body"] == seed_templates.default_body_for(code).body
        assert payload["notice"] == seed_templates.CONTRACT_DEFAULT_NOTICE
        assert payload["requires_effective_date"] is True
    assert len(templates_api._platform_default(PLACEHOLDER)["requires_from_utility"]) == 8
    assert templates_api._platform_default(PLACEHOLDER)["placeholder_marker"] == (
        rendering.PLACEHOLDER_MARK
    )
    # None for a class the platform PUBLISHES — an offer beside a live body
    # would be two sources for one document.
    assert templates_api._platform_default("receipt") is None


def test_cr011__the_default_notice_says_it_is_not_legal_advice():
    """`rights_footer.PLATFORM_DEFAULT_NOTICE`'s posture, applied to contracts:
    the platform wrote it, the utility owns it, and the product warrants
    nothing.

    ⚠ **AND IT IS STAFF-FACING.** Whether a signed contract page also carries a
    visible "reviewed with your own counsel" line is a yes/no the CR keeps for
    the PO with an exact sentence attached, *not assumed* — so no contract body
    carries one, and this asserts that too.
    """
    notice = seed_templates.CONTRACT_DEFAULT_NOTICE
    assert "not legal advice" in notice
    assert "effective-dated" in notice
    for code in CONTRACTS:
        body = seed_templates.default_body_for(code).body
        assert "legal advice" not in body.lower() or code == PLACEHOLDER


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-005@cr011i9 (12-governance/11-change-requests.md §"CR-011 item 9 · THE PO RULED ON BOTH FLAGGED CONTRACTS" + §"CR-011 · The Phase-4 decision batch" · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-002/004/013/016 · 12-governance/01-open-questions.md OQ-244/OQ-206 · apps/notifications/catalogs.py + seed_templates.py)
# generated: 2026-08-18 by the CR-011 item 9 lane
# checklist: A✔ B✔ C✔ D✔(the detail payload's `platform_default` block and the draft endpoint's `effective_from`) E=deferred(the SET-10 designer is the frontend lane's — the offer is SERVED and owed a screen; recorded in the lane's write-back) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every case below was proved RED first — the schedule guard by deleting `{schedule_table}` from the body (refused, quoting BR-NOT-016), the placeholder guard by rendering the shipped body (refused, quoting NACHA), the BR-NOT-002 case by seeding a contract into SEEDABLE (a published undated contract version appeared and the case failed)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

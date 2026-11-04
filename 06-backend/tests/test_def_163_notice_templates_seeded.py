# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the catalogue the seeded bodies are validated against) ·
#           US-NOT-006 (the version lifecycle they join) ·
#           US-NOT-010 (the reminder a tenant can finally send) ·
#           US-NOT-009 (the disconnect notice it still cannot) ·
#           US-TEN-001 (provisioning, which is where the rows now come from)
#           Screens: S8 → Notifications · S34 · S35
# Rules:    BR-NOT-001 (the `default` fallback variant is MANDATORY) ·
#           BR-NOT-006 (type × category × language) · BR-BIL-026 (only a
#           PUBLISHED version resolves; versions are append-only) ·
#           BR-BIL-027 (publishing is the System Admin's right — the seed does
#           not borrow it) · BR-TEN-013 (tenancy reaches notifications only
#           through a named seam) · BR-TEN-043 (the business date is passed in) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (audit)
# Tests:    this file
# Impacts:  apps/notifications/seed_templates.py ·
#           apps/notifications/services.seed_notice_templates ·
#           apps/tenancy/seams.seed_notice_templates ·
#           apps/tenancy/services._provision_inside_context ·
#           10-scripts/gates/required_rows.txt
# ───────────────────────────────────────────────────────
"""DEF-163 — no tenant had a notice template, and nothing could create one.

**THE DEFECT, VERBATIM:** *"NO TENANT HAS EVER HAD A NOTICE TEMPLATE, so every
disconnect notice and every dunning letter this product tries to generate is
REFUSED rather than queued."*

**WHY THE EXISTING TESTS COULD NOT HAVE CAUGHT IT**, and it is DEF-123's lesson
one module along: `test_us_not_006_template_lifecycle.py` calls `register` and
`save_draft` in its own setup and then proves the resolution order over the rows
it just made. **A test that supplies the row cannot discover that nothing else
supplies it.** So this file does the one thing those tests cannot — it provisions
a tenant through the REAL service and then asks the REAL resolver, with nothing
in between.

**AND IT DOES THE SECOND THING `test_def_123` DOES NOT.** A provisioning-time
change reaches a tenant when it is created and never afterwards (hard-won law 4
in its data form), so `test_def_163_tc3` builds the case a fresh-tenant test can
never see: a tenant whose notification tables are EMPTY — exactly the state of
every tenant provisioned before 2026-08-16 — and runs the repair door on it.

**THE BODIES ARE ASSERTED AGAINST THE SPEC FILE ITSELF** (TC-5). A notice body
is what a customer reads; if a later lane "improves" A13's wording in the
seeder, this test goes RED rather than the change reaching a customer.
"""

from __future__ import annotations

import pathlib
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import re

import pytest

from apps.notifications import catalogs, notices, seed_templates
from apps.notifications import template_models as tm
from apps.notifications import template_service
from apps.notifications.rendering import RenderRefused
from apps.tenancy import seams as tenancy_seams

from tests.isolation_helpers import assert_rls_scoped, requires_postgres
from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    live_tenant_context,
    rls,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — provisioning fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — the caller names the business date. Nothing in this file reads a
#: clock, and neither does the seeder it drives.
ON_DATE = date(2026, 8, 16)

#: DEF-630: what may never appear in a sentence an operator reads. Deliberately
#: the same vocabulary CLAUDE.md §Screen IDs defines — if the repo cites it by
#: ID, served prose must not.
_INTERNAL_REF = re.compile(
    r"\b(?:BR-[A-Z]{3}-\d+|US-[A-Z]{3}-\d+|EP-[A-Z]{3}-\d+|OQ-\d+|DEF-\d+|GT-\d+|CR-\d+|ADR-\d+)\b"
)

#: The signed source of both seeded bodies. Read at test time so the assertion
#: is against the DOCUMENT rather than against a second copy of it.
A13 = (
    pathlib.Path(__file__).resolve().parents[2] / "04-docs" / "01-spec" / "13-copy-and-microcopy.md"
)


def test_def_163_tc1__a_provisioned_tenant_can_resolve_the_platform_notice_bodies(
    growth_plan, identity_seam
):
    """**THE ASSERTION THAT WAS MISSING.** Sign up, then ask for the pin.

    Not *"the resolver resolves the rows I made"* — that was always covered and
    was always green while no utility on any deployment could send a letter.
    """
    tenant, result = provisioned_tenant()
    assert result["created"] is True

    with tenant_ctx(tenant):
        for code in ("dunning", "receipt"):
            resolved = template_service.resolve(code=code, on_date=ON_DATE)
            # BR-BIL-026: only a PUBLISHED version resolves, so a seeded DRAFT
            # would have left the tenant exactly as unable to send as no row.
            assert resolved.version == 1, code
            assert resolved.category == tm.VARIANT_DEFAULT, code
            assert resolved.language == tm.VARIANT_DEFAULT, code
            assert resolved.via == template_service.VIA_EXACT, code


def test_def_163_tc2__every_consumer_category_falls_back_to_the_seeded_variant(
    growth_plan, identity_seam
):
    """BR-NOT-001's *"fallback mandatory"*, over a tenant that has only it.

    A brand-new tenant has no category variants, so a residential, commercial,
    industrial or government account must all resolve the one seeded row. If
    they did not, a bulk reminder would send some letters and refuse others on
    the same tenant — the worst of the three failures, because a partially-sent
    run looks like a run that worked.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        seeded = template_service.resolve(code="dunning", on_date=ON_DATE)
        for category in tm.CATEGORIES:
            resolved = template_service.resolve(code="dunning", category=category, on_date=ON_DATE)
            assert resolved.template_id == seeded.template_id, category


def test_def_163_tc3__the_repair_door_fixes_a_tenant_provisioned_before_the_seeder(
    growth_plan, identity_seam
):
    """**THE CASE A FRESH-TENANT TEST CANNOT SEE**, and the reason this exists.

    Editing provisioning fixes nothing already deployed — hard-won law 4 in its
    data form. So the tenants that matter are the ones that already exist, and
    their state is exactly this: the tables are there and EMPTY.

    `manage.py seed_demo --tenant <subdomain>` is the operator door and it calls
    this same seam. Proved here from the refusal a real operator sees, through
    the repair, to a resolvable pin.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # Wind the tenant back to 2026-08-15: the lifecycle service exists, the
        # tables exist, and not one row was ever written.
        tm.NotificationTemplateVersion.objects.all().delete()
        tm.NotificationTemplate.objects.all().delete()

        with pytest.raises(template_service.TemplateRefused) as refusal:
            template_service.resolve(code="dunning", on_date=ON_DATE)
        # ⚠ AMENDED 2026-08-24 (DEF-630). This asserted the substring
        # "no published 'dunning' template resolves" and was RED on the branch,
        # because the refusal was rewritten into a clerk's English and the
        # technical phrasing is gone. The rewrite was right — `TemplateRefused`'s
        # own docstring says it exists to explain a break *"in a clerk's words"*
        # — so what is pinned now is what the operator must be able to ACT on,
        # not the sentence a developer once wrote.
        #
        # Four facts, and each is load-bearing for the repair this case proves:
        # WHICH class, WHICH audience and locale it looked under, WHICH date it
        # judged, and WHAT to do next. A refusal missing the last one sends an
        # operator to support.
        message = str(refusal.value)
        assert "dunning" in message
        assert "no published wording" in message
        assert "default" in message  # the category and locale it searched under
        assert ON_DATE.isoformat() in message  # the date it judged, not "today"
        assert "Publish a default version" in message  # the way out

        repaired = tenancy_seams.seed_notice_templates(None, on_date=ON_DATE)

        assert repaired is not None
        # ⚠ AMENDED 2026-08-17 (DEF-210). This read `== ["dunning", "receipt"]`
        # and the PO's authoring ruling took the library to twenty-eight, so the
        # literal pair became a stale count rather than a claim about repair.
        # What TC-3 is actually about is that the repair door plants EVERY class
        # the platform authors on a tenant that has none — so it asserts the
        # whole library, read from the seeder, and it stays true as the library
        # grows.
        assert [row["code"] for row in repaired["seeded"] if row["created"]] == [
            entry.code for entry in seed_templates.SEEDABLE
        ]
        resolved = template_service.resolve(code="dunning", on_date=ON_DATE)
        assert resolved.version == 1


def test_def_163_tc4__the_seed_is_insert_missing_and_a_re_run_writes_nothing(
    growth_plan, identity_seam
):
    """Idempotent in the `seed_chart_of_accounts` sense: a re-run is a REPAIR.

    *Safe* means it writes nothing, not that it writes a harmless duplicate: a
    second published undated version is refused by `uq_ntv_one_published_undated`
    and a second `(code, default, default)` variant by `uq_ntpl_variant` — but
    the guarantee that matters to a tenant is that a body they edited is never
    replaced by the platform's.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before_templates = tm.NotificationTemplate.objects.count()
        before_versions = tm.NotificationTemplateVersion.objects.count()

        again = seed_templates.seed_notice_templates(None, on_date=ON_DATE)

        # AMENDED 2026-08-17 (DEF-210) — was `== [True, True]`. Every seeded
        # class, not two of them: a re-run touches nothing.
        assert [row["already_present"] for row in again["seeded"]] == [
            True for _ in seed_templates.SEEDABLE
        ]
        assert all("insert-missing left it untouched" in row["reason"] for row in again["seeded"])
        assert tm.NotificationTemplate.objects.count() == before_templates
        assert tm.NotificationTemplateVersion.objects.count() == before_versions


def test_def_163_tc5__the_seeded_bodies_are_a13_word_for_word(growth_plan, identity_seam):
    """**The guard against a well-meaning improvement.**

    A notice body is what a customer reads, so the seeded strings are asserted
    against `04-docs/01-spec/13-copy-and-microcopy.md` ITSELF rather than
    against a second copy that could drift with them. Reword the seeder and this
    goes red; reword A13 and it goes red too, which is correct — a spec change
    to customer-facing copy should not reach a customer unnoticed.
    """
    spec = A13.read_text(encoding="utf-8")
    assert seed_templates.DUNNING_BODY in spec
    assert seed_templates.RECEIPT_BODY in spec

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        for code, body in (
            ("dunning", seed_templates.DUNNING_BODY),
            ("receipt", seed_templates.RECEIPT_BODY),
        ):
            resolved = template_service.resolve(code=code, on_date=ON_DATE)
            pinned = template_service.load_pinned(
                template_id=resolved.template_id, version=resolved.version
            )
            assert pinned.body == body, code


def test_def_163_tc6__a_seeded_body_is_one_the_ordinary_designer_would_accept(
    growth_plan, identity_seam
):
    """The seed writes its row directly (BR-BIL-027 — no human in a provisioning
    transaction) and must not thereby smuggle in a body the palette forbids.

    `validate_body` is US-NOT-005 TC-5's rule, and running it here proves the
    platform body clears the same bar a tenant's own save would: every token in
    the class catalogue, mandatory content present, `{usage}` never without
    `{unit}`.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        for code, body in (
            ("dunning", seed_templates.DUNNING_BODY),
            ("receipt", seed_templates.RECEIPT_BODY),
        ):
            template_service.rendering.validate_body(code, body)  # no raise = accepted

        # And the negative, so the check above is known to bite: a receipt body
        # carrying a meter number is refused, which is what a WHITELIST is for.
        with pytest.raises(RenderRefused):
            template_service.rendering.validate_body("receipt", "Meter {meter_no} was read.")


def test_def_163_tc7__the_disconnect_notice_is_absent_and_says_why(growth_plan, identity_seam):
    """**THE REFUSAL THIS LANE SHIPPED ON PURPOSE (OQ-243) — HALF OF IT IS OVER.**

    The SUPERSEDED single `disconnect_notice` class is still absent and still
    says why, and its reason is now STRUCTURAL rather than a missing ruling: A19
    §2 gives three tier bodies, a variant holds one, and BR-NOT-014 replaced this
    class with three. A body here would be a fourth disconnect wording with no
    tier and no ladder position.

    ⚠ **THE THREE TIERS ARE NO LONGER ABSENT (CR-007, 2026-08-17).** They were,
    citing OQ-253, until the PO ruled that the platform writes the rights
    footer — *"you build default langauge and let Utility user change it as they
    want"*. The assertions are INVERTED rather than deleted: this case now proves
    each tier IS seeded, which is the thing that was broken (no tenant on the
    platform could produce a disconnection notice at any tier).
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        answer = seed_templates.seed_notice_templates(None, on_date=ON_DATE)
        absent = {row["code"]: row["reason"] for row in answer["absent"]}
        refs = {row["code"]: set(row["refs"]) for row in answer["absent"]}

        # ⚠ AMENDED 2026-08-24 (DEF-630), AND THE AMENDMENT IS THE FIX.
        # These two lines used to read `assert "BR-NOT-014" in
        # absent["disconnect_notice"]` and `assert "OQ-244" in
        # absent["contract_payment_plan"]` — i.e. they asserted that an internal
        # reference appears in the sentence an OPERATOR reads. Both went red
        # when the reasons were rewritten into plain English, and the rewrite
        # was correct: a rule id in served prose is exactly what G28 forbids and
        # what DEF-645 has just finished removing from the audit screens.
        #
        # But the citations then existed only in code comments, so a test COULD
        # not check them and support could not reach them. `absent_refs` now
        # carries them as data. The pair below is therefore stronger than what
        # it replaces: the fact is asserted in the prose, the citation is
        # asserted on the row, and the third assertion pins that they stay
        # SEPARATE — which is the property that was silently lost and is what
        # made these two tests go red for the right change.
        assert "replaced by three separate notices" in absent["disconnect_notice"]
        assert "BR-NOT-014" in refs["disconnect_notice"]

        assert "only you can choose the date it takes effect" in absent["contract_payment_plan"]
        assert "OQ-244" in refs["contract_payment_plan"]

        # THE REGRESSION GUARD: no operator-facing reason may name a rule, an
        # open question, a defect, a story or a screen. Every absence still has
        # to be traceable, so each also carries at least one citation.
        leaked = {
            code: found
            for code, reason in absent.items()
            if (found := _INTERNAL_REF.findall(reason))
        }
        assert not leaked, f"internal references reached operator prose: {leaked}"
        untraced = sorted(code for code in absent if not refs[code])
        assert not untraced, f"absences nobody can trace back to a ruling: {untraced}"
        # ⚠ AMENDED 2026-08-17 (DEF-210). `email_past_due` and
        # `plan_notice_upcoming` were absent citing OQ-206 / OQ-207; the PO
        # ruled *"please define it for this product"* and both are now seeded,
        # so asserting their absence would assert the defect. The classes that
        # are STILL absent are the ones no authoring ruling can reach, and each
        # is asserted by the ID that would have to close it.
        assert "email_past_due" not in absent
        assert "plan_notice_upcoming" not in absent
        # INVERTED 2026-08-17 (CR-007): all three tiers are seeded now.
        for tier_code in (
            "disconnect_notice_10_day",
            "disconnect_notice_5_day",
            "disconnect_notice_48_hour",
        ):
            assert tier_code not in absent, tier_code
        # ⚠ AMENDED 2026-08-24 (DEF-630), and this one moved for a SECOND
        # reason on top of the plain-English rewrite: the class changed state.
        # `OQ-206`/`OQ-207` are about a class with NO TOKEN CATALOG at all
        # (`template_service` refuses a draft save quoting them). This class HAS
        # a catalog now — what it does not have is finished wording, because
        # BR-NOT-004 type ④ is NACHA-required for recurring ACH and that scheme's
        # text is not in this repo. So asserting OQ-206 here asserted a state the
        # class left; what is pinned instead is the state it is actually in, and
        # the fact an operator must act on — it is a PLACEHOLDER the renderer
        # refuses to print, not a body someone forgot to publish.
        assert "placeholder" in absent["contract_autopay_authorization"]
        assert "will not print it until you replace it" in absent["contract_autopay_authorization"]
        assert "BR-NOT-004" in refs["contract_autopay_authorization"]
        # ⚠ AMENDED 2026-08-18 (CR-009 C-14). `plan_notice_void` was absent
        # citing BR-PAY-016 ("no event left to announce"); the PO ruled its
        # default language authored anyway — verbatim *"you give default
        # language for the plan-void notice only"* — so asserting its absence
        # would assert against the ruling. INVERTED: it is seeded, and the
        # event it announces still has no writer (the 'nodrop' ruling stands),
        # which its catalog note and seed source both state.
        assert "plan_notice_void" not in absent
        # Bills and statements are BILLING's registry (B2 r10 #4) — reporting
        # them here would offer one document two homes.
        for billing_owned in ("bill_residential", "bill_commercial", "statement"):
            assert billing_owned not in absent

        # …and a 10-day notice now RESOLVES A BODY. It still refuses here, and
        # the reason it gives is the interesting part: the template is found and
        # the RECIPIENT is not, because `uuid.uuid4()` is not an account. Before
        # CR-007 the refusal was *"no published 'disconnect_notice' template
        # resolves"* on every tenant in the product; now the only way to see that
        # sentence is to archive the seeded version (which
        # `test_us_not_009_generation_refuses_when_no_disconnect_template_is_published`
        # does deliberately).
        with pytest.raises(Exception) as refusal:  # noqa: B017 — any refusal will do
            notices.generate_disconnect_notice(
                account_id=uuid.uuid4(),
                tier=notices.TIER_FIRST_10_DAY,
                balance=Decimal("1842.10"),
                cut_date=date(2026, 8, 26),
                on_date=ON_DATE,
                actor=None,
            )
        assert "no published 'disconnect_notice_10_day' template resolves" not in str(refusal.value)


def test_def_163_tc8__every_class_this_module_owns_is_either_seeded_or_explained(
    growth_plan, identity_seam
):
    """No class falls between the two lists.

    The failure this forbids is the quiet one: a class added to `catalogs` with
    no body and no reason would show a blank cell on the S8 card, which reads as
    *"nothing to say here"* rather than *"nobody has written this yet"*.
    """
    owned = {*catalogs.CATALOGS, *catalogs.CLASSES_WITHOUT_CATALOG} - set(
        template_service.BILLING_OWNED_CLASSES
    )
    seeded = {entry.code for entry in seed_templates.SEEDABLE}
    for code in sorted(owned):
        reason = seed_templates.absent_reason(code)
        if code in seeded:
            assert reason is None, code
        else:
            assert reason, f"{code} has no body and no reason — the blank-cell failure"


def test_def_163_tc9__the_seam_is_wired_and_answers_through_tenancy(growth_plan, identity_seam):
    """The SEAM, not the function — DEF-075's lesson.

    An optional seam whose implementer is absent answers None and provisioning
    commits anyway, which is exactly how a tenant ends up unable to send a
    letter with nothing going red. So this asserts the resolution itself.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assert tenancy_seams.resolve("notifications", "seed_notice_templates") is not None
        answer = tenancy_seams.seed_notice_templates(None, on_date=ON_DATE)
    assert answer is not None
    assert all(row["already_present"] for row in answer["seeded"])


def test_def_163_tc10__the_seeded_version_names_no_human_publisher(growth_plan, identity_seam):
    """`published_by` is NULL, and the NULL is the true answer.

    BR-BIL-027 gives publishing to a System Admin because it puts a page in
    front of every customer the template is assigned to. Nobody did that here —
    the platform planted its own body before any human signed in — so the row
    says nobody rather than naming an owner who has never read it.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        resolved = template_service.resolve(code="receipt", on_date=ON_DATE)
        row = tm.NotificationTemplateVersion.objects.get(
            template_id=resolved.template_id, version=resolved.version
        )
        assert row.published_by is None
        assert row.created_by is None
        assert row.status == tm.VERSION_PUBLISHED
        # Undated: BR-NOT-002's effective dating is the CONTRACT classes' and
        # this seeder plants none of them.
        assert row.effective_from is None


def test_def_163_tc11__the_seed_is_audited_and_says_where_the_body_came_from(
    growth_plan, identity_seam, audit_rows
):
    """CLAUDE.md rule 7. The audit row is where *who published this* is answered
    once `published_by` is NULL — and it names the SPEC the body was quoted
    from, so a reviewer can check the wording without reading this code."""
    provisioned_tenant()
    published = [
        row
        for row in audit_rows
        if row["action"] == "template.published"
        and row["entity_type"] == "notification_template_version"
    ]
    # ⚠ AMENDED 2026-08-17 (DEF-210) — was `== 2` and `spec_source.startswith
    # ("A13")` for every row. Twenty-six bodies are now AUTHORED rather than
    # quoted, so a blanket "every source starts with A13" would have forced the
    # authored rows to claim a spec that does not exist. The rule this test
    # protects is unchanged and is now stated for both kinds: **every published
    # seed row says where its words came from**, and a quote and an authored
    # body say different things.
    # ⚠ AMENDED 2026-10-22 (`DEF-CWP-10381`) — the Account access classes are
    # ALSO planted once per registry language (`seed_language_variants`), so
    # the one-per-class figure is asserted over the `default` variants and the
    # language variants are counted on their own.
    variants = [row for row in published if row["after"]["language"] != "default"]
    published = [row for row in published if row["after"]["language"] == "default"]
    # MERGE 2026-10-22: the agreement emails are language-seeded the same way.
    assert {row["after"]["code"] for row in variants} <= set(seed_templates.LANGUAGE_WORDING)
    assert len(published) == len(seed_templates.SEEDABLE)
    assert {row["after"]["code"] for row in published} == {
        entry.code for entry in seed_templates.SEEDABLE
    }
    quoted = {
        row["after"]["code"] for row in published if row["after"]["spec_source"].startswith("A13")
    }
    assert quoted == {"dunning", "receipt"}
    for row in published:
        assert row["after"]["source"] == "provisioning_seed"
        # ⚠ WIDENED 2026-08-18 (CR-009 C-14): a third source kind exists — the
        # plan-void notice, authored under its own dated ruling. The rule is
        # unchanged: every row says where its words came from, and a source
        # that is neither a quote nor a dated authoring stamp still fails.
        # ⚠ WIDENED 2026-10-22 (`DEF-CWP-10381`) to ANY dated authoring stamp,
        # which is what the sentence above already says the rule is. Listing
        # dates one by one had gone red on 2026-09-20 (the transfer lane's
        # "AUTHORED 2026-09-20") and would again for every lane-authored body,
        # the Account access ones of 2026-10-22 among them.
        assert row["after"]["spec_source"].startswith("A13") or re.search(
            r"AUTHORED \d{4}-\d{2}-\d{2}", row["after"]["spec_source"]
        ), row["after"]["spec_source"]
        assert row["actor_user_id"] is None or row["after"]["source"] == "provisioning_seed"


def test_def_163_tc12__a_utility_can_finally_produce_a_friendly_reminder(
    growth_plan, identity_seam, monkeypatch
):
    """**THE WHOLE POINT, END TO END.** Generate the letter, read the sentence.

    `generate_reminder(friendly)` renders the DUNNING class (BR-NOT-008 keeps
    the regulated tones on the disconnect class) and writes queue rows —
    nothing is sent, by PO ruling. Before this lane it refused for every tenant.

    The QUEUE WRITE is captured rather than executed: `outbound_messages.
    account_id` is a foreign key into CUSTOMERS' table and this fixture has no
    accounts, which is a fact about the fixture and not about the letter. What
    is under test is the link DEF-163 broke — resolve → load the pinned body →
    render — plus the PIN the queue row would carry, which is what makes the
    customer's copy reproducible three years later (BR-BIL-026). **The real
    write was proved on a live database against sample account AC-2026-00001;
    see this file's gates line.**
    """
    tenant, _ = provisioned_tenant()

    from apps.notifications import services as notification_services

    captured: dict[str, object] = {}

    class _Written:
        messages = (SimpleNamespace(id=uuid.uuid4()),)
        problems: tuple[dict[str, object], ...] = ()

    def _capture(**kwargs: object) -> object:
        captured.update(kwargs)
        return _Written()

    monkeypatch.setattr(notification_services, "queue_document", _capture)

    with tenant_ctx(tenant):
        result = notices.generate_reminder(
            account_id=uuid.uuid4(),
            balance=Decimal("412.80"),
            on_date=ON_DATE,
            actor=None,
            tone=notices.TONE_FRIENDLY,
            channels=("pdf_print",),
        )

    assert result.template_code == notices.CLASS_DUNNING
    assert result.skipped is False
    assert len(result.queued_message_ids) == 1
    # A13's own sentence, with the balance merged at 2dp beside its currency.
    assert "this is a friendly reminder that your account" in result.artifact.body
    assert "412.80" in result.artifact.body
    # BR-BIL-026 — the row is pinned to the EXACT version it rendered from, so a
    # reprint finds the same bytes rather than today's template.
    pin = captured["template"]
    assert pin.code == notices.CLASS_DUNNING
    assert pin.version == result.artifact.template_version == 1


@pytest.mark.isolation
@requires_postgres
def test_def_163_tc13__one_tenants_seeded_templates_never_reach_another(
    growth_plan, identity_seam, rls  # noqa: F811
):
    """Hard rule 1 — two provisioned tenants, two libraries, no crossing."""
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())

    # Counted inside each tenant's own context: with `app.tenant_id` unset the
    # policy matches nothing and an explicit `filter(tenant_id=…)` still returns
    # zero on a connection RLS applies to (DEF-GOV-4036). That is deny-by-
    # default, not a missing seed.
    #
    # ⚠ AND THE NUMBER IS `len(SEEDABLE)`, NOT A LITERAL. This asserted `== 2`,
    # which was right on 2026-08-16 when DEF-163 seeded exactly `dunning` and
    # `receipt`. The library is THIRTY-THREE today — the same two plus
    # thirty-one platform-authored bodies added under four PO rulings, the
    # largest being the twenty-eight of 2026-08-17 (*"please define it for this
    # product"*), BR-NOT-014's three disconnect tiers the same day, and the
    # plan-void notice on 2026-08-18. Naming the seeder's own catalogue keeps
    # the case about ISOLATION — two libraries, no crossing — and stops the
    # number rotting again the next time the Product Owner authors a notice.
    #
    # ⚠ AMENDED 2026-10-22 (merge, lane MERGE-EMAILS): since `CR-188`/`CR-190`
    # some classes are also planted once per registry language, which is more
    # ROWS for the same CLASSES — so the `default` variants are what is counted
    # against `SEEDABLE`, as `test_def_210` already does. This case runs on
    # PostgreSQL only (RLS), which is why no lane's SQLite run saw it go red.
    expected = len(seed_templates.SEEDABLE)
    with live_tenant_context(brazos.id):
        assert (
            tm.NotificationTemplate.objects.filter(
                tenant_id=brazos.id, language=tm.VARIANT_DEFAULT
            ).count()
            == expected
        )
    with live_tenant_context(lonestar.id):
        assert (
            tm.NotificationTemplate.objects.filter(
                tenant_id=lonestar.id, language=tm.VARIANT_DEFAULT
            ).count()
            == expected
        )

    for table in ("notification_templates", "notification_template_versions"):
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
        assert_rls_scoped(rls, table, owner=lonestar, intruder=brazos)

    # ⚠ **THE CATALOGUE-SIZE REMINDER IS LAST NOW, AND THAT IS THE FIX
    # (`DEF-GOV-6703`, 2026-09-25).** It used to stand FIRST, and when the
    # library grew from 33 to 44 it raised `assert 44 == 33` before a single
    # line above it ran — so **the only proof in this repo that one utility's
    # notice library cannot reach another's had not been performed since the
    # catalogue last grew**, while the case sat red in a suite nobody read
    # (hard-won law 7). A reminder about DOCUMENTATION must never gate a proof
    # of hard rule 1. It still fires, it still names the new number, and the
    # isolation verdict is already in hand when it does.
    #
    # 45 since 2026-09-27: `email_scheduled_report`, CR-142-BRC07 `P4.10`
    # (commit aff5f079d, 2.376.0) — a scheduled report tells the people it
    # names, with a link and not the file. Intended; said here as asked.
    # (DEF-NOT-9138: this pin read 44 and the isolation run went red on it.)
    #
    # 59 since 2026-10-22 (merge, lane MERGE-EMAILS). This pin read 45 and was
    # ALREADY red on the 2.594.3 tip at 51 — `staff_field_work`, SRV-5's four
    # (2026-10-04) and `email_high_usage_alert` (CR-182) were never said here,
    # because this case runs on PostgreSQL only. Now also the three CR-188
    # account-access emails with `portal_password_reset`, CR-189's three, and
    # CR-190's two agreement emails. All intended; `test_def_210` lists them.
    assert expected == 59, (
        f"the notice catalogue is {expected} classes, not 59 — if that is "
        "intended, say so here; the counts above follow the catalogue on "
        "purpose and have already been asserted"
    )


def test_def_163_tc14__the_seed_needs_a_tenant_context(growth_plan, identity_seam):
    """Hard rule 1 from the other side: no `app.tenant_id`, no write."""
    from core import errors

    with pytest.raises(errors.AuthError):
        seed_templates.seed_notice_templates(None, on_date=ON_DATE)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-163 (12-governance/10-defect-log.csv DEF-163 · 04-docs/01-spec/13-copy-and-microcopy.md §"Reminder / notice templates (previews)" + 04-docs/01-spec/19-document-templates.md §2/§3 + r8 revision · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-001/002/006/007 · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md US-NOT-005/006 + EP-NOT-03 US-NOT-009/010)
# generated: 2026-08-16 by story-coder (DEF-163 notice-template seeding lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half in this file — the endpoint's own assertions live in tests/test_us_not_004_settings_api.py) E=deferred(no-frontend-half — SettingsNotificationsTab.test.tsx covers the card) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (this file) 13 passed / 1 skipped on sqlite, and the isolation case 1 passed against live PostgreSQL 16 · the browser half is `07-frontend/e2e/DEF-163-notice-templates.spec.ts`, red-proved by removing the seeded rows from a booted stack (it failed on `toContainText(/Version 1/)` receiving the resolver's own refusal) and green again after `manage.py seed_demo --tenant brazosbend` · the RED state was proved on a LIVE tenant before the fix, not only in a fixture: a tenant provisioned from the pre-change worktree into PostgreSQL 16 answered `no published 'dunning' template resolves for category 'default' in language 'default'` for all four classes, `manage.py seed_demo --tenant pecangrove` repaired it, and the same probe then resolved dunning v1 and receipt v1 while the disconnect notice still refused by name
# exceptions: (1) TC-12 stubs `_recipients_for`, which is a CUSTOMERS read and
#         not the thing under test; the live-database run above did it for real,
#         on sample account AC-2026-00001, and printed the rendered sentence.
#         (2) NO TEST ASSERTS A SENT MESSAGE. Nothing dispatches in this release
#         (BR-NOT-013); generation ends at a queue row.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

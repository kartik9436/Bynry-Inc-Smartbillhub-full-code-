# ── Trace ──────────────────────────────────────────────
# Story:    CR-007 (SET-09 template catalog · SET-10 template detail, preview,
#           variant management, editing and versioning)
#           Screens: SET-09 · SET-10
# Rules:    BR-NOT-001 · BR-NOT-006 · BR-NOT-014 (three disconnect slots) ·
#           BR-NOT-015 (the rights footer's sentences are not ours to invent) ·
#           BR-NOT-005 (queue only; NO send endpoint) · BR-BIL-026 (an edit is a
#           new version) · BR-BIL-027 (System Admin publishes) · BR-SHL-011
#           (list grammar) · BR-SHL-025 (disabled WITH its reason, never
#           hidden) · BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1 ·
#           CLAUDE.md rule 4 (a published body is evidence) · rule 7 (audited)
# ───────────────────────────────────────────────────────
"""SET-09/SET-10 over HTTP, on the cases CR-007 declares.

Read `test_cr_007__an_unknown_merge_token_blocks_the_save_with_an_inline_error`
first: it is the CR's own rule (*"Merge fields validated on save — unknown token
blocks save with inline error"*) and it is the one a System Admin meets. The
refusal comes from `rendering.validate_body` — the SAME check the seeder and
every queued render go through — and arrives as a FIELD error on `body`, so the
editor puts it under the box the token was typed into rather than in a banner.

Read `test_cr_007__the_disconnect_notice_has_three_slots_and_every_one_is_empty`
second. BR-NOT-014 gave the disconnection notice three slots on 2026-08-16 and
until this lane **the code still held one**; the slots now exist, are listed,
open, and refuse every save by name, because BR-NOT-015's rights footer has five
sentences no signed document writes (OQ-250). Three slots and no wording is the
honest state, and the test asserts both halves so neither can quietly change.

Every path is resolved through the REAL root URLconf first: an `api.py` that
exports `urlpatterns` is not an endpoint until `config/urls.py` includes it
(DEF-112 / DEF-128, four times in this repository).
"""

from __future__ import annotations

import pytest
from django.urls import Resolver404, resolve

from apps.notifications import catalogs
from apps.notifications import template_models as tm
from apps.notifications import template_service, templates_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_actions, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: A13's own reminder preview, the body `seed_templates` plants verbatim. Used
#: here because it is the one body this platform has actually written — a test
#: that invented one would be testing wording nobody signed.
DUNNING_BODY = (
    "Hi {first_name}, this is a friendly reminder that your account {account} has a "
    "balance of {balance}. You can pay online at any time. Thanks for being a customer."
)


def _get(view, tenant, actor, role="system_admin", query=None, **kwargs):
    return api_call(
        view,
        "get",
        user=getattr(actor, "user", None),
        role=role,
        tenant=tenant,
        query=query,
        **kwargs,
    )


def _post(view, tenant, actor, data, role="system_admin", **kwargs):
    return api_call(
        view,
        "post",
        user=getattr(actor, "user", None),
        role=role,
        tenant=tenant,
        data=data,
        **kwargs,
    )


def _variant(actor, code, *, name="Template", category=None, language=None):
    # DEF-207: `register` reports `(row, created)`. The helper keeps returning
    # the row alone, because every caller here wants the row; the tests that
    # care about `created` call `register` directly and say so.
    row, _created = template_service.register(
        code=code,
        name=name,
        actor=actor,
        category=category or tm.VARIANT_DEFAULT,
        language=language or tm.VARIANT_DEFAULT,
    )
    return row


# ── the routes exist at all ────────────────────────────────────────────────
def test_cr_007__all_nine_paths_resolve_through_the_root_urlconf():
    """DEF-128's lesson, applied before anything else is asserted.

    ⚠ **THIS WAS `…all_eight_paths…` UNTIL CR-048 B7 ADDED THE NINTH.** The
    count is in the NAME, so it is a figure that goes stale silently the moment
    a route is added and the list below is edited without it — the same shape as
    the three counts CR-048 has already had to re-derive. Renamed with the
    route rather than left to decay.
    """
    base = "/api/brazosbend/template-catalog"
    assert resolve(base).func is templates_api.template_catalog
    assert resolve(f"{base}/dunning").func is templates_api.template_detail
    assert resolve(f"{base}/dunning/variants").func is templates_api.add_variant
    assert resolve(f"{base}/dunning/preview").func is templates_api.preview_body
    assert resolve(f"{base}/dunning/draft").func is templates_api.save_draft
    assert resolve(f"{base}/dunning/publish").func is templates_api.publish_version
    assert resolve(f"{base}/dunning/deactivate").func is templates_api.deactivate_variant
    assert resolve(f"{base}/dunning/restore").func is templates_api.restore_version
    assert resolve(f"{base}/dunning/queue-test").func is templates_api.queue_template_test


def test_cr_007__no_send_endpoint_is_minted_by_this_surface():
    """BR-NOT-005 / A11 Addendum r2 §4: *"no synchronous send endpoint anywhere
    (queue only)"*. CR-007 asks for "Send test to me" and this asserts its
    ABSENCE, so the rule stays visible rather than depending on nobody adding
    one later.

    ⚠ **CR-048 B7 BUILT THE BUTTON AND THIS CASE IS UNCHANGED AND STILL RIGHT.**
    The route it added is `queue-test`, because it QUEUES: one real row on the
    outgoing queue and no provider call anywhere. The three spellings below are
    the ones that would claim otherwise, and their absence is the rule.
    """
    for path in (
        "template-catalog/dunning/send",
        "template-catalog/dunning/test-send",
        "template-catalog/dunning/send-test",
    ):
        with pytest.raises(Resolver404):
            resolve(f"/api/brazosbend/{path}")


# ── SET-09 · the catalog ───────────────────────────────────────────────────
def test_cr_007__the_catalog_lists_every_class_in_the_five_cr_categories(brazos, dana):
    """CR-007's chips, verbatim: *"All · Billing · Collections · Payments ·
    Service & field · Account lifecycle"*."""
    with tenant_ctx(brazos):
        response = _get(templates_api.template_catalog, brazos, dana)
    assert response.status_code == 200
    assert response.data["count"] == len(catalogs.listable_codes())
    assert [chip["key"] for chip in response.data["categories"]] == list(catalogs.CR_CATEGORIES)
    # Every listed row files under one of the five. A row with a category the
    # chips do not offer is a row nobody can filter to.
    assert {row["category"] for row in response.data["results"]} <= set(catalogs.CR_CATEGORIES)


def test_cr_007__bills_are_not_on_this_catalog_and_the_refusal_says_where_they_are(brazos, dana):
    """B2 r10 #4 gives bills and statements their own registry and their own
    chooser. Listing them here would offer one document two homes — so the
    catalog omits them and the DETAIL route names the tab they live on."""
    with tenant_ctx(brazos):
        listed = _get(templates_api.template_catalog, brazos, dana)
        codes = {row["code"] for row in listed.data["results"]}
        assert codes.isdisjoint(template_service.BILLING_OWNED_CLASSES)
        refused = _get(templates_api.template_detail, brazos, dana, code="bill_residential")
    assert refused.status_code == 422
    assert "Bill layout" in refused.data["params"]["detail"]


def test_cr_007__search_and_the_category_chip_filter_the_same_list(brazos, dana):
    """BR-SHL-011: `q` and `f.category`, and an unknown value FALLS BACK rather
    than erroring."""
    with tenant_ctx(brazos):
        collections = _get(
            templates_api.template_catalog,
            brazos,
            dana,
            query={"f.category": catalogs.CAT_COLLECTIONS},
        )
        searched = _get(templates_api.template_catalog, brazos, dana, query={"q": "outage"})
        nonsense = _get(
            templates_api.template_catalog,
            brazos,
            dana,
            query={"f.category": "not-a-category", "sort": "not-a-column", "per": "77"},
        )
    assert collections.data["count"] > 0
    assert all(row["category"] == catalogs.CAT_COLLECTIONS for row in collections.data["results"])
    assert [row["code"] for row in searched.data["results"]] == ["service_outage_notice"]
    # Fall back, never error: the bad filter is ignored, the bad sort falls to
    # the default, and 77 clamps DOWN to 50 (never granting more than asked).
    assert nonsense.status_code == 200
    assert nonsense.data["count"] == len(catalogs.listable_codes())
    assert nonsense.data["per"] == 50


def test_cr_007__the_service_and_field_category_ships_with_its_four_templates(brazos, dana):
    """PO ruling 2026-08-16, verbatim: *"CR-007's 'Service & field' template
    category — appointment, work completed, door hanger, outage — is wording,
    and wording can exist before the flow that sends it. Those templates are
    catalogued and editable now."*

    They create NO work-order table and do not touch OQ-249: the Used-by column
    says the wording is ready and the flow is not, rather than implying a flow
    that exists. ⚠ It says that in the CUSTOMER's words since CR-016 — it used to
    name the release and the open question, on a screen a utility reads.
    """
    with tenant_ctx(brazos):
        response = _get(
            templates_api.template_catalog,
            brazos,
            dana,
            query={"f.category": catalogs.CAT_SERVICE_FIELD},
        )
    codes = {row["code"] for row in response.data["results"]}
    # ⚠ **FOUR BECAME EIGHT ON 2026-10-04 (`2.517.0`, `CR-168-BRC10` P6.1,
    # lane SRV-5)** — ruling 3's visit told on the channels the customer chose:
    # *visit moved* by email, and booked / moved / on the way by text. And the
    # ruling this case protects — wording before the flow — now holds for TWO
    # of the eight, not four: assignment, departure and acceptance send the
    # other six, so their Used-by says when it is sent, and saying *"not
    # switched on yet"* there would be a held control over a live flow (law 2).
    assert codes == {
        "service_appointment",
        "service_work_completed",
        "service_door_hanger",
        "service_outage_notice",
        "service_visit_moved",
        "sms_visit_booked",
        "sms_visit_moved",
        "sms_technician_on_the_way",
        # `DEF-WRK-10652` (PO 2026-10-29, ruling 1A) — *Work order logged*, a
        # job with a customer raised without a date; sent at the raise.
        "service_work_order_logged",
        "sms_work_order_logged",
    }
    sent_now = codes - {"service_door_hanger", "service_outage_notice"}
    for row in response.data["results"]:
        if row["code"] in sent_now:
            assert row["used_by"].startswith("Sent when"), row
            assert row["body_unavailable"] is None
            assert row["has_published"] is True
            continue
        # ⚠ AMENDED AGAIN 2026-08-19 (CR-016). This read
        # `assert "R5" in row["used_by"] and "OQ-249" in row["used_by"]`, and it
        # is the clearest example in the repo of the escape reason CR-016 was
        # filed for: `used_by` is rendered VERBATIM in the "Used by" column of
        # Settings → Configure → Templates, so this test made an INTERNAL
        # RELEASE NAME and an OPEN-QUESTION ID a REQUIREMENT of a screen a
        # utility System Admin reads. The Product Owner photographed that
        # column: *"Youa re also adding internal content and BR codes on screen,
        # that is not required"*.
        #
        # WHAT THE TEST WAS PROTECTING IS KEPT, because it is a real ruling —
        # *"wording can exist before the flow that sends it"* — and it is the
        # CLAIM, not the vocabulary, that matters. The column must still say the
        # wording is ready and the flow is not.
        assert "wording is ready" in row["used_by"]
        assert "not switched on yet" in row["used_by"]
        # …and it must not carry our vocabulary back onto the screen (G28).
        assert "OQ-" not in row["used_by"]
        assert "R5" not in row["used_by"]
        # ⚠ AMENDED 2026-08-17 (DEF-210). This asserted the four were EMPTY,
        # citing OQ-254 (written here as OQ-251, itself a stale id). The PO then
        # ruled *"please define it for this product"* and all four are authored
        # and published, so the assertion is inverted: what the PO's OTHER
        # ruling protects is that WORDING may exist before the FLOW — and now
        # there is a body to go with it. No work-order table was created by
        # either ruling.
        assert row["body_unavailable"] is None
        assert row["has_published"] is True


# ── BR-NOT-014 · three slots, and every one of them empty ──────────────────
def test_cr_007__the_disconnect_notice_has_three_slots_and_every_one_is_empty(brazos, dana):
    """BR-NOT-014 (PO 2026-08-16 closing OQ-243), verbatim: *"a  Give the
    disconnection notice three separate slots — one per stage"*.

    Both halves are asserted because they are separately losable:

      * THREE slots exist and the superseded single class is NOT among them —
        a fourth row would be the collapse this ruling exists to prevent;
      * every slot now HAS a body — amended 2026-08-17. This half used to read
        *"every slot is EMPTY and names OQ-253"*, which was correct for one day:
        BR-NOT-015 made the rights footer a platform default and said its
        sentences were not that ruling's to invent, so nothing could validate.
        **The PO then ruled who writes them** — *"you build default langauge and
        let Utility user change it as they want"* (CR-007) — the five clauses
        live in `apps/notifications/rights_footer.py`, and each tier is seeded.
        The assertion is INVERTED rather than deleted, so a lane that empties a
        tier again goes red.
    """
    with tenant_ctx(brazos):
        response = _get(
            templates_api.template_catalog,
            brazos,
            dana,
            query={"f.category": catalogs.CAT_COLLECTIONS},
        )
    codes = {row["code"] for row in response.data["results"]}
    assert {
        "disconnect_notice_10_day",
        "disconnect_notice_5_day",
        "disconnect_notice_48_hour",
    } <= codes
    assert "disconnect_notice" not in codes  # the superseded single slot
    for row in response.data["results"]:
        if row["code"].startswith("disconnect_notice_"):
            # ⚠ INVERTED 2026-08-17 (CR-007). This asserted `"OQ-253" in
            # row["body_unavailable"]` and `has_published is False` — the empty
            # state — and the consequence, measured and put to the PO in plain
            # English, was that NO DISCONNECTION NOTICE COULD BE PRODUCED ON ANY
            # TENANT. The PO ruled that the platform writes the five rights
            # sentences and a utility overrides them, so every tier is seeded and
            # publishable. Kept as an assertion rather than removed: a tier that
            # loses its body again fails here.
            assert row["body_unavailable"] is None, row["code"]
            assert row["has_published"] is True, row["code"]


def test_cr_007__each_disconnect_tier_carries_only_its_own_signed_tokens(brazos, dana):
    """A19 §2 writes one sentence per tier and the whitelist is the mechanism.

    A 10-day WARNING that could carry `{48h}` and `{certified_no}` is a 10-day
    warning that can be written as a 48-hour certified letter — which is exactly
    what the three slots exist to make impossible.
    """
    with tenant_ctx(brazos):
        ten_day = _get(templates_api.template_detail, brazos, dana, code="disconnect_notice_10_day")
        final = _get(templates_api.template_detail, brazos, dana, code="disconnect_notice_48_hour")
    assert "pay_by_date" in ten_day.data["merge_fields"]
    assert "48h" not in ten_day.data["merge_fields"]
    assert "certified_no" not in ten_day.data["merge_fields"]
    assert {"48h", "certified_no", "cut_date"} <= set(final.data["merge_fields"])
    # US-NOT-007 TC-6 — the regulatory footer token can never be removed, and
    # since CR-007 there are TWO non-removable phrases rather than one: the
    # regulator's reference, and the rights paragraph that tells the customer
    # what to do with it (BR-NOT-015).
    assert final.data["mandatory_content"] == ["{state_puc_ref}", "{rights_footer}"]
    # And `{rights_footer}` is on EVERY tier, not only the certified one.
    assert "rights_footer" in ten_day.data["merge_fields"]


def test_cr_007__a_disconnect_tier_refuses_a_body_without_its_mandatory_content(
    brazos, dana, marcus
):
    """A19 §2's tier-1 sentence ALONE is still not a publishable notice.

    ⚠ **RENAMED AND RE-AIMED 2026-08-17 (CR-007).** It was
    `…_refuses_every_save_and_names_oq_250` and its point was that NOTHING could
    be saved on this class while the rights footer was unwritten — and its ID was
    wrong twice over (OQ-250 is CR-005's counter-pad question; the rights-footer
    row is OQ-253, and OQ-253 itself means two different things — DEF-226).

    The footer is now written and the class is seeded, so "refuses every save" is
    no longer true and asserting it would be asserting a defect. What survives is
    the rule underneath, which is the durable half: `mandatory_content` refuses a
    body missing `{state_puc_ref}` OR `{rights_footer}` (US-NOT-007 TC-6 +
    BR-NOT-015). A System Admin who deletes either one and saves is stopped, and
    the refusal names what is missing.
    """
    with tenant_ctx(brazos):
        variant = _variant(marcus, "disconnect_notice_10_day", name="10-day warning")
        response = _post(
            templates_api.save_draft,
            brazos,
            dana,
            {
                "variant": str(variant.pk),
                # A19 §2 tier 1, verbatim — and still not publishable.
                "body": (
                    "Your account is past due in the amount of {balance}. Please pay by "
                    "{pay_by_date} (10 days) to avoid service interruption."
                ),
            },
            code="disconnect_notice_10_day",
        )
    assert response.status_code == 422
    assert "{state_puc_ref}" in response.data["params"]["detail"]


# ── SET-10 · editing, and the rule that blocks a bad save ──────────────────
def test_cr_007__an_unknown_merge_token_blocks_the_save_with_an_inline_error(brazos, dana, marcus):
    """CR-007, verbatim: *"Merge fields validated on save — unknown token blocks
    save with inline error"*, which is US-NOT-005 TC-5 asked again by the PO.

    `{meter_no}` is not in the receipt class's palette — a receipt states a
    transaction, not a meter — so the save is refused and the error arrives on
    the `body` FIELD so the editor can put it under the box.
    """
    with tenant_ctx(brazos):
        # `register` is idempotent, so this returns the variant PROVISIONING
        # already planted — `receipt` is one of the two classes with a platform
        # body (DEF-163) and the test works against the real seeded state.
        variant = _variant(marcus, "receipt", name="Payment receipt")
        before = tm.NotificationTemplateVersion.objects.filter(template=variant).count()
    response = _post(
        templates_api.save_draft,
        brazos,
        dana,
        {
            "variant": str(variant.pk),
            "body": "Thanks {first_name}, we received {amount} for meter {meter_no}.",
        },
        code="receipt",
    )
    assert response.status_code == 422
    assert "meter_no" in response.data["params"]["detail"]
    assert [err["field"] for err in response.data["field_errors"]] == ["body"]
    # Nothing was written. A refused save that left a draft behind would put an
    # unrenderable body one click from publish.
    with tenant_ctx(brazos):
        assert tm.NotificationTemplateVersion.objects.filter(template=variant).count() == before


def test_cr_007__an_edit_creates_a_new_version_and_publishing_archives_the_old(
    brazos, dana, marcus, audit_rows
):
    """BR-BIL-026 + BR-BIL-027 through the CR's own two buttons.

    The worked shape: v1 published, an edit saves v2 as a DRAFT while v1 keeps
    rendering, publishing v2 archives v1, and v1 is retained forever because
    every message already sent is pinned to it (CLAUDE.md rule 4).
    """
    with tenant_ctx(brazos):
        # The seeded `dunning` variant, with the platform-published version
        # provisioning planted (DEF-163).
        variant = _variant(marcus, "dunning", name="Past-due reminder")
        live = tm.NotificationTemplateVersion.objects.get(
            template=variant, status="published", effective_from__isnull=True
        )

    edit = _post(
        templates_api.save_draft,
        brazos,
        dana,
        {"variant": str(variant.pk), "body": DUNNING_BODY + " Questions? Call us."},
        code="dunning",
    )
    assert edit.status_code == 201
    assert edit.data["version"] == live.version + 1
    assert edit.data["status"] == "draft"
    with tenant_ctx(brazos):
        # The live version is untouched and keeps rendering until somebody
        # publishes the draft — BR-BIL-026: publishing affects FUTURE renders.
        live.refresh_from_db()
        assert live.status == "published"

    published = _post(
        templates_api.publish_version,
        brazos,
        dana,
        {"version_id": edit.data["id"]},
        code="dunning",
    )
    assert published.status_code == 200
    assert published.data["status"] == "published"
    with tenant_ctx(brazos):
        live.refresh_from_db()
        assert live.status == "archived"
    # Hard rule 7 — every one of those actions wrote an audit row.
    assert {"template.saved", "template.published"} <= set(audit_actions(audit_rows))


def test_cr_007__restore_creates_a_new_draft_and_never_rewrites_history(brazos, dana, marcus):
    """CR-007: *"version history list with restore; audit-logged"*.

    Restoring v1 produces v3 holding v1's body. v1 is NOT re-opened — migration
    0006's trigger freezes a non-draft version's body, and rule 4 is why: v1 is
    evidence of what a customer was sent.
    """
    with tenant_ctx(brazos):
        variant = _variant(marcus, "dunning", name="Past-due reminder")
        original = tm.NotificationTemplateVersion.objects.get(
            template=variant, status="published", effective_from__isnull=True
        )
        latest = template_service.save_draft(
            template=variant, body=DUNNING_BODY + " CHANGED.", actor=marcus
        )

    restored = _post(
        templates_api.restore_version,
        brazos,
        dana,
        {"version_id": str(original.pk)},
        code="dunning",
    )
    assert restored.status_code == 201
    assert restored.data["version"] == latest.version + 1
    assert restored.data["status"] == "draft"
    assert restored.data["restored_from_version"] == original.version
    assert restored.data["body"] == DUNNING_BODY
    with tenant_ctx(brazos):
        # History is NOT rewritten: the source row is byte-identical and still
        # published, so every message pinned to it renders what it always did.
        original.refresh_from_db()
        assert original.body == DUNNING_BODY and original.status == "published"


# ── variant management ─────────────────────────────────────────────────────
def test_cr_007__a_variant_is_added_and_the_default_one_is_marked(brazos, dana, marcus):
    """CR-007's *"add variant (name + language + audience note)"*. The audience
    IS the consumer category — BR-NOT-001's four values plus the mandatory
    `default` — and the default variant is the row whose category and language
    are both the sentinel, marked by the SERVER (OQ-252 option (a))."""
    with tenant_ctx(brazos):
        _variant(marcus, "dunning", name="Past-due reminder")
        added = _post(
            templates_api.add_variant,
            brazos,
            dana,
            {"name": "Past-due reminder · Spanish", "language": "es-MX", "category": "commercial"},
            code="dunning",
        )
        assert added.status_code == 201
        assert added.data["is_default"] is False
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    defaults = [row for row in detail.data["variants"] if row["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["language"] == "default"
    # OQ-252 — "set default" would be a RE-KEY, so it is disabled with its
    # reason rather than hidden (BR-SHL-025).
    assert detail.data["can_set_default"] is False
    # ⚠ DEF-335 — THIS ASSERTION USED TO READ `"OQ-252" in set_default_reason`,
    # which is a test PINNING the internal sentence the PO photographed. The
    # reason is what a utility reads and must name no id; the provenance moved
    # to the machine field, and both halves are asserted so neither can drift.
    assert "OQ-252" not in detail.data["set_default_reason"]
    assert "BR-" not in detail.data["set_default_reason"]
    assert "OQ-252" in detail.data["set_default_br_ref"]
    # CR-048 wave I — and the sentence is no longer DRAWN inline. Three words on
    # screen, the whole sentence on hover. Both asserted: a label with no
    # reachable reason is a control that refuses and will not say why, which is
    # BR-SHL-025's exact prohibition and a worse defect than the paragraph.
    assert detail.data["set_default_label"] == "Default is fixed"
    assert len(detail.data["set_default_label"].split()) <= 4
    assert "OQ-" not in detail.data["set_default_label"]
    assert detail.data["set_default_reason"].startswith("You cannot change")


def test_cr_007__re_adding_an_existing_variant_reports_a_FETCH_not_a_creation(brazos, dana, marcus):
    """DEF-207 — found by clicking, and it is a lie the screen tells, not a bug.

    `register` is `get_or_create` on `(code, category, language)` and that
    IDEMPOTENCY IS CORRECT: two clicks must not mint two "Spanish commercial"
    variants holding different published bodies. What was wrong is the REPORT of
    it — the route answered a bare **201 Created** either way and echoed the
    EXISTING row, so typing "Large print" over a variant that already existed
    produced *"Variant 'Past-due reminder · Spanish' created."* and created
    nothing. Nothing is corrupted; the person's model of their own catalog is.

    The walkthrough found it BY ACCIDENT, when a second run failed on a name the
    first run had supposedly created — which is the shape of defect no assertion
    over a single call can see. So this test makes the second call explicitly.
    """
    with tenant_ctx(brazos):
        _variant(marcus, "dunning", name="Past-due reminder")
        body = {"name": "Past-due reminder · Spanish", "language": "es-MX", "category": "commercial"}

        first = _post(templates_api.add_variant, brazos, dana, body, code="dunning")
        assert first.status_code == 201, "the first add really does create"

        # Same key, DIFFERENT name — this is exactly the user's mistake.
        again = _post(
            templates_api.add_variant,
            brazos,
            dana,
            {"name": "Large print", "language": "es-MX", "category": "commercial"},
            code="dunning",
        )
        assert again.status_code == 200, (
            "re-adding an existing variant is a FETCH; 201 here is the screen "
            "telling a person something was created when nothing was (DEF-207)"
        )
        # …and it is honest about WHICH row it is: the one that already existed,
        # under its own name, not the name that was just typed.
        assert again.data["name"] == "Past-due reminder · Spanish"
        assert again.data["id"] == first.data["id"]

        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    es = [
        row
        for row in detail.data["variants"]
        if row["language"] == "es-MX" and row["category"] == "commercial"
    ]
    assert len(es) == 1, "the idempotency itself is unchanged — still exactly one"


def test_cr_007__a_variant_in_use_is_deactivated_and_its_consumers_are_named(brazos, dana, marcus):
    """CR-007: *"a variant in use by a notification rule can't be deleted —
    deactivate only, with usage warning listing consumers"*.

    Deactivating archives the live version; resolution then falls through to
    the `(default, default)` variant, which BR-NOT-006 makes a ratified answer
    and never a blank. The version is retained forever.
    """
    with tenant_ctx(brazos):
        base = _variant(marcus, "dunning", name="Past-due reminder")
        base_live = tm.NotificationTemplateVersion.objects.get(
            template=base, status="published", effective_from__isnull=True
        )
        spanish = _variant(marcus, "dunning", name="Past-due reminder ES", language="es-MX")
        es_v1 = template_service.save_draft(template=spanish, body=DUNNING_BODY, actor=marcus)
        template_service.publish(version_row=es_v1, actor=dana)

    response = _post(
        templates_api.deactivate_variant,
        brazos,
        dana,
        {"variant": str(spanish.pk)},
        code="dunning",
    )
    assert response.status_code == 200
    assert response.data["variant"]["active"] is False
    assert response.data["version"]["status"] == "archived"
    assert "consumers" in response.data
    assert "never deleted" in response.data["consumers"]["detail"]
    with tenant_ctx(brazos):
        # The row survives — archived, not gone (CLAUDE.md rule 4).
        es_v1.refresh_from_db()
        assert es_v1.status == "archived"
        # And a Spanish-preferring account still gets a letter: resolution falls
        # through to the (default, default) variant. BR-NOT-006, verbatim:
        # "missing variant → tenant-default fallback, NEVER a blank."
        fallback = template_service.resolve(code="dunning", language="es-MX")
        assert fallback.version == base_live.version
        assert fallback.language == "default"


# ── preview ────────────────────────────────────────────────────────────────
def test_cr_007__the_preview_renders_through_the_real_engine_with_sample_data(brazos, dana, marcus):
    """CR-007: *"Live preview pane showing the actual rendered artifact with
    sample data"*.

    It is the SAME renderer a queued message goes through — so the money is
    formatted at the tenant's currency and the tokens the sample cannot fill
    print the named absence rather than a blank.
    """
    with tenant_ctx(brazos):
        response = _post(
            templates_api.preview_body,
            brazos,
            dana,
            {"body": DUNNING_BODY, "version": 1},
            code="dunning",
        )
    assert response.status_code == 200
    assert response.data["sample_data"] is True
    assert "SAMPLE" in response.data["sample_data_notice"].upper()
    # ⚠ AMENDED 2026-10-05 (`DEF-NOT-6397`, lane FIX-7). This asserted
    # `"Sample" in body` — *"a sample that reads like a real customer is a
    # sample somebody screenshots"*. The PO ruled the opposite on 2026-09-07
    # (`1c9c3771a`, `template_preview.py`): the preview reads *"Hi Pat, your bill
    # for 12 Oak Street is ready… Account AC-000000"*, and what keeps a
    # screenshot from passing for a customer is the all-zero account number no
    # live account can hold, plus the notice above the pane. Both are asserted.
    assert "Pat" in response.data["body"]
    assert "AC-000000" in response.data["body"]
    assert "Sample" not in response.data["body"]
    assert "123.45" in response.data["body"]
    assert "{balance}" not in response.data["body"]


def test_def_2478__the_preview_tells_a_clerk_what_to_fix_not_how_we_render(brazos, dana):
    """DEF-2478 — the PO opened `?template=email_account_closed` and asked, of
    two blocks of text, simply *"why this text"*.

    They were reading, verbatim:

        "{support_phone} is in the 'email_account_closed' palette and the render
         context carries no value for it, so the document shows a named absence
         rather than a blank or a literal brace. OQ-117's closure: a document
         with a NAMED absence goes out; the customer needs the rest of it."

        "{support_email} — the utility's own, stamped at render (BR-TEN-017) —
         never sampled." … repeated once per identity token.

    Neither says the two things a clerk can act on: WHICH FIELD prints blank,
    and WHERE they fix it. This pins both halves of the rewrite.
    """
    body = (
        "Hello {first_name}, service at {service_address} ended {service_end_date}. "
        "Questions: {support_phone} or {support_email}. — {utility_name}"
    )
    with tenant_ctx(brazos):
        response = _post(
            templates_api.preview_body,
            brazos,
            dana,
            {"body": body, "version": 1},
            code="email_account_closed",
        )
    assert response.status_code == 200

    # ── (a) the absence note ────────────────────────────────────────────────
    absences = {row["token"]: row for row in response.data["absences"]}
    assert absences, "this body must produce at least one absence or it proves nothing"
    for token, row in absences.items():
        detail = row["detail"]
        # No architecture, no ids, no jargon on a water utility's screen.
        for banned in ("palette", "render context", "literal brace", "OQ-", "BR-"):
            assert banned not in detail, f"{token} still says {banned!r}: {detail!r}"
        # It names the FIELD in a person's words…
        assert detail.startswith(token.replace("_", " ").capitalize())
        assert "print blank" in detail
        # …and the provenance still exists, on the machine field.
        assert "OQ-117" in row["br_ref"]
    # An identity field is one the reader can fix THEMSELVES, so the sentence
    # says where. That is the half the old wording never had.
    if "support_phone" in absences:
        assert "Settings" in absences["support_phone"]["detail"]

    # ── (b) the unsampled list ──────────────────────────────────────────────
    unsampled = response.data["unsampled"]
    assert unsampled, "the identity tokens must appear here or this proves nothing"
    for row in unsampled:
        for banned in ("BR-TEN-017", "BR-NOT-015", "BR-", "OQ-"):
            assert banned not in row["reason"], f"{row['token']}: {row['reason']!r}"
    # ⚠ THE POINT OF THE FIX: the identity tokens SHARE ONE SENTENCE, so the
    # screen can print it once instead of once per row. Four rows saying the
    # same thing is what the PO photographed, and a lane that "helpfully"
    # differentiates these strings re-creates the defect while every other
    # assertion here still passes — which is why this is asserted by COUNT.
    identity = [r for r in unsampled if r["token"] in {"support_phone", "support_email", "utility_name"}]
    assert len(identity) >= 2, "need at least two identity tokens to test the grouping"
    assert len({r["reason"] for r in identity}) == 1, (
        "the identity tokens must share ONE reason string so the screen groups them; "
        f"got {len({r['reason'] for r in identity})} distinct reasons"
    )


def test_cr_007__the_preview_refuses_exactly_what_the_save_refuses(brazos, dana):
    """An editor whose preview accepts a body its save rejects teaches the wrong
    lesson, so both go through `rendering.validate_body`.

    ⚠ **AMENDED 2026-10-29 (`CR-199-BRC10`, image 17 of the drawing).** This
    asserted the preview answered 422. The redesigned workspace renders the
    wording WITH `{bogus}` shown as typed beside the error, so an unknown
    placeholder no longer fails the preview — it is reported in `errors` with
    the SAME key the save refuses with. The lesson is kept: the preview still
    names exactly what the save will refuse, and the save still refuses it."""
    with tenant_ctx(brazos):
        response = _post(
            templates_api.preview_body,
            brazos,
            dana,
            {"body": "Thanks for paying. Meter {meter_no}.", "version": 0},
            code="receipt",
        )
    assert response.status_code == 200
    assert [e["params"]["token"] for e in response.data["errors"]] == ["meter_no"]
    assert "{meter_no}" in response.data["body"]


def test_cr_007__the_preview_never_invents_the_utilitys_own_identity(brazos, dana):
    """BR-TEN-017 stamps the utility's name, address and support details AT
    RENDER from Settings → Company. Sampling them would hide the one thing this
    pane genuinely proves — whether THIS utility has filled its profile in."""
    from apps.notifications import template_preview

    context = template_preview.sample_context("receipt")
    for token in ("utility_name", "utility_address", "support_phone", "support_email"):
        assert token not in context
    assert "meter_no" not in template_preview.sample_context("bill_residential")


def test_cr_007__the_merge_field_panel_shows_each_token_with_its_resolved_sample(brazos, dana):
    """PO 2026-08-17, showing SET-10.corrected: the right rail is **two
    columns** — the token, and the value it will actually resolve to
    (`{{bill.original_total}}` beside `$32.22`).

    A token list is a palette; a token beside its value is an explanation, and
    it is the difference between guessing where a figure lands and seeing it.
    The value is resolved through the RENDERER's own formatter, so money carries
    the tenant's currency and a date the tenant's format — one formatter, so the
    panel can never disagree with the pane below it.
    """
    with tenant_ctx(brazos):
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    rows = {row["token"]: row for row in detail.data["merge_field_rows"]}
    assert set(rows) == set(detail.data["merge_fields"])
    # `{balance}` is money and renders formatted, not as a bare number.
    assert "123.45" in rows["balance"]["sample_value"]
    # Insert-on-click writes exactly the spelling the save will accept.
    assert rows["balance"]["insert"] == "{balance}"
    # BR-TEN-017's identity tokens are NOT sampled, and the row says why —
    # a made-up utility name would hide an unfilled company profile.
    assert rows["utility_name"]["sample_value"] is None
    # ⚠ DEF-2478 — THIS REQUIRED `BR-TEN-017` TO BE DRAWN IN THE MERGE-FIELD
    # TABLE, which is a THIRD surface for the same leaked sentence (the
    # preview's unsampled list and its absence notes were the other two, and
    # this one was found only because the assertion went red). The claim is
    # unchanged and the id is gone: the row still says the value is not sampled,
    # and now says WHERE it comes from — the part a clerk can act on.
    unavailable = rows["utility_name"]["sample_unavailable"]
    assert "BR-" not in unavailable
    assert "OQ-" not in unavailable
    assert "Settings" in unavailable


def test_cr_007__the_preview_strip_names_the_identity_the_body_actually_uses(brazos, dana):
    """The PO's header strip reads *"Previewing as · <kind> · sample data:
    <customer> · <account>"*. Both come from the SAME sample context the pane
    renders from, so the strip can never name somebody the body does not."""
    with tenant_ctx(brazos):
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    identity = detail.data["sample_identity"]
    # ⚠ AMENDED 2026-09-07 BY PO RULING. The sample customer is a PERSON now —
    # `Pat Rivera` at `12 Oak Street` on `AC-000000` — because the word
    # *"sample"* appeared twelve to twenty-one times on one screen and most of
    # it was the data. `AC-000000` is the safety the old `SAMPLE-ACCOUNT`
    # provided, kept: a real account SHAPE whose digits are all zero, which no
    # live account can hold. `template_preview.py`'s header records the sentence
    # this supersedes and why the worry behind it is answered rather than
    # dropped.
    assert identity["account_no"] == "AC-000000"
    assert identity["customer_name"] == "Pat Rivera"
    # …and the STRIP still cannot name somebody the BODY does not, which is what
    # this case has always been about and is untouched by the rename.
    assert identity["account_no"] in detail.data["preview"]["body"]


def test_cr_007__the_history_states_what_it_cannot_record_rather_than_leaving_it_blank(
    brazos, dana, marcus
):
    """The PO's history line is *"Jul 30 · Priya Menon — softened wording"*.
    This product holds the DATE and neither of the other two — `created_by` is a
    plain uuid because identity is another module's table (B11 F-3), and no
    column anywhere records what an edit changed. OQ-255.

    A blank column would read as *"nobody edited this"*, which is a different
    and false statement, so the absence is a value the server returns.
    """
    with tenant_ctx(brazos):
        _variant(marcus, "dunning", name="Past-due reminder")
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    row = detail.data["versions"][0]
    assert row["change_note"] is None
    # ⚠ DEF-2479 — THIS READ `"OQ-255" in change_note_unavailable`, which
    # required the open-question id to be drawn in a TABLE CELL on a water
    # utility's screen. The absence is still a value the server returns (that
    # is what this test is for); the id moved to the machine field beside it.
    assert row["change_note_unavailable"] == "No change note recorded"
    assert "OQ-255" in row["change_note_br_ref"]
    # The platform's own seeded body is attributed to the PLATFORM, never to a
    # person: provisioning writes created_by NULL because nobody published it.
    assert row["author_label"] == "platform seed"


def test_cr_007__no_money_is_computed_or_stored_anywhere_on_this_screen(brazos, dana):
    """A template is WORDING. B4's money math is not on this screen and must
    never be (CR-007 coordinator instruction, 2026-08-17).

    Asserted three ways, because the risk is that a later lane adds a total to
    the preview and nothing objects: the sample amount is a CONSTANT, the
    template tables carry no money column at all, and a save stores only text.
    """
    from decimal import Decimal

    from apps.notifications import template_preview

    # 1. The sample is a constant, not a computation.
    assert template_preview.sample_context("dunning")["balance"] == Decimal("123.45")
    # 2. Neither template table has a money column — nothing could be stored.
    money_ish = {"amount", "balance", "total", "price", "rate", "currency"}
    for model in (tm.NotificationTemplate, tm.NotificationTemplateVersion):
        names = {field.name for field in model._meta.get_fields()}
        assert not (names & money_ish), f"{model.__name__} grew a money column"
    # 3. The rendered preview FORMATS the constant and does not sum anything:
    #    one occurrence in, one occurrence out.
    with tenant_ctx(brazos):
        preview = _post(
            templates_api.preview_body,
            brazos,
            dana,
            {"body": "Balance {balance}. Again {balance}.", "version": 1},
            code="dunning",
        )
    assert preview.data["body"].count("123.45") == 2


# ── permissions · BR-SHL-025 + the PO's Settings ruling ────────────────────
def test_cr_007__a_clerk_reads_everything_and_writes_nothing(brazos, dana, marcus):
    """PO 2026-08-16: *"all settingsa re Admin only I believ; follow same rule
    that we folowed for settings related permission"*.

    The gate is the SERVER's. A Billing Clerk gets 200 on every read and 403 on
    every write, and the read TELLS the screen why so the control renders
    disabled with its reason rather than vanishing (BR-SHL-025).
    """
    with tenant_ctx(brazos):
        variant = _variant(marcus, "dunning", name="Past-due reminder")
        listed = _get(templates_api.template_catalog, brazos, marcus, role="billing_clerk")
        detail = _get(
            templates_api.template_detail,
            brazos,
            marcus,
            role="billing_clerk",
            code="dunning",
        )
        preview = _post(
            templates_api.preview_body,
            brazos,
            marcus,
            {"body": DUNNING_BODY, "version": 1},
            role="billing_clerk",
            code="dunning",
        )
        writes = [
            _post(
                templates_api.save_draft,
                brazos,
                marcus,
                {"variant": str(variant.pk), "body": DUNNING_BODY},
                role="billing_clerk",
                code="dunning",
            ),
            _post(
                templates_api.add_variant,
                brazos,
                marcus,
                {"name": "X", "language": "es-MX"},
                role="billing_clerk",
                code="dunning",
            ),
            _post(
                templates_api.publish_version,
                brazos,
                marcus,
                {"version_id": "00000000-0000-0000-0000-000000000000"},
                role="billing_clerk",
                code="dunning",
            ),
            _post(
                templates_api.deactivate_variant,
                brazos,
                marcus,
                {"variant": str(variant.pk)},
                role="billing_clerk",
                code="dunning",
            ),
            _post(
                templates_api.restore_version,
                brazos,
                marcus,
                {"version_id": "00000000-0000-0000-0000-000000000000"},
                role="billing_clerk",
                code="dunning",
            ),
        ]
    # CR-007: *"others read-only + preview"* — and preview is part of read.
    assert listed.status_code == 200 and detail.status_code == 200
    assert preview.status_code == 200
    assert [write.status_code for write in writes] == [403] * 5
    assert listed.data["can_edit"] is False
    assert "System Admin only" in listed.data["cannot_edit_reason"]
    assert detail.data["can_edit"] is False


def test_cr_007__the_two_controls_this_release_does_not_build_are_disabled_with_reasons(
    brazos, dana
):
    """BR-SHL-025 — never hidden. And the two reasons are DIFFERENT sentences
    because they have different fixes.

    ⚠ **AMENDED 2026-08-30 (CR-048 B7, DEF-2503). ONE OF THE TWO STOPPED BEING
    A "DOES NOT BUILD" AND THE OTHER DID NOT.** This case asserted
    `"no email yet" in test_send_reason` — the PO's own words from 2026-08-16,
    quoted correctly at the time, when NO screen in the product could queue a
    test on any channel. The notification-rules screen has queued real test rows
    since CR-009, so by the time anybody read that sentence on SET-10 it told a
    utility the product cannot do something the product does.

    **The superseded assertion, kept rather than deleted, because it is the
    evidence:** `assert "no email yet" in detail.data["test_send_reason"]`.

    `dunning` is a PRINT class, so the control is STILL disabled here and this
    case still proves BR-SHL-025 — but for the true reason and not the stale
    one: this platform holds an email address and a mobile number for a user and
    no postal address, so a printed template's rehearsal has nowhere to go. The
    email side of the same rule is proved in
    `test_cr048_b7_e6_template_send_test.py`, where the control is now ENABLED.
    The sample PDF is unchanged: the page writer is still billing's and still
    writes bills.
    """
    with tenant_ctx(brazos):
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    assert detail.data["can_test_send"] is False
    assert "post a test letter to yourself" in detail.data["test_send_reason"]
    assert detail.data["can_download_pdf"] is False
    # ⚠ **DEF-2479 — THIS ASSERTION USED TO READ `"billing" in
    # download_pdf_reason`, AND THAT IS HOW THE DEFECT SURVIVED.** The served
    # sentence named `apps/billing/documents.py` and OQ-149 on a water
    # utility's screen, and this line PINNED it as a requirement — G28's own
    # header predicts exactly this: *"a test written beside the string protects
    # the string."* DEF-335 had already replaced the identical assertion on
    # `set_default_reason` and `language_selection_reason`; the third field on
    # the same payload was missed, and its violation was entered in the gate's
    # baseline file instead.
    #
    # Both halves are asserted now, as DEF-335 does for the two neighbours: the
    # sentence a utility reads names NO internal reference, and the explanation
    # is still reachable rather than deleted.
    assert "apps/" not in detail.data["download_pdf_reason"]
    assert "OQ-" not in detail.data["download_pdf_reason"]
    assert "BR-" not in detail.data["download_pdf_reason"]
    assert "documents.py" not in detail.data["download_pdf_reason"]
    # The honesty survives the rewrite: it still says there is no PDF and still
    # says what you get instead. A sentence that dropped both would pass the
    # four checks above and be a worse screen than the one being fixed.
    assert "No sample PDF" in detail.data["download_pdf_reason"]
    assert "text body" in detail.data["download_pdf_reason"]
    # CR-048 wave I — the SHORT label the screen actually draws, beside the
    # sentence it carries on hover. Three or four words, and never a
    # substitute for the reason: assert both or a later lane can drop one.
    assert detail.data["download_pdf_label"] == "No sample PDF"
    assert len(detail.data["download_pdf_label"].split()) <= 4
    assert detail.data["download_pdf_reason"] != detail.data["download_pdf_label"]
    assert detail.data["test_send_reason"] != detail.data["download_pdf_reason"]


def test_cr_007__multi_language_says_messages_use_the_utilitys_language(brazos, dana):
    """A variant carries a language and resolution records the one it used.

    ⚠ **FLIPPED 2026-09-23 (`OQ-CUS-12619`, `DEF-NOT-6354`), NOT DELETED.** This
    case was `test_cr_007__multi_language_is_honest_about_having_no_input` and
    pinned the sentence *"Nothing stores a customer's preferred language yet"*
    under the label *"Not chosen automatically"*. The first half was false the
    day it was written (`accounts.preferred_language` exists, r15 #2); the PO
    then ruled that every message goes in the UTILITY's default language —
    *"(a) Portal only; emails in English."* — so the screen now says which
    language IS chosen, and that no other one ever is."""
    with tenant_ctx(brazos):
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    # DEF-335, as above: the sentence is customer English, the id is beside it.
    assert "OQ-" not in detail.data["language_selection_reason"]
    assert "apps/customers" not in detail.data["language_selection_reason"]
    assert "OQ-CUS-12619" in detail.data["language_selection_br_ref"]
    # CR-048 wave I — short label on screen, sentence on hover. Both.
    assert detail.data["language_selection_label"] == "Utility's language only"
    assert len(detail.data["language_selection_label"].split()) <= 4
    reason = detail.data["language_selection_reason"]
    assert reason.startswith("Messages use your utility's language.")
    # The false half of the old sentence must not come back in any rewording.
    assert "preferred language" not in reason
    assert "customer" not in reason.lower()
    # B14 rule 33 — two sentences of six beat one of twelve.
    assert all(len(one.split()) <= 6 for one in reason.rstrip(".").split(". "))


def test_def_2479__the_version_history_note_is_a_value_not_a_paragraph(brazos, dana):
    """DEF-2479 — a table cell holds a VALUE.

    `change_note_unavailable` rendered *"No column records what an edit changed,
    and the author's display name is identity's to publish — this module holds a
    user id, not a name (OQ-255). The date and the version number are this
    product's own facts and are shown."* AS A TABLE CELL, in a 344px-wide panel,
    on every version row of every template. Measured on the deployed v2.83.0 it
    drew a **645px-tall cell** — the worst geometry on the screen, and the one
    the PO photographed.

    Two things are asserted and the second is the one that matters: the note is
    SHORT, and the FACT still exists. A blank cell would pass any length check
    and would read as *"nobody edited this"*, which is a different and false
    statement — that is why this was never a candidate for deletion.
    """
    with tenant_ctx(brazos):
        detail = _get(templates_api.template_detail, brazos, dana, code="dunning")
    rows = detail.data["versions"]
    assert rows, "the fixture must have at least one version for this to mean anything"
    for row in rows:
        note = row["change_note_unavailable"]
        # Short enough to be a cell. The old one was 249 characters.
        assert len(note) <= 40, f"a table cell is holding {len(note)} characters: {note!r}"
        # …and still says the thing a blank cell would get wrong.
        assert "change note" in note.lower()
        # No internal reference in the words; the provenance rides the machine
        # field, which is where support reads it (DEF-335's pattern).
        assert "OQ-" not in note
        assert "B11" not in note
        assert "module" not in note.lower()
        assert "OQ-255" in row["change_note_br_ref"]


# ── isolation ──────────────────────────────────────────────────────────────
def test_cr_007__another_tenants_variant_is_not_visible_here(brazos, lonestar, dana, erin):
    """CLAUDE.md rule 1 + BR-TEN-003 / HR-1. The catalog's CLASS list is
    platform vocabulary and reads the same on every tenant; the VARIANT rows and
    their versions are tenant data and must not cross."""
    with tenant_ctx(lonestar):
        _variant(erin, "dunning", name="Lonestar's own reminder", language="fr-CA")

    response = _get(templates_api.template_detail, brazos, dana, code="dunning")
    languages = {row["language"] for row in response.data["variants"]}
    assert "fr-CA" not in languages
    assert response.data["name"] == catalogs.LISTINGS["dunning"].name

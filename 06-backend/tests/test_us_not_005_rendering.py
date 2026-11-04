# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the rendering engine + merge-variable catalogs per
#           template type)   Screens: S8 · S94–S106
# Rules:    BR-BIL-026 (every render uses the PINNED version) · BR-TEN-017
#           (identity stamped at render; issued documents never re-rendered) ·
#           BR-CUS-039 (the reconnect fee is a tenant charge code, never a
#           default) · BR-NOT-006 (language rides the pin) · CLAUDE.md rule 2
#           (money is Decimal, 2dp at display, with its currency) · rule 3 (a
#           consumption figure never renders without its unit)
# ───────────────────────────────────────────────────────
"""The engine's four rules, its refusals, and the two things it cannot do yet.

TC-5 is the case the whole catalog exists for and it was proved RED by ADDING
`meter_no` to the receipt catalog — at which point the refusal stopped and the
case failed. The float refusal was proved the same way: with the isinstance
check removed, `247.3` rendered as `247.30` and hid a hard-rule-2 violation
behind a correct-looking string.

TC-1 and TC-2 use A19 §2's own disconnect wording and US-NOT-005 §4's fixture
figures (A-11024 Ridge Coffee, balance 1,842.10, cut date Aug 18 2026, RECON
45.00) so the assertions are against the spec's numbers rather than against
convenient ones.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.notifications import catalogs, models, rendering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: A19 §2 tier 2, verbatim, reduced to the tokens it names.
DISCONNECT_BODY = (
    "FINAL REMINDER. Service to {service_address} is scheduled for disconnection on "
    "{cut_date} unless {balance} is received. A reconnect fee of {reconnect_fee} applies "
    "to restore service. {state_puc_ref}"
)

#: A19 r8's receipt row, reduced to tokens: one transaction and nothing else.
RECEIPT_BODY = (
    "Thanks {first_name}! We received your payment of {amount} on {date}. "
    "Confirmation {confirmation}. Balance {balance_before} → {balance_after}. "
    "Processed by {processed_by}."
)


def set_regional(tenant, **values):
    """Set the tenant's Regional row directly — the S8 Regional card is
    tenancy's own story and its service is not this lane's subject."""
    from apps.tenancy import models as tenancy_models

    row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant=tenant)
    for field, value in values.items():
        setattr(row, field, value)
    row.save()


# ── TC-1 · the receipt, with A19's content and nothing else ─────────────────
def test_us_not_005_tc1__a_receipt_renders_one_transaction_at_2dp(brazos):
    """US-NOT-005 TC-1: *"amount $247.30 (2dp), method, confirmation, applied-to
    bill, balance before/after, processed-by; NO usage, NO rates, NO due date."*

    The three absences are structural rather than checked: the catalog is a
    WHITELIST, so `{usage}`, `{rate}` and `{due_date}` are simply not in it.
    """
    set_regional(brazos, date_format="MM/DD/YYYY")
    with tenant_ctx(brazos):
        artifact = rendering.render(
            template_code="receipt",
            template_version=1,
            body=RECEIPT_BODY,
            context={
                "first_name": "Sarah",
                "amount": Decimal("247.300000"),
                "date": date(2026, 8, 9),
                "confirmation": "RCT-2608-0455",
                "balance_before": Decimal("412.80"),
                "balance_after": Decimal("165.50"),
                "processed_by": "Priya Menon",
            },
        )

    assert "$247.30" in artifact.body  # 2dp at display, currency named
    assert "$412.80" in artifact.body and "$165.50" in artifact.body
    assert "08/09/2026" in artifact.body
    assert "RCT-2608-0455" in artifact.body
    assert artifact.absences == ()
    # The stored figure keeps its six decimals; only the string changed.
    assert "247.300000" not in artifact.body

    catalog = catalogs.catalog_for("receipt")
    assert {"usage", "rate", "due_date", "meter_no"} & catalog.tokens == set()


# ── TC-2 · the disconnect notice, with A19 §2's own wording ─────────────────
def test_us_not_005_tc2__a_disconnect_tier_renders_a19_2s_tokens(brazos):
    """US-NOT-005 TC-2: *"'FINAL REMINDER… reconnect fee of $45.00' —
    {balance}, {cut_date} Aug 18 2026, {reconnect_fee} from the tenant charge
    code, dates in the tenant's format."*

    BR-CUS-039: the reconnect fee arrives in the CONTEXT from a tenant charge
    code. There is no default for it here and there must not be — US-NOT-009 §5
    marks a missing one an error, never a defaulted figure.
    """
    set_regional(brazos, date_format="MM/DD/YYYY")
    with tenant_ctx(brazos):
        artifact = rendering.render(
            template_code="disconnect_notice",
            template_version=2,
            body=DISCONNECT_BODY,
            context={
                "service_address": "1400 Ridge Rd, Katy TX",
                "cut_date": date(2026, 8, 18),
                "balance": Decimal("1842.10"),
                "reconnect_fee": Decimal("45.00"),
                "state_puc_ref": "TX PUC Substantive Rule 25.29",
            },
        )

    assert "FINAL REMINDER." in artifact.body
    assert "$45.00" in artifact.body
    assert "$1,842.10" in artifact.body
    assert "08/18/2026" in artifact.body


# ── TC-3 · the tenant's date format, never a hardcoded one ──────────────────
def test_us_not_005_tc3__the_same_body_re_renders_in_the_tenants_date_format(brazos):
    """US-NOT-005 TC-3: *"Tenant Regional format = DD/MM/YYYY → Same template
    renders 18/08/2026 — format from Settings, never hardcoded."*"""
    body = "Cut date {cut_date}."
    with tenant_ctx(brazos):
        set_regional(brazos, date_format="MM/DD/YYYY")
        us = rendering.render(
            template_code="disconnect_notice",
            template_version=2,
            body=body + " {state_puc_ref}",
            context={"cut_date": date(2026, 8, 18), "state_puc_ref": "TX PUC 25.29"},
        )
        set_regional(brazos, date_format="DD/MM/YYYY")
        rest_of_world = rendering.render(
            template_code="disconnect_notice",
            template_version=2,
            body=body + " {state_puc_ref}",
            context={"cut_date": date(2026, 8, 18), "state_puc_ref": "TX PUC 25.29"},
        )

    assert "08/18/2026" in us.body
    assert "18/08/2026" in rest_of_world.body


def test_us_not_005_a_month_name_format_names_its_own_limitation(brazos):
    """`DD-MMM-YY` renders an ENGLISH month name because there is no server-side
    `Intl`. A document in Spanish reading `25-Aug-26` is a real defect for a
    real customer, so every render in that format carries the problem rather
    than shipping as if it were right (hard-won law 1)."""
    set_regional(brazos, date_format="DD-MMM-YY")
    with tenant_ctx(brazos):
        artifact = rendering.render(
            template_code="disconnect_notice",
            template_version=2,
            body="Cut {cut_date}. {state_puc_ref}",
            context={"cut_date": date(2026, 8, 18), "state_puc_ref": "TX PUC 25.29"},
            language="es-MX",
        )
    assert "18-Aug-26" in artifact.body
    assert "month_name_not_localized" in {problem["code"] for problem in artifact.problems}


# ── TC-4 · identity is stamped AT RENDER ────────────────────────────────────
def test_us_not_005_tc4__identity_is_stamped_at_render_and_the_caller_still_wins(brazos):
    """BR-TEN-017 · US-NOT-005 TC-4: identity values are stamped at render, and
    a caller holding a SNAPSHOT (the reprint of an issued document) overrides
    today's Settings — which is what "issued documents are never re-rendered"
    means in code."""
    with tenant_ctx(brazos):
        live = rendering.render(
            template_code="receipt",
            template_version=1,
            body="From {utility_name}, call {support_phone}.",
            context={},
        )
        reprint = rendering.render(
            template_code="receipt",
            template_version=1,
            body="From {utility_name}, call {support_phone}.",
            context={"utility_name": "Brazos Bend Water (as issued)"},
        )

    assert live.identity is not None
    assert "Brazos Bend Water (as issued)" in reprint.body


# ── TC-5 · the catalog is a whitelist ───────────────────────────────────────
def test_us_not_005_tc5__a_token_outside_the_classs_catalog_is_refused(brazos):
    """US-NOT-005 TC-5: *"Draft saved with token {meter_no} in the receipt body
    → Save/test-render rejects — {meter_no} is not in the receipt type's
    catalog (palette-enforced, server-validated)."*

    PROVED RED by adding `meter_no` to the receipt catalog: the body was then
    accepted and this failed with `Failed: DID NOT RAISE RenderRefused`.
    """
    with tenant_ctx(brazos):
        with pytest.raises(rendering.RenderRefused, match=r"\{meter_no\}"):
            rendering.validate_body("receipt", "Meter {meter_no} paid {amount}.")
        with pytest.raises(rendering.RenderRefused):
            rendering.render(
                template_code="receipt",
                template_version=1,
                body="Meter {meter_no} paid {amount}.",
                context={"meter_no": "M-1", "amount": Decimal("1.00")},
            )


def test_us_not_005_a_regulated_footer_cannot_leave_the_disconnect_class(brazos):
    """US-NOT-007 TC-6: removing the regulatory footer from the DUNNING draft is
    fine (A19 rule 2 — it never has one); removing it from the DISCONNECT draft
    is a save refusal, because it is a mandatory block of the regulated class."""
    with tenant_ctx(brazos):
        rendering.validate_body("dunning", "Hi {first_name}, {balance} is past due.")
        with pytest.raises(rendering.RenderRefused, match="state_puc_ref"):
            rendering.validate_body("disconnect_notice", "Pay {balance} by {pay_by_date}.")


def test_us_not_005_dunning_cannot_borrow_the_regulated_footer(brazos):
    """A19 rule 2, from the other side: *"Dunning is a courtesy reminder with no
    regulatory footer."* `{state_puc_ref}` is absent from the dunning catalog,
    so a body reaching for it is refused rather than rendering a reminder that
    looks like a legal notice."""
    with tenant_ctx(brazos):
        with pytest.raises(rendering.RenderRefused, match="state_puc_ref"):
            rendering.validate_body("dunning", "Past due. {state_puc_ref}")


def test_us_not_005_a_statement_must_say_nothing_is_due(brazos):
    """A19 rule 1: *"both the printed statement and the statement email must say
    nothing is due, or customers pay twice."* Mandatory class content, checked
    at save."""
    with tenant_ctx(brazos):
        with pytest.raises(rendering.RenderRefused, match="nothing is due"):
            rendering.validate_body("statement", "Account {account_no}, ledger follows.")
        rendering.validate_body(
            "statement", "Account {account_no}. This is a statement — nothing is due."
        )


def test_us_not_005_a_usage_figure_never_renders_without_its_unit(brazos):
    """CLAUDE.md rule 3, made structural. `684` on a bill is not checkable by
    the customer who receives it; `684 kWh` is, and A19 §1.4 writes the pair
    together for exactly that reason."""
    with tenant_ctx(brazos):
        with pytest.raises(rendering.RenderRefused, match="rule 3"):
            rendering.validate_body("bill_residential", "You used {usage} this cycle.")
        rendering.validate_body("bill_residential", "You used {usage} {unit} this cycle.")


def test_us_not_005_a_float_where_money_belongs_is_refused(brazos):
    """CLAUDE.md rule 2. A float that reaches a document has already lost the
    precision that made it correct.

    PROVED RED by removing the isinstance check, and the measured result is
    worse than the one this docstring first guessed. A float does not fall
    through to the money path — it falls through to `str(value)`, so the
    document rendered **`247.3`**: one decimal place, no currency code, on a
    customer's receipt. `_rendered_value("amount", 247.3, currency="USD",
    date_format=None)` returned `('247.3', None)` with the check gone. The test
    failed with `Failed: DID NOT RAISE RenderRefused`.
    """
    with tenant_ctx(brazos):
        with pytest.raises(rendering.RenderRefused, match="rule 2"):
            rendering.render(
                template_code="receipt",
                template_version=1,
                body="Paid {amount}.",
                context={"amount": 247.3},
            )


# ── TC-6 · there is no "render on latest" path ──────────────────────────────
def test_us_not_005_tc6__rendering_requires_the_pin_and_offers_no_latest(brazos):
    """US-NOT-005 TC-6 · BR-BIL-026: *"Render requested 'on latest version' for
    an issued document → No such path exists — pinned version only."*

    Asserted on the SIGNATURE, because that is where "no such path" lives: the
    version is a required keyword argument and this module reads no
    published-version pointer, so there is no flag to get wrong.
    """
    import inspect

    signature = inspect.signature(rendering.render)
    version = signature.parameters["template_version"]
    assert version.default is inspect.Parameter.empty
    assert version.kind is inspect.Parameter.KEYWORD_ONLY

    with tenant_ctx(brazos):
        artifact = rendering.render(
            template_code="receipt",
            template_version=2,
            body="Paid {amount}.",
            context={"amount": Decimal("10.00")},
        )
    assert artifact.template_version == 2


# ── absences, never a leaked template artifact ──────────────────────────────
def test_us_not_005_a_missing_value_is_a_named_absence_not_a_leaked_token(brazos):
    """OQ-117's closure (PO 2026-08-12, *"issue and report it"*): a document
    with a NAMED absence goes out, because the customer needs the rest of it.
    What must never reach them is the literal `{token}`, the word `None`, or a
    gap nobody can account for."""
    with tenant_ctx(brazos):
        artifact = rendering.render(
            template_code="receipt",
            template_version=1,
            body="Paid {amount}, confirmation {confirmation}.",
            context={"amount": Decimal("10.00")},
        )

    assert "{confirmation}" not in artifact.body
    assert "None" not in artifact.body
    assert rendering.ABSENT_MARK in artifact.body
    assert [absence["token"] for absence in artifact.absences] == ["confirmation"]


# ── the classes with no catalog — ZERO now, and the mechanism still bites ───
def test_us_not_005_an_uncatalogued_class_is_refused_with_its_reason(brazos, monkeypatch):
    """Field map N-1's posture applied to every class A19 leaves without tokens:
    *"content never invented."* The refusal quotes the reason and names the OQ,
    so nobody has to work out whether it is a typo or a gap.

    ⚠ AMENDED 2026-08-17 (DEF-210). The cases were `email_bill_ready` (OQ-206)
    and `plan_notice_missed` (OQ-207); the PO ruled *"please define it for this
    product"* and both got a palette and a body.

    ⚠ **AMENDED AGAIN 2026-08-18 (CR-011 item 9), AND THIS TIME THE LIST RAN
    OUT.** The last three uncatalogued classes were the service agreement, the
    deposit agreement and the ACH authorization, and the PO ruled — verbatim —
    *"the 4 template classes needing legal wording - already answer - provide
    default and allow user to change"*. `CLASSES_WITHOUT_CATALOG` is now EMPTY,
    so this case can no longer name a real class to refuse.

    **The mechanism is kept under test rather than deleted with the last case
    that used it**, because the next class a ruling has not reached must land in
    exactly that hole: a fake entry is registered for the length of this test and
    the refusal is asserted against it. The two former cases are INVERTED — both
    contracts now VALIDATE, which is the thing the ruling changed.
    """
    with tenant_ctx(brazos):
        # INVERTED: the two classes this case used to prove refused now accept a
        # body, because both have a palette (PO 2026-08-18).
        rendering.validate_body("contract_deposit", "Your deposit of {amount}.")
        rendering.validate_body(
            "contract_autopay_authorization", "You authorize {utility_name} to debit."
        )

        # The MECHANISM, on a class that exists only inside this test.
        monkeypatch.setitem(
            catalogs.CLASSES_WITHOUT_CATALOG,
            "contract_future_thing",
            "a class some future rule creates and no signed document gives tokens to. OQ-206.",
        )
        with pytest.raises(rendering.RenderRefused, match="OQ-206"):
            rendering.validate_body("contract_future_thing", "anything")

        with pytest.raises(rendering.RenderRefused, match="not a template class"):
            rendering.validate_body("invoice_reminder_v2", "anything")


def test_us_not_005_the_payment_plan_contract_offers_no_countersign_token(brazos):
    """A19's 2026-08-08 addendum SUPERSEDES §3's countersign block — *"the
    payment-plan agreement executes via the customer's e-signature alone"*
    (BR-CUS-044). A catalog that still offered `{utility_rep}` would let a
    designer put a signature line on a contract nobody is supposed to sign."""
    catalog = catalogs.catalog_for("contract_payment_plan")
    assert "customer_signature" in catalog.tokens
    assert "utility_rep" not in catalog.tokens


# ── what the engine cannot do yet — asserted, not assumed ───────────────────
def test_us_not_005_dispatch_rendering_holds_when_a_row_carries_no_pin(brazos):
    """Field map N-1: *"dispatch holds safely on missing published template."*

    ⚠ AMENDED 2026-08-15 (notifications CONTENT lane). This case used to assert
    that EVERY row refuses because `notification_templates` did not exist, and
    matched on the string `US-NOT-006`. That store is now built
    (`apps/notifications/template_service.py`), so the row this case writes
    refuses for the reason that is still true and always will be: it carries a
    version number and NO `template_id`, i.e. no resolvable pin, and there is no
    path in the module that renders "the latest published version" instead
    (BR-BIL-026, US-NOT-005 TC-6).

    The refusal still names the pin, so a dashboard can show which template a
    held row was waiting for. A bill class is used deliberately: S91–S93 are
    billing's designers and `bill_templates` (B2 r10 #4) is STILL unbuilt, so a
    bill row is the live example of a document that cannot render on this
    deployment.
    """
    with tenant_ctx(brazos):
        row = models.OutboundMessage.objects.create(
            tenant_id=brazos.id,
            source_type="invoice",
            source_id=uuid.uuid4(),
            channel=models.CHANNEL_PRINT,
            template_code="bill_residential",
            template_version=3,
            template_language="en-US",
            recipient_address="1901 Bluestem Ln",
        )
        with pytest.raises(rendering.RenderRefused, match="no pinned template version"):
            rendering.render_for_dispatch(row)


def test_us_not_005_tc7__two_tenants_render_with_their_own_identity_and_formats(brazos, lonestar):
    """US-NOT-005 TC-7: *"Render for Lone Star Ridge → uses its own templates,
    identity and formats."*

    The DATABASE half of that guarantee is the isolation suite (RLS FORCE); this
    is the application half — the same body, rendered under two contexts,
    produces two documents.
    """
    set_regional(brazos, date_format="MM/DD/YYYY")
    set_regional(lonestar, date_format="DD/MM/YYYY")
    body = "From {utility_name} on {date}."

    with tenant_ctx(brazos):
        first = rendering.render(
            template_code="receipt",
            template_version=1,
            body=body,
            context={"date": date(2026, 8, 18)},
        )
    with tenant_ctx(lonestar):
        second = rendering.render(
            template_code="receipt",
            template_version=1,
            body=body,
            context={"date": date(2026, 8, 18)},
        )

    assert "08/18/2026" in first.body
    assert "18/08/2026" in second.body
    assert first.body != second.body

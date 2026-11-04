# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-006 (allocation — the within-invoice class order) ·
#           US-TEN-009 (the S66 rule-page card the value lives on)
#           Screens: S66 (Settings → Configure → Billing defaults, where the
#           tenant sets the order) · S22/S33/S35 (where the money lands)
# Rules:    BR-PAY-010 (allocation order — "tenant-configurable") ·
#           BR-PAY-038 (the FOURTH class, between taxes and fees) ·
#           BR-TEN-024 (atomic per-page save) · BR-TEN-043 (event-time forward)
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (Decimal money)
# Golden:   The PO's own OQ-109 figure, unchanged by this lane: usage+base
#           $100.58 + tax $8.30 + tenant-defined $15.00 + late fee $5.00 =
#           $128.88; a $120.00 payment meets 100.58, then 8.30, then 11.12,
#           and the late fee stays LAST at 0.00.
# ───────────────────────────────────────────────────────
"""The allocation SEQUENCE is a tenant setting (PO ruling 2026-08-12).

**PO verbatim:** *"Cant we give option to user to set the rule in settings; Im
not sure how Utilities are going to set settlement rules ; they might differ in
case of HOA or SUb metering ; better to let user set the sequence; we can give
default option and allow them to change the order"*.

The arithmetic did not change and the default did not change. What this file
asserts is the three things that were missing on 2026-08-11 and exist now:

  1. the order has SOMEWHERE TO LIVE, per tenant, on the S66 rule page;
  2. it is VALIDATED as a permutation — all four classes, each exactly once,
     because an order that dropped a class would silently stop allocating money
     to it and the bill would still foot;
  3. **the CALLER follows it.** `services.record_payment` is handed no
     `class_order` by the S22 form, so it must resolve the tenant's. A setting
     nothing reads is worse than no setting (hard-won law 2), and the test that
     proves this one is wired is the one where the SAME payment against the SAME
     bill lands differently after the tenant reorders the classes.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.payments import allocation, services
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from apps.tenancy import settings_families
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_pay_001_record_payment import (
    FOUR_CLASS_LATE_FEE,
    FOUR_CLASS_PAYMENT,
    FOUR_CLASS_TAX,
    FOUR_CLASS_TENANT_DEFINED_BILLED,
    FOUR_CLASS_TENANT_DEFINED_MET,
    FOUR_CLASS_TOTAL,
    FOUR_CLASS_USAGE_BASE,
    a_composition_read,
    a_payment,
    a_tenant_defined_class,
    an_issued_bill,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

BILLING_DEFAULTS = "billing-defaults"
KEY = "allocation_class_order"

#: BR-PAY-038's default, in the PO's own words: usage+base → taxes → the
#: tenant-defined class → fees LAST.
RATIFIED_ORDER = ["usage_base", "taxes", "tenant_defined", "fees"]

#: The tenant who wants the late fee met BEFORE the service charge. Nothing
#: signs this order — it is the tenant's, which is the entire point of the
#: ruling.
FEES_BEFORE_TENANT_DEFINED = ["usage_base", "taxes", "fees", "tenant_defined"]

#: What the PO's $120.00 payment meets under that reordering. Worked here, not
#: copied from a rule, because no rule states it — the tenant does: 120.00 −
#: 100.58 − 8.30 = 11.12 left; the late fee takes its whole 5.00 first, so the
#: tenant-defined class gets the remaining 6.12.
REORDERED_TENANT_DEFINED_MET = Decimal("6.12")


def a_system_admin(tenant):
    return staff_actor(tenant, "system_admin", "settings-admin@brazosbendutilities.test")


def a_four_class_bill(tenant, actor, monkeypatch, account):
    """The PO's $128.88 bill, composed, with the fourth class defined."""
    bill = an_issued_bill(
        tenant,
        account,
        number="BL-2608-000128",
        total=FOUR_CLASS_TOTAL,
        issued_on=date(2026, 8, 1),
    )
    a_tenant_defined_class(monkeypatch)
    a_composition_read(
        monkeypatch,
        [
            {
                "id": bill.pk,
                "number": bill.invoice_no,
                "total": FOUR_CLASS_TOTAL,
                "issued_on": date(2026, 8, 1),
                "composition": {
                    "usage_base": FOUR_CLASS_USAGE_BASE,
                    "taxes": FOUR_CLASS_TAX,
                    "tenant_defined": FOUR_CLASS_TENANT_DEFINED_BILLED,
                    "fees": FOUR_CLASS_LATE_FEE,
                },
            }
        ],
    )
    return bill


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the order has somewhere to live, and it ships holding the ruled default
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__the_class_order_is_a_tenant_setting_on_s66(brazos):
    """The S66 Billing-defaults page carries the sequence, seeded with the
    order the PO ruled on 2026-08-11 and left UNCHANGED on 2026-08-12."""
    with tenant_ctx(brazos):
        page = tenancy_selectors.settings_family(BILLING_DEFAULTS)
    assert page[KEY] == RATIFIED_ORDER


def test_po_20260812__the_shipped_default_is_the_engines_own_default(brazos):
    """The setting's default and `allocation.DEFAULT_CLASS_ORDER` are the SAME
    order — a second copy free to drift is exactly the failure
    `payments/settings_seam.py` was written to avoid."""
    assert tuple(RATIFIED_ORDER) == allocation.DEFAULT_CLASS_ORDER
    assert tuple(settings_families.ALLOCATION_CLASS_SEQUENCE) == allocation.ALLOCATION_CLASSES


# ═══════════════════════════════════════════════════════════════════════════
# 2 — it is validated as a PERMUTATION
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "bad,why",
    [
        (["usage_base", "taxes", "fees"], "a dropped class is never paid"),
        (["usage_base", "taxes", "taxes", "fees"], "a class named twice is not an order"),
        (["usage_base", "taxes", "tenant_defined", "fees", "fees"], "five entries, four classes"),
        (["usage_base", "taxes", "tenant_defined", "late_fee"], "a class no rule places"),
        ("usage_base,taxes", "a string is not a sequence of classes"),
        ([], "an empty order allocates nothing"),
    ],
)
def test_po_20260812__a_class_order_that_is_not_a_permutation_is_refused(brazos, bad, why):
    """All four classes, each exactly once. A saved order missing `taxes` would
    leave every tax balance outstanding forever while each bill still footed —
    the silent failure the PO's own remittance question turns on."""
    actor = a_system_admin(brazos)
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(actor, BILLING_DEFAULTS, {KEY: bad})
        # …and nothing was stored: a refused save leaves the ruled order standing.
        assert tenancy_selectors.settings_family(BILLING_DEFAULTS)[KEY] == RATIFIED_ORDER


def test_po_20260812__a_tenant_may_reorder_the_four_classes(brazos):
    """*"we can give default option and allow them to change the order"* — the
    save succeeds and the page reads back the tenant's own sequence."""
    actor = a_system_admin(brazos)
    with tenant_ctx(brazos):
        saved = tenancy_services.save_settings_family(
            actor, BILLING_DEFAULTS, {KEY: FEES_BEFORE_TENANT_DEFINED}
        )
        assert saved[KEY] == FEES_BEFORE_TENANT_DEFINED
        assert tenancy_selectors.settings_family(BILLING_DEFAULTS)[KEY] == (
            FEES_BEFORE_TENANT_DEFINED
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3 — THE ONE THAT MATTERS: the CALLER's behaviour changes with the setting
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__record_payment_follows_the_shipped_default(
    brazos, marcus, monkeypatch, audit_rows
):
    """With the tenant untouched, the PO's ruled figure is unmoved: $120.00 on
    a $128.88 bill meets 100.58, then 8.30, then 11.12, and the late fee stays
    LAST at 0.00."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        a_four_class_bill(brazos, marcus, monkeypatch, account)

        result = a_payment(marcus, account, amount=FOUR_CLASS_PAYMENT)

        by_class = result.allocations[0]["by_class"]
        assert by_class["usage_base"] == str(FOUR_CLASS_USAGE_BASE)
        assert by_class["taxes"] == str(FOUR_CLASS_TAX)
        assert by_class["tenant_defined"] == str(FOUR_CLASS_TENANT_DEFINED_MET)
        assert "fees" not in by_class, "the late fee is LAST and this payment never reached it"


def test_po_20260812__record_payment_follows_the_tenants_own_order(
    brazos, marcus, monkeypatch, audit_rows
):
    """**THE WIRING TEST.** The same payment, the same bill, a different tenant
    setting — and the money lands somewhere else.

    A tenant who puts fees before the tenant-defined class has decided that a
    late fee is met before a service charge. Under that order the $120.00 meets
    100.58 usage+base, 8.30 tax, the whole 5.00 late fee, and 6.12 of the 15.00
    service charge. Nothing in the arithmetic changed; the tenant's sequence
    did.

    This is the test hard-won law 2 asks for: it fails if the setting is stored,
    validated, rendered on a screen and never read by the thing that allocates
    money.
    """
    actor = a_system_admin(brazos)
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            actor, BILLING_DEFAULTS, {KEY: FEES_BEFORE_TENANT_DEFINED}
        )
        account = an_account(marcus, brazos)
        a_four_class_bill(brazos, marcus, monkeypatch, account)

        result = a_payment(marcus, account, amount=FOUR_CLASS_PAYMENT)

        by_class = result.allocations[0]["by_class"]
        assert by_class["usage_base"] == str(FOUR_CLASS_USAGE_BASE)
        assert by_class["taxes"] == str(FOUR_CLASS_TAX)
        # The two that MOVED, and the reason this test exists.
        assert by_class["fees"] == str(FOUR_CLASS_LATE_FEE)
        assert by_class["tenant_defined"] == str(REORDERED_TENANT_DEFINED_MET)

        # The trail records the order the money was actually allocated under —
        # not the shipped default, which is what it would say if the read were
        # cosmetic.
        allocated = [row for row in audit_rows if row["action"] == services.AUDIT_ALLOCATED][0]
        assert allocated["after"]["class_order"] == FEES_BEFORE_TENANT_DEFINED


def test_po_20260812__an_unreadable_setting_refuses_and_never_falls_back(brazos, monkeypatch):
    """The seam read REFUSES rather than substituting the shipped order, and
    that is asserted rather than described (hard-won law 1).

    Both directions: tenancy publishing no `settings_family` at all, and a
    settings document that carries no `allocation_class_order`. A
    `.get(key, DEFAULT_CLASS_ORDER)` in either place would be a second copy of
    a finance-adjacent default, free to drift from the sequence on the tenant's
    own screen — and the drift lands as money meeting a late fee before a
    service charge, with every total still footing.
    """
    from apps.payments.exceptions import PaymentRuleError

    with tenant_ctx(brazos):
        monkeypatch.setattr(tenancy_selectors, "settings_family", None, raising=False)
        with pytest.raises(PaymentRuleError, match="settings_family is not published"):
            services.tenant_class_order()

        monkeypatch.setattr(
            tenancy_selectors, "settings_family", lambda _slug: {"late_pct": "1.5"}, raising=False
        )
        with pytest.raises(PaymentRuleError, match="allocation_class_order"):
            services.tenant_class_order()


def test_po_20260812__an_explicit_class_order_still_wins_over_the_setting(
    brazos, marcus, monkeypatch
):
    """The staff/preview path keeps its argument. `class_order` is still an
    ARGUMENT (US-PAY-006 TC-5 prices a preview with one); the setting is what
    the argument defaults to when nobody states one."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        a_four_class_bill(brazos, marcus, monkeypatch, account)

        result = a_payment(
            marcus,
            account,
            amount=FOUR_CLASS_PAYMENT,
            class_order=tuple(FEES_BEFORE_TENANT_DEFINED),
        )

        by_class = result.allocations[0]["by_class"]
        assert by_class["fees"] == str(FOUR_CLASS_LATE_FEE)
        assert by_class["tenant_defined"] == str(REORDERED_TENANT_DEFINED_MET)

# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CUS-9776 (a company's account was named after its CONTACT
#           person) · DEF-CUS-9774 / DEF-CUS-9775 (an account holding a per-tax
#           exemption certificate read "Tax exempt: No")
# Rules:    BR-CUS-054 (the first-class customer) · BR-RAT-105 (a certificate is
#           per tax) · PO ruling (A) 2026-10-05 (DEF-CUS-9724: an exemption
#           removes only the tax on its certificate; the blanket flag stays false)
# Change:   CR-171-BRC10 (M4/M5 matrix, §22)
# ───────────────────────────────────────────────────────
"""The account's NAME is its customer's; its EXEMPTION is its certificates.

M5's church — *Grace Fellowship of Cedar Ford*, contact *Ruth Okafor*,
certificate CF-REL-2026-0412 against the City's utility tax — read *Ruth
Okafor* on its own account title, unit and meter, and *Tax exempt: No* on its
account page and its move record, while its first bill rightly dropped the
City's 2.00%. Both reads are pinned here at the server, where every screen gets
them from.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.customers import models as customers_models
from apps.customers import search_sources, selectors, unit_account_facts
from tests.test_cr171_p1_15_move_in_preferences import _category, _exemption, _move_in, _vacated
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CHURCH = "Grace Fellowship of Cedar Ford"
CONTACT = "Ruth Okafor"
AS_OF = date(2026, 10, 10)


def _church(actor, tenant, **extra):
    _u, _p, outgoing = _vacated(actor, tenant)
    result = _move_in(
        actor,
        outgoing,
        account_type="commercial",
        contact={"full_name": CONTACT, "email": "ruth.okafor@example.com", "phone": "+1 (281) 555-0190"},
        customer={
            "display_name": CHURCH,
            "kind": "company",
            "identity": {"tax_id": "74-3051190"},
        },
        **extra,
    )
    return customers_models.Account.objects.get(pk=result["id"])


# ── DEF-CUS-9776 — the name ────────────────────────────────────────────────
def test_def_cus_9776__a_company_account_is_named_after_the_company(brazos, dana):
    with tenant_ctx(brazos):
        account = _church(dana, brazos)
        key = str(account.pk)
        assert customers_models.Contact.objects.get(account=account).full_name == CONTACT
        # the single read, its plural, and every surface that reaches them
        assert selectors.primary_contact_name(account) == CHURCH
        assert selectors.primary_contact_names_for([key]) == {key: CHURCH}
        assert selectors.account_detail(key)["name"] == CHURCH
        assert selectors.active_account_for_unit(account.unit_id)["customer_name"] == CHURCH
        # the global search's account row is labelled — and found — by it
        rows = search_sources.search_accounts("Grace Fellowship", 5)
        assert [(row["label"], row["context"]) for row in rows] == [(account.account_no, CHURCH)]


def test_def_cus_9776__the_list_sorts_on_the_name_it_shows(brazos, dana):
    with tenant_ctx(brazos):
        account = _church(dana, brazos)
        sub = customers_models.Account.objects.filter(pk=account.pk).annotate(
            sort_name=selectors._primary_contact_name_subquery()
        )
        assert sub.get().sort_name == CHURCH.lower()


def test_def_cus_9776__a_sold_account_names_its_buyer_and_an_unlinked_one_its_contact(brazos, dana):
    """`ended_at` is load-bearing: an ENDED link is a former holder."""
    with tenant_ctx(brazos):
        account = _church(dana, brazos)
        key = str(account.pk)
        from django.utils import timezone

        customers_models.CustomerAccount.objects.filter(account=account).update(ended_at=timezone.now())
        # no CURRENT customer: the contact is the fallback, as before
        assert selectors.primary_contact_name(account) == CONTACT
        assert selectors.primary_contact_names_for([key]) == {key: CONTACT}
        sub = customers_models.Account.objects.filter(pk=account.pk).annotate(
            sort_name=selectors._primary_contact_name_subquery()
        )
        assert sub.get().sort_name == CONTACT.lower()


# ── DEF-CUS-9774 / DEF-CUS-9775 — the certificate ─────────────────────────
def test_def_cus_9774__the_account_serves_its_certificate_with_the_tax_it_removes(brazos, dana):
    with tenant_ctx(brazos):
        category = _category(brazos)
        account = _church(dana, brazos, tax_exemption=_exemption(category))
        detail = selectors.account_detail(str(account.pk))
        unit_facts = unit_account_facts.account_facts(account.pk, as_of=AS_OF)
    # ruling (A): the blanket flag stays false …
    assert (detail["tax_exempt"], detail["tax_exempt_ref"]) == (False, None)
    # … and the certificate is what the page reads
    assert [
        (row["tax_name"], row["category_name"], row["certificate_ref"], row["expires_on"], row["state"])
        for row in detail["tax_exemptions"]
    ] == [("City utility tax", "Religious organisation", "IA-EX-2231", "2027-01-15", "live")]
    assert unit_facts["tax_exemption"]["claimed"] is True
    assert unit_facts["tax_exemption"]["reference"] == "IA-EX-2231"


def test_def_cus_9774__an_account_with_no_certificate_serves_none(brazos, dana):
    with tenant_ctx(brazos):
        account = _church(dana, brazos)
        detail = selectors.account_detail(str(account.pk))
        unit_facts = unit_account_facts.account_facts(account.pk, as_of=AS_OF)
    assert detail["tax_exemptions"] == []
    assert unit_facts["tax_exemption"]["claimed"] is False


def test_def_cus_9774__a_revoked_certificate_is_not_served(brazos, dana):
    from django.utils import timezone

    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        category = _category(brazos)
        account = _church(dana, brazos, tax_exemption=_exemption(category))
        rating_models.TaxExemptionCertificate.objects.filter(account_id=account.pk).update(
            revoked_at=timezone.now()
        )
        assert selectors.account_detail(str(account.pk))["tax_exemptions"] == []


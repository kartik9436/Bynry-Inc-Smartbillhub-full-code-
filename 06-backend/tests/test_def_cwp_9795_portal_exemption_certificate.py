# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-9795 (the portal's Your account page read a per-tax
#           exemption certificate as no exemption)
# Rules:    BR-RAT-105 (a certificate is per tax) · PO ruling (A) 2026-10-05
#           (DEF-CUS-9724: the blanket flag stays false for a certificate) ·
#           BR-CWP-053 (the exemption shows its expiry) · US-CWP-031 TC-5 (the
#           certificate NUMBER is the utility's record and is not served)
# Screen:   CWP-065 Your account, rail panel TAX (From / Runs out)
# ───────────────────────────────────────────────────────
"""The portal reads the SAME certificate read the staff account page reads.

M5's church holds a certificate against the City's utility tax and no blanket
flag. Until 2.549.x its own portal page showed no Tax panel at all, because
`account_summary` read only `accounts.tax_exempt`. These cases pin the read at
the server: a live certificate is served with the tax it removes and its
expiry, an expired one is not served as an exemption, a revoked one is not
served, the number never is, and the blanket flag still reads as before.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.portal import selectors as portal_selectors
from tests.test_cr171_p1_15_move_in_preferences import _category, _exemption
from tests.test_def_cus_9774_9776_account_name_and_exemption import _church
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 10, 10)


def _summary(tenant, account):
    return portal_selectors.account_summary(tenant.id, account, as_of=AS_OF)


def test_def_cwp_9795__a_certificate_only_account_shows_its_exemption(brazos, dana):
    with tenant_ctx(brazos):
        category = _category(brazos)
        account = _church(dana, brazos, tax_exemption=_exemption(category))
        assert account.tax_exempt is False  # ruling (A)
        view = _summary(brazos, account)
    block = view["tax_exemption"]
    assert block is not None, "a live certificate is an exemption the customer holds"
    assert block["taxes"] == [{"tax": "City utility tax", "until": "2027-01-15"}]
    assert block["certificate_on_file"] is True
    assert block["reminder_days_before"] == 30
    # US-CWP-031 TC-5: the number is the utility's record, never the customer's screen
    assert "IA-EX-2231" not in str(view)


def test_def_cwp_9795__an_expired_certificate_is_not_an_exemption(brazos, dana):
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        category = _category(brazos)
        account = _church(dana, brazos, tax_exemption=_exemption(category))
        rating_models.TaxExemptionCertificate.objects.filter(account_id=account.pk).update(
            expires_on=date(2020, 1, 1)
        )
        view = _summary(brazos, account)
    assert view["tax_exemption"] is None


def test_def_cwp_9795__a_revoked_certificate_is_not_served(brazos, dana):
    from django.utils import timezone

    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        category = _category(brazos)
        account = _church(dana, brazos, tax_exemption=_exemption(category))
        rating_models.TaxExemptionCertificate.objects.filter(account_id=account.pk).update(
            revoked_at=timezone.now()
        )
        view = _summary(brazos, account)
    assert view["tax_exemption"] is None


def test_def_cwp_9795__the_blanket_flag_still_reads_as_before(brazos, dana):
    with tenant_ctx(brazos):
        account = _church(dana, brazos)
        account.tax_exempt = True
        account.tax_exempt_ref = "TX-EX-1"
        account.tax_exempt_expires = date(2027, 3, 31)
        account.save(update_fields=["tax_exempt", "tax_exempt_ref", "tax_exempt_expires"])
        view = _summary(brazos, account)
    block = view["tax_exemption"]
    assert block["until"] == "2027-03-31"
    assert block["certificate_on_file"] is True
    assert block["taxes"] == []


def test_def_cwp_9795__no_exemption_means_no_block(brazos, dana):
    with tenant_ctx(brazos):
        account = _church(dana, brazos)
        view = _summary(brazos, account)
    assert view["tax_exemption"] is None

# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-4625 — S21's *Portal access* panel announced *"The customer
#          portal is out of scope for this version, and the paperless, SMS and
#          portal flags are columns that were never built. No login date is
#          shown because none exists."* over an account that HAS a portal
#          login. Found by the Product Owner on the live product, by looking:
#          *"I have login portal for this account - portal access says…"*.
# Rules:   PO 2026-09-07 (decision log, the `used_by` ruling): *"it should be
#          dynamic and based on actual usage"* — derive the STATE, keep the
#          SPECIFICITY, and print what a derivation skipped beside what it
#          checked · BR-CWP-004 (a staff user and a customer login are two
#          tables and must never join) · BR-CUS-054 (`customer_accounts`) ·
#          BR-CUS-028 (the delivery election) · CLAUDE.md hard rule 1 (tenant
#          scoping) · hard-won law 2's mirror (a refusal that outlived the
#          thing it refused)
# Tests:   this file
# Impacts: apps/customers/portal_seam.py · apps/customers/selectors.py
# ───────────────────────────────────────────────────────
"""The account detail READS portal access instead of announcing its absence.

⚠ **WHY A HAND-WRITTEN SENTENCE WAS NOT AN ACCEPTABLE FIX, and the reasoning
is the Product Owner's rather than ours.** Offered a choice between deriving a
stale sentence and keeping the literal with a drift test behind it, they chose
derivation: a check tells the next engineer the string is wrong, while
derivation means the string cannot be wrong. The sentence this replaced was
true the day it was typed and false from the day `CR-068` shipped the portal —
nothing was watching, and nothing could be.

⚠ **THREE STATES THAT LOOK ALIKE AND ARE NOT, which is what the old sentence
flattened into one.** *Nobody has signed up* is a fact about this customer.
*Never signed in* is a fact about a customer who has. *Could not be read* is a
fact about US. The panel says which, and the cases below hold them apart —
because a screen that prints one for another is exactly how *"no login date is
shown because none exists"* survived the portal landing.
"""

import pytest

from apps.customers import portal_seam, selectors
from apps.portal import models as portal_models
from core.tenancy import tenant_context

from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_cwp_helpers import elm_street_account, enrol_maria

pytestmark = pytest.mark.django_db


def test_def_cus_4625__an_account_with_no_login_says_nobody_rather_than_no_portal(pine_hill, sarah):
    """`0` is an answer about this account, not about the product."""
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        state = portal_seam.portal_access_for_account(account)

    assert state["logins"] == 0
    assert state["last_sign_in"] is None
    # ⚠ THE BLIND-SPOT CLAUSE: an empty list is a CLAIM that both reads
    # succeeded, so it must never be the value of a read that did not run.
    assert state["unreadable"] == []


def test_def_cus_4625__an_enrolled_account_is_READ_as_having_a_login(pine_hill, sarah):
    """The Product Owner's own case: this account HAS a portal login."""
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)

    with tenant_context(pine_hill.id):
        state = portal_seam.portal_access_for_account(account)

    assert state["logins"] == 1, state
    assert state["locked"] == 0
    # Enrolled but never signed in — a REAL state, and a different sentence
    # from "nobody has signed up".
    assert state["last_sign_in"] is None
    assert state["unreadable"] == []


def test_def_cus_4625__a_session_is_the_last_sign_in_date(pine_hill, sarah):
    """`portal_session` is where the date lives, and it always did.

    The sentence this replaces said *"No login date is shown because none
    exists"*. The date exists; the screen was not reading it.
    """
    from datetime import timedelta

    from django.utils import timezone

    account = elm_street_account(pine_hill, sarah)
    credential = enrol_maria(pine_hill, sarah)
    when = timezone.now()
    with tenant_context(pine_hill.id):
        portal_models.PortalSession.objects.create(
            tenant_id=pine_hill.id,
            portal_credential_id=credential.id,
            account_set=[],
            expires_at=when + timedelta(days=1),
        )
        state = portal_seam.portal_access_for_account(account)

    assert state["last_sign_in"] == when.date().isoformat(), state
    assert state["unreadable"] == []


def test_def_cus_4625__the_account_payload_carries_it(pine_hill, sarah):
    """S21 reads it from `GET /accounts/{id}`, so the payload must carry it."""
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)

    with tenant_context(pine_hill.id):
        payload = selectors.account_detail_dict(account)

    assert "portal_access" in payload, sorted(payload)
    assert payload["portal_access"]["logins"] == 1
    # ⚠ AND THE TWO COLUMNS THE OLD SENTENCE CALLED "never built" — both have
    # been real since 2026-08-31 (CR-052 W4 task 14).
    assert payload["paperless"] is False
    assert payload["sms_reminders"] is False


def test_def_cus_4625__another_tenants_credential_is_not_this_accounts(pine_hill, oak_ridge, sarah):
    """CLAUDE.md hard rule 1, on a read that crosses two modules.

    A credential is found through `customer_accounts`, and a walk that forgot
    the tenant would report a neighbouring utility's customer as holding a
    login on this account.
    """
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)

    with tenant_context(oak_ridge.id):
        # The same account object, read under a DIFFERENT tenant: no links,
        # therefore no logins. Nothing leaks either way.
        state = portal_seam.portal_access_for_account(
            type("Row", (), {"tenant_id": oak_ridge.id, "pk": account.pk})()
        )

    assert state["logins"] == 0, state


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-4625 (the S21 portal panel, derived rather than declared)
# generated: 2026-09-07 by the account-Usage-tab lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_def_cus_4625_portal_access.py
# exceptions: E3 the cross-tenant case builds a stand-in row rather than
#   re-seeding a whole second utility's account — the assertion is about the
#   WHERE clause this seam writes, and a bare object with the two attributes
#   it reads is the smallest thing that can prove it

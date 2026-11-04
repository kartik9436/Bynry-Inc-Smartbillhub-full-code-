# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-023 (EP-CWP-06) — the portal shell: changing the account
#           switcher re-scopes EVERY tab. Screens: CWP-022 and every signed-in
#           screen after it
# Defects:  DEF-CWP-3900 — `GET bills` and `GET payments` took no account, so
#           a landlord who chose `22 Palm Ct` in the header went on reading all
#           four accounts underneath it
# Rules:    BR-CWP-010 (every read intersected with the session's set AND the
#           tenant, IN THE QUERY, never in the screen) · BR-CWP-013 (the set is
#           FLAT) · BR-CWP-015 (balances shown separately, never merged) ·
#           BR-CWP-047 (never cached — the narrowed answer is still `no-store`)
# Tests:    this file
# Impacts:  apps/portal/api.py `_scope`, `bills`, `payments`
# ───────────────────────────────────────────────────────
"""`US-CWP-023` TC-2 and TC-3, at the edge rather than at the seam.

⚠ **THESE TWO CASES CANNOT BE PROVED AT THE SEAM, WHICH IS WHY THEY ARE HERE.**
`billing_seam.bills_for([ids])` has always taken a list and has always been
right; what was missing was anything that put ONE id in that list. The bug was
entirely in the edge and in the screen above it, and a seam test — `test_us_
cwp_032_bills.py` calls the seam directly — passed through the whole of it.

⚠ **AND TC-3 IS THE ONE THAT MATTERS MORE THAN TC-2.** A switcher is a
convenience; anybody can call `GET bills?account_id=…` with any id at all. The
answer for an account outside the session's set is the same 404 as for an
account that does not exist, so the endpoint cannot be used to ask whether a
particular account exists.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client

from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    switch_on,
)
from tests.test_us_cwp_026_my_accounts import a_tenants_account, landlord

TODAY = date(2026, 9, 2)

#: `US-CWP-024` §4 — the landlord's four accounts owe these, in this order.
#: Three carry a bill; the `$0.00` row is an account with none.
ELM_A = "142.1800"
PALM_CT = "412.6000"


def signed_in(tenant):
    client = Client()
    answer = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def totals(body):
    return sorted(row["total"] for row in body["bills"])


def _without_trace(body):
    return {key: value for key, value in body.items() if key != "trace_id"}


@pytest.mark.django_db
def test_us_cwp_023_tc2_bills_without_an_account_are_still_the_whole_set(pine_hill, sarah):
    """The parameter is OPTIONAL and its absence is the behaviour that shipped.

    Stated as its own case so that a lane reading only the narrowing case below
    cannot conclude the whole-set answer was replaced. `CWP-023` (all my
    accounts) and `CWP-022` (home) both depend on it.
    """
    switch_on(pine_hill, sarah)
    landlord(pine_hill, sarah)
    answer = signed_in(pine_hill).get(f"/api/{pine_hill.subdomain}/portal/bills")
    assert answer.status_code == 200, answer.content
    assert totals(answer.json()) == sorted([ELM_A, "318.0400", PALM_CT])


@pytest.mark.django_db
def test_us_cwp_023_tc2_bills_narrow_to_the_account_the_switcher_names(pine_hill, sarah):
    """`BR-CWP-010` — and this is the defect itself.

    Before `_scope`, the assertion below read *three bills* whichever account
    the header named: the customer was told they were looking at `22 Palm Ct`
    and shown `1408 Elm St`'s bills at the same time.
    """
    switch_on(pine_hill, sarah)
    _credential, accounts, _master = landlord(pine_hill, sarah)
    client = signed_in(pine_hill)
    seen = []
    for account in accounts:
        answer = client.get(
            f"/api/{pine_hill.subdomain}/portal/bills", {"account_id": str(account.pk)}
        )
        assert answer.status_code == 200, answer.content
        rows = answer.json()["bills"]
        assert len(rows) <= 1, "one account, one bill in this fixture"
        seen.extend(row["total"] for row in rows)
        # `BR-CWP-047` — narrowing does not make an answer cacheable.
        assert "no-store" in answer["Cache-Control"]
    assert sorted(seen) == sorted([ELM_A, "318.0400", PALM_CT]), (
        "each account answered for itself, and the four together are the set"
    )


@pytest.mark.django_db
def test_us_cwp_023_tc2_payments_narrow_the_same_way(pine_hill, sarah):
    """The second of the four tabs TC-2 names. Same parameter, same guard."""
    switch_on(pine_hill, sarah)
    _credential, accounts, _master = landlord(pine_hill, sarah)
    client = signed_in(pine_hill)
    whole = client.get(f"/api/{pine_hill.subdomain}/portal/payments")
    assert whole.status_code == 200, whole.content
    one = client.get(
        f"/api/{pine_hill.subdomain}/portal/payments", {"account_id": str(accounts[0].pk)}
    )
    assert one.status_code == 200, one.content
    assert "no-store" in one["Cache-Control"]
    assert len(one.json()["money"]) <= len(whole.json()["money"])


@pytest.mark.django_db
def test_us_cwp_023_tc3_an_account_outside_the_set_is_refused_IN_THE_QUERY(pine_hill, sarah):
    """`BR-CWP-010` — the switcher is a convenience; the guard is the query.

    ⚠ **AND THE REFUSAL IS THE SAME ONE AN UNKNOWN ID GETS.** A different
    status for *exists but not yours* would make this endpoint an oracle for
    which account numbers a utility has.
    """
    switch_on(pine_hill, sarah)
    landlord(pine_hill, sarah)
    outside = a_tenants_account(pine_hill, sarah)
    client = signed_in(pine_hill)
    for route in ("bills", "payments"):
        refused = client.get(
            f"/api/{pine_hill.subdomain}/portal/{route}", {"account_id": str(outside.pk)}
        )
        assert refused.status_code == 404, (route, refused.content)
        unknown = client.get(
            f"/api/{pine_hill.subdomain}/portal/{route}",
            {"account_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert unknown.status_code == 404, (route, unknown.content)
        # ⚠ `trace_id` is per REQUEST and is the one field that must differ;
        # everything a caller could learn from — the code, the message, the
        # rule reference — has to be identical, or the difference is the leak.
        assert _without_trace(refused.json()) == _without_trace(unknown.json()), (
            "an account of this utility that Maria does not hold answers "
            "exactly what an account nobody holds answers"
        )

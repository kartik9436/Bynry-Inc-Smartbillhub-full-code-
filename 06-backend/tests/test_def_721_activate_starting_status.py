# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-721 (2026-08-26, HIGH) — *"POST /accounts/{id}/ACTIVATE NEVER
#           READS THE ACCOUNT'S CURRENT STATUS — A CUT CUSTOMER CAN BE PUT BACK
#           TO ACTIVE, AROUND THE RECONNECT FLOW."*  Screens: S21
# Rules:    BR-CUS-018 (a new account is a DRAFT until something activates it) ·
#           BR-CUS-055 (the seeded status vocabulary) · BR-CUS-107 (PO
#           2026-08-25 — the SIXTH status, `Disconnected`, class
#           `non_billable`) · BR-PAY-036 + B18 §5.8.4 (restoration is an
#           explicit audited act AFTER the money arrives — `mark_reconnecting`)
# Tests:    this file
# Impacts:  apps/customers/services.py :: activate_account
# ───────────────────────────────────────────────────────
"""A PRECONDITION THAT WAS SAFE BECAUSE A SET HAD ONE MEMBER.

`activate_account` was written when `pending_activation` was the ONLY
non-billable status. "Activate" therefore had exactly one lawful starting
point, and reading the current status looked redundant — so it never did.

BR-CUS-107 grew that set. `disconnected` is the second `non_billable` member,
and the omission became reachable the moment it was seeded: nothing on the
SERVER refused activating an account whose service is CUT and whose debt is
unpaid. That walks straight around the reconnect flow BR-PAY-036 and B18 §5.8.4
require — `disconnects.mark_reconnecting` exists precisely so restoration is an
explicit, audited act after the money arrives.

**A DISPLAY GUARD IS NOT THE FIX, AND THAT IS THIS FILE'S POINT.** The frontend
guard shipped with BR-CUS-107 narrows `isDraftAccount` by code so S21 no longer
OFFERS the button. The endpoint still accepted the call. A screen that stops
showing a door is not a door that refuses.

The wider lesson, and it is the same one as DEF-724: **a precondition that is
redundant because a set has one member becomes a defect the day the set grows.**
"""
from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx


def _unit(actor, tenant, *, label="Unit A"):
    from tests.test_w7_transfers import _unit as make_unit

    return make_unit(actor, tenant, label=label)


def _draft(actor, tenant, *, label="12 Ashcroft Row"):
    unit = _unit(actor, tenant, label=label)
    return unit, customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": "2026-07-01",
            "contact": {"full_name": "Alvarez, Ana"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                "Alvarez, Ana", account_type="residential"
            ),
        },
    )


def _move_to(account_id, code):
    """Write the status through the ORM, deliberately.

    `_apply_status_change` refuses a direct status write and `commit_cut` does
    not assign `Disconnected` yet (BR-CUS-107's row is seeded and nothing
    assigns it — see `disconnects.DISCONNECTED_STATUS_ASSIGNED`, and note that
    since 2026-08-30 the CUT does assign it). The
    fixture has to put the account where the defect lives, and that it CAN'T be
    reached through a door today is exactly why no test exercised it.
    """
    account = customers_models.Account.objects.get(id=account_id)
    status = customers_models.AccountStatus.objects.get(
        tenant_id=account.tenant_id, code=code
    )
    customers_models.Account.objects.filter(id=account.id).update(status=status)


def test_def_721_a_draft_still_activates(brazos, marcus):
    """BR-CUS-018's own path, unbroken. A fix that closed the hole by refusing
    everything would pass every negative case in this file and ship a product
    where no account can be opened."""
    with tenant_ctx(brazos):
        _u, draft = _draft(marcus, brazos)
        activated = customers_services.activate_account(marcus, draft["id"])
        assert activated["status"] == "active"


def test_def_721_a_cut_account_cannot_be_activated_around_the_reconnect_flow(
    brazos, marcus
):
    """**THE DEFECT.** `A-11340`-shaped: service cut, debt unpaid, and
    `POST /accounts/{id}/activate` put it straight back to Active."""
    with tenant_ctx(brazos):
        _u, draft = _draft(marcus, brazos, label="70 Harrow Bank")
        customers_services.activate_account(marcus, draft["id"])
        _move_to(draft["id"], "disconnected")

        with pytest.raises(errors.BizError) as caught:
            customers_services.activate_account(marcus, draft["id"])
        assert caught.value.message_key == (
            "customers.account.activate_wrong_starting_status"
        )
        assert caught.value.params["status"] == "disconnected"
        # and the account did NOT move
        assert (
            customers_models.Account.objects.get(id=draft["id"]).status.code
            == "disconnected"
        )


@pytest.mark.parametrize("code", ["active", "marked_disconnect", "vacation_hold"])
def test_def_721_activation_is_refused_from_every_status_that_is_not_the_draft(
    brazos, marcus, code
):
    """The set is NAMED, not inferred from a behaviour class.

    `active` and `marked_disconnect` already occupy — activating one is a no-op
    that would rewrite `opened_at`. `vacation_hold` comes back through its own
    resume, and BR-CUS-055 owns that vocabulary. None of the three is this
    door's business, and before DEF-721 all three walked through it.
    """
    with tenant_ctx(brazos):
        _u, draft = _draft(marcus, brazos, label=f"5 Weir Lane {code}")
        customers_services.activate_account(marcus, draft["id"])
        _move_to(draft["id"], code)
        with pytest.raises(errors.BizError) as caught:
            customers_services.activate_account(marcus, draft["id"])
        assert caught.value.message_key == (
            "customers.account.activate_wrong_starting_status"
        )


def test_def_721_the_refusal_resolves_to_a_customer_sentence():
    """G32's rule, asserted here too because a refusal nobody can read is
    DEF-320's shape: the clerk clicks, nothing happens, no explanation appears.
    """
    import json
    import pathlib

    catalogue = json.loads(
        (
            pathlib.Path(__file__).resolve().parents[2]
            / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    assert "customers.account.activate_wrong_starting_status" in catalogue
    assert "customers.account.type_is_legacy" in catalogue

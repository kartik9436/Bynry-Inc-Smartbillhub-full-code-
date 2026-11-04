# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-628 (2026-08-24, high) — *"A PENDING-ACTIVATION ACCOUNT SERVES
#           `$0.00` WHERE THE SPEC REQUIRES THE BALANCE TO READ *AWAITING* — A
#           FABRICATED-LOOKING ZERO ON AN ACCOUNT THAT CANNOT BE BILLED YET."*
#           Measured on a live seeded row: `balance='0.000000'`,
#           `balance_unavailable=()`, `last_bill_at=None`.
# Rules:    BR-CUS-510 (this lane, 2026-08-27 — the four clauses below) ·
#           BR-CUS-107 (a cut account is `Disconnected`, class `non_billable`,
#           and it HOLDS A DEBT) · BR-CUS-055 (the status vocabulary is
#           TENANT-EXTENSIBLE, so the CLASS is read and never a code) ·
#           BR-CUS-015 / DEF-127 (an absence is not spelled like a zero) ·
#           B18 §5.1.5 (*"`Pending activation` (balance reads awaiting,
#           `LAST BILL` = `—`)"*)
# ───────────────────────────────────────────────────────
"""A ZERO THAT IS NOT AN ANSWER — and the one that is.

════════════════════════════════════════════════════════════════════════════
THE HALF OF THIS FILE THAT MATTERS MOST IS §2, AND IT IS NOT THE DEFECT
════════════════════════════════════════════════════════════════════════════
DEF-628's own `prevention` column, written 2026-08-24, reads:

    "the row already carries `status_behavior_class`; the cell should key off
     `non_billable` rather than off the amount. A guard asserting that a
     non-billable account's balance cell never renders a currency figure would
     hold it."

**Implemented as written, that sentence ships a worse defect than the one it
fixes**, and it did not become wrong through anybody's carelessness — it was
overtaken **twenty-four hours later** by `BR-CUS-107` (PO 2026-08-25, migration
`customers/0025`), which put a SIXTH status into that same behaviour class:
`Disconnected`. That migration's own worked row is **`A-11488`, cut 2026-08-18
owing $612.75**, reading `Disconnected / non-billable`. A cell keying off
`non_billable` alone would render *awaiting* over that $612.75 — hiding the
arrears on precisely the account the disconnect ladder exists to chase, which is
DEF-127 again pointed at real money.

So §2 is a guard against this repo's own written prescription, and it is why
`BR-CUS-510` is four clauses rather than one. **A defect's prevention note is a
statement about the world on the day it was filed** (r11 step 0: *"was this
ruled since the doc I am about to build from was written?"*).

════════════════════════════════════════════════════════════════════════════
BR-CUS-510 — THE CELL MAY SAY *AWAITING* ONLY WHEN ALL FOUR HOLD
════════════════════════════════════════════════════════════════════════════
  1. the ledger **ANSWERED** (`positions.available`) — when it could not,
     `balance_unavailable` governs and says a different thing (DEF-127);
  2. the derived amount is **exactly zero** — §2's clause;
  3. the status behaviour **CLASS** is `non_billable` (never a code —
     BR-CUS-055 lets a tenant add and rename statuses);
  4. **no bill has ever been issued** (`last_bill_at is None`) — a cut account
     that has been billed has a history, and calling its settled zero
     *awaiting* would invent a future for a relationship that is over.

⚠ **THE FIGURE IS NEVER HIDDEN AND NEVER NULLED.** `balance` still serves the
ledger's `0.000000`; `balance_not_yet_billable` is served BESIDE it. Nulling it
would claim the books could not be asked, which is false.

PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
------------------------------------------------------
Run against `selectors.py` at the tip, before the fix:

  * §1 `test_def_628__pending_activation_is_awaiting_not_zero`
    → `AttributeError`/`KeyError: 'balance_not_yet_billable'` — the key did not
      exist, which IS the defect: nothing on the row distinguished the two zeros.
  * §2 `test_def_628__a_cut_account_owing_money_still_shows_the_figure`
    → PASSES at the tip and FAILS against the prevention-as-written
      (a one-line `not_yet_billable = account.status.behavior_class ==
      "non_billable"` makes `A-11488` read *awaiting* over $612.75).
    That is the point of §2: it is green today and it is the clause that stops
    tomorrow's "simplification".
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import seams as customers_seams
from apps.metering import models as metering_models

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _unit_for(tenant, label="Unit A"):
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line="12 Foundry Row", city="Katy", state="TX"
    )
    return metering_models.Unit.objects.create(tenant=tenant, premises=premises, label=label)


def _account(tenant, *, account_no, status_code, unit=None):
    status = customers_models.AccountStatus.objects.get(tenant=tenant, code=status_code)
    account_type = customers_models.AccountType.objects.get(code="residential")
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit or _unit_for(tenant, label=account_no),
        account_no=account_no,
        status=status,
        account_type=account_type,
    )


def _answered(account, amount):
    """An `ArPositions` whose books WERE asked and answered `amount`.

    Clause 1's input. `positions is not None` is the whole of `available`, so
    this is the shape a live ledger read produces — never a stub that refuses.
    """
    return customers_seams.ArPositions(
        positions={str(account.id): Decimal(amount)},
        currency="USD",
        basis="posting",
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT — a pending-activation account may not serve a settled zero
# ══════════════════════════════════════════════════════════════════════════
def test_def_628__pending_activation_is_awaiting_not_zero(growth_plan, identity_seam):
    """B18 §5.1.5, on the row the seed lane measured.

    All four clauses hold: the ledger answered, it answered zero, the class is
    `non_billable`, and nothing has ever been billed.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account(tenant, account_no="A-10001", status_code="pending_activation")
        row = customers_selectors.account_row(account, positions=_answered(account, "0"))

    assert row["status_behavior_class"] == "non_billable"
    assert row["last_bill_at"] is None
    # The figure is STILL SERVED and is still the ledger's — nothing is nulled.
    assert row["balance"] == "0.000000"
    assert row["balance_unavailable"] == ()
    # ...and the row now says which KIND of zero it is.
    assert row["balance_not_yet_billable"] is True


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE GUARD — DEF-628's OWN PRESCRIBED FIX, REFUSED
# ══════════════════════════════════════════════════════════════════════════
def test_def_628__a_cut_account_owing_money_still_shows_the_figure(growth_plan, identity_seam):
    """`A-11488`, cut owing **$612.75**, is `non_billable` — and shows $612.75.

    ⛔ This is the test that fails if a later lane implements DEF-628's
    prevention note as written (*"the cell should key off `non_billable`"*).
    BR-CUS-107 put `Disconnected` in that class the day after the note was
    written; a cut customer holds a debt, can pay it, and comes back.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account(tenant, account_no="A-11488", status_code="disconnected")
        row = customers_selectors.account_row(account, positions=_answered(account, "612.75"))

    assert row["status_behavior_class"] == "non_billable"  # the trap's premise
    assert row["balance"] == "612.750000"
    assert row["balance_not_yet_billable"] is False


def test_def_628__a_cut_account_at_zero_that_has_been_billed_is_not_awaiting(
    growth_plan, identity_seam
):
    """Clause 4, on its own. Settled and gone is not *awaiting a first bill*.

    A `non_billable` account sitting at exactly zero passes clauses 1–3; only
    the bill history separates *"nothing can be owed yet"* from *"this
    relationship is over and squared"*. Calling the second one *awaiting* would
    promise a bill that is never coming.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account(tenant, account_no="A-11490", status_code="disconnected")
        row = customers_selectors.account_row(
            account,
            positions=_answered(account, "0"),
            last_bill_dates={str(account.id): __import__("datetime").date(2026, 8, 18)},
        )

    assert row["last_bill_at"] == "2026-08-18"
    assert row["balance_not_yet_billable"] is False


# ══════════════════════════════════════════════════════════════════════════
# 3 · CLAUSE 1 — an UNREADABLE balance is not "not yet billable" either
# ══════════════════════════════════════════════════════════════════════════
def test_def_628__unreadable_books_stay_def_127s_absence_and_not_this_one(
    growth_plan, identity_seam
):
    """Two absences, two sentences. They must not collapse into each other.

    `balance_unavailable` says *the books could not be asked*; this flag says
    *the books answered nothing and nothing can be owed yet*. A screen shown the
    wrong one tells a clerk to wait for a bill when the real problem is that the
    tenant has designated no AR account.
    """
    tenant, _ = provisioned_tenant()
    refused = customers_seams.ArPositions(
        positions=None,
        unavailable=({"code": "ledger_unread", "br_ref": "DEF-127", "detail": "no AR account"},),
    )
    with tenant_ctx(tenant):
        account = _account(tenant, account_no="A-10002", status_code="pending_activation")
        row = customers_selectors.account_row(account, positions=refused)

    assert row["balance"] is None
    assert row["balance_unavailable"] != ()
    assert row["balance_not_yet_billable"] is False


# ══════════════════════════════════════════════════════════════════════════
# 4 · CLAUSE 3 — an ACTIVE account at zero is a settled account, and says so
# ══════════════════════════════════════════════════════════════════════════
def test_def_628__an_active_account_at_zero_is_settled_not_awaiting(growth_plan, identity_seam):
    """The ordinary, and by far the commonest, case — it must not move.

    `$0.00` on an ACTIVE account is the answer a customer wants: you owe us
    nothing. Turning that into *awaiting* would be this defect inverted, on
    every well-behaved account a utility has.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account(tenant, account_no="A-10003", status_code="active")
        row = customers_selectors.account_row(account, positions=_answered(account, "0"))

    assert row["status_behavior_class"] == "billable"
    assert row["balance"] == "0.000000"
    assert row["balance_not_yet_billable"] is False

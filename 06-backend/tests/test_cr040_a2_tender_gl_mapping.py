# ── Trace ──────────────────────────────────────────────
# Story:    CR-040 wave A tasks A2 + A3 (the books have somewhere to point)
#           Screens: S8 (Settings → Accounting → GL mapping, section 3)
# Rules:    BR-PAY-150 (CONFIRMED 2026-08-27 — every seeded tender clears
#           through Undeposited funds) · CLAUDE.md hard rule 7 (every money
#           action audits) · BR-TEN-012 (insert-missing: a tenant's own choice
#           is never overwritten) · hard-won law 4 (a template change never
#           reaches a host that already exists — hence the repair door)
# Tests:    this file
# Impacts:  apps/tenancy/services._map_tender_clearing_accounts ·
#           apps/tenancy/seams.ledger_account_id_for_designation ·
#           apps/ledger/services.gl_account_id_for_designation ·
#           apps/payments/ledger_seam.tender_clearing_account_id
# ───────────────────────────────────────────────────────
"""CR-040 task A3 — THE GUARD, and it may never pass over an empty estate.

WHAT DEF-891 WAS, IN ONE SENTENCE
----------------------------------
Every payment method a tenant was ever given carried `clearing_gl_account_id =
NULL`, and NULL is **lawful**: `apps/payments/ledger_seam.
tender_clearing_account_id` answers None and the receipt debits the
`undeposited_funds` designation exactly as it has since OQ-143. So nothing
refused, nothing was corrupt, and **every payment test passed** — because
posting DID succeed, into the fallback account. That is DEF-891's own
`escape_reason`, verbatim: *"THE FALLBACK IS THE CAMOUFLAGE … a documented,
deliberate, lawful default cannot be distinguished from a configured value by
any test that asks 'did posting succeed'."*

So this file asks a different question: **is the pointer STATED?**

THE NON-VACUOUS SHAPE, WHICH IS THE WHOLE REQUIREMENT (DEF-466 · DEF-828)
--------------------------------------------------------------------------
*"the unmapped set is EMPTY"* is satisfied by a tenant with **no tenders at
all**, and that is exactly how a ratchet rots: the fixture shrinks, the guard
keeps passing, and nobody learns anything. Every assertion below therefore
comes in a PAIR — the unmapped set is empty **and** the mapped set is
non-empty, counted on the same rows in the same transaction.

⚠ **AND THE MAPPED SET IS CHECKED AGAINST THE CHART, NOT AGAINST ITSELF.** A
pointer at a uuid that is not a live account of this tenant's own chart is
worse than a NULL: `tender_clearing_account_id` REFUSES the whole payment for
it (CR-008 B-10), so a bad mapping stops a utility taking money. The id is
resolved through the ledger's own `account_is_live`, the same read the settings
screen validates against.

WHAT IS DELIBERATELY **NOT** ASSERTED HERE — AND IT IS PINNED AS AN ABSENCE
----------------------------------------------------------------------------
`reason_codes.default_gl_account_id` stays NULL. CR-040 task **A1 is closed as
NOT TO BE SEEDED** (decision log 2026-08-27), for three measured reasons: no
backend path reads the column, the right revenue account for a billing-error
credit is the **service's** (4110 Water, 4100 Electric) and therefore a
property of the bill rather than of the reason, and the signed chart has no
general adjustments account to point at — adding one is a ❄️ FROZEN B5 line 74
change and a finance re-sign. `test_a1__reason_codes_stay_unmapped_on_purpose`
pins that so the next lane meets a decision instead of what looks like a gap.

RED-FIRST RECORD (hard-won law 7) — see the lane report for the verbatim
failures. Every test below was run against the tree before
`_map_tender_clearing_accounts` was wired in.
"""

from __future__ import annotations

import pytest

from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import admin_actor, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _tender_pointers(tenant):
    """`(mapped_ids, unmapped_codes)` for this tenant's payment methods."""
    rows = list(tenancy_models.PaymentMethod.objects.filter(tenant=tenant))
    mapped = [row.clearing_gl_account_id for row in rows if row.clearing_gl_account_id]
    unmapped = [row.code for row in rows if not row.clearing_gl_account_id]
    return mapped, unmapped


def _undeposited_funds_id():
    from apps.ledger import selectors as ledger_selectors

    return ledger_selectors.gl_account_id_for_designation("undeposited_funds")


def test_a3__no_seeded_tender_is_unmapped_and_the_mapped_set_is_not_empty():
    """CR-040 A3. **Both halves, or the guard is decoration.**

    The empty-set half alone passes over a tenant with no tenders; the
    non-empty half alone passes over a tenant with seven pointers at nonsense.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        mapped, unmapped = _tender_pointers(tenant)

    assert unmapped == [], (
        f"{len(unmapped)} seeded tender(s) carry no clearing account — {unmapped}. "
        "DEF-891: the pointer must be STATED, not left to the fallback"
    )
    # NON-VACUITY. Without this line an estate with zero tenders passes.
    assert len(mapped) >= 7, (
        f"only {len(mapped)} tender(s) are mapped — the fixture seeds seven "
        "(ach, card, check, cash, lockbox, wire, money_order), so this guard "
        "would be passing over an estate that lost most of them"
    )


def test_a3__every_pointer_is_a_live_account_of_this_tenants_own_chart():
    """A pointer at a dead or foreign account REFUSES the payment whole
    (`ledger_seam.tender_clearing_account_id`), so a wrong mapping is worse
    than a NULL. Checked through the ledger's own read, not by a join."""
    from apps.ledger import selectors as ledger_selectors

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        mapped, _unmapped = _tender_pointers(tenant)
        live = [account_id for account_id in mapped if ledger_selectors.account_is_live(account_id)]

    assert mapped, "no tender is mapped at all — this test would pass vacuously"
    assert len(live) == len(mapped), (
        "a tender points at an account that is not live in this tenant's chart; "
        "the payment path refuses the whole receipt for that (CR-008 B-10)"
    )


def test_a2__every_tender_clears_through_undeposited_funds():
    """The PO's own ruling, on rows: *"(a) Undeposited funds is the answer for
    every tender"* (2026-08-27, OQ-490).

    ⚠ It is `1010 Undeposited funds` and NOT `1000 Cash`, and the difference is
    the whole of OQ-143: money is not realised until the bank confirms it.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        mapped, _unmapped = _tender_pointers(tenant)
        undeposited = _undeposited_funds_id()

    assert undeposited is not None, "the seeded chart carries no undeposited_funds account"
    assert mapped, "no tender is mapped at all — this test would pass vacuously"
    assert {str(account_id) for account_id in mapped} == {str(undeposited)}, (
        "a tender clears somewhere other than Undeposited funds. Pointing one at "
        "1000 Cash recognises money as banked the moment it is taken and bypasses "
        "the deposit-batch and reconciliation flow entirely (OQ-490 option b, NOT ruled)"
    )


def test_a2__the_receipt_path_agrees_with_the_seeded_pointer():
    """**Built is not wired** (hard-won law 2), asked of DATA.

    The column could be perfectly seeded and read by nothing. This asserts the
    posting seam resolves the SAME account off a payment carrying the tender —
    the function `record_payment` actually calls.
    """
    from types import SimpleNamespace

    from apps.payments import ledger_seam

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        method = tenancy_models.PaymentMethod.objects.filter(tenant=tenant, code="check").first()
        assert method is not None
        resolved = ledger_seam.tender_clearing_account_id(SimpleNamespace(method=method))
        undeposited = _undeposited_funds_id()

    assert resolved is not None, (
        "the posting seam still resolves None for a mapped tender — the receipt would "
        "debit the fallback and the seeded value would be decoration"
    )
    assert str(resolved) == str(undeposited)


def test_a2__a_tenants_own_choice_is_never_overwritten():
    """BR-TEN-012's insert-missing posture, one field along.

    A clerk who picked an account on Settings → Accounting → GL mapping has
    made a decision. A repair run that overwrote it would be provisioning
    quietly undoing a human.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        cash = None
        from apps.ledger import selectors as ledger_selectors

        cash = ledger_selectors.gl_account_id_for_designation("cash")
        assert cash is not None
        row = tenancy_models.PaymentMethod.objects.filter(tenant=tenant, code="card").first()
        row.clearing_gl_account_id = cash
        row.save(update_fields=["clearing_gl_account_id"])

        tenancy_services._map_tender_clearing_accounts(tenant, admin_actor())
        row.refresh_from_db()

    assert str(row.clearing_gl_account_id) == str(
        cash
    ), "the repair run overwrote a tender the tenant had mapped themselves"


def test_a2__the_repair_door_maps_a_tenant_that_already_exists():
    """Hard-won law 4 in its data form: *a template change never reaches a host
    that already has a `.env`.* Every tenant provisioned before 2026-08-27
    carries seven NULL pointers, and only this door reaches them.

    Also the idempotency proof (BR-TEN-063): the second call maps nothing.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        tenancy_models.PaymentMethod.objects.filter(tenant=tenant).update(
            clearing_gl_account_id=None
        )
        _mapped_before, unmapped_before = _tender_pointers(tenant)
        first = tenancy_services._map_tender_clearing_accounts(tenant, admin_actor())
        second = tenancy_services._map_tender_clearing_accounts(tenant, admin_actor())
        mapped_after, unmapped_after = _tender_pointers(tenant)

    assert unmapped_before, "this test would pass vacuously — nothing was un-mapped to repair"
    assert first["mapped"] == len(unmapped_before)
    assert second["mapped"] == 0, "a replay re-wrote pointers that were already stated"
    assert unmapped_after == []
    assert len(mapped_after) == len(unmapped_before)


def test_a2__the_mapping_writes_an_audit_row(audit_rows):
    """CLAUDE.md hard rule 7. WHICH GL account receives a customer's cash is a
    money decision even when the account chosen is the one the posting path
    already fell back to.

    Read off the BE-03 capture sink, not off `audit_log`: `apps.audit`
    registers the real sink at `AppConfig.ready` and the test settings do not,
    so a query against the table answers 0 for EVERY provisioning row and would
    make this assertion a statement about the harness rather than the code.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        tenancy_models.PaymentMethod.objects.filter(tenant=tenant).update(
            clearing_gl_account_id=None
        )
        tenancy_services._map_tender_clearing_accounts(tenant, admin_actor())

    rows = [row for row in audit_rows if row["action"] == "reference.tender_gl_mapped"]
    # TWO, and both are named: PROVISIONING writes one (the seven tenders it
    # just planted) and the repair call above writes the second. Asserting "at
    # least one" would let the provisioning half rot away unnoticed, which is
    # the half a live tenant depends on.
    assert len(rows) == 2, (
        f"expected an audit row from provisioning AND one from the repair call, got " f"{len(rows)}"
    )
    for row in rows:
        after = row["after"]
        assert after["designation"] == "undeposited_funds"
        assert after["tenders"] >= 7
        # DEF-2377 — the key is `br_ref` now, because the S61 presenter drops a
        # machine field and would otherwise show a clerk a rule id. The row
        # still records which rule decided it.
        assert after["br_ref"] == "BR-PAY-150"


def test_a1__reason_codes_stay_unmapped_on_purpose():
    """⚠ **THIS ASSERTS AN ABSENCE, AND THE ABSENCE IS A DECISION.**

    CR-040 task A1 is closed as **NOT TO BE SEEDED** (decision log 2026-08-27).
    Nothing in the backend reads `reason_codes.default_gl_account_id`; the right
    revenue account for a billing-error credit is the SERVICE's, a property of
    the bill being corrected; and the signed chart holds no general adjustments
    account to point at, so seeding one would need a row added to ❄️ FROZEN B5
    line 74 and a finance re-sign.

    If this test ever fails because a lane seeded the column, the lane has
    resolved an open question by choosing a value — the fix is to revert it and
    take the question to the PO, not to update this assertion.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        reasons = list(tenancy_models.ReasonCode.objects.filter(tenant=tenant))
        mapped = [row.code for row in reasons if row.default_gl_account_id]

    assert len(reasons) >= 5, "the five seeded reason codes are missing — pass would be vacuous"
    assert mapped == [], (
        f"{mapped} now carry a default GL account. A1 is CLOSED AS NOT TO BE SEEDED — "
        "no posting path reads that column, and the right account for a billing-error "
        "credit belongs to the SERVICE being corrected, not to the reason chosen"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-040 wave A tasks A2/A3 + 12-governance/02-decision-log.md 2026-08-27 (OQ-490)
# generated: 2026-08-27 by the CR-040 wave A/D lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

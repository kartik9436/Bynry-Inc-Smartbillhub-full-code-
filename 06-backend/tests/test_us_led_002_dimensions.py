# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-002 (dimension stamping: service · account · premises+unit ·
#           source · tax authority on every line — TC-1 the WE-1 entry, TC-2
#           the LE-2 by-service slice, TC-3 the regrouping, TC-4 the unit
#           lifecycle, TC-5 the unresolvable chain, TC-6 isolation)
#           Screens: S56 · S36 · S60
# Rules:    BR-LED-001 (every line carries the dimension set, premises+unit
#           RESOLVED AT POSTING) · BR-MET-046 (units never move between
#           premises) · BR-REP-002 (read-models over dimensions, never a
#           side-maintained number) · BR-LED-015 (stamping is system posting
#           work) · CLAUDE.md rule 1 (tenant scoping) · rule 4 (a posted line
#           is immutable, so a stamp is permanent)
# Golden:   LE-2 (electric 100.60 · water 47.50 · sewer 15.80 · trash 18.00 ·
#           solar 40.00 · late 5.00 = 226.90) · LE-6 (500 Main St 247.87 ·
#           Oak Grove 16.42 · Marina Bay 289.40 → 553.69)
# ───────────────────────────────────────────────────────
"""US-LED-002 — the dimension that was CARRIED for five days and never RESOLVED.

BR-LED-001 has been CONFIRMED since 2026-08-08 (PO LF-1) and wants `premises_id`
and `unit_id` *"resolved account → unit → premises AT POSTING TIME"*. Until
2026-08-16 `apps/ledger/posting.py` carried both columns and resolved neither,
because neither customers nor metering published the read — so **every journal
line in the product held `premises_id = NULL`**, S60 answered `available: false`
over 553.69 of billed money, and the by-premises extract handed an ERP nothing.

`apps/ledger/dimension_seam.py` publishes the chain and
`apps/ledger/posting._stamped` consumes it. This file is that story's six test
cases, and the two that matter most are the ones that are NOT about the happy
path:

  * **TC-4** — a re-homed account must not move the money it has already been
    billed. The stamp is what makes a July report still say July's premises in
    December, and a read-time join is what would break it.
  * **TC-5** — an account whose chain cannot be resolved must stop the posting
    dead, not write a NULL. A skipped stamp and a lawful un-dimensioned line
    are the same row and opposite facts, and nothing downstream could tell them
    apart afterwards.
"""

from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.ledger import dimension_seam, models as ledger_models, posting, reporting

from tests.ledger_le_fixtures import (
    BILLED_IN_PERIOD,
    JULY_END,
    JULY_START,
    LE1_WE1_BILL,
    LE1_WE3_BILL,
    LE1_WE7B_BILL,
    LE2_BY_SERVICE,
    POSTED_AT,
    a_request,
    gl,
    make_accounts,
    post_le1_month,
    uuid_for,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")


def a_month(tenant, actor):
    world = {}
    accounts = make_accounts(actor, tenant, world)
    post_le1_month(tenant, accounts)
    return accounts, world


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — every line of a real entry carries the chain
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_002_tc1__every_line_naming_an_account_carries_premises_and_unit(brazos, dana):
    """US-LED-002 TC-1: *"revenue lines carry service, ACC-1042, premises 500
    Main St + unit, source_type + line id"*.

    Asserted per LINE rather than per entry, because the dimensions live on the
    line for a reason `models.JournalLine` states: one entry's lines span
    several services, several authorities and — on a master-account transfer —
    **two accounts**. An entry-level stamp would put both legs of LE-1's 135.90
    transfer on one premises and the by-premises report would be wrong by
    exactly that amount.
    """
    with tenant_ctx(brazos):
        accounts, _world = a_month(brazos, dana)
        expected = {
            str(account.pk): str(account.unit_id) for account in accounts.values()
        }

        lines = ledger_models.JournalLine.objects.filter(
            tenant=brazos, account_id__isnull=False
        )
        assert lines.count() > 0
        for line in lines:
            # BR-LED-001's two unconditional dimensions were already enforced.
            assert line.source_type and line.source_id
            # …and the two this story adds.
            assert str(line.unit_id) == expected[str(line.account_id)]
            assert line.premises_id is not None


def test_us_led_002_tc1b__a_line_that_names_no_account_is_left_alone(brazos, dana):
    """BR-LED-001 requires the dimensions *where they apply*, and this is the
    case where they do not.

    A cash leg of LE-1's opening entry names no customer account — it is money
    about the utility's own bank, not about anybody's address. Inventing a
    premises for it would put the utility's own balances onto a customer's row
    in every by-premises report, which is a wrong number rather than a missing
    one. So the rule is *resolve where an account is named*, and this asserts
    the other half of it.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        # A bank fee, exactly as `apps/payments/ledger_seam.post_bank_fee`
        # composes it: source_type and source_id, and deliberately NO account
        # dimension — its own comment says *"BR-LED-001's dimensions describe
        # WHOSE money a line is, and a bank charge is the utility's."*
        cash = gl(brazos, "1000", "asset")
        fees = gl(brazos, "6800", "expense")
        posting.post(
            a_request(
                (
                    posting.PostingLine(
                        ledger_account_id=fees.id,
                        side=ledger_models.SIDE_DEBIT,
                        amount=Decimal("5.00"),
                        source_type="payment",
                        source_id=uuid_for("a bounced payment"),
                    ),
                    posting.PostingLine(
                        ledger_account_id=cash.id,
                        side=ledger_models.SIDE_CREDIT,
                        amount=Decimal("5.00"),
                        source_type="payment",
                        source_id=uuid_for("a bounced payment"),
                    ),
                ),
                key="payment|tc1b|bank_fee",
            ),
            actor=dana,
        )

        anonymous = ledger_models.JournalLine.objects.filter(
            tenant=brazos, account_id__isnull=True
        )
        assert anonymous.count() == 2
        assert anonymous.filter(premises_id__isnull=False).count() == 0
        assert anonymous.filter(unit_id__isnull=False).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 / TC-3 — one dimension set, every slice (LE-2 → LE-6)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_002_tc2_tc3__the_same_rows_regroup_into_le2_and_le6(brazos, dana):
    """LE-2's own claim, now provable end to end: *"same query grouped by
    premises → LE-6; by authority → LE-3. One dimension set, every slice."*

    The point is not that either total is right on its own — it is that BOTH
    come out of the SAME journal lines. A by-premises figure maintained beside
    the by-service one is precisely what BR-REP-002 forbids (*"never a
    side-maintained number"*), and the way to prove there is only one number is
    to sum it two ways and get the same answer.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)

        by_service = {
            row.service_code: row.total_billed
            for row in reporting.revenue_by_service(start=JULY_START, end=JULY_END)
        }
        for code, total in LE2_BY_SERVICE.items():
            assert by_service[code] == total

        by_premises = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        billed = {row.name: row.billed for row in by_premises["rows"]}
        assert billed == {
            "500 Main St": LE1_WE1_BILL,
            "Oak Grove": LE1_WE3_BILL,
            "Marina Bay": LE1_WE7B_BILL,
        }
        assert by_premises["kpis"]["billed"] == BILLED_IN_PERIOD == Decimal("553.69")


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the stamp is permanent, and that is the whole reason it is a stamp
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_002_tc4__a_re_homed_account_never_moves_money_already_posted(brazos, dana):
    """US-LED-002 TC-4: *"historical lines keep their stamped premises_id /
    unit_id FOREVER — reporting on old periods is unchanged"*.

    The scenario, concretely: ACC-1042 is billed **247.87** at 500 Main St in
    July. In August the account is re-homed to a unit at Cedar Court. A
    read-time account → unit → premises join would move all 247.87 out of July's
    500 Main St row and into Cedar Court, and July's signed LE-6 figures would
    silently change months after the books closed.

    They do not, and cannot: the ids are columns on an immutable row (hard rule
    4 — there is no lawful UPDATE that could rewrite them). This test moves the
    account for real and then re-reads July.
    """
    with tenant_ctx(brazos):
        accounts, _world = a_month(brazos, dana)
        before = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        july_main_street = {row.name: row.billed for row in before["rows"]}["500 Main St"]
        assert july_main_street == LE1_WE1_BILL

        moved = accounts["ACC-1042"]
        elsewhere = make_premises(dana, address_line="Cedar Court", services_available=["electric"])
        new_unit = make_unit(dana, elsewhere["id"], label="9", services=["electric"])
        customer_models.Account.objects.filter(pk=moved.pk).update(unit_id=new_unit["id"])

        after = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        assert {row.name: row.billed for row in after["rows"]} == july_main_street_unchanged(
            july_main_street
        )
        assert "Cedar Court" not in {row.name for row in after["rows"]}


def july_main_street_unchanged(main_street_total):
    """LE-6's July table, restated for readability at the call site."""
    return {
        "500 Main St": main_street_total,
        "Oak Grove": LE1_WE3_BILL,
        "Marina Bay": LE1_WE7B_BILL,
    }


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — an unresolvable chain STOPS the posting (negative)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_002_tc5__an_unresolvable_account_refuses_and_writes_nothing(brazos, dana):
    """US-LED-002 TC-5, verbatim: *"posting fails atomically naming the gap — no
    undimensioned money line ever lands"*.

    The alternative — stamp what you can and leave NULL where you cannot — is
    refused for a reason that outlives this test: a skipped stamp produces
    exactly the same row as a LAWFUL un-dimensioned line (TC-1b's cash leg), and
    once both exist nothing downstream can tell a cash line from a customer line
    the books lost track of. The by-premises footer would quietly stop matching
    S36 and no gate would notice.

    *Atomically* is asserted as well as *fails*: the refusal happens before the
    transaction opens, so there is no entry, no line and no audit row afterwards.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        entries_before = ledger_models.JournalEntry.objects.filter(tenant=brazos).count()
        lines_before = ledger_models.JournalLine.objects.filter(tenant=brazos).count()

        ar = gl(brazos, "1200", "asset")
        revenue = gl(brazos, "4100", "revenue")
        stranger = uuid_for("an account this tenant does not have")
        request = a_request(
            (
                posting.PostingLine(
                    ledger_account_id=ar.id,
                    side=ledger_models.SIDE_DEBIT,
                    amount=Decimal("10.00"),
                    source_type="invoice",
                    source_id=uuid_for("a bill"),
                    account_id=stranger,
                ),
                posting.PostingLine(
                    ledger_account_id=revenue.id,
                    side=ledger_models.SIDE_CREDIT,
                    amount=Decimal("10.00"),
                    source_type="invoice",
                    source_id=uuid_for("a bill"),
                    account_id=stranger,
                ),
            ),
            key="invoice|tc5|issued",
        )

        with pytest.raises(posting.PostingError) as refusal:
            posting.post(request, actor=dana)

        message = str(refusal.value)
        assert str(stranger) in message
        assert dimension_seam.ACCOUNT_NOT_IN_REGISTER in message
        assert "US-LED-002 TC-5" in message

        assert ledger_models.JournalEntry.objects.filter(tenant=brazos).count() == entries_before
        assert ledger_models.JournalLine.objects.filter(tenant=brazos).count() == lines_before


def test_us_led_002_tc5b__a_line_already_carrying_the_chain_is_never_re_resolved(brazos, dana):
    """A reversal copies its original's stamps, and this is what protects that.

    `posting.reverse_entry` mirrors *"every line of the original, same account,
    same amount, same dimensions, the other side"*. If `_stamped` re-resolved a
    line that already carried both ids, a mirror posted in August would take
    AUGUST's chain — and the correction of a July bill would land on a different
    premises from the bill it corrects, which is the one thing a reversal may
    never do.
    """
    with tenant_ctx(brazos):
        accounts, _world = a_month(brazos, dana)
        original = (
            ledger_models.JournalLine.objects.filter(
                tenant=brazos, account_id__isnull=False
            )
            .order_by("created_at")
            .first()
        )

        # The account is re-homed AFTER the original was stamped …
        elsewhere = make_premises(dana, address_line="Quarry Row", services_available=["electric"])
        new_unit = make_unit(dana, elsewhere["id"], label="1", services=["electric"])
        customer_models.Account.objects.filter(pk=original.account_id).update(
            unit_id=new_unit["id"]
        )

        # … and the mirror still carries the ORIGINAL's premises.
        mirror = posting.reverse_entry(
            original.journal_entry_id,
            posting_key="reversal|tc5b|reversed",
            entry_date=JULY_END,
            posted_at=POSTED_AT,
            actor=dana,
        )
        mirrored = ledger_models.JournalLine.objects.filter(
            tenant=brazos, journal_entry_id=mirror.entry_id, account_id=original.account_id
        ).first()
        assert str(mirrored.premises_id) == str(original.premises_id)
        assert str(mirrored.unit_id) == str(original.unit_id)
        assert str(mirrored.unit_id) != str(new_unit["id"])


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_002_tc6__the_chain_never_resolves_across_a_tenant_boundary(
    brazos, dana, lonestar, erin
):
    """US-LED-002 TC-6: *"its lines only (RLS); grouping never sees Brazos Bend
    premises"*.

    The interesting failure is not a leaked row — the isolation suite already
    covers those. It is a leaked RESOLUTION: if the seam read customers or
    metering without a tenant scope, Lone Star Ridge could post an entry naming
    a Brazos Bend account and the chain would resolve, stamping a NEIGHBOUR's
    premises onto its own books. The tenant scoping is the owners' own (their
    published reads are RLS-bound), which is exactly why this seam does not
    re-implement it — and this test is what proves the inherited scoping bites.
    """
    with tenant_ctx(brazos):
        accounts, _world = a_month(brazos, dana)
        theirs = accounts["ACC-1042"]

    with tenant_ctx(lonestar):
        make_accounts(erin, lonestar, {}, service="water")
        # A Brazos Bend account id, resolved from inside Lone Star Ridge.
        assert dimension_seam.location_for_account(theirs.pk).problem == (
            dimension_seam.ACCOUNT_NOT_IN_REGISTER
        )
        # …and the by-premises report sees none of the neighbour's money.
        report = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        assert report["kpis"]["billed"] == ZERO
        assert report["rows"] == ()


# ── Lifecycle ─────────────────────────────────────────────
# packet: EP-LED-01 US-LED-002 §1/§3/§5/§7 · 04-docs/05-modules/09-ledger/02-business-rules.md
#         BR-LED-001 · 04-docs/05-modules/04-metering/02-business-rules.md BR-MET-046 ·
#         04-docs/05-modules/09-ledger/08-worked-examples.md LE-2/LE-6 · B2 Addendum r13 #1
# generated: 2026-08-16 by story-coder (US-LED-002 dimension lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — every case here was run against a mutated
#         `apps/ledger/posting._stamped` and seen to FAIL before the real one
#         was trusted; the verbatim failures are quoted in the human-review
#         ledger row for apps/ledger/dimension_seam.py
# exceptions: TC-1's tax-authority half is NOT asserted — `tax_authority_id` is
#         still NULL on every tax line because rating publishes no
#         `tax_authority_id_for_tax` (parked for G20 since 2026-08-11, and the
#         per-authority SPLIT works through the 2200-nn accounts instead per
#         BR-BIL-069). That is a different story's gap and is not smuggled in
#         here · TC-4 re-homes an account with a direct `.update()` because
#         `accounts.unit_id` is a REFUSED_FIELD on the edit path (BR-CUS-017);
#         the test needs the state, not the workflow
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

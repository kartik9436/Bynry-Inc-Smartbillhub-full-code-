# ── Trace ──────────────────────────────────────────────
# Story:    CR-040 (the seeded utility must have a FINANCIAL history) — the
#           tie-out guard the CR's step 5 ordering makes necessary and which
#           no task row named.  Screens: S36 (Tie-out panel), S8
# Rules:    BR-LED-007 (AR GL = Σ account balances · deposit-liability GL = Σ
#           deposits held · tax payable = remittance outstanding; ANY drift =
#           red flag + RELEASE BLOCKER) · CLAUDE.md hard rule 5 (balanced
#           pairs, written only by the posting service) · hard rule 4 (issued
#           invoices are append-only) · BR-TEN-056 as AMENDED 2026-08-16
# Golden:   none moved.  golden-verify stayed 33 PASS / 0 FAIL across this
#           work.  This file pins no ❄️ FROZEN figure — see §"what is pinned".
# Defects:  DEF-177 (the deposit register, open since 2026-08-16 — CLOSED
#           2026-08-28) · DEF-1713 (its MIRROR, found by this file — CLOSED
#           2026-08-28) · DEF-2250 (found by closing them: this row compared a
#           windowed control total against an undated register)
# Tests:    this file
# Impacts:  apps/billing/sample_data · apps/payments/sample_data ·
#           apps/customers/sample_data · apps/ledger/tie_out
# ───────────────────────────────────────────────────────
"""CR-040 — **do the seeded utility's books actually foot?**  Measured: mostly.

WHY THIS FILE EXISTS
--------------------
CR-040 turned the demo tenant from *one billed month* into a financial HISTORY:
two issued cycles, with payments, a carried credit, a refund and a corrected
overcharge written **between** them.  All of that posts to the ledger, and hard
rule 5 says the pairs must balance.

Two suites nearly covered it and neither did.  `test_us_led_004_tie_out.py`
runs the real tie-out against **hand-built LE fixtures** — it proves the CHECK
works and says nothing about the estate the PO clicks on.
`test_cr040_two_cycles.py` runs the real seeder on a real tenant and asks it
only how many invoices ISSUED — it never opens the ledger.

So the product's own release blocker had **never been pointed at the fixture it
ships with.**

WHAT THE MEASUREMENT FOUND — 2026-08-27, on a full plant
---------------------------------------------------------
155 journal entries, 506 journal lines, 47 June bills and 46 July bills issued,
one settled refund, one executed correction::

    accounts_receivable   AGREED     GL 5,171.18  register 5,171.18  drift  0.00
    deposit_liability     DRIFTING   GL     0.00  register   750.00  drift −750.00
    tax_payable           DRIFTING   GL   242.30  register   242.99  drift  −0.69

**Every one of the 155 entries balances.**  Hard rule 5 holds, and the AR
control account — the one that says *the money the bills claim is the money the
ledger carries* — agrees with the customer subledger **to the cent, at zero
drift, on a book with two issued cycles and the money between them.**  That is
the thing CR-040 most needed to be true and it is true.

The other two rows do not agree, and **neither is an unbalanced book**:

⚠ **RE-MEASURED 2026-08-28, AND THE DEPOSIT ROW IS NOW GREEN:**

    accounts_receivable   AGREED     GL 5,171.18  register 5,171.18  drift  0.00
    deposit_liability     AGREED     GL   750.00  register   750.00  drift  0.00
    tax_payable           DRIFTING   GL   242.30  register   242.99  drift  −0.69

The two deposit defects below are CLOSED (BR-CUS-670 / BR-CUS-671), and one more
was found in the process: the row was comparing a control total windowed at
`period_end` against an undated live column, so it read *GL 0.00 / register
750.00* over a book holding exactly 750.00 (DEF-2250 — the estate's cutover is
2026-08-27 and the fixture's last period ends 2026-08-14).  The measurement
below is kept as the record of what was found on 2026-08-27; what the file now
ASSERTS is the paragraph above.

* **deposit_liability, −750.00 — the MIRROR of `DEF-177`, filed as `DEF-1713`.**
  DEF-177 (open since 2026-08-16) says the register column is never written
  while payments credits the GL — *books 150.00 / register 0.00*.  The seeded
  estate shows the opposite: the migrated deposits arrive through
  `create_from_import` (`IMPORT_ACCOUNT_FIELDS`, US-CUS-023), which writes
  `accounts.deposit_on_file` and **posts nothing**, so the register carries
  750.00 that the balance sheet has never heard of.  Same column, opposite
  direction, different cause — and a real utility's migrated deposit is money
  it owes back.
* **tax_payable, −0.69 — a basis mismatch the product already names**, cause
  `tax_outstanding_is_the_billed_basis_only`.  Not a lost 69 cents: the two
  sides are computed over different bases and the row says so itself.

WHAT IS PINNED HERE, AND WHAT DELIBERATELY IS NOT
--------------------------------------------------
**No money figure is asserted.**  Not 5,171.18, not 750.00, not 0.69.  A
fixture's receivables total is not a signed number — nothing in ❄️ B4/B5 says
what a demo's books should total — and a guard that reddens every time a lane
adds a case to the estate is a guard people are trained to edit.  An edited
tie-out guard is no guard.

What is asserted instead is a **shape**, in both directions:

1. every entry balances, per entry, and there are entries to balance;
2. AR is `AGREED` at **exactly zero drift** with **both sides non-zero**;
3. the drifting set is **exactly** `{deposit_liability, tax_payable}`, each
   carrying its named cause.

Assertion 3 is the important one and it is a **stated absence** in the shape
B7's guard established.  It goes RED **two ways**: red if a *third* subledger
starts drifting — a new fault, which is what this file is for — and red the day
someone *fixes* DEF-177/DEF-1713 or the tax basis, which is the day this guard
should be tightened to demand a clean book.  A test that merely tolerated
"some drift" would do neither.

WHY THE JUNE BOUNDARY IS CHECKED SEPARATELY
--------------------------------------------
A drift introduced by cycle one and cancelled by cycle two would pass an
end-state check.  That is not hypothetical here: the money cases sit BETWEEN
the runs by design (task D14).  ⚠ **And the June check is nearly vacuous for
AR, which is itself worth knowing:** June's bills are dated `bill_on` 2 July,
so as of 30 June the AR control and the register are both 0.00 and the row is
AGREED about nothing.  The test says so rather than counting it as evidence.

RED-FIRST RECORD (hard-won law 7) — each mutation was run, not imagined:

4. **2026-08-28 — `..._the_deposit_register_now_equals_the_deposit_liability`
   was run against the tree BEFORE the fix and failed
   `AssertionError: the deposit register and the books disagree again: GL 0
   vs register 750.000000 (drift -750.000000)`.** That is the red proof for the
   new assertion, and it is the defect stated in the assertion's own words.

1. **The whole file first ran with assertion 3 written as "nothing drifts".**
   It failed on exactly the two rows above, printing both figures and both
   causes — which is how the deposit mirror was found.  That failure IS the
   red-proof for the drift assertions, and DEF-1713 came out of it.
2. `..._balanced_pairs` with the comparison inverted (`==` for `!=`) failed on
   **all 155 entries**, printing real pairs — `debit 64.800000 credit
   64.800000`, `103.020000 / 103.020000` — which proves two things at once:
   the test reads real rows rather than an empty set, and all 155 genuinely
   balance.
3. `..._non_vacuous` against a provisioned-but-UNSEEDED tenant failed
   `AssertionError: cycle one issued nothing / assert 0 > 0` — the assertion
   that makes every green in this file mean anything.

Both mutations were run on 2026-08-27 (`2 failed in 112.33s`), observed, and
reverted; the unmutated file is `5 passed in 241.22s`, exit 0.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import correction_models
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.ledger import models as ledger_models, tie_out
from apps.payments import models as payment_models
from apps.tenancy import sample_data
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: The subledgers that drift on the seeded estate TODAY, each with the cause the
#: product itself names for it, and the defect that owns the fix.  This is a
#: STATED ABSENCE, not a tolerance: the test asserts this set EXACTLY, so it
#: reddens when a third row joins it and when any member leaves it.
KNOWN_DRIFT = {
    # ⚠ **`deposit_liability` LEFT THIS SET ON 2026-08-28 — DEF-177 and
    # DEF-1713 ARE FIXED, and this file said in advance that its own guard
    # should be tightened on that day rather than edited around.**  The estate
    # now reads **GL 750.00 / register 750.00, AGREED at zero drift**, and the
    # tightening is the assertion below (`..._the_deposit_register_now_equals
    # _the_deposit_liability`) rather than a silent deletion: a name that just
    # goes missing from a banked set proves nothing about what replaced it.
    tie_out.SUBLEDGER_TAX: (
        "tax_outstanding_is_the_billed_basis_only",
        "the two sides are computed over different bases and the row says so",
    ),
}


def _real_admin(tenant):
    """An actor whose id resolves to a real user row.

    BR-BIL-058's fifth fact is WHO authorised the run, and `authorise_release`
    refuses a null `confirmed_by` — correctly, since a bill run authorised by
    nobody is not authorised.  The shared `admin_actor()` helper is a namespace
    with a random uuid, which several blocks get away with and a bill run
    cannot.  Duplicated from `test_cr040_two_cycles` rather than shared: the two
    files are read independently, and a helper living in one is a surprise in
    the other.
    """
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(
        tenant=tenant, email="demo.owner@example.invalid"
    ).first() or identity_models.User.objects.create(
        tenant=tenant, email="demo.owner@example.invalid", full_name="Demo Owner"
    )
    return SimpleNamespace(id=user.id, role="system_admin")


def _seeded_tenant():
    """A real tenant, provisioned and seeded through the real orchestrator.

    Nothing is hand-written.  The point of this file is the estate the PO gets,
    so it must come through the same door the Sample data panel presses.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
    return tenant


def _estate_evidence() -> dict[str, int]:
    """What the seeded book actually contains — the non-vacuity witnesses."""
    issued = {
        period["key"]: billing_models.Invoice.objects.filter(
            bill_run__period_start=period["start"],
            bill_run__period_end=period["end"],
            status="issued",
        ).count()
        for period in fixture.PERIODS
    }
    return {
        "june_issued": issued["june"],
        "july_issued": issued["july"],
        "august_issued": issued[fixture.PERIODS[-1]["key"]],
        "refunds_settled": payment_models.Refund.objects.filter(
            status__in=(payment_models.REFUND_ISSUED, payment_models.REFUND_CLEARED)
        ).count(),
        "corrections_done": correction_models.CorrectionCase.objects.filter(
            status=correction_models.CASE_DONE
        ).count(),
        "journal_entries": ledger_models.JournalEntry.objects.count(),
        "journal_lines": ledger_models.JournalLine.objects.count(),
    }


def test_cr040__the_seeded_estate_is_a_real_financial_history_before_anything_is_believed():
    """The witnesses, asserted on their own so a failure here is legible.

    If THIS test is the one that reddens, every tie-out result below is
    meaningless and the reader needs to know that first — which is why it is a
    test rather than an assertion buried in the others.  Same shape as
    DEF-828's guard: prove the set is NON-EMPTY in the transaction that proves
    the check passes over it.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        evidence = _estate_evidence()

    assert evidence["june_issued"] > 0, "cycle one issued nothing"
    assert evidence["july_issued"] > 0, "cycle two issued nothing"
    # CR-040 step 5 row 7, and CR-010 Part-10.4's surviving intent: the third
    # period is the PO's own acceptance run.
    assert evidence["august_issued"] == 0, "August must stay unbilled"
    assert evidence["refunds_settled"] > 0, "wave D's refund never reached issue"
    assert evidence["corrections_done"] > 0, "wave D's correction never executed"
    # 33 is the seeded chart's own size.  More ENTRIES than the chart has
    # ACCOUNTS is a cheap, stable way of saying "money actually moved" without
    # pinning a count every future fixture case would have to edit.
    assert evidence["journal_entries"] > 33, (
        "the ledger holds fewer entries than the chart has accounts — the money "
        "cases did not post"
    )
    assert evidence["journal_lines"] >= 2 * evidence["journal_entries"]


def test_cr040__every_seeded_journal_entry_is_a_balanced_pair():
    """CLAUDE.md hard rule 5, over the whole seeded book.

    Not a sample, and not the grand total: **per entry**.  A book whose total
    nets to zero can still hold two entries each wrong by the same amount in
    opposite directions, which is exactly what a posting-service bug produces.
    Summing per entry is what catches it.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        debits: dict[str, Decimal] = defaultdict(lambda: ZERO)
        credits: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for entry_id, side, amount in ledger_models.JournalLine.objects.values_list(
            "journal_entry_id", "side", "amount"
        ):
            key = str(entry_id)
            if side == ledger_models.SIDE_DEBIT:
                debits[key] += amount
            else:
                credits[key] += amount
        entry_count = ledger_models.JournalEntry.objects.count()

    unbalanced = {
        key: (debits[key], credits[key])
        for key in set(debits) | set(credits)
        if debits[key] != credits[key]
    }
    assert not unbalanced, (
        f"{len(unbalanced)} seeded journal entries do not balance: "
        + "; ".join(f"{k} debit {d} credit {c}" for k, (d, c) in list(unbalanced.items())[:5])
    )
    # NON-VACUITY: an empty ledger balances perfectly.
    assert entry_count > 33, "no entries to balance — the seed did not post"
    assert len(set(debits) | set(credits)) == entry_count, (
        "an entry exists with no lines at all — it balances vacuously"
    )


def test_cr040__the_receivables_control_agrees_with_the_customer_subledger():
    """The row CR-040 most needed to be true: **AR ties out at zero drift.**

    *The money the bills claim is the money the ledger carries*, on a book with
    two issued cycles, payments, a carried credit, a refund and a corrected
    overcharge between them.  Measured 2026-08-27 at 5,171.18 on both sides.

    The figure is NOT pinned — see the module docstring.  What is pinned is
    `drift == 0` with **both sides non-zero**, because `AGREED` over 0.00
    against 0.00 is a row that agreed with itself about nothing, and after two
    issued cycles with July uncollected by design (`collected_share` 0) this
    estate must owe money.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        evidence = _estate_evidence()
        result = tie_out.tie_outs(
            period_start=fixture.PERIODS[0]["start"],
            period_end=fixture.PERIODS[-1]["end"],
        )
        rows = {row.subledger: row for row in result["rows"]}

    # The tie-out below is only meaningful about a book that holds two cycles
    # and the money between them — asserted in THIS transaction.
    assert evidence["july_issued"] > 0 and evidence["corrections_done"] > 0

    ar = rows[tie_out.SUBLEDGER_AR]
    assert ar.state == tie_out.STATE_AGREED, (
        f"the receivables control does not agree with the customer subledger: "
        f"GL {ar.gl} vs register {ar.register} (drift {ar.drift})"
    )
    assert ar.gl is not None and ar.register is not None
    assert ar.gl != ZERO, (
        "the AR control account is empty after two issued cycles — this row "
        "agreed with itself about nothing"
    )
    assert ar.register != ZERO
    assert ar.drift == ZERO


def test_cr040__exactly_the_two_known_subledgers_drift_and_each_names_its_cause():
    """The STATED ABSENCE, and it reddens in both directions.

    RED if a **third** subledger starts drifting — a new fault, which is what
    this file exists to catch.  RED the day DEF-177 / DEF-1713 or the tax basis
    is **fixed** — which is the day this guard should be tightened to demand a
    clean book and `release_blocked is False`.

    A test that merely tolerated "some drift" would do neither, and would go
    quietly green over a demo whose books had stopped footing.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        result = tie_out.tie_outs(
            period_start=fixture.PERIODS[0]["start"],
            period_end=fixture.PERIODS[-1]["end"],
        )
        rows = {row.subledger: row for row in result["rows"]}

    drifting = {row.subledger for row in result["rows"] if row.state == tie_out.STATE_DRIFTING}
    assert drifting == set(KNOWN_DRIFT), (
        "the set of drifting subledgers has MOVED.\n"
        f"  expected (each with a filed cause): {sorted(KNOWN_DRIFT)}\n"
        f"  measured:                           {sorted(drifting)}\n"
        "A NEW name here is a new fault in the seeded books. A name that has "
        "GONE means its defect was fixed — tighten this guard to require a "
        "clean tie-out rather than deleting the name."
    )

    # Nothing may be UNVERIFIABLE: BR-LED-007 blocks a release on it for the
    # same reason it blocks on a drift — a row nobody could compute has proved
    # nothing, and folding it in with the greens is how a demo ships on a check
    # that never ran.
    unverifiable = [
        f"{row.subledger}: GL {row.gl} vs register {row.register}"
        for row in result["rows"]
        if row.state == tie_out.STATE_UNVERIFIABLE
    ]
    assert not unverifiable, "a seeded subledger is unreadable: " + "; ".join(unverifiable)

    # Each known drift must still NAME its cause. A drift that lost its cause is
    # an unexplained one wearing a known one's clothes.
    for subledger, (cause_code, _why) in KNOWN_DRIFT.items():
        row = rows[subledger]
        codes = {cause.get("code") for cause in row.causes}
        assert cause_code in codes, (
            f"{subledger} drifts by {row.drift} and no longer names "
            f"{cause_code!r} — its causes are {sorted(c for c in codes if c)}"
        )
        # Both sides readable, so "drifting" is a real comparison and not a
        # missing figure reported as a difference.
        assert row.gl is not None and row.register is not None


def test_cr040__the_deposit_register_now_equals_the_deposit_liability():
    """DEF-177 + DEF-1713 CLOSED — measured on the estate the PO clicks on.

    Before 2026-08-28 this row read **GL 0.00 / register 750.00**: five migrated
    accounts each holding $150.00 of a customer's money, written to
    `accounts.deposit_on_file` by `create_from_import` and posted NOWHERE.  It
    now reads **750.00 on both sides**, because the same import handoff posts a
    balanced opening entry per account (DR opening clearing / CR 2300, dated at
    cutover — BR-CUS-671) and a cleared deposit moves the register through
    customers' own writer (BR-CUS-670).

    ⚠ **THE FIGURE IS NOT PINNED and both sides being NON-ZERO is.**  750.00 is
    a fixture total, not a signed number — a lane adding a sixth deposit case
    must not have to edit a tie-out guard, because an edited tie-out guard is no
    guard (this file's own rule).  What is pinned is the property: the two sides
    are EQUAL, and they are equal about real money rather than about two zeros.
    """
    tenant = _seeded_tenant()
    with tenant_ctx(tenant):
        result = tie_out.tie_outs(
            period_start=fixture.PERIODS[0]["start"],
            period_end=fixture.PERIODS[-1]["end"],
        )
        rows = {row.subledger: row for row in result["rows"]}
        registered = sum(
            (
                held or ZERO
                for held in customer_models.Account.objects.values_list(
                    "deposit_on_file", flat=True
                )
            ),
            ZERO,
        )

    deposits = rows[tie_out.SUBLEDGER_DEPOSITS]
    assert deposits.state == tie_out.STATE_AGREED, (
        f"the deposit register and the books disagree again: GL {deposits.gl} vs register "
        f"{deposits.register} (drift {deposits.drift}) — DEF-177 / DEF-1713"
    )
    assert deposits.drift == ZERO
    # NON-VACUITY, twice over: the estate must actually HOLD deposits, and the
    # register the tie-out read must be the same register the accounts carry.
    assert registered > ZERO, "the seeded estate holds no deposits — this row agreed about nothing"
    assert deposits.gl == registered
    assert deposits.register == registered
    assert deposits.blocks_release is False


def test_cr040__the_books_are_asked_at_the_june_boundary_too_not_only_at_the_end():
    """A drift introduced by cycle one and cancelled by cycle two would pass an
    end-state check — and the money cases sit BETWEEN the runs by design (D14),
    so that is the shape this fixture actually has.

    ⚠ **The June AR row is nearly vacuous and this test says so rather than
    counting it as evidence:** June's bills are dated `bill_on` 2 July, so as of
    30 June the control and the register are both 0.00.  What June DOES prove is
    that no *extra* subledger drifts at that boundary.

    ⚠ **AND THE DEPOSIT ROW NO LONGER MOVES WITH THE BOUNDARY AT ALL — DEF-2250,
    2026-08-28.**  This docstring used to cite *"the deposit register is already
    750.00 against an empty GL before a single bill has issued"* as evidence that
    DEF-1713's cause was the import door.  It was true and it was reached by a
    faulty comparison: `_deposit_row` windowed the control account at
    `period_end` and compared it against `accounts.deposit_on_file`, an UNDATED
    live column, so the GL side read 0.00 at any boundary before the estate's
    2026-08-27 cutover whatever the books held.  The row now takes no `as_of` —
    both sides are cumulative — so it reads the same 750.00 = 750.00 here as at
    the end of the fixture, which is the correct answer to *"how much of our
    customers' money do we hold"*.
    """
    tenant = _seeded_tenant()
    june = fixture.PERIODS[0]
    with tenant_ctx(tenant):
        at_june = tie_out.tie_outs(period_start=june["start"], period_end=june["end"])

    drifting = {row.subledger for row in at_june["rows"] if row.state == tie_out.STATE_DRIFTING}
    assert drifting <= set(KNOWN_DRIFT), (
        "a subledger drifts at the JUNE boundary that does not drift at the end "
        f"of the fixture — cycle two is cancelling a cycle-one fault: {sorted(drifting)}"
    )
    unverifiable = [
        row.subledger for row in at_june["rows"] if row.state == tie_out.STATE_UNVERIFIABLE
    ]
    assert not unverifiable, f"unreadable subledger at the June boundary: {unverifiable}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-040 (12-governance/11-change-requests.md) + BR-LED-007 +
#         CLAUDE.md hard rule 5 + apps/ledger/tie_out.py + DEF-177
# generated: 2026-08-27 by the CR-040 tie-out lane
# checklist: A=n/a(no backend change) B=n/a(no UI) C✔ D✔(RED-first record in the
#            module docstring; the drift assertions were red-proved by the file's
#            own first run, which is what found DEF-1713)
# gates: golden-verify 33 PASS / 0 FAIL, unmoved — this file pins no ❄️ figure
# exceptions: this guard PASSES over a book that does not fully tie out, and the
#             module docstring states why: the two drifts are filed defects with
#             named causes, and pinning them as a STATED ABSENCE reddens on a
#             third fault AND on their fix. Weakening the comparison to make the
#             row green — the thing DEF-177 explicitly warns against — would
#             compare the ledger against itself and is not done here.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

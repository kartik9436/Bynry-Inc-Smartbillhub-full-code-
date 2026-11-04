# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (chart of accounts — TC-1 seeded at provisioning,
#           TC-6 isolation; the designation attribute is what makes a
#           tenant-customizable chart usable by a posting entry)
#           Screens: S56 · S8
# Rules:    BR-BIL-010 (service → revenue GL with an OPTIONAL usage/base split;
#           AR / deposit-liability / clearing / write-off designations) ·
#           BR-LED-015 (every chart change writes audit_log) · BR-TEN-012
#           (seeding never overwrites a tenant-touched row) · CLAUDE.md rule 1
#           (tenant scoping; RLS FORCE)
# ───────────────────────────────────────────────────────
"""The GL designations: the thing that lets a journal entry find its accounts.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_005_tc1__a_designation_resolves_by_name_after_the_tenant_renumbers`.
OQ-106 was raised because the posting service could not resolve "the AR
account" without writing `1200` into Python, while US-LED-005 makes the chart
tenant-customizable. That test renumbers accounts receivable from 1200 to 1150,
renames it, and requires the lookup to still land. Any future change that
reintroduces a hardcoded code fails it — which is the only reason the defect
cannot come back.

WHAT RUNS WHERE. Shape, constraints, the seed and the selectors run on SQLite
and Postgres alike. The two `-m isolation` cases at the bottom carry
`requires_postgres` and prove the DATABASE refuses a cross-tenant read of a
designation under a NOSUPERUSER probe role — on SQLite they SKIP with a vendor
reason rather than passing vacuously.
"""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from core import errors

from apps.ledger import chart
from apps.ledger import models as ledger_models
from apps.ledger import selectors as ledger_selectors
from apps.ledger import services as ledger_services
from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db


def account_for(tenant, code):
    return ledger_models.LedgerAccount.objects.get(tenant=tenant, code=code)


def timezone_now():
    """IS-1 deactivation stamp. A helper so the several tests that deactivate
    an account do it identically."""
    return timezone.now()


# ═══════════════════════════════════════════════════════════════════════════
# The chart file is internally consistent — the OQ discipline, as a test
# ═══════════════════════════════════════════════════════════════════════════
def test_the_designation_set_is_exactly_the_eleven_the_po_ruled():
    """PO ruling 2026-08-11 closing OQ-110, option A — *"all seven now"*, on
    top of the four BR-BIL-010 already confirmed.

    The count is asserted as well as the membership. *"Do not invent a twelfth
    designation"* is a standing instruction, and a twelfth added quietly would
    otherwise pass every other test in this file: it would simply resolve to
    None everywhere and look like an unconfigured account.

    **A TWELFTH ARRIVED ON 2026-08-15, AND THIS TEST IS WHY IT ARRIVED PROPERLY.**
    An attempt to add `budget_variance` as a bare constant went RED here and in
    `apps/ledger/selectors` before reaching the database, which forced it through
    the route OQ-110 priced: a PO ruling (*"Create seperate account"*, OQ-142),
    an entry in the closed set, and `ledger/0006` to move the CHECK constraint.
    The guard is unchanged in spirit — the set is still CLOSED and still counted;
    it now closes at twelve, and a thirteenth still goes RED.
    """
    assert chart.GL_DESIGNATIONS == (
        # The eleven of 2026-08-11 (OQ-110), in the PO's own order.
        "accounts_receivable",
        "deposit_liability",
        "opening_clearing",
        "write_off",
        "minimum_bill_adjustment",
        "customer_credit_balance",
        "cash",
        "undeposited_funds",
        "unbilled_ar",
        "bank_fees",
        "deposit_interest_expense",
        # The twelfth, ruled 2026-08-15 (OQ-142).
        "budget_variance",
        # ⚠ **THE THIRTEENTH, RULED 2026-08-28 — and it arrived through the same
        # door for the same reason.** The PO answered the designation question
        # DEF-536 was blocked on: *"you will need differnt GL code for these -
        # dont keep them in same, create differnt category as required and keep
        # them in it"*. A bare constant went RED here and in
        # `apps/ledger/selectors` before reaching the database, which forced it
        # through `ledger/0009` to move the CHECK. The set is still CLOSED and
        # still counted; it now closes at thirteen, and a fourteenth goes RED.
        "discount_contra_revenue",
        # ⚠ **FOURTEEN, FIFTEEN AND SIXTEEN — `CR-060` T7b and T7f, 2026-09-02.**
        # The month-end cost accrual needed something to CREDIT and depreciation
        # needed both sides. `accrued_expenses` lands on `2100` and
        # `accumulated_depreciation` on `1730` (both `UTILITY_BOOKS_CHART` rows
        # the PO ruled into existence on 2026-09-01/02); `5700 Depreciation
        # expense` is MINTED, because the PO's own 111-row reference chart
        # carries four accumulated-depreciation accounts and nothing to charge
        # against them. `ledger/0014` moved the CHECK.
        "accrued_expenses",
        "depreciation_expense",
        "accumulated_depreciation",
        # ⚠ **SEVENTEEN — `CR-060` T15, PO ruling 2026-09-03**, over a
        # recommendation to defer: *"Why I recommended deferring it. Three
        # reasons: let's do this"*. `1290 Allowance for doubtful accounts` was
        # withheld for two days by `chart.py` judgment 3 precisely because
        # seeding it offers an accounting policy the product did not implement;
        # the product implements it now. `ledger/0015` moved the CHECK.
        "allowance_doubtful_accounts",
        # ⚠ **EIGHTEEN — `CR-136-BRC07` §3.3, PO ruling 2026-09-23.** A drawer
        # counted at the end of a shift and found short or over now writes a
        # balanced pair, which the payments blueprint said in as many words it
        # would NOT do (*"The ledger: Nothing — counting is not a posting"*).
        # PO verbatim: *"(b) Post it. A short writes a balanced pair to a cash
        # over/short account the day it is declared. Needs one new account
        # added to the chart"*. **ONE designation for BOTH directions** — a
        # short debits `6850` and an over credits it — and `ledger/0016` moved
        # the CHECK. A second `cash_over` pointer is refused by
        # `tests/test_cr136_p221_cash_over_short_account.py`.
        "cash_over_short",
        # PO 2026-10-29 (CR-197-BRC10, BR-LED-803) — the nineteenth: a refund
        # has its own account role. NOT seeded — the tenant picks it on the GL
        # mapping list, and until then a refund credits cash as before.
        "refunds_payable",
    )
    # ⚠ **MOVED 2026-09-03 (`DEF-3441`). THIS PINNED THIRTEEN AND HAD BEEN RED
    # SINCE 2026-09-02** — `CR-060` T7b added three designations and neither
    # that lane nor `CR-061`'s ran this file. The guard is unchanged in spirit:
    # the set is still CLOSED, still counted, and a TWENTIETH still goes RED
    # (nineteen since CR-197-BRC10 added `refunds_payable`, 2026-10-29).
    assert len(chart.GL_DESIGNATIONS) == 19


def test_every_designation_has_a_home_in_the_finance_signed_chart():
    """A designation with no seeded account is a designation nothing can ever
    resolve — the exact hole OQ-110 was raised to close, in reverse.

    **THE EXCEPTION THIS TEST USED TO PIN IS CLOSED, AND THE CLOSING IS THE
    POINT.** From 2026-08-15 `budget_variance` was the one designation with no
    seeded home, because its account was an addition to ❄️ frozen B5 line 74
    that no agent could write. The PO closed it on 2026-08-17 (CR-010 B-8),
    verbatim: *"8 - A ✅ 4180 "Budget billing variance", revenue, signed=False
    (the 4160/4170 precedent)"* — so all TWELVE designations now seed, the
    pending-designation tuple is empty, and 4180 carried `signed=False` while
    its finance re-sign (HUMAN-GUIDE §6) was owed. This test went RED on the old
    pins the moment 4180 landed, which is the guard working.

    ⚠ **AND IT WENT RED AGAIN THE SAME DAY, WHICH IS THE GUARD WORKING TWICE.**
    The Product Owner finance re-signed 4180 on **2026-08-18** — in the working
    chat session, shown the code and the name in plain English (**4180 Budget
    billing variance, revenue**) alongside the eight cost accounts, with the
    explicit statement that no dollar figure is attached to any of the nine and
    that B4/B5 stay ❄️ FROZEN and were NOT edited. So the pin below is INVERTED
    to `signed=True` with the ruling named. **What the signature covers is the
    code and the name.** The WE-8 figures this account exists to hold (292.87
    recognised, 242.00 asked, 50.87 standing) were NOT re-signed by it and stay
    where B4/B5 put them.
    """
    assert chart.PENDING_FINANCE_RESIGN == ()
    # ⚠ **MOVED 2026-09-03 (DEF-3441). THIS READ `sorted(SEEDED) ==
    # sorted(GL_DESIGNATIONS)` AND `len(SEEDED) == 13`, AND BOTH WENT RED ON
    # 2026-09-02 WHEN FOUR DESIGNATIONS ARRIVED THAT THE SEED CHART DOES NOT
    # PLACE.** Three of them are claimed on first use (`chart.
    # DESIGNATED_ON_FIRST_USE`) and one, `depreciation_expense`, is placed by
    # `PERIOD_MATCHING_CHART`, which is a seed tuple of its own rather than
    # `SEED_CHART`. The guard's SPIRIT is unchanged and is what is asserted
    # below: every designation has a home, and the homes are enumerated rather
    # than assumed — so a designation added with no home anywhere still goes
    # RED, which is the whole reason this assertion exists.
    homed = (
        set(chart.SEEDED_DESIGNATIONS)
        | {row.designation for row in chart.PERIOD_MATCHING_CHART if row.designation}
        | {row.designation for row in chart.ALLOWANCE_CHART if row.designation}
        | set(dict(chart.PERIOD_MATCHING_PLACEMENTS))
        # CR-197-BRC10: `refunds_payable` is homed by the TENANT's own choice on
        # the GL mapping list, never by a seed (BR-LED-803).
        | set(chart.CHOSEN_BY_TENANT)
    )
    assert homed == set(chart.GL_DESIGNATIONS), sorted(set(chart.GL_DESIGNATIONS) - homed)
    # ⚠ 14 since 2026-09-23: `cash_over_short` is SEEDED (`6850`), not claimed
    # on first use — every utility that takes cash at a counter has drawers, so
    # the account ships with the chart and `ensure_cash_over_short_account` is a
    # repair door rather than the plan (CR-136-BRC07 §3.3).
    assert len(chart.SEEDED_DESIGNATIONS) == 14
    assert len(chart.SEEDED_DESIGNATIONS) == len(set(chart.SEEDED_DESIGNATIONS))
    # The twelfth designation's home, pinned: 4180, revenue, and SIGNED since
    # the HUMAN-GUIDE §6 re-sign of 2026-08-18 (this read `False` until then).
    # The name is pinned as well as the code, because the name is half of what
    # was put to the PO and a rename is not covered by that signature.
    home = [row for row in chart.SEED_CHART if row.designation == chart.BUDGET_VARIANCE]
    assert [(row.code, row.name, row.type, row.signed) for row in home] == [
        ("4180", "Budget billing variance", "revenue", True)
    ]


def test_the_seed_chart_matches_the_finance_signed_codes():
    """B5 line 74, ❄️ finance-signed 2026-08-08 — the pairing, transcribed.

    Written out as literals rather than derived from the same tuple the code
    reads, so an edit to `chart.py` has to be made TWICE and deliberately. The
    figures are the PO's own, from the decision log's OQ-110 closure.
    """
    by_designation = {row.designation: row.code for row in chart.SEED_CHART if row.designation}
    assert by_designation == {
        "accounts_receivable": "1200",
        "deposit_liability": "2300",
        "opening_clearing": "3000",
        "write_off": "6900",
        "minimum_bill_adjustment": "4190",
        "customer_credit_balance": "2400",
        "cash": "1000",
        "undeposited_funds": "1010",
        "unbilled_ar": "1210",
        "bank_fees": "6800",
        "deposit_interest_expense": "6950",
        # PO 2026-08-17 (CR-010 B-8, "8 - A") — the twelfth. The CODE is the
        # PO's own figure; it awaits its finance re-sign and says so in
        # PENDING_FINANCE_RE_SIGN.
        "budget_variance": "4180",
        # PO 2026-08-28 (the discount ruling, closing DEF-536) — the thirteenth.
        # ⚠ **AMENDED 2026-09-01 (CR-061) — 4300 → 4760, AND THE CODE IS NOW
        # THE PO's OWN CALL RATHER THAN A LANE's.** This comment used to say the
        # code was "this lane's reading of the chart's own ladder"; the PO then
        # ruled on it directly — *"if you need differnt number assign it - im
        # okay with it"* — and the number moved to 4760 because the reference
        # chart the PO supplied gives 4300 to Electric Energy Revenue and files
        # revenue adjustments at 4700-4750. It still awaits its finance re-sign
        # (PENDING_FINANCE_RE_SIGN): permission to renumber is not a signature.
        # Pinned here so a silent renumber goes RED.
        "discount_contra_revenue": "4760",
        # PO 2026-09-23 (CR-136-BRC07 §3.3) — the eighteenth. The RULING is
        # that a counted drawer difference reaches the books; the CODE, the
        # NAME and the TYPE are this lane's reading of the ladder — `6850` is
        # the only slot between the two signed expense codes `6800 Bank fees`
        # and `6900 Bad debt` — and all three await a HUMAN-GUIDE §6 re-sign
        # (`PENDING_FINANCE_RE_SIGN`). Pinned here so a silent renumber goes
        # RED, exactly as 4760's is.
        "cash_over_short": "6850",
    }


def test_the_signed_chart_seeds_no_tax_payable_account():
    """B5: *"2200-series Tax payable per authority (tenant authorities mint
    their own)"*. Seeding a 2200 would invent an authority no tenant created
    (BR-TEN-037), so the seed carries none — asserted so a later 'helpful'
    addition goes RED."""
    assert not [row for row in chart.SEED_CHART if row.code.startswith("22")]


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-005 TC-1 — seeded at provisioning, and WIRED (hard-won law 2)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_005_tc1__provisioning_seeds_the_full_chart_for_every_tenant(brazos):
    """*"Given provisioning, Then the seeded chart exists"* — through the REAL
    `provision_tenant`, not by calling the seed directly.

    This is the built-is-wired assertion (hard-won law 2): the `brazos` fixture
    provisions a tenant the way the product does, and if nobody had called the
    seam from `_provision_inside_context` the chart would be empty and every
    other test in this file would still pass by seeding by hand.

    ⚠ **REWRITTEN 2026-08-18 (CR-010 B-9) — THE NARROWING THIS TEST PINNED IS
    REVERSED BY ITS OWN AUTHOR.** Under OQ-115 (PO 2026-08-11: *"every Utility
    may not have all the services"*) Brazos Bend — Electric + Water — got
    seventeen signed rows and four cost rows, and this test asserted the six
    revenue rows and four cost rows it did NOT get. The PO reversed that on
    2026-08-17, verbatim: *"9 - A full ~40 accounts for every tenant, as you
    said"* (and New mandate 4: *"more is better ; less is contraint"*). So the
    NEW law is asserted: **all 25 signed-chart rows plus all 8 cost rows — 33
    accounts — whatever the tenant sells.** No frozen figure moved; only which
    rows land.
    """
    with tenant_ctx(brazos):
        codes = set(
            ledger_models.LedgerAccount.objects.filter(tenant=brazos).values_list("code", flat=True)
        )
    signed_expected = {row.code for row in chart.SEED_CHART}
    cost_expected = {row.code for row in chart.COST_OF_SERVICE_CHART}
    # ⚠ **AMENDED 2026-09-01 (CR-060 C15 · task T5) — 48 ACCOUNTS, NOT 34.**
    # The cost vocabulary widened from two non-service categories to sixteen,
    # and each of the fourteen new ones seeds its own expense account
    # (`chart.WIDENED_COST_CHART`). **Every one is `signed=False`** and waits
    # for a HUMAN-GUIDE §6 re-sign, the same route 4160/4170, 4180 and 4300
    # each took — B5 line 74 is ❄️ FROZEN and was NOT edited.
    #
    # The three counts stay SEPARATE rather than becoming one 48, deliberately:
    # they are three different questions — what finance signed in B5, what the
    # 2026-08-18 cost re-sign covers, and what C15 added unsigned — and one
    # total would hide a row moving between them.
    widened_expected = {row.code for row in chart.WIDENED_COST_CHART}
    # ⚠ **AMENDED 2026-09-02 (CR-061 statement (1)) — 125 ACCOUNTS, NOT 58.**
    # The PO reported on 2026-09-01 that they had tried to assign GL codes with
    # this chart and RUN OUT — *"actually you need more GL code s and
    # categories, I tried to assigned using existing code, they are not
    # sufficiencnt"* — and closed it on 2026-09-02 with *"complete 61 based on
    # actual code"*. `chart.UTILITY_BOOKS_CHART` adds **67** rows for the half
    # of a utility's books this product never posts: plant, construction,
    # depreciation, payables, debt, grants, transfers and net position.
    # **Every one is `signed=False`** and waits for a HUMAN-GUIDE §6 re-sign —
    # B5 line 74 is ❄️ FROZEN and was NOT edited. Counted as a FOURTH set for
    # the reason the third is counted separately: four different questions, and
    # one total would hide a row moving between them.
    books_expected = {row.code for row in chart.UTILITY_BOOKS_CHART}
    # ⚠ **A FIFTH SET SINCE 2026-09-02 — `DEF-3441`.** `CR-060` T7f added
    # `chart.PERIOD_MATCHING_CHART` — `5700 Depreciation expense`, the one row
    # the PO's own 111-row reference chart has no entry for at all — and it
    # joins `services._wanted_rows` like every other seed tuple. This assertion
    # had been RED since that day and neither that lane nor CR-061's ran this
    # file. Counted as its own set for the reason the other four are: five
    # different questions, and one total would hide a row moving between them.
    #
    # `chart.ALLOWANCE_CHART` is deliberately NOT a sixth: `CR-060` T15 mints
    # `1290` when a tenant switches the allowance policy on, never here.
    matching_expected = {row.code for row in chart.PERIOD_MATCHING_CHART}
    assert codes == (
        signed_expected | cost_expected | widened_expected | books_expected | matching_expected
    )
    # 22 of B5 line 74 + 4160/4170 + 4180 + **4300** (the discount account, PO
    # ruling 2026-08-28 closing DEF-536 — unsigned, awaiting its §6 re-sign)
    # + **4155 Fire** (CR-063, PO ruling 2026-09-02 — the ELEVENTH utility
    # service, also unsigned and also awaiting §6; it sits between 4150 Capacity
    # and 4160 Storm water in this chart's own ladder).
    # + **4165 Battery** (PO ruling 2026-09-03, verbatim: *"We need seperate
    # code for Solar 4150 and Battery 4150"*). ⚠ **AND THE SENTENCE ABOVE USED
    # TO END "…does NOT share solar and battery's 4150, whose ❄️ frozen name
    # says solar/battery" — READ THAT IN THE PAST TENSE.** There is no shared
    # account any more: solar keeps 4150 and battery has its own, so 4150's name
    # is now "Solar" and it too is unsigned, because what finance signed was an
    # account covering the pair.
    # +9 (CR-066, 2026-09-02): 4600/4610/4630/4640/4650 fee accounts and the
    # 4700-4730 revenue-adjustment block, every one `signed=False`.
    # ⚠ 38 since 2026-09-23 (CR-136-BRC07 §3.3): +1 **6850 Cash over and
    # short**, `signed=False`, the account a counted drawer difference posts to.
    assert len(signed_expected) == 38
    assert len(cost_expected) == 8
    assert len(widened_expected) == 14
    assert len(books_expected) == 67  # CR-061 statement (1)
    assert len(matching_expected) == 1  # CR-060 T7f — 5700 Depreciation expense
    # +67 (CR-061) +1 (5700) +1 (4165 Battery, 2026-09-03) +1 (6850 Cash over
    # and short, CR-136-BRC07 §3.3, 2026-09-23).
    assert len(codes) == 128
    # The rows the OLD narrowing withheld from an Electric+Water tenant are the
    # exact rows B-9 now plants — asserted by name so the reversal is visible.
    assert {"4120", "4130", "4140", "4145", "4150", "4160", "4170"} <= codes
    assert {"5120", "5130", "5140", "5145"} <= codes


def test_us_led_005_tc1__every_designation_resolves_to_its_seeded_account(brazos):
    """Each SEEDED designation landing on the account the finance-signed chart
    gives it. Resolved through the published selector — the same call the posting
    service will make — rather than by reading the column.

    ⚠ AMENDED 2026-08-18: this paragraph asserted `budget_variance` resolves to
    NOTHING while its account awaited a finance re-sign. The PO seeded it on
    2026-08-17 (CR-010 B-8, *"8 - A ✅ 4180"*), so ALL TWELVE now resolve and
    the pending set below is empty — the assertion is unchanged in shape and
    flipped in outcome by the ruling, which is exactly how it was meant to move.
    """
    expected = {row.designation: row.code for row in chart.SEED_CHART if row.designation}
    with tenant_ctx(brazos):
        for designation, code in expected.items():
            account = ledger_selectors.gl_account_for_designation(designation)
            assert account is not None, f"{designation} resolved to nothing"
            assert account.code == code, f"{designation} resolved to {account.code}, want {code}"
        # And the bulk read agrees with the one-at-a-time read, in both
        # directions: all twelve keys present, and exactly the pending-signature
        # one is None.
        resolved = ledger_selectors.designation_map()
        assert set(resolved) == set(chart.GL_DESIGNATIONS)
        unresolved = sorted(name for name, value in resolved.items() if value is None)
        # ⚠ **MOVED 2026-09-03 (DEF-3441).** This compared against
        # `PENDING_FINANCE_RESIGN` alone — i.e. against `()` — and had been RED
        # since 2026-09-02, when two designations moved to a place-on-first-use
        # top-up and a third (the allowance) arrived that is claimed only when a
        # tenant switches the policy on. Both families are ENUMERATED in
        # `chart.DESIGNATED_ON_FIRST_USE`, so a designation that stops resolving
        # WITHOUT being named there still goes red.
        may_be_unresolved = sorted(
            set(chart.PENDING_FINANCE_RESIGN) | set(chart.DESIGNATED_ON_FIRST_USE)
        )
        assert unresolved == may_be_unresolved, (
            "a designation may resolve to nothing at provisioning only if it awaits a finance "
            "re-sign or is claimed on first use; "
            f"unresolved={unresolved}, allowed={may_be_unresolved}"
        )


def test_us_led_005_tc1__the_worked_gt16_accounts_are_findable_by_name(brazos):
    """GT-16's opening entry is *"DR AR 267.30 / CR opening-balance clearing
    267.30"* — the entry the decision log names as unblocked by this work.

    Both sides of it are resolved here BY DESIGNATION, which is the whole
    claim: the posting service never needs to know that they are 1200 and 3000.
    """
    with tenant_ctx(brazos):
        debit = ledger_selectors.gl_account_for_designation(chart.AR)
        credit = ledger_selectors.gl_account_for_designation(chart.OPENING_CLEARING)
    assert (debit.code, debit.type) == ("1200", "asset")
    assert (credit.code, credit.type) == ("3000", "equity")


def test_us_led_005_tc1__the_seed_writes_one_audit_row_per_account(brazos, audit_rows):
    """BR-LED-015 — every chart change audits, seeded or typed.

    `audit_rows` captures from the sink, so this asserts the rows the seed
    wrote during THIS call rather than during the fixture's provisioning.

    ⚠ **REWRITTEN 2026-08-18 (CR-010 B-9).** Under OQ-115's narrowing this test
    read a water-only tenant's trail as two stories — the shared rows
    (`source: provisioning_seed`) and 4110/4115 minted by the Water enablement
    (`source: service_enabled`). B-9's full seed (*"9 - A full ~40 accounts for
    every tenant, as you said"*) plants everything BEFORE services are enabled,
    so a new tenant's whole chart — **all 33 rows** — audits as
    `provisioning_seed` and the enablement call finds every account present
    and mints nothing. `service_enabled` still exists as a source: it is the
    top-up path's stamp for narrowing-era tenants, asserted in
    `test_cr010_b9__enabling_a_service_tops_up_a_narrowing_era_tenant`.

    The signature is asserted PER CODE and against the chart row's own flag
    (never as one set — the 2026-08-15 lesson).

    ⚠ **AMENDED 2026-08-18 — THE UNSIGNED SET IS NOW EMPTY.** This read *"the
    eight cost rows (BR-LED-037, re-sign owed) and 4180 (CR-010 B-8, re-sign
    owed) audit `finance_signed: False`; every other row True"*, and named those
    nine codes in a literal. The Product Owner finance re-signed all nine that
    day (their codes and names, in plain English, no dollar figure attached), so
    every row now audits True. **The literal is replaced by a derivation from
    `chart`'s own rows rather than by `== {True}`**: a set form would go on
    passing if the flag were dropped, which is exactly the trap the 2026-08-15
    note was written about, and a hardcoded "all True" would go on passing the
    day an unsigned row is added.
    """
    other, _ = provisioned_tenant(lonestarridge_payload(subdomain="auditseed", services=["water"]))
    seeded = [
        row
        for row in audit_rows
        if row["action"] == "ledger_account.created" and row["tenant_id"] == other.id
    ]
    by_source = {row["after"]["code"]: row["after"]["source"] for row in seeded}
    by_signature = {row["after"]["code"]: row["after"]["finance_signed"] for row in seeded}
    # Derived from the chart's own rows, so this stays honest whichever way a
    # future re-sign (or a future unsigned addition) moves it.
    signed_by_chart = {
        row.code: row.signed
        for row in chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
        # ⚠ DEF-3441 — the fifth seed tuple, red since 2026-09-02 (CR-060 T7f's
        # 5700 Depreciation expense, `signed=False` like the 67 books rows).
        + chart.PERIOD_MATCHING_CHART
    }
    unsigned_codes = {code for code, signed in signed_by_chart.items() if not signed}
    # ⚠ AMENDED 2026-09-01 (CR-060 C15 · task T5): 26 signed-chart rows + 8 cost
    # rows + **14 widened cost rows**. The `finance_signed` half of this test is
    # the part that matters and it needed no change at all — it is DERIVED from
    # the chart's own flags, so the fourteen new unsigned rows flow into
    # `unsigned_codes` on their own and the audit trail is asserted to say
    # `false` for each of them at the moment it is minted. **That is the
    # mechanism working on real rows again for the first time since the
    # 2026-08-18 re-sign emptied it.**
    # ⚠ AMENDED 2026-09-02 (CR-061 statement (1)): +67 utility-books rows, every
    # one `signed=False`. The `finance_signed` half of this test needed no change
    # at all — it is DERIVED from the chart's own flags below, so all 67 flow
    # into `unsigned_codes` on their own and the audit trail is asserted to say
    # `false` for each of them at the moment it is minted.
    # DEF-3441 — 126 since CR-060 T7f seeded 5700 Depreciation expense; 127
    # since the PO split solar and battery on 2026-09-03 (4165 Battery).
    # 128 since 2026-09-23 (CR-136-BRC07 §3.3 seeded 6850 Cash over and short).
    assert len(seeded) == 128
    assert set(by_source) == {row.code for row in chart.SEED_CHART} | {
        row.code for row in chart.COST_OF_SERVICE_CHART
    } | {row.code for row in chart.WIDENED_COST_CHART} | {
        row.code for row in chart.UTILITY_BOOKS_CHART
    } | {
        # ⚠ DEF-3441 — the fifth seed tuple, red since 2026-09-02 when CR-060
        # T7f seeded 5700 Depreciation expense. ALLOWANCE_CHART is NOT a sixth:
        # CR-060 T15 mints 1290 when a tenant switches the policy on.
        row.code
        for row in chart.PERIOD_MATCHING_CHART
    }
    # ONE story now: everything provisioning plants says so.
    assert set(by_source.values()) == {"provisioning_seed"}
    # Judgment call 2 + BR-LED-037 + CR-010 B-8: the trail carries whether
    # finance signed the account, PER CODE, and it must equal that row's own
    # flag — not a constant and not a set.
    for code, signed in signed_by_chart.items():
        assert by_signature[code] is signed, (
            f"{code} audits finance_signed={by_signature[code]} and its chart row says "
            f"{signed} — the trail is the row a finance reviewer reads"
        )
    # Since the PO's re-sign of 2026-08-18 (nine codes and names, no figure
    # attached) there was nothing left unsigned. Stated as its own line so that
    # the day one appears, this figure is what says so — and one appeared on
    # 2026-08-28: **4760** (**4300** until CR-061 re-filed it on 2026-09-01),
    # the discount account the PO's ruling of that day
    # required, whose CODE and NAME await a HUMAN-GUIDE §6 re-sign even though
    # the ruling behind it is signed. The audit row for it therefore stamps
    # `finance_signed: False`, which is the whole mechanism working: a finance
    # reviewer reading the trail sees which account was minted unsigned.
    #
    # ⚠ **AMENDED 2026-09-01 (CR-060 C15 · task T5) — FOURTEEN MORE JOINED IT,
    # AND THE PIN NAMES THEM RATHER THAN COUNTING THEM.** The cost vocabulary
    # widened to sixteen categories and each of the fourteen new accounts seeds
    # `signed=False`, awaiting the same HUMAN-GUIDE §6 re-sign. Written as
    # `{"4760"} | the widened codes` so the two stay legible as two separate
    # facts: 4760 is a CONTRA-REVENUE row from the discount ruling (a REVENUE
    # row until CR-061, 2026-09-01), the fourteen are
    # COST rows from C15, and a row moving between the two groups — or a
    # signature landing on either — goes red here rather than netting out.
    # ⚠ **AMENDED 2026-09-02 (`CR-063`) — `4155 Fire` IS THE THIRD GROUP, AND IT
    # IS NAMED SEPARATELY FOR THE SAME REASON THE OTHER TWO ARE.** Fire is the
    # ELEVENTH utility service (`BR-RAT-024` amended; a real utility is being
    # onboarded and it sells fire protection), and its revenue account seeds
    # `signed=False` on exactly the posture `4160`, `4170`, `4180` and `4760`
    # each arrived on: the PO ruled that the SERVICE exists and is billed, and
    # the CODE and the NAME are the lane's reading of this chart's ladder until
    # a dated HUMAN-GUIDE §6 addendum says otherwise. **Three groups, three
    # facts:** `4155` is a REVENUE row from the fire ruling, `4760` a
    # CONTRA-REVENUE row from the discount ruling, and the fourteen are COST
    # rows from C15 — so a row moving between groups, or a signature landing on
    # any of them, goes red here rather than netting out.
    # ⚠ **AMENDED 2026-09-02 (`CR-066`) — NINE MORE UNSIGNED REVENUE-SIDE ROWS.**
    # The set is written out rather than derived from the flags it is checking,
    # which is the whole point of the assertion: reading it back from
    # `chart.PENDING_FINANCE_RE_SIGN` would make it assert that the chart equals
    # itself. `4600`/`4610`/`4630`/`4640`/`4650` are CR-066's fee accounts and
    # `4700`–`4730` its revenue-adjustment block; the PO approved the MAPPING
    # those accounts serve and NOT the chart, which is exactly why they are
    # here and not signed.
    # ⚠ **AMENDED 2026-09-02 (`CR-061` statement (1)) — SIXTY-SEVEN MORE.** The
    # PO ruled the utility's own books into the chart — plant, construction,
    # depreciation, payables, debt, grants, transfers, net position — and that
    # is a ruling on the CODES and NAMES, never a finance signature: no dollar
    # figure was attached to any of them and B5 line 74 stays ❄️ FROZEN. They
    # are named through `chart.UTILITY_BOOKS_CHART` rather than written out one
    # by one, which is the same shape the fourteen C15 rows already take here:
    # a whole SECTION arriving is one fact, and listing 67 codes would make the
    # next reader diff a page to find the one that moved.
    # ⚠ **AMENDED 2026-09-03 — `4150` AND `4165`, AND THE PAIR IS ONE FACT.**
    # PO verbatim: *"We need seperate code for Solar 4150 and Battery 4150"*.
    # B5 line 74 signs ONE account for the pair, so a utility selling both saw
    # one number; battery moved to `4165` and solar kept `4150`. Both are here
    # because BOTH rows changed: 4165 is new and unsigned, and 4150's NAME is
    # no longer the one finance signed ("Capacity (solar/battery)" → "Solar").
    assert unsigned_codes == {
        "4150",
        "4155",
        "4165",
        "4600",
        "4610",
        "4630",
        "4640",
        "4650",
        "4700",
        "4710",
        "4720",
        "4730",
        "4760",
        # ⚠ **CR-136-BRC07 §3.3, PO 2026-09-23 — `6850 Cash over and short`.**
        # The PO ruled that a counted drawer difference must POST and named no
        # code, no name and no type, so the row seeds `signed=False` on the
        # 4160/4170/4180/4760 precedent and the audit trail stamps
        # `finance_signed: false` at the moment it is minted — which is this
        # whole mechanism doing its job on a real row again.
        "6850",
    } | {row.code for row in chart.WIDENED_COST_CHART} | {
        row.code for row in chart.UTILITY_BOOKS_CHART
    } | {
        # DEF-3441 — the fifth seed tuple, red since 2026-09-02. 5700 is
        # signed=False like the 67 books rows, so it belongs in the unsigned
        # set and the audit trail was right about it all along.
        row.code
        for row in chart.PERIOD_MATCHING_CHART
        if not row.signed
    }, (
        "the audit trail's unsigned set is the chart's own flags read back. A code leaving "
        "it is a SIGNATURE, recorded in 12-governance/09-human-review-ledger.md and never "
        "by editing this line"
    )
    # BR-AUD-007 — the trail is stamped from tenant context, never a parameter,
    # so the second tenant's seed cannot land in the first tenant's trail.
    assert {row["tenant_id"] for row in seeded} == {other.id}


# ═══════════════════════════════════════════════════════════════════════════
# THE ONE THAT MUST NOT BE GOT WRONG — resolve by NAME, never by number
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_005_tc1__a_designation_resolves_by_name_after_the_tenant_renumbers(brazos):
    """**The defect this whole question existed to prevent.**

    US-LED-005 makes the chart tenant-customizable, so a utility may renumber
    accounts receivable from 1200 to 1150 and rename it. The decision log:
    *"the code reads the DESIGNATION and never the number."* Here the tenant
    does exactly that, and the lookup must still land.

    Proved RED by pointing `gl_account_for_designation` at `code="1200"`
    instead of the designation column: this test then resolves the OLD account
    (or nothing at all once the code is gone), while every other test in the
    file stays green — which is precisely why this one is written.
    """
    with tenant_ctx(brazos):
        ar = account_for(brazos, "1200")
        ar.code, ar.name = "1150", "Trade debtors"
        ar.save(update_fields=["code", "name", "updated_at"])

        found = ledger_selectors.gl_account_for_designation(chart.AR)
        assert found is not None, "AR became unfindable the moment the tenant renumbered it"
        assert found.pk == ar.pk
        assert (found.code, found.name) == ("1150", "Trade debtors")
        # No `1200` remains anywhere — so a lookup that resolved would only
        # have resolved by designation.
        assert not ledger_models.LedgerAccount.objects.filter(tenant=brazos, code="1200").exists()


def test_us_led_005_tc1__a_tenant_repointing_a_designation_survives_a_reseed(brazos, dana):
    """BR-TEN-012's law applied to money: a re-seed never undoes a tenant edit.

    The tenant deactivates the seeded AR account (IS-1 deactivate-first) and
    points `accounts_receivable` at a brand-new 1150. A re-seed then runs —
    a re-provision, a repair script, a later migration — and must leave that
    standing rather than resurrecting 1200 as AR.
    """
    with tenant_ctx(brazos):
        original = account_for(brazos, "1200")
        original.designation = None
        original.deleted_at = timezone_now()
        original.save(update_fields=["designation", "deleted_at", "updated_at"])
        replacement = ledger_models.LedgerAccount.objects.create(
            tenant=brazos,
            code="1150",
            name="Trade debtors",
            type="asset",
            designation=chart.AR,
        )

        summary = ledger_services.seed_chart_of_accounts(dana)

        assert ledger_selectors.gl_account_for_designation(chart.AR).pk == replacement.pk
        # The seed created nothing: every signed code already exists (1200 is
        # soft-deleted, not gone, and its code is still occupied).
        assert summary["accounts_created"] == 0
        assert summary["designations_already_placed"] == ()
        assert (
            ledger_models.LedgerAccount.objects.filter(tenant=brazos, designation=chart.AR).count()
            == 1
        )


def test_the_seed_defers_to_a_tenant_pointer_when_the_seeded_code_is_gone(brazos, dana):
    """The awkward case, and the reason `seed_chart_of_accounts` checks the
    designation as well as the code.

    A tenant that HARD-removed 1200 (an unreferenced account is deletable per
    IS-1) and moved `accounts_receivable` onto 1150 leaves the code free but
    the designation taken. A naive re-seed would insert 1200 carrying AR and
    hit `uq_ledger_accounts_designation` mid-provisioning. Instead the account
    comes back WITHOUT the designation and the summary says so.
    """
    with tenant_ctx(brazos):
        account_for(brazos, "1200").delete()
        replacement = ledger_models.LedgerAccount.objects.create(
            tenant=brazos, code="1150", name="Trade debtors", type="asset", designation=chart.AR
        )

        summary = ledger_services.seed_chart_of_accounts(dana)

        assert summary["accounts_created"] == 1
        assert summary["codes_created"] == ("1200",)
        assert summary["designations_already_placed"] == (chart.AR,)
        assert account_for(brazos, "1200").designation is None
        assert ledger_selectors.gl_account_for_designation(chart.AR).pk == replacement.pk


# ═══════════════════════════════════════════════════════════════════════════
# The uniqueness rule, and the CHECK
# ═══════════════════════════════════════════════════════════════════════════
def test_two_live_accounts_cannot_carry_the_same_designation(brazos):
    """The database half of the PO's *"unambiguous at posting time"*.

    Two `accounts_receivable` accounts means the posting service picks one by
    `ORDER BY` accident — the ambiguity a designations table would have had,
    reintroduced through the column.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            ledger_models.LedgerAccount.objects.create(
                tenant=brazos, code="1151", name="Other AR", type="asset", designation=chart.AR
            )


def test_a_designation_frees_up_when_its_account_is_deactivated(brazos):
    """The partial half of the same index: IS-1 deactivates rather than
    deletes, so re-pointing must remain possible or a designation would be
    frozen onto a dead account forever."""
    with tenant_ctx(brazos):
        original = account_for(brazos, "1200")
        original.deleted_at = timezone_now()
        original.save(update_fields=["deleted_at", "updated_at"])
        replacement = ledger_models.LedgerAccount.objects.create(
            tenant=brazos, code="1150", name="Trade debtors", type="asset", designation=chart.AR
        )
        # The live one wins the lookup; the deactivated one is invisible to it.
        assert ledger_selectors.gl_account_for_designation(chart.AR).pk == replacement.pk


def test_a_typod_designation_is_refused_by_the_database(brazos):
    """`ck_ledger_accounts_designation`. A designation is resolved BY NAME, so
    `accounts_recievable` is an account nothing will ever find and money that
    posts to it vanishes from every report — the same silent hole an unreadable
    `journal_lines.side` would open."""
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            ledger_models.LedgerAccount.objects.create(
                tenant=brazos,
                code="1199",
                name="Typo",
                type="asset",
                designation="accounts_recievable",
            )


def test_an_unknown_designation_is_refused_by_the_selector(brazos):
    """A typo at the CALL site is a different failure from an unconfigured
    account, and returning None for it would hide the typo inside the caller's
    own not-configured branch."""
    with tenant_ctx(brazos):
        with pytest.raises(ValueError) as raised:
            ledger_selectors.gl_account_for_designation("accounts_recievable")
    # ⚠ **THIS ASSERTED THE WORD "eleven" UNTIL 2026-09-23 AND THE SET HELD
    # SEVENTEEN (`DEF-LED-6222`).** The test was pinning a COUNT in a sentence
    # rather than the behaviour, so it stayed green through six new designations
    # while the message it guarded told a developer the opposite of the truth.
    # What matters is that the refusal NAMES the ruled set, so a typo is
    # distinguishable from an unconfigured account — that is what is asserted.
    message = str(raised.value)
    assert "accounts_recievable" in message
    assert "accounts_receivable" in message
    assert "eleven" not in message, "the refusal quotes a count again; count the tuple"


# ═══════════════════════════════════════════════════════════════════════════
# BR-BIL-010 — the service attributes, and the OPTIONAL base split
# ═══════════════════════════════════════════════════════════════════════════
def test_br_bil_010__provisioning_points_electric_at_the_split_pair(brazos):
    """B5: *"4100/4105 Electric usage/base"*. Both attributes filled, and by
    the real provisioning path — nothing here writes them by hand."""
    with tenant_ctx(brazos):
        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="electric")
        assert row.revenue_account.code == "4100"
        assert row.base_revenue_account.code == "4105"
        assert ledger_selectors.revenue_account_for_service("electric").code == "4100"
        assert ledger_selectors.revenue_account_for_service("electric", base=True).code == "4105"


def test_br_bil_010__a_service_with_no_base_account_falls_back_to_revenue(brazos, dana):
    """The reason the split is OPTIONAL rather than a second required field.

    Trash carries ONE account in the finance-signed chart (4130). A base charge
    on it must land in Trash revenue — not nowhere, and not in a duplicate
    column somebody had to fill in to satisfy a NOT NULL.
    """
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})
        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="trash")
        assert row.revenue_account.code == "4130"
        assert row.base_revenue_account is None

        assert ledger_selectors.revenue_account_id_for_service("trash", base=True) == str(
            row.revenue_account_id
        )
        assert ledger_selectors.revenue_account_for_service("trash", base=True).code == "4130"


def test_br_bil_010__a_service_the_tenant_did_not_pick_is_present_but_off(brazos):
    """⚠ REWRITTEN 2026-08-18 — the absence this test pinned is REVERSED.

    It asserted `service_gl_attributes("gas") is None` for Brazos Bend
    (Electric + Water): no row, no resolution. The PO's New mandate 4
    (2026-08-17), verbatim: *"we will provdie full list for all services - they
    can always select what they want out of it; more is better ; less is
    contraint"* — so Gas now has a `tenant_services` row at provisioning,
    **enabled=False**, with its UoM and GL pointers FILLED (4140, per B-9's
    full chart). The GL read resolves through the stored pointer exactly as it
    always has for a service a tenant toggled off (the selector never gated on
    `enabled`; `enabled` travels in the attributes for the caller to judge —
    unchanged behaviour, now reachable from provisioning too).
    """
    with tenant_ctx(brazos):
        attributes = tenancy_selectors.service_gl_attributes("gas")
        assert attributes is not None
        assert attributes["enabled"] is False
        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="gas")
        assert row.enabled is False
        assert row.disabled_at is None  # never on ≠ switched off
        assert row.revenue_account.code == "4140"
        assert ledger_selectors.revenue_account_id_for_service("gas") == str(row.revenue_account_id)


# ═══════════════════════════════════════════════════════════════════════════
# OQ-115 — CLOSED 2026-08-11. All three halves of the PO's ruling, asserted
# ═══════════════════════════════════════════════════════════════════════════
def test_oq_115__every_catalog_service_now_has_a_revenue_account(brazos):
    """*"A, you create an account…"* — 4160 Storm water, 4170 Thermal/Heat.

    Before the ruling the catalog was ten services and the chart covered eight,
    so a tenant that enabled Storm water and billed a $38.50 usage line had the
    WHOLE bill refused at issue (BR-BIL-010's stamp). The gap is closed against
    the LIVE platform catalog rather than a literal list, so a service added to
    `SERVICE_SEED` without a chart line reopens it here instead of at issue.
    """
    catalog = set(tenancy_models.Service.objects.filter(active=True).values_list("code", flat=True))
    assert catalog == set(chart.SERVICE_REVENUE_ACCOUNTS)
    # ELEVEN since CR-063 (2026-09-02): `fire` -> 4155. The count is here as well
    # as the set comparison above because the set alone would be satisfied by BOTH
    # sides losing a service, which is the failure this pair exists to separate.
    assert len(catalog) == 11
    assert chart.SERVICE_REVENUE_ACCOUNTS["storm_water"] == ("4160", None)
    assert chart.SERVICE_REVENUE_ACCOUNTS["thermal_heat"] == ("4170", None)


def test_po_2026_09_03__solar_and_battery_no_longer_share_one_revenue_account():
    """PO 2026-09-03: *"We need seperate code for Solar 4150 and Battery 4150"*.

    ⚠ **RED BEFORE THE CHANGE, AND THE ASSERTION THAT MATTERS IS THE FIRST ONE.**
    Both services mapped to `4150` because B5 line 74 names ONE account for the
    pair — *"4150 Capacity (solar/battery)"* — so a utility selling both put 40 kW
    of solar and 40 kW of battery into the same number and could not tell them
    apart in its own books. `assert usage != battery_usage` could not pass on any
    version before today.

    **Solar keeps 4150 and battery moves**, because battery is the service
    leaving: nothing already posted to 4150 changes account, and only battery's
    future postings go elsewhere.

    **NEITHER ROW IS FINANCE-SIGNED ANY MORE**, on the 4155 / 4160 / 4170
    precedent. The PO ruled the SPLIT into existence and that is not a signature
    on a number — `4165` is this lane's reading of a chart that moves in fives,
    and `4150`'s NAME no longer says what finance signed it saying.
    """
    solar, solar_base = chart.SERVICE_REVENUE_ACCOUNTS["solar"]
    battery, battery_base = chart.SERVICE_REVENUE_ACCOUNTS["battery"]

    assert solar != battery, "solar and battery must not share one revenue account"
    assert (solar, solar_base) == ("4150", None)
    assert (battery, battery_base) == ("4165", None)

    # The account itself exists in the seed, or a battery tenant's bill refuses at
    # issue with nowhere to post (BR-BIL-010) — the exact wall DEF-2386 was about.
    seeded = {row.code: row for row in chart.SEED_CHART}
    assert battery in seeded, "4165 is mapped but not seeded"
    assert seeded[battery].name == "Battery"
    assert seeded[solar].name == "Solar", "4150 still names the pair it no longer holds"

    # Both await a finance re-sign, and the pending list is DERIVED from the rows
    # rather than listed, so this cannot drift from the flags above.
    for code in (solar, battery):
        assert code in chart.PENDING_FINANCE_RE_SIGN, (
            f"{code} reads as finance-signed. The PO ruled the SPLIT; they did not "
            "sign a number or a name, and a signature covers only what was shown."
        )


def test_oq_115__every_seeded_code_is_finance_signed_after_the_2026_08_11_addendum():
    """**The distinction this file must not lose**, now asserted from the other side.

    THIS TEST USED TO ASSERT THE OPPOSITE, and the change is the point. It read
    `test_..._the_two_new_codes_are_marked_as_not_finance_signed` and pinned
    4160/4170 as UNSIGNED — because B5 line 74 is ❄️ FROZEN, names EIGHT
    services, and those two were a lane's reading of the chart's own 41xx ladder
    under a PO ruling (OQ-115). The flag was data rather than a comment
    precisely so that dropping it without a re-sign would go RED.

    **It did go RED, on 2026-08-11, when the re-sign arrived** — PO verbatim
    *"okay"*, in direct answer to "Finance re-sign for the two new revenue
    accounts", recorded in the decision log and applied to B5 as a dated
    ADDENDUM rather than an inline edit of the frozen line. So the guard worked:
    the signature could not be assumed, and when it came the test that assumed
    its absence failed loudly instead of passing quietly.

    What is asserted now is the same discipline pointed forwards: the goal state
    is that NOTHING is unsigned, and any future row added without a re-sign
    turns this RED the moment it appears.

    ⚠ **AND IT TURNED RED AGAIN ON 2026-08-18, WHICH IS THE GUARD WORKING A
    SECOND TIME.** The PO ruled on 2026-08-17 (CR-010 B-8, verbatim: *"8 - A ✅
    4180 "Budget billing variance", revenue, signed=False (the 4160/4170
    precedent)"*), so the pending set was EXACTLY `("4180",)` — pinned, not
    merely non-empty — until finance re-signed via HUMAN-GUIDE §6.

    ⚠ **AND A THIRD TIME, HOURS LATER, WHEN THAT RE-SIGN ARRIVED.** On
    **2026-08-18** the Product Owner — the sign-off authority per their own
    ruling of 2026-08-11 — re-signed **4180 Budget billing variance (revenue)**
    together with the eight cost accounts, shown the nine codes and names in
    plain English, with no dollar figure attached to any of them and with B4/B5
    ❄️ FROZEN and un-edited. So the pin is `()` again, exactly as it emptied for
    4160/4170 on 2026-08-11, and the discipline is unchanged: any FUTURE row
    added without a re-sign turns this RED the moment it appears.
    """
    # ⚠ **AND A FOURTH TIME, ON 2026-08-28 — THE GUARD FIRING ON A NEW ROW,
    # WHICH IS EXACTLY WHAT THE PARAGRAPH ABOVE PROMISED IT WOULD DO.** The PO
    # ruled that a discount posts to a GL code of its own in a category of its
    # own ("you will need differnt GL code for these - dont keep them in same,
    # create differnt category as required and keep them in it"), so
    # `SEED_CHART` gained **4300 Customer discounts (contra-revenue)**. The
    # RULING is signed; the CODE and the NAME are the lane's reading of this
    # chart's own ladder, so the row is `signed=False` on the 4160/4170/4180
    # precedent and awaits its HUMAN-GUIDE §6 re-sign. Pinned EXACTLY, not
    # merely non-empty, so a second unsigned row cannot join it quietly.
    #
    # ⚠ **AND A FIFTH TIME, ON 2026-09-01 (CR-061) — THIS TIME THE PO ANSWERED
    # THE QUESTION THE ROW WAS WAITING ON, AND ANSWERED IT AGAINST THE LANE.**
    # Verbatim: *"no, you cannot file discount under revenue"* and *"if you need
    # differnt number assign it - im okay with it"*. So the code is **4760** and
    # the type is **`contra_revenue`**, a sixth `LEDGER_ACCOUNT_TYPES` value.
    # **`signed` did NOT move and this pin is the reason it must not:** the PO
    # ruled on WHICH KIND of account and gave permission on the NUMBER, and
    # neither is a finance re-sign of the chart. A lane that read the ruling as
    # a signature would turn this line green by deleting the guard.
    # ⚠ **4155 Fire JOINED THIS LIST ON 2026-09-02 (`CR-063`) AND THE PIN MOVED
    # WITH IT RATHER THAN BEING WIDENED.** Fire is the eleventh utility service
    # (`BR-RAT-024`, amended) and its revenue account arrived on exactly the
    # posture 4160, 4170 and 4180 each arrived on: the PO ruled that the SERVICE
    # exists and is billed, the CODE and the NAME are the lane's reading of this
    # ladder, and only a dated HUMAN-GUIDE §6 addendum makes it `signed=True`.
    # The list is spelled out rather than counted for the same reason it always
    # was: a lane that reads a ruling as a signature turns this line green by
    # deleting the guard, and a length check would let a swap through.
    # ⚠ **NINE MORE JOINED ON 2026-09-02 (`CR-066`), AND THE PIN MOVES WITH THEM
    # RATHER THAN BEING WIDENED INTO A COUNT.** `4600` Connection & new-service
    # fees · `4610` Disconnection & reconnection fees · `4630` Field-service &
    # meter fees · `4640` Equipment recovery & penalties · `4650` Billing &
    # payment fees · `4700` Billing adjustment · `4710` Leak adjustment · `4720`
    # Rate / meter correction · `4730` Customer credit. They arrived on exactly
    # the posture 4160, 4170, 4180, 4760 and 4155 each arrived on: **the Product
    # Owner approved the MAPPING — which charge code and which adjustment
    # reason posts where — having been shown every name and number in plain
    # English, and an approval of a mapping is not a finance signature on the
    # chart.** Only a dated HUMAN-GUIDE §6 addendum makes any of them
    # `signed=True`.
    assert chart.PENDING_FINANCE_RE_SIGN == (
        "4150",
        "4155",
        "4165",
        "4600",
        "4610",
        "4630",
        "4640",
        "4650",
        "4700",
        "4710",
        "4720",
        "4730",
        "4760",
        # ⚠ **6850 Cash over and short — CR-136-BRC07 §3.3, PO 2026-09-23.**
        # The PO ruled that a counted drawer difference must POST; they did not
        # state a number, a name or a type, so all three are this lane's reading
        # of the ladder and await a HUMAN-GUIDE §6 re-sign. The $12.0000 in that
        # ruling is the worked CASE, not a figure attached to the account.
        "6850",
    )
    assert [row.code for row in chart.SEED_CHART if not row.signed] == [
        "4150",
        "4155",
        "4165",
        "4600",
        "4610",
        "4630",
        "4640",
        "4650",
        "4700",
        "4710",
        "4720",
        "4730",
        "4760",
        "6850",
    ]
    # The discount account's own row, pinned code, name, type and designation —
    # the name is half of what a re-sign covers, so a rename must go RED.
    discount_row = {row.code: row for row in chart.SEED_CHART}["4760"]
    assert (
        discount_row.name,
        discount_row.type,
        discount_row.designation,
        discount_row.signed,
    ) == (
        "Customer discounts (contra-revenue)",
        "contra_revenue",
        chart.DISCOUNT_CONTRA_REVENUE,
        False,
    )
    # The re-signed row is still THERE and still carries the designation — a
    # signature is not a deletion (CR-010 B-8 + the 2026-08-18 addendum).
    budget = {row.code: row for row in chart.SEED_CHART}["4180"]
    assert (budget.name, budget.type, budget.designation, budget.signed) == (
        "Budget billing variance",
        "revenue",
        chart.BUDGET_VARIANCE,
        True,
    )

    # The two codes the addendum added are present, signed, and revenue.
    added = {row.code: row for row in chart.SEED_CHART if row.code in ("4160", "4170")}
    assert set(added) == {"4160", "4170"}
    assert added["4160"].name == "Storm water" and added["4170"].name == "Thermal/Heat"
    assert all(row.signed and row.type == "revenue" for row in added.values())

    # Every service in the ten-service catalogue now resolves to a signed
    # account — which is the whole of what the $38.50 storm-water bill needed.
    signed_codes = {row.code for row in chart.SEED_CHART if row.signed}
    # 25 since 2026-08-18 (it read 24 while 4180 awaited its re-sign, and 24
    # before 4180 existed at all).
    # ⚠ **24 SINCE 2026-09-03, AND THE NUMBER WENT DOWN RATHER THAN UP.** `4150`
    # LEFT this set when the PO split solar and battery — the account is still
    # solar's and still ratified as a number, but it is named "Solar" now and
    # what finance signed was an account covering the pair. A signature covers
    # only what was shown (PO 2026-08-11), so the row goes back on the pending
    # list until they see the new name. Nothing was unsigned by accident: the
    # assertion below still walks every service and still demands an account.
    assert len(signed_codes) == 24

    # ⚠ **THIS USED TO BE ONE LOOP OVER TEN HAND-LISTED SERVICES ASKING
    # `code in signed_codes`, AND IT WAS TWO QUESTIONS WEARING ONE ASSERTION.**
    # Fire was quietly left out of that list when `4155` arrived unsigned, and
    # solar would have had to be left out too when the PO split it from battery
    # — which is a guard shrinking every time the chart moves, until it guards
    # the services that never change. The two questions are separated here.
    #
    # **QUESTION ONE, AND IT IS THE ONE THE $38.50 STORM-WATER BILL NEEDED:
    # every service resolves to an ACCOUNT.** A service without one has its
    # whole bill refused at issue (BR-BIL-010). This now walks the WHOLE map —
    # eleven services, fire included — rather than a list a lane edits, so it
    # gets STRONGER as the catalogue grows instead of weaker.
    for service, (usage, base) in chart.SERVICE_REVENUE_ACCOUNTS.items():
        assert usage, f"{service} has no revenue account and its bills refuse at issue"
        for code in (usage, base):
            assert code is None or code in {row.code for row in chart.SEED_CHART}, (
                f"{service} points at {code}, which nothing seeds"
            )

    # **QUESTION TWO: which of them finance has actually signed.** Three are
    # not, each for a stated reason, and naming them is what keeps an unsigned
    # row from being waved through on a comment:
    #   4150 Solar    — the name, since the PO split the pair (2026-09-03)
    #   4155 Fire     — the eleventh service (CR-063, 2026-09-02)
    #   4165 Battery  — the other half of that split (2026-09-03)
    unsigned_service_codes = {
        code
        for pair in chart.SERVICE_REVENUE_ACCOUNTS.values()
        for code in pair
        if code is not None and code not in signed_codes
    }
    assert unsigned_service_codes == {"4150", "4155", "4165"}, (
        "a service revenue account changed signature. That is a HUMAN-GUIDE §6 "
        "addendum recorded in the review ledger, never an edit to this line."
    )

    # The route a FUTURE re-sign must take is still named in the code, so the
    # next unsigned row cannot be waved through on a comment.
    assert "HUMAN-GUIDE §6" in chart.PENDING_FINANCE_RE_SIGN_SOURCE


def test_oq_115__enabling_storm_water_is_one_toggle_onto_the_seeded_4160(brazos, dana):
    """The end of the $38.50 problem, through the real S8 write path.

    ⚠ REWRITTEN 2026-08-18 (CR-010 B-9 + New mandate 4): Brazos Bend now HAS
    4160 from provisioning (*"9 - A full ~40 accounts for every tenant"*) and a
    present-but-off storm_water row already pointing at it (*"more is better ;
    less is contraint"*). Switching the service on is therefore ONE FLAG FLIP —
    no mint, no configuration hunt — and the line is stampable at issue the
    moment the toggle lands, which is mandate 4's whole point.
    """
    with tenant_ctx(brazos):
        account = account_for(brazos, "4160")
        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="storm_water")
        assert row.enabled is False and row.revenue_account_id == account.id

        tenancy_services.update_tenant_service(dana, "storm_water", {"enabled": True})

        row.refresh_from_db()
        assert row.enabled is True
        assert (account.code, account.name, account.type) == ("4160", "Storm water", "revenue")
        assert row.base_revenue_account_id is None  # no split in the chart
        assert ledger_selectors.revenue_account_id_for_service("storm_water") == str(account.id)
        # The base charge falls back to the usage account, as for every
        # unsplit service (BR-BIL-010).
        assert ledger_selectors.revenue_account_for_service("storm_water", base=True).code == "4160"


def test_oq_115__the_shared_rows_carry_every_designation_and_no_service_account():
    """The invariant that makes conditional seeding safe.

    If a designation ever landed on a per-service revenue row, a tenant that
    does not sell that service would be provisioned unable to resolve it — a
    posting entry with no home, discovered at posting time. The split is
    mechanical (a code is conditional iff a service names it), so this asserts
    the two halves cannot overlap.
    """
    # Every designation the seed chart places is on a SHARED row — all twelve
    # since 2026-08-18, when 4180 gave `budget_variance` its home (CR-010 B-8).
    # ⚠ **MOVED 2026-09-03 (`DEF-3441`). THIS COMPARED `SHARED_CHART` AGAINST
    # THE WHOLE DESIGNATION SET AND HAD BEEN RED SINCE 2026-09-02.** Four
    # designations arrived that day and after which the SHARED chart does not
    # carry: `depreciation_expense` lives in `PERIOD_MATCHING_CHART`,
    # `allowance_doubtful_accounts` in `ALLOWANCE_CHART`, and `accrued_expenses`
    # and `accumulated_depreciation` are PLACED on `2100` and `1730` at first
    # use rather than seeded carrying a designation at all.
    #
    # The claim being made is unchanged and is the one that matters: **the
    # shared chart carries every designation that is not accounted for
    # somewhere else, and the somewhere-elses are ENUMERATED** — so a
    # designation with no home anywhere still goes RED.
    shared = {row.designation for row in chart.SHARED_CHART if row.designation}
    elsewhere = (
        {row.designation for row in chart.PERIOD_MATCHING_CHART if row.designation}
        | {row.designation for row in chart.ALLOWANCE_CHART if row.designation}
        | set(chart.DESIGNATED_ON_FIRST_USE)
    )
    assert shared | elsewhere == set(chart.GL_DESIGNATIONS), sorted(
        set(chart.GL_DESIGNATIONS) - (shared | elsewhere)
    )
    assert not shared & set(chart.DESIGNATED_ON_FIRST_USE)
    # WHICH designated rows are unsigned. This read `== ["4180"]` from the moment
    # the PO ruled 4180 in with `signed=False` (CR-010 B-8) until finance
    # re-signed it on 2026-08-18 — the code and the name, in plain English, no
    # figure attached — and then `== []`.
    # ⚠ **IT WENT RED AGAIN ON 2026-08-28 AND THAT IS THE GUARD WORKING.** The
    # PO's discount ruling requires an account (*"you will need differnt GL code
    # for these"*) and does NOT state its number or its name, so 4300 is seeded
    # `signed=False` on the 4160/4170/4180 precedent and awaits a HUMAN-GUIDE §6
    # re-sign. Pinned EXACTLY rather than merely non-empty: a designation is a
    # slot in a SIGNED enumeration, so a SECOND unsigned designated row must not
    # be able to join this one quietly.
    # ⚠ **A SECOND ONE JOINED ON 2026-09-23 AND THAT IS THE GUARD WORKING
    # AGAIN.** `CR-136-BRC07` §3.3 requires an account (*"Needs one new account
    # added to the chart"*) and does NOT state its number, name or type, so
    # `6850` is seeded `signed=False` on the 4160/4170/4180/4760 precedent and
    # awaits a HUMAN-GUIDE §6 re-sign. Still pinned EXACTLY rather than merely
    # non-empty: a designation is a slot in a SIGNED enumeration, so a THIRD
    # unsigned designated row must not be able to join these two quietly.
    assert [row.code for row in chart.SEED_CHART if row.designation and not row.signed] == [
        "4760",
        "6850",
    ]
    conditional = {row.code for row in chart.SEED_CHART} - {row.code for row in chart.SHARED_CHART}
    assert conditional == chart.SERVICE_REVENUE_CODES
    # ⚠ `4165` JOINED ON 2026-09-03 — battery's own revenue account, split off
    # 4150 by PO ruling. It is CONDITIONAL like every other service account: a
    # tenant that does not sell battery storage never receives it.
    assert conditional == {
        "4100",
        "4105",
        "4110",
        "4165",
        "4115",
        "4120",
        "4130",
        "4140",
        "4145",
        "4150",
    } | {
        "4160",
        "4170",
    } | {
        # CR-063 — fire's own account, and it is CONDITIONAL like every other
        # per-service revenue code: a tenant that does not sell fire is not
        # seeded 4155. Written as its own group rather than folded into the
        # first, so a reader sees which ruling put each code here — B5 line 74
        # signed the first nine, OQ-115 added 4160/4170, and CR-063 added this.
        "4155",
    }
    # Revenue accounts that are NOT per-service and must reach every tenant.
    assert {"4190", "4200", "4210"} <= {row.code for row in chart.SHARED_CHART}


def test_cr010_b9__silver_creek_water_gets_the_full_chart_and_every_service_row():
    """⚠ REWRITTEN 2026-08-18 — **the PO's OQ-115 worked case, REVERSED by its
    own author.** This test pinned Silver Creek Water (water + sewer) at 21
    accounts with 4100/4105/4130/4140/4145/4150 and 5100/5130/5140/5145 ABSENT.
    CR-010 B-9 (PO 2026-08-17, verbatim: *"9 - A full ~40 accounts for every
    tenant, as you said"*) and New mandate 4 (*"we will provdie full list for
    all services - they can always select what they want out of it; more is
    better ; less is contraint"*) reverse both halves:

      * the FULL chart — all 48 accounts since CR-060 C15 widened the cost
        vocabulary on 2026-09-01, 34 before it — seeds at provisioning, and
      * `tenant_services` carries a row for ALL TEN catalog services: water and
        sewer enabled, the other eight present-but-off with UoM and GL
        pointers filled.

    Provisioned through the REAL signup path, so this fails if either half
    lives anywhere but in the product.
    """
    silver, _ = provisioned_tenant(
        lonestarridge_payload(
            name="Silver Creek Water", subdomain="silvercreek", services=["water", "sewer"]
        )
    )
    with tenant_ctx(silver):
        codes = set(
            ledger_models.LedgerAccount.objects.filter(tenant=silver).values_list("code", flat=True)
        )
    # ⚠ AMENDED 2026-09-01 (CR-060 C15 · task T5) — CR-010 B-9's ruling is
    # unchanged and is what this asserts: *"full ~40 accounts for every tenant"*,
    # unconditional, whatever the tenant sells. The FULL chart is 48 now that
    # the cost vocabulary widened; a water-only tenant still gets every row.
    # ⚠ AMENDED 2026-09-02 (CR-061 statement (1)): the FULL chart is 125 now.
    # A water-only tenant still gets every row — B-9 is unconditional.
    assert codes == {row.code for row in chart.SEED_CHART} | {
        row.code for row in chart.COST_OF_SERVICE_CHART
    } | {row.code for row in chart.WIDENED_COST_CHART} | {
        row.code for row in chart.UTILITY_BOOKS_CHART
    } | {
        # ⚠ DEF-3441 — the fifth seed tuple, red since 2026-09-02 when CR-060
        # T7f seeded 5700 Depreciation expense. ALLOWANCE_CHART is NOT a sixth:
        # CR-060 T15 mints 1290 when a tenant switches the policy on.
        row.code
        for row in chart.PERIOD_MATCHING_CHART
    }
    # DEF-3441 — 126 since CR-060 T7f seeded 5700 Depreciation expense; 127
    # since the PO split solar and battery on 2026-09-03 (4165 Battery).
    # 128 since 2026-09-23 (CR-136-BRC07 §3.3 seeded 6850 Cash over and short).
    assert len(codes) == 128
    with tenant_ctx(silver):
        rows = {
            row.service.code: row
            for row in tenancy_models.TenantService.objects.filter(tenant=silver).select_related(
                "service", "revenue_account"
            )
        }
        assert set(rows) == set(chart.SERVICE_REVENUE_ACCOUNTS)  # all ten
        assert {code for code, row in rows.items() if row.enabled} == {"water", "sewer"}
        # Present-but-off is CONFIGURED-but-off: every row points at its chart
        # default, so enabling later is one toggle (mandate 4's whole point).
        for code, row in rows.items():
            expected_usage, _expected_base = chart.SERVICE_REVENUE_ACCOUNTS[code]
            assert row.revenue_account.code == expected_usage, code
            assert row.disabled_at is None, f"{code}: never-on must not read as switched-off"
        # Every designation resolves EXCEPT the three claimed on first use.
        # ⚠ **MOVED 2026-09-03 (DEF-3441)** — this asserted `== []` and had been
        # red since 2026-09-02; see `chart.DESIGNATED_ON_FIRST_USE`.
        unresolved = sorted(
            name for name, value in ledger_selectors.designation_map().items() if value is None
        )
        assert unresolved == sorted(chart.DESIGNATED_ON_FIRST_USE)


def test_cr010_b9__enabling_a_service_tops_up_a_narrowing_era_tenant():
    """B-9's own boundary: *"`ensure_service_revenue_accounts` keeps working as
    the lookup+top-up path."*

    A tenant provisioned between 2026-08-11 (OQ-115's narrowing) and 2026-08-17
    (its reversal) has NO 4140 — the full seed never reached it, and hard-won
    law 4 says a provisioning change never reaches a tenant that already has a
    chart. That state is reconstructed here (the account is hard-removed, which
    IS-1 permits while nothing references it, and the gas service row with it),
    and enabling Gas through `update_tenant_service` — the S8 write path —
    must MINT 4140 at that moment, exactly as it did under the narrowing.
    """
    silver, _ = provisioned_tenant(
        lonestarridge_payload(
            name="Silver Creek Water", subdomain="silvercreekgas", services=["water", "sewer"]
        )
    )
    actor = staff_actor(silver, "system_admin", "ops@silvercreek.test")
    with tenant_ctx(silver):
        # Reconstruct the narrowing-era shape: no gas account, no gas row.
        tenancy_models.TenantService.objects.filter(tenant=silver, service__code="gas").delete()
        account_for(silver, "4140").delete()
        assert not ledger_models.LedgerAccount.objects.filter(tenant=silver, code="4140").exists()

        tenancy_services.update_tenant_service(actor, "gas", {"enabled": True})

        gas = account_for(silver, "4140")
        assert (gas.code, gas.name) == ("4140", "Gas")
        assert ledger_selectors.revenue_account_id_for_service("gas") == str(gas.id)


# ═══════════════════════════════════════════════════════════════════════════
# OQ-115 second half — *"but allow tenant user to override it"*
# ═══════════════════════════════════════════════════════════════════════════
def test_oq_115__a_tenant_may_point_a_service_at_an_account_of_their_own(brazos, dana):
    """The override, through the S8 write path the API already exposes.

    A utility that keeps water revenue in its own `4111 Water sales — retail`
    says so once. From that moment every read resolves THEIR account, because
    `apps/ledger/selectors.py` reads the stored pointer and never the chart's
    default.
    """
    with tenant_ctx(brazos):
        own = ledger_models.LedgerAccount.objects.create(
            tenant=brazos, code="4111", name="Water sales — retail", type="revenue"
        )

        result = tenancy_services.update_tenant_service(
            dana, "water", {"revenue_account": str(own.id)}
        )

        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="water")
        assert row.revenue_account_id == own.id
        assert ledger_selectors.revenue_account_id_for_service("water") == str(own.id)
        # The write's own response shows what it wrote — a screen that cannot
        # read back what it saved is a screen nobody can trust.
        assert result["revenue_account"] == {
            "id": str(own.id),
            "code": "4111",
            "name": "Water sales — retail",
        }
        # The base account is untouched: an override names the field it names.
        assert row.base_revenue_account.code == "4115"


def test_oq_115__a_tenants_own_pointer_survives_a_reseed(brazos, dana):
    """**The protection the PO asked for, and the one this lane had to add.**

    `seed_chart_of_accounts` already refused to overwrite a CLAIMED DESIGNATION
    (its rule 2 — *"their pointer, not ours"*). The service→account attribute
    had no such protection because nothing could edit it. Now something can, so
    a re-provision, a repair script or a later migration that re-seeds must
    leave a tenant's own mapping standing.

    Proved RED first by making the seed re-point the service at 4110: this test
    then fails with the tenant's 4111 replaced by the chart's default.
    """
    with tenant_ctx(brazos):
        own = ledger_models.LedgerAccount.objects.create(
            tenant=brazos, code="4111", name="Water sales — retail", type="revenue"
        )
        tenancy_services.update_tenant_service(dana, "water", {"revenue_account": str(own.id)})

        summary = ledger_services.seed_chart_of_accounts(dana)

        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="water")
        assert row.revenue_account_id == own.id, "the re-seed took the tenant's own mapping back"
        assert ledger_selectors.revenue_account_id_for_service("water") == str(own.id)
        # Nothing was created: the tenant sells Electric and Water and already
        # has every account those need. 4110 still EXISTS — the seed does not
        # delete an account a tenant has stopped pointing at — it is simply not
        # what water revenue resolves to any more.
        assert summary["accounts_created"] == 0
        assert summary["services_seeded"] == ("electric", "water")
        assert account_for(brazos, "4110").deleted_at is None


def test_oq_115__an_override_may_clear_the_mapping(brazos, dana):
    """`null` CLEARS, and that is a real thing a tenant may want (an account
    retired, a chart restructured). The consequence is honest rather than
    hidden: an unmapped service refuses its lines at issue (BR-BIL-010)."""
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "electric", {"base_revenue_account": None})
        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="electric")
        assert row.base_revenue_account_id is None
        # …and the usage account now answers the base charge, per BR-BIL-010's
        # fallback — a cleared split is not a missing account.
        assert ledger_selectors.revenue_account_for_service("electric", base=True).code == "4100"


def test_oq_115__an_override_cannot_point_at_another_tenants_account(brazos, lonestar, dana):
    """The reason the LEDGER validates and not tenancy: the cross-module FK
    constrains existence, never ownership. Without the check a crafted id would
    point Brazos Bend's water revenue at Lone Star Ridge's chart — a
    cross-tenant read written into a money path."""
    with tenant_ctx(lonestar):
        stranger = account_for(lonestar, "4110")
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as raised:
            tenancy_services.update_tenant_service(
                dana, "water", {"revenue_account": str(stranger.id)}
            )
    assert raised.value.field_errors[0]["field"] == "revenue_account"
    assert raised.value.field_errors[0]["message_key"] == "settings.services.gl_account_unknown"
    with tenant_ctx(brazos):
        row = tenancy_models.TenantService.objects.get(tenant=brazos, service__code="water")
        assert row.revenue_account.code == "4110"
        assert row.revenue_account.tenant_id == brazos.id


def test_oq_115__an_override_cannot_point_at_a_deactivated_account(brazos, dana):
    """IS-1 deactivation is how a tenant says stop using this. Mapping revenue
    onto a row their own trial balance treats as retired is a gap they would
    only find at issue."""
    with tenant_ctx(brazos):
        retired = ledger_models.LedgerAccount.objects.create(
            tenant=brazos,
            code="4112",
            name="Old water sales",
            type="revenue",
            deleted_at=timezone_now(),
        )
        with pytest.raises(errors.ValidationError):
            tenancy_services.update_tenant_service(
                dana, "water", {"revenue_account": str(retired.id)}
            )


def test_oq_115__an_unknown_gl_field_is_still_refused(brazos, dana):
    """The closed payload stays closed: two new fields were added, not a door."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as raised:
            tenancy_services.update_tenant_service(dana, "water", {"gl_account": "1200"})
    assert raised.value.field_errors[0]["field"] == "gl_account"


def test_oq_115__a_malformed_account_id_is_a_field_error_not_a_500(brazos, dana):
    """An account id is a uuid the client sends back. A clerk's stale tab, or a
    caller sending an account CODE where an id belongs, must reach the same
    field error as an unknown account — not a database exception through the
    envelope. `account_is_live` answers False for anything that is not an id."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as raised:
            tenancy_services.update_tenant_service(dana, "water", {"revenue_account": "4110"})
    assert raised.value.field_errors[0]["message_key"] == "settings.services.gl_account_unknown"
    assert raised.value.field_errors[0]["params"]["account"] == "4110"


def test_a_deactivated_revenue_account_stops_resolving(brazos):
    """The liveness check the ledger performs over tenancy's pointer. The FK
    guarantees the row exists; it does not guarantee the tenant still uses it,
    and IS-1 deactivation is how a tenant says stop."""
    with tenant_ctx(brazos):
        account = account_for(brazos, "4100")
        account.deleted_at = timezone_now()
        account.save(update_fields=["deleted_at", "updated_at"])
        assert ledger_selectors.revenue_account_id_for_service("electric") is None
        # …and the base side is unaffected: 4105 is a different account.
        assert ledger_selectors.revenue_account_for_service("electric", base=True).code == "4105"


def test_the_ledger_refuses_when_tenancy_publishes_no_read(brazos, monkeypatch):
    """Hard-won law 3 — the unsafe option must be the one you type.

    "This service has no revenue account" and "the ledger cannot see tenancy"
    have the same shape and different meanings; conflating them turns a wiring
    failure into a silently unmapped bill line that freezes at issue.
    """
    from apps.ledger import tenancy_seam

    monkeypatch.delattr(tenancy_selectors, "service_gl_attributes")
    with tenant_ctx(brazos):
        with pytest.raises(tenancy_seam.LedgerSeamNotWired) as raised:
            ledger_selectors.revenue_account_id_for_service("electric")
    assert "service_gl_attributes" in str(raised.value)


# ═══════════════════════════════════════════════════════════════════════════
# OQ-147 — THE PRODUCT NUMBERS A TAX-PAYABLE ACCOUNT. THE TENANT DOES NOT TYPE
# IT. PO ruling 2026-08-12, verbatim: *"Generated"*.
#
# These tests replace the pair that pinned the REFUSAL (`create_tax_authority
# _account(code=None)` used to raise a `NotImplementedError` citing the then-open
# question). They are
# rewritten, not deleted: each one now pins the ruling in the same place the
# refusal was pinned, so the day someone reverts to "make the clerk type it"
# this file goes RED.
#
# The three properties that matter, and each has its own test below:
#   1. MONOTONIC — the next code is strictly above every 2200-nn this tenant
#      has ever held, live or deactivated. A gap is left as a gap, forever.
#   2. THE DATABASE DECIDES, NOT THE READ — `uq_ledger_accounts_code` is what
#      stops two clerks sharing a code; the allocator re-reads and retries when
#      it loses that race.
#   3. PER TENANT — Brazos and Lone Star Ridge each have their own 2200-01.
# ═══════════════════════════════════════════════════════════════════════════
def test_oq_147__the_product_numbers_the_next_2200_account(brazos, dana):
    """PO 2026-08-12, verbatim *"Generated"* — three authorities, three codes.

    A tenant adds State of Texas, Harris County and the City of Katy and never
    types a code: the product allocates 2200-01, 2200-02, 2200-03 inside the ❄️
    finance-signed 2200 series (B5 line 74). Each is a liability and none
    carries a designation (option C of OQ-116 was declined by the PO).
    """
    with tenant_ctx(brazos):
        minted = [
            ledger_services.create_tax_authority_account(
                name=f"Tax payable — {authority}", actor=dana
            )
            for authority in ("State of Texas", "Harris County", "City of Katy")
        ]
    assert [account.code for account in minted] == ["2200-01", "2200-02", "2200-03"]
    assert {account.type for account in minted} == {chart.TAX_PAYABLE_TYPE}
    assert {account.designation for account in minted} == {None}
    assert all(chart.is_tax_payable_code(account.code) for account in minted)


def test_oq_147__a_generated_code_never_reuses_a_deactivated_ones_number(brazos, dana):
    """THE GAP RULE, half one: a deactivated authority's number is never re-let.

    2200-02 AND 2200-03 are deactivated (IS-1 deactivate-first — the rows stay,
    and so does the journal history pointing at them). The next allocation is
    **2200-04**, not 2200-02 and not 2200-03. Two reasons, and the first alone
    settles it: `uq_ledger_accounts_code` counts soft-deleted rows, so
    re-issuing 2200-02 is an IntegrityError, not a nice-to-have. The second is
    finance's — a code that meant Harris County in March and City of Katy in
    June makes every remittance report drawn before the reissue read wrong,
    silently.

    **THE HIGHEST number is deactivated on purpose.** An earlier draft of this
    test retired only the middle one, and an allocator that filtered
    `deleted_at__isnull=True` — the exact mutation this test exists to catch —
    still passed it, because the live maximum was unchanged. Retiring the top of
    the range is what makes the guard bite (hard-won law 7: the mutation was run
    and it went GREEN, which is how this paragraph came to be written).
    """
    with tenant_ctx(brazos):
        for authority in ("State of Texas", "Harris County", "City of Katy"):
            ledger_services.create_tax_authority_account(name=f"Tax payable — {authority}")
        for code in ("2200-02", "2200-03"):
            retired = account_for(brazos, code)
            retired.deleted_at = timezone_now()
            retired.save(update_fields=["deleted_at", "updated_at"])

        nxt = ledger_services.create_tax_authority_account(name="Tax payable — Fort Bend County")
    assert nxt.code == "2200-04", "a deactivated number is retired, not recycled"
    assert (
        ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code__in=("2200-02", "2200-03")
        ).count()
        == 2
    ), "the deactivated rows are still there holding their codes"


def test_oq_147__a_generated_code_steps_over_a_gap_the_tenant_left(brazos):
    """THE GAP RULE, half two: a gap that was NEVER filled stays a gap.

    A utility migrating an accountant's chart typed 2200-01 and 2200-04 by
    hand; 02 and 03 never existed. The allocator does not backfill them — it
    goes to **2200-05**. "Lowest free" would be the other reading and it is the
    unsafe one: it hands out the number a clerk deliberately skipped, and it
    walks straight into a soft-deleted row the moment one exists.
    """
    with tenant_ctx(brazos):
        ledger_services.create_tax_authority_account(code="2200-01", name="Tax payable — Texas")
        ledger_services.create_tax_authority_account(code="2200-04", name="Tax payable — Katy")
        assert (
            ledger_services.create_tax_authority_account(name="Tax payable — Harris").code
            == "2200-05"
        )


def test_oq_147__the_suffix_is_ordered_by_number_not_by_string(brazos):
    """Past 99 the suffix widens; it does not wrap and it does not go backwards.

    A tenant with 2200-99 gets **2200-100** next. Asserted because the obvious
    implementation — `max()` over the code strings — answers `2200-99` for a
    chart holding `2200-100`, and would then re-issue a code that already
    exists on every subsequent call.
    """
    with tenant_ctx(brazos):
        ledger_services.create_tax_authority_account(code="2200-99", name="Tax payable — 99")
        assert (
            ledger_services.create_tax_authority_account(name="Tax payable — 100").code
            == "2200-100"
        )
        assert (
            ledger_services.create_tax_authority_account(name="Tax payable — 101").code
            == "2200-101"
        )


def test_oq_147__non_generated_2200_codes_do_not_disturb_the_series(brazos):
    """A hand-typed `2200` or `2200.TX` is left out of the count, not parsed.

    `is_tax_payable_code` accepts any code in the series and always has (it is
    a prefix test). Only the `2200-<digits>` shape the product itself issues is
    read as a number; anything else is a tenant's own code that cannot collide
    with a generated one, so it neither raises nor moves the high-water mark.
    """
    with tenant_ctx(brazos):
        for code in ("2200", "2200.TX", "2200XYZ"):
            ledger_services.create_tax_authority_account(code=code, name=f"Tax {code}")
        assert (
            ledger_services.create_tax_authority_account(name="Tax payable — generated").code
            == "2200-01"
        )


def test_oq_147__two_clerks_at_the_same_moment_cannot_get_the_same_code(brazos, monkeypatch):
    """CONCURRENCY — the unique index decides the winner, and the loser re-reads.

    The interleaving simulated is the real one: clerk A reads the high-water
    mark (nothing → 2200-01), clerk B commits 2200-01 first, and A's INSERT then
    hits `uq_ledger_accounts_code`. A read-then-write allocator would either
    raise in A's face or — worse, if it swallowed the IntegrityError the way the
    tenant-typed path does — hand A the account that already belongs to B's
    authority. Neither happens: A retries and gets **2200-02**, and two
    authorities end up with two accounts.

    The rival insert is forced OUTSIDE the allocator's savepoint, which is what
    makes this a race and not a self-inflicted rollback.
    """
    real_next = ledger_services._next_tax_payable_code
    rival: dict[str, object] = {}

    def rival_clerk_commits_first(tenant_id):
        code = real_next(tenant_id)
        if not rival:
            rival["account"] = ledger_models.LedgerAccount.objects.create(
                tenant_id=tenant_id, code=code, name="Tax payable — the other clerk"
            )
            rival["code"] = code
        return code

    monkeypatch.setattr(ledger_services, "_next_tax_payable_code", rival_clerk_commits_first)
    with tenant_ctx(brazos):
        mine = ledger_services.create_tax_authority_account(name="Tax payable — my authority")

    assert rival["code"] == "2200-01"
    assert mine.code == "2200-02", "the loser of the race re-reads and takes the next code"
    assert mine.id != rival["account"].id
    assert (
        ledger_models.LedgerAccount.objects.filter(tenant=brazos, code__startswith="2200").count()
        == 2
    )


def test_oq_147__the_database_is_the_guarantee_not_the_read(brazos):
    """The guard the allocator leans on, asserted directly (hard-won law 1).

    `uq_ledger_accounts_code` is a real UNIQUE index on (tenant, code), created
    by ledger migration 0001 — not a comment, not an application check. If it
    ever went away this test goes RED before the allocator quietly starts
    issuing duplicates under load.
    """
    with tenant_ctx(brazos):
        ledger_services.create_tax_authority_account(name="Tax payable — first")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ledger_models.LedgerAccount.objects.create(
                    tenant=brazos, code="2200-01", name="A second account on the same code"
                )


def test_oq_147__each_tenant_numbers_its_own_series(brazos, lonestar):
    """CLAUDE.md rule 1 — Brazos and Lone Star Ridge each get their own 2200-01.

    The high-water read is tenant-filtered and the unique constraint leads with
    `tenant`, so a busy tenant's numbering never pushes a quiet one's along.
    """
    with tenant_ctx(brazos):
        mine = ledger_services.create_tax_authority_account(name="Tax payable — Brazos")
    with tenant_ctx(lonestar):
        theirs = ledger_services.create_tax_authority_account(name="Tax payable — Lone Star")
    assert mine.code == theirs.code == "2200-01"
    assert mine.tenant_id == brazos.id
    assert theirs.tenant_id == lonestar.id
    assert mine.id != theirs.id


def test_oq_147__a_generated_account_says_so_in_the_audit_trail(brazos, dana, audit_rows):
    """BR-LED-015 / CLAUDE.md rule 7 — and the trail records WHO numbered it.

    The ruling is that choosing and numbering are different acts, so the audit
    row says which one happened: `code_source` is `generated` for a code the
    product allocated and `tenant_supplied` for one a human typed. Without it
    the trail cannot answer "did we number this, or did their accountant?" —
    the first question anyone asks when two authorities look wrong.
    """
    with tenant_ctx(brazos):
        ledger_services.create_tax_authority_account(
            name="Tax payable — State of Texas", actor=dana
        )
        ledger_services.create_tax_authority_account(
            code="2200-77", name="Tax payable — their own code", actor=dana
        )
    rows = {
        row["after"]["code"]: row["after"]
        for row in audit_rows
        if row["action"] == "ledger_account.created" and row["after"]["source"] == "tax_authority"
    }
    assert rows["2200-01"]["code_source"] == "generated"
    assert rows["2200-77"]["code_source"] == "tenant_supplied"
    assert rows["2200-01"]["designation"] is None
    assert rows["2200-01"]["finance_signed"] is True


def test_oq_147__the_allocator_refuses_outside_a_tenant_context():
    """CLAUDE.md rule 1 — a generated code belongs to a tenant or to nobody.

    The refusal happens before any query, so no allocation is attempted against
    a chart the caller cannot name.
    """
    with pytest.raises(errors.AuthError) as raised:
        ledger_services.create_tax_authority_account(name="Tax payable — nobody's")
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ═══════════════════════════════════════════════════════════════════════════
# Tenant scoping (CLAUDE.md rule 1)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_005_tc6__a_designation_never_crosses_a_tenant(brazos, lonestar):
    """US-LED-005 TC-6 at the app layer: each tenant's AR is its own row.

    Both tenants get the same seeded chart, so both have an account designated
    `accounts_receivable` — which is exactly why this needs asserting: a lookup
    that lost its tenant filter would still find *an* AR account and look fine.
    """
    with tenant_ctx(brazos):
        brazos_ar = ledger_selectors.gl_account_for_designation(chart.AR)
    with tenant_ctx(lonestar):
        lonestar_ar = ledger_selectors.gl_account_for_designation(chart.AR)
    assert brazos_ar.pk != lonestar_ar.pk
    assert brazos_ar.tenant_id == brazos.id
    assert lonestar_ar.tenant_id == lonestar.id


def test_the_selectors_refuse_outside_a_tenant_context(brazos):
    """CLAUDE.md rule 1's app half: no tenant table is touched without
    `app.tenant_id`, and the refusal happens before a query is built."""
    from core import errors

    with pytest.raises(errors.AuthError) as raised:
        ledger_selectors.gl_account_for_designation(chart.AR)
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE

    with pytest.raises(errors.AuthError):
        ledger_services.seed_chart_of_accounts()


# ═══════════════════════════════════════════════════════════════════════════
# G5 — the DATABASE half, on a live cluster under a NOSUPERUSER probe role
# ═══════════════════════════════════════════════════════════════════════════
GL_TABLES = ("ledger_accounts", "tenant_services")


@pytest.mark.isolation
@requires_postgres
def test_us_led_005_tc6__a_designation_is_rls_scoped(rls, brazos, lonestar):  # noqa: F811
    """US-LED-005 TC-6 at the DATABASE, with the app-layer filter deliberately
    out of the path.

    Reading another tenant's `accounts_receivable` account is reading which
    account their whole ledger is anchored on. This migration added a COLUMN
    and no table, so the guarantee comes from `ledger_accounts_tenant_isolation`
    (ledger/0002) and `tenant_services_tenant_isolation` (tenancy/0003) — and a
    claim that an existing policy covers a new column is worth nothing until it
    is probed, which is what this does.
    """
    with live_tenant_context(brazos.id):
        brazos_ar = str(
            ledger_models.LedgerAccount.objects.get(tenant=brazos, designation=chart.AR).id
        )

    assert_rls_scoped(
        rls, "ledger_accounts", owner=brazos, intruder=lonestar, owner_ids={brazos_ar}
    )
    assert_rls_scoped(rls, "tenant_services", owner=brazos, intruder=lonestar)

    # The designation-keyed probe, which is the shape a posting service uses:
    # under the intruder's context the neighbour's AR row is simply not there.
    with live_tenant_context(lonestar.id):
        assert rls.count("ledger_accounts", "id = %s", [brazos_ar]) == 0
        assert rls.count("ledger_accounts", "designation = %s", [chart.AR]) == 1
    assert_no_foreign_rows_anywhere(rls, lonestar, GL_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_led_005_tc6__gl_attributes_are_denied_outright_with_no_context(
    rls, brazos
):  # noqa: F811
    """Deny-by-default, both halves: with `app.tenant_id` unset the policy's
    `::uuid` cast of '' fails and NO row is visible, and the selector refuses
    before a query is ever built."""
    from core import errors

    assert_denied_without_context(rls, *GL_TABLES)
    with pytest.raises(errors.AuthError) as raised:
        ledger_selectors.designation_map()
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (sources: 12-governance/02-decision-log.md 2026-08-11 "OQ-106 IS CLOSED" / "OQ-110 CLOSED" / "STORM WATER AND THERMAL HEAT GET REVENUE ACCOUNTS" · 12-governance/01-open-questions.md OQ-115 (CLOSED) · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ seed chart · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-010 + BR-BIL-067 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md US-LED-005)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane — the ruling's three halves: 4160/4170 marked unsigned · the tenant override and its survival of a re-seed · Silver Creek Water's conditional chart and the Gas mint) · AMENDED 2026-08-15 by the AP-capture lane (US-LED-017 / BR-LED-037/038: three seeded-set assertions restated for the COST ladder — provisioning now also seeds 5200/5300 to every tenant and a commodity cost account per service SOLD. No signed-chart assertion was weakened: the signed set is still asserted exactly, the cost set is asserted separately, and the audit assertion was SPLIT so that `finance_signed` is checked per code — the old `== {True}` set form would have gone on passing if the flag were dropped from the unsigned cost rows)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED-proof recorded in the lane report and the human-review ledger row
# exceptions: the two -m isolation cases are Postgres-only and SKIP on the
#         default sqlite database with a vendor reason (never a silent pass) ·
#         [OQ-115 lane] the override tests assert the SERVICE LAYER, not HTTP:
#         `update_tenant_service` is what PUT /api/settings/services/<service>
#         already calls, and no new route was added — so the API half is wired
#         by the existing endpoint rather than deferred
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defects: DEF-BIL-5326 (a percent-of-service utility cannot be back-billed) ·
#          DEF-BIL-5317 (the penalty bill's tamper fee refuses over a read that
#          exists). Both filed 2026-09-15, both on the SUB-PERIOD bill path.
# Rules:   BR-BIL-015 (a missing read is a HUMAN's decision — NOT weakened
#          here, and the negative halves below are the proof) · BR-RAT-015
#          (sewer prices a percentage of water, so it has no reading of its
#          own) · BR-BIL-007 (a charge code carries its own amount and GL) ·
#          BR-BIL-019 (a penalty bill is assessed reads + charge-code lines,
#          and a hand-typed amount is neither)
# Screens: S30 One-time bill, step 2
# ───────────────────────────────────────────────────────
"""The two defects the sub-period bill path shipped, and the halves that stay.

**Neither defect is a rule being wrong; both are a SECOND OPINION that drifted.**
`backbill` kept its own copy of which absent-read reasons are exempt and it had
fallen three reasons behind the interim path. `penalty` kept its own opinion
about whether rating publishes a charge-code read and it had been wrong for
nineteen days. Each file was internally consistent, so every suite was green.

**What each cost, measured on the demo tenant before the fix:**

  * `DEF-BIL-5326` — account `E11-0001` over 2026-08-16 → 2026-09-15 priced 24
    lines totalling **$573.33** as an INTERIM bill, two of them *"sewer usage —
    60.00% of water volume"* **$28.35** and *"sewer base charge"* **$22.50**.
    The same account and the same window as a BACK-BILL or a PENALTY bill
    refused with `missing_read_undecided_at_calculate` naming sewer.
  * `DEF-BIL-5317` — `penalty_charge_line` raised for every code in every
    tenant, so a theft bill restated the stolen usage and carried no tamper fee.
    The demo tenant's `TAMPER` is **$250.0000**.

⚠ **THE NEGATIVE HALVES ARE THE DELIVERABLE, NOT THE LEFTOVER**, and they are
the half a careless fix removes: a METERED service with no read must still stop
the bill, and a charge code with no flat amount must still REFUSE rather than
charge a number nobody computed.
"""

from decimal import Decimal

import pytest

from apps.billing import backbill, fee_bill, midperiod, one_time, penalty, runs
from apps.billing.stages import measure_consumption as mcs
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-5326 — the exempt list is ONE list, and the sub-period path reads it
# ══════════════════════════════════════════════════════════════════════════


def test_def_bil_5326__the_four_exempt_reasons_are_one_list():
    """The list itself, named and complete — the thing that drifted.

    Asserted by VALUE rather than by length, because the defect was a list that
    had grown on one side. A fifth reason added to `EXEMPT_FROM_MISSING_READ`
    fails here and is then added deliberately, in one place, for all three paths.
    """
    assert mcs.EXEMPT_FROM_MISSING_READ == (
        mcs.ABSENT_BASE_ONLY,
        mcs.ABSENT_NOT_USAGE_MEASURED,
        mcs.ABSENT_TARIFF_BASE_ONLY,
        mcs.ABSENT_SERVICE_NOT_METERED,
        # ADDED 2026-10-01 (billing red triage), deliberately, as this
        # docstring asks: the FIFTH reason, a clerk's fact — PO 2026-09-30,
        # fixed-charge case 1, a service billed WITHOUT its reading has its
        # usage billed next bill (`dd0ecb9d1`, US-BIL-037). Red from that
        # commit until today.
        mcs.ABSENT_USAGE_NEXT_BILL,
    )


def test_def_bil_5326__a_percent_of_service_reason_is_exempt_and_a_missing_read_is_not():
    """BR-RAT-015 sewer is exempt; BR-BIL-015's own reason never is.

    `ABSENT_NOT_USAGE_MEASURED` is the reason a percent-of-service sewer carries
    — measured on the demo tenant, `measure_consumption` derives exactly this
    for sewer on both the interim and the back-bill path. `ABSENT_NO_READING` is
    a metered service nobody read, which is the whole subject of BR-BIL-015 and
    must never appear on the exempt list.
    """
    assert mcs.ABSENT_NOT_USAGE_MEASURED in mcs.EXEMPT_FROM_MISSING_READ
    assert mcs.ABSENT_NO_READING not in mcs.EXEMPT_FROM_MISSING_READ
    # The three that refuse BY THEIR OWN NAME one layer up stay OFF the list —
    # reading any of them as exempt bills a three-cart household $0.00 for trash
    # and a 14 kW array $0.00 for solar, on documents that foot and print.
    assert mcs.ABSENT_ASSET_COUNT_UNAVAILABLE not in mcs.EXEMPT_FROM_MISSING_READ
    assert mcs.ABSENT_ASSET_COUNT_UNIT_UNSTATED not in mcs.EXEMPT_FROM_MISSING_READ
    assert mcs.ABSENT_INSTALLED_CAPACITY_UNRESOLVED not in mcs.EXEMPT_FROM_MISSING_READ


def test_def_bil_5326__no_bill_path_carries_its_own_copy_of_the_list():
    """The guard that stops the defect recurring — read the SOURCE, not a value.

    This is the assertion the register asked for. Three modules raise
    BR-BIL-015's refusal and each used to spell the reasons out; `backbill`'s
    copy fell three behind and nothing could see it. A path that re-spells them
    passes every other test in this file and fails this one.
    """
    import inspect

    for module in (runs, midperiod, backbill):
        source = inspect.getsource(module)
        # The refusal's own filter must name the shared tuple...
        assert "EXEMPT_FROM_MISSING_READ" in source, module.__name__
        # ...and must not re-spell the membership beside it.
        assert "ABSENT_NOT_USAGE_MEASURED,\n" not in source, (
            f"{module.__name__} spells an exempt reason out again — that is the "
            "second opinion DEF-BIL-5326 was filed for"
        )


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-5317 — the penalty line is built by the ONE charge-code builder
# ══════════════════════════════════════════════════════════════════════════

#: ⚠ **$250.00 IS A PRODUCT OWNER RULING, NOT THIS TEST'S NUMBER AND NOT THIS
#: TENANT'S EITHER.** On 2026-08-10 the PO chose between `EP-RAT-03` §4's
#: **$250.00** and the billing workbook's **$500.00** and made the first a
#: PLATFORM DEFAULT; `apps/rating/services.py` seeds it from the reference
#: fixture's own decimal string, so every provisioned tenant starts with it.
#: WE-11 and the Billing blueprint still draw **$500.00** — B14 rule 37 makes a
#: drawn figure an ILLUSTRATION and never a fact to build to, and BR-BIL-019
#: forbids a hand-typed amount outright.
#:
#: **So this file asserts the SEEDED figure rather than creating one**, which is
#: the stronger claim: it proves the line carries what the utility's own
#: catalogue says, and it goes red if the platform default ever moves without a
#: ruling.
TAMPER_AMOUNT = Decimal("250.0000")


def _charge(tenant, code, *, amount, rule="flat", gl=True, name=None):
    """A charge code in whatever state the case needs, seeded or not.

    `update_or_create` rather than `create`, because provisioning already seeds
    this tenant's catalogue (`TAMPER`, `NSF`, `LATE` among them) and a plain
    create collides on `charges.tenant_id, charges.code` — which is a fixture
    failing, not the product refusing, and the two must not look alike in a red
    run (hard-won law 7: a check that fails for the wrong reason proves nothing).
    """
    row, _created = rating_models.Charge.objects.update_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": name or f"{code} fee",
            "charge_type": "penalty",
            "amount_rule": rule,
            "amount": None if amount is None else Decimal(amount),
            # `DEF-BIL-9073` — a REAL ledger account of this tenant, never a
            # literal id: PostgreSQL refuses one at COMMIT, SQLite never checks.
            "gl_account_id": (
                ledger_models.LedgerAccount.objects.filter(tenant=tenant)
                .order_by("code")
                .values_list("id", flat=True)
                .first()
                if gl
                else None
            ),
        },
    )
    return row


def test_def_bil_5317__the_platform_seeds_tamper_at_the_ruled_figure(brazos):
    """The PO's 2026-08-10 ruling, asserted where a tenant actually gets it.

    Provisioning seeds this code from the reference fixture; nothing in billing
    or in this test chooses the number. If the platform default ever moves, this
    goes red and the ruling has to move with it.
    """
    with tenant_ctx(brazos):
        seeded = rating_models.Charge.objects.filter(code="TAMPER").first()

    assert seeded is not None, "TAMPER is a platform-seeded code (PO 2026-08-10)"
    assert _flat(seeded) == TAMPER_AMOUNT
    # ⚠ AND IT IS NOT THE DRAWN ONE. WE-11 and the blueprint both say $500.00.
    assert _flat(seeded) != Decimal("500.0000")


def test_def_bil_5317__the_tamper_line_carries_the_tenants_own_amount(brazos):
    """The defect itself: a real line where there was an unconditional refusal.

    `penalty_charge_line` raised `charge_code_reader_not_published` for EVERY
    code, in every tenant, because it named the seam as the module constant
    `CHARGE_CODE_READ = "charge_ref"` — a name rating never published — instead
    of asking `gather._resolve` at call time. `apps.rating.selectors
    .charge_by_code` has been published for billing since `DEF-708` on
    2026-08-27 and `fee_bill.charge_code_line` has read it ever since.
    """
    with tenant_ctx(brazos):
        # The AMOUNT is the platform seed's (asserted above); only the GL
        # account is ensured here, because BR-BIL-010 requires one and pointing
        # seeded codes at accounts is `CR-066`'s job, not this defect's.
        _charge(brazos, "TAMPER", amount=TAMPER_AMOUNT, name="Tamper fee")
        line = penalty.penalty_charge_line("TAMPER")

    assert line.amount == TAMPER_AMOUNT
    assert line.kind == "fee"
    assert line.description == "Tamper fee"
    # BR-BIL-010 / DEF-714 — WHICH code this line came from, or `issue` refuses
    # it at release and the bill dies after an invoice number is spent.
    assert line.charge_id is not None


def test_def_bil_5317__it_delegates_rather_than_holding_a_second_opinion(brazos):
    """The repair the register asked for, asserted BY CALLING the delegate.

    Two opinions about whether a charge code can be priced is how these two
    drifted nineteen days apart. The assertion is byte-for-byte equality with
    `fee_bill.charge_code_line`, so a future `penalty`-side reimplementation —
    a second refusal list, a second amount read — fails here.
    """
    with tenant_ctx(brazos):
        _charge(brazos, "TAMPER", amount=TAMPER_AMOUNT, name="Tamper fee")
        mine = penalty.penalty_charge_line("TAMPER")
        theirs = fee_bill.charge_code_line("TAMPER")

    assert (mine.kind, mine.description, mine.amount, mine.taxable, mine.charge_id) == (
        theirs.kind,
        theirs.description,
        theirs.amount,
        theirs.taxable,
        theirs.charge_id,
    )


def test_def_bil_5317__no_module_constant_names_the_seam_any_more(brazos):
    """`CHARGE_CODE_READ` is gone, and its absence is the durable half.

    The wrong string was not the defect — holding a string at all was. A module
    constant naming a seam cannot go stale loudly: it simply keeps being wrong
    while every test passes. `gather._resolve` is asked at call time instead.
    """
    assert not hasattr(penalty, "CHARGE_CODE_READ")


@pytest.mark.parametrize(
    "code,amount,rule,gl,why",
    [
        ("NOSUCH", None, "flat", True, "not a live charge code of this tenant"),
        ("PCT", None, "percent", True, "a percent rule has no basis to apply"),
        ("NOGL", "40.0000", "flat", False, "no GL account, so it could never be issued"),
    ],
)
def test_def_bil_5317__an_unpriceable_code_still_refuses(brazos, code, amount, rule, gl, why):
    """⚠ THE NEGATIVE HALF — a number nobody computed is never charged.

    `charge_by_code` returns `amount=None` for a `percent` or
    `percent_with_minimum` rule ON PURPOSE, because such a rule needs a BASIS
    and a penalty line has none. The caller must REFUSE, not default: a fee that
    quietly prices at nothing is a fee nobody notices was never charged, and it
    lands on a document rule 4 makes immutable.
    """
    with tenant_ctx(brazos):
        if code != "NOSUCH":
            _charge(brazos, code, amount=amount, rule=rule, gl=gl)
        with pytest.raises(Exception) as raised:
            penalty.penalty_charge_line(code)

    assert code in str(raised.value)
    # And nothing anywhere in the refusal offers a figure to fall back on.
    assert "500" not in str(raised.value)


def test_def_bil_5317__an_unpriceable_code_stops_the_prepare_before_anything_is_written(brazos):
    """Refused in PHASE 1, which writes nothing — before an invoice number.

    `prepare_penalty_bill` builds the lines, so a code this tenant does not have
    costs a clerk their time and not a spent number on a draft that can never be
    issued. A penalty bill that silently dropped its penalty is the worst of the
    available failures: it looks complete, the customer pays the restated usage,
    and the tamper fee is never charged at all.
    """
    import inspect

    source = inspect.getsource(penalty.prepare_penalty_bill)
    assert "penalty_charge_line(code) for code in charge_codes" in source
    # And what it built travels ONTO the document rather than being discarded —
    # the loop used to call the line builder purely for the exception it raised
    # and then price the back-bill without it.
    assert "extra_fees=prepared.charge_lines" in inspect.getsource(penalty.calculate_penalty_bill)


def test_def_bil_5317__the_screen_no_longer_states_an_absence_that_ended(brazos):
    """The mirror sentence is GONE, not reworded (hard-won law 1 + law 2's mirror).

    `ONE_TIME_UNAVAILABLE` told every clerk on the One-time tab that a penalty
    bill's charge-code line *"cannot be added"*. It was true when written and
    stopped being true on 2026-08-27. A live capability behind a sentence saying
    it does not exist is the mirror of dead UI, and it keeps a clerk from trying
    the thing that now works.
    """
    codes = {row["code"] for row in one_time.ONE_TIME_UNAVAILABLE}
    assert "penalty_charge_code_line_cannot_be_priced" not in codes
    # A penalty bill's charge code is OPTIONAL, unlike a fee's, where the code
    # IS the bill — restated usage and nothing else is a legal penalty bill.
    assert one_time.KIND_PENALTY not in one_time.CHARGE_CODE_KINDS
    assert one_time.KIND_PENALTY in one_time.SUB_PERIOD_KINDS

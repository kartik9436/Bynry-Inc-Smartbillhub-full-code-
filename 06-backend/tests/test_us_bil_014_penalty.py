# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-014 (penalty / theft bill — assessed reads priced by the
#           engine plus charge-code penalties, never hand-typed)
#           Screens: S30 · S31
# Rules:    BR-BIL-019 (charge-code lines only; assessed reads priced by
#           back-billing; approval-gated) · BR-BIL-018 (theft EXEMPT from the
#           window cap) · BR-BIL-007 (a charge code carries its own amount and
#           GL) · BR-MET-053 (assessed reads enter through metering)
# Golden:   GT-27 (= WE-11, ❄️ FROZEN 2026-08-08): assessed on 150 → 33.00 ·
#           mid 300 → 42.00 · off 450 → 40.50 = taxable **115.50** → tax
#           **10.92** → TAMPER **500.00** → total **626.42**.
# ───────────────────────────────────────────────────────
"""The theft bill: what it CAN do today, and exactly where it stops.

WE-11's figures are NOT asserted here as passing values, and the reason is
worth stating plainly because a green test that quietly proved nothing would be
worse than this file's honesty. WE-11's usage is TOU (summer on/mid/off at
0.22/0.14/0.09) and the rating engine implements flat and tiered only — its own
docstring lists TOU as unimplemented. Its TAMPER $500.00 line needs a
charge-code reader that rating does not publish. Building a flat tariff that
happened to total 115.50 would bind the frozen figure to a fixture rather than
to the product.

So what is proved is the half that carries the money and IS built: assessed
reads for a stolen period, priced per sub-period on the tariff versions in
force THEN, exempt from the back-bill window cap. And what is not built refuses
BY NAME, which the negative tests assert — because a penalty bill that silently
dropped its penalty is the worst available failure: it looks complete, the
customer pays the restated usage, and the tamper fee is never charged.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import backbill, models as billing_models, penalty
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_bil_013_backbill import (
    V3_BASE,
    V3_TIERS,
    a_cycle,
    a_two_version_water_plan,
    a_water_unit,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

THEFT_REASON = "theft-restated"  # US-BIL-014 §4 verbatim
#: ⚠ **THE TENANT'S FIGURE, AND IT IS DELIBERATELY NOT WE-11's $500.00**
#: (`DEF-BIL-5317`, 2026-09-15). B14 rule 37: a figure drawn in a wireframe is
#: an ILLUSTRATION, never a fact to build to. This is what the demo tenant's own
#: `TAMPER` row carries, and it is SEEDED below rather than expected — the point
#: of BR-BIL-007 is that a utility sets its own price.
TENANT_TAMPER_AMOUNT = Decimal("250.0000")
ASSESSED_MONTHS = [
    (date(2025, 11, 1), date(2025, 11, 30)),
    (date(2025, 12, 1), date(2025, 12, 31)),
]
#: A 14-month theft window — over the tenant's 12-month cap, allowed only
#: because BR-BIL-018's closure exempts theft (US-BIL-014 TC-4).
FOURTEEN_MONTHS = [
    (date(2025, 1, 1), date(2025, 1, 31)),
    (date(2026, 2, 1), date(2026, 2, 28)),
]


def a_run(tenant, cycle, key="penalty-1"):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=ASSESSED_MONTHS[0][0],
        period_end=ASSESSED_MONTHS[-1][1],
        idempotency_key=key,
    )


def test_us_bil_014_tc1__assessed_reads_are_priced_by_the_engine_not_typed(brazos, dana):
    """TC-1: the restated consumption is priced, per period, by the rating engine.

    BR-BIL-019's first ingredient. The clerk supplies no amount anywhere: the
    reads exist (metering's lifecycle) and back-billing prices them on the
    version in force during the stolen months, which is why a theft bill and a
    catch-up bill can never round differently.
    """
    with tenant_ctx(brazos):
        plan, versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-9001", read_days=[e for _s, e in ASSESSED_MONTHS]
        )
        account = an_account(brazos, unit["id"], "A-14001")

        prepared = penalty.prepare_penalty_bill(
            account_id=account.id, sub_periods=ASSESSED_MONTHS, reason_code=THEFT_REASON
        )
        invoice = penalty.calculate_penalty_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, code="TH-A"))
        )

        priced = sorted(line.amount for line in invoice.lines.all() if line.kind == "usage")
        bases = sorted(line.amount for line in invoice.lines.all() if line.kind == "base")

    assert invoice.bill_type == "penalty"
    # Both stolen months sit inside v3's window, so both price on v3 — a theft
    # case does not escape BR-RAT-007 any more than a catch-up does.
    assert priced == sorted(V3_TIERS * 2)
    assert bases == [V3_BASE, V3_BASE]
    assert {str(v) for v in prepared.back_bill.groups[0].tariff_version_ids.values()} == {
        str(versions["v3"].id)
    }


def test_us_bil_014_tc2__the_tamper_charge_code_is_priced_from_the_tenants_own_row(brazos, dana):
    """TC-2 (WE-11's charge-code half): the tenant's figure, never WE-11's.

    ⚠ **THIS TEST ASSERTED A REFUSAL UNTIL 2026-09-15 AND THE REFUSAL WAS THE
    DEFECT (`DEF-BIL-5317`).** It read
    *"the_tamper_charge_code_refuses_rather_than_inventing_500"* and asserted
    `raised.value.reason == penalty.PENALTY_NO_CHARGE_CODE_READER`, on the
    stated grounds that *"rating publishes no read that resolves a code to an
    amount"*. **That stopped being true on 2026-08-27**, when `DEF-708` pointed
    `fee_bill.charge_code_line` at `apps.rating.selectors.charge_by_code`;
    `first_bill`'s connection charge and `decisions`' late fee read it too.
    `penalty` alone went on raising because it named the seam as a module
    constant, **and this test kept the suite green over it** — which is why the
    assertion had to be replaced rather than relaxed.

    **WHAT IS UNCHANGED, and it is the part WE-11's $500.00 was always about:
    nothing here types an amount.** WE-11 and the Billing blueprint both draw
    **$500.00**; B14 rule 37 makes a figure drawn in a wireframe an
    ILLUSTRATION and never a fact to build to, and BR-BIL-019 forbids a
    hand-typed amount outright. So the test SEEDS this tenant's own charge-code
    row at **$250.0000** — the figure the demo tenant actually carries, and the
    prototype's own charge-code card — and asserts the line comes back with it.
    Change the row and the line changes; there is no literal to keep in step.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-9002", read_days=[e for _s, e in ASSESSED_MONTHS]
        )
        account = an_account(brazos, unit["id"], "A-14002")
        # ⚠ `update_or_create`: provisioning ALREADY seeds `TAMPER` at this
        # figure (PO ruling 2026-08-10, a platform default), so a plain create
        # collides on `charges.tenant_id, charges.code` — a FIXTURE failing,
        # which must never be mistaken for the product refusing. The amount is
        # restated here rather than read so the case is legible on its own; the
        # platform seed itself is asserted in
        # `tests/test_def_bil_5326_5317_sub_period_bill_path.py`. Only the GL
        # account is genuinely being ensured — BR-BIL-010 requires one and
        # pointing seeded codes at accounts is `CR-066`'s job.
        rating_models.Charge.objects.update_or_create(
            tenant=brazos,
            code="TAMPER",
            defaults={
                "name": "Tamper fee",
                "charge_type": "penalty",
                "amount_rule": "flat",
                "amount": TENANT_TAMPER_AMOUNT,
                # `DEF-BIL-9073` — a REAL ledger account of this tenant. The
                # literal id this read until then exists in no database here;
                # PostgreSQL refuses it at COMMIT and SQLite never checks.
                "gl_account_id": ledger_models.LedgerAccount.objects.filter(tenant=brazos)
                .order_by("code")
                .values_list("id", flat=True)
                .first(),
            },
        )

        prepared = penalty.prepare_penalty_bill(
            account_id=account.id,
            sub_periods=ASSESSED_MONTHS,
            reason_code=THEFT_REASON,
            charge_codes=("TAMPER",),
        )
        # Resolved in phase 1, which writes nothing — so a code this tenant does
        # not have is refused before an invoice number is spent.
        assert [line.amount for line in prepared.charge_lines] == [TENANT_TAMPER_AMOUNT]
        invoice = penalty.calculate_penalty_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, code="TH-B"), key="penalty-2")
        )

        fees = [
            line
            for line in billing_models.InvoiceLine.objects.filter(invoice=invoice)
            if line.kind == "fee"
        ]

    # The line reached the DOCUMENT, which is the half the old loop never did:
    # it called the builder purely for the exception and priced the back-bill
    # without it, so lifting the refusal alone would have changed nothing.
    assert [line.amount for line in fees] == [TENANT_TAMPER_AMOUNT]
    # ⚠ AND THE FROZEN FIGURE IS NOT WRITTEN ANYWHERE. WE-11's 500.00 is B5's
    # and stays B5's; binding it to a fixture here would make a ❄️ FROZEN number
    # true of this test rather than of the product.
    assert all("500" not in str(line.amount) for line in fees)


def test_us_bil_014_tc3__the_approval_mode_is_read_and_nothing_yet_enforces_it(brazos, dana):
    """TC-3: Admin approval before any money-bearing write — the honest half.

    What IS true: preparing writes nothing, so an impact preview costs nothing
    and commits nothing. What is NOT true, and is asserted as the gap it is:
    BR-BIL-014's gate (US-BIL-017) exists nowhere in this codebase, so the
    approval MODE is read and recorded and NOTHING stops an unapproved penalty
    bill being issued. Writing this test as though the gate worked is precisely
    the "comment claiming a guarantee" hard-won law 1 was written for.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        # DEF-BIL-8326 (2026-10-01): the assessed months are READ, as in tc1.
        # Never read, the meter has no multiplier since R3 + R4 (e998f92b1,
        # BR-MET-056) and prepare refused before the approval mode was read.
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-9003", read_days=[e for _s, e in ASSESSED_MONTHS]
        )
        account = an_account(brazos, unit["id"], "A-14003")

        prepared = penalty.prepare_penalty_bill(
            account_id=account.id, sub_periods=ASSESSED_MONTHS, reason_code=THEFT_REASON
        )

        assert prepared.back_bill.approval_mode == "all"  # BR-BIL-014 v1, OQ-072
        assert billing_models.Invoice.objects.count() == 0
        assert billing_models.InvoiceLine.objects.count() == 0
        # The gate itself: absent. Stated as an assertion so the day US-BIL-017
        # lands, this test fails and someone wires it here on purpose.
        from apps.billing import issue as issue_module

        assert not any("approv" in name.lower() for name in dir(issue_module))


def test_us_bil_014_tc4__a_fourteen_month_theft_window_is_allowed(brazos, dana):
    """TC-4: theft is EXEMPT from the back-bill cap (BR-BIL-018 / OQ-071).

    The same 14-month span that US-BIL-013 TC-4 refuses. The exemption is the
    whole reason a theft case can reach back further than a catch-up: the
    customer's consumption was never measured because they prevented it.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        # DEF-BIL-8326 (2026-10-01): both months READ — see tc3. The subject
        # here is the cap exemption, which a never-read meter never reached.
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-9004", read_days=[e for _s, e in FOURTEEN_MONTHS]
        )
        account = an_account(brazos, unit["id"], "A-14004")

        assert backbill.months_spanned(date(2025, 1, 1), date(2026, 2, 28)) == 14
        prepared = penalty.prepare_penalty_bill(
            account_id=account.id, sub_periods=FOURTEEN_MONTHS, reason_code=THEFT_REASON
        )

        # The SAME window without the theft flag is refused — the exemption is
        # what allows it, not a looser rule for penalty bills.
        with pytest.raises(Exception) as raised:
            backbill.prepare_back_bill(
                account_id=account.id, sub_periods=FOURTEEN_MONTHS, reason_code="catch-up"
            )

    assert prepared.back_bill.theft is True
    assert prepared.back_bill.cap_months == 12
    assert raised.value.reason == backbill.BACKBILL_OVER_CAP


def test_us_bil_014_tc5__no_penalty_entry_point_accepts_a_typed_amount():
    """TC-5 (negative): "a typed $500 penalty line" has nowhere to go.

    Structural, exactly as US-BIL-012 TC-4: the only way to add a penalty is a
    CHARGE CODE (a string), and the only way to add usage is a committed READ.
    Neither carries money from the caller.
    """
    import inspect

    signature = inspect.signature(penalty.prepare_penalty_bill)
    assert set(signature.parameters) == {
        "account_id",
        "sub_periods",
        "reason_code",
        "charge_codes",
        "scope_services",
        # DEF-BIL-8324 (2026-09-30) — the REGISTER readings a clerk typed on
        # step 2, preview only. A reading is a meter value metering turns into
        # usage by its own arithmetic; it carries no money, so TC-5 still holds.
        "keyed_reads",
        # The preview's flag: a stretch nothing can price WAITS for step 2's
        # reading instead of refusing. A boolean; no money.
        "waiting_ok",
    }
    assert signature.parameters["keyed_reads"].default is None
    assert signature.parameters["waiting_ok"].default is False
    assert signature.parameters["charge_codes"].default == ()
    # ⚠ **THESE THREE LINES ASSERTED A REFUSAL UNTIL 2026-09-15
    # (`DEF-BIL-5317`)** — `penalty.penalty_charge_line("TAMPER")` raising
    # `PENALTY_NO_CHARGE_CODE_READER` — which read as a structural guard and was
    # really the defect holding itself in place. TC-5's actual subject is that
    # a penalty AMOUNT has nowhere to enter from a caller, and that is still
    # true and now stated directly: the only argument is a CODE, a string, and
    # the figure comes from the tenant's own row (BR-BIL-007).
    signature_of_line = inspect.signature(penalty.penalty_charge_line)
    assert list(signature_of_line.parameters) == ["code"]
    # ⚠ THE ANNOTATION IS A STRING, NOT THE TYPE: `penalty.py` opens with
    # `from __future__ import annotations`, so `inspect` hands back `"str"`
    # rather than `str`. Comparing against the type passes review and fails at
    # runtime, which is a check that cannot pass (hard-won law 7) — it was
    # written that way here first and caught by running it.
    assert signature_of_line.parameters["code"].annotation == "str"
    # And the one builder it delegates to is the one every other charge-code
    # line in this app already comes from, so there is no second door.
    assert "fee_bill.charge_code_line(code)" in inspect.getsource(penalty.penalty_charge_line)


def test_us_bil_014_tc6__the_unverifiable_assessed_flag_is_stamped_on_the_bill(brazos, dana):
    """TC-6: metering publishes no ASSESSED flag — so the bill SAYS it could not check.

    r10 #14 / BR-MET-053 give an assessed read a flag and a reason code;
    metering's reads carry `estimated`, which is a VEE substitute and not a
    tamper restatement. Treating one as the other would let an ordinary
    estimated month be billed as theft — a claim about a customer this code has
    no basis to make. So the absence rides the payload BR-BIL-030 locks at
    issue, where a dispute or a reprint in 2033 can still read it.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-9005", read_days=[e for _s, e in ASSESSED_MONTHS]
        )
        account = an_account(brazos, unit["id"], "A-14006")

        prepared = penalty.prepare_penalty_bill(
            account_id=account.id, sub_periods=ASSESSED_MONTHS, reason_code=THEFT_REASON
        )
        invoice = penalty.calculate_penalty_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, code="TH-C"), key="penalty-6")
        )

    assert prepared.assessed_unverifiable is not None
    stamped = invoice.bill_payload["penalty"]
    assert "no ASSESSED flag" in stamped["assessed_flag_unverifiable"]
    assert stamped["theft_case"] is True
    assert stamped["cap_exempt"] is True
    assert stamped["reason_code"] == THEFT_REASON


def test_us_bil_014_tc7__a_theft_case_never_crosses_a_tenant_boundary(brazos, dana, lonestar):
    """TC-7 (isolation): another tenant's account and charge codes are invisible."""
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-9006")
        account = an_account(brazos, unit["id"], "A-14007")

    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as raised:
            penalty.prepare_penalty_bill(
                account_id=account.id, sub_periods=ASSESSED_MONTHS, reason_code=THEFT_REASON
            )
    assert raised.value.__class__.__name__ == "NotFoundError"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-014@f0a3c21 (EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md · B2 §2 + Addendum r10)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane)
# gates: ruff✔ black✔ · 7 passed
# RED PROOF EXECUTED 2026-08-11 (verbatim, not predicted). THE MUTATION:
#         `penalty.calculate_penalty_bill`'s charge-code loop was deleted, so a
#         requested TAMPER line would be silently dropped and the bill would
#         draft with its restated usage and NO penalty — the failure the
#         docstring names as the worst available. Result:
#         `1 failed, 6 passed in 20.47s` — FAILED tc2
#         `Failed: DID NOT RAISE <class 'Exception'>`. Reverted; 7 passed.
# exceptions: WE-11's own figures (115.50 / 10.92 / 500.00 / 626.42) are cited
#         in the Golden header and asserted NOWHERE as passing values — the
#         engine has no TOU model and rating publishes no charge-code read.
#         Binding them to a hand-built flat tariff would prove a fixture, not a
#         product. Stated here so a later reader does not mistake their absence
#         for an oversight.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

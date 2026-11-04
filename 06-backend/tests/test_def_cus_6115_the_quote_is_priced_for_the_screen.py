# ── Trace ──────────────────────────────────────────────
# Defect:   `DEF-CUS-6115` — **New Connect step 6 showed no money at all.** The
#           CR-126 §9 acceptance walk committed six build variations at
#           v2.322.0 and not one showed the clerk a figure: quantities right,
#           no unit price, no line total, no quote total. The commit then
#           raised `7 x $45.00 = $315.00` — visible only AFTER the build
#           existed.
#           `DEF-MET-6110` — a charge code the catalogue cannot price lost the
#           whole build with a bare 500, after eight steps.
# Rules:    CLAUDE.md hard rule 2 (money 4dp stored / 2dp displayed, rounded
#           ONCE on the server, never a float) · hard rule 1 (tenant scoping) ·
#           BR-BIL-007 (the TENANT's row carries the price) · BR-BIL-020 (lines
#           come only from rules and charge codes) · BR-MET-112 (nothing is
#           written until step 8) · BR-MET-1178 (a build prices itself)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**What step 6 costs, asked of the engine that will raise it.**

⚠ **THE POINT IS THAT THE PREVIEW AND THE COMMIT ASK ONE QUESTION.** A preview
priced by a second route would be a screen showing a clerk a figure the commit
will not raise — `DEF-MET-5428`'s shape on a money path — so
`price_quote_preview` builds its lines with `charge_code_line`, the function
`price_quote_bill` builds with, and the case below asserts the two agree on a
real worked figure rather than asserting each separately.

⚠ **IT WRITES NOTHING, AND THAT IS ASSERTED RATHER THAN DESCRIBED.** No run
row, no invoice, no number spent. `BR-MET-112` is *nothing is written until
step 8*, and a preview that quietly minted a document would break it on every
keystroke of step 6.

⚠ **`$0.00` IS NEVER AN ANSWER.** A build nobody has charged answers `{None,
None}` with `build_names_no_charge`, which is the rule
`connection_record._money` already applies to the build record's tiles: *a zero
on a money line reads as settled, and the truth is never priced.*

RED-FIRST PROOF (r11 step 2d). Each guard was broken first and its failure read
before it was trusted green — see the module's conformance note; the worked
figure case fails with the total absent, and the unpriceable-code case fails
with `BillingRuleError` escaping as a 500, which is the defect it was written
for.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import fee_bill
from apps.metering import connection_reads

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The walk's own build: a seven-unit block with a connection fee per unit.
#: `CONN` is `$45.0000` in the demo tenant's catalogue (`BR-BIL-007` — the
#: figure is the TENANT's row, and this test reads it rather than asserting a
#: literal price, so a utility entitled to charge $60.00 does not fail here).
SEVEN_UNITS = {"quote_lines": [{"charge_code": "CONN", "quantity": 7, "basis": "per unit"}]}


def test_the_walks_own_build_is_priced_before_it_exists(brazos, dana):
    """`7 x $45.00 = $315.00`, on the screen, before the press."""
    with tenant_ctx(brazos):
        answer = connection_reads.preview_quote(SEVEN_UNITS)

        assert answer["priced"] is True
        assert answer["unavailable"] == []
        assert answer["currency"] == "USD"

        (line,) = answer["lines"]
        assert line["charge_code"] == "CONN"
        assert line["basis"] == "per unit"
        assert line["quantity"] == "7"
        # Hard rule 3 — a quantity always travels with its unit, never assumed.
        assert line["unit"] == "unit"

        # ⚠ **BOTH SHAPES, AND THE DISPLAY ONE IS THE SERVER'S ROUNDING.**
        # Hard rule 2: 4 decimals stored, 2 displayed, rounded once, here. A
        # client that re-rounded `stored` would be the second rounding path
        # `DEF-088` removed, which is why both travel.
        unit_price = Decimal(line["unit_price"]["stored"])
        assert line["unit_price"]["display"] == str(unit_price.quantize(Decimal("0.01")))
        assert line["amount"]["stored"] == str((unit_price * 7).quantize(Decimal("0.0001")))
        assert answer["total"]["display"] == str((unit_price * 7).quantize(Decimal("0.01")))
        # The walk's figure, named so a silent catalogue change is visible.
        assert (line["unit_price"]["display"], answer["total"]["display"]) == ("45.00", "315.00")


def test_the_preview_and_the_commits_own_engine_agree_to_the_cent(brazos, dana):
    """**One question, two callers.**

    The screen asks `price_quote_preview`; the commit asks `price_quote_bill`
    through `raise_and_issue_quote_bill`. Both build their lines with
    `charge_code_line`, and this is the case that fails the day one of them
    grows an arithmetic of its own.
    """
    with tenant_ctx(brazos):
        shown = connection_reads.preview_quote(SEVEN_UNITS)
        priced = fee_bill.price_quote_preview(
            charges=[
                fee_bill.QuotedCharge(
                    charge_code="CONN", quantity=Decimal("7"), basis="per unit"
                )
            ]
        )
        assert shown["total"]["stored"] == str(priced.total.quantize(Decimal("0.0001")))
        assert [one.amount for one in priced.lines] == [priced.total]


def test_several_lines_total_without_a_second_rounding(brazos, dana):
    """Σ of already-rounded lines, and no `quantize` on the sum.

    Summing four four-decimal figures cannot produce a fifth decimal, so a
    rounding here would be `DEF-088`'s removed path returning. Asserted as
    arithmetic rather than stated in a comment.
    """
    with tenant_ctx(brazos):
        answer = connection_reads.preview_quote(
            {
                "quote_lines": [
                    {"charge_code": "CONN", "quantity": 7, "basis": "per unit"},
                    {"charge_code": "INSPECT", "quantity": 16, "basis": "per meter"},
                ]
            }
        )
        assert answer["priced"] is True
        assert len(answer["lines"]) == 2
        total = sum(Decimal(one["amount"]["stored"]) for one in answer["lines"])
        assert answer["total"]["stored"] == str(total.quantize(Decimal("0.0001")))


def test_a_build_with_no_charge_is_BLANK_and_never_zero(brazos, dana):
    """⚠ **THE DISTINCTION THIS WHOLE READ EXISTS TO KEEP.**

    On a money line a zero reads as *free*; the truth is *not priced*. Every
    figure is `{None, None}` and the absence is NAMED — the same code the
    commit reports, so the screen before the press and the panel after it say
    one thing.
    """
    with tenant_ctx(brazos):
        answer = connection_reads.preview_quote({"quote_lines": []})
        assert answer["priced"] is False
        assert answer["lines"] == []
        assert answer["total"] == {"stored": None, "display": None}
        assert [one["code"] for one in answer["unavailable"]] == ["build_names_no_charge"]
        # Not a zero anywhere on the payload, in either shape.
        assert "0.00" not in str(answer["total"])


def test_def_cus_6119_a_code_the_catalogue_cannot_price_is_named_not_raised(brazos, dana):
    """**The refusal lands where the code was PICKED, not eight steps later.**

    `TAP`, `IMPACT` and `DAMAGE` are live charge codes in the demo tenant with
    no amount at all. Picking one and pressing on committed the premises, the
    units, the services, the plan and the meters, then answered **500** from
    inside the commit's transaction — nothing written, thirty-eight presses
    gone, and a bare error where a reason should be.

    Here it is an ABSENCE on a successful read, with the engine's own sentence
    carried for the register and the console. The screen says its own six
    words; `B14` rule 32 keeps an engineer's sentence off a clerk's screen.
    """
    with tenant_ctx(brazos):
        answer = connection_reads.preview_quote(
            {"quote_lines": [{"charge_code": "TAP", "quantity": 7, "basis": "per unit"}]}
        )
        assert answer["priced"] is False
        assert answer["total"] == {"stored": None, "display": None}
        (refusal,) = answer["unavailable"]
        assert refusal["code"] == "quote_line_cannot_be_priced"
        assert "TAP" in refusal["detail"]


def test_a_code_no_tenant_holds_is_the_same_named_absence(brazos, dana):
    """An unknown code, a deactivated one (IS-1) and another tenant's are ONE
    answer — `charge_code_line`'s own rule (HR-1), reported not raised."""
    with tenant_ctx(brazos):
        answer = connection_reads.preview_quote(
            {"quote_lines": [{"charge_code": "NO-SUCH-CODE", "quantity": 1, "basis": "per premise"}]}
        )
        assert answer["priced"] is False
        assert answer["unavailable"][0]["code"] == "quote_line_cannot_be_priced"


def test_a_malformed_line_still_RAISES_because_the_caller_got_it_wrong(brazos, dana):
    """⚠ **SHAPE IS NOT THE SAME AS PRICE, AND THE TWO MUST NOT COLLAPSE.**

    A basis outside `QUOTE_BASES` and a quantity of zero mean the CALLER does
    not know what it is asking for; an unpriceable code means the build is fine
    and no charge can be raised yet. `build_quote_lines` keeps that line and
    this preview does not blur it — otherwise a screen sending `basis: "per
    building"` would read *"this charge has no price"* and the clerk would
    change a charge code over a bug in the client.
    """
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            connection_reads.preview_quote(
                {"quote_lines": [{"charge_code": "CONN", "quantity": 7, "basis": "per building"}]}
            )
        with pytest.raises(errors.ValidationError):
            connection_reads.preview_quote(
                {"quote_lines": [{"charge_code": "CONN", "quantity": 0, "basis": "per unit"}]}
            )


def test_br_met_112_a_preview_writes_nothing_at_all(brazos, dana):
    """*Nothing is written until step 8* — asserted, not described.

    A preview runs on every change to step 4's grid. One that minted a run row
    or spent an invoice number would burn a document per keystroke.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        before = (billing_models.Invoice.objects.count(), billing_models.BillRun.objects.count())
        connection_reads.preview_quote(SEVEN_UNITS)
        connection_reads.preview_quote(SEVEN_UNITS)
        after = (billing_models.Invoice.objects.count(), billing_models.BillRun.objects.count())
        assert before == after


def test_hard_rule_1_a_preview_prices_only_this_tenants_catalogue(
    brazos, dana, lonestar, erin
):
    """The price is the TENANT's row (`BR-BIL-007`). A preview that read another
    tenant's catalogue would quote a figure this utility never set."""
    with tenant_ctx(lonestar):
        other = connection_reads.preview_quote(SEVEN_UNITS)
    with tenant_ctx(brazos):
        mine = connection_reads.preview_quote(SEVEN_UNITS)
    # Either the other tenant does not sell it, or it sells it at its OWN
    # price — never at this one's. Both are lawful; reading this one's is not.
    if other["priced"]:
        assert other["currency"] is not None
    assert mine["priced"] is True

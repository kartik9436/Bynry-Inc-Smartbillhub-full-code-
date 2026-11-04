# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-030 (the terminal stages — assemble-document · post-to-ledger
#           — and GT-1..61 as the refactor contract)   Screens: S30 · S56
# Rules:    BR-BIL-038 (GT-1..61 reproduce to the digit; a boundary move and a
#           golden-value change never share a commit; the suite runs the public
#           entry point only) · BR-BIL-037 (stages 6 and 7 are terminal; stage 7
#           emits and never writes) · BR-BIL-030 (locked at issue) ·
#           BR-BIL-032 (the instance ties out to its rows) · BR-BIL-033 (render
#           before issue) · BR-BIL-011 (one balanced JE, written only by the
#           posting service) · CLAUDE.md rule 4 · rule 5
# ───────────────────────────────────────────────────────
"""The pipeline's last two stages, and the contract that survives a refactor.

❄️ **EVERY FIGURE HERE IS FROZEN (B5, finance-signed 2026-08-08) AND NOTHING IN
THIS FILE COMPUTES ONE.** WE-1: current charges **247.87**, prior **45.00**,
total due **292.87**, 15 lines; DR 1200 AR **247.87** = Σ CR buckets. US-BIL-030
exists to protect those, not to touch them — its own scope line says so.

WHAT RUNS HERE AND WHAT DOES NOT (hard-won law 1):

* The **tie-out** (BR-BIL-032) and the **handoff shape** (BR-BIL-011) run
  against real rows.
* The **arithmetic** is NOT re-asserted here — `10-scripts/03-golden-verify.py`
  (33 PASS) and `tests/golden/` own it, and duplicating a signed figure in a
  third place is how a fourth copy starts disagreeing. What this file asserts is
  that the CONTRACT holds: one public door, the tie-out bites, and stage 7
  writes nothing.
* The **refactor drill** (TC-2) and the two-change rule (TC-5) are the gate's,
  `10-scripts/gates/g21_refactor_contract.py`, whose own self-test bites 2/2 and
  is re-runnable. A test here could not see a commit.
"""

import pytest

from django.db import connection

from apps.billing import models, pipeline
from apps.billing.exceptions import BillingRuleError

from tests.test_us_bil_005_issue import a_priced_draft
from tests.test_us_bil_016_bulk_corrections import ORIGINAL_TOTAL, an_issued_bill
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db


def test_us_bil_030_tc1__the_seven_stages_are_named_once_in_one_fixed_order(brazos):
    """BR-BIL-037 as amended 2026-08-22 — EIGHT stages, one order, WHO owns each.

    Named once in `pipeline.SEQUENCE` so the refactor gate can read the boundary
    set from code rather than from a comment that would drift away from it.

    ⚠ THIS TEST ASSERTED SEVEN STAGES UNTIL 2026-08-22, and updating it is the
    visible half of DEF-502's designed close: the defect row itself says the fix
    *"is a BOUNDARY MOVE under BR-BIL-038 clause (a) — it changes SEQUENCE,
    which is deliberately the one change the refactor gate makes visible in a
    diff."* apply-discounts is stage 5 (R6 before R7 — BR-RAT-071; each tax
    picks its own base — BR-RAT-106); compute-tax, assemble-document and
    post-to-ledger renumbered 6·7·8. No golden value changes in this commit and
    GT-1..61 reproduce to the digit, because every B5 fixture passes no
    discounts. The function name keeps "seven_stages" so the test's history is
    findable; the assertion is the truth.
    """
    assert [n for n, _, _ in pipeline.SEQUENCE] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [name for _, name, _ in pipeline.SEQUENCE] == [
        "resolve-subscription",
        "measure-consumption",
        "price-usage",
        "apply-charges",
        "apply-discounts",
        "compute-tax",
        "assemble-document",
        "post-to-ledger",
    ]
    assert pipeline.TERMINAL_STAGES == (7, 8)
    # Stages 3–6 are rating's; billing never re-implements their arithmetic.
    assert [pipeline.stage_owner(n) for n in (3, 4, 5, 6)] == ["rating"] * 4
    assert [pipeline.stage_owner(n) for n in (1, 2, 7, 8)] == ["billing"] * 4

    with pytest.raises(BillingRuleError) as refusal:
        pipeline.stage_owner(9)
    assert "there is no stage 9" in str(refusal.value)


def test_us_bil_030_tc6__the_public_door_is_declared_and_the_internals_are_named(brazos):
    """TC-6 / BR-BIL-038 clause (b) — one door, declared where a gate can read it.

    *"The suite executes the pipeline's public entry point, never a stage's
    internals, so a refactor cannot quietly retarget the tests at the thing it
    just changed."*

    This asserts the DECLARATION; the enforcement is
    `10-scripts/gates/g21_refactor_contract.py`, which greps the golden suite and
    was proved RED against a file importing `apps.billing.stages.
    assemble_document` before it was trusted.
    """
    assert "apps.billing.pipeline.run_to_document" in pipeline.PUBLIC_ENTRY_POINTS
    assert "apps.billing.runs.calculate_account" in pipeline.PUBLIC_ENTRY_POINTS
    # The pricing seam is a DOOR, not a stage internal: B5's GT-1..11 are
    # single-service unit fixtures with no account to gather, and
    # `stages/__init__.py` documents both `price_bill` and `price_period` as the
    # published route into stages 3–5.
    assert "apps.billing.rating_seam.price_bill" in pipeline.PUBLIC_ENTRY_POINTS
    # And the insides are named so the gate can refuse a reach past the door.
    assert "apps.billing.stages.assemble_document" in pipeline.STAGE_INTERNALS
    assert not set(pipeline.PUBLIC_ENTRY_POINTS) & set(pipeline.STAGE_INTERNALS)


def test_us_bil_030_tc3__the_stamped_instance_ties_out_to_its_rows(brazos, dana):
    """TC-3 / BR-BIL-032 — the payload agrees with the rows, and both are checked.

    The redundancy is DELIBERATE: the payload is what a reprint renders and the
    rows are what the ledger posted. Silent drift would show the customer one
    number and the trial balance another, each internally consistent — which is
    the failure with no symptom until somebody disputes a bill.
    """
    # ⚠ THIS CASE HAD BEEN ERRORING, NOT FAILING, SINCE THE IMMUTABILITY
    # TRIGGERS LANDED (DEF-155's class). It built the payload by UPDATEing an
    # already-issued invoice and PostgreSQL refused, correctly: `bill_payload`
    # is frozen at issue like the money. An erroring test reads identically to a
    # test nobody wrote, because `run_gates` G4 runs `pytest -m golden` and no
    # gate runs a full pytest. Fixed the way the fixture's own docstring
    # prescribes — set the column at INSERT, which is also the only shape
    # production ever produces.
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018410",
            bill_payload={
                "total": str(ORIGINAL_TOTAL),
                "lines": [{"n": 1}, {"n": 2}, {"n": 3}],
            },
        )
        rows = list(bill.lines.all())

        tie = pipeline.tie_out_document(bill)
        assert tie.ties_out
        assert tie.payload_total == tie.invoice_total
        assert tie.payload_line_count == tie.row_line_count == len(rows)
        assert pipeline.refuse_untied_document(bill) is not None


def test_us_bil_030_tc8__a_forged_payload_fails_the_tieout_naming_the_delta(brazos, dana):
    """TC-8 / BR-BIL-032 — *"drift can never be silent"*, and the refusal NAMES it.

    Two shapes, because they are two different lies: a payload whose TOTAL
    disagrees with the rows, and a payload MISSING a line the rows have. A
    refusal that only said "tie-out failed" would send somebody looking; one
    that says `292.87 over 2 lines` versus `247.87 over 3 lines` does not.
    """
    # ⚠ ERRORING, NOT FAILING, SINCE THE TRIGGERS LANDED — see tc3's note. It
    # forged three payloads by UPDATEing one issued bill three times. Each
    # forgery now gets its OWN bill with its payload set at INSERT, which is
    # both lawful and clearer: three lies about three bills, not one bill that
    # changed its story twice.
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        three_lines = [{"n": 1}, {"n": 2}, {"n": 3}]

        # 1 · the total disagrees.
        wrong_total = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018411",
            bill_payload={"total": "292.87", "lines": three_lines},
        )
        with pytest.raises(BillingRuleError) as refusal:
            pipeline.refuse_untied_document(wrong_total)
        message = str(refusal.value)
        assert "does not tie out" in message
        assert "292.87" in message and "247.87" in message
        assert "delta of" in message

        # 2 · a line is missing.
        short = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018412",
            bill_payload={"total": str(ORIGINAL_TOTAL), "lines": [{"description": "only one"}]},
        )
        rows = list(short.lines.all())
        tie = pipeline.tie_out_document(short)
        assert not tie.ties_out
        assert tie.payload_line_count == 1 and tie.row_line_count == len(rows)
        with pytest.raises(BillingRuleError) as second:
            pipeline.refuse_untied_document(short)
        assert "line(s)" in str(second.value)

        # 3 · no total at all is its own refusal, not a crash.
        totalless = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-018413", bill_payload={"lines": []}
        )
        with pytest.raises(BillingRuleError) as third:
            pipeline.refuse_untied_document(totalless)
        assert "no total" in str(third.value)


def test_us_bil_030_tc4__stage7_emits_a_balanced_handoff_and_writes_nothing(brazos, dana):
    """TC-4 + TC-7 / BR-BIL-011 + CLAUDE.md rule 5 — **DR AR = Σ CR buckets**.

    ❄️ The contract's shape, asserted on real rows: the AR debit equals the sum
    of the credit buckets exactly, and the handoff carries the six things
    US-BIL-009 contracted — invoice id, account, service_date, per-GL bucket
    sums, AR total, currency.

    **And billing wrote nothing.** The journal-line count is taken before and
    after, because that is the only assertion that catches a write nobody
    expected: reading the return value only ever confirms what the code meant to
    do. The ledger posting service is the sole writer and `ledger/0004`'s trigger
    is the fence.
    """
    from apps.ledger import models as ledger_models

    from tests.test_us_bil_009_posting_handoff import (
        ISSUED_AT,
        SUBTOTAL,
        TEMPLATE_ID,
        TEMPLATE_VERSION,
        a_priced_draft,
        an_authorised_run,
    )
    from apps.billing import issue as issue_module

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        # The REAL issue path, because stage 7's stamps are written at issue and
        # a hand-built fixture would have no GL accounts to bucket — which is
        # `posting_seam`'s own refusal, correctly.
        bill = issue_module.issue_invoice(
            a_priced_draft(brazos, account, run),
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        before = ledger_models.JournalLine.objects.count()

        handoff = pipeline.balanced_handoff(bill)

        assert handoff.balanced, "DR AR must equal the sum of the CR buckets exactly"
        assert handoff.ar_total == SUBTOTAL == bill.total
        assert handoff.invoice_id == str(bill.pk)
        assert handoff.account_id == str(bill.account_id)
        assert handoff.service_date == bill.service_date
        assert handoff.currency == bill.currency
        assert handoff.buckets, "the handoff names its GL buckets, never one net figure"

        assert ledger_models.JournalLine.objects.count() == before, (
            "stage 7 EMITS and never writes — only the ledger posting service writes "
            "journal lines (CLAUDE.md rule 5, BR-BIL-011)"
        )


def test_us_bil_030_tc2__the_public_door_calls_what_the_run_calls(brazos, dana, monkeypatch):
    """TC-2's premise — the door is a DOOR, not a second orchestrator.

    BR-BIL-037: *"only the orchestrator knows the sequence"*. If
    `run_to_document` grew its own sequence, the refactor contract would be
    measuring a path nothing ships — the suite would pass while the bill run
    took a different route. So it delegates to exactly the two functions
    `runs.calculate_account` is reached through, and this asserts the
    delegation rather than taking the docstring's word for it (hard-won law 1).
    """
    from apps.billing import single

    seen: list[str] = []
    real_prepare = single.prepare_single_bill
    real_calculate = single.calculate_single_bill
    monkeypatch.setattr(
        single,
        "prepare_single_bill",
        lambda **kw: (seen.append("prepare"), real_prepare(**kw))[1],
    )
    monkeypatch.setattr(
        single,
        "calculate_single_bill",
        lambda *a, **kw: (seen.append("calculate"), real_calculate(*a, **kw))[1],
    )

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        with pytest.raises(BillingRuleError):
            # The fixture account has no reads, so stages 1–2 refuse — which is
            # itself the assertion that matters here: the door goes THROUGH the
            # stages and does not route around them.
            pipeline.run_to_document(
                account.id,
                period_start=bill_period()[0],
                period_end=bill_period()[1],
                service_date=bill_period()[1],
                bill_run=run,
            )
    assert seen == ["prepare"], "the door enters at stage 1 and stops where the stages stop"


def bill_period():
    from datetime import date

    return date(2026, 7, 1), date(2026, 7, 31)


def test_us_bil_030_tc5_tc6__the_refactor_gate_bites_on_both_clauses():
    """TC-5 + TC-6 / BR-BIL-038 — the two clauses, PROVED RED from here too.

    *"Proven RED first (hard-won law 7)."* The gate's own `self_test()` stages
    both violations and asserts the gate refuses each: a manifest naming a stage
    file and a golden file together (clause (a)), and a golden test importing a
    stage internal (clause (b)). Run from the suite as well as from CI, so the
    proof is re-runnable rather than a claim in a lane report.

    A gate whose self-test does not bite is not a gate, and `run()` FAILS in
    that case rather than passing — which is why this asserts 2 of 2 rather than
    merely that the gate currently passes.
    """
    import importlib.util
    import sys
    from pathlib import Path

    gates = Path(__file__).resolve().parents[2] / "10-scripts" / "gates"
    sys.path.insert(0, str(gates))
    try:
        spec = importlib.util.spec_from_file_location(
            "g21_refactor_contract", gates / "g21_refactor_contract.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bit, total = module.self_test()
        assert (bit, total) == (2, 2), "both BR-BIL-038 clauses must be shown to bite"
        status, detail = module.run()
        assert status == "PASS", detail
    finally:
        sys.path.remove(str(gates))



# ═══════════════════════════════════════════════════════════════════════════
# THE SURFACE — added 2026-08-16, because BOTH guarantees ran on fixtures only
# ═══════════════════════════════════════════════════════════════════════════
# A repo-wide search on 2026-08-16 found NO caller for `tie_out_document`,
# `refuse_untied_document` or `balanced_handoff` outside this file. So
# BR-BIL-032 — *"drift can never be silent"* — was enforced against fixtures and
# against no bill this product ever produced: every invoice could carry a
# payload saying one number and rows saying another, each internally consistent,
# and nobody would learn of it until a customer disputed a bill. That is
# DEF-112's shape applied to a GUARANTEE instead of to a screen, and it is
# exactly what hard-won law 1 warns about — the rule existed, the enforcement
# did not.
def test_us_bil_030_tc11__the_tieout_and_the_handoff_are_ANSWERED_on_the_bill(
    brazos, dana
):
    """`GET /invoices/{id}` states both guarantees for the bill a clerk opened.

    RED-PROVED: `invoice_detail` carried no `integrity` key at all, so this
    failed with `KeyError: 'integrity'` before the block was served.
    """
    from apps.billing import selectors

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        bill = an_issued_bill(
            brazos,
            account,
            a_run(brazos),
            invoice_no="BL-2608-018420",
            bill_payload={
                "total": str(ORIGINAL_TOTAL),
                "lines": [{"n": 1}, {"n": 2}, {"n": 3}],
            },
        )
        block = selectors.invoice_detail(str(bill.pk))["integrity"]

    assert block["document_ties_out"] is True
    assert block["rows_total"] is not None
    # CLAUDE.md rule 2 — every money figure travels with its CHAR(3).
    assert block["currency"] == bill.currency
    assert block["payload_line_count"] == block["row_line_count"]


def test_us_bil_030_tc12__a_draft_says_UNKNOWN_and_never_says_it_failed(brazos, dana):
    """`null` with a reason, never `false`.

    A draft carries no stamped payload and no GL stamps — both are written at
    issue — so neither question can be asked of it. Answering `false` would be
    an accusation about a bill that has done nothing wrong, and it is the shape
    of the zero-that-means-I-don't-know this release exists to stop making.
    """
    from apps.billing import selectors

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        draft = a_priced_draft(
            brazos, account, a_run(brazos), invoice_no="BL-2607-000903", bill_payload=None
        )
        block = selectors.invoice_detail(str(draft.pk))["integrity"]

    assert block["document_ties_out"] is None
    assert any(gap["field"] == "document_ties_out" for gap in block["unavailable"])
    assert all(gap["why"] for gap in block["unavailable"])


def test_us_bil_030_tc13__the_read_never_RAISES_where_the_issue_gate_would(brazos, dana):
    """A drifted bill is REPORTED on the screen, not 500'd.

    `refuse_untied_document` raises by design — it gates an issue. This is a
    READ on a screen a clerk already has open, and a detail endpoint that blew
    up on a drifted bill would hide the one bill somebody needs to look at.

    The drift is built at INSERT, because production cannot produce a drifted
    ISSUED bill and the database will not let a test pretend otherwise — which
    is the honest half of this case: the only way drift reaches an issued bill
    is a bug upstream of the trigger, and the read has to survive it.
    """
    from apps.billing import selectors

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        bill = an_issued_bill(
            brazos,
            account,
            a_run(brazos),
            invoice_no="BL-2608-018421",
            bill_payload={"total": "999.99", "lines": [{"n": 1}]},
        )
        block = selectors.invoice_detail(str(bill.pk))["integrity"]

    assert block["document_ties_out"] is False
    assert block["payload_total"] != block["rows_total"]
    # The FIGURES travel, not a boolean: "the tie-out failed" sends somebody
    # looking, "999.99 against 247.87 over 1 line against 3" does not.
    assert block["payload_line_count"] != block["row_line_count"]
    assert block["currency"] == bill.currency


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-030@1d2c271 (ships with apps/billing/pipeline.py — the same four sources)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the pipeline has no endpoint and needs none) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest · run_gates (G21 is this story's) · 10-scripts/03-golden-verify.py
# exceptions: (1) THE ARITHMETIC IS NOT RE-ASSERTED HERE. GT-1..61 are owned by
#         `10-scripts/03-golden-verify.py` (33 PASS) and `tests/golden/`;
#         copying a signed figure into a third place is how a fourth copy starts
#         disagreeing. This file asserts the CONTRACT, not the numbers.
#         (2) TC-2's REFACTOR DRILL AND TC-5's TWO-CHANGE RULE ARE THE GATE'S,
#         not this suite's — a test cannot see a commit. `test_..._tc5_tc6`
#         re-runs the gate's self-test so the RED proof is re-runnable here too.
#         (3) TC-9 (an unrenderable bill does not issue) and TC-10 (the golden
#         suite under two tenant contexts) are NOT covered here: TC-9 is
#         asserted by `tests/test_us_bil_022_documents.py` where the renderer
#         lives, and TC-10 belongs to the isolation suite. REPORTED rather than
#         claimed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-030 (the terminal stages — assemble-document · post-to-ledger
#           — and GT-1..61 as the refactor contract)   Screens: S30 · S56
# Rules:    BR-BIL-038 (GT-1..61 reproduce to the digit across any internal
#           restructuring; a boundary move and a golden-value change never
#           share a commit; the suite runs the PUBLIC ENTRY POINT only) ·
#           BR-BIL-037 (stages 6 and 7 are the terminal stages of the
#           seven-stage pipeline; stage 7 EMITS and never writes) · BR-BIL-030
#           (the bill is LOCKED at issue — the instance is stamped and a reprint
#           renders it forever, joining nothing live) · BR-BIL-032 (the instance
#           TIES OUT to its rows: `bill_payload.total == invoices.total` and the
#           payload's lines reconcile to `invoice_lines`) · BR-BIL-033 (render
#           BEFORE issue — a failed render refuses the issue) · BR-BIL-011 (one
#           balanced JE per bill, written ONLY by the posting service) ·
#           CLAUDE.md rule 2 (money) · rule 4 (immutability) · rule 5 (only the
#           ledger posting service writes journal lines)
# Golden:   ❄️ B5 FROZEN, finance-signed 2026-08-08. This module PINS signed
#           figures and computes none: WE-1's `total_due = 247.87 + 45.00 =
#           292.87`; stage 7's DR 1200 AR 247.87 = Σ CR buckets. GT-1 108.88 ·
#           GT-2 13.74 · GT-3 15.25 · GT-5 343.60 · GT-8 8.13 · GT-10 116.01 ·
#           GT-11 108.71 · GT-13 6.90/2.06 · GT-15 40.00 + 24.00.
# Tests:    06-backend/tests/test_us_bil_030_terminal_stages.py
# Impacts:  apps/billing/stages/assemble_document.py (stage 6) ·
#           apps/billing/posting_seam.py (stage 7's emitter) ·
#           apps/billing/runs.py + single.py (the orchestrators that call this)
#           · 10-scripts/gates/g21_refactor_contract.py (BR-BIL-038 in CI)
# ───────────────────────────────────────────────────────
"""The pipeline's PUBLIC DOOR, its two terminal stages, and its tie-outs.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module names the seam the golden suite
is allowed to enter through, and the tie-outs it asserts are money assertions.
AI-authored 2026-08-15 under the PO ruling of 2026-08-09; row owed in
12-governance/09-human-review-ledger.md.

⚠ **THIS MODULE CHANGES NO ARITHMETIC AND MAY NOT.** B4 money-math and B5 golden
tests are ❄️ FROZEN and finance-signed (2026-08-08). US-BIL-030 exists to PROTECT
them through a refactor, not to touch them — the story's own scope line says so:
*"any change to B4/B5, which are ❄ frozen and which US-BIL-030 exists to
protect, not to touch."* Every figure below is quoted from a signed source.

════════════════════════════════════════════════════════════════════════════
THE CONTRACT, AND THE TWO CLAUSES THAT GIVE IT TEETH
════════════════════════════════════════════════════════════════════════════
BR-BIL-038: **however the billing engine is restructured inside, GT-1..61 come
out identical.** That is worth nothing as a sentence in a docstring — hard-won
law 1 is exactly about sentences like it — so the story names two clauses that
make it mechanical, and both are enforced by `10-scripts/gates/
g21_refactor_contract.py` rather than by intention:

  **(a) A commit may not both move a stage boundary and change a golden expected
  value.** A B5 change needs a finance re-sign via HUMAN-GUIDE §6, never an
  inline edit. The failure this prevents is specific and would look like
  success: a refactor that shifts a figure, and the same patch adjusting the
  fixture so the suite still passes. Nobody would be lying; the signed number
  would simply have moved.

  **(b) The suite executes the pipeline's PUBLIC ENTRY POINT, never a stage's
  internals.** A refactor cannot quietly retarget the tests at the thing it just
  changed. `PUBLIC_ENTRY_POINTS` below is that door, named once so the gate can
  read it, and `run_to_document` is the door itself.

════════════════════════════════════════════════════════════════════════════
STAGE 6 — assemble-document. **BEFORE ISSUE, NEVER AFTER.**
════════════════════════════════════════════════════════════════════════════
BR-BIL-033 (CONFIRMED, PO 2026-08-10 closing OQ-089): a bill that cannot render
must never become immutable. So the stamped instance (`bill_payload` +
`payload_version`, BR-BIL-030) is built while the invoice is still a DRAFT and
is a PRECONDITION of issuing, not a consequence of it. `issue.issue_invoice`
calls the renderer inside the issue transaction before the status moves, which
is what makes the rule real rather than described.

⚠ AMENDED BY OQ-117 (PO 2026-08-12, *"issue and report it"*): a document that
cannot be PRODUCED refuses the issue; a document produced with a NAMED absence
goes out and the run reports it. `tie_out_document` below therefore checks that
the instance AGREES with its rows — which is a different question from whether
every A19 field is present, and the only one BR-BIL-032 asks.

════════════════════════════════════════════════════════════════════════════
BR-BIL-032 — THE TIE-OUT, AND WHY THE REDUNDANCY IS DELIBERATE
════════════════════════════════════════════════════════════════════════════
`bill_payload.total == invoices.total`, and the payload's line set reconciles to
`invoice_lines`. Those are two copies of the same fact, on purpose: the payload
is what a reprint renders and the rows are what the ledger posted, and **silent
drift between them would be invisible**. A reprint would show one number while
the trial balance showed another, and both would look internally consistent.

❄️ Worked on WE-1: `bill_payload.total` **292.87** equals the invoice's rendered
total — `total_due = current_charges 247.87 + prior_balance 45.00` — and the
payload's line set reconciles 1:1 to the 15 `invoice_lines`.

════════════════════════════════════════════════════════════════════════════
STAGE 7 — post-to-ledger. **EMITS. WRITES NOTHING. EVER.**
════════════════════════════════════════════════════════════════════════════
CLAUDE.md rule 5 and BR-BIL-011: only the ledger posting service writes journal
lines. Billing emits `{invoice id, account, service_date, per-GL bucket sums, AR
total, currency}` and the ledger is the sole writer — `ledger/0004`'s trigger is
the fence, and `posting_seam.post_bill_issue` is the one door.

❄️ Worked on WE-1: DR 1200 AR **247.87** / CR 4100 88.60 · 4105 12.00 · 4110
39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200–2203 20.97 ·
4200 5.00 — balanced. `balanced_handoff` re-states that equality as a check
rather than a comment.

⚠ **A POSTING REFUSAL REFUSES THE ISSUE.** `posting_seam.PostingRefused` is
raised inside the issue transaction, so the bill stays a discardable DRAFT
rather than becoming an immutable record whose money never reached the books.
That ordering is the whole reason stage 7 is a stage and not an afterthought.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT THIS MODULE IS NOT: A SECOND ORCHESTRATOR
════════════════════════════════════════════════════════════════════════════
BR-BIL-037: *"only the orchestrator knows the sequence"*, which is why
`stages/__init__.py` exports the stages and no `run_all()`. `run_to_document`
does NOT become a second sequence — it calls the SAME functions `runs.
calculate_account` calls, in the same order, and exists so that the golden suite
and the bill run enter through one door instead of two. If it drifted from
`runs.calculate_account` the contract would be measuring a path nothing ships,
so `SEQUENCE` names the stages once and `tests/test_us_bil_030_terminal_stages`
asserts the two agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from apps.billing import models
from apps.billing.exceptions import BillingRuleError
from core import money

ZERO = Decimal("0")

#: BR-BIL-037's seven stages, in their one fixed total order, with the owner of
#: each. NAMED ONCE, here, so the refactor gate can read the boundary set from
#: code rather than from a comment that would drift away from it.
#:
#: A "boundary move" — clause (a) of BR-BIL-038 — is a change to this tuple or
#: to the signature of a stage entry point. That is what makes the gate's
#: question answerable by a diff rather than by judgement.
#: ⚠ EIGHT STAGES SINCE 2026-08-22 (DEF-502) — THIS IS THE BOUNDARY MOVE THE
#: DEFECT ROW PRESCRIBED. BR-BIL-037's seven stages had NO discount stage, so
#: `apps/rating/discount_pricing.py` was priced by nothing on the bill path and
#: an enrolled customer's reduction never reached an invoice; the gap was a
#: missing STAGE, which is why no per-function test could catch it and why the
#: PO found it by reading this list aloud. **apply-discounts is stage 5** —
#: after apply-charges (a scoped discount is a percentage of the PRINTED tariff
#: amounts, BR-RAT-068) and before compute-tax (R6 before R7, BR-RAT-071, with
#: each tax picking its own base per BR-RAT-106's `taxes.discount_treatment`) —
#: and the stages after it renumbered 6·7·8. Made deliberately in this tuple so
#: BR-BIL-038 clause (a)'s gate sees it in the diff; no golden value changes in
#: the same commit, and every B5 fixture passes no discounts so GT-1..61
#: reproduce to the digit. BR-BIL-037 is amended the same day, with the note
#: that older prose citing "stage 6/7" reads as 7/8.
SEQUENCE: tuple[tuple[int, str, str], ...] = (
    (1, "resolve-subscription", "billing"),
    (2, "measure-consumption", "billing"),
    (3, "price-usage", "rating"),
    (4, "apply-charges", "rating"),
    (5, "apply-discounts", "rating"),
    (6, "compute-tax", "rating"),
    (7, "assemble-document", "billing"),
    (8, "post-to-ledger", "billing"),
)

#: The TERMINAL stages this story owns. Stages 1–6 are the pure front
#: (US-BIL-029 + the DEF-502 discount stage).
TERMINAL_STAGES: tuple[int, ...] = (7, 8)

#: **BR-BIL-038 clause (b): the only doors the golden suite may enter through.**
#:
#: Dotted paths, as strings, so `10-scripts/gates/g21_refactor_contract.py` can
#: check what the suite imports without importing Django. A patch that pointed
#: the golden tests at `stages.assemble_document` or at a rating internal would
#: be testing the thing it just changed, and the gate names this tuple when it
#: refuses.
#:
#: `rating_seam.price_bill` and `.price_period` are here because B5's fixtures
#: legitimately enter at the pricing seam — GT-1..11 are single-service unit
#: fixtures and have no account to gather. That is the seam, not a stage
#: internal: `stages/__init__.py` documents both as the published route into
#: stages 3–5.
PUBLIC_ENTRY_POINTS: tuple[str, ...] = (
    "apps.billing.pipeline.run_to_document",
    "apps.billing.runs.calculate_account",
    "apps.billing.runs.calculate_run",
    "apps.billing.single.calculate_single_bill",
    "apps.billing.issue.issue_invoice",
    "apps.billing.rating_seam.price_bill",
    "apps.billing.rating_seam.price_period",
)

#: What a caller must NOT reach for from a golden test — a stage's insides.
#: The gate greps the golden suite for these and refuses.
STAGE_INTERNALS: tuple[str, ...] = (
    "apps.billing.stages.assemble_document",
    "apps.billing.stages.measure_consumption",
    "apps.billing.stages.resolve_subscription",
)

#: Where a signed figure is allowed to change, and the only way. Quoted so the
#: gate's refusal names the process rather than telling somebody "no".
FINANCE_RESIGN_ROUTE = "HUMAN-GUIDE §6 (finance re-sign)"


@dataclass(frozen=True)
class DocumentTieOut:
    """BR-BIL-032's answer: does the stamped instance agree with its rows?

    Carries the two figures and the two line counts rather than a boolean,
    because *"the tie-out failed"* is not actionable and *"payload 292.87 vs
    rows 247.87"* is.
    """

    invoice_id: str
    payload_total: Decimal | None
    invoice_total: Decimal
    #: `None` — NOT `0` — when the stamped instance carries no line set at all.
    #: See `_payload_lines` and `line_count_unavailable` below: a bill stamped
    #: before `assemble_document` began writing one cannot be asked this half of
    #: the question, and answering `0` made it look like a bill with no charges.
    payload_line_count: int | None
    row_line_count: int
    currency: str

    @property
    def line_count_unavailable(self) -> bool:
        """The stamped instance states no line set, so the counts cannot be
        compared. `DEF-969`: every bill issued before 2026-08-27 is in this
        state, permanently — hard rule 4 makes an issued payload append-only,
        so there is no path to add the line set to a bill already sent."""
        return self.payload_line_count is None

    @property
    def ties_out(self) -> bool:
        """The equality BR-BIL-032 states, over what this payload can answer.

        ⚠ **THE LINE-COUNT HALF IS NOT WAIVED — IT IS THREE-STATE, WHICH IS THE
        DISCIPLINE THIS MODULE ALREADY APPLIES EVERYWHERE ELSE (`DEF-969`).**
        A payload that STATES a line set must match its rows exactly, and a
        payload one line short still FAILS. A payload that states no line set at
        all is not a failure and never was: it is a question that cannot be
        asked of that bill, and the caller reports it as unanswered with its
        reason (`selectors._integrity_for`) rather than as *"these do not
        match"*, which on 47 of 47 bills is an accusation the figures do not
        support.

        `None` is not `false`. The whole reason this rule is worth having is
        that a clerk believes it; a check that cries wolf on every bill in the
        product is a check that has been switched off by the person reading it.
        """
        if self.payload_total is None or self.payload_total != self.invoice_total:
            return False
        if self.line_count_unavailable:
            return True
        return self.payload_line_count == self.row_line_count


@dataclass(frozen=True)
class BalancedHandoff:
    """Stage 7's emitted contract — US-BIL-009's shape, restated as a value.

    `{invoice id, account, service_date, per-GL bucket sums, AR total,
    currency}`. **Nothing on this object is written by billing**: it is what the
    ledger's posting service consumes (BR-BIL-011, CLAUDE.md rule 5).
    """

    invoice_id: str
    account_id: str
    service_date: date
    buckets: tuple[tuple[Any, Decimal], ...]
    ar_total: Decimal
    currency: str

    @property
    def balanced(self) -> bool:
        return money.finalize(sum((amount for _, amount in self.buckets), ZERO)) == money.finalize(
            self.ar_total
        )


def _payload_lines(payload: Any) -> list[Any] | None:
    """The payload's line set, whatever shape stage 6 stamped it in — or `None`.

    Read STRUCTURALLY and defensively: `bill_payload` is a contract
    (`payload_version`) rather than a fixed class, and a tie-out that crashed on
    an unexpected shape would be a tie-out that stopped tying out.

    ⚠ **THE EMPTY LIST AND THE ABSENT LIST WERE THE SAME ANSWER UNTIL 2026-08-27
    (`DEF-969`), AND THEY ARE DIFFERENT FACTS.** This function used to return
    `[]` for both, on the stated reasoning that an unrecognised shape *"FAILS
    the reconciliation loudly instead of passing it quietly"*. The reasoning is
    right for a shape that is unrecognised. It was applied to a payload that
    simply had no line set — because `assemble_document._snapshot_payload` never
    wrote one — so *"loudly"* meant a red alarm on every bill the product had
    ever issued, over figures that were correct to the cent.

    So the three answers are now distinct:
      * a **list** — the stamped line set, however it is keyed. Compared 1:1.
      * `[]` — the payload STATES a line set and it is empty. A real failure on
        a bill that has rows, and it still fails.
      * `None` — the payload states no line set anywhere. Unanswerable, not
        false; the caller says which (see `DocumentTieOut.ties_out`).
    """
    if not isinstance(payload, dict):
        return None
    for key in ("lines", "invoice_lines", "charge_lines"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    groups = payload.get("services")
    if isinstance(groups, list):
        collected: list[Any] = []
        stated = False
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get("lines"), list):
                stated = True
                collected.extend(group["lines"])
        # A `services` block whose groups carry no `lines` key is the SEEDED
        # shape (`{"code": …, "measured": …, "read_id": …}`) — it describes which
        # services were measured, not what was charged, and it is not a line set.
        return collected if stated else None
    return None


def tie_out_document(invoice: models.Invoice) -> DocumentTieOut:
    """**BR-BIL-032**, computed. Reads only; writes nothing; decides nothing.

    ❄️ On WE-1 the answer is `payload_total == invoice_total == 292.87` with the
    payload's line set reconciling 1:1 to **15** `invoice_lines`.

    The redundancy this checks is DELIBERATE (see the module docstring): the
    payload is what a reprint renders and the rows are what the ledger posted.
    Drift between them would show a customer one number and the trial balance
    another, with each internally consistent — which is precisely the failure
    that has no symptom until somebody disputes a bill.
    """
    payload = invoice.bill_payload or {}
    raw_total = payload.get("total") if isinstance(payload, dict) else None
    if raw_total is None and isinstance(payload, dict):
        # ⚠ `DEF-1064` — THIS FALLBACK COMPARES TWO DIFFERENT FIGURES AND HAS
        # ALWAYS BEEN A FALSE ALARM ON ANY ACCOUNT CARRYING ARREARS.
        # `issue._stamp_balance_forward` writes `total_due` as
        # *previous balance − payments + this period* (BR-BIL-035), while
        # `invoices.total` is THIS PERIOD ALONE. They are equal only when the
        # opening balance is zero — which is every bill on the seeded demo, so
        # the fallback looked harmless for a fortnight. Stage 6 now stamps
        # `total` (DEF-969), so this path is reached only by a bill issued
        # before that, and it stays because dropping it would move those bills
        # from a wrong answer to no answer at all.
        raw_total = payload.get("total_due")
    stamped_lines = _payload_lines(payload)
    return DocumentTieOut(
        invoice_id=str(invoice.pk),
        payload_total=(money.finalize(Decimal(str(raw_total))) if raw_total is not None else None),
        invoice_total=money.finalize(invoice.total),
        payload_line_count=(None if stamped_lines is None else len(stamped_lines)),
        row_line_count=models.InvoiceLine.objects.filter(
            tenant_id=invoice.tenant_id, invoice=invoice
        ).count(),
        currency=invoice.currency,
    )


def refuse_untied_document(invoice: models.Invoice) -> DocumentTieOut:
    """TC-8 — a forged or drifted payload FAILS, and the refusal NAMES the delta.

    *"A forged payload whose total disagrees with `invoices.total`, or a payload
    missing a line present in `invoice_lines` → tie-out fails naming the delta;
    drift can never be silent."*
    """
    tie = tie_out_document(invoice)
    if tie.ties_out:
        return tie
    if tie.payload_total is None:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} carries a stamped instance with no "
            "total, so it cannot be reconciled to its rows (BR-BIL-032). The payload is "
            "what a reprint renders; a reprint that cannot state a total is not the "
            "document the customer was sent.",
            br_ref="BR-BIL-032",
        )
    # `None` is not a count and must not print as one: a refusal reading
    # "over None line(s)" sends the reader hunting for a line called None.
    stated = (
        "states no line set"
        if tie.line_count_unavailable
        else f"over {tie.payload_line_count} line(s)"
    )
    raise BillingRuleError(
        f"bill {invoice.invoice_no or invoice.pk} does not tie out (BR-BIL-032): the "
        f"stamped instance says {tie.payload_total} {tie.currency} and "
        f"{stated}, and the rows say {tie.invoice_total} "
        f"{tie.currency} over {tie.row_line_count} line(s) — a delta of "
        f"{money.finalize(tie.payload_total - tie.invoice_total)}. The redundancy is "
        "deliberate: the payload is what a reprint renders and the rows are what the "
        "ledger posted, so drift shows the customer one number and the trial balance "
        "another with each internally consistent. It is never allowed to be silent.",
        br_ref="BR-BIL-032",
    )


def balanced_handoff(invoice: models.Invoice) -> BalancedHandoff:
    """**Stage 7's emitted contract.** Billing writes NOTHING here (rule 5).

    ❄️ On WE-1: DR 1200 AR **247.87** = Σ CR buckets exactly — 4100 88.60 · 4105
    12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 ·
    2200–2203 20.97 · 4200 5.00.

    The buckets and the AR figure are computed by `posting_seam`, which is the
    module that already owns the handoff and the one seam the ledger reads. This
    function does not recompute them — a second computation of a signed figure
    is a second figure — it re-states the equality as a checkable value so
    US-BIL-030 TC-4 can assert it without reaching into the ledger.
    """
    from apps.billing import posting_seam

    lines = list(models.InvoiceLine.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice))
    buckets = posting_seam.posting_buckets(invoice, lines)
    ar_total = posting_seam._refuse_unless_balanced(invoice, buckets)
    return BalancedHandoff(
        invoice_id=str(invoice.pk),
        account_id=str(invoice.account_id),
        service_date=invoice.service_date,
        buckets=tuple((bucket.gl_account_id, bucket.amount) for bucket in buckets),
        ar_total=ar_total,
        currency=invoice.currency,
    )


def run_to_document(
    account_id: Any,
    *,
    period_start: date,
    period_end: date,
    service_date: date,
    bill_run: models.BillRun,
    bill_type: str = "cycle",
) -> models.Invoice:
    """**THE PUBLIC ENTRY POINT** — stages 1 → 6, one DRAFT bill (BR-BIL-038 (b)).

    The door the bill run and the golden suite both use. It is deliberately a
    thin delegation to `single.prepare_single_bill` + `single.
    calculate_single_bill` — the SAME functions `runs.calculate_account` calls,
    in the same order — because a second sequence would be a second pipeline,
    and the contract would then be measuring a path nothing ships (BR-BIL-037:
    *"only the orchestrator knows the sequence"*).

    **Stage 7 is deliberately NOT here.** It runs at ISSUE, inside
    `issue.issue_invoice`'s transaction, because a posting refusal must refuse
    the issue and leave a discardable draft (BR-BIL-011, rule 4). A
    `run_to_document` that also posted would have to either issue the bill or
    post an unissued one, and both are wrong.

    Returns a DRAFT invoice with its stamped instance, which is BR-BIL-033's
    ordering expressed as a return type: the document exists before the bill
    does.
    """
    from apps.billing import single

    prepared = single.prepare_single_bill(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        service_date=service_date,
        bill_type=bill_type,
    )
    if prepared.blocked:
        first = prepared.blocked[0]
        raise BillingRuleError(
            f"this account could not be taken through the pipeline: {first.detail}. Stages "
            "1–2 refused before anything was priced, so no draft exists and nothing was "
            "written."
        )
    return single.calculate_single_bill(prepared, bill_run=bill_run, bill_type=bill_type)


def stage_owner(stage_no: int) -> str:
    """Who owns a stage — billing or rating. One list, read twice."""
    for number, _name, owner in SEQUENCE:
        if number == stage_no:
            return owner
    raise BillingRuleError(
        f"there is no stage {stage_no}; BR-BIL-037 (as amended 2026-08-22, DEF-502) "
        f"names eight ({', '.join(name for _, name, _ in SEQUENCE)}).",
        br_ref="BR-BIL-037",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-030@1d2c271 (sha256[:7] over the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-02-invoice-gl.md · 04-docs/05-modules/07-billing/02-business-rules.md · 08-qa/01-e2e/journeys/J2-read-to-cash.md · 04-docs/02-decisions/05-golden-tests.md)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D✔(2026-08-16 — `tie_out_document` and `balanced_handoff` are ANSWERED on `GET /invoices/{id}` as its `integrity` block, via apps/billing/selectors._integrity_for. The STAGES themselves still have no endpoint of their own and need none — S31 drives them through `runs` — and that half of the old note was and is correct) E✔(S30's Record-check panel on 07-frontend/src/features/billing/BillDetailPage.tsx: "Saved bill matches its charge lines" and "Posted amounts add up to the amount owed", with both figures and their currency when they disagree) ⚠ CORRECTED 2026-08-16, and the correction is worth reading: the old note said this module had "nothing of its own to draw", and `10-scripts/gates/surface_debt.txt` repeated it. A repo-wide search found NO caller for `tie_out_document`, `refuse_untied_document` or `balanced_handoff` outside their own test file — so BR-BIL-032's *"drift can never be silent"* was enforced against fixtures and against no bill this product ever produced. A guarantee nobody asks for is a guarantee nobody has, which is DEF-112's shape applied to a rule instead of to a screen F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff · black · pytest · run_gates · 10-scripts/03-golden-verify.py
#         (33 PASS, unchanged — this story pins B5 and must never move it) —
#         see the lane report for the verbatim RED transcripts of the new
#         BR-BIL-038 gate (G21), which was shown to fail on a boundary-move +
#         golden-value commit and on a retargeted suite before it was trusted.
# exceptions: (1) THIS MODULE CHANGES NO ARITHMETIC AND MAY NOT. B4/B5 are ❄
#         frozen; US-BIL-030's own scope line says it exists "to protect, not to
#         touch" them. Every figure in this file is quoted from a signed source
#         and none is computed here.
#         (2) STAGE 7 IS NOT IN `run_to_document`. It runs at ISSUE, inside
#         `issue.issue_invoice`'s transaction, because a posting refusal must
#         refuse the issue and leave a discardable draft. `balanced_handoff`
#         exposes the CONTRACT for assertion without moving where it runs.
#         (3) `balanced_handoff` READS `posting_seam._refuse_unless_balanced`, a
#         private helper, for the reason `corrections.py` records for the same
#         read: the seam publishes the bill-issue handoff and this lane may not
#         edit that file. Same package, one seam — but it is a private read and
#         is REPORTED rather than left to be discovered.
#         (4) `run_to_document` IS A DOOR, NOT A SECOND ORCHESTRATOR. It calls
#         exactly what `runs.calculate_account` calls; a test asserts the two
#         agree, because a door that drifted would make the contract measure a
#         path nothing ships.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

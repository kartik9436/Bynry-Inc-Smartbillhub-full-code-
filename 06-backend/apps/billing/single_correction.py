# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 (single-bill correction: credit note + rebill with
#           impact preview)   Screens: S30 (Fix a bill tab)
# Rules:    BR-BIL-014 (correction = reason → scope → impact preview → approval
#           → staged idempotent execution → deliver + audit; NO money-bearing
#           write before approval) · BR-BIL-004 (the original never changes) ·
#           BR-BIL-041 (the reason's CLASS derives the mechanism) · BR-BIL-042
#           (a single case takes the STRONGEST class present) · BR-BIL-043 (a
#           D-class case that moves money is REFUSED; an R-class case at $0.00
#           still emits its pair and the preview FLAGS the zero) · BR-BIL-044
#           (the preview is a persisted content-hashed artifact with NINE
#           required sections; approval binds it) · BR-BIL-045 (the posting
#           period is named before confirm) · BR-BIL-048 (only the LATEST
#           document in a chain is correctable) · BR-BIL-064 (the chain the
#           phase-4 panel follows) · BR-BIL-026 (the rebill pins the CURRENT
#           template version) · BR-BIL-018 (the back-bill window caps an UPWARD
#           correction — OQ-104 CLOSED, PO 2026-08-11 option A) · BR-TEN-043
#           (event time is an argument) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (money) · rule 4 (immutability) · rule 6 (idempotency) ·
#           rule 7 (audit)
# Golden:   ❄️ WE-9 / GT-25 (B5 FROZEN): ACC-1042's water read 8 → 6 kgal moves
#           an issued 247.87 to 227.95 — delta −19.92, of which −18.20 is
#           service revenue and −1.72 is tax across four authorities. ❄️ GT-6:
#           a 25.00 goodwill credit against a 247.30 invoice → 222.30.
#           NOTHING HERE MINTS A FIGURE: the engine re-prices through rating and
#           these fixtures pin arithmetic B4/B5 already froze.
# Tests:    06-backend/tests/test_us_bil_015_single_correction.py
# Impacts:  apps/billing/corrections.py (the per-bill mechanics this composes) ·
#           apps/billing/bulk_corrections.py (the case layer — ONE
#           implementation, entered here with a one-bill scope) ·
#           apps/billing/release.py (BR-BIL-064's panel follows the chain this
#           writes) · apps/billing/selectors.py (serves the chain to the API)
# ───────────────────────────────────────────────────────
"""US-BIL-015 — correcting ONE bill: what it will cost, then what it did.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 rating math, money rounding and the
ledger handoff all meet in the path this composes, and every executed branch
writes money. AI-authored 2026-08-15 under the PO ruling of 2026-08-09 (*"AI
will do it; we will review it later as human"*); row owed in
12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHY THIS MODULE IS A FAÇADE AND NOT AN ENGINE
════════════════════════════════════════════════════════════════════════════
US-BIL-016 (bulk) was built first and its own epic says why that is the right
order: *"bulk corrections are one case with many bills"* — a single-bill case
and a four-hundred-bill case are **the same row with a different scope**, which
is why the S30 list offers no bulk row action. So the per-bill mechanics live in
`corrections.py`, the case lifecycle lives in `bulk_corrections.py`, and this
module is the ONE-BILL DOOR onto both.

A second implementation of a money write is a second chance to double-write.
`open_case`, `approve`, `execute` and `abandon` are re-exported here by name
rather than wrapped, so a reader who greps for "who writes a credit note" finds
one answer and a caller who imports the wrong module still gets the right code.

WHAT THIS MODULE ADDS THAT THE BULK LAYER DOES NOT HAVE:

  1. **`open_for_bill`** — the one-bill entry: resolve → refuse → preview, with
     the balance and the back-bill window as explicit arguments rather than
     defaults, because both are facts about THIS bill.
  2. **`nine_sections`** — BR-BIL-044's nine-section contract, rendered. The
     bulk layer persists a per-bill `impact` dict and aggregates it; the
     approver of a SINGLE bill reads the sections themselves, and the epic is
     explicit that all nine are required and none is collapsible away.
  3. **`chain_of`** — TC-3's *"chain original ↔ credit note ↔ rebill, navigable
     both ways"*, which became buildable on 2026-08-12 (OQ-120).

════════════════════════════════════════════════════════════════════════════
THE CHAIN, AND THE RULING THAT MADE IT POSSIBLE
════════════════════════════════════════════════════════════════════════════
**PO 2026-08-12, OQ-120 CLOSED, verbatim: *"Nod to add the link on the new
bill"*.** `invoices.corrects_invoice_id` (migration `0017`) is carried by the
REPLACEMENT and points back at what it replaces. The direction is the ruling:
the original is immutable (BR-BIL-004, hard rule 4) and must not gain a column
after issue, while a rebill is still a draft when the link is written.

That one column is read in both directions, which is what makes TC-3's
*"navigable both ways"* one column and not two:

    original  ←──corrects_invoice_id──  rebill
       │                                  ▲
       └──credit_notes.original_invoice_id┘  (the other leg, already built)

**It also unblocks BR-BIL-064.** `release.summary_for` refused outright — naming
this exact column — for every run holding a superseded bill, because both
reachable figures were wrong. ❄️ On the PO's own case: a **$117.01** bill
corrected to **$104.20** makes the first run's panel read **$104.20**, not
$117.01 (which nobody owes) and not $0.00 (which is what dropping it like a VOID
would show).

════════════════════════════════════════════════════════════════════════════
WHAT REFUSES BEFORE ANYTHING IS WRITTEN, AND WHY EACH REFUSAL IS THE POINT
════════════════════════════════════════════════════════════════════════════
Every one of these fires at PREVIEW time, before a single money-bearing row
exists (BR-BIL-014: *"NO money-bearing write before approval"*).

* **A D-class reason whose recomputation moves money** (BR-BIL-043, TC-9). A
  misspelt name must not put $19.92 on somebody's account.
* **A supplied mechanism** (BR-BIL-041, TC-10). Answering "wrong rate" with a
  reprint is a *silent* underbilling — the customer keeps the wrong amount and
  no gate ever fires. This is the guard the epic singles out to be proved RED.
* **A bill that is not the latest in its chain** (BR-BIL-048, TC-15), which now
  NAMES the replacement instead of telling the operator to go and find it.
* **An upward correction beyond the back-bill window** (BR-BIL-018). ⚠ See
  below: this is BUILT, not stubbed.
* **Input drift between preview and execute** (BR-BIL-044, TC-13) — the case
  layer re-hashes the pinned impacts and refuses, retaining the stale artifact.

════════════════════════════════════════════════════════════════════════════
⚠ OQ-104 IS CLOSED. THIS STORY IS NOT BLOCKED, AND TC-16 IS NOT A STUB.
════════════════════════════════════════════════════════════════════════════
EP-BIL-04's frontmatter for US-BIL-015 still reads `blocked_by: [OQ-104]` and
its TC-16 still says *"implement to the boundary and stub"* against that id.
**Both are stale**, and the live registry is the authority (CLAUDE.md: *"12-governance/01-open-questions.md — the live
registry; A17 scoreboard is the historical view"*). That row reads:

    **CLOSED** — PO 2026-08-11, option A: the BR-BIL-018 back-bill window
    APPLIES to an upward correction. Shown: a 2023 under-read corrected now
    would bill $1,840 for a period 30 months back. The correction workflow is
    NOT a route around the cap; the preview carries the refusal. Downward
    corrections are unaffected at any age.

So TC-16 is a **REFUSAL test**, not a stub: `corrections.refuse_upward_beyond_
window` raises `BillingRuleError` for a positive delta beyond the window, and is
exempt for theft (OQ-071, carried through unchanged). A not-implemented stub
here would cite a CLOSED id — which gate G8 exists to catch, and which the
release lane's own docstring names as the mistake to avoid. The stale
frontmatter is REPORTED.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT THIS MODULE DOES *NOT* DECIDE — OQ-215
════════════════════════════════════════════════════════════════════════════
**Does a class-C goodwill concession move THIS bill, or the NEXT one?** Two PO
rulings of consecutive days survive in the corpus and disagree:

  * EP-BIL-04 §1a/TC-17 — *"a partial credit note referencing the original"*,
    and the BILL's balance moves to **$222.30**;
  * the decision-log row of 2026-08-11 — *"you dont touch the bill; you issue
    new a good will credit; everything remain as it is, it is new good will
    credit to be applied in new bill"*, under which the BILL's delta is
    **$0.00** and the credit is consumed by a FUTURE bill.

❄️ **GT-6's frozen $222.30 is reached either way**, which is exactly why nothing
has forced the question — and why an implementer must not pick. EP-BIL-04 §8
says so in as many words: *"It needs one sentence from the PO and is not a thing
an implementer may pick."* `corrections.build_impact` implements the second
reading (class-C bill delta forced to ZERO); this module RENDERS whichever the
engine produced and states the open question in section 3 of the preview, so the
approver is told that the wording is unratified rather than shown a number
presented as settled. **Nothing here re-decides it.** Filed as **OQ-215**.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.apps import apps as django_apps

from apps.billing import bulk_corrections, correction_reasons, corrections, models
from apps.billing.correction_models import (
    CASE_APPROVED,
    CASE_DONE,
    CASE_EXECUTING,
    CASE_OPEN,
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    SCOPE_SINGLE,
    CorrectionCase,
    CorrectionCaseBill,
)
from apps.billing.exceptions import BillingRuleError
from core import money

ZERO = Decimal("0")

#: BR-BIL-044's nine sections, in the epic's own order and with the epic's own
#: numbering. A tuple, not a set: *"nine sections, all required, none
#: collapsible away"* is an ORDERED contract — an approver reads them top to
#: bottom, and section 9 (the gate) is last for a reason.
PREVIEW_SECTIONS: tuple[tuple[int, str], ...] = (
    (1, "what_is_being_corrected"),
    (2, "the_lines"),
    (3, "the_money"),
    (4, "the_documents_that_will_exist"),
    (5, "the_ledger_handoff"),
    (6, "the_customers_balance"),
    (7, "what_the_customer_will_receive"),
    (8, "warnings"),
    (9, "the_gate"),
)

#: The unresolved question this module RENDERS rather than answers. See the
#: docstring: a live id, never a closed one, because a stub or a caveat citing a
#: CLOSED id is what gate G8 rejects.
OQ_CLASS_C_ARTIFACT = "OQ-215"

#: BR-BIL-014's gate, v1 (OQ-072 closed): ALL corrections need System Admin
#: approval. Named as a VALUE so section 9 quotes the rule rather than
#: paraphrasing it, and so a change of role is one edit.
APPROVER_ROLE = "System Admin"

#: BR-BIL-036's floor. Every bill goes out on paper at minimum, so section 7
#: never renders an empty channel list.
DELIVERY_FLOOR = "print"


@dataclass(frozen=True)
class SingleCase:
    """One bill's case, its pinned row and its impact — the three, together.

    A convenience over the case layer's rows and nothing more: no state of its
    own, nothing persisted, no arithmetic. It exists because every caller of a
    single-bill case wants all three and joining them at four call sites is how
    two of them start disagreeing about which bill the case is for.
    """

    case: CorrectionCase
    bill_row: CorrectionCaseBill
    invoice: models.Invoice

    @property
    def impact(self) -> dict[str, Any]:
        return dict(self.bill_row.impact or {})

    @property
    def correction_class(self) -> str:
        return self.case.correction_class


def _one_row(case: CorrectionCase) -> CorrectionCaseBill:
    """The single case's one pinned bill, refusing if it is not exactly one."""
    rows = list(CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case))
    if len(rows) != 1:
        raise BillingRuleError(
            f"case {case.case_no or case.pk} pins {len(rows)} bills and this is the "
            "SINGLE-bill surface (US-BIL-015). A multi-bill case is US-BIL-016's — its "
            "approver reads an aggregate panel, not nine sections about one customer, and "
            "one signature cannot honestly cover both shapes.",
            br_ref="BR-BIL-046",
        )
    return rows[0]


def open_for_bill(
    invoice: models.Invoice,
    *,
    reason_codes: tuple[str, ...],
    actor: Any,
    as_of: date,
    posting_period: date | None = None,
    goodwill_amount: Decimal | None = None,
    balance_before: Decimal | None = None,
    backbill_window_months: int = corrections.DEFAULT_BACKBILL_WINDOW_MONTHS,
    theft_exempt: bool = False,
    case_no: str | None = None,
) -> SingleCase:
    """Open a correction case on ONE bill. **Writes no money** (BR-BIL-014).

    The rows written are the case, its one pinned bill and that bill's impact —
    none money-bearing. No credit note, no invoice, no adjustment and no journal
    line exists until `execute`, and US-BIL-015 TC-2 counts those four tables
    before and after rather than taking this paragraph's word for it.

    ❄️ **Worked on WE-9 (B5 FROZEN), which is TC-1.** ACC-1042's water read is
    superseded 8 → 6 kgal after BL-2608-018410 issued at **247.87**. Re-pricing
    the same period against today's inputs gives water **26.50** (was 39.50),
    sewer **10.60** (was 15.80), taxable **203.70**, tax **19.25** — corrected
    current **227.95**, delta **−19.92**. Nothing in this module computes any of
    those: `corrections.recompute` re-prices through the rating engine and B4/B5
    own the arithmetic.

    `as_of`, `balance_before` and `posting_period` are ARGUMENTS, never lookups
    or clock reads (BR-TEN-043). A preview and the execute that follows it must
    judge the same bill against the same day, and the balance is payments'
    fact — billing emits a re-allocation PLAN and never computes an allocation.

    `theft_exempt` is a caller's fact about the case rather than something
    inferred from a reason code (OQ-071/BR-BIL-019 carried through unchanged).
    """
    corrections.refuse_unless_latest_in_chain(invoice)
    # BR-BIL-043 / TC-9, checked BEFORE the case row is even attempted so that
    # "Nothing was written" is true by construction rather than by rollback.
    # See `refuse_document_class_that_moves_money` for why the impact-level
    # guard cannot fire on its own — the class-D impact is zero by definition.
    correction_class = correction_reasons.class_for(reason_codes)
    corrections.refuse_document_class_that_moves_money(invoice, correction_class=correction_class)
    case = bulk_corrections.open_case(
        reason_codes=reason_codes,
        scope_kind=SCOPE_SINGLE,
        scope={
            "invoice_id": str(invoice.pk),
            "invoice_no": invoice.invoice_no,
            # The case layer reads these back at execute; they are recorded
            # rather than re-derived so the executed case runs on the numbers
            # the approver saw (BR-BIL-044).
            **({"goodwill_amount": str(goodwill_amount)} if goodwill_amount is not None else {}),
            **({"balance_before": str(balance_before)} if balance_before is not None else {}),
        },
        invoices=(invoice,),
        actor=actor,
        posting_period=posting_period,
        goodwill_amount=goodwill_amount,
        as_of=as_of,
        backbill_window_months=backbill_window_months,
        theft_exempt=theft_exempt,
        case_no=case_no,
    )
    return SingleCase(case=case, bill_row=_one_row(case), invoice=invoice)


def _balance_figures(single: SingleCase) -> tuple[str | None, str | None]:
    """§6's before → after, derived from the case SCOPE, never re-priced.

    ⚠ **THE BALANCE IS NOT WRITTEN INTO THE PINNED IMPACT, AND THAT IS
    DELIBERATE.** The impact is what BR-BIL-044's content hash covers and what
    approval binds; `bulk_corrections.execute` re-hashes the pinned rows and
    REFUSES on any difference. Stamping a derived display figure into that dict
    after the hash was taken makes every execution look like input drift — which
    is exactly the bug this function exists instead of: caught here by TC-2
    failing with *"the inputs moved between preview and execute"* on a case
    where nothing had moved.

    So the balance travels on `case.scope`, which is the operator's own input
    and is not hashed, and the arithmetic is the impact's OWN delta applied to
    it — one subtraction, no second source of truth.
    """
    raw = single.case.scope.get("balance_before")
    if raw is None:
        return None, None
    before = money.finalize(Decimal(str(raw)))
    delta = Decimal(single.impact.get("delta", "0"))
    return str(before), str(money.finalize(before - delta))


def nine_sections(single: SingleCase) -> dict[str, Any]:
    """BR-BIL-044's nine-section contract, rendered. Reads only; decides nothing.

    *"Nine sections, all required, none collapsible away."* Every section is
    present on every class — and four of them say **none** on a class-D case,
    which the epic names as the reason the two mechanisms are impossible to
    confuse on screen.

    ⚠ **Money is rendered as STRINGS at their stored precision, never floats and
    never pre-formatted.** CLAUDE.md rule 2: a Decimal through JSON becomes a
    float, and 2-decimal display is `MoneyCell`'s job on the screen, not this
    function's. What ships here is the number and its currency.

    THE SECTIONS THIS FUNCTION ADDS RATHER THAN COPIES, AND WHY:

    * **§5 the ledger handoff IN FULL.** Both balanced entries line by line plus
      the net per GL bucket — the epic's own reason is that *"the correction is
      not one net entry"*: the credit note reverses the original's stamped
      buckets and the rebill posts its own. Netting them would lose the fact
      that a bill was issued and reversed, which is what an auditor follows.
      ⚠ It is DESCRIBED here and EMITTED by `corrections.post_credit_note_
      reversal` / `issue_invoice`; this function writes no journal line and
      composes no posting request (CLAUDE.md rule 5).
    * **§7 what the customer will receive.** BR-BIL-036's print floor, always,
      because the delivery ELECTION (`accounts.paperless`) is PROPOSED-SCHEMA
      and unbuilt — so an empty channel list would read as "nothing is sent".
    * **§9 the gate.** The standing statement that nothing money-bearing exists
      yet, which BR-BIL-014 requires be on the approval screen itself.
    """
    impact = single.impact
    case = single.case
    klass = single.correction_class
    currency = impact.get("currency", single.invoice.currency)
    original = Decimal(impact.get("original_total", "0"))
    corrected = Decimal(impact.get("corrected_total", "0"))
    delta = Decimal(impact.get("delta", "0"))

    sections: dict[str, Any] = {
        "what_is_being_corrected": {
            "bill_no": impact.get("invoice_no") or str(single.invoice.pk),
            "account_id": impact.get("account_id"),
            "period_start": single.invoice.period_start.isoformat(),
            "period_end": single.invoice.period_end.isoformat(),
            "reason_codes": list(case.reason_codes),
            # BR-BIL-041: the class is shown as a WORD, not a code — the epic is
            # explicit, and "restatement" is what an approver can act on where
            # "R" is a thing to go and look up.
            "class_in_words": correction_reasons.mechanism_in_words(klass),
            "class": klass,
            "initiated_by": str(case.initiated_by_id) if case.initiated_by_id else None,
        },
        "the_lines": {
            # EVERY line, including the ones that did not move. The epic's
            # reason: "a preview that shows only movement cannot be checked" —
            # "only water and sewer changed" is a claim the approver must be
            # able to verify rather than take.
            "lines": impact.get("lines", []),
            "unchanged_count": sum(1 for line in impact.get("lines", []) if not line.get("moved")),
            "moved_count": sum(1 for line in impact.get("lines", []) if line.get("moved")),
        },
        "the_money": {
            "original_total": str(original),
            "corrected_total": str(corrected),
            "delta": str(delta),
            "currency": currency,
            "tax_by_authority": impact.get("tax_by_authority", []),
            # ⛔ CR-101-BRC03 §06 — THE DISCOUNTS PANEL, AND IT BELONGS IN THIS
            # SECTION RATHER THAN IN A TENTH ONE, for the reason the settlement
            # panel gives under `the_customers_balance`: BR-BIL-044 is nine
            # sections, none may be added, and section (3) is already "money:
            # original total, corrected total, delta, tax broken out per
            # authority" — a reduction is money on the same two bills. Drawn
            # on EVERY class (p129: "an absent panel is drawn, never omitted")
            # with a CODE saying which shape; `corrections.discount_panel`
            # states what it knows and what it cannot. A case whose stored
            # artifact predates the panel (approval binds the artifact, so it
            # is not recomputed) says so by code too, never by an absent key.
            "discounts": impact.get("discounts") or _discounts_not_in_artifact(currency),
        },
        "the_documents_that_will_exist": {
            "documents": list(impact.get("documents", ())) or ["none"],
        },
        "the_ledger_handoff": _ledger_handoff_section(single),
        "the_customers_balance": {
            "before": _balance_figures(single)[0],
            "after": _balance_figures(single)[1],
            "currency": currency,
            "reallocation_plan": impact.get("reallocation_plan", []),
            "in_plain_language": _balance_sentence(single),
            # ⛔ CR-059 CS-36 · task 20 — THE SETTLEMENT PANEL, AND IT BELONGS
            # IN THIS SECTION RATHER THAN IN A TENTH ONE. BR-BIL-044 says
            # *"nine sections, all required, none collapsible away"* and that is
            # a ratified contract a lane may not widen. This section is already
            # the one about the customer's money, and it already carries the
            # `reallocation_plan` SENTENCE that CS-36's defect is made of —
            # *"payments allocated to the original re-allocate to the rebill"* —
            # which was composed on every preview and executed by nobody until
            # 2026-09-01. The figures now sit beside the sentence that promises
            # them. `null` on any class but a restatement, and `null` when
            # payments could not be asked; see `corrections.settlement_preview`.
            "settlement": impact.get("settlement"),
        },
        "what_the_customer_will_receive": {
            "channels": [DELIVERY_FLOOR],
            "br_ref": "BR-BIL-036",
            "detail": "print is the floor and is what every bill gets. The delivery "
            "ELECTION (`accounts.paperless`) is PROPOSED-SCHEMA and unbuilt, so no email "
            "or SMS row is written on a guess — an empty channel list would read as "
            "'nothing is sent'.",
        },
        "warnings": {"warnings": list(single.bill_row.warnings or [])},
        "the_gate": {
            "approver_role": APPROVER_ROLE,
            "br_ref": "BR-BIL-014 · OQ-072",
            "status": case.status,
            "preview_hash": case.preview_hash,
            # `CR-180-BRC10` B9 / `DEF-BIL-5357` — who sent it and who approved
            # it, by NAME (B14 rule 31). Null until there is one.
            "initiated_by_name": _name_of(case, "initiated_by"),
            "approved_by_name": _name_of(case, "approved_by"),
            # BR-BIL-014's standing statement, on the screen where the decision
            # is taken rather than in a docstring nobody approving reads.
            "standing_statement": (
                "Nothing money-bearing exists yet. No credit note, no rebill, no "
                "adjustment and no journal entry has been written — this preview IS the "
                "approval artifact, and approval binds these exact figures (BR-BIL-044): "
                "if any input moves before execution, execution is refused and a fresh "
                "preview is required."
            ),
        },
    }

    if klass == CLASS_CREDIT_ONLY:
        # OQ-215 — the ONE place the two surviving readings diverge on screen.
        # Stated, never resolved: the approver is told the wording is
        # unratified rather than shown a settled-looking number.
        sections["the_money"]["open_question"] = {
            "oq": OQ_CLASS_C_ARTIFACT,
            "detail": (
                "this bill's own delta reads 0.00 because the engine implements the PO's "
                "2026-08-11 reading — the concession is an ACCOUNT credit consumed by a "
                "future bill and the bill is untouched. EP-BIL-04 §1a states the opposite "
                "reading (a partial credit note against THIS bill, balance 222.30) and "
                "both survive in the corpus. GT-6's 222.30 is reached either way, which "
                "is why nothing has forced the question. What differs is whether the "
                "customer's current bill says 247.30 or 222.30."
            ),
        }

    missing = [name for _, name in PREVIEW_SECTIONS if name not in sections]
    if missing:  # pragma: no cover - the literal above covers all nine
        raise BillingRuleError(
            f"the impact preview is missing required section(s) {missing} — BR-BIL-044 "
            "requires all nine and none is collapsible away. An approval recorded against "
            "a partial artifact covers less than it appears to.",
            br_ref="BR-BIL-044",
        )
    return sections


#: The discounts panel's outcome for an artifact stored BEFORE the panel
#: existed (CR-101-BRC03 §06, 2026-09-15). Approval binds the stored artifact,
#: so it is never recomputed to fill the gap; the panel is drawn with this
#: code instead, which is what "drawn, never omitted" means for old cases.
DISCOUNTS_NOT_IN_ARTIFACT = "not_in_this_preview"


def _discounts_not_in_artifact(currency: str) -> dict[str, Any]:
    return {
        "outcome": DISCOUNTS_NOT_IN_ARTIFACT,
        "original": [],
        "corrected": [],
        "original_total": None,
        "corrected_total": None,
        "delta": None,
        "currency": currency,
        "service_date": None,
        "version_basis": None,
        "problems": [],
    }


def _ledger_handoff_section(single: SingleCase) -> dict[str, Any]:
    """§5 — both entries and the net per bucket, DESCRIBED. Writes nothing.

    ❄️ On WE-9 this is the shape §7a of the epic states verbatim: JE-A debits the
    original's own stamped buckets (4100 88.60 · 4105 12.00 · 4110 39.50 · 4115
    8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200-03 20.97 · 4200 5.00) and
    credits AR **247.87**; JE-B debits AR **227.95** and credits the rebill's own
    stamps. The NET per bucket — which is what the preview leads with — is
    **4110 −13.00 · 4120 −5.20 · 2200-03 −1.72 · 1200 AR −19.92**, and the
    cross-check the epic gives is DR 13.00 + 5.20 + 1.72 = 19.92 = CR AR 19.92.

    The per-bucket figures are NOT recomputed here. They are the tax split and
    line deltas already on the impact, read back — a second computation of a
    signed figure is a second figure.

    **§5 also names the POSTING PERIOD before confirm (BR-BIL-045).** A closed
    July posts to the earliest open period (BR-TEN-038), so the month that moves
    is not always the month on the bill, and a tax delta therefore lands in a
    remittance basis after that month was filed (BR-LED-002).
    """
    impact = single.impact
    klass = single.correction_class
    currency = impact.get("currency", single.invoice.currency)
    period = single.case.posting_period

    net_by_bucket = [
        {"line": line.get("label"), "delta": line.get("delta"), "currency": currency}
        for line in impact.get("lines", [])
        if line.get("moved")
    ]
    if klass == CLASS_RESTATEMENT:
        entries = [
            {
                "entry": "JE-A · credit note",
                "detail": "the ORIGINAL's own stamped buckets debited, AR credited by the "
                f"same total ({impact.get('original_total')} {currency}). Emitted by "
                "`corrections.post_credit_note_reversal` through the posting seam.",
            },
            {
                "entry": "JE-B · rebill",
                "detail": f"AR debited {impact.get('corrected_total')} {currency}, the "
                "rebill's OWN stamps credited. Emitted by `issue.issue_invoice`.",
            },
        ]
        note = (
            "TWO balanced entries, never one net entry (BR-BIL-011): the credit note "
            "reverses the original in full and the rebill posts its own stamps. Netting "
            "them would lose the fact that a bill was issued and reversed, which is what "
            "an auditor follows. Billing writes no journal line — the ledger posting "
            "service is the sole writer (CLAUDE.md rule 5)."
        )
    elif klass == CLASS_CREDIT_ONLY:
        entries = [
            {
                "entry": "JE · goodwill credit",
                "detail": "DR write-off / CR customer credit balance, both resolved BY "
                "DESIGNATION and never by account number (PO 2026-08-12, OQ-105/OQ-168 — "
                '"a separate write-off account"). The original service revenue is NOT '
                "reversed: no 41xx bucket moves, which is the whole content of that "
                "ruling. Emitted by `corrections.execute_credit_only`.",
            }
        ]
        note = (
            "ONE entry. The bill's own buckets do not move, so the utility's month of "
            "revenue keeps reading as the revenue that was billed and concessions are "
            "their own visible figure rather than a dent in the top line."
        )
        net_by_bucket = []
    else:  # CLASS_DOCUMENT
        entries = []
        note = (
            "NONE. A document correction posts nothing at all (BR-BIL-041/043): the money "
            "is right and only the page was wrong, so the balance delta is exactly 0.00."
        )
        net_by_bucket = []

    return {
        "entries": entries,
        "net_by_bucket": net_by_bucket,
        "tax_by_authority": impact.get("tax_by_authority", []),
        "note": note,
        # BR-BIL-045 — named BEFORE confirm, always.
        "posting_period": period.isoformat() if period else None,
        "posting_period_note": (
            "the entries land in this period. BR-TEN-038: a period that is closed posts to "
            "the earliest OPEN one, so the month that moves is not always the month on the "
            "bill — and a tax delta therefore changes a remittance basis in a month that "
            "has already been filed (BR-LED-002)."
            if period is not None
            else "not resolved on this preview. BR-BIL-045 requires it be named before "
            "confirm; supply `posting_period` when opening the case."
        ),
    }


def _balance_sentence(single: SingleCase) -> str:
    """§6's plain-language line — BR-BIL-009, the sentence the approver reads.

    ❄️ The epic writes it out for WE-9 and this reproduces its shape: *"Sarah has
    already paid this bill. After the correction she will have paid $19.92 more
    than she owes. That $19.92 stays on her account as a credit and comes off
    her next bill; she can ask for it back instead."*

    Deliberately built from the impact's OWN figures and never re-derived, and
    deliberately not translated here — i18n is the frontend's, and a money
    sentence assembled twice is a money sentence that can disagree with itself.
    """
    impact = single.impact
    before, after = _balance_figures(single)
    currency = impact.get("currency", single.invoice.currency)
    delta = Decimal(impact.get("delta", "0"))
    if before is None or after is None:
        return (
            "the customer's balance is not shown on this preview: it is payments' fact and "
            "was not supplied (`balance_before`). BR-BIL-044 §6 requires it before "
            "approval — a correction approved without knowing what the customer has "
            "already paid can leave them owed money nobody has told them about."
        )
    if delta < ZERO:
        return (
            f"This correction reduces what the customer owes by {abs(delta)} {currency}. "
            f"Their balance moves from {before} to {after} {currency}. If the original was "
            "already paid, the difference stays on the account as a credit and comes off "
            "the next bill; they can ask for it back instead (BR-PAY-010)."
        )
    if delta > ZERO:
        return (
            f"This correction increases what the customer owes by {delta} {currency}. "
            f"Their balance moves from {before} to {after} {currency}. They were never "
            "told they owed this, so the bill they receive has to explain it."
        )
    return (
        f"This correction does not change what the customer owes: their balance stays at "
        f"{after} {currency}."
    )


def _iso_or_none(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def _name_of(case: Any, relation: str) -> str | None:
    """`CR-180-BRC10` B9 — the case's own actor FK, by name; null, never ""."""
    if getattr(case, f"{relation}_id", None) is None:
        return None
    user = getattr(case, relation, None)
    return (getattr(user, "full_name", "") or "").strip() or None


def _leg(invoice: models.Invoice | None) -> dict[str, Any] | None:
    """One end of the chain, as the Corrections tab's *What happened* row.

    ⚠ **THE THREE ADDED MEMBERS ARE COLUMNS OF THE ROW, NOT A COMPUTATION.**
    `issued_at`, `total` and `currency` are read off the invoice exactly as
    stored (hard rule 2 — four decimals, `CHAR(3)` partner, rounded once at
    DISPLAY and never here). They exist because the drawn table gives every
    event a date and an effect, and until 2026-09-14 the chain served a number
    and an id and nothing else, so a screen drawing that table would have had
    to fetch each leg's whole invoice to date it.
    """
    if invoice is None:
        return None
    return {
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "issued_at": _iso_or_none(invoice.issued_at),
        "total": str(invoice.total),
        "currency": invoice.currency,
    }


def _actor(user: Any, tenant_id: Any) -> dict[str, Any] | None:
    """WHO did it — a NAME and a ROLE, and never an id (B14 rule 31).

    The drawn *What happened* table puts the actor's role under their name
    (*"Vijay Bikkad / System Admin"*), and `correction_cases` stores two user
    FKs and nothing else. This resolves them the way `apps/audit/selectors.
    actor_names` already does — a tenant-scoped cross-module READ through the
    app registry, never an import of another module's models — and adds the
    role from `tenant_memberships`, which is where a user's role lives.

    ⚠ **A BLANK NAME STAYS NULL RATHER THAN BECOMING AN EMPTY STRING.**
    `identity.User.full_name` defaults to `""` while a user is only invited
    (US-IDN-004), and a cell drawn from `""` reads as a name that failed to
    render. The screen states the absence instead.

    ⚠ **NO ID IS SERVED AT ALL, not even as a fallback.** The audit trail's
    actor payload keeps one because a removed actor still has to be traceable
    there; here the row is a correction event that the case itself identifies,
    so an unresolvable user is simply an unnamed one.
    """
    if user is None:
        return None
    name = (getattr(user, "full_name", "") or "").strip() or None
    role: str | None = None
    membership_model = django_apps.get_model("identity", "TenantMembership")
    membership = (
        membership_model.objects.filter(tenant_id=tenant_id, user_id=user.pk)
        .select_related("role")
        .first()
    )
    if membership is not None and membership.role is not None:
        role = membership.role.name or None
    return {"name": name, "role": role}


def _case_of(invoice: models.Invoice) -> dict[str, Any] | None:
    """The correction CASE this bill was pinned into, if any.

    `CorrectionCaseBill` pins the bill, so the case is one indexed read from
    the invoice — which is why the drawn *correction opened* and *approved*
    rows are reachable at all. A bill can be pinned into more than one case
    over its life (a second correction on a bill already corrected), so the
    LATEST is served and the screen draws one pair of rows for it.

    `case_no` is served as it stands, `null` included. ⚠ **IT READ "BR-BIL-014
    mints the number on approval" UNTIL 2026-10-14, AND NOTHING EVER MINTED
    ONE** (`DEF-BIL-10147`). G3 (PO 2026-10-14) numbers a case AT SEND from the
    tenant's Correction case series (`corrections.allocate_case_no`), and
    existing cases were numbered once by `billing/0043`. `null` now means the
    series was missing at Send; the screen says so in words rather than
    printing the case's database id, which is B14 rule 31.
    """
    row = (
        CorrectionCaseBill.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice)
        .select_related("case", "case__initiated_by", "case__approved_by")
        .order_by("-case__created_at", "-id")
        .first()
    )
    if row is None:
        return None
    case = row.case
    return {
        "case_no": case.case_no,
        "status": case.status,
        "reason_codes": list(case.reason_codes or []),
        "opened_at": _iso_or_none(case.created_at),
        "opened_by": _actor(case.initiated_by, invoice.tenant_id),
        "approved_on": _iso_or_none(case.approved_on),
        "approved_by": _actor(case.approved_by, invoice.tenant_id),
    }


def chain_of(invoice: models.Invoice) -> dict[str, Any]:
    """TC-3 — *"the chain original ↔ credit note ↔ rebill, navigable both ways"*.

    Buildable since 2026-08-12 (OQ-120) and not before: the rebill leg had no
    column, so `selectors.invoice_detail` served `rebill_of_invoice_id` and
    `corrected_by_invoice_id` as null on every row and this function could not
    have existed.

    BOTH DIRECTIONS COME OFF ONE COLUMN, which is why the chain cannot fork or
    disagree with itself:

      * `replaces`     — this bill's own `corrects_invoice_id`, read forwards;
      * `replaced_by`  — the same column read backwards
                         (`uq_invoices_one_replacement` makes it single-valued);
      * `credit_notes` — the other leg, `credit_notes.original_invoice_id`,
                         which has existed all along.

    `head` is what BR-BIL-064's panel shows and what BR-BIL-048 allows a new
    case to be opened on. For an uncorrected bill it is the bill itself.

    ══════════════════════════════════════════════════════════════════════════
    WIDENED 2026-09-14 (`CR-101-BRC03`) SO THE DRAWN *WHAT HAPPENED* TABLE CAN
    BE BUILT AT ALL — ADDITIVE, AND NOT ONE EXISTING MEMBER MOVED.
    ══════════════════════════════════════════════════════════════════════════
    The Billing blueprint's §02.3 populated state draws five events with a
    date, a reason, an actor and an effect apiece. Four of those five facts
    were not on this payload: the legs carried a number and an id, the credit
    notes carried neither their reason nor their date, and no actor was served
    anywhere. The step-1 record chipped that state *Exists behind* and flagged
    the chip as a claim to CHECK — this is the check, and the answer was no.

    So: every leg now carries `issued_at`, `total` and `currency`; every credit
    note carries `reason` and `issued_at`; and `case` carries the correction
    case with its two actors. All of it is COLUMNS, read as stored.

    ⚠ **`net_effect` IS THE ONE DERIVED FIGURE, AND IT IS DERIVED HERE RATHER
    THAN IN THE BROWSER FOR THE REASON `BillDetailPage` STATES ABOUT ITSELF:**
    *"the screen displays what the server resolved"* (PO 2026-08-30). It is
    Σ(credit notes against this bill) + (the replacement's total, when there is
    one) — the arithmetic the blueprint states in its own prose against hard
    rule 4: the original stays charged for ever, a credit note cancels it, a
    replacement charges the right amount, and the difference is what the
    customer is better or worse off by. **Three documents, not one edited one.**

    It is summed at the STORED scale and rounded nowhere: hard rule 2 rounds at
    display, and `MoneyCell` is the display. **It moves no signed figure** — no
    B4 rule and no B5 golden test states a net-effect figure, and every input
    is a total this screen already shows one row above. It is `null`, not
    `0.0000`, when nothing has corrected this bill, because "nothing happened"
    and "it netted to zero" are different claims (a class-R restatement that
    nets to zero is real, and `billing.fix.warning.restatement_nets_to_zero`
    exists for it).
    """
    replaces = invoice.corrects_invoice
    replaced_by = corrections.replacement_of(invoice)
    head = corrections.latest_in_chain(invoice)
    notes = models.CreditNote.objects.filter(
        tenant_id=invoice.tenant_id, original_invoice=invoice
    ).order_by("issued_at", "id")
    note_rows = [
        {
            "id": str(note.pk),
            "credit_note_no": note.credit_note_no,
            "amount": str(note.amount),
            "currency": note.currency,
            "reason": note.reason,
            "issued_at": _iso_or_none(note.issued_at),
        }
        for note in notes
    ]
    net_effect: Decimal | None = None
    if note_rows or replaced_by is not None:
        net_effect = sum(
            (Decimal(row["amount"]) for row in note_rows),
            Decimal("0"),
        )
        if replaced_by is not None:
            net_effect += Decimal(replaced_by.total)
    return {
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "status": invoice.status,
        "issued_at": _iso_or_none(invoice.issued_at),
        "total": str(invoice.total),
        "currency": invoice.currency,
        "replaces": _leg(replaces),
        "replaced_by": _leg(replaced_by),
        "credit_notes": note_rows,
        "case": _case_of(invoice),
        "net_effect": None if net_effect is None else str(net_effect),
        "head": {"invoice_id": str(head.pk), "invoice_no": head.invoice_no},
        "is_latest": str(head.pk) == str(invoice.pk),
        "br_ref": "BR-BIL-048 · BR-BIL-064",
        "chain_column": "invoices.corrects_invoice_id (PO 2026-08-12, OQ-120)",
    }


def execute_single(
    single: SingleCase,
    *,
    issued_at: datetime,
    on_date: date,
    template_id: Any = None,
    template_version: int | None = None,
    actor: Any = None,
) -> bulk_corrections.ExecutionResult:
    """Execute an APPROVED single-bill case. One bill, one transaction.

    Delegates to the case layer verbatim — `bulk_corrections.execute` is
    idempotent (rule 6: a row already `done` is skipped, so a retry storm, a
    double-clicked button and a resumed worker all leave exactly ONE credit note
    and ONE rebill), re-hashes the pinned impact and refuses on drift
    (BR-BIL-044), and catches a per-bill failure with zero artifacts left behind
    (BR-BIL-047). Re-implementing any of that for the one-bill case would be a
    second chance to double-write.

    `template_id` / `template_version` are the rebill's pin (BR-BIL-026: the
    CURRENT version at rebill issue) and are REQUIRED for a class-R case. They
    are not defaulted from the original — hard-won law 3: silently reprinting on
    a version that may have been superseded is the unsafe option, so it is the
    one you type.
    """
    # The case layer refuses too (same three states); this refuses EARLIER and
    # names the gate, which is what the S30 button needs in order not to be
    # offered at all. `executing` and `open` are here because a resumed or
    # retried execution is the SAME call (rule 6) — see `bulk_corrections.
    # resume`, which is `execute` under another name for exactly that reason.
    if single.case.status not in (CASE_APPROVED, CASE_EXECUTING, CASE_OPEN):
        raise BillingRuleError(
            f"case {single.case.case_no or single.case.pk} is "
            f"{single.case.status!r}: nothing executes without a recorded {APPROVER_ROLE} "
            "approval (BR-BIL-014, and the gate is server-side — TC-4). The preview is "
            "an artifact, not a permission.",
            br_ref="BR-BIL-014",
        )
    return bulk_corrections.execute(
        single.case,
        issued_at=issued_at,
        on_date=on_date,
        template_id=template_id,
        template_version=template_version,
        actor=actor,
    )


def executed_artifacts(single: SingleCase) -> dict[str, Any]:
    """What the case ACTUALLY produced, re-read from the rows (BR-BIL-047).

    *"The case's own claim of success is checkable against what it produced"* —
    so every id here comes off `correction_case_bills` after execution rather
    than out of the return value, and the chain is re-walked from the database.
    A result table and a progress bar differ in exactly this.
    """
    row = _one_row(single.case)
    row.refresh_from_db()
    invoice = models.Invoice.objects.get(tenant_id=single.case.tenant_id, pk=row.invoice_id)
    return {
        "case_status": single.case.status,
        "bill_status": row.status,
        "failure_reason": row.failure_reason,
        "credit_note_id": str(row.credit_note_id) if row.credit_note_id else None,
        "rebill_invoice_id": str(row.rebill_invoice_id) if row.rebill_invoice_id else None,
        "document_instance_id": (
            str(row.document_instance_id) if row.document_instance_id else None
        ),
        "original_status": invoice.status,
        "chain": chain_of(invoice),
    }


# Re-exported by NAME, never re-implemented — see the module docstring. A
# caller that reaches for the single-bill door still gets the one gate, the one
# executor and the one abandon path.
approve = bulk_corrections.approve
abandon = bulk_corrections.abandon
resolve_scope = bulk_corrections.resolve_scope

__all__ = [
    "APPROVER_ROLE",
    "CLASS_CREDIT_ONLY",
    "CLASS_DOCUMENT",
    "CLASS_RESTATEMENT",
    "CASE_DONE",
    "OQ_CLASS_C_ARTIFACT",
    "PREVIEW_SECTIONS",
    "SingleCase",
    "abandon",
    "approve",
    "chain_of",
    "executed_artifacts",
    "execute_single",
    "nine_sections",
    "open_for_bill",
    "resolve_scope",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-015@f24bbae (sha256[:7] over the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-04-corrections.md US-BIL-015 §1/§1a/§1b/§7/§7a · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-041..048/064 · 08-qa/01-e2e/journeys/J6-corrections.md · 12-governance/01-open-questions.md OQ-104/OQ-120/OQ-121)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's correction endpoints are unbuilt and no correction route is mounted; REPORTED) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff · black · makemigrations --check · pytest · run_gates ·
#         10-scripts/03-golden-verify.py — see the lane report for the verbatim
#         RED transcripts (the immutability freeze on the new chain column, the
#         one-replacement-per-original constraint, and the BR-BIL-041 supplied-
#         mechanism guard were each broken deliberately, RUN, and the measured
#         failure quoted before any was trusted green — hard-won law 7)
# exceptions: (1) OQ-104 IS CLOSED AND THIS STORY IS NOT BLOCKED. EP-BIL-04's
#         frontmatter still reads `blocked_by: [OQ-104]` and TC-16 still asks
#         for a not-implemented stub against that id. The live registry
#         (12-governance/01-open-questions.md) records the PO closing it on
#         2026-08-11 with option A, and the refusal is BUILT
#         (`corrections.refuse_upward_beyond_window`). A not-implemented stub
#         against a CLOSED id is what G8 exists to catch. The stale frontmatter
#         is REPORTED and corrected in the epic in the same change.
#         (2) THE CLASS-C ARTIFACT QUESTION IS NOT DECIDED HERE — OQ-215, minted
#         by this lane. Two PO rulings of consecutive days disagree about
#         whether a goodwill concession moves THIS bill or the NEXT one; GT-6's
#         222.30 is reached either way. The preview STATES the question in its
#         §3 and the engine's existing reading is left untouched.
#         (3) NO API HALF. The S30 correction endpoints do not exist for the
#         bulk case either; adding routes for one shape and not the other would
#         make the single-bill path look like the supported one. REPORTED.
#         (4) THIS MODULE RE-EXPORTS `approve` / `abandon` / `resolve_scope`
#         RATHER THAN WRAPPING THEM. A wrapper is a second call site for a money
#         gate; a re-export is one.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections — the PER-BILL mechanics every bill in
#           a case goes through)   Screens: S30
# Rules:    BR-BIL-004 (the original invoice and its lines NEVER change — a
#           correction is new rows) · BR-BIL-014 (reason → scope → impact
#           preview → approval → staged idempotent execution → deliver + audit;
#           NO money-bearing write before approval) · BR-BIL-041 (the reason's
#           CLASS derives the mechanism) · BR-BIL-042 (strongest class wins) ·
#           BR-BIL-043 (a D-class case that moves money is REFUSED; an R-class
#           case at $0.00 still emits its pair and the preview FLAGS the zero) ·
#           BR-BIL-044 (the preview is a persisted content-hashed artifact;
#           drift refuses execution) · BR-BIL-045 (the posting period is named
#           before confirm) · BR-BIL-047 (one bill = one transaction; no batch
#           rollback) · BR-BIL-048 (only the latest document in a chain) ·
#           BR-BIL-018 (the back-bill window caps an UPWARD correction — PO
#           2026-08-11, OQ-104 option A) · BR-BIL-026 (the rebill pins a
#           template version at issue) · BR-BIL-011 (billing writes no journal
#           lines; it emits a handoff) · BR-TEN-043 (event time is an argument)
#           · CLAUDE.md rule 2 (money) · rule 4 (immutability) · rule 6
#           (idempotency) · rule 7 (audit)
# Golden:   WE-9 / **GT-25** shape (B5 ❄️ FROZEN): water read 8 → 6 kgal moves
#           an issued 247.87 to 227.95, a delta of −19.92. Nothing here mints a
#           figure — the engine recomputes through rating and the fixtures pin
#           the arithmetic B4/B5 already froze.
# Tests:    06-backend/tests/test_us_bil_016_bulk_corrections.py ·
#           06-backend/tests/test_cr101_lane_b_discount_panel.py (CR-101-BRC03
#           §06 — the step-2 DISCOUNTS panel, `discount_panel`)
# Impacts:  apps/billing/bulk_corrections.py (the case layer above this) ·
#           apps/billing/document_correction.py (the class-D artifact) ·
#           apps/billing/correction_models.py · apps/payments (consumes the
#           re-allocation plan this emits; billing never executes it)
# ───────────────────────────────────────────────────────
"""The per-bill correction: what it costs, what it writes, what it refuses.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 rating math, money rounding and the
ledger handoff all meet here, and every path writes money. AI-authored
2026-08-11 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
THE ORIGINAL BILL IS NEVER TOUCHED. NOT ONCE, NOT ANYWHERE, NOT EVEN A LINE.
════════════════════════════════════════════════════════════════════════════
Hard rule 4 and BR-BIL-004. There is no UPDATE of `invoices` money, no UPDATE of
`invoice_lines` and no DELETE of either in this module — a correction is a
CREDIT NOTE plus a REBILL, both new rows, and the original stays issued and
visible forever with byte-identical lines. The one column this module moves on
an original is `status` → `corrected`, which is the lifecycle column the `0002`
immutability trigger deliberately leaves mutable (issued → paid → corrected);
every frozen column — total, subtotal, tax, number, dates, template pin,
`bill_payload` — is refused by the database itself, and a test proves that
refusal RED rather than trusting this paragraph (hard-won law 1).

════════════════════════════════════════════════════════════════════════════
THREE MECHANISMS, DERIVED FROM THE REASON — never chosen (BR-BIL-041)
════════════════════════════════════════════════════════════════════════════
**R · restatement** — the money AND the document are wrong. Full credit note
(−original total, the whole bill reversed), a rebill for the recomputed amount,
the ledger handoff as TWO balanced entries (never one net entry: the credit note
reverses the original's own stamped buckets and the rebill posts its own), a
re-allocation plan for payments, and the original moves to `corrected`.

**C · credit-only (goodwill)** — nothing is wrong; the utility chooses to charge
less. **This is NOT a credit note against the bill.** The PO ruled it on
2026-08-11, verbatim:

    "A goodwill credit - that ia category, keep it there; it will exclude the
     tax; you dont touch the bill; you issue new a good will credit; everything
     remain as it is, it is new good will credit to be applied in new bill"

So the original bill, its lines, its revenue and its tax liability stand
untouched; a separate account-level credit is raised and consumed by a FUTURE
bill. The tax half answers itself — **no tax is credited back, because no line
is being reversed** — and `goodwill_credit_amount` refuses a request that tries
to include any. EP-BIL-04's older description of class C as *"a partial credit
note referencing the original"* is superseded by that ruling and is not what
this module does.

**D · document** — the money is right and the page is wrong. Zero rows of money
of any kind; the artifact is a reissued document instance and lives in
`document_correction.py`.

════════════════════════════════════════════════════════════════════════════
WHAT REFUSES, AND WHY EACH REFUSAL IS THE POINT
════════════════════════════════════════════════════════════════════════════
* A **D-class case whose recomputation moves money** (BR-BIL-043). The reason is
  wrong or the wrong bill was picked; either way a spelling must not put a
  credit on somebody's account.
* A **supplied mechanism** (`correction_reasons.refuse_supplied_mechanism`).
  Answering "wrong rate" with a reprint is a silent underbilling: the customer
  keeps the wrong amount and no gate ever fires.
* An **UPWARD correction older than the tenant's back-bill window** — PO
  2026-08-11 closing OQ-104 with option A, shown as *"a meter was read too low
  in 2023; correcting it bills the customer $1,840 for a period 30 months
  back."* The correction workflow is NOT a lawful route around a
  consumer-protection cap. Downward corrections are unaffected **at any age**,
  which is the asymmetry that made it finance's call and not engineering's.
* A **bill that is not the latest in its chain** (BR-BIL-048).
* **Execution before approval** — enforced by the case layer, which is where the
  gate record lives (US-BIL-017).

════════════════════════════════════════════════════════════════════════════
THE RECOMPUTATION WRITES NOTHING, AND THAT IS A RULE NOT AN OPTIMISATION
════════════════════════════════════════════════════════════════════════════
BR-BIL-014: *"NO money-bearing write before approval; the preview IS the
approval artifact."* So `recompute` goes gather → stages → `rating_seam.
price_bill` and stops — the same three calls `runs.calculate_account` makes,
minus `assemble_document`, which is the one that writes a draft. A preview that
drafted a bill would put an invoice row in the books for a correction nobody
had approved, and the S30 case list would be showing money that already existed.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DOES NOT DECIDE
════════════════════════════════════════════════════════════════════════════
* **The re-allocation.** Billing emits the PLAN (BR-BIL-014, EP-BIL-04 §5:
  *"plan emitted to payments; execution payments-owned"*); payments executes it.

⚠ **ONE ITEM WAS DELETED FROM THIS LIST ON 2026-09-02 (CR-059 task 8 / CS-38),
BECAUSE IT HAD BEEN ANSWERED ON 2026-08-12 AND THE CODE WAS ALREADY WRITTEN.**
It read, verbatim:

    "* **Which GL account a goodwill concession DEBITS.** OQ-105 was closed by
       changing the MECHANISM (above) and the credit side is settled — `2400
       customer_credit_balance` is one of the eleven ruled designations, and the
       decision log of 2026-08-11 says in as many words that this is where the
       goodwill ruling lands. The DEBIT side is not settled by that, and the
       registry still carries OQ-105's *"⚠ REDUCED FORM STILL OPEN"*. Worse, the
       two documents disagree about whether it is open at all. So class-C
       EXECUTION raises rather than choosing between a contra-revenue account, an
       expense account, and not posting until the credit is consumed — three
       answers with three different P&Ls. The PREVIEW is complete and the
       arithmetic is asserted."

**Every sentence of that was false at the moment it was read.** The PO ruled
the DEBIT side on 2026-08-12 (OQ-105 / OQ-168), verbatim *"a separate write-off
account"*; `credit_only_gl_accounts` below resolves it by designation, says so
in its own docstring, and `execute_credit_only` has posted the balanced pair
ever since — class-C execution does not raise and `refuse_credit_only_execution`
no longer exists. A paragraph describing a refusal that executes is hard-won
law 1 pointed the wrong way: it is not a stale comment about an absence, it is
a comment asserting an absence that is not there, and it sent readers away from
working code. It is kept here, quoted and dated, rather than deleted silently,
because the same expired sentence was quoted in two other places in this
product (`apps/customers/services.ACTION_UNAVAILABLE["issue_credit"]` and the
`customers.account.action.issueCreditBlocked` catalogue string) and a reader who
meets the old reading elsewhere should arrive at the correction here.

**WHAT IS STILL GENUINELY OPEN NEXT DOOR, AND IS NOT THIS:** `OQ-215` — whether
a class-C concession is a credit note that moves THIS bill's balance to 222.30,
or an account-level credit consumed by the NEXT bill while this bill still reads
247.30. ❄️ GT-6's **222.30** is reached either way, which is why nothing has
forced it. This module implements the second reading (`build_impact` forces the
class-C bill delta to ZERO) and `single_correction.py` cites the row at the
divergence. **Nothing in CR-059 resolves it and nothing here may.**
════════════════════════════════════════════════════════════════════════════
WHERE THE REBILL LINK LIVES — **RULED 2026-08-12, OQ-120 CLOSED**
════════════════════════════════════════════════════════════════════════════
The PO, verbatim: *"Nod to add the link on the new bill"*. `execute_restatement`
stamps `invoices.corrects_invoice_id` on the REBILL, pointing back at the
original, before the rebill is issued (migration `0017`). The direction is the
ruling: the original is immutable and must not gain a column after issue
(BR-BIL-004), while a rebill is still a draft when the link is written.

⚠ SUPERSEDED (PO 2026-08-11 → PO 2026-08-12, OQ-120). This paragraph used to
read, verbatim:

    "* **The account-level history log** the rebill link belongs in (PO
     2026-08-11, OQ-120 — *"in Histrory log only - at account level"*). That
     ruling explicitly left its STORAGE open (`audit_log`, or a distinct
     account-history record). So this module writes the link into the
     hard-rule-7 audit row it must write anyway, and adds no
     `corrects_invoice_id` column on the strength of BR-BIL-064."

It is kept because a reader who arrives at the old reading elsewhere in the
corpus should arrive at the correction with it. What changed: the audit row is
still written (rule 7 owes it) but it is no longer the ONLY carrier, because
BR-BIL-064's phase-4 panel must JOIN to the replacement and a panel cannot join
to a log — `release.summary_for` refused outright, naming this column, for as
long as it did not exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import (
    correction_reasons,
    delivery_seam,
    models,
    payments_seam,
    posting_seam,
    rating_seam,
    runs,
    single,
)
from apps.billing.correction_models import (
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    DIRECTION_DOWN,
    DIRECTION_UP,
    DIRECTION_ZERO,
)
from apps.billing.exceptions import BillingRuleError
from apps.billing.stages.measure_consumption import measure_consumption
from apps.billing.stages.resolve_subscription import resolve_subscription
from core import audit, money
from core import numbering as core_numbering
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: The unresolved question this module refuses rather than answers. See the
#: module docstring — OQ-105's reduced form has no live id of its own, and a
#: stub citing a CLOSED id is exactly what gate G8 rejects.
OQ_CONCESSION_DEBIT = "OQ-168"

#: BR-BIL-018's default window, cited not restated: the tenant setting is
#: r10 #6 / S71 and this module READS it. The constant is the documented
#: default for a tenant that has set nothing, and it fails CLOSED — twelve
#: months, the same number BR-BIL-018 carries — because an absent window read as
#: "no cap" would make the workflow the route around the cap OQ-104 just shut.
DEFAULT_BACKBILL_WINDOW_MONTHS = 12

#: Warning codes carried on an impact. CODES, never prose: the S30 preview
#: groups on them and the aggregate counts warned rows (BR-BIL-046), and a
#: screen cannot group on a sentence.
WARN_ZERO_DELTA_ON_RESTATEMENT = "restatement_nets_to_zero"
WARN_CLOSED_PERIOD = "posting_period_is_not_the_bill_period"
WARN_UPWARD = "correction_increases_what_the_customer_owes"
WARN_PAID_IN_FULL = "bill_already_paid_in_full"

#: CR-059 CS-37 · task 27 — the credit note's own number, minted from the
#: tenant's **Credit memo #** series.
#:
#: ⚠ **THE TIMING QUESTION IN `models.CreditNote.credit_note_no` IS ANSWERED,
#: AND THIS IS THE ANSWER.** That column's comment read *"Timing UNRULED for
#: credit notes … EP-BIL-04 is W5 and nothing writes this column yet"*, and
#: CS-37 rules it in one sentence: a credit note **takes its number from the
#: tenant's Credit memo series at creation, in the same transaction as the row,
#: and never afterwards.** Both writers below are already `@transaction.atomic`,
#: so "in the same transaction" costs nothing and BR-TEN-035's allocation law —
#: `SELECT … FOR UPDATE` on the series row, gaps acceptable, a number never
#: reused — holds without any further ceremony: a rolled-back correction rolls
#: the counter back with the row it would have numbered.
#:
#: **THE DATE IS AN ARGUMENT, NEVER A CLOCK** (BR-TEN-043, gate G6). The caller
#: passes the correction's own `issued_at`, which is the credit note's
#: `issued_at`, so a backdated correction numbers under ITS date and the number
#: is reproducible on a replay years later. `CM-{0000}` — the seeded default at
#: `core/numbering.py:317` — carries no date token, so on an untouched tenant
#: this changes nothing; it matters the moment an admin picks `CR-{YYYY}-{000}`.
#:
#: **A MISSING SERIES ROW IS REPORTED, NEVER FAKED, AND NEVER STOPS THE
#: CORRECTION.** This is `runs._allocate_run_no`'s posture applied one table
#: along, and CS-37's own rule is what makes it safe: *"historic rows keep a
#: null number; they are NOT back-filled"*, so a numberless credit note is
#: already a state every reader must handle. Refusing the correction over a
#: settings gap would stop a utility fixing a wrong bill — and refusing AFTER
#: the ledger pair had posted would be worse. The absence travels on the
#: posting's `audit_context` (hard rule 7) under `numbering_series_missing`,
#: the same code `create_run` uses, so one grep finds every unnumbered document
#: in the product.
CREDIT_NOTE_SERIES_MISSING = "numbering_series_missing"


def _allocate_credit_note_no(issued_at: datetime) -> tuple[str | None, str | None]:
    """The next `CM-` number for this tenant, or `(None, reason-code)`.

    Returns a pair rather than raising: see `CREDIT_NOTE_SERIES_MISSING` above
    for why a settings gap may not stop a correction. The second element is a
    CODE and never prose — it reaches an audit row and, through it, a support
    line; B14 rule 32 keeps rule ids and internal codes off clerk-facing copy,
    so no screen prints it.
    """
    try:
        return core_numbering.next_number(core_numbering.CREDIT_MEMO, issued_at.date()), None
    except core_numbering.NumberingError:
        return None, CREDIT_NOTE_SERIES_MISSING


#: G3 (PO 2026-10-14) — the case number's own absence code when the series row
#: refuses to number BACKWARDS across its yearly restart (a Send dated last
#: December after this year's first case). `allocate_series_number` refuses it
#: by name; the case is left unnumbered for that reason rather than the
#: missing-series one, so the audit row says which it was.
CASE_NUMBER_BACKDATED = "numbering_restart_backdated"
#: A Send with no business date to number under (a background preview row
#: written before `as_of` was stored). Never guessed from a clock (BR-TEN-043).
CASE_NUMBER_DATE_MISSING = "numbering_date_missing"


def allocate_case_no(on_date: date | None) -> tuple[str | None, str | None]:
    """The next `CC-` number for this tenant's correction case, or
    `(None, reason-code)` — G3, PO ruling 2026-10-14 (`DEF-BIL-10147`).

    Ruling, verbatim: *"a correction case takes its number at Send from a new
    tenant series "Correction case", default `CC-{YYYY}-{000}` … a deleted
    series leaves the case unnumbered and is never blocking (the credit-memo
    precedent)"*. So this is `_allocate_credit_note_no` one series along:

    * called INSIDE the transaction that writes the case (`correction_items.
      _open_case` and `bulk_corrections.open_case` are both atomic), so
      BR-TEN-035's `SELECT … FOR UPDATE` on the series row serialises two
      concurrent Sends and a rolled-back Send rolls its number back with it;
    * the date is the Send's own `as_of` (BR-TEN-043, gate G6), never a clock,
      which is what `{YYYY}` and the yearly restart read;
    * a refusal is returned as a CODE, never raised — the caller records it on
      the case's audit row and the case opens unnumbered.
    """
    if on_date is None:
        return None, CASE_NUMBER_DATE_MISSING
    try:
        return core_numbering.next_number(core_numbering.CORRECTION_CASE, on_date), None
    except core_numbering.NumberingError as gap:
        if str(gap).startswith(CASE_NUMBER_BACKDATED):
            return None, CASE_NUMBER_BACKDATED
        return None, CREDIT_NOTE_SERIES_MISSING


@dataclass(frozen=True)
class LineImpact:
    """One line, original → corrected → Δ (BR-BIL-044 §2).

    Present for EVERY line including the ones that did not move, and `moved` is
    a stored fact rather than a `delta != 0` the reader has to compute. The
    epic's reason: *"a preview that shows only movement cannot be checked"* —
    "only water and sewer changed" is a claim the approver must be able to
    verify, not take.
    """

    key: str
    label: str
    kind: str
    original: Decimal
    corrected: Decimal
    delta: Decimal
    moved: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "original": str(self.original),
            "corrected": str(self.corrected),
            "delta": str(self.delta),
            "moved": self.moved,
        }


@dataclass(frozen=True)
class BillImpact:
    """What one correction would do to one bill — the nine-section preview.

    Persisted on `correction_case_bills.impact` and hashed into the case's
    `preview_hash`; approval binds THIS, and execution refuses on drift
    (BR-BIL-044).
    """

    invoice_id: str
    invoice_no: str | None
    account_id: str
    correction_class: str
    reason_codes: tuple[str, ...]
    currency: str
    lines: tuple[LineImpact, ...]
    original_total: Decimal
    corrected_total: Decimal
    delta: Decimal
    #: (label, original, corrected, delta) per authority — shown separately
    #: because tax moves a liability owed to a third party (BR-LED-002).
    tax_by_authority: tuple[tuple[str, Decimal, Decimal, Decimal], ...]
    documents: tuple[str, ...]
    posting_period: date | None
    balance_before: Decimal | None
    balance_after: Decimal | None
    reallocation_plan: tuple[str, ...]
    #: CR-059 CS-36 · task 20 — the SETTLEMENT panel's four figures, or None
    #: when payments could not be asked. RESTATEMENT only; see
    #: `settlement_preview` for the arithmetic and why None is not zeroes.
    settlement: dict[str, Any] | None = None
    warnings: tuple[dict[str, Any], ...] = ()
    #: BR-BIL-041's sentence, in the operator's words rather than as an enum.
    mechanism: str = ""
    #: `CR-101-BRC03` §06 — THE DISCOUNTS PANEL, drawn on every class and
    #: never omitted (p129: *"An absent panel is drawn, never omitted"*). What
    #: reduced the original bill, what reduces the corrected one, which
    #: programme VERSION each line names, and the outcome as a CODE. Part of
    #: `as_dict`, so it is inside the content hash approval binds. See
    #: `discount_panel` for the shape and for what it cannot know.
    discounts: dict[str, Any] = field(default_factory=dict)

    @property
    def direction(self) -> str:
        if self.delta > ZERO:
            return DIRECTION_UP
        if self.delta < ZERO:
            return DIRECTION_DOWN
        return DIRECTION_ZERO

    def as_dict(self) -> dict[str, Any]:
        """The persisted shape. Money as STRINGS — a Decimal through JSON
        becomes a float and CLAUDE.md rule 2 forbids money ever being one."""
        return {
            "invoice_id": self.invoice_id,
            "invoice_no": self.invoice_no,
            "account_id": self.account_id,
            "class": self.correction_class,
            "mechanism": self.mechanism,
            "reason_codes": list(self.reason_codes),
            "currency": self.currency,
            "lines": [line.as_dict() for line in self.lines],
            "original_total": str(self.original_total),
            "corrected_total": str(self.corrected_total),
            "delta": str(self.delta),
            "direction": self.direction,
            "tax_by_authority": [
                {
                    "authority": label,
                    "original": str(was),
                    "corrected": str(now),
                    "delta": str(delta),
                }
                for label, was, now, delta in self.tax_by_authority
            ],
            "documents": list(self.documents),
            "posting_period": self.posting_period.isoformat() if self.posting_period else None,
            "balance_before": (
                str(self.balance_before) if self.balance_before is not None else None
            ),
            "balance_after": (str(self.balance_after) if self.balance_after is not None else None),
            "reallocation_plan": list(self.reallocation_plan),
            # CR-059 CS-36 · task 20. `null` on a mechanism that releases
            # nothing AND on a restatement payments could not be asked about —
            # the screen tells those apart by the `class`, never by guessing.
            "settlement": dict(self.settlement) if self.settlement is not None else None,
            "warnings": [dict(warning) for warning in self.warnings],
            # CR-101-BRC03 §06 — drawn on every class; the CODE says which
            # shape (`discount_panel`). Inside the hash, so approval binds it.
            "discounts": dict(self.discounts),
        }


@dataclass(frozen=True)
class ExecutedBill:
    """What ONE bill's execution actually produced (BR-BIL-047).

    Every id here is checkable against a row. The case does not get to claim
    success and leave the artifacts unnamed — that is the difference between a
    result table and a progress bar.
    """

    invoice_id: str
    credit_note_id: str | None = None
    rebill_invoice_id: str | None = None
    goodwill_adjustment_id: str | None = None
    document_instance_id: str | None = None
    #: CR-059 CS-36 — what came OFF the original so the rebill could draw on it
    #: (BR-PAY-1072). A POSITIVE magnitude, `None` on a mechanism that releases
    #: nothing, and 0.00 on a restatement of a bill nobody had paid. Three
    #: distinct facts and a screen must not render them the same way: S30's
    #: settlement panel (CR-059 task 20) reads exactly this.
    released_amount: Decimal | None = None
    released_rows: tuple[dict[str, Any], ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _tenant_id() -> Any:
    """Hard rule 1: never touch a tenant table without `app.tenant_id` set."""
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _line_key(kind: str, service_code: Any, tax_id: Any, description: str) -> str:
    """How an original line is matched to its recomputed counterpart.

    On IDENTITY (kind + service + tax), never on the description — a tenant may
    reword "Water usage" between July and September and the line is still the
    same line. The description is the fallback for kinds that carry neither
    (a fee), where it is the only identity there is.
    """
    if tax_id:
        return f"tax:{tax_id}"
    if service_code:
        return f"{kind}:{service_code}"
    return f"{kind}:{description.strip().lower()}"


def recompute(invoice: models.Invoice) -> rating_seam.RatedBill:
    """Re-price the bill from TODAY's inputs. **Writes nothing.**

    This is the correction's whole arithmetic: the corrected read is already in
    metering (BR-MET-053 superseded it before anyone opened a case), the tariff
    version is whatever now governs the bill's service date, and re-pricing the
    same period against those inputs IS the recomputation. Nothing here adjusts
    a figure by hand — US-BIL-015 §7 is CONFIRMED against WE-9 and this engine
    reproduces it by pricing, not by arithmetic of its own.

    The three calls are `runs.calculate_account`'s first three, deliberately
    stopping before `assemble_document` — see the module docstring on why a
    preview may not draft a bill.
    """
    scope = single.billable_account(invoice.account_id)
    # 🔒 DEF-2430 — priced AS IF this bill had granted nothing: the executed
    # correction gives the original's discount grants back before its rebill
    # is priced, so a preview that still counted them would show a smaller
    # discount (a capped one at $0.00) than the correction then issues.
    with rating_seam.grants_excluded(invoice.pk):
        data = single.gather_single(
            scope,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            service_date=invoice.service_date,
            cycle_days=(invoice.period_end - invoice.period_start).days + 1,
        )
    subscription = resolve_subscription(data)
    usage = measure_consumption(subscription, data)
    return rating_seam.price_bill(
        services=tuple((service.tariff, service.consumption) for service in usage.measured),
        base_only_services=tuple(service.tariff for service in usage.unmeasured),
        period=subscription.period,
        account=rating_seam.AccountContext(
            currency=subscription.currency, tax_exempt=subscription.tax_exempt
        ),
        taxes=subscription.taxes,
        fees=subscription.fees,
        # DEF-537 — THE ARGUMENT THAT WAS MISSING, AND ITS ABSENCE WAS SILENT.
        # `gather` has resolved the account's granted discounts since DEF-502
        # (enrolment ∩ plan binding, BR-RAT-069/110) and `resolve_subscription`
        # has carried them onto `subscription.discounts` the whole time; this
        # call simply did not pass them. So a corrected period for an enrolled
        # customer re-priced at FULL TARIFF while the original bill carried the
        # reduction — the correction would have handed the customer back less
        # than they were owed, or billed them more, by exactly the discount.
        # Both ends built, the CALL missing: hard-won law 2, one door over from
        # DEF-502 itself.
        #
        # RESOLVED AS OF THE CORRECTED PERIOD'S OWN SERVICE DATE, not today's —
        # `gather_single` above is handed `invoice.service_date`, which is
        # BR-RAT-007's pivot and the same one the tariff version resolves on. A
        # September correction of a July bill therefore reproduces JULY's
        # enrolment and JULY's programme version, which is exactly why
        # `discount_grants` stamps `discount_version_id`.
        discounts=getattr(subscription, "discounts", ()),
    )


def goodwill_credit_amount(*, amount: Decimal, tax_included: bool = False) -> Decimal:
    """A class-C concession, **excluding tax** — PO 2026-08-11, verbatim
    *"it will exclude the tax"*.

    The rule is not a rounding convenience. No line of the original bill is
    being reversed, so the utility's remittance basis is unchanged and there is
    no tax to credit back: a concession that carried tax would reduce a
    liability actually owed to an authority whether or not the utility chose to
    be generous. A caller asserting its figure INCLUDES tax is refused rather
    than having the tax stripped by a guess, because only the caller knows
    which authorities and which rates went into it.
    """
    if tax_included:
        raise BillingRuleError(
            "a goodwill credit EXCLUDES tax (PO 2026-08-11, OQ-105). Nothing on the "
            "original bill is reversed, so no tax comes back — the amount handed over is "
            "the credit itself, gross of nothing. Splitting a tax-inclusive figure here "
            "would need this module to pick rates and authorities it was never told.",
            br_ref="BR-BIL-041",
        )
    credit = money.finalize(amount)
    if credit <= ZERO:
        raise BillingRuleError(
            f"a goodwill credit of {credit} is not a concession. A credit-only correction "
            "reduces what the customer pays; zero changes nothing and a negative one is a "
            "charge wearing a credit's name.",
            br_ref="BR-BIL-041",
        )
    return credit


def _tax_split(
    original_lines: list[models.InvoiceLine], corrected: rating_seam.RatedBill
) -> tuple[tuple[str, Decimal, Decimal, Decimal], ...]:
    """Tax, per authority, original → corrected → Δ (BR-BIL-044 §3).

    Never one summed tax figure: four authorities are four debts and four
    returns (BR-LED-002), and a preview that showed −1.72 without saying whose
    would hide which remittance basis moved.
    """
    was: dict[str, Decimal] = {}
    labels: dict[str, str] = {}
    for line in original_lines:
        if line.kind != "tax":
            continue
        key = str(line.tax_id) if line.tax_id else line.description
        was[key] = money.finalize(was.get(key, ZERO) + line.amount)
        labels[key] = line.description
    now: dict[str, Decimal] = {}
    for rated in corrected.lines_of("tax"):
        key = str(rated.tax_id) if rated.tax_id else rated.description
        now[key] = money.finalize(now.get(key, ZERO) + rated.amount)
        labels.setdefault(key, rated.description)
    return tuple(
        (
            labels[key],
            was.get(key, ZERO),
            now.get(key, ZERO),
            money.finalize(now.get(key, ZERO) - was.get(key, ZERO)),
        )
        for key in sorted(set(was) | set(now), key=lambda k: labels[k])
    )


def _paid_in_full_warning(invoice: models.Invoice, *, currency: str) -> dict[str, Any] | None:
    """`bill_already_paid_in_full` — the warning the code defined and never raised.

    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  CR-059 CS-36, task 14. THE CHEAP HALF, DELIBERATELY SHIPPED FIRST.      ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    `WARN_PAID_IN_FULL` has existed since this module was written and **nothing
    ever appended it to a warnings list**, so a clerk correcting a bill the
    customer has already settled was shown warnings about upward corrections
    and closed posting periods and *nothing at all* about the payment. It moves
    no money and changes no schema; it puts the fact in front of the one person
    placed to notice that the figures afterwards are wrong (CS-36's own
    reasoning, verbatim: *"it will not fix anything, but it puts the fact in
    front of the clerk"*).

    **THE TWO FIGURES ARE ASKED FOR, NEVER COMPUTED HERE.**
      * what the bill ASKS — `selectors.amount_due_for`, which is the total for
        an ordinary bill and the LEVEL for a budget-billing one (BR-BIL-072,
        PO 2026-08-11 *"Level is due"*). Using `invoice.total` instead would
        call ❄️ WE-8's 292.87 bill unpaid when the customer had paid the 242.00
        it asked for — DEF-2416 in a new place, and the second definition of
        "settled" that CS-36's whole defect is made of.
      * what has been PAID — payments' own `allocated_so_far` through the seam,
        NET of the negative mirror rows a bounce or a release writes.

    **RESTATEMENT ONLY, AND THAT IS A BOUNDARY NOT AN OVERSIGHT.** A goodwill
    concession leaves the bill untouched (PO 2026-08-11) and a document
    correction moves $0.00, so on neither does an existing payment have
    anywhere to go wrong. The warning is raised where a payment is about to be
    left pointing at a bill that is being replaced.

    **AN UNREACHABLE SEAM RAISES NOTHING RATHER THAN THE OPPOSITE WARNING.**
    `None` from the seam means *nobody could ask*, not *nothing was paid*
    (see `payments_seam.allocated_against_invoice`), and a warning list that
    silently said "unpaid" on an unreadable seam would be worse than the
    silence this closes.
    """
    from apps.billing import payments_seam, selectors

    allocated = payments_seam.allocated_against_invoice(invoice.pk)
    if allocated is None:
        return None
    asked = money.finalize(selectors.amount_due_for(invoice))
    applied = money.finalize(allocated)
    if asked <= ZERO or applied < asked:
        return None
    return {
        "code": WARN_PAID_IN_FULL,
        # The ids live in the STRUCTURED field, never in the sentence a clerk
        # reads (B14 rule 31/32, ratified 2026-08-31).
        "br_ref": "BR-BIL-014 · BR-PAY-010 · BR-BIL-072",
        "detail": f"this bill has already been paid in full — {applied} {currency} has been "
        f"applied against the {asked} {currency} it asks for. A restatement credits this bill "
        "and issues a replacement in its place, so the money that met this one has to meet "
        "the replacement instead.",
    }


def settlement_preview(
    invoice: models.Invoice, *, currency: str, corrected_total: Decimal
) -> dict[str, Any] | None:
    """WHAT HAPPENS TO THE MONEY THAT ALREADY MET THIS BILL — CR-059 CS-36, task 20.

    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  THE SETTLEMENT PANEL CS-36 ASKS FOR, AS DATA: paid to date · what the   ║
    ║  replacement takes · what returns to credit · what is still owed.        ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    **These four figures are computed HERE and never on a screen.** S30 already
    draws money it is given; a frontend that subtracted `corrected_total` from a
    payment would be a second definition of "settled", which is the shape of
    CS-36's own defect (DEF-2416, one bill along).

    **THE ARITHMETIC IS CS-36's OWN, and its three worked cases are the test.**
    A restatement releases what the payment put against this bill
    (`BR-PAY-1072`), the released money joins whatever the account already holds,
    and the replacement's issue draws that down (`credit.apply_credit_at_issue`,
    which already exists and is already called):

        available   = released + credit already on account (never below 0)
        takes       = min(available, corrected_total)
        to credit   = available − takes
        still owed  = corrected_total − takes

    ❄️ CS-36's cases, all three:
      * **down** — 100.00 paid, corrected to 80.00 → takes 80.00, credit 20.00,
        owed **0.00**;
      * **up** — 100.00 paid, corrected to 120.00 → takes 100.00, credit 0.00,
        owed **20.00** (on the replacement, due on the correction date plus the
        days to pay — PO 2026-10-13; it read "the ORIGINAL due date" before);
      * **part-paid** — 60.00 of 100.00, corrected to 80.00 → takes 60.00,
        credit 0.00, owed **20.00**.

    **A DEBT SETTLES NOTHING.** `credit_position_for_account` returns a SIGNED
    figure and does not floor it (BR-PAY-041, PO 2026-08-11 *"Yes, it's a real
    debt"*) — its own docstring says the caller decides. A negative position is
    money the customer owes; it cannot pay for the replacement, so it is floored
    at zero HERE and the debt keeps existing where it is recorded.

    **`None` MEANS NOBODY COULD ASK, AND IT IS NOT ZEROES.** Either seam read
    answering `None` means payments could not be reached (`payments_seam`'s own
    posture), and a panel that printed 0.00 over that would tell a clerk the
    customer had paid nothing. RESTATEMENT only: a goodwill concession and a
    document correction move no bill, so no payment has anywhere to go wrong —
    the same boundary `_paid_in_full_warning` draws, for the same reason.
    """
    from apps.billing import payments_seam

    allocated = payments_seam.allocated_against_invoice(invoice.pk)
    if allocated is None:
        return None
    position = payments_seam.credit_position_for_account(invoice.account_id)
    if position is None:
        return None

    released = money.finalize(allocated)
    on_account = money.finalize(position)
    usable = on_account if on_account > ZERO else ZERO
    available = money.finalize(released + usable)
    target = money.finalize(corrected_total)
    takes = available if available < target else target
    return {
        "currency": currency,
        # What has met THIS bill, net of the negative mirror rows a bounce or an
        # earlier release already wrote (`allocated_so_far` is a NET sum).
        "paid_to_date": str(released),
        # The same figure under the name the release gives it. Two names for one
        # number on purpose: the panel says "100.00 comes off this bill" and
        # "100.00 was paid", and a clerk should not have to infer they are one.
        "released": str(released),
        # SIGNED, as payments serves it — a screen that showed only the floored
        # value could not say the customer is in debt.
        "credit_on_account": str(on_account),
        "available": str(available),
        "rebill_takes": str(money.finalize(takes)),
        "returns_to_credit": str(money.finalize(available - takes)),
        "still_owed": str(money.finalize(target - takes)),
    }


#: The line kind the engine gives a reduction (`apps/rating/pricing/stages/
#: apply_discounts.py`, `KIND_DISCOUNT`) and the kind `issue.py` designates
#: to the contra-revenue account. Named here rather than imported: rating is
#: not imported by this module (B1), and the kind is part of the line contract
#: both sides already share by name.
LINE_KIND_DISCOUNT = "discount"

#: `discount_panel` OUTCOMES — a CODE the screen renders in the clerk's own
#: language (the shape `warnings` already uses; `DEF-BIL-5267` is what a
#: server-composed sentence on the approval surface costs). p129's DISCOUNTS
#: column, one code per drawn cell:
#:   26.1 / 26.2 / 26.3 (class R) — *"On both bills" + which version* → the
#:        first four, depending on where the reduction actually is;
#:   26.4 goodwill (class C) — *"Nothing is re-priced"*;
#:   26.5 the page only (class D) — *"Unchanged"*.
DISCOUNTS_ON_BOTH = "on_both_bills"
DISCOUNTS_ORIGINAL_ONLY = "on_the_original_only"
DISCOUNTS_CORRECTED_ONLY = "on_the_corrected_bill_only"
DISCOUNTS_NONE = "none_on_either"
DISCOUNTS_NOT_REPRICED = "nothing_is_repriced"
DISCOUNTS_UNCHANGED = "unchanged"
#: How the VERSION on each row was arrived at. There is exactly one basis
#: today and it is stated rather than implied — see `discount_panel`.
DISCOUNT_VERSION_BASIS = "in_force_on_service_date"
#: The panel's problem code when rating has not published the version read.
DISCOUNT_VERSIONS_UNAVAILABLE = "discount_versions_unavailable"


def _discount_lines(lines: Any) -> list[tuple[str, Decimal]]:
    """`(label, amount)` for every DISCOUNT line, in emitted order.

    Works over `invoice_lines` rows and over the seam's `RatedLine`s alike —
    both carry `kind`, `description` and `amount`, which is all a reduction
    carries across either boundary. Amounts are the line's own (NEGATIVE:
    BR-RAT-068, *"its own line, beside the full tariff amount"*), finalized
    the way every other figure on the preview is (`money.finalize`, once).
    """
    return [
        (str(getattr(line, "description", "") or ""), money.finalize(Decimal(line.amount)))
        for line in (lines or ())
        if getattr(line, "kind", None) == LINE_KIND_DISCOUNT
    ]


def discount_panel(
    invoice: models.Invoice,
    *,
    correction_class: str,
    lines: Any,
    corrected: rating_seam.RatedBill | None,
) -> dict[str, Any]:
    """`CR-101-BRC03` §06 — the DISCOUNTS panel of the step-2 preview.

    p129's case table draws discounts in all five step-2 variants and rules
    that *"an absent panel is drawn, never omitted"*, so this returns a panel
    for EVERY class and says with a CODE which shape it is:

    * **class R (restatement)** — the reductions on the ORIGINAL bill (its own
      `discount` lines) beside the reductions on the CORRECTED bill (the
      engine's `discount` lines from the recomputation), each with the
      programme and the VERSION it names, and `outcome` says whether they are
      on both bills, one, or neither. `26.2`'s *"each month on its own
      enrolment"* is this panel once per bill — the version is resolved at
      EACH bill's own service date, so a July bill and an August bill in one
      case can name two versions of one programme.
    * **class C (goodwill)** — `nothing_is_repriced`: the bill is untouched
      (PO 2026-08-11), so `corrected` IS `original` and the delta is 0.00.
    * **class D (the page only)** — `unchanged`, for the same reason.

    **WHAT THIS PANEL KNOWS AND WHAT IT CANNOT.** A discount reaches a bill as
    a LINE whose label is the programme's bill line label (DIS-02 step 1) and
    nothing else: `invoice_lines` has no discount FK, the priced line carries
    no code, and `discount_grants` — the row BR-BIL-792 and this module's own
    `recompute` comment said *"stamps `discount_version_id`"* — is written by
    nothing on the bill path (`record_grant` has no caller; measured
    2026-09-15, `DEF-BIL-5341`). So the identity is the LABEL, resolved
    through `rating_seam.discount_versions_for_labels` at the bill's SERVICE
    DATE — BR-RAT-007's pivot, the same day the run priced it on — and every
    row says so in `version_basis`. That is a reconstruction, not a stamp: it
    is what was in force that day as the catalogue reads today. A label that
    names no programme, or two, or one with no version in force that day,
    comes back with null version fields and a `reason`, never dropped.

    No money is computed here beyond summing the lines the engine already
    priced — the totals exist so a reader can tie the panel to `the_lines`.
    """
    original_rows = _discount_lines(lines)
    if correction_class == CLASS_RESTATEMENT:
        corrected_rows = _discount_lines(getattr(corrected, "lines", ()) if corrected else ())
        if original_rows and corrected_rows:
            outcome = DISCOUNTS_ON_BOTH
        elif original_rows:
            outcome = DISCOUNTS_ORIGINAL_ONLY
        elif corrected_rows:
            outcome = DISCOUNTS_CORRECTED_ONLY
        else:
            outcome = DISCOUNTS_NONE
    else:
        # The bill is not re-priced on either of these mechanisms, so what
        # reduces the corrected bill is exactly what reduced the original.
        corrected_rows = list(original_rows)
        outcome = (
            DISCOUNTS_NOT_REPRICED if correction_class == CLASS_CREDIT_ONLY else DISCOUNTS_UNCHANGED
        )

    problems: list[dict[str, Any]] = []
    labels = sorted({label for label, _ in original_rows} | {label for label, _ in corrected_rows})
    versions: dict[str, dict[str, Any]] = {}
    if labels:
        answered = rating_seam.discount_versions_for_labels(labels, invoice.service_date)
        if answered is None:
            problems.append(
                {
                    "code": DISCOUNT_VERSIONS_UNAVAILABLE,
                    "br_ref": "BR-RAT-007",
                    "detail": "rating has not published the read that names which programme "
                    "version a discount line belongs to, so the version column is empty "
                    "for every line. The amounts are the bills' own and are unaffected.",
                }
            )
        else:
            versions = answered

    def _entry(label: str, amount: Decimal) -> dict[str, Any]:
        found = versions.get(label) or {}
        return {
            "label": label,
            "amount": str(amount),
            "code": found.get("code"),
            "version_id": found.get("version_id"),
            "version_no": found.get("version_no"),
            "effective_from": found.get("effective_from"),
            "reason": found.get("reason"),
        }

    original_total = money.finalize(sum((amount for _, amount in original_rows), ZERO))
    corrected_total = money.finalize(sum((amount for _, amount in corrected_rows), ZERO))
    return {
        "outcome": outcome,
        "original": [_entry(label, amount) for label, amount in original_rows],
        "corrected": [_entry(label, amount) for label, amount in corrected_rows],
        "original_total": str(original_total),
        "corrected_total": str(corrected_total),
        "delta": str(money.finalize(corrected_total - original_total)),
        "currency": invoice.currency,
        "service_date": invoice.service_date.isoformat() if invoice.service_date else None,
        "version_basis": DISCOUNT_VERSION_BASIS,
        "problems": problems,
    }


def build_impact(
    invoice: models.Invoice,
    *,
    reason_codes: tuple[str, ...],
    correction_class: str,
    corrected: rating_seam.RatedBill | None = None,
    posting_period: date | None = None,
    goodwill_amount: Decimal | None = None,
    balance_before: Decimal | None = None,
    mechanism: object = None,
) -> BillImpact:
    """The nine-section preview for ONE bill. Writes nothing, decides nothing.

    `mechanism` exists only to be REFUSED (BR-BIL-041) — a caller that supplies
    one is told the mechanism is derived from the reason. It is a parameter
    rather than an absence so the refusal has somewhere to happen and a test can
    prove it RED; see `correction_reasons.refuse_supplied_mechanism`.
    """
    correction_reasons.refuse_supplied_mechanism(mechanism)
    lines = list(
        models.InvoiceLine.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice).order_by(
            "created_at", "id"
        )
    )
    currency = invoice.currency
    original_total = money.finalize(invoice.total)

    if correction_class == CLASS_RESTATEMENT:
        if corrected is None:
            corrected = recompute(invoice)
        corrected_total = money.finalize(corrected.total)
        by_key: dict[str, list[Any]] = {}
        for line in lines:
            key = _line_key(line.kind, line.service_id, line.tax_id, line.description)
            entry = by_key.setdefault(key, [line.description, line.kind, ZERO, ZERO])
            entry[2] = money.finalize(entry[2] + line.amount)
        for rated in corrected.lines:
            key = _line_key(rated.kind, rated.service, rated.tax_id, rated.description)
            entry = by_key.setdefault(key, [rated.description, rated.kind, ZERO, ZERO])
            entry[3] = money.finalize(entry[3] + rated.amount)
        impact_lines = tuple(
            LineImpact(
                key=key,
                label=str(label),
                kind=str(kind),
                original=was,
                corrected=now,
                delta=money.finalize(now - was),
                moved=money.finalize(now - was) != ZERO,
            )
            for key, (label, kind, was, now) in by_key.items()
        )
        taxes = _tax_split(lines, corrected)
        documents = (
            f"credit note reversing {invoice.invoice_no or invoice.pk} in full "
            f"({-original_total} {currency})",
            f"rebill for {corrected_total} {currency}, citing the original",
        )
    elif correction_class == CLASS_CREDIT_ONLY:
        credit = goodwill_credit_amount(amount=goodwill_amount or ZERO)
        corrected_total = original_total  # the bill does NOT move — PO 2026-08-11
        impact_lines = tuple(
            LineImpact(
                key=_line_key(line.kind, line.service_id, line.tax_id, line.description),
                label=line.description,
                kind=line.kind,
                original=money.finalize(line.amount),
                corrected=money.finalize(line.amount),
                delta=ZERO,
                moved=False,
            )
            for line in lines
        )
        taxes = tuple(
            (line.description, money.finalize(line.amount), money.finalize(line.amount), ZERO)
            for line in lines
            if line.kind == "tax"
        )
        documents = (
            f"goodwill credit of {credit} {currency} on the ACCOUNT — no credit note, no "
            "rebill; the bill is untouched and the credit comes off a future bill",
        )
    else:  # CLASS_DOCUMENT — the money does not move and must be SHOWN not to
        corrected_total = original_total
        impact_lines = tuple(
            LineImpact(
                key=_line_key(line.kind, line.service_id, line.tax_id, line.description),
                label=line.description,
                kind=line.kind,
                original=money.finalize(line.amount),
                corrected=money.finalize(line.amount),
                delta=ZERO,
                moved=False,
            )
            for line in lines
        )
        taxes = tuple(
            (line.description, money.finalize(line.amount), money.finalize(line.amount), ZERO)
            for line in lines
            if line.kind == "tax"
        )
        documents = ("one reissued document instance — no credit note, no rebill, no posting",)

    delta = money.finalize(corrected_total - original_total)
    if correction_class == CLASS_CREDIT_ONLY:
        # The BILL's delta is zero; what moves is the account credit. Both are
        # shown, and they are not the same number — conflating them is how a
        # concession would look like a restatement on the S30 list.
        delta = ZERO

    warnings: list[dict[str, Any]] = []
    if correction_class == CLASS_RESTATEMENT and delta == ZERO:
        warnings.append(
            {
                "code": WARN_ZERO_DELTA_ON_RESTATEMENT,
                "br_ref": "BR-BIL-043",
                "detail": "the lines moved but the total did not. This is not a refusal — "
                "a rate fix that raises water by exactly what it lowers sewer is real — "
                "but an approver seeing a $0.00 delta must be told the pair is still "
                "emitted and the ledger buckets still move.",
            }
        )
    if delta > ZERO:
        warnings.append(
            {
                "code": WARN_UPWARD,
                "br_ref": "BR-BIL-018",
                "detail": f"this correction increases what the customer owes by {delta} "
                f"{currency}. The BR-BIL-018 back-bill window applies to an upward "
                "correction (PO 2026-08-11, OQ-104) — the workflow is not a route around "
                "the cap.",
            }
        )
    if correction_class == CLASS_RESTATEMENT:
        paid = _paid_in_full_warning(invoice, currency=currency)
        if paid is not None:
            warnings.append(paid)
    if posting_period is not None and posting_period != invoice.service_date:
        warnings.append(
            {
                "code": WARN_CLOSED_PERIOD,
                "br_ref": "BR-BIL-045",
                "detail": f"the bill's period is {invoice.service_date} and the entries "
                f"will land in {posting_period} (BR-TEN-038: a closed period posts to the "
                "earliest open one). A tax delta therefore moves a remittance basis in a "
                "month that has already been filed.",
            }
        )

    balance_after = money.finalize(balance_before - delta) if balance_before is not None else None
    plan: tuple[str, ...] = ()
    if correction_class == CLASS_RESTATEMENT:
        plan = (
            "payments allocated to the original re-allocate to the rebill; any excess "
            "becomes a carried account credit (BR-PAY-010). Billing emits this plan; "
            "payments executes it — no allocation row is ever edited (BR-PAY-031).",
        )
    elif correction_class == CLASS_CREDIT_ONLY:
        plan = (
            "nothing re-allocates: no payment moved and no invoice changed. The goodwill "
            "credit sits on the account until a future bill consumes it.",
        )
    else:
        plan = ("nothing re-allocates — no money moved.",)

    return BillImpact(
        invoice_id=str(invoice.pk),
        invoice_no=invoice.invoice_no,
        account_id=str(invoice.account_id),
        correction_class=correction_class,
        reason_codes=tuple(reason_codes),
        currency=currency,
        lines=impact_lines,
        original_total=original_total,
        corrected_total=corrected_total,
        delta=delta,
        tax_by_authority=taxes,
        documents=documents,
        posting_period=posting_period,
        balance_before=balance_before,
        balance_after=balance_after,
        reallocation_plan=plan,
        # CR-059 CS-36 · task 20 — the settlement panel's figures. RESTATEMENT
        # only: nothing is released by a concession or a document reissue, so
        # there is no settlement to preview and `None` says so.
        settlement=(
            settlement_preview(invoice, currency=currency, corrected_total=corrected_total)
            if correction_class == CLASS_RESTATEMENT
            else None
        ),
        warnings=tuple(warnings),
        mechanism=correction_reasons.mechanism_in_words(correction_class),
        # CR-101-BRC03 §06 — drawn on every class, never omitted (p129).
        # `corrected` is None on classes C and D, and the panel says so by
        # CODE rather than by absence.
        discounts=discount_panel(
            invoice, correction_class=correction_class, lines=lines, corrected=corrected
        ),
    )


def refuse_unless_class_matches_money(impact: BillImpact) -> None:
    """BR-BIL-043 — the guard that keeps a spelling out of the ledger.

    US-BIL-015 TC-9 / US-BIL-031 TC-4: a clerk opens a case with reason "name
    spelling" (class D) and the recomputation moves $19.92 because the READ was
    also wrong. Refused, naming the delta, before anything is written. The
    operator picks the reason that describes what is actually wrong.
    """
    if impact.correction_class != CLASS_DOCUMENT:
        return
    if impact.delta == ZERO:
        return
    raise BillingRuleError(
        f"this reason does not change money, but recomputing bill "
        f"{impact.invoice_no or impact.invoice_id} moved {impact.delta} "
        f"{impact.currency} (BR-BIL-043). A document correction reissues a page and "
        "posts nothing — pick the reason that describes what is wrong, or the money will "
        "be corrected by a case nobody reviewed as a money correction. Nothing was "
        "written.",
        br_ref="BR-BIL-043",
    )


def refuse_document_class_that_moves_money(
    invoice: models.Invoice,
    *,
    correction_class: str,
    corrected: rating_seam.RatedBill | None = None,
) -> None:
    """BR-BIL-043 / US-BIL-015 TC-9 — the guard, made REACHABLE.

    ⚠ **WHY THIS EXISTS BESIDE `refuse_unless_class_matches_money`, WHICH READS
    LIKE THE SAME CHECK.** It is not the same check, and the difference is why
    TC-9 could not fire:

    `refuse_unless_class_matches_money` inspects a built `BillImpact`. But
    `build_impact` constructs a class-D impact by DEFINITION at zero — it sets
    `corrected_total = original_total` and never re-prices, because a document
    correction moves $0.00 and that is the ruled behaviour (BR-BIL-041/043). So
    `impact.delta` on a class-D case is always exactly ZERO, the guard's
    condition is never true, and the refusal TC-9 requires is unreachable
    through that path. A guard nothing can reach is hard-won law 2 wearing a
    money path's clothes: it reads as covered, every test passes, and the
    protection does not exist.

    TC-9's scenario is about the RECOMPUTATION, not about the impact: *"a clerk
    opens a case with reason 'name spelling' (class D) and the recomputation
    produces a non-zero delta because the read was ALSO wrong."* So this
    re-prices the bill and compares that against what was billed. The reason is
    wrong or the wrong bill was picked; either way a spelling must not put a
    credit on somebody's account.

    ❄️ On WE-9's fixture the recomputation moves **19.92** and the case is
    REFUSED before anything is written. Re-opened with "wrong read" it proceeds
    as TC-1.

    `refuse_unless_class_matches_money` is KEPT and still called: it catches a
    caller that hands in a class-D impact built some other way, which is a
    different door onto the same harm.
    """
    if correction_class != CLASS_DOCUMENT:
        return
    if corrected is None:
        corrected = recompute(invoice)
    delta = money.finalize(money.finalize(corrected.total) - money.finalize(invoice.total))
    if delta == ZERO:
        return
    raise BillingRuleError(
        f"this reason does not change money, but recomputing bill "
        f"{invoice.invoice_no or invoice.pk} moved {delta} {invoice.currency} "
        "(BR-BIL-043). A document correction reissues a page and posts nothing — pick the "
        "reason that describes what is wrong, or the money will be corrected by a case "
        "nobody reviewed as a money correction. Nothing was written.",
        br_ref="BR-BIL-043",
    )


#: The code a bill carries when the cap took it out of a case. The WORDS a
#: clerk reads are the catalogue's in eleven languages (B14 rule 35) and carry
#: no rule id (rule 32) — this is the key they are looked up by.
BEYOND_BACKBILL_WINDOW = "beyond_the_back_bill_cap"


def beyond_backbill_window(
    impact: BillImpact,
    *,
    as_of: date,
    period_end: date,
    window_months: int = DEFAULT_BACKBILL_WINDOW_MONTHS,
    theft_exempt: bool = False,
) -> dict[str, Any] | None:
    """Is THIS bill past the cap — and if so, in figures a screen can draw?

    `None` when the bill is fine; otherwise the facts, never a sentence: the
    code, how many months old the period is, and the window it broke. The words
    belong to the catalogues.

    ⚠ **THIS IS THE SAME TEST `refuse_upward_beyond_window` HAS ALWAYS MADE,
    SPLIT OUT ON 2026-09-15 — THE CAP ITSELF DID NOT MOVE.** `BR-BIL-018` with
    the tenant's window, applying to an UPWARD correction only, theft exempt,
    `OQ-104` option A and `OQ-071`/`BR-BIL-019` all stand exactly as signed.
    What the PO changed is the BLAST RADIUS of the refusal — verbatim, on seven
    months of which one is past the cap: *"in such sitution 6 bills only ; 7th
    is not valid case"*. A case of seven now runs the six; before, a clerk got
    nothing at all (`DEF-BIL-5360`).

    **Two callers and they want opposite things, which is why this exists.**
    `refuse_upward_beyond_window` below raises, for every path that judges ONE
    bill and has no rest-of-the-case to proceed with. `bulk_corrections.
    open_case` reads the dict and leaves the bill out. Neither restates the
    test.
    """
    if impact.delta <= ZERO or theft_exempt:
        return None
    months = (as_of.year - period_end.year) * 12 + (as_of.month - period_end.month)
    if months <= window_months:
        return None
    return {
        "code": BEYOND_BACKBILL_WINDOW,
        "months": months,
        "window_months": window_months,
        "period_end": period_end.isoformat(),
        "delta": str(impact.delta),
        "currency": impact.currency,
    }


def refuse_upward_beyond_window(
    impact: BillImpact,
    *,
    as_of: date,
    period_end: date,
    window_months: int = DEFAULT_BACKBILL_WINDOW_MONTHS,
    theft_exempt: bool = False,
) -> None:
    """OQ-104, closed by the PO on 2026-08-11 with option **A: the cap APPLIES**.

    *"The correction workflow is NOT a route around the consumer-protection cap;
    the preview carries the refusal. Downward corrections are unaffected at any
    age."*

    `as_of` is a parameter and never a clock (BR-TEN-043) — a preview and the
    execute that follows it must judge the same bill against the same day.
    Theft cases are EXEMPT, which is OQ-071's closure carried through unchanged
    (BR-BIL-019); the exemption is a caller's fact about the case, not something
    this function infers from a reason code it might not recognise.
    """
    beyond = beyond_backbill_window(
        impact,
        as_of=as_of,
        period_end=period_end,
        window_months=window_months,
        theft_exempt=theft_exempt,
    )
    if beyond is None:
        return
    months = beyond["months"]
    raise BillingRuleError(
        f"this correction adds {impact.delta} {impact.currency} to a period that ended "
        f"{months} months ago, and the tenant's back-bill window is {window_months} "
        "months (BR-BIL-018; PO 2026-08-11 closing OQ-104: the window applies to an "
        "UPWARD correction too). Charging a customer for a period they were never told "
        "about is capped however the charge arrives. A DOWNWARD correction of the same "
        "bill is unaffected at any age.",
        br_ref="BR-BIL-018",
    )


#: How deep a correction chain may be walked before the walk is called a loop.
#: The database forbids self-reference (`ck_invoices_corrects_not_self`) and
#: makes a replacement unique per original (`uq_invoices_one_replacement`), so a
#: cycle should be unreachable — this is the belt to those braces, because a
#: panel that spins forever is a worse failure than one that refuses. Twenty is
#: far past anything real: a bill corrected twenty times is a process problem
#: somebody needs to be told about, not a chain to keep following.
MAX_CHAIN_DEPTH = 20


def replacement_of(invoice: models.Invoice) -> models.Invoice | None:
    """The bill that REPLACED this one, or `None` — one hop, not the whole chain.

    **PO 2026-08-12, OQ-120:** the link lives on the new bill, so this reads
    backwards along it: *"which invoice carries `corrects_invoice_id` = me?"*.
    `uq_invoices_one_replacement` guarantees at most one answer, which is why
    this returns an invoice rather than a queryset — a bill with two
    replacements would be a chain that forked, and BR-BIL-048's "the latest in
    the chain" would have no referent.

    Tenant-scoped explicitly as well as by RLS (hard rule 1), the same belt-and-
    braces `documents._lines_of` states for itself.
    """
    return (
        models.Invoice.objects.filter(
            tenant_id=invoice.tenant_id, corrects_invoice_id=invoice.pk
        ).first()
        or None
    )


def latest_in_chain(invoice: models.Invoice) -> models.Invoice:
    """Follow the chain to its head — the bill the customer actually owes.

    BR-BIL-048's own sentence made computable: *"only the LATEST document in a
    correction chain may be corrected"*. A bill corrected twice has a chain
    original → rebill₁ → rebill₂, and the answer is rebill₂.

    Returns the invoice itself when nothing replaced it, which is the ordinary
    case for every bill that was ever right.

    **This is also BR-BIL-064's read.** The phase-4 sign-off panel shows *"what
    these customers owe NOW"* (the PO's own parenthetical closing OQ-111), and
    "now" is the head of the chain — worked on the PO's case, a $117.01 bill
    corrected to $104.20 resolves here to the $104.20 bill.
    """
    seen = {str(invoice.pk)}
    current = invoice
    for _ in range(MAX_CHAIN_DEPTH):
        nxt = replacement_of(current)
        if nxt is None:
            return current
        if str(nxt.pk) in seen:  # pragma: no cover - the DB constraints forbid it
            break
        seen.add(str(nxt.pk))
        current = nxt
    raise BillingRuleError(
        f"the correction chain from bill {invoice.invoice_no or invoice.pk} is longer than "
        f"{MAX_CHAIN_DEPTH} links or loops back on itself, and the head cannot be named. "
        "`uq_invoices_one_replacement` and `ck_invoices_corrects_not_self` (migration 0017) "
        "make a loop unreachable through the correction workflow, so reaching this means "
        "something wrote the column another way. The panel refuses rather than spinning.",
        br_ref="BR-BIL-048",
    )


def refuse_unless_latest_in_chain(invoice: models.Invoice) -> None:
    """BR-BIL-048 — only the LATEST document in a correction chain is correctable.

    A bill already moved to `corrected` has a replacement somewhere; correcting
    the superseded copy would produce a credit note for money that was already
    credited.

    This check reads the original's own `status`, which is the cheapest form of
    the question and needs no join. The replacement is now REACHABLE as well —
    `invoices.corrects_invoice_id` on the rebill, PO 2026-08-12 closing OQ-120
    (*"Nod to add the link on the new bill"*), which is what
    `latest_in_chain` follows and what the refusal below NAMES so the operator
    is told which bill to open the case on instead of being told to go and look.

    ⚠ SUPERSEDED (PO 2026-08-11 → 2026-08-12): this docstring used to end *"The
    replacement is found through the ACCOUNT HISTORY LOG and not through a
    column — the PO ruled the link's home on 2026-08-11 (OQ-120, 'in Histrory
    log only - at account level') — so this check reads the original's own
    status rather than following a join that must not exist."* The join exists.
    """
    if invoice.status == models.INVOICE_CORRECTED:
        replacement = replacement_of(invoice)
        named = (
            f" Its replacement is {replacement.invoice_no or replacement.pk}."
            if replacement is not None
            else (
                " Its replacement cannot be named: this bill is `corrected` but no bill "
                "carries `corrects_invoice_id` pointing at it, which means it was "
                "corrected before the chain column existed (migration 0017) or by a path "
                "that does not stamp it. Both are worth reporting."
            )
        )
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} has already been corrected and is "
            "not the latest document in its chain (BR-BIL-048). Open the case on its "
            "replacement — correcting a superseded bill credits money that was credited "
            "once already." + named,
            br_ref="BR-BIL-048",
        )
    if invoice.status == models.INVOICE_VOID:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} is void: there is nothing to "
            "correct, because the customer was never billed. A void is not a correction "
            "and a correction is not a void (US-BIL-027).",
            br_ref="BR-BIL-048",
        )
    if invoice.status == models.INVOICE_DRAFT:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} is still a DRAFT. A draft is "
            "re-priced or discarded, not corrected — the correction workflow exists "
            "because an ISSUED bill can never be edited (BR-BIL-004).",
            br_ref="BR-BIL-004",
        )


def post_credit_note_reversal(
    credit_note: models.CreditNote,
    *,
    invoice: models.Invoice,
    lines: list[models.InvoiceLine],
    posted_at: datetime,
    actor: Any = None,
) -> Any:
    """The credit note's half of the handoff: the original's buckets, REVERSED.

    EP-BIL-04 §7a states the shape and this function is that shape and nothing
    more: *DR 4100 88.60 · 4105 12.00 · 4110 39.50 … / CR 1200 AR 247.87* — the
    original's own stamped buckets debited, AR credited by the same total.

    **THE CORRECTION IS NOT ONE NET ENTRY.** The credit note reverses the
    original in full and the rebill posts its own stamps (which `issue_invoice`
    emits on its own). Netting them into a single entry would lose the fact that
    a bill was issued and reversed, which is what an auditor follows.

    Billing writes no journal lines (CLAUDE.md rule 5, BR-BIL-011): this emits a
    request to the ledger's posting service, resolved BY NAME through the seam
    `posting_seam` already owns, and the ledger is the sole writer.
    """
    contract = posting_seam._ledger_contract()
    post = contract[posting_seam.POSTING_WRITE]
    compose_key = contract[posting_seam.POSTING_KEY]
    request_type = contract[posting_seam.POSTING_REQUEST_TYPE]
    line_type = contract[posting_seam.POSTING_LINE_TYPE]
    refusal_type = contract[posting_seam.POSTING_REFUSAL_TYPE]

    ar_account_id = posting_seam._ar_account_id()
    buckets = posting_seam.posting_buckets(invoice, lines)
    ar_credit = posting_seam._refuse_unless_balanced(invoice, buckets)

    key = compose_key(source_type="credit_note", source_id=credit_note.pk, event="issued")
    common = {
        "source_type": "credit_note",
        "source_id": credit_note.pk,
        "account_id": invoice.account_id,
    }
    # 🔒 DEF-BIL-9501 — EACH BUCKET ON THE OPPOSITE OF ITS OWN SIDE. This read
    # `side=SIDE_DEBIT` for every bucket, which was true until DEF-536 (PO
    # 2026-08-28) made a discount its own DEBIT bucket (4760); reversing that
    # as another debit left every discounted bill's credit note unbalanced —
    # an $80.00 bill with $25.00 off: debits $105.00, credits $55.00 — and the
    # ledger refused every correction of a discounted bill. Reversed, the
    # discount is CREDITED back: DR revenue $80.00 / CR 4760 $25.00 + AR $55.00.
    posting_lines = [
        line_type(
            ledger_account_id=bucket.gl_account_id,
            side=(
                posting_seam.SIDE_CREDIT
                if bucket.side == posting_seam.SIDE_DEBIT
                else posting_seam.SIDE_DEBIT
            ),
            amount=bucket.amount,
            service_id=bucket.service_id,
            tax_authority_id=bucket.tax_authority_id,
            **common,
        )
        for bucket in buckets
    ]
    posting_lines.append(
        line_type(
            ledger_account_id=ar_account_id,
            side=posting_seam.SIDE_CREDIT,
            amount=ar_credit,
            **common,
        )
    )
    # 🔒 `CR-180-BRC10` B8 — BR-BIL-045 / BR-TEN-038: a closed month posts to
    # the earliest OPEN one. The ledger REFUSES a closed date and leaves the
    # forward to the caller (`ledger.posting._refuse_if_period_closed`), so this
    # asks the ledger's one implementation through the seam — the same read the
    # rebill's own issue makes (`posting_seam._book_date`) — and both halves of
    # the correction land in the same month. An open month answers the bill's
    # own service date, byte for byte what this posted before.
    entry_date, _forward_note = posting_seam.forward_for(invoice.service_date)
    try:
        return post(
            request_type(
                posting_key=key,
                entry_date=entry_date,
                posted_at=posted_at,
                currency=invoice.currency,
                lines=tuple(posting_lines),
                source_type="credit_note",
                source_id=credit_note.pk,
                memo=(f"Credit note reversing bill {invoice.invoice_no or invoice.pk} in full"),
                audit_context={
                    "invoice_no": invoice.invoice_no,
                    "credit_note_id": str(credit_note.pk),
                    # CS-37 — read off the ROW, not passed in: this function
                    # takes the credit note itself, so there is exactly one
                    # place the number can come from and it cannot disagree
                    # with the column.
                    "credit_note_no": credit_note.credit_note_no,
                    "gl_buckets": len(buckets),
                },
            ),
            actor=actor,
        )
    except refusal_type as refusal:  # the ledger's vocabulary → billing's
        raise posting_seam.PostingRefused(
            f"the books refused the credit note reversing bill "
            f"{invoice.invoice_no or invoice.pk}, so the correction did not execute and "
            f"nothing was written (BR-BIL-011): {refusal}",
            br_ref="BR-BIL-011",
        ) from refusal


def credit_only_gl_accounts() -> tuple[str, str]:
    """The two sides of a goodwill / concession credit: `(debit, credit)`.

    **PO ruling 2026-08-12 (OQ-105 / OQ-168), verbatim: _"a separate write-off
    account"_ — the DEBIT side that had been missing.**

    ❄️ Worked on GT-6's frozen shape: a **$25.00** goodwill credit against a
    **$247.30** invoice leaves the customer owing **$222.30**, and that figure
    was never in doubt — all three candidate readings produced it. What was in
    doubt is where the utility's side of the gesture lands, and they are three
    different P&Ls: contra-revenue (the utility earned less), an expense (the
    utility spent something on goodwill), or no entry at all until a future bill
    consumes the credit. The ruling picks the separate account.

    So the entry is **DR write-off / CR customer credit balance**, both resolved
    BY DESIGNATION and never by number. The original service revenue is not
    touched, which means a month's revenue keeps reading as the revenue that was
    billed and concessions are their own visible figure rather than a dent in
    the top line.

    This function REFUSED until the ruling landed, and it refused BEFORE writing
    anything rather than half-way through — a credit row without its entry is
    money in the product and not in the books.
    """
    return posting_seam.write_off_account_id(), posting_seam.credit_balance_account_id()


@transaction.atomic
def execute_credit_only(
    invoice: models.Invoice,
    *,
    impact: BillImpact,
    amount: Decimal,
    reason: str,
    issued_at: datetime,
    actor: Any = None,
) -> models.CreditNote:
    """Class C — the goodwill credit, written and posted. **PO 2026-08-12.**

    The bill is NOT touched (PO ruling 2026-08-11: the credit is raised on the
    ACCOUNT), so this writes ONE credit note and emits ONE balanced entry:

        DR  write-off              amount
        CR  customer credit        amount

    ❄️ GT-6's frozen shape: **25.00** against a **247.30** invoice → the customer
    owes **222.30**, unchanged by which reading won, because the ruling decides
    the utility's side and not the customer's.

    Billing writes no journal line (rule 5): the entry is emitted through the
    same seam every other correction uses, so the ledger stays the sole writer
    and the idempotency key is composed by the ledger's own function (rule 6).

    ════════════════════════════════════════════════════════════════════════
    IT NOW TELLS PAYMENTS — CR-059 CS-38, 2026-09-02
    ════════════════════════════════════════════════════════════════════════
    **THIS FUNCTION USED TO BE THE WHOLE STORY, AND THAT WAS THE DEFECT.** The
    credit note was written, the entry was posted, a *"credit issued"* letter was
    queued — and no figure any customer or clerk can read moved a cent.
    Outstanding is bill totals less payment ALLOCATIONS; account credit is
    payments less allocations less refunds; **neither reads `credit_notes`**. So
    on the frozen shape above the account screen said outstanding **247.30** and
    credit **0.00**, the next bill was calculated without the concession, and the
    collection ladder chased the customer for the full 247.30 — after a letter
    telling them they had been given 25.00. Of everything in CR-059 this was the
    only item where the customer had been told, in writing, something the system
    then contradicted.

    `payments_seam.record_concession_credit` closes it by asking payments to
    record a CREDIT-type row for the same amount. Payments' own credit position
    picks it up with no further change, and billing's existing draw-down
    consumes it at the next bill — which is the PO's own OQ-105 sentence, *"it
    is new good will credit to be applied in new bill"*.

    ⚠ **THERE IS EXACTLY ONE POSTING AND THIS FUNCTION OWNS IT.** CS-38 leaves
    the choice to the build and says to write it down: **billing keeps the
    posting; payments' row is marked NON-POSTING** (`already_posted_source=
    "credit_note"`). The alternative — moving the posting to payments — would
    reverse the ruling of 2026-08-12, and would file new concessions under
    `source_type payment` while every historic one stays `credit_note`, which is
    one event in two shapes forever on rows nobody may go back and fix. Asserted
    rather than promised: `tests/test_cr059_cs35_cs38_credit_rows.py` counts the
    journal entries either side and requires exactly **one** — DR write-off
    25.00 / CR customer credit 25.00 — with **no** payment-sourced entry.

    ⚠ **THE CREDIT CARRIES; IT DOES NOT MEET THE BILL IT CAME FROM.** `OQ-215`
    is OPEN and asks precisely whether a concession moves THIS bill's balance to
    222.30 or is an account credit consumed by the next bill. It says GT-6's
    222.30 is reached either way and that the choice *"needs one sentence from
    the PO and is not a thing an implementer may pick"*. This module implements
    the second reading (`build_impact` forces the class-C delta to ZERO), so the
    credit row is recorded with the carry-credit allocation order and touches no
    invoice. **Recording it oldest-first would have settled 25.00 of this very
    bill and decided OQ-215 on a money path with no ruling.**

    **THE SEAM NEVER RAISES INTO THIS FUNCTION.** A refusal comes back on the
    outcome's `problems` and the credit note stands: the entry is posted, the
    note is issued, and hard rule 4 forbids unwinding either because a
    downstream call failed.
    """
    if amount <= ZERO:
        raise BillingRuleError(
            f"a goodwill credit of {amount} is not a credit. A concession gives money back to "
            "the customer, so its amount is positive and its SIGN is decided here, once.",
            br_ref="BR-BIL-014",
        )
    debit_account_id, credit_account_id = credit_only_gl_accounts()
    credited = money.finalize(amount)

    # CR-059 CS-37 · writer 1 of 2. Inside this function's own `@transaction.
    # atomic`, so BR-TEN-035's row lock and this INSERT commit or roll back
    # together. See `_allocate_credit_note_no`.
    credit_note_no, numbering_gap = _allocate_credit_note_no(issued_at)
    credit_note = models.CreditNote.objects.create(
        tenant_id=_tenant_id(),
        account_id=invoice.account_id,
        original_invoice=invoice,
        credit_note_no=credit_note_no,
        amount=money.finalize(-credited),
        currency=invoice.currency,
        reason=reason,
        issued_at=issued_at,
    )

    contract = posting_seam._ledger_contract()
    post = contract[posting_seam.POSTING_WRITE]
    compose_key = contract[posting_seam.POSTING_KEY]
    request_type = contract[posting_seam.POSTING_REQUEST_TYPE]
    line_type = contract[posting_seam.POSTING_LINE_TYPE]
    refusal_type = contract[posting_seam.POSTING_REFUSAL_TYPE]

    common = {
        "source_type": "credit_note",
        "source_id": credit_note.pk,
        "account_id": invoice.account_id,
    }
    try:
        post(
            request_type(
                posting_key=compose_key(
                    source_type="credit_note", source_id=credit_note.pk, event="goodwill"
                ),
                entry_date=issued_at.date(),
                posted_at=issued_at,
                currency=invoice.currency,
                lines=(
                    line_type(
                        ledger_account_id=debit_account_id,
                        side=posting_seam.SIDE_DEBIT,
                        amount=credited,
                        **common,
                    ),
                    line_type(
                        ledger_account_id=credit_account_id,
                        side=posting_seam.SIDE_CREDIT,
                        amount=credited,
                        **common,
                    ),
                ),
                source_type="credit_note",
                source_id=credit_note.pk,
                memo=f"Goodwill credit on bill {invoice.invoice_no or invoice.pk}",
                audit_context={
                    "invoice_no": invoice.invoice_no,
                    "credit_note_id": str(credit_note.pk),
                    # CS-37 — the number a person can quote, beside the id the
                    # support line needs. `numbering_series_missing` is present
                    # ONLY when the tenant has no Credit memo series row, and
                    # says so rather than leaving a silent null.
                    "credit_note_no": credit_note_no,
                    "numbering_problem": numbering_gap,
                    "amount": str(credited),
                },
            ),
            actor=actor,
        )
    except refusal_type as refusal:
        raise posting_seam.PostingRefused(
            f"the books refused the goodwill credit of {credited} on bill "
            f"{invoice.invoice_no or invoice.pk}, so nothing was written (BR-BIL-011): {refusal}",
            br_ref="BR-BIL-011",
        ) from refusal

    # ── CR-048 wave B task B11 · THE CUSTOMER IS TOLD ──────────────────────
    # `catalogs.LISTINGS["email_credit_issued"]` has said *"Not in use yet"*
    # since 2026-08-16 and its wording has existed since 2026-08-17, so what was
    # missing was a sender. A concession the customer is never told about is
    # money the utility gave away for nothing, which is the one outcome a
    # goodwill credit exists to avoid.
    #
    # ⚠ **THIS RUNS INSIDE `@transaction.atomic` AND THE SEAM'S SAVEPOINT IS
    # WHAT MAKES THAT SAFE** (CLAUDE.md law 14): on PostgreSQL a failed
    # statement aborts the whole transaction, so without the nested `atomic()`
    # inside `queue_credit_note` a refused queue row would take the credit note
    # and its balanced journal pair down at COMMIT — and pass every test,
    # because the suite's default settings hardcode SQLite, which has no
    # aborted-transaction state.
    #
    # The outcome is DISCARDED here rather than returned, and that is a real
    # cost stated rather than hidden: this function's contract is
    # `-> models.CreditNote` and four callers unpack it as one. `queue_credit_
    # note` raises nothing and reports on `problems`, so a letter that could not
    # be queued is currently visible only in the queue's own absence. Widening
    # the return to carry it is the follow-up, and it belongs to the lane that
    # owns the correction result shape rather than to a notifications wave.
    delivery_seam.queue_credit_note(
        credit_note=credit_note,
        account_id=invoice.account_id,
        # The finalised figure, as a string (CLAUDE.md rule 2 — never a float
        # and never a number this call rounded). `credited` is `money.finalize`
        # of the amount, the SAME value the journal pair was posted with, so the
        # letter and the books cannot state different figures.
        amount=str(credited),
        # BR-TEN-043 — the correction's own business date, never a wall clock.
        on_date=issued_at.date(),
        # A19 r8 ratifies the clerk's memo as this class's customer-visible
        # reason. It is passed verbatim and reworded nowhere.
        reason=reason,
        actor=actor,
    )

    # ── CR-059 CS-38 · THE BALANCE THE CUSTOMER READS ──────────────────────
    # Inside this function's own `@transaction.atomic`, deliberately: the credit
    # row, the credit note and the journal pair are one fact or none of them is.
    # A credit row written afterwards, outside, could outlive a rolled-back
    # concession and hand a customer 25.00 the books never gave them.
    #
    # ⚠ AND THE SEAM'S SAVEPOINT IS WHAT MAKES THAT SAFE ON POSTGRESQL
    # (CLAUDE.md law 14): `record_concession_credit` refuses in payments'
    # vocabulary and the seam catches it, but a refusal that reached the
    # DATABASE first would abort this whole transaction at COMMIT — and pass
    # every test, because the suite's default settings hardcode SQLite, which
    # has no aborted-transaction state. `record_payment` opens its own nested
    # `transaction.atomic()`, which is that savepoint.
    #
    # The outcome is DISCARDED here rather than returned, and that is a real
    # cost stated rather than hidden — the same one `queue_credit_note` above
    # carries, for the same reason: this function's contract is
    # `-> models.CreditNote` and four callers unpack it as one. A concession
    # whose credit row could not be written is therefore visible today only in
    # the audit trail and in the account's unmoved credit position. Widening the
    # return to carry both outcomes belongs to the lane that owns the correction
    # result shape. REPORTED.
    payments_seam.record_concession_credit(
        credit_note=credit_note,
        account_id=invoice.account_id,
        # `credited` is `money.finalize(amount)` — the SAME value the journal
        # pair was posted with and the same one the letter quotes, so the books,
        # the letter and the customer's balance cannot state three figures.
        amount=credited,
        # ONE reason code, not the joined list. `bulk_corrections` passes
        # `", ".join(case.reason_codes)` because BR-BIL-042 lets a case carry
        # several, and a payments reason is a single value from the tenant's own
        # list (BR-TEN-036). Class C has exactly one reason in the taxonomy —
        # `goodwill` — so the first element is the whole answer today, and
        # splitting here rather than in the seam keeps the joined string as the
        # credit note's own `reason`, which is where a human reads it.
        reason_code=(reason.split(",")[0].strip() or "goodwill"),
        # BR-TEN-043 — the correction's own business date, never a wall clock.
        on_date=issued_at.date(),
        currency=invoice.currency,
        memo=reason,
        actor=actor,
    )
    return credit_note


@transaction.atomic
def execute_restatement(
    invoice: models.Invoice,
    *,
    impact: BillImpact,
    reason: str,
    issued_at: datetime,
    on_date: date,
    template_id: Any,
    template_version: int,
    actor: Any = None,
    rebill_data: Any = None,
    goodwill_amount: Decimal | None = None,
    goodwill_reason: str | None = None,
) -> ExecutedBill:
    """ONE bill's class-R correction: credit note + reversal + rebill. Atomic.

    ── `CR-180-BRC10` · TWO OPTIONAL ARGUMENTS, BOTH NONE FOR EVERY OLD CALLER ──
    🔒 HUMAN-REVIEW-PENDING (rating math + ledger handoff).

    * **`rebill_data`** — the gathered `AccountBillingData` the approved
      preview was priced from, already carrying the case's correction rows (a
      plan, a schedule version, a tax rate, an added charge, a deposit, the
      corrected dates — `correction_items.prepare_bill`). The rebill is then
      `runs.calculate_account` over EXACTLY that data — the one pricing path
      (`runs.price_account`), so the preview total and the issued total are one
      computation, not two that agree. `None` keeps `single.prepare_single_bill`
      below, byte for byte.
    * **`goodwill_amount`** — PO 2026-10-12, decision log item 10: *"a goodwill
      row beside a reading row rides on the re-priced bill as a credit line"*.
      It is the SIGNED concession mechanism (`execute_credit_only`: DR write-off
      / CR customer credit, tax excluded, PO 2026-08-11/12), run AFTER the
      release and BEFORE the rebill issues — so the rebill's issue draws it
      down with the released payment (`apply_credit_at_issue`) and the customer
      owes the re-priced bill less the goodwill. ⚠ It is NOT a negative line on
      the rebill: a negative bucket on any account but the discount contra-
      revenue is refused at posting (`posting_seam.posting_buckets`, OQ-152),
      and the ruled account for a concession is the write-off account, not
      revenue.

    **BR-BIL-047's atomicity unit is this function.** All of it commits or none
    of it does: a bill that fails leaves ZERO artifacts and stays correctable,
    and a bill that succeeds is never reversed because a later bill failed — a
    posted pair cannot be un-posted (hard rule 4) and a delivered bill cannot be
    un-sent, so a batch rollback would be a lie in the UI. `bulk_corrections.py`
    is what catches the failure and carries on.

    `template_id` / `template_version` are REQUIRED and are the rebill's pin
    (BR-BIL-026: the rebill pins the CURRENT template version at rebill issue).
    They are not defaulted from the original, and hard-won law 3 is why: the
    unsafe option — silently reprinting on a version that may have been
    superseded — must be the one you type. `bill_templates` (r10 #4) does not
    exist, so "current" is the caller's fact until it does.

    Idempotency (rule 6) is the CASE's: `correction_case_bills` holds one row
    per bill per case and only moves queued → done, so a replayed execution
    never reaches this function twice for the same bill. The rebill run's
    idempotency key carries the case and the bill for the same reason.
    """
    lines = list(
        models.InvoiceLine.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice).order_by(
            "created_at", "id"
        )
    )
    tenant_id = _tenant_id()

    # ── 1 · the credit note: the original, reversed in full, referencing it ──
    # CR-059 CS-37 · writer 2 of 2, in this function's own `@transaction.atomic`.
    # TWO credit notes raised in ONE bill run therefore take CONSECUTIVE numbers:
    # the series row is locked per allocation, so `CM-0001` and `CM-0002` cannot
    # collide and cannot skip (`tests/test_cr059_cs37_credit_note_identity.py`).
    credit_note_no, numbering_gap = _allocate_credit_note_no(issued_at)
    credit_note = models.CreditNote.objects.create(
        tenant_id=tenant_id,
        account_id=invoice.account_id,
        original_invoice=invoice,
        credit_note_no=credit_note_no,
        amount=money.finalize(-impact.original_total),
        currency=invoice.currency,
        reason=reason,
        issued_at=issued_at,
    )
    post_credit_note_reversal(
        credit_note,
        invoice=invoice,
        lines=lines,
        posted_at=issued_at,
        actor=actor,
    )

    # ── 1b · 🔒 DEF-2430 · THE ORIGINAL'S DISCOUNT IS GIVEN BACK — BEFORE THE
    # REBILL IS PRICED ─────────────────────────────────────────────────────
    # The credit note above reverses the original's money; this reverses what
    # it SPENT of the customer's yearly cap, lifetime cap and programme budget
    # (one reversing `discount_grants` row per grant, hard rule 4). Its
    # position is the rule, like 1a's: the rebill below is priced against the
    # caps, so if the original's grant still stood the rebill would find the
    # year already spent by the very bill it replaces — Carl's corrected
    # December with a $25.00 CAP credit would rebill at $0.00 off. Idempotent
    # per grant (rule 6), so a replayed execution gives nothing back twice.
    grants_reversed = rating_seam.reverse_discount_grants(
        invoice, reason=reason, document_id=credit_note.pk, actor=actor
    )

    # ── 1a · THE RELEASE — BEFORE THE REBILL, IN THIS TRANSACTION ───────────
    #
    # CR-059 CS-36, BR-PAY-1074. ⚠ **THIS CALL'S POSITION IS THE RULE.** It sits
    # between the credit note and the rebill because the rebill's issue draws
    # down account credit (BR-PAY-010, `payments_seam.apply_credit_at_issue`,
    # called from `issue.issue_invoice` a few lines below) and the credit it
    # draws on is the money this releases. Move it after `issue_invoice` and the
    # rebill issues against a credit balance that does not exist yet: Ajinkya's
    # 80.00 rebill goes out unsettled, and the collection ladder chases a man who
    # overpaid. (This read *"six days late on arrival because it inherited the
    # ORIGINAL due date"* — a corrected bill is now due on the correction date
    # plus the days to pay, PO 2026-10-13, but the ordering rule is unchanged.) Move it into a transaction of its own and a crash between the two
    # leaves him with a credit and no bill.
    #
    # It is stated as a rule and asserted by test because it is INVISIBLE in the
    # code — nothing about these lines looks ordered, and a later reader tidying
    # "payments things" together would put it after the issue without a single
    # test going red before CS-36's own proof was written.
    #
    # NOTHING IS POSTED (BR-PAY-1073): no money moves. The customer's cash is
    # already in the books, the credit note above has reversed the original's
    # revenue and receivable, and the rebill posts its own.
    released = payments_seam.release_allocations(
        invoice,
        reason=reason,
        # BR-TEN-043 — the correction's own business date, never a wall clock.
        occurred_on=on_date,
        actor=actor,
    )

    # ── 1c · `CR-180-BRC10` · GOODWILL ON THE RE-PRICED BILL ────────────────
    # After the release, before the rebill: the concession credit joins the
    # released money that the rebill's issue draws down. See the docstring.
    goodwill_note = None
    if goodwill_amount is not None and goodwill_amount > ZERO:
        goodwill_note = execute_credit_only(
            invoice,
            impact=impact,
            amount=goodwill_amount,
            reason=goodwill_reason or "goodwill",
            issued_at=issued_at,
            actor=actor,
        )

    # ── 2 · the rebill: a NEW invoice, its own run, its own GL stamps ────────
    rebill_start = getattr(rebill_data, "period_start", None) or invoice.period_start
    rebill_end = getattr(rebill_data, "period_end", None) or invoice.period_end
    rebill_run = models.BillRun.objects.create(
        tenant_id=tenant_id,
        cycle_id=invoice.bill_run.cycle_id,
        period_start=rebill_start,
        period_end=rebill_end,
        # PO ruling 2026-10-13 (decision log *"⚖️ RULED 2026-10-13"* item 2,
        # *"this is correct"*): a corrected bill is due on THE CORRECTION
        # DATE plus the account's usual days to pay — corrected 10/13 with 20
        # days is due 11/02/2026. Copying the original run's bill date made a
        # corrected August bill due 09/22/2026, already past. The days to pay
        # are still the original run's (below) or its cycle's.
        bill_date=on_date,
        # DEF-BIL-10102 — a run with no cycle (a one-time run) names its
        # ACCOUNT as its scope (`ck_bill_runs_has_a_scope`) and carries its own
        # days to pay; the replacement's run copies both, or the database
        # refuses it and the due date cannot be derived (BR-BIL-024).
        scope_account_id=(None if invoice.bill_run.cycle_id else invoice.account_id),
        due_days=invoice.bill_run.due_days,
        status="issuing",
        bill_type="rebill",
        # Rule 6: the key names the CASE and the BILL, so a replayed execution
        # collides on the unique key rather than minting a second rebill run.
        idempotency_key=f"correction:{impact.invoice_id}:{credit_note.pk}",
        parent_run=invoice.bill_run,
    )
    if rebill_data is not None:
        # `CR-180-BRC10` — the approved preview's own data, priced by the one
        # pricing path. `calculate_account` answering None is a bill with no
        # lines, which single mode refuses rather than issuing (BR-BIL-1024).
        rebill = runs.calculate_account(
            rebill_data,
            bill_run=rebill_run,
            service_date=invoice.service_date,
            bill_type="rebill",
        )
        if rebill is None:
            raise BillingRuleError(
                f"the corrected bill for {invoice.invoice_no or invoice.pk} prices no "
                "lines, so there is no bill to issue. The credit note was NOT written — "
                "one bill is one transaction (BR-BIL-047).",
                br_ref="BR-BIL-047",
            )
    else:
        prepared = single.prepare_single_bill(
            account_id=invoice.account_id,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            service_date=invoice.service_date,
            bill_type="rebill",
        )
        if prepared.blocked:
            first = prepared.blocked[0]
            raise BillingRuleError(
                f"the rebill for {invoice.invoice_no or invoice.pk} could not be priced: "
                f"{first.detail}. The credit note was NOT written — one bill is one "
                "transaction (BR-BIL-047), so this bill leaves no artifacts and stays "
                "correctable.",
                br_ref="BR-BIL-047",
            )
        rebill = single.calculate_single_bill(prepared, bill_run=rebill_run, bill_type="rebill")

    # ── 2a · the chain link, ON THE REBILL (PO 2026-08-12, OQ-120) ───────────
    # *"Nod to add the link on the new bill"*. Written here — while the rebill
    # is still a DRAFT — because the `0017` trigger freezes this column at
    # issue along with the money, and the original must not gain a column after
    # issue (BR-BIL-004). This is what BR-BIL-064's phase-4 panel follows to
    # show the replacement's figure instead of a total nobody owes.
    models.Invoice.objects.filter(tenant_id=tenant_id, pk=rebill.pk).update(
        corrects_invoice_id=invoice.pk
    )
    rebill.refresh_from_db(fields=["corrects_invoice"])

    # ── 3 · the original moves to `corrected` — the ONE mutable column ───────
    #
    # ⚠ **BEFORE THE REBILL ISSUES, AND THE ORDER IS THE RULE (`DEF-BIL-10077`).**
    # The rebill's issue stamps its balance-forward box from payments' read of
    # the account's OPEN bills, and that read takes `issued` and `paid` bills.
    # Flipped after the issue, the original was still `issued` at the stamp and
    # its whole amount was counted again: BL-2610-000053 ($198.90, unpaid)
    # corrected to $183.60 printed *Previous balance 414.12 · Payments 215.22 ·
    # Total due 382.50* where the customer owed $183.60. The credit note above
    # has already reversed it, so by this point it is not an open bill. Same
    # transaction, so nothing is visible half-done.
    models.Invoice.objects.filter(tenant_id=tenant_id, pk=invoice.pk).update(
        status=models.INVOICE_CORRECTED
    )

    from apps.billing import issue as issue_module

    issued = issue_module.issue_invoice(
        rebill,
        issued_at=issued_at,
        template_id=template_id,
        template_version=template_version,
        actor=actor,
    )

    # ── 3a · BR-BIL-1045 · AND SO DO THE TWO RUNS ───────────────────────────
    #
    # ⚠ **THE REBILL RUN WAS CREATED `"issuing"` ABOVE AND NOTHING EVER MOVED
    # IT (`DEF-BIL-5352`).** It is an ordinary run of one bill, that bill has
    # just issued, and it reaches `issued` exactly as a cycle run does — through
    # the one writer, so there is one vocabulary and not two.
    #
    # ⚠ **THE ORIGINAL RUN BECOMES `corrected`, AND THIS IS THE BLUEPRINT'S OWN
    # SENTENCE** (p146): *"Corrected is a status the correction workflow sets …
    # §06 screen 26.5 restated its 412 water bills. The two sections meet here,
    # and this is the only screen where a clerk can see that a whole run was
    # redone."* Written HERE rather than inferred by the read, because the read
    # would have to join every run to every correction case to find it out, and
    # because the fact is *this run was restated* — an event, not a shape.
    #
    # The original's own bills are untouched by this: step 3 above is the ONE
    # mutable column on an issued invoice and hard rule 4 governs the rest.
    runs.record_run_outcome(rebill_run, actor=actor)
    runs.mark_run_corrected(invoice.bill_run)

    # ── 4 · hard rule 7, and the account-history link the PO ruled (OQ-120) ──
    audit.money_action(
        actor,
        "correction.executed",
        "invoices",
        str(invoice.pk),
        before={"status": invoice.status, "total": str(impact.original_total)},
        after={
            "status": models.INVOICE_CORRECTED,
            "credit_note_id": str(credit_note.pk),
            # CS-37 — the number, and the reason there is none when there is
            # none. `numbering_problem` is null on every tenant that has its
            # Credit memo series seeded, which is every tenant provisioned
            # since CR-005.
            "credit_note_no": credit_note_no,
            "credit_note_numbering_problem": numbering_gap,
            "credit_note_amount": str(money.finalize(-impact.original_total)),
            # The rebill link, in the audit trail — hard rule 7 owes this row
            # whatever the schema does, and it stays.
            #
            # ⚠ IT IS NO LONGER THE ONLY CARRIER. The 2026-08-11 reading of
            # OQ-120 ("in Histrory log only - at account level") was SUPERSEDED
            # by the PO on 2026-08-12: *"Nod to add the link on the new bill"*.
            # `invoices.corrects_invoice_id` is stamped on the rebill above
            # (migration 0017), because BR-BIL-064's panel has to JOIN to the
            # replacement and no panel can join to a log.
            "rebill_invoice_id": str(issued.pk),
            # WAS `"chain_link_column": "invoices.corrects_invoice_id (PO
            # 2026-08-12, OQ-120)"` until DEF-2377 — a key naming a database
            # column and a value naming a rule, both rendered on S61. The link
            # itself is unchanged: `invoices.corrects_invoice_id` is stamped on
            # the rebill above (migration 0017), per the PO ruling of 2026-08-12
            # that superseded the history-log-only reading of OQ-120.
            "replacement_link": "this bill is linked to the bill it replaces",
            "rebill_invoice_no": issued.invoice_no,
            "account_id": str(invoice.account_id),
            "delta": str(impact.delta),
            "currency": invoice.currency,
            "reason_codes": list(impact.reason_codes),
            "correction_class": CLASS_RESTATEMENT,
            "occurred_on": on_date.isoformat(),
            # CR-059 CS-36 — the fifth thing this workflow does, and the one it
            # did not do until 2026-09-01. Recorded on the CORRECTION's row as
            # well as on payments' own `payment.allocations_released` row,
            # because they are two facts about two entities and rule 7 wants
            # both: what the correction did, and what happened to the money.
            # DEF-2430 — how many discount grants the original's correction
            # gave back (each is its own `discount.subsidy_reversed` row).
            "discount_grants_reversed": grants_reversed.reversed,
            # CR-180-BRC10 — the goodwill that rode on this re-priced bill, as
            # its own credit note (null when the case carried none).
            "goodwill_credit_note_id": str(goodwill_note.pk) if goodwill_note else None,
            "goodwill_amount": str(money.finalize(goodwill_amount)) if goodwill_note else None,
            "allocations_released": str(released.released),
            "allocations_released_rows": list(released.rows),
        },
    )
    return ExecutedBill(
        invoice_id=str(invoice.pk),
        credit_note_id=str(credit_note.pk),
        rebill_invoice_id=str(issued.pk),
        released_amount=released.released,
        released_rows=released.rows,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S30 correction endpoints are US-BIL-015/016's API half and none exists) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim RED transcripts — the immutability
#         path, the D-class money guard and the per-bill idempotency were each
#         broken deliberately, RUN, and the measured failure quoted before any
#         of them was trusted green (hard-won law 7)
# exceptions: (1) CLASS C PREVIEWS BUT DOES NOT EXECUTE — `NotImplementedError
#         ("OQ-168")`: the concession's DEBIT account is unruled and the three
#         live answers are three different P&Ls. The credit side (2400) IS
#         ruled. The PO's mechanism ruling — the bill is untouched, the credit
#         is raised on the account, tax excluded — is implemented in the
#         preview and asserted.
#         (2) THE REBILL'S TEMPLATE PIN IS A REQUIRED ARGUMENT, not defaulted
#         from the original: BR-BIL-026 wants the CURRENT version and
#         `bill_templates` (r10 #4) does not exist, so the caller supplies it
#         (hard-won law 3 — the unsafe option is the one you type).
#         (3) THIS MODULE READS `posting_seam`'s private helpers
#         (`_ledger_contract`, `_ar_account_id`, `_refuse_unless_balanced`) to
#         build the credit note's reversal, because the seam publishes only the
#         BILL-ISSUE handoff and this lane may not edit that file. Same package,
#         same contract, one seam — but it is a private read and is REPORTED
#         rather than left to be discovered.
#         (4) NO `corrects_invoice_id` COLUMN. The rebill link goes in the
#         account history (PO 2026-08-11, OQ-120); this module writes it into
#         its hard-rule-7 audit row and reports that the log's own storage
#         question is still open.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections — one class per case) · US-BIL-031
#           (document-only correction — the class-D half)
#           Screens: S30 · S8 (the lookup this stands in for)
# Rules:    BR-BIL-041 (every reason carries a CLASS and the class DERIVES the
#           mechanism; the operator picks the reason, never the mechanism) ·
#           BR-BIL-042 (a multi-reason case takes the STRONGEST class present,
#           R > C > D) · BR-BIL-043 (a D-class case with a non-zero money delta
#           is REFUSED) · BR-BIL-014 (reason codes are reference data,
#           tenant-extensible)
# Tests:    06-backend/tests/test_us_bil_016_bulk_corrections.py ·
#           06-backend/tests/test_us_bil_031_document_correction.py
# Impacts:  apps/billing/corrections.py · apps/billing/bulk_corrections.py ·
#           apps/billing/document_correction.py
# ───────────────────────────────────────────────────────
"""The correction reason taxonomy: reason → class → mechanism.

The load-bearing sentence of EP-BIL-04, and the reason this module exists at
all: **some reasons change the MONEY and some change only the DOCUMENT, and
those two are not the same correction.** A name fix that issues a credit note
moves the ledger and a customer's balance for a spelling. A rate fix that only
reprints is a silent underbilling nobody ever sees. So the operator picks the
REASON, the system DERIVES the mechanism from the reason's class, and there is
no mechanism dropdown anywhere in this module or above it.

WHAT THIS FILE IS STANDING IN FOR, AND WHY THAT IS SAID OUT LOUD
----------------------------------------------------------------
BR-BIL-014 makes correction reasons **tenant-extensible reference data** and
Addendum r10 #13 mints the lookup — with no `class` column. Both the table and
the column are **US-BIL-017's** and neither is built. EP-BIL-04's closing
section names the gap in its own words: *"a `class` column on the
correction-reason lookup … without it BR-BIL-041 has nothing to derive from and
the mechanism becomes a dropdown, which is the failure the taxonomy exists to
prevent."*

So this module holds the SEEDED map, and `class_for()` REFUSES any code it
cannot class. That is deliberately the opposite of a fallback: a tenant-added
reason is unknown here, and an unknown reason cannot be cited by a case — which
is exactly BR-BIL-041's rule (*"a reason with no class cannot be saved and
cannot be cited by a case"*) enforced one layer up until the table lands. A
default of "restatement" would let a tenant's new "address typo" reason issue
credit notes; a default of "document" would let it discharge a rate error with a
reprint. Neither absence is safe, so neither is guessed.

THE MAP IS PROPOSED, NOT RATIFIED — AND THAT IS ON THE AGENDA, NOT IN THE CODE
------------------------------------------------------------------------------
BR-BIL-041/042/043 were authored from the PO's statement of 2026-08-11 (*"Bill
correction can be due to reading error, name or address changes, rate issues,
credit, multiple reasons"*) and are **PROPOSED**. EP-BIL-04 §8 names the exact
thing to put to the PO, in the plain-English form the 2026-08-11 review
mechanism requires:

    "a misspelt name changes $0.00 and issues no credit note; a wrong rate
     changes $19.92 and always issues a credit note plus a corrected bill"

That sentence and this map are the human-review row for this file. The epic
itself rules the class-R path buildable today (*"fully specified by WE-1 +
WE-9"*), which is why this is a map with a review row rather than a stub.

CLASS C IS NOT WHAT THE FIRST DRAFT OF THIS TAXONOMY THOUGHT IT WAS
--------------------------------------------------------------------
EP-BIL-04's table describes class C as a *"partial credit note referencing the
original"*. **That description is superseded by the PO's own ruling of the same
day** (OQ-105), verbatim:

    "A goodwill credit - that ia category, keep it there; it will exclude the
     tax; you dont touch the bill; you issue new a good will credit; everything
     remain as it is, it is new good will credit to be applied in new bill"

So a concession is **not a credit note against the issued invoice at all**. The
original bill, its lines, its revenue and its tax liability stand untouched, and
a separate goodwill credit is raised on the ACCOUNT and consumed by a FUTURE
bill. `MECHANISM_IN_WORDS` says that, not the epic's older sentence, because
what the screen tells an operator must be what the code does.
"""

from __future__ import annotations

from apps.billing.correction_models import (
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
)
from apps.billing.exceptions import BillingRuleError

#: BR-BIL-042's precedence, strongest first: **R > C > D**. A document reason
#: costs nothing when a restatement is already happening, because the rebill
#: re-snapshots from current master data anyway.
CLASS_PRECEDENCE = (CLASS_RESTATEMENT, CLASS_CREDIT_ONLY, CLASS_DOCUMENT)

#: The seeded reason → class map, EP-BIL-04 §4 verbatim (US-BIL-015 §1a's table
#: plus US-BIL-017 §4's two document rows the r1.2 seeded six does not contain).
#: PROPOSED — see the module docstring.
SEEDED_REASON_CLASSES: dict[str, str] = {
    # ── class R · restatement — the money and the document both move ─────────
    "wrong_read": CLASS_RESTATEMENT,
    "wrong_rate_plan": CLASS_RESTATEMENT,
    "wrong_tax": CLASS_RESTATEMENT,
    "missed_charge": CLASS_RESTATEMENT,
    "charge_billed_in_error": CLASS_RESTATEMENT,
    "wrong_period_or_service": CLASS_RESTATEMENT,
    "theft_restated": CLASS_RESTATEMENT,
    # ── CR-180-BRC10 (PO 2026-10-12, decision log *FIX A BILL REVAMP* item 11):
    # *"we should keep plan are rate seperate option like wrong pla, wrong rate,
    # wrong deposit etc"*. Each re-prices the bill, so each is class R — a plan,
    # a rate, a discount and a deposit all change what the bill CHARGES, and a
    # reprint could never discharge one (BR-BIL-041's silent underbilling).
    # `wrong_rate_plan` above is KEPT: cases opened before the split cite it.
    "wrong_plan": CLASS_RESTATEMENT,
    "wrong_rate": CLASS_RESTATEMENT,
    "wrong_discount": CLASS_RESTATEMENT,
    "wrong_deposit": CLASS_RESTATEMENT,
    # ── class C · credit-only — the bill is RIGHT; the utility charges less ──
    "goodwill": CLASS_CREDIT_ONLY,
    # ── class D · document — the money is right, the page is wrong ───────────
    "customer_name": CLASS_DOCUMENT,
    "service_or_mailing_address": CLASS_DOCUMENT,
    "premises_or_unit_label": CLASS_DOCUMENT,
    "meter_number_or_read_dates": CLASS_DOCUMENT,
    "template_or_language": CLASS_DOCUMENT,
}

#: TC-1a: *"The class is shown in the operator's words … never as an enum
#: value."* One sentence per class, and the sentence is what the case screen
#: renders beside the reason the operator picked.
MECHANISM_IN_WORDS: dict[str, str] = {
    CLASS_RESTATEMENT: (
        "issues a corrected bill: the original is credited in full, a rebill is issued "
        "for the right amount, and the customer's balance moves by the difference"
    ),
    CLASS_CREDIT_ONLY: (
        "issues a goodwill credit on the account, excluding tax: the bill is not touched "
        "and nothing about it changes — the credit comes off a future bill"
    ),
    CLASS_DOCUMENT: (
        "reprints the document with the details corrected: no money moves, no credit is "
        "raised, and the balance changes by exactly $0.00"
    ),
}

#: The three things people bring to a correction screen that are NOT
#: corrections. EP-BIL-04 §1a: *"the case screen says so by name rather than
#: accepting the work."* Keyed by the reason an operator would reach for.
ROUTED_ELSEWHERE: dict[str, str] = {
    "estimate_replaced_by_actual": (
        "an estimate replaced by an actual read trues up on the NEXT bill by register "
        "arithmetic (BR-BIL-006 / WE-13: there is no reversal of the July bill). Nothing "
        "about July was wrong — the register caught up."
    ),
    "bill_should_not_exist": (
        "a bill that should never have existed is VOIDED (US-BIL-027). A void is not a "
        "correction: a correction says what the customer owes, a void says they were "
        "never billed."
    ),
    "period_never_billed": (
        "a period never billed is a BACK-BILL (BR-BIL-018) — there is nothing to restate."
    ),
    "payment_on_wrong_bill": (
        "a payment that landed on the wrong bill is a payments RE-ALLOCATION "
        "(BR-PAY-010/031); the bills themselves are right."
    ),
    "master_data_only": (
        "master data wrong with no already-sent document affected is the customers-module "
        "edit (BR-BIL-049). This workflow decides what an already-sent document says, "
        "never what the account record says."
    ),
}


def class_for(reason_codes: tuple[str, ...] | list[str]) -> str:
    """The case's class, DERIVED from its reasons (BR-BIL-041/042).

    Refuses three things, each of which would otherwise become a wrong
    mechanism nobody chose:

    * **no reason at all** — the mechanism would have to be defaulted;
    * **a reason routed elsewhere** — named, with where it goes instead;
    * **a reason with no class** — a tenant-added code this build cannot class,
      which BR-BIL-041 forbids a case from citing.

    US-BIL-015 TC-11: `("wrong_read", "service_or_mailing_address")` → the case
    is class **R**, one approval, one document, and no separate reissue.
    """
    codes = tuple(reason_codes)
    if not codes:
        raise BillingRuleError(
            "a correction case cites at least one reason code (BR-BIL-014). The reason is "
            "what the mechanism is DERIVED from (BR-BIL-041), so a case with none would "
            "have to be given a mechanism by default — and the default would be wrong "
            "half the time in the direction that moves money.",
            br_ref="BR-BIL-041",
        )
    classes: list[str] = []
    for code in codes:
        if code in ROUTED_ELSEWHERE:
            raise BillingRuleError(
                f"{code!r} is not a correction: {ROUTED_ELSEWHERE[code]}",
                br_ref="BR-BIL-041",
            )
        found = SEEDED_REASON_CLASSES.get(code)
        if found is None:
            raise BillingRuleError(
                f"correction reason {code!r} carries no class, so no mechanism can be "
                "derived from it (BR-BIL-041). The seeded reasons are "
                f"{', '.join(sorted(SEEDED_REASON_CLASSES))}. The tenant-extensible "
                "lookup that would carry a class for a tenant's OWN reason is r10 #13 + "
                "US-BIL-017 and is NOT BUILT — until it is, a reason this build cannot "
                "class is refused rather than defaulted, because defaulting it either "
                "issues a credit note for a spelling or discharges a rate error with a "
                "reprint.",
                br_ref="BR-BIL-041",
            )
        classes.append(found)
    for candidate in CLASS_PRECEDENCE:
        if candidate in classes:
            return candidate
    raise AssertionError(  # pragma: no cover - CLASS_PRECEDENCE covers the map
        "every seeded class is in CLASS_PRECEDENCE"
    )


def mechanism_in_words(correction_class: str) -> str:
    """What the class DOES, in the sentence the operator reads (TC-1a)."""
    try:
        return MECHANISM_IN_WORDS[correction_class]
    except KeyError:  # pragma: no cover - guarded by class_for
        raise BillingRuleError(
            f"unknown correction class {correction_class!r}; BR-BIL-041 defines "
            f"{', '.join(CLASS_PRECEDENCE)}.",
            br_ref="BR-BIL-041",
        ) from None


def refuse_supplied_mechanism(supplied: object) -> None:
    """US-BIL-016/US-BIL-015 TC-10 — the silent-underbilling guard.

    The mechanism is DERIVED (BR-BIL-041). A caller — an API client, a script,
    a well-meaning integration — that supplies one is refused rather than
    obeyed, because the failure mode is invisible: answering "wrong rate/plan"
    with a document reissue leaves the customer holding the wrong amount and
    fires no gate anywhere. There is no keyword on any function in this module
    that accepts a mechanism; this exists so an attempt has somewhere to be
    refused, and a test can prove the refusal RED.
    """
    if supplied is None:
        return
    raise BillingRuleError(
        f"a correction's mechanism cannot be supplied ({supplied!r} was passed): it is "
        "DERIVED from the reason's class (BR-BIL-041). Answering a money reason with a "
        "document reissue is a silent underbilling — the customer keeps the wrong amount "
        "and no gate ever fires. Pick the reason that describes what is wrong.",
        br_ref="BR-BIL-041",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — vocabulary module; the S8 reference-data screen for these rows is US-BIL-017) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim run
# exceptions: (1) THIS IS NOT THE LOOKUP TABLE. r10 #13 + US-BIL-017 own the
#         tenant-extensible reason rows and the `class` column; neither is
#         built, so an unknown code is REFUSED here rather than defaulted.
#         REPORTED.
#         (2) THE MAP IS PROPOSED (BR-BIL-041/042/043, PO statement 2026-08-11,
#         detail unratified). The plain-English sentence to put to the PO is in
#         the module docstring and in the human-review ledger row.
#         (3) EP-BIL-04's class-C description ("a partial credit note
#         referencing the original") is SUPERSEDED by the PO's OQ-105 ruling of
#         the same day and `MECHANISM_IN_WORDS` follows the RULING, not the epic.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

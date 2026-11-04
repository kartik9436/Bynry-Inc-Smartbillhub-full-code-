# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — the late-fee assessment this module publishes)
#           Screens: — (the fee line renders on the invoice / S31.2)
#           No US-ID is cited in this header ON PURPOSE — the same reason
#           apps/billing/late_fee.py states: this module publishes one pure
#           calculation, not the S31.2 preview story that consumes it.
# Rules:    BR-BIL-001 (late fee = max($5, 1.5% × overdue portion); grace from
#           the Due date; AMENDED 2026-08-11 — no fee under a $25.00 overdue
#           balance) · BR-BIL-008 (grace: tenant-defined, default 5
#           calendar days, range 0–30) · BR-BIL-002 (calendar or business days)
#           · BR-BIL-071 (lateness is decided by the ACTUAL date the money
#           arrived, on the records that exist when the bill is generated)
# Golden:   GT-8 — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/golden/test_gt08_late_fee.py ·
#           06-backend/tests/test_gt08_late_fee_grace.py
# Impacts:  apps/billing/rating_seam.py (`assess_late_fee` resolves here)
# ───────────────────────────────────────────────────────
"""billing service layer — the ONLY write path into this module's tables (B1 boundary rule).
Other modules call these functions; they never touch this module's ORM directly.

**AMENDED 2026-08-11.** This paragraph used to open *"Today this module holds no
write path at all, because billing owns no tables yet"*, and it stayed there long
after billing grew `invoices`, `invoice_lines`, `bill_runs`, `credit_notes` and
`adjustments`, with `runs.py`, `issue.py` and `corrections.py` writing all of
them. It is corrected rather than left to rot (hard-won law 1): a docstring that
describes a module which no longer exists is how the NEXT reader concludes a
function has nowhere to live.

What this file itself holds is re-exports — the names other modules resolve BY
NAME as `apps.<module>.services.<name>`, whose implementations live in the file
that owns each one. One function should not exist twice.

  · `assess_late_fee` / `overdue_portion` / `PaymentReceipt` — GT-8's calculation
    out of `late_fee.py`, resolved here by `apps.billing.rating_seam`.
  · `financial_records_exist` — BR-TEN-042's currency-lock probe out of
    `selectors.py`, resolved here by `apps.tenancy.seams`. It is a READ, and it
    is re-exported into the write surface only because `tenancy/seams.resolve`
    imports `apps.<module>.services` and nothing else; see **DEF-075**, where its
    absence let a tenant holding an issued bill change its currency.
  · `seed_bill_templates` — **DEF-123**, the row without which no tenant can
    issue a bill. `templates_service.seed_platform_default` out of
    `templates_service.py`, resolved here by `apps.tenancy.seams` at
    PROVISIONING, exactly as the ledger's chart of accounts is. Until it existed
    `templates_service.resolve_for` correctly refused *"this tenant has no bill
    template … and no fallback"* for every tenant on every deployment, because
    the only rows that had ever existed were ones the TESTS created — built is
    not wired (hard-won law 2), applied to DATA. It is published here and NOT
    called from the issue path: seeding a tenant's template as a side effect of
    billing would make the first bill run decide what every future bill looks
    like.

NOT published here, and deliberately: `issue_credit_note` (GT-6). The seam names
it and it stays a stub — see that seam's docstring and the build report. Issuing
a correction document and emitting its ledger handoff are bill-run work the
Product Owner has held ("i need to give you multiple inputs — so run with me
before you build"), and B5 GT-6 freezes the balance arithmetic but explicitly
NOT the journal entry's accounts or amount. A pure function that reported a
balanced pair it never posted would be a guarantee in a docstring rather than in
the code — hard-won law 1, and exactly the shape of defect that reached
production once already.
"""

from typing import Any

from apps.billing.dispute_ageing import open_dispute_for_account
from apps.billing.late_fee import (
    NO_DISPUTE,
    NO_LATE_FEE_TERMS,
    DisputeExclusion,
    LateFeeTerms,
    PaymentReceipt,
    ageable_portion,
    assess_late_fee,
    assess_late_fee_for_plan,
    late_fee_terms_for_plan,
    overdue_portion,
)
from apps.billing.selectors import (
    charge_line_count,
    tariff_version_issued_bill_count,
    financial_records_exist,
    plan_invoice_count,
    reason_code_used_by_count,
)
from apps.billing.templates_service import seed_platform_default as seed_bill_templates

#: `overdue_portion` and `PaymentReceipt` are published alongside the fee for
#: one reason: BR-BIL-071 (PO 2026-08-11) makes WHICH DATE decides lateness a
#: rule, and a caller that computed the overdue portion for itself would be free
#: to compute it from the import date — which is exactly what the PO ruled
#: against. One implementation, reachable by name, is what makes the ruling
#: enforceable rather than advisory.
#:
#: `ageable_portion`, `DisputeExclusion`, `NO_DISPUTE` and
#: `open_dispute_for_account` are published for the SAME reason, one rule later:
#: BR-MET-133 clause 4 (PO 2026-08-26) says the disputed amount does not age,
#: and a caller that subtracted it for itself would be free to subtract it after
#: the $25.00 balance floor instead of before — a different answer on a $60.00
#: bill with $40.00 disputed ($5.00 against $0.00). One implementation,
#: reachable by name.
#: `assess_late_fee_for_plan`, `late_fee_terms_for_plan`, `LateFeeTerms` and
#: `NO_LATE_FEE_TERMS` are published for the same reason a third time, and this
#: one is a REVERSAL rather than an addition. BR-RAT-1011 (`CR-078`, PO ruling
#: 2026-09-07, finance re-signed): the two terms come from the charge code the
#: PLAN names, and *"if plan doent provide you that charge code then you have
#: to put zero on late payment"*. `assess_late_fee` still exists and still
#: takes `percent` and `minimum` — GT-8 calls it that way and its ❄️ FROZEN
#: 8.13 is untouched — but a PRODUCTION caller must use the plan form, because
#: a caller free to choose its own two numbers is free to reinstate the tenant
#: default the PO ruled against.
__all__ = [
    "sample_record_count",
    "remove_sample_records",
    "seed_sample_records",
    "seed_sample_second_cycle",
    "seed_sample_correction",
    "NO_DISPUTE",
    "NO_LATE_FEE_TERMS",
    "DisputeExclusion",
    "LateFeeTerms",
    "PaymentReceipt",
    "ageable_portion",
    "assess_late_fee",
    "assess_late_fee_for_plan",
    "late_fee_terms_for_plan",
    "charge_line_count",
    "tariff_version_issued_bill_count",
    "financial_records_exist",
    "open_dispute_for_account",
    "overdue_portion",
    "plan_invoice_count",
    # ⚠ **DEF-708 — THE "no ad-hoc charge service" THIS MODULE DID NOT HAVE.**
    # `apps/customers/disconnects.FEE_POSTED (formerly FEE_NOT_POSTED)` names this exact absence:
    # *"Measured 2026-08-25: `apps.billing.services.__all__` publishes
    # `assess_late_fee` and no ad-hoc charge service, so there is no
    # owning-module service to hand this to"* — so the $75.00 reconnection fee
    # BR-CUS-104 makes owed at the cut was quoted and never charged. This is
    # that service. See `apps/billing/fee_bill.py`.
    "raise_charge_fee",
    "raise_and_issue_charge_fee",
    # DEF-PAY-10698 (PO 2026-10-30) — the NSF penalty a bounce charges, found
    # account → unit → plan → the plan's NSF code. Payments calls these BY
    # NAME (`payments.billing_seam`). See `apps/billing/nsf_fee.py`.
    "quote_nsf_fee",
    "raise_nsf_fee",
    # ⚠ **CR-052 W0 task 1 — THE FINAL METERED BILL A DISCONNECTION RAISES AT
    # THE CUT.** PO ruling 2026-08-30 (*"when we disconnect - we generate final
    # bill at that time itself"*), closing OQ-1170. Customers may not write an
    # invoice (BR-CUS-037 / B1), so `commit_cut` asks through this name. See
    # `apps/billing/cut_bill.py`.
    "preview_final_bill",
    "estimate_closing_usage",
    # DEF-CUS-10093 (PO 2026-10-13, option B) — the move-out's Complete drafts
    # the final bill before the close. See `final_bill.draft_move_out_final_bill`.
    "draft_move_out_final_bill",
    # DEF-NOT-10536 (PO 2026-10-22) — the drafted final bill's page, due date
    # and total for the move-out email. See `final_bill_email`.
    "final_bill_email_document",
    "raise_and_issue_cut_bill",
    "reason_code_used_by_count",
    "seed_bill_templates",
]


# ══════════════════════════════════════════════════════════════════════════
# DEF-708 — A TENANT CHARGE CODE, RAISED AS A REAL RECEIVABLE
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders, exactly like the sample-data block below: the seam contract
# names `apps.billing.services.raise_and_issue_charge_fee` and the
# implementation lives in the module that owns the reasoning
# (`apps/billing/fee_bill.py`). A caller in another module resolves this path
# BY NAME and never imports billing.
from apps.billing.fee_bill import (  # noqa: E402
    raise_and_issue_charge_fee,
    raise_charge_fee,
)
from apps.billing.nsf_fee import quote_nsf_fee, raise_nsf_fee  # noqa: E402,F401

# ══════════════════════════════════════════════════════════════════════════
# CR-052 W0 TASK 1 — THE DISCONNECT IS THE WHOLE EVENT (PO 2026-08-30)
# ══════════════════════════════════════════════════════════════════════════
# The same thin-forwarder shape, one rule along: the seam contract names
# `apps.billing.services.raise_and_issue_cut_bill`, G20 harvests that exact
# path, and the reasoning lives in `apps/billing/cut_bill.py`. Customers
# resolves this BY NAME and never imports billing.
from apps.billing.cut_bill import raise_and_issue_cut_bill  # noqa: E402

# ══════════════════════════════════════════════════════════════════════════
# S20 STEP 3 — THE FINAL-BILL PREVIEW (PO 2026-09-19, *"we need to do it"*)
# ══════════════════════════════════════════════════════════════════════════
# The same thin-forwarder shape again: the seam contract names
# `apps.billing.services.preview_final_bill`, G20 harvests that exact path,
# and the reasoning lives in `apps/billing/final_bill.py`. Customers resolves
# this BY NAME and never imports billing.
#
# ⚠ **IT IS A READ.** Unlike `raise_and_issue_cut_bill` two lines up, this one
# writes NOTHING — no invoice, no journal line, no bill number. The Billing
# blueprint p112 settles it: *"NO BILL IS ISSUED BY THIS SCREEN. Billing
# raises the final bill; this wizard prices what it will contain and posts
# nothing."* The two doors sit together on purpose, because the difference
# between them is the whole of what step 3 is allowed to do.
from apps.billing.final_bill import (  # noqa: E402
    draft_move_out_final_bill,
    estimate_closing_usage,
    preview_final_bill,
)
from apps.billing.final_bill_email import final_bill_email_document  # noqa: E402

# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — billing's block (BR-TEN-056 as AMENDED 2026-08-16)
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders: the seam contract names `apps.billing.services.
# seed_sample_records`, G20 harvests that exact path, and the implementation is
# large enough to deserve its own file. The import is inside each function
# because `sample_data` drives the same run services a clerk's click uses.


def seed_sample_records(actor: Any) -> int:
    """**CYCLE ONE.** June issued.

    ⚠ **THIS DOCSTRING SAID "June and July issued" AND WAS WRONG FOR TEN DAYS.**
    CR-010 Part-10.4 (PO 2026-08-17) cut the fixture to one billed month and
    this sentence was not corrected with it, so a reader of the seam contract
    was told the product did something it had stopped doing — the stale-comment
    failure (hard-won law 1) sitting on the published name a gate harvests.
    Two cycles are billed again since CR-040 task C8, and they are billed by
    **two seams**: this one and `seed_sample_second_cycle` below.
    """
    from apps.billing import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_second_cycle(actor: Any) -> int:
    """**CYCLE TWO.** July issued, after the money. AUGUST IS THE PO'S OWN RUN.

    A separate published seam rather than a flag on the one above, because the
    orchestrator's ordering is what CR-040 asked for: the payments block runs
    BETWEEN them, so the estate this cycle bills already carries collections, a
    credit balance, a refund and an overcharge correction.
    """
    from apps.billing import sample_data

    return sample_data.seed_sample_second_cycle(actor)


def seed_sample_correction(actor: Any) -> int:
    """The seeded OVERCHARGE, corrected — spec §4 case 15 (CR-040 task D13).

    ⚠ **PUBLISHED HERE BECAUSE A BLOCK NOBODY CAN RESOLVE IS A BLOCK THAT DOES
    NOT RUN.** `apps.tenancy.sample_data` reaches every block through
    `seams.resolve(module, seam)`, which looks in `apps.<module>.SERVICES` —
    never in `sample_data`. A seam written only in `sample_data.py` resolves to
    None, the orchestrator SKIPS the block as "seam not wired", and the load
    reports a healthy tenant with no correction in it: hard-won law 2 in its
    seam form.
    """
    from apps.billing import sample_data

    return sample_data.seed_sample_correction(actor)


def remove_sample_records() -> dict[str, Any]:
    """0, and WHY — an issued bill is append-only (hard rule 4)."""
    from apps.billing import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    from apps.billing import sample_data

    return sample_data.sample_record_count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — GT-8 companion seam)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no billing endpoints yet) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-8 PASS✔ · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# revised: 2026-08-11 (late-fee rulings lane) — publishes `overdue_portion` and `PaymentReceipt` as well, so BR-BIL-071's "the ACTUAL date the money arrived, never the posting or import date" exists in one place a caller resolves by name instead of being a sentence each caller re-derives. `rating_seam.assess_late_fee` is UNCHANGED and still forwards the seven GT-8 terms; the $25.00 balance floor rides its default (BR-BIL-001 as amended 2026-08-11), which is why GT-8 reaches 8.13 through this re-export untouched.
# exceptions: `issue_credit_note` (GT-6) is NOT published — the PO has held bill issuance, documents and the ledger, and B5 freezes GT-6's balance but neither the accounts nor the amount of its "balanced reversing journal entry". GT-6 stays xfail at the seam, reported.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

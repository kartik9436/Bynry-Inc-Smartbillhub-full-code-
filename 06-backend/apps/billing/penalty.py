# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-014 (S30 One-time bill tab with a theft reason · S31 —
#           assessed reads priced by the ENGINE plus charge-code penalties,
#           never hand-typed)   Screens: S30 · S31
# Rules:    BR-BIL-019 (penalty bills: charge-code lines only — hand-typed
#           amounts NEVER exist on any bill; theft/unmetered consumption enters
#           as assessed/estimated READS, reason-coded and flagged, which
#           back-billing prices; approval-gated) · BR-BIL-018 (theft cases are
#           EXEMPT from the back-bill window cap — OQ-071 CLOSED) · BR-BIL-007
#           (TAMPER etc. are tenant charge codes with their own GL — the amount
#           comes from the code, never typed) · BR-MET-053 (assessed reads
#           enter through the metering lifecycle, reason-coded and flagged,
#           append-only) · BR-BIL-014 (the approval gate) · BR-RAT-007 (price
#           on the SERVICE date)
# Golden:   GT-27 (= WE-11, ❄️ B5 FROZEN, finance-signed 2026-08-08): assessed
#           on 150 → 33.00 · mid 300 → 42.00 · off 450 → 40.50 = taxable
#           **115.50** → tax **10.92** → plus TAMPER **500.00** (fee,
#           non-taxable) → total **626.42**.
# Tests:    06-backend/tests/test_us_bil_014_penalty.py
# Impacts:  apps/billing/backbill.py (this IS its pricing pass, cap-exempt) ·
#           apps/metering (the assessed-read lifecycle it consumes)
# ───────────────────────────────────────────────────────
"""Theft / penalty bill: two ingredients, and a typed amount is not one of them.

BR-BIL-019 is unusually specific about WHAT a penalty bill may be made of,
because the obvious implementation is the forbidden one. A clerk who finds a
bypassed meter knows roughly what was stolen and what the penalty should be,
and every billing system that lets them type those two numbers produces bills
nobody can defend. So the rule names the only two ingredients:

  1. **assessed/estimated READS**, entered through the metering lifecycle,
     reason-coded and flagged (r10 #14 / BR-MET-053), which BACK-BILLING then
     prices — on the tariff versions in force during the stolen period, per
     sub-period, exactly as US-BIL-013 does. This module does not price
     anything itself; it calls `apps.billing.backbill`, cap-exempt.
  2. **charge-code lines** (WE-11's TAMPER $500.00), whose amount comes from
     the tenant's charge code and its own GL (BR-BIL-007).

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE.** This path was added to
`10-scripts/gates/human_owned.txt` by PO ruling 2026-09-30 (option A, commit
`dabb8a323`, with 51 others), so `G7` reads its markers now.

🔒 **HUMAN-OWNED · HUMAN-REVIEW-PENDING** (CLAUDE.md 🔒 sensitive paths, PO
ruling 2026-08-09 *"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`. ⚠ **ADDED 2026-09-15 BY
`DEF-BIL-5317`, WHICH IS WHEN THIS FILE STARTED DECIDING WHAT A BILL CHARGES**
— until then every charge code refused, so the file decided nothing and carried
no marker. ⚠ **AND NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS
PATH, so `G7` does not check these markers.** Adding a glob is a PROCESS EVENT
and the PO's call, not a lane's (the same rule that stopped the pricing lane
adding one) — it is reported in the review-ledger row rather than taken here.
`apps/billing/final_bill.py` is the same escape and is reported with it.

⚠ **BOTH INGREDIENTS NOW BUILD — THE SECOND ONE ONLY SINCE 2026-09-15.** This
docstring said *"WHAT IS BUILDABLE TODAY IS HALF OF THAT"* and gave as the
reason *"There is no charge-code reader … rating publishes no seam that turns a
code into an amount and a GL account"*. **That was false from 2026-08-27**, when
`DEF-708` pointed `fee_bill.charge_code_line` at
`apps.rating.selectors.charge_by_code`; `first_bill`'s connection charge and
`decisions`' late fee read the same seam. This module went on refusing every
code for nineteen days because it named the seam as a module CONSTANT rather
than asking `gather._resolve` for it at call time — **and its own tests
asserted the refusal, so the suite was green over a capability that existed**
(hard-won law 1: a comment claiming a guarantee is not the guarantee, and here
it claimed an ABSENCE). A theft bill restated the stolen usage and carried no
tamper fee at all. `penalty_charge_line` now delegates; in the demo tenant
`TAMPER` is **$250.0000** and reaches the document as a non-taxable fee line.

WHAT IS STILL MISSING, and it is not this lane's to invent:

  * **Metering has no `assessed` flag.** Its reads carry `estimated` (a routine
    VEE substitute) and nothing that says "restated because this meter was
    tampered with". They are different facts and this module does not treat one
    as the other; the absence is STAMPED onto the bill's own payload rather
    than assumed away, so a reprint says which reads it could not verify.

WHAT IS BUILDABLE — and it is the part that carries the money — is the pricing:
assessed reads for a stolen period, split at every tariff-version boundary,
priced on the versions in force THEN, with the tenant's back-bill window cap
NOT applied because BR-BIL-018's closure exempts theft. That is real, tested
and the reason a 14-month theft case can be billed at all (US-BIL-014 TC-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from apps.billing import backbill, fee_bill, gather, models, rating_seam

#: Why a penalty bill is refused, or what it could not verify. VALUES — S30
#: groups on them, like every other reason code in this module set.
#:
#: ⚠ **`PENALTY_NO_CHARGE_CODE_READER` IS NO LONGER RAISED BY
#: `penalty_charge_line` AND IS KEPT ONLY SO AN OLD STORED REASON STILL READS
#: (`DEF-BIL-5317`, 2026-09-15).** The seam it named — `apps.rating.selectors
#: .charge_by_code` — has been published FOR BILLING and read by
#: `fee_bill.charge_code_line` since `DEF-708` on 2026-08-27, and by
#: `first_bill`'s connection charge and `decisions`' late fee besides. This
#: module went on refusing every code because it named the seam as the module
#: CONSTANT `CHARGE_CODE_READ = "charge_ref"` — a string rating never published
#: under that name — instead of ASKING `gather._resolve` for it at call time as
#: its three siblings do. The refusal is now `fee_bill`'s, by delegation.
PENALTY_NO_CHARGE_CODE_READER = "charge_code_reader_not_published"
PENALTY_ASSESSED_FLAG_UNVERIFIABLE = "assessed_read_flag_not_published"

#: ⚠ **REMOVED 2026-09-15 — `CHARGE_CODE_READ = "charge_ref"` (`DEF-BIL-5317`).**
#: It is deleted with its reason rather than corrected to the right string
#: (hard-won law 1), because the lesson is that a module must not hold a NAME
#: for a seam at all: a constant cannot go stale loudly. `gather._resolve` is
#: asked at call time, once, inside `fee_bill.charge_code_line`, and a seam that
#: arrives or leaves is then visible to every caller on the next call instead of
#: to whoever remembers to re-read a literal.


@dataclass(frozen=True)
class PreparedPenaltyBill:
    """A theft case ready to price: the back-bill groups plus what is unverified.

    `assessed_unverifiable` is None once metering flags assessed reads; today
    it always carries the reason, and it travels ONTO THE BILL (see
    `calculate_penalty_bill`) rather than being logged and forgotten. A penalty
    bill is the document a customer disputes and a regulator reads; "these
    reads could not be shown to be assessed" belongs on it.
    """

    back_bill: backbill.PreparedBackBill
    charge_codes: tuple[str, ...]
    assessed_unverifiable: str | None
    #: ⚠ **`DEF-BIL-5317` — THE BUILT LINES, RESOLVED AT PREPARE.** One
    #: `RatedLine` per requested code, each from the TENANT's own charge-code row
    #: (BR-BIL-007) through `fee_bill.charge_code_line`. They are built HERE, in
    #: phase 1, because phase 1 writes nothing: a code this tenant does not have,
    #: a retired one, a `percent` rule with no basis or a code with no GL account
    #: must refuse BEFORE a draft exists and before an invoice number is spent.
    #: Empty when the clerk requested no code — a penalty bill may be restated
    #: usage and nothing else.
    charge_lines: tuple[Any, ...] = ()

    @property
    def account_no(self) -> str:
        return self.back_bill.account_no

    @property
    def groups(self) -> tuple[backbill.BackBillGroup, ...]:
        return self.back_bill.groups


def assessed_reads_verifiable() -> str | None:
    """None when metering can prove a read is ASSESSED — otherwise the reason.

    r10 #14 and BR-MET-053 give an assessed read a flag and a reason code.
    `apps.metering.selectors.billing_reads_for_unit` publishes `estimated` and
    an `absent_reason`, and nothing else about how a read came to exist. An
    estimate is a routine substitute produced by the VEE rules; an assessed
    read is a restatement of consumption somebody took without paying for it.
    Treating the first as evidence of the second would let an ordinary
    estimated month be billed as theft, which is a claim about a customer that
    this code has no basis to make.
    """
    reads = gather._resolve("metering", "billing_reads_for_unit")
    if reads is None:
        return (
            "apps.metering.selectors.billing_reads_for_unit is not published, so no "
            "read — assessed or otherwise — can be consumed (BR-MET-053)."
        )
    return (
        "metering publishes no ASSESSED flag on a read (r10 #14 / BR-MET-053): its "
        "reads carry `estimated`, which is a VEE substitute and not a tamper "
        "restatement. This bill's reads are the committed reads for the period and "
        "are NOT shown to be assessed. US-BIL-014 TC-6 — 'blocked while the assessed "
        "reads are still unflagged drafts' — therefore cannot be enforced here."
    )


def penalty_charge_line(code: str) -> rating_seam.RatedLine:
    """BR-BIL-019's charge-code line, built by the ONE builder that builds them.

    ⚠ **THIS DOCSTRING SAID *"REFUSES: no reader exists … rating publishes no
    read that resolves one"* UNTIL 2026-09-15, AND IT WAS FALSE
    (`DEF-BIL-5317`, hard-won law 1 — a comment claiming a guarantee is not the
    guarantee, and here it claimed an ABSENCE that had stopped being true).**
    `apps.rating.selectors.charge_by_code` is published FOR BILLING and has
    three live consumers in this same app: `fee_bill.charge_code_line` since
    `DEF-708` on 2026-08-27, `first_bill`'s connection charge, and `decisions`'
    late fee. This function alone went on raising, for every code, in every
    tenant — because it named the seam as a module CONSTANT rather than asking
    `gather._resolve` for it at call time, and **its own tests asserted the
    refusal**, so the suite was green over a capability that existed. A penalty
    bill therefore restated the stolen usage and carried no tamper fee at all.

    **It DELEGATES rather than resolving the seam itself**, which is the repair
    the defect asked for: two opinions about whether a charge code can be priced
    is how the two drifted apart, and `fee_bill.charge_code_line` is the one
    place that answer lives. Its four refusals travel with it, unchanged and
    still refusing — no such code for this tenant (or a retired one, or another
    tenant's), a `percent` / `percent_with_minimum` rule whose `amount` is
    `None` because there is no basis to apply, and a code with no GL account.

    ⚠ **THE AMOUNT IS THE TENANT'S AND IS NEVER TYPED HERE.** In the demo
    tenant `TAMPER` is **$250.0000**; WE-11 and the blueprint both draw
    **$500.00**, and B14 rule 37 is explicit that a figure drawn in a wireframe
    is an ILLUSTRATION and never a fact to build to. `Decimal("500")` in this
    file would be the hand-typed amount BR-BIL-019 forbids and would be wrong
    for every tenant but one.
    """
    return fee_bill.charge_code_line(code)


def prepare_penalty_bill(
    *,
    account_id: Any,
    sub_periods: Any,
    reason_code: str,
    charge_codes: tuple[str, ...] = (),
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
    waiting_ok: bool = False,
) -> PreparedPenaltyBill:
    """Phase 1 of a theft case. Writes nothing.

    `theft=True` on the back-bill is what makes a 14-month restatement legal
    (BR-BIL-018 / OQ-071: theft cases are EXEMPT from the window cap) — and it
    is the ONLY thing the flag exempts. The case is still reason-coded and
    still approval-gated.
    """
    prepared = backbill.prepare_back_bill(
        account_id=account_id,
        sub_periods=sub_periods,
        reason_code=reason_code,
        theft=True,
        scope_services=scope_services,
        # DEF-BIL-8324 — step 2's typed readings, used first (preview only).
        keyed_reads=keyed_reads,
        waiting_ok=waiting_ok,
    )
    # `DEF-BIL-5317` — resolved in PHASE 1, which writes nothing. Every reason a
    # charge code cannot be priced is therefore reported to the clerk while the
    # only cost is their time; after this point a draft exists and an invoice
    # number has been spent. `charge_code_line` raises, so an unpriceable code
    # stops the whole prepare rather than dropping one line quietly — which is
    # the posture `calculate_penalty_bill` already took and stated.
    lines = tuple(penalty_charge_line(code) for code in charge_codes)
    return PreparedPenaltyBill(
        back_bill=prepared,
        charge_codes=tuple(charge_codes),
        assessed_unverifiable=assessed_reads_verifiable(),
        charge_lines=lines,
    )


def calculate_penalty_bill(
    prepared: PreparedPenaltyBill,
    *,
    bill_run: models.BillRun,
    service_date: date | None = None,
) -> models.Invoice:
    """Price the assessed reads through back-billing; draft ONE bill, typed `penalty`.

    ⚠ **THE CHARGE-CODE LINES NOW REACH THE DOCUMENT (`DEF-BIL-5317`,
    2026-09-15).** This loop used to call `penalty_charge_line(code)` purely for
    the exception it always raised, and then price the back-bill WITHOUT it — so
    even once the refusal was lifted the line would have gone nowhere. They are
    built at PREPARE (phase 1 writes nothing, so an unpriceable code costs a
    clerk their time and not an invoice number) and carried here on
    `extra_fees`, the bill-level channel the carried lines and the account's own
    fees already travel. A penalty bill that silently dropped its penalty is
    still the worst of the available failures: it looks complete, the customer
    pays the restated usage, and the tamper fee is never charged at all.
    """
    return backbill.calculate_back_bill(
        prepared.back_bill,
        bill_run=bill_run,
        service_date=service_date,
        bill_type="penalty",
        extra_fees=prepared.charge_lines,
        extra_snapshot={
            "penalty": {
                "reason_code": prepared.back_bill.reason_code,
                "theft_case": True,
                "cap_exempt": True,
                "charge_codes": list(prepared.charge_codes),
                # `DEF-BIL-5317` — WHAT WAS CHARGED, not merely which code was
                # asked for. BR-BIL-030 locks this payload at issue, so a
                # reprint or a dispute in 2033 reads the amount this bill
                # actually carried rather than today's charge-code row, which
                # the tenant is free to re-price tomorrow.
                "charge_lines": [
                    {"description": line.description, "amount": str(line.amount)}
                    for line in prepared.charge_lines
                ],
                # STAMPED, not logged. BR-BIL-030 locks this payload at issue,
                # so a reprint in 2033 still says which reads this bill could
                # not prove were assessed.
                "assessed_flag_unverifiable": prepared.assessed_unverifiable,
            }
        },
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-014@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane — US-BIL-011..014)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's One-time tab is unbuilt) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_014_penalty.py
# exceptions: (1) THE CHARGE-CODE HALF CANNOT BE BUILT. Rating publishes no
#         charge-code read, so WE-11's TAMPER 500.00 line REFUSES by name.
#         `apps/billing/decisions.py` refuses its `extra_charge` case on the
#         same missing seam — REPORTED (a `charge_ref(code)` returning amount +
#         gl_account_id would close both at once). Nothing is substituted: a
#         literal 500 here would be the hand-typed amount BR-BIL-019 forbids,
#         and the prototype's own card says $250 for the same code.
#         (2) WE-11's USAGE FIGURES ARE NOT REPRODUCIBLE EITHER, for a reason
#         one layer down: they are TOU (summer on/mid/off 0.22/0.14/0.09) and
#         the rating engine implements flat and tiered only — its own docstring
#         lists TOU as unimplemented with no frozen figure to bind to. So GT-27
#         is quoted in this file's Golden header as the specification and is
#         asserted nowhere as a passing figure. A fabricated flat tariff that
#         happened to total 115.50 would be a green test proving nothing.
#         (3) NO ASSESSED FLAG EXISTS in metering (r10 #14 / BR-MET-053), so
#         US-BIL-014 TC-6 cannot be enforced. The absence is STAMPED onto
#         `bill_payload` — locked at issue by BR-BIL-030 — rather than assumed
#         away, and `estimated` is deliberately NOT treated as evidence of
#         assessment: a VEE substitute is not a tamper restatement.
#         (4) The approval gate is not enforced here either — see
#         apps/billing/backbill.py's trailer, exception (5). Same gap, one
#         cause: US-BIL-017's machinery does not exist.
#         (5) This module PRICES NOTHING. It composes `backbill`, which is the
#         rule BR-BIL-019 states ("back-billing prices them") and also the
#         reason a theft bill and a catch-up bill can never round differently.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

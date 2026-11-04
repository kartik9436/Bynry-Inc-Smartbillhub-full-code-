# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data) · US-PAY-001 (record a
#           payment)   Screens: S22, S32, S37 · S8 (Sample data panel)
# Rules:    BR-TEN-056 as AMENDED 2026-08-16 (the sample set reaches money) ·
#           BR-TEN-063 (idempotent, audited) · BR-TEN-066 (removal is
#           partial-and-named) · BR-PAY-022 (the record-a-payment field set) ·
#           BR-PAY-028 (idempotency) · BR-PAY-038 (allocation class order —
#           usage+base → tax → fees LAST) · CLAUDE.md rule 2 (money carries its
#           currency) · hard rule 4 (a payment is append-only)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py ·
#           06-backend/tests/test_def_pay_6321_seeded_deposit_batches.py
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves the seam;
#           `DEF-PAY-6321` also moved `tenancy:seed_sample_portal_content`
#           ahead of the money blocks, because a counter is a till AT a place)
# ───────────────────────────────────────────────────────
"""payments' half of the sample set: the money in (DEF-153).

WHAT THE SPEC ASKS FOR, AND WHAT IS HERE
------------------------------------------
Spec §3 AS AMENDED 2026-08-17 (CR-010 Part-10.4, PO verbatim: *"do 1 month
billed na dkeep other month ready"*): **JUNE is billed and ~95% collected;
JULY is READY-TO-RUN and therefore has nothing to pay** — the spec's old
*"July ~80% collected"* is superseded with its period's billing. §5 stands:
*"one busy day (8 August) with mixed methods"* — cheques, cash, card and ACH —
so deposit batches and bank reconciliation have something real to group.

Every payment goes through `record_payment`, the S22 form's own call, so
BR-PAY-038's allocation order (usage+base → tax → fees LAST) is the product's
and not the fixture's, and every one carries its **currency** beside its amount
(CLAUDE.md rule 2).

THE AWKWARD CASES THIS MODULE OWNS (spec §4)
---------------------------------------------
* **case 4 — two partial payments.** Half of one bill (the JUNE bill, the only
  one issued since the 2026-08-17 amendment), so the allocation order is
  visible on a real account rather than only in a test.
* **case 6 — the payment plan's MONEY.** The plan rows themselves are written
  by customers' `seed_sample_payment_plans` block through the S24 wizard's own
  path; THIS module then records the down payment (purpose `plan_down`,
  BR-PAY-012) and the paid instalments through `record_payment` — the only
  writer of `payments` — and links each instalment through
  `record_installment_payment` (BR-PAY-021: on-time-ness is the POSTING date).
  Its June bill is deliberately left unpaid below, because a plan spreads a
  debt that exists (US-CUS-018 TC-6).
* **case 8 — one account 70 days past due.** It is created by NOT paying: the
  June bill of one account is left alone, so by 8 August it is genuinely in the
  60+ ageing bucket rather than being stamped there. (Unchanged by the July
  amendment — this case was always June's; see core/sample_fixture.py.)
* **case 11 — a credit balance.** One account overpays, and the surplus carries
  as a credit exactly as the allocator decides it should.

WHAT IS **NOT** SEEDED HERE, AND IT IS NAMED RATHER THAN QUIETLY MISSING
-------------------------------------------------------------------------
The bounced cheque (case 5), the write-off awaiting approval (case 7), the
goodwill credit (case 12) and the bank statement with its non-tying card day
(spec §5) are **NOT** written by this lane. Each needs a service call this lane
did not have the budget to drive correctly, and a half-driven money path is
worse than an absent one. They are reported by name in `NOT_SEEDED` below,
which the Sample data panel renders, so a reader sees a gap rather than
assuming the fixture is complete. The payment plan LEFT this list on
2026-08-17 — CR-010 Part-10.4 amendment 3 seeds it as real rows.

⚠ **THE DEPOSIT BATCHES LEFT IT ON 2026-09-23 (`DEF-PAY-6321`), AND WHY THEY
WERE STILL ON IT IS THE PART WORTH READING.** The Product Owner opened the
Payments list on the deployed build and found the BATCH column reading *No
batch yet* on **every** row while SOURCE read *Counter* — a counter payment
with no batch, which is self-contradictory on its face. The column was not
wrong: this file had never made a batch, said so honestly in `NOT_SEEDED`
since 2026-08-16, and **nothing ever counted that sentence**. A declared
absence reads as candour and gets filed as a record instead of as a debt, so
it outlived four screens that were built on top of it. Batches are seeded now,
through the counter's own door — see the till block below `_instant`.
"""

from __future__ import annotations

import itertools
import logging
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.payments import idempotency, models, services
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.payments")

ZERO = Decimal("0")

#: Spec §5's mixed methods, cycled deterministically so one busy day carries
#: cheques, cash, card and ACH rather than 48 identical rows.
METHODS: tuple[str, ...] = ("check", "cash", "card", "ach")

#: `DEF-PAY-8756` — the tenders a second-cycle collection takes when it falls
#: on the busy day after that day's drawer was sealed: none passes through a
#: person's hands, so none needs an open till.
AFTER_THE_DRAWER: tuple[str, ...] = ("card", "ach")


def _reference_for(method_code: str, index: int) -> str | None:
    """What a clerk or a gateway would really put in `confirmation`.

    ⚠ **`DEF-CWP-3974` — THIS COLUMN WAS SEEDED WITH A BILL NUMBER AND THE
    PORTAL PRINTS IT AS THE CUSTOMER'S REFERENCE.** Every row of `CWP-041` read
    `SAMPLE-BL-2608-000077`: `confirmation=f"SAMPLE-{invoice.invoice_no}"`, an
    INVOICE number wearing a seed prefix, in the column CLAUDE.md hard rule 4
    calls *"the cheque or confirmation number"*. Nothing looked wrong because
    the column always held a real value, and a test asserting the cell is
    non-empty passes over the wrong FIELD.

    `CWP-041.png` shows what belongs there — `#10188` on a cheque,
    `Chase ••••4021` on a bank transfer, `Visa ••••8812` on a card — so each
    tender now seeds the reference that tender actually produces. **Cash gets
    NONE**, which is right: a cash payment has no reference and the portal falls
    back to the `PMT-` number a customer can read out on the telephone.

    ⚠ **THIS CHANGES NOTHING ALREADY WRITTEN** (hard-won law 4's shape for
    data): a tenant seeded before today keeps `SAMPLE-…` in the column until it
    is seeded again. Say so rather than implying the screen is fixed everywhere.
    """
    if method_code == "check":
        # A cheque number is what the customer wrote on the cheque.
        return str(10100 + index * 7)
    if method_code == "card":
        return "Visa \u2022\u2022\u2022\u20228812"
    if method_code == "ach":
        return "Chase \u2022\u2022\u2022\u20224021"
    return None


#: Named, never silently absent — see the module docstring.
#: ⚠ THE PAYMENT PLAN LEFT THIS LIST 2026-08-17 (CR-010 Part-10.4): it is now
#: seeded as REAL rows — the plan by customers' wizard block, its money below.
NOT_SEEDED: tuple[dict[str, str], ...] = (
    {"what": "the bounced cheque (NSF) and its fee", "reason": "spec §4 case 5 — not driven by this lane"},
    {"what": "the write-off awaiting approval", "reason": "spec §4 case 7 — not driven by this lane"},
    {"what": "the goodwill credit", "reason": "spec §4 case 12 — not driven by this lane"},
    # ⚠ **THE DEPOSIT BATCHES LEFT THIS LIST 2026-09-23 (`DEF-PAY-6321`) AND
    # THE BANK STATEMENT DID NOT.** They were one entry and they are two facts:
    # the batches are now seeded, through the counter's own door, because the
    # Payments list has a BATCH column and over this fixture it could only ever
    # read *No batch yet*. The statement — spec §5's card day that does NOT tie
    # — still needs `reconciliation`'s import path driven and is still absent.
    # A named absence is a DEBT: this one had been standing since 2026-08-16
    # with nothing counting it, which is `DEF-PAY-6321`'s escape reason.
    {"what": "the bank statement (the card day that does NOT tie)", "reason": "spec §5 — not driven by this lane"},
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _instant(day: Any) -> datetime:
    """The caller names the moment — G6 bans a clock from a money path."""
    return datetime.combine(day, time(11, 0), tzinfo=dt_timezone.utc)


# ════════════════════════════════════════════════════════════════════════════
# `DEF-PAY-6321` · THE TILL THE COUNTER MONEY IS TAKEN INTO
# ════════════════════════════════════════════════════════════════════════════
# The Product Owner opened the Payments list on the deployed build and found
# **BATCH reading *No batch yet* on every row while SOURCE read *Counter***. The
# column was telling the truth: `NOT_SEEDED` above declared the deposit batches
# out of scope on 2026-08-16 and nothing ever came back for them, so the answer
# was structurally *no* on a fixture that has never held a single batch.
#
# ⚠ **THE BATCH IS NOT SOMETHING THIS FILE MAY WRITE.** `payments/0033`'s
# `trg_deposit_batch_needs_session` refuses a batch with no counter session, and
# a row INSERTed here would be data the product could never have made. So the
# money goes in the way a clerk's money goes in: a till is OPENED, payments are
# taken INTO it, and it is SEALED — `counters.open_counter` →
# `services.record_payment(counter_session_id=…)` → `counters.close_counter`.
# `record_payment` opens the batch for a tender inside that payment's own
# transaction (`P2.13`), and the close foots it so Finance → Deposits shows a
# real figure rather than `$0.00`.
#
# ⚠ **THE GROUPING IS THE PRODUCT'S AND NOT THIS FILE'S.** `BR-PAY-025` as
# amended 2026-09-22 keys a batch on **one TILL × one TENDER**
# (`uq_deposit_batches_session_method`), and a till is one drawer DAY — so the
# day-and-tender grouping still holds, one layer down, and a shift taking cash
# and cheques ends with TWO batches and one till, which is what the bank sees.
#
# ⚠ **WHAT IS DELIBERATELY LEFT WITH NO BATCH, because *No batch yet* is the
# right answer there and a fixture where every row has one would hide the case
# the column exists to show:** every `card` and `ach` payment this file writes.
# `counters.HAND_TENDERS` is cash, cheques and money orders — the money that
# physically passes through a person's hands — and `services._counter_session`
# REFUSES a card or ACH payment a till BY NAME, because a card total typed back
# into a drawer count would make the reconciliation worthless. The plan's down
# payment (card) and its instalments (ACH) are in that population too.
#
# ⚠ **AND ONE HAND TENDER IS LEFT WITHOUT A BATCH THAT SHOULD HAVE ONE, WHICH
# IS A DEFECT AND NOT A CHOICE — `DEF-PAY-6322`.** The landlord's single cheque
# covering three properties goes through `tenders.record_multi_account_payment`,
# and that door accepts no `counter_session_id`: `P2.13` wired the till at ONE
# of the two doors that take a hand tender and nothing asked whether the other
# had been carried. So three cheque payments, on the busy day, belong to no
# drawer, and **no amount of seeding can change that from here.** It is FILED
# rather than left in this comment (`DEF-GOV-5229`'s lesson — a finding
# recorded only in the file you are standing in is a finding nobody can count),
# and `test_def_pay_6321_seeded_deposit_batches.py` pins the size of that
# population so the exclusion cannot grow and goes RED the day the door is
# wired.

#: The drawer's opening float. p056's worked shift starts on **$200.00** and
#: this is that figure. Four decimals and a `Decimal`, never a float — CLAUDE.md
#: hard rule 2. The CURRENCY is not typed here on purpose: `open_counter`
#: resolves the tenant's own (BR-TEN-042 locks one per utility), so a fixture
#: cannot put a Canadian demo's drawer into dollars it does not hold.
TILL_FLOAT = Decimal("200.0000")

#: A shift brackets the money. `_instant` posts every seeded payment at 11:00,
#: so the till is open before the first receipt and sealed after the last:
#: `services._counter_session` refuses a CLOSED till by name, and an unsealed
#: one never becomes bankable. Derived from the day the caller names — G6 bans
#: a clock from a money path, here as everywhere else in this file.
TILL_OPENS_AT = time(8, 30)
TILL_CLOSES_AT = time(17, 30)


def _till_moment(day: Any, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=dt_timezone.utc)


def _is_counter_tender(method_code: Any) -> bool:
    """Is this money that passes through a person's hands?

    Read from `counters.HAND_TENDERS` rather than re-spelled here — one rule,
    one implementation, the same reason `services._counter_session` reads it.
    Re-spelling it would let this file and the write disagree about what a
    drawer holds, and the disagreement would show up as a refused payment in
    the middle of a seed run.
    """
    from apps.payments import counters

    return str(method_code or "").strip().lower() in counters.HAND_TENDERS


# ── `DEF-PAY-6323` · WHERE THE MONEY CAME FROM IS STATED, NEVER DEFAULTED ───
# Every seeded payment used to take `record_payment`'s default
# `idempotency_source`, which is `entry` — the S22 form's word, correct for a
# person keying a row. `payments.origin` is written FROM that source, and since
# `CR-132-BRC07` the Payments list labels `entry` **Counter**. So every card
# and ACH payment in the demo read *Counter* over money that never reached a
# counter, beside a BATCH column correctly reading *No batch yet* (the PO's
# report of 2026-09-23, `DEF-PAY-6321`'s other half).
#
# ⚠ **THE NAIVE FIX DUPLICATES MONEY, AND THE GUARD AGAINST THAT IS A READ.**
# The source is also the first segment of the idempotency KEY
# (`idempotency.inbound_payment_key`), so a card payment seeded as `webhook`
# is keyed `webhook|sample:BL-…` where the same payment was keyed
# `entry|sample:BL-…` on every tenant seeded before this change. On such a
# tenant `record_payment`'s own replay read asks for the NEW key, finds
# nothing, and records a SECOND permanent payment against every card and ACH
# bill (hard rule 4 — neither could ever be deleted). So before an electronic
# payment is recorded, `_recorded_before_the_source_was_stated` asks for the
# OLD key too, and a hit is answered exactly as `record_payment` answers a
# replay: `created=False`, the original's figures, nothing written.
#
# ⚠ **IT DOES NOT REWRITE THE OLD ROWS AND CANNOT.** `origin` is not on
# `payments/0014`'s allow list, so a tenant seeded before this change keeps
# *Counter* on those rows until it is seeded afresh. The fix is for every
# tenant seeded from now on; it says so rather than implying the screen is
# fixed everywhere (`_reference_for` makes the same admission).
def _source_for(method_code: Any) -> str:
    """`entry` for money a clerk took at a counter; `webhook` for the rest.

    Decided by the same `HAND_TENDERS` question the till block asks, so the
    SOURCE column and the BATCH column can never disagree about which rows
    passed through a person's hands: cash and cheques are keyed at a counter
    and banked in its drawer; card and ACH arrive from a payment processor
    (the `webhook` origin, *Digital* on screen) and bank in no drawer.
    """
    if _is_counter_tender(method_code):
        return idempotency.SOURCE_ENTRY
    return idempotency.SOURCE_WEBHOOK


def _recorded_before_the_source_was_stated(reference: str) -> Any:
    """The payment an earlier seed recorded under the `entry` key, or None.

    One indexed SELECT on `uq_payments_webhook_key`. Asked only for an
    electronic payment — a counter tender's key did not change.
    """
    old_key = idempotency.inbound_payment_key(source=idempotency.SOURCE_ENTRY, reference=reference)
    return models.Payment.objects.filter(tenant_id=_tenant_id(), webhook_key=old_key).first()


def _record_sample_payment(
    actor: Any, *, method_code: str, idempotency_reference: str, **fields: Any
) -> Any:
    """`services.record_payment` with the SOURCE stated — the only way this
    file records a payment (`DEF-PAY-6323`; see the block comment above)."""
    source = _source_for(method_code)
    if source != idempotency.SOURCE_ENTRY:
        earlier = _recorded_before_the_source_was_stated(idempotency_reference)
        if earlier is not None:
            # The replay answer `record_payment` itself gives, from the same
            # module: the original's figures, `created=False`, nothing written.
            return services._replayed(earlier)
    return services.record_payment(
        actor,
        method_code=method_code,
        idempotency_source=source,
        idempotency_reference=idempotency_reference,
        **fields,
    )


def _walk_in_counter() -> Any:
    """The service centre this shift is worked at — the utility's first.

    A counter is a till AT a place (`counters._service_centre` refuses one that
    names none), and the sample utility's centres are seeded by
    `tenancy:seed_sample_portal_content`, which was moved ahead of the money
    blocks for exactly this (`DEF-PAY-6321`). Ordered by the screen's own
    `position` so the demo's till is always at the same desk — *Main office* —
    rather than at whichever row a uuid sort happened to put first.
    """
    from apps.tenancy import published_content_models as places

    return (
        places.ServiceCentre.objects.filter(tenant_id=_tenant_id())
        .order_by("position", "created_at")
        .first()
    )


def _open_sample_till(actor: Any, *, day: Any) -> tuple[Any, str | None]:
    """This day's till, or `(None, why not)` — never a silent absence.

    Returns the OPEN session the day's counter money goes into. The second
    member is a refusal a caller can report; `DEF-167`'s rule applies here as
    much as to the bills read — a fixture that could not do what it says
    reports it rather than leaving a column empty and looking finished.

    **Idempotent by the MOMENT, not by a flag** (BR-TEN-063). `opened_at` is
    derived from the day, so a replay finds its own till:

      * already SEALED → this block has run; its payments will replay and write
        nothing, and `(None, None)` is returned so no `counter_session_id` is
        passed. That matters more than it looks: `record_payment` resolves the
        till **before** the replay check, so handing it a closed till id would
        raise instead of replaying, and the whole block would fail on its
        second run.
      * still OPEN → a previous run was interrupted between the payments and
        the close. It is reused and sealed at the end of this one.

    ⚠ **THE TILL BELONGS TO THE ACTOR, which for this fixture is the utility's
    System Admin.** `open_counter` makes the opener the owner and accepts both
    System Admin and Billing Clerk (`BR-SHL-025`), and at our ICP — 1 to 20
    staff — the person who owns the utility working the counter is the ordinary
    case rather than a fixture convenience. It also keeps `payments` from
    importing `identity` to go looking for a seeded clerk.
    """
    from apps.payments import counter_session_models as tills
    from apps.payments import counters

    opened_at = _till_moment(day, TILL_OPENS_AT)
    existing = tills.CounterSession.objects.filter(
        tenant_id=_tenant_id(), opened_at=opened_at, system_day__isnull=True
    ).first()
    if existing is not None:
        return (existing if existing.closed_at is None else None), None

    centre = _walk_in_counter()
    if centre is None:
        return None, (
            "this utility has no service centre, so there is nowhere to open a counter "
            "(a counter is a till AT a place). The centres are seeded by "
            "`tenancy:seed_sample_portal_content`, which runs BEFORE the money blocks "
            "for this reason — if it did not run, the fix is there and not here"
        )
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            opened = counters.open_counter(
                actor,
                # The SLUG, never the primary key — B14 rule 31, and what
                # `counters._service_centre` looks for first.
                service_centre_id=centre.slug,
                opening_float=TILL_FLOAT,
                opened_at=opened_at,
            )
    except Exception as exc:  # noqa: BLE001 — the reason is REPORTED, not swallowed
        logger.info("sample data: no counter till for %s (%s)", day, type(exc).__name__)
        return None, f"{type(exc).__name__}: {exc}"
    return opened.session, None


def _close_sample_till(actor: Any, *, session: Any, day: Any) -> str | None:
    """Seal the drawer, or say why it could not be. `None` means sealed.

    **A count that matches, on purpose.** `close_counter` is a COMPARISON: the
    clerk types what is in the drawer and the product works out the difference.
    The figures typed here are the ones `counters.running_split` says the
    system expects, so the difference is exactly `0.0000` — no note is required
    (p056) and no cash-over/short journal pair is posted (`P2.22`). A demo till
    that was short would be a money story this fixture never chose to tell, and
    inventing one here would write a ledger posting nobody ruled.

    The count is keyed by the tender's CODE, which `_counted_map` accepts and
    stores as the method id; the ids are this tenant's own and a code is what a
    reader of this file can check against `COUNTABLE_TENDERS`.

    Sealing is not tidiness: `_seal_batches` is what foots each batch's
    `recorded_total`, and without it every counter batch reaches Finance →
    Deposits at **$0.00** with the right payments in it.
    """
    from apps.payments import counters

    split = counters.running_split(session)
    counted = {
        row["method_code"]: row["system_total"]
        for row in split["by_method"]
        if row["countable"] and row["method_code"]
    }
    if not counted:
        # `_counted_map` refuses an empty count BY NAME, and it is right to: a
        # close with no count is a FORCED close, which is a System Admin's act
        # and a different record. Reported rather than worked around.
        return "the till holds no countable tender, so there is nothing to count"
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            counters.close_counter(
                actor,
                session_id=session.pk,
                counted_totals=counted,
                closed_at=_till_moment(day, TILL_CLOSES_AT),
            )
    except Exception as exc:  # noqa: BLE001 — the reason is REPORTED, not swallowed
        logger.info("sample data: the till of %s could not be sealed (%s)", day, type(exc).__name__)
        return f"{type(exc).__name__}: {exc}"
    return None


def _bills_by_account() -> dict[str, list[Any]]:
    """The seeded bills, through billing's own published read (B1)."""
    from apps.payments import billing_seam

    resolver = getattr(billing_seam, "_resolve", None)
    queryset = resolver("billing", "invoice_queryset") if resolver else None
    if queryset is None:
        from apps.billing import selectors as billing_selectors

        queryset = billing_selectors.invoice_queryset
    out: dict[str, list[Any]] = {}
    for invoice in queryset().filter(status="issued").order_by("issued_at"):
        out.setdefault(str(invoice.account_id), []).append(invoice)
    return out


def _unit_index_by_account() -> dict[str, int]:
    """`{account_id: unit_index}` through customers' published read (B1) — the
    documented seam target, same shape as billing's use of metering's. `{}`
    when customers cannot answer; the caller falls back to sort position."""
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            from apps.customers import sample_data as customers_sample

            return {
                account_id: index
                for index, account_id in customers_sample.sample_account_ids().items()
            }
    except Exception:  # noqa: BLE001 — the fallback is honest, not silent
        logger.info("sample data: customers publishes no sample_account_ids map")
        return {}


def _amount_due(invoice: Any) -> tuple[Decimal, str]:
    """The bill's own total and ITS currency — never a bare number (rule 2)."""
    for field in ("amount_due", "total", "total_due", "grand_total", "amount"):
        value = getattr(invoice, field, None)
        if value is not None:
            return Decimal(str(value)), str(getattr(invoice, "currency", "USD"))
    return ZERO, str(getattr(invoice, "currency", "USD"))


def seed_sample_records(actor: Any) -> int:
    """THE SEAM: June ~95% collected, on the busy day. (July is READY-TO-RUN
    and unbilled — CR-010 Part-10.4, PO 2026-08-17.)

    Idempotent (BR-TEN-063) through BR-PAY-028: every payment carries an
    idempotency reference derived from the invoice, so a replay is recognised by
    the product's own key and writes nothing — the guarantee lives where the
    money is written rather than in a flag here.
    """
    bills = _bills_by_account()
    if not bills:
        # ⚠ DEF-167 — THIS USED TO `return 0` AND THE PANEL PRINTED "OK … 0
        # row(s)" OVER A REAL UPSTREAM FAILURE. `_bills_by_account` asks billing
        # for invoices with `status='issued'`; on the measured run that set was
        # empty because DEF-166 left all 95 bills in `draft`, and a green empty
        # line read as "nothing to do" rather than "the bills upstream were
        # never issued". It also HID DEF-166.
        #
        # This repo's seam rule, applied to a seeder rather than a selector: an
        # unanswerable read REPORTS that it cannot answer and NEVER answers 0.
        # The upstream block is named, because the fix is there and not here.
        raise fixture.BlockCannotRun(
            "no payment could be recorded: this tenant has NO ISSUED BILL to pay. The "
            "fixture pays June, and the Bills block above is what issues it "
            "— fix that block and load again. This is a failure, not an empty result: "
            "0 payments against 0 issued bills is not the same fact as 0 payments "
            "because the fixture asked for none."
        )
    # ⛔ **DEF-2969 — THIS BLOCK USED TO PAY EVERY ISSUED BILL IT COULD SEE.**
    # `_bills_by_account` asks for every invoice with `status='issued'`, and the
    # loop below paid each one. That was correct only because of WHEN this block
    # runs — between cycle one and cycle two, when June is the only issued cycle
    # — and nothing said so. A SECOND load, after the tenant had billed more
    # cycles, found bills whose `sample:{invoice_no}` key had never been used and
    # paid them in full as though they were June. Measured 2026-09-01 on a
    # tenant seeded end to end and then billed for a third cycle: a replay wrote
    # 82 payments and 82 allocations across June, July AND August, plus a second
    # refund downstream — and CLAUDE.md hard rule 4 makes every one of them
    # permanent.
    #
    # The scope is a STATED fact now rather than a property of block order, and
    # it is the same three lines `seed_sample_cycle_collections` below already
    # uses (which is why that block's replay wrote 0).
    windows = {(period["start"], period["end"]) for period in _first_cycle_periods()}
    written = 0
    could_not_record: list[str] = []
    accounts = sorted(bills)
    # THE CASE MAP IS ASKED FOR, NOT INFERRED. This loop used to hand
    # `_share_for` the account's position in a uuid sort and call it the unit
    # index — right only because uuid7 is time-ordered and accounts were
    # created in unit order, which is a coincidence a re-run repair could
    # break. `sample_account_ids` is customers' published read for exactly
    # this question (its own docstring: "so billing and payments never have to
    # guess which account is which awkward case"). The enumerate position
    # stays as the fallback so an older tenant without the read still seeds.
    index_by_account = _unit_index_by_account()
    # ── `DEF-PAY-6321` · THE BUSY DAY IS A SHIFT, AND A SHIFT HAS A TILL ────
    # Opened BEFORE the first receipt because a payment names the till it was
    # taken into at INSERT and can never be given one afterwards
    # (`trg_payment_immutable`; `counter_session_id` is in neither the mutable
    # nor the stamps list of `payments/0014`). Sealed below.
    till, till_refusal = _open_sample_till(actor, day=fixture.BUSY_DAY)
    counter_money = 0
    for position, account_id in enumerate(accounts):
        index = index_by_account.get(str(account_id), position)
        for invoice in bills[account_id]:
            if _invoice_window(invoice) not in windows:
                continue  # DEF-2969 — a later cycle's bill is not this block's to pay
            share = _share_for(index, invoice)
            if share is None:
                continue  # deliberately unpaid — see _share_for
            amount, currency = _amount_due(invoice)
            if amount <= ZERO:
                continue
            paid = (amount * share).quantize(Decimal("0.01"))
            if paid <= ZERO:
                continue
            method_code = METHODS[index % len(METHODS)]
            # Cash and cheques go in the drawer; card and ACH never reach one
            # and are REFUSED a till by name — see the block comment above.
            taken_into = till.pk if (till is not None and _is_counter_tender(method_code)) else None
            try:
                # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
                # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
                # (this block runs inside tenancy's per-module `atomic`), so without it the
                # work already done is lost at COMMIT. NOT tidiness — do not remove.
                with transaction.atomic():
                    result = _record_sample_payment(
                        actor,
                        account_id=account_id,
                        amount=paid,
                        currency=currency,
                        posted_at=_instant(fixture.BUSY_DAY),
                        cleared_at=_instant(fixture.BUSY_DAY),
                        method_code=method_code,
                        confirmation=_reference_for(method_code, index),
                        memo="sample data",
                        idempotency_reference=f"sample:{invoice.invoice_no}",
                        counter_session_id=taken_into,
                    )
            except Exception as exc:  # noqa: BLE001 — one payment must not stop the rest
                # ⚠ DEF-167's SECOND, INDEPENDENT SWALLOW. This handler used to
                # log at INFO and continue, so 95 consecutive failures still
                # printed "OK … 0 row(s)". The failures are COUNTED now and
                # reported below: "N payments could not be recorded" costs
                # nothing and is the difference between a fixture that is
                # honest and one that is quiet.
                could_not_record.append(
                    f"{getattr(invoice, 'invoice_no', invoice.pk)}: "
                    f"{type(exc).__name__}: {exc}"
                )
                logger.info(
                    "sample data: no payment against %s (%s)",
                    getattr(invoice, "invoice_no", invoice.pk), type(exc).__name__,
                )
                continue
            if getattr(result, "created", False):
                written += 1
                # Counted on the TENDER and not on `taken_into`, deliberately:
                # the number this feeds is *how much counter money had no
                # till*, so a counter asked only about payments that DID get a
                # till could never report the failure it exists to report.
                if _is_counter_tender(method_code):
                    counter_money += 1
    # ── `DEF-PAY-6321` · SEAL THE DRAWER, OR SAY WHY NOT ───────────────────
    # A till left open is not a cosmetic loose end: `_seal_batches` is what
    # foots each batch's `recorded_total`, so an unsealed shift reaches
    # Finance → Deposits at $0.00 with the right payments in it — and the NEXT
    # block's `open_counter` is refused, because one person may hold one open
    # till. Either failure is reported through `could_not_record`, which makes
    # it a BlockCannotRun rather than a quiet gap (DEF-167).
    if till is not None:
        sealed = _close_sample_till(actor, session=till, day=fixture.BUSY_DAY)
        if sealed:
            could_not_record.append(f"the counter till could not be sealed — {sealed}")
    elif counter_money:
        # ⚠ NOT GUARDED ON `till_refusal`, AND THE DIFFERENCE MATTERS. There are
        # TWO ways to arrive here with no till: one is a refusal, which carries
        # its own sentence; the other is a REPLAY that found this day's till
        # already sealed and correctly declined to reopen it. A replay writes no
        # payment, so `counter_money` is 0 and this never fires — but a re-run
        # that DOES write new counter money against a sealed day is a real gap
        # and would have been silent if this asked about the refusal first.
        could_not_record.append(
            f"{counter_money} counter payment(s) were taken with no OPEN till, so they "
            f"belong to no deposit batch and the Payments list reads 'No batch yet' over "
            f"money a clerk handled — "
            + (
                till_refusal
                or "this day's till was already sealed by an earlier run, and a sealed "
                "till cannot take money: its drawer has been counted and its deposit "
                "footed. New counter money on a re-run needs a shift of its own"
            )
        )
    if could_not_record:
        # ⚠ THE WORDING IS `problem(s)` AND NOT `payment(s)` SINCE
        # `DEF-PAY-6321`: this list now also carries a till that would not open
        # or would not seal, which is not a payment that failed. A count whose
        # noun is wrong is the smaller half of the same fault as a count that
        # is wrong — both send a reader to the wrong place.
        raise fixture.BlockCannotRun(
            f"{written} payment(s) recorded and {len(could_not_record)} problem(s): "
            + " | ".join(could_not_record[:2])
            + (
                f" (+{len(could_not_record) - 2} more)"
                if len(could_not_record) > 2
                else ""
            )
        )
    return written


def _share_for(index: int, invoice: Any) -> Decimal | None:
    """How much of this bill was paid — `None` means DELIBERATELY UNPAID.

    Spec §3 AS AMENDED 2026-08-17 asks for ~95% of JUNE collected (July is
    ready-to-run and unbilled, so its old ~80% clause is superseded with it),
    and spec §4 asks for two partial payments, one 70-days-past-due account,
    one credit balance — and, since CR-010 Part-10.4, one account whose June
    bill is left WHOLLY unpaid so a real payment plan can spread it. All of it
    comes out of this one function, so the fixture's collection story lives in
    one place a reader can check against the spec.

    `invoice` stays in the signature deliberately: the share is a fact about
    ONE bill, and the July branch that used to read `invoice.bill_run` will be
    needed again the day the PO's own July run exists and a later fixture
    revision pays against it.
    """
    del invoice  # only June is billed since 2026-08-17 — see the docstring
    unit_index = index
    if unit_index == fixture.CASE_PAST_DUE_70:
        return None  # case 8: never paid → genuinely 60+ days at 8 August
    if unit_index == fixture.CASE_PAYMENT_PLAN:
        # case 6: the arrears the plan spreads. A plan needs a debt that
        # exists (US-CUS-018 TC-6), so this bill is settled through the plan's
        # own instalments — recorded by seed_sample_plan_payments — never here.
        return None
    if unit_index in fixture.CASE_LANDLORD:
        # ⚠ **CR-059 CS-12 · task 74 — LEFT OPEN ON PURPOSE, FOR ONE CHEQUE TO
        # SETTLE ALL THREE.** The landlord's three June bills are not paid here
        # because `seed_sample_multi_account_tender` below pays them together as
        # ONE tender: *"a customer with three properties hands over one cheque"*.
        # Paid at 100% like every other ordinary unit, the demo's only
        # multi-property cheque would have nothing to settle and the three-way
        # split it exists to show could not be drawn.
        #
        # ⚠ **THIS IS NOT A FOURTH UNPAID CASE.** The money still arrives on 8
        # August, in the same busy day and the same deposit batch as every other
        # cheque — it simply arrives through a different door. Nothing here
        # changes the collected share the spec asks for.
        return None
    if unit_index in fixture.CASE_PARTIAL_PAYMENT:
        return Decimal("0.5")  # case 4: half, so the allocation order shows
    if unit_index == fixture.CASE_CREDIT_BALANCE:
        return Decimal("1.25")  # case 11: an overpayment carried as credit
    if unit_index == fixture.REFUND["unit_index"]:
        # ⚠ CASE 14, AND IT IS A SECOND OVERPAYMENT ON PURPOSE (CR-040 D12).
        # A refund can only come out of a REAL credit (BR-PAY-014), so the
        # account that asks for money back has to have handed too much over
        # first. It is NOT case 11's account: case 11 exists to show a credit
        # being CARRIED, and refunding it would replace that case rather than
        # add one. The SHARE is fixture authorship; the CREDIT it produces is
        # the allocator's, and `seed_sample_refund` reads that figure back
        # rather than assuming it.
        return Decimal(str(fixture.REFUND["overpay_share"]))
    # ~95% collected: one in twenty.
    return None if unit_index % 20 == 0 else Decimal("1")


# ══════════════════════════════════════════════════════════════════════════
# THE COLLECTIONS AGAINST THE SECOND CYCLE — PO 2026-09-01
# ══════════════════════════════════════════════════════════════════════════
#
# PO verbatim: *"after second bill is generated, I want to add another step
# which will add - meter reads and payment data - so that We can run the next
# bill cycle on our own and see how it is working"*.
#
# ⚠ **WHAT WAS ACTUALLY MISSING, MEASURED RATHER THAN ASSUMED.** On a tenant
# seeded end to end on 2026-09-01, June carried **42 payments** and July carried
# **ZERO** — not because anything failed, but because `seed_sample_records`
# above runs BETWEEN the two billing blocks and July has not been billed when it
# runs. Nothing in the sample set has ever paid a second-cycle bill. So every
# July bill sat 100% outstanding, which is not a mix and gives the ageing report
# one shape instead of four.
#
# ⚠ **THE PERIOD'S OWN `collected_share` IS `0` AND THAT IS NOT BEING
# OVERTURNED — IT IS BEING READ FOR WHAT IT SAYS.** `core/sample_fixture`'s July
# entry explains the zero: *"a bill issued on 2 August, with this fixture's
# 'today' in mid-August, is a bill nobody has paid yet … it leaves the ageing
# report a live CURRENT bucket beside June's aged one"*. That sentence is about
# the moment the PAYMENTS BLOCK runs, and it is still true there. This block
# runs later, after the second cycle, and it deliberately leaves a large part of
# July unpaid so the live CURRENT bucket the comment protects is still there.
#
# ⚠ **JUNE IS NOT TOUCHED.** Its collection story is the fixture's — 95%, two
# part-payments, one credit, one overpayment-for-refund, two deliberately
# unpaid — and re-touching it would move the payment plan's own spread balance
# and consume the credit case 11 exists to carry. The MIX the PO asked for is
# read across the two bills together: June aged and mostly settled, July fresh
# and four different ways of being unsettled.

#: How much of the JULY bill each account paid. `None` means DELIBERATELY
#: UNPAID — the same vocabulary `_share_for` uses for June.
#:
#: ⚠ **THE PROPORTIONS ARE THIS LANE'S JUDGMENT AND THEY ARE WRITTEN DOWN**
#: (12-governance/02-decision-log.md, 2026-09-01). The PO asked for *"a mix"*
#: and named no figures, so the figures are ours and the reasoning has to
#: travel with them:
#:
#:   * **QUARTERS, because the fixture already reads in quarters.** Spec §4's
#:     own sentence is *"Roughly one account in four is deliberately awkward"*,
#:     so a quarter is this fixture's unit of "some" and nothing new is being
#:     invented to express the mix.
#:   * **1 in 4 pays nothing** (`index % 4 == 1`). This is the number that
#:     matters: arrears, the dunning ladder, the collection worklist and the
#:     30/60/90 buckets all have nothing to show on a tenant where everybody
#:     pays, and the PO's whole reason for asking is to WATCH the next cycle
#:     work.
#:   * **1 in 4 pays 60%** (`index % 4 == 2`). Sixty rather than a half so it
#:     cannot be confused with June's two 50% part-payments on a statement, and
#:     so the residue is a different number on each of the two bills.
#:   * **The remaining half pays in full**, which keeps the demo's centre of
#:     gravity where a real utility's is.
#:   * **ONE account overpays** and carries the surplus, so a credit balance
#:     exists that was NOT created in June. It is the last ordinary unit — the
#:     highest index in no awkward case — DERIVED here rather than declared as
#:     a constant, so it cannot drift out of step with `AWKWARD_UNITS`.
#:
#: Worked on the seeded tenant's own 46 July bills: 12 unpaid · 11 part-paid ·
#: 1 overpaid · the rest settled.
JULY_PART_PAID_SHARE = Decimal("0.6")
JULY_OVERPAY_SHARE = Decimal("1.2")


def _july_overpayer() -> int:
    """The highest unit index that carries no awkward case of its own.

    DERIVED, never typed: an account that is already a payment plan, a refund,
    a write-off or a 70-day arrear cannot also demonstrate a clean overpayment
    without the two stories interfering, and a constant naming one would go
    stale the day another case took that index.
    """
    ordinary = [
        unit["unit_index"]
        for unit in fixture.units_flat()
        if unit["unit_index"] not in fixture.AWKWARD_UNITS
    ]
    return max(ordinary) if ordinary else fixture.CASE_REFERENCE_BILL


def _july_share_for(unit_index: int) -> Decimal | None:
    """How much of THIS account's July bill was collected — `None` = unpaid.

    The named cases come first and each states why it is where it is; the
    quarters below carry everybody else.
    """
    if unit_index == fixture.CASE_PAST_DUE_70:
        # Spec §4 case 8 — unpaid in June AND unpaid in July. The deepest
        # arrear in the demo, and it has to keep getting deeper or the ageing
        # report never has a 60+ row that also has a current one.
        return None
    if unit_index == fixture.CASE_PAYMENT_PLAN:
        # Case 6's plan spreads a debt read live off the ledger
        # (`customers.sample_data.seed_sample_payment_plans` → `ar_positions`).
        # Paying this account here would move the figure that plan is built
        # from — a fixture reshaping another fixture's case.
        return None
    if unit_index == fixture.CASE_CREDIT_BALANCE:
        # Case 11 overpaid in June and BR-PAY-010 spends a carried credit on
        # the next bill AT ISSUE. Its July bill is therefore already settled or
        # part-settled by its own credit; a payment on top would be the
        # customer paying twice.
        return None
    if unit_index == fixture.CASE_REFUND:
        # Case 14's surplus was refunded (`seed_sample_refund`). Overpaying
        # again would re-create the credit the refund exists to have consumed.
        return None
    if unit_index in fixture.CASE_PARTIAL_PAYMENT:
        # Case 4 stays case 4 across both bills — the same two accounts, still
        # paying part, so the allocation order has two months to work over.
        return JULY_PART_PAID_SHARE
    if unit_index == fixture.CASE_OVERCHARGE:
        # Case 15's June bill was credited and restated. Paying July in full
        # shows the account healthy again, which is the second half of what a
        # correction demonstrates.
        return Decimal("1")
    if unit_index == _july_overpayer():
        return JULY_OVERPAY_SHARE
    remainder = unit_index % 4
    if remainder == 1:
        return None
    if remainder == 2:
        return JULY_PART_PAID_SHARE
    return Decimal("1")


def seed_sample_cycle_collections(actor: Any) -> int:
    """**THE MONEY AGAINST THE SECOND CYCLE** — the other half of the PO's
    2026-09-01 step, and it runs AFTER `billing:seed_sample_second_cycle`
    because it pays bills that block issues.

    Every payment goes through `services.record_payment`, the module's one and
    only writer (US-PAY-001/002), so the allocator decides what each payment
    settles and what surplus becomes a credit — no figure here is an amount
    this fixture typed. Idempotent (BR-TEN-063) through BR-PAY-028: the
    idempotency reference is derived from the invoice, so a replay is
    recognised by the product's own key and writes nothing.

    ⚠ **IT PAYS THE SECOND CYCLE'S BILLS AND NOTHING ELSE.** The bills it can
    see are every issued invoice; the ones it PAYS are the ones whose period is
    a `billed` fixture period that the June block did not already collect
    against — in practice July. June is left exactly as `seed_sample_records`
    left it, for the reasons in the block comment above.
    """
    bills = _bills_by_account()
    if not bills:
        raise fixture.BlockCannotRun(
            "no collection could be recorded: this tenant has NO ISSUED BILL to pay. The "
            "second cycle is what issues them and it runs immediately above this block "
            "— fix that block and load again. This is a failure, not an empty result."
        )
    later = _later_cycle_periods()
    if not later:
        return 0
    windows = {(period["start"], period["end"]) for period in later}
    index_by_account = _unit_index_by_account()
    written = 0
    could_not_record: list[str] = []
    paid_in_full = part_paid = unpaid = overpaid = 0
    # ── `DEF-PAY-6321` · THE WORK IS ORDERED BY DRAWER DAY, NOT BY ACCOUNT ──
    # A till is one shift at one desk, and `BR-PAY-025` as amended makes a
    # batch one TILL × one TENDER — so the money has to be taken in day order,
    # with the previous drawer sealed before the next one opens. **One person
    # may hold only one open till** (`uq_counter_sessions_open_owner`, a
    # PARTIAL unique index), so opening a second while the first is unsealed is
    # refused by the DATABASE, not merely by this file.
    #
    # In practice this list holds ONE day: `_collection_day` is the issue date
    # plus a week and the second cycle issues in one run. It is grouped anyway
    # rather than assuming, because the day a run spans two dates the
    # assumption would fail as a refused `open_counter` in the middle of a seed
    # — which reads like a broken product and is a broken fixture.
    work: list[dict[str, Any]] = []
    for position, account_id in enumerate(sorted(bills)):
        index = index_by_account.get(str(account_id), position)
        for invoice in bills[account_id]:
            if _invoice_window(invoice) not in windows:
                continue
            share = _july_share_for(index)
            if share is None:
                unpaid += 1
                continue
            amount, currency = _amount_due(invoice)
            if amount <= ZERO:
                continue
            paid = (amount * share).quantize(Decimal("0.01"))
            if paid <= ZERO:
                continue
            if share > Decimal("1"):
                overpaid += 1
            elif share < Decimal("1"):
                part_paid += 1
            else:
                paid_in_full += 1
            work.append(
                {
                    "day": _collection_day(invoice),
                    "account_id": account_id,
                    "invoice": invoice,
                    "index": index,
                    "paid": paid,
                    "currency": currency,
                }
            )
    # Sorted on facts the BILL carries, never on a uuid's accident of ordering:
    # a tenant seeded today and one seeded next month write the same rows in
    # the same sequence, which is what makes the `PMT-` numbers reproducible.
    work.sort(key=lambda row: (row["day"], str(getattr(row["invoice"], "invoice_no", ""))))

    for day, same_day in itertools.groupby(work, key=lambda row: row["day"]):
        till, till_refusal = _open_sample_till(actor, day=day)
        # `DEF-PAY-8756` — signed up on the 1st to the 8th, the calendar clamps
        # BOTH the busy day and this collection day to today, and the busy
        # day's drawer was sealed by `seed_sample_records` before this block
        # ran: a sealed till takes no money, so every cash and cheque here was
        # refused and the block failed. Money taken after that drawer closed is
        # not counter money — it arrives by card or bank transfer. ONLY on the
        # busy day, and decided the same way on a replay, so a replay sends the
        # same payment it sent the first time (its idempotency key).
        busy_drawer_sealed = till is None and till_refusal is None and day == fixture.BUSY_DAY
        counter_money = 0
        for row in same_day:
            invoice = row["invoice"]
            index = row["index"]
            method_code = METHODS[index % len(METHODS)]
            if busy_drawer_sealed and _is_counter_tender(method_code):
                method_code = AFTER_THE_DRAWER[index % len(AFTER_THE_DRAWER)]
            taken_into = till.pk if (till is not None and _is_counter_tender(method_code)) else None
            try:
                # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
                # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
                # (this block runs inside tenancy's per-module `atomic`), so without it the
                # work already done is lost at COMMIT. NOT tidiness — do not remove.
                with transaction.atomic():
                    result = _record_sample_payment(
                        actor,
                        account_id=row["account_id"],
                        amount=row["paid"],
                        currency=row["currency"],
                        posted_at=_instant(day),
                        cleared_at=_instant(day),
                        method_code=method_code,
                        confirmation=_reference_for(method_code, index + 1),
                        memo="sample data — second-cycle collections",
                        idempotency_reference=f"sample:cycle2:{invoice.invoice_no}",
                        counter_session_id=taken_into,
                    )
            except Exception as exc:  # noqa: BLE001 — one payment must not stop the rest
                could_not_record.append(
                    f"{getattr(invoice, 'invoice_no', invoice.pk)}: "
                    f"{type(exc).__name__}: {exc}"
                )
                logger.info(
                    "sample data: no second-cycle collection against %s (%s)",
                    getattr(invoice, "invoice_no", invoice.pk), type(exc).__name__,
                )
                continue
            if getattr(result, "created", False):
                written += 1
                if _is_counter_tender(method_code):
                    counter_money += 1
        if till is not None:
            sealed = _close_sample_till(actor, session=till, day=day)
            if sealed:
                could_not_record.append(f"the counter till of {day} could not be sealed — {sealed}")
        elif counter_money:
            # Not guarded on `till_refusal` — see the same branch in
            # `seed_sample_records` for why a sealed-till replay must still be
            # able to speak up.
            could_not_record.append(
                f"{counter_money} counter payment(s) were taken on {day} with no OPEN till, "
                f"so they belong to no deposit batch — "
                + (
                    till_refusal
                    or "that day's till was already sealed by an earlier run, and a sealed "
                    "till cannot take money. New counter money on a re-run needs its own shift"
                )
            )
    if could_not_record:
        # DEF-167: a fixture that cannot record the money it specifies is a
        # broken fixture, and the reasons travel on the exception a human reads.
        raise fixture.BlockCannotRun(
            f"{written} collection(s) recorded and {len(could_not_record)} problem(s): "
            + " | ".join(could_not_record[:2])
            + (f" (+{len(could_not_record) - 2} more)" if len(could_not_record) > 2 else "")
        )
    logger.info(
        "sample data: second-cycle collections — %s paid in full, %s part-paid, "
        "%s overpaid, %s left unpaid",
        paid_in_full, part_paid, overpaid, unpaid,
    )
    return written


def _first_cycle_periods() -> tuple[dict[str, Any], ...]:
    """The FIRST billed period — the only one `seed_sample_records` collects
    against (DEF-2969). The mirror of `_later_cycle_periods` below, and the pair
    is exhaustive by construction, so no billed period is either paid twice or
    left to no block at all."""
    billed = tuple(period for period in fixture.PERIODS if period["billed"])
    return billed[:1]


def _later_cycle_periods() -> tuple[dict[str, Any], ...]:
    """Every BILLED period after the first — the ones `seed_sample_records`
    above did not collect against. The same slice
    `apps/billing/sample_data._second_cycle_periods` bills, derived here from
    the fixture rather than imported, because payments may not import billing
    (B1 / BR-TEN-013)."""
    billed = tuple(period for period in fixture.PERIODS if period["billed"])
    return billed[1:]


def _invoice_window(invoice: Any) -> tuple[Any, Any]:
    """The period an issued bill covers, off the bill itself.

    Read from the invoice's own columns where it has them and from its run
    otherwise — never from the fixture, because the question being asked is
    *which period is THIS bill for*, and answering it from the fixture would
    make the check agree with itself.
    """
    start = getattr(invoice, "period_start", None)
    end = getattr(invoice, "period_end", None)
    if start is None or end is None:
        run = getattr(invoice, "bill_run", None)
        start = getattr(run, "period_start", None)
        end = getattr(run, "period_end", None)
    return (start, end)


#: How long after a bill is issued this fixture's early payers pay it.
#:
#: ⚠ **NOT `BUSY_DAY`, AND THE FIRST DRAFT OF THIS BLOCK USED IT.** The busy day
#: (8 August) is spec §5's *one busy day of mixed takings*, and it is what the
#: deposit batches and the bank-reconciliation demo are built on. July's bills
#: issue on 2 August, so putting their collections on the busy day too took that
#: day from 43 receipts to 76 and quietly reshaped somebody else's exhibit.
#: A week after issue is a date the BILL fixes, it is deterministic, it lands
#: the day AFTER the busy day so the two cycles' money is told apart on a bank
#: statement, and it is still before the fixture's mid-August "today".
COLLECTION_LAG_DAYS = 7


def _collection_day(invoice: Any) -> Any:
    """When the money arrived: a week after the bill went out.

    G6 bans a wall clock from a money path, so this is derived from a date the
    bill itself carries — a tenant seeded today and one seeded next month carry
    the same dates on the same receipts.
    """
    issued = getattr(invoice, "issued_at", None)
    issued_on = issued.date() if hasattr(issued, "date") else issued
    if issued_on is None:
        return fixture.BUSY_DAY
    # ⚠ **CLAMPED TO THE FIXTURE'S DECLARED "TODAY" — DEF-LED-6640.** The
    # calendar travels now (`core/sample_fixture.build_calendar`), so a demo
    # seeded on the 3rd of a month issues its second-cycle bill on the 1st or
    # 2nd and a naive `issued + 7` would bank the money on the 9th: **a receipt
    # dated next week**, in a period that has not happened. `fixture.TODAY` is
    # a DECLARED figure on the fixture, not a clock of this module's own, which
    # is what `BR-TEN-043` and G6 are about — the same reason `BUSY_DAY` may be
    # read here and `date.today()` may not.
    return min(issued_on + timedelta(days=COLLECTION_LAG_DAYS), fixture.TODAY)


def seed_sample_plan_payments(actor: Any) -> int:
    """THE PLAN-MONEY SEAM — CR-010 Part-10.4 amendment 3 (PO 2026-08-17).

    Customers' `seed_sample_payment_plans` block (which runs just before this
    one) created and activated the plan through the S24 wizard's own path;
    this block records its MONEY, because `payments` has exactly one writer
    (US-PAY-001/002) and it is this module:

      * the DOWN PAYMENT — a `payments` row with purpose `plan_down` linked to
        its plan (BR-PAY-012), for the figure the plan row itself states;
      * the PAID INSTALMENTS — ordinary bill-purpose payments allocated against
        the outstanding June bill (BR-PAY-038's class order), each POSTED ON
        its due date and linked through `record_installment_payment`, so
        BR-PAY-021's on-time test reads true on real rows;
      * the NEXT instalment is left due — the plan is genuinely MID-SCHEDULE,
        which is the whole point of the amendment.

    Idempotent (BR-TEN-063) three ways: every payment carries a plan-derived
    idempotency reference (BR-PAY-028), an instalment already holding a
    `paid_posted_on` is skipped, and a missing plan is a NAMED refusal — the
    fix is in the block above, not here.
    """
    from apps.customers import sample_data as customers_sample  # documented seam target
    from apps.payments import plans

    plan_spec = fixture.PAYMENT_PLAN
    account_id = customers_sample.sample_account_ids().get(plan_spec["unit_index"])
    if account_id is None:
        raise fixture.BlockCannotRun(
            "no plan money was recorded: the sample accounts are not seeded, so the "
            "plan account does not exist. The Accounts block above has to load first."
        )
    plan = plans.live_plan_for(account_id)
    if plan is None:
        raise fixture.BlockCannotRun(
            "no plan money was recorded: this account holds no live payment plan. "
            "The 'Payment plan' block above (customers' seed_sample_payment_plans) "
            "is what creates it — fix that block and load again."
        )
    written = 0

    down = Decimal(str(plan.down_payment))
    if down > ZERO:
        result = _record_sample_payment(
            actor,
            account_id=account_id,
            amount=down,
            currency=plan.currency,
            posted_at=_instant(plan_spec["signed_on"]),
            cleared_at=_instant(plan_spec["signed_on"]),
            method_code="card",
            # ⚠ **`SAMPLE-PLAN-{plan.pk}` PUT A UUID ON A CUSTOMER'S SCREEN**
            # (`DEF-CWP-3974`, second half). `CWP-041`'s REFERENCE column serves
            # `confirmation` straight through, so the plan's PRIMARY KEY was the
            # reference a customer read for their own down payment — B14 rule
            # 31, *no database id is ever the visible value of a field*, broken
            # by the FIXTURE rather than by the screen. The card's own reference
            # is what a gateway would return.
            confirmation=_reference_for("card", 0),
            memo="sample data",
            purpose=models.PURPOSE_PLAN_DOWN,  # BR-PAY-012 — linked to its plan
            plan_id=plan.pk,
            idempotency_reference=f"sample:plan:{plan.pk}:down",
        )
        if getattr(result, "created", False):
            written += 1

    installments = sorted(plan.installments.all(), key=lambda row: row.seq)
    for installment in installments[: int(plan_spec["paid_installments"])]:
        if installment.paid_posted_on is not None:
            continue  # BR-TEN-063: a replay changes no count
        # POSTED ON the due date, deliberately: BR-PAY-021 judges an instalment
        # on its POSTING date, so these two render on time however long the
        # fictional cheque took to clear.
        result = _record_sample_payment(
            actor,
            account_id=account_id,
            amount=Decimal(str(installment.amount)),
            currency=installment.currency,
            posted_at=_instant(installment.due_date),
            cleared_at=_instant(installment.due_date),
            method_code="ach",
            # Same as the down payment above: the mandate's own reference, never
            # the plan's primary key (B14 rule 31).
            confirmation=_reference_for("ach", installment.seq),
            memo="sample data",
            idempotency_reference=f"sample:plan:{plan.pk}:{installment.seq}",
        )
        plans.record_installment_payment(
            actor=actor,
            plan_id=plan.pk,
            seq=installment.seq,
            payment_id=result.payment_id,
            posted_on=installment.due_date,
        )
        if getattr(result, "created", False):
            written += 1
    return written


# ── CR-040 task D12 · the refund (spec §4 case 14) ──────────────────────────
# 🔒 HUMAN-REVIEW-PENDING — this block drives money OUT of the utility through
# the real refund door, so it is money-deciding fixture code. Row in
# 12-governance/09-human-review-ledger.md.
def seed_sample_refund(actor: Any) -> int:
    """THE REFUND SEAM — all four steps, through `apps/payments/refunds.py`.

    PO 2026-08-27: *"you need credit and refunds cases"*. **Nothing in this
    fixture had ever paid a customer back**: every one of spec §4's thirteen
    earlier cases moves money IN or holds it, so the whole outbound half of the
    product — the approval queue, the credit test that runs twice, the
    DR customer-credit / CR cash posting, the cheque clearing the bank — had no
    seeded row anywhere and could only be seen in a test.

    ⚠ **THE REAL DOOR, ALL FOUR STEPS, NEVER A WRITTEN ROW** (spec rule 4:
    *"seed through the services a clerk's click uses"*). `request_refund` →
    `approve_refund` → `issue_refund` → `clear_refund`. Only step 3 moves
    money and only step 3 posts; the other three exist so the demo shows a
    refund with a HISTORY rather than a refund that simply is.

    ⚠ **THE AMOUNT IS THE ALLOCATOR'S, NOT THIS FILE'S.** It is read back from
    `account_credit_position` after the overpayment the June collection already
    recorded — so a refund of "the customer's whole credit" is exactly the
    figure the product itself holds, and no number in this fixture has to agree
    with a number in that one. A typed amount would drift the day a tariff
    moves and would fail as a refusal deep inside `_credit_or_refuse`.

    ⚠ **IT DOES NOT TOUCH `CASE_CREDIT_BALANCE`.** Case 11 exists to show a
    credit being CARRIED. A refund CONSUMES a credit, so paying case 11 out
    would replace one case with another rather than add one. `CASE_REFUND` is
    its own ordinary unit, overpaying its own June bill.

    ⚠ **THE OFFSET RULING IS HONOURED, NOT SKIPPED** — `cross_account_check` is
    ON, so the PO's ruling of 2026-08-12 (*"offset first"*) is applied by the
    product to this fixture like any other refund. The seeded account holds one
    account and no arrears, so the offset is zero and the whole credit is
    refundable; passing False would have made the demo the one case in the
    product that skips the check.

    Idempotent (BR-TEN-063) through the product's own key: `idempotency_key` is
    derived from the payment, so a replay returns the existing request with
    `created=False` and the later steps see a refund that is already past them
    and stop. Returns the number of refunds CREATED — 0 on a replay.
    """
    from apps.payments import refunds, selectors as payment_selectors

    spec = fixture.REFUND
    account_id = _account_for_unit(spec["unit_index"])
    if account_id is None:
        raise fixture.BlockCannotRun(
            "no refund was recorded: the sample accounts are not seeded, so the account that "
            "overpays does not exist. The Accounts block above has to load first."
        )
    payment = (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, memo="sample data"
        )
        .order_by("-amount", "created_at")
        .first()
    )
    if payment is None:
        raise fixture.BlockCannotRun(
            "no refund was recorded: the account that should have OVERPAID its June bill "
            "carries no seeded payment at all. The Payments block above is what records it "
            "— fix that block and load again. A refund seeded without the overpayment behind "
            "it would be money paid out of a credit that does not exist."
        )
    # ⚠ **THE REPLAY CHECK COMES BEFORE THE CREDIT CHECK, AND THE ORDER IS A
    # BUG THIS LANE SHIPPED AND FIXED.** `request_refund` is idempotent on its
    # own key, so the naive order (ask for the credit, then let the product
    # dedupe) looks equivalent — and is not. On a replay the credit is GONE:
    # this refund spent it the first time, and the second billing cycle spends
    # what a credit-carrying account still had. So the credit check refused a
    # replay by name, loudly, over a fixture that was already correct. Asking
    # "have I already done this?" first is the only order that is true both
    # times (BR-TEN-063: a replay changes no count AND reports no failure).
    already = models.Refund.objects.filter(
        tenant_id=_tenant_id(), idempotency_key=f"sample:refund:{payment.pk}"
    ).exists()
    if already:
        return 0
    credit = payment_selectors.account_credit_position(account_id)
    if credit <= ZERO:
        raise fixture.BlockCannotRun(
            f"no refund was recorded: this account's credit position is {credit}, so there is "
            "nothing to pay back. The fixture overpays its June bill by "
            f"{fixture.REFUND['overpay_share']}x through `_share_for`; if the collection share "
            "moved, the credit went with it. NOT worked around by refunding a typed amount — "
            "BR-PAY-014 allows a refund only out of a REAL credit."
        )

    requested = refunds.request_refund(
        actor,
        payment_id=payment.pk,
        amount=credit,
        method=spec["method"],
        requested_at=_instant(spec["requested_on"]),
        reason=spec["reason"],
        reference=spec["reference"],
        memo="sample data",
        cross_account_check=True,
        idempotency_key=f"sample:refund:{payment.pk}",
    )
    if not requested.created:
        return 0  # BR-TEN-063: a replay changes no count and writes nothing
    refund_id = requested.refund_id
    refunds.approve_refund(actor, refund_id=refund_id, approved_at=_instant(spec["approved_on"]))
    refunds.issue_refund(
        actor,
        refund_id=refund_id,
        issued_at=_instant(spec["issued_on"]),
        entry_date=spec["issued_on"],
    )
    refunds.clear_refund(actor, refund_id=refund_id, cleared_at=_instant(spec["cleared_on"]))
    return 1


# ── CR-059 CS-12 task 74 · one customer, three properties, ONE cheque ───────
# 🔒 HUMAN-REVIEW-PENDING — this block drives the multi-account money path, so
# it is money-deciding fixture code. Row in 12-governance/09-human-review-ledger.md.
def seed_sample_multi_account_tender(actor: Any) -> int:
    """THE MULTI-PROPERTY TENDER — through `apps/payments/tenders.py`'s own door.

    `CR-059` CS-12: *"A customer with three properties hands over one cheque;
    the clerk records three payments, splits the money on paper, and **gets
    three receipts printed for one cheque.** Nothing checks the split adds up."*
    **Nothing in this fixture had ever shown that**: every seeded payment
    settles exactly one account, so the whole multi-account story — one tender
    row, N payments, the split that must sum exactly — could only be seen in a
    test.

    ⚠ **THE REAL DOOR, NEVER A WRITTEN ROW** (spec rule 4: *"seed through the
    services a clerk's click uses"*). `tenders.record_multi_account_payment`,
    which is what `POST /customers/{id}/payments` calls.

    ⚠ **THE AMOUNTS ARE THE PRODUCT'S, NOT THIS FILE'S.** Each part is read back
    from `billing_seam.open_invoices_for_account` — what that property actually
    still owes — and the cheque is their SUM, so the tender's own sum check
    (BR-PAY-1127) can never fail on a tariff that moved. `CR-059`'s worked
    scenario is **184.20 + 156.90 + 178.90 = 520.00**; this estate's own figures
    are whatever its June bills came to, and the demo shows the SHAPE with real
    numbers rather than a typed total that would drift. Same discipline
    `seed_sample_refund` keeps two blocks down, and for the same reason.

    ⚠ **THE THREE BILLS ARE UNPAID BECAUSE `_share_for` LEAVES THEM SO**, which
    is stated at that branch as well as here — a cheque seeded against three
    settled bills would be a cheque for 0.00 and the block would refuse.

    Idempotent (BR-TEN-063) through the product's own guard: the submission key
    is fixed, so a replay finds the tender, replays all three parts and writes
    nothing. Returns the number of TENDERS created — 0 on a replay.
    """
    from apps.payments import billing_seam, tenders

    spec = fixture.MULTI_PROPERTY_TENDER
    account_ids = [_account_for_unit(index) for index in spec["unit_indexes"]]
    if any(account_id is None for account_id in account_ids):
        raise fixture.BlockCannotRun(
            "no multi-property cheque was recorded: the landlord's three accounts are not "
            "seeded, so there is nobody holding three properties. The Accounts block above "
            "has to load first."
        )

    parts: list[tenders.TenderPart] = []
    total = ZERO
    for account_id in account_ids:
        position = billing_seam.open_invoices_for_account(account_id)
        owed = sum((invoice.balance for invoice in position.invoices), ZERO)
        if owed <= ZERO:
            raise fixture.BlockCannotRun(
                "no multi-property cheque was recorded: one of the landlord's three "
                "properties owes nothing, so a cheque covering all three would be a cheque "
                "for less than it claims and the tender's own sum check would refuse it. "
                "`_share_for` leaves these three June bills open on purpose — if the "
                "Payments block above paid them, that branch is what to look at. NOT worked "
                "around by typing an amount: BR-PAY-1127 makes the parts and the total one "
                "arithmetic fact."
            )
        parts.append(tenders.TenderPart(account_id=account_id, amount=owed))
        total += owed

    # ⚠ **THE CUSTOMER IS ASKED FOR, NEVER ASSUMED.** All three accounts carry
    # one BR-CUS-054 customer because `CASE_LANDLORD` gives them one
    # `customer_key`, and the tender REFUSES an account that customer does not
    # hold — so reading it back through customers' own published seam is what
    # makes this block fail loudly if that link ever stops being made.
    holder = billing_seam._resolve("customers", "customer_for_account")
    customer = holder(account_ids[0]) if callable(holder) else None
    if not customer:
        raise fixture.BlockCannotRun(
            "no multi-property cheque was recorded: the landlord's first property is linked "
            "to no customer, so there is nothing to scope one cheque across three accounts "
            "to. `CASE_LANDLORD` gives all three one `customer_key` and customers' Accounts "
            "block is what turns that into a customer row."
        )

    paid_at = _instant(spec["paid_on"])
    recorded = tenders.record_multi_account_payment(
        actor,
        customer_id=customer["id"],
        parts=tuple(parts),
        amount=total,
        posted_at=paid_at,
        cleared_at=paid_at,
        method_code=spec["method"],
        reference=spec["reference"],
        memo="sample data",
        submission_key="sample:tender:multi-property",
    )
    # BR-TEN-063: a replay changes no count and writes nothing.
    return 1 if recorded.created else 0


def _account_for_unit(unit_index: int) -> Any:
    """The seeded account on a unit, through customers' published read (B1).

    `sample_account_ids()` is customers' own answer to *"which account is which
    awkward case"* — its docstring says so — and it is asked rather than
    inferred from a sort position, which is the mistake DEF-167's neighbour
    documents two functions up.
    """
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            from apps.customers import sample_data as customers_sample

            return customers_sample.sample_account_ids().get(unit_index)
    except Exception:  # noqa: BLE001 — the refusal above is honest, not silent
        logger.info("sample data: customers publishes no sample_account_ids map")
        return None


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-066 — 0, and WHY.

    A payment is append-only (CLAUDE.md hard rule 4) and the database enforces
    it with triggers, so nothing here deletes one. The count of what stays is
    NAMED, because "we removed the demo" over rows that are still there is the
    sentence a utility would act on and be wrong about.
    """
    held = models.Payment.objects.filter(tenant_id=_tenant_id()).count()
    # ⚠ CR-040 D12 — the refund is NAMED SEPARATELY, because it is money that
    # went OUT and a utility reading "N payments stay" would not know a cheque
    # was written. Its journal entry is append-only like every other, so the
    # row stays with it (hard rule 4).
    refunded = models.Refund.objects.filter(tenant_id=_tenant_id()).count()
    if not held and not refunded:
        return {"removed": 0, "retained": []}
    retained = []
    if held:
        retained.append(
            {
                "label": f"{held} payment(s) and their allocations",
                "reason": (
                    "a payment can never be changed or deleted — a correction is a new "
                    "row (CLAUDE.md hard rule 4, enforced by database triggers). For a "
                    "genuinely empty tenant, create a new one"
                ),
            }
        )
    if refunded:
        retained.append(
            {
                "label": f"{refunded} refund(s) already paid out",
                "reason": (
                    "a refund that has been issued moved real money out of the utility and "
                    "left a journal entry behind it. Neither can be deleted (hard rule 4), "
                    "and a refund removed without its entry would leave the books short of "
                    "the bank by exactly the amount refunded"
                ),
            }
        )
    return {"removed": 0, "retained": retained}


def sample_record_count() -> int:
    return int(
        models.Payment.objects.filter(
            tenant_id=_tenant_id(), memo="sample data"
        ).count()
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel serves this through tenancy's endpoints) E=deferred(same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: THREE of the spec's money cases are NOT seeded by this lane and are NAMED in NOT_SEEDED rather than silently missing — the bounced cheque, the write-off and the goodwill credit — plus spec §5's bank statement with its non-tying card day. Each needs a service path this lane did not have the budget to drive correctly, and a half-driven money path is worse than an absent one · the payment plan left that list 2026-08-17 and THE DEPOSIT BATCHES LEFT IT 2026-09-23 (DEF-PAY-6321): they are seeded through counters.open_counter → record_payment(counter_session_id) → counters.close_counter, never written directly, because trg_deposit_batch_needs_session refuses a batch with no session · card and ACH money is deliberately left with NO batch: HAND_TENDERS is cash, cheques and money orders, and services._counter_session refuses the rest a till by name · removal returns 0 and NAMES what stays: hard rule 4 forbids deleting a payment
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

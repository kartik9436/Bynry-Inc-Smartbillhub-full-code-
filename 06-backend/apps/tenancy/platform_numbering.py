# ── Trace ──────────────────────────────────────────────
# Story:    CR-039 wave F task 27 — "all of it on the platform side of the
#           boundary with its own numbering"
# Rules:    PO 2026-08-26 (the commercial model, verbatim) · PO 2026-08-27
#           (*"it is duration of implmentation project"* · *"youc anhave 0 month
#           implmentaiton"*) · BR-TEN-035 shape (a number is allocated inside
#           the transaction that creates the record) · BR-TEN-240 (this module)
# Tests:    06-backend/tests/test_cr039_wave_f_task27_numbering.py
# ───────────────────────────────────────────────────────
"""BYNRY'S OWN NUMBERING — the platform side of the boundary (CR-039 task 27).

⚠ **THIS IS NOT `core/numbering.py` AND MUST NOT BECOME IT.** That kernel
allocates a TENANT's document numbers: it refuses without `app.tenant_id` in
context by design (*"a caller cannot number into another tenant's series"*), it
reads a format the tenant configures on Settings → Numbering, and it counts in
that tenant's own `number_series` row. Every one of those properties is wrong for
this number. `implementation_orders.order_no` names a thing **Bynry sold**, not a
thing the utility issued — the model's own docstring says so: *"NOT one of the
twenty-six tenant series in `core/numbering.py`: a tenant's own numbering is the
tenant's to configure, and this number is Bynry's."*

So the **format machinery is reused and the storage is not**. `render()` and
`validate_format()` are tenant-free grammar functions, and using them is what
keeps `IMPL-26-0001` shaped like the `CON-26-0110` and `TRF-26-0001` a person
already reads — a second, hand-rolled formatter is how two number families come
to disagree about what a `{YY}` looks like.

WHERE THE SEQUENCE LIVES
-------------------------
In `platform_number_series`, one row per series per year, bumped by
`allocate_sequence()` below and made safe by `uq_implementation_orders_order_no`
(tenancy `0025`) plus a retry.

⚠ **THIS PARAGRAPH SAID THE OPPOSITE UNTIL 2026-09-07, AND THE REASON IT CHANGED
IS WORTH MORE THAN THE CHANGE.** It read *"WHERE THE SEQUENCE LIVES, AND WHY
THERE IS NO COUNTER TABLE"* and argued, correctly for its day, that deriving the
next number from `MAX` over the year's rows is better than a counter because
*"it can drift from the rows it counts. Deriving cannot: the answer IS the
data."* That derivation scanned `implementation_orders` **across every tenant**,
which was lawful only because `tenancy/0021` had left that table with no
row-level security policy — and B2 §3 never exempted it. `DEF-TEN-4446` applied
the signed policy in `tenancy/0042`, and a cross-tenant scan is exactly what a
tenant policy exists to prevent. **The old argument did not become wrong; the
ground it stood on was removed.**

What survives from it, unchanged:

* **The race is closed by the INDEX, not by the counter.** Two allocations that
  somehow reach the same number produce one winner and one `IntegrityError`,
  which `_create` catches and retries — and the retry now bumps the counter
  again, so a drifted counter heals itself instead of looping.
* **BR-TEN-035's gapless promise is still NOT claimed here.** It is about
  documents a regulator may audit; this is a sales reference. As it happens the
  counter row is gap-free — it is bumped inside the caller's transaction, so a
  rolled-back signup returns its number — but nothing may depend on that, and no
  screen or report should say it.

⚠ **AND NOTHING HERE READS A CLOCK.** The caller names the date (BR-TEN-043's
event-time law), because a signup at 23:59 on 31 December belongs to the year it
happened in and not to the year the write finished in.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.tenancy import models
from core import numbering as core_numbering

logger = logging.getLogger("smartbillhub.tenancy")

#: `IMPL-26-0001`. The same grammar as the tenant catalogue's own series, so a
#: person reading a reference off an order does not have to learn a second shape.
#: It is a CONSTANT and not a configurable format: a tenant may not rename
#: Bynry's series, and Bynry has no settings screen in this product to do it on.
ORDER_NO_FORMAT = "IMPL-{YY}-{0000}"

#: The one row of `platform_number_series` this module owns. A CONSTANT rather
#: than a literal at three call sites: the backfill in tenancy `0041` writes the
#: same string, and a typo there would open a second, empty series in silence.
IMPLEMENTATION_ORDER_SERIES = "implementation_order"

#: How many times `_create` will re-read the maximum and try again after a
#: unique-constraint collision. Three is enough for any realistic signup rate and
#: is bounded on purpose: an unbounded retry over a constraint that is failing
#: for some OTHER reason is an infinite loop inside a signup.
MAX_ALLOCATION_ATTEMPTS = 3

#: Self-serve is priced at nothing because there is no engagement to charge for
#: — the utility does its own configuration and migration.
#: ⚠ **STATED, NOT SIGNED.** The PO gave the SHAPE (*"youc anhave 0 month
#: implmentaiton"*) and not this figure, so a non-zero self-serve price is a
#: CHANGE and not a correction. Money at 4 decimals, CLAUDE.md hard rule 2.
SELF_SERVE_PRICE = Decimal("0.0000")
SELF_SERVE_DURATION_MONTHS = 0


def render_order_no(sequence: int, on: date) -> str:
    """`(7, 2026-08-27)` → `IMPL-26-0007`. Pure; touches no database."""
    return core_numbering.render(ORDER_NO_FORMAT, sequence, on)


# ⚠ `_year_prefix()` AND THE `MAX`-OVER-THE-ROWS READER THAT USED IT WERE DELETED
# HERE ON 2026-09-07 (DEF-TEN-4446). They existed to scan `implementation_orders`
# across every tenant; `tenancy/0042` gives that table a tenant policy, so the
# scan can no longer see what it was reading and keeping a helper for it would be
# keeping a road to a bridge that is out. The backfill in `tenancy/0041` carries
# its own frozen copy of the parse, deliberately — a migration is a record of
# what was done and must not change when this module does.


def allocate_sequence(on: date) -> int:
    """Take the next counter for `on`'s year and leave the series pointing past it.

    ⚠ **THIS REPLACED A SCAN OF `implementation_orders`, AND THE REPLACEMENT IS
    THE WHOLE OF `DEF-TEN-4446`'s SECOND HALF.** Until 2026-09-07 the answer was
    `MAX` over every order of the year, ACROSS ALL TENANTS — which `tenancy/0021`
    could write because it had left the table with no row-level security policy.
    B2 §3 never exempted it, `tenancy/0042` applies the signed policy, and from
    that moment the old scan runs inside the signing-up tenant's own context and
    can see only that tenant's orders. A brand-new tenant has none, so every
    signup would read a maximum of 0, propose `IMPL-26-0001`, collide with
    `uq_implementation_orders_order_no`, retry three times and raise — killing
    the signup, and **only on PostgreSQL**, because sqlite has no RLS and the
    default suite would have stayed green through all of it (hard-won law 14).

    THREE THINGS WERE WEIGHED AND THIS IS WHY THE COUNTER WON
    ---------------------------------------------------------
    * **Allocate before entering tenant context** — the smallest change, and it
      does not work. The policy denies by DEFAULT: with `app.tenant_id` unset the
      predicate is NULL, so a context-free read of `implementation_orders`
      returns **zero rows**, not all of them. It fails identically.
    * **A PostgreSQL sequence** — genuinely outside RLS, and the ordinary tool.
      Rejected on the YEAR, not on the gaps: `IMPL-{YY}-{0000}` restarts at 0001
      each January, and a sequence cannot be reset on a calendar without either
      runtime DDL inside a signup transaction or a job nobody would remember in
      December. (Its gaps would have been acceptable — this module has always
      said so: a rolled-back signup may reuse a number because *"this is a sales
      reference"*, not an invoice a regulator audits.)
    * **A counter row, which is this.** Keeps the number shape byte-identical,
      needs no DDL, behaves the same on PostgreSQL and sqlite so the suite
      exercises the real path, and happens to be gap-free.

    HOW IT IS SAFE UNDER TWO SIGNUPS AT ONCE
    -----------------------------------------
    The seed is `INSERT … ON CONFLICT DO NOTHING` (Django's
    `bulk_create(ignore_conflicts=True)`), so two signups opening a new year
    produce one row and **no exception** — which matters more than tidiness,
    because on PostgreSQL a raised `IntegrityError` would abort the whole signup
    transaction (hard-won law 14) and this call sits inside one.

    The bump is a single `UPDATE … SET next_sequence = next_sequence + 1`. That
    statement re-reads the row under a row lock, so a second signup BLOCKS on it
    until the first commits or rolls back and then increments whatever it finds.
    Two concurrent signups therefore serialise on one row for the length of the
    provisioning transaction. At the rate a utility SaaS is signed up for that is
    free, and it buys the property that a rolled-back signup returns its number
    instead of burning it.

    ⚠ **THE UNIQUE INDEX IS STILL THE GUARANTEE.** If this counter is ever
    behind the rows — restored from a stale backup, seeded wrong — the INSERT in
    `create_implementation_order` fails and the retry calls this again, which
    bumps past the collision. The counter is the fast path; the index is the
    truth.
    """
    year = on.year
    # Lazily open the year. ignore_conflicts → ON CONFLICT DO NOTHING: no row is
    # overwritten and, crucially, no error is raised into a transaction that
    # cannot survive one.
    models.PlatformNumberSeries.objects.bulk_create(
        [
            models.PlatformNumberSeries(
                series=IMPLEMENTATION_ORDER_SERIES, year=year, next_sequence=1
            )
        ],
        ignore_conflicts=True,
    )
    updated = models.PlatformNumberSeries.objects.filter(
        series=IMPLEMENTATION_ORDER_SERIES, year=year
    ).update(next_sequence=F("next_sequence") + 1)
    if updated != 1:  # pragma: no cover — the seed above makes this unreachable
        raise core_numbering.NumberingError(
            f"the platform series {IMPLEMENTATION_ORDER_SERIES!r} has no counter "
            f"for {year} and one could not be opened"
        )
    row = models.PlatformNumberSeries.objects.get(
        series=IMPLEMENTATION_ORDER_SERIES, year=year
    )
    return row.next_sequence - 1


def create_implementation_order(
    tenant: Any,
    *,
    on: date,
    duration_months: int,
    price: Decimal = SELF_SERVE_PRICE,
    currency: str = "USD",
    instalments: int = 1,
    status: str = "delivered",
) -> models.ImplementationOrder:
    """Create ONE implementation order, numbered, inside the caller's transaction.

    ⚠ **THE NUMBER IS ALLOCATED HERE AND NOT BY A CALLER**, which is the same
    guarantee CR-039 wave D built `transfers.transfer_no` and
    `disconnect_cases.case_no` with: there is no instant in which the record
    exists unnumbered, so no screen and no report has to render the absence of a
    reference that will be along shortly.

    Each attempt runs in its own SAVEPOINT. That is not decoration: on
    PostgreSQL an `IntegrityError` aborts the enclosing transaction, so a retry
    without a savepoint would be executed inside a transaction that can no
    longer do anything — and the signup this sits inside would die on the next
    statement rather than on this one.
    """
    last_error: IntegrityError | None = None
    for attempt in range(MAX_ALLOCATION_ATTEMPTS):
        candidate = render_order_no(allocate_sequence(on), on)
        try:
            with transaction.atomic():
                return models.ImplementationOrder.objects.create(
                    tenant=tenant,
                    order_no=candidate,
                    duration_months=duration_months,
                    price=price,
                    currency=currency,
                    instalments=instalments,
                    status=status,
                )
        except IntegrityError as exc:  # another signup took this number first
            last_error = exc
            logger.info(
                "implementation order number %s was taken; retrying (%s of %s)",
                candidate,
                attempt + 1,
                MAX_ALLOCATION_ATTEMPTS,
            )
    # Loud, never silent: a signup that cannot number its order must fail with
    # the reason rather than write one without a reference (hard-won law 3 —
    # the unsafe option must be the one you type).
    raise core_numbering.NumberingError(
        f"could not allocate an implementation order number after "
        f"{MAX_ALLOCATION_ATTEMPTS} attempts: {last_error}"
    )


def create_self_serve_order(tenant: Any, *, on: date) -> models.ImplementationOrder:
    """The zero-month order a self-serve signup writes — PO 2026-08-27.

    Verbatim: *"when utility will do cofiguration, data migrton by themself then
    it is self serve and we dont have to implment it - how you want to handle it,
    youc anhave 0 month implmentaiton"*.

    ⚠ **WHY THE ROW IS WRITTEN AT SIGNUP RATHER THAN LEFT FOR SOMEBODY TO
    RECORD.** The decision log of 2026-08-27 chose a zero-month ROW over the
    absence of an order for one reason: *"a row and no row are different things
    to a report"* — with the row, *"how many customers are self-serve?"* is one
    query. **That payoff only exists if something writes it**, and the only path
    in this product that creates a tenant is the public self-serve signup, where
    the utility is by definition doing its own configuration. So the row is a
    FACT about how that tenant arrived, not a guess about what it will buy.

    ⚠ **AND THE THING THAT WOULD MAKE IT A GUESS IS RAISED RATHER THAN
    ASSUMED — `OQ-610`.** If a tenant is ever created by Bynry's sales for a
    utility that has bought a 9-month implementation, this line would stamp it
    self-serve before anyone scoped it — and *"implementation not yet scoped"*
    would become indistinguishable from *"self-serve"*, which is the exact
    distinction the row was chosen to preserve. There is no such path today.
    One call site changes it.

    `status="delivered"` with no `delivered_on`, and that pair is deliberate: a
    zero-month project has nothing left to do, so `draft` would read as *somebody
    is about to scope this* — the confusion the row exists to prevent — while a
    delivery DATE would assert an event nobody performed.
    """
    return create_implementation_order(
        tenant,
        on=on,
        duration_months=SELF_SERVE_DURATION_MONTHS,
        price=SELF_SERVE_PRICE,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@04064df (EP-TEN-01 tenant provisioning — CR-039 wave F tasks 25/27, the commercial model's platform-side numbering. The hex is the branch tip this packet was assembled from, the one carrying CR-042's build and the 2026-08-27 wave F rulings in 12-governance/02-decision-log.md; no verifier tool stamps this yet, so it is a checkable reference rather than a recomputed snapshot hash)
# generated: 2026-08-27 by the CR-039 wave F + CR-040 wave E tail lane (BR-TEN-240; OQ-610 minted rather than answered)
# checklist: A✔ (packet assembled at r11 step 0 against 01-open-questions, 02-decision-log, 10-defect-log and 11-change-requests — which is what found DEF-978 and the four stale wave rows) B✔ (BR-TEN-240 → code; 6 cases in test_cr039_wave_f_task27_numbering.py) C✔ (the money column is written once at creation and never updated, so nothing append-only is edited) ⚠ AMENDED 2026-09-07, DEF-TEN-4446 — this cell used to read "no tenant-scoped query: `implementation_orders` is RLS-EXEMPT PLATFORM DATA by tenancy/0021's own ruling", which B2 §3 never said. tenancy/0042 applies the signed policy to that table, and the cross-tenant scan this cell was excusing is the thing `allocate_sequence` replaced D=deferred(no-API-half — there is no Bynry-side admin surface in this product and inventing one is not task 27; the number is written by the provisioning transaction and read by nothing yet) E=deferred(no-frontend-half — **STATED SO SKIPPING IT IS VISIBLE, r11 step 2b.** The ONLY surface for any platform-side commercial record is Settings → Billing plan, which is an unbuilt feature carrying `settings.arrivesWith.billingPlan` in eleven catalogues; `subscriptions` has been seeded since tenancy/0005 and has never had a screen either. Building one here would be building the Billing plan feature, which no task in wave F asks for — reported as DEF-1092 rather than silently omitted) F✔ (see gates:) G✔ (OQ-610 MINTED and not answered — whether every signup should be stamped self-serve; BR-TEN-240 CONFIRMED with clause 4's $0.00 marked STATED-NOT-SIGNED) H=deferred(PO 2026-08-09 — AI authors, human reviews later; the row is in 12-governance/09-human-review-ledger.md as HUMAN-REVIEW-PENDING and states in plain English with the figure what is owed to the PO)
# gates: makemigrations --check --dry-run *No changes detected* · pytest tests/test_cr039_wave_f_task27_numbering.py + tests/test_cr039_wave_f_commercial_model.py · 10-scripts/03-golden-verify.py **33 PASS / 0 FAIL** before and after, unchanged — this money is Bynry's, not a utility's customer's, and no B4/B5 figure is anywhere near it · run_gates enumerated line by line against this lane's own diff with common.summarize's 5-of-N truncation disabled (DEF-973), which is how G1's missing trailer on this very file and G7's missing marker on tenancy/0025 were found
# exceptions: this module deliberately does NOT use core/numbering.py's series storage — see the docstring; the FORMAT functions are reused so the two number families cannot disagree about what a {YY} looks like · the sequence is DERIVED from the rows rather than counted in a table, so a rolled-back signup leaves a reusable sequence and BR-TEN-035's gapless promise is NOT claimed here · `platform_numbering.py` is NOT added to 10-scripts/gates/human_owned.txt: that file's own header makes editing it a PROCESS EVENT and a lane may not add itself (the precedent is rating/selectors.py's line and the three money-path escapes recorded under it), so the question is put to the PO in the review ledger instead
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

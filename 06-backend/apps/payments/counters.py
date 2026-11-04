# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 — the payments blueprint's phase 2, tasks `P2.1`
#           (POST /counters), `P2.2` (close · force-close · declare), `P2.3`
#           (the reads), `P2.22` (the drawer difference reaches the books) and
#           `P2.23` (a hand tender needs an open till).
#           Drawing: `05-prototype/06 Payments Page Blueprint.pdf` p054–p059.
#           ⚠ **THAT PDF IS NOT ON THIS BRANCH** — it lives on the default
#           branch `claude/confirm-understanding-3ktufc`, the same anomaly
#           CLAUDE.md records for the Billing blueprint. Read it with
#           `git cat-file -p <that ref>:'05-prototype/06 Payments Page
#           Blueprint.pdf'`.
# Story:    no story — the six Counter screens are `S-NEW · PAY-N` in the
#           blueprint and A1 has not been renumbered for them (OQ-014's range
#           is untouched). `P2.6` is the screen lane.
# Rules:    CLAUDE.md hard rule 1 (every read and write inside a tenant;
#           `payments/0032` gives this table RLS FORCE) · hard rule 2 (money
#           stored to four decimals, displayed to two, never a float) · hard
#           rule 4 (NARROW: `counter_sessions` is NOT one of its four frozen
#           tables — see `declare_counter`) · hard rule 5 (only the ledger
#           posting service writes journal lines — `ledger_seam` is the one
#           door) · hard rule 6 (a second open till is refused by the DATABASE)
#           · hard rule 7 (open, close, force-close and declare each write
#           `audit_log`) · BR-SHL-025 (a role check lives on the SERVICE) ·
#           BR-TEN-043 (the caller names the moment; nothing here reads a
#           clock) · BR-PAY-025 as amended 2026-09-22 (a batch is one TILL ×
#           one TENDER) · NFR-3 (server pagination) · NFR-5 (no hard caps)
# Tests:    06-backend/tests/test_cr136_p2_counters.py ·
#           10-scripts/cr136_p2_counters_postgres_proof.py (the race, the
#           poisoned transaction and the RLS probe, on PostgreSQL 16)
# Impacts:  apps/payments/counters_api.py (the five routes) ·
#           apps/payments/api.py (one `include`, and `P2.23`'s guard on the
#           record door) · apps/payments/ledger_seam.py
#           (`post_counter_difference`) · apps/payments/reconciliation.py
#           (`_get_or_create_batch`, reused rather than re-implemented)
# ───────────────────────────────────────────────────────
"""payments — a till's whole life: opened, filled, sealed, and counted.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). Money
rounding and ledger posting are CLAUDE.md 🔒 sensitive paths, so there is a row
in `12-governance/09-human-review-ledger.md` stating in plain English, with a
figure, what would be put to the Product Owner. It may not reach lifecycle
RATIFIED without a recorded human sign-off.

════════════════════════════════════════════════════════════════════════════
THE FOUR ACTS, AND WHAT EACH ONE WRITES
════════════════════════════════════════════════════════════════════════════
    open           a session row and its batch, in ONE transaction
    close          closed_at · closed_by · close_kind='counted' ·
                   counted_totals · difference · note
    force close    closed_at · closed_by · close_kind='forced' · a reason.
                   `@require_role(SYSTEM_ADMIN)`, and `closed_by` is NOT the
                   owner
    declare        counted_totals · difference · note · declared_at ·
                   declared_by — and `close_kind` DOES NOT MOVE

⚠ **THERE IS NO FOURTH `close_kind` AND THERE WILL NOT BE ONE.** It was put to
the Product Owner on 2026-09-23 and declined: *"(a) Keep it as a forced close
and add the late count beside it… The row reads: force-closed Monday by the
supervisor, declared Tuesday by Dana, $12 short. It leaves the Not counted
list. Nothing is erased"*. `close_kind` holds `counted`, `forced`, `system`.

════════════════════════════════════════════════════════════════════════════
⚠ THE JUDGMENT THIS FILE CARRIES: *"ITS BATCH"*, WHEN A TILL HAS NO TENDER YET
════════════════════════════════════════════════════════════════════════════
**Two PO rulings, one day apart, and they cannot both be obeyed literally.**

  * **2026-09-21**, drawn at p055: *"When a counter is started a batch should
    be automatically started with it."* Singular. The blueprint's outcome is
    *"One act, not two. The batch exists before the money does."*
  * **2026-09-22**, `OQ-PAY-12577` (a): **a batch is one TILL × one TENDER.**
    Dana's shift taking $600 cash and $640 cheques is ONE till, TWO tenders and
    **two batches**. `deposit_batches.method_id` is NOT NULL and the key is
    `UNIQUE (tenant, session, method) WHERE session_id IS NOT NULL`.

A till at the moment it opens has taken nothing, so **the set of tenders it
will take is not knowable** and *"its batch"* has no single answer. Three ways
out were weighed:

  **(a) open one batch per hand tender — cash, cheque and money order.**
  Literal, and it strands rubbish for ever. `payments_deposit_batch_lock()`
  (`payments/0005`) **REFUSES A DELETE BY NAME**: *"A batch is the record of
  what physically went to the bank on a day; corrections are new events on its
  trail, never a deletion."* So a till that takes only cash leaves TWO empty
  `$0.00` in-transit batches that nothing can ever remove, and they answer
  `bankrec_read`'s match-candidate query (`status IN (in_transit, unmatched)`)
  for ever. Three clerks × 250 shifts is up to **1,500 undeletable empty rows a
  year** on the screen whose whole job is *ready to match*.

  **(b) open nothing; create each batch with the first payment of its tender.**
  Strands nothing and honours the ruling's stated PURPOSE — *"that removes a
  window in which a counter payment would have had no batch"* — because the
  batch is INSERTed inside that payment's own transaction. But it makes the
  drawn sentence false at the moment it is drawn about, and `P2.12` asks for
  *"open and its batch in ONE transaction"*.

  **(c) — BUILT — open the session and ONE batch: the till's CASH batch.**
  Cash is the tender a drawer is MADE of. `opening_float` is denominated in it
  (*"Cash in the drawer before you start"*, p054), the Close screen's first row
  is *"Cash incl. float"*, and it is the one tender that is present at the
  instant the till opens — the float is in the drawer before the first payment.
  So the drawn sentence is literally true, `P2.12` holds, and the stranding is
  bounded to **at most one** row, and only for a till that took no cash at all
  across a whole shift. Every other tender's batch is created by the first
  payment of that tender through `batch_for()` below, inside that payment's
  transaction, so *"no payment without a batch"* holds for all seven.

**WHY REVERSIBILITY DECIDED IT.** (a) wrong is permanent — the rows cannot be
deleted. (c) wrong is one function. When two readings of a ruling are both
arguable, the one you can undo is the one to build.

**WHAT WAS NOT DONE, AND WHY IT WOULD HAVE LOOKED CLEVERER.**
`tenancy.ServiceCentre.payment_methods_accepted` exists and p054 says the
centre *"already carries which methods a site takes"*, which reads like the
tender set this needs. It is not: it is PORTAL vocabulary — the seeded values
are `["cash", "cheque", "card", "money_order"]` and the tender lookup's code is
`check`, not `cheque` — so using it needs a translation table nobody has
signed, and one seeded centre publishes `[]`, which would have opened NO batch
at all and put the window straight back. Measured, not assumed.

**RAISED, NOT DECIDED:** `OQ-PAY-12599`, because this is a collision between two
of the PO's own rulings and hard-won law 13 names that as one of the three
things that legitimately reach them. It is raised for CONFIRMATION and blocks
nothing — the safe reading is built and is running.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT *"NOT COUNTED"* IS — ONE EXPRESSION, FOUR READERS
════════════════════════════════════════════════════════════════════════════
`close_kind = 'forced' AND declared_at IS NULL`. It is `not_counted_q()` and
nothing else may spell it: the list on `3·1`, its filter chip, `P2.11`'s notice
to a supervisor and phase 2's own *done when* are four readers of one fact, and
four spellings of it is four places for it to drift (B14 rule 43's shape,
applied to a query).

⚠ **`declared_at` IS `P2.20`, ANOTHER LANE'S MIGRATION, AND IT HAD NOT LANDED
WHEN THIS WAS WRITTEN.** Until it does, the expression is `close_kind =
'forced'` alone — which is not a degradation, it is the same set: with no
column there is no way to declare, so every forced close is uncounted. The
switch is `_declaration_columns_exist()`, it is asserted from the MODEL rather
than from this module's own opinion of it, and `test_p2_2_declare_
fires_when_p2_20_lands` runs the real behaviour on whichever side of that line
the repo is on — never a skip (hard-won law 7: a check that cannot fail).
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet, Sum

from apps.payments import bankrec_models as bankrec
from apps.payments import counter_receipt_models as cr_models
from apps.payments import counter_session_models as tills
from apps.payments import ledger_seam, models, reconciliation
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit
from core import errors
from core import permissions
from core import tenancy as core_tenancy
from core.pagination import ListParams

ZERO = Decimal("0")
#: Hard rule 2 — money is STORED to four decimals. Display rounds to two and
#: that is the screen's job, never this module's.
MONEY_QUANTUM = Decimal("0.0001")

#: ── §3.4 · THE THREE TENDERS THAT PASS THROUGH A PERSON'S HANDS ───────────
#: PO ruling 2026-09-23, verbatim: *"(a) Refuse it. \"Start your counter
#: first.\" One press, then take the money. It is the only option where every
#: cash dollar belongs to somebody"*.
#:
#: ⚠ **THE OTHER FOUR ARE UNTOUCHED ON PURPOSE** — `ach`, `card`, `wire` and
#: `lockbox` go on banking under phase 0's system till. A card swiped at a
#: window is among them deliberately: the Close screen counts only what is in a
#: drawer, and a card total typed back at the system's own figure makes the
#: whole reconciliation worthless (p056 ③).
HAND_TENDERS: tuple[str, ...] = ("cash", "check", "money_order")

#: What a drawer can be COUNTED against — the same three, and the coincidence
#: is not one: a tender is countable exactly when it is a physical thing a
#: person can put in a drawer, which is also what makes it need a till.
#: A method absent from a `counted_totals` map was not counted, and that
#: distinction is free in a map (see `counter_session_models`).
COUNTABLE_TENDERS: tuple[str, ...] = HAND_TENDERS

#: The tender a drawer is MADE of — see the judgment in the module docstring.
DRAWER_TENDER = "cash"

#: The statuses a payment still in (or banked from) a drawer can be in.
#: `posted` since `CR-186-BRC10` (PO 2026-10-21: every payment is posted at
#: entry); `processing` and `cleared` for the rows written before. A
#: `cancelled` payment left with nobody and is excluded — which is how a
#: cancel makes *"the counter total drops"* true.
DRAWER_STATUSES = (models.PAYMENT_POSTED, models.PAYMENT_PROCESSING, models.PAYMENT_CLEARED)

#: `audit_log` actions (hard rule 7). One per act, so the trail can answer
#: *which* of the four happened without parsing a payload.
AUDIT_COUNTER_OPENED = "counter.opened"
AUDIT_COUNTER_CLOSED = "counter.closed"
AUDIT_COUNTER_FORCE_CLOSED = "counter.force_closed"
AUDIT_COUNTER_DECLARED = "counter.declared"

#: `GET /counters` — BR-SHL-011's vocabulary for this list. Every one of these
#: is a real column, so the ORDER BY is SQL's (NFR-3) and never Python's.
COUNTER_SORTS: tuple[str, ...] = ("opened_at", "closed_at", "owner", "centre")
#: ⚠ **`mine` IS SERVED BY THE SERVER AND WAS NOT (`DEF-PAY-6235`).** The page
#: head asked `GET /counters?f.mine=1&per=1` and took the first row; `f.mine`
#: was undeclared, and `core.pagination.parse_list_params` **DROPS an
#: undeclared filter silently** (its own comment: *"undeclared filter names are
#: ignored"*). So the read succeeded, returned the SUPERVISOR's list of
#: everyone's open tills, and `per: 1` made the wrong row arrive faster. The
#: slot then announced a colleague's drawer as *"Your counter"* beside a button
#: that takes money. Nothing went red: both states render, the shape is right,
#: and only the identity is wrong.
COUNTER_FILTERS: tuple[str, ...] = ("state", "owner_id", "centre_id", "mine")
DEFAULT_COUNTER_SORT = "opened_at"


@dataclass(frozen=True)
class OpenedCounter:
    """What `POST /counters` produced — the till and the batch it opened."""

    session: Any
    batch: Any
    batch_created: bool


@dataclass(frozen=True)
class SealedCounter:
    """What a close, a force close or a declare left behind."""

    session: Any
    difference: Decimal | None
    posting_key: str | None


# ════════════════════════════════════════════════════════════════════════════
# TENANT, MOMENT AND MONEY — the three things nothing here may guess
# ════════════════════════════════════════════════════════════════════════════
def _tenant_id() -> Any:
    """Hard rule 1 — nothing touches a tenant table without `app.tenant_id`.

    ⚠ **REFUSES RATHER THAN DEFAULTING, AND THE MEASURED REASON IS WHY.** With
    the GUC unset, RLS FORCE matches **zero rows** and every statement reports
    success — the shape that once stamped 0 of 74 payments and said it had
    stamped them. A till opened with no tenant would be invisible to the person
    who opened it and to the supervisor chasing it.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _require_moment(value: Any, what: str) -> datetime:
    """BR-TEN-043 / gate G6 — the caller names the moment; this reads no clock."""
    if not isinstance(value, datetime):
        raise PaymentRuleError(
            f"{what} must be given as a moment by the caller. Nothing in this module reads a "
            "clock (BR-TEN-043): a server clock decides a business day in the SERVER's "
            "timezone, and a till opened at 08:55 local would then be stamped with somebody "
            "else's day.",
            br_ref="BR-TEN-043",
        )
    return value


def _money(value: Any, what: str) -> Decimal:
    """Hard rule 2 — a Decimal, never a float, never cents, four decimals stored.

    A float is REFUSED rather than converted. A conversion hides the place where
    money became binary, and the refusal names it — the same posture
    `ledger_seam` takes one module along.
    """
    if isinstance(value, float):
        raise PaymentRuleError(
            f"{what} arrived as a float ({value!r}). Money is a Decimal at four decimal places "
            "and never a binary float (CLAUDE.md hard rule 2). Refused rather than converted, "
            "because a conversion would hide the place where the money stopped being exact.",
            br_ref="BR-PAY-002",
        )
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as bad:
        raise PaymentRuleError(
            f"{what} is not a money figure ({value!r}).",
            br_ref="BR-PAY-002",
        ) from bad


def _q(amount: Decimal) -> Decimal:
    """Store at four decimal places — hard rule 2's storage half."""
    return amount.quantize(MONEY_QUANTUM)


# ════════════════════════════════════════════════════════════════════════════
# `P2.20`'s COLUMNS — present or not, and the answer is taken from the MODEL
# ════════════════════════════════════════════════════════════════════════════
def _declaration_columns_exist() -> bool:
    """Has `P2.20` landed? Asked of the model, never remembered.

    ⚠ **THE FALSE PASS THIS SHAPE INVITES, NAMED SO IT CANNOT HAPPEN QUIETLY**
    (hard-won law 7, habit 2): if this answered `False` because somebody
    mistyped a field name, `declare_counter` would refuse for ever and every
    test of it would take the *"not built yet"* branch and pass. So the test
    asserts this function against `CounterSession._meta` INDEPENDENTLY, and the
    declare test runs real behaviour on whichever side of the line the repo is.
    """
    names = {field.name for field in tills.CounterSession._meta.get_fields()}
    return {"declared_at", "declared_by"} <= names


def _payments_name_their_till() -> bool:
    """Has `P2.4` landed — does a payment carry `counter_session_id` yet?

    **It has (`payments/0035`), and since `P2.13` something WRITES it**
    (`DEF-PAY-6226`): `services.record_payment` stamps the till and the till's
    batch in one INSERT. Both facts are therefore true of a counter payment
    and `session_payments_q` reads them TOGETHER rather than one replacing the
    other — a till's money must be findable by either, because the batch is
    what an older row carries and the till is what a new one names.

    Kept as a question rather than deleted: it is asked of the MODEL, so a
    tree that predates `0035` still answers, and the test asserts it against
    `Payment._meta` independently so a mistyped field name cannot turn it into
    a check that quietly always says no.
    """
    names = {field.name for field in models.Payment._meta.get_fields()}
    return "counter_session" in names or "counter_session_id" in names


# ════════════════════════════════════════════════════════════════════════════
# `NOT COUNTED` — ONE EXPRESSION, FOUR READERS (§3.2)
# ════════════════════════════════════════════════════════════════════════════
def not_counted_q() -> Q:
    """A till the system sealed that nobody has counted — the ONLY spelling.

    `close_kind = 'forced' AND declared_at IS NULL`.

    Four readers, and that is exactly why this is a function: `3·1`'s list, its
    `Not counted` filter chip, `P2.11`'s notice to a supervisor, and phase 2's
    own *done when* (*"a supervisor can see the three tills nobody counted"*).
    Four spellings would be four places for it to drift the first time a rule
    moves — B14 rule 43's argument, made about a query instead of a component.

    ⚠ A **system** till never answers this and needs no clause to say so: it is
    born CLOSED with `close_kind = 'system'`, which is not `forced`. That is
    `_system_session`'s own design decision and this expression inherits it
    rather than restating it.
    """
    published = getattr(tills, "NOT_COUNTED", None)
    if published is not None:
        # ⚠ **THE MODEL'S OWN `NOT_COUNTED` IS THE DEFINITION AND THIS RETURNS
        # IT.** `P2.20` published `counter_session_models.NOT_COUNTED` beside
        # the two columns it is made of, and this function was written the
        # same afternoon from the same ruling — **two spellings of the one
        # expression §3.2 says must be written once.** They agreed on the day
        # they were written, which is exactly how this kind of drift starts:
        # the second one is only wrong later. So the column's owner wins and
        # this is now a pointer rather than a copy. It stays a FUNCTION, not a
        # re-export, because the three readers here call it and a module-level
        # `NOT_COUNTED = tills.NOT_COUNTED` would freeze the answer at import
        # time — which is what the fallback below exists to avoid.
        return published
    # `P2.20` has not landed in this tree: there is no way to declare, so every
    # forced close is uncounted and this is the SAME SET rather than a weaker
    # one. Kept so the module still answers on a tree that predates 0035.
    return Q(close_kind=models.COUNTER_CLOSE_FORCED)


def session_payments_q(session: Any) -> Q:
    """Which payments this till took — one definition, read by every figure.

    A payment belongs to a till when it names the till (`P2.4`, once that
    column exists) **or** when it banks in one of the till's batches. The two
    are read together rather than one superseding the other, because they are
    two records of one fact and a till's money must be found by either.

    ⚠ **IT IS A SUBQUERY, NOT A PYTHON LIST OF IDS.** `NFR-3` is about server
    work, not only about page sizes: materialising a shift's batch ids to build
    an `IN` clause is the same mistake `GET /outstandings` makes with its sort.
    """
    batch_ids = bankrec.DepositBatch.objects.filter(
        tenant_id=session.tenant_id, session_id=session.pk
    ).values("pk")
    clause = Q(deposit_batch_id__in=batch_ids)
    if _payments_name_their_till():
        clause = clause | Q(counter_session_id=session.pk)
    return clause


def _drawer_payments(session: Any) -> QuerySet:
    """The rows a drawer is counted against — taken, positive, not failed.

    * `type = payment` — a credit or an adjustment is not money anybody handed
      over, and counting one would put the drawer out by its value. The same
      exclusion `cut_deposit_batches` applies, for the same reason.
    * `amount > 0` — a reversing row is not money in the drawer.
    * `status IN (processing, cleared)` — and **`processing` is the one that
      matters**. A cheque taken at 11:42 is `processing` until the bank clears
      it days later, and it is still physically in the drawer at 17:30. A
      `failed` row is a voided cheque that was torn up, and a `reversed` one
      left with the customer.
    """
    return models.Payment.objects.filter(
        session_payments_q(session),
        tenant_id=session.tenant_id,
        type=models.PAYMENT_TYPE_PAYMENT,
        amount__gt=ZERO,
        status__in=DRAWER_STATUSES,
    )


def _drawer_receipts(session: Any) -> Any:
    """The counter receipts this till took — the drawer's OTHER half.

    ⚠ **THESE ARE NOT PAYMENT ROWS AND THAT IS A2's DESIGN, NOT AN OVERSIGHT.**
    A service request's application fee posts `DR 1010 · CR 2400` at collection
    and writes no `payments` row (decision log 2026-09-19, option A2). The cash
    is still in the drawer, so it still has to be counted — `OQ-PAY-12621`, PO
    2026-09-24, option (a): *the fee counts toward the counter's expected cash;
    the drawer balances; the books are unchanged.*

    **ALL THREE STATES COUNT.** `held`, `applied` and `earned` differ in what
    the BOOKS have done with the money since; none of them is the money leaving
    the drawer, and a receipt in any of them was taken during this shift.

    ⚠ **GROUPED IN SQL, NOT FOLDED IN PYTHON** — `NFR-3`, and the same reason
    `running_split`'s own docstring gives: a shift can hold any number of
    receipts and `NFR-5` forbids a cap. `ix_counter_receipts_session` is the
    index that makes it one read.
    """
    return (
        cr_models.CounterReceipt.objects.filter(
            tenant_id=session.tenant_id, counter_session_id=session.pk
        )
        .values("method_id", "method__code", "method__name", "currency")
        .annotate(amount=Sum("amount"), n=Count("id"))
        .order_by("method__code")
    )


def _merge_sources(payment_rows: Any, receipt_rows: Any) -> list[dict[str, Any]]:
    """One row per tender, from the two things a till can hold.

    ⚠ **IT MERGES BEFORE THE LOOP RATHER THAN ADDING AFTER IT**, so the float
    rule, the countable rule and the currency set are each applied in exactly
    one place. Adding a fee to a finished `system_total` would have meant
    re-deciding *is this the cash row?* a second time, and a rule stated twice
    is a rule that drifts.

    ⚠ **`n` COUNTS WHAT MADE UP THE FIGURE BESIDE IT, WHICH NOW INCLUDES
    RECEIPTS.** `MyCounterPage` renders that number under each tender's total,
    so a count that excluded a line the total includes would be a number a
    clerk cannot reconcile with what is next to it. A receipt is money this
    till took; it is not a `payments` row, and that distinction belongs to the
    payments LIST, not to the drawer figure.

    Ordered by `method_code`, which is what the un-merged query returned.
    """
    tally: dict[Any, dict[str, Any]] = {}
    for source in (payment_rows, receipt_rows):
        for row in source:
            key = row["method_id"]
            found = tally.get(key)
            if found is None:
                tally[key] = {
                    "method_id": key,
                    "method__code": row["method__code"],
                    "method__name": row["method__name"],
                    "currency": row["currency"],
                    "amount": _q(row["amount"] or ZERO),
                    "n": row["n"],
                }
                continue
            found["amount"] = _q(found["amount"] + _q(row["amount"] or ZERO))
            found["n"] += row["n"]
            # A row with no currency of its own must not blank one that has it.
            if not found["currency"] and row["currency"]:
                found["currency"] = row["currency"]
    return sorted(tally.values(), key=lambda row: (row["method__code"] or "", str(row["method_id"])))


def running_split(session: Any) -> dict[str, Any]:
    """`3·2`'s four tiles and `3·3b`'s SYSTEM SAYS column — computed in SQL.

    One `CounterMethodTotal` per tender the till has taken — the member names
    are `07-frontend/src/api/counterEndpoints.ts`'s and not this lane's — plus
    the whole-shift figures:

        {"by_method": [
             {"method_id": "8f3c…", "method_name": "Cash",
              "method_code": "cash", "system_total": "510.0000",
              "countable": true, "payment_count": 12, "counted_total": null},
             {"method_id": "2b71…", "method_name": "Cheque",
              "method_code": "check", "system_total": "1284.6000",
              "countable": true, "payment_count": 8, "counted_total": null},
             {"method_id": "9d0a…", "method_name": "Tap and pay",
              "method_code": "card", "system_total": "402.1500",
              "countable": false, "payment_count": 3, "counted_total": null}],
         "taken": "1996.7500", "count": 23,
         "opening_float": "200.0000",
         "countable_expected": "1794.6000",
         "currency": "USD"}

    ⚠ **`countable: false` IS p056's ③ AND IT IS DRAWN DELIBERATELY** — *"you
    cannot count a card total in a drawer, so the screen does not pretend"*. An
    uncountable tender is SERVED, so the screen can show what the till took by
    card, and it joins neither `countable_expected` nor the difference.

    ⚠ **THE AGGREGATION IS `GROUP BY` IN THE DATABASE, NOT A PYTHON LOOP, AND
    THAT IS `NFR-3`.** `counter_receipts.list_totals` is the named reference
    for the SHAPE and it does `list(queryset)` and sums in Python — correct for
    a screen that lists what it sums, and the wrong pattern to copy here, where
    a shift can hold any number of payments and `NFR-5` forbids a cap. `GET
    /outstandings` and `GET /cheques` already breach this (`DEF-PAY-4221`) and
    the brief for this lane is explicit: do not add a sixth.

    ⚠ **IT READS TWO SOURCES SINCE 2026-09-24 — `payments` AND
    `counter_receipts` (`OQ-PAY-12621`, PO: *"p1 a"*).** A service request's
    application fee posts at collection with NO payment row (A2), so until this
    ruling the cash was in the drawer and not in the expectation: the close read
    OVER by the fee, and since 2026-09-23 that over POSTS — **one fee booked
    twice.** Worked, and it is the ruling's own figure: **$70.00** taken in
    cash, **$470.00** counted at close against an expected **$400.00** →
    `$70.00` over, posted again. Now the expected count is **$470.00** and the
    difference is **$0.00**. The two are merged by `_merge_sources` BEFORE the
    loop below, so the float rule and the countable rule are each stated once.

    ⚠ **THE FLOAT SITS INSIDE THE CASH LINE AND IS NOT NETTED OUT** — p056,
    which flags it as a finance question rather than a UI one. Built as drawn:
    `$310.00` taken in cash plus a `$200.00` float is a **`$510.00`** cash line,
    and `countable_expected` of `$1,794.60` is that plus `$1,284.60` of cheques.
    A clerk counts what is in the drawer, and the float is in the drawer; the
    alternative asks them to subtract before they type. Recorded in the decision
    log of 2026-09-23 with these figures.
    """
    rows = (
        _drawer_payments(session)
        .values("method_id", "method__code", "method__name", "currency")
        .annotate(amount=Sum("amount"), n=Count("id"))
        .order_by("method__code")
    )
    # ⚠ **THE SECOND SOURCE — AN APPLICATION FEE IS IN THE DRAWER AND IS NOT A
    # PAYMENT ROW (`OQ-PAY-12621`, PO 2026-09-24: *"p1 a"*).** A2 (2026-09-19)
    # posts a service request's fee at collection and writes NO `payments` row,
    # so the query above cannot see it; the ruling of 2026-09-23 then made a
    # drawer difference REACH THE BOOKS. Together that booked one fee twice —
    # once at collection and again as the over it created at close.
    # `_drawer_receipts` is the other half of what the till holds, aggregated in
    # SQL for the same `NFR-3` reason as the query above.
    fee_rows = _drawer_receipts(session)
    counted = session.counted_totals or {}
    by_method: list[dict[str, Any]] = []
    currencies: set[str] = set()
    taken = ZERO
    countable = ZERO
    count = 0
    for row in _merge_sources(rows, fee_rows):
        code = row["method__code"]
        amount = _q(row["amount"] or ZERO)
        taken += amount
        count += row["n"]
        is_countable = code in COUNTABLE_TENDERS
        system_total = amount
        if is_countable and code == DRAWER_TENDER:
            # p056's first row is *"Cash incl. float"* — the float is IN the
            # drawer, so the figure a clerk counts against includes it.
            system_total = _q(amount + _q(session.opening_float or ZERO))
        if is_countable:
            countable += system_total
        if row["currency"]:
            currencies.add(row["currency"])
        by_method.append(
            {
                # ⚠ Served and NEVER RENDERED (B14 rule 31) — it is the key the
                # counted map is posted back under, which is the shape
                # `counter_sessions.counted_totals` already declares.
                # ⚠ **`None` IS REACHABLE AND IS NOT DROPPED.** `payments.method`
                # is nullable, and money with an unreadable tender is money that
                # still has to be accounted for — leaving it out would make the
                # split disagree with `taken`, which is the one thing a
                # reconciliation figure may never do (`_by_method`'s own rule,
                # one module along). It is not countable, so it never reaches a
                # drawer figure.
                "method_id": str(row["method_id"]) if row["method_id"] else None,
                "method_name": row["method__name"],
                "method_code": code,
                "system_total": str(system_total),
                "countable": is_countable,
                "payment_count": row["n"],
                "counted_total": (
                    counted.get(str(row["method_id"])) if row["method_id"] else None
                ),
            }
        )
    opening_float = _q(session.opening_float or ZERO)
    if not any(row["method_code"] == DRAWER_TENDER for row in by_method) and opening_float > ZERO:
        # ⚠ **A TILL THAT TOOK NO CASH STILL HAS A DRAWER WITH THE FLOAT IN
        # IT**, and without this line its cash row would be absent from the
        # Close screen entirely — so the clerk would be asked to count nothing
        # while holding $200.00, and the difference would come out at exactly
        # minus the float. Found by asking what an EMPTY shift looks like.
        cash = _method_row(DRAWER_TENDER)
        countable += opening_float
        by_method.insert(
            0,
            {
                "method_id": str(cash.pk) if cash is not None else None,
                "method_name": getattr(cash, "name", "Cash"),
                "method_code": DRAWER_TENDER,
                "system_total": str(opening_float),
                "countable": True,
                "payment_count": 0,
                "counted_total": counted.get(str(cash.pk)) if cash is not None else None,
            },
        )
    return {
        "by_method": by_method,
        "taken": str(_q(taken)),
        "count": count,
        "opening_float": str(opening_float),
        "countable_expected": str(_q(countable)),
        # BR-TEN-042 locks one currency per tenant; the till's own is the
        # authority when nothing has been taken yet.
        "currency": (currencies.pop() if len(currencies) == 1 else session.currency),
    }


def _expected_countable(session: Any) -> Decimal:
    """What the drawer SHOULD hold, in countable tenders, including the float."""
    return _q(Decimal(running_split(session)["countable_expected"]))


# ════════════════════════════════════════════════════════════════════════════
# `P2.1` · OPEN — the session and its batch, in ONE transaction
# ════════════════════════════════════════════════════════════════════════════
def batch_for(session: Any, *, method_code: str | None = None, day: date) -> tuple[Any, bool]:
    """The till's ONE batch, all tenders, found or opened. **The public seam.**

    ⚠ **AMENDED 2026-10-21 (`CR-186-BRC10`).** PO, verbatim: *"this is one
    batch only - it will ahve 1 batch ID not 2"* — Dana's cash $300.00 and
    cheques $500.00 are ONE batch of $800.00 with a total per tender. So the
    tender no longer chooses the batch: `method_code` is still accepted (and
    still refused when the utility has no such active tender, because a
    payment needs one), and the batch is the till's single all-tenders batch.
    The paragraphs below describe the per-tender seam this replaced; the
    reuse of `reconciliation._get_or_create_batch` and the numbering are
    unchanged.

    `reconciliation._get_or_create_batch` is REUSED rather than re-implemented:
    it already keys on `(tenant, session, method)`, already allocates the code
    from Settings → Numbering's `deposit_batch` series (`DEP-{YY}{MM}{DD}-
    {0000}`, PO ruling 2026-09-22) and already refuses a code collision by name.
    A second implementation here would be a second answer to *"which batch does
    this money go in"*, and hard-won law 5's argument about generated files is
    the same argument about money paths.

    ⚠ **THIS IS WHAT THE TAKE-PAYMENT LANE CALLS, AND IT NOW DOES**
    (`P2.13`, `DEF-PAY-6226`, 2026-09-23 — this paragraph ended *"Nothing
    calls it for those tenders YET"* until then). `services.record_payment`
    calls it inside the payment's own transaction when the payment names a
    till, so every tender other than cash gets its batch from the first
    payment that uses it — see the judgment in the module docstring.
    `test_p2_1_batch_for_is_idempotent` proves the seam;
    `test_cr136_p2_13_the_till_attaches_when_taken.py` proves the wiring.
    """
    method = _method_row(method_code) if method_code else True
    if method is None:
        raise PaymentRuleError(
            f"this utility has no active {method_code!r} tender, so a till cannot open a "
            "deposit batch for it. Settings → Reference data → Payment methods is where a "
            "tender is added or reactivated. Refused rather than opening a batch with no "
            "method: `deposit_batches.method_id` is NOT NULL and a batch that cannot name "
            "its tender cannot be reconciled against a bank statement, which credits cash "
            "and cheques separately.",
            br_ref="BR-PAY-026",
        )
    return reconciliation._get_or_create_batch(
        tenant_id=session.tenant_id,
        day=day,
        session=session,
    )


def _method_row(method_code: str | None) -> Any:
    """This tenant's ACTIVE tender for a code, or None.

    Deliberately NOT importing `counter_receipts._method_row`: that one also
    translates the service-request screen's `cheque` into the tender's `check`,
    which is a different screen's vocabulary and has no business on this path.
    """
    if not method_code:
        return None
    from apps.tenancy import models as tenancy_models

    return tenancy_models.PaymentMethod.objects.filter(
        tenant_id=_tenant_id(), code=str(method_code).strip().lower(), active=True
    ).first()


@permissions.require_role(permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, br_ref="BR-SHL-025")
def open_counter(
    actor: Any,
    *,
    service_centre_id: Any,
    opening_float: Any,
    opened_at: datetime,
    currency: str | None = None,
) -> OpenedCounter:
    """`POST /counters` — *"I am opening the counter for my shift."* (`3·3a`)

    **One act, not two.** The session row and the till's cash batch are created
    inside ONE `transaction.atomic()`: either both exist or neither does. A
    session with no batch is the window the 2026-09-21 ruling exists to close,
    and a batch with no session is refused by the database anyway
    (`trg_deposit_batch_needs_session`).

    ⚠ **THE SECOND-OPEN REFUSAL IS THE DATABASE'S, AND THE CHECK BELOW IS ONLY
    THE SENTENCE.** `uq_counter_sessions_open_owner` is a PARTIAL UNIQUE index
    (`WHERE closed_at IS NULL`), so two terminals pressing *Start counter* in
    the same millisecond cannot both win — one INSERT dies on the index. A
    `SELECT … then INSERT` in this function could not make that true and does
    not claim to; it exists so the loser reads a sentence naming their open till
    instead of a constraint name. **The race is proved on PostgreSQL** in
    `10-scripts/cr136_p2_counters_postgres_proof.py`, not on the default SQLite
    suite where it cannot be (hard-won law 14).

    ⚠ **AND THAT IS ALSO HARD RULE 6'S ANSWER HERE.** A double-clicked *Start
    counter* is the idempotency case this act actually has, and the drawing
    answers it with a REFUSAL rather than with a replay (p017: *"refuses a
    second open counter for the same user"*). The refusal names the till that
    is already open, which is the door the screen needs — a refusal with no way
    out is hard-won law 2's mirror.

    ⚠ **THE WRITE ROLE IS ON THIS FUNCTION AND NOT ON THE ENDPOINT**, because
    `/counters` is one route serving two verbs and `permission_classes` is per
    VIEW: a decorator there would either shut an Executive out of the
    supervisor's LIST or let them open a till. `BR-SHL-025` wants it here
    regardless — server-side enforcement is THE enforcement.

    Hard rule 7: it writes `audit_log`.
    """
    tenant_id = _tenant_id()
    opened_at = _require_moment(opened_at, "the moment the counter was opened")
    amount = _q(_money(opening_float, "the opening float"))
    if amount < ZERO:
        raise PaymentRuleError(
            "an opening float cannot be negative — a drawer that starts owing money is not a "
            "state a shift can be balanced from. `ck_counter_sessions_float_not_negative` "
            "refuses it at the database too.",
            br_ref="BR-PAY-1160",
        )
    owner_id = core_audit.actor_user_id(actor)
    if owner_id is None:
        raise PaymentRuleError(
            "a counter belongs to the person who opens it, and this request names nobody. A "
            "till with no owner is the SYSTEM till, which is born closed and is nobody's — it "
            "is not something a person may open.",
            br_ref="BR-PAY-1160",
        )
    centre = _service_centre(service_centre_id)

    with transaction.atomic():
        already = (
            tills.CounterSession.objects.filter(
                tenant_id=tenant_id, owner_id=owner_id, closed_at__isnull=True
            )
            .order_by("-opened_at")
            .first()
        )
        if already is not None:
            raise PaymentRuleError(
                "you already have a counter open, and one person may have only one at a time. "
                "Close it — count the drawer — and the next one can be started. If it belongs "
                "to a shift that has already ended, a System Admin can force it closed. The "
                "open counter was started on "
                f"{already.opened_at.date().isoformat()}.",
                br_ref="BR-PAY-1160",
            )
        session = _create_with_a_free_code(
            tenant_id=tenant_id,
            owner_id=owner_id,
            service_centre=centre,
            system_day=None,
            opening_float=amount,
            currency=(currency or _tenant_currency()),
            opened_at=opened_at,
        )
        # ── THE BATCH, IN THE SAME TRANSACTION (the judgment, module docstring)
        batch, created = batch_for(session, method_code=DRAWER_TENDER, day=opened_at.date())
        core_audit.money_action(
            actor,
            AUDIT_COUNTER_OPENED,
            "counter_session",
            str(session.pk),
            after={
                "service_centre_id": str(centre.pk),
                "opening_float": str(amount),
                "currency": session.currency,
                "opened_at": opened_at.isoformat(),
                "code": session.code,
                "batch_code": batch.code,
                # CR-186-BRC10 — the till's one batch holds every tender.
                "batch_method": None,
            },
        )
    return OpenedCounter(session=session, batch=batch, batch_created=created)


# ════════════════════════════════════════════════════════════════════════════
# `DEF-PAY-10140` · THE CODE IS ALLOCATED ONCE, AT OPEN, AND STORED
# ════════════════════════════════════════════════════════════════════════════
# Decision log 2026-10-14 *"G1–G4 APPROVED"* item 2 (PO: *"g1-g4 - go"*). The
# first till on a base keeps the plain base (`CTR-261013-BS`); the next till on
# the SAME base — the same person again that day, or a colleague who shares the
# initials — is `CTR-261013-BS-2`, then `-3`. The number is never reused and an
# earlier till's code never moves.
#
#: How many times an open re-chooses its code after losing a race for it. Each
#: retry reads the winner's committed row, so two terminals settle in one; this
#: bounds a pathological loop, it caps nothing a utility owns (`NFR-5`).
CODE_ATTEMPTS = 8
#: The partial unique index that makes the allocation safe under a race.
CODE_CONSTRAINT = "uq_counter_sessions_code"


def _next_free_code(tenant_id: Any, base: str) -> str:
    """`base` if no till of this tenant carries it, else `base-N` one past the highest.

    One indexed read over the tills that share the base — a day's handful for
    one set of initials, never the tenant's history.
    """
    taken = (
        tills.CounterSession.objects.filter(tenant_id=tenant_id)
        .filter(Q(code=base) | Q(code__startswith=f"{base}-"))
        .values_list("code", flat=True)
    )
    highest = 0
    for code in taken:
        if code == base:
            highest = max(highest, 1)
            continue
        suffix = code[len(base) + 1 :]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return base if highest == 0 else f"{base}-{highest + 1}"


def _is_code_collision(error: BaseException) -> bool:
    """True when the refused INSERT died on `uq_counter_sessions_code` itself.

    ⚠ **WALKED, NOT READ ONE HOP** (hard-won law 14): a Django `IntegrityError`
    wraps another, and the driver's message naming the constraint is further
    down. SQLite names the COLUMNS instead of the index, so both are accepted.
    Anything else — the second-open index above all — is re-raised unchanged.
    """
    seen: BaseException | None = error
    while seen is not None:
        text = str(seen)
        if CODE_CONSTRAINT in text or "counter_sessions.code" in text:
            return True
        seen = seen.__cause__ or seen.__context__
    return False


def _create_with_a_free_code(**columns: Any) -> Any:
    """INSERT the till with the next free code, retrying if a twin terminal won it.

    ⚠ **THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE** (hard-won law 14).
    This runs inside `open_counter`'s transaction; on PostgreSQL a refused
    INSERT aborts the whole transaction unless it was wrapped in a nested
    `atomic()`, and the retry would meet `InFailedSqlTransaction`. SQLite has no
    such state, so the race is proved on PostgreSQL in
    `tests/test_def_pay_10140_counter_code_stored.py`.
    """
    probe = tills.CounterSession(**columns)
    base = composed_code_base(probe, owner=_owner_row(columns.get("owner_id")))
    tenant_id = columns["tenant_id"]
    for _attempt in range(CODE_ATTEMPTS):
        code = _next_free_code(tenant_id, base)
        try:
            with transaction.atomic():
                return tills.CounterSession.objects.create(code=code, **columns)
        except IntegrityError as refused:
            if not _is_code_collision(refused):
                raise
    raise PaymentRuleError(
        f"{CODE_ATTEMPTS} counters were started at the same moment under {base}, and this one "
        "could not be given a number. Press Start counter again.",
        br_ref="BR-PAY-1160",
    )


def _owner_row(owner_id: Any) -> Any:
    """The person whose initials go into the code — read once, at open."""
    from apps.identity import models as identity_models

    if owner_id is None:
        return None
    return identity_models.User.objects.filter(pk=owner_id).first()


def _service_centre(service_centre_id: Any) -> Any:
    """The walk-in counter this till is at — required, and this tenant's.

    A cross-tenant id reads as ABSENT rather than as forbidden (hard rule 1 /
    BR-TEN-003): telling a caller that somebody else's centre exists is itself
    a leak.
    """
    from apps.tenancy import published_content_models as places

    if not service_centre_id:
        raise PaymentRuleError(
            "a counter is a till AT a place, and this request names none. p101 of the "
            "blueprint puts it plainly: a counter is not a location, it is a till at one, and "
            "one office can have three windows each with its own drawer. Choose the service "
            "centre you are taking money at.",
            br_ref="BR-PAY-1160",
        )
    # ⚠ **THE SLUG FIRST, AND B14 RULE 31 IS WHY.** The reference-data list is
    # keyed by slug everywhere it is already read, and a database id may never
    # be the visible value of a field — which a form value that lands in an
    # error message is. The primary key is still accepted, because a caller
    # that already holds one should not be made to look a slug up.
    reference = str(service_centre_id).strip()
    centre = places.ServiceCentre.objects.filter(tenant_id=_tenant_id(), slug=reference).first()
    if centre is None and _looks_like_a_uuid(reference):
        centre = places.ServiceCentre.objects.filter(tenant_id=_tenant_id(), pk=reference).first()
    if centre is None:
        raise PaymentRuleError(
            "that service centre is not one of this utility's. Configure → Reference data → "
            "Service centres is where they are kept.",
            br_ref="BR-TEN-003",
        )
    return centre


def _tenant_currency() -> str:
    """BR-TEN-042 — one currency per tenant. Hard rule 2's `CHAR(3)` half.

    `settings_seam.tenant_currency()` REFUSES rather than defaulting to `USD`,
    and that refusal is inherited here on purpose: a float stated in a currency
    nobody configured is half a money fact, and defaulting would put a
    Canadian utility's drawer into dollars it does not hold.
    """
    from apps.payments import settings_seam

    return settings_seam.tenant_currency()


# ════════════════════════════════════════════════════════════════════════════
# HOW A COUNTER IS NAMED ON THE WIRE — ITS CODE, NEVER ITS PRIMARY KEY
# ════════════════════════════════════════════════════════════════════════════
# ⚠ **THIS IS A CONTRACT A SIBLING LANE WROTE DOWN AND THIS ONE HONOURS.**
# `07-frontend/src/api/counterEndpoints.ts` (LANE P2-SCREENS) states it in its
# own header: 3·2's address is drawn as `/:tenant/payments/counter/
# CTR-260921-DW` — the CODE — while every write is drawn as
# `POST /counters/{id}`. **Both cannot be literally true of one value, and B14
# rule 31 decides it**: no database id is ever the visible value of a field,
# and an address bar is the most visible field there is. So every route segment
# is a `CounterRef`, which is the code.
#
# ⚠ **THE PRIMARY KEY IS STILL ACCEPTED**, and that is not hedging: it is the
# unambiguous name. ⚠ **THIS BLOCK SAID UNTIL 2026-10-14 THAT THE ONE CASE THE
# CODE CANNOT ANSWER IS TWO PEOPLE WITH ONE SET OF INITIALS ON ONE DAY**, and
# sent the clerk to the list for the id. Two things were wrong with it
# (`DEF-PAY-10140`): the SAME person opening twice in a day collided too, and
# the list printed the same code, so the advice led nowhere. The code is now
# STORED and unique per tenant, with `-2`, `-3` for a repeat base, and the
# collision cannot arise for any till a person opened.
def _looks_like_a_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


class CounterCodeUnknown(PaymentRuleError):
    """No till of this tenant answers to that code or id (`payments.counter.not_found`)."""


class CounterCodeAmbiguous(PaymentRuleError):
    """Two tills with NO stored code compose one label — the safety net only."""


def _session_by_ref(ref: Any) -> Any:
    """This tenant's till, named by its CODE or by its id. Absent reads as absent.

    ⚠ **BY THE STORED CODE FIRST (`DEF-PAY-10140`).** Until 2026-10-14 the code
    was composed on every read and resolved by recomposing it over the day's
    tills, and a code matching two was refused — reasoning only about two
    DIFFERENT people with one set of initials. The same person opening twice in
    a day matched twice too, and the refusal's advice (*open it from the
    list*) was a dead end because the list served the same code. The code is
    now a stored, per-tenant-unique column, so one code is one till.

    The id still resolves — it is the unambiguous name, and the open endpoint
    reads its own new row back by it.

    ⚠ **THE RECOMPOSING PATH SURVIVES ONLY AS A SAFETY NET**, over rows with no
    stored code (a system till, which no person reaches, or a row written
    behind the service's back). Two such rows answering one label are refused
    BY NAME rather than guessed between.
    """
    tenant_id = _tenant_id()
    reference = str(ref or "").strip()
    if not reference:
        raise CounterCodeUnknown("no counter was named.", br_ref="BR-TEN-003")
    if _looks_like_a_uuid(reference):
        found = tills.CounterSession.objects.filter(tenant_id=tenant_id, pk=reference).first()
        if found is not None:
            return found
    wanted = reference.upper()
    stored = (
        tills.CounterSession.objects.filter(tenant_id=tenant_id, code=wanted)
        .select_related("owner", "service_centre")
        .first()
    )
    if stored is not None:
        return stored
    day = _day_in_code(reference)
    candidates = []
    if day is not None:
        candidates = [
            row
            for row in tills.CounterSession.objects.filter(
                tenant_id=tenant_id, opened_at__date=day, code__isnull=True
            ).select_related("owner", "service_centre")
            if counter_code(row) == wanted
        ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise CounterCodeAmbiguous(
            f"two counters opened on that day answer to {reference} and neither has a stored "
            "code. Open the one you want by its id.",
            br_ref="BR-PAY-1160",
        )
    raise CounterCodeUnknown("that counter is not one of this utility's.", br_ref="BR-TEN-003")


def _day_in_code(reference: str) -> date | None:
    """`CTR-260921-DW` → 21 Sep 2026, or None when the shape is not a code."""
    parts = reference.split("-")
    if len(parts) < 3 or parts[0].upper() != "CTR" or len(parts[1]) != 6:
        return None
    try:
        return datetime.strptime(parts[1], "%y%m%d").date()
    except ValueError:
        return None


# ════════════════════════════════════════════════════════════════════════════
# `P2.2` · THREE ENDPOINTS, THREE DIFFERENT ROWS
# ════════════════════════════════════════════════════════════════════════════
def _open_session(session_id: Any) -> Any:
    """This tenant's till, and it must still be open.

    A cross-tenant id reads as ABSENT (hard rule 1 / BR-TEN-003). An already
    closed one is refused by NAME and with its close kind, because *"it was
    already closed"* and *"somebody force-closed it an hour ago"* are different
    facts and only the second tells a clerk what to do next.
    """
    session = _session_by_ref(session_id)
    if session.closed_at is not None:
        raise PaymentRuleError(
            f"this counter was already sealed on {session.closed_at.date().isoformat()} "
            f"({session.close_kind}). A till is sealed once — corrections are new records, "
            "never an edit of a closed one. A forced close with no count can still be "
            "declared.",
            br_ref="BR-PAY-1160",
        )
    if session.system_day is not None:  # pragma: no cover - a system till is born closed
        raise PaymentRuleError(
            "that till is the system's own — it holds money that arrived over a wire and "
            "nobody ever sat at it. It is born closed and there is nothing to seal.",
            br_ref="BR-PAY-1160",
        )
    return session


def _counted_map(session: Any, counted_totals: Any) -> tuple[dict[str, str], Decimal]:
    """The clerk's count, keyed by `payment_methods.id`, and its countable sum.

    ⚠ **THE KEY MAY BE EITHER THE METHOD ID OR ITS CODE, AND IT IS STORED AS
    THE ID EITHER WAY.** `counter_sessions.counted_totals` declares
    `{payment_method_id: "1240.0000"}` and `CounterMethodTotal.method_id` is
    what the Close screen posts back, so an id is the ordinary case. A code is
    accepted because a code is what a person writing this by hand — a test, a
    script, a support call — would reach for, and refusing it would be a
    refusal about spelling rather than about money. **A tenant may rename a
    tender**, which is why the ID is what gets stored: a stored code would
    describe something that no longer exists.

    ⚠ **THE VALUES ARE STRINGS AND HARD RULE 2 IS WHY.** A JSON number is a
    double in every serialiser this stack uses, so `1240.00` round-trips as
    `1240.0000000000001` sooner or later — on a figure whose entire job is to
    be compared with a drawer.

    ⚠ **A TENDER THE SCREEN CANNOT COUNT IS REFUSED BY NAME.** p056 ③: *"you
    cannot count a card total in a drawer, so the screen does not pretend"*. A
    card figure typed into this map would be the system's own number handed
    back, and a reconciliation built on it proves nothing.
    """
    if not isinstance(counted_totals, dict) or not counted_totals:
        raise PaymentRuleError(
            "a close with no count is a FORCED close and is a different act, done by a System "
            "Admin and recorded as such. To close your own till, type what is in the drawer.",
            br_ref="BR-PAY-1160",
        )
    stored: dict[str, str] = {}
    counted = ZERO
    for raw_key, raw_amount in counted_totals.items():
        method = _method_by_ref(raw_key)
        if method is None:
            raise PaymentRuleError(
                f"this utility has no active {str(raw_key)!r} tender, so nothing can be "
                "counted against it. Settings → Reference data → Payment methods is where a "
                "tender is added or reactivated.",
                br_ref="BR-PAY-026",
            )
        code = method.code
        if code not in COUNTABLE_TENDERS:
            raise PaymentRuleError(
                f"{code!r} is not a tender a drawer can be counted in. Only cash, cheques and "
                "money orders are physically in the drawer; a card total typed back at the "
                "system's own figure would make the whole reconciliation worthless.",
                br_ref="BR-PAY-1160",
            )
        amount = _q(_money(raw_amount, f"the counted {code} figure"))
        if amount < ZERO:
            raise PaymentRuleError(
                f"the counted {code} figure is negative. A drawer holds what it holds; a "
                "shortfall is the DIFFERENCE and this product works it out for you.",
                br_ref="BR-PAY-1160",
            )
        stored[str(method.pk)] = str(amount)
        counted += amount
    return stored, _q(counted)


def _method_by_ref(reference: Any) -> Any:
    """This tenant's ACTIVE tender, named by its id or by its code."""
    key = str(reference or "").strip()
    if not key:
        return None
    if _looks_like_a_uuid(key):
        from apps.tenancy import models as tenancy_models

        return tenancy_models.PaymentMethod.objects.filter(
            tenant_id=_tenant_id(), pk=key, active=True
        ).first()
    return _method_row(key)


def _note_for(difference: Decimal, note: Any) -> str | None:
    """Required only when the difference is not zero — a SERVICE rule (p056).

    The database deliberately cannot demand it: a FORCED close has no count to
    explain, and a `CHECK` that insisted on a note would make a forced close
    impossible to record. `counter_session_models` says the same from the other
    side.
    """
    text = (str(note).strip() if note is not None else "") or None
    if difference != ZERO and not text:
        raise PaymentRuleError(
            "the drawer does not balance, so say why in one line. A difference with no "
            "explanation is the one thing nobody can reconcile later — and this is the only "
            "place the reason is recorded.",
            br_ref="BR-PAY-1160",
        )
    return text


def _seal_batches(session: Any) -> list[str]:
    """Foot every batch this till opened, so the deposit is bankable.

    p059: *"Close — … The batch becomes bankable. It IS the deposit batch, so
    it appears on Finance → Deposits ready to be matched."* A batch's
    `recorded_total` is Σ its member payments and is **system-derived, never
    hand-edited** (US-PAY-020 §5) — but nothing had recomputed it since the
    till opened, because `cut_deposit_batches` only foots the batches IT cuts,
    and a counter payment is already banked in its till's batch and is
    therefore excluded from the cut by `deposit_batch_id IS NULL`.

    ⚠ **WITHOUT THIS, EVERY COUNTER BATCH WOULD REACH FINANCE AT `$0.00`** —
    with the right payments in it, the right method and the right day, and a
    total that says the shift took nothing. That is the shape this repo files
    most: the absence is invisible, every test passes, and a finance lead is
    handed a deposit slip for zero dollars. `P2.10` is the lane that renders
    it; this is the figure it renders.

    `recompute_batch_total` is REUSED rather than re-summed here, so there is
    one answer to *what is in this batch* — and it refuses on a RECONCILED
    batch (BR-PAY-004), which is the correct posture: a batch already agreed
    against a bank statement does not move because somebody closed a till.
    """
    footed: list[str] = []
    for batch in bankrec.DepositBatch.objects.filter(
        tenant_id=session.tenant_id, session_id=session.pk
    ).order_by("code"):
        if batch.status == bankrec.BATCH_RECONCILED:  # pragma: no cover - BR-PAY-004
            continue
        reconciliation.recompute_batch_total(batch.pk)
        footed.append(batch.code)
    return footed


def close_counter(
    actor: Any,
    *,
    session_id: Any,
    counted_totals: Any,
    closed_at: datetime,
    note: Any = None,
) -> SealedCounter:
    """`POST /counters/{id}/close` — *"My shift is over: does the drawer match?"*

    **A COMPARISON, NEVER A READ-BACK** (p055). The clerk types what is in the
    drawer; this works out what the system says and stores the difference as it
    stood at the count.

    Worked, and it is the blueprint's own figure: a till with a **$200.00**
    float that took **$310.00** cash and **$1,284.60** in cheques expects
    **$1,794.60** countable. A clerk who counts exactly that stores
    `difference = 0.0000`, writes no note and posts no journal line.

    `difference` is STORED rather than derived because it is a SNAPSHOT of a
    comparison: payments move, are reversed and are reallocated afterwards, and
    re-deriving it next month would answer a different question.

    ⚠ **`P2.22` — A NON-ZERO DIFFERENCE REACHES THE BOOKS, AND THIS SUPERSEDES
    THE DRAWING.** p059 says *"The ledger: Nothing — counting is not a
    posting"*. **PO ruling 2026-09-23 §3.3 reverses it, verbatim:** *"(b) Post
    it. A short writes a balanced pair to a cash over/short account the day it
    is declared. Needs one new account added to the chart"*. Posted INSIDE this
    transaction, through `ledger_seam` — hard rule 5, payments never writes a
    journal line itself.

    Hard rule 7: it writes `audit_log`.
    """
    closed_at = _require_moment(closed_at, "the moment the counter was closed")
    with transaction.atomic():
        session = _open_session(session_id)
        expected = _expected_countable(session)
        stored, counted = _counted_map(session, counted_totals)
        difference = _q(counted - expected)
        text = _note_for(difference, note)
        closer = core_audit.actor_user_id(actor)
        session.closed_at = closed_at
        session.closed_by_id = closer
        session.close_kind = models.COUNTER_CLOSE_COUNTED
        session.counted_totals = stored
        session.difference = difference
        session.note = text
        session.save(
            update_fields=[
                "closed_at",
                "closed_by",
                "close_kind",
                "counted_totals",
                "difference",
                "note",
                "updated_at",
            ]
        )
        footed = _seal_batches(session)
        posting_key = _post_difference(
            actor, session=session, difference=difference, when=closed_at
        )
        core_audit.money_action(
            actor,
            AUDIT_COUNTER_CLOSED,
            "counter_session",
            str(session.pk),
            after={
                "close_kind": models.COUNTER_CLOSE_COUNTED,
                "closed_at": closed_at.isoformat(),
                "counted_totals": stored,
                "expected_countable": str(expected),
                "counted_countable": str(counted),
                "difference": str(difference),
                "note": text,
                "posting_key": posting_key,
                "batches": footed,
            },
        )
    return SealedCounter(session=session, difference=difference, posting_key=posting_key)


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-SHL-025")
def force_close_counter(
    actor: Any, *, session_id: Any, reason: Any, closed_at: datetime
) -> SealedCounter:
    """`POST /counters/{id}/force-close` — *"Someone went home without closing."*

    **PO ruling 2026-09-22, verbatim: *"(b) A System Admin can close it,
    recorded as a forced close"*.** The case that forced it: Dana opens a till
    on Monday, takes **$1,240 in cheques**, goes home at 17:00 without closing,
    and is off sick on Tuesday. Under *only Dana may close it* the one-open-
    till-per-person index means Dana cannot work when they return.

    ⚠ **`@require_role(SYSTEM_ADMIN)` IS ON THIS FUNCTION AND NOT ON AN
    ENDPOINT**, because `BR-SHL-025` makes the server the enforcement: a button
    hidden from a Billing Clerk is not a guarantee, and this refuses no matter
    which endpoint, job or shell forgot to gate. The endpoint mounts
    `SystemAdminOnly` as well, so a wrong role is refused twice.

    ⚠ **`closed_by` IS THE SUPERVISOR AND NOT THE OWNER**, for ever. Somebody
    other than the person accountable for the drawer has declined to count it,
    and the two people stay distinguishable — which is the whole point of the
    ruling.

    ⚠ **NO COUNT, SO NO JOURNAL LINE.** `P2.22` posts when the money is
    COUNTED; a forced close counted nothing and posts nothing. The pair comes
    later, at `declare`, which is what makes the PO's *"the day it is
    declared"* true of both paths.

    ⚠ **AND IT NEVER HAPPENS ON A CLOCK.** The midnight auto-close the
    blueprint draws at `P2.18` was STRUCK by the PO on 2026-09-23: *"(a) Your
    ruling stands — no auto-close. A System Admin closes it. Dana cannot work
    Tuesday until someone is free to do that"*. No scheduled job exists and
    none may be written.
    """
    closed_at = _require_moment(closed_at, "the moment the counter was force-closed")
    text = (str(reason).strip() if reason is not None else "") or None
    if not text:
        raise PaymentRuleError(
            "say why this counter is being closed for somebody else. A forced close with no "
            "reason is indistinguishable from a mistake, and this is the only record of it.",
            br_ref="BR-PAY-1160",
        )
    with transaction.atomic():
        session = _open_session(session_id)
        closer = core_audit.actor_user_id(actor)
        session.closed_at = closed_at
        session.closed_by_id = closer
        session.close_kind = models.COUNTER_CLOSE_FORCED
        # ⚠ **THE REASON DOES *NOT* GO IN `note`, AND THAT COSTS SOMETHING THAT
        # IS NAMED RATHER THAN HIDDEN.** `note` is the DECLARE's column (§3.2:
        # *"Declaring fills counted_totals, difference and note — NULL on a
        # forced close precisely because nobody counted"*), so writing the
        # supervisor's reason here would be silently overwritten by the late
        # count's own note — which is exactly the *"Nothing is erased"* the
        # same ruling insists on. So the reason lives in `audit_log` alone, and
        # `audit_log` is PRUNED on a retention schedule (`OQ-1340`, OPEN).
        # p057 calls the field *"the only record of the reason"*, and today
        # that record is not permanent. Raised as `OQ-PAY-12600`; no screen,
        # document or docstring may call this path a permanent record until it
        # is answered.
        session.save(update_fields=["closed_at", "closed_by", "close_kind", "updated_at"])
        # The drawer was not counted; the MONEY still went to the bank. A
        # forced close's batches are footed exactly like a counted close's,
        # because what is in them is a fact about payments and not about
        # whether anybody looked in the drawer.
        footed = _seal_batches(session)
        core_audit.money_action(
            actor,
            AUDIT_COUNTER_FORCE_CLOSED,
            "counter_session",
            str(session.pk),
            after={
                "close_kind": models.COUNTER_CLOSE_FORCED,
                "closed_at": closed_at.isoformat(),
                "reason": text,
                "owner_id": str(session.owner_id),
                "expected_countable": str(_expected_countable(session)),
                # The count is ABSENT rather than zero — nobody counted.
                "counted_totals": None,
                "difference": None,
                "batches": footed,
            },
        )
    return SealedCounter(session=session, difference=None, posting_key=None)


def declare_counter(
    actor: Any,
    *,
    session_id: Any,
    counted_totals: Any,
    declared_at: datetime,
    note: Any = None,
) -> SealedCounter:
    """`POST /counters/{id}/declare` — the count, late, beside the forced close.

    **PO ruling 2026-09-23 §3.2, verbatim:** *"(a) Keep it as a forced close and
    add the late count beside it… The row reads: force-closed Monday by the
    supervisor, declared Tuesday by Dana, $12 short. It leaves the Not counted
    list. Nothing is erased"*.

    So this fills `counted_totals`, `difference`, `note`, `declared_at` and
    `declared_by` — and **leaves `close_kind` at `forced`**. There is no fourth
    close kind; it was put to the PO and declined.

    ⚠ **HARD RULE 4 DOES NOT BITE, AND IT WAS CHECKED RATHER THAN ASSUMED.**
    The rule freezes issued invoices, invoice lines, payments and journal
    entries. `counter_sessions` is none of those, carries no immutability
    trigger of its own (`payments/0031`–`0034` mint `ck_…` CHECK constraints and
    an RLS policy, and no `trg_…` at all), and `trg_payment_immutable` is a
    trigger ON `payments`. So this UPDATE is lawful. What it may NOT do is
    change anything the forced close recorded — and it does not.

    ⚠ **ONLY ON A FORCED CLOSE, AND ONLY ONCE.** A counted till was already
    counted; a system till is nobody's; and a second declare would silently
    overwrite the first person's figure. §3.2 asks for the CHECK constraint
    (`P2.20`) to say the first half at the database; this says both halves with
    a sentence a person can act on.

    ⚠ **`P2.22` POSTS HERE** — *"the day it is declared"*, in the PO's own
    words, for a till that was forced closed.
    """
    declared_at = _require_moment(declared_at, "the moment the count was declared")
    with transaction.atomic():
        session = tills.CounterSession.objects.filter(tenant_id=_tenant_id(), pk=session_id).first()
        if session is None:
            raise PaymentRuleError(
                "that counter is not one of this utility's.", br_ref="BR-TEN-003"
            )
        if session.close_kind != models.COUNTER_CLOSE_FORCED:
            raise PaymentRuleError(
                "only a till that was force-closed without a count can be declared. This one "
                f"is {session.close_kind or 'still open'} — a counted till was already "
                "counted, and an open one is closed by counting it.",
                br_ref="BR-PAY-1160",
            )
        # ⚠ **THE CAPABILITY CHECK COMES AFTER THE *WHICH TILL* CHECK, AND THE
        # ORDER IS THE CLERK'S RATHER THAN THE CODE'S.** A person aiming
        # `declare` at a counted till needs to be told it was already counted,
        # whichever columns this database happens to have; telling them the
        # product is half-built instead would send them to the wrong place.
        # Same argument `cut_deposit_batches` makes for testing the TYPE before
        # the tender one module along.
        if not _declaration_columns_exist():
            raise PaymentRuleError(
                "a late count cannot be recorded yet: this database has nowhere to put WHO "
                "declared it and WHEN, so recording the figure alone would make a forced "
                "close look like a counted one and erase who did what. The two columns are "
                "task `P2.20` of the counter work and they are not in this database.",
                br_ref="BR-PAY-1160",
            )
        if session.declared_at is not None:
            raise PaymentRuleError(
                "this counter has already been declared, on "
                f"{session.declared_at.date().isoformat()}. A drawer is counted once; a second "
                "figure would overwrite the first person's and nothing would say it had.",
                br_ref="BR-PAY-1160",
            )
        expected = _expected_countable(session)
        stored, counted = _counted_map(session, counted_totals)
        difference = _q(counted - expected)
        # ⚠ **A DECLARE ALWAYS NEEDS A REASON, WHERE A COUNTED CLOSE NEEDS ONE
        # ONLY WHEN IT DOES NOT BALANCE.** p058 ②, verbatim: *"A reason is
        # required — because a declared difference is the only number nobody
        # watched happen"*. Nobody was at this drawer when it was sealed and
        # nobody was there when it was counted, so the sentence somebody
        # writes is the entire record of what happened to it.
        text = (str(note).strip() if note is not None else "") or None
        if not text:
            raise PaymentRuleError(
                "say what happened to this till. Nobody was there when it was sealed and "
                "nobody watched it being counted, so this sentence is the only record of "
                "why the figure is what it is.",
                br_ref="BR-PAY-1160",
            )
        session.counted_totals = stored
        session.difference = difference
        session.note = text
        session.declared_at = declared_at
        session.declared_by_id = core_audit.actor_user_id(actor)
        session.save(
            update_fields=[
                "counted_totals",
                "difference",
                "note",
                "declared_at",
                "declared_by",
                "updated_at",
            ]
        )
        posting_key = _post_difference(
            actor, session=session, difference=difference, when=declared_at
        )
        core_audit.money_action(
            actor,
            AUDIT_COUNTER_DECLARED,
            "counter_session",
            str(session.pk),
            after={
                # UNCHANGED, and said out loud in the trail: the forced close
                # stands and the late count sits beside it.
                "close_kind": models.COUNTER_CLOSE_FORCED,
                "declared_at": declared_at.isoformat(),
                "counted_totals": stored,
                "expected_countable": str(expected),
                "counted_countable": str(counted),
                "difference": str(difference),
                "note": text,
                "posting_key": posting_key,
            },
        )
    return SealedCounter(session=session, difference=difference, posting_key=posting_key)


# ════════════════════════════════════════════════════════════════════════════
# `P2.22` · THE DRAWER DIFFERENCE REACHES THE BOOKS — ⚠ SUPERSEDES THE DRAWING
# ════════════════════════════════════════════════════════════════════════════
def _post_difference(
    actor: Any, *, session: Any, difference: Decimal, when: datetime
) -> str | None:
    """A non-zero drawer difference writes a balanced pair. Zero writes nothing.

    **PO ruling 2026-09-23 §3.3, verbatim:** *"(b) Post it. A short writes a
    balanced pair to a cash over/short account the day it is declared. Needs one
    new account added to the chart"*. The blueprint says the opposite at p059
    (*"The ledger: Nothing — counting is not a posting"*) and the ruling wins;
    `P2.15`'s test flips with it.

        $12.0000 SHORT   DR 6850 Cash over and short · CR 1010 Undeposited funds
        $12.0000 OVER    DR 1010 Undeposited funds  · CR 6850 Cash over and short

    **One account, both directions.** A short is an expense the utility takes;
    an over is that expense given back. Two accounts would make the month's net
    position a subtraction somebody has to do by hand.

    **Against `1010`, not `1000`, and that is the load-bearing half.** Taking a
    payment already DEBITS `1010 Undeposited funds` (`post_payment_cleared`);
    the bank only ever receives what was physically in the drawer, so the
    difference has to leave `1010` **before** the deposit clears it. Posted
    against `1000 Cash` instead, reconciliation would carry a permanent
    `$12.00` stub in undeposited funds that no statement will ever match —
    `apps/ledger/reporting.py` explains the 1010 → 1000 move this depends on.

    **It posts when the money is COUNTED** — at close on a counted close, at
    DECLARE on a forced one. That is what makes *"the day it is declared"* true
    of both paths, and it is why this is called from two places and defined in
    one.

    **Hard rule 5 is untouched.** Payments does not write a journal line: it
    calls `ledger_seam`, which calls the ledger's posting service, exactly as
    taking a payment already does. Hard rule 6's replay guard is the posting
    key, so a retried close writes one entry and not two.
    """
    if difference == ZERO:
        # A journal line for money that did not move is a line somebody has to
        # explain. The same rule `post_payment_cleared` applies to a zero leg.
        return None
    return ledger_seam.post_counter_difference(
        session=session,
        difference=difference,
        entry_date=when.date(),
        posted_at=when,
        actor=actor,
    ).posting_key


# ════════════════════════════════════════════════════════════════════════════
# `P2.3` · THE READS — paginated in SQL, sorted in SQL, summed in SQL
# ════════════════════════════════════════════════════════════════════════════
#: `?f.state=` — the three a supervisor filters on, and `not_counted` is the
#: chip §3.2 names as one of `not_counted_q()`'s four readers.
STATE_OPEN = "open"
STATE_CLOSED = "closed"
STATE_NOT_COUNTED = "not_counted"
COUNTER_STATES: tuple[str, ...] = (STATE_OPEN, STATE_CLOSED, STATE_NOT_COUNTED)

#: BR-SHL-011's `sort` names, mapped to real columns. **Every value is a
#: column**, so the ORDER BY is the database's — `NFR-3`, and the reason
#: `GET /outstandings` is a defect (`DEF-PAY-4221`) is that it sorts in Python.
_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "opened_at": ("opened_at",),
    "closed_at": ("closed_at",),
    "owner": ("owner__full_name",),
    "centre": ("service_centre__name",),
}


def _is_true(value: Any) -> bool:
    """`f.mine=1` — a filter VALUE is a string off a query string.

    `1`, `true` and `yes` are what a client sends; anything else, including the
    empty string a cleared control produces, is absent. An EMPTY value is an
    ABSENT dimension and never a filter for nothing, which is the convention
    every other list in this product already keeps.
    """
    return str(value or "").strip().lower() in ("1", "true", "yes")


def counter_list_queryset(params: ListParams, *, actor: Any = None) -> QuerySet:
    """`GET /counters` — `3·1`, *"Whose till is open, and whose did not get counted?"*

    ⚠ **SERVER PAGINATION AND A SQL SORT, BECAUSE `NFR-3` AND `NFR-5` ARE THE
    DELIVERABLE AND NOT THE BACKGROUND.** No slice of this is materialised: the
    caller hands the queryset to `StandardPagination`, which adds `LIMIT` and
    `OFFSET`. Four lists in this module already breach that rule by sorting in
    Python and naming a 3,000-connection utility as the excuse — correct at T7
    and **13× short of T5**. This is not a fifth.

    `q` matches the till's OWNER by name. It deliberately does NOT match an id:
    B14 rule 31 keeps database ids off the screen, so an id is not something a
    clerk could have read to search for.

    ⚠ **`f.mine=1` IS NARROWED HERE, FROM THE AUTHENTICATED CALLER, AND THAT
    IS THE WHOLE POINT OF IT (`DEF-PAY-6235`).** The row a screen gets carries
    `owner_name` and **no owner id** — deliberately, B14 rule 31 — so a client
    asking *"is MY till open?"* can only match the person by their DISPLAYED
    NAME. **A name is not an identity**: two staff called the same thing at one
    utility, or a renamed user, and the page head offers somebody else's drawer
    beside a button that takes money. The identity is on the server and the
    narrowing belongs where the identity is.

    ⚠ **AN UNRESOLVABLE CALLER GETS NOTHING, NOT EVERYTHING.** If `f.mine` is
    asked and no user can be resolved from the actor, this answers the EMPTY
    set. The other direction — quietly ignoring the filter — is exactly the
    defect: it returns every till in the utility and looks like a working read.
    """
    queryset = tills.CounterSession.objects.filter(
        tenant_id=_tenant_id(),
        # A system till is nobody's and never appears on a supervisor's list of
        # drawers — it is born closed with no owner and nobody sat at it.
        system_day__isnull=True,
    ).select_related("owner", "service_centre")

    state = (params.filters.get("state") or "").strip().lower()
    if state == STATE_OPEN:
        queryset = queryset.filter(closed_at__isnull=True)
    elif state == STATE_CLOSED:
        queryset = queryset.filter(closed_at__isnull=False)
    elif state == STATE_NOT_COUNTED:
        queryset = queryset.filter(not_counted_q())

    # `f.mine=1` before `f.owner_id`, and they COMPOSE rather than override:
    # asking for *my* tills and *somebody else's* at once is a contradiction,
    # and two `filter()` calls answer it with the empty set, which is the truth.
    if _is_true(params.filters.get("mine")):
        caller_id = core_audit.actor_user_id(actor)
        queryset = queryset.filter(owner_id=caller_id) if caller_id else queryset.none()

    owner_id = (params.filters.get("owner_id") or "").strip()
    if owner_id:
        queryset = queryset.filter(owner_id=owner_id)
    centre_id = (params.filters.get("centre_id") or "").strip()
    if centre_id:
        queryset = queryset.filter(service_centre_id=centre_id)

    if params.q:
        queryset = queryset.filter(
            Q(owner__full_name__icontains=params.q)
            | Q(owner__email__icontains=params.q)
            | Q(service_centre__name__icontains=params.q)
        )

    columns = _SORT_COLUMNS.get(params.sort or DEFAULT_COUNTER_SORT, ("opened_at",))
    prefix = "-" if params.dir == "desc" else ""
    # `id` LAST and always: two tills opened in the same second would otherwise
    # come back in a different order on page 1 and page 2, and a row would be
    # served twice or not at all. A stable tiebreak is part of pagination, not
    # a nicety.
    return queryset.order_by(*[f"{prefix}{column}" for column in columns], "id")


def counter_list_totals(queryset: QuerySet, *, as_of: date | None = None) -> dict[str, Any]:
    """`3·1`'s four tiles, folded over the WHOLE filtered set in SQL.

    Drawn at p051: **OPEN NOW 2** with the two names under it · **TAKEN TODAY
    $4,101.10 / 41 payments** · **NOT COUNTED 3 / Oldest 09/18** · **DIFFERENCE
    THIS WEEK $0.00**.

    ⚠ **EVERY FIGURE IS A DATABASE AGGREGATE OVER THE FILTER, NOT OVER THE
    PAGE** (`NFR-3`). A tile computed in the browser off one page of a
    paginated list says *2 open* when there are fifty, and it is right about
    the page, which is what makes it so hard to notice.

    ⚠ **THE TWO DAY-SHAPED TILES ANSWER `null` WITHOUT `as_of`, AND SAY WHY.**
    Nothing under `apps/payments/` may read a wall clock (BR-TEN-043, gate G6
    rule 3): a server clock decides a business day in the SERVER's timezone.
    A stated absence beats a figure that is quietly a day out — `DEF-099`'s
    rule, which `counter_receipts.list_totals` already applies to a currency.

    ⚠ **`open_owner_names` IS BOUNDED AND SAYS SO.** It is the detail line
    under a tile — two names at a two-window office — and a utility with fifty
    open tills gets the first ten and a count. That is a DISPLAY bound on one
    tile's subtitle, not a cap on the list, which stays paginated and uncapped
    (`NFR-5`).
    """
    open_now = queryset.filter(closed_at__isnull=True)
    names = [
        _person(row.owner) for row in open_now.select_related("owner").order_by("-opened_at")[:10]
    ]
    uncounted = queryset.filter(not_counted_q())
    oldest = uncounted.order_by("opened_at").values_list("opened_at", flat=True).first()
    totals: dict[str, Any] = {
        "open_now": open_now.count(),
        "open_owner_names": [name for name in names if name],
        "not_counted": uncounted.count(),
        "not_counted_oldest": _iso(oldest),
        "currency": _tenant_currency(),
    }
    if as_of is None:
        totals.update(
            {
                "taken_today": None,
                "taken_today_payment_count": None,
                "difference_this_week": None,
                "totals_unavailable": "as_of_missing",
            }
        )
        return totals
    week_start = as_of - timedelta(days=6)
    difference = queryset.filter(
        closed_at__date__gte=week_start, closed_at__date__lte=as_of
    ).aggregate(total=Sum("difference"))["total"]
    taken = _takings_on(queryset, day=as_of)
    totals.update(
        {
            "taken_today": str(_q(taken[0])),
            "taken_today_payment_count": taken[1],
            "difference_this_week": str(_q(difference or ZERO)),
        }
    )
    return totals


def _takings_on(queryset: QuerySet, *, day: date) -> tuple[Decimal, int]:
    """What every till in this filter took on one day — ONE aggregate.

    Read through the tills' BATCHES, which is the only link a payment has to a
    counter until `P2.4` lands `counter_session_id`; when it does, the second
    half below starts answering and the two are read TOGETHER rather than one
    replacing the other.
    """
    session_ids = queryset.values("pk")
    batch_ids = bankrec.DepositBatch.objects.filter(session_id__in=session_ids).values("pk")
    clause = Q(deposit_batch_id__in=batch_ids)
    if _payments_name_their_till():
        clause = clause | Q(counter_session_id__in=session_ids)
    row = models.Payment.objects.filter(
        clause,
        type=models.PAYMENT_TYPE_PAYMENT,
        amount__gt=ZERO,
        status__in=DRAWER_STATUSES,
        posted_at__date=day,
    ).aggregate(total=Sum("amount"), n=Count("id"))
    return (row["total"] or ZERO, row["n"] or 0)


def counter_row(session: Any) -> dict[str, Any]:
    """One row of `3·1`, in the member names the screen lane published.

    ⚠ **THE FIELD NAMES ARE `07-frontend/src/api/counterEndpoints.ts`'s AND NOT
    THIS LANE'S.** That file declares `CounterRow` and the six Counter screens
    are already built against it. Two lanes naming one fact two ways is the
    defect this repo files most, and the tie-break is simple: the side that
    wrote its contract down first and said so.

    ⚠ **B14 RULE 31 — NO DATABASE ID IS THE VISIBLE VALUE OF A FIELD.** `code`
    is what a clerk reads and what the address carries — the STORED code since
    `DEF-PAY-10140`, so it is unique per tenant. `id` is served beside it and is
    never rendered.
    """
    counted = _counted_countable(session)
    return {
        "id": str(session.pk),
        "code": counter_code(session),
        "owner_name": _person(session.owner),
        "service_centre_name": getattr(session.service_centre, "name", None),
        "opened_at": session.opened_at.isoformat() if session.opened_at else None,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "close_kind": session.close_kind,
        # §3.2's two columns. `P2.20` is a parallel lane's migration; until it
        # lands these are NULL, which is the truth rather than a placeholder —
        # nothing can declare a count without somewhere to record who did.
        "declared_at": _iso(getattr(session, "declared_at", None)),
        "declared_by_name": _person(getattr(session, "declared_by", None)),
        "not_counted": _row_is_not_counted(session),
        "payment_count": None,
        "taken_total": None,
        "counted_total": counted,
        "difference": None if session.difference is None else str(_q(session.difference)),
        "currency": session.currency,
    }


def _iso(moment: Any) -> str | None:
    return moment.isoformat() if moment is not None else None


def _counted_countable(session: Any) -> str | None:
    """What somebody counted, across the COUNTABLE methods — `3·1`'s ④ column.

    ⚠ **`None` IS THE FINDING AND NOT A GAP.** p052 ④: *"Counted · empty is the
    finding — the payments are safe, the drawer figure is missing"*. A forced
    close has no count and the column is EMPTY, which is what sends a
    supervisor to the Declare screen; a zero would say somebody counted an
    empty drawer.
    """
    stored = session.counted_totals
    if not stored:
        return None
    total = ZERO
    for value in stored.values():
        total += _money(value, "a counted figure")
    return str(_q(total))


def counter_rows(sessions: Any) -> list[dict[str, Any]]:
    """A PAGE of rows, with every till's takings read in ONE query.

    ⚠ **`payment_count` AND `taken_total` ARE THE REASON THIS TAKES A PAGE AND
    NOT A ROW.** Asked per row they are one query each — fifty tills, fifty
    round trips, which is the shape `GET /payments` already records in its own
    comment (*"a page costs a page"*). Here they are one `GROUP BY` over the
    page's tills, and a till that took nothing is absent from the result and
    reads as `0`, which is true.
    """
    page = list(sessions)
    rows = [counter_row(session) for session in page]
    if not page:
        return rows
    tenant_id = page[0].tenant_id
    batch_to_session = dict(
        bankrec.DepositBatch.objects.filter(
            tenant_id=tenant_id, session_id__in=[session.pk for session in page]
        ).values_list("pk", "session_id")
    )
    takings: dict[Any, tuple[Decimal, int]] = {}
    if batch_to_session:
        for row in (
            models.Payment.objects.filter(
                tenant_id=tenant_id,
                deposit_batch_id__in=list(batch_to_session),
                type=models.PAYMENT_TYPE_PAYMENT,
                amount__gt=ZERO,
                status__in=DRAWER_STATUSES,
            )
            .values("deposit_batch_id")
            .annotate(amount=Sum("amount"), n=Count("id"))
        ):
            session_id = batch_to_session[row["deposit_batch_id"]]
            amount, count = takings.get(session_id, (ZERO, 0))
            takings[session_id] = (amount + (row["amount"] or ZERO), count + row["n"])
    if _payments_name_their_till():  # `P2.4` — read TOGETHER, never instead
        for row in (
            models.Payment.objects.filter(
                tenant_id=tenant_id,
                counter_session_id__in=[session.pk for session in page],
                deposit_batch_id__isnull=True,
                type=models.PAYMENT_TYPE_PAYMENT,
                amount__gt=ZERO,
                status__in=DRAWER_STATUSES,
            )
            .values("counter_session_id")
            .annotate(amount=Sum("amount"), n=Count("id"))
        ):
            amount, count = takings.get(row["counter_session_id"], (ZERO, 0))
            takings[row["counter_session_id"]] = (
                amount + (row["amount"] or ZERO),
                count + row["n"],
            )
    for session, row in zip(page, rows):
        amount, count = takings.get(session.pk, (ZERO, 0))
        row["taken_total"] = str(_q(amount))
        row["payment_count"] = count
    return rows


def counter_detail(session_id: Any) -> dict[str, Any]:
    """`GET /counters/{ref}` — `3·2 My counter`, with the running split by method."""
    session = _session_by_ref(session_id)
    row = counter_rows([session])[0]
    split = running_split(session)
    row["opening_float"] = split["opening_float"]
    row["methods"] = split["by_method"]
    row["countable_expected"] = split["countable_expected"]
    row["note"] = session.note
    row["closed_by_name"] = _person(session.closed_by)
    row["batches"] = [
        {
            "id": str(batch.pk),
            "code": batch.code,
            "method": getattr(batch.method, "code", None),
            "recorded_total": str(_q(batch.recorded_total or ZERO)),
            "status": batch.status,
        }
        for batch in bankrec.DepositBatch.objects.filter(
            tenant_id=session.tenant_id, session_id=session.pk
        )
        .select_related("method")
        .order_by("code")
    ]
    return row


def _row_is_not_counted(session: Any) -> bool:
    """The SAME rule as `not_counted_q()`, asked of one row that is in hand.

    ⚠ It is derived FROM the Q object rather than re-typed, so the two can not
    drift — which is the whole reason `not_counted_q()` exists. A second
    spelling here would be the fourth reader quietly disagreeing with the other
    three.
    """
    if session.close_kind != models.COUNTER_CLOSE_FORCED:
        return False
    return getattr(session, "declared_at", None) is None


def counter_code(session: Any) -> str:
    """`CTR-260921-DW` — what a clerk calls their till, drawn on every screen.

    ⚠ **THE STORED CODE WINS, AND EVERY READER COMES THROUGH HERE**
    (`DEF-PAY-10140`). A person's till carries the code `open_counter` gave it
    — `CTR-261013-BS-2` for the second till on that base — and that is what the
    list row, the detail, the address and every door print. This used to be
    composed on each read, which made two tills by one person on one day the
    SAME label; the composition below now runs only for a row with nothing
    stored (a system till), exactly as it always did.
    """
    stored = getattr(session, "code", None)
    if stored:
        return stored
    return composed_code_base(session)


def composed_code_base(session: Any, *, owner: Any = None) -> str:
    """The BASE a till's code is built on: `CTR-{yymmdd}-{initials}`.

    The day is the UTC date of `opened_at` — what every row read back from the
    database has always been labelled by, so no code printed before
    `payments/0050` moves. `payments/0050` freezes a copy of this rule for its
    backfill, and a test asserts the two agree.
    """
    moment = session.opened_at
    if moment is not None and getattr(moment, "tzinfo", None) is not None:
        moment = moment.astimezone(UTC)
    day = moment.date().strftime("%y%m%d") if moment else "------"
    owner = owner if owner is not None else session.owner
    initials = ""
    if owner is not None:
        # `full_name` is the one name column `identity.User` has. `D. Whitfield`
        # and `Dana Whitfield` both give `DW`; a single-word name gives its
        # first letter, and an empty one falls back to the email.
        parts = [word for word in (getattr(owner, "full_name", "") or "").split() if word]
        initials = "".join(word[0] for word in parts[:2]).upper()
        if not initials:
            initials = (getattr(owner, "email", "") or "")[:2].upper()
    return f"CTR-{day}-{initials or 'SYS'}"


def _person(owner: Any) -> str | None:
    """The name a screen shows beside a till.

    ⚠ `identity.User` carries **`full_name`**, not `first_name`/`last_name` —
    a first draft of this module assumed the Django default and every counter
    row would have come back blank with `tsc` and the suite green, which is
    the absence-is-invisible shape this repo files most.
    """
    if owner is None:
        return None
    return (getattr(owner, "full_name", "") or "").strip() or getattr(owner, "email", None)


# ════════════════════════════════════════════════════════════════════════════
# `P2.23` · A HAND TENDER NEEDS AN OPEN TILL — ⚠ NEW BEHAVIOUR, NOT DRAWN
# ════════════════════════════════════════════════════════════════════════════
def open_counter_for(actor: Any) -> Any:
    """This person's open till, or None. One query, one definition."""
    owner_id = core_audit.actor_user_id(actor)
    if owner_id is None:
        return None
    return (
        tills.CounterSession.objects.filter(
            tenant_id=_tenant_id(), owner_id=owner_id, closed_at__isnull=True
        )
        .order_by("-opened_at")
        .first()
    )


def assert_till_open_for_tender(actor: Any, method_code: str | None) -> Any:
    """Refuse a hand-recorded `cash`, `check` or `money_order` with no open till.

    **PO ruling 2026-09-23 §3.4, verbatim:** *"(a) Refuse it. \"Start your
    counter first.\" One press, then take the money. It is the only option
    where every cash dollar belongs to somebody"*.

    Returns the open till (so the caller can attach it) or raises.

    ⚠ **THE OTHER FOUR TENDERS ARE UNTOUCHED, AND A CARD IS AMONG THEM ON
    PURPOSE.** `ach`, `card`, `wire` and `lockbox` bank under phase 0's system
    till. A card swiped at a window looks like counter money and is not
    countable money: the Close screen counts what is in a drawer, and a card
    total typed back at the system's own figure makes the reconciliation
    worthless.

    ⚠ **`payments.counter_session_id` STAYS NULLABLE AND THIS IS A SERVICE
    RULE, NOT A COLUMN CONSTRAINT.** A `NOT NULL` would refuse every ACH, card,
    wire and lockbox row in the product — `P2.4` does not move.

    ⚠ **NOT DECIDED, AND DELIBERATELY NOT BUILT: A CHEQUE THAT ARRIVES IN THE
    POST.** The case shown to the PO was cash at a counter. A back-office clerk
    keying a mailed cheque never sits at a till, and this rule refuses them.
    A silent exception would be this lane widening a ruling nobody gave, so
    there is none — the question is `OQ-PAY-12601` and it is OPEN. The refusal
    below is therefore KNOWN to be wider than the case that was ruled on, and
    that is stated rather than papered over.
    """
    code = str(method_code).strip().lower() if method_code else ""
    if code not in HAND_TENDERS:
        return None
    till = open_counter_for(actor)
    if till is not None:
        return till
    raise PaymentRuleError(
        "Start your counter first. Money that passes through your hands — cash, cheques and "
        "money orders — belongs to a till, so the drawer can be counted at the end of the "
        "shift and every dollar belongs to somebody. It is one press, and then you can take "
        "the money.",
        br_ref="BR-PAY-1186",
    )

# ── Trace ──────────────────────────────────────────────
# Change:   CR-135-BRC07 — the payments blueprint's phase 0, tasks `P0.3`,
#           `P0.4` and `P0.5`. `05-prototype/06 Payments Page Blueprint.pdf`
#           p012, and it is on the DEFAULT branch
#           (`claude/confirm-understanding-3ktufc`), not on any working one.
#           AMENDED 2026-09-23 · CR-136-BRC07 `P2.20` — `declared_at`,
#           `declared_by`, `ck_counter_sessions_declared_together` and
#           `NOT_COUNTED`, from the PO ruling of that date. NOT in the drawing:
#           the blueprint's phase 2 has 19 tasks and this is the 20th.
# Story:    no story — phase 0 SHIPS NO SCREEN. The six Counter screens that
#           read this table are `3·1 Counters`, `3·2 My counter` and
#           `3·3a–d Start / Close / Force close / Declare`, all phase 2.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE — migration
#           `payments/0032`) · hard rule 2 (a NEW money column declares FOUR
#           decimals; PO re-sign 2026-08-22 — see `opening_float`) · hard rule
#           7 (a forced close is a money action and writes `audit_log`) ·
#           BR-SHL-025 (server-side enforcement is THE enforcement) ·
#           BR-PAY-1160 (this table)
# Tests:    06-backend/tests/test_cr135_p0_foundations.py (the constraint and
#           its easy-to-miss half) ·
#           06-backend/tests/test_cr135_p0_rls_pg.py (isolation, on PostgreSQL) ·
#           06-backend/tests/test_cr136_p2_counter_columns.py (`P2.20`'s
#           constraint and `NOT_COUNTED`) ·
#           10-scripts/cr136_p2_20_declared_readback.py (the same guarantee on
#           PostgreSQL 16, where a CHECK's NULL behaviour is real)
#           ⚠ This line named `test_cr135_p0_counter_sessions.py` until
#           2026-09-22 and that file has never existed — the cases were merged
#           into `…_foundations.py` an hour after this header was written and
#           nothing moved the citation (`DEF-PAY-6205`). `G116` was RED on it.
# Impacts:  apps/payments/migrations/0035_cr136_p2_4_p2_5_p2_20_the_till_on_a_payment.py
#           (`P2.20`'s two columns and their CHECK) ·
#           apps/payments/migrations/0031_cr135_p0_3_p0_4_counter_sessions.py
#           (this schema) · 0032_rls_cr135_p0_5_counter_sessions.py (the
#           guarantees this class cannot give) · apps/payments/apps.py
#           (`ready()` registers this module)
# ───────────────────────────────────────────────────────
"""payments — `counter_sessions`: **one person's shift at one till.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). Migration
ordering and RLS are CLAUDE.md 🔒 sensitive paths, so there is a row in
`12-governance/09-human-review-ledger.md` saying in plain English, with a
figure, what would be put to the Product Owner. It may never reach lifecycle
RATIFIED without a recorded human sign-off.

╔══════════════════════════════════════════════════════════════════════════╗
║  PHASE 0 BUILDS THE TABLE AND NOT ONE SCREEN, ONE ENDPOINT OR ONE        ║
║  SERVICE. PO ruling 2026-09-22: *"go as per phase 0 ; we are going to    ║
║  implement all phases one by one so fcus on current one."*               ║
╚══════════════════════════════════════════════════════════════════════════╝

WHAT A ROW IS
-------------
A till opens when a clerk starts a shift and closes when they count the drawer.
The blueprint's worked shift, which is also journey `J-PAY-counter-shift`:
**08:55 open with a $200 float · seventeen payments in cash, cheque and card ·
17:30 count · close.**

A COUNTER IS NOT A LOCATION, WHICH IS WHY THE FLOAT IS HERE
------------------------------------------------------------
p101, and it says it came out of the author being challenged on a first answer:
*"A counter is not a location — it is a till at one. One centre can have three
windows, each with its own drawer. So the float belongs to the counter, which
is payments' own object, and the centre stays a portal record."*
`tenancy.ServiceCentre` is published content — *"where a customer can walk
in"* — so this row NAMES a centre and puts no operational field on it.

⚠ THE FLOAT IS `NUMERIC(18,4)` AND THE DRAWING SAYS `NUMERIC(18,6)`
--------------------------------------------------------------------
`P0.3`'s own words are *"opening float at NUMERIC(18,6)"*, and **the drawing is
not followed here.** CLAUDE.md hard rule 2, PO re-sign 2026-08-22, verbatim:
*"We already confirmed this - MOney 4 decimal, percentage 6 decimal , display
both 2 decimal"*. Existing `18,6` columns stay lawful containers — `payments.
amount` is one — but **the rule governs what NEW columns declare**, and this
column is new. So it is `core.money_fields.money_field()`, which is the one
place that number is written down.

This is not a lane overruling a drawing on its own authority. It was put to the
Product Owner with the figure and they were told the signed rule wins; the
divergence is recorded in the decision log of 2026-09-22 and in `B14`'s terms
it is rule 38's shape — where a drawing and a signed rule disagree about
CONSTRUCTION, the rule wins, because the alternative changes one money column
on one screen's authority.

WHO MAY CLOSE A TILL, AND WHY THERE ARE TWO KINDS
--------------------------------------------------
**PO ruling 2026-09-22, verbatim: *"(b) A System Admin can close it, recorded
as a forced close"*.** The case put to them: Dana opens a till on Monday at
08:00, takes **$1,240 in cheques**, goes home at 17:00 without closing it, and
is off sick on Tuesday. Under *only Dana may close it* the one-open-till-per-
person index below means **Dana cannot work when they return**. Under *the till
closes itself overnight with no count* there is a hole in the money trail, and
that option was declined.

So `close_kind` holds `counted` or `forced`, and `closed_by` records who
actually did it — **which on a forced close is not the owner.** The two people
stay distinguishable for ever, which is the point: somebody other than the
owner has counted, or declined to count, a drawer the owner is accountable for.

⚠ **TWO RULES ATTACH TO THE FORCED CLOSE AND NEITHER IS BUILT IN THIS PHASE,
DELIBERATELY.** A forced close is a money action, so CLAUDE.md hard rule 7
applies and it writes `audit_log`; and who may do it is `@require_role(
SYSTEM_ADMIN)` **at the service**, never on a screen — `BR-SHL-025`, a button
hidden from a Billing Clerk is not a guarantee. There is no close service in
phase 0 to carry either. **The hold has a test that fires when it expires**
(`test_cr135_p0_foundations.py::
test_p0_3_the_force_close_role_check_has_no_service_to_sit_on_yet`), because
hard-won law 2's mirror
is a hold nobody is keeping and it cost the customer portal six of its eight
front doors.

WHAT `difference` IS, AND WHY IT IS STORED RATHER THAN DERIVED
---------------------------------------------------------------
What the drawer held minus what the system says it should have held, at the
moment of the count. It is a SNAPSHOT of a comparison, and re-deriving it later
would answer a different question — payments move, are reversed and are
reallocated afterwards. The same reasoning `payments` already applies to a
locked-at-issue figure.

⚠ `counted_totals` HOLDS MONEY IN JSON AND THEREFORE HOLDS STRINGS
-------------------------------------------------------------------
One counted figure per countable method, keyed by `payment_methods.id`:

    {"8f3c…": "1240.0000", "2b71…": "318.5000"}

**The values are strings and hard rule 2 is why** — *"never float/cents"*. A
JSON number is a double in every serialiser this stack uses, so `1240.00`
round-trips as `1240.0000000000001` sooner or later, on a figure whose whole
job is to be compared with a drawer. `DjangoJSONEncoder` writes a `Decimal` as
a string for exactly this reason and it is the encoder this column declares.

⚠ **CARD IS NOT COUNTABLE AND THE SHAPE SAYS SO BY OMISSION.** p056: *"you
cannot count a card total in a drawer so the screen does not pretend"*. A
method with no key in this map was not counted; a method with a key was. That
distinction is free in a map and would have to be invented in a column per
method.
"""

from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.payments.models import (
    COUNTER_CLOSE_FORCED,
    COUNTER_CLOSE_KINDS,
    COUNTER_CLOSE_KINDS_BY_A_PERSON,
    COUNTER_CLOSE_SYSTEM,
)
from core.dbfields import uuid7_pk
from core.money_fields import money_field

#: ── `NOT COUNTED`, WRITTEN ONCE (CR-136-BRC07 `P2.20`, B14 rule 43) ────────
#: **A till that was sealed and never counted.** PO ruling 2026-09-23 names
#: this as a derived state with FOUR readers and says in terms that it must be
#: written once: screen `3·1 Counters`' list, that screen's filter chip,
#: `P2.11`'s notice to the supervisor, and phase 2's own done-when (*"a
#: supervisor can see the three tills nobody counted"*).
#:
#: `close_kind = 'forced' AND declared_at IS NULL`, and it needs no third term
#: because `ck_counter_sessions_declared_together` makes every declared row a
#: forced one. Declaring is what takes a till OFF this list, which is the
#: ruling's *"It leaves the Not counted list. Nothing is erased"*.
#:
#: ⚠ **NOTHING IMPORTS THIS YET AND THAT IS STATED RATHER THAN LEFT TO BE
#: NOTICED (hard-won law 2 — built is not wired).** Its four readers are
#: `P2.2`, `P2.3`, `P2.6` and `P2.11`, none of which is built on 2026-09-23.
#: It is written here, beside the columns it is made of, because the
#: alternative is four lanes each spelling it out and one of them spelling it
#: differently. **The front end is not a fifth speller:** the filter chip sends
#: a query parameter and the server answers with THIS expression — a
#: TypeScript copy of the rule would be the two-places-that-can-disagree shape
#: with a language boundary in the middle.
NOT_COUNTED = models.Q(close_kind=COUNTER_CLOSE_FORCED, declared_at__isnull=True)


class CounterSession(models.Model):
    """One till, from the moment it opens to the moment somebody seals it.

    Written by nothing yet — phase 0 ships no service. `payments/0031` creates
    the table, `payments/0032` gives it RLS and the phase 2 Counter screens are
    what fill it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    # ── whose till, and where ──────────────────────────────────────────────
    #: The person accountable for the drawer. `uq_counter_sessions_open_owner`
    #: below is keyed on this and refuses them a second OPEN one.
    #:
    #: ⚠ **NULLABLE SINCE `P0.6`, AND NULL MEANS *NOBODY SAT AT THIS TILL*.**
    #: `ck_counter_sessions_system_is_nobodys` below makes that exact and
    #: two-way: `owner`, `service_centre` and `closed_by` are all NULL if and
    #: only if `close_kind = 'system'`. A person's till still cannot be written
    #: without an owner — the constraint refuses it by name.
    owner = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="owner_id",
        related_name="counter_sessions",
        null=True,
        blank=True,
    )
    #: The walk-in counter this till is at. A real FK rather than a deferred
    #: uuid: `counter_receipts.method_id` already carries a payments → tenancy
    #: edge and this is the same boundary, so a till cannot name a centre that
    #: was deleted out from under it. It is NOT in B2 §2's reviewed interface
    #: set, which is why the review-ledger row names it.
    #: ⚠ **NULLABLE SINCE `P0.6`** — an ACH file arrives at no counter. Moves
    #: with `owner`; see `ck_counter_sessions_system_is_nobodys`.
    service_centre = models.ForeignKey(
        "tenancy.ServiceCentre",
        on_delete=models.PROTECT,
        db_column="service_centre_id",
        related_name="counter_sessions",
        null=True,
        blank=True,
    )
    #: ── `P0.6` · WHICH BANKING DAY A SYSTEM TILL STANDS FOR ────────────────
    #: NULL on a person's till, and NOT NULL on a system one. A human till is
    #: bounded by the shift its owner works; a system till is bounded by the
    #: DAY, because `cut_deposit_batches` is called for a day and must find the
    #: same session again when it is re-run for that day (hard rule 6 — the cut
    #: is idempotent and a second call cuts nothing). `uq_counter_sessions_
    #: system_day` is what makes two concurrent cuts of one day share one till
    #: rather than each making its own.
    #:
    #: It is a separate column rather than `opened_at::date` deliberately: a
    #: future lane setting `opened_at` to the moment of the cut would break the
    #: idempotency silently, which is the failure shape this repo files most.
    system_day = models.DateField(null=True, blank=True)
    #: ── `CR-186-BRC10` · WHICH PROVIDER OR CHANNEL THIS SYSTEM TILL BANKS ──
    #: PO 2026-10-21, *"this is correct"* to the table that gave Invoice Cloud,
    #: Paymentus and the lockbox file a batch EACH per day (decision log
    #: *"DEPOSIT BATCHES: ONE BATCH ID PER TILL OR PER PROVIDER, PER DAY"*). A
    #: system till is now one per (day, channel) — `invoice_cloud`,
    #: `paymentus`, `lockbox`, `office` — and its one batch holds every tender.
    #: NULL on every person's till and on the system tills opened before this
    #: change (one per day for everybody), which keep their meaning untouched.
    channel = models.TextField(null=True, blank=True)

    # ── opening ────────────────────────────────────────────────────────────
    #: ⚠ **FOUR DECIMAL PLACES, WHERE THE DRAWING SAYS SIX.** The argument is
    #: in the module docstring; the short form is CLAUDE.md hard rule 2 — a NEW
    #: money column declares four, and this one is new.
    opening_float = money_field()
    #: Hard rule 2's other half. Money is never a bare number in this schema.
    currency = models.CharField(max_length=3, default="USD")
    opened_at = models.DateTimeField()

    # ── closing — all four move together or none of them do ────────────────
    closed_at = models.DateTimeField(null=True, blank=True)
    #: **Who actually sealed it**, which on a forced close is not `owner`.
    closed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="closed_by",
        related_name="+",
        null=True,
        blank=True,
    )
    #: `counted` or `forced` — see `COUNTER_CLOSE_KINDS` and the PO ruling in
    #: the module docstring.
    close_kind = models.TextField(null=True, blank=True)
    #: `{payment_method_id: "1240.0000"}`. Strings, not JSON numbers — hard
    #: rule 2, and the module docstring says why at length.
    counted_totals = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    #: Counted minus expected, as it stood at the count. Positive is over.
    difference = money_field(null=True, blank=True)
    #: Required by the screen only when `difference` is not zero (p056). That
    #: is a SERVICE rule and phase 2's to enforce: a database that demanded it
    #: could not record a forced close, where there is no count to explain.
    note = models.TextField(null=True, blank=True)

    # ── the LATE count, which sits BESIDE the forced close (CR-136 `P2.20`) ─
    #: **When somebody finally counted a drawer that was force-closed without a
    #: count, and who.** PO ruling 2026-09-23, verbatim: *"(a) Keep it as a
    #: forced close and add the late count beside it… The row reads:
    #: force-closed Monday by the supervisor, declared Tuesday by Dana, $12
    #: short. It leaves the Not counted list. Nothing is erased"*.
    #:
    #: ⚠ **BESIDE, NOT OVER. `close_kind` DOES NOT MOVE and there is no fourth
    #: value.** Both rejected options are on the record because the difference
    #: is the whole point: changing the row to `counted` would make it read
    #: afterwards as though Dana closed it herself, **erasing the fact that
    #: nobody counted it on the day** — the exact outcome the 2026-09-22
    #: forced-close ruling exists to prevent; and a fourth `close_kind` of
    #: `declared` would move `ck_counter_sessions_close_kind`,
    #: `COUNTER_CLOSE_KINDS`, `COUNTER_CLOSE_KINDS_BY_A_PERSON` and three
    #: screens to record a fact that is not a way of SEALING a till at all.
    #:
    #: The count itself needs no new column: `counted_totals`, `difference`
    #: and `note` are NULL on a forced close **precisely because nobody
    #: counted**, and declaring is what fills them.
    declared_at = models.DateTimeField(null=True, blank=True)
    #: Who did the late count. Same shape as `closed_by` one field up —
    #: `PROTECT` so a person who counted a drawer cannot be deleted out from
    #: under the record, `related_name="+"` because a user's reverse accessor
    #: for *tills I once counted late* is not a question any screen asks.
    #:
    #: ⚠ **NOT necessarily `owner` and NOT necessarily `closed_by`.** The
    #: worked case has three roles on one row: Dana owns the drawer, a
    #: supervisor force-closed it, and Dana declares it the next morning — but
    #: nothing says the declarer is the owner, and a second supervisor
    #: counting the bag is the same row with a third name in it.
    declared_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="declared_by",
        related_name="+",
        null=True,
        blank=True,
    )

    # ── `DEF-PAY-10140` · WHAT A CLERK CALLS THIS TILL, STORED ───────────────
    #: `CTR-261013-BS`, and `CTR-261013-BS-2` for a second till on that base.
    #: Decision log 2026-10-14 *"G1–G4 APPROVED"* item 2: the code is STORED at
    #: open and unique per tenant. It was composed on every read until then, so
    #: the same person opening twice in a day produced ONE label for TWO tills
    #: and every door that named the second one was refused.
    #:
    #: ⚠ **NULLABLE, AND NULL MEANS A SYSTEM TILL** (`system_day` set, nobody
    #: sat at it). `counters.counter_code()` composes a code for those exactly as
    #: before; a person's till always carries one from `payments/0050` on.
    #: Written ONCE, by `counters.open_counter`; nothing updates it, so a rename
    #: of the owner never moves the label printed on the morning's slips.
    code = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "counter_sessions"
        constraints = [
            # ── P0.4, and the outcome is stated as a contrast on purpose ────
            # *"The database refuses a second open till — not a service check
            # that a second caller can skip."* A partial unique index is what
            # makes that sentence true when two terminals race, which a
            # `SELECT … then INSERT` in a service cannot.
            #
            # ⚠ **AND IT PERMITS A SECOND CLOSED ONE**, which `P0.15` names as
            # the easy-to-miss half: without the `WHERE`, a clerk could open a
            # till exactly once in the life of the utility.
            models.UniqueConstraint(
                fields=["tenant", "owner"],
                condition=models.Q(closed_at__isnull=True),
                name="uq_counter_sessions_open_owner",
            ),
            models.CheckConstraint(
                condition=models.Q(close_kind__in=COUNTER_CLOSE_KINDS)
                | models.Q(close_kind__isnull=True),
                name="ck_counter_sessions_close_kind",
            ),
            # ⚠ **THE THREE CLOSING FACTS MOVE TOGETHER, AND THIS IS THE PO's
            # RULING GIVEN TEETH.** A row with `closed_at` set and `close_kind`
            # null is a till that was sealed with no record of HOW — which is
            # precisely the forced close becoming indistinguishable from a
            # normal one, the thing the ruling exists to prevent. A row with
            # `close_kind` set and no `closed_at` is a till that is open and
            # closed at once, and the unique index above would then let a
            # second open till through.
            #
            # ⚠ **WIDENED BY `P0.6` FOR THE SYSTEM TILL, AND THE INTENT IS
            # UNCHANGED.** The rule the PO's ruling needs is *a sealed till
            # always records HOW it was sealed* — `close_kind`. The original
            # spelling also demanded a `closed_by`, which a system till cannot
            # have: nobody sealed it. So the third branch below permits a NULL
            # `closed_by` **only** when `close_kind = 'system'`, and
            # `ck_counter_sessions_system_is_nobodys` then forces the rest of
            # that row to be nobody's too. A forced close is still
            # distinguishable from a counted one and both still name a person.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        closed_at__isnull=True,
                        closed_by__isnull=True,
                        close_kind__isnull=True,
                    )
                    | models.Q(
                        closed_at__isnull=False,
                        closed_by__isnull=False,
                        close_kind__isnull=False,
                    )
                    | (
                        # ⚠ **`close_kind IS NOT NULL` FIRST, AND WITHOUT IT
                        # THIS WHOLE CONSTRAINT WAS OFF (`DEF-PAY-6207`).**
                        # A CHECK refuses a row only when its expression is
                        # FALSE and **PASSES when it is NULL**. With
                        # `close_kind` NULL this branch read `NULL = 'system'`
                        # → NULL, so the chain became `FALSE OR FALSE OR NULL`
                        # = NULL and a till sealed with **no record of how or
                        # by whom** was accepted — the exact outcome the PO's
                        # forced-close ruling exists to prevent.
                        models.Q(close_kind__isnull=False)
                        & models.Q(
                            closed_at__isnull=False,
                            closed_by__isnull=True,
                            close_kind=COUNTER_CLOSE_SYSTEM,
                        )
                    )
                ),
                name="ck_counter_sessions_closed_together",
            ),
            # ── `P0.6` · A SYSTEM TILL IS NOBODY'S, IN EVERY COLUMN ─────────
            # Two-way, and both directions matter. Left to right: a till marked
            # `system` may not name a person anywhere or carry a float, or the
            # *"a supervisor can see the three tills nobody counted"* screen
            # starts listing drawers no human was ever at. Right to left: a
            # till with no owner may not pretend to be a person's, so nothing
            # can write an ownerless `counted` session and lose who is
            # accountable for a drawer.
            models.CheckConstraint(
                condition=(
                    # ⚠ **SAME `DEF-PAY-6207` FAULT, AND THE FILED ROW DOES NOT
                    # NAME THIS ONE — IT WAS FOUND BY CHECKING THE OTHER
                    # BRANCHES.** With `close_kind` NULL this branch was NULL
                    # too, and on a row carrying a `system_day` the second
                    # branch is FALSE, so `NULL OR FALSE` = NULL accepted an
                    # **OPEN system till**: `closed_at` NULL, so it answers
                    # `ix_counter_sessions_open` and appears on the *"which
                    # tills are open"* screen — a drawer a supervisor would
                    # chase and nobody ever sat at.
                    (
                        models.Q(close_kind__isnull=False)
                        & models.Q(
                            close_kind=COUNTER_CLOSE_SYSTEM,
                            owner__isnull=True,
                            service_centre__isnull=True,
                            closed_by__isnull=True,
                            system_day__isnull=False,
                            opening_float=0,
                        )
                    )
                    | (
                        # Spelled as a membership test and NOT as `~Q(...)`:
                        # `close_kind` is NULL on an open till, `NOT (NULL =
                        # 'system')` is NULL, and a CHECK that evaluates to
                        # NULL PASSES. A negation here would have let an
                        # ownerless OPEN till through — a check that cannot
                        # fail on the one row it was written for (law 7).
                        (
                            models.Q(close_kind__isnull=True)
                            | models.Q(close_kind__in=COUNTER_CLOSE_KINDS_BY_A_PERSON)
                        )
                        & models.Q(
                            owner__isnull=False,
                            service_centre__isnull=False,
                            system_day__isnull=True,
                        )
                    )
                ),
                name="ck_counter_sessions_system_is_nobodys",
            ),
            # ── `P2.20` · THE LATE COUNT, AS A CONSTRAINT ──────────────────
            # PO ruling 2026-09-23 names the shape as well as the fact: the
            # pairing *"is a CONSTRAINT, not a service check, for the same
            # reason `ck_counter_sessions_closed_together` is"*. Two facts,
            # one constraint, because they are one rule:
            #
            #   (a) `declared_at` and `declared_by` are both set or both NULL.
            #       Half a declaration is a count with nobody's name on it, or
            #       a name with no date — and the whole value of the ruling is
            #       that the row goes on saying WHO did WHAT and WHEN for ever.
            #   (b) a declaration requires `close_kind = 'forced'`. **A
            #       counted till has already been counted and a system till is
            #       nobody's**, so neither can be declared. A declared row is
            #       therefore always a forced close, which is what makes
            #       `Not counted` the single expression `NOT_COUNTED` below.
            #
            # ⚠ **EVERY BRANCH THAT COMPARES `close_kind` OPENS WITH
            # `close_kind IS NOT NULL` — `DEF-PAY-6207`, WHICH HAPPENED TWICE
            # IN THIS FILE.** A CHECK refuses a row only when its expression is
            # FALSE and **PASSES when it is NULL**. Written as plain
            # `close_kind = 'forced'`, the second branch would read NULL on
            # every OPEN till (`close_kind` is NULL until a till is sealed) and
            # `FALSE OR NULL` is NULL — so an open till could be handed a
            # `declared_at`, and the constraint that exists to stop exactly
            # that would accept it. Proved RED on PostgreSQL 16 before the
            # `IS NOT NULL` went in, by `10-scripts/
            # cr136_p2_20_declared_readback.py` section 2.
            models.CheckConstraint(
                condition=(
                    models.Q(declared_at__isnull=True, declared_by__isnull=True)
                    | (
                        models.Q(close_kind__isnull=False)
                        & models.Q(
                            declared_at__isnull=False,
                            declared_by__isnull=False,
                            close_kind=COUNTER_CLOSE_FORCED,
                        )
                    )
                ),
                name="ck_counter_sessions_declared_together",
            ),
            # A negative opening float is a drawer that starts owing money.
            # Same shape and same reason as `ck_counter_receipts_amount_
            # positive` one table along.
            models.CheckConstraint(
                condition=models.Q(opening_float__gte=0),
                name="ck_counter_sessions_float_not_negative",
            ),
            # ── `P0.6` · ONE SYSTEM TILL PER TENANT PER BANKING DAY ────────
            # `cut_deposit_batches(day=…)` is idempotent (hard rule 6) and that
            # now depends on a re-run finding the SAME system till. Two cuts
            # racing on one day would otherwise open two, and the day's ACH
            # money would land in two batches that each look complete.
            # A partial index rather than a service check, for the reason
            # `P0.4`'s outcome already states: *"not a service check that a
            # second caller can skip."*
            # ⚠ NARROWED 2026-10-21 (`CR-186-BRC10`, `payments/0051`) to the
            # system tills WITHOUT a channel — the ones opened before a
            # provider got a batch of its own. A channel's till is unique per
            # (day, channel) by the index below instead.
            models.UniqueConstraint(
                fields=["tenant", "system_day"],
                condition=models.Q(system_day__isnull=False, channel__isnull=True),
                name="uq_counter_sessions_system_day",
            ),
            models.UniqueConstraint(
                fields=["tenant", "system_day", "channel"],
                condition=models.Q(system_day__isnull=False, channel__isnull=False),
                name="uq_counter_sessions_system_day_channel",
            ),
            # A channel names WHERE money came from without a person, so only a
            # system till may carry one.
            models.CheckConstraint(
                condition=models.Q(channel__isnull=True) | models.Q(system_day__isnull=False),
                name="ck_counter_sessions_channel_is_system",
            ),
            # ── `DEF-PAY-10140` · ONE TILL PER CODE, PER TENANT ─────────────
            # The database, not the allocator, is what makes two terminals
            # pressing *Start counter* in one millisecond end with two codes:
            # the loser's INSERT dies here and `open_counter` retries inside a
            # SAVEPOINT (hard-won law 14). Per TENANT — another utility's
            # `CTR-261013-BS` is not a clash (hard rule 1).
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=models.Q(code__isnull=False),
                name="uq_counter_sessions_code",
            ),
        ]
        indexes = [
            # *"Which tills are open right now"* is `3·1 Counters`' default
            # view and the one question this table is asked on every page load.
            # Tenant first, as every index in this module is: RLS scopes every
            # read and the tenant is always known.
            models.Index(fields=["tenant", "closed_at"], name="ix_counter_sessions_open"),
            # A person's own shift history — `3·2 My counter`.
            models.Index(fields=["tenant", "owner", "-opened_at"], name="ix_counter_sessions_own"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug convenience
        state = "open" if self.closed_at is None else self.close_kind
        return f"counter session {self.pk} ({state})"


# ── `P2.11` · STILL OPEN — ONE EXPRESSION, AND IT IS NOT "NOT COUNTED" ──────
#
# ⚠ **THE TWO ARE DIFFERENT STATES AND THE PHASE NEEDS BOTH.** `CR-136-BRC07`
# §3.2 defines *Not counted* as `close_kind = 'forced' AND declared_at IS NULL`
# — a till somebody SEALED without a count — and rules it *"one derived
# expression with four readers"*: screen 3·1's list, its filter chip, `P2.11`'s
# notice and the phase's done-when. **This is the OTHER one**, and it is what
# `P2.11`'s notice actually fires on:
#
#   STILL OPEN   `closed_at IS NULL`                     nobody has sealed it
#   NOT COUNTED  `close_kind='forced' AND declared_at IS NULL`  sealed, uncounted
#
# **Why the notice is on this one and not on the other**, argued in the
# decision-log row of 2026-09-23 and summarised here because this is where a
# lane will look:
#
#   * The blueprint's task row (p017) names it: *"Notifications: **the unclosed
#     till**"*, and screen 3·1 (p051) renders exactly this state as the words
#     *"still open"* in its CLOSED column.
#   * §3.1 struck the midnight auto-close, so **a forced close by a System
#     Admin is now the ONLY way an unclosed till gets sealed** — and the notice
#     is what prompts it. A notice fired AFTER the force close would be telling
#     a supervisor about work they had just done.
#   * *Not counted* already has its three readers on 3·1 and its own message:
#     the blueprint's acts table (p059) says a force close is where *"the OWNER
#     is told"*. Two different people, two different moments.
#
# **System tills answer NO, and for free.** `reconciliation._system_session`
# creates them CLOSED, so `closed_at IS NULL` never matches one — its own
# docstring says that is *"what keeps it off the supervisor's screen"*. There
# is no exception list here and there must not be one.
STILL_OPEN = models.Q(closed_at__isnull=True)


def still_open(queryset):
    """Narrow a `CounterSession` queryset to the tills nobody has sealed.

    The caller supplies the tenant scoping (hard rule 1); this adds the one
    condition. `ix_counter_sessions_open` is the index behind it.
    """
    return queryset.filter(STILL_OPEN)

# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave D tasks 17–19 — *"decide what a move-in and move-out
#           ARE"* · *"build and number that record"* · *"seed one or two of
#           each"*, against the CR's own trace finding 5, verbatim: *"Transfer
#           and disconnect have tables and no number; **move-in and move-out
#           have NO RECORD AT ALL**"*, consequence *"A clerk cannot quote a
#           reference; nothing on a bill can point at the job that caused a
#           change."*
# Rules:    **BR-CUS-150** (each is a record and it captures the JOB, not its
#           effects) · **BR-CUS-151** (what it carries is PROVENANCE — who,
#           when, the effective date, the reads taken — and nothing that
#           already has an owner) · **BR-CUS-152** (append-only in spirit: a
#           correction is a new row, CLAUDE.md hard rule 4's posture) ·
#           **BR-CUS-153** (each flow gets its OWN series, as a stated
#           EXTENSION of OQ-427's ruling rather than a ruling of its own) ·
#           BR-TEN-035 (allocation inside the issuing transaction; gaps ok;
#           never reused; issued numbers never renumbered) · BR-TEN-043 (the
#           event date is an argument, never the wall clock) · BR-TEN-057 (the
#           `is_sample` tag rides the owning row) · BR-CUS-021 (readings travel
#           only through the metering event door) · BR-CUS-023 / BR-CUS-024
#           (the deposit is a LOOKUP and carry-forward mechanics are PROPOSED —
#           which is why there is no deposit column here; DEF-921 / OQ-510) ·
#           CLAUDE.md rule 1 (tenant scoping / RLS FORCE) · rule 7 (audit)
# Screens:  S19 (Move-In wizard) · S20 (Move-Out wizard) · the Accounts page's
#           Move-ins and Move-outs tabs (B18 §5.5 / §5.6)
# Questions: **OQ-510** (should S19/S20 OFFER a deposit election at all — it
#           needs BR-CUS-024's mechanics confirmed first) · OQ-429/430/431
#           (fixture fields nobody has stated) — none of them blocks this file.
# Tests:    06-backend/tests/test_cr039_wd_move_records.py
# Impacts:  apps/customers/services.py (`move_in` / `move_out` write the row
#           inside their own existing `atomic()`) · apps/customers/models.py
#           (imports this module at its foot so the model registers) ·
#           apps/customers/migrations/0030_cr039_wd_move_records.py ·
#           core/numbering.py (the two catalogue rows)
# ───────────────────────────────────────────────────────
"""CR-039 wave D tasks 17–19 — **a move-in and a move-out are RECORDS.**

PO ruling 2026-08-27, verbatim and in full: *"you cna keep them as records for
audit perpuses"*, answering *"what ARE a move-in and a move-out, as records?"*.

═══════════════════════════════════════════════════════════════════════════
1 · THE RULING DECIDES THE SHAPE, AND THE SHAPE IS "THE JOB, NOT ITS EFFECTS"
═══════════════════════════════════════════════════════════════════════════
*"For audit purposes"* is a requirement about **provenance**, and provenance is
what a wizard holds and then throws away. So this row records **that somebody
did the job, who they were, when, and on what terms** — and records nothing
that is already written elsewhere.

**What is deliberately NOT here, each with the row that already owns it:**

| Fact | Who owns it |
|---|---|
| the unit is now occupied / vacant | DERIVED from the account's status class (BR-MET-036) — there is no column to copy |
| the account's status, `opened_at`, `closed_at` | `accounts`, written by the same transaction |
| every reading the job captured | `meter_reads`, written through the BR-CUS-021 event door |
| the service agreements' start/end dates | `service_agreements` |

**A second copy of a fact that already has an owner is how two numbers come to
disagree** — the ruling says so in as many words, and `Transfer`'s own docstring
reached the same conclusion one table over (*"a stored `deposit_carried` would
read as money that moved on a path where nothing moved"*).

⚠ **`reads_committed` IS A COUNT, NOT A COPY.** How many readings *this job*
took is a fact about the JOB; the readings themselves are metering's. A reader
wanting the values follows the account and the date.

⚠ **`performed_by` / `performed_at` DUPLICATE THE AUDIT ROW, AND THAT IS
DELIBERATE.** `move_in` and `move_out` already write `account.moved_in` /
`account.closed` through `core.audit`, and hard rule 7 keeps them there whatever
this table does. The difference is reachability: `audit_log` is keyed by entity
and action and is not a list a clerk can filter, sort or quote a reference from.
The ruling asked for a RECORD, which is a thing with a number and a row on a
screen. Stated here rather than left to look like an oversight.

═══════════════════════════════════════════════════════════════════════════
2 · THE DEPOSIT ELECTION IS NOT A COLUMN, AND THE RULING NAMED IT
═══════════════════════════════════════════════════════════════════════════
⛔ The ruling's own enumeration reads *"the clerk, the moment, the effective
date, the reads taken, **the deposit election**"*, and calls that set *"exactly
the set of facts a wizard currently holds and then discards"*.

**Measured 2026-08-27, and the last item is not true: neither wizard holds a
deposit election.** `MoveInWizard` refuses step 4's three radios by name
(*"no deposit radios (BR-CUS-023/024): the amount is a lookup from the unbuilt
plan deposit schedule and carry-forward rides the `customer_accounts` linkage,
which does not exist"*), `MoveOutWizard` refuses step 3's disposition and refund
radios the same way, and `services.REFUSED_FIELDS` refuses `deposit_on_file` on
every door that edits an account. There is nothing to discard.

So a `deposit_carry_elected` column here would be **a slot nothing can fill** —
hard-won law 2 on data rather than on a prop, which is the shape DEF-837 took.
It is refused BY NAME instead of invented, `move_reads
.DEPOSIT_CARRY_ELECTION_HAS_NO_COLUMN` keeps pointing at *"the same boolean on
the move-in's record"* as the thing it wants, and the mismatch between the
ruling's sentence and the product is filed as **DEF-921** with the substance
routed to the PO as **OQ-510**. A signature covers only what was shown
(CLAUDE.md, PO 2026-08-11), and what was shown here was a list, not a column.

═══════════════════════════════════════════════════════════════════════════
3 · ONE TABLE, TWO KINDS — AND WHY NOT TWO TABLES
═══════════════════════════════════════════════════════════════════════════
A move-in and a move-out carry the SAME provenance set. Two tables would be two
copies of one shape that drift the first time either gains a column, and the two
tabs would then read two different serializers for one concept. `kind` is a
CHECK-constrained literal, so a third value cannot appear by accident.

⚠ **THEY ARE STILL TWO SERIES.** See §4 — one table is a storage decision and
the number is a customer-facing vocabulary decision, and they are not the same
question.

`from_account` is the one asymmetric column: a chained move-in is *"the next
occupant takes the unit the account named in the URL is leaving"* (11b §S19), so
the outgoing account is part of the job. **Today that link is returned in
`move_in`'s response as `moved_in_after_account_id` and stored NOWHERE** — it is
exactly the kind of fact this record exists to keep. A move-out has no
counterpart, so the column is NULL there and a CHECK does not force one.

═══════════════════════════════════════════════════════════════════════════
4 · THE NUMBER IS AN EXTENSION OF A RULING, NOT A RULING — AND ONE WORD
    REVERSES IT
═══════════════════════════════════════════════════════════════════════════
The PO ruled the record and **did not rule the number**; the decision log says
so explicitly (*"IT DOES NOT SETTLE D18's NUMBERING, and that is not a
quibble"*). What the same day's later ruling did was **kill the argument that
had blocked it**:

  · the transfer's format was ruled with a reason — *"it is one job spanning two
    accounts, and neither account number names it"* — and a move belongs to ONE
    account whose number already names it, so that reason did not carry;
  · then a DISCONNECT, which belongs to one account too, got its own series on
    *"it needs its own series"*.

**It cannot be true both that a one-account job needs no number of its own and
that a disconnect, a one-account job, needs one.** So the build extends the
ruling rather than resting on a reason the PO has just overturned — and flags it
as an extension, in the decision log, in `core/numbering.py` and here.
`MVI-{YY}-{0000}` and `MVO-{YY}-{0000}` are the BUILD's choice, so day one is
`MVI-26-0001` and `MVO-26-0001`.

**TWO series and not one shared `MV-`:** a clerk reading `MV-26-0004` back down
a phone could not say whether it was an arrival or a departure, and the two are
separate flows on separate tabs. The cost is honest — two counters instead of
one — and it is the cost of a number that says what it names.

⚠ **THE ALLOCATION FOLLOWS THE WAVE D POSTURE EXACTLY.** `_allocate_move_no`
allocates BY NAME inside the caller's transaction and, when the tenant has no
row, REPORTS `numbering_series_missing` and writes NULL rather than raising —
because a household must not be refused a move-in for a numbering gap, and
because a host provisioned before today has no row until it is re-seeded.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.customers import seams
from core.dbfields import uuid7_pk

# ═══════════════════════════════════════════════════════════════════════════
# THE KINDS — two literals, and a CHECK so a third cannot arrive by accident
# ═══════════════════════════════════════════════════════════════════════════
KIND_MOVE_IN = "move_in"
KIND_MOVE_OUT = "move_out"
KINDS: tuple[str, ...] = (KIND_MOVE_IN, KIND_MOVE_OUT)

#: The catalogue KEYS, one per kind. Not prefixes — the format a clerk reads out
#: is the catalogue's to hold and every tenant may change it on S8 (BR-TEN-035).
MOVE_IN_SERIES = "move_in"
MOVE_OUT_SERIES = "move_out"
SERIES_BY_KIND: dict[str, str] = {
    KIND_MOVE_IN: MOVE_IN_SERIES,
    KIND_MOVE_OUT: MOVE_OUT_SERIES,
}

#: `apps/metering/services._allocate_number`'s own code string, reused so a
#: reader who has met one stated absence in this product has met all of them.
NUMBERING_SERIES_MISSING = "numbering_series_missing"

#: The two sentences a clerk reads when the number is absent. They are per-kind
#: because *"a number series for moves"* is not a thing anybody configured — the
#: S8 row an admin has to go and look at is named `Move-in #` or `Move-out #`.
MOVE_NUMBER_UNAVAILABLE: dict[str, dict[str, Any]] = {
    KIND_MOVE_IN: {
        "code": NUMBERING_SERIES_MISSING,
        "series": MOVE_IN_SERIES,
        "detail": (
            "This move-in has no reference number yet. A number series for move-ins has not "
            "been set up, so nothing has been issued — the move-in itself completed and only "
            "its reference is missing."
        ),
    },
    KIND_MOVE_OUT: {
        "code": NUMBERING_SERIES_MISSING,
        "series": MOVE_OUT_SERIES,
        "detail": (
            "This move-out has no reference number yet. A number series for move-outs has not "
            "been set up, so nothing has been issued — the move-out itself completed and only "
            "its reference is missing."
        ),
    },
}


class MoveRecord(models.Model):
    """One move-in or one move-out, as the job that happened.

    ⚠ **MANAGED, unlike `Transfer` one file over, and that difference is not an
    inconsistency to tidy.** `transfers.Transfer` is `managed = False` because
    the lane that wrote it could not touch `apps/customers/models.py` and its
    DDL lives in raw SQL (migration 0021), with 0027 supplying state only.
    `disconnects.DisconnectCase` is an ordinary managed model in exactly this
    position — its own module, imported at the foot of `models.py` — and that is
    the pattern this follows, so the autodetector keeps model and table in step
    with no introspection test to maintain.

    ⛔ **NO STATUS, NO STEP, NO STATE MACHINE.** A `transfers` row exists while
    the job is IN FLIGHT and carries `step` and `state`; a move record is
    written by a flow that has already committed, in the same transaction, so
    there is no in-flight moment for it to describe. `move_reads
    .STEP_HAS_NO_STORE` stays exactly true and is NOT closed by this table —
    it asks for *"a move-in/move-out case row carrying step + state"*, which is
    a different thing than an audit record of a completed job, and B18 §5.5.2's
    own footnote rules the first one out (*"a move-in is short enough that the
    wizard is the record"*).

    ⛔ **NOTHING UPDATES A ROW OF THIS TABLE.** BR-CUS-152: a move-out that
    happened is a thing that happened, and correcting one is a NEW row — the
    posture CLAUDE.md hard rule 4 takes for every financial record. `updated_at`
    exists for parity with every other customers table and for the sample-data
    sweep; no service function writes it after the insert.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: BR-CUS-153. The reference a clerk quotes, allocated by
    #: `_allocate_move_no` INSIDE the flow's own transaction so a job never
    #: exists unnumbered even for the width of a transaction.
    #:
    #: ⚠ **OR ADOPTED FROM A ROW THAT RESERVED IT EARLIER, AND THERE ARE TWO
    #: OF THOSE NOW.** A parked wizard reserves (`CR-122-BRC06`) and, since
    #: `BR-CUS-1090`, so does the APPROVAL that raised the job
    #: (`move_in_jobs.move_no`). `record_move` prefers **draft → job → mint**,
    #: in that order, so the number a clerk has been quoting since the day they
    #: pressed Approve is the number the finished job is filed under. Minting a
    #: second one here is how one move-in comes to have two numbers, which is
    #: the cost `record_move`'s own comment spells out.
    #:
    #: ⚠ **NULL WHERE THE TENANT HAS NO SERIES ROW**, which is every host
    #: provisioned before 2026-08-27 until `manage.py seed_demo --tenant
    #: <subdomain>` runs — `_seed_number_series` is `get_or_create`. The reason
    #: is SERVED beside the row (`MOVE_NUMBER_UNAVAILABLE`), never a bare dash.
    move_no = models.TextField(null=True, blank=True)
    #: `move_in` | `move_out`, CHECK-constrained in the migration.
    kind = models.TextField()
    #: The account the job ACTED ON — for a move-in the NEW account it opened,
    #: for a move-out the one it closed. PROTECT, because deleting an account
    #: out from under its own audit record would defeat the point of keeping it.
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="+",
    )
    #: §3 — the OUTGOING account a chained move-in followed. NULL on a move-out
    #: and on any move-in that was not chained. **This is the fact `move_in`
    #: returns as `moved_in_after_account_id` and stores nowhere today.**
    from_account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="from_account_id",
        related_name="+",
        null=True,
        blank=True,
    )
    #: The BUSINESS date the clerk entered — `opened_at` for a move-in,
    #: `moved_out_on` for a move-out. BR-TEN-043: an input, never a wall clock,
    #: and it is what fills `{YY}` in the number.
    effective_on = models.DateField()
    #: WHO. NULL only where the actor carries no `identity.User` row (a system
    #: or seeded actor), which is a real state and is not read as "nobody".
    performed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="performed_by",
        null=True,
        blank=True,
    )
    #: WHEN the job was committed — the wall clock, deliberately, because this
    #: one IS about the moment somebody pressed the button. It is NOT the
    #: business date; `effective_on` is, and the two differ on a backdated move.
    performed_at = models.DateTimeField(default=timezone.now)
    #: HOW MANY readings this job committed through the BR-CUS-021 event door.
    #: A COUNT, never a copy — see the module docstring §1. `0` is a real answer
    #: (a meterless unit, or a clerk who captured none) and is distinguishable
    #: from the reads never having been offered, because the wizards always do.
    reads_committed = models.SmallIntegerField(default=0)
    #: `CR-094-BRC01` — **the service request this move was raised from**,
    #: `BR-CUS-080`'s CHILD half. NULL on every move a clerk starts from the
    #: account page, which is the ordinary case.
    #:
    #: ⚠ **IT IS FILLED BY THE WIZARD, NOT BY THE APPROVAL, AND THAT IS THE
    #: WHOLE OF `request_jobs` §3.** A move-in and a move-out have no queue row
    #: to raise: this table is the record of a move that HAS HAPPENED (see the
    #: class docstring — *"written by a flow that has already committed"*, and
    #: `BR-CUS-152`'s no-updates rule), and it carries the very account the job
    #: would create. So approving a move-in records the outcome and the money
    #: and creates nothing; `record_move` writes this column at the moment
    #: somebody actually does the job.
    #:
    #: **It replaces a weaker link rather than adding a second one.** The
    #: Move-ins tab finds the request today by matching `outcome_ref` against an
    #: ACCOUNT NUMBER (`move_reads._requests_by_account_no`), whose own docstring
    #: records that two vocabularies already disagree there. This is the id.
    request_id = models.UUIDField(null=True, blank=True)
    #: BR-TEN-057 — the sample-data tag on the owning row, so BR-TEN-061 can
    #: delete a demo estate on one predicate.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # ⚠ EXPLICIT, exactly as `disconnects.py`'s three models declare it. A
        # model defined outside `models.py` has no app to infer from, and
        # without this Django raises *"doesn't declare an explicit app_label"*
        # the moment the module is imported.
        app_label = "customers"
        db_table = "move_records"
        constraints = [
            # `kind` is a two-value vocabulary and the CHECK is what stops a
            # third arriving by a typo in a caller. `SERIES_BY_KIND` would
            # KeyError on one anyway — this makes the database say so too, at
            # the layer an import or a fixture can also reach.
            models.CheckConstraint(condition=Q(kind__in=KINDS), name="ck_move_record_kind"),
            # The shape `uq_customers_tenant_customer_no_ci` established and
            # `uq_disconnect_cases_tenant_case_no_ci` repeated eight days later:
            # per tenant, case-INSENSITIVE, and **only where a number exists**.
            # The partial predicate is what lets the column be NULL on a host
            # that has not been re-seeded — NULLs must not collide with each
            # other — and `LOWER(...)` is there because a clerk typing
            # `mvi-26-0001` means the row that reads `MVI-26-0001`, which is one
            # number to a human and two to a plain unique index.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("move_no"),
                condition=Q(move_no__isnull=False),
                name="uq_move_records_tenant_move_no_ci",
            ),
        ]
        indexes = [
            # `records_for_account` reads by account, newest first, and it reads
            # BOTH sides of the link — so the second index is not redundant with
            # the first: a chained move-in's outgoing account is only reachable
            # through `from_account_id`.
            models.Index(fields=["tenant", "account", "-performed_at"], name="ix_move_rec_account"),
            models.Index(fields=["tenant", "from_account"], name="ix_move_rec_from_account"),
            # `CR-094-BRC01` — *"what happened to this application"* read from
            # the JOB's side: given a request, find the move it became.
            models.Index(fields=["tenant", "request_id"], name="ix_move_records_request"),
        ]


def _allocate_move_no(
    kind: str, *, issue_date: Any = None
) -> tuple[str | None, dict[str, Any] | None]:
    """BR-TEN-035 allocation for a move record. **A missing series is REPORTED,
    never faked.**

    Returns `(number, absence)` — exactly one of them is not None, which is the
    shape `transfers._allocate_transfer_no` established so a caller cannot serve
    a number and a reason at the same time.

    ⚠ **CALL THIS INSIDE THE TRANSACTION THAT CREATES THE ROW** — BR-TEN-035,
    and `services._allocate_account_no` is the precedent this whole module
    follows: the allocation and the `objects.create(...)` share one `atomic()`,
    so a record never sits on file unnumbered. A rolled-back move leaves a GAP
    in the counter, which BR-TEN-035 permits and prefers to a number issued
    twice.

    ⚠ **REPORTING RATHER THAN RAISING IS THE WHOLE POINT.** A household must not
    be refused a move-in because nobody configured numbering. The move is the
    regulated act; its reference is not.
    """
    from core import numbering as core_numbering

    series = SERIES_BY_KIND[kind]
    try:
        return core_numbering.next_number(series, issue_date or seams.tenant_today()), None
    except core_numbering.NumberingError:
        return None, dict(MOVE_NUMBER_UNAVAILABLE[kind])


def record_move(
    *,
    kind: str,
    account_id: Any,
    effective_on: Any,
    actor: Any = None,
    from_account_id: Any = None,
    reads_committed: int = 0,
    is_sample: bool = False,
    service_request_id: Any = None,
    reserved_move_no: str | None = None,
) -> dict[str, Any]:
    """Write the record for a job that has just completed, and return what a
    screen needs to show for it.

    ⚠ **THE CALLER SUPPLIES THE TRANSACTION.** `services.move_in` and
    `services.move_out` each already open one for the account write, the
    agreement writes and the reads; this joins it rather than opening a second,
    so a refused reading rolls the record back with everything else and there is
    never a record of a move that did not happen (BR-SHL-019, one commit).

    The return is `{move_no, move_no_unavailable, move_record_id}` — the two
    number keys being exactly the pair `transfers` and `disconnects` already
    serve, so one frontend cell (`RecordNumberCell`) reads all four flows.
    """
    if kind not in KINDS:  # pragma: no cover - callers pass a module constant
        raise ValueError(f"unknown move kind {kind!r}")
    from core import tenancy as core_tenancy

    # ── THE NUMBER: ADOPTED IF ONE WAS RESERVED, MINTED ONLY IF NOT ──────────
    #
    # ⚠ **A RESERVED NUMBER IS ADOPTED, NOT RE-ALLOCATED (`CR-122-BRC06`).**
    # The move-in draft took `MVI-{YY}-{0000}` from THIS series the moment the
    # wizard opened, and the clerk has been quoting it ever since. Allocating a
    # second one here would file the finished job under a number nobody was
    # told — which is exactly the two-vocabularies split `move_reads
    # ._requests_by_account_no` already records the cost of, one table over.
    # The draft's row is deleted by the caller inside this same transaction, so
    # the number is never live in two places at once.
    #
    # ⚠ **AND SINCE `BR-CUS-1090` THERE IS A SECOND RESERVER, ONE STEP EARLIER
    # IN THE SAME JOB'S LIFE: THE APPROVAL.** A move-in approved on a service
    # request took its `MVI-` the moment the clerk pressed Approve, and it has
    # been printed on the Move-ins queue ever since. So the order is
    # **draft → job → mint**, and it is an order rather than three cases:
    # a clerk who approved AND parked has one number in both rows (the park
    # CARRIES the job's, `wizard_parks.CARRIED_REFERENCE_KEYS`), so the two arms
    # cannot disagree; a move-in through any other door reserves nothing and
    # mints here exactly as it always has.
    #
    # ⚠ **THE JOB IS READ BEFORE THE RECORD IS WRITTEN AND CLOSED AFTER**, and
    # that is not an ordering accident: `complete_for_request` moves the row to
    # `done`, and reading the number off it afterwards would be reading a row
    # this function has just changed.
    # ⚠ **AND THE JOB'S NUMBER BEATS THE DRAFT'S (`DEF-CUS-9684`, 2026-10-05).**
    # The order above read *draft → job → mint*, which is right only when the
    # draft CARRIED the job's number. The wizard opened from an approval
    # autosaves on open with no `move_in_no` on its subject, so its draft MINTS
    # one — and the finished move was filed under that second number while the
    # request went on linking to the first (SR-26-0009 → MVI-26-0005, the move
    # and its visit on MVI-26-0006). The job's number was issued FIRST and is
    # the one printed on the request, so it wins; the draft's becomes a gap,
    # which `BR-TEN-035` permits. **So the order is job → draft → mint.**
    pending_job = None
    if kind == KIND_MOVE_IN and service_request_id:
        from apps.customers import move_in_jobs

        pending_job = (
            move_in_jobs.MoveInJob.objects.filter(
                tenant_id=core_tenancy.current_tenant_id(),
                request_id=service_request_id,
                state=move_in_jobs.STATE_PENDING,
            )
            .only("id", "move_no")
            .first()
        )
    if pending_job is not None and pending_job.move_no:
        move_no, absence = str(pending_job.move_no), None
    elif reserved_move_no:
        move_no, absence = str(reserved_move_no), None
    else:
        move_no, absence = _allocate_move_no(kind, issue_date=effective_on)
    row = MoveRecord.objects.create(
        tenant_id=core_tenancy.current_tenant_id(),
        move_no=move_no,
        kind=kind,
        account_id=account_id,
        from_account_id=from_account_id,
        effective_on=effective_on,
        performed_by_id=getattr(actor, "id", None),
        reads_committed=int(reads_committed or 0),
        is_sample=bool(is_sample),
        # `CR-094-BRC01` — the application this move came from, where there was
        # one. `BR-CUS-080`'s child half, written at the moment the job is DONE
        # because that is the only moment this table has (see the model note).
        request_id=service_request_id or None,
    )
    # ── `BR-CUS-1077` (PO ruling 2026-09-16, *"it should do B"*) ────────────
    # **THE JOB IS DONE, SO IT LEAVES THE QUEUE.** Approving a move-in raises a
    # pending `move_in_jobs` row; this is the moment it stops being pending, and
    # it is the only moment that exists — a move-in is not "done" until it has
    # committed, which is what writing this record means.
    #
    # ⚠ **INSIDE THE CALLER'S TRANSACTION, deliberately.** A refused reading
    # rolls the account, the record AND this back together (`BR-SHL-019`), so a
    # move-in that did not happen leaves its job still waiting rather than
    # quietly closed. `0` is the ordinary answer on a move-out, on a move-in
    # nobody raised a job for, and on the second attempt at one.
    #
    # ⚠ **A MOVE-IN COMMITTED THROUGH SOME OTHER DOOR PASSES NO
    # `service_request_id` AND CLOSES NOTHING**, which is stated on the tab
    # rather than hidden — `move_reads.PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE`.
    jobs_closed = 0
    if kind == KIND_MOVE_IN and service_request_id:
        from apps.customers import move_in_jobs

        jobs_closed = move_in_jobs.complete_for_request(service_request_id)
    return {
        "move_record_id": str(row.id),
        "move_no": move_no,
        "move_no_unavailable": absence,
        # RETURNED rather than logged: the caller is the only code that knows
        # whether a zero here is expected, and a function that swallowed it
        # would be a check that cannot fail (hard-won law 7).
        "move_in_jobs_closed": jobs_closed,
    }


def serialize(row: MoveRecord) -> dict[str, Any]:
    """One record, as a screen reads it.

    The absence is RE-DERIVED from the stored row rather than remembered from
    the write, for the reason `disconnect_reads.case_reference_absence` gives:
    a row read back a week later must state its own absence, and a reason that
    only existed in a response is a reason nobody can see again.
    """
    return {
        "id": str(row.id),
        "kind": row.kind,
        "move_no": row.move_no,
        "move_no_unavailable": (None if row.move_no else dict(MOVE_NUMBER_UNAVAILABLE[row.kind])),
        "account_id": str(row.account_id),
        "from_account_id": str(row.from_account_id) if row.from_account_id else None,
        "effective_on": row.effective_on.isoformat() if row.effective_on else None,
        "performed_by_id": str(row.performed_by_id) if row.performed_by_id else None,
        "performed_at": row.performed_at.isoformat() if row.performed_at else None,
        "reads_committed": row.reads_committed,
        # `CR-094-BRC01` — the application, or None. A screen renders the
        # request NUMBER by walking it; B14 rule 31 keeps the id off the page.
        "request_id": str(row.request_id) if row.request_id else None,
    }


def records_for_account(account_id: Any) -> list[dict[str, Any]]:
    """Every move record that names this account, newest first — the provenance
    trail S18's account page shows.

    ⚠ **BOTH SIDES.** A chained move-in names the OUTGOING account in
    `from_account`, and that account's page should show the job that ended its
    tenancy as well as the one that started it. Filtering on `account` alone
    would hide the arrival from the person who left.
    """
    from django.db.models import Q

    rows = MoveRecord.objects.filter(
        Q(account_id=account_id) | Q(from_account_id=account_id)
    ).order_by("-performed_at", "-created_at")
    return [serialize(row) for row in rows]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave D tasks 17–19 (12-governance/11-change-requests.md) + the
#         PO ruling of 2026-08-27 (12-governance/02-decision-log.md, "a move-in
#         and a move-out ARE records, kept for audit") + BR-CUS-150..153
#         (04-docs/05-modules/03-customers/02-business-rules.md) + BR-TEN-035 /
#         BR-TEN-043 / BR-TEN-057 + B18 §5.5 / §5.6. ⚠ NO STORY OWNS the move
#         worklists — hard-won law 8, the same gap `disconnect_reads.py` filed
#         for S90 — so there is no US- id to name here and one is OWED.
# generated: 2026-08-27, CR-039 wave D tasks 17–19 lane
# gates: ruff✔ black✔ (line-length 100) · makemigrations --check clean✔ ·
#        tests/test_cr039_wd_move_records.py · the five hand-pinned numbering
#        places each PROVED RED first and quoted verbatim in the commit and in
#        the decision log · tsc --noEmit clean✔ · vitest 3 files / 39 tests✔ ·
#        run_gates: this file's own G11 trailer failure is what added these two
#        lines. ⚠ 15 gates FAIL repo-wide and NONE of the others is this lane's
#        — measured, and named in the lane report rather than claimed clean.
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(migration ordering is 🔒
#            HUMAN-REVIEW-PENDING per the PO ruling of 2026-08-09 — the ledger
#            row for customers/0030 is appended)
# exceptions: E1 no deposit-election column — the ruling names one and NEITHER
#             WIZARD HOLDS ONE (measured; DEF-921, routed as OQ-510), so a
#             column here would be a slot nothing can fill · E2 no step/state
#             columns — `move_reads.STEP_HAS_NO_STORE` asks for a case row and
#             is NOT closed by this table, which records a COMPLETED job · E3
#             `performed_by`/`performed_at` duplicate the audit row on purpose
#             (§1) · E4 no money column of any kind, for `Transfer`'s reason
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

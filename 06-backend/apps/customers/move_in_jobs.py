# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-16, verbatim: *"it should do B"*, choosing from
#           three options put to them with each cost named — decision log,
#           *"RULED — OPTION B: APPROVING A MOVE-IN RAISES A PENDING MOVE-IN
#           JOB, THE WAY A NEW CONNECTION RAISES A DRAFT BUILD. THE ACCOUNT
#           STILL DOES NOT OPEN AT APPROVAL."*
# Defects:  DEF-CUS-5398 (approving a move-in raised nothing, and the request
#           sat at `Under review` with its outcome already saved)
# Rules:    **BR-CUS-1077** (this file) · **BR-CUS-1090** (the `MVI-` number
#           this row carries from the moment it is approved, PO 2026-09-22 —
#           `CR-133-BRC07`) · BR-CUS-093 (the numbered-at-creation precedent,
#           burned number included) · BR-TEN-035 (allocation, and the lawful
#           gap) · BR-CUS-080 (the SR alone answers
#           *what happened to this application*; the child names the request) ·
#           BR-CUS-018 (a draft account is the move-in window — and a pending
#           job is the window BEFORE that) · BR-CUS-150/151/152 (`move_records`
#           is the record of a move that HAS happened and nothing updates a row
#           of it — untouched by this file) · BR-TEN-057 (the sample tag rides
#           the owning row) · CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE)
#           · hard rule 4 (no UPDATE on an issued money row — none here) ·
#           hard rule 8 (an address lives on `premises` and is WALKED to)
# Screens:  the Accounts page's Move-ins tab (B18 §5.5.2) — the drawn `— draft`
#           row, which until now this product could not hold.
# Tests:    06-backend/tests/test_br_cus_1077_move_in_job.py ·
#           06-backend/tests/test_br_cus_1090_move_in_job_number.py ·
#           10-scripts/br_cus_1090_move_in_number_readback.py (real PostgreSQL)
# Impacts:  apps/customers/request_jobs.py (`_raise_move_in`, and §3's absence
#           is superseded for the move-in) · apps/customers/move_reads.py (the
#           Move-ins tab reads two kinds of row) · apps/customers/moves.py
#           (`record_move` closes the job) · apps/customers/models.py (imports
#           this module at its foot so the model registers) ·
#           apps/customers/migrations/0053_br_cus_1077_move_in_jobs.py ·
#           apps/customers/migrations/0064_br_cus_1090_move_in_job_number.py ·
#           apps/customers/migrations/0080_cr171_p1_01_move_in_redesign.py (`cancelled`) ·
#           apps/tenancy/wizard_parks.py (`CARRIED_REFERENCE_KEYS` — a wizard
#           opened on a job carries its number) · apps/customers/
#           move_record_reads.py (`/moves/{ref}` resolves a pending job)
# ───────────────────────────────────────────────────────
"""**A pending move-in job — the row approving a move-in raises.**

PO ruling 2026-09-16, verbatim: *"it should do B"*. The clerk walk found that
approving a move-in **did not complete at all**: `SR-26-0024` sat at
`Under review` with `outcome=move_in` already saved, so the request looked
decided while being nothing of the kind.

═══════════════════════════════════════════════════════════════════════════
1 · WHY A ROW OF ITS OWN, AND NOT ONE OF THE THREE PLACES THAT ALREADY EXIST
═══════════════════════════════════════════════════════════════════════════
Weighed before a line was written, and recorded here because the next lane
will ask the same question (build skill §3 — a judgment with its reasoning is
the deliverable):

| Where it could have lived | Why not |
|---|---|
| **`accounts`, as a draft** | The account **does not open at approval**. The Approve drawing says so on all five outcomes, in as many words: *"Not now — No account opens. Nothing is energised."* |
| **`move_records`** | It is the record of a move that **HAS HAPPENED** — its own docstring says *"written by a flow that has already committed"*, `BR-CUS-152` says nothing ever updates a row of it, and `account_id` is NOT NULL, which is the very account the job exists to create. A pending row there would state that somebody did a move-in that nobody has done. |
| **the `service_requests` row itself** | It is the APPLICATION, and its lifecycle is `approved` the moment the clerk presses. A JOB has its own life after that — it is pending, then it is done — and folding two lifecycles into one row is how `move_records` came to be asked to hold a queue in the first place. It also fixes the queue to requests: a move-in raised by any other door could never join it. |
| **a row of its own (this)** | The shape the product already uses one outcome over: a new connection raises a **draft** `connections` row that appears on its tab at once, carries `request_id`, and whose own wizard asks for the rest. |

⚠ **B18 §5.5.2's FOOTNOTE IS SUPERSEDED FOR THE MOVE-IN, AND THE SUPERSESSION
IS STATED RATHER THAN QUIETLY OUTBUILT (B14 rule 41, law 13).** That footnote
reads *"a move-in is short enough that the wizard is the record"*, and
`move_reads.STEP_HAS_NO_STORE` has cited it since CR-030 W5 as the reason no
case row exists. **The PO has now ruled one into existence**, for a reason the
footnote never weighed: without it an approved move-in appears on no queue at
all, and *"the queue stays empty until somebody finishes the wizard"* was the
cost that made them reject option C.

⚠ **AND THE FOOTNOTE IS SUPERSEDED ONLY FOR THE `pending` HALF.**
`STEP_HAS_NO_STORE` asks for *"a move-in/move-out case row carrying step + state"*
and **this row carries no step**: nothing in this product writes one, so a step
column would be a slot nothing fills — hard-won law 2 on data, which is the
shape `DEF-921` took one table over when a `deposit_carry_elected` column was
refused for exactly this reason. The absence stays served on every row.

═══════════════════════════════════════════════════════════════════════════
2 · IT COPIES NOTHING. EVERY FACT IS READ THROUGH THE REQUEST.
═══════════════════════════════════════════════════════════════════════════
The applicant, the resolved premises, the resolved unit, the requested start,
the services asked for, the outstanding money and the unchecked documents are
**all on the request already**, and this row names the request. So it stores
none of them.

That is `request_jobs` §4's own doctrine applied to a whole table rather than
to one figure — *"the money travels by the link and is never copied … a second
copy of a fact that already has an owner is how two numbers come to disagree"*
— and it is the one place this row deliberately differs from `connections`,
which DOES copy `premises_id` and `target_activation`. The difference has a
reason: a build can be raised with no request at all, so it must carry its own
copy; **`request` here is NOT NULL and a job with no request cannot exist.**

⚠ **THE ADDRESS IS WALKED, NEVER STORED (CLAUDE.md hard rule 8).** There is no
address column here and there is not going to be one: the request resolves to a
premises (and sometimes a unit), and every screen walks to `premises` for the
line it prints.

⚠ **AND THE UNCHECKED DOCUMENTS TRAVEL THE SAME WAY (PO ruling 2026-09-16,
*"lets not make it mandetory"*).** Unchecked documents no longer block an
approval — so an approved request may well still be waiting on one, and
`outstanding_documents()` below reads that condition back through the link at
the moment anybody asks. *Not mandatory* is not *not mentioned*: the job
carries the list into its own wizard, and it carries it live rather than as a
snapshot of what was outstanding on the day the clerk pressed.

═══════════════════════════════════════════════════════════════════════════
3 · THREE STATES, BECAUSE THREE IS WHAT HAS A WRITER
═══════════════════════════════════════════════════════════════════════════
`pending` → `done`, and **`pending` → `cancelled`** since `customers/0080`.

⚠ **THIS READ *"`cancelled` is deliberately absent: no door in this product
cancels a move-in job"* UNTIL 2026-10-05, AND THE REASON WAS TRUE THEN.** The PO
then ruled a door into existence (CR-171-BRC10, mock-up v22, verbatim *"update
details view button accrdongly"* over the table that gives a *Not started*
move-in **More: Cancel move-in…**), so the state now has a writer: `P1.22`
(`CR-171` S2). ⚠ **`P1.22` LANDED 2026-10-05 (lane MVI-FLOW, 2.531.0): the ONE
writer is `move_in_cancel._cancel_job`** — `pending → cancelled`, `closed_at`
stamped, `closed_reason = move_in_cancelled`. A `done` job is never moved to
`cancelled`: a committed move-in's cancel closes the ACCOUNT, and the job WAS
done (`move_in_cancel` module docstring).

**What closes it is `moves.record_move`** — the one function both move-in doors
already go through, inside their own transaction. When a move-in record is
written naming this job's request, the job is `done` and the row leaves the
Move-ins tab in the same commit that puts the account on it.

⚠ **AND A MOVE-IN DONE BY SOME OTHER DOOR LEAVES THE JOB PENDING. THAT IS
STATED, NOT HIDDEN.** A clerk who opens an account through S18 rather than
through the move-in wizard passes no `service_request_id`, so nothing closes
the job and the tab would show the pending job AND the draft account — B18
§5.7.3's counting contract in miniature. `move_reads` serves
`PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE` on every Move-ins response rather
than leaving a clerk to notice, and the door the job needs — *the wizard,
opened FROM the job, carrying the request* — is filed rather than faked.

═══════════════════════════════════════════════════════════════════════════
4 · IT CARRIES A NUMBER — `BR-CUS-1090`, AND WHY THAT IS NOT §2 BEING BROKEN
═══════════════════════════════════════════════════════════════════════════
PO ruling 2026-09-22, verbatim: *"you would ahve created a new move In request
ID and add all details from servcies request to it and save it as a draft - do
you ahve move in request ID in numbering?"*

`move_no` is `MVI-{YY}-{0000}`, allocated in `raise_for_request` inside the
approval's own transaction. **It is not a copy of anything** — §2 forbids
storing a fact the request already owns, and the request owns no number for this
job. A number has no owner until somebody issues one, and this is where it is
issued.

**THE PRECEDENT IS THE PO'S OWN AND IS FOLLOWED WHOLE, INCLUDING THE PART THAT
COSTS SOMETHING.** `BR-CUS-093` (2026-08-24) numbers a service request at
CREATION rather than at submission, *"the clerk can quote the number to the
customer on the phone while the form is still half-filled"*, and an abandoned
draft **burns its number**. So a rolled-back approval leaves a gap in the `MVI-`
series, `BR-TEN-035` permits it, and **a gap here is not loss and must never be
reported as one.**

⚠ **ONE MOVE-IN, ONE NUMBER, THREE TABLES — AND THE CHAIN IS THE RULE RATHER
THAN A NICETY.** A move-in can leave a row in `move_in_jobs` (approval), in
`wizard_parks` (a clerk opened the wizard and put it down) and in
`move_records` (the commit). Numbering the first without chaining it to the
other two would print `MVI-26-0115` on the queue and file the finished job under
`MVI-26-0117` — the *two vocabularies* cost `moves.record_move` already names in
its own comment.

    approval ──► move_in_jobs.move_no      allocated ONCE, here
                     │
                     │ `move_in_no` in `wizard_parks.CARRIED_REFERENCE_KEYS`
                     ▼
    park     ──► wizard_parks.reference    CARRIED — burns no counter
                     │
                     │ `_adopt_wizard_draft`, else this job's own
                     ▼
    commit   ──► move_records.move_no      ADOPTED, never re-allocated

⚠ **NO DATABASE CAN HOLD THAT, AND SAYING SO IS THE POINT** (hard-won law 1).
`uq_move_in_jobs_tenant_move_no_ci` makes one number mean one JOB; nothing in
PostgreSQL makes one number mean one move-in across three tables. The chain is
held by this code path and by
`06-backend/tests/test_br_cus_1090_move_in_job_number.py`, and the guarantee is
narrower than the rule.

⚠ **THE DETAILS ARE CARRIED, NOT COPIED, AND THAT IS A JUDGMENT RECORDED
RATHER THAN SMUGGLED.** The PO's sentence asks for *"all details from servcies
request"* on the draft. Every detail they named is already on the row and has
been since 2026-09-16 — applicant, unit, requested start, outstanding documents
— read through the link at the moment anybody asks; `services_asked_for` below
adds the one that genuinely was not shown, the same way. **A clerk sees no
difference. A copy would let the queue and the application disagree about a
start date the day somebody edits one**, which is §2's whole argument, and an
address column here would be a fourth home CLAUDE.md hard rule 8 forbids and
`G85` fails by name. `request` is NOT NULL and `PROTECT`ed, so the facts can
never become unreachable — which is the only argument a copy would have had.
"""

from __future__ import annotations

from typing import Any

from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from core.dbfields import uuid7_pk

# ═══════════════════════════════════════════════════════════════════════════
# THE THREE STATES — §3, and a CHECK so a fourth cannot arrive by a typo
# ═══════════════════════════════════════════════════════════════════════════
STATE_PENDING = "pending"
STATE_DONE = "done"
#: CR-171-BRC10 `P1.01` (`customers/0080`) — §3. Written by `P1.22`'s cancel.
STATE_CANCELLED = "cancelled"
STATES: tuple[str, ...] = (STATE_PENDING, STATE_DONE, STATE_CANCELLED)

#: Why a job stopped being pending. One value today, and it is written rather
#: than inferred so a row read back next year says what closed it.
CLOSED_BY_MOVE_RECORD = "move_recorded"
#: `DEF-CUS-9036` (2026-10-01) — the approved request was fulfilled by the
#: owner's MASTER account rather than a tenant's move-in: an owner or manager
#: taking a whole multi-unit premises. No move record exists for it, because no
#: unit was occupied, so the reason says which door closed the job.
CLOSED_BY_MASTER_ACCOUNT = "master_account_opened"


class MoveInJob(models.Model):
    """One approved move-in, waiting for somebody to do it.

    ⚠ **MANAGED, and registered by `models.py`'s import at its foot** — the
    pattern `moves.MoveRecord`, `disconnects.DisconnectCase` and
    `account_document_models.AccountDocument` all follow: one capability, one
    module, with each column's reasoning beside the column rather than restated
    in a migration.

    ⛔ **NO STEP, NO ACCOUNT, NO ADDRESS, NO MONEY.** Every one of those is
    refused by name and for a stated reason — see the module docstring §1 and
    §2. What is here is the LINK, the LIFE and the PROVENANCE, and nothing that
    already has an owner.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: **The application this job came from** — `BR-CUS-080`'s child half, and
    #: the requirement the ruling states in its own words: *"the job carries the
    #: request's id so a clerk can walk back"*. `connections.request_id` is the
    #: precedent and this is the same direction of link.
    #:
    #: ⚠ **NOT NULL, unlike `connections.request_id`, and unique per tenant.**
    #: A build exists whether or not an application produced it; this row exists
    #: ONLY because an approval raised it, so a NULL here would be a state no
    #: door can reach. The uniqueness is what makes a double-click idempotent at
    #: the database layer rather than only in the service (CLAUDE.md rule 6's
    #: posture, and the shape `ux_service_requests_outcome_ref` already has).
    request = models.ForeignKey(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="+",
    )
    #: **`MVI-{YY}-{0000}` — the reference a clerk quotes for this move-in, and
    #: its identity for the rest of its life** (`BR-CUS-1090`, PO ruling
    #: 2026-09-22). Allocated ONCE, inside the approval's own transaction, from
    #: the same `move_in` series the parked draft and the finished record draw
    #: from — see §4.
    #:
    #: ⚠ **NULL WHERE THE TENANT HAS NO SERIES ROW**, and that is a real answer
    #: rather than a gap: `moves._allocate_move_no`'s own words, *"A household
    #: must not be refused a move-in because nobody configured numbering. The
    #: move is the regulated act; its reference is not."* The reason is SERVED
    #: beside the row (`moves.MOVE_NUMBER_UNAVAILABLE['move_in']`), never a bare
    #: dash. Jobs raised before 2026-09-22 are NULL for a second reason — no
    #: back-fill, `customers/0064` §1 — and say the same thing.
    #:
    #: ⛔ **NOTHING REWRITES IT.** There is no door that renumbers a job, and
    #: `uq_move_in_jobs_tenant_move_no_ci` is what makes that a guarantee rather
    #: than a comment claiming one (hard-won law 1).
    move_no = models.TextField(null=True, blank=True)
    #: `pending` | `done` | `cancelled` — §3, CHECK-constrained in the migration.
    state = models.TextField(default=STATE_PENDING)
    #: WHO approved the request that raised this, and WHEN. NULL `raised_by`
    #: only where the actor carries no `identity.User` row (a system or seeded
    #: actor), which is a real state and is not read as "nobody" — `MoveRecord`
    #: takes the same posture on `performed_by` and says why.
    raised_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="raised_by",
        null=True,
        blank=True,
    )
    raised_at = models.DateTimeField(default=timezone.now)
    #: When the job stopped being pending, and what closed it. Both NULL while
    #: it is pending; `closed_reason` is `move_recorded` today and is written
    #: rather than inferred (§3).
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.TextField(null=True, blank=True)
    #: BR-TEN-057 — the sample tag rides the owning row, so BR-TEN-061 can
    #: delete a demo estate on one predicate. Taken from the REQUEST, which is
    #: the row this one exists for.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # EXPLICIT, as every model defined outside `models.py` in this app
        # declares it: without it Django raises *"doesn't declare an explicit
        # app_label"* the moment the module is imported.
        app_label = "customers"
        db_table = "move_in_jobs"
        constraints = [
            models.CheckConstraint(condition=Q(state__in=STATES), name="ck_move_in_job_state"),
            # ONE job per request, per tenant — §1's idempotency, at the layer
            # a double-click, an import and a fixture all have to pass.
            models.UniqueConstraint(
                fields=["tenant", "request"], name="uq_move_in_jobs_tenant_request"
            ),
            # ONE number to ONE job — `BR-CUS-1090`. PARTIAL because the NULLs
            # of `move_no` must not collide with each other (a tenant with no
            # series would otherwise hold exactly one unnumbered job), and
            # `Lower(...)` because `mvi-26-0115` and `MVI-26-0115` are one
            # number to a person and two to a plain index — which is also how
            # `/moves/{ref}` resolves. The same shape `move_records` carries.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("move_no"),
                condition=Q(move_no__isnull=False),
                name="uq_move_in_jobs_tenant_move_no_ci",
            ),
        ]
        indexes = [
            # The Move-ins tab's own read: this tenant's pending jobs, newest
            # first. `state` leads the trailing columns because the tab always
            # filters on it.
            models.Index(fields=["tenant", "state", "-created_at"], name="ix_move_in_jobs_state"),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# THE DOORS
# ═══════════════════════════════════════════════════════════════════════════
def raise_for_request(actor: Any, request: Any) -> dict[str, Any]:
    """Raise the pending job for an approved move-in, or report why not.

    Returns either the job (`{"id", "state", …}`) or a named refusal carrying
    `code` — the shape `request_jobs` established so `raise_job` can tell them
    apart, and the shape every stated absence in this module already uses.

    ⚠ **IDEMPOTENT, AND CHECKED HERE RATHER THAN ONLY CAUGHT.** The unique
    constraint is the guarantee; this read is what turns a second press into a
    sentence a clerk can read instead of an `IntegrityError` in a log. Both are
    kept: a check without the constraint is a race, and a constraint without
    the check is a stack trace.

    ⚠ **THE NUMBER IS ALLOCATED HERE AND NOWHERE ELSE** (`BR-CUS-1090`). It
    happens BEFORE the `create`, in the caller's own transaction, so a job never
    exists unnumbered even for the width of a transaction — `moves.record_move`'s
    posture and `services._allocate_account_no`'s before it. A second press
    returns above without touching the series, so the double-click that is the
    whole point of `uq_move_in_jobs_tenant_request` also burns no counter.
    """
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    existing = MoveInJob.objects.filter(tenant_id=tenant_id, request_id=request.id).first()
    if existing is not None:
        return {
            "code": JOB_ALREADY_RAISED,
            "br_ref": "BR-CUS-1077 · BR-CUS-1090",
            "detail": (
                "This request already has a move-in job waiting, and one decision raises one "
                "job. Nothing further was created and no second number was issued."
            ),
            "id": str(existing.id),
            "move_no": existing.move_no,
        }
    # ⚠ **ITS OWN TRANSACTION, BECAUSE THE CALLER HAS NONE (`DEF-CUS-6421`).**
    # The paragraph above says the number is allocated *"in the caller's own
    # transaction"* — and `approve_and_raise` calls `raise_job` AFTER its
    # transaction commits (`BR-WRK-055`: the approval stands whatever the job
    # does). So on PostgreSQL the series row's `SELECT … FOR UPDATE` ran in
    # autocommit and Django refused it (*"select_for_update cannot be used
    # outside of a transaction"*): every move-in approved through the screen
    # read *The job could not be opened.* SQLite has no `FOR UPDATE` and every
    # pytest case runs inside a wrapping transaction, so nothing but a real
    # request could see it. The allocation and the row are one act, so they
    # are one transaction; inside a caller's transaction this is a savepoint.
    with transaction.atomic():
        move_no, _absence = _allocate_move_in_no(request)
        row = MoveInJob.objects.create(
            tenant_id=tenant_id,
            request_id=request.id,
            move_no=move_no,
            state=STATE_PENDING,
            raised_by_id=getattr(actor, "id", None),
            is_sample=bool(getattr(request, "is_sample", False)),
        )
    return serialize(row)


def _allocate_move_in_no(request: Any) -> tuple[str | None, dict[str, Any] | None]:
    """`MVI-{YY}-{0000}` for a job being raised — or the reason there is none.

    ⚠ **ONE ALLOCATOR, NOT A SECOND SPELLING.** It delegates to
    `moves._allocate_move_no(KIND_MOVE_IN)`, which is the function the finished
    record has always used and which reads `SERIES_BY_KIND`. Writing the series
    key out again here would be two places that have to agree about what a
    move-in's number looks like, and `moves.py` §2 already records what that
    costs one table over.

    ⚠ **THE ISSUE DATE IS THE REQUESTED START WHERE THERE IS ONE, ELSE TODAY.**
    `BR-TEN-035` formats `{YY}` off the issue date, and an application asking to
    move in on 2 January is a `MVI-27-…` job even when the clerk approves it in
    December. An application that named no date is numbered on the day the clerk
    decided, which is the only date the job then has.

    ⚠ **A MISSING SERIES IS REPORTED BY ABSENCE, NEVER BY REFUSAL.** The
    approval must not fail because nobody configured numbering — that is
    `moves._allocate_move_no`'s own ruling and this inherits it whole. The
    returned absence is DISCARDED by the caller on purpose: it is re-derived
    from the stored NULL wherever it is read (`serialize`, `move_reads`), for
    the reason `moves.serialize` gives — *"a reason that only existed in a
    response is a reason nobody can see again"*.
    """
    from apps.customers import moves, seams

    issue_date = getattr(request, "requested_start", None) or seams.tenant_today()
    return moves._allocate_move_no(moves.KIND_MOVE_IN, issue_date=issue_date)


#: The one refusal this door has. Named beside the function that returns it.
JOB_ALREADY_RAISED = "move_in_job_already_raised"


def complete_for_request(request_id: Any, *, reason: str = CLOSED_BY_MOVE_RECORD) -> int:
    """The move happened — the job is done and leaves the queue.

    Called by `moves.record_move` **inside the wizard's own transaction**, so a
    refused reading rolls this back with the account and the record and the job
    is still waiting afterwards (`BR-SHL-019`, one commit).

    Returns how many rows moved — `0` is the ordinary answer for a move-in
    nobody raised a job for, and is not an error. It is RETURNED rather than
    logged because the caller is the only code that knows whether a zero is
    expected, and a function that swallowed it would be the kind of check that
    cannot fail (hard-won law 7).

    ⚠ **THIS IS THE ONLY UPDATE IN THIS FILE, AND IT IS NOT HARD RULE 4's
    SUBJECT.** That rule names issued invoices, invoice lines, payments and
    journal entries; a queue row moving from `pending` to `done` is the
    lifecycle of a job, exactly as `connections` moves from `draft` onward. No
    money is written here and none is readable from here.
    """
    if not request_id:
        return 0
    return MoveInJob.objects.filter(request_id=request_id, state=STATE_PENDING).update(
        state=STATE_DONE,
        closed_at=timezone.now(),
        closed_reason=reason,
        updated_at=timezone.now(),
    )


def pending_queryset():
    """This tenant's move-in jobs still waiting — the Move-ins tab's second
    source.

    Tenant-scoped explicitly rather than trusting RLS alone: CLAUDE.md hard rule
    1 is belt AND braces everywhere else in this module and a queryset that
    reads correctly only because a policy is switched on is a queryset that
    reads wrongly the day somebody runs it as a migration.
    """
    from core import tenancy as core_tenancy

    return MoveInJob.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), state=STATE_PENDING
    ).select_related("request")


def serialize(row: MoveInJob) -> dict[str, Any]:
    """One job, as a screen reads it.

    ⚠ **NO `request_id` IN THE PAYLOAD AS A VISIBLE VALUE.** B14 rule 31 keeps a
    database id off the page, so the id is served for a screen to navigate with
    and the REQUEST NUMBER is served beside it as the thing a clerk reads and
    quotes.
    """
    from apps.customers import moves

    request = row.request
    return {
        "id": str(row.id),
        "state": row.state,
        # `BR-CUS-1090` — the number a clerk quotes, and the pair every other
        # move surface in this product serves: exactly one of the two is set.
        # The absence is RE-DERIVED from the stored NULL rather than remembered
        # from the write, which is `moves.serialize`'s own rule — *"a reason
        # that only existed in a response is a reason nobody can see again"*.
        "move_no": row.move_no,
        "move_no_unavailable": (
            None if row.move_no else dict(moves.MOVE_NUMBER_UNAVAILABLE[moves.KIND_MOVE_IN])
        ),
        "request_id": str(row.request_id),
        "request_no": request.request_no,
        "raised_at": row.raised_at.isoformat() if row.raised_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "closed_reason": row.closed_reason,
    }


def services_asked_for(request: Any) -> list[dict[str, Any]]:
    """The services the application asked for — READ through the link.

    `BR-CUS-1090`: the PO asked that the job carry *"all details from servcies
    request"*, and this was the one detail no surface showed. It is CARRIED and
    not COPIED, exactly as the applicant, the unit and the requested start
    already are — §2 above is the whole argument and it does not weaken for one
    more field.

    ⚠ **`request.services` IS A REVERSE MANAGER, NOT A JSON LIST, AND THE FIRST
    DRAFT OF THIS FUNCTION GOT IT WRONG IN THE WAY THAT LEAVES NO TRACE.** It
    read `isinstance(raw, list)` and returned `[]` — so every request on the
    seeded utility reported *no services asked for*, truthfully-looking and
    completely false, with `tsc`, ruff and every suite green. It was found by
    printing the value against a real database rather than by any check, which
    is CLAUDE.md hard-won law 7's *reporting zero over a scope it silently
    excludes* in one function. **The rows live in `service_request_services`**
    (`models.ServiceRequestService`), one per requested utility service.

    ⚠ **CODE AND NAME, NEVER A SENTENCE** (`BR-SHL-010`). `service.code` is what
    a screen keys a badge and a catalogue label off; `service.name` is the
    platform's own English and is served beside it as the fallback a screen
    renders when no catalogue answers — the same pair `ratingShared` already
    reads. `available` rides along because REQ-03.2 is explicit that **NULL is
    *not yet asked* and is never spelled the same way as *no***: a screen that
    rendered a blank for both would merge two different facts, which is
    `DEF-127`'s shape.

    Returns `[]` for a request that named none, which is a real answer: a
    move-in application can be taken before anybody has decided what to connect.

    ⚠ **ONE QUERY, `select_related` ON THE SERVICE.** This is read once per JOB
    PAGE and never per row of a list — `move_reads` deliberately does not carry
    it, because a per-row read here would be a query per row on a worklist.
    """
    manager = getattr(request, "services", None)
    if manager is None or not hasattr(manager, "select_related"):  # pragma: no cover
        return []
    return [
        {
            "code": getattr(row.service, "code", None),
            "name": getattr(row.service, "name", None),
            # NULL means *nobody has asked yet* (REQ-03.2), which step 3 of the
            # review settles. It is NOT `False`.
            "available": row.available,
        }
        for row in manager.select_related("service").order_by("service__name")
    ]


def outstanding_documents(request: Any) -> dict[str, Any] | None:
    """What the clerk still owes this job, read back through the link.

    PO ruling 2026-09-16: unchecked documents no longer BLOCK an approval, and
    *not mandatory is not not mentioned*. So the job carries the list into its
    own wizard — **live**, by asking the same condition the Approve dialog asks,
    rather than as a snapshot of what was outstanding on the day it was
    approved. A document that arrives tomorrow makes this answer `None`
    tomorrow, with nothing to keep in step.

    `None` means *nothing is outstanding*, which is the shipped default for a
    utility that has ticked no checklist (`BR-CUS-095`).
    """
    from apps.customers import service_request_reads as reads

    condition = reads._documents_condition(request)
    # `clear` is the property, not the raw state: it is TRUE for `noted` as well
    # as `clear`, which is the distinction `Condition` itself draws and the one
    # a caller of this function means by *nothing outstanding*.
    if condition.clear:
        return None
    return {
        "key": condition.key,
        "state": condition.state,
        "message_key": condition.message_key,
        "params": dict(condition.params),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: the PO ruling of 2026-09-16 (12-governance/02-decision-log.md, *"it
#         should do B"*) + BR-CUS-1077 (04-docs/05-modules/03-customers/
#         02-business-rules.md) + DEF-CUS-5398. ⚠ NO STORY OWNS the move
#         worklists — hard-won law 8, the finding `move_reads.py` and
#         `moves.py` have each already filed — so there is no US- id to name
#         and one is still OWED.
# generated: 2026-09-16, the option-B lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(migration ordering + the RLS
#         policy are 🔒 HUMAN-REVIEW-PENDING per the PO ruling of 2026-08-09;
#         the ledger row for customers/0053 is appended)
# gates: ruff✔ · `makemigrations --check` clean for customers✔ ·
#         tests/test_br_cus_1077_move_in_job.py 12/12, TEN of them proved RED
#         first in pytest against `JOB_SHAPES["move_in"]["raises"] = None` —
#         the product as it stood — and quoted in that file's docstring ·
#         the double-press race proved on REAL PostgreSQL (hard-won law 14):
#         the second press is refused by name, a forced race is refused by
#         `uq_move_in_jobs_tenant_request`, and the connection is usable after
#         · RLS verified on the live cluster (`relrowsecurity` and
#         `relforcerowsecurity` both true, policy `move_in_jobs_tenant_isolation`)
#         · browser walk `10-scripts/br_cus_1077_move_in_job_walkthrough.mjs`,
#         22 checks, all passing. ⚠ THE REPO-WIDE GATE SUITE IS RED IN ~30
#         PLACES AND NONE OF THEM IS NAMED FOR THIS FILE — measured against
#         `run_gates.py --changed`, not assumed; the one that WAS this lane's
#         was G11 wanting this very line.
# exceptions: E1 no `step` column — `move_reads.STEP_HAS_NO_STORE` asks for one
#         and nothing in this product writes a step, so it would be a slot
#         nothing fills (DEF-921's shape) · E2 no `cancelled` state — no door
#         cancels a job · E3 no copied fact of any kind (§2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

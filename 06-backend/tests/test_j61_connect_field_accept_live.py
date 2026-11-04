# ── Trace ──────────────────────────────────────────────
# Journey:  J61 — connect → field → accept → live (08-qa/01-e2e/journeys/
#           J61-connect-field-accept-live.md). THIS FILE IS ITS ACTIVATION.
#           Extends J27; picks up what J65 leaves.
# Story:    US-WRK-003 · US-WRK-022 · US-WRK-035 · US-WRK-046
# Rules:    BR-WRK-003 · BR-WRK-015 · BR-WRK-007 · BR-WRK-057 · BR-MET-110 ·
#           BR-MET-115 · hard rule 1 · hard rule 3
# ───────────────────────────────────────────────────────
"""**`J61` ACTIVATED — one press, four consequences, and the fourth refused.**

`J61` is the morning after `J65`. The phone's Close moved nothing; here a
person presses Accept and **four things happen in one transaction**: the field
data is accepted, the reading is posted through metering's own door dated to
the COMPLETION, the service is activated — and the *your service is live*
letter is **refused at the queue** (`OQ-376`), which this journey asserts
rather than papers over.

⚠ **WHY A `.py`, NOT THE `.spec.ts` THE PLAN NAMES** — the argument is written
out once, in `test_j65_offline_day_one_sync.py`'s docstring, and not repeated
here. Short form: no `.spec.ts` runner exists, so such a file would be a check
that cannot fail, and a journey is a claim about what upstream leaves in the
DATABASE.

⚠ **WHAT THIS FILE ASSERTS** — the journey's own *"This journey leaves (for
downstream)"* paragraph and its INVARIANCE row, one test per clause. Not the
fifteen-step table: a test per drawn cell is a second copy of the journey,
free to disagree with the first.

⚠ **TWO OF THIS JOURNEY'S THREE BOUNDARIES CLOSED WHILE IT SAT UNACTIVATED,
AND THE FILE STILL DESCRIBED THEIR STUBS.** `OQ-WRK-1492` (who may accept) and
`OQ-WRK-1494` (the web-blocked login) were both ruled on 2026-09-04; steps 8
and 9 and boundaries (b) and (c) were amended on 2026-09-05, in the commit
that added this file, **before** anything was built on them. Had they not
been, this spec would have asserted an `xfail` for a question the PO had
already answered — which is `DEF-WRK-4030` exactly, and is why CLAUDE.md's
prime directive now says the STATUS COLUMN decides and a body that
contradicts it is stale until proved otherwise.

⚠ **`OQ-376` IS STILL OPEN**, and is the one boundary that remains. It is
asserted, not resolved: the letter is refused, the refusal names the question,
and **no `outbound_messages` row is written at all** — least of all one filed
as `notice`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.notifications import models as notification_models
from apps.work import selectors as work_selectors
from apps.work import sync
from tests.test_j65_offline_day_one_sync import _a_days_work
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_actor  # CR-168 P1.34 — sync as the field
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db

#: `J65` leaves the completion here. `J61`'s exit test is that the read lands
#: on THIS day and not on the day of the acceptance, which is today.
COMPLETION_DAY = "2026-03-15"


def _a_closed_job_on_a_build(actor, tenant):
    """A closed job standing on a BUILD as well as on a meter.

    ⚠ **WITHOUT THE BUILD THE LETTER CLAUSE PROVES NOTHING, AND IT LOOKS
    IDENTICAL WHEN IT DOES.** `dispatch_communication` returns at its FIRST
    guard when `order.connection_id is None` — *"an order with no build sends
    nothing, and says so"* (`DEF-WRK-3635`) — answering `queued: False` with
    `no_connection: True`, and **never reaching `queue_document` at all**. A
    test that only asserted `queued is False` would go green on a job that
    never had a letter to send, and `BR-WRK-057` would be unproved. The same
    hole was live in wave L's own walkthrough and is fixed in the same commit
    as this file.
    """
    # `make_premises` is the helpers' own door and fills the owner the
    # premises validator requires; an inline payload here refused with
    # `metering.premises.owner_required`, correctly.
    premises = make_premises(
        actor, address_line="12 Heron Way", services_available=["electric"]
    )
    build = w6.create_connection(actor, {"premises_id": str(premises["id"])})
    oid, batch = _a_days_work(actor, tenant, jobs=1, connection_id=build["id"])[0]
    sync.sync_batch(field_actor(oid, actor), oid, batch)
    return oid, build


def _a_closed_job(actor, tenant):
    """What `J65` leaves: one completed order, accepted by nobody, with a
    reading marked *becomes a meter read* waiting on it.

    ⚠ **BUILT BY `J65`'s OWN HELPER, ON PURPOSE.** These two journeys are a
    handoff, and a handoff proved against two different fixtures proves
    nothing about the join. If `J65`'s day stops producing what `J61` opens,
    this file goes red — which is the whole reason the pair exists.
    """
    oid, batch = _a_days_work(actor, tenant, jobs=1)[0]
    sync.sync_batch(field_actor(oid, actor), oid, batch)
    return oid


# ══════════════════════════════════════════════════════════════════════════
# The handoff FROM J65 — the queue is where the day arrives
# ══════════════════════════════════════════════════════════════════════════
def test_j61_picks_up_what_j65_left_the_completed_job_is_on_the_approval_queue(
    brazos, dana
):
    """`J61` step 7 — `Work-009` is *"one query, no new table"*:
    `accepted_by IS NULL AND state = completed`.

    This is the join between the two journeys: if `J65`'s close left the order
    in any other shape, `J61` has nothing to open.
    """
    with tenant_ctx(brazos):
        oid = _a_closed_job(dana, brazos)
        queue = work_selectors.awaiting_approval(page=1, per=100)
        ids = {str(row["id"]) for row in queue["rows"]}

    assert str(oid) in ids, f"the completed job is not on the approval queue ({len(ids)} row(s))"


def test_j61_an_order_nobody_finished_is_NOT_on_the_queue(brazos, dana):
    """The negative that gives the positive above its meaning.

    ⚠ **THE NULL ALONE IS NOT ENOUGH** (`J61` step 7). A planned order also has
    `accepted_by IS NULL`; what puts a job in front of a supervisor is that the
    FIELD finished it. A queue built on the null alone would show a dispatcher
    every job they had ever raised.
    """
    with tenant_ctx(brazos):
        planned, _unused = _a_days_work(dana, brazos, jobs=1)[0]  # raised, never closed
        queue = work_selectors.awaiting_approval(page=1, per=100)
        ids = {str(row["id"]) for row in queue["rows"]}

    assert str(planned) not in ids, "an unfinished job is sitting in the approval queue"


# ══════════════════════════════════════════════════════════════════════════
# "This journey leaves" — the read, through metering's door, dated to the
# COMPLETION, with its unit
# ══════════════════════════════════════════════════════════════════════════
def test_j61_leaves_ONE_meter_read_dated_to_the_completion_with_its_unit(brazos, dana):
    """The wave's exit test (`BR-WRK-003`), as a handoff clause.

    D. Ortiz types 1,204 kWh at 16:07 on 15 March; the office accepts today;
    **the meter's history shows 15 March**. `BR-TEN-043`: an event date, never
    a wall clock. Getting this wrong puts a read in the wrong billing period
    and nothing on any screen would show it.
    """
    from django.utils import timezone

    with tenant_ctx(brazos):
        before = metering_models.MeterRead.objects.count()
        oid = _a_closed_job(dana, brazos)
        w6.accept_field_result(dana, oid)
        after = metering_models.MeterRead.objects.count()
        read = metering_models.MeterRead.objects.order_by("-created_at").first()

    # ONE read, counted — not "at least one", which would pass on a door that
    # posted the same reading twice.
    assert after == before + 1, f"the acceptance wrote {after - before} reads, not 1"
    assert read.read_at.date().isoformat() == COMPLETION_DAY, read.read_at
    # Hard rule 3 — a quantity carries its unit, on the row that is kept.
    assert read.unit == "kWh", f"the read landed with unit {read.unit!r}"
    assert read.current_value == Decimal("1204"), read.current_value
    # ⚠ AND THE TWO DAYS ARE GENUINELY DIFFERENT, or the case above could pass
    # by the acceptance happening to fall on 15 March.
    assert timezone.now().date().isoformat() != COMPLETION_DAY, (
        "the fixture's completion day is today — the date assertion proves nothing"
    )


# ⚠ **A `MeterRead.objects.create` GREP LIVED HERE FOR TEN MINUTES AND WAS
# DELETED, WHICH IS WORTH MORE THAN THE TEST WOULD HAVE BEEN.**
# `J61` claims *"Work wrote NO `meter_reads` row itself"*, and the obvious way
# to assert it is to grep `apps/work/**` for the constructor. It went RED
# immediately — on `seams/metering_seam.py`, which contains the string **only
# inside a comment** that says the breach does not exist:
#     `apps/work/**` still contains no `MeterRead.objects.create`
# A substring search cannot tell a write from a sentence about a write, so the
# check reported a breach over prose. Left in place it would have been the
# other failure in hard-won law 7's list — a check whose output cannot
# distinguish pass from fail — and somebody would eventually have "fixed" it by
# editing the comment.
# **`G78` already holds this boundary properly**, by reading the module graph
# rather than the characters, and it is a merge gate rather than one file's
# test. A second, weaker copy of a gate is worse than no copy: it is trusted.

def test_j61_accepting_twice_posts_no_second_read(brazos, dana):
    """*Accepting twice does nothing* — refused idempotently.

    A second read on the same meter for the same day is a wrong number on a
    billing path, and `BR-MET-059` (one read per meter per date) is the
    backstop underneath the refusal rather than a substitute for it.
    """
    with tenant_ctx(brazos):
        oid = _a_closed_job(dana, brazos)
        w6.accept_field_result(dana, oid)
        after_one = metering_models.MeterRead.objects.count()
        try:
            w6.accept_field_result(dana, oid)
        except Exception:
            pass  # a refusal is the expected shape; what matters is the count
        after_two = metering_models.MeterRead.objects.count()

    assert after_two == after_one, "a second acceptance posted a second read"


# ══════════════════════════════════════════════════════════════════════════
# "One refused letter with tracks OQ-376 and NO outbound_messages row"
# ══════════════════════════════════════════════════════════════════════════
def test_j61_leaves_the_letter_REFUSED_with_its_reason_and_filed_NOWHERE(brazos, dana):
    """`J61` step 11 · `BR-WRK-057` · `OQ-376`, **OPEN**.

    The platform's message-source vocabulary is a CONSTANT and `connection` is
    not in it, so the queue refuses the *your service is live* letter. Three
    things are asserted and the third is the one that matters:

      1. the acceptance REPORTS the refusal — `queued: False` with a reason,
         never a tick over a send that did not happen (hard-won law 1);
      2. it names the question it is waiting on;
      3. **no `outbound_messages` row exists at all** — and in particular none
         filed as `notice`, which is the tempting fix and would put a connect
         letter among the dunning notices in every monthly report.
    """
    with tenant_ctx(brazos):
        before = notification_models.OutboundMessage.objects.count()
        oid, _build = _a_closed_job_on_a_build(dana, brazos)
        result = w6.accept_field_result(dana, oid)
        after = notification_models.OutboundMessage.objects.count()
        kinds = set(
            notification_models.OutboundMessage.objects.values_list("source_type", flat=True)
        )

    letter = result.get("communication") or {}
    assert letter.get("queued") is False, f"the acceptance claimed a letter it did not send: {letter}"
    # ⚠ THE REASON IS REPORTED RATHER THAN SWALLOWED. Which key carries it
    # depends on WHY it was refused, so this asserts that SOMETHING says so.
    assert letter.get("unavailable") or letter.get("tracks"), letter
    assert letter.get("tracks") == "OQ-376", (
        f"the refusal does not name the question it waits on: {letter}"
    )
    # The absence, paired with the fact that the acceptance really happened —
    # otherwise "no message was written" is what a failed acceptance looks like.
    assert after == before, f"{after - before} message row(s) were written for a refused letter"
    assert "connection" not in kinds
    with tenant_ctx(brazos):
        assert work_tables.WorkOrder.objects.get(id=oid).accepted_at is not None


def test_j61_the_tempting_fix_is_asserted_as_an_ABSENCE_by_name(brazos, dana):
    """*The tempting fix — sending it as `notice` — makes the test FAIL.*

    ⚠ **THIS IS A DIFFERENT ASSERTION FROM "no row was written", AND IT IS THE
    ONE THAT SURVIVES `OQ-376` BEING ANSWERED.** The day the ruling lands a row
    WILL be written, and the only thing standing between a correct letter and a
    silently wrong monthly report is that its kind is not `notice`. So the
    check is on the KIND, and it is written now, while the answer is still
    open, because afterwards nobody will think to add it.
    """
    with tenant_ctx(brazos):
        oid, _build = _a_closed_job_on_a_build(dana, brazos)
        w6.accept_field_result(dana, oid)
        misfiled = notification_models.OutboundMessage.objects.filter(
            source_type="notice", source_id=oid
        ).count()

    assert misfiled == 0, "the *your service is live* letter was filed as a disconnect notice"


# ══════════════════════════════════════════════════════════════════════════
# ISOLATION — hard rule 1
# ══════════════════════════════════════════════════════════════════════════
def test_j61_leaves_lone_star_ridges_queue_EMPTY(brazos, lonestar, dana, erin):
    """`J61` step 14 — *its `Work-009` is empty*.

    ⚠ **PAIRED WITH THE POSITIVE, BECAUSE AN EMPTY QUEUE IS ALSO WHAT A BROKEN
    SELECTOR LOOKS LIKE.** Brazos Bend's queue must hold the job in the same
    breath that Lone Star's does not.
    """
    with tenant_ctx(brazos):
        oid = _a_closed_job(dana, brazos)
        mine = work_selectors.awaiting_approval(page=1, per=100)
    assert str(oid) in {str(r["id"]) for r in mine["rows"]}, "the job is not on its OWN queue"

    with tenant_ctx(lonestar):
        theirs = work_selectors.awaiting_approval(page=1, per=100)
    assert theirs["rows"] == [], f"Lone Star can see {len(theirs['rows'])} of another utility's jobs"


def test_j61_another_tenant_cannot_accept_this_job(brazos, lonestar, dana, erin):
    """`POST /lone-star-ridge/work-orders/{id}/accept` → **404**, byte-identical
    to an absent row and **before any chain runs** — existence must not leak,
    and a 403 would confirm the order is real."""
    with tenant_ctx(brazos):
        oid = _a_closed_job(dana, brazos)
        before = metering_models.MeterRead.objects.count()

    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as refused:
            w6.accept_field_result(erin, oid)

    assert "404" in str(refused.value) or "not found" in str(refused.value).lower(), refused.value
    # …and the chain really did not run: no read was posted by the attempt.
    with tenant_ctx(brazos):
        assert metering_models.MeterRead.objects.count() == before


# ── Lifecycle ─────────────────────────────────────────────
# packet: J61 (08-qa/01-e2e/journeys/J61-connect-field-accept-live.md) · CR-070 wave L task L5
# generated: 2026-09-05 by the wave-L leftovers lane (L4 desktop + J61/J65 activation)
# checklist: A✔ B=n/a(no screen — the screens are the walkthrough's) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest 06-backend/tests/test_j61_connect_field_accept_live.py
# exceptions: the SERVICE-state and connection-state clauses of J61 step 10 are
#   NOT asserted here — this fixture's order stands on a meter and a premises
#   rather than on the two-service build the journey describes, and building
#   CON-26-0129's four orders inside a test would make this file a seeder. The
#   state transition is proved on the running product by
#   10-scripts/render-checks/cr070-l-the-offline-day-and-the-read.mjs, which
#   reads *Service: Activated* off the drawer after a real press. REPORTED, not
#   quietly skipped.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

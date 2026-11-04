# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 — the payments blueprint's phase 2 (*the counter*),
#          tasks `P2.4` (`payments.counter_session_id`), `P2.5` (its index) and
#          `P2.20` (`counter_sessions.declared_at` / `declared_by` and their
#          CHECK). `P2.20` is not in the drawing — PO ruling 2026-09-23.
# Rules:   CLAUDE.md hard rule 2 · hard rule 4 (this schema change writes no
#          row and lifts no trigger) · hard-won law 7 (every guard proved RED
#          first, and *what would make this pass wrongly*) · hard-won law 14
#          (SQLite cannot answer the questions the `_pg` proof asks) ·
#          B14 rule 43 (`Not counted` is written once) · BR-PAY-1160
# Tests:   this file, plus the two PostgreSQL proofs named below.
# ───────────────────────────────────────────────────────
"""Phase 2's database half, checked where a check can actually run.

WHAT IS NOT HERE, AND WHY — READ THIS BEFORE ADDING TO IT
-----------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`, so this file holds only what SQLite can genuinely answer:
CHECK constraints, field declarations, and facts about the source tree.

**Two things are deliberately absent**, which is hard-won law 14's whole
subject and law 7's *structurally incapable of failing*:

  * **the partial index as an INDEX.** SQLite has partial indexes, but whether
    the PLANNER can use one for `counter_session_id = ?` is a PostgreSQL
    question and the answer decides the whole shape. It is measured, on
    PostgreSQL 16.13 and at 40,000 rows, by
    `10-scripts/cr136_p2_5_till_index_measure.py`. What is asserted here is
    that the index is DECLARED partial, which is the thing a later edit could
    silently change.
  * **the constraint against the real database's NULL semantics.** The cases
    below do run on SQLite and they are worth having — but the guarantee has
    to hold on PostgreSQL, and `DEF-PAY-6207` is in this very table twice
    because a suite that runs on SQLite went green over it. The proof is
    `10-scripts/cr136_p2_20_declared_readback.py`, which was **run against the
    naive spelling of this constraint first and watched accept the bad row**
    before the `close_kind IS NOT NULL` clause went in.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.payments import models as payment_models
from apps.payments.counter_session_models import NOT_COUNTED, CounterSession
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db]

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture()
def centre(brazos):
    """A walk-in counter for the till to be at."""
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="main-office-p2",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def _user(actor):
    """The real `users` row behind a test actor (see phase 0's helper)."""
    return getattr(actor, "user", actor)


def _forced_close(tenant, owner, sealer, centre, **extra):
    """Dana's Monday till, force-closed by somebody else and never counted.

    The PO's own worked case, and the row every `P2.20` case starts from.
    """
    kwargs = dict(
        tenant=tenant,
        owner=_user(owner),
        service_centre=centre,
        opening_float=Decimal("200.0000"),
        opened_at=timezone.now(),
        closed_at=timezone.now(),
        closed_by=_user(sealer),
        close_kind=payment_models.COUNTER_CLOSE_FORCED,
    )
    kwargs.update(extra)
    return CounterSession.objects.create(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════
#  P2.4 — a payment names its till
# ═══════════════════════════════════════════════════════════════════════════


def test_p2_4_the_till_on_a_payment_is_nullable_and_the_ruling_says_so():
    """PO ruling 2026-09-23: *"`payments.counter_session_id` STAYS NULLABLE"*.

    Not a default and not an oversight. **Three of the seven tenders pass
    through a person's hands** — `cash`, `check`, `money_order` — and only
    those three are refused without an open till. `NOT NULL` would refuse
    **every ACH, card, wire and lockbox row in the product**, which is the
    figure that was put to the Product Owner.

    Asserted on the FIELD rather than on a stored NULL, because a row that
    happens to have no till proves nothing about whether one is required.
    """
    field = payment_models.Payment._meta.get_field("counter_session_id")
    assert field.null is True, (
        "PO ruling 2026-09-23 (CR-136-BRC07 §3.4): counter_session_id stays "
        "NULLABLE. A NOT NULL here refuses every ACH, card, wire and lockbox "
        "payment — the four tenders that never touch a counter. The refusal "
        "for the other three is a SERVICE rule at the take-payment endpoint "
        "(BR-SHL-025), never a column constraint."
    )


def test_p2_4_the_till_is_a_plain_uuid_and_the_drawings_reason_for_that_is_wrong():
    """A `UUIDField`, the shape `deposit_batch_id` already uses — `DEF-PAY-6219`.

    ⚠ **THIS CASE PINS THE SHAPE AND DISOWNS THE DRAWING'S REASON FOR IT.**
    The blueprint's outcome sentence is *"A payment names its till. No ORM
    edge into another module"* and it cites `B11 F-3`. **Neither applies:**
    `counter_sessions` is a PAYMENTS table (`apps/payments/
    counter_session_models.py`), so no module boundary is crossed; and B11 F-3
    is about a forward FK breaking migration ORDER, while `counter_sessions`
    has existed since `payments/0031` and this column arrives at `0035`.

    The reason that does hold is the sibling column: `deposit_batch_id`
    answers the same *which container did this money land in* question about
    the same rows and is read beside this one on the same list. **Two columns
    answering one question in two shapes is the two-places-that-can-disagree
    shape this module keeps filing.**

    So a later lane converting this to a ForeignKey is not obviously wrong —
    but it must convert BOTH columns and say so, which is what this message is
    for rather than a silent green.
    """
    field = payment_models.Payment._meta.get_field("counter_session_id")
    assert isinstance(field, models.UUIDField), (
        "P2.4 ships counter_session_id as a plain uuid, the shape "
        "deposit_batch_id already uses. If you are making it a ForeignKey, "
        "read DEF-PAY-6219 first: the blueprint's stated reasons for the uuid "
        "are both false, and the real reason is consistency with "
        "deposit_batch_id — so convert BOTH or neither."
    )
    assert not field.is_relation
    sibling = payment_models.Payment._meta.get_field("deposit_batch_id")
    assert type(field) is type(sibling), (
        "counter_session_id and deposit_batch_id must keep the SAME shape — "
        "they answer the same question about the same rows and are read side "
        "by side on the payments list (P2.8's Source and Batch columns)."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  P2.5 — the till's own list
# ═══════════════════════════════════════════════════════════════════════════


def test_p2_5_the_till_index_exists_and_is_partial():
    """`ix_payments_counter_session`, `WHERE counter_session_id IS NOT NULL`.

    ⚠ **WHAT THIS CASE CANNOT TELL YOU, STATED SO IT IS NOT MISTAKEN FOR
    PROOF:** whether the PostgreSQL planner USES it. That is the question the
    whole shape rests on — a partial index the planner cannot use would look
    thrifty and cost a sequential scan on every page load — and it is measured
    on PostgreSQL 16.13 at 40,000 rows by
    `10-scripts/cr136_p2_5_till_index_measure.py`, including under a GENERIC
    plan, which is where a constant-folding artefact would show up.

    What this case IS for: the predicate is one word away from being deleted
    by a later edit, and nothing else in the suite would notice.
    """
    by_name = {ix.name: ix for ix in payment_models.Payment._meta.indexes}
    index = by_name.get("ix_payments_counter_session")
    assert index is not None, (
        "P2.5's index is gone. The till's running total reads it on every " "payment taken."
    )
    assert index.fields == ["tenant", "counter_session_id"], (
        "tenant first, as every index on this table is — RLS scopes every "
        "read and the tenant is always known."
    )
    assert index.condition == models.Q(counter_session_id__isnull=False), (
        "P2.5's index is PARTIAL on purpose; see payments/0035's docstring "
        "for the measurement. Dropping the predicate is not a tidy-up."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  P2.20 — a late count sits BESIDE the forced close
# ═══════════════════════════════════════════════════════════════════════════


def test_p2_20_the_rulings_worked_case_is_exactly_what_one_row_holds(brazos, dana, marcus, centre):
    """PO ruling 2026-09-23: *"force-closed Monday by the supervisor, declared
    Tuesday by Dana, $12 short… Nothing is erased"*.

    Dana's till is force-closed Monday night uncounted; Tuesday she counts
    **$1,228.00 against $1,240.00 expected — $12.00 short**, reason *"cheque
    stuck to the bag"*. Afterwards **the one row says both things**, which is
    the whole ruling: `close_kind` is still `forced` and `closed_by` is still
    the supervisor, while `declared_by` is Dana.
    """
    with tenant_ctx(brazos):
        declared_at = timezone.now()
        till = _forced_close(
            brazos,
            dana,
            marcus,
            centre,
            declared_at=declared_at,
            declared_by=_user(dana),
            difference=Decimal("-12.0000"),
            note="cheque stuck to the bag",
        )
        till.refresh_from_db()

        # The seal, unchanged — this is the half the rejected option (b) erased.
        assert till.close_kind == payment_models.COUNTER_CLOSE_FORCED
        assert till.closed_by_id == _user(marcus).id
        # The late count, beside it.
        assert till.declared_by_id == _user(dana).id
        assert till.declared_at is not None
        assert till.difference == Decimal("-12.0000")
        # Three roles on one row, and two of them are different people.
        assert till.owner_id == _user(dana).id
        assert till.closed_by_id != till.declared_by_id


def test_p2_20_a_declaration_with_no_name_on_it_is_refused(brazos, dana, marcus, centre):
    """`declared_at` without `declared_by` — a count nobody signed."""
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            _forced_close(brazos, dana, marcus, centre, declared_at=timezone.now())


def test_p2_20_a_name_with_no_date_is_refused(brazos, dana, marcus, centre):
    """`declared_by` without `declared_at` — the other half missing.

    Both directions, because a pairing constraint written one-way is a check
    that cannot fail on half its subject.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            _forced_close(brazos, dana, marcus, centre, declared_by=_user(dana))


def test_p2_20_an_OPEN_till_cannot_be_declared(brazos, dana, centre):
    """⚠ **`DEF-PAY-6207`'s SHAPE, AND THE REASON THE CONSTRAINT IS SPELLED THE
    WAY IT IS.**

    `close_kind` is NULL on every till that is still open. A CHECK refuses a
    row only when its expression is FALSE and **PASSES when it is NULL**, so a
    branch written `close_kind = 'forced'` reads NULL here, the chain becomes
    `FALSE OR NULL` = NULL, **and a drawer declared as counted before it was
    ever sealed is accepted** — on the *which tills are open* screen, with a
    count against it.

    That is the third time this exact fault has been reachable in this one
    table. The branch therefore begins `close_kind IS NOT NULL`, and the
    spelling without it was **run against a real PostgreSQL 16 and watched
    accept this row** before the clause went in
    (`10-scripts/cr136_p2_20_declared_readback.py`, section 1c).
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            CounterSession.objects.create(
                tenant=brazos,
                owner=_user(dana),
                service_centre=centre,
                opening_float=Decimal("200.0000"),
                opened_at=timezone.now(),
                declared_at=timezone.now(),
                declared_by=_user(dana),
            )


def test_p2_20_a_counted_till_cannot_be_declared(brazos, dana, centre):
    """A counted till was already counted — there is nothing to declare.

    PO ruling 2026-09-23: *"a counted till has already been counted and a
    system till is nobody's, so neither can be declared"*.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            _forced_close(
                brazos,
                dana,
                dana,
                centre,
                close_kind=payment_models.COUNTER_CLOSE_COUNTED,
                declared_at=timezone.now(),
                declared_by=_user(dana),
            )


def test_p2_20_a_system_till_cannot_be_declared(brazos, dana):
    """A system till is nobody's, so nobody can declare it.

    ⚠ Built to satisfy `ck_counter_sessions_system_is_nobodys` in full — no
    owner, no centre, no closer, a zero float and a `system_day` — so that
    **only** `ck_counter_sessions_declared_together` can refuse it. A row a
    neighbouring constraint would have refused anyway proves nothing about
    this one.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            CounterSession.objects.create(
                tenant=brazos,
                owner=None,
                service_centre=None,
                system_day=timezone.now().date(),
                opening_float=Decimal("0"),
                opened_at=timezone.now(),
                closed_at=timezone.now(),
                closed_by=None,
                close_kind=payment_models.COUNTER_CLOSE_SYSTEM,
                declared_at=timezone.now(),
                declared_by=_user(dana),
            )


def test_p2_20_a_forced_close_nobody_has_counted_is_still_lawful(brazos, dana, marcus, centre):
    """The `Not counted` row itself — sealed, never declared.

    A fix that refuses everything is not a fix, and this is the row the whole
    *"a supervisor can see the three tills nobody counted"* screen is made of.
    """
    with tenant_ctx(brazos):
        till = _forced_close(brazos, dana, marcus, centre)
        till.refresh_from_db()
        assert till.declared_at is None and till.declared_by_id is None


def test_p2_20_close_kind_still_holds_exactly_three_values():
    """⚠ **A FOURTH VALUE `declared` WAS PUT TO THE PO AND REJECTED.**

    PO ruling 2026-09-23 records why: it *"would move
    `ck_counter_sessions_close_kind`, `COUNTER_CLOSE_KINDS`,
    `COUNTER_CLOSE_KINDS_BY_A_PERSON` and three screens, to record a fact that
    is not a way of SEALING a till at all"*. A late count sits BESIDE the
    forced close, never over it.
    """
    assert payment_models.COUNTER_CLOSE_KINDS == ("counted", "forced", "system"), (
        "close_kind does not move. A fourth value `declared` was rejected by "
        "the PO on 2026-09-23 — see CR-136-BRC07 §3.2."
    )
    assert payment_models.COUNTER_CLOSE_KINDS_BY_A_PERSON == ("counted", "forced")


# ═══════════════════════════════════════════════════════════════════════════
#  `Not counted` — one expression, four readers (B14 rule 43)
# ═══════════════════════════════════════════════════════════════════════════


def test_not_counted_is_the_expression_the_ruling_names():
    """`close_kind = 'forced' AND declared_at IS NULL`, and nothing else.

    It needs no third term because `ck_counter_sessions_declared_together`
    makes every declared row a forced one — which is why the constraint and
    this expression are written in the same commit.
    """
    assert NOT_COUNTED == models.Q(
        close_kind=payment_models.COUNTER_CLOSE_FORCED, declared_at__isnull=True
    )


def test_not_counted_is_written_once_and_nobody_has_re_spelled_it():
    """⚠ **THE GUARD FOR B14 RULE 43, AND IT FIRES ON THE DAY A LANE RE-SPELLS
    THE RULE RATHER THAN IMPORTING IT.**

    PO ruling 2026-09-23 names four readers of this one expression — screen
    `3·1 Counters`' list, its filter chip, `P2.11`'s notice to the supervisor,
    and phase 2's own done-when — and says it must be written once. **None of
    the four is built yet**, so there is nothing to assert about wiring; what
    CAN be asserted is that no second spelling has appeared.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2), because a
    source-text scan is exactly the kind of check that reports zero over a
    scope it silently excludes: a lane writing the rule in a different ORDER
    (`declared_at__isnull=True, close_kind=...`), across two statements, in
    raw SQL, or in TypeScript. The first is caught — both orders are searched.
    **The rest are not, and that is stated rather than left implied.** The
    front end is not expected to be a fifth speller at all: the filter chip
    sends a query parameter and the server answers with this expression.
    """
    home = "apps/payments/counter_session_models.py"
    # Both orders of the pair, on one line — the two ways a lane would type it.
    spellings = (
        re.compile(r"close_kind\s*=\s*COUNTER_CLOSE_FORCED\s*,\s*declared_at__isnull\s*=\s*True"),
        re.compile(r"declared_at__isnull\s*=\s*True\s*,\s*close_kind\s*=\s*COUNTER_CLOSE_FORCED"),
        re.compile(r"close_kind\s*=\s*[\"']forced[\"']\s*,\s*declared_at__isnull\s*=\s*True"),
    )
    offenders = []
    for path in (BACKEND / "apps").rglob("*.py"):
        relative = path.relative_to(BACKEND).as_posix()
        if relative == home:
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in spellings):
            offenders.append(relative)

    assert not offenders, (
        "`Not counted` is written once, in " + home + " as NOT_COUNTED — PO "
        "ruling 2026-09-23 and B14 rule 43. These files spell it out again "
        "instead of importing it: " + ", ".join(sorted(offenders)) + ". Import "
        "NOT_COUNTED; a second spelling is how the list, the filter chip and "
        "the supervisor's notice start disagreeing about which tills nobody "
        "counted."
    )


def test_the_postgres_proofs_this_file_defers_to_actually_exist():
    """⚠ **A `Tests:` LINE POINTING AT A FILE THAT DOES NOT EXIST SAYS *THIS IS
    COVERED* AND THE CASE NEVER GETS WRITTEN (`DEF-RBS-4335`, `DEF-PAY-6205`).**

    This file's docstring sends the reader to two scripts for everything
    SQLite cannot answer. `DEF-PAY-6205` is exactly this failure one table
    along — `counter_session_models.py` named a test file that had never
    existed, for days, and `G116` was red on it. So the pointers are asserted
    rather than trusted.
    """
    for script in (
        "10-scripts/cr136_p2_20_declared_readback.py",
        "10-scripts/cr136_p2_5_till_index_measure.py",
    ):
        assert (BACKEND.parent / script).exists(), (
            f"{script} is named as the proof for something this suite cannot "
            "answer, and it is not there. Either write it or stop citing it."
        )

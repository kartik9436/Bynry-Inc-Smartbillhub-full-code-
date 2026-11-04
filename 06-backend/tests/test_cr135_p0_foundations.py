# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, tasks `P0.15` (the
#          constraint and backfill cases) and the half of `P0.2` that can be
#          checked at merge rather than at 2am.
# Rules:   CLAUDE.md hard rule 2 (a NEW money column declares FOUR decimals) ·
#          hard rule 4 (financial immutability) · hard-won law 7 (every guard
#          proved RED first, and *what would make this pass wrongly*) ·
#          hard-won law 2's mirror (a hold ships with the test that fires when
#          it expires) · BR-SHL-025 (server-side enforcement)
# Tests:   this file. `P0.14` and the re-derivation's real path are in
#          test_cr135_p0_rls_pg.py — see WHAT IS NOT HERE, below.
# ───────────────────────────────────────────────────────
"""Phase 0's foundations, checked where a check can actually run.

WHAT IS NOT HERE, AND WHY — READ THIS BEFORE ADDING TO IT
-----------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. So this file holds only what SQLite can genuinely answer:
CHECK constraints, a partial unique index, and facts about the source tree.

**Three things are deliberately absent because SQLite would pass them by
vacuum**, which is CLAUDE.md hard-won law 14's whole subject and law 7's
*structurally incapable of failing*:

  * **row-level security** — SQLite has none, so a policy assertion here is a
    green test proving nothing. `P0.14` is `test_cr135_p0_rls_pg.py`.
  * **the immutability trigger** — SQLite has no triggers, which is exactly how
    `payments/0029`'s backfill was green on every machine here and blocked the
    Product Owner's release (`DEF-PAY-6165`).
  * **`payments/0030`'s re-derivation as it really runs** — the per-tenant pass
    only exists on PostgreSQL. Its cases are in the `_pg` file, against the
    real freeze and the real policy.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.payments import models as payment_models
from apps.payments.counter_session_models import CounterSession
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = [pytest.mark.django_db]

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture()
def centre(brazos):
    """A walk-in counter for the till to be at.

    `tenancy.ServiceCentre` is published content — *"where a customer can walk
    in"* — and the blueprint is explicit that a counter is not a location:
    *"One centre can have three windows, each with its own drawer."* So the
    session names this and puts no operational field on it.
    """
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="main-office",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def a_payment_row(tenant, actor):
    """One `payments` row, through the real service.

    ⚠ **THROUGH `record_payment` RATHER THAN `Payment.objects.create`, AND
    THAT IS THE POINT OF THE THREE CASES BELOW.** What they assert is that the
    CHECKs bind the path the product actually writes through, not a row a test
    hand-built to suit itself.
    """
    from apps.payments import services

    account = an_account(actor, tenant, account_no=f"A-{uuid.uuid4().hex[:6]}")
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal("142.1800"),
        posted_at=timezone.now(),
        idempotency_reference=uuid.uuid4(),
    )
    # ⚠ `RecordedPayment` carries `payment_id`, not the row. The first draft of
    # this helper read `.payment` and every case using it errored with
    # `AttributeError: 'RecordedPayment' object has no attribute 'payment'` —
    # which is the honest failure, and is why the helper is exercised by cases
    # that ASSERT rather than by one that only calls it.
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


def _user(actor):
    """The real `users` row behind a test actor.

    ⚠ `staff_actor` returns a `SimpleNamespace` carrying the role AND the row
    (`.user`), because most services want the actor and not the record. A
    foreign key wants the record, so every one of these fixtures says `.user`
    — the first draft did not and eight cases failed with *"CounterSession.owner
    must be a User instance"*, which is Django refusing to guess.
    """
    return getattr(actor, "user", actor)


def _open_a_till(tenant, owner, centre, *, float_amount="200.0000"):
    return CounterSession.objects.create(
        tenant=tenant,
        owner=_user(owner),
        service_centre=centre,
        opening_float=Decimal(float_amount),
        opened_at=timezone.now(),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  P0.4 / P0.15 — one open till per person, and the half that is easy to miss
# ═══════════════════════════════════════════════════════════════════════════


def test_p0_4_a_person_may_open_a_till(brazos, dana, centre):
    """The green case, first — a check that refuses everything is not a check.

    CLAUDE.md hard-won law 7: *ask what would make this pass wrongly*. The
    mirror question for a constraint is what would make it FAIL wrongly, and a
    partial unique index written with the predicate inverted would refuse the
    very first till. This is the case that separates the two.
    """
    with tenant_ctx(brazos):
        till = _open_a_till(brazos, dana, centre)
    assert till.closed_at is None
    assert till.close_kind is None
    assert till.opening_float == Decimal("200.0000")


def test_p0_4_the_database_refuses_a_second_OPEN_till(brazos, dana, centre):
    """`P0.4`'s outcome, and it is stated as a contrast on purpose.

    *"The database refuses a second open till — not a service check that a
    second caller can skip."* Two terminals at one counter can race a
    `SELECT … then INSERT`; they cannot race a unique index.
    """
    with tenant_ctx(brazos):
        _open_a_till(brazos, dana, centre)
        with pytest.raises(IntegrityError), transaction.atomic():
            _open_a_till(brazos, dana, centre)


def test_p0_15_a_second_CLOSED_till_is_permitted(brazos, dana, centre):
    """**The easy-to-miss half, named in the drawing and in `P0.15`.**

    Without `WHERE closed_at IS NULL` the index would let a clerk open a till
    exactly ONCE in the life of the utility — a bug nobody would find until a
    second shift, by which time the index is in production.

    The second row is also the PO's forced close: Dana's Monday till, sealed by
    somebody else, and then Dana's own Tuesday till after it.
    """
    with tenant_ctx(brazos):
        monday = _open_a_till(brazos, dana, centre)
        monday.closed_at = timezone.now()
        monday.closed_by = _user(dana)
        monday.close_kind = payment_models.COUNTER_CLOSE_COUNTED
        monday.save()

        tuesday = _open_a_till(brazos, dana, centre, float_amount="150.0000")
        tuesday.closed_at = timezone.now()
        tuesday.closed_by = _user(dana)
        tuesday.close_kind = payment_models.COUNTER_CLOSE_FORCED
        tuesday.save()

        assert CounterSession.objects.filter(owner=_user(dana), closed_at__isnull=False).count() == 2
        assert CounterSession.objects.filter(owner=_user(dana), closed_at__isnull=True).count() == 0


def test_p0_15_two_people_may_each_have_an_open_till(brazos, dana, marcus, centre):
    """The index is keyed on (tenant, owner) and not on (tenant, centre).

    Three windows at one counter is the blueprint's own example, so an index
    that accidentally serialised a whole office would be wrong in a way the
    single-person cases above cannot see.
    """
    with tenant_ctx(brazos):
        _open_a_till(brazos, dana, centre)
        _open_a_till(brazos, marcus, centre)
        assert CounterSession.objects.filter(closed_at__isnull=True).count() == 2


# ═══════════════════════════════════════════════════════════════════════════
#  P0.3 — the PO's ruling on the forced close, held by the schema
# ═══════════════════════════════════════════════════════════════════════════


def test_p0_3_a_forced_close_records_who_actually_sealed_it(brazos, dana, marcus, centre):
    """PO ruling 2026-09-22: *"(b) A System Admin can close it, recorded as a
    forced close"*.

    The worked case: Dana takes **$1,240 in cheques** on Monday, goes home
    without closing, and is off sick on Tuesday. Somebody else seals the
    drawer, and the record must keep the two people apart for ever — which is
    the whole reason there is a `close_kind` beside a `closed_by` rather than a
    quiet close in the owner's name.
    """
    with tenant_ctx(brazos):
        till = _open_a_till(brazos, dana, centre)
        till.closed_at = timezone.now()
        till.closed_by = _user(marcus)
        till.close_kind = payment_models.COUNTER_CLOSE_FORCED
        till.counted_totals = None  # sealed, NOT counted — p057 keeps them apart
        till.save()

        till.refresh_from_db()
        assert till.owner_id == _user(dana).id
        assert till.closed_by_id == _user(marcus).id
        assert till.closed_by_id != till.owner_id
        assert till.close_kind == "forced"


def test_p0_3_a_till_cannot_be_sealed_with_no_record_of_how(brazos, dana, centre):
    """`ck_counter_sessions_closed_together`, and it is the ruling given teeth.

    A row with `closed_at` set and `close_kind` null is a forced close that has
    become indistinguishable from a normal one — the exact outcome the PO's
    ruling exists to prevent.

    ⚠ **THIS CASE IS RED ON THE BRANCH AND IT IS RIGHT — `DEF-PAY-6207`, filed
    2026-09-22, NOT FIXED HERE.** `payments/0033` (`P0.6`, landed the same day)
    replaced the two-branch constraint with a three-branch one, and the new
    branch begins `close_kind = 'system'`. **A CHECK refuses a row only when its
    expression is FALSE and PASSES when it is NULL** — so with `close_kind`
    NULL that branch reads `NULL = 'system'`, which is NULL, and the whole
    chain becomes `FALSE OR FALSE OR NULL` = NULL. The row is accepted.

    Measured both ways rather than reasoned: **PostgreSQL 16.13 accepted an
    INSERT of exactly this shape**, and a hand-built SQLite probe of the same
    expression accepted it too. So the guarantee is off on the real database as
    well as in the suite.

    **The case is deliberately not weakened to make the suite green.** The cure
    is one clause in `payments/0033`'s own constraint — begin the system branch
    with `close_kind IS NOT NULL AND` — and that migration belongs to another
    lane that was landing it while this was measured.
    """
    with tenant_ctx(brazos):
        till = _open_a_till(brazos, dana, centre)
        till.closed_at = timezone.now()
        with pytest.raises(IntegrityError), transaction.atomic():
            till.save()


def test_p0_3_there_is_no_third_close_kind(brazos, dana, centre):
    """`auto` is refused BY NAME, and that is a decision rather than an omission.

    The option *"the till closes itself overnight with no count"* was put to
    the Product Owner on 2026-09-22 as a hole in the money trail and was not
    chosen. A value the column can hold is a value some path can write
    (`REFUND_METHODS`' own note, one module along), so the schema does not
    hold it.
    """
    with tenant_ctx(brazos):
        till = _open_a_till(brazos, dana, centre)
        till.closed_at = timezone.now()
        till.closed_by = _user(dana)
        till.close_kind = "auto"
        with pytest.raises(IntegrityError), transaction.atomic():
            till.save()


def test_p0_3_the_opening_float_is_four_decimals_not_six(brazos, dana, centre):
    """⚠ **THE DRAWING SAYS `NUMERIC(18,6)` AND THE SIGNED RULE SAYS FOUR.**

    `P0.3`, verbatim: *"opening float at NUMERIC(18,6)"*. CLAUDE.md hard rule
    2, PO re-sign 2026-08-22, verbatim: *"We already confirmed this - MOney 4
    decimal, percentage 6 decimal , display both 2 decimal"*. Existing `18,6`
    columns stay lawful containers; the rule governs what a NEW column
    declares.

    Asserted on the FIELD rather than on a stored value, because a `Decimal`
    round-trip can look right on SQLite while the column is wrong — which is
    the divergence this test exists to keep visible to the next reader.
    """
    field = CounterSession._meta.get_field("opening_float")
    assert (field.max_digits, field.decimal_places) == (18, 4), (
        "CLAUDE.md hard rule 2: a NEW money column declares FOUR decimals. "
        "The blueprint's P0.3 says NUMERIC(18,6) and the signed rule wins — "
        "see the decision log of 2026-09-22 and counter_session_models.py."
    )
    assert CounterSession._meta.get_field("difference").decimal_places == 4


def test_p0_3_a_negative_opening_float_is_refused(brazos, dana, centre):
    """A drawer that starts owing money. Same shape and reason as
    `ck_counter_receipts_amount_positive` one table along."""
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            _open_a_till(brazos, dana, centre, float_amount="-0.0001")


# ═══════════════════════════════════════════════════════════════════════════
#  P0.1 / P0.2 — the source column's CHECK
# ═══════════════════════════════════════════════════════════════════════════


def test_p0_1_the_three_values_are_the_idempotency_key_s_own_three():
    """The map, pinned. If these ever drift the column and the key disagree
    about one fact, which is the *two places that can disagree* shape
    `payments/0029` was written to close."""
    from apps.payments import idempotency

    assert payment_models.PAYMENT_ORIGINS == (
        idempotency.SOURCE_ENTRY,
        idempotency.SOURCE_WEBHOOK,
        idempotency.SOURCE_IMPORT,
    )


def test_p0_2_a_fourth_origin_value_fails_loudly(brazos, dana, marcus):
    """`P0.2`'s outcome: *"a row matching none of the three fails loudly rather
    than defaulting."*

    This is the half of `P0.2` that is served. `'lockbox'` is a plausible
    fourth word and it is refused by the database, from every path, rather
    than landing as an origin no filter finds and no reconciliation classifies.
    """
    with tenant_ctx(brazos):
        payment = a_payment_row(brazos, marcus)
        payment.origin = "lockbox"
        with pytest.raises(IntegrityError), transaction.atomic():
            payment.save(update_fields=["origin"])


def test_p0_2_a_null_origin_is_lawful_and_says_nobody_told_us(brazos, marcus):
    """⚠ **`P0.2` ASKS FOR NOT NULL AND IT IS DELIBERATELY NOT BUILT.**

    `payments/0029` argues the column must stay nullable because *"a fifth
    creation site added by a lane that has not read this file would fail its
    INSERT"*. **That site already exists**, measured:
    `apps/integrations/management/commands/seed_partner_morning.py:232`
    bulk-creates `Payment` rows and passes no origin — a SIXTH site where that
    docstring counts four (`DEF-PAY-6196`).

    So a NULL is lawful and means *nobody told us*, which is a real answer. A
    DEFAULT would turn it into a claim, and CLAUDE.md hard-won law 3 says the
    unsafe option must be the one you type.
    """
    with tenant_ctx(brazos):
        payment = a_payment_row(brazos, marcus)
        payment.origin = None
        payment.origin_is_derived = False
        payment.save(update_fields=["origin", "origin_is_derived"])
        payment.refresh_from_db()
        assert payment.origin is None


def test_p0_2_an_inference_of_nothing_is_refused(brazos, marcus):
    """`ck_payments_origin_derived_needs_a_value` — the PO's ruling kept honest.

    *TRUE* means *we inferred this*. With no origin at all there is nothing to
    have inferred, so `origin IS NULL AND origin_is_derived` is a row claiming
    to have guessed nothing — refused, rather than left as a state every
    report would have to learn to ignore.
    """
    with tenant_ctx(brazos):
        payment = a_payment_row(brazos, marcus)
        payment.origin = None
        payment.origin_is_derived = True
        with pytest.raises(IntegrityError), transaction.atomic():
            payment.save(update_fields=["origin", "origin_is_derived"])


def test_p0_2_a_non_null_webhook_key_does_NOT_mean_the_money_came_over_a_wire():
    """⚠ **THE BLUEPRINT'S FIRST DERIVATION IS WRONG AND THIS IS WHY.**

    `P0.2`: *"non-null `webhook_key` → digital"*. Measured on a PostgreSQL 16
    clone of the demo database on 2026-09-22, inside the tenant context:
    **74 payments, 74 with a non-null `webhook_key`, 74 of them prefixed
    `entry|`.** That rule misclassifies 74 of 74.

    The mechanism, asserted here so it cannot be re-learned from data: the
    column is named for webhooks and holds the key for ALL THREE sources.
    """
    from apps.payments import idempotency

    entry_key = idempotency.inbound_payment_key(
        source=idempotency.SOURCE_ENTRY, reference="3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10"
    )
    assert entry_key.startswith("entry|"), (
        "`webhook_key` holds a key for every source, not only for webhooks — "
        "so a non-null value says nothing about where the money came from. "
        "This is why payments/0030 keeps the key-PREFIX derivation."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  The two holds, each with the test that fires when it expires
# ═══════════════════════════════════════════════════════════════════════════

#: The Payment creation sites, as measured on 2026-09-22. `payments/0029`'s own
#: `Impacts:` line says FOUR; there are six, and the sixth writes no origin.
CREATION_SITES_WITH_AN_ORIGIN = {
    "apps/payments/services.py",
    "apps/payments/transfer.py",
    "apps/payments/reversal.py",
    "apps/payments/counter_receipts.py",
}
CREATION_SITES_WITHOUT_ONE = {
    # DEF-PAY-6196 — a demo seeder, so the rows it writes are not customer
    # money; it is here because it is the live proof that NOT NULL would have
    # failed, and because a seventh site must not be added silently.
    "apps/integrations/management/commands/seed_partner_morning.py",
}

#: ⚠ **TWO THINGS HERE ARE LOAD-BEARING AND THE FIRST DRAFT HAD NEITHER.**
#:
#:   * **No `\s*` before the paren.** An instantiation is `Payment(`; a
#:     PROSE MENTION is `Payment (`. The first draft allowed the space and
#:     matched `apps/payments/models.Payment (payments/0017's …` — a sentence
#:     in `cheques.py`'s Trace header — reporting a file that creates nothing
#:     as a creation site.
#:   * **Comments are stripped before the scan**, for the same reason: every
#:     file in this module names `models.Payment` in its header.
#:
#: That first draft is worth the four lines it costs to record, because this
#: test's own docstring argues against regexes over source and then shipped one
#: that could not tell code from prose — CLAUDE.md hard-won law 7's *looking at
#: the wrong thing*, committed by the case written to avoid it. **It was caught
#: by running the scan by hand and reading the seven matches**, which is the
#: only thing that finds this class.
_CREATES_A_PAYMENT = re.compile(
    r"(?:\w*models|payment_models)\.Payment(?:\.objects\.(?:create|bulk_create))?\("
)


def test_p0_2_every_payment_creation_site_states_an_origin():
    """**The *"no nulls"* half of `P0.2`, enforced at MERGE instead of at 2am.**

    A `NOT NULL` column turns a forgotten write into a production INSERT
    failure. This turns the same mistake into a red test on the branch, and it
    is the trade `payments/0030`'s docstring argues for rather than assumes.

    ⚠ **IT IS AN INVENTORY, NOT A PATTERN MATCH, AND THAT IS ON PURPOSE.** A
    regex over source can only ask *does the word `origin` appear near the
    word `Payment`*, which is the *looking at the wrong thing* shape. This
    asks the question that matters — **has the SET of places that create a
    payment changed** — and fails naming the new one, so whoever added it
    decides what its origin is instead of inheriting a NULL.
    """
    found = set()
    for path in sorted(BACKEND.glob("apps/**/*.py")):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            # Strip the comment before matching — every file in this module
            # names `models.Payment` in its Trace header, and the first draft
            # of this scan reported one of those sentences as a creation site.
            if _CREATES_A_PAYMENT.search(line.split("#", 1)[0]):
                found.add(str(path.relative_to(BACKEND)))
                break

    known = CREATION_SITES_WITH_AN_ORIGIN | CREATION_SITES_WITHOUT_ONE
    new = found - known
    assert not new, (
        "A new place creates `payments` rows: "
        + ", ".join(sorted(new))
        + ". Decide its `origin` (apps/payments/models.PAYMENT_ORIGINS) and add it "
        "to this inventory. `payments.origin` is deliberately NULLable — see "
        "payments/0030 — so a forgotten write is silent in production and this "
        "test is the only thing that asks."
    )
    gone = known - found
    assert not gone, (
        "These no longer create payments and the inventory is stale: " + ", ".join(sorted(gone))
    )


def test_p0_3_the_force_close_role_check_has_no_service_to_sit_on_yet():
    """⚠ **A HOLD, WITH THE TEST THAT FIRES WHEN IT EXPIRES — CLAUDE.md
    hard-won law 2's mirror, in the same commit as the hold.**

    Phase 0 builds the TABLE and no service (PO 2026-09-22: *"go as per phase
    0 ; we are going to implement all phases one by one"*). So the two rules
    that attach to a forced close have nothing to sit on yet:

      * it is a money action, so hard rule 7 applies and it writes `audit_log`;
      * who may do it is `@require_role(SYSTEM_ADMIN)` **at the service** —
        `BR-SHL-025`, because a button hidden from a Billing Clerk is not a
        guarantee.

    **This test asserts the ABSENCE.** The day somebody writes a force-close
    entry point it goes RED and names both requirements, which is the whole
    point: on 2026-09-05 the customer portal had two working doors out of
    eight because every hold there was a promise nobody was keeping.
    """
    force_close = []
    for path in sorted(BACKEND.glob("apps/payments/**/*.py")):
        if "migrations" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^\s*def (force_close\w*|\w*force_close)\s*\(", text, re.M):
            force_close.append(f"{path.relative_to(BACKEND)}:{match.group(1)}")

    assert not force_close, (
        "A force-close entry point now exists: "
        + ", ".join(force_close)
        + ". The hold has expired, so before deleting this test confirm BOTH: "
        "(1) it carries @require_role(SYSTEM_ADMIN) — BR-SHL-025, server-side "
        "enforcement is THE enforcement; (2) it writes `audit_log` — CLAUDE.md "
        "hard rule 7, a forced close is a money action. PO ruling 2026-09-22, "
        '"(b) A System Admin can close it, recorded as a forced close".'
    )


# ═══════════════════════════════════════════════════════════════════════════
#  P0.16 — migration forwards and backwards
# ═══════════════════════════════════════════════════════════════════════════


def test_p0_16_every_phase_0_migration_is_in_the_reversibility_proof():
    """`P0.16`: *"Migration forwards and backwards. Migration ordering is a 🔒
    sensitive path."*

    The proof itself is `10-scripts/cr135_migrations_forwards_and_backwards.py`
    — it applies, REVERSES and re-applies phase 0's migrations against a private
    PostgreSQL clone, because reversing a migration alters the database the test
    process is connected to and a pytest case doing that would leave every
    sibling case in the run looking at a schema that no longer matches the
    models.

    ⚠ **WHAT THIS CASE ADDS IS THE THING A SCRIPT CANNOT DO: NOTICE A NEW
    MIGRATION.** A reversibility proof that names four migrations is true of
    those four for ever and says nothing about the fifth. This compares the
    script's `PHASE_0` list against the migrations actually on disk, so a phase
    0 migration that lands without being added to the proof turns the ordinary
    suite RED on the day it lands.

    ⚠ **THIS REPLACED A HOLD, AND THE HOLD EXPIRED WITHIN THE HOUR.** Until
    `payments/0033` landed there was no deposit re-key to reverse, so this case
    asserted `uq_deposit_batches_day_method` was still on `DepositBatch` and
    said in its own message what to do when it left. It left — `P0.6` landed
    while this lane was proving the other three — and the message was followed:
    `0033` is in `PHASE_0` and the script reverses it. The replacement key is
    covered by `test_cr135_p06_deposit_batch_rekey.py::
    test_p06_the_day_x_method_key_is_gone_and_the_till_x_tender_key_is_there`,
    which is why it is not re-asserted here.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, stated because a check you cannot
    describe a false pass for is a check you do not understand: a phase 0
    migration whose FILENAME does not contain `cr135`. Every one of the four
    does, and the change request is the only thing phase 0 ships under — but a
    lane numbering the next one differently would not be caught here. It would
    be caught by the script's own STEP 0, which refuses to run unless every
    migration it names is applied AND every object it expects is present.
    """
    proof = (BACKEND.parent / "10-scripts/cr135_migrations_forwards_and_backwards.py").read_text()
    named = set(re.findall(r'"(\d{4}_[a-z0-9_]*cr135[a-z0-9_]*)"', proof))

    on_disk = {
        path.stem
        for path in (BACKEND / "apps/payments/migrations").glob("0*.py")
        if "cr135" in path.stem
    }

    assert on_disk, "no cr135 migration found in apps/payments/migrations — the glob is wrong"
    missing = on_disk - named
    assert not missing, (
        "These phase 0 migration(s) are not named in PHASE_0 in "
        "10-scripts/cr135_migrations_forwards_and_backwards.py, so nothing has "
        "ever reversed them: " + ", ".join(sorted(missing)) + ". Migration "
        "ordering is a CLAUDE.md 🔒 sensitive path — add them to that list, run "
        "the script against a private clone, and check the reverse actually "
        "removes what the migration added rather than reporting success and "
        "changing nothing."
    )

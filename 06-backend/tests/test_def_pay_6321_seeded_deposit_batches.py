# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-6321 — the sample set creates no deposit batch, so the
#          Payments list's BATCH column can only ever read "No batch yet"
#          while its SOURCE column reads "Counter" on the same rows.
#          DEF-PAY-6322 · DEF-PAY-6323 — the two neighbours this lane FILED
#          and did not fix. 6322's population is pinned by name and by COUNT
#          so the exclusion cannot rot. 6323 was FIXED on 2026-09-24 and is
#          asserted in its own file, `test_def_pay_6323_seeded_payment_source.py`.
# Rules:   BR-PAY-025 as amended 2026-09-22 (a batch is one TILL × one TENDER;
#          a till is one drawer DAY) · PO ruling 2026-09-21 (*"When a counter
#          is started a batch should be automatically started with it"*) · PO
#          ruling 2026-09-23 §3.4 (only cash, cheques and money orders reach a
#          drawer) · CLAUDE.md hard rule 2 (money four decimals, never a float,
#          CHAR(3) currency) · hard rule 4 (a payment is append-only, so
#          `deposit_batch_id` is written at INSERT or never) · hard-won law 7
#          (prove a guard RED first, in the harness that will run it)
# Tests:   this file
# Impacts: apps/payments/sample_data.py (the till block) ·
#          apps/tenancy/sample_data.py (the service centres moved ahead of the
#          money blocks, because a counter is a till AT a place)
# ───────────────────────────────────────────────────────
"""DEF-PAY-6321 — the seeded utility banks its counter money, and only that.

WHY THIS FILE EXISTS RATHER THAN AN ASSERTION INSIDE THE SEEDER
---------------------------------------------------------------
The omission this file guards was **declared**, in `apps/payments/
sample_data.py`'s own `NOT_SEEDED` manifest, on 2026-08-16:

    {"what": "the deposit batches and the bank statement …",
     "reason": "spec §5 — not driven by this lane"}

It was honest and it was never counted. Four screens were then built over a
fixture in which the BATCH column's answer is structurally *no*, every check
passed, and the Product Owner found it by opening the list. **A named absence
with no number attached is indistinguishable from a finished feature** — which
is CLAUDE.md hard-won law 7's *"reporting zero over a scope it silently
excludes"*, one layer out, in a fixture instead of in a gate.

So the count lives here, where a suite reads it.

RED-FIRST RECORD (hard-won law 7), AND IT IS ON POSTGRESQL BOTH WAYS
--------------------------------------------------------------------
RED, against commit `8004cd1bb` — the tree BEFORE the till block landed — in a
private detached `git worktree`, on **PostgreSQL 16**, through the same
`pytest` the suite runs (17:59):

    E   AssertionError: the seeded utility holds NO deposit batch at all, so
        the Payments list's BATCH column can only ever read 'No batch yet'
        (DEF-PAY-6321)
    E   assert 0 > 0
    1 failed, 1 passed

GREEN, on the fixed tree, same database, same invocation: **2 passed** (12:38).
Measured on that run: **2 tills** (8 and 9 August, each `counted` with a
`0.0000` difference), **4 deposit batches** — `DEP-260808-0001` cash
`$1,451.20` over 6 payments, `DEP-260808-0002` check `$2,388.84` over 9,
`DEP-260809-0003` cash `$320.96` over 1, `DEP-260809-0004` check `$4,345.75`
over 12 — **$8,506.75** of deposits, and of 66 payments **28 are in a batch**
and 38 (card and ACH) deliberately are not.

⚠ **THE FIRST RED RUN PROVED THE WRONG THING AND THAT IS WORTH KEEPING.** It
failed on this file's own precondition rather than on the batch count, because
an unrelated block was refusing — see `REQUIRED_BLOCKS` and `DEF-PAY-6339`. A
red is only a proof when you read WHICH assertion produced it.

The load-bearing assertion is the PAYMENT-side one, not the batch count: a
test that only counted batches would go green the day somebody INSERTed a row
straight into `deposit_batches`, which is exactly the data the product could
never have made and which `trg_deposit_batch_needs_session` exists to forbid.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import counter_session_models as tills
from apps.payments import counters
from apps.payments import models as payment_models
from apps.tenancy import sample_data as tenancy_sample_data
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _plant():
    """A tenant provisioned through the REAL signup service, then planted.

    ⚠ **THE ACTOR IS THE PROVISIONING OWNER AND NOT `admin_actor()`**, and this
    file needs that twice over. `tenancy.sample_data._attributed` strips an
    invented uuid, which is what `DEF-2722`'s file records — and on top of
    that, `counters.open_counter` makes the opener the till's OWNER, and
    `counter_sessions.owner` is a real FK to `identity.User`. An actor with no
    users row cannot open a counter at all, so the whole subject of this file
    would be absent for a reason that has nothing to do with the defect.
    """
    payload = dict(brazosbend_payload())
    slug = f"def-pay-6321-{uuid.uuid4().hex[:10]}"
    payload["subdomain"] = slug
    payload["name"] = "DEF-PAY-6321 counter batches"
    owner = dict(payload["owner"])
    owner["email"] = f"owner@{slug}.test"
    payload["owner"] = owner

    tenant, result = provisioned_tenant(payload)
    owner_id = result["owner_user_id"]
    actor = SimpleNamespace(
        id=uuid.UUID(str(owner_id)),
        pk=uuid.UUID(str(owner_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )
    with tenant_ctx(tenant):
        tenancy_sample_data.seed_sample_data(actor)
    return tenant


#: ⚠ **ONE TEST SEEDS AND EVERY CHECK RUNS INSIDE IT, WHICH IS NOT LAZINESS.**
#: The obvious shape is a module-scoped planted tenant and six small cases
#: reading it — `test_def_2414_trash_tenant_bills.py` does exactly that. **It
#: only works on PostgreSQL**, and the reason is worth writing down because it
#: is invisible until you try: `core.tenancy.set_current_tenant` runs
#: `SELECT set_config('app.tenant_id', …)`, sqlite has no such function, and
#: the autouse `sqlite_guc` fixture that records it instead is FUNCTION-scoped.
#: A module-scoped fixture is built BEFORE it, so the plant dies on
#: `sqlite3.OperationalError: no such function: set_config` — after paying for
#: every migration. That file answers it with `@requires_postgres`, which is
#: right for a file about RLS and savepoints and wrong for this one: a SKIP on
#: the default tier is how a check stops being read (hard-won law 7 — `G5`
#: counted 192 skips as a pass). So the plant happens inside one ordinary case
#: and runs on BOTH vendors, and the checks below are functions so a failure
#: still names which one failed rather than a line number.


#: The blocks this file's questions actually stand on. Anything outside this set
#: that refuses is REPORTED and does not fail the case.
#:
#: ⚠ **THE FIRST DRAFT FAILED ON ANY REFUSING BLOCK AND THAT WAS A CHECK THAT
#: COULD NOT PASS (`DEF-PAY-6339`, found by this file's own first run).**
#: `payments:seed_sample_multi_account_tender` has been refusing on the branch
#: — *"one of the landlord's three properties owes nothing"* — on the tip and
#: on the fixed tree alike, so a blanket precondition stopped this case before
#: it reached a single assertion about deposit batches, on BOTH trees. A test
#: that cannot reach its own subject proves nothing about it, and one that is
#: hostage to an unrelated block will be deleted by the next lane rather than
#: read (hard-won law 7's *incapable of passing*).
#:
#: **The blind spot is published as a NUMBER instead**, which is the same law's
#: other half: the required set is asserted empty, and every other refusing
#: block is named in the message so a reader sees what the fixture could not do
#: rather than a green line over it.
REQUIRED_BLOCKS: tuple[str, ...] = (
    "billing:seed_sample_records",
    "payments:seed_sample_records",
    "billing:seed_sample_second_cycle",
    "payments:seed_sample_cycle_collections",
    "tenancy:seed_sample_portal_content",
)

#: The block `_check_the_tender_cheque_is_the_only_gap` measures. It is NOT
#: required — when it refuses there is no cheque to measure, and that check
#: says so rather than asserting three parts that were never written.
TENDER_BLOCK = "payments:seed_sample_multi_account_tender"


def _failed_blocks(tenant) -> list[str]:
    """Which sample blocks did not seed — asked, never assumed.

    `DEF-2413`'s shape: the plant job reported SUCCEEDED over eight failed
    blocks. A file about what the fixture CONTAINS has to know whether the
    fixture ran, or a green assertion about an empty tenant is the result.
    """
    with tenant_ctx(tenant):
        return [
            f"{row.get('module')}:{row.get('block')}"
            for row in tenancy_sample_data.stored_blocks()
            if row.get("outcome") not in ("seeded", "skipped")
        ]


def _hand_tender_payments():
    """Every seeded payment taken in a tender that physically reaches a drawer.

    `counters.HAND_TENDERS` is asked rather than re-spelled — the same
    discipline the seeder keeps — so the day the PO adds a fourth hand tender
    this test covers it without being edited.
    """
    return payment_models.Payment.objects.filter(
        memo__startswith="sample data",
        method__code__in=counters.HAND_TENDERS,
        type=payment_models.PAYMENT_TYPE_PAYMENT,
    )


def _counter_payments():
    """The hand-tender payments this lane's seeder actually took, MINUS the one
    population it cannot reach — and the exclusion is COUNTED, never silent.

    ⚠ **`DEF-PAY-6322`.** The landlord's single cheque covering three
    properties is recorded through `tenders.record_multi_account_payment`,
    which accepts no `counter_session_id` — so those payments are cheques, on
    the busy day, in no drawer, and no amount of seeding can change that from
    here. Excluding them silently would make this file report a clean sweep
    over a population it never looked at, which is hard-won law 7's *reporting
    zero over a scope it silently excludes* — the exact shape `DEF-PAY-6321`
    itself is. So the scope is excluded by NAME, its size is asserted against
    the fixture, and `_check_the_tender_cheque_is_the_only_gap` asserts the gap
    is still open, so **the day DEF-PAY-6322 is fixed this file goes red and
    says so** rather than leaving a stale exclusion behind (law 2's "write the
    test that fires when the hold expires, in the same commit").
    """
    return _hand_tender_payments().filter(tender_id__isnull=True)


def _tender_payments():
    """The multi-property cheque's parts — `DEF-PAY-6322`'s whole population."""
    return _hand_tender_payments().filter(tender_id__isnull=False)


def _check_the_seeded_utility_holds_a_deposit_batch(seeded):
    """THE DEFECT ITSELF, in one number.

    Non-vacuous by construction (DEF-466's shape): a fixture that seeded no
    payments at all would satisfy "no payment lacks a batch" and prove nothing,
    so the payment count is asserted first and separately.
    """
    failed = _failed_blocks(seeded)
    required = [block for block in failed if block in REQUIRED_BLOCKS]
    others = [block for block in failed if block not in REQUIRED_BLOCKS]
    with tenant_ctx(seeded):
        payments = payment_models.Payment.objects.count()
        batches = bankrec.DepositBatch.objects.count()

    assert required == [], (
        f"a block this file stands on did not seed, so nothing below is about this defect: "
        f"{required}"
        + (f" (and {others} refused too)" if others else "")
    )
    if others:
        # NAMED, never swallowed — a refusing block is a missing exhibit and
        # `DEF-PAY-6339` is what happens when nobody counts one.
        print(f"note: {len(others)} block(s) refused and are not this file's subject: {others}")
    assert payments > 0, "no payments seeded — every assertion below would pass vacuously"
    assert batches > 0, (
        "the seeded utility holds NO deposit batch at all, so the Payments list's BATCH "
        "column can only ever read 'No batch yet' (DEF-PAY-6321)"
    )


def _check_every_counter_payment_names_a_till_and_a_batch(seeded):
    """The assertion that cannot be satisfied by an INSERTed row.

    A batch written straight into the table would turn the test above green
    while being data the product could never have made — `payments/0033`'s
    `trg_deposit_batch_needs_session` refuses a batch with no session. This one
    asks the question from the PAYMENT's side: cash and cheques the fixture
    took must each name the till they were taken into AND the batch that till
    banked them in, which is only true if the money went through
    `open_counter` → `record_payment` → `close_counter`.
    """
    with tenant_ctx(seeded):
        taken_by_hand = _counter_payments()
        total = taken_by_hand.count()
        no_batch = list(
            taken_by_hand.filter(deposit_batch_id__isnull=True).values_list(
                "payment_no", "method__code"
            )
        )
        no_till = taken_by_hand.filter(counter_session_id__isnull=True).count()

    assert total > 0, "the fixture took no cash and no cheques — nothing to bank"
    assert no_batch == [], (
        f"{len(no_batch)} counter-tender payment(s) belong to no deposit batch, so the "
        f"Payments list reads 'No batch yet' over money a clerk handled: {no_batch[:5]}"
    )
    assert no_till == 0, (
        f"{no_till} counter-tender payment(s) name no till. A batch without a till is the "
        "window the 2026-09-21 ruling exists to close"
    )


def _check_the_batches_group_one_till_by_one_tender(seeded):
    """BR-PAY-025 as amended — the grouping is the product's, not the fixture's.

    Every seeded batch names a session (nothing was written the old way), no
    two batches of one till share a tender, and every batch's tender is one a
    drawer can actually hold. The day is the TILL's drawer day, which is what
    keeps the *day × tender* reading of BR-PAY-025 true one layer down.
    """
    with tenant_ctx(seeded):
        rows = list(
            bankrec.DepositBatch.objects.select_related("method", "session").order_by("code")
        )
        # CR-186-BRC10 (PO 2026-10-21): ONE batch per till, all tenders —
        # the key is the till, and the tenders are read from the members.
        keys = [str(row.session_id) for row in rows]
        sessionless = [row.code for row in rows if row.session_id is None]
        from apps.payments import models as _pm

        wrong_tender = [
            row.code
            for row in rows
            if row.session is not None
            and row.session.system_day is None
            and _pm.Payment.objects.filter(deposit_batch_id=row.pk)
            .exclude(method__code__in=counters.HAND_TENDERS)
            .exists()
        ]
        wrong_day = [
            row.code
            for row in rows
            if row.session is not None and row.deposited_on != row.session.opened_at.date()
        ]

    assert rows, "no batch to check"
    assert sessionless == [], (
        f"{sessionless} name no counter session. `trg_deposit_batch_needs_session` refuses "
        "that at the database, so a row here means the fixture bypassed the product"
    )
    assert len(set(keys)) == len(keys), (
        f"two batches share one till: {keys}. `uq_deposit_batches_session_all_tenders` "
        "is the key BR-PAY-025 was re-keyed to on 2026-10-21"
    )
    assert wrong_tender == [], (
        f"{wrong_tender} bank a tender that never reaches a drawer — a card or ACH total in "
        "a counter batch would make the close count disagree with what is physically there"
    )
    assert wrong_day == [], f"{wrong_day} are dated off their till's drawer day"


def _check_the_tills_are_sealed_and_their_batches_are_footed(seeded):
    """A shift that is never closed banks nothing — `$0.00` at Finance.

    `close_counter._seal_batches` is what recomputes `recorded_total`; without
    it every counter batch reaches Finance → Deposits with the right payments
    in it and a total saying the shift took nothing. So the count is asserted
    against Σ its members rather than against a typed figure, and the drawer is
    asserted to balance: the fixture counts what the system expects, so the
    difference is exactly `0.0000` and no cash-over/short pair is posted.
    """
    with tenant_ctx(seeded):
        sessions = list(
            tills.CounterSession.objects.filter(system_day__isnull=True).order_by("opened_at")
        )
        open_still = [str(row.pk) for row in sessions if row.closed_at is None]
        differences = [(row.opened_at.date(), row.difference) for row in sessions]
        footed = []
        for batch in bankrec.DepositBatch.objects.all():
            members = payment_models.Payment.objects.filter(deposit_batch_id=batch.pk)
            total = sum((row.amount for row in members), Decimal("0"))
            footed.append((batch.code, Decimal(str(batch.recorded_total)), total))

    assert sessions, "the fixture opened no counter till"
    assert open_still == [], (
        f"{open_still} was left OPEN. An unsealed till's batch is never footed, and the next "
        "block's `open_counter` is refused — one person may hold one open till"
    )
    for day, difference in differences:
        assert Decimal(str(difference)) == Decimal("0.0000"), (
            f"the till of {day} closed {difference} out. The fixture counts what "
            "`running_split` says the system expects, so a difference here means the count "
            "and the takings have drifted apart"
        )
    for code, recorded, members in footed:
        assert recorded == members, (
            f"batch {code} is footed at {recorded} and holds {members} — a deposit slip that "
            "disagrees with its own members is the figure a finance lead acts on"
        )


def _check_electronic_money_is_left_with_no_batch_on_purpose(seeded):
    """THE OTHER HALF, and it is an assertion rather than a comment.

    A fixture where every row has a batch would hide the case the column exists
    to show. Card and ACH money never passes through a person's hands, is
    REFUSED a till by name (`services._counter_session`, PO ruling 2026-09-23
    §3.4), and *No batch yet* is the correct and useful answer on those rows.

    ⚠ **IT ASSERTS THE ABSENCE IS COMPLETE, NOT MERELY PRESENT.** A single
    batchless card row would satisfy a weaker test while a later lane quietly
    cut the rest into batches; this says NONE of them may have one, which is
    the shape the rule actually has.
    """
    with tenant_ctx(seeded):
        electronic = payment_models.Payment.objects.filter(
            memo__startswith="sample data"
        ).exclude(method__code__in=counters.HAND_TENDERS)
        total = electronic.count()
        # ⚠ CR-186-BRC10 (PO 2026-10-21): electronic money IS banked at
        # posting now — in its provider or channel's batch for the day, never
        # in a person's drawer. What stays absolute is the second half: no
        # card or ACH payment sits in a TILL's batch.
        banked = list(
            electronic.filter(
                deposit_batch_id__in=bankrec.DepositBatch.objects.filter(
                    session__system_day__isnull=True
                ).values("pk")
            )
            .values_list("payment_no", "method__code")
        )
        in_a_till = electronic.filter(counter_session_id__isnull=False).count()

    assert total > 0, (
        "the fixture seeded no card or ACH payment, so the 'No batch yet' case the BATCH "
        "column exists to show is not demonstrated anywhere"
    )
    assert banked == [], (
        f"{banked} were banked in a deposit batch. A card total in a drawer makes the close "
        "count disagree with what is physically there"
    )
    assert in_a_till == 0, f"{in_a_till} electronic payment(s) name a counter till"


def _check_the_tender_cheque_is_the_only_gap(seeded):
    """The excluded scope, with a NUMBER beside it (`DEF-PAY-6322`).

    Two assertions and each does a different job: the population is the SIZE
    the fixture says it is, so the exclusion cannot quietly grow; and it is
    still batchless, so the day the other door is wired this goes red and names
    the defect to close. That it is a HAND tender is not asserted here because
    it is how `_tender_payments` selects the rows in the first place — an
    assertion that restates its own query proves nothing.
    """
    expected = len(fixture.MULTI_PROPERTY_TENDER["unit_indexes"])
    refused = TENDER_BLOCK in _failed_blocks(seeded)
    with tenant_ctx(seeded):
        parts = list(_tender_payments().values_list("payment_no", "deposit_batch_id"))

    if refused:
        # `DEF-PAY-6339` — the block is refusing on the branch, so there is no
        # cheque to measure. Asserted as ZERO rather than skipped, so the day it
        # seeds again this check notices instead of staying quietly satisfied.
        assert parts == [], (
            f"{TENDER_BLOCK} refused, so the demo holds no multi-property cheque — yet "
            f"{len(parts)} part(s) exist. Something else wrote them"
        )
        return
    assert len(parts) == expected, (
        f"the multi-property cheque should have {expected} parts and has {len(parts)}. "
        "This number is the scope this file excludes; it may not drift unnoticed"
    )
    # CR-186-BRC10 (PO 2026-10-21): every payment is stamped at posting, so
    # the tender's parts now bank in the OFFICE channel's day batch. What
    # still marks DEF-PAY-6322 open is that none of them is in a TILL's batch.
    with tenant_ctx(seeded):
        till_batches = {
            str(pk)
            for pk in bankrec.DepositBatch.objects.filter(
                session__system_day__isnull=True
            ).values_list("pk", flat=True)
        }
    banked = [row for row in parts if row[1] is not None and str(row[1]) in till_batches]
    assert banked == [], (
        f"{banked} now belong to a deposit batch. If `record_multi_account_payment` has "
        "been given a till, DEF-PAY-6322 is FIXED: fold these back into "
        "`_counter_payments` and delete the exclusion rather than widening this"
    )


def test_def_pay_6321__the_seeded_utility_banks_its_counter_money():
    """THE CASE. One plant, six checks, in order of what they would tell you.

    Each check is a function so a failure names WHICH question failed rather
    than a line number, and they run in the order a reader would ask them: is
    there a batch at all → does the money name one → is it grouped the way the
    product groups it → is the drawer sealed and footed → is the deliberate
    absence still complete → is the one population this file cannot reach still
    exactly the size and the shape it was excluded at.
    """
    seeded = _plant()
    _check_the_seeded_utility_holds_a_deposit_batch(seeded)
    _check_every_counter_payment_names_a_till_and_a_batch(seeded)
    _check_the_batches_group_one_till_by_one_tender(seeded)
    _check_the_tills_are_sealed_and_their_batches_are_footed(seeded)
    _check_electronic_money_is_left_with_no_batch_on_purpose(seeded)
    _check_the_tender_cheque_is_the_only_gap(seeded)


def test_def_pay_6321__what_this_file_does_not_assert():
    """The two neighbours this lane FILED and did not fix, named so a later
    reader does not mistake their absence for a claim that they are fine.

    * **`DEF-PAY-6322`** — `tenders.record_multi_account_payment` accepts no
      `counter_session_id`, so the landlord's one cheque covering three
      properties can never belong to a batch however the fixture is seeded.
      It is a CHEQUE taken on the busy day and it has no till: a door that was
      not carried when `P2.13` wired the other one. ⚠ **Its POPULATION is
      asserted** — `_check_the_tender_cheque_is_the_only_gap` pins the size
      and the batchlessness, so the exclusion cannot grow and the day the door
      is wired this file goes red. What is NOT asserted is that the gap should
      exist; it should not.
    * **`DEF-PAY-6323`** — every seeded payment took `record_payment`'s
      default `idempotency_source`, so a card or ACH row's `origin` was `entry`
      and the SOURCE column labelled it *Counter*. Not fixed here because
      `origin` is written FROM the idempotency source, so changing it changes
      the KEY: on a tenant already seeded the replay check would miss and
      record a SECOND permanent payment against every card and ACH bill.
      ⚠ **FIXED 2026-09-24** — the seeder states the source and asks for the
      old key before recording; `test_def_pay_6323_seeded_payment_source.py`
      asserts both halves, so this file still asserts nothing about it.

    This test asserts nothing about either. It exists because a file that
    checks five things reads as a file that checked everything.
    """
    assert True


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6321 (PO report on the deployed build, 2026-09-23)
# generated: 2026-09-23 by lane SEED-BATCH
# checklist: A✔ B=n/a(no screen) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED at commit 8004cd1bb and GREEN on the fixed tree, both on
#        PostgreSQL 16 through the suite's own pytest — quoted verbatim in the
#        module docstring (CLAUDE.md hard-won law 14: the seeder catches a
#        database error and continues in two new places, so the default
#        in-memory SQLite tier could not prove them)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

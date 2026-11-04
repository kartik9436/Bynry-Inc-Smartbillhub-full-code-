# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 — the payments blueprint's phase 2 (*the counter*),
#          tasks `P2.4`, `P2.5` and `P2.20`.
#          `05-prototype/06 Payments Page Blueprint.pdf` pp.16–18 for the first
#          two; `P2.20` is NOT in the drawing and comes from the PO ruling of
#          2026-09-23 (decision log, *"A LATE COUNT IS ADDED BESIDE THE FORCED
#          CLOSE, NEVER OVER IT"*).
#          ⚠ **THE BLUEPRINT IS NOT ON THIS BRANCH.** It lives on the default
#          branch `claude/confirm-understanding-3ktufc` as
#          `05-prototype/06 Payments Page Blueprint.pdf` (2,905,141 bytes,
#          sha256 0cc31baf…). A lane that greps `05-prototype/` here finds
#          nothing and falls back to r10, which is the trap `DEF-GOV-5248`
#          names.
# Story:   no story — phase 2's db half. The screens that fill these columns
#          are `3·1 Counters`, `3·2 My counter` and `3·3a–d`, tasks `P2.6`.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping; `counter_sessions` and
#          `payments` both carry RLS FORCE — no policy moves here) · hard rule
#          4 (financial immutability — **this migration writes no row**, so
#          `trg_payment_immutable` is never lifted and `payments/0014`'s allow
#          list does not move) · hard rule 7 (a declare is a money action and
#          writes `audit_log` — that is `P2.2`'s, at the service) ·
#          BR-SHL-025 · BR-PAY-1160 · hard-won law 7 (proved RED first, in the
#          harness that will run it) · hard-won law 14 (SQLite cannot show a
#          CHECK's NULL behaviour the way PostgreSQL does)
# Tests:   06-backend/tests/test_cr136_p2_counter_columns.py (the constraint,
#          the column shapes and the derived expression) ·
#          10-scripts/cr136_p2_20_declared_readback.py (PostgreSQL 16: the
#          FIVE forbidden rows refused BY NAME, the four lawful shapes
#          accepted, and the naive spelling shown accepting what it must not) ·
#          10-scripts/cr136_p2_5_till_index_measure.py (the index decision,
#          measured rather than argued)
# Impacts: apps/payments/models.Payment.counter_session_id +
#          ix_payments_counter_session · apps/payments/counter_session_models.
#          CounterSession.declared_at/.declared_by +
#          ck_counter_sessions_declared_together + NOT_COUNTED ·
#          apps/payments/reconciliation._session_for is the ONE function phase
#          2 changes to read the new column — it is NOT changed here
# ───────────────────────────────────────────────────────
"""payments 0035 — A PAYMENT NAMES ITS TILL, AND A TILL CAN BE COUNTED LATE.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). Migration
ordering is a CLAUDE.md 🔒 sensitive path and one of these columns sits on the
money table, so there is a row in `12-governance/09-human-review-ledger.md`
stating in plain English, with a figure, what would be put to the Product
Owner. It may never reach lifecycle RATIFIED without a recorded human sign-off.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS MIGRATION WRITES NO ROW. Three columns, one index and one CHECK —  ║
║  no backfill, no UPDATE, no data step. So `trg_payment_immutable` is     ║
║  never lifted, `payments/0014`'s allow list does not move, and the       ║
║  per-tenant `set_config` loop that `payments/0029` needs has nothing to  ║
║  scope here. Both of those are named because a reader who has just read  ║
║  `0029` will look for them.                                             ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
`P2.4` — `payments.counter_session_id`
────────────────────────────────────────────────────────────────────────────
A nullable uuid naming the drawer this money was taken into.

⚠ **IT STAYS NULLABLE, AND THAT IS A RULING RATHER THAN A DEFAULT.** PO
2026-09-23: *"(a) Refuse it. \"Start your counter first.\" One press, then take
the money"*. Three of the seven tenders pass through a person's hands —
`cash`, `check`, `money_order` — and **only those three** are refused without
an open till. ACH, card, wire and lockbox never touch a counter, so `NOT NULL`
would refuse every one of those rows in the product. The rule is a SERVICE
rule with four tenders' worth of exception and cannot be spelled as a column
constraint; `BR-SHL-025` puts it at the endpoint, never on a hidden button.

⚠ **IT IS A PLAIN UUID AND NOT A ForeignKey — AND BOTH REASONS THE BLUEPRINT
GIVES FOR THAT ARE WRONG (`DEF-PAY-6219`, filed by this lane).**
The drawing's outcome sentence is *"A payment names its till. **No ORM edge
into another module**"* and its reference column cites **`B11 F-3`**.

  * **There is no module boundary here.** `counter_sessions` is a PAYMENTS
    table — `apps/payments/counter_session_models.py`, app label `payments`,
    created by `payments/0031`. Its own docstring distinguishes the two cases
    correctly (it calls `counter_receipts.method_id` *"a payments → tenancy
    edge"*), so the drawing is the only place that gets it wrong.
  * **B11 F-3 is about migration ORDER**, not about modules: *"forward FKs
    break the stated top-to-bottom migration order (… payments→deposit_
    batches) → Eng deferred-FK pass"*. The sibling column it points at,
    `deposit_batch_id`, is a plain uuid for exactly that reason and says so in
    `models.py`'s own exceptions list — *"`deposit_batches` belongs to
    EP-PAY-06 and **does not exist**"*. `counter_sessions` has existed since
    `payments/0031` and this migration is `0035`, so there is no order to
    break and F-3 has nothing to say.

**THE SHAPE IS BUILT AS DRAWN ANYWAY, FOR A REASON THE DRAWING DOES NOT
GIVE.** `deposit_batch_id` answers the same *which container did this money
land in* question, about the same rows, and is read beside this column on the
same list (`P2.8`'s Source and Batch columns). **Two columns answering one
question in two shapes is the *two places that can disagree* shape this module
keeps filing** — and a lane holding a `Payment` would have `.counter_session`
traversable and `.deposit_batch_id` not, which is precisely the kind of
difference that gets read as meaning something.

⚠ **WHAT IT COSTS, STATED HERE SO NOBODY HAS TO DISCOVER IT: THERE IS NO
REFERENTIAL INTEGRITY.** Nothing refuses a payment naming a till that does not
exist, and nothing stops a `counter_sessions` row being deleted out from under
one — both already true of `deposit_batch_id`. The writing service is the only
guard. If that ever bites, the fix is an FK on BOTH columns together, not on
this one alone.

────────────────────────────────────────────────────────────────────────────
`P2.5` — `ix_payments_counter_session`, and it is PARTIAL
────────────────────────────────────────────────────────────────────────────
*"The till's own list reads it on every payment taken … the running total
stays cheap as a shift fills up."*

**MEASURED, NOT ARGUED** — `10-scripts/cr136_p2_5_till_index_measure.py`, on
PostgreSQL 16.13, on a probe table of **40,000 rows (the top of tier T5, the
largest tenant `B6` models)** carrying the two uuid columns the index covers.

  1 · **SIZE.** Full vs partial, by the share of rows carrying a till:

        rows with a till     full index    partial index    saved
         40,000 (100%)         1,864 kB        1,864 kB       0 kB   (0%)
         12,000 ( 30%)           760 kB          568 kB     192 kB  (25%)
          2,000 (  5%)           376 kB          112 kB     264 kB  (70%)

    ⚠ **AND THE OBVIOUS ARGUMENT FOR A PARTIAL INDEX IS WRONG.** *A btree
    stores a NULL key like any other, so the full index pays full price for
    every payment that never touched a counter* is what this lane expected to
    measure. **PostgreSQL 13+ DEDUPLICATES equal keys and every NULL is equal
    to every other NULL**, so a NULL row costs about **7 bytes** of index
    where a real till id costs about **48**. The saving is a seventh of what
    the argument assumes, and **264 kB at T5's ceiling decides nothing.**

  2 · **WRITE COST — MEASURED AND DISCARDED.** Same 40,000 rows, five runs
    each, medians: no index **173 ms**, full index **219 ms**, partial index
    **159 ms**. The partial index came out *faster than having no index at
    all*, which is impossible — so the three are inside this machine's noise
    and **no write-cost figure may be quoted in support of either shape.**
    It is recorded because the alternative is the next lane running it and
    believing it.

  3 · **THE ONE THING THAT HAD TO BE CHECKED: IS A PARTIAL INDEX USABLE AT
    ALL HERE?** A partial index the planner cannot use would look thrifty and
    cost a sequential scan on every page load. It is usable, twice over:

        Bitmap Index Scan on ix_probe_partial      (bound parameters)
        Index Scan using ix_probe_partial          (PREPAREd, GENERIC plan)

    The second is the load-bearing one — the first could be constant folding.
    **The reason it works is STRICTNESS:** `counter_session_id = $1` uses a
    strict operator, so a NULL column makes the clause NULL rather than true,
    which implies `counter_session_id IS NOT NULL` with no knowledge of `$1`.

  4 · **WHAT IT CANNOT DO, ON THE RECORD.** *Which payments have NO till* can
    never be answered from an index that excludes exactly those rows — the
    measured plan is a `Seq Scan`. That query returns most of the table at any
    realistic share, so a sequential scan is the right plan for it whichever
    index exists, and this costs nothing rather than being a trade.

**SO THE DECISION RESTS ON (3) AND (4) AND NOT ON A PERFORMANCE FIGURE**, and
saying so is the point: it is never larger, it is provably usable including
generically, it cannot serve only a query that wants a sequential scan anyway,
and its `WHERE` states in the schema what the index is for. A later lane
quoting *"we made it partial for performance"* would be quoting something this
measurement does not support.

────────────────────────────────────────────────────────────────────────────
`P2.20` — `declared_at`, `declared_by`, and one CHECK
────────────────────────────────────────────────────────────────────────────
**NOT IN THE DRAWING.** PO ruling 2026-09-23, verbatim: *"(a) Keep it as a
forced close and add the late count beside it… The row reads: force-closed
Monday by the supervisor, declared Tuesday by Dana, $12 short. It leaves the
Not counted list. Nothing is erased"*.

The worked case: Dana's till is force-closed Monday night uncounted; Tuesday
she counts **$1,228.00 against $1,240.00 expected — $12.00 short**, reason
*"cheque stuck to the bag"*. **One row, afterwards, says both things.**

`close_kind` **does not move** and holds exactly `counted`, `forced`,
`system`. A fourth value `declared` was put to the PO and rejected, as was
changing a forced close to `counted` on declare — that one *"erases the fact
that nobody counted it on the day"*. The count needs no new column:
`counted_totals`, `difference` and `note` are NULL on a forced close precisely
because nobody counted, and declaring fills them.

**`ck_counter_sessions_declared_together` is a CONSTRAINT and not a service
check, because the ruling says so** — *"for the same reason
`ck_counter_sessions_closed_together` is"*. Two facts, one rule:

    (a) `declared_at` and `declared_by` are both set or both NULL
    (b) `declared_at` set requires `close_kind = 'forced'`

⚠ **THE SECOND BRANCH OPENS WITH `close_kind IS NOT NULL`, AND WITHOUT IT THE
CONSTRAINT WOULD BE OFF FOR EVERY OPEN TILL — `DEF-PAY-6207`, WHICH HAPPENED
TWICE IN THIS EXACT FILE.** A CHECK refuses a row only when its expression is
FALSE and **PASSES when it is NULL**. `close_kind` is NULL on every till that
is still open, so a plain `close_kind = 'forced'` reads NULL there, the chain
becomes `FALSE OR NULL` = NULL, **and an OPEN till could be handed a
`declared_at` — a drawer declared before it was ever sealed.** Proved RED on
PostgreSQL 16 in exactly that form before the clause went in; see
`10-scripts/cr136_p2_20_declared_readback.py` section 2, which keeps both the
RED and the GREEN readings.

`Not counted` is the one derived expression the ruling names —
`close_kind = 'forced' AND declared_at IS NULL` — with four readers. It is
written once as `counter_session_models.NOT_COUNTED` and nothing imports it
yet; its four readers are `P2.2`, `P2.3`, `P2.6` and `P2.11`.

⚠ **HARD RULE 4 DOES NOT BITE AND HARD RULE 7 DOES.** `counter_sessions` is not
one of the four tables rule 4 freezes, so declaring may UPDATE the row in
place; and a declare is a money action and writes `audit_log` — at the service,
which is `P2.2`'s and is not built here.

────────────────────────────────────────────────────────────────────────────
REVERSIBILITY
────────────────────────────────────────────────────────────────────────────
Every operation is a Django schema operation with a real reverse: two
`AddField`s on `counter_sessions`, one on `payments`, one `AddIndex`, one
`AddConstraint`. Proved FORWARDS, BACKWARDS and FORWARDS AGAIN on a
PostgreSQL 16 clone, and **verified by reading `pg_get_constraintdef` and
`pg_indexes` back after the round trip rather than by trusting the migration
state** — which is the check `payments/0034` added and the reason it is
repeated here.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    # ⚠ `tenancy` is NOT listed although `CounterSession` points at it: the
    # FKs to `Tenant` and `ServiceCentre` were established by `payments/0031`
    # and nothing here touches them. `identity` is listed because `declared_by`
    # is a NEW edge to `identity.User` and the historical model registry must
    # carry that model when this runs. `customers` comes with `payments/0034`'s
    # own chain.
    dependencies = [
        ("customers", "0065_br_cus_1091_address_parts_as_given"),
        ("identity", "0005_cr070_f_field_technician"),
        ("payments", "0034_def_pay_6207_null_safe_check_branches"),
    ]

    operations = [
        # ── P2.20 · the late count ─────────────────────────────────────────
        migrations.AddField(
            model_name="countersession",
            name="declared_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="countersession",
            name="declared_by",
            field=models.ForeignKey(
                blank=True,
                db_column="declared_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
        # ── P2.4 · which till took this money ──────────────────────────────
        migrations.AddField(
            model_name="payment",
            name="counter_session_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        # ── P2.5 · the till's own list, PARTIAL — see the docstring ────────
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                condition=models.Q(("counter_session_id__isnull", False)),
                fields=["tenant", "counter_session_id"],
                name="ix_payments_counter_session",
            ),
        ),
        # ── P2.20 · both or neither, and only on a forced close ────────────
        # `close_kind IS NOT NULL` FIRST in the second branch. Without it the
        # branch is NULL for every OPEN till and NULL is ACCEPTED, which is
        # `DEF-PAY-6207` for the third time in this table.
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("declared_at__isnull", True), ("declared_by__isnull", True)),
                    models.Q(
                        ("close_kind__isnull", False),
                        ("close_kind", "forced"),
                        ("declared_at__isnull", False),
                        ("declared_by__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="ck_counter_sessions_declared_together",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/change-requests/CR-136-BRC07-payments-phase-2-the-counter.md §3.2 and §3.4 · 12-governance/02-decision-log.md 2026-09-23 (four rulings) · 05-prototype/06 Payments Page Blueprint.pdf pp.16-18, ON THE DEFAULT BRANCH ONLY · CLAUDE.md hard rules 1, 4, 7 · hard-won laws 7 and 14
# generated: 2026-09-23 by LANE P2-DB
# checklist: A✔ B=n/a(no screen) C✔ D=n/a(a migration) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a PostgreSQL 16.13 clone — the constraint written WITHOUT `close_kind IS NOT NULL` ACCEPTED an open till carrying a declared_at, named by the constraint that should have refused it; GREEN with the clause, all three bad shapes refused BY NAME and all four lawful shapes still accepted. `cr136_p2_5_till_index_measure.py` green, its figures quoted above. makemigrations --check clean for payments · ruff clean · FORWARDS, BACKWARDS, FORWARDS AGAIN on the clone with `pg_get_constraintdef` and `pg_indexes` read back after the round trip rather than inferred
# exceptions: `counter_session_id` is a plain uuid and not an FK, so there is NO referential integrity on it — built as the blueprint draws it, but BOTH reasons the blueprint gives for that shape are false and are filed as `DEF-PAY-6219`; the reason that holds is consistency with `deposit_batch_id`, which answers the same question about the same rows

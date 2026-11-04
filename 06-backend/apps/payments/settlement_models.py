# ── Trace ──────────────────────────────────────────────
# Change:   CR-139-BRC07 — the payments blueprint's phase 5, tasks `P5.4`
#           (`settlements`), `P5.5` (`settlement_members` + its RLS) and the
#           membership half of `P5.6`. Drawing:
#           `05-prototype/06 Payments Page Blueprint.pdf` p024.
# Story:    no story — phase 5's two Settlements screens are `P5.7` and belong
#           to another lane. These tables are what they read.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is its own
#           migration, `payments/0039`) · hard rule 2 (a NEW money column
#           declares FOUR decimals — the drawing says six and the PO's re-sign
#           of 2026-08-22 wins) · hard rule 4 (a settlement never rewrites a
#           payment's money) · hard rule 6 (the repeat-payout key is the
#           `uq_settlements_provider_code` index below) · BR-INT-037 (no
#           provider is named in `apps/payments`)
# Tests:    06-backend/tests/test_cr139_p5_settlements.py ·
#           06-backend/tests/test_cr139_p5_rls_pg.py (PostgreSQL only)
# Impacts:  apps/payments/migrations/0038_cr139_p5_4_p5_5_p5_6_settlements.py
#           (this schema) · 0039_rls_cr139_p5_5_settlements.py (the guarantee
#           these classes cannot give) · apps/payments/apps.py (`ready()`
#           registers this module) · apps/payments/migrations/
#           0044_oq_pay_12608_drop_settlement_pointer.py (the denormalised
#           pointer `P5.6` asked for, REMOVED on the PO's ruling of
#           2026-09-24 — these two tables are now the only record)
#           · apps/payments/settlements.py
#           (the ONLY write path for both tables)
# ───────────────────────────────────────────────────────
"""payments — `settlements` and `settlement_members`: **the third source.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). Migration
ordering, RLS and idempotency keys are CLAUDE.md 🔒 sensitive paths, so a row in
`12-governance/09-human-review-ledger.md` states in plain English, with a
figure, what a reviewer is owed. Nothing here reaches lifecycle RATIFIED
without a recorded human sign-off.

WHAT A ROW IS
-------------
Money reaches this product from three places. Two are closed: a clerk keys it at
the counter, or a file is imported. **The third is a processor** — it takes card
and ACH money all day and then pays the utility **ONE bank credit for the lot,
net of its fee**. Until this table, nothing in the product could say which
payments were inside that credit.

The blueprint's worked payout, which is also journey `J-PAY-settle-the-night`:
**forty-six payments, one fee, one bank credit.**

╔══════════════════════════════════════════════════════════════════════════╗
║  ⚠ THE WORD `settlement` WAS ALREADY TAKEN, IN THIS MODULE, ON THIS      ║
║  MONEY PATH — AND THE DRAWING DOES NOT WARN ABOUT IT.                    ║
╚══════════════════════════════════════════════════════════════════════════╝
`apps/payments/webhooks.py` publishes `CHARGE_SETTLED = "charge.settled"` and a
function `settle_charge`, and **there *settlement* means ONE PAYMENT CLEARED**
— the gateway confirming a single card charge. **Here it means A PAYOUT BATCH
CONTAINING MANY PAYMENTS.** Two meanings, one word, one module.

The convention `CR-139-BRC07` §2.1 sets, so nobody has to rediscover it: the
phase 5 object is spelled **payout** in prose and **`Settlement`** in code, and
**nothing in `webhooks.py`'s charge path is renamed**. `settle_charge` is about
a payment; `ingest_payout` is about a payout. Renaming the live one to win a
word would move a constant that fifteen shipped tests and one signed idempotency
key already name.

⚠ THE MONEY COLUMNS ARE `NUMERIC(18,4)` AND THE DRAWING SAYS `NUMERIC(18,6)`
-----------------------------------------------------------------------------
`P5.4`, verbatim: *"Money at `NUMERIC(18,6)`, currency `CHAR(3)`"*. **Not
followed.** CLAUDE.md hard rule 2, PO re-sign 2026-08-22, verbatim: *"We already
confirmed this - MOney 4 decimal, percentage 6 decimal , display both 2
decimal"* — and that re-sign supersedes the rule's own original `NUMERIC(18,6)`.
**Existing 18,6 columns stay lawful containers; what a NEW column DECLARES is
four.** `payments/0031` took the same reading for `counter_sessions`, so this is
the second time and the precedent is already on the branch.

This is B14 rule 37's shape one level down: **a figure drawn in a wireframe is
an illustration, never a fact to build to** — and a signed rule is not an
illustration.

⚠ `code` IS THE PROVIDER'S OWN REFERENCE, NOT A NUMBER THIS PRODUCT MINTS
-----------------------------------------------------------------------------
Everywhere else in this product a `code` column holds a number allocated from
the tenant's own series — `DEP-260922-0001`, `SR-26-0017`. **Not here, and the
choice is deliberate rather than an omission** (decision log 2026-09-23).

  * **A payout is the PROVIDER'S object.** They created it, they numbered it,
    and the utility's finance clerk will be looking at the processor's own
    statement when they open our screen. A second number of our own would give
    one payout two names and guarantee the clerk is quoting the wrong one on
    the phone.
  * **It is also the idempotency key** (`P5.3`, hard rule 6): the unique index
    is `(tenant, provider, code)` and `code` is the provider's settlement id.
    Minting our own number would leave the provider's id in a second column
    that the key would have to use anyway — the *two places that can disagree*
    shape this module keeps filing.
  * **Minting one would be a THIRTY-SECOND numbering series**, which is a
    seeded default a tenant edits on Settings and therefore a question for the
    Product Owner, not a lane's call (`OQ-PAY-12605` is the precedent — the
    refund series had to be asked). Nothing here needed it.

⚠ `status` AND `bank_line_id` CANNOT DISAGREE, AND THAT IS A CHECK CONSTRAINT
-----------------------------------------------------------------------------
Two values, both real, and **no third is invented**:

  * **`received`** — the payout message arrived and its members are written.
    The money has NOT reached the utility's bank yet as far as this product
    knows, which is the PO's ruling of 2026-08-11 (`OQ-143`) working normally:
    *"until bank record and reconcilaition confirm it it is not realised"*.
  * **`matched`** — the bank credit for this payout has been identified, and
    `bank_line_id` names it.

A status column and a nullable pointer answering the same question is two places
that can disagree, so `ck_settlements_matched_has_line` makes them one fact:
`(status = 'matched') = (bank_line_id IS NOT NULL)`. A row that says *matched*
with no line, or names a line while saying *received*, cannot be written.

⚠ WHAT THIS TABLE DOES **NOT** DO: IT DOES NOT POST THE MONEY
-----------------------------------------------------------------------------
**The balanced pair for a card day already exists and is shipped**, and finding
that out is the single most important measurement of this phase. `OQ-144` (PO
2026-08-11, *"Match net with a fee line"*) and `OQ-160` (PO 2026-08-12, *the fee
may be DERIVED from the shortfall*) are both CLOSED, and
`reconciliation.reconcile_batch` → `ledger_seam.post_batch_reconciled` already
writes exactly the entry the drawing asks `P5.2` for:

    DR 1000 Cash               4,972.90   ← what the bank actually credited
    DR 6800 Bank fees            147.50   ← the processor's fee, ITS OWN LINE
    CR 1010 Undeposited funds  5,120.40   ← what the customers handed over

So a settlement that ALSO posted cash would post the same money twice — the
drawing's own *"two answers to one question"* risk, on the money path. What
phase 5 changes is not the ENTRY, it is where the fee figure COMES FROM: known
from the payout instead of derived from the gap. `apps/payments/settlements.py`
carries that reasoning and the refusal that makes it worth having.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

# ── THE TWO STATES A PAYOUT HAS, AND THERE IS NO THIRD ─────────────────────
#: The payout message arrived and its members are written. The utility's bank
#: has not been shown to hold the money yet.
SETTLEMENT_RECEIVED = "received"
#: The bank credit for this payout has been identified; `bank_line` names it.
SETTLEMENT_MATCHED = "matched"
SETTLEMENT_STATUSES = (SETTLEMENT_RECEIVED, SETTLEMENT_MATCHED)


class Settlement(models.Model):
    """One payout: what a provider paid the utility, and what it kept.

    ⚠ **THE THREE FIGURES ARE THE PROVIDER'S, AND THE PRODUCT CHECKS THEIR
    ARITHMETIC RATHER THAN RE-DERIVING IT.** `gross`, `fees` and `net` all
    arrive in the payout message. `ck_settlements_net_ties` refuses a row where
    `gross - fees != net`, which is the one thing a provider can get wrong that
    we would otherwise carry into the books silently. **Recomputing `net`
    ourselves would hide exactly that error**, which is `OQ-160`'s recorded
    hazard one level up: a figure derived to close a gap is a figure that can
    never disagree with anything.

    ⚠ **`fees` IS A POSITIVE NUMBER.** It is what the provider KEPT, so it
    reduces the credit; writing it negative would make `gross - fees = net`
    read as an addition and would put a negative expense in front of the next
    person who posts it. `ck_settlements_fees_not_negative` holds the sign.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ **THE PROVIDER'S OWN SETTLEMENT REFERENCE** — see the module docstring.
    #: Not a number this product mints, and half of the idempotency key.
    code = models.TextField()
    #: ⚠ **A `provider_key` STRING, NEVER A VENDOR NAMED IN CODE.** Which
    #: processor this is belongs to the tenant's integration connection
    #: (`BR-INT-037`, PO ruling 2026-09-05: *"we will have multiple payment
    #: providers integrated using integration module. For given utility we will
    #: activate 1 or 2."*). `G77` fails the merge on a `provider_key ==`
    #: comparison anywhere outside `adapters/` and `manifests/`, and nothing in
    #: this module compares this column to a literal.
    provider = models.TextField()
    #: When the PROVIDER says it paid out. Their clock, not ours — `BR-TEN-043`
    #: and `G6` keep this module from reading one at all.
    paid_out_at = models.DateTimeField()
    #: What the customers paid, before the provider kept anything.
    gross = models.DecimalField(max_digits=18, decimal_places=4)
    #: What the provider kept. POSITIVE, and its own expense when it posts.
    fees = models.DecimalField(max_digits=18, decimal_places=4)
    #: What reached (or will reach) the utility's bank. `gross - fees`.
    net = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")  # CHAR(3), hard rule 2
    #: The bank statement line this payout was identified on. NULL until it is
    #: — and `status` cannot disagree with that, by CHECK constraint.
    #:
    #: ⚠ **A ForeignKey HERE AND A PLAIN UUID ON `payments`, AND THE DIFFERENCE
    #: IS NOT AN INCONSISTENCY.** `bank_lines` is a PAYMENTS table created by
    #: `payments/0004`, so there is no module boundary and no migration order to
    #: break (B11 F-3) — an FK is simply available and gives referential
    #: integrity for free.
    #:
    #: ⛔ **THE SECOND HALF OF THIS NOTE IS SUPERSEDED — `payments.settlement_id`
    #: NO LONGER EXISTS (`payments/0044`, `OQ-PAY-12608`, 2026-09-24).** It read
    #: that the pointer was *a plain uuid for the reason `payments/0035` records
    #: for `counter_session_id`: it sits beside `deposit_batch_id` on the same
    #: rows and on the same list*. It never sat anywhere, because nothing could
    #: write it: hard rule 4's trigger froze it in every status, and the PO
    #: dropped the column rather than widening the lock. **There is no longer a
    #: difference to explain** — `settlement_members.settlement_id` below is the
    #: only place a payment's payout is held.
    bank_line = models.ForeignKey(
        "payments.BankLine",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="bank_line_id",
        related_name="settlements",
    )
    status = models.TextField(
        choices=[(one, one) for one in SETTLEMENT_STATUSES], default=SETTLEMENT_RECEIVED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settlements"
        constraints = [
            # ── `P5.3` · HARD RULE 6 — A REDELIVERY WRITES NOTHING TWICE ────
            # The drawing's own key: `(tenant, provider, settlement id)`. This
            # is the DATABASE half; `settlements.ingest_payout` holds the cheap
            # pre-insert lookup, and the two are asserted separately for the
            # reason `webhooks.py` records — `DEF-058` is what happens when one
            # guard silently stands in for another.
            models.UniqueConstraint(
                fields=["tenant", "provider", "code"],
                name="uq_settlements_provider_code",
            ),
            # A provider's own arithmetic, checked rather than re-derived.
            models.CheckConstraint(
                condition=Q(net=models.F("gross") - models.F("fees")),
                name="ck_settlements_net_ties",
            ),
            # `fees` is what was KEPT, so it is positive (or zero — a payout
            # with no fee is real; a free ACH rail has none).
            models.CheckConstraint(
                condition=Q(fees__gte=0),
                name="ck_settlements_fees_not_negative",
            ),
            # The status and the pointer are ONE fact, not two.
            models.CheckConstraint(
                condition=(
                    Q(status=SETTLEMENT_MATCHED, bank_line__isnull=False)
                    | Q(status=SETTLEMENT_RECEIVED, bank_line__isnull=True)
                ),
                name="ck_settlements_matched_has_line",
            ),
        ]
        indexes = [
            # The list screen (`P5.7`): this tenant's payouts, newest first.
            # ⚠ `NFR-3` — every list in this product is paged in SQL, and an
            # index the sort can walk is what makes `LIMIT`/`OFFSET` cheap at
            # the top of tier T5.
            models.Index(fields=["tenant", "-paid_out_at"], name="ix_settlements_paid_out"),
            # *Which payouts are still waiting for their bank credit?* — the
            # question the bank-rec screen asks, and the only one `status` is
            # filtered on.
            models.Index(fields=["tenant", "status"], name="ix_settlements_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug convenience
        return f"{self.provider}:{self.code}"


class SettlementMember(models.Model):
    """One payment inside one payout, with what the provider kept on IT.

    ⚠ **`gross` HERE IS THE PAYMENT'S OWN AMOUNT AND IT IS NEVER NET.** This is
    the money-correctness heart of the phase, stated on the column that would
    carry the error: a **$100.00** card payment with a **$2.90** fee is **a
    $100.00 payment and a $2.90 expense** — never a $97.10 payment. The customer
    paid the gross; the fee is the utility's cost of collecting it. Writing
    $97.10 here would leave the customer's account $2.90 short of what they
    actually paid and the trial balance tied to the wrong number.

    `ingest_payout` refuses a member whose `gross` does not equal the payment's
    own `amount`, so the wrong version cannot be written even by a caller that
    means to.

    ⚠ **A PAYMENT BELONGS TO AT MOST ONE PAYOUT**, and that is
    `uq_settlement_members_payment` rather than a service rule: one dollar
    cannot be paid out twice, and a second membership row would make the
    question *which payout was this in?* have two answers.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    settlement = models.ForeignKey(
        Settlement,
        on_delete=models.PROTECT,
        db_column="settlement_id",
        related_name="members",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        db_column="payment_id",
        related_name="settlement_memberships",
    )
    #: What the CUSTOMER paid. Equal to `payments.amount`, checked on write.
    gross = models.DecimalField(max_digits=18, decimal_places=4)
    #: What the provider kept on this one payment. POSITIVE, and zero is real.
    fee = models.DecimalField(max_digits=18, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settlement_members"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "payment"],
                name="uq_settlement_members_payment",
            ),
            models.CheckConstraint(
                condition=Q(fee__gte=0),
                name="ck_settlement_members_fee_not_negative",
            ),
        ]
        indexes = [
            # *What is inside this payout?* — the `5·2` screen's whole read,
            # paged in SQL like every other list (`NFR-3`).
            models.Index(fields=["tenant", "settlement"], name="ix_settlement_members_set"),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug convenience
        return f"{self.settlement_id}:{self.payment_id}"

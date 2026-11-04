# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 lane H — the PO ruling of 2026-09-15: *"payemnt should
#           show in payments, in ledge and in fiannce books"*.
# Story:    US-CUS-0xx (capture step 5, `Taking the money`) · US-LED-001 (the
#           source-event posting contracts)   Screens: the capture wizard's
#           step 5 · S33 · the finance books
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE — migration 0028) ·
#           hard rule 2 (money 4 dp into an 18,6 container + CHAR(3), display 2,
#           never float) · hard rule 4 (financial immutability — the freeze
#           trigger is in migration 0027) · hard rule 5 (only the ledger posting
#           service writes journal lines) · hard rule 6 (idempotency — one
#           receipt number, one row) · hard rule 7 (audit) · BR-CUS-090 (the
#           counter accepts what is handed over) · BR-PAY-1140 (this table)
# Tests:    06-backend/tests/test_cr094_counter_receipt_posts.py
# Impacts:  apps/payments/counter_receipts.py (the only writer) ·
#           apps/payments/ledger_seam.py (the two postings) ·
#           apps/payments/apps.py (`ready()` registers this module) ·
#           apps/customers/payments_seam.py (customers' only door to it)
# ───────────────────────────────────────────────────────
"""payments — `counter_receipts`: **money taken at a counter before there is an
account to put it on.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — ledger posting and money rounding are
CLAUDE.md 🔒 sensitive paths. AI-authored 2026-09-15 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

╔══════════════════════════════════════════════════════════════════════════╗
║  A `Payment` IS MONEY PAID BY AN ACCOUNT. THIS IS MONEY PAID BY SOMEBODY ║
║  WHO IS APPLYING TO BECOME ONE. THEY ARE DIFFERENT FACTS.                ║
╚══════════════════════════════════════════════════════════════════════════╝

WHY THIS TABLE EXISTS AND NOT A NULLABLE `payments.account_id`
--------------------------------------------------------------
The PO ruled WHERE the $25.00 must be visible and said, in the same breath,
that which table holds it *"is the PAYMENTS module's design to make and to
record with its reasoning"*. The reasoning, in full, is the decision-log row of
2026-09-15 beginning *"DECIDED — THE COUNTER RECEIPT IS A `counter_receipts`
ROW IN PAYMENTS"*. In short, and measured before it was decided:

  * `payments.account_id` is a **reviewed cross-module FK** under B2 §2 and
    `apps/payments` reads it in **161 places across 40 files** — 27 of them
    `select_related`/`values` clauses that would begin yielding a `None` for
    which nobody has written a branch. Widening it is a one-way door.
  * The blueprint's own sentence survives the ruling. `04 Accounts` p079 says
    *"No journal line, no invoice, no account — there is no account yet"*; the
    ruling reversed *posts nothing* and left **no account** standing.
  * The shape is already in this module one table along. `payment_import_rows`
    is money that has arrived and cannot yet be attached: a nullable account, a
    `payment_id` written at COMMIT, and a `commit_error` column whose docstring
    says *"a row that skipped silently would be money nobody chased"*. This is
    that pattern with a service request in place of a bank file, and
    `release_error` below is that column.

THE THREE MOMENTS, AND ONLY TWO OF THEM MOVE MONEY
--------------------------------------------------
    collection   DR the tender's clearing account, else 1010 Undeposited funds
                 CR 2400 Customer credit balances          state → `held`
    approval     DR 2400  CR the charge code's own revenue account
                                                           state → `applied`
    refusal      DR 2400  CR the charge code's own revenue account
                                                           state → `earned`
    ask for more NOTHING. No entry made, none reversed.     state unchanged

`applied` and `earned` post the IDENTICAL pair. They are two states rather than
one because the reason differs and a clerk reading the row is entitled to know
which door the request went out of — the ruling's own words are *"when it is
approved you can attached it to account"* against *"if it is refuse then it is
application fees non refundable"*.

⚠ **THE DEBIT IS NOT `1000 Cash`, AND THE RULING ROW THAT SAYS SO IS AMENDED
RATHER THAN OBEYED.** The PO's words of 2026-09-15 name no account; `1000` was
our rendering of them, and it collides with the PO's own ruling of 2026-08-11
closing `OQ-143` — *"Cash is received but undeposted in such case payment will
say csah but ledger will say undeposited - until bank record and reconcilaition
confirm it it is not realised"*. Cash on a counter is the paradigm case. The
amendment, its worked $25.00 and the cash double-count it avoids are in the
decision log of the same day.

⚠ **WHY THE STATE IS NOT DERIVED FROM THE REQUEST.** A reader could ask the
service request what happened to it and skip the column. It is stored because
the release is an EVENT with a date, an actor and a journal entry behind it, and
because a request may be reopened after a refusal (B18 §5.3.3, TC-REQ-10) — at
which point the request says `under_review` again while the $25.00 has been
revenue for a fortnight. The books do not reopen; this column is what says so.

APPEND-MOSTLY, AND THE FREEZE TRIGGER NAMES THE EXCEPTIONS
----------------------------------------------------------
Hard rule 4 protects `payments`, `invoices` and `journal_entries` by name and
says nothing about this table — so `migrations/0027` gives it a trigger of its
own. Everything about **what was handed over** is write-once: `amount`,
`currency`, `method_id`, `receipt_no`, `taken_at`, `taken_by`, every tender
detail column, and the source the money came in against. Only the RELEASE
columns may be written a second time, once each, by the one service that owns
them: `state`, `released_at`, `released_by`, `earned_amount`, `revenue_postings`,
`release_entry_id`, `release_error`, `payment_id`, `attached_at`.

That split is the whole point. A receipt whose AMOUNT could be edited would
stop being evidence of what was in the drawer — which is `payment_tenders`'
write-once law, one table along, for the identical reason.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk
from core.money_fields import money_field

# ── WHAT KIND OF THING THE MONEY CAME IN AGAINST ────────────────────────────
#: Today there is exactly one counter surface: capture step 5 takes the
#: application fee on a `service_requests` row. It is a TextField rather than a
#: hard-coded assumption because the next one — a counter payment against a work
#: order, say — must not need a migration to be recorded, and because a row that
#: does not say what it belongs to is a row nobody can reconcile.
SOURCE_SERVICE_REQUEST = "service_request"
SOURCE_TYPES = (SOURCE_SERVICE_REQUEST,)

# ── THE THREE STATES ────────────────────────────────────────────────────────
#: Taken, in the books as a LIABILITY, and owed to somebody who is not yet a
#: customer. `2400 Customer credit balances` holds it.
RECEIPT_HELD = "held"
#: The application was APPROVED. The fee is earned and the receipt may be
#: attached to the account the moment one exists.
RECEIPT_APPLIED = "applied"
#: The application was REFUSED. The fee is earned and non-refundable — the PO's
#: *"it stya in books"* — and nothing is given back.
RECEIPT_EARNED = "earned"
RECEIPT_STATES = (RECEIPT_HELD, RECEIPT_APPLIED, RECEIPT_EARNED)
#: The two TERMINAL outcomes, and the only two that release the liability. Ask
#: for more is neither, which is why it posts nothing — the ruling says so in as
#: many words and says it was written down precisely so a lane reading only the
#: other two clauses would not invent a third posting.
RECEIPT_RELEASED_STATES = (RECEIPT_APPLIED, RECEIPT_EARNED)


class CounterReceipt(models.Model):
    """One slip a clerk wrote at the counter, and everything the books need.

    **THE WORKED CASE THIS TABLE EXISTS FOR**, and it is the one the PO was
    shown: Sarah Miller hands over **$25.00 cash** on 12 May against receipt
    **`RCP-26-4471`**, for the `CC-REQFEE` application fee on her new-connection
    request. One row here, one balanced journal entry the same minute
    (DR `1010 Undeposited funds` $25.0000 / CR `2400 Customer credit balances`
    $25.0000), and — whichever way the application goes — a second balanced pair
    releasing that $25.0000 to the fee's own revenue account.

    Written by `apps/payments/counter_receipts.py` and by NOTHING else.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    # ── what the money came in against ─────────────────────────────────────
    source_type = models.TextField(default=SOURCE_SERVICE_REQUEST)
    #: The `service_requests` row. A deferred uuid and NOT an FK, for the reason
    #: `payment_tenders.customer_id` already records: `customers` is another
    #: module's table and payments carries no import edge into its ORM (B1). It
    #: is validated through customers' own published read before anything here
    #: is written.
    source_id = models.UUIDField()
    #: `SR-26-0048` — the number a clerk says out loud, snapshotted so a finance
    #: screen can name the request without a cross-module join, and so the row
    #: still reads if the request is ever renumbered. B14 rule 31: no database
    #: id is ever the visible value of a field.
    source_ref = models.TextField(null=True, blank=True)

    # ── what was handed over ───────────────────────────────────────────────
    #: `RCP-26-4471` — the number on the slip the clerk has just written.
    #: **RECORDED, NOT ALLOCATED.** Payments owns the `RCT-` series and this is
    #: not it: it is what a human wrote on a pad. Unique per tenant per source,
    #: which is hard rule 6's guard here (`uq_counter_receipts_source`).
    receipt_no = models.TextField()
    #: Hard rule 2: four decimal places written into an 18,6 container, and it
    #: DISPLAYS at two. Never a float, never cents.
    amount = money_field()
    currency = models.CharField(max_length=3, default="USD")  # CHAR(3), hard rule 2
    #: The tender. A real FK, exactly as `payments.method` and
    #: `payment_tenders.method` are — `tenancy.PaymentMethod` is the reviewed
    #: lookup (B2 §2 / r5 #20), and it is what `ledger_seam.
    #: tender_clearing_account_id` reads to decide WHICH holding account the
    #: collection debits. Nullable for the same reason those two are: a row may
    #: legitimately record no instrument, and a NULL means *unmapped*, which
    #: routes to `undeposited_funds` and is stated behaviour, not a fallback.
    method = models.ForeignKey(
        "tenancy.PaymentMethod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="method_id",
        related_name="counter_receipts",
    )

    # ── THE TENDER DETAIL (CR-094-BRC01 lane H) ────────────────────────────
    # PO, 2026-09-15: *"we need to allow to take payment detials, card detial
    # scheck details here curerntly is is not taking inputs"*. Six columns, and
    # the set is bounded on purpose.
    #
    # ⚠ **THE CARD NUMBER IS NOT HERE AND MUST NEVER BE.** Last four digits, the
    # brand and the terminal's authorisation code are enough to match our line
    # to the bank's, which is the whole job. The full number would put every
    # table in this database under card-industry rules for a fact no screen and
    # no report in this product reads. `StoredPaymentInstrument`'s own docstring
    # takes the identical posture one table along — *"a token, never a number"*.
    #: The last four digits as printed on the terminal slip. TEXT and not an
    #: integer: `0042` is four digits and 42 is not.
    card_last4 = models.TextField(null=True, blank=True)
    #: `visa` · `mastercard` · whatever the slip says. Free text rather than a
    #: lookup: it is transcribed from a piece of paper, and a refusal here would
    #: block a clerk over a brand nobody has seeded.
    card_brand = models.TextField(null=True, blank=True)
    #: The terminal's authorisation code — the string the acquirer's statement
    #: carries, and the one thing that matches our line to theirs.
    card_auth_code = models.TextField(null=True, blank=True)
    #: The cheque's own three facts. **The names are `payments`' names on
    #: purpose** — `confirmation` holds the number there, `drawer_bank` the
    #: bank and `cheque_date` the date on the face — so `attach_to_account`
    #: copies across without a mapping table nobody would maintain.
    cheque_no = models.TextField(null=True, blank=True)
    drawer_bank = models.TextField(null=True, blank=True)
    cheque_date = models.DateField(null=True, blank=True)

    # ── when, and by whom ──────────────────────────────────────────────────
    #: BR-PAY-021's posting moment, and BR-TEN-043: named by the caller, never
    #: read from a clock inside this module.
    taken_at = models.DateTimeField()
    taken_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="taken_by",
        related_name="+",
    )

    # ── WHICH TILL THE MONEY WENT INTO (OQ-PAY-12621, `payments/0045`) ──────
    #: The `counter_sessions` row open when this receipt was taken.
    #:
    #: ⚠ **IT EXISTS SO THE DRAWER BALANCES, AND THAT IS A PO RULING RATHER
    #: THAN A TIDINESS (`OQ-PAY-12621`, 2026-09-24, option (a); PO: *"p1 a"*).**
    #: Two earlier rulings met here and produced a WRONG POSTING. A2
    #: (2026-09-19) posts an application fee at collection with **no payment
    #: row**, so `running_split` — which reads `payments` — could not see it;
    #: the 2026-09-23 ruling then made a drawer difference REACH THE BOOKS. So
    #: the cash was physically in the drawer, the expected count did not
    #: include it, the close read OVER by the fee, and that over POSTED: **one
    #: fee booked twice.** Worked, and it is the ruling's own figure: Dana
    #: takes Sarah Miller's **$70.00** in cash, counts **$470.00** at close
    #: against an expected **$400.00** → `$70.00` over, posted again. With this
    #: column the expected count is **$470.00** and the difference is zero.
    #:
    #: ⚠ **A PLAIN UUID AND NOT A ForeignKey, FOR THE REASON `payments/0035`
    #: ALREADY RECORDS FOR `payments.counter_session_id`.** `counter_sessions`
    #: is a PAYMENTS table, so no module boundary is crossed and an FK is
    #: available — but the sibling column answering this same *which container
    #: did this money land in* question about the same tills is a plain uuid,
    #: and two columns answering one question in two shapes is what gets read
    #: as meaning something.
    #:
    #: ⚠ **NULLABLE, AND NOT AS A DEFAULT.** `till_refusal` is called at the
    #: ENDPOINT and not inside `record_counter_receipt`, because the sample
    #: fixture seeds a counter collection for a utility that has no clerks
    #: (`P2.23`) — so a receipt can legitimately be written with no till open,
    #: and every row taken before this column existed has none. A `NOT NULL`
    #: would refuse the fixture and the history together. **A null means this
    #: receipt joins no drawer**, which is the honest answer and not a zero.
    counter_session_id = models.UUIDField(null=True, blank=True)
    # ── what Record a payment also asks — DEF-CUS-6376 (payments/0042) ─────
    #: **The business day this money counts for** — Record a payment's posting
    #: date, typed by the clerk and PROPOSED as the tenant's today (BR-PAY-033,
    #: BR-TEN-081). It is the collection entry's `entry_date`, and the day the
    #: `Payment` is dated when `attach_to_account` finally writes one. A DATE
    #: and not an instant: a calendar day typed by a person in the utility's own
    #: zone. NULL only on the rows taken before the column existed, whose
    #: entries were dated `taken_at.date()`.
    posted_on = models.DateField(null=True, blank=True)
    #: The instrument's own number — a check number, a card authorisation, a
    #: money-order serial. **`payments`' name for it on purpose**, so
    #: `attach_to_account` copies it across by name. NOT the receipt number,
    #: which is the slip the CLERK handed back.
    confirmation = models.TextField(null=True, blank=True)
    #: Free text, as on Record a payment.
    memo = models.TextField(null=True, blank=True)

    #: The ledger entry the COLLECTION made. A bare uuid rather than an FK, for
    #: the reason `payments.journal_entry_id` already records: the ledger
    #: publishes no key→entry read, and this is the only way a row can name the
    #: entry it is evidence for.
    collection_entry_id = models.UUIDField(null=True, blank=True)

    # ── the release, and it is the only half that is ever written twice ────
    state = models.TextField(default=RECEIPT_HELD)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="released_by",
        related_name="+",
    )
    #: How much of `amount` became revenue. It is `min(amount, quoted)` and the
    #: cap is a decision with its own decision-log row: `4xxx` is money EARNED
    #: and `2400` is money HELD, so $30.00 handed over against a $25.00
    #: application fee earns $25.0000 and leaves **$5.0000 a liability**. A
    #: refusal that earned money we owe back is the mirror of the defect p085
    #: warns about.
    earned_amount = money_field(null=True, blank=True)
    #: `[{"ledger_account_id": …, "charge_code": "CC-REQFEE", "amount": "25.0000"}]`
    #: — which revenue account took which part, snapshotted at the release. The
    #: mapping is a tenant SETTING and settings move; a row that could not say
    #: where its own money went would be unauditable a year later.
    revenue_postings = models.JSONField(null=True, blank=True)
    release_entry_id = models.UUIDField(null=True, blank=True)
    #: **Why the release did NOT post.** `payment_import_rows.commit_error`'s
    #: reason, word for word: a row that skipped silently would be money nobody
    #: chased. The terminal outcome is never blocked by a missing GL mapping —
    #: a clerk must always be able to refuse an application — so the liability
    #: stands, visibly, and this column says whose configuration to fix.
    release_error = models.TextField(null=True, blank=True)

    # ── the attach, when there is finally an account ───────────────────────
    #: Set by `attach_to_account` when a `Payment` is written on the account the
    #: approved application opened. A bare uuid and not an FK, exactly as
    #: `payment_import_rows.payment_id` is: a staging row may name a payment
    #: without opening a second write path into `payments`.
    #:
    #: ⚠ **NOTHING CALLS THAT FUNCTION IN PRODUCTION TODAY AND `DEF-PAY-5394`
    #: SAYS SO OUT LOUD.** Approval raises WORK; it opens no account, and
    #: `customers.Account` carries no link back to a request — so at the moment
    #: of approval there is nothing to attach to. The MONEY half of the ruling
    #: is complete without it.
    payment_id = models.UUIDField(null=True, blank=True)
    attached_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "counter_receipts"
        constraints = [
            # Hard rule 6, and it is the drawing's rule rather than a database
            # habit. p079: *"Collecting twice is refused by name. The same
            # receipt number again answers with what is already recorded; a
            # DIFFERENT one on a request that has already been collected is
            # refused and names the receipt it already holds."* One source, one
            # receipt — so a double-submitted form cannot make two.
            models.UniqueConstraint(
                fields=["tenant", "source_type", "source_id"],
                name="uq_counter_receipts_source",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="ck_counter_receipts_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=RECEIPT_STATES),
                name="ck_counter_receipts_state",
            ),
        ]
        indexes = [
            # NFR-3: every list is paginated in the database, and the finance
            # read is ordered by the moment the money was taken.
            models.Index(fields=["tenant", "-taken_at"], name="ix_counter_receipts_taken"),
            models.Index(fields=["tenant", "state"], name="ix_counter_receipts_state"),
            # `running_split` asks *what did THIS till take in fees?* on every
            # open Close screen, so the drawer figure is one indexed read
            # rather than a scan of every receipt the tenant has ever taken
            # (`NFR-3`/`NFR-5` — no cap, so no scan).
            models.Index(
                fields=["tenant", "counter_session_id"],
                name="ix_counter_receipts_session",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug convenience
        return f"{self.receipt_no} {self.amount} {self.currency}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 lane H (the PO ruling of 2026-09-15 · blueprint `04
#         Accounts` p079 and p085 read as IMAGES at scale 2 · `apps/ledger/
#         chart.py` · B2 §2 · hard rules 1, 2, 4, 5, 6, 7)
# generated: 2026-09-15 by the CR-094-BRC01 counter-fee lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the finance SCREEN for these rows is not
#         built — `GET /counter-receipts` serves them and no page mounts it yet;
#         named in the lane report) F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING)
# gates: ruff✔ black✔ · makemigrations --check clean · pytest
#         tests/test_cr094_counter_receipt_posts.py
# exceptions: `payment_id`'s writer `attach_to_account` has a test and no
#         production caller — `DEF-PAY-5394`, because approval opens no account
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────

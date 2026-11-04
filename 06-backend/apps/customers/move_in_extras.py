# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 `P1.01` (lane MVI-SCHEMA). PO, mock-up v12: *"this
#           should be fees and table array and allow user to add all fees for
#           this move in - may will come from plan and some can be come from
#           others charge codes"*; v13: *"This should be table array and allow
#           user to add more details while we show default - What goes out -
#           call it communication or messaging"*.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE — `customers/0080`) · hard rule 2
#           (money to 4 places, `CHAR(3)` currency) · hard rule 4's posture (a
#           written line is never edited; a correction is a new row) ·
#           BR-BIL-007 (a fee is a tenant charge code) · BR-BIL-012 (the first
#           bill carries the move's one-time lines) · BR-CUS-152 (the move record
#           is the record of a move that HAS happened)
# Migration: apps/customers/migrations/0080_cr171_p1_01_move_in_redesign.py 🔒
# Tests:    06-backend/tests/test_cr171_p1_01_move_in_schema.py ·
#           06-backend/tests/test_cr171_p1_01_rls_pg.py
# Writers:  P1.12 (fee lines, at Complete) · P1.20 (extra messages, at Complete;
#           `notification_id` when queued) · Readers: P1.14 (first bill) ·
#           P1.05/P2.11/P2.12 (the details view's Billing and Messages tabs)
# ───────────────────────────────────────────────────────
"""**The two lists a move-in carries that nothing held before: its FEES and its
EXTRA MESSAGES.** Both hang off `move_records`, the record written at Complete.

═══════════════════════════════════════════════════════════════════════════
1 · WHY THEY HANG OFF THE MOVE RECORD AND NOT THE JOB OR THE ACCOUNT
═══════════════════════════════════════════════════════════════════════════
* **Not `move_in_jobs`** — a job exists only for a move-in that came from an
  approved request (`request` is NOT NULL there); a walk-in move-in has no job
  and still has fees.
* **Not `accounts`** — the account outlives the move; *"the fees of THIS
  move-in"* is the question the Billing tab asks (image 26), and a second
  move-in on the same account (a correction, a return) must not merge with it.
* **Before Complete** both lists live in the parked wizard
  (`wizard_parks.values`), as every other unfinished fact of a move-in does
  (CR-171 §6 (2): *"and their parked shape before commit"* — the parked shape is
  the wizard's JSON, not a table).

═══════════════════════════════════════════════════════════════════════════
2 · A FEE LINE STATES WHAT WAS CHARGED; IT DOES NOT DECIDE TAX
═══════════════════════════════════════════════════════════════════════════
There is **no `taxable` column, deliberately — and now permanently.**
`OQ-BIL-12788` was CLOSED by the PO on 2026-10-05, option (a), verbatim: *"this
si correct - a (recommended) $25.00 (never taxed at move-in)"*. A move-in fee is
never taxed at move-in, whether taken today or added to the first bill, so a
column would only ever hold `false`. ⚠ This paragraph read *"OPEN and stopped for
the PO … stubbed on the taxing path"* until the ruling; there is no stub
(`move_fees.py`, lane MVI-MONEY, P1.12).

**Money:** `amount` is an AMOUNT at 4 places (`core.money_fields`) and is
never negative — a credit is billing's, not a move-in fee.

⚠ **NOTHING UPDATES A WRITTEN LINE** — the move record's own posture
(BR-CUS-152). A wrong fee after Complete is corrected by a NEW row from whatever
door P1.22 builds, never by editing this one. No trigger enforces it today; it
is stated, and `P1.12`'s tests are where it becomes a guarantee.

═══════════════════════════════════════════════════════════════════════════
3 · THE EXTRA MESSAGES ARE THE PLAN, NOT THE SENDS
═══════════════════════════════════════════════════════════════════════════
A row says *send this template, to this person, by this channel, at this
moment*. The two defaults (`move_in_welcome`, `service_agreement`) are NOT rows
here (image 46, *"Defaults come from Settings · add any other"*); both are
queued by their own writers at Complete (the service agreement since
`DEF-CUS-9743`, 2026-10-05). The SEND is `notifications`' own
outbound row; `notification_id` points at it once `P1.20` queues the message
(a UUID with no foreign key: `notifications` is another module, B2 §2).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.dbfields import uuid7_pk
from core.money_fields import money_field

# ═══════════════════════════════════════════════════════════════════════════
# FEE LINES
# ═══════════════════════════════════════════════════════════════════════════
FEE_KIND_DEPOSIT = "deposit"
FEE_KIND_FEE = "fee"
FEE_KINDS: tuple[str, ...] = (FEE_KIND_DEPOSIT, FEE_KIND_FEE)

#: *From* on image 41: the plan put it in (locked) or the clerk added a charge code.
FEE_SOURCE_PLAN = "plan"
FEE_SOURCE_CHARGE_CODE = "charge_code"
FEE_SOURCES: tuple[str, ...] = (FEE_SOURCE_PLAN, FEE_SOURCE_CHARGE_CODE)


class MoveFeeLine(models.Model):
    """One row of a move-in's *Fees* table (images 41, 43, 26)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    move_record = models.ForeignKey(
        "customers.MoveRecord",
        on_delete=models.PROTECT,
        db_column="move_record_id",
        related_name="fee_lines",
    )
    #: The row's place in the table (*#*), unique per move.
    seq = models.SmallIntegerField()
    #: `deposit` | `fee`. The deposit is one capability (`deposit.py`,
    #: `BR-CUS-1050`) and is told apart by KIND, never by reading `code`.
    kind = models.TextField()
    #: `plan` | `charge_code` — §1 of image 41's *From* column.
    source = models.TextField()
    #: The rating charge code priced (BR-BIL-007). ⚠ A UUID, NOT A FOREIGN KEY:
    #: `charges` is RATING's table and customers may not add a cross-module FK
    #: outside B2 §2's reviewed set — the posture `TaxExemptionCertificate.
    #: account_id` takes in the other direction. NULL where no code exists (a
    #: plan deposit `deposit.py` priced without one).
    charge_code_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → rating.charges
    #: The code AS QUOTED on the day (*DEPOSIT*, *CONNECT*, *RUSH*) and its
    #: description — written once, because a later rename of the charge code
    #: must not rewrite what this move-in was charged.
    code = models.TextField()
    description = models.TextField(null=True, blank=True)
    amount = money_field()
    currency = models.CharField(max_length=3, default="USD")
    note = models.TextField(null=True, blank=True)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "customers"
        db_table = "move_fee_lines"
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=FEE_KINDS), name="ck_move_fee_lines_kind"),
            models.CheckConstraint(
                condition=Q(source__in=FEE_SOURCES), name="ck_move_fee_lines_source"
            ),
            models.CheckConstraint(condition=Q(amount__gte=0), name="ck_move_fee_lines_amount"),
            models.UniqueConstraint(fields=["move_record", "seq"], name="uq_move_fee_lines_seq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "move_record"], name="ix_move_fee_lines_move"),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# EXTRA MESSAGES
# ═══════════════════════════════════════════════════════════════════════════
#: *To* on image 46 — the PO's v13 words: *"sent to the customer, a co-owner or
#: the unit owner"*.
RECIPIENT_CUSTOMER = "customer"
RECIPIENT_CO_OWNER = "co_owner"
RECIPIENT_UNIT_OWNER = "unit_owner"
RECIPIENTS: tuple[str, ...] = (RECIPIENT_CUSTOMER, RECIPIENT_CO_OWNER, RECIPIENT_UNIT_OWNER)

#: *"by email, text, letter or portal"* (v13).
CHANNELS: tuple[str, ...] = ("email", "text", "letter", "portal")

#: *"on complete / the day before move-in / on the move-in date / the day
#: before the visit"* (v13).
SEND_WHEN: tuple[str, ...] = (
    "on_complete",
    "day_before_move_in",
    "on_move_in_date",
    "day_before_visit",
)


class MoveExtraMessage(models.Model):
    """One added row of a move-in's *Messaging* table (images 45, 46, 28)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    move_record = models.ForeignKey(
        "customers.MoveRecord",
        on_delete=models.PROTECT,
        db_column="move_record_id",
        related_name="extra_messages",
    )
    seq = models.SmallIntegerField()
    #: The notification template the *Message* dropdown chose (a template KEY,
    #: the vocabulary `notifications` owns).
    template_key = models.TextField()
    recipient = models.TextField()
    #: Which co-owner, when `recipient` is `co_owner` — and only then.
    co_owner = models.ForeignKey(
        "customers.AccountCoOwner",
        on_delete=models.PROTECT,
        db_column="co_owner_id",
        related_name="+",
        null=True,
        blank=True,
    )
    channel = models.TextField()
    send_when = models.TextField()
    #: The `notifications` outbound row once `P1.20` has queued it. ⚠ A UUID,
    #: NOT A FOREIGN KEY (another module's table, B2 §2). NULL = not yet queued.
    notification_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → notifications
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "customers"
        db_table = "move_extra_messages"
        constraints = [
            models.CheckConstraint(
                condition=Q(recipient__in=RECIPIENTS), name="ck_move_extra_messages_recipient"
            ),
            models.CheckConstraint(
                condition=Q(channel__in=CHANNELS), name="ck_move_extra_messages_channel"
            ),
            models.CheckConstraint(
                condition=Q(send_when__in=SEND_WHEN), name="ck_move_extra_messages_send_when"
            ),
            # A co-owner recipient names which one; nobody else names one.
            models.CheckConstraint(
                condition=(Q(recipient=RECIPIENT_CO_OWNER) & Q(co_owner__isnull=False))
                | (~Q(recipient=RECIPIENT_CO_OWNER) & Q(co_owner__isnull=True)),
                name="ck_move_extra_messages_co_owner",
            ),
            models.UniqueConstraint(
                fields=["move_record", "seq"], name="uq_move_extra_messages_seq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "move_record"], name="ix_move_extra_messages_move"),
        ]

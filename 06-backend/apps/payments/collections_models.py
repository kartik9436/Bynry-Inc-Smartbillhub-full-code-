# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-017 (plan rows + schedule math + activation on signature) ·
#           US-PAY-018 (plan notices) · US-PAY-015 (manual reminder +
#           disconnect-notice modals) · US-PAY-016 (returned mail → bad address
#           → needs attention) · US-PAY-012 (write-offs — the `write_offs`
#           table, initiated in Payments and approved in Finance)
#           Screens: S21 · S24 · S33 · S34 · S35
# Rules:    BR-CUS-043 (one live plan per account; the schedule must re-sum
#           exactly; while active AND current, dunning and disconnect pause;
#           late-fee suspension is a per-plan election) · BR-CUS-044 (proposed →
#           agreement_sent → active ON THE CUSTOMER'S SIGNATURE ALONE → closed;
#           ⚠ its `defaulted` state and {missed_count} clause are SUPERSEDED —
#           PO 2026-08-11, "nodrop we chase for payments until write off") ·
#           BR-PAY-012 (a down payment carries purpose plan_down) · BR-PAY-016
#           (plan notices; ⚠ its "2nd miss VOIDS plan" clause is SUPERSEDED by
#           the same ruling) · BR-PAY-017 (the tenant-config collection ladder)
#           · BR-PAY-018 (returned mail → bad-address flag → needs-attention →
#           paper suppressed until verified; balances unaffected) · BR-PAY-021
#           (on-time is judged on the POSTING date) · BR-NOT-005 (every notice
#           is a queue-write; the dispatcher sends) · BR-TEN-043 (event time is
#           an argument) · CLAUDE.md rule 1 · rule 2 · rule 4 · rule 6 · rule 7
# Tests:    06-backend/tests/test_us_pay_017_payment_plans.py ·
#           06-backend/tests/test_us_pay_018_plan_notices.py ·
#           06-backend/tests/test_us_pay_015_notice_modals.py ·
#           06-backend/tests/test_us_pay_016_returned_mail.py ·
#           06-backend/tests/test_us_pay_012_write_offs.py
# Impacts:  apps/payments/plans.py · apps/payments/notices.py ·
#           apps/payments/dunning.py · apps/payments/returned_mail.py ·
#           apps/payments/apps.py (registers this module) ·
#           apps/customers/payment_plan_service.py (the S24 wizard, which hands
#           its schedule to this module's service through the customers seam)
# ───────────────────────────────────────────────────────
"""The plan and collections tables — B2 Addendum r12 #7, #8, #9.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — `payment_plans` and
`payment_plan_installments` decide what a customer in arrears is asked to pay
and when, and money math is a CLAUDE.md 🔒 path. AI-authored 2026-08-11 under
the PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

**WHY THESE CLASSES ARE NOT IN `apps/payments/models.py`.** The reason
`apps/payments/bankrec_models.py` already records for itself: another lane held
that file, and two lanes in one models module is how a migration graph forks.
`app_label` is `payments`, the tables are payments' own, and
`apps/payments/apps.py` imports this module so the registry sees them.

════════════════════════════════════════════════════════════════════════════
THERE IS NO `missed_count` COLUMN, NO `defaulted` STATE AND NO `void` STATE
════════════════════════════════════════════════════════════════════════════
B2 Addendum r12 #9 adds `missed_count` to `payment_plans`, BR-PAY-016 says
*"2nd miss VOIDS plan"*, BR-CUS-044 carries a `defaulted` state, and J13 is a
journey literally titled *born to die*. **All four are SUPERSEDED** by the PO's
ruling of 2026-08-11, verbatim:

    "nodrop we chase for payments until write off"

So `PLAN_STATUSES` has FOUR values. An account that falls behind is CHASED
through the ordinary collections path to write-off and **stays on its plan while
that happens**. The absence is the rule, not work left undone — `apps/customers/
payment_plan.py` built the same absence on the customers side and asserts that
ten misses change nothing, and a column here would be an invitation to wire the
drop-off back up.

Notices still go out. A miss is a fact worth recording so collections can chase
it, and `notice_history` is where that fact lives — as HISTORY, not as a
counter with a threshold behind it.

════════════════════════════════════════════════════════════════════════════
WHAT IS TRANSCRIBED, AND WHAT IS AN ENG-LEAD DDL CALL
════════════════════════════════════════════════════════════════════════════
`payment_plans` + `payment_plan_installments` are **B2 §2** (payments-owned,
named there and cited by BR-CUS-037 as the reason customers may not write them);
`notice_history` and the per-account collection state are **r12 #7**; the
delivery-return events are **r12 #8**. None of the four names its columns, so
r12 #15's rule applies — exact DDL is Eng-Lead-owned — and every column below
cites the rule that puts it there.

**`accounts.bad_address` (r12 #8) IS NOT HERE AND CANNOT BE** — it is a column on
`accounts`, which is customers-owned, and B1 forbids this module writing it.
⚠ **UNTIL 2026-09-23 THIS PARAGRAPH WENT ON TO SAY *"So the flag is DERIVED"*
from unresolved `delivery_return_events`, and that left two flags that never met
(`DEF-PAY-6342`):** the account page, the unit page, the runbooks and the portal
read the column nobody wrote, while payments read its own derivation. The column
is now the one fact — CUSTOMERS writes it (`apps/customers/bad_address.py`), at
`returned_mail`'s request — and these rows are its HISTORY and the
needs-attention list, which is what a row with a date and a resolution is for.
"""

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

#: BR-CUS-044 as the PO's ruling of 2026-08-11 leaves it. FOUR states, and the
#: two that are missing are missing on purpose (see the module docstring). Kept
#: identical to `apps.customers.payment_plan.PLAN_STATUSES` — the wizard and the
#: rows must agree, and two vocabularies is how a state machine grows a sixth
#: state nobody ruled.
PLAN_PROPOSED = "proposed"
PLAN_AGREEMENT_SENT = "agreement_sent"
PLAN_ACTIVE = "active"
PLAN_CLOSED = "closed"
PLAN_STATUSES = (PLAN_PROPOSED, PLAN_AGREEMENT_SENT, PLAN_ACTIVE, PLAN_CLOSED)

#: US-CUS-018 TC-7 / BR-CUS-043 — "exactly one LIVE plan per account".
LIVE_PLAN_STATUSES = (PLAN_PROPOSED, PLAN_AGREEMENT_SENT, PLAN_ACTIVE)

#: The notice kinds this module writes history for. The collection-ladder tiers
#: are BR-PAY-017's (US-PAY-014/015); the plan ones are BR-PAY-016's
#: (US-PAY-018). One vocabulary, because US-PAY-015 TC-4 dedupes a TIER across
#: the manual modal and the automatic engine and cannot do that across two.
NOTICE_REMINDER = "reminder"
NOTICE_DISCONNECT = "disconnect"
NOTICE_PLAN_REMINDER = "plan_installment_reminder"
NOTICE_PLAN_MISSED = "plan_installment_missed"
NOTICE_PLAN_SECOND = "plan_installment_second_notice"
NOTICE_TYPES = (
    NOTICE_REMINDER,
    NOTICE_DISCONNECT,
    NOTICE_PLAN_REMINDER,
    NOTICE_PLAN_MISSED,
    NOTICE_PLAN_SECOND,
)

#: BR-PAY-017's ladder tiers, and US-PAY-015's modal offers the same three.
TIER_FRIENDLY = "friendly"
TIER_FIRST_10_DAY = "first_10_day"
TIER_SECOND_5_DAY = "second_5_day"
TIER_FINAL_48_HOUR = "final_48_hour"
DISCONNECT_TIERS = (TIER_FIRST_10_DAY, TIER_SECOND_5_DAY, TIER_FINAL_48_HOUR)

#: Every send AND every skip (BR-PAY-017 / J4 step 2: *"notice_history appended;
#: medical-hold skipped"*). A skip that left no row would be a silent exclusion,
#: which is the one thing a collections trail may not contain.
OUTCOME_SENT = "sent"
OUTCOME_SKIPPED = "skipped"
OUTCOMES = (OUTCOME_SENT, OUTCOME_SKIPPED)


class PaymentPlan(models.Model):
    """One arrears schedule (B2 §2 `payment_plans`, r12 #9).

    The MATH is not here and is not repeated anywhere in this module:
    `apps.customers.payment_plan.build_schedule` owns it (BR-CUS-043, frozen as
    GT-47 — 267.30 − 50 down over 6 → 5 × 36.22 + 36.20) and payments persists
    what the wizard computed. `plans.propose` re-validates the invariant
    (Σ instalments + down = total) rather than re-deriving the figures: a check
    catches a wrong schedule, a second implementation of the arithmetic
    eventually disagrees with the first.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    total_amount = models.DecimalField(max_digits=18, decimal_places=6)
    down_payment = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    currency = models.CharField(max_length=3, default="USD")  # rule 2 partner
    installment_count = models.IntegerField()
    cadence = models.TextField(default="monthly")
    status = models.TextField(default=PLAN_PROPOSED)

    #: BR-CUS-043's per-plan ELECTIONS — *"late-fee suspension is a per-plan
    #: election"*, not a global setting. `suspend_late_fees` defaults OFF and
    #: `suspend_disconnect` ON, which are the prototype's own S24 defaults
    #: (US-CUS-018 §1) carried through the wizard rather than re-decided here.
    suspend_late_fees = models.BooleanField(default=False)
    suspend_disconnect = models.BooleanField(default=True)
    autopay_enabled = models.BooleanField(default=True)

    #: BR-TEN-043 — business dates, supplied by the caller. `created_at` is when
    #: the row was written and is a different fact.
    proposed_on = models.DateField()
    agreement_sent_on = models.DateField(null=True, blank=True)
    #: BR-CUS-044: activation is the CUSTOMER's e-signature ALONE. No
    #: countersignature column exists because no countersignature exists.
    signed_on = models.DateField(null=True, blank=True)
    closed_on = models.DateField(null=True, blank=True)

    #: ⚠ **WHO OFFERED IT, KEPT ON THE PLAN — `CR-085` `CPB-21`, closing
    #: `OQ-CWP-1567` option (a) on 2026-09-08.** The clerk's identity used to
    #: exist ONLY on the `payment_plan.rows_written` audit row, and `audit_log`
    #: is pruned on a retention schedule — so a customer asking *who set this
    #: up* on a plan that is still running would eventually be told *we no
    #: longer know*. This is a durable FACT ABOUT THE PLAN rather than a trace
    #: of the action that made it, which is the shape
    #: `stored_documents.stored_by_user_id` already uses.
    #:
    #: ⚠ **NULL IS A REAL ANSWER AND IS NEVER FILLED IN.** A plan written
    #: before this column existed has no name to give, and neither has one
    #: written by a job (`core.audit.money_action`'s `AutomationActor` branch
    #: carries no user id at all, on purpose). The portal says so in the
    #: customer's own words instead of naming an office nobody recorded.
    #:
    #: ⚠ **THE ID NEVER REACHES A SCREEN** (B14 rule 31). `payment_plans_for_account`
    #: publishes it for the server to resolve; the portal seam turns it into a
    #: NAME and drops the id before the body is built.
    #: ⚠ **AN FK, LIKE `notice_history.actor` ONE CLASS DOWN, AND NOT A BARE
    #: UUID.** `OQ-CWP-1567` named `stored_documents.stored_by_user_id` as the
    #: shape, and that column is bare because a document may be stored by a
    #: PROCESS with no user at all. A plan is offered by a person or by nobody,
    #: so this module's own convention wins: `PROTECT` keeps the name readable
    #: for as long as the plan is (`BR-IDN-030` keeps user rows), and the read
    #: gets the name in one join instead of a second query per plan.
    offered_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="offered_by_user_id",
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_plans"
        indexes = [
            models.Index(fields=["tenant", "account", "status"], name="ix_plans_account"),
        ]
        constraints = [
            # BR-CUS-043 / US-CUS-018 TC-7, held by the DATABASE and not by a
            # SELECT-then-INSERT: two clerks on two screens is exactly the race
            # a check in Python loses, and the loser gives one debt two
            # schedules with no rule for which the customer signed.
            models.UniqueConstraint(
                fields=["tenant", "account"],
                condition=Q(status__in=LIVE_PLAN_STATUSES),
                name="uq_one_live_plan_per_account",
            ),
        ]


class PaymentPlanInstallment(models.Model):
    """One scheduled row (B2 §2, UNIQUE (plan, seq)).

    `paid_payment` and `paid_posted_on` record WHICH payment met this
    instalment and WHEN IT POSTED — BR-PAY-021: on-time is `posted_at ≤ due
    date`, and a cheque posted on the due date that clears three days later is
    ON TIME. Clearing dates never touch this table.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    plan = models.ForeignKey(
        PaymentPlan, on_delete=models.PROTECT, db_column="plan_id", related_name="installments"
    )
    seq = models.IntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")  # rule 2 partner
    paid_payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="paid_payment_id",
    )
    paid_posted_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_plan_installments"
        indexes = [
            models.Index(fields=["tenant", "plan", "due_date"], name="ix_plan_inst_due"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "plan", "seq"], name="uq_plan_installment"),
        ]


class NoticeHistory(models.Model):
    """Every notice SENT and every notice SKIPPED (r12 #7, J4 step-2 contract).

    APPEND-ONLY. This is the record a utility shows a regulator when a customer
    says they were never told — and a row that can be edited afterwards is not
    that record. The trigger is in the RLS migration; the service layer never
    updates.

    `outbound_message_id` is a plain uuid and not an FK: `outbound_messages` is
    notifications-owned, and while B2 r16 #7 opens it to cross-module WRITES
    through `queue_document`, it does not make it a target for other modules'
    foreign keys. The B11 F-3 deferred-uuid convention, used here for a boundary
    rather than for an unbuilt table.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    plan = models.ForeignKey(
        PaymentPlan, on_delete=models.PROTECT, null=True, blank=True, db_column="plan_id"
    )
    notice_type = models.TextField()
    tier = models.TextField(null=True, blank=True)
    channel = models.TextField(null=True, blank=True)
    outcome = models.TextField(default=OUTCOME_SENT)
    #: Why a notice was NOT sent — a medical hold, a suppressed address. A CODE,
    #: because the S34 column and the returned-mail report group on it.
    skip_reason = models.TextField(null=True, blank=True)
    outbound_message_id = models.UUIDField(null=True, blank=True)
    detail = models.JSONField(default=dict)
    actor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="actor_id"
    )
    #: BR-TEN-043 — the business date of the send, supplied by the caller.
    occurred_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notice_history"
        indexes = [
            models.Index(fields=["tenant", "account", "occurred_on"], name="ix_notice_hist_acct"),
            models.Index(fields=["tenant", "notice_type", "tier"], name="ix_notice_hist_tier"),
        ]


class AccountCollectionState(models.Model):
    """Where an account stands on the ladder (r12 #7).

    ONE row per account, and that is what makes US-PAY-015 TC-4 possible: the
    manual modal and the automatic engine (US-PAY-014) advance the SAME state,
    so a tier never double-sends. Two states — one for staff, one for the job —
    would send the 5-day notice twice to the customer who complained.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    tier = models.TextField(null=True, blank=True)
    tier_sent_on = models.DateField(null=True, blank=True)
    last_notice_on = models.DateField(null=True, blank=True)
    next_step_due = models.DateField(null=True, blank=True)
    #: US-PAY-019: WHY the ladder is or is not running, in a word the S34 column
    #: can show. Derived state is recomputed, never trusted from here — this is
    #: the last computed answer, kept so a clerk can see it without re-running
    #: the evaluation.
    paused_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_collection_state"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "account"], name="uq_collection_state_per_account"
            ),
        ]


class DeliveryReturnEvent(models.Model):
    """A piece of post came back (r12 #8, PE-16).

    ONE row per returned delivery, and `UNIQUE (tenant, outbound_message_id)` is
    US-PAY-016 TC-5's idempotency: marking the same piece returned twice — the
    obvious accident on a Tuesday stack of fourteen — writes one event, not two.

    `resolved_on` + `resolution` are the HISTORY of the account's bad-address
    flag, which is `accounts.bad_address` and is written by customers
    (`DEF-PAY-6342` — this docstring said *"An unresolved row IS the flag"*
    until 2026-09-23, and two flags that never met was the result). An
    unresolved row is a needs-attention row; the account's last one closing
    lowers the flag, and the history of both survives.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    #: Deferred uuid, not an FK — see `NoticeHistory.outbound_message_id`.
    outbound_message_id = models.UUIDField(null=True, blank=True)
    #: What came back, so the S30 delivery dashboard can name it.
    source_type = models.TextField(default="invoice")
    source_id = models.UUIDField(null=True, blank=True)
    returned_on = models.DateField()
    reason = models.TextField(null=True, blank=True)
    marked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="marked_by",
        related_name="delivery_returns_marked",
    )
    resolved_on = models.DateField(null=True, blank=True)
    #: J18 records THREE outcomes and they are not the same fact: an address
    #: corrected, an address verified-as-already-correct (carrier error), and
    #: one still unresolved at close of day. A single boolean would lose the
    #: middle one, which is the one that stops a clerk chasing it again.
    resolution = models.TextField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="resolved_by",
        related_name="delivery_returns_resolved",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "delivery_return_events"
        indexes = [
            models.Index(fields=["tenant", "account", "resolved_on"], name="ix_returns_account"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "outbound_message_id"],
                condition=Q(outbound_message_id__isnull=False),
                name="uq_return_per_delivery",
            ),
        ]


# ── write-offs (US-PAY-012 / BR-PAY-020, r12 #11) ───────────────────────────
#: The prototype's own four reasons (US-PAY-012 §1), verbatim. TEXT rather than
#: an FK for the reason `REVERSAL_REASONS` gives one file over: B2 r14 #2 puts
#: reason lookups in tenancy's seeded extensible family and tenancy has not
#: built one, so these are held in code until that table exists and the column
#: is plain text so the lookup can take it over without a data migration.
#:
#: *"Send to collections agency instead"* and *"Flag these accounts so future
#: service requires a deposit"* are NOT here: both are prototype checkboxes with
#: NO ratified rule (field-map P-4/P-5), and US-PAY-012 §1 excludes them from v1
#: by name. A value the column can hold is a value some path can write.
WRITE_OFF_REASON_UNCOLLECTIBLE = "uncollectible_120_days"
WRITE_OFF_REASON_BANKRUPTCY = "customer_bankruptcy"
WRITE_OFF_REASON_DECEASED = "deceased_no_estate"
WRITE_OFF_REASON_BELOW_THRESHOLD = "below_write_off_threshold"
WRITE_OFF_REASONS = (
    WRITE_OFF_REASON_UNCOLLECTIBLE,
    WRITE_OFF_REASON_BANKRUPTCY,
    WRITE_OFF_REASON_DECEASED,
    WRITE_OFF_REASON_BELOW_THRESHOLD,
)

#: BR-PAY-020's three-way split, as FOUR states on one row.
#:
#: ⚠ **THIS COMMENT SAID "two states" AND "There is no `rejected` state and no
#: `cancelled` one — neither is ruled" UNTIL 2026-09-01. `rejected` IS RULED
#: NOW** — CR-059 CS-25, PO 2026-09-01 — and the sentence is corrected here
#: rather than left to rot (hard-won law 1). `cancelled` is still absent and
#: still for that reason: nobody has named it.
#:
#:   `requested`  operational, and moves NO money (US-PAY-012 TC-1).
#:   `approved`   the Finance act that does. Terminal — an approved write-off
#:                has already reduced receivables, so its status may never move
#:                again and the correction is a NEW ROW (hard rule 4).
#:   `rejected`   NEW (CS-25). The approver's other answer. A `requested` row
#:                moves here, it moves NO money and it is NOT a deletion, and
#:                nothing moves after it. It is a status move rather than a new
#:                row precisely BECAUSE the row it lands on never posted
#:                anything — there is nothing to correct, only a decision to
#:                record.
#:   `reversed`   NEW (CS-25). Carried by the NEW row that corrects an approved
#:                write-off, exactly as `payments`' own `reversed` is carried by
#:                the reversing payment row and never by the original. *"Has
#:                this write-off been reversed?" is a question about the
#:                existence of another row, never about a flag on this one.*
WRITE_OFF_REQUESTED = "requested"
WRITE_OFF_APPROVED = "approved"
WRITE_OFF_REJECTED = "rejected"
WRITE_OFF_REVERSED = "reversed"
WRITE_OFF_STATUSES = (
    WRITE_OFF_REQUESTED,
    WRITE_OFF_APPROVED,
    WRITE_OFF_REJECTED,
    WRITE_OFF_REVERSED,
)

#: The statuses a bad-debt figure counts as MONEY THE UTILITY GAVE UP ON.
#: `requested` never posted and `rejected` never will; `reversed` is the
#: correction row and is NETTED rather than counted (`apps/payments/bad_debt.py`).
WRITE_OFF_POSTED_STATUSES = (WRITE_OFF_APPROVED, WRITE_OFF_REVERSED)


class WriteOff(models.Model):
    """A debt the utility stops chasing (r12 #11, BR-PAY-020).

    BR-PAY-020, CONFIRMED: *"INITIATED in Payments (S34/S35 outstandings,
    operational), APPROVED + reported in Finance (Owner/Admin, bad-debt GL);
    payments owns the transaction record, ledger posts, finance reports"*.

    **THE APPROVAL IS WHAT GATES THE MONEY, and it is why this table has two
    timestamps rather than a boolean.** US-PAY-012 TC-1 is explicit that an
    initiation has *"NO balance/ledger effect yet"*: the row exists, the S34
    screen shows it pending, and nothing has left the books. TC-2 is the
    approval, and only then does `DR write-off / CR AR` post.

    BR-PAY-037 applies here exactly as it does to refunds — *"the SAME user
    holding the approver role MAY initiate AND approve in v1 — both acts
    recorded distinctly"* — so who/when is stored for BOTH acts, four columns,
    not a flag. The audit trail IS the control in v1 and a boolean would erase
    half of it.

    **APPEND-ONLY IN SUBSTANCE (BR-PAY-002 family, hard rule 4).** US-PAY-012
    TC-4: a payment that arrives after a write-off is recorded as a NEW credit
    event against the account; this row is never edited and never deleted. The
    guarantee is the trigger in migration 0010 — deny-by-default with only the
    approval columns open, the shape `refunds` uses — and it is stated here
    rather than claimed here (hard-won law 1).

    `gl_account_id` is a deferred uuid (B11 F-3): `ledger_accounts` is the
    ledger's table and payments carries no import edge into it. It is resolved
    BY DESIGNATION (`write_off`, one of the twelve the PO ruled) at approval
    time, never by number — field-map P-17 is the defect that follows from
    resolving a GL by its code.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3
    currency = models.CharField(max_length=3, default="USD")  # hard rule 2
    reason = models.TextField()
    #: US-PAY-012 §5 — the prototype marks the note *"Required"*, and it is the
    #: only place a human explains a decision that permanently reduces AR.
    note = models.TextField()
    status = models.TextField(default=WRITE_OFF_REQUESTED)
    requested_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="requested_by",
        related_name="write_offs_requested",
    )
    requested_on = models.DateField()
    approved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="approved_by",
        related_name="write_offs_approved",
    )
    approved_on = models.DateField(null=True, blank=True)
    # ── the REJECTION triple (CR-059 CS-25, migration 0011) ─────────────────
    #: CS-25, verbatim: *"A request may be rejected with a reason by an
    #: approver; rejection moves no money and is not a deletion."* Three
    #: columns and not a flag, for BR-PAY-037's reason — the audit trail IS the
    #: separation-of-duties control in v1, so WHO decided and WHEN are facts on
    #: the row and not only in `audit_log`.
    #:
    #: ⚠ **NOT `approved_by`/`approved_on` REUSED.** A rejected row reading
    #: *"approved by Dana"* is a sentence a finance reviewer would act on, and
    #: B14 rule 31's cousin applies: a field's visible value must mean what its
    #: name says.
    rejected_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="rejected_by",
        related_name="write_offs_rejected",
    )
    #: The business date of the decision, supplied by the caller. There is no
    #: clock in this module (BR-TEN-043, gate G6).
    rejected_on = models.DateField(null=True, blank=True)
    #: FREE TEXT and required by the service, exactly like `note`, because
    #: CS-25 says *"with a reason"* and names no closed set. The four
    #: `WRITE_OFF_REASONS` are the reasons a debt is written OFF; why an
    #: approver refused one is a different question with no ratified
    #: vocabulary, and a column of plain text can be taken over by a lookup
    #: later without a data migration — the posture the reason column above
    #: already takes.
    rejection_reason = models.TextField(null=True, blank=True)
    # ── the REVERSAL pair (CR-059 CS-25, migration 0011) ────────────────────
    #: CS-25, verbatim: *"An approved write-off is corrected by a reversing
    #: write-off row and a mirrored ledger entry, never by editing or deleting
    #: the original."* A SELF-FK, so the pair lives in one table exactly as
    #: `payments.reverses_payment` does for a bounced cheque — the same rule
    #: (hard rule 4) answered the same way in the same module.
    #:
    #: `uq_write_offs_reverses` below makes it UNIQUE per tenant: **a write-off
    #: is reversed ONCE.** That is this flow's idempotency guard (hard rule 6)
    #: and it is the DATABASE's, not a SELECT-then-INSERT's: two approvers on
    #: two screens is exactly the race a check in Python loses, and the loser
    #: would credit receivables twice for one correction.
    reverses_write_off = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="reverses_write_off_id",
        related_name="reversals",
    )
    #: WHY the write-off was reversed. Free text for `rejection_reason`'s
    #: reason, and required by the service. **WHO reversed it is the reversing
    #: row's own `requested_by`/`approved_by`** — one Admin act, recorded in the
    #: two columns BR-PAY-037 already gives every write-off.
    reversal_reason = models.TextField(null=True, blank=True)
    #: Deferred uuid — see the class docstring.
    gl_account_id = models.UUIDField(null=True, blank=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "write_offs"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=WRITE_OFF_STATUSES), name="ck_write_offs_status"
            ),
            models.CheckConstraint(
                condition=Q(reason__in=WRITE_OFF_REASONS), name="ck_write_offs_reason"
            ),
            # A write-off REDUCES receivables; its sign lives in the posting.
            #
            # ⚠ **A REVERSING ROW IS POSITIVE TOO, AND THAT IS DELIBERATE.**
            # `payments` writes a NEGATIVE reversing row because its rows are
            # summed to a cash total. A write-off's direction is its POSTING's
            # (DR write-off / CR AR going out, the ledger's own mirror coming
            # back), so the figure here stays the magnitude a human approved and
            # `status` says which way it went. `bad_debt.py` is the one reader
            # that nets the two, and it nets by STATUS.
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="ck_write_offs_amount_positive"
            ),
            # CS-25 / hard rule 6 — a write-off is reversed ONCE. Partial, so
            # every ordinary write-off (which reverses nothing) passes.
            models.UniqueConstraint(
                fields=["tenant", "reverses_write_off"],
                condition=Q(reverses_write_off__isnull=False),
                name="uq_write_offs_reverses",
            ),
            # A reversing row states WHY, and only a reversing row may.
            models.CheckConstraint(
                condition=(
                    Q(reverses_write_off__isnull=False, reversal_reason__isnull=False)
                    | Q(reverses_write_off__isnull=True, reversal_reason__isnull=True)
                ),
                name="ck_write_offs_reversal_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_write_offs_account"),
            # The Finance approval queue and the "write-offs YTD" figure S32/S36
            # both read this one index (US-PAY-005 TC-4).
            models.Index(
                fields=["tenant", "status", "-requested_on"], name="ix_write_offs_status"
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-017@7b2ce54 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-05-payment-plans.md · 04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md · 04-docs/05-modules/08-payments/02-business-rules.md · 08-qa/01-e2e/journeys/J13-payment-plan-life.md)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — models only; the S24/S34/S35 endpoints are their stories' API halves and none exists) E=deferred(no-frontend-half — S24, S34 and S35 are unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim run
# exceptions: (1) NO `missed_count`, NO `defaulted`, NO `void` — PO 2026-08-11
#         "nodrop we chase for payments until write off" SUPERSEDES r12 #9's
#         column, BR-PAY-016's "2nd miss VOIDS plan" and BR-CUS-044's
#         `defaulted` state. The absence is the rule and a test asserts it.
#         (2) `accounts.bad_address` (r12 #8) IS NOT WRITTEN HERE — it is a
#         customers-owned column and B1 forbids the cross-module write.
#         ⚠ AMENDED 2026-09-23 (DEF-PAY-6342): the flag is no longer DERIVED
#         from these rows; customers writes the column at returned_mail's
#         request, and these rows are its history and the needs-attention list.
#         (3) These classes are in their own module, not `models.py` — the
#         `apps/payments/bankrec_models.py` precedent, for the same reason.
#         (4) [WRITE-OFF lane 2026-08-15] `WriteOff` added (r12 #11). Its
#         reason set carries FOUR values and not six: the prototype's *"send to
#         collections agency"* and *"flag for future deposit"* checkboxes have
#         NO ratified rule (field-map P-4/P-5) and US-PAY-012 §1 excludes them,
#         so the column cannot hold them. Two acts, four columns (BR-PAY-037),
#         never a boolean. `gl_account_id` is resolved BY DESIGNATION at
#         approval and is NULL until then — nothing money-bearing exists before
#         a human approves (US-PAY-012 TC-1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

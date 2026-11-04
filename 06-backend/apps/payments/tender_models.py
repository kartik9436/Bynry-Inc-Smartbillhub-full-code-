# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-12 (one payment covering several accounts — the
#           multi-property tender) · CR-059 CS-27 (a master pays its units'
#           bills — the sub-metering core case)
#           Screens: S21 · S22 · S33 · S35 (CR-059 tasks 50 and 52 — ANOTHER
#           LANE. Nothing here draws anything.)
# Rules:    BR-PAY-1126 (one tender, N payments — never N unrelated payments) ·
#           BR-PAY-1127 (the parts sum to the tender EXACTLY or nothing
#           commits) · BR-PAY-1128 (each account's payment carries its OWN
#           duplicate-guard key) · BR-PAY-1129 (a master may pay a bill on a
#           unit of its own premises, and the authority is recorded) ·
#           BR-PAY-1130 (money no unit bill absorbs returns to the MASTER's
#           credit, never a tenant's) · BR-PAY-1131 (reversing a master tender
#           reverses every unit payment it made) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money 4 dp written into a NUMERIC(18,6)
#           container + CHAR(3), never float) · rule 4 (financial
#           immutability) · rule 6 (idempotency) · BR-PAY-021 (posting date ≠
#           clearing date, always both)
# Tests:    06-backend/tests/test_cr059_cs12_multi_account_tender.py ·
#           06-backend/tests/test_cr059_cs27_master_pays_units.py
# Impacts:  apps/payments/tenders.py (the ONLY writer) ·
#           apps/payments/models.Payment.tender (the nullable link) ·
#           apps/payments/migrations/0021_cr059_cs12_cs27_payment_tenders (this
#           schema) · 0022_rls_cr059_cs12_cs27_tenders (the guarantees this
#           class cannot give) · apps/payments/apps.py (registration)
# ───────────────────────────────────────────────────────
"""`payment_tenders` — ONE cheque, N payments (CR-059 CS-12 and CS-27).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this table is the parent of money rows and
migration ordering is a CLAUDE.md 🔒 path. AI-authored 2026-09-03 under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*); row
in 12-governance/09-human-review-ledger.md. It may never reach lifecycle
RATIFIED without a recorded human sign-off.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS TABLE IS FOR, IN ONE SENTENCE: a customer with three          ║
║  properties hands over ONE CHEQUE, and today that becomes three          ║
║  unrelated payments, three receipts for one cheque, and nothing anywhere ║
║  that checks the split adds up.                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

**IT IS NOT A PAYMENT AND IT NEVER BECOMES ONE.** A payment carries exactly one
mandatory account and meets a bill only through an allocation against that
bill's invoice. The tender carries the thing the clerk is holding — the amount
on the cheque, its number, its tender, and both of BR-PAY-021's dates — and each
account's own payment points BACK at it through `payments.tender_id`. So one
cheque reads as one cheque on S21 and S33, and the three payments it made are
still three ordinary payments with their own allocations, their own audit rows
and their own journal entries.

────────────────────────────────────────────────────────────────────────────
THE TWO SCOPES, AND WHY THEY ARE ONE TABLE WITH A DISCRIMINATOR
────────────────────────────────────────────────────────────────────────────
CS-27 is explicit that it is **not** CS-12 repeated: *"CS-12 groups by
CUSTOMER, and the customer link does not join a landlord to their tenants. This
groups by PREMISES — unit → premises → owner → master — which is a different
key and a different authority question."* And it is explicit about the order:
*"Build CS-12 first; this extends it rather than repeating it."*

So `scope` says which key was used, and the two are kept apart by a check
constraint rather than by convention:

  * `scope='customer'` (CS-12) — `customer_id` is set, `payer_account` is NULL.
    Every account the tender settles is held by that ONE customer. The payer IS
    the account holder, so no authority question arises at all.
  * `scope='premises'` (CS-27) — `payer_account` and `premises_id` are set,
    `customer_id` is NULL. **The payer does not hold the accounts it settles**;
    the landlord and the tenants are different customers, which is precisely why
    nothing joined their accounts before this table existed.

────────────────────────────────────────────────────────────────────────────
THE PAYER IS RECORDED ONCE, HERE, AND NOT ALSO ON THE PAYMENT
────────────────────────────────────────────────────────────────────────────
CS-27 asks for a unit payment *"annotated with the payer"* and for the authority
to be *"recorded on the payment"*. **Both facts are reached from the payment
through its tender, and neither is copied onto `payments`** — hard-won law 5 in
schema form: a copy is a second place for one fact to be wrong, and this one
would have to be maintained on an append-only row that cannot be corrected.

A tenant asking *"has my landlord paid my water?"* is answered by
`payment.tender.payer_account` and `payment.tender.authority`, which is one join
from the row their own account already carries.

────────────────────────────────────────────────────────────────────────────
WHAT IS **NOT** ON THIS TABLE, EACH FOR A STATED REASON
────────────────────────────────────────────────────────────────────────────
  * **No shortfall order.** CS-12 says a ruling is needed for *"whose property
    goes short when the cheque does not cover everything"* — and says in the
    same breath that *"manual entry against three visible bills sidesteps the
    question entirely, which is why it is the right version one."* Version one
    is what is built: the clerk types the parts, the parts must sum, and no
    column here would ever be read to decide who goes short. Choosing one would
    be resolving an open question by picking a value (prime directive).
  * **No `tender_no`.** A tender is identified by the cheque number the customer
    wrote, which is `reference`, and by the `PMT-` numbers of its parts. Minting
    a second human-facing series would be a number nobody asked for on a screen
    B14 rule 31 already forbids showing ids on.
  * **No remainder column.** Where money the master paid that no unit bill
    absorbed ends up is BR-PAY-1130's rule and it is a PAYMENT — one row on the
    master's own account, carried as the master's credit. A column here would be
    a second answer to the same question.

────────────────────────────────────────────────────────────────────────────
IMMUTABILITY IS NOT ENFORCED BY THIS CLASS (hard-won law 1)
────────────────────────────────────────────────────────────────────────────
A Django model cannot refuse a `.save()`. The guarantee is the write-once
trigger in `migrations/0022`, exactly as `bank_rec_match_sets` has one: a tender
whose amount could be rewritten is not evidence of what was in the drawer. Hard
rule 4's narrowing of 2026-09-02 opened three columns on **`payments`** and on
nothing else — `payments/0014` is the only place that allow-list moves — so this
table takes the unnarrowed rule.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

# ── the two scopes (CS-12 · CS-27) ──────────────────────────────────────────
#: CS-12 — several accounts of ONE customer. The payer holds them all.
TENDER_SCOPE_CUSTOMER = "customer"
#: CS-27 — several accounts on ONE premises, held by DIFFERENT customers, paid
#: by a master account that holds none of them.
TENDER_SCOPE_PREMISES = "premises"
TENDER_SCOPES: tuple[str, ...] = (TENDER_SCOPE_CUSTOMER, TENDER_SCOPE_PREMISES)

# ── how the payer came to be allowed to pay (CS-27, ruled 2026-09-01) ───────
#: `scope='customer'`: the payer holds the account. Not a question anybody asks.
AUTHORITY_ACCOUNT_HOLDER = "account_holder"
#: `scope='premises'`: the unit is on the master's premises. **PO ruling
#: 2026-09-01 makes this a RELATIONSHIP check and not a consent check** — a
#: master *"may always"* pay a unit's bill and the tenant's agreement is not
#: required — so the authority recorded is the relationship that was true at the
#: moment the money was taken.
AUTHORITY_PREMISES_OWNER_MASTER = "premises_owner_master"
TENDER_AUTHORITIES: tuple[str, ...] = (
    AUTHORITY_ACCOUNT_HOLDER,
    AUTHORITY_PREMISES_OWNER_MASTER,
)


class PaymentTender(models.Model):
    """One thing handed over — a cheque, a transfer, a card swipe — that settled
    SEVERAL accounts (CR-059 CS-12 · CS-27).

    Written by `apps/payments/tenders.py` and by nothing else, inside the one
    transaction that writes its parts. It is append-only: `migrations/0022`
    refuses every UPDATE and every DELETE.

    **THE WORKED CASE THIS TABLE EXISTS FOR (CS-12's own fixture scenario):**
    cheque **#8842 for $520.00** on 8 August settles `ACC-1042` 12 Oak St Unit 1
    **184.20**, `ACC-1043` Unit 2 **156.90** and `ACC-1044` 40 Cedar Ave
    **178.90**. One tender row, three payments, three receipts that each name
    the same cheque, and 184.20 + 156.90 + 178.90 = **520.00** checked before
    anything commits.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: `customer` | `premises`. See the module docstring — the two keys are
    #: different keys and a check constraint keeps them apart.
    scope = models.TextField(default=TENDER_SCOPE_CUSTOMER)
    #: CS-12 — the ONE customer whose accounts this tender settles. A deferred
    #: uuid rather than an FK for the B11 F-3 reason `payments.deposit_batch_id`
    #: is one: `customers` is another module's table and payments carries no
    #: import edge into its ORM (B1). It is validated through customers' own
    #: published read before anything is written.
    customer_id = models.UUIDField(null=True, blank=True)
    #: CS-27 — **the payer, which need not hold the accounts it settles.** This
    #: IS an FK, unlike `customer_id`, because `payments.account` is already one
    #: of B2 §2's reviewed cross-module edges (*"account 1:N payments"*) and this
    #: column points at the very same table through the very same edge.
    payer_account = models.ForeignKey(  # ⚠ reviewed cross-module payments→customers (B2 §2)
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="payer_account_id",
        related_name="tenders_paid",
    )
    #: CS-27's *"authority reference"* — WHICH premises made the payer allowed to
    #: pay. Deferred uuid: premises are metering's table and payments reaches
    #: them through customers' published read, never through an ORM edge.
    premises_id = models.UUIDField(null=True, blank=True)
    #: One of `TENDER_AUTHORITIES`. **Recorded, never inferred at read time**: the
    #: relationship that authorised this money is a fact about the day it was
    #: taken, and a landlord who sells the building must not retroactively lose
    #: the authority for payments they already made.
    authority = models.TextField(null=True, blank=True)
    #: What was handed over. Hard rule 2: 4 dp written into an 18,6 container.
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")  # CHAR(3), hard rule 2
    #: The tender itself — cheque, cash, ACH. Nullable exactly as
    #: `payments.method` is, and for the same reason.
    method = models.ForeignKey(
        "tenancy.PaymentMethod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="method_id",
    )
    #: The cheque or confirmation number — CS-12's *"reference"*. It is copied
    #: onto each part's `confirmation` as well, because that is the column bank
    #: reconciliation matches on and the column hard rule 4 opened to correction
    #: (`payments/0014`). **This one is not correctable and does not need to be:**
    #: a mistyped number is corrected on the payments, which is where every
    #: reader looks.
    reference = models.TextField(null=True, blank=True)
    #: BR-PAY-021, both of them, on the tender as well as on every part — the
    #: cardinal rule of this module. The parts are stamped from these, so one
    #: cheque cannot have three different posting dates.
    posted_at = models.DateTimeField()
    cleared_at = models.DateTimeField(null=True, blank=True)
    #: Hard rule 6, and **the whole of CS-12's silent trap seen from the other
    #: side.** The submission's own client token, stored ONCE per tender, unique
    #: per tenant. A re-submitted form finds this row and replays every part
    #: rather than writing a second tender that points at the same payments.
    #:
    #: ⚠ It is NOT the parts' key. Each part derives its OWN key from this one
    #: plus its account id — `tenders.tender_part_reference` — because the
    #: payment guard is keyed on **tenant + token and NOT on the account**, so a
    #: token reused across accounts makes payments two and three look like
    #: replays of payment one. See that function; it is the defect this whole
    #: change exists to avoid.
    submission_key = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_tenders"
        constraints = [
            # Hard rule 6. One submission, one tender, however many times the
            # clerk's browser sends it.
            models.UniqueConstraint(
                fields=["tenant", "submission_key"], name="uq_payment_tenders_submission"
            ),
            # A typo'd scope is a tender no reader can classify — the same class
            # of hole `ck_payments_status` closes for a payment.
            models.CheckConstraint(condition=Q(scope__in=TENDER_SCOPES), name="ck_tenders_scope"),
            models.CheckConstraint(
                condition=Q(authority__in=TENDER_AUTHORITIES) | Q(authority__isnull=True),
                name="ck_tenders_authority",
            ),
            # CS-12's shape: a customer tender names a customer and no payer
            # account. Without this a customer-scoped tender could carry a payer
            # who holds none of the accounts, which is CS-27 wearing CS-12's
            # label and would skip the authority check entirely.
            models.CheckConstraint(
                condition=Q(scope=TENDER_SCOPE_CUSTOMER)
                & Q(customer_id__isnull=False)
                & Q(payer_account__isnull=True)
                | Q(scope=TENDER_SCOPE_PREMISES)
                & Q(payer_account__isnull=False)
                & Q(premises_id__isnull=False)
                & Q(customer_id__isnull=True),
                name="ck_tenders_scope_shape",
            ),
            # A tender of 0.00 or less is not a thing anybody handed over, and
            # the sum check would then pass on three empty parts.
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_tenders_amount_positive"),
        ]
        indexes = [
            # S21's master view — "the units it may pay for, and what this
            # cheque settled". Without it, every render is a scan.
            models.Index(fields=["tenant", "payer_account"], name="ix_tenders_payer"),
            # CS-12's customer roll-up, and S33's grouping by customer.
            models.Index(fields=["tenant", "customer_id"], name="ix_tenders_customer"),
            # S33 lists tenders the way it lists payments: newest posting first.
            models.Index(fields=["tenant", "-posted_at"], name="ix_tenders_posted"),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug convenience
        return f"{self.scope} tender {self.reference or self.pk} {self.amount} {self.currency}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 CS-12 + CS-27 (12-governance/11-change-requests.md §8 · §11 tasks 49, 51, 74 · 04-docs/05-modules/08-payments/02-business-rules.md · CLAUDE.md hard rules 1/2/4/6/7)
# generated: 2026-09-03 by the CR-059 W9 multi-account/master-tender lane
# checklist: A✔ B✔ C✔ D=deferred(no API in this file) E=deferred(no UI — tasks 50/52 are another lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean
# exceptions: (1) NO SCREEN IS BUILT ANYWHERE IN THIS LANE. CR-059 tasks 50 and
#         52 own P5, P6, S21's two sides and S33's grouping, and another lane is
#         in `07-frontend/src/features/payments/` while this was written — so the
#         endpoints below are live and no screen reaches them yet. Hard-won law 2
#         with the halves in two lanes BY DESIGN, and REPORTED rather than left
#         to be discovered.
#         (2) `customer_id` and `premises_id` are deferred uuids (B11 F-3) while
#         `payer_account` is a real FK — the asymmetry is deliberate and the
#         column comments give the reason: `payments→customers.accounts` is
#         already one of B2 §2's REVIEWED cross-module edges and the other two
#         are not.
#         (3) THE AUTOMATIC SHORTFALL ORDER IS NOT DECIDED AND NO COLUMN HERE
#         COULD BE READ TO DECIDE IT. CS-12 says a ruling is needed and says
#         manual entry sidesteps it; manual entry is what is built.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

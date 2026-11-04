# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 — `BR-CUS-1047` BUILT. The ruling of 2026-09-12
#           reached the register, the rule table, the decision log and the
#           open-questions register, and never reached the code: a clerk who
#           put an account on the wrong unit still could not correct it.
# Rules:    BR-CUS-1047 (CONFIRMED 2026-09-12 — the correction, under four
#           conditions) · BR-CUS-017 (CONFIRMED 2026-08-08 — one account ↔ one
#           unit; NARROWED by 1047, never replaced) · BR-CUS-020 (unit
#           eligibility) · BR-MET-040 (a plan is required at activation) ·
#           OQ-042's closure (*"supervisor = SysAdmin/Executive"*) · A4's
#           `adjustment_approval` row (SysAdmin Approve · Executive Approve ·
#           Billing Clerk Request) · CLAUDE.md hard rule 4 (issued bills are
#           never restated) · hard rule 7 (audit) · hard rule 8 (no address
#           column — an account walks to its premises).
# Question: OQ-CUS-12355 — may a BILLING CLERK raise a correction for a
#           supervisor to approve as a second act? Not built; see below.
# Tests:    06-backend/tests/test_br_cus_1047_unit_correction.py
# ───────────────────────────────────────────────────────
"""THE RECORD OF A UNIT CORRECTION — who moved this account, why, and who said
it could.

WHY THIS IS A TABLE AND NOT AN `audit_log` ROW
─────────────────────────────────────────────────────────────────────────────
Hard rule 7 already requires an audit row, and one is written. It is not enough
on its own, for a reason `CLAUDE.md` states about a neighbouring path in hard
rule 4's own text: **`audit_log` is pruned on a retention schedule**, and
whether a correction's audit row is exempt from that pruning is `OQ-1340` and is
OPEN. A record that may be pruned cannot be the only answer to *"why is this
account on Suite 2 when five bills say Suite 1?"* — and that question outlives
any retention window, because the five bills do.

So the audit row is the EVENT and this row is the RECORD. It is append-only:
nothing in this product updates or deletes a row here, and a lane adding such a
path must say which rule permits it.

WHAT EACH COLUMN IS FOR, AND EACH ONE IS A CLAUSE OF THE RULING
─────────────────────────────────────────────────────────────────────────────
`BR-CUS-1047` is four conditions and they are the specification, quoted rather
than summarised — PO 2026-09-12: ***"(a) Narrow the rule to allow exactly this
correction: a reason from a fixed list, a supervisor's approval, effective
today, never backdated, issued bills untouched."***

  * **a reason from a fixed list** → `reason_code`, CHECK-constrained to
    `CORRECTION_REASONS`. A closed vocabulary in code, not a tenant lookup: the
    ruling says *fixed*, and a list a tenant may extend is not fixed.
  * **a supervisor's approval** → `approved_by` + `approved_at`, NOT NULL both.
    The approver is the actor, and the door is `@require_role(SYSTEM_ADMIN,
    EXECUTIVE)` — see `unit_correction.py` for why those two roles and not a
    third.
  * **effective today, never backdated** → `effective_on`, written from the
    server's own date. It is a column rather than a derivation because the
    service agreements it closes and opens carry that date too, and two answers
    to *"from when"* is how a bill and a history come to disagree.
  * **issued bills untouched** → there is no column for this and there cannot
    be one. It is an ABSENCE: no code path from this table reaches `invoices`,
    and the test that proves it reads the invoice rows before and after.

`from_unit` and `to_unit` are both kept. The account carries only where it is
NOW, so without `from_unit` the record could not answer the one question it
exists for — the reads, the meters and the five issued bills all stayed with
Suite 1, and something has to say that Suite 1 was ever this account's.

⚠ **NO ADDRESS COLUMN — hard rule 8.** Both units are in the same building in
the ruling's own worked case, and even when they are not, a correction walks
`unit → premises` like everything else. A `from_address` here would be a fourth
home for an address and `G85` would fail it by name.

WHAT IS DELIBERATELY ABSENT
─────────────────────────────────────────────────────────────────────────────
**There is no `requested_by`, and no `pending` state.** A4's signed matrix
(`BR-IDN-014`) gives `adjustment_approval` as *System Admin: Approve · Executive:
Approve · Billing Clerk: **Request***, so the product's signed vocabulary does
have a REQUEST tier — but nothing in this product implements a request that
waits for an approval, on any table, and inventing the queue, the notification
and the screen would be resolving an open decision by picking a value, which the
prime directive forbids. **`OQ-CUS-12355` carries it.** What is built is the
half that is ruled twice over: a supervisor approves, and a clerk may not.
"""

from django.db import models

from core.dbfields import uuid7_pk

#: **THE FIXED LIST.** `BR-CUS-1047` requires *"a reason from a fixed list"* and
#: does not enumerate it, so the list is DERIVED rather than invented: these are
#: the three doors in this product that write `accounts.unit_id`, which are the
#: three ways a record can come to name the wrong one.
#:
#:   · `create_account`     → `opened_on_wrong_unit`
#:   · `create_from_import` → `imported_onto_wrong_unit`
#:   · `move_in`            → `moved_in_to_wrong_unit`
#:
#: ⚠ **NONE OF THEM IS *the customer moved*, and that is the whole point.**
#: `BR-CUS-017`'s reason for existing is that a move takes the OUTGOING
#: account's unit and the bills, meters and reads must not follow a person; the
#: move-out → move-in pair remains the ONLY way to re-home an account that
#: genuinely moved. Every reason here describes a RECORD that was wrong, never
#: a PERSON who went somewhere.
CORRECTION_REASONS: tuple[str, ...] = (
    "opened_on_wrong_unit",
    "imported_onto_wrong_unit",
    "moved_in_to_wrong_unit",
)


class AccountUnitCorrection(models.Model):
    """One correction: this account was on that unit, it is on this one now.

    APPEND-ONLY. Nothing in this product updates or deletes a row here."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="unit_corrections",
    )

    #: ⚠ Cross-module FKs, customers → metering, in B2 §2's reviewed interface
    #: set — the same direction `accounts.unit_id` already takes. `PROTECT`,
    #: because a unit named in a correction is part of an account's history and
    #: deactivating it must not take the record with it (`BR-MET-047` already
    #: blocks deactivation while an account lives on a unit; this covers the
    #: unit the account has LEFT, which that rule does not).
    from_unit = models.ForeignKey(
        "metering.Unit",
        on_delete=models.PROTECT,
        db_column="from_unit_id",
        related_name="+",
    )
    to_unit = models.ForeignKey(
        "metering.Unit",
        on_delete=models.PROTECT,
        db_column="to_unit_id",
        related_name="+",
    )

    #: One of `CORRECTION_REASONS` — a CHECK constraint, so the fixed list is
    #: the DATABASE's and not a validator's. A validator can be bypassed by the
    #: next writer; a constraint cannot.
    reason_code = models.TextField()

    #: `BR-CUS-1047` condition 3. Written from the server's date, never from a
    #: payload — `correct_account_unit` refuses an `effective_on` key BY NAME.
    effective_on = models.DateField()

    #: `BR-CUS-1047` condition 2 — the supervisor. NOT NULL on both columns: a
    #: correction with no approver is the thing the rule exists to prevent, and
    #: "nobody knows" is not an answer this table may give.
    approved_by = models.ForeignKey(  # ⚠ cross-module customers→identity (B2 §2)
        "identity.User",
        on_delete=models.PROTECT,
        db_column="approved_by",
        related_name="+",
    )
    approved_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_unit_corrections"
        indexes = [
            models.Index(
                fields=["tenant", "account", "-effective_on"],
                name="ix_auc_tenant_account_eff",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(reason_code__in=CORRECTION_REASONS),
                name="ck_account_unit_corrections_reason",
            ),
            #: A correction to the unit it is already on is not a correction.
            #: Refused at the door too, by name with its message — this is the
            #: database's half, so a second writer cannot skip it.
            models.CheckConstraint(
                condition=~models.Q(from_unit=models.F("to_unit")),
                name="ck_account_unit_corrections_moved",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug convenience
        return f"{self.account_id}: {self.from_unit_id} → {self.to_unit_id}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-1047 (PO ruling 2026-09-12) · BR-CUS-017 · OQ-CUS-1769 (CLOSED)
# generated: 2026-09-13 — the ruling's first arrival in code
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

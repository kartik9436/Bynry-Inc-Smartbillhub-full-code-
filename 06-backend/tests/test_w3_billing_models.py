# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (bill runs + the exclusions queue) · US-BIL-005 (issue)
#           · US-BIL-007 (bill detail)   Screens: S30 · S31 · S31.2
# Rules:    BR-BIL-004 (issued invoices immutable) · BR-BIL-005 (a run is
#           idempotent) · BR-BIL-015/023 (every exclusion recorded) ·
#           BR-BIL-063 (the invoice number is allocated at DRAFT creation, PO
#           2026-08-11 — this header said "minted at issue only" until the
#           US-BIL-005 lane found it stale; tc1's own docstring below had
#           already recorded the reversal) ·
#           CLAUDE.md rule 2 (money NUMERIC(18,6) + CHAR(3)) · rule 3 (unit
#           carried) · rule 4 (financial immutability)
# ───────────────────────────────────────────────────────
"""The billing invoice core: the shape of the tables, and the laws on them.

WHAT RUNS WHERE, stated because it changes what these tests are worth. The
test database is SQLite, which has neither row-level security nor the
immutability triggers `billing/0002` installs. So:

  * SHAPE and CONSTRAINTS (below) run everywhere — money precision, the
    currency partner, the idempotency key, one exclusion per account per run,
    the partial unique on invoice numbers.
  * TENANT ISOLATION is the G5 suite's job, against Postgres.
  * IMMUTABILITY is a database trigger and was proved on a live cluster (see
    the migration's trailer). The Python half asserted here is the SERVICE
    layer's, which is the door application code actually walks through.

The last point is the one worth not glossing: a `.save()` in a management
command bypasses every service guard, and only the trigger stops it. Anyone
reading this file should know the trigger is the real fence and this is the
gate in it.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.billing import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def an_account(actor, tenant, *, account_no="A-10432"):
    """A minimal account, and an explicitly **Active** one.

    Built through customers' own service would drag in the whole activation
    path; this test is about billing's tables.

    ⚠ **THE STATUS WAS `…filter(tenant=tenant).first()` UNTIL 2026-09-15 AND
    THAT WAS A LATENT FIXTURE DEFECT, NOT A DETAIL.** `AccountStatus` declares
    no `Meta.ordering`, so *first* is whatever row the database hands back — on
    this tenant a `pending_activation`, whose behaviour class is
    `non_billable` (BR-CUS-055). Every account in every billing test was
    therefore in an ARBITRARY billability state, and nothing read that state,
    so nothing noticed.
    **It stopped being harmless the moment a read started asking.** The PO's
    ruling of this date makes a bulk correction select its accounts the way a
    bulk bill run does (`DEF-BIL-5377`), so `bulk_corrections.
    resolve_scope_queryset` now consults `customers.selectors.
    billable_accounts` — and six existing cases across two files resolved to
    ZERO bills, correctly, because their accounts were never billable.
    Pinning the status to `active` is what those tests always meant; falling
    back to `.first()` keeps a tenant that seeds no `active` row working.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line="1901 Bluestem Ln")
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    statuses = customer_models.AccountStatus.objects.filter(tenant=tenant)
    status = statuses.filter(code="active").first() or statuses.first()
    account_type = customer_models.AccountType.objects.first()
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=status,
        account_type=account_type,
        account_no=account_no,
    )


def a_cycle(tenant, code="06-A"):
    """The tenant's billing cycle. The provisioning fixture seeds none, so a
    run test has to make one — a bill run without a cycle is not a thing."""
    from apps.metering import models as metering_models

    cycle, _ = metering_models.Cycle.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            # W5-T2 — the RULED fields. `window_start`/`window_end` were dropped
            # by metering 0021; June 1–30 is start day 1 for 30 days, and the
            # window comes out the same. ⚠ `bill_date` was the last deprecated
            # column and it is GONE too (RC-W6, metering 0023 / OQ-344): the
            # fallback billing's due-terms read is now DERIVED from the bill
            # DAY — *"the bill day, in the month after the period ends"* — which
            # is exactly what these run tests are about.
            "frequency": "Monthly",
            "start_day": 1,
            "days_to_complete": 30,
            "bill_day": 1,
            "due_days": 21,
        },
    )
    return cycle


def a_run(tenant, *, key="2026-06|cycle-1"):
    cycle = a_cycle(tenant)
    return models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        idempotency_key=key,
    )


def a_draft(tenant, account, **overrides):
    values = dict(
        tenant=tenant,
        account=account,
        service_date=date(2026, 6, 30),
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        subtotal=Decimal("100.58"),
        tax_total=Decimal("8.30"),
        total=Decimal("108.88"),
    )
    values.update(overrides)
    return models.Invoice.objects.create(**values)


def test_us_bil_001_tc1__a_bill_run_key_is_unique_per_tenant(brazos, dana):
    """BR-BIL-005 — the guarantee that a re-submitted run cannot bill twice.

    Double-billing a whole cycle is the single most expensive mistake this
    system could make, and the thing that prevents it is one unique index.
    """
    with tenant_ctx(brazos):
        a_run(brazos)
        with pytest.raises(IntegrityError), transaction.atomic():
            a_run(brazos)


def test_us_bil_001_tc2__every_excluded_account_lands_in_the_pending_queue(brazos, dana):
    """BR-BIL-015/023, and the PO's own words: *"anything excluded from a run
    drops into a 'pending billing' queue — Yes."*

    The difference between a run that billed 480 of 500 accounts and a run that
    billed 480 accounts. Without a row per exclusion the twenty are invisible
    until a customer asks why no bill arrived.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)
        exclusion = models.BillRunExclusion.objects.create(
            tenant=brazos, bill_run=run, account=account, reason_code="no_read"
        )

        assert exclusion.resolved_at is None  # pending — that is what makes it a queue
        assert exclusion.reason_code == "no_read"  # never excluded without a reason

        # The same account cannot be excluded twice from one run: two rows would
        # make the queue count wrong, and the queue count is what staff work.
        with pytest.raises(IntegrityError), transaction.atomic():
            models.BillRunExclusion.objects.create(
                tenant=brazos, bill_run=run, account=account, reason_code="held"
            )


def test_us_bil_001_tc3__a_catch_up_run_names_its_parent(brazos, dana):
    """BR-BIL-015 — a sub-run's lineage is queryable, not reconstructed."""
    with tenant_ctx(brazos):
        parent = a_run(brazos, key="2026-06|cycle-1")
        child = a_run(brazos, key="2026-06|cycle-1|catchup-1")
        child.parent_run = parent
        child.save(update_fields=["parent_run"])

        assert models.BillRun.objects.get(pk=child.pk).parent_run_id == parent.pk


def test_us_bil_005_tc1__the_number_is_unique_and_a_numberless_row_never_collides(brazos, dana):
    """The two halves of the unique index, one of which changed hands.

    THIS TEST USED TO ASSERT THE OPPOSITE. It pinned "a draft carries no
    number", citing BR-BIL-022 — a rule whose text names only the SOURCE and
    FORMAT of a number and is silent on timing. The PO ruled the timing on
    2026-08-11 (BR-BIL-063): a number is allocated when the DRAFT is created,
    and an unused one is lost. So the assertion it was written to defend is
    gone, and what remains is what the index actually guarantees.

    The PARTIAL index (`WHERE invoice_no IS NOT NULL`) is deliberately KEPT and
    is tested here for its second half: two numberless rows must still be able
    to coexist. Nothing in the module writes one today, but the column stays
    nullable — a NOT NULL would make the schema the enforcer of a timing rule
    the PO could revisit tomorrow, and it would refuse every row written under
    the previous reading.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = a_draft(brazos, account)
        second = a_draft(brazos, account)

        # The fixture writes rows directly, so these are numberless — the case
        # the partial index exists for. Two of them, no collision.
        assert first.invoice_no is None and second.invoice_no is None
        assert first.status == models.INVOICE_DRAFT

        first.invoice_no = "BL-2606-000001"
        first.status = models.INVOICE_ISSUED
        first.save(update_fields=["invoice_no", "status"])

        second.invoice_no = "BL-2606-000001"
        with pytest.raises(IntegrityError), transaction.atomic():
            second.save(update_fields=["invoice_no"])


def test_us_bil_007_tc1__money_keeps_six_decimals_and_its_currency(brazos, dana):
    """CLAUDE.md rule 2 — NUMERIC(18,6) with a CHAR(3) partner, never floats.

    Six decimals is not decoration: a per-unit price of $0.09734 rounded to two
    would misprice every bill in the system.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = a_draft(brazos, account)
        line = models.InvoiceLine.objects.create(
            tenant=brazos,
            invoice=invoice,
            account=account,
            kind="usage",
            description="Electric usage",
            quantity=Decimal("1283.500000"),
            unit="kWh",
            unit_price=Decimal("0.097340"),
            amount=Decimal("124.917290"),
            taxable=True,
        )
        stored = models.InvoiceLine.objects.get(pk=line.pk)

        assert stored.unit_price == Decimal("0.097340")  # six decimals survive
        assert stored.amount == Decimal("124.917290")
        assert stored.unit == "kWh"  # rule 3 — never inferred from the service
        assert models.Invoice.objects.get(pk=invoice.pk).currency == "USD"


def test_us_bil_005_tc2__the_bill_payload_holds_what_the_document_printed(brazos, dana):
    """PO ruling 2026-08-11 — *"keep lock data for that bill and save the
    instance"*.

    Sarah marries and changes her name; the apartment is renumbered; the plan
    is edited. Every one of those is a legitimate change to live data, and
    every one silently rewrites history if a December reprint re-joins today's
    rows. The document a customer disputes must be the document they received.

    This asserts the payload round-trips. What it does NOT assert is that the
    bill run populates it — no bill run exists yet — and that is the next
    story's test, not a gap papered over here.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        snapshot = {
            "customer_name": "Sarah Chen",
            "service_address": "1901 Bluestem Ln, Unit A, Katy TX 77494",
            "plan": {"name": "Residential Standard", "version": 3},
            "tenant": {"name": "Brazos Bend Utilities"},
        }
        invoice = a_draft(brazos, account, bill_payload=snapshot)

        stored = models.Invoice.objects.get(pk=invoice.pk)
        assert stored.bill_payload["customer_name"] == "Sarah Chen"
        assert stored.bill_payload["plan"]["version"] == 3


def test_us_bil_007_tc2__a_credit_note_references_its_source_and_never_edits_it(brazos, dana):
    """B2's own reason for the column: "references the source, per immutability".

    GT-6's subject. A credit against a $108.88 bill leaves that bill reading
    $108.88 forever; the customer's balance moves, the history does not.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = a_draft(brazos, account, status=models.INVOICE_ISSUED)
        note = models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=invoice,
            # NEGATIVE since DEF-085 / BR-BIL-074 (billing/0020): a credit note's
            # amount is never positive, because a credit REDUCES what the
            # customer owes. This fixture wrote +25.00 and was one of the two
            # opposite conventions the defect found; the database now refuses it.
            amount=Decimal("-25.00"),
            reason="billed on an estimate; actual read lower",
        )

        assert note.original_invoice_id == invoice.pk
        assert models.Invoice.objects.get(pk=invoice.pk).total == Decimal("108.88")


def test_w3__every_new_billing_table_is_tenant_scoped(brazos):
    """CLAUDE.md rule 1, as a SHAPE check that runs on SQLite too.

    The live policies are the G5 suite's job and cannot run here. What CAN run
    here is the precondition every policy depends on: a table with no
    `tenant_id` cannot be tenant-scoped by any policy, so a new billing table
    that forgets the column is caught on the commit that adds it rather than in
    a Postgres-only suite someone may not run locally.
    """
    for model in (
        models.BillRun,
        models.BillRunExclusion,
        models.Invoice,
        models.InvoiceLine,
        models.Adjustment,
        models.CreditNote,
    ):
        fields = {f.name for f in model._meta.get_fields()}
        assert "tenant" in fields, f"{model._meta.db_table} has no tenant column"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 billing DDL + Addendum r10, the PO-approved billing schema batch — · 07-billing/06-epics/EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md · 07-billing/03-field-map.md, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-11 by Eng-Lead (W3 billing schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — schema slice) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the IMMUTABILITY half was proved on a LIVE POSTGRES cluster, not here:
#         an issued invoice refused a total change, refused a snapshot rewrite
#         and refused deletion; its lines refused update and delete; and
#         issued -> paid still succeeded, which is the narrow door working.
#         Those five refusals and one permission are recorded in the migration
#         trailer. SQLite has no triggers, so this file asserts SHAPE and
#         CONSTRAINTS only and says so rather than implying coverage.
# exceptions: does NOT assert that a bill run populates `bill_payload` — no
#         bill run exists yet; that belongs to the run story and is named here
#         rather than left looking covered
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

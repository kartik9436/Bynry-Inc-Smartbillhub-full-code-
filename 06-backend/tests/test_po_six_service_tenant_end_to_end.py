# ── Trace ──────────────────────────────────────────────
# Acceptance: PO, 2026-09-02, in the working chat session, defining the test
#             this product did not have, verbatim:
#               "here scenario is when we are creating a tenant - all 17 steps
#                should run and create bills an dfinance entries - all 17 tasks
#                should be successfully complete - thats a test - take a
#                utility with 6 utility services"
#             Screens: S110–S114 (signup) · S8 (sample data) · S31 (bill run)
# Rules:      BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
#             BR-TEN-063 (each block its own transaction; idempotent; audited) ·
#             BR-TEN-064 (a human asks; the job runs in production) ·
#             BR-RAT-024 (the eleven-service catalogue) · CLAUDE.md hard rule 1
#             (tenant scoping) · rule 3 (a quantity carries its unit) ·
#             rule 5 (only the ledger posting service writes journal lines) ·
#             law 14 (this file is POSTGRES-ONLY on purpose — see below)
# ───────────────────────────────────────────────────────
"""**THE TEST THE PRODUCT DID NOT HAVE, AND THE REASON IT DID NOT HAVE IT.**

Everything about provisioning was covered in pieces. Seventeen seeding blocks
each had a test. The rating engine had sixty-one golden figures. The bill run
had four route tests. **Nothing asserted that the pieces, run in the order a
real signup runs them, end with a customer holding a bill and a book that
balances** — so on 2026-09-02 a utility was created by hand, produced no bills,
and every check in this repo was green while that was true.

The Product Owner then wrote the missing acceptance criterion themselves, and
it is quoted verbatim in the trailer above. This file is that sentence, made
executable. It asserts FOUR things, in the order the sentence names them:

  1. **All seventeen steps run.** Not sixteen with one honestly skipped —
     seventeen, every one reporting ``seeded``. ``BR-TEN-060`` makes a skip a
     NAMED line rather than a silence, which is why a skip can be asserted
     against at all; this test refuses one anyway, because a demo tenant that
     is missing a block is a demo tenant that cannot show the product.
  2. **Bills exist and are ISSUED.** A draft is not a bill. Hard rule 4 makes
     an issued invoice immutable, which is what makes ``status='issued'`` the
     honest thing to count.
  3. **Finance entries exist and BALANCE.** Debits equal credits to the
     4-decimal place money is stored at (hard rule 2). An unbalanced book is
     not a smaller success than a balanced one; it is a different outcome.
  4. **Every service the utility sells reaches a bill line.** This is the
     assertion that would have caught ``DEF-3279`` — a tenant selling three
     metered services received meters for ONE, and its 95 bills silently
     carried no electric line at all, not even the signed $12.00 base, which
     is $576.00 a month across 48 homes. The seeding reported success
     throughout.

**SIX SERVICES, CHOSEN TO SPAN ALL THREE BILLING BASES** (``BR-TEN-1180``,
PO 2026-09-02) rather than to be a tidy list:

  * ``electric`` and ``water`` — **metered**: a register is read, and the
    quantity is the read times the multiplier.
  * ``sewer`` — **share**: a percentage of another service's value, so it
    cannot be billed unless water billed first. It is in this list precisely
    because it fails if the ordering is wrong.
  * ``trash`` and ``fire`` — **capacity, COUNTING**: the size class picks the
    price and the COUNT multiplies it. ``fire`` is the eleventh service
    (``CR-063``, PO 2026-09-02) and a real utility is being onboarded on it.
  * ``solar`` — **capacity, SUMMING**: the installed capacities ADD UP
    (PO 2026-09-02: *"3 panels with 2Kw, 4Kw and 8 Kw … totla capacity will be
    14 Kw"*). It is here so that the two capacity shapes are both exercised,
    because they are different arithmetic wearing one word.

⚠ **POSTGRES ONLY, AND THAT IS LAW 14 RATHER THAN CONVENIENCE.**
``config/settings/test.py`` hardcodes in-memory SQLite and ignores
``DATABASE_URL``. SQLite has no aborted-transaction state, so the seeding
blocks' catch-and-continue paths — every one of which opens a SAVEPOINT
precisely because PostgreSQL poisons a transaction after a failed statement —
**cannot fail there**. A green run of this file on SQLite would prove nothing
about the thing it exists to prove. It skips rather than lying.

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://... pytest tests/test_po_six_service_tenant_end_to_end.py
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.ledger import models as ledger_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models

from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's *"utility with 6 utility services"*, chosen to span all three
#: billing bases and BOTH capacity shapes. See the module docstring.
SIX_SERVICES: tuple[str, ...] = ("electric", "water", "sewer", "trash", "fire", "solar")

#: The number is asserted rather than read from `SAMPLE_MODULES`, because a
#: seeder quietly LOSING a block would otherwise pass this file — reading the
#: count from the thing under test is a check that cannot fail.
#:
#: ⚠ **SEVENTEEN WHEN THE PO WROTE THE CRITERION, EIGHTEEN SINCE 2026-09-02.**
#: `CR-062`'s J addendum added *"The Municipal discount, granted to the
#: municipal account"* as its own block, so the seeding is one step longer and
#: the signup screen says **"All 18 steps"**. That is a deliberate addition and
#: this constant follows it; the PO's *"all 17"* named every step there was on
#: the day they wrote it, and the rule they were stating is **all of them**.
#: Moving this number is a decision that belongs in a commit message, which is
#: exactly why it is typed here rather than derived.
EXPECTED_BLOCKS = 18


def _blocks(tenant) -> list[dict]:
    """Every block this tenant's seeding recorded, flattened across modules."""
    rows: list[dict] = []
    for run in tenancy_models.SampleDataRun.objects.filter(tenant_id=tenant.id):
        for block in run.blocks or []:
            rows.append(dict(block, module=block.get("module") or run.module))
    return rows


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="law 14 — the seeders' catch-and-continue paths cannot fail on SQLite, "
    "so a green run here would not be evidence. Run under config.settings.local "
    "with DATABASE_URL set.",
)
def test_a_six_service_utility_is_provisioned_billed_and_booked(settings) -> None:
    """The PO's acceptance criterion, end to end, on one tenant."""
    settings.JOBS_EAGER = True
    slug = "sixsvc"
    tenant, result = provisioned_tenant(
        brazosbend_payload(
            subdomain=slug,
            name="Six Service Utility",
            services=list(SIX_SERVICES),
            owner={
                "full_name": "Dana Whitfield",
                "email": f"owner@{slug}.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    assert result.get("created") is True, result

    with tenant_ctx(tenant):
        # ── 1 · ALL SEVENTEEN STEPS ─────────────────────────────────────────
        blocks = _blocks(tenant)
        assert len(blocks) == EXPECTED_BLOCKS, (
            f"the seeding recorded {len(blocks)} block(s), not {EXPECTED_BLOCKS}. "
            f"Recorded: {[str(b.get('module')) + '/' + str(b.get('block')) for b in blocks]}"
        )
        short = [b for b in blocks if b.get("outcome") != "seeded"]
        assert not short, "\n".join(
            f"  {b.get('module')}/{b.get('block')} → {b.get('outcome')} "
            f"({b.get('reason') or b.get('reason_code') or 'no reason recorded'}): "
            f"{str(b.get('detail'))[:400]}"
            for b in short
        )

        # ── the estate those steps were supposed to build ───────────────────
        premises = metering_models.Premises.objects.filter(tenant_id=tenant.id).count()
        units = metering_models.Unit.objects.filter(tenant_id=tenant.id).count()
        accounts = customers_models.Account.objects.filter(tenant_id=tenant.id).count()
        assert premises and units and accounts, (
            f"seventeen blocks reported seeded and the estate is empty: "
            f"{premises} premises, {units} units, {accounts} accounts"
        )

        # ── 2 · BILLS, AND ISSUED ONES ──────────────────────────────────────
        issued = billing_models.Invoice.objects.filter(tenant_id=tenant.id, status="issued")
        assert issued.exists(), (
            "no ISSUED bill on a tenant whose seventeen seeding blocks all "
            f"reported success ({billing_models.Invoice.objects.filter(tenant_id=tenant.id).count()} "
            "invoice(s) in any status)"
        )

        # ── 3 · FINANCE ENTRIES, AND A BOOK THAT BALANCES ───────────────────
        entries = ledger_models.JournalEntry.objects.filter(tenant_id=tenant.id)
        assert entries.exists(), (
            f"{issued.count()} bill(s) issued and the ledger holds no journal entry. "
            "Only the ledger posting service writes journal lines (hard rule 5), so "
            "this is that service never being reached, not a rounding difference."
        )
        lines = ledger_models.JournalLine.objects.filter(tenant_id=tenant.id)
        debits = sum(
            (line.amount for line in lines if line.side == "debit"), Decimal("0")
        )
        credits = sum(
            (line.amount for line in lines if line.side == "credit"), Decimal("0")
        )
        # Money is stored to 4 decimals (hard rule 2, PO re-sign 2026-08-22), so
        # that is the place the two sides are compared at.
        assert debits.quantize(Decimal("0.0001")) == credits.quantize(Decimal("0.0001")), (
            f"the book does not balance: debits {debits} vs credits {credits} "
            f"across {lines.count()} line(s) in {entries.count()} entry(ies)"
        )

        # ── 4 · EVERY SERVICE SOLD REACHES A BILL LINE ──────────────────────
        # DEF-3279's shape: a tenant sold three metered services, received
        # meters for one, and its bills silently carried no line for the other
        # two while every seeding block reported success.
        booked = {
            str(code)
            for code in ledger_models.JournalLine.objects.filter(tenant_id=tenant.id)
            .exclude(service__isnull=True)
            .values_list("service__code", flat=True)
            .distinct()
        }
        missing = [code for code in SIX_SERVICES if code not in booked]
        assert not missing, (
            f"the utility sells {len(SIX_SERVICES)} services and only {sorted(booked)} "
            f"reached a posted line. Missing: {missing}. Every seeding block reported "
            "success, which is exactly how DEF-3279 stayed invisible."
        )

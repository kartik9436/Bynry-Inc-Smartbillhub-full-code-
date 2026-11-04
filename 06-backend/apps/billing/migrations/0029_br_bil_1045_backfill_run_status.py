# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5352 — a bill run's status never advances. Measured on the
#          demo tenant: a run that had ISSUED 39 BILLS read `draft`.
# Rule:    BR-BIL-1045 (the five-word vocabulary and its transitions, decided
#          2026-09-15 from blueprint p146 §07 Past billing runs)
# Also:    BR-MET-132 (`RUN_STATUSES_THAT_CONSUME_A_PERIOD`) · BR-LED-006 (the
#          month-end close's *"every run finished"* item) · CLAUDE.md hard
#          rule 4 (no invoice moves here) · rule 1 (RLS: this runs as the
#          migration role and walks every tenant on purpose)
# Tests:   06-backend/tests/test_def_bil_5352_run_status_machine.py
# ───────────────────────────────────────────────────────
"""billing 0029 — give every EXISTING run the word its own rows already support.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-15 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*).

════════════════════════════════════════════════════════════════════════════
WHY A BACK-FILL AND NOT JUST THE NEW WRITER
════════════════════════════════════════════════════════════════════════════
`release.release_run` now advances a run's status the instant its issue pass
returns (`BR-BIL-1045`). That fixes every run made from today. **It fixes no run
already in the database**, and those are the rows a clerk opens screen 27 to
look at — the whole point of the screen is *"what did we bill last month"*.

Measured on the demo tenant with the writer in place and before this migration:
**`RUN-0002` had issued 39 bills worth $15,453.63 and still read `draft`.** A
lane could ship the writer, close the defect, and the Product Owner would open
the screen and see exactly the symptom the defect describes.

════════════════════════════════════════════════════════════════════════════
WHAT IT WRITES, AND THE TWO THINGS IT REFUSES TO TOUCH
════════════════════════════════════════════════════════════════════════════
**IT WRITES EXACTLY ONE WORD: `issued`, AND ONLY WHERE A LOCKED BILL PROVES
IT.** A run holding at least one bill in `issued`/`paid`/`void`/`corrected` put
money in a customer's hand, and that is a fact about the past that cannot be
mistaken.

⚠ **IT DOES NOT WRITE `abandoned`, AND THE FIRST DRAFT OF THIS MIGRATION DID.**
`BR-BIL-1045` defines `abandoned` as *the run ENDED having issued nothing*, and
"ended" is an EVENT — `release.release_run` returning. A stored row cannot tell
a run that ended with nothing from **a run a clerk created this morning and has
not finished yet**: both are `draft` with no bills. The first draft would have
stamped **Abandoned on every run in flight**, which is worse than the defect it
is fixing, because Draft is at least true of a new run. So `abandoned` is only
ever written by the live writer, at the one moment the word can be verified, and
this pass leaves a run it cannot prove anything about exactly as it found it.

**It only rewrites a row currently reading `draft` or `issuing`** — the two
words a creator wrote. A row already carrying a terminal word was written by a
deliberate act and this migration is not one; in particular **a `corrected` run
is never touched**, because `corrected` outranks `issued` and reverting it would
tell a clerk a restatement had been undone.

**IT WRITES ONE COLUMN AND TOUCHES NO BILL.** Hard rule 4: no invoice, invoice
line, payment or journal entry is read for anything but a COUNT, and none is
written. `updated_at` moves with `status` because the row changed.

════════════════════════════════════════════════════════════════════════════
IT WALKS EVERY TENANT, ON PURPOSE
════════════════════════════════════════════════════════════════════════════
Migrations run as the migration role, outside any `app.tenant_id`, which is the
one context in this product where a cross-tenant pass is lawful and intended
(CLAUDE.md rule 1 governs application code). The alternative — a per-tenant
management command — would leave a utility's history reading Draft until
somebody remembered to run it for them.

**NO CHECK CONSTRAINT IS ADDED.** `bill_runs.status` is a plain `TextField` and
a `CHECK` over `BR-BIL-1045`'s five words would refuse any historical row this
pass could not classify, on a column whose vocabulary is three weeks old. The
tuple in `runs.py` is the vocabulary and `test_def_bil_5352_run_status_machine`
is what holds the consumers to it.
"""

from django.db import migrations, transaction
from django.db.models import Count

#: `BR-BIL-1045`'s words, written out rather than imported. A migration that
#: imported `runs.RUN_STATUS_ISSUED` would change meaning the day that constant
#: moved, and a migration must mean the same thing for ever.
DRAFT = "draft"
ISSUING = "issuing"
ISSUED = "issued"
#: Named here because the docstring above reasons about why this pass must NEVER
#: write it. Nothing below assigns it, deliberately.
ABANDONED = "abandoned"  # noqa: F841 — see the docstring

#: The only two a creator writes, and therefore the only two this pass may
#: overwrite. Everything else was set deliberately.
REWRITABLE = (DRAFT, ISSUING)

#: `models.INVOICE_LOCKED_STATUSES` — the states past which a bill is money that
#: left the building. Spelled out here for the same reason as above.
LOCKED = ("issued", "paid", "void", "corrected")


def backfill(apps, schema_editor):
    BillRun = apps.get_model("billing", "BillRun")
    Invoice = apps.get_model("billing", "Invoice")

    # One grouped pass over every tenant's invoices — the run ids that hold a
    # bill money has already left the building with.
    issued_run_ids = {
        row["bill_run_id"]
        for row in (
            Invoice.objects.filter(status__in=LOCKED)
            .values("bill_run_id")
            .annotate(n=Count("id"))
            .order_by()
        )
        if row["n"]
    }
    if not issued_run_ids:
        return
    # ⚠ One UPDATE, narrowed three ways: these runs, a rewritable word, and not
    # already `issued`. No row outside that set is read for anything but its id.
    BillRun.objects.filter(id__in=issued_run_ids, status__in=REWRITABLE).update(status=ISSUED)


def _backfill_every_tenant(apps, schema_editor):
    """`DEF-BIL-5382` — run the pass ONCE PER TENANT, inside that tenant.

    ⚠ **THE MODULE DOCSTRING CLAIMS A CROSS-TENANT PASS THIS DATABASE DOES NOT
    GRANT, AND THE CLAIM COST THE WHOLE MIGRATION.** `13-provision-database.sh
    --migrate` runs `manage.py migrate` under the ambient `DATABASE_URL`, which
    is the **app** role — provisioning's own verify records it `rolsuper=f
    rolbypassrls=f` — and `bill_runs` carries RLS `FORCE`. With no
    `app.tenant_id` set the role sees **zero rows**, so `backfill` selected
    nothing, updated nothing, and `migrate` printed OK.

    Measured on the demo database before this fix: applied OK and `bill_runs`
    stayed at 3 `draft` + 1 `issuing`, while `RUN-0001` held 40 issued bills and
    `RUN-0002` held 39. As the app role with no tenant, `select count(*) from
    bill_runs` answers **0**; with the tenant set, **4**.

    So the per-tenant pass the docstring named as its rejected alternative is
    the only one that works here. `set_config(..., true)` is transaction-local
    and the id is bound as a parameter, never interpolated.
    """
    Tenant = apps.get_model("tenancy", "Tenant")
    tenant_ids = list(Tenant.objects.values_list("id", flat=True))
    if not tenant_ids:
        # A new database migrating before its first tenant exists: nothing to
        # back-fill, and the writer in `runs.py` owns every run from here on.
        return
    for tenant_id in tenant_ids:
        with transaction.atomic():
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])
            backfill(apps, schema_editor)


def unbackfill(apps, schema_editor):
    """Back to `draft` for the one word only this pass can have written.

    ⚠ **`issuing` IS DELIBERATELY LEFT ALONE, AND THE FIRST DRAFT OF THIS
    FUNCTION GOT IT WRONG.** A rebill run is CREATED `issuing` by
    `corrections.execute_correction`, so reverting every `issuing` row to
    `draft` would destroy a word a writer had put there before this migration
    ever ran — the reverse doing damage the forward pass could not.

    `issued` is a word no creator writes, so a row carrying it came either from
    this pass or from the new writer, and `draft` is what it said before either
    existed. `corrected` and `abandoned` are left alone for the same reason as
    `issuing`: this pass never wrote them.
    """
    BillRun = apps.get_model("billing", "BillRun")
    BillRun.objects.filter(status=ISSUED).update(status=DRAFT)


class Migration(migrations.Migration):
    dependencies = [("billing", "0028_def_bil_5255_cr105_run_defaults_label_template")]
    operations = [migrations.RunPython(_backfill_every_tenant, unbackfill)]

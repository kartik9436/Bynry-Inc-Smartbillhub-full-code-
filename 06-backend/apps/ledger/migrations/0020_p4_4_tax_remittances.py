"""ledger 0020 — **`tax_remittances`, the filing register, built at last.**

Finance blueprint `P4.4` (p017, and p058's finding: *"you can record a tax
payment and never see it again"*). B2 Addendum r13 #3 named this table when the
journal core landed and **it was never built**, which is why
`journal.record_tax_remittance` has returned two `unavailable` codes on every
single response it has ever given:

    tax_remittances_register_not_built
    remittance_receipt_attachment_has_no_column

Both go with this migration. `POST /finance/taxes/remittances` posted one
balanced entry and **stored nothing else** — so a finance officer asked *"did we
pay Bexar County in August?"* had to leave Finance, open the journal and filter
by source, and even then could not see the filing reference or the receipt.

═══════════════════════════════════════════════════════════════════════════
1 · THIS DOES NOT BECOME THE SOURCE OF `REMITTED`
═══════════════════════════════════════════════════════════════════════════
⚠ **`reporting.remittance_by_authority` GOES ON READING THAT COLUMN OUT OF THE
BOOKS** — it sums remittance-sourced debits per 2200-nn account — and nothing
here changes it. `BR-REP-002` makes the books the number that has to be right,
and a register is a convenience over them. Two independent totals of one fact is
exactly how a screen and a trial balance come to disagree, and the one that
would be wrong is the one nobody posts to.

What this table records is what a journal entry cannot carry: the filing
reference the authority issued, the day the money actually left, and — through
`stored_documents` — the receipt.

═══════════════════════════════════════════════════════════════════════════
2 · APPEND-ONLY, BY TRIGGER, ALTHOUGH HARD RULE 4 DOES NOT NAME IT
═══════════════════════════════════════════════════════════════════════════
Hard rule 4 lists issued invoices, invoice lines, payments and journal entries.
`tax_remittances` is none of them. **It is still append-only**, and the reason is
what a row IS: the auditor artefact for money that has already moved through a
journal entry that can never be edited. A register that could be rewritten
afterwards would be a record free to disagree with the books it points at, which
is worse than no register.

A Django model cannot refuse a `.save()`, so the refusals are triggers — the
same shape `ledger/0002` uses for the journal and `ledger/0008` for a supplier
invoice's DELETE.

⚠ **THIS IS NOT A WIDENING OF HARD RULE 4 AND IT IS NOT A NARROWING EITHER.**
Nothing about invoices, payments or journal entries moves. CLAUDE.md is explicit
that `payments/0014` is the ONLY place the immutability allow list moves; this
migration adds a NEW table that starts immutable, which is the opposite
direction and needs no ruling.

⚠ **SO A MISTYPED CONFIRMATION REFERENCE IS A NEW ROW, AND THERE IS NO
`correct-reference` HERE.** The PO's 2026-09-02 narrowing is for three columns
of `payments` and for nothing else. `OQ-LED-12653` is OPEN with the worked case
and **nothing is blocked**: the reference is required, so nothing is lost, and a
correcting row can be filed today.

═══════════════════════════════════════════════════════════════════════════
3 · THE UNIQUE KEY IS THE JOURNAL ENTRY
═══════════════════════════════════════════════════════════════════════════
`posting.post()` is idempotent on (authority, period, amount), so a retried
request returns the **same** entry. Without `uq_tax_remittances_entry` a second
register row would appear beside it and the filing history would list one
payment twice — the same failure `export_batches` closes with its
period+target key.

═══════════════════════════════════════════════════════════════════════════
4 · 🔒 ORDERING, AND THE ORPHAN QUESTION
═══════════════════════════════════════════════════════════════════════════
Migration ordering is a CLAUDE.md 🔒 sensitive path, so both dependencies are
named explicitly rather than inferred: `ledger/0019` is the latest ledger
migration at the time of writing, and `tenancy/0001` is what `tenant` points at.

⚠ **THE TWO FOREIGN KEYS NEED NO ORPHAN SWEEP, AND THE REASON IS THAT THE TABLE
IS NEW.** CLAUDE.md requires *"no orphans on real data before any foreign
key"*, measured on more than one database — a migration whose *"0 orphans"* was
measured on one killed a deploy on 2026-09-24. **`tax_remittances` has no rows
anywhere**, on any database, because it did not exist until this file ran: there
is nothing to sweep and no measurement that could be wrong. The check the rule
asks for is the empty set by construction, and saying so is not a way around it
— `P0.4`'s GL pointers are the case where that sweep is real, because those
columns already held values.

⚠ **THE ROLLBACK DROPS THE TABLE AND EVERY FILING IN IT.** Django's own
`DeleteModel` is what unwinds a `CreateModel`, and a `RunPython` refusal in
front of it would be this file deciding that a register row is more precious
than a clean revert — which is a judgment for whoever is reverting. The receipts
are NOT dropped with it: a `stored_documents` row is write-once and survives,
pointing at an id nothing resolves any more, which is the honest outcome
(`document_store.for_source` answers empty rather than wrong).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored under the PO ruling of 2026-08-09; the deferred
human review is its row in `12-governance/09-human-review-ledger.md`
(`DEF-GOV-8547`).
"""

from pathlib import Path

from django.db import migrations, models

from core.dbfields import uuid7

#: The signed B2 §3 policy text, read from the .sql file rather than composed
#: here — same discipline as ledger/0002, 0007 and 0008.
RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_ledger_tax_remittances.sql"

NEW_TABLES = ("tax_remittances",)

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE
#: would abort the migration, so every placeholder is doubled here and arrives
#: at the server as a single `%`. Same reason as ledger/0002, 0004, 0007 and
#: 0008 — and **the SQLite test tier cannot see this defect**, so it is stated
#: rather than relied on being remembered.
IMMUTABLE_SQL = """
CREATE OR REPLACE FUNCTION ledger_tax_remittance_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-LED-019: tax remittance %% is a filing record and cannot be %%. It is the auditor artefact for money that already moved through a journal entry that can never be edited, so a register free to disagree with the books it points at would be worse than no register. File a correcting row instead (OQ-LED-12653).',
    COALESCE(OLD.confirmation_ref, OLD.id::text), TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tax_remittance_no_update ON tax_remittances;
CREATE TRIGGER trg_tax_remittance_no_update
  BEFORE UPDATE ON tax_remittances
  FOR EACH ROW EXECUTE FUNCTION ledger_tax_remittance_immutable();

DROP TRIGGER IF EXISTS trg_tax_remittance_no_delete ON tax_remittances;
CREATE TRIGGER trg_tax_remittance_no_delete
  BEFORE DELETE ON tax_remittances
  FOR EACH ROW EXECUTE FUNCTION ledger_tax_remittance_immutable();
"""

DROP_IMMUTABLE_SQL = """
DROP TRIGGER IF EXISTS trg_tax_remittance_no_update ON tax_remittances;
DROP TRIGGER IF EXISTS trg_tax_remittance_no_delete ON tax_remittances;
DROP FUNCTION IF EXISTS ledger_tax_remittance_immutable();
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in NEW_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _pg_only(sql):
    def run(apps_registry, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        schema_editor.execute(sql)

    return run


class Migration(migrations.Migration):

    dependencies = [
        # 🔒 ORDERING — named, never inferred.
        ("ledger", "0019_p5_4_handover_acknowledgement"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaxRemittance",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid7, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(max_length=3)),
                ("basis", models.TextField()),
                ("confirmation_ref", models.TextField()),
                ("paid_on", models.DateField()),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "journal_entry",
                    models.ForeignKey(
                        db_column="journal_entry_id",
                        on_delete=models.deletion.PROTECT,
                        to="ledger.journalentry",
                    ),
                ),
                (
                    "tax_account",
                    models.ForeignKey(
                        db_column="tax_account_id",
                        on_delete=models.deletion.PROTECT,
                        to="ledger.ledgeraccount",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "tax_remittances"},
        ),
        migrations.AddConstraint(
            model_name="taxremittance",
            constraint=models.CheckConstraint(
                condition=models.Q(basis__in=("billed", "collected")),
                name="ck_tax_remittances_basis",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxremittance",
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="ck_tax_remittances_amount"
            ),
        ),
        migrations.AddConstraint(
            model_name="taxremittance",
            constraint=models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="ck_tax_remittances_period",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxremittance",
            constraint=models.CheckConstraint(
                condition=~models.Q(confirmation_ref=""),
                name="ck_tax_remittances_confirmation",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxremittance",
            constraint=models.UniqueConstraint(
                fields=("tenant", "journal_entry"), name="uq_tax_remittances_entry"
            ),
        ),
        migrations.AddIndex(
            model_name="taxremittance",
            index=models.Index(
                fields=["tenant", "-paid_on"], name="ix_tax_remittances_tenant_paid"
            ),
        ),
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(_pg_only(IMMUTABLE_SQL), _pg_only(DROP_IMMUTABLE_SQL)),
    ]

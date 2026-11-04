"""CR-038 W3 — THE READ METHOD ON THE ROW.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. ⚠ **ADDED BY THE MERGE LANE 2026-08-26: this file already
carried its ledger row and its `HUMAN-REVIEW-PENDING` status and had NO
`HUMAN-OWNED` marker**, so G7 named it. That is the same shape the guard list
itself records twice over — `apps/billing/issue.py`'s line reads *"the file
already carried HUMAN-REVIEW-PENDING and a ledger row and NO glob here matched
it"* — arriving from the other direction: there the glob was missing, here the
marker was. Either half alone leaves the gate reporting conform.

BR-MET-123 (PO 2026-08-26), verbatim: *"we are only selectiing the soruce and
accepting the CSV or excel file; thats is the scope right now; there is no
integration yet; but it should not stop us from tagging the soruce and
accepting the CSV or excel file"*.

BR-MET-014 (PO 2026-08-08), verbatim: *"Batch tags (month/cycle/route/service/
source) inherit to every row unless a row-level column overrides; effective
tags recorded on batch + rows"*.

WHAT THIS ADDS AND WHY THREE COLUMNS RATHER THAN ONE
-----------------------------------------------------
Three, because BR-MET-014 names three places a tag lives: the BATCH states it
once at step 1, each staged ROW carries the effective value (inherited or
overridden), and the committed READ carries it forward so the fact travels
with the reading rather than with the file it arrived in.

    read_import_batches.read_method   — the stage-1 choice
    read_import_rows.read_method      — inherited, or the row's own override
    meter_reads.read_method           — carried at commit

All three NULLABLE, and that is a rule rather than a convenience: BR-MET-014
makes every batch tag optional, an ESTIMATE was collected by nobody, and every
row already on file predates the column. NULL reads as "not stated".

⛔ THIS MIGRATION MOVES NO DATA — READ THE MAPPING DECISION
------------------------------------------------------------
There are readings on file today tagged under the OLD vocabulary
(`meter_reads.source` ∈ ami · manual · import, plus six `source_detail`
values). They are NOT rewritten here, and the choice is deliberate:

  1. **CLAUDE.md hard rule 4.** A committed read is append-only; the only
     UPDATE the rules permit sets `superseded_by_id`. A backfill UPDATE over
     `meter_reads` would be exactly the write the rule forbids, performed in
     bulk, on rows some of which are already BILLED.
  2. **Three of the six legacy words name no PO method.** `walk_by`,
     `ami_itron` and `ami_sensus` map to `walk_by`/`ami`/`ami` because they are
     the same word. `drive_by`, `self_read` and `field_visit` are NOT `amr`,
     NOT `manual` and NOT `mobile` — they are a different list. Mapping them
     would be inventing a collection method nobody recorded, and `import` is a
     TRANSPORT and states nothing about method at all.

So the mapping is **applied on READ**, declared once in
`apps/metering/read_import.py` (`LEGACY_READ_METHOD_BY_SOURCE` /
`LEGACY_READ_METHOD_BY_DETAIL` / `legacy_read_method`) and asserted in
`tests/test_cr038_w3_read_method.py::test_legacy_mapping_is_a_declared_table
_and_never_guesses`. `selectors.read_dict` serves `read_method` alongside a
`read_method_origin` of `recorded` · `derived` · `not_stated`, so no screen
ever shows a derived value as though somebody typed it.

If a later ruling wants the history rewritten, that is a NEW flagged migration
with the PO's word on the three unmappable values — not a silent addition here.

PARTITIONING
------------
`meter_reads` is partitioned monthly (DB-7/NFR-24). `ADD COLUMN` on the
partitioned parent propagates to every attached partition; a DETACHED archive
partition does not receive it. That is why `selectors.ReadArchiveResultSet.
_COLUMNS` deliberately does NOT name the new column — that class re-points ONE
compiled SELECT at each detached partition by table name, so naming a column an
older partition lacks would make the S25 archive toggle RAISE instead of
answer. An archived row therefore hydrates with `read_method` unset and falls
through to the derived translation, reporting `derived` or `not_stated`; it can
never report a wrong method. Same posture as `route_id`, which that SELECT list
has never carried either. The real fix belongs to the US-MET-020 job (a
per-partition probe, or an ALTER over the detached set) and is REPORTED.

RLS: none needed. All three tables already carry their policies (0003 / 0004);
a policy is per TABLE, not per column.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0031_cr038_backfill_service_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="readimportbatch",
            name="read_method",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="readimportrow",
            name="read_method",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="meterread",
            name="read_method",
            field=models.TextField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ────────────────────────────────────────────────────
# packet: CR-038 W3 (2026-08-26) — BR-MET-123 + BR-MET-014, quoted verbatim above
# generated: 2026-08-26 by the CR-038 W3 read-method lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred (no ledger row — this migration is
#         🔒-free: no RLS policy, no money rule, no idempotency key; the ONE
#         sensitive path it touches is BR-MET-018's file+tags key, and it
#         DELIBERATELY does not change it — see read_import.IDEMPOTENCY_TAG_FIELDS)
# gates: makemigrations --check clean · G31 PASS (0 undeclared, at the 509 ceiling)
#         · G32 PASS (790 keys, 0 unresolved) · G02/G06/G13/G16/G20/G40 PASS
#         · NO POSTGRES IN THIS WORKTREE CONTAINER, so the ADD COLUMN is NOT
#         proven against a live partitioned parent here and that is stated
#         rather than implied (hard-won law 1)
# exceptions: this migration MOVES NO DATA and that is a decision, not an
#         omission — hard rule 4 forbids rewriting a committed read, and three
#         of the six legacy `source_detail` words map to no PO method. The
#         translation is applied ON READ instead; see the module docstring above
#         and read_import.LEGACY_READ_METHOD_BY_SOURCE. REPORTED · a partition
#         detached before this ran does not receive the column, which
#         selectors.ReadArchiveResultSet._COLUMNS states and falls back for
# status: VERIFIED-UNRATIFIED
# ─────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   OQ-421 CLOSED 2026-08-27 — **store the twelve-month usage PER
#           METER as well.** PO verbatim: *"(b) Store it per meter too -
#           otherwise we will ahve to calculate it again and again"*. The
#           reason they gave IS the requirement: recomputation cost.
#           Screens: S50 (asset detail — the Reads tab's rollup strip) ·
#           S21 (the account tab this must never disagree with)
# Story:    US-AST-005 (the S50 Reads tab) · US-CUS-011 (the account half)
# Rules:    BR-MET-141 (the per-meter stored grain — NEW, this build) ·
#           BR-MET-106 (a month is computed from reads, STORED, RESTATED never
#           edited, ABSENT when unread, estimates counted and MARKED) ·
#           BR-MET-059 (a register is a channel) · BR-MET-135 / BR-AST-029 /
#           BR-RAT-014 (the registers that are never consumption) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 3 (an explicit unit)
# Defects:  DEF-798 (the monthly figure summed across channels unit-blind —
#           684 + 14 = 698 kWh where the truth is 684 kWh). **The grain of
#           this table is that fix expressed as a key**, see below.
# Tests:    06-backend/tests/test_def_798_register_blind_usage.py ·
#           06-backend/tests/test_oq_421_per_meter_monthly_usage.py
# Impacts:  apps/metering/monthly_usage_service.py (the SOLE writer) ·
#           apps/metering/asset_usage.py (the S50 reader) ·
#           apps/metering/migrations/0039_oq421_asset_monthly_usage.py
# ───────────────────────────────────────────────────────
"""BR-MET-141 — one meter's ONE REGISTER's usage in one calendar month, STORED.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the row this model describes is created by
a 🔒 migration (migration ordering) and keyed by a 🔒 idempotency fingerprint.
AI-authored 2026-08-27 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*). The ledger row is
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

────────────────────────────────────────────────────────────────────────────
THE RULING, VERBATIM, AND THE ONE CONSTRAINT IT CAME WITH
────────────────────────────────────────────────────────────────────────────
PO, 2026-08-27, closing OQ-421: *"(b) Store it per meter too - otherwise we
will ahve to calculate it again and again"*.

⚠ **THE PO CHOSE THE LESS REVERSIBLE DIRECTION KNOWINGLY, AND THAT WAS THE
WHOLE CONTENT OF THE QUESTION.** OQ-421 put it to them in as many words:
adding the dimension is a migration, removing it later is dropping a column
with data in it. They ruled with that stated.

The decision log adds the one thing the build may not do:

    "the stored per-meter row must be produced by the SAME functions the
     computed figure uses, not a second implementation — otherwise the account
     total and the meter total can disagree and no test would say which is
     right. The existing test that holds the two surfaces against each other
     stays, and now holds the stored row against the computed one."

So there is exactly one derivation in this repo and it is
`apps.metering.monthly_usage` — `group_by_month`, `summarise`, `fingerprint`,
the metric functions. This table holds what those functions said; it does not
know how to compute anything.

────────────────────────────────────────────────────────────────────────────
WHAT IS LOST IF THIS IS EVER REVERSED: A CACHE, NOT A FACT
────────────────────────────────────────────────────────────────────────────
Every column here is derivable from `meter_reads` alone. Nothing is entered by
a person, nothing is decided by staff, nothing here is the only copy of
anything. **`asset_usage.asset_usage_payload` reads a stored row when one
exists and COMPUTES the identical figure when one does not**, publishing which
it did as `source` — so dropping this table returns the product to the
behaviour it shipped with on 2026-08-26 and loses no statement about any
customer. `test_oq_421_per_meter_monthly_usage` asserts exactly that by
deleting every row and re-reading the payload.

That is the deliberate answer to the asymmetry the PO ruled against: the
direction is less reversible in SCHEMA and fully reversible in MEANING.

────────────────────────────────────────────────────────────────────────────
WHY THE KEY IS (asset, channel) AND NOT (asset) — DEF-798, AS A KEY
────────────────────────────────────────────────────────────────────────────
DEF-798, verbatim: *"monthly_usage.month_figure adds consumption over every
usable read for the account, so a demand peak-delta lands in the ENERGY total
and TOU window reads are double-counted against total. **Measured: 684 + 14 =
698 kWh where the truth is 684 kWh.**"*

A stored figure freezes whatever the derivation gets wrong, so the grain is
chosen so that the wrong number is **not representable**: one row per REGISTER
means 684 and 14 are two rows in two units of meaning, and no row in this table
can ever hold 698. There is no code path in the writer that adds two channels
together, because the bucket key is the channel.

`is_consumption` is deliberately **NOT a column**. It is a function of the
channel against `monthly_usage_service.NEVER_CONSUMPTION`, declared once, and a
stored copy would be a second statement of the same law that can drift from it
(hard-won law 5). The reader derives it.

────────────────────────────────────────────────────────────────────────────
WHY THE MODEL IS HERE AND `managed = False`
────────────────────────────────────────────────────────────────────────────
The same disposition `apps/customers/transfers.py` records for the `transfers`
table. `apps/metering/models.py` is not in this lane's write scope — a sibling
lane holds it for register units and multipliers in the same session — and a
model Django never imports at startup is invisible to the autodetector, so a
`CreateModel` in the migration would leave migration STATE holding a model the
app registry does not have and `makemigrations --check` would answer with a
`DeleteModel`. So: migration 0039 carries raw DDL and no model state, this
model is `managed = False`, and the two are held together by
`tests/test_oq_421_per_meter_monthly_usage.py::test_the_table_matches_the_model`,
which introspects the LIVE table and asserts a column for every model field and
no column the model does not declare.

**The one line that retires all of this** is `from apps.metering import
monthly_usage_asset  # noqa: F401` at the foot of `apps/metering/models.py`,
plus converting 0039's `RunPython` into a `CreateModel`, by whoever owns that
file next. REPORTED, not done here.
"""

from __future__ import annotations

from django.db import models as django_models

from core.dbfields import uuid7

#: The table the migration builds. One name, imported by the migration, the
#: model and the tests, so a rename cannot leave three spellings behind.
TABLE = "meter_read_asset_monthly_usage"


class AssetMonthlyUsage(django_models.Model):
    """One (tenant, asset, channel, period_month) statement — BR-MET-141.

    The column-for-column sibling of `MonthlyUsage` (BR-MET-106) at a finer
    grain, and deliberately the same SHAPE so a reader who knows one knows the
    other:

      * **The quantity carries its unit** (hard rule 3). `unit` is NOT NULL.
      * **Corrections RESTATE, they never edit** (hard rule 4). A late or
        superseded read supersedes the head and writes a NEW row; uniqueness
        holds over lineage HEADS only.
      * **An unread month is ABSENT, never `0`** (BR-MET-106). No row is
        written for a month a register did not report.
      * **Estimates count and are marked** (BR-MET-028).

    ⚠ `service_id` is NULLABLE and it is not part of the key. A meter's service
    is resolved through `asset → service_point → service`, exactly as the
    account writer resolves it, and a meter with no service point yields NULL —
    the account writer DROPS such a read because it belongs to no service, and
    this table keeps it because it still belongs to a METER. The column is
    carried for reporting and for the account tie-out, never to filter on.
    """

    id = django_models.UUIDField(primary_key=True, default=uuid7, editable=False)
    tenant = django_models.ForeignKey(
        "tenancy.Tenant", on_delete=django_models.PROTECT, db_column="tenant_id"
    )
    account = django_models.ForeignKey(  # ⚠ the SAME reviewed metering→customers
        "customers.Account",  # edge `meter_reads.account_id` already is (B2 §2)
        on_delete=django_models.PROTECT,
        db_column="account_id",
    )
    asset = django_models.ForeignKey(  # ⚠ the SAME reviewed metering→assets edge
        "assets.Asset", on_delete=django_models.PROTECT, db_column="asset_id"
    )
    service = django_models.ForeignKey(
        "tenancy.Service",
        on_delete=django_models.PROTECT,
        db_column="service_id",
        null=True,
        blank=True,
    )
    #: BR-MET-059's register string. NOT an enum column: the vocabulary is
    #: extensible by ruling (*"adding a register means adding a string"*), and
    #: a CHECK here would have to be migrated every time one is minted.
    channel = django_models.TextField()
    period_month = django_models.DateField()  # the FIRST DAY of the month
    #: Σ over this register's reads in this month, UNROUNDED, at the reads' own
    #: 18,6 precision. A QUANTITY, not money — rule 2's 4-dp law governs money.
    quantity = django_models.DecimalField(max_digits=18, decimal_places=6)
    unit = django_models.TextField()  # EXPLICIT, always (hard rule 3)
    read_count = django_models.IntegerField()
    estimated_read_count = django_models.IntegerField(default=0)
    source_read_ids = django_models.JSONField(default=list)
    #: `monthly_usage.fingerprint` of the SAME `MonthFigure` — CLAUDE.md rule 6
    #: over content, because nobody submits a "monthly usage request".
    source_fingerprint = django_models.TextField()
    computed_at = django_models.DateTimeField()
    superseded_by_id = django_models.UUIDField(null=True, blank=True)
    superseded_at = django_models.DateTimeField(null=True, blank=True)
    supersede_reason = django_models.TextField(null=True, blank=True)
    #: BR-TEN-057 — the sample tag on the OWNING row, inherited from the reads.
    is_sample = django_models.BooleanField(default=False)
    created_at = django_models.DateTimeField(auto_now_add=True)
    updated_at = django_models.DateTimeField(auto_now=True)

    class Meta:
        managed = False  # see the module docstring — the DDL is migration 0039's
        db_table = TABLE


#: The head predicate, written ONCE. `MonthlyUsage`'s reader and writer each
#: spell it out and the asymmetry between `superseded_by_id` (what the partial
#: unique is scoped on) and `superseded_at` (what a WITHDRAWAL sets, with no
#: successor to point at) is exactly the kind of thing a later lane "tidies"
#: into a bug. One name, both halves.
HEAD_FILTER = {"superseded_by_id__isnull": True, "superseded_at__isnull": True}


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-421 as ruled 2026-08-27 (decision log item 12) + BR-MET-106 + DEF-798
# generated: 2026-08-27 by the OQ-421/OQ-422 lane
# checklist: A✔ B=deferred(no-frontend-half — this is a model) C✔ D=deferred(no-API-half — no new route; the S50 payload is unchanged in shape) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row APPENDED)
# gates: ruff✔ black✔ · makemigrations --check clean · pytest tests/test_oq_421_per_meter_monthly_usage.py tests/test_def_798_register_blind_usage.py
# exceptions: E3 the model is `managed = False` and lives outside `models.py` — that file is another lane's this session; the DDL is migration 0039's and an introspection test holds the two together · E3 `is_consumption` is DERIVED at read time from `NEVER_CONSUMPTION` rather than stored, so the classification has one statement (law 5) · E3 `service_id` is nullable and not part of the key — a meter with no service point still belongs to a meter
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

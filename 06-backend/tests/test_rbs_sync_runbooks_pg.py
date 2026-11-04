# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-032 · US-RBS-034 (EP-RBS-05) — CR-075 wave Q′, the half the
#           default suite CANNOT prove.
# Rules:    CLAUDE.md hard-won law 14 (a savepoint is the only option on
#           PostgreSQL, and in-memory SQLite cannot see the difference) · hard
#           rule 1 (RLS FORCE; no tenant table without app.tenant_id) ·
#           BR-RBS-039 (every foreign read through a seam this module owns) ·
#           BR-RBS-007 (one record's failure never aborts the run) ·
#           BR-RBS-020 (the report is composed at close and frozen)
# Tests:    this file. The reasoning half is
#           tests/test_us_rbs_032_gis_reconciliation.py and
#           tests/test_us_rbs_034_undeliverable_contacts.py.
# Impacts:  apps/runbooks/definitions/gis_reconciliation.py ·
#           apps/runbooks/definitions/undeliverable_contacts.py ·
#           apps/metering/selectors.py · apps/notifications/selectors.py ·
#           apps/customers/selectors.py
# ───────────────────────────────────────────────────────
"""The two integration runbooks on real PostgreSQL, through the REAL seams.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_rbs_sync_runbooks_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY, IN ONE SENTENCE.** The sibling suites
replace the seams with fixed answers, so they prove the runbooks' REASONING and
nothing about the reads. **These cases replace nothing**: the connection check
asks `integrations` for real, the parcel batch is staged through `metering`'s own
importer, the returned letters are stamped through `notifications`' own
`mark_returned`, and the contact ladder is read out of `customers`. Every case
carries `requires_postgres` and SKIPS on the default suite rather than passing
vacuously — `G5` once ran the isolation suite on SQLite and called **192 skips a
pass**.

⚠ **WHAT THESE CASES WOULD PROVE ON SQLITE: NOTHING, AND FOR TWO REASONS.** The
seam cases read under a tenant context that only exists because PostgreSQL
enforces it; the savepoint case is meaningless where there is no
aborted-transaction state at all. The difference is the point.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest
from django.db import DatabaseError, connection

from apps.runbooks import models, services
from apps.runbooks.definitions import gis_reconciliation as gis
from apps.runbooks.definitions import undeliverable_contacts as uc
from apps.runbooks.engine import executor
from tests.isolation_helpers import live_tenant_context, requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · make_premises

pytestmark = [pytest.mark.django_db, requires_postgres]

#: The county's file, in the county's own column names.
PARCELS = (
    "PARCEL,SITE ADDRESS,CITY,STATE,ZIP,OWNER,USE\r\n"
    "88214,1408 Bluestem Ln,Katy,TX,77494,Whitfield Rentals LLC,Single-family\r\n"
    "88215,2201 Cane Island Pkwy,Katy,TX,77493,Chen David,Single-family\r\n"
    "88999,77 Nowhere Rd,Katy,TX,77494,Somebody Else,Single-family\r\n"
)

PARCEL_MAPPING = {
    "PARCEL": "external_ref",
    "SITE ADDRESS": "address_line",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "postal_code",
    "OWNER": "owner_manager",
    "USE": "premises_type",
}


def _runbook(tenant, definition):
    """The runbook row, written the way the product writes it.

    `cap` is typed rather than defaulted: `OQ-RBS-1731` CLOSED on 2026-09-06 at
    **100**, and `runbooks.cap` still has NO column default — wave `L4` carries
    that change, and a fixture that pre-empted it would hide the gap.
    """
    return models.Runbook.objects.create(
        tenant=tenant,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
        template_key=definition.key,
        timezone="America/Chicago",
        tags=list(definition.tags),
        origin=models.ORIGIN_SHIPPED,
        trigger_kind=models.TRIGGER_MANUAL,
        enabled=True,
        cap=100,
    )


def _run(tenant, definition, params=None):
    runbook = _runbook(tenant, definition)
    run = services.open_run(runbook, definition)
    return executor.execute(
        definition, tenant_id=tenant.id, run_id=run.pk, params=params or {}
    )


def _admin(actor):
    """The B12 §6a actor shape the importer's `@require_role` reads."""
    return SimpleNamespace(
        id=getattr(actor, "id", None),
        pk=getattr(actor, "id", None),
        role="system_admin",
        user=actor,
    )


def _an_account(tenant, actor, account_no, address="1408 Bluestem Ln"):
    """One account, anchored, with a status and a type — the row the schema wants.

    ⚠ **THREE THINGS A FIXTURE GETS WRONG HERE AND EACH IS THE SCHEMA BEING
    RIGHT.** `status` is a tenant-extensible LOOKUP row rather than the word
    (`BR-CUS-055`, r5 #20); `account_type` is `NOT NULL`; and
    `ck_accounts_anchored` refuses an account that hangs off neither a unit nor
    a premises — because an account nothing can be read against cannot be
    billed, which is exactly what runbook 1 exists to find.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=address)  # noqa: F405
    unit = make_unit(actor, premises["id"])  # noqa: F405
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.first(),
    )


def _stage_the_parcels(actor):
    from apps.metering import import_runs

    admin = _admin(actor)
    staged = import_runs.extract(
        admin,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": "county-parcels.csv",
            "content": PARCELS,
            "batch_label": "County parcels",
        },
    )
    import_runs.transform(admin, staged["id"], {"mapping": PARCEL_MAPPING})
    import_runs.validate(admin, staged["id"], "upsert")
    return str(staged["id"])


# ── the designed stop, through the real reads ─────────────────────────────


def test_no_connection_and_no_file_stops_runbook_20(brazos, dana):
    """PO 2026-09-06 — *"that is a valid case and state for us"*.

    ⚠ **THE `brazos` FIXTURE PROVISIONS A TENANT AND STAGES NOTHING**, which is
    exactly the day-one utility: no GIS connection, no parcel file, and a run
    that must SAY so rather than raise.
    """
    with live_tenant_context(brazos.id):
        result = _run(brazos, gis.RUNBOOK)
    stop = (result.set_results[gis.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing to compare."
    assert "No GIS connection is set up." in stop["detail"]
    assert result.subjects == ()
    # The KPI strip is ABSENT rather than zeroed — a strip of noughts over a run
    # that examined nothing reads exactly like a clean morning.
    assert "kpis" not in {block["block"] for block in result.report}
    assert "failed" not in str(result.report).lower()


def test_no_provider_and_no_returned_letters_stops_runbook_22(brazos, dana):
    with live_tenant_context(brazos.id):
        result = _run(brazos, uc.RUNBOOK, {"window": 7})
    stop = (result.set_results[uc.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing has come back."
    assert "No delivery provider is set up" in stop["detail"]
    assert "kpis" not in {block["block"] for block in result.report}


def test_the_stop_says_what_nobody_reports_beside_what_it_found(brazos, dana):
    """Hard-won law 7 — a declared blind spot with no number is an empty one."""
    with live_tenant_context(brazos.id):
        result = _run(brazos, uc.RUNBOOK, {"window": 7})
    checked = (result.set_results[uc.STEP_GATHER])["checked"]
    # ⚠ **STRUCTURALLY EMPTY ON THIS DEPLOYMENT, AND THE ASSERTION SAYS SO.** No
    # adapter writes either status on any channel (`delivery_ops.queue_health`:
    # *"delivery is out of this release by PO ruling (2026-08-15)"*). The day one
    # does, this line is where the change announces itself.
    assert checked["not_reported"] == ["delivered", "bounced"]
    assert checked["feedback_items"] == 0


# ── the real seams answer the shape their caller reads ────────────────────


def test_the_premises_read_answers_every_key_runbook_20_walks(brazos, dana):
    """`DEF-075`'s defect was a seam that answered `None` and read as *no findings*."""
    with live_tenant_context(brazos.id):
        make_premises(dana)  # noqa: F405 — from test_us_met_helpers
        rows = gis.metering_seam.premises_for_reconciliation(include_sample=True)
    assert rows, "no premises were created; nothing is concluded"
    wanted = set(gis.FIELD_LABELS) | {
        "premises_id",
        "label",
        "external_ref",
        "premises_type_label",
        "is_sample",
    }
    assert wanted <= set(rows[0])


def test_the_contact_ladder_answers_in_the_cards_own_order(brazos, dana):
    from apps.customers import models as customer_models

    with live_tenant_context(brazos.id):
        premises = make_premises(dana)  # noqa: F405
        account = _an_account(brazos, dana, "A-10432")
        customer_models.Contact.objects.create(
            tenant=brazos,
            account=account,
            full_name="Nunes, R.",
            email="nunes@example.test",
            phone="+15550100",
            is_primary=True,
        )
        customer_models.Address.objects.create(
            tenant=brazos,
            account=account,
            kind="mailing",
            line1="12 Prairie Bend Ct",
            city="Katy",
            state="TX",
            postal_code="77494",
        )
        answer = uc.customers_seam.contact_channels_for([account.id])
    assert premises is not None
    entry = answer[str(account.id)]
    assert entry["channels"] == ["email", "text", "post"]
    assert entry["post"].startswith("12 Prairie Bend Ct")


def test_the_feedback_read_names_both_halves(brazos, dana):
    with live_tenant_context(brazos.id):
        answer = uc.notifications_seam.undeliverable_feedback()
    assert set(answer) >= {"items", "messages_on_file", "not_reported", "channels_with_traffic"}
    assert answer["not_reported"] == ["delivered", "bounced"]


# ── a real staged file, matched, planned, and nothing written ─────────────


def test_a_real_parcel_file_is_matched_planned_and_nothing_is_changed(brazos, dana):
    """The whole runbook against `metering`'s own importer and its own premises.

    ⚠ **`validate` AND NOT `load`.** A loaded run's rows are premises by then;
    the runbook reads a batch that has been read, mapped and judged and has
    written nothing.
    """
    from apps.metering import models as metering_models

    with live_tenant_context(brazos.id):
        make_premises(dana)  # noqa: F405 — 1408 Bluestem Ln
        make_premises(  # noqa: F405
            dana,
            address_line="2201 Cane Island Pkwy",
            postal_code="77494",
            owner_manager="Chen David",
        )
        before = metering_models.Premises.objects.count()
        batch_id = _stage_the_parcels(dana)
        result = _run(brazos, gis.RUNBOOK, {"batch": batch_id})
        after = metering_models.Premises.objects.count()

    assert (result.set_results[gis.STEP_GATHER]).get("stop") is None
    assert len(result.subjects) == 3
    matched = (result.set_results[gis.STEP_MATCH])["checked"]
    assert matched["parcels_examined"] == 3
    assert matched["matched_on_standardised_address"] == 2
    assert matched["no_premises_found"] == 1
    # ⚠ **NOTHING IS WRITTEN, AND THE COUNT IS THE PROOF.** The port is bound
    # (`CR-075` task `L2`) and `engine.acts.LIVE_ENABLED_RUNBOOKS` is empty, so
    # every runbook is handed a writer-less copy and the refusal is the outcome.
    assert after == before
    assert gis.OUTCOME_APPLIED not in result.counts
    assert result.records[0].outcome in (
        gis.OUTCOME_PLANNED,
        gis.OUTCOME_AGREES,
        gis.OUTCOME_NEEDS_A_PERSON,
        gis.OUTCOME_NEVER_TOUCHED,
    )


def test_a_loaded_batch_is_not_offered_as_a_landed_one(brazos, dana):
    """Its rows are premises by then; reconciling it compares the estate with itself."""
    from apps.metering import models as metering_models

    with live_tenant_context(brazos.id):
        make_premises(dana)  # noqa: F405
        batch_id = _stage_the_parcels(dana)
        metering_models.ImportRun.objects.filter(pk=batch_id).update(status="loaded")
        result = _run(brazos, gis.RUNBOOK, {"batch": batch_id})
    assert (result.set_results[gis.STEP_GATHER])["stop"]["headline"] == (
        "That parcel file is not here."
    )


# ── a real returned letter, through notifications' own writer ─────────────


def _a_paper_message(tenant, account, copy_no=0):
    """One letter that left the building.

    ⚠ **`copy_no` IS WHAT MAKES A SECOND LETTER LAWFUL** —
    `uq_outbound_msgs_source_channel` is one row per document per channel
    (`BR-BIL-016`), and `copy_no > 0` is the deliberate extra copy. A fixture
    wanting three letters for one account is asking for three copies, and the
    constraint refusing the naive version is the rule working.
    """
    from apps.notifications import models as notification_models

    return notification_models.OutboundMessage.objects.create(
        tenant=tenant,
        source_type="invoice",
        source_id=account.id,
        channel=notification_models.CHANNEL_PRINT,
        copy_no=copy_no,
        account=account,
        recipient_address="12 Prairie Bend Ct, Katy TX 77494",
        status=notification_models.STATUS_SENT,
    )


def test_a_returned_letter_suppresses_post_and_names_its_fall_back(brazos, dana):
    """`US-RBS-034`'s acceptance sentence, through the real reads and writer.

    ⚠ **THE LETTER IS STAMPED THROUGH `delivery_ops.mark_returned`**, which is a
    PERSON's act (`US-NOT-014` TC-1) and the only feedback this deployment can
    produce at all: `bounced` and `failed` are provider facts and no adapter
    writes them on any channel.
    """
    from apps.customers import models as customer_models
    from apps.notifications import delivery_ops
    from django.utils import timezone

    with live_tenant_context(brazos.id):
        account = _an_account(brazos, dana, "A-10433", "2 Mill Rd")
        customer_models.Contact.objects.create(
            tenant=brazos,
            account=account,
            full_name="Nunes, R.",
            email="nunes@example.test",
            is_primary=True,
        )
        message = _a_paper_message(brazos, account)
        events, refused = delivery_ops.mark_returned(
            message_ids=(message.pk,),
            at=timezone.now() - dt.timedelta(hours=2),
            actor=_admin(dana),
        )
        assert len(events) == 1 and not refused
        result = _run(brazos, uc.RUNBOOK, {"window": 7})

    assert (result.set_results[uc.STEP_GATHER]).get("stop") is None
    plan = (result.set_results[uc.STEP_FLAG])["plan"]
    assert len(plan) == 1
    assert plan[0]["kind"] == uc.KIND_RETURNED_POST
    assert plan[0]["falls_back_to"] == uc.CHANNEL_EMAIL
    assert plan[0]["account_label"] == "Nunes, R."
    # Neither port binds a writer, so the plan is a plan.
    assert result.records[0].outcome == uc.OUTCOME_PLANNED
    assert "has no writer bound" in result.records[0].decided_by_rule


def test_the_window_excludes_an_older_letter_and_counts_it(brazos, dana):
    """Without a window this runbook re-suppresses the same channels for ever."""
    from apps.customers import models as customer_models
    from apps.notifications import delivery_ops
    from django.utils import timezone

    with live_tenant_context(brazos.id):
        account = _an_account(brazos, dana, "A-10434", "3 Ridge Ln")
        message = _a_paper_message(brazos, account)
        delivery_ops.mark_returned(
            message_ids=(message.pk,),
            at=timezone.now() - dt.timedelta(days=40),
            actor=_admin(dana),
        )
        result = _run(brazos, uc.RUNBOOK, {"window": 7})
    checked = (result.set_results[uc.STEP_GATHER])["checked"]
    assert checked["feedback_items"] == 0
    assert checked["items_outside_the_window"] == 1


# ── hard-won law 14 ───────────────────────────────────────────────────────


def test_one_records_database_error_never_aborts_the_run(brazos, dana, monkeypatch):
    """`BR-RBS-007` — and on PostgreSQL only a SAVEPOINT can deliver it.

    ⚠ **THIS CASE IS GREEN ON SQLITE FOR THE WRONG REASON**, which is why it
    lives here and skips there: SQLite has no aborted-transaction state, so a
    runbook that carried on without a savepoint would pass. On PostgreSQL the
    first refused statement poisons the transaction and every later query raises
    `InFailedSqlTransaction`, so a green here is a statement about the savepoint
    and nowhere else.
    """
    from apps.customers import models as customer_models
    from apps.notifications import delivery_ops
    from django.utils import timezone

    from apps.runbooks import boundary

    # ⚠ **THE REFUSAL IS INJECTED AT THE PORT, WHICH IS WHERE A WRITE ACTUALLY
    # GOES, AND `Step` IS FROZEN ANYWAY.** Patching the step function would test
    # a shape rather than the path: a real suppression reaches the database
    # through `PortDeclaration.call`, so that is where a refused statement comes
    # from in production and that is where this one comes from here.
    seen: list[str] = []
    original_call = boundary.PortDeclaration.call

    def refusing_call(self, *args, **kwargs):
        if self.name == "suppress_channel":
            seen.append(self.name)
            if len(seen) == 1:
                with connection.cursor() as cursor:
                    # A REAL statement the database refuses — not a bare Python
                    # exception — because what is under test is what PostgreSQL
                    # does to the surrounding transaction.
                    cursor.execute("INSERT INTO runbook_runs (id) VALUES (NULL)")
        return original_call(self, *args, **kwargs)

    monkeypatch.setattr(boundary.PortDeclaration, "call", refusing_call)

    with live_tenant_context(brazos.id):
        account = _an_account(brazos, dana, "A-10435", "4 Cedar St")
        customer_models.Contact.objects.create(
            tenant=brazos, account=account, full_name="Nunes, R.", email="n@x.test", is_primary=True
        )
        for copy_no in range(3):
            message = _a_paper_message(brazos, account, copy_no)
            delivery_ops.mark_returned(
                message_ids=(message.pk,),
                at=timezone.now() - dt.timedelta(hours=2),
                actor=_admin(dana),
            )
        result = _run(brazos, uc.RUNBOOK, {"window": 7})

    assert len(result.subjects) == 3
    assert len(seen) == 3, (
        "the run stopped at the first refused record: without a savepoint the "
        "transaction is aborted and every later record is lost at COMMIT"
    )
    assert result.records[0].outcome == executor.OUTCOME_FAILED
    # ⚠ AND THE REST CARRIED ON. A run that returned three `failed` rows would
    # satisfy the count above and prove nothing — that is the false pass this
    # line closes.
    assert executor.OUTCOME_FAILED not in [one.outcome for one in result.records[1:]]


def test_the_savepoint_is_the_only_thing_between_this_and_a_lost_run():
    """The engine's own guarantee, asserted where it can actually be false.

    ⚠ Deliberately NOT a test of the runbooks: it asserts that a refused
    statement inside a nested `atomic()` leaves the outer transaction usable,
    which is the property `_run_one_record` depends on and the property SQLite
    cannot have.
    """
    from django.db import transaction

    with transaction.atomic():
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("INSERT INTO runbook_runs (id) VALUES (NULL)")
        except DatabaseError:
            pass
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)

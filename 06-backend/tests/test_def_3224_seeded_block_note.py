# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-3224 (high, 2026-09-02) — a service the tenant SELLS is dropped
#           from the sample estate and nothing on screen ever says so. The
#           seeder composes a correct sentence naming the service and the
#           reason and writes it to `logger.info`. The block SUCCEEDS, so every
#           surface is green: 95 bills issued, 0 of 17 blocks failed, and
#           electric had no line on any of them — not even its $12.00 base,
#           which is $576.00 a month across 48 units.
# Rules:    BR-TEN-060 (a gap is NAMED, never swallowed) · BR-MET-003 (a seeder
#           must not plant a service the utility does not sell) · B14 rule 31
#           (nothing internal is ever visible to a utility user) · CLAUDE.md
#           law 2 (built is not wired) · law 1 (a comment claiming a guarantee
#           is not the guarantee)
# Story:    US-TEN-019 (sample data)                    Screens: S8 (SET-03)
# ───────────────────────────────────────────────────────
"""THE SENTENCE REACHES THE PANEL, FROM A REAL SEEDED RUN.

WHY THIS FILE EXISTS, AND IT IS `DEF-3224`'s ESCAPE REASON WORD FOR WORD
------------------------------------------------------------------------
**Three checks all passed on it and none of them asked the question.**

  1. The seeding block **SUCCEEDED** — the estate WAS built — so the block
     outcome is `seeded` and the S8 panel is entirely green.
  2. The refusal sentence **EXISTS and is well written**, naming electric and
     the reason, and it goes to `logger.info` — a server log a clerk cannot
     read — beside a comment saying *"a utility that cannot see gas in its demo
     will ask why"*. That is CLAUDE.md law 1 exactly.
  3. `test_service_billing_coverage.py` counts **INVOICES PER TENANT**, so a
     tenant that bills water correctly and drops electric entirely scores as a
     PASS. A count of invoices cannot see a missing SERVICE on those invoices.

⚠ **AND G13's TRAP IS THE ONE THIS FILE IS SHAPED AROUND.** A `detail` field
that nothing populates is dead UI: it renders nothing, every test passes, and
the feature does not exist. So the case that matters most below does not assert
that a field exists or that a function returns a string — it **provisions the
Product Owner's own tenant, runs the whole sample plant, and reads the sentence
back out of the ledger the S8 panel serves from.**

RED PROVED FIRST (hard-won law 7). See each case; the end-to-end one is quoted
in `test_a_refused_service_is_named_on_the_panel_after_a_real_plant`.
"""

from __future__ import annotations

import importlib.util
import pathlib
import uuid
from types import SimpleNamespace

import pytest

from apps.metering import sample_data as metering_sample_data
from apps.metering import services as metering_services
from apps.tenancy import sample_data, sample_notes
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: The block the estate is planted by, and therefore the one that owes the note.
#: Taken from the orchestrator's own list so this cannot name a block that no
#: longer exists.
ESTATE_BLOCK = "metering:seed_sample_records"


def _fake_every_seam(monkeypatch, *, counts: int = 1) -> None:
    """A one-line fake on every block's seam — the orchestrator under test.

    The real seeders plant an entire estate and take minutes; what four of the
    five cases below examine is the REPORTING, so each block becomes a fake.
    The fifth case runs the real thing and is marked `requires_postgres`.
    """
    from importlib import import_module

    for spec in sample_data.SAMPLE_MODULES:
        services = import_module(f"apps.{spec.module}.services")

        def make():
            def fake(actor):
                return counts

            return fake

        monkeypatch.setattr(services, spec.seam, make(), raising=False)


def _g28_patterns():
    """G28's OWN pattern list, loaded from the gate file.

    Application code may not import a gate script, so `apps.tenancy.
    sample_notes` re-declares these patterns. Two copies of one list drift
    silently unless something holds them together — this is that something. A
    pattern added to the gate and not to the module turns this test red.
    """
    path = REPO_ROOT / "10-scripts/gates/g28_internal_references.py"
    spec = importlib.util.spec_from_file_location("g28_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PATTERNS


# ── 1 · the sentence is fit for a SCREEN (B14 rule 31) ─────────────────────
def test_every_refusal_sentence_reaches_the_screen_with_no_internal_reference():
    """**RED-PROVED by feeding the raw sentences to G28's own patterns:** two of
    the four hit — `_SEWER_NEEDS_WATER` on `BR-RAT-015` (rule or story id) and
    `_NO_DEFAULT_UOM` on `CLAUDE.md rule 3`. The PO's words, 2026-08-19:
    *"Youa re also adding internal content and BR codes on screen, that is not
    required."*
    """
    patterns = _g28_patterns()
    raw = {
        "no_default_uom": fixture._NO_DEFAULT_UOM.format(service="gas"),
        "multiplier_no_factor": fixture._MULTIPLIER_NO_FACTOR.format(
            service="gas", register="therm", billed="ccf"
        ),
        "sewer_needs_water": fixture._SEWER_NEEDS_WATER,
        "not_in_the_shape": fixture._NOT_IN_THE_SHAPE.format(service="hydrogen"),
    }

    dirty = [
        f"{name}: {label}"
        for name, text in raw.items()
        for label, pattern in patterns
        if pattern.search(text)
    ]
    assert dirty, (
        "no raw refusal sentence carries an internal reference any more — if the "
        "owning lane cleaned them at source, `sample_notes.for_screen` is now a "
        "no-op and this file should say so rather than keep implying otherwise"
    )

    clean = {name: sample_notes.for_screen(text) for name, text in raw.items()}
    leaked = [
        f"{name}: {label} in {clean[name]!r}"
        for name in raw
        for label, pattern in patterns
        if pattern.search(clean[name] or "")
    ]
    assert not leaked, "a screen sentence still carries an internal reference:\n  " + "\n  ".join(
        leaked
    )

    # A sentence that carries nothing internal is returned UNTOUCHED — asked of
    # the module's own predicate rather than listed here, so this keeps holding
    # when the owning lane cleans one at source.
    untouched = [
        name
        for name, text in raw.items()
        if not sample_notes.carries_internal_reference(text)
        and sample_notes.for_screen(text) != text
    ]
    assert not untouched, untouched
    # And one that DOES carry something still says something afterwards.
    assert all(clean[name] for name in raw), clean

    # ── clause 1 · a RATIONALE sentence in the middle is dropped whole ───────
    # B14 rule 33 puts rationale at zero words on screen anyway, and dropping it
    # leaves the fact and the instruction standing. Checked rather than
    # described, because "it still reads well" is not a property a comment can
    # guarantee (law 1).
    assert clean["no_default_uom"] == (
        "gas: the tenant declares no primary unit of measure for it, so a meter would "
        "have to be created with a blank UoM. Set a primary UoM on Settings -> "
        "Services & UoM and load the sample data again"
    )

    # ── clause 2 · THE LAST SENTENCE IS NEVER DROPPED ───────────────────────
    # `_MULTIPLIER_NO_FACTOR` carries its reference in its FINAL sentence, and
    # that sentence is where the instruction lives. The first draft of
    # `for_screen` dropped it — which is `G33`'s named failure: *"SHORTEN BY
    # DELETING THE RATIONALE, NEVER THE INSTRUCTION"*. This is the assertion
    # that stops that draft coming back.
    assert "load the sample data again" in clean["multiplier_no_factor"], clean[
        "multiplier_no_factor"
    ]
    # A one-sentence reason likewise keeps its words and loses the reference.
    assert clean["sewer_needs_water"].startswith("sewer: prices sewer as 40% of the WATER")
    assert "bill nothing" in clean["sewer_needs_water"]

    # And a cut never leaves visible damage behind — an orphan possessive or an
    # empty bracket where the reference used to be.
    for name, sentence in clean.items():
        assert "'s " not in sentence[:2], (name, sentence)
        assert "()" not in sentence and "( )" not in sentence, (name, sentence)

    # And nothing in, nothing out — a caller need not decide first.
    assert sample_notes.for_screen(None) is None
    assert sample_notes.for_screen("   ") is None


# ── 2 · the orchestrator records it on a block that SUCCEEDED ──────────────
def test_a_seeded_block_carries_its_modules_note(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """**THE DEFECT.** `_record(spec, OUTCOME_SEEDED, ...)` passed no detail and
    the results entry hardcoded `"detail": None`, so a block that built an
    estate and left a service out of it had nowhere to say so.

    RED-PROVED: against the code before this lane, this failed with

        AssertionError: a SEEDED block cannot carry a note — DEF-3224
        assert None
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(monkeypatch)
    sentence = "electric: the estate is metered in water"
    monkeypatch.setattr(
        metering_services, "seed_sample_records_note", lambda: sentence, raising=False
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    row = blocks[ESTATE_BLOCK]
    assert row["outcome"] == "seeded", "the note must not turn a good block red"
    assert row["detail"], "a SEEDED block cannot carry a note — DEF-3224"
    assert sentence in row["detail"]
    # Every other seeded block still carries nothing: a module that publishes no
    # note reports exactly what it reported before.
    others = [k for k, r in blocks.items() if k != ESTATE_BLOCK and r["detail"]]
    assert not others, others


def test_a_module_with_nothing_to_report_still_says_nothing(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """A note seam answering `None` leaves the line exactly as it was.

    The ordinary case is a tenant whose estate speaks every service it sells,
    and a panel that grew a sentence per block would teach people to stop
    reading the sentences.
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(monkeypatch)
    monkeypatch.setattr(metering_services, "seed_sample_records_note", lambda: None, raising=False)

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    assert blocks[ESTATE_BLOCK]["outcome"] == "seeded"
    assert blocks[ESTATE_BLOCK]["detail"] is None


def test_a_note_seam_that_raises_never_fails_the_run(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """Narration must never break seeding.

    A seam that blows up is logged and treated as having no note — the block
    still seeded, and refusing a whole sample plant because a sentence could
    not be composed would be a worse defect than the one being fixed.
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(monkeypatch)

    def explode():
        raise RuntimeError("the note seam is broken")

    monkeypatch.setattr(metering_services, "seed_sample_records_note", explode, raising=False)

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        summary = sample_data.run_summary()
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    assert summary["succeeded"] is True
    assert blocks[ESTATE_BLOCK]["outcome"] == "seeded"
    assert blocks[ESTATE_BLOCK]["detail"] is None


@requires_postgres
def test_a_note_seam_that_hits_a_DATABASE_error_never_fails_the_run(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """**CLAUDE.md law 14, and the case above cannot see it.**

    The note seam READS the tenant's own tables, so what it raises in real life
    is a DATABASE error and not a `RuntimeError`. On PostgreSQL a failed
    statement aborts the WHOLE transaction: catching it and carrying on leaves
    `_record`'s write failing with `InFailedSqlTransaction`, and a block that
    seeded perfectly is reported FAILED because its NARRATION broke.

    ⚠ **THE CASE ABOVE PASSES EITHER WAY AND SO DOES THE ENTIRE SUITE**, because
    `config/settings/test.py` hardcodes in-memory SQLite and SQLite has no
    aborted-transaction state. That is exactly the trap law 14 was written from,
    and it is why this case is marked `requires_postgres` and run separately.

    RED-PROVED by removing the nested `transaction.atomic()` from
    `_seeded_note` and running this against PostgreSQL 16:

        django.db.transaction.TransactionManagementError: An error occurred in
        the current transaction. You can't execute queries until the end of the
        'atomic' block.
    """
    from django.db import connection

    tenant, _ = provisioned_tenant()
    _fake_every_seam(monkeypatch)

    def bad_query():
        # A REAL failed statement, which is the only thing that puts PostgreSQL
        # into the aborted state this case exists to survive.
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM a_table_that_does_not_exist")

    monkeypatch.setattr(metering_services, "seed_sample_records_note", bad_query, raising=False)

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        summary = sample_data.run_summary()
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    assert summary["succeeded"] is True, summary
    assert blocks[ESTATE_BLOCK]["outcome"] == "seeded", blocks[ESTATE_BLOCK]
    assert blocks[ESTATE_BLOCK]["detail"] is None


def test_the_retry_reports_the_same_note_as_the_run(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """One question, one answer, whichever button was pressed.

    A block that seeds through **Retry** and says nothing, while the same block
    in a full run names the service it left out, would be two answers to one
    question depending on how the operator got there.
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(monkeypatch)
    sentence = "electric: the estate is metered in water"
    monkeypatch.setattr(
        metering_services, "seed_sample_records_note", lambda: sentence, raising=False
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        report = sample_data.retry_block(
            admin_actor(), module="metering", block="seed_sample_records"
        )

    assert report["block"]["outcome"] == "seeded"
    assert sentence in (report["block"]["detail"] or "")


# ── 3 · THE ONE THAT PROVES THE FEATURE EXISTS ─────────────────────────────
@requires_postgres
def test_a_refused_service_is_named_on_the_panel_after_a_real_plant(audit_rows):
    """**A REAL TENANT, A REAL PLANT, AND THE SENTENCE READ BACK OFF THE PANEL.**

    Nothing is faked here. The tenant is provisioned through the real signup
    path, the whole sample plant runs, and the sentence is read out of
    `stored_blocks()` — the same call that serves the S8 Sample data panel, so
    what this asserts is what a clerk sees.

    ── **WHY THE SHAPE IS ELECTRIC + SEWER AND NOT THE PO's OWN THREE** ───────
    `DEF-3224` was reported on Electric + Water + Sewer: the estate took ONE
    metered backbone, water won it, and **electric got no service point, no
    meter, no read and no line on any of the 95 issued bills — not even its
    `$12.00` monthly charge, `$576.00` a month across 48 units** — while 0 of 17
    blocks failed and every surface was green.

    ⚠ **THAT EXACT SHAPE STOPPED ARISING WHILE THIS FIX WAS BEING BUILT.**
    `CR-062` group C landed, the estate now meters EVERY metered service a
    utility sells, `_NOT_THE_BACKBONE` is gone from the fixture, and electric is
    no longer refused. **The message still has to exist**, because services are
    still legitimately refused — and the standing example is the one used here:
    **sewer without water.** `BR-RAT-015` ❄️ prices sewer at 40% of the WATER
    usage charge, so a utility that sells sewer and not water has no basis for
    the percentage and gets no sewer service point. That is CORRECT rather than
    a fault, and it is exactly the case a clerk will ask about.

    So this asserts the GENERAL property — every service the tenant sells that
    the estate does not speak is NAMED on the panel — and it names no service
    itself. Written against electric it would have passed today and silently
    stopped testing anything the day `CR-062` landed.

    RED-PROVED against the code before this lane:

        AssertionError: the panel says nothing about the services this tenant
        sells and the estate does not speak — DEF-3224
        assert ''
    """
    slug = f"def3224-{uuid.uuid4().hex[:10]}"
    payload = dict(brazosbend_payload())
    payload["subdomain"] = slug
    payload["name"] = f"DEF-3224 {slug}"
    # Electric is metered and seeds the estate; sewer is sold and cannot be
    # seeded, because there is no water charge for it to be a percentage of.
    payload["services"] = ["electric", "sewer"]
    payload["owner"] = {**dict(payload["owner"]), "email": f"owner@{slug}.test"}

    tenant, result = provisioned_tenant(payload)
    # ⚠ NOT `admin_actor()`: that helper invents a uuid no `users` row carries,
    # `_attributed` strips it, and BR-BIL-058's release gate then refuses to
    # issue a bill — five money blocks fail for a reason unrelated to this
    # defect. The real job body uses the provisioning owner (DEF-2722 tc1).
    owner_id = uuid.UUID(str(result["owner_user_id"]))
    actor = SimpleNamespace(
        id=owner_id,
        pk=owner_id,
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(actor)
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}
        plan = metering_sample_data.estate()
        seam_answer = metering_services.seed_sample_records_note()

    # The fixture must actually be refusing something, or this case is a check
    # that cannot fail (DEF-182). It says WHICH, so a fixture change that removes
    # the refusal reports that fact instead of quietly passing.
    assert plan.refused, (
        "this tenant sells a service the estate cannot speak and the fixture refuses "
        "nothing — the shape this case is built on has changed"
    )
    refused_codes = [code for code, _reason in plan.refused]

    row = blocks[ESTATE_BLOCK]
    detail = row["detail"] or ""

    # The block SUCCEEDED — that is the whole point of the defect, and the note
    # must not have turned it into a failure.
    assert row["outcome"] == "seeded", row

    assert detail, (
        "the panel says nothing about the services this tenant sells and the "
        "estate does not speak — DEF-3224"
    )
    missing = [code for code in refused_codes if code not in detail]
    assert not missing, (
        f"the panel does not name {missing}, which this tenant SELLS and the estate "
        f"does not speak — DEF-3224. It says: {detail!r}"
    )
    # The seam and the panel are the same sentence: two spellings of one fact is
    # how a screen and a log come to disagree.
    assert seam_answer is not None
    assert sample_notes.for_screen(seam_answer) == detail

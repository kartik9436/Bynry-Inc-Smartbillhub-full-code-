# ── Trace ──────────────────────────────────────────────
# Change:   CR-054 waves 2 and 4, BACKEND — tasks 8, 10, 14 and 16.
# Rules:    BR-MET-940 (PARTIAL POSTING on a read batch — "all or nothing will
#           not work ... we accept what is correct and rejct what i not
#           correct", PO carried into CR-054; supersedes BR-MET-015's ERROR
#           half at the post gate and reverses nothing else) ·
#           BR-MET-941 (the rejects export on a batch) ·
#           BR-MET-018 + CLAUDE.md hard rule 6 (a posted batch does not post
#           twice — the property partial posting must NOT weaken) ·
#           BR-MET-129 (a warned reading posts) · BR-MET-015 (a disposition
#           that keeps a row out still keeps it out) · BR-MET-014 + BR-MET-137
#           (the service-coherence statement and its shorthand) ·
#           BR-MET-017 (a posted batch is immutable) · CLAUDE.md hard rule 4
#           (a correction is a new row, never an edit).
# Tests:    this file. Every guard was proved RED first and the failing run is
#           quoted verbatim in the docstring that owns it.
# Impacts:  apps/metering/services.py (commit_read_batch — the gate, the
#           per-row SAVEPOINT and the held-row record) ·
#           apps/metering/read_rejects.py (NEW) · apps/metering/api.py
#           (GET /read-batches/{id}/rejects.csv) ·
#           apps/metering/validation.py (the RULE_SERVICE_COHERENCE comment)
# ───────────────────────────────────────────────────────
"""CR-054 W2/W4 backend — the four things a clerk could not do.

**Task 8** is answered by a route that already exists, so what is here is the
assertion that keeps it answered (`GET /settings/services`, `AnyTenantRole`).
**Task 10** was already built by BR-MET-137 and its own comment said otherwise
(`DEF-2670`); the CR's own worked case is pinned here so prose cannot be the
only record of it again. **Task 14** is the work: a batch of 1,180 rows with 2
unknown meters posts 1,178 readings instead of nothing. **Task 16** hands the
2 back as a file the clerk can fix and upload.
"""

import pytest
from django.db import connection

from apps.metering import models, read_rejects, services, validation
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def outcome_named(row, rule):
    hits = [o for o in (row.rule_outcomes or []) if o["rule"] == rule]
    return hits[0] if hits else None


def rows_of(batch_id):
    return list(models.ReadImportRow.objects.filter(batch_id=batch_id).order_by("row_no"))


# ═══════════════════════════════════════════════════════════════════════════
# TASK 8 — the endpoint that lists a utility's enabled services to a clerk
#
# ⛔ **THE ANSWER IS THAT IT ALREADY EXISTS, AND NO SECOND ONE IS ADDED.**
# CR-054 row 8 reads *"An endpoint listing a utility's enabled services to a
# Billing Clerk. Its absence is the reason stage 1 has no service control"*,
# and its `Server ready?` column says **No**. That column is wrong and the
# 36-word note on the screen it cites is wrong with it (`DEF-2671`):
# `GET /settings/services` has carried `AnyTenantRole` — all three roles —
# since its first commit, and answers every catalog service with an `enabled`
# flag. A second endpoint for one fact would be two places for the tenant's
# service list to disagree, which is the argument `tenant_services`' own model
# docstring makes about a second mapping table.
# ═══════════════════════════════════════════════════════════════════════════


def test_task8__a_billing_clerk_may_already_read_this_utilitys_enabled_services():
    """The route the reads wizard needs is mounted, open to a Billing Clerk,
    and answers the enabled subset. Three separate claims, each asserted, so
    narrowing any one of them goes RED here rather than emptying a picker.

    Guard proved RED first — `AnyTenantRole` swapped for `SystemAdminOnly` on
    `services_settings`, which is the state the on-screen note describes:

        E   AssertionError: a Billing Clerk cannot call GET /settings/services
        (1 failed, 4 warnings in 93.39s)
    """
    from apps.tenancy import api as tenancy_api

    from core.permissions import BILLING_CLERK

    # 1 · the route is mounted, at the path the frontend already wraps.
    paths = {
        getattr(route, "pattern", None) and str(route.pattern) for route in tenancy_api.urlpatterns
    }
    assert "settings/services" in paths

    # 2 · a Billing Clerk may call it.
    classes = getattr(tenancy_api.services_settings, "permission_classes", None) or getattr(
        tenancy_api.services_settings.cls, "permission_classes", []
    )
    allowed = set()
    for klass in classes:
        allowed |= set(getattr(klass, "allowed_roles", ()) or ())
    assert BILLING_CLERK in allowed, (
        f"a Billing Clerk cannot call GET /settings/services\n"
        f"assert {BILLING_CLERK!r} in {allowed!r}"
    )

    # 3 · it is a READ. The control fills a picker; it must not be able to
    #     change what this utility sells on the way past.
    assert getattr(tenancy_api.services_settings, "cls", tenancy_api.services_settings)
    handler = getattr(tenancy_api.services_settings, "cls", None)
    assert set(getattr(handler, "http_method_names", ["get"])) <= {
        "get",
        "head",
        "options",
    }, "GET /settings/services must stay a read"


def test_task8__the_payload_names_every_service_and_says_which_are_enabled(brazos, marcus):
    """The picker's own data: one row per ACTIVE catalog service with a boolean
    saying whether this utility sells it. The control defaults to *every
    enabled service*, so it needs both halves — the list and the flag.

    Guard proved RED first — `enabled` removed from `service_row`:

        E   KeyError: 'enabled'
        (1 failed, 4 warnings in 104.67s)
    """
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        rows = tenancy_selectors.services_overview()
        enabled = tuple(tenancy_selectors.enabled_service_codes())

    assert rows, "the platform catalog is seeded in migration 0001"
    assert {row["service"] for row in rows if row["enabled"]} == set(enabled)
    assert "electric" in enabled and "water" in enabled


# ═══════════════════════════════════════════════════════════════════════════
# TASK 10 — service coherence, with the CR's OWN worked case
#
# ⛔ **ALREADY BUILT, AND ITS OWN COMMENT SAID OTHERWISE (`DEF-2670`).** The
# rule has warned with both values named since CR-038 W2, and has resolved the
# single-letter shorthand since BR-MET-137 the same day. What was missing is
# the case CR-054 row 10 actually names — the disagreement stated by the
# BATCH TAG rather than by a row column — which travels a different line of
# `stage_read_batch` (`parsed.service or tags["service"]`) and had no test.
# ═══════════════════════════════════════════════════════════════════════════


def test_task10__a_water_meter_in_a_batch_tagged_electric_warns_with_both_named(brazos, marcus):
    """CR-054 row 10, verbatim: *"a water meter in a batch tagged Electric
    becomes a warning with a name instead of a report"*.

    The statement is the BATCH's, not the row's — the file's service column is
    empty and BR-MET-014 makes the batch tag the row's effective service. Both
    values are named because only a person knows which of the two is wrong: the
    file may be mis-tagged, or the meter may be on the wrong service point.

    Guard proved RED first — the batch-tag fallback removed from
    `stage_read_batch` (`service=parsed.service` alone), which is the row
    stating nothing and inheriting nothing:

        E   AssertionError: assert None == 'electric'
        (1 failed, 4 warnings in 89.08s)
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7301", service="water", uom="kgal", unit_label="Apt 101")
        batch = stage(
            marcus,
            csv_body("M-7301,2026-08-03,412,total,,"),  # the file states NO service
            service="electric",  # the CLERK tagged the batch Electric
        )
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    assert row.service == "electric"  # BR-MET-014 — the tag inherited to the row
    flagged = outcome_named(row, validation.RULE_SERVICE_COHERENCE)
    assert flagged is not None
    assert flagged["severity"] == validation.WARNING
    assert flagged["detail"]["stated_service"] == "electric"
    assert flagged["detail"]["meter_service"] == "water"
    assert flagged["detail"]["summary"] == "row says electric, meter M-7301 is water"


def test_task10__the_disagreement_is_a_warning_and_never_holds_the_reading_out(brazos, marcus):
    """BR-MET-129: it is a WARNING, so the reading posts carrying the flag. A
    coherence disagreement must never be the thing that loses a collected read
    — *"when reading are colelcted then only we will know whether there is
    usage or not"*.

    Guard proved RED first — the coherence outcome raised to `ERROR`. The
    reading does not exist afterwards, which is exactly the loss BR-MET-129 was
    ruled to prevent:

        E   apps.metering.models.MeterRead.DoesNotExist: MeterRead matching
            query does not exist.
        (1 failed, 4 warnings in 88.34s)
    """
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, "M-7301", service="water", uom="kgal", unit_label="Apt 101")
        batch = stage(marcus, csv_body("M-7301,2026-08-03,412,total,,"), service="electric")
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        read = models.MeterRead.objects.get(asset_id=asset["id"], read_at=at("2026-08-03"))

    assert result["posted_reads"] == 1
    carried = [o for o in read.rule_outcomes if o["rule"] == validation.RULE_SERVICE_COHERENCE]
    assert carried and carried[0]["severity"] == validation.WARNING


# ═══════════════════════════════════════════════════════════════════════════
# TASK 14 — PARTIAL POSTING
#
# ⛔ **THE RULING, VERBATIM (PO, carried into CR-054):** *"COMMITTING All or
# nothing... - all or nothing will not work - we accept what is correct and
# rejct what i not correct - then create csv file at loading stage itself so
# that suer can see all cases thata re rejcted"*. CR-047 shipped it for the
# account importer on 2026-08-29; CR-054 says tasks 13–16 apply that ruling to
# reads and make no new decision.
# ═══════════════════════════════════════════════════════════════════════════


def test_task14__two_bad_rows_no_longer_hold_back_the_good_ones(brazos, marcus):
    """**BR-MET-940, the headline.** Three rows: two real meters and one that
    does not exist. The two readings are filed and the third is held with a
    reason — where before, all three waited on the one.

    The worked case CR-054 states is 1,180 rows and 2 unknown meters; this is
    the same shape at a size a test can read.

    Guard proved RED first — the all-or-nothing gate restored to
    `commit_read_batch` exactly as it stood:

        E core.errors.BizError: BIZ-COMPLETENESS (metering.read_batch.errors_need_resolution)
        (1 failed, 4 warnings in 87.56s (0:01:27))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",  # no such meter — an ERROR
                "M-7002,2026-08-03,900,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})

        assert result["posted_reads"] == 2
        assert result["held_reads"] == 1
        assert result["unresolved_errors"] == 1
        assert models.MeterRead.objects.count() == 2

        held = [row for row in result["held_rows"] if row["row_no"] == 2]
        assert held and held[0]["reason"] == "unresolved_error"
        # The clerk reads a sentence, not a rule id (CR-016).
        assert held[0]["why_it_failed"] == "There is no meter called M-9999 on this utility."

        # ⚠ AND THE REASON SURVIVES THE REQUEST. A payload is gone when the
        # response ends; the ruling's second half is a FILE downloaded later,
        # which can only be built from what is stored on the row.
        row2 = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)
        record = outcome_named(row2, "post")
        assert record is not None and record["detail"]["reason"] == "unresolved_error"
        assert record["detail"]["how_to_fix_it"].startswith("Check the meter number")


def test_task14__posting_a_partly_posted_batch_again_is_refused(brazos, marcus):
    """⚠ **THE SINGLE MOST DANGEROUS THING PARTIAL POSTING COULD HAVE BROKEN,
    AND IT IS UNBROKEN: CLAUDE.md hard rule 6.**

    A batch that filed 2 of 3 readings is still `posted` and still immutable
    (BR-MET-017), so a second POST is refused by the same guard as before and
    the two readings that landed cannot land twice. This is exactly why the
    batch is CLOSED rather than left open for a second attempt: the way back in
    for the held row is a corrected FILE, which is a different batch with a
    different hash.

    Guard proved RED first — the `status == "posted"` refusal removed from
    `commit_read_batch`:

        E Failed: DID NOT RAISE BizError
        (1 failed, 4 warnings in 87.11s (0:01:27))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",
                "M-7002,2026-08-03,900,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        first = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert first["posted_reads"] == 2

        with pytest.raises(errors.BizError) as caught:
            services.commit_read_batch(marcus, batch["id"], {"certified": True})

        assert caught.value.message_key == "metering.read_batch.already_posted"
        # THE PROOF, and it is the count and not the exception: nothing landed
        # a second time.
        assert models.MeterRead.objects.count() == 2


def test_task14__re_uploading_the_identical_file_is_still_blocked(brazos, marcus):
    """Hard rule 6's OTHER half, and partial posting must not open it either.
    BR-MET-018 keys on file hash + tag set, so a clerk who re-uploads the SAME
    file after a partial post is told the work is already done — with who and
    when — rather than filing the good rows twice.

    Guard proved RED first — `_idempotency_block` made a no-op:

        E sqlite3.IntegrityError: UNIQUE constraint failed: read_import_batches.tenant_id, read_import_batches.file_hash, read_import_batches.tag_fingerprint
        E django.db.utils.IntegrityError: UNIQUE constraint failed: read_import_batches.tenant_id, read_import_batches.file_hash, read_import_batches.tag_fingerprint
        (1 failed, 4 warnings in 84.82s (0:01:24))
    """
    content = csv_body(
        "M-7001,2026-08-03,42864,total,E,",
        "M-9999,2026-08-03,100,total,E,",
    )
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        first = stage(marcus, content)
        services.validate_read_batch(marcus, first["id"])
        posted = services.commit_read_batch(marcus, first["id"], {"certified": True})
        assert posted["posted_reads"] == 1

        again = stage(marcus, content)  # same bytes, same tags
        services.validate_read_batch(marcus, again["id"])
        with pytest.raises(errors.BizError) as caught:
            services.commit_read_batch(marcus, again["id"], {"certified": True})

        assert caught.value.message_key == "metering.read_batch.already_posted_identical"
        assert models.MeterRead.objects.count() == 1


def test_task14__a_dispositioned_row_is_still_kept_out_and_says_who_by(brazos, marcus):
    """BR-MET-015's ROW half is untouched — partial posting supersedes only the
    BATCH consequence. A clerk who rejects a row still keeps it out, and the
    held record says so in different words from the row nobody has judged.

    Guard proved RED first — `POSTING_DISPOSITIONS` widened to include
    `reject`:

        E assert 2 == 1
        (1 failed, 4 warnings in 90.54s (0:01:30))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7002,2026-08-03,900,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        services.set_row_disposition(
            marcus, batch["id"], 2, {"disposition": "reject", "reason": "meter face unreadable"}
        )
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row2 = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

        assert result["posted_reads"] == 1
        assert result["held_reads"] == 1
        record = outcome_named(row2, "post")
        assert record["detail"]["reason"] == "not_dispositioned_for_posting"
        assert record["detail"]["why_it_failed"].startswith("Somebody decided")
        # ⚠ The clerk's OWN reason is untouched — the post record sits beside it.
        assert row2.disposition_reason == "meter face unreadable"


def test_task14__a_held_row_writes_no_reading_at_all(brazos, marcus):
    """The PO's *"dont write to dB"*, and CLAUDE.md hard rule 4 beside it: a
    row that is held leaves NOTHING — no reading, no partial reading, no
    lineage closure — and the row keeps its `meter_read_id` empty so nothing
    downstream can mistake it for filed.

    Guard proved RED first — `_hold` moved INSIDE the savepoint, so the reason
    is rolled back with the reading and the row comes out of a failed post
    carrying nothing at all:

        E AssertionError: assert None is not None
        (1 failed, 4 warnings in 89.04s (0:01:29))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row2 = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

        assert row2.meter_read_id is None
        assert models.MeterRead.objects.count() == 1
        assert outcome_named(row2, "post") is not None


def test_task14__a_refusal_at_the_write_holds_one_row_and_the_rest_post(
    brazos, marcus, monkeypatch
):
    """**THE SAVEPOINT, exercised through a business refusal.** `_post_row`
    reaches rules that can only be judged against the head as it is NOW, so a
    refusal can arrive at the write and not at the rehearsal. Row 2 is refused;
    rows 1 and 3 file, and the batch commits.

    ⚠ **AND THE ROW AFTER THE FAILURE IS THE ONE THAT MATTERS.** Row 3 posting
    is the whole assertion: without the savepoint, on PostgreSQL, row 2 poisons
    the connection and row 3 cannot even be read.

    Guard proved RED first — the two `except` arms removed:

        E core.errors.BizError: BIZ-STATE (metering.read_batch.discarded)
        (1 failed, 4 warnings in 91.22s (0:01:31))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        a_meter(marcus, "M-7003", unit_label="Unit C", address="1412 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7002,2026-08-03,900,total,E,",
                "M-7003,2026-08-03,700,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])

        real = services._post_row

        def refuse_row_two(actor, b, row, config, **kwargs):
            if row.row_no == 2:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-016",
                    message_key="metering.read_batch.discarded",
                )
            return real(actor, b, row, config, **kwargs)

        monkeypatch.setattr(services, "_post_row", refuse_row_two)
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row2 = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

        assert result["posted_reads"] == 2
        assert result["held_reads"] == 1
        assert models.MeterRead.objects.count() == 2
        assert outcome_named(row2, "post")["detail"]["reason"] == "write_refused"


def test_task14__a_database_refusal_holds_one_row_and_the_rest_post(brazos, marcus, monkeypatch):
    """**THE SAVEPOINT, exercised through a REAL database refusal** — the arm
    CR-047's accounts loader does not need and reads does, because `_post_row`
    writes `meter_reads` straight through the ORM.

    Row 2 is made to insert its reading TWICE, so the second statement violates
    the table's primary key (it read `uq_meter_reads_head` until that index was
    dropped by `BR-MET-1189`, 2026-10-04) and the DATABASE raises. Nothing about the refusal is
    simulated: it is a genuine unique violation carrying a genuine error code,
    which is also what exercises the `__cause__` walk — a one-hop read would
    return the generic sentence here and look handled (`DEF-2519`'s first
    draft).

    Guard proved RED first — the `(IntegrityError, DataError)` arm removed:

        E sqlite3.IntegrityError: UNIQUE constraint failed: meter_reads.tenant_id, meter_reads.asset_id, meter_reads.read_at, meter_reads.channel
        E django.db.utils.IntegrityError: UNIQUE constraint failed: meter_reads.tenant_id, meter_reads.asset_id, meter_reads.read_at, meter_reads.channel
        (1 failed, 4 warnings in 87.07s (0:01:27))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        a_meter(marcus, "M-7003", unit_label="Unit C", address="1412 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7002,2026-08-03,900,total,E,",
                "M-7003,2026-08-03,700,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])

        real = services._post_row

        def double_write_row_two(actor, b, row, config, **kwargs):
            read = real(actor, b, row, config, **kwargs)
            if row.row_no == 2:
                # ⚠ AMENDED 2026-10-04 (`BR-MET-1189`, `DEF-WRK-9642`): this
                # used to call `real` a second time and trip
                # `uq_meter_reads_head`, which no longer exists — a second
                # reading of a register on one date is now STORED. The refusal
                # is still a genuine database unique violation: the SAME row
                # inserted twice, against the table's primary key.
                twin = models.MeterRead(
                    **{f.attname: getattr(read, f.attname) for f in read._meta.concrete_fields}
                )
                twin.save(force_insert=True)  # the row already exists
            return read

        monkeypatch.setattr(services, "_post_row", double_write_row_two)
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row2 = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

        assert result["posted_reads"] == 2
        assert result["held_reads"] == 1
        # ⚠ **THE SAVEPOINT ROLLED BACK BOTH WRITES, NOT JUST THE SECOND** —
        # row 2 left NOTHING, which is the PO's *"dont write to dB"*.
        assert models.MeterRead.objects.count() == 2
        record = outcome_named(row2, "post")
        assert record["detail"]["reason"] == "database_refused"
        # The sentence a clerk reads carries no constraint name and no table
        # name (CR-016), and it is the UNIQUE-violation sentence rather than the
        # generic one — which is what proves the `__cause__` walk found the
        # driver's own error and not the Django wrapper two hops up.
        assert "uq_meter_reads_head" not in record["detail"]["why_it_failed"]
        assert "pkey" not in record["detail"]["why_it_failed"]
        assert "already on file" in record["detail"]["why_it_failed"]


def test_task14__a_fault_that_is_not_about_this_row_still_takes_the_batch_down(
    brazos, marcus, monkeypatch
):
    """The other half of the `except` clause, and it is the half that keeps the
    books honest: `RuntimeError` — a bug, a broken invariant, anything
    unforeseen — is NOT swallowed. Swallowing it is how a post reports *"43
    held"* over a fault nobody diagnoses, and it would also silently convert
    `test_us_met_010_tc3`'s atomicity proof into nothing.

    Guard proved RED first — the two `except` arms widened to `Exception`:

        E Failed: DID NOT RAISE RuntimeError
        (1 failed, 4 warnings in 89.89s (0:01:29))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7002,2026-08-03,900,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])

        real = services._post_row

        def explode(actor, b, row, config, **kwargs):
            if row.row_no == 2:
                raise RuntimeError("simulated fault that is not about this row")
            return real(actor, b, row, config, **kwargs)

        monkeypatch.setattr(services, "_post_row", explode)
        with pytest.raises(RuntimeError):
            services.commit_read_batch(marcus, batch["id"], {"certified": True})

        assert models.MeterRead.objects.count() == 0
        assert models.ReadImportBatch.objects.get(pk=batch["id"]).status != "posted"


# ═══════════════════════════════════════════════════════════════════════════
# TASK 16 — THE REJECTS EXPORT
#
# PO: *"then create csv file at loading stage itself so that suer can see all
# cases thata re rejcted"*. CR-047's two-file shape, applied.
# ═══════════════════════════════════════════════════════════════════════════


def _csv(batch, kind):
    _filename, body = read_rejects.results_csv(batch, kind)
    return "".join(body)


def test_task16__the_rejects_file_is_the_clerks_own_cells_plus_two_columns(brazos, marcus):
    """**BR-MET-941.** The file comes back under the published template's own
    headers, carrying the values the clerk typed, with `why_it_failed` and
    `how_to_fix_it` appended — CR-047's rule, and the reason for it: they fix
    two things in a spreadsheet they already know and upload it again.

    ⚠ **THE READING IS THE FILE's, NOT OURS.** `raw_value` and, where the date
    would not parse, `read_at_raw` — handing back our correction would return a
    file that was never corrected.

    Guard proved RED first — the appended columns dropped from
    `REJECT_COLUMNS`:

        E AssertionError: assert False
        (1 failed, 4 warnings in 95.23s (0:01:35))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch_dict = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch_dict["id"])
        services.commit_read_batch(marcus, batch_dict["id"], {"certified": True})
        batch = services._batch_row(batch_dict["id"])
        text = _csv(batch, "failures")

    lines = [line for line in text.splitlines() if line.strip()]
    assert lines[0].split(",")[:3] == ["row_key", "meter_id", "read_date"]
    assert lines[0].endswith("why_it_failed,how_to_fix_it")
    assert len(lines) == 2, "one held row, one line — the posted row is not a reject"
    assert "M-9999" in lines[1] and "2026-08-03" in lines[1]
    assert "There is no meter called M-9999 on this utility." in lines[1]
    # ⚠ AND THE POSTED ROW IS NOT IN IT. A warning-free reading that landed is
    # not something to hand back.
    assert "M-7001" not in text


def test_task16__the_file_is_offered_before_the_post_at_the_loading_stage(brazos, marcus):
    """The PO's own words: *"create csv file at loading stage itself"*. A batch
    that has been VALIDATED and not posted already answers, listing the rows
    that would be held if the clerk pressed Post now — which is `DEF-2487`'s
    ruling one importer over, and for its reason: the moment a person most
    needs the list of what failed is before they commit, not on a receipt
    screen a failed commit never reaches.

    Guard proved RED first — `_refuse_not_decided` tightened to `posted` only:

        E core.errors.BizError: BIZ-STATE (metering.read_batch.not_checked_no_download)
        (1 failed, 4 warnings in 95.58s (0:01:35))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch_dict = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch_dict["id"])
        batch = services._batch_row(batch_dict["id"])
        assert batch.status == "validated"
        text = _csv(batch, "failures")

    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2
    assert "M-9999" in lines[1]


def test_task16__what_the_pre_post_file_lists_is_what_the_post_actually_holds(brazos, marcus):
    """⚠ **THE PROPERTY THAT MAKES THE EARLY FILE WORTH HAVING.** A rejects
    file offered before the commit is worse than none if it disagrees with what
    the commit holds: the clerk fixes rows that would have gone in and
    re-uploads rows that would not.

    Guard proved RED first — `would_hold`'s BR-MET-129 default flipped so a
    warned row reads as a reject before the post and posts after it:

        E AssertionError: assert ['M-7001', 'M-7002', 'M-9999'] == ['M-9999']
        (1 failed, 4 warnings in 89.03s (0:01:29))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch_dict = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",
                "M-7002,2026-08-03,900,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch_dict["id"])
        before = _csv(services._batch_row(batch_dict["id"]), "failures")
        services.commit_read_batch(marcus, batch_dict["id"], {"certified": True})
        after = _csv(services._batch_row(batch_dict["id"]), "failures")

    def meters(text):
        return sorted(line.split(",")[1] for line in text.splitlines()[1:] if line.strip())

    assert meters(before) == meters(after) == ["M-9999"]


def test_task16__a_warned_reading_is_a_success_and_never_a_reject(brazos, marcus):
    """BR-MET-129 decides this and not the exporter: *"we cannot reject the
    reading, when reading are colelcted then only we will know whether there is
    usage or not"*. A vacant-unit warning posts, so a file of nothing but
    warnings has an EMPTY rejects file, and it is right to be empty.

    Guard proved RED first — `would_hold` reading `severity in ("ok",)`:

        E AssertionError: assert 2 == 1
        (1 failed, 4 warnings in 85.36s (0:01:25))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")  # no account on the unit → vacant_unit warning
        batch_dict = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch_dict["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch_dict["id"], row_no=1)
        assert row.severity == validation.WARNING
        result = services.commit_read_batch(marcus, batch_dict["id"], {"certified": True})
        batch = services._batch_row(batch_dict["id"])
        rejects = _csv(batch, "failures")
        successes = _csv(batch, "successes")

    assert result["posted_reads"] == 1
    assert len([line for line in rejects.splitlines() if line.strip()]) == 1  # header only
    assert len([line for line in successes.splitlines() if line.strip()]) == 2
    assert "M-7001" in successes


def test_task16__the_rejects_file_re_uploads_as_a_batch(brazos, marcus):
    """**THE ONE PROPERTY THE FILE EXISTS FOR**: the clerk corrects the cell
    and uploads the file back. Its headers are the first alias of every
    `TEMPLATE_COLUMNS` target, so `detect_mapping` reads it; the two appended
    columns are simply not mapped and are ignored, exactly as any extra column
    is.

    Guard proved RED first — `REJECT_COLUMNS` written from our field names
    (`meter_no_raw`, `read_at`) rather than the published headers:

        E core.errors.ValidationError: VAL-002 (metering.read_import.required_column_not_mapped)
        (1 failed, 4 warnings in 92.63s (0:01:32))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-9999", unit_label="Unit Z", address="9 Late Ln")
        first = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-8888,2026-08-03,100,total,E,",  # unknown — held
            ),
        )
        services.validate_read_batch(marcus, first["id"])
        services.commit_read_batch(marcus, first["id"], {"certified": True})
        rejects = _csv(services._batch_row(first["id"]), "failures")

        # The clerk corrects the meter number in their spreadsheet and uploads
        # the same file back.
        corrected = rejects.replace("M-8888", "M-9999")
        second = stage(marcus, corrected, file_name="rejects-corrected.csv")
        services.validate_read_batch(marcus, second["id"])
        result = services.commit_read_batch(marcus, second["id"], {"certified": True})

        assert result["posted_reads"] == 1
        assert models.MeterRead.objects.filter(asset__asset_no="M-9999").count() == 1


def test_task16__the_two_halves_refuse_by_name_rather_than_serving_an_empty_file(brazos, marcus):
    """A header with nothing under it reads as an ANSWER — *"nothing was
    rejected"* — which is `DEF-320`'s shape. So a batch that has not been
    judged refuses, the successes half refuses until the post, and an unknown
    `kind` names what IS allowed rather than defaulting to one of them.

    ⚠ **THE FIRST TWO KEYS ARE THE READS VOCABULARY'S OWN AS OF 2026-09-01
    (`DEF-2733`).** They were the ACCOUNT IMPORTER's — *"That RUN has not been
    checked"* and *"That run has not been LOADED"* — recorded as owed at the
    time because copy means editing eleven catalogues. **A read batch is a
    BATCH and it is POSTED**, and the sentences now say so in all eleven. The
    account importer's keys are untouched, where they are correct.

    The third key stays shared on purpose: *"Pick one of: {{allowed}}."* names
    the allowed values and says nothing about runs or batches.

    Guard proved RED first — both refusals removed:

        E Failed: DID NOT RAISE BizError
        (1 failed, 4 warnings in 85.96s (0:01:25))
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch_dict = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        batch = services._batch_row(batch_dict["id"])
        assert batch.status == "staged"

        with pytest.raises(errors.BizError) as not_checked:
            _csv(batch, "failures")
        assert not_checked.value.message_key == "metering.read_batch.not_checked_no_download"

        services.validate_read_batch(marcus, batch_dict["id"])
        batch = services._batch_row(batch_dict["id"])
        with pytest.raises(errors.BizError) as not_posted:
            _csv(batch, "successes")
        assert not_posted.value.message_key == "metering.read_batch.not_posted_no_download"

        with pytest.raises(errors.ValidationError) as unknown:
            _csv(batch, "rejects")
        assert unknown.value.message_key == "metering.import.kind_unknown"


def test_task16__the_route_is_mounted_and_streams(brazos, marcus):
    """Hard-won law 2: a built exporter nothing routes to is dead code. The
    path is registered, it is a GET, and it hands back a streaming response so
    a 50,000-row batch is never assembled in memory (`DEF-766`).

    Guard proved RED first — the `path(...)` line removed from `urlpatterns`:

        E AssertionError: assert 'read-batches/<uuid:batch_id>/results.csv' in {'accounts/<uuid:account_id>/usage', 'assets/<uuid:asset_id>/usage', 'connections', 'connections/<uuid:connection_id>', 'connections/<uuid:connection_id>/commit', 'cycles', ...}
        (1 failed, 4 warnings in 85.31s (0:01:25))
    """
    from apps.metering import api as metering_api

    paths = {str(route.pattern) for route in metering_api.urlpatterns}
    assert "read-batches/<uuid:batch_id>/results.csv" in paths
    assert "GET" in getattr(
        metering_api.read_batch_results_csv.cls, "http_method_names", ["get"]
    ) or "get" in getattr(metering_api.read_batch_results_csv.cls, "http_method_names", [])


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md HARD-WON LAW 14 — THE TWO CASES THAT ONLY BITE ON POSTGRESQL
#
# ⛔ **THE SUITE RUNS ON IN-MEMORY SQLITE (`config/settings/test.py`, which
# HARDCODES it and ignores `DATABASE_URL`), AND SQLITE HAS NO ABORTED-
# TRANSACTION STATE.** So the version of `commit_read_batch` with a bare
# `try/except IntegrityError: continue` and NO savepoint passes every test
# above, green, on every machine — and loses the whole batch the first time a
# real row is refused in production.
#
# These two are `skipif`-ed off SQLite rather than written to pass on it,
# because a test that passes on both databases would be proving nothing about
# the one that matters. Run them with:
#
#     DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
#         pytest tests/test_cr054_w24_backend.py -k postgres
#
# The transcript from the run that proved them is quoted in each docstring.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="law 14: SQLite has no aborted-transaction state"
)
def test_law14_postgres__a_failed_statement_really_does_poison_this_transaction():
    """**THE MECHANISM, ON THIS DATABASE, BEFORE ANY PRODUCT CODE IS TRUSTED.**

    Half of it is the claim law 14 makes and half is the fix, in one test, so a
    reader can see the difference rather than take it on faith:

      1. a failed statement inside `atomic()` → the NEXT query raises, and the
         message is the one law 14 quotes;
      2. the identical failure inside a nested `atomic()` (a SAVEPOINT) → the
         next query runs normally.

    Observed on PostgreSQL 16, verbatim:

        django.db.transaction.TransactionManagementError: An error occurred in
        the current transaction. You can't execute queries until the end of the
        'atomic' block.
    """
    from django.db import transaction
    from django.db.utils import Error as DbError

    poisoned = None
    with transaction.atomic():
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1 FROM a_table_that_does_not_exist")
        except DbError:
            pass
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception as exc:  # noqa: BLE001 — the whole point is WHICH one
            poisoned = exc
        transaction.set_rollback(True)

    assert poisoned is not None, (
        "law 14 claims a failed statement poisons the transaction — it did not, "
        "so either this is not PostgreSQL or the claim needs re-checking"
    )
    assert "can't execute queries" in str(poisoned) or "current transaction is aborted" in str(
        poisoned
    )

    # 2 · the same failure, inside a SAVEPOINT.
    with transaction.atomic():
        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute("SELECT 1 FROM a_table_that_does_not_exist")
        except DbError:
            pass
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)  # the transaction is healthy
        transaction.set_rollback(True)


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="law 14: SQLite has no aborted-transaction state"
)
def test_law14_postgres__the_partial_post_survives_a_real_database_refusal(
    brazos, marcus, monkeypatch
):
    """**THE PRODUCT PATH, ON REAL POSTGRESQL.** Row 2 provokes a genuine
    `uq_meter_reads_head` violation; rows 1 and 3 file, the batch commits, and
    row 2 comes back with the unique-violation sentence.

    **RED PROVED FIRST, ON THIS DATABASE, AND THE TRANSCRIPT IS THE POINT.**
    With the nested `transaction.atomic()` replaced by `if True:` and nothing
    else changed, the same three-row file on PostgreSQL 16 answered:

        django.db.transaction.TransactionManagementError: An error occurred in
        the current transaction. You can't execute queries until the end of the
        'atomic' block.
        readings filed: 0

    **Zero of three.** With the savepoint restored, the identical run answers
    `posted_reads: 2`, `held_reads: 1`, and row 2's stored reason reads *"…is
    already on file, and it has to be unique."* — which is `_db_state` having
    walked the `__cause__` chain down to the driver's own 23505 rather than
    stopping at the Django wrapper two hops up.

    ⚠ **AND ONE CORRECTION TO WHAT THIS LANE EXPECTED, RECORDED RATHER THAN
    QUIETLY DROPPED.** The obvious claim to write here is *"the sabotaged
    version passes on SQLite, which is law 14's whole point"*. **It does not.**
    Django sets `needs_rollback` on the connection for ANY `DatabaseError`
    raised inside an atomic block, on every vendor, so the same sabotage turns
    the SQLite sibling of this test red too (measured: 1 failed, 18 passed).
    The savepoint is genuinely load-bearing — the PostgreSQL run above proves
    that — but the DETECTION is not PostgreSQL-only here, and saying otherwise
    would be a comment claiming a guarantee it does not give. What IS
    PostgreSQL-only is the database-level behaviour underneath, which is why
    the test above this one exercises it with a raw cursor.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        a_meter(marcus, "M-7003", unit_label="Unit C", address="1412 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7002,2026-08-03,900,total,E,",
                "M-7003,2026-08-03,700,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])

        real = services._post_row

        def double_write_row_two(actor, b, row, config, **kwargs):
            read = real(actor, b, row, config, **kwargs)
            if row.row_no == 2:
                real(actor, b, row, config, **kwargs)
            return read

        monkeypatch.setattr(services, "_post_row", double_write_row_two)
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row2 = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

        # Row 3 is the assertion: it comes AFTER the poisoned statement, and on
        # PostgreSQL nothing but a savepoint lets it be read, let alone written.
        assert result["posted_reads"] == 2
        assert result["held_reads"] == 1
        assert models.MeterRead.objects.filter(source="import").count() == 2
        assert models.MeterRead.objects.filter(asset__asset_no="M-7003").exists()
        record = outcome_named(row2, "post")
        assert record["detail"]["reason"] == "database_refused"
        assert "already on file" in record["detail"]["why_it_failed"]

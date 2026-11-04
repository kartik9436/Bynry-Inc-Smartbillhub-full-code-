# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-016 (EP-MET-04 — the BILLED read and its J6 correction
#           linkage) · US-BIL-005 (issue)   Screens: S29 · S31 step 6
# Rules:    BR-MET-053 (a BILLED read is corrected ONLY through the correction
#           flow — read fix and money fix travel together) · BR-MET-016
#           (billing prices lineage heads) · BR-BIL-030 (what a bill priced is
#           frozen into the bill) · BR-BIL-055 (a break never blocks the run) ·
#           CLAUDE.md rule 1 · rule 4
# ───────────────────────────────────────────────────────
"""DEF-098 — the BILLED lock on a meter read, which nothing could reach.

`apps/metering/services.mark_read_billed` was published FOR BILLING TO CALL and
**nothing called it**. So a read that HAD been billed still read as `committed`,
a clerk correcting it took the PLAIN SUPERSEDE path, and **no correction linkage
was recorded** — precisely the failure US-MET-016 exists to prevent.

**THE DIAGNOSIS THAT MATTERS.** This was reported as *"one call in the issue
path"* and it was not. The read's identity is published by metering on every row
of `billing_reads_for_unit` and was DROPPED at billing's own contract boundary:
`ServiceReading` had no `read_id`, `runs._readings_for` did not copy it, the
string `read_id` appeared nowhere in `apps/billing/`, and `issue_invoice`
receives only the Invoice — so by issue time the identity was gone and could not
be recovered where the lock must be applied.

**THE TESTS ARE WRITTEN FROM THE CORRECTION'S SIDE, NOT THE LOCK'S.** Asserting
`lifecycle == "billed"` alone would pass the day `mark_read_billed` was written
and prove nothing about the defect. What the defect COST is that a billed read
could be quietly superseded with no money linkage, so that is what is driven:
the plain supersede path must now REFUSE, and the correction path must write the
`read_corrections` row J6 step 1 consumes.

RED-PROVED (law 7): with the `metering_seam.mark_reads_billed` call removed from
`issue_invoice`, the read stays `committed`, `supersede_read` SUCCEEDS on a read
that has been billed, and no `read_corrections` row exists. That success IS the
defect. Transcript in the lane report.
"""

from datetime import UTC, date, datetime

import pytest

from apps.billing import issue, metering_seam
from apps.billing import runs
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_bil_029_assemble import assemble

pytestmark = pytest.mark.django_db

ISSUED_AT = datetime(2026, 7, 3, 9, 41, tzinfo=UTC)


def a_dated_cycle(tenant, code):
    """A cycle carrying BR-MET-009's bill-date/due-days pair.

    `test_us_bil_001_prepare.a_cycle` builds one WITHOUT them, which is fine for
    a prepare test and fatal for an issue test: `derive_due_date` refuses rather
    than guessing a due date, and a guessed one decides when a late fee starts
    (BR-BIL-024). Each case gets its own code so two never collide on a shared
    `get_or_create`.
    """
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # W5-T2 — the ruled fields; `window_start`/`window_end` were dropped
        # columns (metering 0021) and the window is derived from these two.
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        # ⚠ OQ-344 (RC-W6): `cycles.bill_date` is dropped (metering 0023). The
        # surviving default is the bill DAY, and a run with no typed date
        # resolves *"the bill day, in the month after the period ends"*.
        bill_day=1,
        due_days=21,
    )


def a_run_on(tenant, cycle, key):
    """A bill run over THIS cycle — the one the service points are stamped with."""
    from apps.billing import models as billing_models

    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        idempotency_key=key,
    )


def a_real_billed_bill(brazos, dana, *, asset_no="M-7801", account_no="A-10801"):
    """A bill issued through the WHOLE chain, from a real committed meter read.

    Nothing is hand-built. The read is committed through metering's own service,
    `prepare_run` gathers it across four modules' real selectors, stages 1–5
    price it and stage 6 writes the draft — which is the only way this test can
    catch the contract dropping `read_id` anywhere along the way. A fixture that
    handed `ServiceReading(read_id=...)` straight to stage 6 would pass with
    `runs._readings_for` still throwing the id away, which is exactly where the
    defect lived.

    Returns `(read, invoice)`.
    """
    cycle = a_dated_cycle(brazos, code=f"06-{asset_no}")
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label="Unit A")
    account = an_account(brazos, unit["id"], account_no)

    prepared = runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )
    assert prepared.blocked == (), prepared.blocked
    data = prepared.ready[0]

    run = a_run_on(brazos, cycle, key=f"2026-06|{asset_no}")
    draft = assemble(brazos, account, run, data)
    invoice = issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
    )
    read = metering_models.MeterRead.objects.get(tenant=brazos, asset__asset_no=asset_no)
    read.refresh_from_db()
    return read, invoice


def test_def_098_tc1__the_reads_identity_survives_the_whole_pipeline(brazos, dana):
    """The contract change, asserted where it was broken.

    Four boundaries, each of which dropped it before: metering's row →
    `ServiceReading` → `MeasuredService` → the bill's frozen snapshot.
    """
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos, code="06-M-7802")
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7802", label="Unit A")
        account = an_account(brazos, unit["id"], "A-10802")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        data = prepared.ready[0]
        read = metering_models.MeterRead.objects.get(tenant=brazos, asset__asset_no="M-7802")

        # 1 + 2 — metering publishes it and billing's own contract now carries it.
        assert data.readings[0].read_id == str(read.id), (
            "`runs._readings_for` dropped this, and the row it read from has "
            "always carried it — that is the whole of DEF-098's first half"
        )

        # 3 + 4 — it survives stage 2 and is FROZEN into the bill (BR-BIL-030),
        # which is the only surface that reaches issue.
        draft = assemble(brazos, account, a_run_on(brazos, cycle, key="2026-06|M-7802"), data)
        assert metering_seam.read_ids_on(draft) == (str(read.id),)


def test_def_098_tc2__issue_applies_the_billed_lock(brazos, dana):
    """The call that did not exist. BR-MET-053's lock, applied at issue."""
    with tenant_ctx(brazos):
        read, invoice = a_real_billed_bill(brazos, dana, asset_no="M-7803", account_no="A-10803")

        assert read.lifecycle == "billed"
        assert invoice.reads.locked == 1
        assert invoice.reads.already_billed == 0
        assert invoice.reads.read_ids == (str(read.id),)
        assert invoice.reads.problems == (), invoice.reads.problems
        assert invoice.reads.ran is True


def test_def_098_tc3__the_plain_supersede_path_now_refuses(brazos, dana):
    """**THE DEFECT, STATED AS A TEST.**

    Before the fix this call SUCCEEDED — the read still read as `committed`, so
    BR-MET-053's service-layer lock never engaged, the read was quietly replaced
    and the money behind it was never touched. That success is the defect; the
    refusal is the fix.
    """
    with tenant_ctx(brazos):
        read, _ = a_real_billed_bill(brazos, dana, asset_no="M-7804", account_no="A-10804")

        with pytest.raises(errors.BizError) as refusal:
            metering_services.supersede_read(
                dana, read.id, {"value": "14300", "reason": "meter misread"}
            )
    assert refusal.value.code == errors.BIZ_LOCKED
    assert refusal.value.br_ref == "BR-MET-053"


def test_def_098_tc4__correcting_a_billed_read_writes_the_j6_linkage(brazos, dana):
    """The linkage US-MET-016 exists for, and which no bill could ever produce.

    `read_corrections` is the row J6 step 1 consumes: it names the read PAIR and
    the INVOICE, so the money fix has something to travel with. With the lock
    unreachable this row could not be written at all — `correct_billed_read`
    refuses a read that is not `billed`, and no read ever was.
    """
    with tenant_ctx(brazos):
        read, invoice = a_real_billed_bill(brazos, dana, asset_no="M-7805", account_no="A-10805")

        metering_services.correct_billed_read(
            dana,
            read.id,
            {"value": "14300", "reason": "meter misread", "invoice_id": str(invoice.pk)},
        )

        linkage = metering_models.ReadCorrection.objects.get(
            tenant=brazos, superseded_read_id=read.id
        )
        assert str(linkage.invoice_id) == str(invoice.pk)
        assert linkage.superseding_read_id is not None
        assert str(linkage.superseding_read_id) != str(read.id)
        # The original is closed and still fully readable (hard rule 4 shape).
        read.refresh_from_db()
        assert read.superseded_by_id is not None


def test_def_098_tc5__re_issuing_locks_nothing_twice(brazos, dana):
    """Hard rule 6's shape. `mark_read_billed` filters on `committed`, so a
    second pass answers False and the counters say so honestly — a replay that
    reported `locked: 1` would make a resumed release look like fresh work."""
    with tenant_ctx(brazos):
        read, invoice = a_real_billed_bill(brazos, dana, asset_no="M-7806", account_no="A-10806")
        assert invoice.reads.locked == 1

        # The seam called a second time on the SAME issued bill — the shape a
        # resumed batch reaches.
        again = metering_seam.mark_reads_billed(invoice)
        assert again.locked == 0
        assert again.already_billed == 1
        assert again.problems == ()
        read.refresh_from_db()
        assert read.lifecycle == "billed"


def test_def_098_tc6__a_bill_naming_no_read_says_so_rather_than_reporting_zero(brazos, dana):
    """An unwired seam REPORTS; it never answers a silent zero.

    A snapshot with no `read_id` is a real state — a base-only bill, a service
    with no meter, or a draft priced before DEF-098 was fixed — and the third is
    the one worth naming, because its reads are silently uncorrectable-by-the-
    right-path. A bare `locked: 0` cannot tell those apart from a bill that
    genuinely had nothing to lock.
    """
    from tests.test_us_bil_005_issue import a_priced_draft
    from tests.test_w3_billing_models import a_run as a_w3_run
    from tests.test_w3_billing_models import an_account as a_bare_account

    with tenant_ctx(brazos):
        account = a_bare_account(dana, brazos, account_no="A-10807")
        draft = a_priced_draft(brazos, account, a_w3_run(brazos, key="2026-06|no-reads"))
        outcome = metering_seam.mark_reads_billed(draft)

    assert outcome.locked == 0
    assert outcome.read_ids == ()
    assert {p["code"] for p in outcome.problems} == {"no_read_ids_on_bill"}
    assert outcome.ran is False, (
        "`ran` must be False here: the seam could not do its job, and a caller "
        "reading only `locked == 0` would conclude there was nothing to do"
    )


def test_def_098_tc7__the_lock_never_crosses_a_tenant_boundary(brazos, dana, lonestar):
    """Hard rule 1. `mark_read_billed` filters on `app.tenant_id`, so another
    utility's issue pass cannot lock this utility's read — it would make that
    read uncorrectable by its own owner, for a bill they cannot see."""
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos, code="06-M-7808")
        plan = a_priced_plan(brazos)
        a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7808", label="Unit A")
        read = metering_models.MeterRead.objects.get(tenant=brazos, asset__asset_no="M-7808")
        assert read.lifecycle == "committed"

    with tenant_ctx(lonestar):
        assert metering_services.mark_read_billed(read.id, None) is False

    with tenant_ctx(brazos):
        read.refresh_from_db()
        assert read.lifecycle == "committed"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-098 (defect fix — sources: 12-governance/10-defect-log.csv DEF-098 ·
#         04-docs/05-modules/05-metering/02-business-rules.md BR-MET-053/016 ·
#         04-docs/05-modules/05-metering/06-epics/EP-MET-04 US-MET-016 ·
#         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-030/055 ·
#         08-qa/01-e2e/journeys/J6-read-correction.md)
# generated: 2026-08-15 by the seams lane (DEF-098)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run on live PostgreSQL 16 (sbh_seams_lane, lane-private per DEF-054);
#         every case driven RED first by removing the issue-time seam call, and
#         tc3 failed by SUCCEEDING at the plain supersede, which IS the defect
# exceptions: the fixture drives the REAL chain (commit_read → prepare_run →
#         stages 1–6 → issue) rather than handing a ServiceReading to stage 6,
#         because the defect lived in `runs._readings_for` and a shortcut
#         fixture would have been green over it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

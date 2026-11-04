# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-6109 (no application could become a build, and the two
#          halves were inverted) · DEF-MET-6117 (the REASON given for the
#          refusal, measured false against the schema)
# Rules:   PO ruling 2026-09-21 — *"then approve applciation may create a new
#          conenct request - as draft request - this request is new work and
#          recognized seperately from applcaition and hence we should not make
#          it dependent on applciation #"* · BR-MET-1178 (`request_id` is
#          PROVENANCE, never a dependency) · BR-MET-112 (nothing is written
#          until the last button) · BR-MET-1024 · CLAUDE.md hard rule 1
#          (tenant scoping) · hard rule 8 (one address, on `premises`)
# Screens: S84 the request's approve modal · S87 the New Connect wizard
# Drawing: 05-prototype/02 Accounts Menu Blueprint.pdf p088–p089, read AS
#          IMAGES at scale 2.4 (B14 rule 42)
# ───────────────────────────────────────────────────────
"""**An approved application becomes a DRAFT BUILD, on both shapes of address.**

WHAT WAS BROKEN, AND THE TWO HALVES WERE OPPOSITES
--------------------------------------------------
Reproduced in a browser on 2026-09-21:

  * where the address HAD resolved (`SR-26-0005`, `SR-26-0008`) the approve
    modal **greyed** *"A new connection"* — *"A premise record already exists
    here."*;
  * where it had NOT (`SR-26-0004`, 14 Willow Bend) the option was offered and
    badged *fits the evidence*, and pressing **Approve and raise the build**
    moved the request to `approved` with outcome `new_connection` **and created
    no build at all**.

`service_request._verdict_for` said a new connection **fits when there is NO
premise record**; `request_jobs._raise_connection` **refused when there was no
resolved premises**. Exact opposites, so no request in the product could pass
both.

⛔ **AND THE REASON UNDER THE REFUSAL WAS FALSE — `DEF-MET-6117`.** It read
*"creating the premise here would need the mandatory owner `BR-MET-1010`
requires and the application does not carry"*. `premises.owner_id` is NULLABLE,
the owner refusal on a premises create was itself reversed on 2026-08-27
(`DEF-650`), and `metering/services.py::create_premises` opens the owner's
master account LAST in its own savepoint — *"a refused account leaves the
address standing"*. **The PO is who asked for the measurement.**

WHAT WOULD MAKE THESE CASES PASS WRONGLY (CLAUDE.md law 7, habit 2)
-------------------------------------------------------------------
* **Asserting `outcome_ref` is non-empty.** It would pass on a draft pointing
  at the WRONG build, and on a build raised for a different request entirely.
  So every case reads the `connections` row back and compares its number.
* **Asserting only that a build exists.** It would pass over a build that had
  quietly created a property at approval — which is precisely what `BR-MET-112`
  forbids and what the unresolved case is for. So the premises COUNT is taken
  before and after.
* **Asserting the manifest.** A dict the service returns is not the database;
  every count below is a query.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import request_jobs
from apps.customers import service_request as rules
from apps.customers import service_request_service as sr
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


CAPTURE = {
    "channel": "counter",
    "applicant_kind": "person",
    "applicant_name": "Willow, Ada",
    "applicant_email": "ada@example.test",
    "applicant_phone": "512-555-0199",
    "address_as_given": "14 Willow Bend",
    "property_type": "standalone_owner_occupied",
    "plot_or_parcel": "R-77012",
    "units_on_property": 1,
    "what_they_said": "A new house on an empty plot",
}


def _approved_request(actor, *, premises_id=None):
    """A request walked to the moment the drawn modal opens on it, with its
    outcome already `new_connection`.

    The document gate is CLEARED rather than skipped — `_request_ready_to_approve`
    in `test_cr094_approval_raises_the_job.py` does the same and for the same
    reason: a case that walks round the real gate proves nothing about the real
    path.
    """
    request = sr.create_request(actor, dict(CAPTURE))
    doc = sr.attach_document(
        actor,
        request.id,
        doc_type=customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY,
        name="driving-licence.pdf",
        storage_ref="s3://id",
    )
    sr.submit(actor, request.id)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None, tier=None)
    sr.decide_outcome(actor, request.id, outcome="new_connection")
    sr.verify_document(actor, doc.id)
    if premises_id is not None:
        customers_models.ServiceRequest.objects.filter(pk=request.id).update(
            resolved_premises_id=premises_id, resolution_kind="exact"
        )
    return sr.request_row(request.id)


def _wizard_plan(connection_id, **over):
    """**The payload `commitPlanOf` emits when the wizard was opened on a
    raised draft** — the browser's spelling, not the service's signature.

    `test_def_met_5441_the_commit_door.py` copies the same shape for the
    directly-raised path; the only difference is `connection_id`, which is the
    whole of what this defect added to the wire.
    """
    plan = {
        "premises": {
            "id": None,
            "address": "14 Willow Bend",
            "premise_type": None,
            "parcel_ref": "R-77012",
            "read_route": None,
            "services_available": ["electric"],
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Apt",
        "target_activation": None,
        "service_request_id": None,
        "connection_id": connection_id,
        "units": [{"label": "Apt 1", "is_common_area": False}],
        "meters": [],
        "plan_assignments": [],
        "create_owner_account": False,
        "owner": {},
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
    }
    plan.update(over)
    return plan


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE INVERSION — THE VERDICT AND THE RAISER NOW AGREE
# ════════════════════════════════════════════════════════════════════════════
def test_a_new_connection_is_offered_whether_or_not_the_address_resolved():
    """**Blueprint p089 draws it LIVE on an address matched EXACTLY.**

    Read as an image at scale 2.4 (`B14` rule 42). `SR-26-0001`'s own detail on
    p088 reads `Matched premises · PR-0731 · exact` and `Matched unit ·
    U-001884 · exact`, and the approve modal on p089 draws **`A new connection`
    selected and enabled**, over the callout *"Nothing is preselected,
    deliberately. The resolver matched this address to PR-0731 exactly, and
    that is EVIDENCE — not the decision."*

    ⚠ **`possible` AND NOT `fits_the_evidence`.** No screen draws that badge for
    a matched address, and awarding one would be this module authoring the rule
    `OQ-356` exists to ask for — the header of `service_request.py` refuses that
    in as many words.
    """
    matched = rules.Evidence(premise_exists=True, resolution_kind="exact")
    assert rules.verdict_for("new_connection", matched) == rules.POSSIBLE

    unmatched = rules.Evidence(
        premise_exists=False, resolution_kind=customers_models.ServiceRequest.RESOLUTION_NO_PREMISE
    )
    assert rules.verdict_for("new_connection", unmatched) == rules.FITS_THE_EVIDENCE


def test_no_blocker_is_printed_over_an_address_that_has_not_resolved(brazos, dana):
    """The modal used to warn *"Resolve the address, or create the premise,
    then approve."* before the clerk pressed anything. There is nothing to warn
    about now — the press raises a draft."""
    with tenant_ctx(brazos):
        request = _approved_request(dana)
        assert request.resolved_premises_id is None
        preview = request_jobs.approval_preview(request, "new_connection")
        assert preview["creates"]["blockers"] == []


# ════════════════════════════════════════════════════════════════════════════
# 2 · SHAPE ONE — THE ADDRESS HAS NOT RESOLVED
# ════════════════════════════════════════════════════════════════════════════
def test_an_unresolved_address_raises_a_draft_and_writes_no_property(brazos, dana):
    """**A build, a link back, and NO premises — `BR-MET-112`.**"""
    with tenant_ctx(brazos):
        request = _approved_request(dana)
        before = metering_models.Premises.objects.count()

        out = sr.approve_and_raise(dana, request.id)

        assert "not_raised" not in out["job"]
        build = work_tables.Connection.objects.get(service_request_id=request.id)
        assert build.state == "draft"
        assert build.premises_id is None
        request.refresh_from_db()
        # The request names THIS build — not merely something.
        assert request.outcome_ref == build.connection_no
        # ⛔ And nothing was written for it.
        assert metering_models.Premises.objects.count() == before


def test_the_wizard_s_last_button_creates_the_address_and_finishes_that_draft(brazos, dana):
    """**The whole point: the draft becomes a real build, and no SECOND build
    is made beside it.**

    ⚠ **THE COUNT OF `connections` IS THE ASSERTION THAT MATTERS.** A commit
    that ignored `connection_id` and created its own row would satisfy every
    other line here — the address would exist, the units would exist, the
    manifest would read `premises: 1` — and the clerk would be left with an
    abandoned draft on the New connects tab for ever.
    """
    with tenant_ctx(brazos):
        request = _approved_request(dana)
        sr.approve_and_raise(dana, request.id)
        draft = work_tables.Connection.objects.get(service_request_id=request.id)
        builds_before = work_tables.Connection.objects.count()
        premises_before = metering_models.Premises.objects.count()

        built = w6.commit_new_connect(dana, _wizard_plan(str(draft.id)))

        assert built["id"] == str(draft.id), "the press must FINISH the draft it was opened on"
        assert work_tables.Connection.objects.count() == builds_before, "no second build"
        assert metering_models.Premises.objects.count() == premises_before + 1
        draft.refresh_from_db()
        assert draft.premises_id is not None
        assert draft.state != "draft", "the commit submits the build it finished"
        premises = metering_models.Premises.objects.get(pk=draft.premises_id)
        assert premises.address_line == "14 Willow Bend"
        assert metering_models.Unit.objects.filter(premises_id=premises.id).count() == 1
        assert built["premises_created"] is True
        assert built["manifest"]["premises"] == 1
        # ⛔ **PROVENANCE SURVIVES THE COMMIT.** `BR-MET-1178`: the build carries
        # the application and is not owned by it.
        assert str(draft.service_request_id) == str(request.id)


def test_a_submitted_build_may_not_have_no_address(brazos, dana):
    """**The guarantee MOVED, it did not go** —
    `ck_connections_premises_once_submitted` (`metering/0059`).

    Dropping `NOT NULL` alone would have let a build with units, meters and an
    owner account exist with no address at all, which is worse than the fault
    being fixed. ⚠ **It is keyed on `submitted_at` and never on `state`**: the
    state column is a cache `refresh_connection_state()` rewrites and a cancel
    outranks, so a constraint on it could be defeated by cancelling.

    ⚠ **THIS RUNS ON POSTGRESQL ONLY** (CLAUDE.md law 14's other edge): the
    default suite is in-memory SQLite, which does enforce CHECK constraints but
    whose failure class differs, so the assertion is on `IntegrityError` rather
    than on a SQLSTATE.
    """
    from django.db import IntegrityError, transaction
    from django.utils import timezone

    with tenant_ctx(brazos):
        request = _approved_request(dana)
        sr.approve_and_raise(dana, request.id)
        draft = work_tables.Connection.objects.get(service_request_id=request.id)
        with pytest.raises(IntegrityError):
            # A SAVEPOINT, because on PostgreSQL the refused statement poisons
            # the whole transaction and every later query in this test would
            # raise `InFailedSqlTransaction` (CLAUDE.md hard-won law 14).
            with transaction.atomic():
                work_tables.Connection.objects.filter(pk=draft.pk).update(submitted_at=timezone.now())


# ════════════════════════════════════════════════════════════════════════════
# 3 · SHAPE TWO — THE ADDRESS HAS RESOLVED
#
# ⛔ SUPERSEDED 2026-09-23 AS AN APPLICATION PATH (`DEF-CUS-6350`, PO ruling
# `OQ-CUS-12615`): *"we should allow only if address is not available in
# register"*. An application whose address is in Premises — in ANY status — is
# refused as a new connection at Approve and is a move-in instead. The first
# case below is FLIPPED to assert that. The other two are about the WIZARD's
# commit on a draft that already names a property, which metering's door still
# makes and live drafts from before today still are; they now raise that draft
# through the metering door directly rather than through an approval that no
# longer allows it.
# ════════════════════════════════════════════════════════════════════════════
def test_a_resolved_address_is_refused_as_a_new_connection_and_raises_nothing(brazos, dana):
    """⛔ **FLIPPED 2026-09-23.** This case was `test_a_resolved_address_raises
    _a_draft_against_the_property_on_file`; its name stated the superseded rule,
    so it is rewritten rather than re-pointed.

    The press is refused naming the PROPERTY (never an id), no build names the
    request, and no second property appears (hard rule 8)."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="14 Willow Bend", services_available=["electric"]
        )
        request = _approved_request(dana, premises_id=premises["id"])
        before = metering_models.Premises.objects.count()

        with pytest.raises(errors.BizError) as caught:
            sr.approve_and_raise(dana, request.id)

        assert caught.value.message_key == "customers.serviceRequest.condition.addressInPremises"
        assert "14 Willow Bend" in str(caught.value.params["property"])
        assert not work_tables.Connection.objects.filter(service_request_id=request.id).exists()
        assert metering_models.Premises.objects.count() == before


def _draft_on_file(actor, request, premises_id):
    """A draft build that already names a property, raised through metering's
    own door — the seam `request_jobs._raise_connection` calls. Since
    2026-09-23 an approval no longer reaches it with a property, and the
    wizard's handling of such a draft is still metering's to prove."""
    from apps.customers import seams

    made = seams.raise_connection_build(
        actor,
        premises_id=str(premises_id),
        service_request_id=str(request.id),
        target_activation=None,
    )
    assert made is not None, "the metering door is unwired in this deployment"
    return work_tables.Connection.objects.get(pk=made["id"])


def test_finishing_that_draft_makes_no_second_property(brazos, dana):
    """The commit on the resolved shape creates NOTHING at the address."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="14 Willow Bend", services_available=["electric"]
        )
        request = _approved_request(dana, premises_id=premises["id"])
        draft = _draft_on_file(dana, request, premises["id"])
        before = metering_models.Premises.objects.count()

        built = w6.commit_new_connect(
            dana,
            _wizard_plan(
                str(draft.id),
                premises={"id": str(premises["id"])},
                scope="new_units",
            ),
        )

        assert built["id"] == str(draft.id)
        assert metering_models.Premises.objects.count() == before
        assert built["premises_created"] is False
        assert built["manifest"]["premises"] == 0


def test_naming_a_different_address_on_a_draft_that_has_one_is_refused_by_name(brazos, dana):
    """*Build on THIS address* and *build on that one* are different
    intentions, and a door that quietly preferred one would sometimes move a
    build to a property the clerk never chose. `create_connection`'s *named
    twice* reasoning, one step later."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="14 Willow Bend", services_available=["electric"]
        )
        other = make_premises(dana, address_line="9 Ridgeline Way", services_available=["electric"])
        request = _approved_request(dana, premises_id=premises["id"])
        draft = _draft_on_file(dana, request, premises["id"])

        with pytest.raises(errors.ValidationError) as caught:
            w6.commit_new_connect(
                dana, _wizard_plan(str(draft.id), premises={"id": str(other["id"])})
            )
        assert "premises_named_twice" in str(caught.value.__dict__)


# ════════════════════════════════════════════════════════════════════════════
# 4 · A BUILD RAISED DIRECTLY IS UNTOUCHED — THE RULING'S OTHER HALF
# ════════════════════════════════════════════════════════════════════════════
def test_a_build_with_no_application_still_creates_its_own_row_and_address(brazos, dana):
    """⛔ **`request_id` IS PROVENANCE, NEVER A DEPENDENCY** (`BR-MET-1178`,
    PO 2026-09-21: *"we should not make it dependent on applciation #"*).

    A clerk who opens `/connections/new` with no `?build=` sends
    `connection_id: null` and gets exactly what they always got. This case is
    here because the RULING is about this path as much as the other one, and a
    change that only worked from an application would have satisfied the defect
    and broken the rule.
    """
    with tenant_ctx(brazos):
        premises_before = metering_models.Premises.objects.count()
        built = w6.commit_new_connect(dana, _wizard_plan(None))
        connection = work_tables.Connection.objects.get(pk=built["id"])
        assert connection.service_request_id is None
        assert connection.premises_id is not None
        assert metering_models.Premises.objects.count() == premises_before + 1

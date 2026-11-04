# ── Trace ──────────────────────────────────────────────
# Change:   CR-035 step 6 parts 2-3 — the service and the API behind Park.
# Rules:    BR-SHL-048 (a parked wizard changes NOTHING until it is executed —
#           PO 2026-08-26, verbatim "Option A - Unitl move in executed, no
#           records updates") and its three consequences: (a) no FK to the
#           record it describes · (b) re-validated at execution, never trusted
#           from the park · (c) a draft is discardable · BR-SHL-047 · B19 §12.2
#           · BR-SHL-025 · BR-AUD-006 (PII masked only) · CLAUDE.md rules 1 · 7
# Defect:   DEF-746 — the control is inert on five of six wizards.
# ───────────────────────────────────────────────────────
"""CR-035's park store, proved through the wire.

⚠ **EVERY CASE HERE CROSSES `config/urls.py`**, the way
`test_us_shl_013_user_preferences.py` does and for the same reason: DEF-647 and
DEF-746 are both *built is not wired*, and a service-level test would have
passed on a tree where no route existed. The five verbs are called as a client
calls them.

THE THREE CONSEQUENCES ARE ASSERTED AS THEMSELVES, not as side effects:
  (a) `test_..._no_foreign_key_...` reads the model's own field list, and
      `test_..._parks_a_unit_that_does_not_exist` proves nothing is resolved;
  (b) `test_..._does_not_validate_the_contents_of_values` parks a draft full of
      values that would be refused at execution;
  (c) `test_..._discard_really_deletes` — a form is not a financial record.

And the ruling's own sentence — *"no records updates"* — is asserted by
`test_..._writes_exactly_one_row_in_the_whole_database`, which counts every
table before and after. That one is the rule; the rest are its consequences.
"""

import uuid

import pytest
from django.db import connection

from apps.tenancy.models import WizardPark
from apps.tenancy.wizard_parks import JSON_MAX_BYTES, WAITING_ON_MAX_CHARS
from tests.isolation_helpers import (  # noqa: F401 (fixture import)
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_delete,
    api_get,
    api_patch,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

PARKS = "/wizard-parks"

#: The worked case the Product Owner ruled on, 2026-08-26 — a clerk starts a
#: move-in for Unit 12, 500 Main St on 26 August, stops at step 3 waiting on a
#: $150 deposit, and comes back on 2 September. Every fixture below is that
#: case, so a reader of a failure sees the ruling rather than `foo`/`bar`.
UNIT_12 = str(uuid.uuid4())
DEPOSIT_PARK = {
    "flow": "move_in",
    "subject_label": "Unit 12, 500 Main St",
    "subject_ref": {"unit_id": UNIT_12, "premises_id": str(uuid.uuid4())},
    "step": 3,
    "values": {
        "applicant_name": "Rosa Delgado",
        "applicant_email": "rosa.delgado@example.com",
        "applicant_phone": "555-0142",
        "deposit_amount": "150.0000",
    },
    "waiting_on": "Waiting on a deposit",
    "park_note": "$150 deposit promised by Friday.",
    "remind_on": "2026-09-02",
}


def _clerk():
    """Priya, Billing Clerk — the person CR-035 was raised for."""
    return signed_in_client("priya@silvercreek.example", "Meadow2026sage")


def _admin():
    return signed_in_client("alex@silvercreek.example", "Canyon2026rapids")


def _executive():
    return signed_in_client("diana@silvercreek.example", "Vista2026peak")


def _park(client=None, **overrides):
    body = dict(DEPOSIT_PARK)
    body.update(overrides)
    return api_post(client or _clerk(), PARKS, body)


def _table_counts() -> dict[str, int]:
    """Every row of every table in the database, by table.

    Vendor-agnostic on purpose (the default tier is sqlite, the isolation tier
    is Postgres) — this is the measurement BR-SHL-048 is stated in.
    """
    counts = {}
    with connection.cursor() as cursor:
        for table in sorted(connection.introspection.table_names(cursor)):
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608 (introspected name)
            counts[table] = cursor.fetchone()[0]
    return counts


# ══════════════════════════════════════════════════════════════════════════
# THE RULING ITSELF — "Unitl move in executed, no records updates"
# ══════════════════════════════════════════════════════════════════════════
def test_cr035__parking_writes_exactly_one_row_in_the_whole_database(idn):
    """**BR-SHL-048, asserted as the sentence the PO said.**

    *"Option A - Unitl move in executed, no records updates."* A clerk parks a
    move-in for Unit 12 on 26 August and comes back on 2 September; in between
    **Unit 12 reads Vacant, no account exists, no occupancy begins, no bill
    changes.** The honest way to prove that is not to name the three tables a
    reader thinks of — it is to count EVERY table in the database and show that
    exactly one row appeared, in `wizard_parks`.

    ⚠ This case is why a future convenience cannot quietly undo the ruling. A
    lane that made `park()` "helpfully" reserve the unit, open a draft account
    or file a service request would break this and nothing else.
    """
    idn.seed_silvercreek()
    # ⚠ SIGN IN FIRST. Signing in writes a `sessions` row, and the first draft
    # of this case counted it as a park side effect — the assertion is sharp
    # enough to catch a row the act did not cause, which is the point of it.
    clerk = _clerk()
    before = _table_counts()

    assert _park(clerk).status_code == 201

    after = _table_counts()
    grew = {t: (before.get(t, 0), n) for t, n in after.items() if n != before.get(t, 0)}
    assert set(grew) == {"wizard_parks"}, f"parking touched more than the draft store: {grew}"
    assert grew["wizard_parks"] == (0, 1)


def test_cr035_consequence_a__the_table_has_no_foreign_key_to_what_it_describes(idn):
    """**BR-SHL-048 (a)** — *"Only `tenant_id` and the parking user are real FKs."*

    An FK is a RELATIONSHIP and the ruling says there is none until execution.
    Read off the model rather than the migration, because the model is what a
    later lane would edit: adding `unit = ForeignKey(...)` here would make a
    forgotten draft able to block a unit deletion, and would let a report reach
    a draft by joining to it. Both are the mechanism the ruling removes.
    """
    fks = {f.name for f in WizardPark._meta.get_fields() if getattr(f, "many_to_one", False)}
    assert fks == {"tenant", "parked_by"}, f"a draft grew a relationship it must not have: {fks}"


def test_cr035_consequence_a__parks_a_unit_that_does_not_exist(idn):
    """The same rule from the other side: nothing in `subject_ref` is resolved.

    `unit_id` here is a UUID no row anywhere carries. The park succeeds and
    hands the id straight back, because these are COPIED VALUES — a lookup at
    park time would re-create the relationship the schema was shaped to refuse,
    and would start failing the day a clerk parked against a unit somebody else
    deleted.
    """
    idn.seed_silvercreek()
    response = _park()
    assert response.status_code == 201
    assert response.json()["subject_ref"]["unit_id"] == UNIT_12
    assert WizardPark.objects.count() == 1


def test_cr035_consequence_b__does_not_validate_the_contents_of_values(idn):
    """**BR-SHL-048 (b)** — re-validated at execution, never trusted from the park.

    Everything in this draft would be refused by the move-in wizard: an email
    with no `@`, a negative deposit, a service the tenant does not sell, a date
    in the wrong century. It parks anyway, and that is correct — what was true
    on 26 August may be false on 2 September, so the wizard re-runs every check
    on resume and a second copy of those checks here would be a staler copy
    free to disagree with the first.
    """
    idn.seed_silvercreek()
    response = _park(
        values={
            "applicant_email": "not-an-email",
            "deposit_amount": "-9999.0000",
            "service": "antimatter",
            "move_in_date": "1899-02-30",
        }
    )
    assert response.status_code == 201
    assert response.json()["values"]["deposit_amount"] == "-9999.0000"


def test_cr035_consequence_c__discard_really_deletes(idn):
    """**BR-SHL-048 (c)** — a draft of a form is not a financial record.

    CLAUDE.md rule 4 makes issued invoices, invoice lines, payments and journal
    entries immutable; a half-typed move-in has moved no money and posted
    nothing. So DELETE is a DELETE, the row goes, and a second read is a 404 —
    which is also what makes an erasure request answerable for the PII a parked
    move-in holds before any customer row exists.
    """
    idn.seed_silvercreek()
    park_id = _park().json()["id"]

    assert api_delete(_clerk(), f"{PARKS}/{park_id}").status_code == 204
    assert WizardPark.objects.filter(id=park_id).count() == 0
    assert api_get(_clerk(), f"{PARKS}/{park_id}").status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# THE ROUND TRIP — park, list, resume, patch (the wizard's own cycle)
# ══════════════════════════════════════════════════════════════════════════
def test_cr035__park_returns_the_row_it_wrote(idn):
    idn.seed_silvercreek()
    body = _park().json()
    assert body["flow"] == "move_in"
    assert body["step"] == 3
    assert body["subject_label"] == "Unit 12, 500 Main St"
    assert body["waiting_on"] == "Waiting on a deposit"
    assert body["park_note"] == "$150 deposit promised by Friday."
    assert body["remind_on"] == "2026-09-02"
    assert body["age_days"] == 0
    assert body["parked_at"] is not None
    # The "Waiting on" list says WHO is waiting, by name — an internal uuid on
    # a utility's screen is noise to them and a leak to us (G28). `parked_by`
    # is one of the two real FKs BR-SHL-048 (a) allows, so the join is lawful.
    assert body["parked_by_name"] == "Priya Menon"


def test_cr035__resume_hands_back_what_was_typed_and_the_step(idn):
    """The resume read — CR-035 step 6 part 4 rehydrates from exactly this.

    `values` comes back VERBATIM. Anything this service reshaped on the way out
    would have to be un-reshaped on the way back in, and the wizard lands on
    step 3 because BR-SHL-046 makes the step an index into one declared list.
    """
    idn.seed_silvercreek()
    park_id = _park().json()["id"]
    body = api_get(_clerk(), f"{PARKS}/{park_id}").json()
    assert body["values"] == DEPOSIT_PARK["values"]
    assert body["step"] == 3


def test_cr035__list_is_newest_first_and_every_row_carries_an_age(idn):
    """The "Waiting on" list.

    ⚠ **`age_days` IS LOAD-BEARING, NOT DECORATION.** BR-SHL-048 accepts that a
    parked move-out is invisible to the rest of the product, and says the
    reminder date and the visible age *"are the only thing stopping a draft
    sitting forever"*. A list that dropped it would remove the ruling's own
    mitigation.
    """
    idn.seed_silvercreek()
    first = _park().json()["id"]
    second = _park(flow="move_out", subject_label="Unit 4, 12 Cedar Ave").json()["id"]

    body = api_get(_clerk(), PARKS).json()
    assert [row["id"] for row in body["results"]] == [second, first]
    assert all(row["age_days"] == 0 for row in body["results"])
    assert body["count"] == 2


def test_cr035__list_filters_by_flow_and_by_mine(idn):
    """`?flow=` is the tab; `?mine=` is a FILTER and not a boundary.

    Alex and Priya share a tenant and either may pick up the other's draft —
    there are one to two staff, and a `mine` that hid a colleague's work would
    strand a draft the day its author took leave, which is the working pattern
    CR-035 exists to serve. The boundary is `tenant_id`.
    """
    idn.seed_silvercreek()
    priyas = _park().json()["id"]
    alexs = _park(_admin(), flow="disconnect").json()["id"]

    assert [r["id"] for r in api_get(_clerk(), f"{PARKS}?flow=move_in").json()["results"]] == [
        priyas
    ]
    assert [r["id"] for r in api_get(_clerk(), f"{PARKS}?mine=1").json()["results"]] == [priyas]
    # Not a boundary: Priya still SEES Alex's, she just filtered it out above.
    assert alexs in {r["id"] for r in api_get(_clerk(), PARKS).json()["results"]}


def test_cr035__patch_saves_more_of_the_form(idn):
    idn.seed_silvercreek()
    park_id = _park().json()["id"]
    body = api_patch(
        _clerk(),
        f"{PARKS}/{park_id}",
        {
            "step": 5,
            "values": {"applicant_name": "Rosa Delgado", "deposit_amount": "150.0000"},
            "waiting_on": "Waiting on the customer",
            "park_note": None,
            "remind_on": None,
        },
    ).json()
    assert body["step"] == 5
    assert body["waiting_on"] == "Waiting on the customer"
    assert body["park_note"] is None
    assert body["remind_on"] is None
    assert "applicant_email" not in body["values"]


def test_cr035__patch_cannot_change_the_flow_or_the_subject(idn):
    """A draft that changed which flow it was, or which unit it named, would be
    a different draft wearing the same id — and the "Waiting on" list would
    silently rewrite its own history. Park a new one; discarding is free."""
    idn.seed_silvercreek()
    park_id = _park().json()["id"]
    body = api_patch(
        _clerk(),
        f"{PARKS}/{park_id}",
        {"flow": "disconnect", "subject_ref": {"unit_id": str(uuid.uuid4())}, "step": 4},
    ).json()
    assert body["flow"] == "move_in"
    assert body["subject_ref"]["unit_id"] == UNIT_12
    assert body["step"] == 4  # the one field that WAS asked for did move


# ══════════════════════════════════════════════════════════════════════════
# THE ENVELOPE — and ONLY the envelope
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"flow": ""}, "VAL-001"),
        ({"flow": "move_sideways"}, "VAL-005"),
        ({"step": 0}, "VAL-003"),
        ({"step": "three"}, "VAL-002"),
        # ⚠ **`{"waiting_on": ""}` AND `{"waiting_on": "   "}` WERE HERE AS
        # `VAL-001` AND ARE GONE (`CR-122-BRC06`, PO ruling 2026-09-19).** An
        # empty reason is no longer a refusal: it is the DRAFT state, written
        # by `Save & exit`, which used to write no row at all and so lost a
        # clerk five steps of typing and a $150.00 deposit. The two cases did
        # not simply move to "allowed" — they are now asserted as a BEHAVIOUR
        # in `test_cr122__a_draft_has_no_reason_and_keeps_the_typing` below,
        # because a rule that reversed deserves a test that states the new rule
        # rather than a hole where the old one was.
        ({"values": ["not", "an", "object"]}, "VAL-002"),
        ({"subject_ref": "unit-12"}, "VAL-002"),
        ({"remind_on": "02/09/2026"}, "VAL-002"),
    ],
)
def test_cr035__envelope_refusals_are_catalog_codes(idn, overrides, code):
    """The boundary this service draws, case by case.

    `flow` is one of five (the schema's own check, turned into a 422 a clerk can
    read rather than an IntegrityError that reads like an outage), a step
    indexes something, a park states what it is waiting for — B19 §12.2 gives
    the clerk `Save & exit` for leaving quietly, so a row with no reason is a
    park that forgot the only thing it is for.
    """
    idn.seed_silvercreek()
    response = _park(**overrides)
    assert response.status_code == 422
    assert response.json()["code"] == code
    assert WizardPark.objects.count() == 0


def test_cr035__an_oversized_draft_is_capped_not_stored(idn):
    idn.seed_silvercreek()
    response = _park(values={"note": "x" * (JSON_MAX_BYTES + 1)})
    assert response.status_code == 422
    assert response.json()["code"] == "BIZ-CAP"
    assert WizardPark.objects.count() == 0


def test_cr035__waiting_on_is_free_text_and_is_not_a_closed_vocabulary(idn):
    """⚠ **DELIBERATE, AND IT MATCHES `customers.ServiceRequest.waiting_on`.**

    The nine reasons are what the SCREEN offers; the column stores what was
    chosen. Service requests — the one flow where parking already worked — got
    there first, and one "Waiting on" list cannot carry two contracts for one
    column. So a tenth reason nobody has drawn yet parks fine, and is truncated
    at the same 120 characters the older column uses.
    """
    idn.seed_silvercreek()
    body = _park(waiting_on="Waiting on the county to re-survey the easement").json()
    assert body["waiting_on"] == "Waiting on the county to re-survey the easement"

    long_one = _park(waiting_on="W" * (WAITING_ON_MAX_CHARS + 40)).json()
    assert len(long_one["waiting_on"]) == WAITING_ON_MAX_CHARS


def test_cr035__a_reminder_already_past_is_accepted(idn):
    """A reminder that has come round is exactly the draft a clerk most needs to
    see. Refusing one would be a rule nobody made — the same reasoning that
    keeps a park from expiring after N days."""
    idn.seed_silvercreek()
    assert _park(remind_on="2020-01-01").json()["remind_on"] == "2020-01-01"


def test_cr035__a_park_id_that_is_not_a_uuid_is_a_404_not_a_500(idn):
    """`<str:park_id>` accepts any segment, so this is reachable from a stale
    bookmark or a typed URL. Django raises on a value the UUID column cannot
    hold, BEFORE any query runs, and the BE-02 handler does not map that — it
    would render as a 500 that reads like an outage. An id that names no row is
    a 404 (HR-1), the same answer a foreign tenant's id gets."""
    idn.seed_silvercreek()
    clerk = _clerk()
    assert api_get(clerk, f"{PARKS}/not-a-uuid").status_code == 404
    assert api_patch(clerk, f"{PARKS}/not-a-uuid", {"step": 2}).status_code == 404
    assert api_delete(clerk, f"{PARKS}/not-a-uuid").status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# RULE 7 — every action is on the record, and NO PII IS
# ══════════════════════════════════════════════════════════════════════════
def test_cr035__park_resume_update_and_discard_are_all_audited(idn):
    idn.seed_silvercreek()
    park_id = _park().json()["id"]
    api_get(_clerk(), f"{PARKS}/{park_id}")
    api_patch(_clerk(), f"{PARKS}/{park_id}", {"step": 4})
    api_delete(_clerk(), f"{PARKS}/{park_id}")

    assert [a for a in idn.actions() if a.startswith("wizard_park.")] == [
        "wizard_park.parked",
        "wizard_park.resumed",
        "wizard_park.updated",
        "wizard_park.discarded",
    ]
    discarded = idn.rows_for("wizard_park.discarded")[0]
    # The trail survives the row — audit_log is append-only (BR-AUD-002), so
    # what was discarded, by whom and when is still on the record afterwards.
    assert discarded["before"]["waiting_on"] == "Waiting on a deposit"


def test_cr035__no_applicant_pii_reaches_an_audit_payload(idn):
    """**BR-AUD-006** — PII enters a payload MASKED only, and nothing here masks.

    A parked move-in carries the incoming occupant's name, email and phone
    while there is no customer row to attach them to, and `subject_label` is a
    street address. So the trail records the ENVELOPE and a field COUNT: enough
    to answer *who parked what and when*, never enough to reconstruct anybody's
    contact details from a second table.
    """
    idn.seed_silvercreek()
    park_id = _park().json()["id"]
    api_get(_clerk(), f"{PARKS}/{park_id}")
    api_patch(_clerk(), f"{PARKS}/{park_id}", {"step": 4})
    api_delete(_clerk(), f"{PARKS}/{park_id}")

    payloads = repr(idn.rows)
    for secret in ("Rosa Delgado", "rosa.delgado@example.com", "555-0142", "500 Main St"):
        assert secret not in payloads, f"{secret!r} reached an audit payload (BR-AUD-006)"
    parked = idn.rows_for("wizard_park.parked")[0]
    assert parked["after"]["values_fields"] == 4
    assert parked["after"]["subject_ref"]["unit_id"] == UNIT_12


# ══════════════════════════════════════════════════════════════════════════
# RBAC — BR-SHL-025, server-side is THE enforcement
# ══════════════════════════════════════════════════════════════════════════
def test_cr035__an_executive_can_neither_read_nor_park(idn):
    """Narrower than the service-request lists next door, deliberately.

    A4 gives Executive VIEW on the Premises and Accounts family; a parked draft
    is in neither. BR-SHL-048: it appears *"in the clerk's own 'Waiting on'
    list and in no other surface of the product"*, and it holds a stranger's
    name, email and phone before any customer row exists. A half-typed form is
    a working document, not a report.
    """
    idn.seed_silvercreek()
    _park()
    diana = _executive()
    assert api_get(diana, PARKS).status_code == 403
    assert api_post(diana, PARKS, DEPOSIT_PARK).status_code == 403


def test_cr035__a_signed_out_caller_gets_401(idn):
    from django.test import Client

    idn.seed_silvercreek()
    assert api_get(Client(), PARKS).status_code == 401
    assert api_post(Client(), PARKS, DEPOSIT_PARK).status_code == 401


# ══════════════════════════════════════════════════════════════════════════
# CLAUDE.md RULE 1 — TENANT ISOLATION, both halves
# ══════════════════════════════════════════════════════════════════════════
def test_cr035_isolation__another_tenant_cannot_see_read_patch_or_delete(idn):
    """The APP-LAYER half, over HTTP, on all four surfaces at once.

    ⚠ **A 404, NEVER A 403** (HR-1): a 403 on a foreign id confirms the row
    exists, which is the leak. Jordan is a System Admin — of the WRONG TENANT —
    so nothing here is a role refusal; every one of these is the boundary.
    """
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    park_id = _park().json()["id"]

    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    assert api_get(jordan, PARKS, tenant=BM).json()["results"] == []
    assert api_get(jordan, f"{PARKS}/{park_id}", tenant=BM).status_code == 404
    assert api_patch(jordan, f"{PARKS}/{park_id}", {"step": 6}, tenant=BM).status_code == 404
    assert api_delete(jordan, f"{PARKS}/{park_id}", tenant=BM).status_code == 404

    # And Silver Creek's draft is untouched by any of it.
    kept = WizardPark.objects.get(id=park_id)
    assert kept.step == 3 and kept.tenant_id == idn.silvercreek.id


@pytest.mark.isolation
@requires_postgres
def test_cr035_isolation_rls__a_parked_draft_is_invisible_across_tenants(idn, rls):
    """The DATABASE half — proved under `sbh_rls_probe`, not under the app role.

    ⚠ **A PLAIN ORM ASSERTION WOULD PROVE NOTHING HERE.** The role this app
    connects as is a superuser in dev and CI, and a superuser bypasses row-level
    security unconditionally — the query returns rows because the policy was
    never consulted. So every read below runs under the
    NOLOGIN/NOSUPERUSER/NOBYPASSRLS probe, and the `rls` fixture FAILS (never
    skips) if that role could bypass.

    The app-layer filter is deliberately not in the path. `wizard_parks` holds
    an applicant's name, email and phone before any customer row exists, which
    makes this the table where a cross-tenant read is worst.
    """
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    park_id = _park().json()["id"]

    assert_denied_without_context(rls, "wizard_parks")
    assert_rls_scoped(
        rls,
        "wizard_parks",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={park_id},
    )
    assert_write_into_other_tenant_refused(
        rls, "wizard_parks", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    with live_tenant_context(idn.bluemesa.id):
        # The intruder cannot overwrite, and cannot DISCARD, a draft it cannot
        # see. The delete half matters more here than on most tables: discard
        # is a real DELETE (BR-SHL-048 (c)), so a policy gap would let one
        # tenant destroy another's work rather than merely read it.
        assert (
            rls.affected("UPDATE wizard_parks SET step = 9 WHERE id = %s", [park_id]) == 0
        ), "LEAK — another tenant re-stepped a draft it cannot see"
        assert (
            rls.affected("DELETE FROM wizard_parks WHERE id = %s", [park_id]) == 0
        ), "LEAK — another tenant discarded a draft it cannot see"

    # Read back AS SILVER CREEK, the tenant that owns the draft. With context
    # cleared the policy matches nothing and this `.get()` raises
    # `WizardPark.DoesNotExist` — deny-by-default, not a missing row.
    with live_tenant_context(idn.silvercreek.id):
        kept = WizardPark.objects.get(id=park_id)
    assert kept.step == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-035 step 6 parts 2-3 (BR-SHL-048 + the PO ruling quoted verbatim in
#         12-governance/02-decision-log.md, 2026-08-26)
# generated: 2026-08-26 by the CR-035 park-service lane (PARKSVC)
# checklist: A✔ B✔ C✔ D✔ E=deferred(lane PARKUI builds the port and resume) F✔ G✔ H=deferred(PO)
# gates: recorded in the lane report with the numbers actually run
# exceptions: the frontend half of the round trip is another lane's, so no case
#         here clicks anything — the r11 2d "prove it by clicking" half is
#         PARKUI's and is reported as owed rather than claimed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# CR-122-BRC06 · THE DRAFT — B19 §12.2's QUIET CONTROL NOW KEEPS THE TYPING
# ══════════════════════════════════════════════════════════════════════════
def test_cr122__a_draft_has_no_reason_and_keeps_the_typing(idn):
    """`Save & exit` writes a row, and that row has no `waiting_on`.

    PO ruling 2026-09-19 (`CR-122-BRC06`). Until this, `Save & exit` *"left
    quietly and wrote NOTHING"* — the wizard's own words — so a clerk who keyed
    five steps and a $150.00 deposit with its receipt number started again from
    scratch, unwarned. The refusal this replaces is the one struck out of the
    envelope table above.

    **B19 §12.2's two controls stay two**, and this asserts the distinction
    rather than assuming it: the draft carries `is_draft` true and an empty
    reason; a park carries a reason and `is_draft` false.
    """
    idn.seed_silvercreek()
    body = _park(waiting_on="").json()
    assert body["waiting_on"] == ""
    assert body["is_draft"] is True
    # The whole point: what was typed came back.
    assert body["values"]["applicant_email"] == DEPOSIT_PARK["values"]["applicant_email"]

    parked = _park(waiting_on="Waiting on a deposit").json()
    assert parked["is_draft"] is False
    assert parked["waiting_on"] == "Waiting on a deposit"


@pytest.fixture
def series_sink():
    """The REAL sink the real callers use — `AppConfig.ready` registers it.

    Borrowed verbatim from `test_cr039_wd_move_records.py`, where the same
    fixture exists for the same reason: without it `core.numbering.next_number`
    has nowhere to go, and a test that did not wire it would be asserting the
    absence path while believing it asserted the number.
    """
    from apps.tenancy import services as tenancy_services
    from core import numbering as core_numbering

    core_numbering.set_series_sink(tenancy_services.allocate_series_number)
    yield
    core_numbering.set_series_sink(tenancy_services.allocate_series_number)


def _seed_move_series(series: str = "move_in", fmt: str = "MVI-{YY}-{0000}") -> None:
    """A move series row a real host gets from `manage.py seed_demo`.

    ⚠ **IT TAKES THE SERIES AS AN ARGUMENT SINCE 2026-09-20**, because a
    move-OUT draft is numbered now too (PO ruling of that date, option A,
    item 9). It was `_seed_move_in_series` and hardcoded `move_in`.

    ⚠ **IT IS SEEDED EXPLICITLY RATHER THAN ASSUMED**, because a test that
    assumed it would pass for the wrong reason on a fixture that happens to
    carry one and go quietly green on a fixture that does not — which is
    exactly what the first draft of this test did.

    ⚠ **AND IT IS SEEDED INSIDE A TENANT CONTEXT, WHICH IS THE HALF THAT BIT.**
    A test body runs with no tenant resolved — that is only set per request —
    so the first draft of this helper wrote `tenant_id=None`, the `get_or_create`
    blew up, and the graceful `except` in `_allocate_draft_reference` turned the
    whole thing into a silent `reference: None`. The test then failed for a
    reason that had nothing to do with the code under test.
    """
    from apps.tenancy import models as tenancy_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        tenant_id = tenancy_models.Tenant.objects.get(subdomain="silvercreek").id
    with core_tenancy.tenant_context(tenant_id):
        tenancy_models.NumberSeries.objects.get_or_create(
            tenant_id=tenant_id,
            series=series,
            defaults={"format": fmt, "next_number": 1},
        )


def test_cr122__a_move_in_draft_with_no_series_still_parks(idn):
    """⚠ **A MISSING SERIES COSTS THE REFERENCE, NEVER THE DRAFT.**

    `series_sink` is deliberately NOT requested here. `moves._allocate_move_no`
    states the posture this follows in as many words — *"A household must not
    be refused a move-in because nobody configured numbering. The move is the
    regulated act; its reference is not."* Losing an afternoon's typing because
    a lookup table is empty would be the original defect wearing a new hat.
    """
    idn.seed_silvercreek()
    body = _park(waiting_on="").json()
    assert body["reference"] is None
    assert body["is_draft"] is True
    assert body["values"]["applicant_email"] == DEPOSIT_PARK["values"]["applicant_email"]


def test_cr122__a_move_in_draft_carries_the_reference_it_will_be_filed_under(idn, series_sink):
    """`MVI-{YY}-{0000}`, from the `move_in` series, at the moment it is written.

    The Move-ins tab draws a REFERENCE column over an OPEN counter (blueprint
    p073) and an open draft is what that counter counts — so a clerk chasing an
    unfinished job has something to quote. `services.move_in` ADOPTS this
    number rather than allocating a second one, which is what stops a job being
    filed under a number nobody was told.

    ⚠ **AND A MOVE-OUT ALLOCATES TOO SINCE 2026-09-20** (PO ruling of that
    date, option A, item 9 — `OQ-CUS-12489` closed, `DEF-CUS-5922` closed).
    This test asserted `other["reference"] is None` for a `move_out` draft and
    the docstring called that *"the honest state, not a bug"*, which it was
    for one day. It was not cosmetic: `/moves/{ref}` matches on this column and
    NULL matches nothing, so a parked move-out could not be opened from its own
    record at all and the `Resume` door was unreachable for it.

    ⚠ **THE REMAINING THREE FLOWS STILL CARRY NO REFERENCE** and `transfer` is
    asserted below as the standing case, so a lane that widens the allocator
    again has to come through this test rather than past it.
    """
    idn.seed_silvercreek()
    _seed_move_series()
    _seed_move_series("move_out", "MVO-{YY}-{0000}")
    body = _park(waiting_on="").json()
    assert body["reference"], "a move-in draft must carry a reference"
    assert body["reference"].startswith("MVI-"), body["reference"]

    out = _park(flow="move_out", waiting_on="").json()
    assert out["reference"], "a move-out draft must carry a reference too"
    assert out["reference"].startswith("MVO-"), out["reference"]

    # ⚠ **THE TWO COUNTERS ARE SEPARATE AND THE PREFIX IS WHAT PROVES IT.** One
    # shared `MV-` series was rejected when these were minted, because a clerk
    # reading `MV-26-0004` down a phone cannot say whether it names an arrival
    # or a departure (`core.numbering`'s own note). Asserting only "it has a
    # reference" would pass if the move-out drew from the move-in counter.
    assert out["reference"] != body["reference"]

    other = _park(flow="transfer", waiting_on="").json()
    assert other["reference"] is None

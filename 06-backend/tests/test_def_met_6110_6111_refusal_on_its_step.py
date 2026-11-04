# ── Trace ──────────────────────────────────────────────
# Defects: DEF-MET-6110 (step 6 offers `TAP`, the product's own picker; the
#          last press answers "Something went wrong on our side" — a
#          BillingRuleError leaving `POST /connections/commit` as HTTP 500) ·
#          DEF-MET-6111 (units labelled the same as ones the picked address
#          already holds; the same raw 500, from
#          `uq_units_tenant_premises_label`)
# Rules:   BR-MET-112 (nothing is written until the last button; ONE
#          transaction, both or neither) · BR-BIL-007 / BR-BIL-020 (billing
#          prices a charge code; a fee at a guessed amount lands on an
#          immutable document) · BR-SHL-020 r2 (the clerk reads the catalogue
#          entry, never server prose) · B14 rule 33
# Decision: 12-governance/02-decision-log.md, 2026-09-21 — "A RULE REFUSAL
#          REACHES THE CLERK ON THE STEP THEY CHOSE IT". PO, verbatim: *"this
#          fix is correct - you ahve to show the error at step you mentioned"*.
# Screens: S87 step 3 (Units) · step 6 (Charges) · step 8 (Review & confirm)
# ───────────────────────────────────────────────────────
"""**Does a rule the clerk broke reach them as a sentence, on the step that
owns the field — or as a 500?**

Both defects were reproduced in a browser on the acceptance walk and both
answered `SYS-INTERNAL`. The clerk is told the product is broken when they have
simply chosen something the product refuses; they cannot act on it, and the
work is gone. `DEF-MET-6110` cost **thirty-three clerk acts**.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, AND IT IS THE RISK THE FIX ITSELF
CARRIES.** A `try/except Exception` answering every failure with a polite
sentence would satisfy every *"is it a BizError"* assertion here and would hide
a genuine crash behind a refusal no clerk can escape. So the last two cases ask
the opposite question — a failure that is NOT one of the two recognised rules
must still leave as itself, with its own class — and they are the reason this
file is not a set of happy-path assertions.

⚠ **AND `params["step"]` IS ASSERTED BY VALUE, NOT MERELY FOR PRESENCE.** A
refusal carrying the WRONG step lands the clerk on a screen where the field
they must change is not, which reads as a product that has lost their work.
The browser resolves that id against its own declared step list, so a typo here
is a refusal that routes nowhere and falls back to the step-8 failure card —
silently, which is why the value is pinned.
"""

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import seams
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _wizard_plan(**over):
    """The payload `commitPlanOf` emits, copied from the browser's own shape.

    Same source and same reason as `test_def_met_5441_the_commit_door.py`: three
    defects in a row on this call were the payload and the reader disagreeing
    about a key, with both sides tested on their own half.
    """
    plan = {
        "premises": {
            "id": None,
            "address": "1400 Brazos Bend Drive",
            "premise_type": None,
            "parcel_ref": "R-96110",
            "read_route": None,
            "services_available": ["electric"],
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Apt",
        "target_activation": None,
        "service_request_id": None,
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


def _a_code_that_cannot_be_priced(brazos, code="TAP"):
    """`TAP` as the seeded demo actually holds it: **no amount at all.**

    Measured on the demo tenant on 2026-09-21 — `TAP`, `IMPACT`, `DAMAGE`,
    `BULK-WATER` and `BASE-E-COM` all carry a NULL amount and `LATE` is a
    percent rule. Six of the twenty-nine active codes, every one of them in the
    picker the PO used.
    """
    from apps.rating import models as rating_models

    row, _ = rating_models.Charge.objects.get_or_create(
        tenant_id=brazos.id,
        code=code,
        defaults={"name": "New service tap fee", "charge_type": "one_time"},
    )
    row.amount = None
    row.amount_rule = None
    row.save(update_fields=["amount", "amount_rule"])
    return row


# ════════════════════════════════════════════════════════════════════════════
# 1 · `DEF-MET-6110` — THE CHARGE REFUSAL LANDS ON STEP 6
# ════════════════════════════════════════════════════════════════════════════
def test_an_unpriceable_charge_code_refuses_on_the_charges_step(dana, brazos):
    """**It was a 500. It is a named refusal carrying `step: charges`.**

    ⚠ **THE ASSERTION THAT MATTERS IS THE CLASS, NOT THE TEXT.** Before the fix
    this raised `apps.billing.exceptions.BillingRuleError`, which
    `core.errors.drf_exception_handler` has no row for, so it fell to the 5xx
    branch and the clerk read *"Something went wrong on our side."*
    `errors.BizError` is what answers 422 with a catalogue key.
    """
    _a_code_that_cannot_be_priced(brazos)
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as refused:
            w6.commit_new_connect(
                dana,
                _wizard_plan(
                    quote_lines=[{"charge_code": "TAP", "basis": "per unit", "quantity": 1}],
                    quote_due_days=30,
                    quote_payer="owner_account",
                    create_owner_account=True,
                    owner={"name": "Bend Developments LLC", "party_kind": "company",
                           "identity": {"tax_id": "TX-96110"}},
                    # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account
                    # needs two or more homes, so the build makes two.
                    units=[
                        {"label": "Apt 1", "is_common_area": False},
                        {"label": "Apt 2", "is_common_area": False},
                    ],
                ),
            )
    assert refused.value.message_key == "metering.connection_charge_refused"
    assert refused.value.params["step"] == w6.STEP_OF_THE_CHARGES == "charges"
    # `BR-SHL-020 r2` — the rule's own English is kept for the attempt row and
    # the log and is NOT rendered. Support has to be able to read WHICH of
    # billing's checks refused, or the sentence on screen is all there is.
    assert "TAP" in str(refused.value.params.get("detail", ""))


def test_the_build_that_named_an_unpriceable_charge_wrote_nothing(dana, brazos):
    """**`BR-MET-112` is untouched by the translation — both or neither.**

    The handler sits OUTSIDE `transaction.atomic()`, so the block has already
    rolled back before it runs. A fix that caught INSIDE would be hard-won law
    14's trap: on PostgreSQL the transaction is poisoned by the refused
    statement and the work is lost at COMMIT anyway, while this suite's SQLite
    has no aborted state and would pass the broken version green.
    """
    _a_code_that_cannot_be_priced(brazos)
    with tenant_ctx(brazos):
        premises_before = metering_models.Premises.objects.count()
        units_before = metering_models.Unit.objects.count()
        connections_before = work_tables.Connection.objects.count()
        with pytest.raises(errors.BizError):
            w6.commit_new_connect(
                dana,
                _wizard_plan(
                    quote_lines=[{"charge_code": "TAP", "basis": "per unit", "quantity": 1}],
                    quote_due_days=30,
                    quote_payer="owner_account",
                    create_owner_account=True,
                    owner={"name": "Bend Developments LLC", "party_kind": "company",
                           "identity": {"tax_id": "TX-96111"}},
                ),
            )
        assert metering_models.Premises.objects.count() == premises_before
        assert metering_models.Unit.objects.count() == units_before
        assert work_tables.Connection.objects.count() == connections_before


# ════════════════════════════════════════════════════════════════════════════
# 2 · `DEF-MET-6111` — THE LABEL REFUSAL LANDS ON STEP 3
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# 1b · `DEF-MET-7690` — THE ADDRESS BLOCK'S REFUSALS LAND ON STEP 2
# ════════════════════════════════════════════════════════════════════════════
def test_an_unknown_read_route_refuses_on_the_premise_step(dana, brazos):
    """**`DEF-MET-7690`, reproduced in a browser on the New Connect walk.**

    Typed `RT-07` into *Read route* on step 2, walked six more steps and pressed
    **Create connection**. The server answered `422` with
    `metering.premises.route_unknown` — right refusal, right sentence, `route`
    named in `field_errors` — and `params` was `{}`. The wizard routes on
    `params["step"]` **and nothing else**, so it fell back to the ordinary
    failure card on step 8: *"Failed. The connection was not created. That route
    is not on file."*, naming neither the field nor the step, after thirty-odd
    clerk acts.

    ⚠ **THE REFUSAL PREDATES THE MECHANISM, WHICH IS THE WHOLE ESCAPE.**
    `_resolve_create_route` began refusing an unknown route in `CR-089` wave B,
    before `DEF-MET-6110` built the step stamp on 2026-09-21, and nothing asked
    whether the refusals this commit can actually raise carry one. Both halves
    were correct on their own.
    """
    with tenant_ctx(brazos):
        plan = _wizard_plan()
        plan["premises"]["read_route"] = "RT-07"
        with pytest.raises(errors.ValidationError) as refused:
            w6.commit_new_connect(dana, plan)
    # Everything the envelope carried before is unchanged — this is a STAMP and
    # not a new refusal. `BR-SHL-020 r2` holds: the sentence is still composed
    # in the eleven catalogues from the key, and a step id is a stable code.
    assert refused.value.message_key == "metering.premises.route_unknown"
    assert refused.value.code == errors.VAL_UNKNOWN_LOOKUP
    assert [fe["field"] for fe in refused.value.field_errors] == ["route"]
    # ⚠ ASSERTED BY VALUE, for this file's own reason: a refusal carrying the
    # WRONG step lands the clerk on a screen the field is not on.
    assert refused.value.params["step"] == w6.STEP_OF_THE_PREMISE == "premise"


def test_the_premise_steps_stamp_does_not_reach_a_refusal_from_elsewhere(dana, brazos):
    """**NOT A CATCH-ALL, and this is the case that says so.**

    `_premises_made_for_the_wizard` wraps ONE call. A refusal raised anywhere
    else on this path keeps whatever step it already had — or none — and is
    never re-labelled *premise* on the way out. The unit-label clash below is
    raised after the address is settled, so if the wrapper were widened into a
    blanket handler this case would go red rather than a clerk being sent to
    step 2 to fix a unit number.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="118 Cottonwood Bend")
        metering_models.Unit.objects.create(
            tenant_id=brazos.id, premises_id=premises["id"], label="Apt 1"
        )
        plan = _wizard_plan(units=[{"label": "Apt 1"}])
        plan["premises"] = {"id": premises["id"]}
        with pytest.raises(errors.BizError) as refused:
            w6.commit_new_connect(dana, plan)
    assert refused.value.params["step"] == w6.STEP_OF_THE_UNITS == "units"
    assert refused.value.params["step"] != w6.STEP_OF_THE_PREMISE


def test_a_label_the_address_already_holds_refuses_on_the_units_step(dana, brazos):
    """**Pick an address holding `Apt 101–103`, add `Apt 101–103`.**

    The database was always right to refuse; nothing asked first, and
    `uq_units_tenant_premises_label` is not a sentence a clerk can act on.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="2200 Riverbend Ct")
        for label in ("Apt 101", "Apt 102", "Apt 103"):
            metering_models.Unit.objects.create(
                tenant_id=brazos.id, premises_id=premises["id"], label=label
            )
        plan = _wizard_plan(units=[{"label": f"Apt {n}"} for n in (101, 102, 103)])
        plan["premises"] = {"id": premises["id"]}
        with pytest.raises(errors.BizError) as refused:
            w6.commit_new_connect(dana, plan)
    assert refused.value.message_key == "metering.connection_unit_label_taken"
    assert refused.value.params["step"] == w6.STEP_OF_THE_UNITS == "units"


def test_one_payload_naming_the_same_label_twice_is_the_same_refusal(dana, brazos):
    """**The other source of the same clash, and it never reached the constraint.**

    Two units labelled alike in ONE build failed on the second `create`, not on
    a read — so it was the identical 500 by a different route. One rule, one
    sentence, one step.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as refused:
            w6.commit_new_connect(
                dana, _wizard_plan(units=[{"label": "Apt 7"}, {"label": "Apt 7"}])
            )
    assert refused.value.message_key == "metering.connection_unit_label_taken"
    assert refused.value.params["step"] == "units"


def test_a_label_free_at_this_address_is_not_refused(dana, brazos):
    """**What stops the check above from being one that cannot pass.**

    A guard that refused every build would satisfy both cases above. `Apt 104`
    is free at the same address that refuses `Apt 101`, and it builds.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="2210 Riverbend Ct")
        metering_models.Unit.objects.create(
            tenant_id=brazos.id, premises_id=premises["id"], label="Apt 101"
        )
        plan = _wizard_plan(units=[{"label": "Apt 104"}])
        plan["premises"] = {"id": premises["id"]}
        built = w6.commit_new_connect(dana, plan)
        assert built["manifest"]["units"] == 1
        assert metering_models.Unit.objects.filter(
            premises_id=premises["id"], label="Apt 104"
        ).exists()


# ════════════════════════════════════════════════════════════════════════════
# 3 · WHAT IS **NOT** TURNED INTO A POLITE MESSAGE
# ════════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS SECTION IS THE POINT OF THE FILE.** The whole risk of this fix is a
# catch-all: a commit that answered every failure with *"check the charges"*
# would pass every case above and would hide a real crash behind a refusal the
# clerk cannot escape. CLAUDE.md law 7's second habit is *ask what would make
# this check pass wrongly*, and for this fix the answer is *catching too much*.
def test_a_failure_that_is_not_a_rule_is_re_raised_as_itself(dana, brazos, monkeypatch):
    """**A crash inside the commit still leaves as a crash.**

    `RuntimeError` stands in for every unrecognised failure — a bug, a driver
    error, a seam that raised something nobody expected. It must NOT become a
    `BizError`, because a 422 with a catalogue sentence tells the clerk to
    change a field when the truth is that the product broke.
    """
    def explode(*_args, **_kwargs):
        raise RuntimeError("a bug, not a rule")

    monkeypatch.setattr(w6, "commit_connection", explode)
    with tenant_ctx(brazos):
        with pytest.raises(RuntimeError, match="a bug, not a rule"):
            w6.commit_new_connect(dana, _wizard_plan())


def test_an_integrity_error_on_another_constraint_is_re_raised_as_itself(dana, brazos, monkeypatch):
    """**Only ONE unique constraint on this path is a clerk's choice.**

    `uq_premises_tenant_premise_no`, `uq_units_tenant_unit_no`, `ux_accounts_no`
    and `uq_assets_tenant_no` are all numbers this SERVER allocates, so a
    collision on one is a numbering defect. Translating it would tell a clerk to
    change something they never typed, and would bury the defect.
    """
    from django.db import IntegrityError

    def clash(*_args, **_kwargs):
        raise IntegrityError(
            'duplicate key value violates unique constraint "uq_units_tenant_unit_no"'
        )

    monkeypatch.setattr(w6, "commit_connection", clash)
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError, match="uq_units_tenant_unit_no"):
            w6.commit_new_connect(dana, _wizard_plan())


def test_the_recognised_constraint_is_recognised_from_the_drivers_text(dana, brazos, monkeypatch):
    """The mirror of the case above, so neither is a check that cannot fail.

    ⚠ **IT ALSO PINS THE TEXT FALLBACK, WHICH IS THE HALF WITH NO PRODUCTION
    COVERAGE.** `_constraint_name_of` reads `diag.constraint_name` off the
    driver's own exception first; this suite runs on SQLite, which has no
    `diag`, so only the literal-name fallback is exercised here. Both paths
    compare against the SAME declared constraint name and neither reads prose.
    """
    from django.db import IntegrityError

    def clash(*_args, **_kwargs):
        raise IntegrityError(
            'duplicate key value violates unique constraint "uq_units_tenant_premises_label"'
        )

    monkeypatch.setattr(w6, "commit_connection", clash)
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as refused:
            w6.commit_new_connect(dana, _wizard_plan())
    assert refused.value.message_key == "metering.connection_unit_label_taken"
    assert refused.value.params["step"] == "units"


def test_the_refusal_class_crosses_the_seam_and_is_billings_own(dana, brazos):
    """**The `except` clause must name the class billing actually raises.**

    A seam that answered `Exception` would catch everything and this whole fix
    would be the catch-all it exists not to be; one that answered a class
    billing never raises would be a guard incapable of firing, and every case
    in section 1 would go red the day somebody noticed.
    """
    from apps.billing import exceptions as billing_exceptions

    assert seams.quote_refusal_class() is billing_exceptions.BillingRuleError
    assert issubclass(seams.QuoteRefusalUnavailable, Exception)
    assert not issubclass(billing_exceptions.BillingRuleError, errors.ApiError), (
        "if billing's rule error ever became a catalogue exception this "
        "translation would be dead code — and would go on looking alive"
    )

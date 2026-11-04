# ── Trace ──────────────────────────────────────────────
# Defects: DEF-RAT-5814 — the table permitted FIVE scopes and the model SEVEN,
#          so *All services* and *Specific services* were a guaranteed 500 ·
#          DEF-RAT-5815 — the singular service picker posted a CODE into a UUID
#          foreign key, so *One service* had never been saveable either.
# Rules:   CR-091-BRC01 / PO ruling 2026-09-10 · BR-RAT-024 (a service must be
#          in the platform catalog AND enabled for this tenant) ·
#          CLAUDE.md hard-won law 7 (ask what makes a check pass WRONGLY) ·
#          CLAUDE.md hard-won law 14 (the suite's sqlite cannot express this)
# Fix in:  06-backend/apps/rating/migrations/0040_def_rat_5814_widen_discount_scope.py
#          06-backend/apps/rating/discount_services.py (`_validate_version`)
# ───────────────────────────────────────────────────────
"""**Every scope the product offers can actually be stored — walked, not listed.**

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE IS PostgreSQL-ONLY, AND IT IS THE WHOLE REASON THE BUG SHIPPED
════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory SQLite (CLAUDE.md hard-won law
14). SQLite does not enforce the `CHECK` constraint Django writes here, so
**every existing discount test passes green against both the broken schema and
the fixed one** — and two lanes had already read the resulting
`makemigrations --check` red as cosmetic. The only thing that can tell the two
apart is a row reaching a real table, which is what this file does.

════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THIS CHECK PASS WRONGLY — asked first, per law 7
════════════════════════════════════════════════════════════════════════════
`DEF-RAT-5814`'s own walk had two checks that first PASSED on the defect they
were written for. The trap here is exact and worth naming: **a scope test that
asserts only "the save succeeded" passes if the value silently fell back to
`whole_bill`.** The save would be real, the row would be real, and the scope
the clerk chose would be gone.

So nothing here asserts a status. Every case **reads the stored column back out
of the database** and asserts it equals the scope that was asked for, and the
`one_service` case reads the resolved FOREIGN KEY back and asserts it points at
the service whose CODE was posted.

════════════════════════════════════════════════════════════════════════════
PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Run at the pristine tip `ca3050616` — this file's cases over the tip's source,
through `pytest` against real PostgreSQL. **11 failed, 4 passed**, and the four
that passed are exactly the four scopes the old constraint already permitted,
which is the shape of the defect rather than a coincidence:

    [one_service]          ValidationError: ['"water" is not a valid UUID.']
    [all_services]         IntegrityError: new row for relation
                           "discount_versions" violates check constraint
                           "ck_discount_versions_scope"
    [specific_services]    (the same CheckViolation)
    one_service_resolves…  ValidationError: ['"water" is not a valid UUID.']
    a_service_…_refused    ValidationError: ['"not_a_service" is not a valid
                           UUID.']  — a 500 where a field error belongs

    [whole_bill] [usage_only] [base_only] [named_codes]   passed, before and
    after, because the table already allowed those four.

════════════════════════════════════════════════════════════════════════════
AND IT WALKS `DISCOUNT_SCOPES` RATHER THAN LISTING SEVEN
════════════════════════════════════════════════════════════════════════════
The defect was a LIST that stopped tracking a TUPLE. A test that re-typed the
seven would be a third copy of the same list and would go stale in the same
way — silently, on the day somebody adds the eighth. Iterating the tuple means
**the next scope added to the model cannot ship without its migration**: it
arrives in this loop automatically and fails until the table can hold it.
"""

from datetime import date

import pytest

from apps.rating import discount_services
from apps.rating import discounts as discount_models
from apps.tenancy import models as tenancy_models

from tests.isolation_helpers import requires_postgres
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared W1 fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

#: The scopes that need a target named alongside them, and what to name. Any
#: scope NOT in here is saved bare. Keyed so an unlisted new scope is exercised
#: in its simplest form rather than skipped.
TARGETS: dict[str, dict] = {
    discount_models.SCOPE_ONE_SERVICE: {"applies_to_service": "water"},
    discount_models.SCOPE_NAMED_CODES: {"applies_to_charge_codes": ["BASE-W"]},
    discount_models.SCOPE_SPECIFIC_SERVICES: {"applies_to_services": ["water"]},
}


def _payload(scope: str, code: str) -> dict:
    return {
        "code": code,
        "name": f"Scope probe {scope}",
        "discount_type": "percentage",
        "value": "10",
        "applies_to": scope,
        "effective_from": date(2026, 10, 1),
        **TARGETS.get(scope, {}),
    }


@pytest.mark.parametrize("scope", discount_models.DISCOUNT_SCOPES)
def test_every_offered_scope_reaches_the_table_and_keeps_its_value(env, scope):
    """One discount per scope, committed, then the COLUMN read back.

    Before `rating/0040` the last two parameters raised
    `IntegrityError: new row for relation "discount_versions" violates check
    constraint "ck_discount_versions_scope"`, which the API renders as
    *"Something went wrong on our side."*
    """
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin, _payload(scope, f"SCOPE{scope[:4].upper()}")
        )
        stored = discount_models.DiscountVersion.objects.get(discount_id=row["id"])
        # ⚠ THE ASSERTION THAT MATTERS: the value the clerk chose, out of the
        # database. `row["id"]` existing only proves a row exists.
        assert stored.applies_to == scope, (
            f"a discount saved on scope {scope!r} came back stored as "
            f"{stored.applies_to!r} — a silent fallback is this defect wearing "
            f"a passing test"
        )


def test_one_service_resolves_the_code_the_picker_sends_to_the_right_service(env):
    """`DEF-RAT-5815` — `"water"` in, Water's own row out.

    DIS-02 step 2 builds its picker from `row.service`, the catalogue CODE, and
    the column is a FK to `tenancy.Service`. Before the fix the code went
    straight into `applies_to_service_id` and Django answered
    `ValidationError: ['"water" is not a valid UUID.']`.
    """
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(env.admin, _payload("one_service", "ONESVC"))
        stored = discount_models.DiscountVersion.objects.get(discount_id=row["id"])
        water = tenancy_models.Service.objects.get(code="water")
        assert stored.applies_to_service_id == water.id
        # And it reads back as the CODE on every surface, which is what the
        # edit door reloads into the picker.
        assert stored.applies_to_service.code == "water"


def test_a_service_this_utility_does_not_sell_is_refused_by_name(env):
    """BR-RAT-024, the singular half. A resolver that silently dropped an
    unknown code would make `one_service` mean *whole bill* — a wrong bill
    rather than a refused form."""
    from core import errors

    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ApiError) as caught:
            discount_services.create_discount(
                env.admin,
                {**_payload("one_service", "BADSVC"), "applies_to_service": "not_a_service"},
            )
        fields = {item["field"] for item in caught.value.field_errors}
        assert fields == {"applies_to_service"}, fields

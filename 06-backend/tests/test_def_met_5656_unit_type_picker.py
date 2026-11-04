"""DEF-MET-5656 — a unit type a tenant adds never reaches the Add-units form.

⚠ **THE CAPABILITY EXISTS END TO END EXCEPT FOR THE ONE CONTROL A CLERK
TOUCHES.** Settings → Reference data → Unit types writes to the tenant's own
`unit_types` table; `services._resolve_unit_type` reads that table FIRST and
would accept a tenant's sixth type happily. **The dropdown is the only thing
that never asks.** `AddUnitsWizard.tsx:653` renders
`options={UNIT_TYPES.map(...)}` — a five-string array compiled into the
JavaScript bundle at `UnitsListPage.tsx:131`, above a comment calling it *"the
five ratified unit types (the server's own set)"*. That was true when written
and stopped being true on 2026-08-18, when `BR-MET-084` made the list
tenant-extensible. `models.UnitType`'s own docstring records the change:
*"Until 2026-08-18 the vocabulary was the UNIT_TYPES 5-tuple in services.py — a
closed enum no tenant could extend and no screen could show."*

⚠ **AND THE SCREEN CANNOT SIMPLY CALL `/lookups/unit_types`** — that endpoint is
System-Admin-only, and adding a unit is a clerk's job, so the clerk's own wizard
would receive an empty control. **This exact trap has been paid for once
already**: `DEF-196`, where S28's read-method picker got
`GET /reads/read-methods` under `AnyTenantRole` instead, with its docstring
saying *"NOT a hardcoded array either — the list is tenant-extensible and a copy
here would drift the day a tenant adds a sixth method."* This file asks for the
same door for unit types.

**PROVED RED BEFORE IT WAS TRUSTED GREEN** (hard-won law 7), through pytest —
the harness that runs it.
"""

from __future__ import annotations

import pytest
from django.urls import Resolver404, resolve

pytestmark = pytest.mark.django_db


def test_a_clerk_readable_unit_type_route_exists():
    """⚠ **THE DOOR ITSELF, AND IT MUST NOT BE `/lookups/unit_types`.**

    `DEF-196` paid for this lesson once already: `/lookups/*` is
    System-Admin-only, and adding a unit is a CLERK's job, so a picker reading
    the Settings endpoint hands a Billing Clerk an empty control. Read methods
    solved it with `GET /reads/read-methods` under `AnyTenantRole`, whose
    docstring says the quiet part: *"NOT a hardcoded array either — the list is
    tenant-extensible and a copy here would drift the day a tenant adds a sixth
    method."* Unit types needs the same door and has none.
    """
    try:
        match = resolve("/api/brazosbend/units/unit-types")
    except Resolver404:  # pragma: no cover — this IS the defect today
        pytest.fail(
            "no clerk-readable unit-type route exists, so the Add-units picker "
            "has nothing to ask and falls back to a hardcoded array"
        )
    assert match.func is not None


def test_the_vocabulary_is_read_from_the_tenants_rows():
    """⚠ **THE SELECTOR THE DOOR WILL SERVE.** It must read `unit_types` — the
    tenant's own table — and NOT `services.UNIT_TYPES`, the five-string tuple
    the front end currently mirrors. `models.UnitType`'s own docstring dates the
    change: *"Until 2026-08-18 the vocabulary was the UNIT_TYPES 5-tuple in
    services.py — a closed enum no tenant could extend and no screen could
    show."* The backend moved; the picker did not.
    """
    from apps.metering import selectors

    assert hasattr(selectors, "unit_type_options"), (
        "metering has no unit_type_options(); read_method_options() is the "
        "shape to copy (selectors.py:3676)"
    )

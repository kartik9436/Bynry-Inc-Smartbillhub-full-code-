# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-010 (the ONE list view every reference list plugs into)
#           Screens: S8 / r10 SET-04, S75–S80
# Rules:    BR-TEN-029 (used_by is a LIVE count) · BR-TEN-031 (the owning module
#           serves it through a seam) · BR-TEN-036
# ───────────────────────────────────────────────────────
"""DEF-187 — every hosted list must SERIALIZE, not merely count.

WHY THIS FILE EXISTS, and it is the whole lesson of the defect:

CR-004 shipped six reference lists whose backend tests were entirely green, and
five of the six answered **HTTP 500** the moment a human opened them. It was
found by clicking, and by nothing else.

`HostedFlatLookupHandler.used_by_seam` defaults to `None`; `used_by()` called it
unconditionally; the six new handlers set no seam because no owning module
exposes one yet. So `serialize()` raised
`TypeError: 'NoneType' object is not callable`.

THREE ACCIDENTS HID IT, and each is a lesson about what the old tests measured:

  1. The card GRID calls `count()`, which never touches `serialize()`. Every
     card rendered a correct live count over a list that could not be opened.
  2. `import_mappings` returned **200** — because it is seeded EMPTY, so the
     list comprehension never called `serialize()` once. The only list that
     worked was the one with no rows in it.
  3. The two pre-CR-004 hosted lists set a real seam, so the shared base class
     was exercised only on the paths that could not fail.

The tests that existed asserted the SHAPE of a serialized row for lists that
already had seams, and the COUNT for the new ones. Nothing asserted that a new
list could serialize a row it actually had. That is the gap this file closes.

It is table-driven over `HOSTED_LOOKUP_HANDLERS` on purpose: the next hosted
list added without a seam is covered the moment it is registered, rather than
when somebody remembers to extend a hand-written list.
"""

import pytest

from apps.tenancy import selectors, services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx


HOSTED = sorted(services.HOSTED_LOOKUP_HANDLERS.items())


@pytest.mark.django_db
@pytest.mark.parametrize("list_code,handler_class", HOSTED, ids=[c for c, _ in HOSTED])
def test_def_187__every_hosted_list_serializes_its_rows(
    list_code, handler_class, growth_plan, identity_seam
):
    """The 500 the browser found: opening a list serializes every row.

    `lookup_page` is exactly what `GET /lookups/{list}` calls, so this is the
    endpoint's own code path and not a paraphrase of it.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = selectors.lookup_page(list_code, None)
        for row in rows:
            # BR-TEN-029: used_by is a live count. A list whose owning module
            # exposes no seam yet answers 0 — it stores nothing, so nothing can
            # reference the row. It must NOT raise, which is DEF-187.
            assert isinstance(row["used_by"], int)
            assert row["used_by"] >= 0
            assert row["code"]


@pytest.mark.django_db
def test_def_187__a_seamless_handler_answers_zero_rather_than_raising(
    growth_plan, identity_seam
):
    """The unit-level statement of the same fact, without a database row.

    Kept separate from the sweep above because the sweep would go green again if
    somebody deleted the seedless lists' entries — an empty list serializes
    nothing and proves nothing, which is accident (2) that hid the defect in the
    first place. This one names the class default directly.
    """
    handler = services.AreaLookupHandler()
    assert handler.used_by_seam is None, (
        "This test is pointless if Area gains a seam — rewrite it against "
        "whichever hosted handler still has none, or delete it."
    )

    class _Row:
        code = "NORTH"

    assert handler.used_by(_Row()) == 0

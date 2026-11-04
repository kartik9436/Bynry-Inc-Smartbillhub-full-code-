# ── Trace ──────────────────────────────────────────────
# Change:  CR-036 (h) / DEF-756 — *"No screen can set a premises' services. The
#          Add-Premises wizard and the edit modal both omit the field — only the
#          CSV importer ever fills it. So every address you create by hand has
#          none. - we will ahve to fix that keep them in CR36 only"* (PO,
#          2026-08-26)
# Story:   US-MET-001 (premises write) · US-MET-003 (S16 guided add)
# Rules:   BR-MET-003 (`services_available` ⊆ the tenant's ENABLED services —
#          a premises may only offer what this utility SELLS)
# ───────────────────────────────────────────────────────
"""The SERVER half of CR-036 (h) — the two things the new screen control leans on.

The control was the missing half; these are the two guarantees underneath it,
and neither had a test naming it before today:

  1. **A service this tenant does not sell is REFUSED, and the refusal NAMES
     WHICH** — the same answer the CSV importer gives (*"This utility does not
     sell w, s, t."*, `import_rules._eval_services_enabled`), from the same
     source (`seams.enabled_service_codes()`). A clerk must never read a code
     list they cannot act on, and a refusal that says only "invalid" is that.

  2. ⚠ **AN OMITTED FIELD LEAVES THE COLUMN ALONE — `NULL` IS NOT `[]`.** A
     premises already on file holds SQL NULL, which means *never asked*, not
     *offers nothing*. CR-036 (h)'s scope forbids backfilling it, and the edit
     modal's "send it only when it changed" behaviour is worth nothing if the
     server writes `[]` for an absent field anyway. This pins the contract the
     screen depends on.

⚠ **NOTHING HERE READS SEEDED DATA.** `sample_data.py` and `seed_demo.py` write
the same list by hand to `premises.services_available` AND to each unit, so a
test that leaned on the demo tenant would agree with itself no matter what the
write path did. Every premises below is created through the real service inside
the test, and the assertions are about what the WRITE did.
"""

import pytest

from apps.metering import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def test_cr036h__create_refuses_a_service_this_utility_does_not_sell_and_names_it(brazos, dana):
    """Brazos Bend sells electric + water. `solar` is a real platform service
    (ten exist, not six) that this utility has not switched on."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_premises(
                dana,
                {"owner_id": owner_for(dana), "address_line": "9 Quarry Hill Rd", "services_available": ["water", "solar"]},
            )
    field_errors = caught.value.field_errors
    assert [fe["field"] for fe in field_errors] == ["services_available"]
    # NAMES WHICH — the importer's voice. A refusal a clerk cannot act on is not
    # a refusal, it is a dead end.
    assert field_errors[0]["message_key"] == "metering.service_not_enabled"
    assert field_errors[0]["params"]["service"] == "solar"
    # …and the one the utility DOES sell is not blamed for the one it does not.
    assert len(field_errors) == 1
    with tenant_ctx(brazos):
        assert not models.Premises.objects.filter(address_line="9 Quarry Hill Rd").exists()


def test_cr036h__update_refuses_it_too_and_writes_nothing(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="11 Quarry Hill Rd")
        with pytest.raises(errors.ValidationError) as caught:
            services.update_premises(dana, premise["id"], {"services_available": ["thermal_heat"]})
        row = models.Premises.objects.get(pk=premise["id"])
    assert caught.value.field_errors[0]["message_key"] == "metering.service_not_enabled"
    assert caught.value.field_errors[0]["params"]["service"] == "thermal_heat"
    assert row.services_available == ["electric", "water"]


def test_cr036h__what_the_wizard_sends_is_what_the_column_holds(brazos, dana):
    """The defect itself: until 2026-08-26 no screen sent this at all."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"owner_id": owner_for(dana), "address_line": "13 Quarry Hill Rd", "services_available": ["electric"]},
        )
        row = models.Premises.objects.get(pk=created["id"])
    assert row.services_available == ["electric"]


def test_cr036h__an_omitted_field_leaves_null_alone__never_backfilled(brazos, dana):
    """⚠ CR-036 (h) scope row 5, and the contract the edit modal is built on.

    A premises created without the field holds SQL **NULL** — *never asked*. An
    UPDATE that does not mention the field must leave that NULL exactly as it
    is: writing `[]` would turn an unanswered question into an answered one and
    destroy the only signal that the address was never asked.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "15 Quarry Hill Rd"})
        row = models.Premises.objects.get(pk=created["id"])
        assert row.services_available is None, "a create that never asked must not answer"

        # An unrelated edit — the clerk fixing the street name — mentions no
        # services, so the column must not move.
        services.update_premises(dana, created["id"], {"address_line": "15 Quarry Hill Road"})
        row.refresh_from_db()
    assert row.services_available is None


def test_cr036h__an_explicit_empty_list_IS_an_answer_and_is_stored(brazos, dana):
    """The other side of the same coin: a clerk who empties the control has
    ANSWERED — this address offers nothing — and that must be written, so that
    `NULL` and `[]` stay two distinguishable states in the column."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="17 Quarry Hill Rd")
        services.update_premises(dana, premise["id"], {"services_available": []})
        row = models.Premises.objects.get(pk=premise["id"])
    assert row.services_available == []
    assert row.services_available is not None

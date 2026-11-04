# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-10027 — "Account with the authority" is the utility's tax
#           registration number with that authority (PO ruling 2026-10-09,
#           option (a)). Settings › Accounting › Tax filing accounts now PICKS
#           the authority from the same list a tax uses (`tax_jurisdictions`).
# ───────────────────────────────────────────────────────
#
# What the server must do for that: when a row names its authority by
# `jurisdiction_id`, the authority's NAME is the jurisdiction's name — the
# server writes it, so a picked row can never carry a typed name that
# disagrees with the authority it is linked to. A row with no link (typed
# before this change) keeps working exactly as it did, and can be linked by
# editing. The (authority, number) uniqueness is unchanged.
import pytest

from apps.rating import models as rating_models
from apps.rating import services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx


def _authority(tenant, name):
    row, _ = rating_models.TaxJurisdiction.objects.get_or_create(tenant=tenant, name=name)
    return row


def test_a_picked_authority_names_the_row(brazos, dana):
    with tenant_ctx(brazos):
        state = _authority(brazos, "State Department of Revenue")
        made = services.create_authority_account(
            dana, {"jurisdiction_id": str(state.id), "account_number": "32-1180544"}
        )
        assert made["jurisdiction_id"] == str(state.id)
        assert made["authority_name"] == "State Department of Revenue"


def test_the_picked_authority_wins_over_a_typed_name(brazos, dana):
    with tenant_ctx(brazos):
        city = _authority(brazos, "City of Queen West Finance")
        made = services.create_authority_account(
            dana,
            {"jurisdiction_id": str(city.id), "authority_name": "Queen West", "account_number": "CQW-FR-0091"},
        )
        assert made["authority_name"] == "City of Queen West Finance"


def test_a_typed_row_is_linked_by_editing(brazos, dana):
    with tenant_ctx(brazos):
        typed = services.create_authority_account(
            dana, {"authority_name": "TX Comptroller", "account_number": "32-1180455"}
        )
        assert typed["jurisdiction_id"] is None
        state = _authority(brazos, "Texas Comptroller of Public Accounts")
        linked = services.update_authority_account(dana, typed["id"], {"jurisdiction_id": str(state.id)})
        assert linked["jurisdiction_id"] == str(state.id)
        assert linked["authority_name"] == "Texas Comptroller of Public Accounts"
        assert linked["account_number"] == "32-1180455"


def test_neither_a_name_nor_an_authority_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            services.create_authority_account(dana, {"account_number": "123456789 RT0001"})


def test_one_number_per_authority_still_holds(brazos, dana):
    with tenant_ctx(brazos):
        state = _authority(brazos, "Canada Revenue Agency")
        services.create_authority_account(
            dana, {"jurisdiction_id": str(state.id), "account_number": "123456789 RT0001"}
        )
        with pytest.raises(errors.ValidationError):
            services.create_authority_account(
                dana, {"jurisdiction_id": str(state.id), "account_number": "123456789 rt0001"}
            )

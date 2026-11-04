# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-TEN-9720 (CR-171-BRC10, lane RULINGS-2)
# Rules:   PO ruling (5) of 2026-10-05, decision log "FIVE PO RULINGS IN ONE
#          REPLY", verbatim: "(a) New utilities get their portal address
#          (https://app.bynry.com/brazosbend/portal). Existing utilities keep
#          what they have and can edit it." · core.public_origin (DEF-CWP-9717)
#          · CLAUDE.md hard-won law 3 (defaults fail closed)
# ───────────────────────────────────────────────────────
"""A new utility's website is its PORTAL ADDRESS.

Sign-up seeded `https://smartbillhub.com/<slug>`, a host this product does not
serve, and seven customer messages print it as *"View or pay at
{utility_website}"*. From this ruling the default is `PUBLIC_APP_ORIGIN` +
`/<slug>/portal` — the same address Settings › Portal shows and its QR code
encodes. With no usable `PUBLIC_APP_ORIGIN` the website is left BLANK rather
than guessed (law 3). Existing utilities are not touched: there is no data
migration, and the value stays editable on Settings › Company.

PROVED RED FIRST (hard-won law 7), at 16f88e272:

    E  - https://app.bynry.com/brazosbend/portal
    E  + https://smartbillhub.com/brazosbend
    AssertionError: assert 'https://smartbillhub.com/brazosbend' is None   (x4, origin unset/malformed)
"""

import pytest

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant


@pytest.mark.django_db
def test_def_ten_9720__a_new_utility_gets_its_portal_address(growth_plan, identity_seam, settings):
    settings.PUBLIC_APP_ORIGIN = "https://app.bynry.com"
    tenant, _ = provisioned_tenant()
    assert tenant.subdomain == "brazosbend"
    assert tenant.website == "https://app.bynry.com/brazosbend/portal"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "origin", ["", "https://app.bynry.com/", "app.bynry.com", "https://*.bynry.com"]
)
def test_def_ten_9720__no_usable_public_origin_leaves_it_blank(
    growth_plan, identity_seam, settings, origin
):
    """Fail closed: unset or malformed (`core.public_origin`'s own refusals)
    writes nothing rather than a wrong address."""
    settings.PUBLIC_APP_ORIGIN = origin
    tenant, _ = provisioned_tenant()
    assert tenant.website is None


def test_def_ten_9720__there_is_no_data_migration_rewriting_existing_websites():
    """'Existing utilities keep what they have': no migration in tenancy writes
    `website`. A migration that did would rewrite a value a utility may have
    edited and already sent."""
    from pathlib import Path

    migrations = Path(__file__).resolve().parents[1] / "apps" / "tenancy" / "migrations"
    writers = [
        path.name
        for path in migrations.glob("*.py")
        if "website" in path.read_text(encoding="utf-8") and "9720" in path.name
    ]
    assert writers == []

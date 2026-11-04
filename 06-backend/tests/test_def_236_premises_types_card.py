# ── Trace ──────────────────────────────────────────────
# Change:   CR-010 items 2+3 (PO 2026-08-17) — DEF-235 · DEF-236
# Rules:    BR-MET-034 · BR-TEN-029/030/031/034/036
# Tests:    this file IS the durable guard both defect rows asked for
# Impacts:  apps/metering/lookups.py · 07-frontend referenceDataConfig.ts
# ───────────────────────────────────────────────────────
"""DEF-236's handler tests, and THE GUARD THAT CLOSES DEF-235 AND DEF-236 FROM
OPPOSITE DIRECTIONS.

The two defects were mirror images: `premises_types` had seeded rows and no
card (DEF-236), `account_statuses`/`account_types` had seeded rows and a card
claiming nothing was stored (DEF-235). Both survived because the declared-list
registry is a backend constant, the card grid is a frontend constant, and no
test compared the two. `test_every_declared_list_has_a_card` is that
comparison — a set equation over two files that are both already committed —
and it goes RED on either defect reintroduced.
"""

import json
import re
from pathlib import Path

import pytest

from apps.metering import lookups, models
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CONFIG_TS = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "features"
    / "tenancy"
    / "referenceDataConfig.ts"
)


def _frontend_cards() -> list[dict]:
    """The card entries, read straight out of the committed TS config.

    A regex over source is deliberate: importing a TS module from pytest would
    need a JS runtime, and the fields this guard reads (code · kind ·
    arrivesWithKey) are flat string literals. If the config's shape changes,
    this parser fails LOUD (zero cards), not quietly.
    """
    source = CONFIG_TS.read_text(encoding="utf-8")
    # Slice per card: from each `code: "…"` to the next one (or EOF). Nested
    # objects (`detailField: {…}`) make brace-matching regexes drop cards —
    # the first cut of this parser lost every card carrying one and reported
    # six live lists as doorless.
    hits = list(re.finditer(r"^\s{4}code:\s*\"([a-z_]+)\",", source, re.MULTILINE))
    cards = []
    for index, hit in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(source)
        body = source[hit.start() : end]
        kind = re.search(r"kind:\s*\"([a-z]+)\"", body)
        cards.append(
            {
                "code": hit.group(1),
                "kind": kind.group(1) if kind else None,
                "arrives": bool(re.search(r"^\s{4}arrivesWithKey:", body, re.MULTILINE)),
            }
        )
    assert cards, f"no cards parsed from {CONFIG_TS} — the guard's parser broke, fix IT first"
    return cards


# ═══════════════════════════════════════════════════════════════════════════
# THE JOIN GUARD — DEF-235 + DEF-236, one set equation each
# ═══════════════════════════════════════════════════════════════════════════


def test_every_declared_list_has_a_card__def_236():
    """DEF-236: a list in LOOKUP_LISTS with no frontend card is a vocabulary
    with no door. `premises_types` sat in exactly that state for seven days,
    reported only in a docstring."""
    declared = set(tenancy_services.LOOKUP_LISTS)
    card_codes = {card["code"] for card in _frontend_cards() if card["kind"] == "list"}
    doorless = declared - card_codes
    assert doorless == set(), (
        f"declared reference lists with NO card in referenceDataConfig.ts: {sorted(doorless)} "
        "— rows the operator cannot see, DEF-236's exact shape"
    )


def test_no_card_claims_absence_over_a_registered_handler__def_235():
    """DEF-235: a card carrying `arrivesWithKey` ("arrives with…", i.e. nothing
    here yet) over a list code whose handler IS registered is a contradiction
    the build can compute — both facts are exported constants. The account
    cards spent a week in that state while their lists sat seeded."""
    lying = sorted(
        card["code"]
        for card in _frontend_cards()
        if card["kind"] == "list"
        and card["arrives"]
        and card["code"] in tenancy_services.LOOKUP_LISTS
        and tenancy_services.LOOKUP_LISTS[card["code"]].handler is not None
    )
    assert lying == [], (
        f"cards claiming 'arrives with a future feature' over LIVE handlers: {lying} "
        "— the DEF-235 contradiction"
    )


def test_every_list_card_names_a_declared_list():
    """The reverse join: a list card for a code the backend never declared
    would render a door to nowhere. (Work cards pass by carrying
    `arrivesWithKey` and no declared list — the honest-promise state.)"""
    declared = set(tenancy_services.LOOKUP_LISTS)
    ghosts = sorted(
        card["code"]
        for card in _frontend_cards()
        if card["kind"] == "list" and not card["arrives"] and card["code"] not in declared
    )
    assert ghosts == [], f"list cards over undeclared lists: {ghosts}"


# ═══════════════════════════════════════════════════════════════════════════
# THE HANDLER — the standard lookup contract, against the seeded five
# ═══════════════════════════════════════════════════════════════════════════


def _seed(tenant):
    """Inside tenant_ctx — the catalog seeder reads the context, takes no arg."""
    from apps.metering import services as met_services

    return met_services.ensure_reference_catalogs()


def test_the_handler_is_registered_at_startup(brazos):
    definition = tenancy_services.LOOKUP_LISTS["premises_types"]
    assert definition.handler is not None, (
        "premises_types has no registered handler — DEF-236 is back"
    )
    assert definition.owner == "metering"


def test_the_card_counts_the_seeded_five(brazos):
    with tenant_ctx(brazos):
        _seed(brazos)
        handler = tenancy_services.LOOKUP_LISTS["premises_types"].handler
        assert handler.count() == 6  # BR-MET-034's seeded vocabulary (6 since CR-010 item 4)
        rows = {handler.serialize(row)["code"] for row in handler.search(None)}
    assert rows == {
        "apartment_complex",
        "commercial_building",
        "single_family",
        "mixed_use",
        "mobile_home_park",
        # CR-010 item 4 (PO 2026-08-17: "you can alos make them Govtment
        # building also") — BR-MET-034 amended 5 → 6 the same commit.
        "government_building",
    }


def test_a_tenant_can_add_its_own_type(brazos):
    """The harm DEF-236 named: a utility needing 'Farm' had no way to add it."""
    with tenant_ctx(brazos):
        _seed(brazos)
        handler = tenancy_services.LOOKUP_LISTS["premises_types"].handler
        row = handler.create({"code": "farm", "name": "Farm", "account_kind": "regular"})
        assert row.is_system is False
        assert handler.count() == 7


def test_a_seeded_row_deactivates_but_never_deletes(brazos):
    """BR-TEN-036, the same law every other seeded list enforces."""
    with tenant_ctx(brazos):
        _seed(brazos)
        handler = tenancy_services.LOOKUP_LISTS["premises_types"].handler
        seeded = handler.search("single").first()
        assert seeded is not None and seeded.is_system
        handler.set_active(seeded, False)
        assert handler.get(seeded.pk).active is False
        with pytest.raises(errors.BizError) as caught:
            handler.delete(seeded)
        assert caught.value.params["code"] == seeded.code


def test_used_by_is_live_so_the_delete_lock_bites(brazos, dana):
    """`premises.premises_type` is a PROTECTed FK, so used_by counts real rows
    and BR-TEN-030/034 are live from the first premises — never an honest 0
    pretending to be a guarantee."""
    from tests.test_us_met_helpers import make_premises

    with tenant_ctx(brazos):
        _seed(brazos)
        handler = tenancy_services.LOOKUP_LISTS["premises_types"].handler
        made = make_premises(dana, address_line="1 Guard St")
        used = models.Premises.objects.get(pk=made["id"]).premises_type
        assert handler.used_by(used) >= 1


def test_duplicate_codes_refuse_case_insensitively(brazos):
    with tenant_ctx(brazos):
        _seed(brazos)
        handler = tenancy_services.LOOKUP_LISTS["premises_types"].handler
        with pytest.raises(errors.ValidationError):
            handler.create({"code": "SINGLE_FAMILY", "name": "Duplicate", "account_kind": "regular"})


def test_isolation__lonestar_sees_only_its_own(brazos, lonestar):
    """Both tenants hold the STRUCTURAL five (provisioning seeds them,
    BR-TEN-067), so isolation is proved on the tenant's OWN extension: a row
    added in Brazos Bend must never surface in Lone Star's card."""
    handler = tenancy_services.LOOKUP_LISTS["premises_types"].handler
    with tenant_ctx(brazos):
        handler.create({"code": "farm", "name": "Farm", "account_kind": "regular"})
    with tenant_ctx(lonestar):
        assert handler.count() == 6  # its own structural six, nothing more
        codes = {handler.serialize(row)["code"] for row in handler.search(None)}
        assert "farm" not in codes  # the Brazos extension never leaks


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 items 2+3 / DEF-235 + DEF-236 (PO 2026-08-17)
# generated: 2026-08-17 by the CR-010 seeding lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: this file + SettingsReferenceData.test.tsx
# exceptions: the join guard parses the TS config by regex — deliberate, documented in _frontend_cards
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-10545 (portal a11y F-09, brand half)
# Rules:    decision log 2026-10-23 — "Group A: the new colours apply to the
#           whole product; a failing brand colour is both auto-corrected and
#           refused" (3a, 3b) · "Group A colour build: four judgments" (1)
# Mirrors:  07-frontend/src/lib/contrast.test.ts (same worked figures)
# ───────────────────────────────────────────────────────
"""Ruling 3(a) — the ink on a brand colour — and 3(b), Company → Profile
refusing a colour that reaches 4.5:1 with neither white nor the dark ink.

⚠ With today's inks (white, and black as the dark ink) no colour is refused:
every colour reaches at least 4.58:1 with one of them. So the refusal is
proved by MOVING the dark ink to the product's text ink `#201E1D`, under which
the sample `#EC3013` scores 4.20 / 3.95 and is refused — and the cube walk
proves the vacuity with the real inks, so neither half is assumed.
"""

import pytest

from apps.tenancy import brand, selectors, services
from core import errors
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def test_group_a_ink__the_sample_switches_to_the_dark_ink():
    assert round(brand.contrast_ratio(brand.INK_LIGHT, "#EC3013"), 2) == 4.20
    assert brand.brand_ink("#EC3013") == brand.INK_DARK
    assert round(brand.contrast_ratio(brand.INK_DARK, "#EC3013"), 2) == 5.00


def test_group_a_ink__a_dark_colour_keeps_white():
    assert brand.brand_ink("#1B5E9E") == brand.INK_LIGHT
    assert round(brand.contrast_ratio(brand.INK_LIGHT, "#1B5E9E"), 2) == 6.68


def test_group_a_refusal__with_todays_inks_no_colour_is_refused():
    refused = [
        f"#{r:02X}{g:02X}{b:02X}"
        for r in range(0, 256, 15)
        for g in range(0, 256, 15)
        for b in range(0, 256, 15)
        if brand.brand_colour_refused(f"#{r:02X}{g:02X}{b:02X}")
    ]
    assert refused == []


def test_group_a_refusal__fires_once_the_dark_ink_cannot_reach(monkeypatch):
    monkeypatch.setattr(brand, "INK_DARK", "#201E1D")
    assert round(brand.contrast_ratio("#201E1D", "#EC3013"), 2) == 3.95
    assert brand.brand_colour_refused("#EC3013") is True
    assert brand.brand_colour_refused("#1B5E9E") is False  # white 6.68
    assert brand.brand_colour_refused("#F5E9A0") is False  # light, dark ink passes
    assert brand.brand_colour_refused("not a colour") is False


def _save(changes):
    return services.save_company_profile(admin_actor(), changes)  # noqa: F405


def test_group_a_refusal__profile_refuses_a_new_failing_colour_by_name(growth_plan, identity_seam, monkeypatch):
    monkeypatch.setattr(brand, "INK_DARK", "#201E1D")
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as caught:
            _save({"brand_primary_hex": "#EC3013", "brand_accent_hex": "#1B5E9E"})
        field_errors = caught.value.field_errors
        assert [fe["field"] for fe in field_errors] == ["brand_primary_hex"]
        assert field_errors[0]["message_key"] == "settings.company.hex_contrast"
        # Nothing was written.
        assert selectors.company_profile()["brand_primary_hex"] != "#EC3013"


def test_group_a_refusal__an_unchanged_colour_is_never_refused(growth_plan, identity_seam, monkeypatch):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        _save({"brand_primary_hex": "#EC3013"})  # chosen before the rule
        monkeypatch.setattr(brand, "INK_DARK", "#201E1D")
        _save({"brand_primary_hex": "#EC3013", "dba_name": "Brazos Bend Utilities"})
        assert selectors.company_profile()["dba_name"] == "Brazos Bend Utilities"


def test_group_a_refusal__a_passing_colour_saves(growth_plan, identity_seam, monkeypatch):
    monkeypatch.setattr(brand, "INK_DARK", "#201E1D")
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        _save({"brand_primary_hex": "#1B5E9E"})
        assert selectors.company_profile()["brand_primary_hex"] == "#1B5E9E"


# ── Group A decision 3 (PO/QA 2026-10-23): too light for text or the ring ──


def test_group_a_too_light__the_worked_figures():
    assert brand.mix_with_black("#EC3013", 88) == "#D02A11"
    assert round(brand.contrast_ratio("#D02A11", "#FFFFFF"), 2) == 5.22
    assert round(brand.contrast_ratio("#D02A11", "#F3F2F2"), 2) == 4.67
    assert brand.mix_with_black("#F5C518", 88) == "#D8AD15"
    assert round(brand.contrast_ratio("#D8AD15", "#FFFFFF"), 2) == 2.12
    assert round(brand.contrast_ratio("#F5C518", "#FFFFFF"), 2) == 1.63
    assert round(brand.contrast_ratio("#F5C518", "#F3F2F2"), 2) == 1.46
    assert brand.brand_colour_too_light("#F5C518") is True
    assert brand.brand_colour_too_light("#EC3013") is False
    assert brand.brand_colour_too_light("#E8590C") is False  # 4.50; ring 3.58 / 3.20
    assert brand.brand_colour_too_light("#1B5E9E") is False
    # The ring refuses too: #2A9D8F's ring is 2.97 on #f3f2f2 (its shade 4.19).
    assert brand.brand_colour_too_light("#2A9D8F") is True
    assert brand.brand_colour_too_light("not a colour") is False


def test_group_a_too_light__profile_refuses_a_new_light_primary_and_says_why(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as caught:
            _save({"brand_primary_hex": "#F5C518"})
        field_errors = caught.value.field_errors
        assert [fe["field"] for fe in field_errors] == ["brand_primary_hex"]
        assert field_errors[0]["message_key"] == "settings.company.hex_too_light"
        assert selectors.company_profile()["brand_primary_hex"] != "#F5C518"


def test_group_a_too_light__the_accent_colour_is_not_read_as_text(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        _save({"brand_primary_hex": "#1B5E9E", "brand_accent_hex": "#F5C518"})
        assert selectors.company_profile()["brand_accent_hex"] == "#F5C518"


def test_group_a_too_light__an_unchanged_light_colour_is_never_refused(growth_plan, identity_seam, monkeypatch):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with monkeypatch.context() as before_the_rule:
            before_the_rule.setattr(brand, "brand_colour_too_light", lambda value: False)
            _save({"brand_primary_hex": "#F5C518"})  # chosen before the rule
        _save({"brand_primary_hex": "#F5C518", "dba_name": "Brazos Bend Utilities"})
        assert selectors.company_profile()["dba_name"] == "Brazos Bend Utilities"


def test_group_a_too_light__the_message_is_in_all_eleven_catalogues():
    import json
    from pathlib import Path

    locales = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11
    for path in files:
        assert json.loads(path.read_text(encoding="utf-8")).get("settings.company.hex_too_light"), path.name

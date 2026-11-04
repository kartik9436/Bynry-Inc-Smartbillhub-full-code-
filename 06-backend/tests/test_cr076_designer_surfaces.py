# ── Trace ──────────────────────────────────────────────
# Change:  CR-076 item 1 — SET-10's preview surface switcher. PO, on the
#          hardcoded list they had proposed themselves: *"you are correct -
#          dont use hard coding"*.
# Screens: SET-10 (the template designer)
# Rules:   BR-SHL-010 (an undeclared capability is not rendered) ·
#          BR-SHL-025 (a control that cannot act renders with its reason) ·
#          CLAUDE.md hard-won law 2 (built is not wired — a hand-typed list of
#          five is how the eleventh service never reached the sign-up screen)
# ───────────────────────────────────────────────────────
"""WHICH SURFACES ONE TEMPLATE IS A FORM FOR, DERIVED AND SERVED.

The designer can now preview one template as each of the surfaces it actually
has. The list is **derived from `CHANNELS_BY_KIND`**, which is the only place in
this repo that says what a `kind` string like *"Print + email"* MEANS, and it is
served on the detail payload so that no screen types it out.

**The defect these cases are written against is a hardcoded five.** A tab bar
carrying `printable · email · sms · in_app · contract` as a constant offers an
empty SMS tab on a letter, and goes on offering exactly five on the day a sixth
surface exists. That is the sign-up screen's eleventh service one screen along:
the row exists, the API serves it, every check passes, and the screen is wrong.

So the cases below assert the two directions that a constant cannot satisfy at
once — a two-surface class serves TWO, and a one-surface class serves ONE —
plus the two that keep the derivation honest: it never invents a surface a class
has no channel for, and an unstated `kind` serves NOTHING rather than a guess.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.notifications import catalogs, seed_templates, templates_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: A class whose `kind` names TWO channels — the whole reason this exists. The
#: 10-day disconnect notice is posted AND emailed, so a person checking the
#: regulated wording has two documents to look at and could only ever see one.
TWO_SURFACE_CODE = "disconnect_notice_10_day"
#: A class with exactly one. `sms_bill_ready` is a text message and nothing else.
ONE_SURFACE_CODE = "sms_bill_ready"
#: A CONTRACT, which prints on `pdf_print` like a letter and is a different
#: document to look at — the one place the channel does not name the surface.
CONTRACT_CODE = "contract_payment_plan"

SEED_DATE = date(2026, 8, 30)


def _detail(tenant, actor, code):
    with tenant_ctx(tenant):
        seed_templates.seed_notice_templates(actor, on_date=SEED_DATE)
        response = api_call(
            templates_api.template_detail,
            "get",
            user=getattr(actor, "user", None),
            role="system_admin",
            tenant=tenant,
            code=code,
        )
    assert response.status_code == 200
    return response.data


# ══════════════════════════════════════════════════════════════════════════
# WHAT THE PAYLOAD SAYS
# ══════════════════════════════════════════════════════════════════════════
def test_cr076__a_notice_that_is_posted_and_emailed_serves_both_surfaces(brazos, dana):
    """The 10-day disconnect notice is *"Print + email"*, so it serves two.

    This is the PO's own complaint in one assertion: the notice exists as a
    printed letter and as an email, and before CR-076 the screen could only ever
    draw one of them.
    """
    data = _detail(brazos, dana, TWO_SURFACE_CODE)
    assert data["preview_surfaces"] == ["printable", "email"]


def test_cr076__a_text_message_serves_one_surface_and_not_five(brazos, dana):
    """⚠ THE CASE A HARDCODED LIST FAILS. `sms_bill_ready` has no printed form,
    no email form and no in-app form, and a tab bar built from a constant would
    offer all three."""
    data = _detail(brazos, dana, ONE_SURFACE_CODE)
    assert data["preview_surfaces"] == ["sms"]
    for absent in ("printable", "email", "in_app", "contract"):
        assert absent not in data["preview_surfaces"]


def test_cr076__a_contract_prints_as_a_contract_and_not_as_a_letter(brazos, dana):
    """`pdf_print` is the CHANNEL; the SURFACE depends on the class's group.

    A payment-plan agreement is *"PDF + email"* — the same two channels as a
    disconnect notice — and it is not the same document to look at.
    """
    data = _detail(brazos, dana, CONTRACT_CODE)
    assert data["preview_surfaces"] == ["contract", "email"]


# ══════════════════════════════════════════════════════════════════════════
# WHAT THE DERIVATION REFUSES TO DO
# ══════════════════════════════════════════════════════════════════════════
def test_cr076__every_seeded_class_derives_a_surface_it_can_actually_draw():
    """No class serves a surface the designer has no drawing for, and none
    serves an empty list.

    Swept over the whole catalog rather than sampled: the value of a derivation
    is that it stays true for rows nobody thought about, and the only way to
    claim that is to look at all of them.

    ⚠ **THE SECOND HALF OF THIS CASE IS THE ONE THAT EARNS ITS KEEP, AND IT IS
    A GUARD ACROSS TWO LANGUAGES.** The screen filters the served list down to
    the surfaces it can draw, so a SIXTH surface added here would be dropped by
    the client in silence — the row exists, the API serves it, `tsc` and every
    test pass, and the tab never appears. That is hard-won law 2 exactly, in the
    one direction the "don't hardcode" ruling does not cover. So the derivable
    set is asserted to be exactly the five `DesignerKind` names in
    `07-frontend/src/features/notifications/TemplateDetail.tsx`: adding a
    channel here goes RED, here, naming the file to change.

    ⚠ It is also the one case in this file that a hardcoded five PASSES — the
    sabotage that proves the others red leaves this one green, correctly,
    because five drawable names are five drawable names. It is not evidence the
    derivation works; the three above are.
    """
    #: The `DesignerKind` union, quoted. Kept as a literal ON PURPOSE: a copy
    #: that drifts is the failure this case exists to catch, so it must be
    #: written out rather than derived from the thing it is checking.
    drawable = {"printable", "email", "sms", "in_app", "contract"}
    assert set(catalogs.SURFACE_BY_CHANNEL.values()) | {catalogs.SURFACE_CONTRACT} == drawable, (
        "a surface this catalog can derive is not one the designer draws — add it to "
        "`DesignerKind` and `PreviewBody` in TemplateDetail.tsx, or the tab silently "
        "never appears"
    )
    for code, listing in catalogs.LISTINGS.items():
        klass = catalogs.catalog_for(code)
        surfaces = templates_api._surfaces_for(listing, klass)
        assert surfaces, f"{code} ({listing.kind!r}) derives no surface at all"
        assert set(surfaces) <= drawable, f"{code} derives {surfaces}, which nothing draws"
        assert len(set(surfaces)) == len(surfaces), f"{code} repeats a surface: {surfaces}"


def test_cr076__a_kind_nobody_has_stated_channels_for_serves_nothing(brazos, dana):
    """The unknown case fails to ONE SURFACE, not to five and not to a 500.

    `designer_surfaces` raises for an unstated kind and is right to — a class
    whose channels nobody has written down must not quietly acquire a set. What
    must not happen is the whole designer going down over a tab bar, so the
    payload serves `[]` and the screen's rule for `[]` is *draw no switcher and
    preview the one surface you drew before this field existed*.
    """
    invented = catalogs.TemplateListing(
        code="whatever",
        name="Whatever · something",
        category="Billing",
        category_source="this test",
        kind="Semaphore",
        used_by="nothing",
    )
    with pytest.raises(catalogs.UnknownTemplateKind):
        catalogs.designer_surfaces(invented.kind, None)
    assert templates_api._surfaces_for(invented, None) == ()

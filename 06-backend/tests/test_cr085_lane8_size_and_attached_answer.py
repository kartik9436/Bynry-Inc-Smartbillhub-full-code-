# ── Trace ──────────────────────────────────────────────
# Change:   CR-085 step 2 lane 8 — usage, readings, equipment and asking us
#           something. Screens CWP-033 · CWP-034 · CWP-037.
# Defects:  DEF-CWP-4848 — `CWP-037` never draws `size_class`, so the ONE row
#           carrying a monthly charge is the one row whose charge cannot be
#           checked; and the equipment name stutters where the registry already
#           names the thing after its service (*Fire Fire service line*).
#           DEF-CWP-3945 — `ALSO_SHOW_SCREENS` is ("bill", "usage", "overdue")
#           and the `usage` placement went nowhere: a clerk ticked *also show
#           this on the Usage screen*, the row was written, and no customer
#           could ever see it.
# Rules:    CLAUDE.md fire rule (`CR-063`, PO 2026-09-02/03 — the SIZE CLASS
#           picks the price and the COUNT multiplies it; fire is SIX sizes
#           after `HYD` was withdrawn) · BR-RAT-090 · BR-CWP-093 (nothing empty
#           ever appears) · B14 rule 32 (no internal code in clerk-facing copy)
# Tests:    this file
# Impacts:  apps/portal/selectors.py `_equipment_row`, `account_usage` ·
#           apps/portal/api.py `account_usage` ·
#           07-frontend/src/portal/usage/Equipment.tsx · usage/Usage.tsx
# ───────────────────────────────────────────────────────
"""The two server halves lane 8 was missing, each asserted where it was missing.

⚠ **BOTH ARE ABSENCES, WHICH IS WHY NEITHER HAD A TEST.** `size_class` has been
on the wire and in the TypeScript interface since `CWP-037` was built, so `tsc`
has nothing to say about a field nobody reads; `attached_answer` was a column, a
clerk screen, a seam and a card with no line joining them. An absence is
invisible to every check this repo has — which is `DEF-CWP-3945`'s own
`escape_reason`, written six days before this file.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.portal import selectors
from apps.portal.seams import tenancy_seam
from core.tenancy import tenant_context

from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

TODAY = date(2026, 9, 2)


class _Principal:
    def __init__(self, tenant_id, account_ids):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)
        self.accounts = ()


def _row(service: str, kind: str, size_class: str | None):
    """One `equipment_on_unit` row, as `metering.portal_reads` hands it over."""
    return {
        "serial_no": "F-0118",
        "asset_no": None,
        "kind": kind,
        "kind_code": "fire_line",
        "category": "behind_the_meter",
        "service": service,
        "where": None,
        "fitted_on": "2026-06-02",
        "status": "Installed",
        "status_code": "active",
        "behavior_class": "in_service",
        "test_due_on": None,
        "test_due": False,
        "size_class": size_class,
        "last_read_on": None,
        "maintained_by": "utility",
    }


# ══════════════════════════════════════════════════════════════════════════
# DEF-CWP-4848 · THE SIZE A CUSTOMER CAN CHECK THEIR CHARGE AGAINST
# ══════════════════════════════════════════════════════════════════════════
def test_a_fire_lines_size_code_is_served_as_its_ratified_NAME():
    """⚠ **`FL-2` IS NOT A THING TO PUT ON A CUSTOMER'S SCREEN** (B14 rule 32 —
    no internal code in clerk-facing copy), which is why the screen has drawn
    the size nowhere at all rather than drawing the code. The ratified
    vocabulary is what names it, and it is the SAME call `_billed_on` makes one
    screen along for the *your 96 gal cart* sentence — two answers to *what is
    an `FL-2`* is the drift `DEF-CWP-3655` records.

    ⚠ **FIRE IS WHERE THIS COSTS SOMETHING.** CLAUDE.md's fire rule is that the
    SIZE CLASS PICKS THE PRICE and the COUNT multiplies it, so a fire line is
    the one row on `CWP-037` with a monthly charge, and until today it was also
    the one row whose charge could not be checked against anything the screen
    said.
    """
    sizes = {"fire": tenancy_seam.size_class_names("fire")}
    out = selectors._equipment_row(
        _row("fire", "Fire service line", "FL-2"),
        {"fire": "Fire"},
        {"fire": tenancy_seam.BASIS_CAPACITY},
        {"fire": None},
        sizes,
    )
    assert out["size_class_name"] == 'Fire line 2"'
    #: The CODE still travels — the walkthroughs and the staff side key on it —
    #: and it is the NAME the screen draws.
    assert out["size_class"] == "FL-2"


def test_the_six_ratified_fire_diameters_all_resolve_and_the_withdrawn_hydrant_does_not():
    """⚠ **SIX, NOT SEVEN** — the PO withdrew `HYD` *"Private hydrant"* on
    2026-09-03 (*"remove private hydrants from list"*), and a lookup that
    happily named a withdrawn row would put a size on a customer's screen the
    product no longer bills."""
    names = tenancy_seam.size_class_names("fire")
    assert len(names) == 6
    assert list(names) == ["FL-2", "FL-4", "FL-6", "FL-8", "FL-10", "FL-12"]
    assert "HYD" not in names


def test_an_unnamed_size_code_answers_NONE_rather_than_echoing_the_code():
    """⚠ **THE FALLBACK IS THE DEFECT, NOT THE FIX.** Falling back to the code
    would print `FL-99` to a customer, which is the exact breach this field
    exists to avoid. An absence the screen closes up (`BR-CWP-093`) is the
    honest answer, and it is what a tenant with an unruled service gets too —
    `size_class_names` returns an empty map for one.
    """
    sizes = {"fire": tenancy_seam.size_class_names("fire")}
    out = selectors._equipment_row(
        _row("fire", "Fire service line", "FL-99"), {}, {}, {}, sizes
    )
    assert out["size_class_name"] is None

    #: …and a row with no size class at all is the ordinary case, not an error.
    bare = selectors._equipment_row(_row("water", "Meter", None), {}, {}, {}, sizes)
    assert bare["size_class_name"] is None


# ══════════════════════════════════════════════════════════════════════════
# DEF-CWP-3945 · THE THIRD PLACEMENT — `usage`
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_an_answer_pinned_to_usage_reaches_the_usage_payload(pine_hill, sarah):
    """⚠ **THE MIRROR OF A TEST THAT ALREADY PASSED, AND THAT IS THE POINT.**
    `test_def_cwp_3945_attached_answer.py` publishes an answer pinned to `usage`
    and asserts it does NOT leak onto the overdue screen — correctly, and it
    passed while the usage screen had no such field at all. So the negative case
    was green for the wrong reason: the answer reached nowhere, not just not
    there.
    """
    from tests.test_def_cwp_3945_attached_answer import _publish_answer

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _publish_answer(pine_hill, sarah, question="How do I read my meter?", screen="usage")

    with tenant_context(pine_hill.id):
        body = selectors.account_usage(
            _Principal(pine_hill.id, [account.pk]), account, today=TODAY, locale="en"
        )

    assert body["attached_answer"] is not None
    assert body["attached_answer"]["question"] == "How do I read my meter?"
    #: The BODY travels too — a question with nothing under it is the empty card
    #: `BR-CWP-093` forbids.
    assert body["attached_answer"]["body"]
    #: ⚠ **THE SLUG IS THE ADDRESS THE CARD LINKS TO** — never a uuid (rule 31).
    assert body["attached_answer"]["slug"] == "how-do-i-read-my-meter"


@pytest.mark.django_db
def test_an_answer_pinned_to_the_bill_does_not_leak_onto_usage(pine_hill, sarah):
    """The assertion that makes the one above mean anything: a reader returning
    the first published answer whatever its pin would pass every positive case
    and put the wrong answer under every screen."""
    from tests.test_def_cwp_3945_attached_answer import _publish_answer

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _publish_answer(pine_hill, sarah, question="Why is my bill higher?", screen="bill")

    with tenant_context(pine_hill.id):
        body = selectors.account_usage(
            _Principal(pine_hill.id, [account.pk]), account, today=TODAY, locale="en"
        )

    assert "attached_answer" in body, "the key is always present; the VALUE is the absence"
    assert body["attached_answer"] is None
